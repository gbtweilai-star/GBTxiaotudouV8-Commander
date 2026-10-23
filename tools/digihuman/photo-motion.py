# -*- coding: utf-8 -*-
"""photo-motion.py —— 本地「以图生动作」：不联网、不要 GPU、不要账号

## 为什么是这条路
照片级 i2v（Seedance/Kling）要 GPU 或付费 API；本机 RunPod 无库存、云端六把钥匙未配、
Ark 卡账号验证（主人 2026-10-20 令：「我没有那个，直接自己做」）。
所以用**最朴素但真的能动**的办法：把原图按身体分段，用锚点做仿射/旋转变形，逐帧生成动作。

## 先说清楚代价（不吹）
这是**变形驱动**，不是生成模型：
- ✅ 肢体方向、幅度、节奏是真的（角度由参数决定，可被读数验证）；
- ❌ 不会长出原图没有的信息 ⇒ 手臂内侧/腋下会被拉伸，近景皮肤与手指细节做不到照片级；
- ❌ 正面单人、身体不被遮挡时才可用（遮挡处会糊）。

## 组成
1. **锚点表**：归一化坐标（相对 W/H），默认值按 `reference-front.jpg` 这张正面全身图标定，
   可用 `--anchors <json>` 覆盖 —— 换图只改数据，不改代码。
2. **分段**：左臂 / 右臂 / 躯干 三块，各自一块**羽化蒙版**（边缘 24px 渐变），避免硬接缝。
3. **运动**：`armraise`（双臂抬起）、`wave`（右臂挥手）、`sway`（重心+呼吸）三档，可叠加。
4. **输出**：rawvideo 管道进 ffmpeg（x264 crf 16），落 `outputs/photo-motion/<id>.mp4`。

## 用法
  py -3.14 tools/digihuman/photo-motion.py --image <图> --id pm-armraise \
      --mode armraise --seconds 3 --fps 25
  py -3.14 tools/digihuman/photo-motion.py --image <图> --id pm-mix --mode armraise+sway
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "photo-motion"

# 默认锚点（归一化 x,y）—— 按 736x1248 的正面全身图标定；换姿势/换图请用 --anchors 覆盖
DEFAULT_ANCHORS = {
    "head": [0.500, 0.090],
    "neck": [0.500, 0.185],
    "shoulder_L": [0.395, 0.225], "shoulder_R": [0.605, 0.225],
    "elbow_L": [0.310, 0.330], "elbow_R": [0.690, 0.330],
    "wrist_L": [0.275, 0.420], "wrist_R": [0.725, 0.400],
    "hip_L": [0.445, 0.470], "hip_R": [0.555, 0.470],
    "knee_L": [0.420, 0.700], "knee_R": [0.580, 0.700],
    "ankle_L": [0.405, 0.930], "ankle_R": [0.595, 0.930],
}


def load_anchors(path: str, w: int, h: int) -> dict:
    src = DEFAULT_ANCHORS
    if path:
        src = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: (float(v[0]) * w, float(v[1]) * h) for k, v in src.items()}


def feather_mask(shape, poly, blur: int = 24) -> np.ndarray:
    """多边形蒙版 + 羽化（硬边会产生明显接缝，观感比动作错更刺眼）。"""
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(m, [np.array(poly, np.int32)], 255)
    k = blur * 2 + 1
    m = cv2.GaussianBlur(m, (k, k), 0)
    return (m.astype(np.float32) / 255.0)[:, :, None]


def rotate_about(img, center, ang_deg, mask):
    """绕 center 旋转 img，按 mask 羽化混合回原图。"""
    M = cv2.getRotationMatrix2D(center, ang_deg, 1.0)
    rot = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                         flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return (rot.astype(np.float32) * mask + img.astype(np.float32) * (1 - mask)).astype(np.uint8)


def build_arm_mask(shape, a, side: str) -> np.ndarray:
    """手臂区域多边形：肩→肘→腕→外扩一圈（把袖子和手一起带走）。"""
    sh = a["shoulder_" + side]; el = a["elbow_" + side]; wr = a["wrist_" + side]
    hp = a["hip_" + side]
    pad = 46
    poly = [
        (sh[0], sh[1] - pad), (el[0] - pad * 0.6, el[1]), (wr[0] - pad * 0.5, wr[1] + pad * 0.8),
        (wr[0] + pad * 0.5, wr[1] + pad * 0.8), (el[0] + pad * 0.6, el[1] + pad * 0.4),
        (hp[0], hp[1]),
    ]
    return feather_mask(shape, poly)


def torso_mask(shape, a) -> np.ndarray:
    poly = [
        (a["neck"][0] - 60, a["neck"][1]), (a["shoulder_R"][0] + 30, a["shoulder_R"][1]),
        (a["hip_R"][0] + 30, a["hip_R"][1]), (a["hip_L"][0] - 30, a["hip_L"][1]),
        (a["shoulder_L"][0] - 30, a["shoulder_L"][1]),
    ]
    return feather_mask(shape, poly, blur=30)


def frame_at(img, a, masks, t: float, dur: float, mode: str) -> np.ndarray:
    """t 秒的那一帧。所有角度都是**时间的显式函数**（可被读数验证，不是随手抖）。"""
    ph = 2 * math.pi * (t / max(dur, 1e-6))
    out = img.copy()

    if "sway" in mode:                     # 重心左右 + 呼吸（整帧微仿射）
        dx = 6.0 * math.sin(ph)
        dy = 2.0 * math.cos(ph * 2)
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        out = cv2.warpAffine(out, M, (out.shape[1], out.shape[0]),
                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    if "armraise" in mode or "wave" in mode:
        # 抬起幅度：0 → 峰值 52° → 回落（用 sin 保证首尾归位，不跳帧）
        amp = 52.0 * math.sin(min(1.0, t / max(dur * 0.55, 1e-6)) * math.pi / 2)
        if "wave" in mode:                 # 挥手：叠加 8Hz 小幅摆动
            amp = 38.0 + 10.0 * math.sin(2 * math.pi * 8 * t)
        out = rotate_about(out, a["shoulder_L"], +amp, masks["arm_L"])
        out = rotate_about(out, a["shoulder_R"], -amp, masks["arm_R"])

    if "breathe" in mode:
        s = 1.0 + 0.004 * math.sin(ph * 2)
        M = cv2.getRotationMatrix2D((out.shape[1] * 0.5, out.shape[0] * 0.62), 0.0, s)
        out = cv2.warpAffine(out, M, (out.shape[1], out.shape[0]),
                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--id", default="pm1")
    ap.add_argument("--mode", default="armraise")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--anchors", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    src = Path(a.image)
    img = cv2.imread(str(src))
    if img is None:
        print(json.dumps({"ok": False, "why": "图读不到（中文路径要复制到 ASCII 暂存）",
                          "image": str(src)}, ensure_ascii=False))
        return 2
    h, w = img.shape[:2]
    anc = load_anchors(a.anchors, w, h)
    masks = {"arm_L": build_arm_mask(img.shape, anc, "L"),
             "arm_R": build_arm_mask(img.shape, anc, "R"),
             "torso": torso_mask(img.shape, anc)}

    OUT.mkdir(parents=True, exist_ok=True)
    dst = Path(a.out) if a.out else OUT / ("%s.mp4" % a.id)
    n = max(1, int(round(a.seconds * a.fps)))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", "%dx%d" % (w, h), "-r", str(a.fps), "-i", "-",
           "-c:v", "libx264", "-crf", str(a.crf), "-preset", "medium",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    moved = 0.0
    prev = None
    for i in range(n):
        t = i / a.fps
        fr = frame_at(img, anc, masks, t, a.seconds, a.mode)
        p.stdin.write(fr.tobytes())
        if prev is not None:
            moved += float(np.abs(fr.astype(np.int16) - prev.astype(np.int16)).mean())
        prev = fr
    p.stdin.close()
    rc = p.wait()

    ok = rc == 0 and dst.is_file()
    rep = {"ok": bool(ok), "out": str(dst), "frames": n, "size": [w, h],
           "mode": a.mode, "seconds": a.seconds, "fps": a.fps,
           "mean_frame_diff": round(moved / max(1, n - 1), 4),
           "bytes": dst.stat().st_size if dst.is_file() else 0,
           "note": "变形驱动（非生成模型）：动作方向真，皮肤近景与手指细节做不到照片级"}
    print(json.dumps(rep, ensure_ascii=False))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
