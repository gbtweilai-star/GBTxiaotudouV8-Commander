# -*- coding: utf-8 -*-
"""A19 三态诊断（2026-10-30）

为什么要它：以前只知道"连不上"，分不清是哪一种坏 ——
  ① 服务没起（端口拒绝）      → 只能去 LM Pocket 的 Server 面板点 Start / 开 Auto-Start
  ② 服务起了但钥匙不对（401）  → 密钥要和小写 gbt 一致
  ③ CORS 没开（页面直连被拦）  → 但走桥不需要 CORS，这条只影响页面直连

界面上确认过的字段（App Store 截图 OCR 原文）：
  Server · Start · Port(1234) · Auto-Start · Local Only · Remote Access · CORS
  · Configuration · Authorization: Bearer · POST /v1/chat/completions
"""
from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request

KEY = "gbt"


def probe(host: str = "127.0.0.1", port: int = 1234, key: str = KEY) -> dict:
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
    except Exception as e:                                          # noqa: BLE001
        return {"state": "port_closed", "host": host, "port": port,
                "detail": type(e).__name__,
                "action": "去 LM Pocket → Server → 点 Start，并把 **Auto-Start** 打开"}

    req = urllib.request.Request("http://%s:%d/v1/models" % (host, port),
                                 headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.loads(r.read())
            return {"state": "ok", "host": host, "port": port,
                    "models": [m.get("id") for m in (d.get("data") or [])][:5]}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {"state": "bad_key", "host": host, "port": port, "http": e.code,
                    "action": "服务是通的，但密钥不对：把 LM Pocket 里的 Bearer 改成小写 gbt（或设 GBT_A19_KEY）"}
        return {"state": "http_error", "host": host, "port": port, "http": e.code}
    except Exception as e:                                          # noqa: BLE001
        return {"state": "no_http", "host": host, "port": port,
                "detail": type(e).__name__,
                "action": "端口能连但 HTTP 不应答（可能被挂起），重开 App 再试"}


def main() -> int:
    hosts = ["127.0.0.1"]
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 53))
        hosts.append(s.getsockname()[0])
        s.close()
    except Exception:                                               # noqa: BLE001
        pass
    hosts.append("::1")
    results = [probe(h) for h in hosts]
    best = next((r for r in results if r["state"] == "ok"), None) or results[0]
    print(json.dumps({"results": results, "verdict": best}, ensure_ascii=False, indent=1))
    return 0 if best["state"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
