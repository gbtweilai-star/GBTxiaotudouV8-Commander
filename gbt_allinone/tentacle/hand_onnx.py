# -*- coding: utf-8 -*-
"""hand_onnx — 本地 OpenCV DNN 手部关键点（MediaPipe 模型的 ONNX 版）。

为什么另起一条：
  MediaPipe Python 图在 Intel CPU 上 infer p95 仍 >700ms；这条用 OpenCV DNN 直接跑
  palm detector + handpose ONNX（OpenCV Zoo / Apache-2.0），模型只加载一次。

边界：仍是 21 点 2D/相对 z；摄像头未接；真机需标定。
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS = os.environ.get("GBT_HAND_MODELS") or os.path.join(ROOT, "vendor", "hand-tracking")
if not os.path.isdir(MODELS):
    MODELS = os.path.join(os.path.dirname(ROOT), "vendor", "hand-tracking")
if not os.path.isdir(MODELS):
    MODELS = os.path.join(os.path.dirname(ROOT), "vendor", "hand-tracking")
if MODELS not in sys.path:
    sys.path.insert(0, MODELS)
PYLIBS = os.path.join(ROOT, "vendor", "pylibs")
if not os.path.isdir(PYLIBS):
    PYLIBS = os.path.join(os.path.dirname(ROOT), "vendor", "pylibs")
if PYLIBS not in sys.path:
    sys.path.insert(0, PYLIBS)

_palm = None
_pose = None


def _load():
    global _palm, _pose
    if _palm is None or _pose is None:
        import cv2
        from mp_palmdet import MPPalmDet
        from mp_handpose import MPHandPose
        _palm = MPPalmDet(os.path.join(MODELS, "palm_detection.onnx"), scoreThreshold=0.3)
        _pose = MPHandPose(os.path.join(MODELS, "handpose.onnx"), confThreshold=0.3)
    return _palm, _pose


def detect(image):
    """image: BGR ndarray; returns {hands:[{hand,landmarks}], infer_ms}."""
    import cv2
    import numpy as np
    palm, pose = _load()
    h, w = image.shape[:2]
    t = time.perf_counter()
    palms = palm.infer(image)
    out = []
    if palms is not None and len(palms):
        # 取置信度最高
        p = palms[int(np.argmax(palms[:, -1]))]
        r = pose.infer(image, p)
        if r is not None:
            landmarks = r[4:67].reshape(21, 3).copy()
            for i in range(21):
                landmarks[i, 0] = landmarks[i, 0] / w
                landmarks[i, 1] = landmarks[i, 1] / h
                landmarks[i, 2] = landmarks[i, 2] / max(w, h)
            side = "right" if float(r[130]) >= 0.5 else "left"
            out.append({"hand": side, "landmarks": [[round(float(x), 6) for x in row] for row in landmarks]})
    return {"hands": out, "infer_ms": round((time.perf_counter() - t) * 1000, 2)}


def status(**_kw):
    import cv2
    return {"ok": True, "cap": "hand_onnx", "opencv": cv2.__version__,
            "models": ["palm_detection.onnx", "handpose.onnx"],
            "backend": "OpenCV DNN CPU", "license": "OpenCV Zoo (Apache-2.0)",
            "note": "本地 ONNX；不依赖 MediaPipe Python 图；真机需标定"}


def run(op="status", payload=None, **_kw):
    payload = payload or {}
    op = str(op or "status").lower()
    if op == "status":
        return status(**payload)
    if op == "image":
        import cv2
        p = str(payload.get("image") or "")
        img = cv2.imread(p) if p else None
        if img is None:
            return {"ok": False, "op": "image", "status": "needs_input", "error": "缺/读不了 image"}
        r = detect(img)
        return {"ok": True, "op": "image", "image": p, "count": len(r["hands"]),
                "hands": r["hands"], "infer_ms": r["infer_ms"],
                "note": "OpenCV DNN ONNX；归一化图像坐标"}
    if op == "video":
        import cv2
        p = str(payload.get("video") or payload.get("path") or "")
        cap = cv2.VideoCapture(p)
        if not cap.isOpened():
            return {"ok": False, "op": "video", "status": "needs_input", "error": "打不开视频"}
        frames = detected = 0
        lat = []
        t0 = time.perf_counter()
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            frames += 1
            r = detect(fr)
            lat.append(r["infer_ms"])
            if r["hands"]:
                detected += 1
        cap.release()
        el = time.perf_counter() - t0
        return {"ok": detected > 0, "op": "video", "frames": frames, "detected_frames": detected,
                "infer_ms_mean": round(sum(lat) / len(lat), 2) if lat else None,
                "infer_ms_p95": round(sorted(lat)[int(len(lat) * 0.95)], 2) if lat else None,
                "fps": round(frames / max(el, 1e-6), 2), "seconds": round(el, 3),
                "boundary": "本地 ONNX 批处理；loopback 未接；真机需标定"}
    return {"ok": False, "status": "user_error", "error": "未知 op：%s（status/image/video）" % op}




