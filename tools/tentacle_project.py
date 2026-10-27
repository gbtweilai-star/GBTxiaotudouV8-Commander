#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tentacle_project —— 「摄像头那根触手」：把镜头看到的东西变成**可投屏的稿**。

先说清物理边界（不许含糊）：
  iPhone 没有光学投影器，光不会从手机里射到墙上。
  手机真正能"投影"的只有**屏幕本身**。所以这条触手做的是：
      相机/相册 → 视觉分析（分类/人脸/文字/条码）→ 叠成一张标注稿 → 全屏投屏
  这是"屏幕即幕布、相机即眼睛"的可行版本，不是光投影。

用法：
    python3 tools/tentacle_project.py <图>            # 指定图
    python3 tools/tentacle_project.py --latest        # 拿相册最新一张
    python3 tools/tentacle_project.py <图> --no-marks # 只转投屏尺寸，不叠标注
"""
import argparse, json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

OUT = "/var/minis/attachments/project_sheet.png"
W, H = 1080, 1920          # 竖屏全屏投屏规格


def sh(cmd):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)
    return r.stdout


def latest_photo():
    out = sh(["apple-photos", "list", "--limit", "1"])
    try:
        d = json.loads(out)
        items = d.get("data", {}).get("photos") or d.get("data", {}).get("assets") or []
        p = items[0].get("path") or items[0].get("id")
        if p:
            e = json.loads(sh(["apple-photos", "export", p]))
            return e.get("data", {}).get("path") or e.get("data", {}).get("file")
    except Exception:                                             # noqa: BLE001
        pass
    return None


def analyze(path):
    try:
        return json.loads(sh(["apple-vision", "analyze", path])).get("data", {})
    except Exception:                                             # noqa: BLE001
        return {}


def build(src, dst=OUT, marks=True):
    im = Image.open(src).convert("RGB")
    # 等比铺满 1080x1920，居中裁切
    s = max(W / im.size[0], H / im.size[1])
    im = im.resize((int(im.size[0] * s + 1), int(im.size[1] * s + 1)), Image.LANCZOS)
    x = (im.size[0] - W) // 2; y = (im.size[1] - H) // 2
    canvas = im.crop((x, y, x + W, y + H)).convert("RGBA")
    d = ImageDraw.Draw(canvas, "RGBA")
    info = analyze(src)
    lines = []
    cls = info.get("classification") or []
    for c in cls[:3]:
        lines.append("%s %d%%" % (c.get("label"), round((c.get("confidence") or 0) * 100)))
    faces = (info.get("faces") or {}).get("count")
    if faces:
        lines.append("脸 %d" % faces)
    ocr = (info.get("ocr") or {}).get("text") or ""
    if ocr.strip():
        lines.append('文 "%s"' % ocr.strip().replace("\n", " ")[:24])
    bars = info.get("barcodes") or []
    if bars:
        lines.append("条码 %d" % len(bars))

    if marks:
        # 安全框（投屏时的可视边界）+ 顶部信息条
        d.rectangle([40, 40, W - 40, H - 40], outline=(255, 255, 255, 70), width=3)
        d.rectangle([0, 0, W, 150], fill=(0, 0, 0, 140))
        d.text((48, 44), "GBT · 投影稿", fill=(255, 255, 255, 235))
        d.text((48, 96), " · ".join(lines)[:60] if lines else "未读到内容", fill=(220, 220, 220, 230))
        d.rectangle([0, H - 110, W, H], fill=(0, 0, 0, 140))
        d.text((48, H - 78), os.path.basename(src)[:52], fill=(200, 200, 200, 220))
    canvas.convert("RGB").save(dst, "PNG")
    return dst, lines


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--no-marks", action="store_true")
    a = ap.parse_args()
    src = a.src or (latest_photo() if a.latest else None)
    if not src or not os.path.exists(src):
        print("没有图：给一个路径，或先拍一张（相机属于系统 App，命令行拿不到实时画面）")
        sys.exit(2)
    dst, lines = build(src, a.out, not a.no_marks)
    print("投影稿 %s · %dx%d" % (dst, W, H))
    print("读数  " + (" · ".join(lines) if lines else "（未读到内容）"))
    print("投屏  minis-open %s" % dst)
