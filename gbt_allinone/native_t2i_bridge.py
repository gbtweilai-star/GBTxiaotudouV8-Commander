# -*- coding: utf-8 -*-
"""native_t2i_bridge — 桌面 API 到常驻 SD-Turbo worker 的桥。

配置优先级：
1) env GBT_NATIVE_T2I_PY / GBT_NATIVE_T2I_WORKER / GBT_NATIVE_T2I_ROOT
2) payload/state/native_t2i.json
3) 本机已知 live workspace 路径
"""
from __future__ import annotations

import json
import os
import subprocess
import threading

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CFG_CANDIDATES = [
    os.path.join(_ROOT, "state", "native_t2i.json"),
    os.path.join(os.path.dirname(_ROOT), "state", "native_t2i.json"),
]
_LOCK = threading.Lock()
_PROC = None
_PROC_KEY = None


def _known_root():
    return r"C:\Users\Lenovo E14 Gen 5\Documents\deepseek-harness\default-workspace\GBTxiaotudouV8-Commander"


def _load_cfg():
    cfg = {}
    for p in _CFG_CANDIDATES:
        try:
            if os.path.isfile(p):
                cfg.update(json.load(open(p, encoding="utf-8")))
                break
        except Exception:  # noqa: BLE001
            pass
    ws = _known_root()
    py = os.environ.get("GBT_NATIVE_T2I_PY") or cfg.get("python") or os.path.join(ws, "pyembed", "python.exe")
    root = os.environ.get("GBT_NATIVE_T2I_ROOT") or cfg.get("root") or os.path.join(ws, "GBTxiaotudouV8-Commander-main")
    worker = os.environ.get("GBT_NATIVE_T2I_WORKER") or cfg.get("worker") or os.path.join(root, "tools", "native_t2i_worker.py")
    return {"python": py, "root": root, "worker": worker}


def _ensure(cfg):
    global _PROC, _PROC_KEY
    key = (cfg["python"], cfg["worker"], cfg["root"])
    if _PROC is not None and _PROC.poll() is None and _PROC_KEY == key:
        return _PROC
    _PROC = subprocess.Popen(
        [cfg["python"], "-B", "-X", "utf8", cfg["worker"], "--root", cfg["root"], "--serve"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", bufsize=1, cwd=cfg["root"],
    )
    _PROC_KEY = key
    return _PROC


def run(payload: dict | None = None) -> dict:
    payload = dict(payload or {})
    cfg = _load_cfg()
    if not os.path.isfile(cfg["python"]):
        return {"ok": False, "status": "needs_runtime", "error": "找不到本地 python：%s" % cfg["python"]}
    if not os.path.isfile(cfg["worker"]):
        return {"ok": False, "status": "needs_runtime", "error": "找不到 worker：%s" % cfg["worker"]}
    req = {
        "op": str(payload.get("op") or ""),
        "model": str(payload.get("model") or ""),
        "image": str(payload.get("image") or ""),
        "prompt": str(payload.get("prompt") or payload.get("text") or ""),
        "out": str(payload.get("out") or ""),
        "frames": int(payload.get("frames") or (8 if payload.get("op") == "i2v_svd" else 0)),
        "width": int(payload.get("width") or (256 if payload.get("op") == "i2v_svd" else 0)),
        "height": int(payload.get("height") or (448 if payload.get("op") == "i2v_svd" else 0)),
        "fps": int(payload.get("fps") or 8),
        "motion": int(payload.get("motion") or 127),
        "size": int(payload.get("size") or (256 if payload.get("op") == "t2i_fused" else 512)),
        "steps": int(payload.get("steps") or (2 if payload.get("op") == "i2v_svd" else (8 if payload.get("op") == "t2i_fused" else 1))),
        "seed": int(payload.get("seed") or 0),
    }
    if not req["out"]:
        req["out"] = os.path.join(_ROOT, "state", "native-t2i-%d.png" % (int(__import__("time").time()) % 1000000))
    with _LOCK:
        try:
            p = _ensure(cfg)
            p.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            p.stdin.flush()
            line = p.stdout.readline()
            if not line:
                return {"ok": False, "status": "worker_dead", "error": "worker 无响应"}
            return json.loads(line)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status": "worker_error", "error": "%s: %s" % (type(e).__name__, str(e)[:300])}
