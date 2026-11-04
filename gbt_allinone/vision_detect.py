# -*- coding: utf-8 -*-
"""vision_detect -- YOLO 目标检测（ONNX 路线，不依赖 torch）

为什么要 ONNX：本机没有 torch（装它要 ~200MB），但 onnxruntime 早就装好了。
YOLO11n 导出的 onnx 只有 10.4MB，纯 CPU 就能跑 —— 这是补「找」这一组的最短路径。

模型：state/models/yolo11n.onnx（ultralytics v8.3.0 assets，sha256 前 32 位 634279b40c07c6391472c51ad45b81eb）
输入：images (1,3,H,W) float32 · 输出：output0 (1,84,8400) = 4 框 + 80 类

── 铁律 ──────────────────────────────────────────────
1. **只回坐标与类名，绝不回图**（图片本体永不进上下文）。
2. **不做假阳性**：置信度门槛可调，低于门槛一律不回；没有检测到就如实回 count=0。
3. **中文路径安全**：cv2.imread 在非 ASCII 路径直接返回 None，统一走 imdecode。
"""
from __future__ import annotations

import os
import threading

MODEL_REL = "state/models/yolo11n.onnx"
ENV_MODEL = "GBT_YOLO_ONNX"

COCO80 = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
]

# 界面类截图里最常出现的几类，给个中文，其余保留英文（不硬翻）
CN = {
    "person": "人", "laptop": "笔记本电脑", "tv": "显示器/屏幕", "cell phone": "手机",
    "keyboard": "键盘", "mouse": "鼠标", "book": "书/文档", "cup": "杯子", "chair": "椅子",
    "dining table": "桌子", "clock": "时钟", "remote": "遥控器", "scissors": "剪刀",
    "bottle": "瓶子", "backpack": "背包", "handbag": "包", "potted plant": "绿植",
    "cat": "猫", "dog": "狗", "car": "汽车", "bus": "公交车", "bicycle": "自行车",
    "traffic light": "红绿灯", "umbrella": "雨伞", "vase": "花瓶", "bowl": "碗",
    "banana": "香蕉", "apple": "苹果", "sandwich": "三明治", "pizza": "披萨",
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
    """懒加载 + 复用。模型 10MB，加载一次约几百毫秒，不要每次重开。"""
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


def _imread(path: str):
    """中文路径安全的读图。"""
    import cv2
    import numpy as np
    if not os.path.exists(path):
        raise FileNotFoundError("图片不存在: %s" % path)
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("解不开这张图（格式不支持？）: %s" % path)
    return img


def _letterbox(img, new: int = 640, color=(114, 114, 114)):
    import cv2
    h, w = img.shape[:2]
    r = min(new / float(h), new / float(w))
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    top, left = (new - nh) // 2, (new - nw) // 2
    padded = cv2.copyMakeBorder(resized, top, new - nh - top, left, new - nw - left,
                                cv2.BORDER_CONSTANT, value=color)
    return padded, r, left, top


def _nms(boxes, scores, iou_thr: float):
    """纯 numpy NMS，避免依赖 cv2.dnn 的 API 差异。"""
    import numpy as np
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_thr]
    return keep


def detect(image: str, conf: float = 0.25, iou: float = 0.45,
           max_det: int = 50, imgsz: int = 640, only=None) -> dict:
    """在本地图片上做目标检测。回坐标+类名，不回图。

    only: 可选，只保留这些类名（如 ["person","laptop"]）
    """
    if not image:
        return {"ok": False, "reason": "需要 image：本地截图路径"}
    if not model_ready():
        return {"ok": False, "status": "needs_dependency",
                "reason": "缺模型文件: %s（可设环境变量 %s 指定别处）" % (model_path(), ENV_MODEL)}

    import numpy as np
    sess = _session()
    img = _imread(image)
    oh, ow = img.shape[:2]

    padded, ratio, dx, dy = _letterbox(img, imgsz)
    blob = padded[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    out = sess.run(None, {sess.get_inputs()[0].name: blob})[0]   # (1, 84, N)

    pred = out[0].T                                              # (N, 84)
    boxes_cxcywh = pred[:, :4]
    cls_scores = pred[:, 4:]
    cls_ids = cls_scores.argmax(axis=1)
    scores = cls_scores.max(axis=1)

    m = scores >= float(conf)
    boxes_cxcywh, scores, cls_ids = boxes_cxcywh[m], scores[m], cls_ids[m]
    if boxes_cxcywh.shape[0] == 0:
        return {"ok": True, "backend": "yolo11n-onnx", "count": 0, "detections": [],
                "image_size": [ow, oh], "note": "置信度门槛 %.2f 下无检出" % conf}

    # cxcywh(letterbox 坐标) -> xyxy(原图坐标)
    cx, cy, bw, bh = (boxes_cxcywh[:, i] for i in range(4))
    x1 = (cx - bw / 2 - dx) / ratio
    y1 = (cy - bh / 2 - dy) / ratio
    x2 = (cx + bw / 2 - dx) / ratio
    y2 = (cy + bh / 2 - dy) / ratio
    boxes = np.stack([x1, y1, x2, y2], axis=1)
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, ow)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, oh)

    keep = _nms(boxes, scores, float(iou))
    dets = []
    wanted = set(x.lower() for x in only) if only else None
    for idx in keep:
        ci = int(cls_ids[idx])
        name = COCO80[ci] if 0 <= ci < len(COCO80) else "class_%d" % ci
        if wanted and name.lower() not in wanted:
            continue
        bx1, by1, bx2, by2 = [float(v) for v in boxes[idx]]
        dets.append({
            "name": name, "name_cn": CN.get(name),
            "class_id": ci, "score": round(float(scores[idx]), 4),
            "x": round(bx1, 1), "y": round(by1, 1),
            "w": round(bx2 - bx1, 1), "h": round(by2 - by1, 1),
            "cx": round((bx1 + bx2) / 2, 1), "cy": round((by1 + by2) / 2, 1),
        })
        if len(dets) >= int(max_det):
            break

    summary: dict = {}
    for d in dets:
        summary[d["name"]] = summary.get(d["name"], 0) + 1

    return {"ok": True, "backend": "yolo11n-onnx", "count": len(dets),
            "image_size": [ow, oh], "conf": conf, "iou": iou,
            "summary": summary, "detections": dets}


def run(op: str = "detect", **kw) -> dict:
    if op in ("detect", "find", "boxes"):
        return detect(kw.get("image") or kw.get("path"),
                      float(kw.get("conf") or 0.25),
                      float(kw.get("iou") or 0.45),
                      int(kw.get("max_det") or 50),
                      int(kw.get("imgsz") or 640),
                      kw.get("only"))
    if op in ("status", "health"):
        return {"ok": True, "model": model_path(), "ready": model_ready(),
                "size_mb": round(os.path.getsize(model_path()) / 1e6, 2) if model_ready() else 0,
                "backend": "yolo11n-onnx"}
    return {"ok": False, "reason": "未知 op: %s（支持 detect/status）" % op}
