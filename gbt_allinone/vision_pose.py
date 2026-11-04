# -*- coding: utf-8 -*-
"""vision_pose -- 人体姿态（17 关键点，ONNX 路线，**不依赖 torch**）

背景：19 位视觉里 `pose` 一直缺依赖（要 torch + ultralytics，约 200MB~1GB）。
但 YOLO11n-pose 导出的 onnx 只有 **11.3MB**，onnxruntime 本机早就装好了 ——
和 `vision_detect` 是同一套做法，所以这条补齐路最短。

模型：state/models/yolo11n-pose.onnx（ultralytics v8.3.0 assets）
  sha256 93e2866b0ce678f99b4dd88af0c12e9ea2edf079a361dc2ecbc6226b77ff6408
输入：images (1,3,640,640) float32
输出：output0 (1,56,8400) = 4 框 + 1 置信 + 17×3 关键点(x,y,vis)

── 铁律 ──────────────────────────────────────────────
1. **只回坐标与判定，绝不回图**。
2. **不做假阳性**：低于置信门槛一律不回；没人就如实 `count=0`。
3. **中文路径安全**：复用 vision_detect 的 imdecode 读图。
4. **不假装能懂语义**：这里只给几何（关键点位置 + 由位置推的粗判定），
   不回答「他在干什么」这种需要时序/语义的问题。
"""
from __future__ import annotations

import os
import threading

MODEL_REL = "state/models/yolo11n-pose.onnx"
ENV_MODEL = "GBT_YOLO_POSE_ONNX"

# COCO 17 关键点（顺序固定，别改）
KP17 = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
KP_CN = {
    "nose": "鼻", "left_eye": "左眼", "right_eye": "右眼", "left_ear": "左耳",
    "right_ear": "右耳", "left_shoulder": "左肩", "right_shoulder": "右肩",
    "left_elbow": "左肘", "right_elbow": "右肘", "left_wrist": "左手", "right_wrist": "右手",
    "left_hip": "左髋", "right_hip": "右髋", "left_knee": "左膝", "right_knee": "右膝",
    "left_ankle": "左踝", "right_ankle": "右踝",
}

_SESSION = None
_SESSION_PATH = None
_LOCK = threading.Lock()


def _payload_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def model_path() -> str:
    override = os.environ.get(ENV_MODEL)
    if override:
        return override
    return os.path.join(_payload_root(), *MODEL_REL.split("/"))


def model_ready() -> bool:
    p = model_path()
    return os.path.exists(p) and os.path.getsize(p) > 1_000_000


def _session():
    global _SESSION, _SESSION_PATH
    with _LOCK:
        path = model_path()
        if _SESSION is not None and _SESSION_PATH == path:
            return _SESSION
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _SESSION = ort.InferenceSession(path, sess_options=so,
                                        providers=["CPUExecutionProvider"])
        _SESSION_PATH = path
        return _SESSION


def _judge(person: dict, thr_vis: float = 0.5) -> dict:
    """由关键点位置推**粗判定**。只做几何，不做语义 —— 越界的话宁可不判。"""
    kp = person["keypoints"]
    def pt(name):
        k = kp.get(name) or {}
        return (k.get("x"), k.get("y")) if (k.get("vis") or 0) >= thr_vis else (None, None)

    out = {}
    lw, rw = pt("left_wrist"), pt("right_wrist")
    ls, rs = pt("left_shoulder"), pt("right_shoulder")
    lh, rh = pt("left_hip"), pt("right_hip")

    # 举手：手腕比肩膀更靠上（y 更小）
    hands = []
    if lw[1] is not None and ls[1] is not None and lw[1] < ls[1]:
        hands.append("左手举起")
    if rw[1] is not None and rs[1] is not None and rw[1] < rs[1]:
        hands.append("右手举起")
    if hands:
        out["hands"] = hands

    # 站/坐：必须**看到脚踝**才判 —— 实测踩过：bus.jpg 里站着的人被挡到膝下，
    # 只拿髋-膝距离算，腿被低估，三个人全被判成「坐/俯身」。看不到脚就不该判。
    sh_y = [v for v in (ls[1], rs[1]) if v is not None]
    hip_y = [v for v in (lh[1], rh[1]) if v is not None]
    la, ra = pt("left_ankle"), pt("right_ankle")
    ankle_y = [v for v in (la[1], ra[1]) if v is not None]
    if sh_y and hip_y and ankle_y:
        torso = max(hip_y) - min(sh_y)
        leg = max(ankle_y) - max(hip_y)
        if torso > 0 and leg > 0:
            ratio = leg / torso
            out["posture"] = "站立（腿伸展）" if ratio >= 0.95 else "坐/俯身（腿收拢）"
            out["leg_torso_ratio"] = round(ratio, 2)
    elif sh_y and hip_y:
        out["posture"] = "未判（看不到脚踝）"

    # 是否正对镜头：双肩可见且水平差不大
    if ls[1] is not None and rs[1] is not None and ls[0] is not None and rs[0] is not None:
        dx = abs(rs[0] - ls[0])
        dy = abs(rs[1] - ls[1])
        if dx > 0:
            out["facing"] = "正面" if dy / dx < 0.35 else "侧身/倾斜"
    return out


