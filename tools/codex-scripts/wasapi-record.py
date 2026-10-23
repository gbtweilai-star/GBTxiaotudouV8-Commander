#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主脑离线听觉 · 录音件（走 WASAPI/PortAudio，**绕开旧版 winmm 映射器**）

## 为什么需要它（第 59 轮，本机实测）
`asr-listen.ps1` 的设备直连走 `SetInputToDefaultAudioDevice()`，底层是**旧版 waveIn 映射器**；
本机现读 `waveInGetNumDevs() = 0` ⇒ 那条路**永远**打不开。本件改用 PortAudio，
把声音落成 **16 kHz / 16 bit / 单声道 WAV**（离线中文识别器吃的格式），
再交给 `asr-listen.ps1 -WavFile` 识别 ⇒ 整条腿与 winmm 无关。

## 本机现读的设备层事实（不许含糊）
- 权威 API（MMDevice）录音侧 **5 个端点 · 在场的 0 个**：1 禁用（`立体声混音`）/ 1 已拔出 / 3 不在场
- 三个角色的**默认录音设备全都不存在**（`找不到元素`）
- MME 0 · DirectSound 0 · WASAPI 0 个输入端点；WDM-KS 列 4 个引脚但**全部打不开**
- ⇒ 本件现在会如实报 `no_input`。**要让耳朵通，需要有一个「在场的」录音端点**：
  在「设置 → 系统 → 声音 → 更多声音设置 → 录制」里右键显示禁用的设备，
  启用 `立体声混音`（这是本机唯一一个"被禁用"的端点，启用后即有内录耳），或插 USB 麦克风。

## 🔴 两条口径，不许念错
- **内录耳 ≠ 麦克风耳**：`立体声混音` 录的是**电脑正在放的声音**，听不到房间里的说话。
  要听主人说话，必须有物理麦克风（USB / 3.5mm 耳麦）。
- **管道通 ≠ 听得懂**：本件只证明"录得到字节、WAV 格式对"。
  转写准确率要由 `asr-listen.ps1 -WavFile` 出真文本才算验过。

用法：
  python tools/codex-scripts/wasapi-record.py --list
  python tools/codex-scripts/wasapi-record.py --seconds 3 --out state/ear.wav
  python tools/codex-scripts/wasapi-record.py --seconds 3 --asr        # 录完直接送去识别
