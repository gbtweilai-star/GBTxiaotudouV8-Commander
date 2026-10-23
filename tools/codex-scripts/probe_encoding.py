"""字节级探测：确认 codex app-server stdio 的中文编码约定。

用二进制读写，打印原始字节，判断乱码发生在输入侧还是输出侧。
"""
from __future__ import annotations

import json
import subprocess
import sys

CODEX = r"C:\Users\ADMIN\AppData\Local\OpenAI\Codex\bin\bffc5354119c8421\codex.exe"
WORKDIR = "C:\\Users\\ADMIN\\Desktop\\GBT\u5c0f\u571f\u8c46V8"


def run_rpc(payload_bytes: bytes, label: str) -> None:
    proc = subprocess.Popen(
        [CODEX, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    init = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "clientInfo": {"name": "probe", "version": "1.0"},
            "capabilities": {"experimentalApi": True},
        },
    }
    proc.stdin.write(json.dumps(init).encode("utf-8") + b"\n")
    proc.stdin.flush()
    proc.stdout.readline()
    proc.stdin.write(payload_bytes + b"\n")
    proc.stdin.flush()
    print(f"--- {label} ---", flush=True)
    for _ in range(6):
        raw = proc.stdout.readline()
        if not raw:
            break
        print("RAW:", repr(raw[:400]), flush=True)
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception as e:
            print("decode as utf-8 failed:", e, flush=True)
            continue
        if msg.get("id") == 2:
            cwd = (msg.get("result") or {}).get("thread", {}).get("cwd")
            print("cwd repr:", repr(cwd), flush=True)
            break
    proc.stdin.close()
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except Exception:
        proc.kill()


def main() -> int:
    req = {
        "jsonrpc": "2.0", "id": 2, "method": "thread/start",
        "params": {
            "cwd": WORKDIR,
            "sandbox": "read-only",
            "ephemeral": True,
            "approvalPolicy": "never",
        },
    }
    run_rpc(json.dumps(req, ensure_ascii=False).encode("utf-8"),
            "utf-8 raw, ensure_ascii=False")
    run_rpc(json.dumps(req, ensure_ascii=True).encode("utf-8"),
            "utf-8 raw, ensure_ascii=True escaped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
