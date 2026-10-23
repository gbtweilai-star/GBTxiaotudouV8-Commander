# gbt-capability: 真语音活动检测（SileroVAD · onnxruntime 权重推理，不依赖 torch）
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""真 SileroVAD（ONNX 权重）· 只吃 onnxruntime，绝不碰 torch / torchaudio。

为什么单独成模块（而不是塞进 omni_audio）：
  2026-09 装 silero-vad 包时，pip 把 torch 2.13.0 降级到 2.9.1 并拖进 torchaudio，
  直接打断了 torchvision(::nms) 与 easyocr。教训：**权重与运行时必须解耦**。
  这里只做一件事——用已在盘的 `store/models/*.onnx` 做真推理，
  onnxruntime 缺失或权重缺失时**结构化拒绝**，由调用方退回轻量能量法，
  绝不自作降级、绝不假装听懂了。

实测口径（2026-09-22 本机量测，非文档抄录）：
  input[None,None] + state[2,None,128] + sr(int64) -> output[None,1] + stateN
  窗 = 576 = 64 上下文 + 512 新样本 @16k；跳 = 512（32 ms/帧）
  静音 1.0s -> max 0.0089 / mean 0.0047
  真语音 5.24s（SAPI 合成）-> max 1.0000 / mean 0.6947，163 帧中 112 帧 > 0.5
