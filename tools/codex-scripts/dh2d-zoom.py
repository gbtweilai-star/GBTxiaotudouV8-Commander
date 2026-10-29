# -*- coding: utf-8 -*-
"""dh2d-zoom.py — 把嘴放大看细节（P7：不看缩略图）。

为什么单独一个件：缩略图里"黑药丸"和"真的张嘴"长得一模一样；只有把嘴部放大 3~4 倍、
并按张口度排成一行，才看得出嘴唇边缘、牙、舌、下颌位移是否成立。

用法: py -3.14 tools/codex-scripts/dh2d-zoom.py [--jaws 0,0.25,0.5,0.75,0.95] [--out xxx.png]
"""
import argparse
import base64
import os

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB = os.path.join(ROOT, 'holo_pet_w3', 'voice-theater', 'dh2d-lab.html')
W, H = 720, 1500


def find_chrome():
    base = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright')
    for d in sorted(os.listdir(base), reverse=True):
        p = os.path.join(base, d, 'chrome-win64', 'chrome.exe')
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jaws', default='0,0.25,0.5,0.75,0.95')
    ap.add_argument('--out', default=os.path.join(ROOT, 'outputs', 'dh-probe', 'mouth-zoom.png'))
    ap.add_argument('--crop', default='250,190,470,370', help='x0,y0,x1,y1（720x1500 画布内）')
    ap.add_argument('--zoom', type=int, default=3)
    ap.add_argument('--crop-h', type=float, default=0.0, help='取景（0=用页面自己的 data-crop-h）')
    a = ap.parse_args()
    jaws = [float(x) for x in a.jaws.split(',') if x.strip()]
    x0, y0, x1, y1 = [int(v) for v in a.crop.split(',')]

    tiles = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, executable_path=find_chrome(), args=[
            '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
            '--allow-file-access-from-files'])
        pg = br.new_page(viewport={'width': W + 40, 'height': H + 40}, device_scale_factor=1)
        pg.goto('file:///' + LAB.replace('\\', '/'), wait_until='load')
        pg.wait_for_function('window.__DH2D_READY === true', timeout=20000)
        pg.evaluate('var c=document.getElementById("dh2d");'
                    'c.style.width="%dpx"; c.style.height="%dpx";'
                    'window.GBT_DH2D._frozen(true);' % (W, H))
        if a.crop_h > 0:
            pg.evaluate('window.GBT_DH2D.setCrop(%f)' % a.crop_h)
        for jv in jaws:
            # 量具必须**确定性**：只钉 jaw 不钉姿态，呼吸/晃动/眨眼会吃进对比 ——
            # 实测同一份代码渲两次差 155k 像素，差点把噪声读成"改动生效"（P1/P29）。
            pg.evaluate('window.GBT_DH2D.set({jaw:%f, blink:0, breath:0, sway:0, tilt:0, nod:0, look:0})' % jv)
            url = pg.evaluate('window.GBT_DH2D._png(1.0)')
            tmp = os.path.join(ROOT, 'outputs', 'dh-probe', '_zoom_%s.png' % str(jv).replace('.', '_'))
            with open(tmp, 'wb') as f:
                f.write(base64.b64decode(url.split(',', 1)[1]))
            im = Image.open(tmp).convert('RGB').crop((x0, y0, x1, y1))
            im = im.resize((im.width * a.zoom, im.height * a.zoom), Image.LANCZOS)
            d = ImageDraw.Draw(im)
            d.text((6, 6), 'jaw=%.2f' % jv, fill=(255, 220, 80))
            tiles.append(im)
            os.remove(tmp)
        br.close()

    w, h = tiles[0].size
    sheet = Image.new('RGB', (w * len(tiles), h), (0, 0, 0))
    for k, t in enumerate(tiles):
        sheet.paste(t, (k * w, 0))
    sheet.save(a.out)
    print('<<<GBT-DH2D-ZOOM>>>')
    print('{"ok": true, "out": "%s", "n": %d, "size": [%d, %d]}'
          % (a.out.replace('\\', '/'), len(tiles), sheet.width, sheet.height))


if __name__ == '__main__':
    main()
