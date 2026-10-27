#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""voice_fix —— 把 espeak 那种"机器人"音修得顺耳一点（纯 numpy，不联网）。

为什么需要：成片旁白只能用 espeak（美嘉导不出文件），而 espeak 中文刺耳。
它刺耳的原因不是音高，是 **2–5 kHz 的能量太硬**（齿音区）+ 没有动态起伏。

四步（都可量）：
  ① 音高上移 6%（颗粒重排，时长不变）
  ② 高频软化：2.5–5 kHz 降 4 dB，7 kHz 以上滚降
  ③ 轻微谐波增强：120–200 Hz 抬 2 dB（让它有胸腔感）
  ④ 软压缩：把过硬的瞬态压平

用法： python3 tools/voice_fix.py in.wav [--out out.wav] [--semi 1.06]
"""
import argparse, wave
import numpy as np


def read(p):
    w = wave.open(p, "rb")
    sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
    a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    w.close()
    return a, sr


def write(p, a, sr):
    a = np.clip(a, -1, 1)
    w = wave.open(p, "wb")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((a * 32767).astype(np.int16).tobytes())
    w.close()


def pitch_up(a, sr, factor=1.06, grain_ms=30):
    """颗粒重排：每 30ms 取一段、按 factor 重采样后再拼回去，时长不变。"""
    g = int(sr * grain_ms / 1000)
    hop = int(g * 0.5)
    out = np.zeros_like(a)
    win = np.hanning(g).astype(np.float32)
    i = 0
    while i + g < len(a):
        seg = a[i:i + g]
        idx = np.arange(0, g, factor)
        idx = idx[idx < g - 1]
        rs = np.interp(idx, np.arange(g), seg)
        L = min(len(rs), g)
        out[i:i + L] += rs[:L] * win[:L]
        i += hop
    peak = np.max(np.abs(out)) or 1.0
    return out / peak * np.max(np.abs(a))


def eq(a, sr, harsh_db=-4.0, low_db=2.0, hp_db=-6.0):
    n = len(a)
    A = np.fft.rfft(a)
    f = np.fft.rfftfreq(n, 1 / sr)
    g = np.zeros_like(f)
    # 低架：120-200 Hz 抬
    g += low_db * np.clip((220 - f) / 220, 0, 1)
    # 刺耳区：2.5-5 kHz 降
    band = np.clip((f - 2000) / 500, 0, 1) * np.clip((5500 - f) / 500, 0, 1)
    g += harsh_db * band
    # 7k 以上滚降
    g += hp_db * np.clip((f - 7000) / 3000, 0, 1)
    return np.fft.irfft(A * (10 ** (g / 20)), n)


def compress(a, thresh=0.35, ratio=3.0, attack=0.005, release=0.12, sr=44100):
    env = np.abs(a)
    # 一阶平滑近似
    ka, kr = np.exp(-1 / (sr * attack)), np.exp(-1 / (sr * release))
    e = np.zeros_like(env); prev = 0.0
    for i, v in enumerate(env):
        k = ka if v > prev else kr
        prev = k * prev + (1 - k) * v
        e[i] = prev
    over = e > thresh
    gain = np.ones_like(a)
    gain[over] = (thresh + (e[over] - thresh) / ratio) / e[over]
    return a * gain


def harshness(a, sr):
    """2–5 kHz 能量占比 —— 越小越不刺耳。"""
    A = np.abs(np.fft.rfft(a)) ** 2
    f = np.fft.rfftfreq(len(a), 1 / sr)
    tot = A.sum() or 1
    return float(A[(f >= 2000) & (f <= 5000)].sum() / tot)


def f0(a, sr):
    seg = a[int(sr * 0.3):int(sr * 0.7)]
    if len(seg) < 2000:
        return 0
    seg = seg - seg.mean()
    c = np.correlate(seg, seg, "full")[len(seg) - 1:]
    lo, hi = int(sr / 400), int(sr / 70)
    return round(sr / (np.argmax(c[lo:hi]) + lo), 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--out"); ap.add_argument("--semi", type=float, default=1.06)
    a = ap.parse_args()
    x, sr = read(a.src)
    h0, p0 = harshness(x, sr), f0(x, sr)
    y = pitch_up(x, sr, a.semi)
    y = eq(y, sr)
    y = compress(y, sr=sr)
    y = y / (np.max(np.abs(y)) or 1) * 0.95
    out = a.out or a.src.replace(".wav", "_fix.wav")
    write(out, y, sr)
    print("音高   %.1f → %.1f Hz（+%.0f%%）" % (p0, f0(y, sr), (a.semi - 1) * 100))
    print("刺耳区 2–5k 能量占比 %.4f → %.4f（%.0f%%↓）" % (h0, harshness(y, sr),
                                                    (1 - harshness(y, sr) / max(h0, 1e-9)) * 100))
    print("输出   %s" % out)
