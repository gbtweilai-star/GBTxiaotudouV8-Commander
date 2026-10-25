# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""清晰度量规 v2（修正版）：
  · 轮廓锯齿度：每列只取**上边界行**，沿 x 求二阶差分均值（超采样应使其下降）
  · 强边缘均值：|grad| 前 5% 的均值
  · 脸部 ROI 高光：>240 亮度像素占比 + 最大亮度（眼神光应使其上升）
  · 梯度方差（信息项，不是主判据）
用法: python tools/codex-scripts/measure-clarity.py <图...>  （纯 PIL/numpy，无浏览器）"""
import pathlib
import sys
import numpy as np
from PIL import Image

WS = pathlib.Path(_GBT_ROOT)


def analyze(p):
    im = Image.open(p).convert("RGB")
    a = np.asarray(im, np.float32)
    corners = np.concatenate([a[:8, :8].reshape(-1, 3), a[:8, -8:].reshape(-1, 3),
                              a[-8:, :8].reshape(-1, 3), a[-8:, -8:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    mask = np.linalg.norm(a - bg, axis=2) > 28
    ys, xs = np.where(mask)
    if len(ys) < 50:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    # 上边界（每列第一个前景像素行号），只取连续列
    tops = []
    for x in range(x0, x1 + 1):
        col = np.where(mask[:, x])[0]
        tops.append(col.min() if len(col) else np.nan)
    tops = np.array(tops, np.float32)
    ok = ~np.isnan(tops)
    tops = tops[ok]
    jag = float(np.abs(np.diff(tops, n=2)).mean()) if len(tops) > 3 else 0.0
    g = np.asarray(im.convert("L"), np.float32)
    gx, gy = np.gradient(g)
    mag = np.hypot(gx, gy)
    strong = float(mag[mag >= np.percentile(mag, 95)].mean())
    head_h = max(40, int((y1 - y0) * 0.22))
    cx = (x0 + x1) // 2
    half = max(30, int((x1 - x0) * 0.28))
    roi = g[max(0, y0):y0 + head_h, max(0, cx - half):min(g.shape[1], cx + half)]
    hi = float((roi > 240).mean() * 100) if roi.size else 0.0
    return dict(size=im.size, roi=(roi.shape[1], roi.shape[0]), jag=jag, strong=strong,
                hi=hi, maxlum=float(roi.max()) if roi.size else 0.0, gvar=float(np.var(gx) + np.var(gy)))


for arg in sys.argv[1:]:
    p = pathlib.Path(arg)
    if not p.is_absolute():
        p = WS / p
    m = analyze(p)
    if not m:
        print(f"{p.name}: 找不到前景，跳过")
        continue
    print(f"{p.stem}: {m['size'][0]}×{m['size'][1]} · 轮廓锯齿度 {m['jag']:.3f}（越低越好） · 强边缘均值 {m['strong']:.1f} "
          f"· 脸部高光占比 {m['hi']:.3f}% · 脸部最大亮度 {m['maxlum']:.0f} · 梯度方差 {m['gvar']:.1f}")
