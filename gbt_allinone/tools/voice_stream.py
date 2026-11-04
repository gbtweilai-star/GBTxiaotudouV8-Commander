# -*- coding: utf-8 -*-
# gbt-capability: voice_stream  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""流式语音（P2-14 的可做面）—— 音频分段采集 + Whisper 局部/最终转写。

边界：
  · 只收 **PCM16 单声道 16kHz** base64 分片（浏览器端降采样后发送）；
  · 会话内存缓冲，上限 60s/2MB；不落永久盘（临时 WAV 即用即删）；
  · 局部转写只在显式 `partial` 且 ≥2s 时做（Whisper base 本机，CPU）；
  · **ASR 文本唤醒**：转写文本命中唤醒词；**不是声学 KWS**（无 sherpa-onnx）；
  · 识别文本按外部内容纪律处理，不做指令执行。
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import tempfile
import wave
from pathlib import Path

RATE = 16000
MAX_SECONDS = 60
MAX_BYTES = RATE * 2 * MAX_SECONDS
MAX_SESSIONS = 8
PARTIAL_MIN_S = 2.0
WAKE_WORDS = ("小土豆", "小土", "土豆", "小上游参考项目")
WAKE_VARIANTS = ("想不懂", "想不通", "想规矩", "小兔", "小度")  # 本机 Whisper base 实测误听



class StreamError(ValueError):
    pass


def decode_pcm(b64) -> bytes:
    raw = str(b64 or "").strip()
    if not raw:
        raise StreamError("pcm_base64 为空")
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception:  # noqa: BLE001
        raise StreamError("pcm_base64 不是合法 base64")
    if len(data) % 2:
        raise StreamError("PCM16 字节数必须是偶数")
    if len(data) > MAX_BYTES:
        raise StreamError("单片超过 60s")
    return data


def detect_wake(text: str) -> dict:
    """ASR-based wake：转写文本匹配唤醒词；不是声学 KWS。"""
    norm = "".join(ch for ch in str(text or "") if ch not in "，。！？、,.!? \t\n")
    for w in WAKE_WORDS + WAKE_VARIANTS:
        if w and w in norm:
            return {"ok": True, "wake": True, "word": w, "method": "asr_text_match_fuzzy"}
    return {"ok": True, "wake": False, "word": "", "method": "asr_text_match_fuzzy"}


def stats(pcm: bytes) -> dict:
    import numpy as np
    a = np.frombuffer(pcm, dtype="<i2")
    if a.size == 0:
        return {"samples": 0, "duration": 0.0, "rms": 0.0, "peak": 0.0}
    f = a.astype("float32") / 32768.0
    return {"samples": int(a.size), "duration": round(a.size / RATE, 3),
            "rms": round(float((f ** 2).mean() ** 0.5), 5),
            "peak": round(float(abs(f).max()), 5)}


def write_wav(path, pcm: bytes, rate: int = RATE) -> dict:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return {"ok": True, "path": str(path), "bytes": len(pcm),
            "duration": round(len(pcm) / 2 / rate, 3)}


class StreamStore:
    def __init__(self, max_sessions=MAX_SESSIONS):
        self.sessions = {}
        self.max_sessions = max_sessions

    def start(self, sid=None) -> dict:
        if len(self.sessions) >= self.max_sessions:
            oldest = next(iter(self.sessions))
            self.sessions.pop(oldest, None)
        sid = str(sid or ("vs-" + secrets.token_hex(6)))
        self.sessions[sid] = {"pcm": bytearray(), "created": 0.0}
        return {"ok": True, "session": sid, "rate": RATE, "max_seconds": MAX_SECONDS,
                "partial_min_s": PARTIAL_MIN_S}

    def append(self, sid, b64) -> dict:
        sess = self.sessions.get(str(sid))
        if not sess:
            return {"ok": False, "error": "no_such_session"}
        data = decode_pcm(b64)
        if len(sess["pcm"]) + len(data) > MAX_BYTES:
            return {"ok": False, "error": "session_too_long", "max_seconds": MAX_SECONDS}
        sess["pcm"].extend(data)
        st = stats(bytes(sess["pcm"]))
        return {"ok": True, "session": str(sid), "bytes": len(sess["pcm"]), **st}

    def get(self, sid):
        sess = self.sessions.get(str(sid))
        return bytes(sess["pcm"]) if sess else b""

    def reset(self, sid) -> dict:
        sess = self.sessions.get(str(sid))
        if sess:
            sess["pcm"] = bytearray()
        return {"ok": True, "session": str(sid), "cleared": bool(sess)}

    def end(self, sid) -> dict:
        sess = self.sessions.pop(str(sid), None)
        if not sess:
            return {"ok": False, "error": "no_such_session"}
        pcm = bytes(sess["pcm"])
        return {"ok": True, "session": str(sid), "pcm": pcm, **stats(pcm)}


_STORE = StreamStore()


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    import numpy as np
    pcm = np.zeros(16000, dtype="<i2").tobytes()
    check = stats(pcm)
    ck("静音 stats", check["duration"] == 1.0 and check["rms"] == 0.0, check)
    ck("base64 解码", decode_pcm(base64.b64encode(pcm).decode()) == pcm)
    ck("空片拒", _raises(lambda: decode_pcm("")))
    ck("坏 base64 拒", _raises(lambda: decode_pcm("!!!")))
    ck("奇数拒", _raises(lambda: decode_pcm(base64.b64encode(b"abc").decode())))
    store = StreamStore()
    s = store.start("t1")
    ck("start", s["ok"] and s["rate"] == RATE)
    a = store.append("t1", base64.b64encode(pcm).decode())
    ck("append", a["ok"] and a["samples"] == 16000 and a["duration"] == 1.0, a)
    ck("未知 session", store.append("nope", base64.b64encode(pcm).decode())["ok"] is False)
    ck("reset", store.reset("t1")["ok"] and store.get("t1") == b"")
    store.append("t1", base64.b64encode(pcm).decode())
    e = store.end("t1")
    ck("end 返回 pcm", e["ok"] and len(e["pcm"]) == len(pcm) and "pcm" in e)
    ck("end 后无 session", store.end("t1")["ok"] is False)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        w = write_wav(Path(d) / "x.wav", pcm)
        ck("WAV 写入", w["ok"] and Path(d).joinpath("x.wav").is_file())
        with wave.open(str(Path(d) / "x.wav"), "rb") as fh:
            ck("WAV 参数", fh.getframerate() == RATE and fh.getnchannels() == 1 and fh.getsampwidth() == 2)
    ck("唤醒词命中", detect_wake("你好，小土豆")["wake"] is True)
    ck("唤醒词不命中", detect_wake("今天天气")["wake"] is False)
    ck("schema 可达", "rate" in run("schema") and "max_seconds" in run("schema"))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (StreamError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "rate": RATE, "max_seconds": MAX_SECONDS,
                "max_bytes": MAX_BYTES, "partial_min_s": PARTIAL_MIN_S,
                "kws": "asr_text_match_fuzzy", "acoustic_kws": False, "wake_words": list(WAKE_WORDS),
                "note": "PCM16 分片 + 局部/最终 Whisper + 文本模糊唤醒；非声学 KWS"}
    if op == "start":
        return _STORE.start(params.get("session"))
    if op == "chunk":
        return _STORE.append(params.get("session"), params.get("pcm_base64"))
    if op == "reset":
        return _STORE.reset(params.get("session"))
    if op == "end":
        return _STORE.end(params.get("session"))
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/start/chunk/reset/end/verify）" % op)
