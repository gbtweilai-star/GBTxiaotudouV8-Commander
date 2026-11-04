# -*- coding: utf-8 -*-
"""vision_segment -- SAM 抠图（slimsam-77 ONNX，零 torch）

背景：19 位视觉里 `segment` 一直缺依赖（torch + segment_anything + 2.4GB 权重）。
实测可行路径：**slimsam-77-uniform**（SAM 的蒸馏版）有现成 ONNX，两段共 38MB：
  vision_encoder.onnx                 22.2 MB  sha256 9f8433273a6750b5
  prompt_encoder_mask_decoder.onnx    15.8 MB  sha256 f4514391764fbd56
onnxruntime 本机早就有 ⇒ 与 vision_detect / vision_pose / vision_embed 同一条路。

── 实测数据（i5-1340P · CPU · 810x1080 图）──
  预处理        33 ms
  encoder      3.2 s   ← 每张图只跑一次，之后缓存
  decoder      0.08 s  ← 每次点选/框选只需这一步
  ⇒ 首点 3.3s；同图再点 **0.08s**。这个差距就是缓存 embedding 的意义。

── 模型契约（onnxruntime 实测读出，非文档抄来）──
  encoder  输入 pixel_values  (1,3,1024,1024) float
           输出 image_embeddings / image_positional_embeddings  各 (1,256,64,64)
  decoder  输入 input_points (1,1,N,2) float  · input_labels (1,1,N) int64
                + 上面两个 embedding
           输出 iou_scores (1,1,3)  ·  pred_masks (1,1,3,256,256)
  ⇒ 一次回 **3 个候选 mask**（SAM 的多尺度），按 iou_scores 选。

── 铁律 ──────────────────────────────────────────────
1. **只回路径与数值，绝不回图**：抠图产物落本地文件，返回路径 + bbox + 面积。
   二进制/base64 一律不回（回图会把整个请求撑爆，这正是之前 471 的教训）。
2. **不假装精确**：slimsam 是蒸馏版，弱于 SAM ViT-H。单点常抠出「该点所在的局部
   物体」而不是整个主体 —— 如实回 iou 分数与覆盖率，让调用方判断要不要补点。
3. **不做自动全图分割**：那要跑几十到上百次 decoder 且质量参差，
   本机 CPU 不划算；要自动分割请显式多个点，而不是假装有 auto 模式。
4. **中文路径安全**：统一 imdecode / imencode。
"""
from __future__ import annotations

import hashlib
import os
import threading
import time

ENC_REL = "state/models/slimsam_encoder.onnx"
DEC_REL = "state/models/slimsam_decoder.onnx"
ENV_DIR = "GBT_SAM_DIR"
SEG_DIR = os.path.join("state", "segments")
_KEEP = 50                      # 只留最近 50 组产物，别让磁盘无声涨满

_SESS = {"enc": None, "dec": None, "paths": None}
_EMB = {}                       # (sha, w, h) -> (emb, pos)；encoder 很贵，必须缓存
_LOCK = threading.Lock()


def _root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mp(rel: str) -> str:
    d = os.environ.get(ENV_DIR)
    return os.path.join(d, os.path.basename(rel)) if d else os.path.join(_root(), *rel.split("/"))


def model_ready() -> bool:
    return all(os.path.exists(_mp(r)) and os.path.getsize(_mp(r)) > 1_000_000
               for r in (ENC_REL, DEC_REL))


def _sess():
    with _LOCK:
        paths = (_mp(ENC_REL), _mp(DEC_REL))
        if _SESS["enc"] is not None and _SESS["paths"] == paths:
            return _SESS["enc"], _SESS["dec"]
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _SESS["enc"] = ort.InferenceSession(paths[0], sess_options=so,
                                            providers=["CPUExecutionProvider"])
        _SESS["dec"] = ort.InferenceSession(paths[1], sess_options=so,
                                            providers=["CPUExecutionProvider"])
        _SESS["paths"] = paths
        _EMB.clear()
        return _SESS["enc"], _SESS["dec"]


