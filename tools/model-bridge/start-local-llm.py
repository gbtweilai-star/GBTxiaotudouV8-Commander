# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""起本机自训权重引擎（她自己的口 :8111）—— 用 Python 起，不经 .cmd。

## 为什么不用 `本地权重-起引擎.cmd`

那份 .cmd 的参数是对的（下面 `ARGS` 与它逐项对齐），但**在非交互调用下不可靠**：
  · `start /min` 会把进程分离到一个新窗口，调用方拿不到 PID，也就无法
    「确认它真的起来了」还是「悄悄失败了」
  · 中文路径经 `cmd /c "..."` 转手时会被 PowerShell 的引号规则吃掉
    （实测：`The system cannot find the path specified`）
  · 日志落在窗口里，断了就没了 —— 排查"为什么没起来"时最缺的恰恰是这段

## 它做什么

1. 幂等：`/health` 通就直接复用，不起第二个进程（每个进程要吃 4.88G 内存）
2. 起进程：参数与 .cmd 逐项对齐，日志落到 `state/logs/llama-8111.log`
3. **等到真的能推理**才返回 ok：轮询 `/health` + 一次最小 `/v1/chat/completions`
   （只有 `/health` 通不算——模型可能还没加载完权重，那时请求会 5xx/挂起）

## 用法

    python tools/model-bridge/start-local-llm.py            # 起（已起则复用）
    python tools/model-bridge/start-local-llm.py --status    # 只看状态
    python tools/model-bridge/start-local-llm.py --stop      # 停（只停我们起的）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / "vendor" / "llama" / "llama-server.exe"
ACTIVE = ROOT / "state" / "weights" / "ACTIVE.json"
LOGDIR = ROOT / "state" / "logs"
PIDFILE = ROOT / "state" / "llama-8111.pid"

HOST, PORT = "127.0.0.1", 8111
BASE = f"http://{HOST}:{PORT}"

# 与 本地权重-起引擎.cmd 逐项对齐（改这里要同步改那份 .cmd，反之亦然）
CTX = 8192
THREADS = 12
NGL = 0          # 纯 CPU：本机无可用 GPU offload 时不要乱开，开了会静默退化

# 必带本仓模板（2026-11-04 实测发现）：
#   不带 `--chat-template-file` 时 llama-server 用 GGUF 内置的 Qwen 模板，而它在
#   **普通对话**（不只是 tools 分支）就会注入
#       "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
#   ⇒ 她每句话都顶着别人家的名字说话，与本仓「她自己的口」冲突。
#   本仓模板保留 <|im_start|> 结构（Qwen 系必须用它，否则质量崩），去掉品牌注入，
#   并让 system 消息以标准 role 结构参与，而不是被拼成前缀文本。
TEMPLATE = ROOT / "vendor" / "llama" / "gbt-user-assistant.jinja"


def _active() -> dict:
    if not ACTIVE.is_file():
        return {}
    try:
        return json.loads(ACTIVE.read_text(encoding="utf-8"))
    except Exception:                                    # noqa: BLE001
        return {}


def _get(path: str, timeout: float = 3.0):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def health() -> bool:
    try:
        s, _ = _get("/health")
        return s == 200
    except Exception:                                    # noqa: BLE001
        return False