"""
from __future__ import annotations

import hashlib
import sys
import wave
from pathlib import Path

import numpy as np

DEFAULT_SR = 16000
HOP = 512                 # 每次推进的新样本数
CONTEXT = 64              # 上一窗尾部保留的上下文
WINDOW = HOP + CONTEXT    # 576：与 silero_vad_openvino_16k.onnx 写死的 [1,576] 吻合
FRAME_MS = HOP / DEFAULT_SR * 1000.0   # 32.0 ms

# 优先序按**实测可加载 + 契约最宽**排，不按文件名想当然
MODEL_PREFERENCE = (
    "silero_vad.onnx",                # 动态窗 + sr，最宽
    "silero_vad_16k_op15.onnx",       # 动态窗 + sr
    "silero_vad_op18_ifless.onnx",    # 动态窗 + sr，静态 state
    "silero_vad_half.onnx",           # 动态窗，无 sr
    "silero_vad_openvino_16k.onnx",   # 写死 [1,576]
    "silero_vad_16k_sequence.onnx",   # LSTM 批式，逐窗接口不适用
)
# 逐窗（state+sr）接口可用的模型；sequence 模型只能整段批跑，不在此列
_PER_CHUNK_MODELS = tuple(m for m in MODEL_PREFERENCE if "sequence" not in m)

ENGINE = "silero-vad-onnx"


class SileroVadUnavailable(RuntimeError):
    """结构化不可用：不是崩溃，是"这里确实没有"，调用方据此退回轻量法。"""

    def __init__(self, info: dict):
        super().__init__(info.get("why", "silero vad unavailable"))
        self.info = info


# ---------------------------------------------------------------- 权重发现

def models_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "store" / "models"


def _sha16(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16].upper()


def _contract(inputs, outputs) -> str:
    """按真实会话的入参形状判契约——不认文件名。"""
    names = [i.name for i in inputs]
    if "h" in names and "c" in names:
        return "lstm_sequence"
    last = inputs[0].shape[-1] if inputs and inputs[0].shape else None
    if isinstance(last, int) and last == WINDOW:
        return "fixed_window"
    if "sr" in names:
        return "stateful_sr"
    if "state" in names:
        return "stateful_nosr"
    return "unknown"


def list_models(with_hash: bool = True) -> list[dict]:
    """盘上有什么权重就报什么，含真实契约与校验和（不假设、不美化）。"""
    d = models_dir()
    out: list[dict] = []
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.onnx")):
        rec = {"name": p.name, "bytes": p.stat().st_size, "path": str(p)}
        if with_hash:
            rec["sha256_16"] = _sha16(p)
        try:
            import onnxruntime as ort
            so = ort.SessionOptions()
            so.log_severity_level = 3
            s = ort.InferenceSession(str(p), so, providers=["CPUExecutionProvider"])
            rec["inputs"] = [[i.name, str(i.type), list(i.shape)] for i in s.get_inputs()]
            rec["outputs"] = [[o.name, str(o.type), list(o.shape)] for o in s.get_outputs()]
            rec["contract"] = _contract(s.get_inputs(), s.get_outputs())
            rec["loadable"] = True
        except Exception as e:                              # noqa: BLE001
            rec["loadable"] = False
            rec["error"] = f"{type(e).__name__}: {e}"[:180]
        out.append(rec)
    return out


def _pick(model: str | None = None) -> Path:
    d = models_dir()
    if model:
        p = d / model if not Path(model).is_absolute() else Path(model)
        if not p.is_file():
            raise SileroVadUnavailable({
                "ok": False, "unavailable": True, "denied": False, "engine": ENGINE,
                "rule": "silero-vad-onnx:model",
                "why": f"指定的权重不存在：{model}",
                "missing": [str(p)],
                "available": [m.name for m in sorted(d.glob('*.onnx'))] if d.is_dir() else [],
            })
        return p
    for name in _PER_CHUNK_MODELS:
        p = d / name
        if p.is_file():
            return p
    raise SileroVadUnavailable({
        "ok": False, "unavailable": True, "denied": False, "engine": ENGINE,
        "rule": "silero-vad-onnx:weights",
        "why": "store/models 下没有可用的逐窗 SileroVAD 权重",
        "missing": [str(d / n) for n in _PER_CHUNK_MODELS],
        "available": [m.name for m in sorted(d.glob('*.onnx'))] if d.is_dir() else [],
    })


def probe(model: str | None = None, with_hash: bool = True) -> dict:
    """体检：onnxruntime 在不在 · 权重在不在 · 真会话能否建立。"""
    info: dict = {
        "ok": False, "engine": ENGINE, "models_dir": str(models_dir()),
        "expected_window": WINDOW, "hop": HOP, "frame_ms": round(FRAME_MS, 3),
    }
    try:
        import onnxruntime as ort
        info["onnxruntime"] = getattr(ort, "__version__", "?")
        info["providers_available"] = list(ort.get_available_providers())
    except Exception as e:                                  # noqa: BLE001
        info["why"] = f"onnxruntime 不可用：{type(e).__name__}: {e}"
        info["missing"] = ["onnxruntime"]
        info["models"] = list_models(with_hash=False)
        return info
    info["models"] = list_models(with_hash=with_hash)
    try:
        p = _pick(model)
        so = ort.SessionOptions()
        so.log_severity_level = 3
        s = ort.InferenceSession(str(p), so, providers=["CPUExecutionProvider"])
    except SileroVadUnavailable as e:
        info.update(e.info)
        return info
    except Exception as e:                                  # noqa: BLE001
        info["why"] = f"权重装载失败：{type(e).__name__}: {e}"
        return info
    info.update({
        "ok": True, "model": p.name, "model_path": str(p),
        "model_bytes": p.stat().st_size,
        "model_sha256_16": _sha16(p) if with_hash else None,
        "providers": list(s.get_providers()),
        "contract": _contract(s.get_inputs(), s.get_outputs()),
        "runnable": True,
        "note": "真 SileroVAD 权重推理（onnxruntime CPU），非能量启发式；全程不 import torch",
    })
    return info


# ---------------------------------------------------------------- 音频预备

def prepare_audio(x, source_sr: int = DEFAULT_SR) -> np.ndarray:
    """任何合理输入 -> float32 单声道 16k，值域 [-1,1]。"""
    if isinstance(x, (str, Path)):
        return read_wav_mono16k(x)
    if isinstance(x, (bytes, bytearray, memoryview)):
        a = np.frombuffer(x, dtype="<i2").astype(np.float32) / 32768.0
    elif isinstance(x, np.ndarray):
        a = x
        if a.dtype == np.int16:
            a = a.astype(np.float32) / 32768.0
        elif a.dtype != np.float32:
            a = a.astype(np.float32)
        if a.ndim == 2:                     # (n, ch) 或 (ch, n)
            a = a.mean(axis=1) if a.shape[0] > a.shape[1] else a.mean(axis=0)
    else:
        a = np.asarray(x, dtype=np.float32)
    a = np.ascontiguousarray(a.reshape(-1), dtype=np.float32)
    peak = float(np.max(np.abs(a))) if a.size else 0.0
    if peak > 1.5:                          # 明显是未归一的整型量纲
        a = a / 32768.0
    if source_sr and int(source_sr) != DEFAULT_SR and a.size > 1:
        n = int(round(a.size * DEFAULT_SR / int(source_sr)))
        try:
            from scipy.signal import resample_poly             # noqa: PLC0415
            from math import gcd                               # noqa: PLC0415
            g = gcd(int(source_sr), DEFAULT_SR)
            a = resample_poly(a, DEFAULT_SR // g, int(source_sr) // g).astype(np.float32)
        except Exception:                                      # noqa: BLE001
            a = np.interp(np.linspace(0, a.size - 1, n),
                          np.arange(a.size), a).astype(np.float32)
    return np.ascontiguousarray(a, dtype=np.float32)


def read_wav_mono16k(path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 1:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sw == 4:
        a = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"不支持的位深：{sw * 8} bit")
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return prepare_audio(a, sr)


# ---------------------------------------------------------------- 推理器

class SileroVad:
    """逐窗有状态 VAD。一实例=一路流；换流必须 reset()。"""

    def __init__(self, model: str | None = None, sr: int = DEFAULT_SR):
        try:
            import onnxruntime as ort
        except Exception as e:                              # noqa: BLE001
            raise SileroVadUnavailable({
                "ok": False, "unavailable": True, "denied": False, "engine": ENGINE,
                "rule": "silero-vad-onnx:runtime",
                "why": f"onnxruntime 不可用：{type(e).__name__}: {e}",
                "missing": ["onnxruntime"],
            }) from e
        if int(sr) != DEFAULT_SR:
            # 权重带 sr 入参时可吃 8k；本仓只用 16k，其余一律先重采样，避免"看着能跑其实喂错"
            raise SileroVadUnavailable({
                "ok": False, "unavailable": True, "denied": False, "engine": ENGINE,
                "rule": "silero-vad-onnx:sr",
                "why": f"本封装只走 {DEFAULT_SR} Hz；请先用 prepare_audio 重采样",
                "missing": [], "got_sr": int(sr),
            })
        p = _pick(model)
        so = ort.SessionOptions()
        so.log_severity_level = 3
        self._sess = ort.InferenceSession(str(p), so, providers=["CPUExecutionProvider"])
        self.model_path = p
        self.model_name = p.name
        self.sr = DEFAULT_SR
        ins = {i.name: i for i in self._sess.get_inputs()}
        self.has_sr = "sr" in ins
        self._in = list(ins.keys())
        self._out = [o.name for o in self._sess.get_outputs()]
        self.providers = list(self._sess.get_providers())
        self.contract = _contract(self._sess.get_inputs(), self._sess.get_outputs())
        self.reset()

    # -- 状态
    def reset(self) -> None:
        self._ctx = np.zeros((1, CONTEXT), dtype=np.float32)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._n = 0

    def __repr__(self) -> str:                              # pragma: no cover
        return f"<SileroVad {self.model_name} {self.contract} {self.providers}>"

    # -- 单帧
    def prob(self, frame) -> float:
        a = np.asarray(frame, dtype=np.float32).reshape(-1)
        if a.size != HOP:
            raise ValueError(f"每帧必须恰好 {HOP} 样本（= {FRAME_MS:.0f} ms @16k），收到 {a.size}")
        x = np.concatenate([self._ctx, a.reshape(1, -1)], axis=1)     # 1 x 576
        feed = {"input": x, "state": self._state}
        if self.has_sr:
            feed["sr"] = np.array(self.sr, dtype=np.int64)
        outs = self._sess.run(None, feed)
        m = {n: v for n, v in zip(self._out, outs)}
        p = float(np.asarray(m.get("output", outs[0])).reshape(-1)[0])
        st = m.get("stateN", outs[1] if len(outs) > 1 else None)
        self._ctx = x[:, -CONTEXT:]
        if st is not None:
            self._state = np.asarray(st, dtype=np.float32).reshape(2, 1, 128)
        self._n += 1
        return p

    # -- 整段
    def probs(self, audio, reset: bool = True) -> list[float]:
        a = prepare_audio(audio)
        if reset:
            self.reset()
        n = int(a.size // HOP)
        return [self.prob(a[i * HOP:(i + 1) * HOP]) for i in range(n)]

    def segments(self, audio, threshold: float = 0.5, min_speech_ms: float = 250.0,
                 min_silence_ms: float = 100.0, speech_pad_ms: float = 30.0,
                 neg_threshold: float | None = None) -> list[dict]:
        p = self.probs(audio)
        total_ms = len(p) * FRAME_MS
        if not p:
            return []
        neg = threshold - 0.15 if neg_threshold is None else float(neg_threshold)
        # 迟滞双阈：进用 threshold，出用 neg，避免阈值边缘反复抖动
        runs: list[list[int]] = []
        cur: list[int] | None = None
        for i, v in enumerate(p):
            if cur is None:
                if v >= threshold:
                    cur = [i, i]
            else:
                cur[1] = i
                if v < neg:
                    runs.append(cur)
                    cur = None
        if cur is not None:
            runs.append(cur)
        # 短静音合并
        merged: list[list[int]] = []
        for r in runs:
            if merged and (r[0] - merged[-1][1]) * FRAME_MS < min_silence_ms:
                merged[-1][1] = r[1]
            else:
                merged.append(list(r))
        pad = int(round(speech_pad_ms / FRAME_MS))
        out: list[dict] = []
        for a0, b0 in merged:
            if (b0 - a0 + 1) * FRAME_MS < min_speech_ms:
                continue
            a1, b1 = max(0, a0 - pad), min(len(p) - 1, b0 + pad)
            seg_p = p[a0:b0 + 1]
            out.append({
                "start_frame": a0, "end_frame": b0,
                "start_s": round(a1 * FRAME_MS / 1000.0, 4),
                "end_s": round((b1 + 1) * FRAME_MS / 1000.0, 4),
                "duration_s": round((b1 + 1 - a1) * FRAME_MS / 1000.0, 4),
                "frames": b0 - a0 + 1,
                "mean_prob": round(sum(seg_p) / len(seg_p), 4),
                "max_prob": round(max(seg_p), 4),
            })
        return out


# ---------------------------------------------------------------- 一站式

def vad_silero(audio, model: str | None = None, threshold: float = 0.5,
               min_speech_ms: float = 250.0, min_silence_ms: float = 100.0,
               speech_pad_ms: float = 30.0) -> dict:
    """给触手用的一站式入口。不可用时**结构化拒绝**，不抛穿、不假装。"""
    base = {"engine": ENGINE, "threshold": threshold, "chunk_ms": round(FRAME_MS, 3)}
    try:
        v = SileroVad(model)
    except SileroVadUnavailable as e:
        d = dict(e.info)
        d.setdefault("available", [m["name"] for m in list_models(with_hash=False)])
        d["fallback"] = "audio_vad_energy（轻量能量法，非神经网络）"
        return {**base, **d}
    a = prepare_audio(audio)
    probs = v.probs(a)
    segs = v.segments(a, threshold=threshold, min_speech_ms=min_speech_ms,
                      min_silence_ms=min_silence_ms, speech_pad_ms=speech_pad_ms)
    speech_frames = sum(1 for x in probs if x >= threshold)
    return {
        **base,
        "ok": True, "denied": False,
        "model": v.model_name, "model_bytes": v.model_path.stat().st_size,
        "model_sha256_16": _sha16(v.model_path),
        "providers": v.providers, "contract": v.contract,
        "samples": int(a.size), "duration_s": round(a.size / DEFAULT_SR, 4),
        "frames": len(probs), "speech_frames": speech_frames,
        "speech_ratio": round(speech_frames / len(probs), 4) if probs else 0.0,
        "max_prob": round(max(probs), 4) if probs else 0.0,
        "mean_prob": round(sum(probs) / len(probs), 4) if probs else 0.0,
        "segments": segs, "segment_count": len(segs),
        "has_speech": bool(segs) or (max(probs, default=0.0) >= threshold),
        "note": "真 SileroVAD 神经网络权重推理；不依赖 torch/torchaudio",
    }


def engine_info() -> dict:
    """给 MANIFEST / 体检报告引用，避免再写"回环听得见"那种没量过的漂亮话。"""
    p = probe(with_hash=False)
    return {
        "engine": ENGINE,
        "available": bool(p.get("ok")),
        "onnxruntime": p.get("onnxruntime"),
        "model": p.get("model"),
        "contract": p.get("contract"),
        "providers": p.get("providers"),
        "frame_ms": round(FRAME_MS, 3),
        "window": WINDOW,
        "model_count": len(p.get("models", [])),
        "fallback": "audio_vad_energy（轻量能量法）",
        "why_not_available": p.get("why"),
    }


def _selftest() -> int:                                     # pragma: no cover
    p = probe()
    print("onnxruntime =", p.get("onnxruntime"))
    print("权重目录    =", p.get("models_dir"))
    for m in p.get("models", []):
        print("  %-32s %9d B  %-15s %s%s" % (
            m["name"], m["bytes"], m.get("contract", "-"),
            m.get("sha256_16", ""), "" if m.get("loadable") else "  ✗ " + m.get("error", "")))
    if not p.get("ok"):
        print("不可用：", p.get("why"))
        return 1
    print("选用        =", p["model"], p["model_sha256_16"], p["providers"])
    v = SileroVad()
    sil = np.zeros(DEFAULT_SR, dtype=np.float32)
    ps = v.probs(sil)
    print("静音 1.0s   : 帧=%d max=%.4f mean=%.4f" % (len(ps), max(ps), sum(ps) / len(ps)))
    r = vad_silero(sil)
    print("一站式静音  : ok=%s has_speech=%s segments=%d" % (r["ok"], r["has_speech"], r["segment_count"]))
    # 合成一段真语音（SAPI 写文件，不占声卡）
    try:
        import tempfile
        import pythoncom
        import win32com.client as wc
        pythoncom.CoInitialize()
        tmp = Path(tempfile.gettempdir()) / "_gbt_silero_selftest.wav"
        st = wc.Dispatch("SAPI.SpFileStream")
        st.Open(str(tmp), 3, False)
                # 2026-10-16 主人令：用户可听的语音一律走 voice_cap 的台湾腔女声（zh-TW-HsiaoChenNeural）；
        # 本处 SAPI 仅用于**自检**（判断本机能不能出声），不作为对外语音默认。
        vo = wc.Dispatch("SAPI.SpVoice")
        vo.AudioOutputStream = st
        vo.Speak("你好，我是小土豆，正在做语音活动检测。")
        st.Close()
        sp = read_wav_mono16k(tmp)
        rs = vad_silero(sp)
        print("真语音 %.2fs : 帧=%d max=%.4f mean=%.4f 语音帧=%d 段=%d %s" % (
            rs["duration_s"], rs["frames"], rs["max_prob"], rs["mean_prob"],
            rs["speech_frames"], rs["segment_count"],
            ["%.2f→%.2fs" % (s["start_s"], s["end_s"]) for s in rs["segments"]]))
    except Exception as e:                                  # noqa: BLE001
        print("真语音自测跳过（无 TTS 文件输出）：%s: %s" % (type(e).__name__, e))
    print("torch 已加载 =", "torch" in sys.modules, "· torchaudio 已加载 =", "torchaudio" in sys.modules)
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(_selftest())