def _imread(path: str):
    import cv2
    import numpy as np
    if not os.path.exists(path):
        raise FileNotFoundError("图片不存在: %s" % path)
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("解不开这张图: %s" % path)
    return img


def _imwrite(path: str, img) -> None:
    """中文路径安全的写图。"""
    import cv2
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".png", img)
    if ok:
        buf.tofile(path)


def _gc(keep: int = _KEEP) -> int:
    d = os.path.join(_root(), *SEG_DIR.split("/"))
    if not os.path.isdir(d):
        return 0
    groups = {}
    for f in os.listdir(d):
        stem = f.rsplit("_", 1)[0]
        groups.setdefault(stem, []).append(os.path.join(d, f))
    if len(groups) <= keep:
        return 0
    order = sorted(groups.items(),
                   key=lambda kv: max(os.path.getmtime(p) for p in kv[1]), reverse=True)
    n = 0
    for _, fs in order[keep:]:
        for p in fs:
            try:
                os.remove(p); n += 1
            except OSError:
                pass
    return n


def _embedding(img, key):
    """取（或复用）embedding。encoder 3.2s，缓存后同图再点只要 0.08s。"""
    import cv2
    import numpy as np
    with _LOCK:
        hit = _EMB.get(key)
    if hit is not None:
        return hit, True
    enc, _ = _sess()
    x = cv2.resize(img, (1024, 1024), interpolation=cv2.INTER_LINEAR)
    x = cv2.cvtColor(x, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    x = (x - mean) / std
    x = np.ascontiguousarray(x.transpose(2, 0, 1)[None])
    emb, pos = enc.run(None, {"pixel_values": x})
    with _LOCK:
        if len(_EMB) > 8:                 # 只留最近 8 张图的 embedding，防内存涨
            _EMB.clear()
        _EMB[key] = (emb, pos)
    return (emb, pos), False


def segment(image: str, point=None, box=None, save: bool = True,
            multi: bool = False) -> dict:
    """抠图。`point`=(x,y) 或 `box`=(x1,y1,x2,y2)，二选一（box 优先）。

    回：iou / 覆盖率 / bbox / mask 路径 / cutout（透明背景）路径。**不回图**。
    """
    import cv2
    import numpy as np

    if not image:
        return {"ok": False, "reason": "需要 image：本地图片路径"}
    if not model_ready():
        return {"ok": False, "status": "needs_dependency",
                "reason": "缺模型：%s / %s" % (_mp(ENC_REL), _mp(DEC_REL))}
    if not point and not box:
        return {"ok": False,
                "reason": "需要 point=(x,y) 或 box=(x1,y1,x2,y2) —— 本模块不做自动全图分割",
                "hint": "想抠整个主体，先用 op=detect/pose 拿到 bbox，再把它当 box 传进来"}

    try:
        img = _imread(image)
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "reason": "读图失败: %s: %s" % (type(exc).__name__, str(exc)[:140])}

    H, W = img.shape[:2]
    t_all = time.time()

    sha = hashlib.sha256(open(image, "rb").read()).hexdigest()[:16]
    key = (sha, W, H)
    try:
        (emb, pos), cached = _embedding(img, key)
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "reason": "encoder 失败: %s: %s" % (type(exc).__name__, str(exc)[:140])}

    # 组装 prompt
    if box:
        x1, y1, x2, y2 = [float(v) for v in box]
        pts = np.array([[[[x1 * 1024 / W, y1 * 1024 / H],
                          [x2 * 1024 / W, y2 * 1024 / H]]]], dtype=np.float32)
        lbl = np.array([[[2, 3]]], dtype=np.int64)      # 2/3 = 框的左上/右下
    else:
        x, y = float(point[0]), float(point[1])
        pts = np.array([[[[x * 1024 / W, y * 1024 / H]]]], dtype=np.float32)
        lbl = np.array([[[1]]], dtype=np.int64)         # 1 = 前景点

    _, dec = _sess()
    t0 = time.time()
    try:
        ious, masks = dec.run(None, {"input_points": pts, "input_labels": lbl,
                                     "image_embeddings": emb,
                                     "image_positional_embeddings": pos})
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "reason": "decoder 失败: %s: %s" % (type(exc).__name__, str(exc)[:140])}
    dec_ms = int((time.time() - t0) * 1000)

    scores = [float(v) for v in ious[0, 0]]
    best = int(np.argmax(scores))
    m256 = masks[0, 0, best]
    mu = cv2.resize(m256, (W, H), interpolation=cv2.INTER_LINEAR)
    binm = (mu > 0).astype(np.uint8)

    ys, xs = np.where(binm)
    if xs.size == 0:
        return {"ok": False, "reason": "没抠出任何像素（点在背景上？补个点或换 box）",
                "iou_scores": [round(s, 3) for s in scores]}

    cover = float(binm.mean() * 100)
    out = {"ok": True, "iou_scores": [round(s, 3) for s in scores],
           "chosen": best, "iou": round(scores[best], 3),
           "cover_pct": round(cover, 2),
           "bbox": {"x": int(xs.min()), "y": int(ys.min()),
                    "w": int(xs.max() - xs.min() + 1), "h": int(ys.max() - ys.min() + 1)},
           "area": int(binm.sum()),
           "prompt": ({"box": list(box)} if box else {"point": list(point)}),
           "encoder_cached": cached, "decoder_ms": dec_ms,
           "elapsed_ms": int((time.time() - t_all) * 1000),
           "backend": "slimsam-77 onnxruntime(CPU) · 零 torch"}

    if save:
        stem = "%s_%s" % (time.strftime("%Y%m%d-%H%M%S"), sha[:6])
        d = os.path.join(_root(), *SEG_DIR.split("/"))
        mp = os.path.join(d, stem + "_mask.png")
        cp = os.path.join(d, stem + "_cutout.png")
        _imwrite(mp, binm * 255)
        rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        rgba[:, :, 3] = (binm * 255).astype(np.uint8)
        _imwrite(cp, rgba)
        _gc()
        out.update({"mask": mp, "cutout": cp,
                    "note": "只回路径不回图；cutout 是透明背景 RGBA"})

    if not multi and scores[best] < 0.5:
        out["warn"] = "iou 偏低(%.2f)：单点可能只抠到局部，建议补点或改用 box" % scores[best]
    return out


