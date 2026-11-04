# -*- coding: utf-8 -*-
# gbt-capability: voice_settings  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""语音设置（我们自己的）—— 数字人 TTS/ASR 的可配置面。

对照上游参考项目的「设置 → 语音识别 / TTS Provider / 音色 / 参数」：
只取**设置契约**，不搬它的 Provider/SDK；落成我们自己的本地参数：
  · TTS：音色名（系统中文女声优先 Hanhan/Yating/Huihui/Yaoyao/Xiaoxiao）、语速/音高/音量；
  · ASR：auto（Whisper 优先）/ whisper（只本机 Whisper）/ windows（只 Windows 识别器）；
  · 语言 zh-CN/zh-TW/en-US；自动朗读开关。
本件只做**校验/解析/自检**（纯函数，不写盘）；持久化由 console-server 以 trusted-owner 写
`state/voice-settings.json`（与现有设置同一条本地写面），能力位 zero-scope。
"""
from __future__ import annotations

import hashlib
import re

DEFAULTS = {
    "tts_voice": "",
    "tts_rate": 0.98,
    "tts_pitch": 1.0,
    "tts_volume": 1.0,
    "asr_backend": "auto",
    "culture": "zh-CN",
    "auto_speak": True,
}
BACKENDS = ("auto", "whisper", "windows")
CULTURES = ("zh-CN", "zh-TW", "en-US")
VOICE_PREF = ("Hanhan", "Yating", "Huihui", "Yaoyao", "Xiaoxiao", "Tracy")
MAX_VOICE = 80
_RATE = (0.5, 1.5)
_PITCH = (0.5, 1.5)
_VOLUME = (0.0, 1.0)


class SettingsError(ValueError):
    pass


def schema() -> dict:
    return {"ok": True, "defaults": dict(DEFAULTS), "asr_backends": list(BACKENDS),
            "cultures": list(CULTURES),
            "ranges": {"tts_rate": list(_RATE), "tts_pitch": list(_PITCH),
                       "tts_volume": list(_VOLUME)},
            "voice_prefer": list(VOICE_PREF),
            "note": "设置只改本地行为；不新增出网/Provider 依赖"}


def _num(value, name, lo, hi) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise SettingsError("%s 必须是数字" % name)
    if not (lo <= v <= hi):
        raise SettingsError("%s 范围 %.2f..%.2f" % (name, lo, hi))
    return round(v, 3)


def validate(patch) -> dict:
    """把补丁合并到 DEFAULTS 后校验；未知字段丢弃（不报错，设置向前兼容）。"""
    if not isinstance(patch, dict):
        raise SettingsError("settings 必须是对象")
    out = dict(DEFAULTS)
    for k, v in patch.items():
        if k in out:
            out[k] = v
    voice = str(out.get("tts_voice") or "").strip()
    if len(voice) > MAX_VOICE:
        raise SettingsError("tts_voice 超长（>%d）" % MAX_VOICE)
    if voice and re.search(r"[<>\x00-\x1f]", voice):
        raise SettingsError("tts_voice 含非法字符")
    out["tts_voice"] = voice
    out["tts_rate"] = _num(out.get("tts_rate"), "tts_rate", *_RATE)
    out["tts_pitch"] = _num(out.get("tts_pitch"), "tts_pitch", *_PITCH)
    out["tts_volume"] = _num(out.get("tts_volume"), "tts_volume", *_VOLUME)
    backend = str(out.get("asr_backend") or "auto").strip().lower()
    if backend not in BACKENDS:
        raise SettingsError("asr_backend 只允许 %s" % ",".join(BACKENDS))
    out["asr_backend"] = backend
    culture = str(out.get("culture") or "zh-CN").strip()
    if culture not in CULTURES:
        raise SettingsError("culture 只允许 %s" % ",".join(CULTURES))
    out["culture"] = culture
    out["auto_speak"] = bool(out.get("auto_speak"))
    return out


def resolve(settings, voices=None) -> dict:
    """解析出实际使用的音色（没有 voices 列表时只回偏好名）。"""
    s = validate(settings or {})
    names = []
    for v in (voices or []):
        if isinstance(v, dict):
            names.append(str(v.get("name") or ""))
        else:
            names.append(str(v or ""))
    chosen = ""
    if s["tts_voice"]:
        for n in names:
            if n == s["tts_voice"]:
                chosen = n
                break
    if not chosen:
        for pref in VOICE_PREF:
            for n in names:
                if pref.lower() in n.lower():
                    chosen = n
                    break
            if chosen:
                break
    lang = s["culture"]
    if chosen:
        for v in (voices or []):
            if isinstance(v, dict) and v.get("name") == chosen and v.get("lang"):
                lang = v.get("lang")
                break
    return {"voice": chosen, "lang": lang, "rate": s["tts_rate"],
            "pitch": s["tts_pitch"], "volume": s["tts_volume"],
            "asr_backend": s["asr_backend"], "auto_speak": s["auto_speak"],
            "settings": s}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    ck("默认合法", validate({})["asr_backend"] == "auto")
    ck("未知字段丢弃", "evil" not in validate({"evil": 1}))
    ck("语速范围", _raises(lambda: validate({"tts_rate": 9})))
    ck("音高范围", _raises(lambda: validate({"tts_pitch": 0.1})))
    ck("音量范围", _raises(lambda: validate({"tts_volume": 2})))
    ck("后端白名单", _raises(lambda: validate({"asr_backend": "cloud"})))
    ck("语言白名单", _raises(lambda: validate({"culture": "xx-XX"})))
    ck("音色非法字符", _raises(lambda: validate({"tts_voice": "<script>"})))
    ck("音色超长", _raises(lambda: validate({"tts_voice": "a" * 100})))
    ck("auto_speak 布尔", validate({"auto_speak": 0})["auto_speak"] is False)
    voices = [{"name": "Microsoft David - English (US)", "lang": "en-US"},
              {"name": "Microsoft Hanhan - Chinese (Traditional, Taiwan)", "lang": "zh-TW"},
              {"name": "Microsoft Huihui - Chinese (Simplified, PRC)", "lang": "zh-CN"}]
    r = resolve({"tts_voice": "", "culture": "zh-CN"}, voices)
    ck("偏好 Hanhan", "Hanhan" in r["voice"] and r["lang"] == "zh-TW", r)
    r2 = resolve({"tts_voice": "Microsoft Huihui - Chinese (Simplified, PRC)"}, voices)
    ck("显式音色生效", "Huihui" in r2["voice"], r2)
    r3 = resolve({"tts_voice": "NoSuchVoice"}, voices)
    ck("无效音色回偏好", "Hanhan" in r3["voice"], r3)
    ck("rate 传递", resolve({"tts_rate": 1.2}, voices)["rate"] == 1.2)
    ck("空 voices 不报错", resolve({}, [])["voice"] == "")
    ck("schema 字段", set(schema()["defaults"]) >= {"tts_voice", "asr_backend", "auto_speak"})
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except SettingsError:
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return schema()
    if op == "validate":
        try:
            return {"ok": True, "settings": validate(params.get("settings") or {})}
        except SettingsError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "resolve":
        try:
            return {"ok": True, **resolve(params.get("settings") or {},
                                          params.get("voices") or [])}
        except SettingsError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/validate/resolve/verify）" % op)
