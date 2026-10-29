# -*- coding: utf-8 -*-
"""beauty-pass.py —— **美颜后处理链**（把"美图"的方法搬过来，不搬它的资产）。

主人 2026-10-19：「抓取专业的美图项目来实现」。直说一句：美图秀秀的**成品资产是闭源商业资产，
抓来用是侵权**，这条我不做。但**它好看的原因不是资产，是那条后处理链** —— 磨皮（保边）、
去油光（高光压缩）、锐化（局部对比）、眼部/唇部提亮、肤色统一、调色。这些方法可以自己实现，
而且用我们自己的图就能验。

所以本件做的是「**复刻方法**」：
    1) 肤色遮罩（YCbCr 区间 + 形态学清理）——只在皮肤上动，不动衣服/背景
    2) 保边磨皮（双边滤波，皮肤遮罩内）——不是无脑高斯，边缘和五官不乱糊
    3) 去油光（皮肤高光压缩：L 通道高亮段软压缩）
    4) 局部对比（unsharp mask，全图轻量）——"清晰"靠这个，不靠加像素
    5) 五官提亮（眼周/唇部在遮罩内轻微提亮+饱和）
    6) 调色（轻微 S 曲线 + 暖白平衡）——不要"网红滤镜"，只修平

用法：
    py -3.14 tools/codex-scripts/beauty-pass.py <in.png> [-o out.png] [--strength 1.0]
    py -3.14 tools/codex-scripts/beauty-pass.py <in.png> --compare   # 出左右对比图

口径（判据）：
  · **只改指定像素区间**，原图不动；输出写新文件
  · 强度可调；`--compare` 会把原图/成品并排，方便肉眼判"自然不自然"
  · 没有任何网络/外部服务调用：纯本地 OpenCV
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def _protect_mask(bgr: np.ndarray, skin: np.ndarray) -> np.ndarray:
    """**五官保护**（第一版翻车的真因）：皮肤区间把眼睛/眉毛/唇也圈进来了 ⇒ 一起被磨平，
    脸变成"没有五官的面具"。这里把皮肤区里的**暗部（眉眼）与高饱和红（唇）**挖出来，
    膨胀一圈后从皮肤遮罩里扣掉 —— 五官只做轻提亮，不做磨皮。
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    dark = ((v < 92) & (skin > 32)).astype(np.uint8) * 255
    lips = ((h < 12) | (h > 168)) & (s > 110) & (v > 60)
    lips = lips.astype(np.uint8) * 255
    prot = cv2.bitwise_or(dark, lips)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
    prot = cv2.dilate(prot, k, iterations=1)
    prot = cv2.GaussianBlur(prot, (0, 0), 2)
    return prot


def _skin_mask(bgr: np.ndarray) -> np.ndarray:
    """肤色遮罩：YCbCr **收窄**区间 + 闭运算去洞 + 扣掉五官 + 羽化。"""
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycrcb)
    # 收窄（第一版 133~180 / 77~130 太宽，把眉毛眼睛都算成皮肤了）
    m = ((cr > 137) & (cr < 173) & (cb > 85) & (cb < 125) & (y > 70)).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k, iterations=1)
    m = cv2.bitwise_and(m, cv2.bitwise_not(_protect_mask(bgr, m)))
    m = cv2.GaussianBlur(m, (0, 0), 3)          # 羽化，避免硬边
    return m


def _soft_highlight(bgr: np.ndarray, mask: np.ndarray, strength: float) -> np.ndarray:
    """去油光：皮肤区高光段软压缩（不是整体压暗，只压 200~255 那段）。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    v = hsv[..., 2] / 255.0
    knee, ceil = 0.72, 1.0
    over = np.clip((v - knee) / (ceil - knee), 0.0, 1.0)
    v2 = v - over * 0.28 * strength
    hsv[..., 2] = np.clip(v2, 0, 1) * 255
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    a = (mask.astype(np.float32) / 255.0)[..., None]
    return (bgr.astype(np.float32) * (1 - a) + out.astype(np.float32) * a).astype(np.uint8)


def _bilateral_smooth(bgr: np.ndarray, mask: np.ndarray, strength: float) -> np.ndarray:
    """保边磨皮：双边滤波只在皮肤上生效（五官/发丝边缘因为色差大，d 小 σ_color 小 ⇒ 不被抹平）。"""
    smoothed = cv2.bilateralFilter(bgr, d=9, sigmaColor=28, sigmaSpace=9)
    a = (mask.astype(np.float32) / 255.0 * min(1.0, 0.85 * strength))[..., None]
    return (bgr.astype(np.float32) * (1 - a) + smoothed.astype(np.float32) * a).astype(np.uint8)


def _unsharp(bgr: np.ndarray, amount: float) -> np.ndarray:
    """局部对比（"清晰"的正解）：只加中高频，不动整体亮度。"""
    blur = cv2.GaussianBlur(bgr, (0, 0), 1.2)
    return cv2.addWeighted(bgr, 1 + amount, blur, -amount, 0)


def _tone(bgr: np.ndarray, strength: float) -> np.ndarray:
    """调色：轻微 S 曲线 + 一点点暖，不搞"网红滤镜"。"""
    f = bgr.astype(np.float32) / 255.0
    s = f + (f - 0.5) * 0.10 * strength          # 对比
    s = np.clip(s, 0, 1) ** (1.0 / (1.0 + 0.035 * strength))   # 略提亮中间调
    s[..., 0] *= 1.0 + 0.012 * strength          # 蓝通道微降 ⇒ 偏暖
    s[..., 2] *= 1.0 + 0.006 * strength          # 红通道微升
    return np.clip(s * 255.0, 0, 255).astype(np.uint8)


def apply(path: Path, strength: float = 1.0) -> tuple:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit("读不到图：%s" % path)
    mask = _skin_mask(bgr)
 # 第二版实测翻车：皮肤区**局部压高光** + 遮罩有斑块 ⇒ 脸上出现白斑（像皮肤病）。
    #    结论：3D 渲染出来的皮肤本来就均匀，**不需要"压高光/提亮"这类美图动作**；
    #    只保留两件事：**羽化到几乎无边的保边磨皮** + **轻锐化** + **极轻对比**。
    out = _bilateral_smooth(bgr, mask, strength)
    out = _unsharp(out, 0.20 * strength)
    out = _tone(out, 0.5 * strength)
    skin_ratio = float((mask > 32).mean()) * 100
    return out, bgr, mask, skin_ratio


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="美颜后处理链（保边磨皮/去油光/锐化/调色，纯本地）")
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--compare", action="store_true", help="额外输出左右对比图")
    a = ap.parse_args(argv)

    src = Path(a.src)
    out_p = Path(a.out) if a.out else src.with_name(src.stem + "_beauty.png")
    dst, orig, mask, ratio = apply(src, a.strength)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_p), dst)
    print("美颜成品 => %s（%.1f MB）· 皮肤占画面 %.1f%% · 强度 %.2f"
          % (out_p, out_p.stat().st_size / 1e6, ratio, a.strength))
    if a.compare:
        cmp_p = out_p.with_name(out_p.stem + "_compare.png")
        sep = np.full((orig.shape[0], 8, 3), 255, np.uint8)
        cv2.imwrite(str(cmp_p), np.hstack([orig, sep, dst]))
        print("左右对比 => %s（左=原图 右=美颜）" % cmp_p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
