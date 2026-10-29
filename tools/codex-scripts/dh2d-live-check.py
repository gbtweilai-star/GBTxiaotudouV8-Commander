# -*- coding: utf-8 -*-
"""dh2d-live-check.py — 验**活链路**：音量 → step() → 嘴开合，在真剧场页上跑。

不是"给个 jaw 值看画面"（那只能验着色器）；这里只喂 level()，让 step() 自己算嘴，
再读 st.jaw。三条读数：静音不张嘴 / 有音量开到相应幅度 / 音量掉回去嘴闭合。
"""
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
base = os.path.join(os.environ['LOCALAPPDATA'], 'ms-playwright')
EXE = [os.path.join(base, d, 'chrome-win64', 'chrome.exe')
       for d in sorted(os.listdir(base), reverse=True)
       if os.path.exists(os.path.join(base, d, 'chrome-win64', 'chrome.exe'))][0]

with sync_playwright() as pw:
    br = pw.chromium.launch(headless=True, executable_path=EXE, args=[
        '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
        '--allow-file-access-from-files'])
    pg = br.new_page(viewport={'width': 1440, 'height': 900})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.goto('file:///' + PAGE.replace('\\', '/'), wait_until='load')
    pg.wait_for_function('window.GBT_DH2D && window.GBT_DH2D.ready()', timeout=20000)

    def tick(n=40, level=None, state='speak'):
        if level is not None:
            pg.evaluate('window.GBT_DH2D.level(%f)' % level)
        pg.evaluate('window.GBT_DH2D.setState("%s")' % state)
        return pg.evaluate('window.GBT_DH2D._tick(%d, 1/60)' % n)

    rec = {'ok': True, 'steps': []}
    rec['steps'].append({'case': '静音（level=0, speak）', 'out': tick(40, 0.0)})
    rec['steps'].append({'case': '大声（level=0.95, speak）', 'out': tick(60, 0.95)})
    rec['steps'].append({'case': '中声（level=0.45, speak）', 'out': tick(60, 0.45)})
    rec['steps'].append({'case': '掉回静音', 'out': tick(60, 0.0)})
    rec['steps'].append({'case': '离开说话态（listen）', 'out': tick(60, 0.95, 'listen')})

    jaw = [s['out']['jaw'] for s in rec['steps']]
    rec['jaw_track'] = jaw
    rec['verdict'] = {
        '静音时闭嘴': jaw[0] < 0.05,
        '大声时张开': jaw[1] > 0.35,
        '中声小于大声': jaw[2] < jaw[1],
        '静音后闭合': jaw[3] < 0.05,
        '非说话态不动嘴': jaw[4] < 0.05,
    }
    rec['ok'] = all(rec['verdict'].values())
    rec['errs'] = errs
    print('<<<GBT-DH2D-LIVE>>>')
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    br.close()
