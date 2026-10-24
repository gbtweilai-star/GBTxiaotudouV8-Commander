# -*- coding: utf-8 -*-
"""身体的六根动作 —— 挂成正式能力位（body_see/body_say/…）。

为什么是「壳里再包一层」而不是让能力位直接 import body：
身体要的库（mss / cv2 / sounddevice / pycaw）装在 3.12，框架跑在 3.14。
所以能力位这边只做**定义 + 转发**，真动作由 tools/model-bridge/body.py 在 3.12 里跑。
"""
from __future__ import annotations
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "tools", "model-bridge", "body.py")
PY = os.environ.get("GBT_BODY_PY") or (
    r"C:\Python312\python.exe" if os.path.exists(r"C:\Python312\python.exe") else sys.executable)
LIMBS = ("see", "say", "type", "click", "volume", "open")


def run(limb: str, payload: dict | None = None) -> dict:
    if limb not in LIMBS:
        return {"ok": False, "error": "不认识的肢体：%s（可选 %s）" % (limb, ",".join(LIMBS))}
    try:
        r = subprocess.run([PY, "-X", "utf8", BODY, "--act", limb,
                            json.dumps(payload or {}, ensure_ascii=False)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=120, cwd=ROOT)
        out = (r.stdout or "").strip()
        return json.loads(out) if out.startswith("{") else {"ok": False, "error": out[-200:]}
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}


def body_map() -> dict:
    try:
        r = subprocess.run([PY, "-X", "utf8", BODY], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90, cwd=ROOT)
        return json.loads((r.stdout or "{}"))
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}
