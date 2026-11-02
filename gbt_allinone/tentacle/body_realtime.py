# -*- coding: utf-8 -*-
"""body_realtime — 眼手脑同拍：采集线程持续看，控制环边看边动。

和 body_see/body_click 的区别：
- 不是"截一张图 -> 子进程退出 -> 再点一下"；
- 采集线程持续抓屏（mss），控制环只读最新帧，小步闭环移动；
- 动作期间采集不停，视觉延迟可测（毫秒）。

op=status / servo
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "model-bridge", "realtime_eye_hand.py")
PY = sys.executable


def status(**kw):
    return {"ok": True, "cap": "body_realtime", "script": SCRIPT,
            "exists": os.path.isfile(SCRIPT), "mode": "capture-thread + closed-loop micro-actions",
            "ops": ["status", "servo"], "note": "动作期间采集不停；不是 see 子进程后再 click",
            "args": {"target": "red", "seconds": 6, "gain": 0.35, "max_step": 60, "dry_run": False}}


def servo(payload=None, **kw):
    payload = payload or {}
    if not os.path.isfile(SCRIPT):
        return {"ok": False, "error": "缺 realtime_eye_hand.py", "script": SCRIPT}
    args = [PY, "-B", "-X", "utf8", SCRIPT,
            "--target", str(payload.get("target", "red")),
            "--seconds", str(float(payload.get("seconds", 6))),
            "--gain", str(float(payload.get("gain", 0.35))),
            "--max-step", str(float(payload.get("max_step", 60)))]
    if payload.get("dry_run"):
        args.append("--dry-run")
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=float(payload.get("seconds", 6)) + 15)
        out = (r.stdout or "").strip().splitlines()
        data = json.loads(out[-1]) if out else {}
        data.setdefault("ok", r.returncode == 0)
        data["exit_code"] = r.returncode
        return data
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "realtime 超时（已杀）", "timeout_s": payload.get("seconds")}
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}


def run(op="status", payload=None, **kw):
    if str(op).lower() == "servo":
        return servo(payload, **kw)
    return status(**kw)

