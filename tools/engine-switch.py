"""GBT小土豆V8 · 引擎后端切换（本地 CPU / Vulkan GPU 直连）

主人 2026-11-03：触手要能直连 CPU/GPU，没有就补齐并跑通闭环。

用法：
  python tools/engine-switch.py --backend cpu      # 本机 CPU（默认）
  python tools/engine-switch.py --backend vulkan   # Vulkan（Intel/AMD/NVIDIA 走 Vulkan）
  python tools/engine-switch.py --status

做的事：停掉当前 8792 引擎 → 起所选后端 → 等健康 → 验证 /v1/models → 写 state/engine-backend.json。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_W = ROOT / "state" / "weights"
ACTIVE = STATE_W / "ACTIVE.json"
CONF = ROOT / "state" / "engine-backend.json"
PORT = 8792

MODEL_CHOICES = {
    "q5": STATE_W / "gbt-v8-v82-q5_0.gguf",
    "q4": STATE_W / "gbt-v8-v82-q4_k_m.gguf",   # 低内存档（量化压缩后）
}
BACKENDS = {
    "cpu": {"exe": ROOT / "vendor" / "llama-server.exe", "ngl": 0, "threads": 12},
    "vulkan": {"exe": ROOT / "vendor" / "vulkan-b12032" / "llama-server.exe",
               "ngl": 99, "threads": 8},
}


def _active_model() -> Path:
    rec = json.loads(ACTIVE.read_text(encoding="utf-8-sig"))
    name = rec.get("active_artifact") or rec.get("model")
    return STATE_W / str(name)


def _listening_pids(port: int) -> list:
    try:
        ps = ("(Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction "
              "SilentlyContinue).OwningProcess" % port)
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=20)
        return [int(x) for x in (out.stdout or "").split() if x.strip().isdigit()]
    except Exception:
        return []


def _stop(port: int) -> list:
    stopped = []
    for pid in set(_listening_pids(port)):
        if pid == 0 or pid == __import__("os").getpid():
            continue
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=15)
            stopped.append(pid)
        except Exception:
            pass
    return stopped


def _health(port: int, timeout: float = 180.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=3) as r:
                if json.loads(r.read().decode()).get("status") == "ok":
                    return True
        except Exception:
            time.sleep(2)
    return False


def _models(port: int) -> list:
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/v1/models" % port, timeout=10) as r:
            return [m.get("id") for m in json.loads(r.read().decode()).get("data") or []]
    except Exception:
        return []


def status() -> dict:
    try:
        conf = json.loads(CONF.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        conf = None
    return {"ok": True, "active": conf, "listening": _listening_pids(PORT),
            "models": _models(PORT), "backends": {k: str(v["exe"]) for k, v in BACKENDS.items()}}


def switch(backend: str, model_key: str = "q5", sleep_idle: int = 30) -> dict:
    if backend not in BACKENDS:
        return {"ok": False, "reason": "未知后端：%s（可选 %s）" % (backend, list(BACKENDS))}
    spec = BACKENDS[backend]
    if not Path(spec["exe"]).is_file():
        return {"ok": False, "reason": "后端二进制不存在：%s" % spec["exe"],
                "hint": "vulkan 需先下载 vendors/vulkan-b12032（见 docs/130）"}
    model = MODEL_CHOICES.get(model_key) or _active_model()
    if not model.is_file():
        return {"ok": False, "reason": "ACTIVE 模型不存在：%s" % model}
    stopped = _stop(PORT)
    time.sleep(1.5)
    cmd = [str(spec["exe"]), "-m", str(model), "--host", "127.0.0.1",
           "--port", str(PORT), "-c", "2048", "-t", str(spec["threads"]),
           "-ngl", str(spec["ngl"]), "--no-webui",
           "--sleep-idle-seconds", str(int(sleep_idle))]
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    ok = _health(PORT)
    rec = {"backend": backend, "pid": proc.pid, "model": model.name,
           "sleep_idle": int(sleep_idle), "lane": "on-demand" if sleep_idle <= 60 else "always-on",
           "ngl": spec["ngl"], "threads": spec["threads"], "port": PORT,
           "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "healthy": ok,
           "models": _models(PORT)}
    CONF.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": ok, "stopped": stopped, **rec}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=list(BACKENDS), default="")
    ap.add_argument("--model", choices=list(MODEL_CHOICES), default="q5")
    ap.add_argument("--sleep-idle", type=int, default=30)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    out = status() if (a.status or not a.backend) else switch(a.backend, a.model, a.sleep_idle)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out.get("ok") else 1)
