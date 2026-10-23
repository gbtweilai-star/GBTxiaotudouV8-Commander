# -*- coding: utf-8 -*-
"""V6 数据层：V5 全部读数 + 语音/蓝牙真实探测结果。"""
import json
import time
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
OUT = BASE / ".scratch" / "v6_manifest.json"

M = json.loads((BASE / ".scratch" / "v5_manifest.json").read_text(encoding="utf-8"))
P = json.loads((BASE / ".scratch" / "voice_bt_probe2.json").read_text(encoding="utf-8"))
P0 = json.loads((BASE / ".scratch" / "voice_bt_probe.json").read_text(encoding="utf-8"))


def R(tag):
    return (P.get(tag) or {}).get("result") or {}


def D(tag):
    """被拦时把缺的作用域与授权命令一并带出来（如实报缺）。"""
    v = P.get(tag) or {}
    return {"denied": bool(v.get("denied")), "reason": v.get("reason"),
            "scopes": v.get("scopes") or [], "missing": v.get("missing") or [],
            "how_to_grant": (v.get("result") or {}).get("how_to_grant") or []}


bt_status = R("bt_status")
scan = R("bt_scan")
classic = R("bt_classic")
btc = R("btc_status")
vo = (P0.get("vo_list") or {}).get("result") or {}
vstatus = R("voice_status")
asr = (P0.get("voice_asr") or {}).get("result") or {}

M["device"] = {
    "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "voice": {
        "tts_backend": vstatus.get("tts"),
        "asr_state": vstatus.get("asr"),
        "asr_missing": asr.get("missing") or "GBT_ASR_BASE_URL / GBT_ASR_API_KEY",
        "tts_gate": D("voice_tts"),
        "skills_total": vo.get("count"),
        "skills": [{"name": s.get("name"), "domain": s.get("domain"),
                    "provider": s.get("provider"), "license": s.get("license")}
                   for s in (vo.get("skills") or [])],
        "promote_rule": "本机只跑得动 2 项（Kokoro-82M / sherpa-onnx）→ 未升格为独立 tab；升格条件：云后端到位且能展示真状态",
    },
    "bluetooth": {
        "ble_backend": bt_status.get("ble_backend"),
        "classic_backend": bt_status.get("classic_backend"),
        "ops": bt_status.get("ops") or [],
        "scan_ms": (P.get("bt_scan") or {}).get("ms"),
        "devices": scan.get("devices") or [],
        "classic_gate": D("bt_classic"),
        "protocols": btc.get("protocol_library") or [],
        "btc_ops": btc.get("ops") or [],
        "intent_gate": D("btc_intent"),
        "fixed_at": "2026-09-21 安装 bleak 3.0.2（+9 个 winrt 包）后 scan 由 needs_dependency 转 ok",
    },
}

OUT.write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
d = M["device"]
print("写出:", OUT)
print("语音: tts=%s | asr=%s | 技能 %s 项" % (d["voice"]["tts_backend"], d["voice"]["asr_state"], d["voice"]["skills_total"]))
print("   TTS 门: missing=%s" % d["voice"]["tts_gate"]["missing"])
print("蓝牙: ble=%s | classic=%s | 扫到 %d 台 (%sms)" % (
    d["bluetooth"]["ble_backend"], d["bluetooth"]["classic_backend"],
    len(d["bluetooth"]["devices"]), d["bluetooth"]["scan_ms"]))
for x in d["bluetooth"]["devices"]:
    print("   -", x.get("address"), "rssi", x.get("rssi"), x.get("name"))
print("   经典态门: missing=%s | 协议库 %d 条" % (
    d["bluetooth"]["classic_gate"]["missing"], len(d["bluetooth"]["protocols"])))
