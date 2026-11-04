# -*- coding: utf-8 -*-
# gbt-capability: kws  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""声学关键词唤醒（KWS）—— 本机 sherpa-onnx + 中文 zipformer 小模型。

模型：`state/kws/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01`（Apache-2.0，约 13MB）
关键词：`state/kws/keywords.txt`（拼音 token + @中文），当前 `x iǎo t ǔ d òu @小土豆`
本机 CPU、无网络、无密钥；没装 sherpa/模型时如实 `available=false`，不假装能唤醒。
"""
from __future__ import annotations

import hashlib
import wave
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
KWS_DIR = _ROOT / "state" / "kws"
MODEL_DIR = KWS_DIR / "sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01"
KEYWORDS = KWS_DIR / "keywords.txt"
RATE = 16000


class KwsError(ValueError):
    pass


def available() -> dict:
    try:
        import sherpa_onnx  # noqa: F401
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "sherpa-onnx 未安装", "model_dir": str(MODEL_DIR)}
    need = ["tokens.txt", "encoder-epoch-12-avg-2-chunk-16-left-64.onnx",
            "decoder-epoch-12-avg-2-chunk-16-left-64.onnx",
            "joiner-epoch-12-avg-2-chunk-16-left-64.onnx"]
    if not all((MODEL_DIR / n).is_file() for n in need):
        return {"ok": False, "reason": "KWS 模型文件不全", "model_dir": str(MODEL_DIR)}
    if not KEYWORDS.is_file() or not KEYWORDS.read_text(encoding="utf-8").strip():
        return {"ok": False, "reason": "keywords.txt 缺失/为空", "keywords": str(KEYWORDS)}
    return {"ok": True, "backend": "sherpa-onnx", "model": "zipformer-wenetspeech-3.3M",
            "license": "Apache-2.0", "model_dir": str(MODEL_DIR),
            "keywords": KEYWORDS.read_text(encoding="utf-8").strip(),
            "local": True, "network": False, "key_required": False}


_SPOTTER = None


def _spotter():
    global _SPOTTER
    if _SPOTTER is not None:
        return _SPOTTER
    import sherpa_onnx
    _SPOTTER = sherpa_onnx.KeywordSpotter(
        tokens=str(MODEL_DIR / "tokens.txt"),
        encoder=str(MODEL_DIR / "encoder-epoch-12-avg-2-chunk-16-left-64.onnx"),
        decoder=str(MODEL_DIR / "decoder-epoch-12-avg-2-chunk-16-left-64.onnx"),
        joiner=str(MODEL_DIR / "joiner-epoch-12-avg-2-chunk-16-left-64.onnx"),
        keywords_file=str(KEYWORDS), num_threads=2, provider="cpu")
    return _SPOTTER


def detect_pcm(pcm: bytes, sample_rate: int = RATE) -> dict:
    info = available()
    if not info.get("ok"):
        return {"ok": False, "wake": False, "reason": info.get("reason"), "backend": "unsupported"}
    if not pcm:
        return {"ok": True, "wake": False, "word": "", "backend": "sherpa-onnx", "reason": "empty"}
    try:
        a = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        if sample_rate != RATE and len(a):
            t = np.arange(0, len(a), sample_rate / float(RATE))
            a = a[np.clip(t.astype("int64"), 0, len(a) - 1)]
        kws = _spotter()
        s = kws.create_stream()
        s.accept_waveform(RATE, a)
        s.accept_waveform(RATE, np.zeros(int(0.66 * RATE), dtype=np.float32))
        s.input_finished()
        found = []
        while kws.is_ready(s):
            kws.decode_stream(s)
            r = kws.get_result(s)
            if r:
                found.append(r)
                kws.reset_stream(s)
        return {"ok": True, "wake": bool(found), "word": found[0] if found else "",
                "found": found, "backend": "sherpa-onnx", "method": "acoustic_kws"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "wake": False, "backend": "sherpa-onnx",
                "error": "%s: %s" % (type(e).__name__, str(e)[:160])}


def detect_wav(path) -> dict:
    try:
        with wave.open(str(path), "rb") as w:
            if w.getsampwidth() != 2:
                raise KwsError("WAV 必须是 16-bit")
            sr = w.getframerate()
            ch = w.getnchannels()
            raw = w.readframes(w.getnframes())
        a = np.frombuffer(raw, dtype="<i2")
        if ch > 1:
            a = a.reshape(-1, ch).mean(axis=1).astype("<i2")
        return detect_pcm(a.tobytes(), sr)
    except KwsError as e:
        return {"ok": False, "wake": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "wake": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    info = available()
    ck("模型可用", info.get("ok") is True, info)
    ck("本地/无密钥", info.get("local") is True and info.get("key_required") is False)
    ck("关键词含小土豆", "小土豆" in str(info.get("keywords") or ""))
    fixture = _ROOT / "tests" / "fixtures" / "kws-wake.wav"
    if fixture.is_file():
        r = detect_wav(fixture)
        ck("TTS 夹具唤醒", r.get("wake") is True, r)
    else:
        ck("TTS 夹具唤醒", False, "missing fixture")
    silent = detect_pcm(b"\x00\x00" * 8000)
    ck("静音不唤醒", silent.get("wake") is False, silent)
    ck("空 PCM", detect_pcm(b"")["wake"] is False)
    ck("schema", "model" in run("schema") and "license" in run("schema"))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (KwsError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "backend": "sherpa-onnx", "rate": RATE,
                "model": "zipformer-wenetspeech-3.3M", "license": "Apache-2.0",
                "local": True, "network": False, "key_required": False,
                "keywords_file": str(KEYWORDS), "model_dir": str(MODEL_DIR),
                "note": "声学 KWS；未装 sherpa/模型时 available=false"}
    if op == "status":
        return available()
    if op == "detect":
        return detect_pcm(params.get("pcm") or b"", int(params.get("rate") or RATE))
    if op == "detect_wav":
        return detect_wav(params.get("path") or "")
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/status/detect/detect_wav/verify）" % op)
