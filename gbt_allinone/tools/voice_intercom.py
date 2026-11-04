# -*- coding: utf-8 -*-
# gbt-capability: none  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""语音对讲内核（voice_intercom）—— 从上游参考项目语音系统蒸馏出的**我们自己的判据**。

对照来源（MIT · 只取设计，不搬代码、不引依赖）：
  · 悬浮语音球：idle/enter/frame/text/exit 五态 + 真实音量驱动球体（electron/voice-orb-preload.cjs）；
  · 唤醒词：KWS 阈值 0.35 / score 3.0 / 命中冷却 800ms（kws-process.cjs）；
  · 朗读纪律：Markdown 先剥符号、空音频算失败、纯表情不合成（src/capabilities/tools/media/speech.js）；
  · 自动朗读：语音输入触发的回复走 `tts_reply`，只回发起窗口（README「语音回复只在发起窗口播放」）。

本件只做**确定性内核**（零依赖、零设备、零出网）：
  唤醒词文本门 / 能量门 / 打断判定 / 五态状态机 / 朗读可念化 / 会话账。
真正的麦克风与 TTS 仍走既有 `voice` 能力位（过 `run_task` 门），不在这里偷开设备。
"""
from __future__ import annotations

import hashlib
import math
import re
import time

WAKE_WORDS = ("小土豆", "土豆", "嗨小土豆", "在吗小土豆", "上游参考项目", "小白龙")
STATES = ("idle", "listening", "thinking", "speaking")
MAX_SPEECH_CHARS = 1000
DEFAULT_VAD = 0.020
DEFAULT_BARGE = 0.035
MAX_TURNS = 50

_READABLE_RX = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")
_EMOJI_ONLY_RX = re.compile(r"^[\W_]+$", re.UNICODE)


def strip_markdown(text: str) -> str:
    """Markdown → 朗读纯文本（照上游参考项目 speech.js 的剥离口径，写成我们的规则）。"""
    s = str(text or "").strip()
    s = re.sub(r"^[ \t]*([-*+]|\d+[.、])\s+", "", s, flags=re.M)
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", s, flags=re.S)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s, flags=re.S)
    s = re.sub(r"\*(.+?)\*", r"\1", s, flags=re.S)
    s = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", s, flags=re.S)
    s = re.sub(r"#{1,6}\s+", "", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = s.replace("**", "")
    s = re.sub(r"\n+", " ", s)
    return s.strip()


def speakable(text: str, max_chars: int = MAX_SPEECH_CHARS) -> str:
    """可朗读化：剥符号 → 必须还有可读文字（纯表情/标点不合成）→ 截到上限。"""
    s = strip_markdown(text)
    if not s or _EMOJI_ONLY_RX.match(s) or not _READABLE_RX.search(s):
        return ""
    return s[:max_chars]


def should_wake(text: str) -> dict:
    """文本唤醒门：唤醒词必须在开头（与 KWS 的「先喊名字」同义），命中后返回剩余问句。"""
    s = str(text or "").strip()
    for w in WAKE_WORDS:
        if s.startswith(w):
            q = s[len(w):].lstrip("，,。.！!？? 、:：")
            return {"wake": True, "keyword": w, "query": q}
    return {"wake": False, "keyword": "", "query": s}


def pcm16_rms(data: bytes) -> float:
    """16-bit 单声道 PCM → 归一化 RMS（0~1）。用于能量门，不碰设备。"""
    raw = bytes(data or b"")
    if len(raw) < 2:
        return 0.0
    n = len(raw) // 2
    total = 0.0
    for i in range(n):
        v = int.from_bytes(raw[2 * i:2 * i + 2], "little", signed=True) / 32768.0
        total += v * v
    return math.sqrt(total / n)


def frames_energy(frames) -> float:
    """帧能量：接受 bytes（PCM16）或 0~1 浮点帧列表。"""
    if isinstance(frames, (bytes, bytearray)):
        return pcm16_rms(frames)
    vals = []
    for x in (frames or []):
        try:
            vals.append(abs(float(x)))
        except (TypeError, ValueError):
            continue
    if not vals:
        return 0.0
    return math.sqrt(sum(v * v for v in vals) / len(vals))


def voice_activity(frames, threshold: float = DEFAULT_VAD, min_active: int = 2) -> dict:
    """能量门：够响的帧数达到 min_active 才判『有人在说』（防单帧毛刺）。"""
    if isinstance(frames, (bytes, bytearray)):
        e = pcm16_rms(frames)
        seq = [e]
    else:
        seq = []
        for x in (frames or []):
            try:
                seq.append(abs(float(x)))
            except (TypeError, ValueError):
                continue
    active = sum(1 for x in seq if x > float(threshold))
    energy = frames_energy(seq if seq else frames)
    return {"active": active >= int(min_active) and energy > float(threshold),
            "energy": round(energy, 6), "frames": len(seq), "frames_active": active,
            "threshold": float(threshold)}


def should_barge_in(state: str, energy: float, threshold: float = DEFAULT_BARGE) -> bool:
    """打断：只在『她正在说』且用户能量过线时成立（上游参考项目的打断逻辑内核）。"""
    return str(state) == "speaking" and float(energy) > float(threshold)


class IntercomSession:
    """一轮对讲的五态账：idle → listening → thinking → speaking → listening/idle。"""

    def __init__(self, max_turns: int = MAX_TURNS):
        self.state = "idle"
        self.turns = []
        self.interrupted = 0
        self.barged_in = 0
        self.max_turns = int(max_turns)
        self.started_at = None
        self.updated_at = None

    def _touch(self):
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    def snapshot(self) -> dict:
        return {"state": self.state, "turns": len(self.turns),
                "interrupted": self.interrupted, "barged_in": self.barged_in,
                "started_at": self.started_at, "updated_at": self.updated_at,
                "last": self.turns[-1] if self.turns else None}

    def begin(self):
        self.state = "listening"
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._touch()
        return self.snapshot()

    def on_audio(self, frames, threshold: float = DEFAULT_VAD):
        va = voice_activity(frames, threshold)
        if self.state == "idle" and va["active"]:
            self.begin()
        if self.state == "speaking" and should_barge_in(self.state, va["energy"]):
            self.barged_in += 1
            self.state = "listening"
            self._touch()
        return {"state": self.state, **va}

    def on_heard(self, text: str):
        """听到一句：只认 listening 态；有唤醒词就剥掉；空问句不收。"""
        if self.state != "listening":
            return {"ok": False, "reason": "not_listening", "state": self.state}
        w = should_wake(text)
        query = str(w.get("query") or "").strip()
        if not query:
            return {"ok": False, "reason": "empty_after_wake", "wake": w, "state": self.state}
        self.turns.append({"role": "user", "text": query, "wake": bool(w.get("wake")),
                           "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        if self.turns:
            self.turns = self.turns[-self.max_turns:]
        self.state = "thinking"
        self._touch()
        return {"ok": True, "wake": w, "query": query, "state": self.state}

    def on_reply(self, text: str):
        """她回一句：可朗读才进 speaking；纯表情/空文本直接回 listening。"""
        speech = speakable(text)
        if speech:
            self.turns.append({"role": "assistant", "text": speech,
                               "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
            self.turns = self.turns[-self.max_turns:]
            self.state = "speaking"
        else:
            self.state = "listening"
        self._touch()
        return {"speech": speech, "state": self.state}

    def on_speak_done(self):
        if self.state == "speaking":
            self.state = "listening"
            self._touch()
        return self.snapshot()

    def interrupt(self):
        self.interrupted += 1
        self.state = "idle"
        self._touch()
        return self.snapshot()

    def stop(self):
        self.state = "idle"
        self._touch()
        return self.snapshot()


def verify() -> dict:
    """内建自检（确定性、零设备）；返回逐项结果，不写盘、不出网。"""
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    ck("剥加粗", strip_markdown("**你好**") == "你好")
    ck("剥代码/链接", "示例" in strip_markdown("看 [示例](https://x) 和 `代码`"))
    ck("剥标题", strip_markdown("## 标题") == "标题")
    ck("可朗读中文", speakable("你好，小土豆") != "")
    ck("纯表情不合成", speakable("😀😀") == "")
    ck("纯标点不合成", speakable("……!!!") == "")
    ck("超长截断", len(speakable("字" * 2000)) == MAX_SPEECH_CHARS)
    w = should_wake("小土豆，今天天气怎么样")
    ck("唤醒词开头", w["wake"] and w["keyword"] == "小土豆" and w["query"] == "今天天气怎么样", w)
    ck("非唤醒词", should_wake("今天天气怎么样")["wake"] is False)
    ck("上游参考项目也认", should_wake("上游参考项目在吗")["keyword"] == "上游参考项目")
    ck("静音 RMS≈0", pcm16_rms(b"\x00\x00" * 100) < 0.001)
    ck("响帧 RMS 高", pcm16_rms(b"\x00\x40" * 100) > 0.4)
    ck("静音不活跃", voice_activity([0.0] * 10)["active"] is False)
    ck("大声活跃", voice_activity([0.2] * 5)["active"] is True)
    ck("单帧毛刺不活跃", voice_activity([0.2, 0.0, 0.0])["active"] is False)
    ck("说话时可打断", should_barge_in("speaking", 0.2) is True)
    ck("待命不打断", should_barge_in("idle", 0.2) is False)
    ck("安静不打断", should_barge_in("speaking", 0.001) is False)
    s = IntercomSession()
    ck("初始 idle", s.state == "idle")
    s.begin()
    ck("开始 listening", s.state == "listening")
    r = s.on_heard("小土豆你好")
    ck("听到→thinking 且剥唤醒词", r["ok"] and s.state == "thinking"
       and r["query"] == "你好", r)
    ck("空问句不收", s.on_heard("")["ok"] is False)
    r = s.on_reply("**收到**，我在")
    ck("回复→speaking 且可朗读", r["speech"] == "收到，我在" and s.state == "speaking", r)
    r = s.on_reply("😀")
    ck("纯表情回复不进 speaking", r["speech"] == "" and s.state == "listening")
    s.state = "speaking"
    r = s.on_speak_done()
    ck("说完回 listening", r["state"] == "listening")
    s.interrupt()
    ck("打断→idle 记账", s.state == "idle" and s.interrupted == 1)
    ck("会话账有轮次", len(s.turns) >= 1)
    return {"ok": all(c["ok"] for c in checks),
            "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode("utf-8")).hexdigest()[:12]}
