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
    dh_dir = ROOT / "holo_pet_w3/dh-live"
    if (dh_dir / "index.html").is_file() and (dh_dir / "dh-live.js").is_file():
        dh = (dh_dir / "index.html").read_text(encoding="utf-8")
        check("数字人设置弹窗元素", all(k in dh for k in ('id="dh-gear"', 'id="dh-settings"',
                                                        'id="vs-voice"', 'id="vs-rate"',
                                                        'id="vs-asr"', 'id="vs-auto"')))
        js = (dh_dir / "dh-live.js").read_text(encoding="utf-8")
        check("设置读写/应用到朗读", all(k in js for k in ("DH_SETTINGS", "loadVoiceSettings",
                                                    "saveVoiceSettings", "tts_rate")))
    else:
        # dh-live 面板随「旧 28 面板拆除」（2026-11-01）永久下线：主仓、.archive/panels-20261101、
        # payload 三处都没有这两个文件。原来这里硬读不存在的路径 ⇒ 整个测试抛 FileNotFoundError
        # 崩掉，读者只看到崩栈、看不到「面板已下线」这个事实。改为显式 skip 并写明去向（2026-11-04）。
        print("  skip 数字人设置弹窗（dh-live 面板已下线，主仓/归档/payload 三处均无此文件）")
    payload = None
    for _cand in (ROOT.parent / "GBT小土豆V8桌面版" / "payload",
                  ROOT.parent / "GBT-builds" / "GBT小土豆V8桌面版" / "payload",
                  pathlib.Path("D:/GBT-builds/GBT小土豆V8桌面版/payload")):
        if _cand.is_dir():
            payload = _cand
            break
    if payload is not None:
        check("APP payload 已同步 voice_settings",
              (payload / "gbt_allinone/tools/voice_settings.py").is_file()
              and '"voice_settings": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
              and '"/api/voice/settings"' in (payload / "tools/console-server.py").read_text(encoding="utf-8"))
    else:
        # 2026-11-04：打包产物已从桌面迁至 D:/GBT-builds（主仓留桌面当唯一真源）。
        # 找不到 payload 就明说跳过，而不是假装通过、也不是崩。
        print("  skip APP payload 同步检查（未找到 payload 目录；产物已迁至 D:/GBT-builds）")
    # 文档归类后搬进 docs/legacy/（2026-11-01 仓库整理），仍按「这两处任一处存在」判，
    # 免得整理一次目录就红一次。
    _doc164 = next((p for p in (ROOT / "docs/164-voice-settings.md",
                                ROOT / "docs/legacy/164-voice-settings.md") if p.is_file()), None)
    check("落地文档 docs/164 存在", _doc164 is not None, "docs/ 与 docs/legacy/ 都没找到")

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
