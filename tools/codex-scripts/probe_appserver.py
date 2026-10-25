"""一次性协议探测：验证 Codex app-server 的握手与 thread/start 行为。

只做 initialize + thread/start（只读沙盒、临时会话），不发送任何用户消息，
探测完成后立即关闭子进程。用于确认 JSON-RPC 帧格式，不作为产品代码。
"""
from __future__ import annotations
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])

import json
import subprocess
import sys
import threading

CODEX = r"C:\Users\ADMIN\AppData\Local\OpenAI\Codex\bin\bffc5354119c8421\codex.exe"


def main() -> int:
    proc = subprocess.Popen(
        [CODEX, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        bufsize=1, text=True, encoding="utf-8", errors="replace",
    )

    def drain_stderr():
        for line in proc.stderr:
            sys.stdout.write("[stderr] " + line)
            sys.stdout.flush()

    threading.Thread(target=drain_stderr, daemon=True).start()

    lock = threading.Lock()

    def send(obj):
        line = json.dumps(obj, ensure_ascii=False)
        with lock:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
        print("[send]", json.dumps(obj, ensure_ascii=False)[:300], flush=True)

    send({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "clientInfo": {"name": "gbt-xiaotudou-panel", "version": "8.0.0"},
            "capabilities": {"experimentalApi": True},
        },
    })

    got_init = False
    thread_id = None
    try:
        for raw in proc.stdout:
            print("[recv]", raw.strip()[:1000], flush=True)
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("id") == 1 and not got_init:
                got_init = True
                send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
                send({
                    "jsonrpc": "2.0", "id": 2, "method": "thread/start",
                    "params": {
                        "cwd": _GBT_ROOT,
                        "sandbox": "read-only",
                        "ephemeral": True,
                        "approvalPolicy": "never",
                        "baseInstructions": "protocol probe only",
                    },
                })
            if msg.get("id") == 2:
                thread_id = (msg.get("result") or {}).get("thread", {}).get("id")
                print("[thread]", thread_id, flush=True)
                break
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