def can_infer(timeout: float = 180.0) -> tuple:
    """真能推理才算起来：最小 chat 请求要拿到 choices。

    只测 /health 是不够的 —— llama-server 在权重加载阶段就会先挂上 HTTP 服务，
    那时 /health 可能已经 200 但推理会挂起。**"端口开着"不等于"能用"**。
    """
    body = json.dumps({
        "model": "gbt-v8-v82-q5_0",
        "messages": [{"role": "user", "content": "1+1="}],
        "max_tokens": 8, "temperature": 0.0, "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode("utf-8")
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        ch = (d.get("choices") or [{}])[0]
        txt = ((ch.get("message") or {}).get("content") or "").strip()
        return True, {"seconds": round(time.time() - t0, 1), "reply": txt[:80],
                      "finish": ch.get("finish_reason")}
    except Exception as e:                               # noqa: BLE001
        return False, {"seconds": round(time.time() - t0, 1),
                       "error": f"{type(e).__name__}: {str(e)[:150]}"}


def status() -> dict:
    a = _active()
    return {"health": health(), "endpoint": BASE + "/v1",
            "active_artifact": a.get("active_artifact"), "quant": a.get("quant"),
            "size_gb": a.get("size_gb"), "sha256": (a.get("sha256") or "")[:16],
            "pidfile": PIDFILE.is_file(), "ctx": CTX, "threads": THREADS, "ngl": NGL}


def start(wait: bool = True) -> dict:
    if health():
        return {"ok": True, "reused": True, **status()}

    a = _active()
    model_name = a.get("active_artifact") or ""
    model = ROOT / "state" / "weights" / model_name if model_name else None
    if not model_name or not model or not model.is_file():
        return {"ok": False, "fail_closed": True,
                "error": f"权重不在：{model}", "how": "检查 state/weights/ACTIVE.json"}
    if not EXE.is_file():
        return {"ok": False, "fail_closed": True,
                "error": f"引擎不在：{EXE}", "how": "vendor/llama 未随仓分发"}

    LOGDIR.mkdir(parents=True, exist_ok=True)
    log = LOGDIR / "llama-8111.log"
    args = [str(EXE), "-m", str(model), "--host", HOST, "--port", str(PORT),
            "-c", str(CTX), "-t", str(THREADS), "-ngl", str(NGL),
            "--alias", model_name.rsplit(".", 1)[0],
            "--no-context-shift", "--no-webui"]
    if TEMPLATE.is_file():
        args += ["--chat-template-file", str(TEMPLATE)]

    # 独立进程组 + 日志落盘：调用方断了也不影响它，出问题也有据可查
    fh = open(log, "ab")                       # noqa: SIM115
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    p = subprocess.Popen(args, cwd=str(ROOT), stdout=fh, stderr=fh,
                         stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    PIDFILE.write_text(str(p.pid), encoding="utf-8")

    if not wait:
        return {"ok": True, "started": True, "pid": p.pid, "log": str(log.relative_to(ROOT))}

    # 轮询：/health 通 **且** 真能推理
    t0, last = time.time(), ""
    while time.time() - t0 < 300:
        if health():
            ok, info = can_infer()
            if ok:
                return {"ok": True, "started": True, "pid": p.pid,
                        "boot_seconds": round(time.time() - t0, 1),
                        "log": str(log.relative_to(ROOT)), **info, **status()}
            last = json.dumps(info, ensure_ascii=False)
        time.sleep(2)
    return {"ok": False, "fail_closed": True, "pid": p.pid,
            "error": f"300 秒内没等到「能推理」（最后：{last}）",
            "log": str(log.relative_to(ROOT)),
            "how": "看日志尾部：可能权重损坏 / 内存不足 / 端口被占"}


def stop() -> dict:
    if not PIDFILE.is_file():
        return {"ok": False, "error": "没有 pidfile —— 那不是我起的进程，我不杀别人的"}
    try:
        pid = int(PIDFILE.read_text(encoding="utf-8").strip())
    except Exception:                                    # noqa: BLE001
        return {"ok": False, "error": "pidfile 内容不是数字"}
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True)
        PIDFILE.unlink(missing_ok=True)
        return {"ok": True, "stopped": pid}
    except Exception as e:                               # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def main(argv: list) -> int:
    if "--status" in argv:
        print(json.dumps(status(), ensure_ascii=False, indent=1))
        return 0 if health() else 1
    if "--stop" in argv:
        print(json.dumps(stop(), ensure_ascii=False, indent=1))
        return 0
    r = start()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
