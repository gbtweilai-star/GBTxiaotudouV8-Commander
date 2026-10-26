#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""declutter —— 本地能修的第五轴：**边缘密度过高**（画面太碎、太吵）。

原理：边缘密度 = 梯度图上超阈值的像素占比。它高，多半是背景纹理太细碎。
做法：按梯度分成三档 —— 强边缘（主体轮廓）**保留**、中等纹理（杂物）**削弱**、
      弱起伏（噪点）**抹平**；只作用在 L 通道，不动颜色。

用法： python3 tools/declutter.py 图.jpg --out 修后.png [--lo 12 --hi 45 --amount 0.7]
"""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageFilter

TOOLS = os.path.dirname(os.path.abspath(__file__))


def load_gate():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tg", os.path.join(TOOLS, "taste_gate.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def grad_mag(g):
    a = np.asarray(g, dtype=np.float32)
    gx = np.abs(np.diff(a, axis=1, prepend=a[:, :1]))
    gy = np.abs(np.diff(a, axis=0, prepend=a[:1, :]))
    return np.sqrt(gx ** 2 + gy ** 2)


def declutter(im, lo=12, hi=45, amount=0.7, radius=1.6):
    lab = im.convert("LAB"); L, A, B = lab.split()
    mag = grad_mag(L)
    # 中档权重：越接近 lo 越要压，超过 hi 的强边缘完全不动
    w = np.clip((hi - mag) / max(hi - lo, 1e-6), 0, 1)
    w = np.clip(w, 0, 1) * amount
    soft = L.filter(ImageFilter.GaussianBlur(radius))
    a = np.asarray(L, dtype=np.float32); s = np.asarray(soft, dtype=np.float32)
    out = a * (1 - w) + s * w
    L2 = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "L")
    return Image.merge("LAB", (L2, A, B)).convert("RGB"), float(w.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--out")
    ap.add_argument("--lo", type=float, default=12); ap.add_argument("--hi", type=float, default=45)
    ap.add_argument("--amount", type=float, default=0.7); ap.add_argument("--maxw", type=int, default=900)
    a = ap.parse_args()
    tg = load_gate()
    dst = a.out or a.src.rsplit(".", 1)[0] + "_dc.png"

    im = Image.open(a.src).convert("RGB")
    if im.size[0] > a.maxw:
        im = im.resize((a.maxw, int(im.size[1] * a.maxw / im.size[0])), Image.LANCZOS)
    b = tg.judge(a.src, "photo")
    out, wm = declutter(im, a.lo, a.hi, a.amount)
    tmp = dst
    out.save(tmp, "PNG")
    aft = tg.judge(tmp, "photo")
    print("边缘密度 %s → %s   判定 %s → %s   处理权重均值 %.2f"
          % (b["readings"]["edge"], aft["readings"]["edge"], b["verdict"], aft["verdict"], wm))
    print("不过项 %s → %s" % (",".join(b["fails"]) or "-", ",".join(aft["fails"]) or "-"))
    if len(aft["fails"]) >= len(b["fails"]):
        import shutil; shutil.copy(a.src, dst)
        print("回退  没有变好（或变差）⇒ 输出原图")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
