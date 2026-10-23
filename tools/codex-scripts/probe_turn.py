"""端到端协议探测：initialize -> thread/start -> turn/start -> 收集流式事件。

只读沙盒、临时会话；用于确认事件名称与载荷结构，不作为产品代码。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

CODEX = r"C:\Users\ADMIN\AppData\Local\OpenAI\Codex\bin\bffc5354119c8421\codex.exe"
WORKDIR = os.path.abspath(".")


def main() -> int:
    env = dict(os.environ)
    env["CODEX_HOME"] = r"C:\Users\ADMIN\.codex"
    env["RUST_LOG"] = "warn"
    proc = subprocess.Popen(
        [CODEX, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env,
    )

    def drain_stderr():
        for line in proc.stderr:
            text = line.decode("utf-8", "replace").strip()
            if text:
                print("[stderr]", text[:300], flush=True)

    threading.Thread(target=drain_stderr, daemon=True).start()

    def send(obj):
        proc.stdin.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        proc.stdin.flush()

    send({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "clientInfo": {"name": "gbt-probe", "version": "1.0"},
            "capabilities": {"experimentalApi": True},
        },
    })

    thread_id = None
    turn_id = None
    started = time.time()
    deadline = started + 90
    event_counts: dict[str, int] = {}

    while time.time() < deadline:
        raw = proc.stdout.readline()
        if not raw:
            break
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception:
            continue

        method = msg.get("method")
        msg_id = msg.get("id")

        if msg_id == 1:
            send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
            send({
                "jsonrpc": "2.0", "id": 2, "method": "thread/start",
                "params": {
                    "cwd": WORKDIR,
                    "sandbox": "read-only",
                    "ephemeral": True,
                    "approvalPolicy": "never",
                    "baseInstructions": "You are a protocol probe. Answer in one short sentence.",
                },
            })
            continue

        if msg_id == 2:
            result = msg.get("result") or {}
            if msg.get("error"):
                print("[thread/start error]", json.dumps(msg["error"])[:400], flush=True)
                break
            thread_id = (result.get("thread") or {}).get("id")
            print("[thread]", thread_id, "model:", result.get("model"), flush=True)
            send({
                "jsonrpc": "2.0", "id": 3, "method": "turn/start",
                "params": {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": "Reply with the single word: pong"}],
                },
            })
            continue

        if msg_id == 3:
            if msg.get("error"):
                print("[turn/start error]", json.dumps(msg["error"])[:600], flush=True)
                break
            turn_id = ((msg.get("result") or {}).get("turn") or {}).get("id")
            print("[turn]", turn_id, flush=True)
            continue

        if method:
            event_counts[method] = event_counts.get(method, 0) + 1
            if method in ("item/agentMessage/delta",
                          "item/completed", "turn/completed",
                          "turn/started", "thread/status/changed"):
                print("[event]", method, json.dumps(msg.get("params"), ensure_ascii=False)[:500],
                      flush=True)
            if method == "turn/completed":
                break
            if method == "error":
                print("[error event]", json.dumps(msg.get("params"), ensure_ascii=False)[:500],
                      flush=True)
                break

    print("[event_counts]", json.dumps(event_counts, ensure_ascii=False), flush=True)
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
