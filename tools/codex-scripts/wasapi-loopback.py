#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**WASAPI 回环录音**（录"电脑正在放什么"，不碰麦克风引脚）

开发者：自由的风 · 本署名不可删除、不可篡改归属

## 为什么要有它（2026-10-18 主人令「缺啥就抓取成熟能力补齐」）
本机录音侧现读：`waveInGetNumDevs()=0`、MME/DirectSound/WASAPI 的 `default_input` 全是 `-1`；
WDM-KS 能看见 Realtek 麦克风 #9 / 立体声混音 #10，但**两条都「流开起来了却 0 帧」**
（引脚没被 Windows 路由）。⇒ 传统"开采集设备"那条路在本机走不通。

而 **WASAPI loopback** 录的是**播放端点**的回环：本机扬声器状态 `OK`，
所以这条路不依赖任何采集引脚。成熟件已经在本机：`PyAudioWPatch 0.2.12.8`（3.12 解释器）。

## 它是什么 / 不是什么
  · 是：把「系统正在播放的声音」录成 WAV（16k/16bit/单声道，直接喂离线识别器）。
  · 不是：不是麦克风；**录不到房间里的说话声**。它能证明"耳朵这条链是通的"，
    也能做"她说什么 → 回环抓回来 → 再识别"的闭环演示；真听人说话仍要一个被路由的麦。

## 用法
  python tools/codex-scripts/wasapi-loopback.py --seconds 3 --out .scratch/lo.wav --json
  python tools/codex-scripts/wasapi-loopback.py --list          # 只列回环端点
退出码：0 录到 · 5 录不到（带原因）· 6 缺依赖（没装 PyAudioWPatch）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

SR = 16000          # 离线识别器口径


def emit(ok, status, reason, **kw):
    o = {"ok": ok, "status": status, "reason": reason}
    o.update(kw)
    print(json.dumps(o, ensure_ascii=False))
    return 0 if ok else 5


def _pa():
    try:
        import pyaudiowpatch as pyaudio
        return pyaudio
    except Exception as e:  # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, str(e)[:120])


def list_loopbacks():
    got = _pa()
    if isinstance(got, tuple):
        return None, got[1]
    pyaudio = got
    p = pyaudio.PyAudio()
    try:
        out = []
        for i in range(p.get_device_count()):
            d = p.get_device_info_by_index(i)
            if d.get("isLoopbackDevice"):
                out.append({"index": i, "name": d.get("name"),
                            "sr": int(d.get("defaultSampleRate") or 0),
                            "ch": int(d.get("maxInputChannels") or 0)})
        return out, None
    finally:
        p.terminate()


def record(seconds: float):
    got = _pa()
    if isinstance(got, tuple):
        return {"ok": False, "status": "needs_dependency",
                "why": "PyAudioWPatch 不可用（%s）——装它：pip install PyAudioWPatch" % got[1]}
    pyaudio = got
    p = pyaudio.PyAudio()
    try:
        try:
            dev = p.get_default_wasapi_loopback()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status": "no_loopback",
                    "why": "拿不到默认回环端点：%s: %s" % (type(e).__name__, str(e)[:120])}
        idx = int(dev["index"])
        sr = int(dev.get("defaultSampleRate") or 48000)
        ch = max(1, int(dev.get("maxInputChannels") or 2))
        frames = []

 # 2026-10-18 实测：**阻塞式 st.read() 会挂死**（180s 超时）。
        #    原因：WASAPI 回环在"当前没有声音在放"时不一定持续喂满缓冲，
        #    阻塞读就把整条命令吊在那里。⇒ 改**回调式 + 墙钟硬超时**，
        #    没声音时也能拿到静音帧（静音≠坏，peak=0 会如实报）。
        def cb(in_data, frame_count, time_info, status):  # noqa: ANN001
            frames.append(in_data)
            return (None, pyaudio.paContinue)

        try:
            st = p.open(format=pyaudio.paInt16, channels=ch, rate=sr, input=True,
                        input_device_index=idx, frames_per_buffer=1024,
                        stream_callback=cb)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status": "open_failed",
                    "why": "打开回环流失败：%s: %s" % (type(e).__name__, str(e)[:120]),
                    "device": dev.get("name")}
        try:
            st.start_stream()
            deadline = time.time() + float(seconds) + 2.0      # 硬上限，绝不无限等
            while time.time() < deadline and len(frames) * 1024 < sr * float(seconds):
                time.sleep(0.05)
        finally:
            try:
                st.stop_stream()
                st.close()
            except Exception:  # noqa: BLE001
                pass
        if not frames:
            return {"ok": False, "status": "no_frames",
                    "why": "回环流一帧都没有：**当前没有声音在播放**"
                           "（WASAPI 回环只在渲染端点有输出时喂数据；空闲就静默——这是固件行为，不是坏了）",
                    "device": dev.get("name")}
        raw = np.frombuffer(b"".join(frames), dtype="<i2")
        if ch > 1:
            raw = raw.reshape(-1, ch).mean(axis=1)
        x = raw.astype(np.float64)
        if sr != SR and x.size > 1:
            n_out = max(1, int(round(x.size * SR / sr)))
            x = np.interp(np.linspace(0.0, x.size - 1.0, n_out),
                          np.arange(x.size, dtype=np.float64), x)
        return {"ok": True, "x": x, "device": dev.get("name"), "api": "WASAPI loopback",
                "native_sr": sr, "channels": ch}
    finally:
        p.terminate()


def main():
    ap = argparse.ArgumentParser(description="WASAPI 回环录音（录系统播放，不碰麦克风）")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--out", default=os.path.join("state", "loopback.wav"))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.list:
        rows, why = list_loopbacks()
        if rows is None:
            return emit(False, "needs_dependency", why or "PyAudioWPatch 不可用")
        print("回环端点 %d 个：" % len(rows))
        for r in rows:
            print("  #%-3d sr=%-6d ch=%d  %s" % (r["index"], r["sr"], r["ch"], r["name"]))
        return 0

    t0 = time.time()
    res = record(a.seconds)
    if not res.get("ok"):
        return emit(False, res.get("status") or "no_frames", res.get("why") or "回环录制失败",
                    device=res.get("device"))
    x = res["x"]
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    rms = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    try:
        with wave.open(a.out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(np.clip(x, -32768, 32767).astype("<i2").tobytes())
    except Exception as e:  # noqa: BLE001
        return emit(False, "write_failed", "写 WAV 失败：%s" % e, out=a.out)

    out = {"ok": True, "status": "recorded", "seconds": round(time.time() - t0, 2),
           "frames": int(x.size), "peak": round(peak, 1), "rms": round(rms, 1),
           "wav": a.out, "bytes": os.path.getsize(a.out),
           "device": res.get("device"), "api": res.get("api"),
           "native_sr": res.get("native_sr"), "out_sr": SR,
           "_口径": "回环录的是**系统播放**，不是房间里的说话声；peak/rms 为 0 = 当下没在放声音"}
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print("回环录到 %s（%s）%.2fs · %d 帧 · peak=%.0f rms=%.1f"
              % (out["device"], out["api"], out["seconds"], out["frames"], peak, rms))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