def status() -> dict:
    ok = model_ready()
    return {"ok": True, "model_ready": ok,
            "models": {"encoder": _mp(ENC_REL), "decoder": _mp(DEC_REL)},
            "sizes_mb": {os.path.basename(_mp(r)): (round(os.path.getsize(_mp(r)) / 1024 / 1024, 1)
                          if os.path.exists(_mp(r)) else None) for r in (ENC_REL, DEC_REL)},
            "cached_images": len(_EMB),
            "ops": ["segment", "status"],
            "limits": "slimsam 蒸馏版，弱于 SAM ViT-H；单点常只抠局部；不做自动全图分割；"
                      "首点约 3.3s（encoder），同图再点约 0.08s（decoder）",
            "output": "只回 mask/cutout 的本地路径 + bbox + 面积，绝不回图"}


def run(op: str = "status", **kw) -> dict:
    o = str(op or "status").strip()
    if o in ("status", "health"):
        return status()
    if o in ("segment", "cut", "matte", "seg"):
        pt = kw.get("point") or kw.get("xy")
        bx = kw.get("box") or kw.get("bbox")
        return segment(kw.get("image") or kw.get("path") or "",
                       point=pt, box=bx,
                       save=bool(kw.get("save", True)),
                       multi=bool(kw.get("multi")))
    return {"ok": False, "reason": "未知 op: %s" % o, "supported": ["segment", "status"]}