退出码：0 成功 · 5 没有可用输入端点 · 6 写盘失败
"""
import argparse
import json
import os
import subprocess
import sys
import time
import wave

import numpy as np
import sounddevice as sd

# 🔴 第 75 轮补（**这个文件漏了**）：不重建 stdout 编码 ⇒ Windows 控制台默认 GBK，
#    中文/符号（`⇒`、`——`）一律乱码，遇到 GBK 编不出的字符还会**直接抛 `UnicodeEncodeError` 崩掉**
#    （实测：`emit(...)` 里一个 `⇒` 就把整条错误路径打成 traceback）。
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASR = os.path.join(HERE, "asr-listen.ps1")
SR = 16000          # 离线识别器口径：16k / 16bit / 单声道
STATES = {1: "在场", 2: "已禁用", 4: "不在场", 8: "已拔出"}


def emit(ok, status, reason, **kw):
    o = {"ok": ok, "status": status, "reason": reason}
    o.update(kw)
    print(json.dumps(o, ensure_ascii=False))
    return 0 if ok else 5


def list_inputs():
    apis = sd.query_hostapis()
    rows = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            rows.append({"index": i, "name": d["name"], "ch": d["max_input_channels"],
                         "sr": d["default_samplerate"], "api": apis[d["hostapi"]]["name"]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--out", default=os.path.join(ROOT, "state", "ear.wav"))
    ap.add_argument("--device", default="")      # 序号或名字片段
    ap.add_argument("--asr", action="store_true", help="录完直接送 asr-listen.ps1 -WavFile")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    ins = list_inputs()
    if a.list:
        print("主机 API 输入默认：%s" % json.dumps(
            [{"api": h["name"], "default_input": h["default_input_device"]}
             for h in sd.query_hostapis()], ensure_ascii=False))
        print("可用输入端点 %d 个：" % len(ins))
        for r in ins:
            print("  #%-3d ch=%-2d sr=%-7.0f %-18s %s" % (r["index"], r["ch"], r["sr"], r["api"], r["name"]))
        if not ins:
            print("  （一个都没有 ⇒ 录音侧没有在场的端点；这与插不插麦克风无关，是端点没被激活）")
        return 0

    if not ins:
        return emit(False, "no_input",
                    "PortAudio 看不到任何输入端点（本机现读 MME/DirectSound/WASAPI 均 0 个输入）",
                    hint="启用「立体声混音」（本机唯一被禁用的录音端点）或插 USB 麦克风")

    dev = None
    if a.device:
        for r in ins:
            if str(r["index"]) == a.device or a.device.lower() in r["name"].lower():
                dev = r["index"]
                break
        if dev is None:
            return emit(False, "no_input", "指定设备找不到：%s" % a.device,
                        available=[r["name"] for r in ins])
        cands = [r for r in ins if r["index"] == dev]        # 点名了：只试它这一个
    else:
        # 🔴 第 75 轮改：**不再盲取第一个**。候选顺序 = 真端点优先（WASAPI/MME/DirectSound），
        #    WDM-KS 垫底。理由：WDM-KS 是**内核流引脚**，它可能"流开得起来但 0 帧"
        #    （引脚没被音频引擎路由）—— 先试真端点，能出数据的概率高得多。
        def _rank(r):
            return {"Windows WASAPI": 0, "MME": 1, "Windows DirectSound": 2}.get(r["api"], 3)

        order = sorted(ins, key=_rank)
        for h in sd.query_hostapis():
            if h["name"] == "Windows WASAPI" and h["default_input_device"] >= 0:
                d0 = h["default_input_device"]
                order = [r for r in order if r["index"] != d0] + \
                        [r for r in order if r["index"] == d0]
                break
        cands = order

    def _try(idx, secs):
        """**回调式**录一段。为什么必须回调式：实测（`_wdmks_probe.py`）——
        PortAudio 的 WDM-KS 后端对阻塞式一律报 **`Blocking API not supported yet`**
        ⇒ `sd.rec`/`InputStream.start()` 在那些引脚上**从来开不了**，
        而我此前正是这么写的（旧读数 `Invalid device` 也是探针伪影：给 44100 的引脚传了 16000）。
        回调式下那两个 Realtek 引脚**流开得起来**（但仍可能 0 帧 ⇒ 如实报，不当成功）。"""
        d = sd.query_devices(idx)
        api = sd.query_hostapis(d["hostapi"])["name"]
        native = int(d["default_samplerate"] or SR)
        frames, stats = [], []

        def cb(indata, n, tinfo, status):
            stats.append(str(status))
            frames.append(indata.copy())

        try:
            st = sd.InputStream(device=idx, samplerate=native, channels=1, dtype="int16",
                                blocksize=0, callback=cb)
            st.start()
            time.sleep(secs)
            st.stop()
            st.close()
        except Exception as e:                                             # noqa: BLE001
            return {"ok": False, "why": "%s: %s" % (type(e).__name__, str(e)[:150]),
                    "device": d["name"], "api": api, "native_sr": native}
        if not frames:
            return {"ok": False, "why": "流开起来了但 **0 帧**（引脚没被路由/激活，数据不来）",
                    "device": d["name"], "api": api, "native_sr": native}
        x = np.concatenate(frames).astype(np.float64).ravel()
        # 重采样到离线识别器的口径（16k）；线性插值够用，只为让识别器吃得下
        if native != SR and x.size > 1:
            n_out = max(1, int(round(x.size * SR / native)))
            x = np.interp(np.linspace(0.0, x.size - 1.0, n_out),
                          np.arange(x.size, dtype=np.float64), x)
        return {"ok": True, "x": x, "device": d["name"], "api": api, "native_sr": native,
                "流状态": sorted(set(stats))[:3]}

    attempts, got = [], None
    t0 = time.time()
    for r in cands:
        res = _try(r["index"], a.seconds)
        attempts.append({"index": r["index"], "device": r["name"], "api": r["api"],
                         "ok": bool(res.get("ok")), "why": res.get("why"),
                         "native_sr": res.get("native_sr")})
        if res.get("ok"):
            got = res
            break
    el = time.time() - t0
    if got is None:
        return emit(False, "no_input",
                    "所有候选端点都没拿到帧（%d 个都试过，逐条原因见 attempts）" % len(attempts),
                    attempts=attempts,
                    hint="回调式已用上；0 帧 = 引脚没被路由 ⇒ 启用『立体声混音』或插物理麦")

    x, name, api = got["x"], got["device"], got["api"]
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    rms = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    try:
        with wave.open(a.out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(np.clip(x, -32768, 32767).astype("<i2").tobytes())
    except Exception as e:                                               # noqa: BLE001
        return emit(False, "write_failed", "写 WAV 失败：%s" % e, out=a.out)

    out = {"ok": True, "status": "recorded", "seconds": round(el, 2), "frames": int(x.size),
           "peak": round(peak, 1), "rms": round(rms, 1), "wav": a.out,
           "bytes": os.path.getsize(a.out), "device": name, "api": api,
           "native_sr": got.get("native_sr"), "out_sr": SR, "attempts": attempts,
           "口径": "peak/rms 只说明管道通不通；声音小/为 0 是当下没有声音，不是坏"}
    if not a.asr:
        if a.json:
            print(json.dumps(out, ensure_ascii=False))
        else:
            print("录到 %s（%s）%.2fs · %d 帧 · peak=%.0f rms=%.1f · %d 字节"
                  % (name, api, el, x.size, peak, rms, out["bytes"]))
            print("落盘 %s" % a.out)
        return 0

    print(json.dumps(out, ensure_ascii=False))
    print("→ 交给离线识别器 …")
    p = subprocess.run(["pwsh", "-NoProfile", "-File", ASR, "-WavFile", a.out],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    line = (p.stdout or "").strip().splitlines()
    print(line[-1] if line else "(识别器没有输出)")
    print("[asr exit code: %d]" % p.returncode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
