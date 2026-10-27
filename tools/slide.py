#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""slide —— 生成可打印的**透明幻灯片**（闪光灯/手电 + 透镜那套用）。

为什么走浏览器渲染：本机没有任何中文字体（fc-list 为空），Pillow 画中文是方块。
所以先用 HTML 排版中文 → 截图拿位图 → 再在 PIL 里做镜像与二值化。

输出规格（打印即用）：
  · 300 dpi · A6 105×148mm = 1240×1748 px（--size A5 则 1748×2480）
  · **水平镜像**（透镜成倒立左右反转的实像，要先反一次）
  · 纯黑白二值（灰阶在胶片上会变脏）
  · 四周裁切标记 + 内安全边

用法：
    python3 tools/slide.py "力劈华山" --sub "齐天大圣 · 第一幕"
    python3 tools/slide.py --image 图.png          # 图片走抖动二值
"""
import argparse, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

SIZES = {"A6": (1240, 1748), "A5": (1748, 2480)}
DPI = 300
WORK = "/var/minis/attachments/slide"
OUT = "/var/minis/attachments/slide_print.png"

HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<style>
 html,body{margin:0;height:100%;background:#fff;color:#000;
   font-family:-apple-system,"PingFang SC",system-ui,sans-serif}
 .s{width:100%;height:100%;display:flex;flex-direction:column;justify-content:center;
    padding:8%;box-sizing:border-box}
 h1{font-size:16vh;line-height:1.05;letter-spacing:-.02em;font-weight:800;margin:0}
 p{font-size:5.5vh;line-height:1.4;margin:4vh 0 0;font-weight:600}
 .foot{position:absolute;bottom:5%;left:8%;font-size:3.2vh;letter-spacing:.08em}
</style></head><body><div class="s"><h1>{title}</h1>{sub}<div class="foot">{foot}</div></div></body></html>"""


def render_html(title, sub, foot, w, h, out_png):
    os.makedirs(WORK, exist_ok=True)
    html = (HTML.replace("{title}", title)
                .replace("{sub}", ('<p>%s</p>' % sub) if sub else "")
                .replace("{foot}", foot or ""))
    p = os.path.join(WORK, "slide.html")
    open(p, "w", encoding="utf-8").write(html)
    url = "minis://" + os.path.relpath(p, "/var/minis").replace(os.sep, "/")
    subprocess.run(["minis-browser-use", "set_viewport", "--width", str(w), "--height", str(h)],
                   capture_output=True)
    subprocess.run(["minis-browser-use", "navigate", "--url", url], capture_output=True)
    r = subprocess.run(["minis-browser-use", "screenshot"], capture_output=True, text=True)
    try:
        import json as _j
        src = _j.loads(r.stdout)["data"]["image_path"]
    except Exception:                                             # noqa: BLE001
        return None
    im = Image.open(src).convert("RGB")
    if im.size != (w, h):
        im = im.resize((w, h), Image.LANCZOS)
    im.save(out_png, "PNG")
    return out_png


def to_film(src_png, w, h, out=OUT, mirror=True, threshold=150, dither=False):
    im = Image.open(src_png).convert("L")
    a = np.asarray(im, dtype=np.uint8)
    if dither:
        # Floyd–Steinberg：连续调图片用，文字用不着
        f = a.astype(np.float32)
        for y in range(f.shape[0] - 1):
            for x in range(f.shape[1] - 1):
                old = f[y, x]
                new = 255.0 if old > 127 else 0.0
                err = old - new
                f[y, x] = new
                f[y, x + 1] += err * 7 / 16
                f[y + 1, x - 1:x + 2] += err * np.array([3, 5, 1]) / 16
        bw = (f > 127).astype(np.uint8) * 255
    else:
        bw = ((a > threshold) * 255).astype(np.uint8)
    im2 = Image.fromarray(bw, "L").convert("RGB")
    if mirror:
        im2 = im2.transpose(Image.FLIP_LEFT_RIGHT)
    d = ImageDraw.Draw(im2)
    m = int(w * 0.03)
    for cx, cy in ((m, m), (w - m, m), (m, h - m), (w - m, h - m)):
        d.line([(cx - 18, cy), (cx + 18, cy)], fill=(0, 0, 0), width=4)
        d.line([(cx, cy - 18), (cx, cy + 18)], fill=(0, 0, 0), width=4)
    im2.save(out, "PNG")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("title", nargs="*")
    ap.add_argument("--sub", default="")
    ap.add_argument("--foot", default="GBT小土豆V8")
    ap.add_argument("--image")
    ap.add_argument("--size", default="A6", choices=list(SIZES))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--ink", type=int, default=150, help="二值阈值（越大黑越多）")
    a = ap.parse_args()

    w, h = SIZES[a.size]
    if a.image:
        tmp = os.path.join(WORK, "slide_src.png")
        os.makedirs(WORK, exist_ok=True)
        im = Image.open(a.image).convert("RGB")
        im.thumbnail((int(w * .86), int(h * .86)), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), (255, 255, 255))
        canvas.paste(im, ((w - im.size[0]) // 2, (h - im.size[1]) // 2))
        canvas.save(tmp, "PNG")
        src, dither = tmp, True
    else:
        if not a.title:
            print("用法：slide.py \"标题\" [--sub 副标题] 或 --image 图.png")
            return 1
        src = render_html(" ".join(a.title), a.sub, a.foot, w, h,
                          os.path.join(WORK, "slide_src.png"))
        dither = False
        if not src:
            print("渲染失败（浏览器没在前台？）")
            return 2

    out = to_film(src, w, h, a.out, mirror=not a.no_mirror, threshold=a.ink, dither=dither)
    kb = os.path.getsize(out) / 1024
    print("%s · %dx%d px @300dpi · %s · %.0f KB" % (out, w, h, a.size, kb))
    print("已做：水平镜像 · 纯黑白 · 四角裁切标记")
    print("打印：喷墨透明胶片（不要省墨模式），按 100% 比例打印，勿缩放")
    print("光路：闪光灯 → 匀光纸 → 胶片 → 凸透镜 f≈100-150mm → 墙（全黑房间）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
