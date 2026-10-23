# -*- coding: utf-8 -*-
"""装了 bleak 之后复测蓝牙；同时确认语音的授权门依旧（不该变）。"""
import json
import sys
import time
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
OUT = BASE / ".scratch" / "voice_bt_probe2.json"
from gbt_allinone import api as API  # noqa: E402

res = {}


def call(tag, kind, payload):
    t0 = time.time()
    try:
        r = API.run_task(kind, payload)
        env = (r or {}).get("gbt_result") or r or {}
        res[tag] = {"kind": kind, "payload": payload, "ms": int((time.time() - t0) * 1000),
                    "status": env.get("status"), "result": env.get("result"),
                    "error": env.get("error"), "denied": env.get("denied"),
                    "missing": env.get("missing"), "scopes": env.get("scopes")}
    except Exception as exc:  # noqa: BLE001
        res[tag] = {"kind": kind, "payload": payload, "ms": int((time.time() - t0) * 1000),
                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:260])}


call("bt_status", "bluetooth", {"op": "status"})
call("bt_scan", "bluetooth", {"op": "scan"})
call("bt_classic", "bluetooth", {"op": "classic"})
call("btc_status", "bt_control", {"op": "status"})
call("btc_intent", "bt_control", {"op": "parse_intent", "intent": "把客厅的灯打开"})
call("voice_status", "voice", {"op": "status"})
call("voice_tts", "voice", {"op": "tts", "text": "能力中枢在线"})

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
for k, v in res.items():
    body = json.dumps(v.get("result") or v.get("error"), ensure_ascii=False, default=str)
    print("[%s] %sms status=%s denied=%s" % (k, v.get("ms"), v.get("status"), v.get("denied")))
    print("    " + body[:560])
print("写出:", OUT)
