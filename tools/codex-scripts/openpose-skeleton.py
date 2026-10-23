#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""标准 OpenPose 骨架生成器（COCO-18 关键点 + 官方配色）· 零新依赖

## 这件是「OpenPose+Lora 组合技」的前半截
ControlNet-OpenPose 吃的**不是照片**，是一张**骨架图**：黑底 + 18 个彩点 + 17 根彩棒。
专业流程是「照片 → 检测器抽出骨架 → 喂 ControlNet」；本件先解决**格式与姿态**这一半，
检测器那一半另起一件（见文末「未验」）。

## 为什么必须自己会画（本机实测理由）
- ComfyUI 的 venv 现读**没有 cv2、没有 onnxruntime** ⇒ 检测器不能跑在它里面
- 而工作区 python **有 cv2 4.11.0 + onnxruntime 1.26.0** ⇒ 预处理器放仓里独立跑
- 更关键：本机内存**总 7.4 GB / 可用 0.33 GB** ⇒ 任何东西**都不能**再进 ComfyUI 进程
- 而且"知道骨架长什么样"本身就是这套手艺的基本功：颜色错了、点序错了，ControlNet 就不认

## 关键点顺序与配色（照 OpenPose 官方，不是我编的）
COCO-18：0鼻 1颈 2右肩 3右肘 4右腕 5左肩 6左肘 7左腕
         8右髋 9右膝 10右踝 11左髋 12左膝 13左踝 14右眼 15左眼 16右耳 17左耳
17 根骨（官方 LIMB 顺序）：(1,2)(1,5)(2,3)(3,4)(5,6)(6,7)(1,8)(8,9)(9,10)
                          (1,11)(11,12)(12,13)(1,0)(0,14)(14,16)(0,15)(15,17)
配色（官方 18 色，按关键点序号取；本脚本按 RGB 存，cv2 写图时转 BGR）

用法：
  python tools/codex-scripts/openpose-skeleton.py --list
  python tools/codex-scripts/openpose-skeleton.py --pose stand --out "<ComfyUI>/input/gbt-pose.png"
  python tools/codex-scripts/openpose-skeleton.py --pose walk --size 512 --out pose.png
  python tools/codex-scripts/openpose-skeleton.py --keypoints-json my.json --out pose.png

