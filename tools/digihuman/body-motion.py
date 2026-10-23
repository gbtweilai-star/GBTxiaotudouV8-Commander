# -*- coding: utf-8 -*-
"""body-motion.py — 比 body-sway 更"像人"的身体运动：**逐行弯曲（重心转移 + 躯干跟随）**。

## 和 body-sway 的区别（诚实说清）
- `body-sway`：整帧仿射（呼吸缩放 + 平移 + 极小旋转）。像"被推了一下"，不像"人自己挪重心"。
- `body-motion`（本件）：**按行做位移场**（cv2.remap），下半身几乎不动、腰往上逐渐跟、肩到头摆得最多，
  再叠一点上身的反向倾斜 —— 这是真人站着说话时的 **S 形重心转移**，没有分块接缝（逐行连续）。

## 仍然不是骨骼动画
它不驱动"某一条胳膊绕某关节转"。要那种，必须换带姿态驱动的视频模型（本机无 GPU）。
交付话术里必须继续写明这一点。

## 三个旋钮
  --bend    左右重心摆动幅度（占幅宽比）默认 0.006     ← 主要看得见的那个
  --lean    上身反向倾斜（占幅宽比）  默认 0.003
  --breath  纵向呼吸（占幅高比）      默认 0.003
  --hz      重心频率 默认 0.12（5 秒一个来回）  --audio 用音频包络做重音（可选）

用法：
  py -3.14 tools/digihuman/body-motion.py --in raw.mp4 --out moved.mp4 [--audio tw.wav]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import wave

import numpy as np


def _probe(p: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,r_frame_rate:format=duration",
                        "-of", "json", p], capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def _env(path: str, n: int, fps: float) -> np.ndarray:
    with wave.open(path, "rb") as w:
        sr, ch, raw = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    seg = int(round(sr / fps))
    e = np.array([np.sqrt(np.mean(x[i:i + seg] ** 2) + 1e-12)
                  for i in range(0, min(len(x), seg * n), seg)])
    if e.size < n:
        e = np.pad(e, (0, n - e.size))
    e = e[:n]
    return (e - e.min()) / (e.max() - e.min() + 1e-9)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--audio", default="", help="可选：用音频包络给摆动加一点重音")
    ap.add_argument("--bend", type=float, default=0.006)
    ap.add_argument("--lean", type=float, default=0.003)
    ap.add_argument("--breath", type=float, default=0.003)
    ap.add_argument("--hz", type=float, default=0.12)
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    import cv2

    info = _probe(a.src)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    W, H = int(v.get("width") or 0), int(v.get("height") or 0)
    num, _, den = str(v.get("r_frame_rate") or "25/1").partition("/")
    fps = float(num) / float(den or 1)
    if not W or not H:
        print(json.dumps({"ok": False, "why": "读不到分辨率"}, ensure_ascii=False))
        return 2

    cap = cv2.VideoCapture(a.src)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    n = a.limit or total
    amps = _env(a.audio, n, fps) if a.audio else None

    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-",
         "-i", a.src, "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-crf", str(a.crf), "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", a.dst],
        stdin=subprocess.PIPE)

    # 逐行权重：脚底 0 → 腰 0.25 → 胸 0.6 → 肩 1.0 → 头顶 1.15（头跟着肩走，但不多摆）
    ys = np.arange(H, dtype=np.float32)
    r = (H - 1 - ys) / float(H - 1)          # 0=脚底, 1=头顶
    w_sway = (np.clip((r - 0.18) / 0.82, 0, 1) ** 1.35).reshape(-1, 1)   # 列向量：按行施加
    w_lean = (np.clip((r - 0.45) / 0.55, 0, 1) ** 1.2).reshape(-1, 1)

    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), ys)
    i = 0
    diffs = []
    prev = None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        t = i / fps
        s = math.sin(2 * math.pi * a.hz * t)
        acc = 0.0
        if amps is not None and i < len(amps):
            acc = 0.35 * float(amps[i]) * s          # 说话重音让摆幅略大
        dx = (a.bend * (s + acc)) * W * w_sway
        dx = dx + (a.lean * -s) * W * w_lean         # 上身反向：看着才像"重心转移"
        dy = (-a.breath * (1 + s) * 0.5) * H * w_sway  # 呼吸：上身微微上抬
        map_x = (gx + dx).astype(np.float32)
        map_y = (gy + dy).astype(np.float32)
        out = cv2.remap(f, map_x, map_y, interpolation=cv2.INTER_LANCZOS4,
                        borderMode=cv2.BORDER_REPLICATE)
        if prev is not None:
            diffs.append(float(np.abs(out.astype(np.int16) - prev.astype(np.int16)).mean()))
        prev = out
        enc.stdin.write(out.tobytes())
        i += 1
        if a.limit and i >= a.limit:
            break
    cap.release()
    enc.stdin.close()
    enc.wait()

    rep = {"ok": enc.returncode == 0, "src": a.src, "out": a.dst, "frames": i,
           "size": [W, H], "fps": fps, "bend": a.bend, "lean": a.lean, "breath": a.breath,
           "hz": a.hz, "audio_driven": bool(a.audio),
           "frame_diff_mean": round(float(np.mean(diffs)), 4) if diffs else None,
           "note": "逐行位移场（S 形重心转移）；**不是骨骼动画**，不做单肢绕关节旋转"}
    print(json.dumps(rep, ensure_ascii=False))
    return 0 if rep["ok"] else 4


if __name__ == "__main__":
    sys.exit(main())
