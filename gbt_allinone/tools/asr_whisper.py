# -*- coding: utf-8 -*-
# gbt-capability: none  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""本机语音识别（Whisper 小模型，可选）—— 数字人/对讲的高准确率耳。

背景（主人实测 2026-11-02）：Windows 桌面识别器把「小土豆，今天天气怎么样」
听成「不给路」⇒ 她答非所问。这里加一条**本机 Whisper** 腿：
  · 模型：`state/whisper/base`（faster-whisper base · 145MB · CPU int8）；
  · 只吃 WAV（浏览器 getUserMedia 已经生成 16k 单声道，无需 ffmpeg/PyAV）；
  · 没有模型/依赖时如实 `available()=false`，调用方回退 Windows 识别器；
  · 不写盘、不出网（模型本地）；识别文本仍是**数据**，不是指令。
"""
from __future__ import annotations

import importlib.util
import threading
import time
import wave

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "state" / "whisper" / "base"
_MODEL = None
_LOCK = threading.Lock()


def available() -> dict:
    if importlib.util.find_spec("faster_whisper") is None:
        return {"ok": False, "reason": "faster_whisper 未安装", "model_dir": str(MODEL_DIR)}
    if not (MODEL_DIR / "model.bin").is_file():
        return {"ok": False, "reason": "模型不在 state/whisper/base", "model_dir": str(MODEL_DIR)}
    return {"ok": True, "model": "base", "model_dir": str(MODEL_DIR),
            "license": "MIT（faster-whisper）· 模型 Systran/faster-whisper-base"}


def _load():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _LOCK:
        if _MODEL is None:
            from faster_whisper import WhisperModel
            _MODEL = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8")
    return _MODEL


def _decode_wav(path: str):
    import numpy as np
    with wave.open(path, "rb") as w:
        n, ch, sr, sw = w.getnframes(), w.getnchannels(), w.getframerate(), w.getsampwidth()
        raw = w.readframes(n)
    if sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 4:
        a = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sw == 1:
        a = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        a = (a - 128.0) / 128.0
    else:
        raise ValueError("unsupported sample width %s" % sw)
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != 16000 and len(a):
        t = np.arange(0, len(a), sr / 16000.0)
        idx = np.clip(t.astype("int64"), 0, len(a) - 1)
        a = a[idx]
    return a


def transcribe(wav_path: str, language: str = "zh", timeout: float | None = None,
               initial_prompt: str | None = None) -> dict:
    """WAV → 文本。返回 {ok, heard, text, backend, language, duration, ms}；失败如实。"""
    info = available()
    if not info.get("ok"):
        return {"ok": False, "status": "needs_dependency", "error": info.get("reason"),
                "backend": "faster-whisper:base", "model_dir": str(MODEL_DIR)}
    t0 = time.time()
    try:
        audio = _decode_wav(wav_path)
        if audio.size == 0 or float(abs(audio).max()) < 0.001:
            return {"ok": True, "heard": False, "text": "", "backend": "faster-whisper:base",
                    "status": "quiet", "reason": "WAV 是静音（不是识别器坏）",
                    "ms": int((time.time() - t0) * 1000)}
        model = _load()
        segs, meta = model.transcribe(
            audio, language=language, vad_filter=True, beam_size=1,
            initial_prompt=str(initial_prompt or "以下是普通话的句子，请用简体中文输出。"),
            condition_on_previous_text=False)
        text = "".join((s.text or "") for s in segs).strip()
        return {"ok": True, "heard": bool(text), "text": text,
                "backend": "faster-whisper:base", "language": meta.language,
                "duration": round(float(meta.duration or 0), 2),
                "status": "ok" if text else "quiet",
                "reason": None if text else "没识别出文字（安静或口音）",
                "ms": int((time.time() - t0) * 1000)}
    except Exception as exc:                                    # noqa: BLE001
        return {"ok": False, "status": "error", "backend": "faster-whisper:base",
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                "ms": int((time.time() - t0) * 1000)}
