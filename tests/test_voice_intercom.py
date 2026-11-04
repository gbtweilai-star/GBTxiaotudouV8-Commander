# -*- coding: utf-8 -*-
"""语音对讲内核 + console/APP 接线验收（确定性，不碰麦克风/不出网）。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import voice_intercom as VI  # noqa: E402

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
    print("[1] 内核自检（唤醒/能量门/打断/朗读纪律/五态）")
    r = VI.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 25", r["checks"] >= 25, r["checks"])
    check("剥加粗/链接", VI.strip_markdown("**你好** [x](https://a) `b`") == "你好 x b",
          VI.strip_markdown("**你好** [x](https://a) `b`"))
    check("纯表情不可朗读", VI.speakable("😀😀😀") == "")
    check("超长截断 1000", len(VI.speakable("字" * 2000)) == VI.MAX_SPEECH_CHARS)
    w = VI.should_wake("小土豆，看一下屏幕")
    check("唤醒词开头 + 剥问句", w["wake"] and w["query"] == "看一下屏幕", w)
    check("非唤醒词不触发", VI.should_wake("看一下屏幕")["wake"] is False)
    check("PCM 静音 RMS≈0", VI.pcm16_rms(b"\x00\x00" * 64) < 1e-3)
    check("PCM 大声 RMS 高", VI.pcm16_rms(b"\x00\x40" * 64) > 0.4)
    check("能量门：静音不活跃", VI.voice_activity([0.0] * 8)["active"] is False)
    check("能量门：大声活跃", VI.voice_activity([0.2] * 4)["active"] is True)
    check("打断只在 speaking", VI.should_barge_in("speaking", 0.2) is True
          and VI.should_barge_in("idle", 0.2) is False)

    print("[2] 五态会话账")
    s = VI.IntercomSession()
    check("初始 idle", s.state == "idle")
    s.begin()
    check("开始 → listening", s.state == "listening")
    h = s.on_heard("小土豆在吗")
    check("听到 → thinking 且剥唤醒词", h["ok"] and s.state == "thinking"
          and h["query"] == "在吗", h)
    check("空问句不收", s.on_heard("")["ok"] is False)
    rep = s.on_reply("**你好**，我在")
    check("回复 → speaking 且剥符号", rep["speech"] == "你好，我在" and s.state == "speaking", rep)
    check("纯表情回复不进 speaking", s.on_reply("😀")["speech"] == "")
    s.state = "speaking"
    check("说完回 listening", s.on_speak_done()["state"] == "listening")
    s.interrupt()
    check("打断 → idle 且记账", s.state == "idle" and s.interrupted == 1)

    print("[3] 数字人语音对讲 / APP 接线")
    srv = (ROOT / "tools" / "console-server.py").read_text(encoding="utf-8")
    check("server /api/asr 收 wav_b64", '"/api/asr"' in srv and "wav_b64" in srv)
    check("server ASR 先走本机 Whisper", "asr_whisper" in srv and "whisper:" in srv)
    check("asr_whisper 模块在盘上", (ROOT / "gbt_allinone/tools/asr_whisper.py").is_file())
    dh_index = (ROOT / "holo_pet_w3/dh-live/index.html").read_text(encoding="utf-8")
    check("数字人页有 MIC/对话面板/输入条",
          all(k in dh_index for k in ('id="mic"', 'id="dh-log"', 'id="dh-text"',
                                      'id="dh-send"', 'dh-chip')))
    dh_js = (ROOT / "holo_pet_w3/dh-live/dh-live.js").read_text(encoding="utf-8")
    check("数字人页用 getUserMedia + wav_b64", "getUserMedia" in dh_js
          and "wav_b64" in dh_js and "/api/asr" in dh_js)
    check("数字人朗读显式中文女声（无英文默认回退）",
          "pickZhVoice" in dh_js and "Hanhan" in dh_js and "不出声" in dh_js)
    check("数字人说话前有对话气泡 + 剥 Markdown", "pushBubble" in dh_js
          and "plainSpeech" in dh_js)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    appjs = (ROOT / "holo_pet_w3/console/app.js").read_text(encoding="utf-8")
    check("圆球 UI 已移除（载体=数字人）", "voice-orb" not in idx and "voice-orb" not in appjs)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步语音对讲/Whisper",
              (payload / "gbt_allinone/tools/voice_intercom.py").is_file()
              and (payload / "gbt_allinone/tools/asr_whisper.py").is_file()
              and '"/api/asr"' in (payload / "tools/console-server.py").read_text(encoding="utf-8"))

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— 数字人对讲内核（唤醒/能量门/打断/朗读纪律/五态）+ console/APP 接线全绿")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
