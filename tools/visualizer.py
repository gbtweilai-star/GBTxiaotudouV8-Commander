#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""visualizer —— 静态实物展台：拍一张 → 摆正 → 去阴影 → 提亮 → 出 1080p 展台画面。

为什么是静态：iOS 命令行拿不到实时相机流（Camera2 那套是 Android）。
所以这条做的是"拍一张、投一张"，用于讲实物、讲纸质文件、讲一页书。

四步（都可验证）：
  ① 摆正：用 Vision 的矩形检测取四角，透视拉正（检测不到就保留原图）
  ② 去阴影：用大半径模糊估计光照场，逐像素相除（本地平场校正）
  ③ 提亮与压白：灰世界白平衡 + 白点拉伸到 250（纸变白，不是变灰）
  ④ 上展台：白底 1920×1080，四周留 6% 边距，下方留题注位

用法： python3 tools/visualizer.py 图.jpg [--out x.png] [--title "标题"]
"""
import argparse, json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageOps

W, H = 1920, 1080
MARGIN = 0.06


def detect_quad(path):
    try:
        d = json.loads(subprocess.run(["apple-vision", "detect", path],
                                      capture_output=True, text=True).stdout).get("data", {})
        rects = d.get("rectangles") or []
        if not rects:
            return None
        r = max(rects, key=lambda x: x.get("confidence", 0))
        iw, ih = d["image"]["width"], d["image"]["height"]
        def px(p):   # Vision 归一化坐标 → 像素（y 轴向上）
            return (p[0] * iw, (1 - p[1]) * ih)
        tl, tr = px(r["top_left"]), px(r["top_right"])
        br, bl = px(r["bottom_right"]), px(r["bottom_left"])
        w = max(((tr[0] - tl[0]) ** 2 + (tr[1] - tl[1]) ** 2) ** .5,
                ((br[0] - bl[0]) ** 2 + (br[1] - bl[1]) ** 2) ** .5)
        h = max(((bl[0] - tl[0]) ** 2 + (bl[1] - tl[1]) ** 2) ** .5,
                ((br[0] - tr[0]) ** 2 + (br[1] - tr[1]) ** 2) ** .5)
        if w < 40 or h < 40:
            return None
        return (tl, tr, br, bl), (int(w), int(h))
    except Exception:                                             # noqa: BLE001
        return None


def warp(im, quad, size):
    tl, tr, br, bl = quad
    # PIL 的 PERSPECTIVE 需要「目标→源」的 8 系数，用 cv2 风格的解算代替：
    # 这里用近似四边形映射（QUAD）——对轻微角度足够，不需要 numpy 解线性方程。
    return im.transform(size, Image.QUAD, (tl[0], tl[1], bl[0], bl[1], br[0], br[1], tr[0], tr[1]),
                        resample=Image.BICUBIC)


def deflash(im):
    """平场校正：用大半径模糊估光场，逐像素相除 ⇒ 去掉阴影与渐变照明。"""
    a = np.asarray(im, dtype=np.float32) + 1.0
    lum = a.mean(axis=2, keepdims=True)
    field = np.asarray(Image.fromarray(lum[..., 0].astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(max(im.size) / 12)).convert("L"), dtype=np.float32)[..., None] + 1.0
    a = a / field * float(np.median(field))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def white_balance(im):
    a = np.asarray(im, dtype=np.float32)
    means = a.reshape(-1, 3).mean(axis=0)
    g = means.mean()
    a = a * (g / np.maximum(means, 1e-3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def stretch_white(im, target=250):
    g = im.convert("L")
    hi = np.percentile(np.asarray(g), 99)
    if hi <= 1:
        return im
    k = target / float(hi)
    return Image.fromarray(np.clip(np.asarray(im, dtype=np.float32) * k, 0, 255).astype(np.uint8), "RGB")


def compose(im, title="", out="/var/minis/attachments/visualizer.png"):
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    inner_w, inner_h = int(W * (1 - 2 * MARGIN)), int(H * (1 - 2 * MARGIN) - 90)
    im = ImageOps.contain(im, (inner_w, inner_h), Image.LANCZOS)
    x = (W - im.size[0]) // 2
    y = (H - 90 - im.size[1]) // 2 + 20
    canvas.paste(im, (x, y))
    if title:
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, H - 78, W, H], fill=(250, 249, 246))
        d.text((MARGIN * W, H - 56), title[:60], fill=(30, 30, 34))
    canvas.save(out, "PNG")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--out", default="/var/minis/attachments/visualizer.png")
    ap.add_argument("--title", default=""); ap.add_argument("--no-detect", action="store_true")
    a = ap.parse_args()
    im = Image.open(a.src).convert("RGB")
    w0, h0 = im.size
    quad = None if a.no_detect else detect_quad(a.src)
    if quad:
        im = warp(im, quad[0], quad[1])
        print("① 摆正  检测到矩形 → 拉正为 %dx%d" % im.size)
    else:
        print("① 摆正  未检测到矩形 → 保留原图")
    im = deflash(im); print("② 去阴影  平场校正完成")
    im = white_balance(im); im = stretch_white(im); print("③ 提亮  灰世界白平衡 + 白点拉到 250")
    p = compose(im, a.title, a.out)
    print("④ 展台  %s · 1920×1080 · %.0f KB" % (p, os.path.getsize(p) / 1024))
    print("   投屏：gbt cinema %s  或浏览器全屏" % p)


if __name__ == "__main__":
    sys.exit(main())