def pose(image: str, conf: float = 0.35, kp_vis: float = 0.5, max_people: int = 8) -> dict:
    """取人体 17 关键点。回每人 bbox + 17 点 + 粗判定。"""
    if not image:
        return {"ok": False, "reason": "需要 image：本地图片路径"}
    if not model_ready():
        return {"ok": False, "status": "needs_dependency",
                "reason": "缺模型: %s（11.3MB，可设 %s 指定别处）" % (model_path(), ENV_MODEL)}

    try:
        import numpy as np
        from . import vision_detect as VD
        img = VD._imread(image)
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "reason": "读图失败: %s: %s" % (type(exc).__name__, str(exc)[:140])}

    import time
    t0 = time.time()
    padded, r, left, top = VD._letterbox(img, 640)
    blob = padded[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    blob = np.ascontiguousarray(blob[None])

    try:
        sess = _session()
        out = sess.run(None, {sess.get_inputs()[0].name: blob})[0]
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "reason": "推理失败: %s: %s" % (type(exc).__name__, str(exc)[:140])}

    # (1,56,8400) -> (8400,56)
    pred = out[0].T
    scores = pred[:, 4]
    idx = np.where(scores >= float(conf))[0]
    if idx.size == 0:
        return {"ok": True, "count": 0, "people": [],
                "elapsed_ms": int((time.time() - t0) * 1000),
                "note": "画面里没检出人（阈值 %.2f）" % conf}

    boxes = pred[idx, 0:4]
    sc = scores[idx]
    # cx,cy,w,h -> x1,y1,x2,y2
    xy = np.empty_like(boxes)
    xy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
    xy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
    xy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
    xy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2
    keep = VD._nms(xy, sc, 0.45)

    ih, iw = img.shape[:2]
    people = []
    for i in keep[:max_people]:
        b = xy[i]
        # letterbox 坐标 -> 原图坐标
        x1 = max(0.0, (b[0] - left) / r)
        y1 = max(0.0, (b[1] - top) / r)
        x2 = min(float(iw - 1), (b[2] - left) / r)
        y2 = min(float(ih - 1), (b[3] - top) / r)
        if x2 <= x1 or y2 <= y1:
            continue

        kraw = pred[idx[i], 5:56].reshape(17, 3)
        kps = {}
        for j, name in enumerate(KP17):
            vx, vy, vv = float(kraw[j, 0]), float(kraw[j, 1]), float(kraw[j, 2])
            if vv < 0.05:
                continue
            kps[name] = {"x": int(max(0, min(iw - 1, (vx - left) / r))),
                         "y": int(max(0, min(ih - 1, (vy - top) / r))),
                         "vis": round(vv, 3), "cn": KP_CN.get(name, name)}

        person = {"score": round(float(sc[i]), 3),
                  "box": {"x": int(x1), "y": int(y1),
                          "w": int(x2 - x1), "h": int(y2 - y1)},
                  "cx": int((x1 + x2) / 2), "cy": int((y1 + y2) / 2),
                  "keypoints": kps}
        person.update(_judge(person, kp_vis))
        people.append(person)

    people.sort(key=lambda p: -p["score"])
    return {"ok": True, "count": len(people), "people": people,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "backend": "onnx-yolo11n-pose",
            "note": "只给几何与粗判定；「在干什么」属于语义，本模块不回答"}


def status() -> dict:
    return {"ok": True, "model_ready": model_ready(), "model": model_path(),
            "size_mb": round(os.path.getsize(model_path()) / 1024 / 1024, 1)
            if model_ready() else None,
            "keypoints": len(KP17), "backend": "onnxruntime(CPU) · 零 torch",
            "ops": ["pose", "status"],
            "limits": "只做几何判定（举手/站坐/正面）；不做动作识别、不做多人交互关系"}


def run(op: str = "pose", **kw) -> dict:
    o = str(op or "pose").strip()
    if o in ("status", "health"):
        return status()
    if o in ("pose", "keypoints", "skeleton"):
        return pose(kw.get("image") or kw.get("path") or "",
                    float(kw.get("conf") or 0.35),
                    float(kw.get("kp_vis") or 0.5),
                    int(kw.get("max_people") or 8))
    return {"ok": False, "reason": "未知 op: %s" % o, "supported": ["pose", "status"]}
