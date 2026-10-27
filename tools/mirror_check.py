#!/usr/bin/env python3
"""镜像接入的验收探针 —— 供 rehearsal.acceptance 当命令用

它只做一件事：**把"我以为接上了"变成可复跑的证据**。
三条检查对应计划里的 AC1~AC3：

  AC1  面板页含镜像区块、七个按钮、原有 .rail 仍在
  AC2  /api/mirror 对未知 op fail-closed
  AC3  GET /api/mirror 返回 ok=true 且含 dimension/reality/timelines

退出码：全过 0，任一失败 1（rehearse 靠退出码判绿）
"""
from __future__ import annotations

import json
import pathlib
import re
import socket
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PANEL = ROOT / "holo_pet_w3/panel/index.html"
HOST, PORT = "127.0.0.1", 8765
fails = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print("  %-6s %-46s %s" % ("✅" if ok else "🔴", name, detail))
    if not ok:
        fails.append(name)


def api(method: str, path: str, body: dict | None = None) -> dict:
    s = socket.socket()
    s.settimeout(20)
    try:
        s.connect((HOST, PORT))
        raw = json.dumps(body).encode() if body else b""
        s.sendall(("%s %s HTTP/1.0\r\nHost: x\r\nContent-Type: application/json\r\n"
                   "Content-Length: %d\r\nConnection: close\r\n\r\n"
                   % (method, path, len(raw))).encode() + raw)
        buf = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
        return json.loads(buf.split(b"\r\n\r\n", 1)[1])
    finally:
        s.close()


def main() -> int:
    # AC1 面板页
    if not PANEL.is_file():
        check("AC1 面板页存在", False, str(PANEL))
    else:
        html = PANEL.read_text(encoding="utf-8")
        check("AC1 含镜像区块", 'id="gbt-mirror"' in html)
        n_btn = len(re.findall(r'data-op="(scan|plan|simulate|parity|rehearse|release|rewind)"', html))
        check("AC1 七个入口按钮", n_btn == 7, "实得 %d" % n_btn)
        check("AC1 原有 .rail 仍在", 'class="rail"' in html)

    # AC3 只读口
    try:
        d = api("GET", "/api/mirror")
        r = (d.get("gbt_result") or {}).get("result") or d.get("result") or {}
        have = all(k in r for k in ("dimension", "reality", "timelines"))
        check("AC3 /api/mirror 可用", bool(d.get("ok")) and have,
              "keys=%s" % [k for k in ("dimension", "reality", "timelines") if k in r])
    except Exception as exc:                                  # noqa: BLE001
        check("AC3 /api/mirror 可用", False, "%s" % exc)

    # AC2 fail-closed
    try:
        d = api("POST", "/api/mirror", {"op": "bogus_op"})
        msg = str(d.get("error") or "")
        check("AC2 未知 op fail-closed", d.get("ok") is False and "fail-closed" in msg,
              msg[:60])
    except Exception as exc:                                  # noqa: BLE001
        check("AC2 未知 op fail-closed", False, "%s" % exc)

    print("\n  结果：%s" % ("全绿" if not fails else "失败 %d 项 → %s" % (len(fails), fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