退出码：0 出了骨架图 · 2 姿势名不认 · 3 写盘失败
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 官方 18 关键点定义（COCO-18）──────────────────────────────────────────
KPT_NAMES = ["nose", "neck", "Rshoulder", "Relbow", "Rwrist", "Lshoulder", "Lelbow", "Lwrist",
             "Rhip", "Rknee", "Rankle", "Lhip", "Lknee", "Lankle",
             "Reye", "Leye", "Rear", "Lear"]
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10),
         (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
# 官方 colors 列表（RGB）
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0),
          (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
          (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]

# ── 姿态预设：归一化坐标（x 向右，y 向下，0..1；画面 512 时 x*512, y*512）──
# 数字人常用三种：正面站姿（半身感）、T 姿（给绑定/换装最稳）、行走（动态）。
POSES = {
    "stand": {                       # 正面站姿，右手叉腰，重心略偏
        "nose": (0.500, 0.155), "neck": (0.500, 0.215),
        "Rshoulder": (0.575, 0.245), "Relbow": (0.640, 0.360), "Rwrist": (0.585, 0.455),
        "Lshoulder": (0.425, 0.245), "Lelbow": (0.355, 0.365), "Lwrist": (0.330, 0.510),
        "Rhip": (0.545, 0.535), "Rknee": (0.560, 0.720), "Rankle": (0.555, 0.905),
        "Lhip": (0.455, 0.535), "Lknee": (0.435, 0.720), "Lankle": (0.430, 0.905),
        "Reye": (0.482, 0.140), "Leye": (0.518, 0.140),
        "Rear": (0.462, 0.150), "Lear": (0.538, 0.150),
    },
    "tpose": {                       # T 姿：双臂平伸，做绑定/换装/建模参照最稳
        "nose": (0.500, 0.160), "neck": (0.500, 0.220),
        "Rshoulder": (0.570, 0.250), "Relbow": (0.700, 0.250), "Rwrist": (0.830, 0.250),
        "Lshoulder": (0.430, 0.250), "Lelbow": (0.300, 0.250), "Lwrist": (0.170, 0.250),
        "Rhip": (0.548, 0.540), "Rknee": (0.552, 0.730), "Rankle": (0.552, 0.915),
        "Lhip": (0.452, 0.540), "Lknee": (0.448, 0.730), "Lankle": (0.448, 0.915),
        "Reye": (0.482, 0.145), "Leye": (0.518, 0.145),
        "Rear": (0.462, 0.155), "Lear": (0.538, 0.155),
    },
    "walk": {                        # 行走：一腿前伸，手臂反向摆
        "nose": (0.505, 0.150), "neck": (0.500, 0.215),
        "Rshoulder": (0.572, 0.245), "Relbow": (0.640, 0.350), "Rwrist": (0.700, 0.450),
        "Lshoulder": (0.428, 0.245), "Lelbow": (0.360, 0.350), "Lwrist": (0.300, 0.440),
        "Rhip": (0.545, 0.530), "Rknee": (0.600, 0.700), "Rankle": (0.660, 0.870),
        "Lhip": (0.455, 0.530), "Lknee": (0.400, 0.710), "Lankle": (0.345, 0.900),
        "Reye": (0.487, 0.135), "Leye": (0.523, 0.135),
        "Rear": (0.467, 0.145), "Lear": (0.543, 0.145),
    },
    "sit": {                         # 坐姿：髋低、膝前伸（做直播坐播形象用）
        "nose": (0.500, 0.140), "neck": (0.500, 0.205),
        "Rshoulder": (0.572, 0.235), "Relbow": (0.628, 0.345), "Rwrist": (0.668, 0.455),
        "Lshoulder": (0.428, 0.235), "Lelbow": (0.372, 0.345), "Lwrist": (0.332, 0.455),
        "Rhip": (0.550, 0.520), "Rknee": (0.640, 0.640), "Rankle": (0.660, 0.830),
        "Lhip": (0.450, 0.520), "Lknee": (0.360, 0.640), "Lankle": (0.340, 0.830),
        "Reye": (0.482, 0.125), "Leye": (0.518, 0.125),
        "Rear": (0.462, 0.135), "Lear": (0.538, 0.135),
    },
}


def rgb2bgr(c):
    """🔴 第 70 轮修的一个**真缺陷**：本件原来把 `COLORS` 里的 **RGB 元组直接喂给 cv2**
    （cv2 要的是 **BGR**）⇒ 画出来的骨架**红蓝通道整体反了**。

    后果：几何是对的（所以 ControlNet 照样咬住了姿势，出图正常），**但配色不是官方那套**
    ⇒ ① 它不是"专业标准输入"；② 与标准工具（如 controlnet-aux 的检测器）**互相解码不了**。
    实测抓法：把检测器跑在出图上、再与本件画的骨架逐色比对，发现"鼻子"（红）的质心落在
    `y=0.640` —— 而那里其实是**左髋→左膝的中点**（`COLORS[12]=(0,0,255)` 被画成了红）。
    ⇒ 现在**在画的时候转一次**：对外仍用官方 RGB 表（可读、可对），喂 cv2 时才转 BGR。
    """
    return (int(c[2]), int(c[1]), int(c[0]))


# 只有这些**身体**关节在本表里是按"屏幕左右"写的；**头部的眼/耳本来就是标准的**（受试者左右）
_LR_BODY = ("Shoulder", "Elbow", "Wrist", "Hip", "Knee", "Ankle")


def to_standard_lr(kpts):
    """把**身体**关节的 (R,L) 名互换一次，头部保持不动。

    🔴 第 70 轮修的第二个真缺陷（**而且我第一版还修歪了一次**）：

    **真相是"本表本身不一致"**——
    · **头部的眼/耳本来就是标准的**（受试者左右；正面人像下受试者右 = 观众左）
      ⇒ 原表 `Rear=(0.462) / Reye=(0.482)` **已经正确**；
    · **身体（肩/肘/腕/髋/膝/踝）是按屏幕左右写的** ⇒ `Rshoulder=(0.575)` 在观众右，**反了**。

    **证据（官方检测器给的，不是推的）**：把 `controlnet-aux` 跑在同一张正面图上 ——
    `Rshoulder x=0.418 / Reye x=0.482 / Rear x=0.459` ⇒ 官方这三者**都在观众左**。

    ⚠️ 我第一版用"**一律互换**"，把本来正确的眼/耳也换坏了 —— 关节级读数当场抓到：
    `Rear 40.5px / Lear 38.5px`（而 nose 只有 1.1px）。
    ⇒ 现在**只换 `_LR_BODY` 那六类**；几何一个像素都不动，只有配色正名。
    """
    out = {}
    for k, v in kpts.items():
        # ⚠️ **必须大小写不敏感**：键是 `Rshoulder`（小写 s），而 `_LR_BODY` 里写的是
        # `"Shoulder"`（大写 S）。我第一版直接 `startswith` ⇒ **恒为假 ⇒ 身体一个都没换**
        # ⇒ 关节级读数当场显示"头修好了、身体从 3.9px 掉到 80.4px"。**判据抓到的，不是我想到的。**
        suf = k[1:].lower()
        body = k[:1] in ("R", "L") and any(suf.startswith(s.lower()) for s in _LR_BODY)
        out[(("L" if k[0] == "R" else "R") + k[1:]) if body else k] = v
    return out


def draw(kpts, size):
    """kpts: {名字: (x, y)} 归一化 → 返回 BGR 图（黑底彩骨）"""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    P = np.zeros((18, 2), dtype=np.int32)
    for i, nm in enumerate(KPT_NAMES):
        if nm in kpts:
            x, y = kpts[nm]
            P[i] = [int(round(x * size)), int(round(y * size))]
    stick = max(2, int(round(size / 128.0)))          # 512 → 4，与官方 stickwidth=4 一致
    dot = max(2, int(round(size / 128.0)))
    for a, b in LIMBS:
        if np.all(P[a] == 0) or np.all(P[b] == 0):
            continue                                  # 缺的点不画（官方同样跳过）
        col = rgb2bgr(COLORS[b])                      # 官方按**子**关节取色；RGB→BGR
        cv2.line(img, tuple(P[a]), tuple(P[b]), col, stick, lineType=cv2.LINE_AA)
    for i in range(18):
        if np.all(P[i] == 0):
            continue
        col = rgb2bgr(COLORS[i])
        cv2.circle(img, tuple(P[i]), dot, col, -1, lineType=cv2.LINE_AA)
    return img


def default_out():
    return os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")),
                        "ComfyUI", "input", "gbt-pose.png")


