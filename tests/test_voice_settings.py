# -*- coding: utf-8 -*-
"""语音设置契约 + 统一门 + API + 数字人设置弹窗 + APP 接线验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import voice_settings as VS  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:200])


def main() -> int:
    print("[1] 契约自检（范围/白名单/偏好解析）")
    r = VS.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 15", r["checks"] >= 15, r["checks"])
    check("默认值合法", VS.validate({})["asr_backend"] == "auto")
    check("未知字段丢弃", "evil" not in VS.validate({"evil": 1}))
    for bad in ({"tts_rate": 9}, {"tts_pitch": 0.1}, {"tts_volume": 2},
                {"asr_backend": "cloud"}, {"culture": "xx-XX"},
                {"tts_voice": "<script>"}):
        try:
            VS.validate(bad)
            check("坏设置拒 " + str(list(bad)), False, bad)
        except VS.SettingsError:
            check("坏设置拒 " + str(list(bad)), True)

    print("[2] 音色解析")
    voices = [{"name": "Microsoft David - English (US)", "lang": "en-US"},
              {"name": "Microsoft Hanhan - Chinese (Traditional, Taiwan)", "lang": "zh-TW"},
              {"name": "Microsoft Huihui - Chinese (Simplified, PRC)", "lang": "zh-CN"}]
    r = VS.resolve({"tts_voice": "", "tts_rate": 1.1}, voices)
    check("偏好 Hanhan", "Hanhan" in r["voice"] and r["lang"] == "zh-TW", r)
    r2 = VS.resolve({"tts_voice": "Microsoft Huihui - Chinese (Simplified, PRC)"}, voices)
    check("显式音色", "Huihui" in r2["voice"] and r2["rate"] == 0.98, r2)
    check("语速透传", VS.resolve({"tts_rate": 1.2}, voices)["rate"] == 1.2)
    check("空 voices 不报错", VS.resolve({}, [])["voice"] == "")

    print("[3] 统一门 / API / 数字人设置弹窗 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表有 voice_settings", '"voice_settings": {' in reg
          and '"handler": "voice_settings"' in reg)
    check("api 分派 voice_settings", 'kind == "voice_settings"' in api)
    check("run_task 可达 voice_settings", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server 有 /api/voice/settings", '"/api/voice/settings"' in srv
          and "voice_settings" in srv)
    dh = (ROOT / "holo_pet_w3/dh-live/index.html").read_text(encoding="utf-8")
    check("数字人设置弹窗元素", all(k in dh for k in ('id="dh-gear"', 'id="dh-settings"',
                                                    'id="vs-voice"', 'id="vs-rate"',
                                                    'id="vs-asr"', 'id="vs-auto"')))
    js = (ROOT / "holo_pet_w3/dh-live/dh-live.js").read_text(encoding="utf-8")
    check("设置读写/应用到朗读", all(k in js for k in ("DH_SETTINGS", "loadVoiceSettings",
                                                "saveVoiceSettings", "tts_rate")))
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 voice_settings",
              (payload / "gbt_allinone/tools/voice_settings.py").is_file()
              and '"voice_settings": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
              and '"/api/voice/settings"' in (payload / "tools/console-server.py").read_text(encoding="utf-8"))
    check("落地文档 docs/164 存在", (ROOT / "docs/164-voice-settings.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— 语音设置契约（范围/白名单/解析）+ 统一门 + API + 数字人弹窗/APP 接线全绿")
    return 0


def _gate_ok() -> bool:
    try:
        import gbt_allinone as g
        r = g.run_task("voice_settings", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
