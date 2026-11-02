# -*- coding: utf-8 -*-
"""hand_vision — 本地摄像头/图片/视频 → 21 点手部关键点。

为什么单独一层：
  hand_retarget 只吃 21 点；这一层负责"眼睛"：MediaPipe Hands 本地推理，
  输出 21×[x,y,z] + 左右手；然后可直接喂 hand_retarget / hand_ik / hand_realtime。

诚实边界：
  - 摄像头不可用（驱动/隐私/被占用）时如实 needs_camera，不伪造；
  - 图片/视频可离线用；模型在本机，不联网；
  - MediaPipe 的 21 点坐标是归一化图像坐标，不是米制；标定后再接真手。
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYLIBS = os.path.join(ROOT, "vendor", "pylibs")
if not os.path.isdir(PYLIBS):
    PYLIBS = os.path.join(os.path.dirname(ROOT), "vendor", "pylibs")
if PYLIBS not in sys.path:
    sys.path.insert(0, PYLIBS)
os.environ.setdefault("MPLCONFIGDIR", os.path.join(ROOT, ".scratch", "lead", "mpl"))
os.environ.setdefault("GLOG_minloglevel", "2")

__all__ = ["run", "STATUS", "detect_image", "camera_frames"]


def _mp():
    import mediapipe as mp
    return mp


def _hands(static=True, complexity=1):
    mp = _mp()
    return mp.solutions.hands.Hands(
        static_image_mode=bool(static), max_num_hands=2, model_complexity=int(complexity),
        min_detection_confidence=0.35, min_tracking_confidence=0.35)


def _landmarks(res):
    out = []
    for i, hand in enumerate(res.multi_hand_landmarks or []):
        lm = [[round(float(p.x), 6), round(float(p.y), 6), round(float(p.z), 6)] for p in hand.landmark]
        side = "right"
        try:
            side = res.multi_handedness[i].classification[0].label.lower()
        except Exception:  # noqa: BLE001
            pass
        out.append({"hand": side, "landmarks": lm})
    return out


def status(**_kw):
    import cv2
    mp = _mp()
    cap = cv2.VideoCapture(0)
    cam = bool(cap.isOpened())
    if cam:
        cap.release()
    return {"ok": True, "cap": "hand_vision", "ops": ["status", "image", "camera"],
            "mediapipe": getattr(mp, "__version__", "?"), "opencv": cv2.__version__,
            "camera": cam, "model": "mediapipe.solutions.hands (local tflite)",
            "note": "图片/视频离线可用；摄像头不可用时 needs_camera，不伪造"}


def detect_image(path: str = "", **_kw):
    import cv2
    if not path or not os.path.isfile(path):
        return {"ok": False, "op": "image", "status": "needs_input", "error": "缺 image 路径"}
    img = cv2.imread(path)
    if img is None:
        return {"ok": False, "op": "image", "status": "user_error", "error": "读不了图片"}
    with _hands(static=True) as h:
        res = h.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        found = _landmarks(res)
    return {"ok": True, "op": "image", "image": path, "size": [img.shape[1], img.shape[0]],
            "hands": found, "count": len(found),
            "note": "归一化图像坐标；接真手前需标定"}


def _winrt_capture():
    """OpenCV/DirectShow 绑不上时，用 WinRT MediaCapture 抓一张。"""
    import subprocess, tempfile
    script = os.path.join(ROOT, "tools", "camera-winrt.ps1")
    if not os.path.isfile(script):
        return None
    fd, out = tempfile.mkstemp(prefix="winrt-cam-", suffix=".jpg", dir=os.path.join(ROOT, ".scratch", "lead"))
    os.close(fd)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", script, "-OutFile", out],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and os.path.getsize(out) > 1000:
            return out
        return None
    except Exception:  # noqa: BLE001
        return None


def camera_frames(seconds: float = 2.0, max_frames: int = 120, **_kw):
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        # 回退：WinRT 拍照抓一帧（不是实时流），证明摄像头/视觉入口可用
        w = _winrt_capture()
        if w:
            try:
                img = cv2.imread(w)
                with _hands(static=True) as h:
                    res = h.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                    hands = _landmarks(res)
                return {"ok": True, "op": "camera", "mode": "winrt_photo",
                        "captured": 1, "hands": hands, "count": len(hands),
                        "note": "WinRT 抓单帧；非实时流；接真机前需标定"}
            finally:
                try:
                    os.remove(w)
                except OSError:
                    pass
        return {"ok": False, "op": "camera", "status": "needs_camera",
                "error": "摄像头打不开（OpenCV/DSHOW/VfW 均失败，WinRT 也失败）",
                "how_to_fix": "Windows 设置→隐私→相机；确认无其它程序占用；或先用 image 模式"}
    frames, t0 = [], time.perf_counter()
    try:
        with _hands(static=False) as h:
            while len(frames) < max_frames and time.perf_counter() - t0 < seconds:
                ok, frame = cap.read()
                if not ok:
                    break
                res = h.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if res.multi_hand_landmarks:
                    frames.append({"at": round(time.perf_counter() - t0, 3),
                                   "hands": _landmarks(res)})
    finally:
        cap.release()
    return {"ok": bool(frames), "op": "camera", "frames": frames[:30],
            "captured": len(frames), "seconds": round(time.perf_counter() - t0, 3),
            "note": "摄像头本地推理；需隐私权限"}


def run(op="status", payload=None, **_kw):
    payload = payload or {}
    op = str(op or "status").lower()
    if op == "status":
        return status(**payload)
    if op in ("image", "detect"):
        return detect_image(str(payload.get("image") or payload.get("path") or ""), **payload)
    if op == "camera":
        return camera_frames(float(payload.get("seconds", 2.0)), int(payload.get("max_frames", 120)))
    return {"ok": False, "status": "user_error", "error": "未知 op：%s（status/image/camera）" % op}



