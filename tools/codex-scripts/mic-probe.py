# -*- coding: utf-8 -*-
"""耳（麦克风）探针：**严判**有没有真声音，不许把"帧数"当"有声"。

## 为什么有这件（一次假通过的教训）
2026-10-23 首版试探用 `peak > 0.001` 判"有声音"，
而某次 WDM-KS 引脚返回 float32 却读到 **5.5e11**（float32 不可能 >1）⇒ 垃圾数据被当成成功。
本条把它写成硬判据：float32 的 |值| 必须在 (0, 1]，且 RMS > 1e-4 才算 REAL；
其余一律按静默/垃圾如实报（GARBAGE / SILENCE），并带上 peak / rms 原值。

用法：
  py -3 tools/codex-scripts/mic-probe.py --list           # 列 PortAudio 能看见的采集设备
  py -3 tools/codex-scripts/mic-probe.py --device 9 --seconds 2   # 对某个设备严格试录
  py -3 tools/codex-scripts/mic-probe.py --sweep          # 把所有 input 设备逐个试一遍
"""
from __future__ import annotations

import argparse
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import numpy as np
    import sounddevice as sd
except ImportError as exc:                                        # noqa: BLE001
    print(json.dumps({"ok": False, "why": "缺依赖：%s（用装了 numpy/sounddevice 的解释器，如 C:\\Python312\\python.exe）" % exc},
                     ensure_ascii=False))
    raise SystemExit(2)

REAL_PEAK_MAX = 1.0
REAL_RMS_MIN = 1e-4


def devices() -> list:
    apis = sd.query_hostapis()
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) > 0:
            out.append({"index": i, "api": apis[d["hostapi"]]["name"], "name": d["name"][:60],
                        "channels": d["max_input_channels"], "sr": int(d["default_samplerate"])})
    return out


def judge(a: np.ndarray) -> dict:
    """一行判据：真采样 / 静默 / 垃圾。"""
    peak = float(np.max(np.abs(a))) if a.size else 0.0
 # 2026-10-23 自纠（本件第一次跑就抓到自己）：NaN 会让下面两个比较**全为 False**，
    #   于是「静默的 NaN 数据」被判成 REAL —— 正是本仓最恨的假绿。
    #   判据加死：非有限值（NaN/Inf）与超范围值，一律 GARBAGE。
    with np.errstate(over="ignore", invalid="ignore"):
        rms = float(np.sqrt(np.mean(np.square(a, dtype="float64")))) if a.size else 0.0
    if not np.isfinite(peak) or not np.isfinite(rms):
        return {"verdict": "GARBAGE", "peak": "NaN/Inf", "rms": "NaN/Inf", "frames": int(a.size)}
    if peak > REAL_PEAK_MAX:
        verdict = "GARBAGE"
    elif peak <= 0 or rms < REAL_RMS_MIN:
        verdict = "SILENCE"
    else:
        verdict = "REAL"
    return {"verdict": verdict, "peak": round(peak, 8), "rms": round(rms, 8), "frames": int(a.size)}


def probe(index: int, seconds: float) -> dict:
    info = next((d for d in devices() if d["index"] == index), None)
    if not info:
        return {"index": index, "ok": False, "why": "PortAudio 里没有这个输入设备"}
    tried = []
    for sr in (48000, 44100, info["sr"]):
        try:
            rec = sd.rec(int(sr * seconds), samplerate=sr, channels=1, device=index,
                         dtype="float32", blocking=True)
            v = judge(np.asarray(rec).ravel())
            tried.append({"sr": sr, **v})
            if v["verdict"] == "REAL":
                return {"index": index, "ok": True, "device": info, "picked_sr": sr, "tries": tried}
        except Exception as exc:                                  # noqa: BLE001
            tried.append({"sr": sr, "verdict": "ERROR", "why": str(exc)[:120]})
    return {"index": index, "ok": False, "device": info, "tries": tried,
            "why": "所有采样率下都没有真采样（静默或垃圾数据）"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--device", type=int, default=-1)
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--sweep", action="store_true")
    a = ap.parse_args()

    if a.list or (a.device < 0 and not a.sweep):
        print(json.dumps({"default_input": sd.default.device[0], "capture_devices": devices()},
                         ensure_ascii=False, indent=1))
        return 0
    if a.sweep:
        rows = [probe(d["index"], a.seconds) for d in devices()]
        print(json.dumps({"ok": any(r.get("ok") for r in rows), "rows": rows}, ensure_ascii=False, indent=1))
        return 0 if any(r.get("ok") for r in rows) else 1
    r = probe(a.device, a.seconds)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
