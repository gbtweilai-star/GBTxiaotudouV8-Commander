# -*- coding: utf-8 -*-
"""实测：语音与蓝牙到底能不能真跑（走 run_task 正规入口）。
TTS 用 out= 写文件，不发声，避免打扰。
"""
import json
import sys
import time
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
OUT = BASE / ".scratch" / "voice_bt_probe.json"
WAV = BASE / ".scratch" / "tts_probe.wav"

from gbt_allinone import api as API  # noqa: E402

res = {}


def call(tag, kind, payload):
    t0 = time.time()
    try:
        r = API.run_task(kind, payload, safe=True)
        env = (r or {}).get("gbt_result") or r or {}
        res[tag] = {"kind": kind, "payload": payload, "ms": int((time.time() - t0) * 1000),
                    "status": env.get("status"), "result": env.get("result"), "error": env.get("error")}
    except Exception as exc:  # noqa: BLE001
        res[tag] = {"kind": kind, "payload": payload, "ms": int((time.time() - t0) * 1000),
                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:260])}


call("voice_status", "voice", {"op": "status"})
call("voice_tts_file", "voice", {"op": "tts", "text": "能力中枢在线，语音合成链路正常。", "out": str(WAV)})
call("voice_asr", "voice", {"op": "asr", "audio": str(WAV)})
call("bluetooth_status", "bluetooth", {"op": "status"})
call("bluetooth_scan", "bluetooth", {"op": "scan"})
call("btc_status", "bt_control", {"op": "status"})
call("vo_status", "voice_orchestra", {"op": "status"})
call("vo_list", "voice_orchestra", {"op": "list"})

if WAV.exists():
    res["wav_file"] = {"path": str(WAV), "bytes": WAV.stat().st_size}

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
for k, v in res.items():
    if k == "wav_file":
        print("[wav] %s bytes=%s" % (v["path"], v["bytes"]))
        continue
    body = json.dumps(v.get("result") or v.get("error"), ensure_ascii=False, default=str)
    print("[%s] %sms status=%s" % (k, v.get("ms"), v.get("status")))
    print("    " + body[:520])
print("写出:", OUT)