def main() -> int:
    ap = argparse.ArgumentParser(description="标准 OpenPose 骨架生成器（COCO-18）")
    ap.add_argument("--pose", default="stand", help="预设姿势：%s" % "/".join(POSES))
    ap.add_argument("--keypoints-json", default="", help='自定义：{"nose":[0.5,0.15], ...}')
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--out", default=default_out())
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        print("可用预设姿势：")
        for k, v in POSES.items():
            print("  %-8s 18 点齐=%s" % (k, all(n in v for n in KPT_NAMES)))
        print("默认落点：%s" % default_out())
        return 0

    if a.keypoints_json:
        try:
            raw = json.load(open(a.keypoints_json, encoding="utf-8"))
        except Exception as e:                                            # noqa: BLE001
            print(json.dumps({"ok": False, "status": "bad_json", "error": str(e)[:160]},
                             ensure_ascii=False))
            return 2
        kpts = {k: tuple(v) for k, v in raw.items() if k in KPT_NAMES}
        missing = [n for n in KPT_NAMES if n not in kpts]
    else:
        if a.pose not in POSES:
            print(json.dumps({"ok": False, "status": "unknown_pose", "pose": a.pose,
                              "have": list(POSES)}, ensure_ascii=False))
            return 2
        kpts = to_standard_lr(POSES[a.pose])          # 屏幕左右 → 标准 R/L（几何不动，只正名）
        missing = [n for n in KPT_NAMES if n not in kpts]

    img = draw(kpts, int(a.size))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    try:
        ok = cv2.imwrite(a.out, img)
    except Exception as e:                                                # noqa: BLE001
        print(json.dumps({"ok": False, "status": "write_failed", "error": str(e)[:160]},
                         ensure_ascii=False))
        return 3
    if not ok:
        print(json.dumps({"ok": False, "status": "write_failed", "out": a.out},
                         ensure_ascii=False))
        return 3

    nz = int(np.count_nonzero(img.any(axis=2)))
    print(json.dumps({"ok": True, "status": "drawn", "pose": a.pose or "(json)",
                      "out": a.out, "size": a.size, "bytes": os.path.getsize(a.out),
                      "colored_px": nz, "missing_kpts": missing,
                      "_口径": "本件画的是**骨架格式**，不是从照片检测出来的（检测器另见图鉴未验项）"},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
