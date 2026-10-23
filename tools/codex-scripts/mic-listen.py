# -*- coding: utf-8 -*-
"""耳：录一句话 → 本地识别 → 出文字（一条命令跑完）。

## 为什么有这件
2026-10-23 严判探针 `mic-probe.py --sweep` 首次拿到**真采样**：
`index 9 · 麦克风 (Realtek HD Audio Mic input) · 48000Hz · REAL · peak=0.0292 · rms=1.8e-4`。
但「能录到数」不等于「听清说了什么」——本件补最后一跳：录音 → 落 wav → 调本机 zh-CN 识别器 → 打印文字。

## 判据（写死）
· 录音必须 REAL（float32 的 |值| ≤ 1 且 rms > 1e-4）；SILENCE/GARBAGE 一律不送去识别（别拿噪声当语音）。
· 识别器返回 `heard=false` 就如实报「没听到语音」，不许编文字。

用法：
  py -3 tools/codex-scripts/mic-listen.py                 # 自动挑最优设备，录 6 秒并识别
  py -3 tools/codex-scripts/mic-listen.py --device 9 --seconds 8
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASR = os.path.join(ROOT, "tools", "codex-scripts", "asr-listen.ps1")
REAL_RMS_MIN = 1e-4


def probe_devices():
    import sounddevice as sd
    apis = sd.query_hostapis()
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) > 0:
            out.append({"index": i, "name": d["name"][:56], "api": apis[d["hostapi"]]["name"],
                        "sr": int(d["default_samplerate"])})
    return out


def speech_score(a, sr):
    """语音带能量（300–3400 Hz）占总能量的比例 + 该带 RMS；用来区分"人声"与"电流声/静默"。"""
    import numpy as np
    x = np.asarray(a, dtype="float64")
    if x.size < sr // 2:
        return {"band_rms": 0.0, "ratio": 0.0}
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    freqs = np.fft.rfftfreq(x.size, 1.0 / sr)
    band = (freqs >= 300) & (freqs <= 3400)
    tot = float(np.sum(spec ** 2)) or 1e-30
    band_e = float(np.sum(spec[band] ** 2))
    band_rms = float(np.sqrt(np.mean(np.square(x)) * (band_e / tot)))
    return {"band_rms": round(band_rms, 8), "ratio": round(band_e / tot, 4)}


def record(index, seconds):
    import numpy as np
    import sounddevice as sd
    for sr in (48000, 44100, 16000, 8000):
      for attempt in (1, 2, 3):
        # 每个采样率最多试 3 轮：Realtek 采集引脚会间歇性返回静默
        # （2026-10-23 实测：同一端点 一次 REAL peak=0.029 / 一次 SILENCE peak=0 ⇒ 必须重试再判）
        try:
            rec = sd.rec(int(sr * seconds), samplerate=sr, channels=1, device=index,
                         dtype="float32", blocking=True)
            a = np.asarray(rec).ravel()
            with np.errstate(invalid="ignore", over="ignore"):
                peak = float(np.max(np.abs(a))) if a.size else 0.0
                rms = float(np.sqrt(np.mean(np.square(a, dtype="float64")))) if a.size else 0.0
            real = bool(np.isfinite(peak) and 0 < peak <= 1.0 and rms > REAL_RMS_MIN)
            sc = speech_score(a, sr)
            if real:
                return a, sr, {"peak": round(peak, 6), "rms": round(rms, 8),
                               "verdict": "REAL", **sc}
        except Exception:                                     # noqa: BLE001
            continue
    return None, None, {"verdict": "NO_REAL_CAPTURE"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=-1)
    ap.add_argument("--seconds", type=float, default=6.0)
    a = ap.parse_args()

    devs = probe_devices()
    if not devs:
        print(json.dumps({"ok": False, "why": "PortAudio 看不到任何输入设备"}, ensure_ascii=False))
        return 2
    idx = a.device if a.device >= 0 else None
    if idx is None:
        # 优先 Realtek 麦克风（不是立体声混音），其次第一个
        pick = next((d for d in devs if "麦克风" in d["name"] and "混音" not in d["name"]), None) \
            or next((d for d in devs if "Mic" in d["name"]), None) or devs[0]
        idx = pick["index"]

    print("开始录音，请对着电脑说话……", flush=True)
    a_, sr, stat = record(idx, a.seconds)
    if a_ is None:
        print(json.dumps({"ok": False, "device": idx, "why": "没拿到真采样（静默/垃圾）", "stat": stat},
                         ensure_ascii=False, indent=1))
        return 1

    import numpy as np
    out_wav = os.path.join(ROOT, "state", "ear-live.wav")
    w = wave.open(out_wav, "wb")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((np.clip(a_, -1, 1) * 32767).astype(np.int16).tobytes())
    w.close()

    r = subprocess.run(["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ASR,
                        "-WavFile", out_wav], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    text = (r.stdout or "").strip()
    try:
        asr = json.loads(text.splitlines()[-1]) if text else {}
    except Exception:                                         # noqa: BLE001
        asr = {"raw": text[:300]}
    print(json.dumps({"ok": bool(asr.get("heard")), "device": idx, "record": stat, "wav": out_wav,
                      "asr": asr}, ensure_ascii=False, indent=1))
    return 0 if asr.get("heard") else 1


if __name__ == "__main__":
    raise SystemExit(main())
