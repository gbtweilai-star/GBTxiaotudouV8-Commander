# -*- coding: utf-8 -*-
"""dh2d-theater-shot.py — 给**真剧场页**拍一张，确认数字人在真页面里是活的（不是只在试机台上活）。

用法: py -3.14 tools/codex-scripts/dh2d-theater-shot.py [--jaw 0.55] [--out xxx.png]
"""
import argparse
import json
import os

from playwright.sync_api import sync_playwright
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAGE = os.path.join(ROOT, 'holo_pet_w3', 'voice-theater', 'index.html')


def find_chrome():
    base = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright')
    for d in sorted(os.listdir(base), reverse=True):
        p = os.path.join(base, d, 'chrome-win64', 'chrome.exe')
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=float, default=0.8)
    ap.add_argument('--jaw', type=float, default=-1)
    ap.add_argument('--state', default='speak')
    ap.add_argument('--out', default=os.path.join(ROOT, 'outputs', 'dh-probe', 'theater-speak.png'))
    a = ap.parse_args()

    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, executable_path=find_chrome(), args=[
            '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
            '--allow-file-access-from-files'])
        pg = br.new_page(viewport={'width': 1440, 'height': 900})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.goto('file:///' + PAGE.replace('\\', '/'), wait_until='load')
        pg.wait_for_function('window.GBT_DH2D && window.GBT_DH2D.ready && window.GBT_DH2D.ready()',
                             timeout=20000)
        pg.evaluate('window.GBT_DH2D.setState("%s")' % a.state)
        if a.jaw >= 0:
            pg.evaluate('window.GBT_DH2D._frozen(true);'
                        'window.GBT_DH2D.set({jaw:%f, blink:0})' % a.jaw)
            pg.evaluate('window.GBT_DH2D._draw(1.0)')
        else:
            # 走活链路：只喂音量，让 step() 自己算嘴（与页面上真实说话同一条路）
            pg.evaluate('window.GBT_DH2D.level(%f)' % a.level)
            pg.evaluate('window.GBT_DH2D._tick(45, 1/60)')
        pg.wait_for_timeout(300)
        pg.screenshot(path=a.out)
        info = pg.evaluate('window.GBT_DH2D.info()')
        badge = pg.evaluate('(function(){var b=document.getElementById("dh3dStatus");'
                            'return b?b.textContent:null})()')
        print(json.dumps({'out': a.out, 'bytes': os.path.getsize(a.out),
                          'info': info, 'badge': badge, 'errs': errs},
                         ensure_ascii=False, indent=1))
        br.close()


if __name__ == '__main__':
    main()

