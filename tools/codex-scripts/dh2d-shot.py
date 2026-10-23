# -*- coding: utf-8 -*-
"""dh2d-shot.py — 给 2.5D 数字人试机台拍验收截图（真浏览器、真 WebGL，不是另写一个渲染器）。

用法:
  py -3.14 tools/codex-scripts/dh2d-shot.py --out outputs/dh-probe --shots idle,jaw40,jaw85,blink
回执 <<<GBT-DH2D-SHOT>>> + JSON（每张的路径/字节/尺寸/页面自报状态）
"""
import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright

for _s in (sys.stdout, sys.stderr):          # 不带 -X utf8 调用时不许静默输出空
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAGE = os.path.join(ROOT, 'holo_pet_w3', 'voice-theater', 'dh2d-lab.html')

SHOTS = {
    'idle':   {},
    'jaw20':  {'jaw': 0.20},
    'jaw45':  {'jaw': 0.45},
    'jaw70':  {'jaw': 0.70},
    'jaw100': {'jaw': 1.00},
    'blink':  {'blink': 1.0},
    'tilt':   {'tilt': 0.06, 'nod': 0.03},
    'sway':   {'sway': 9.0, 'breath': 1.0},
    'speak':  {'jaw': 0.55, 'sway': -5.0, 'tilt': -0.02, 'state': 'speak', 'level': 0.8},
}


def find_chrome():
    """py 版 playwright 与盘上浏览器的版本号对不上时，直接指一个真在盘上的 chromium 可执行件。
    （实测：包要 chromium_headless_shell-1217，盘上只有 1223/1243 ⇒ 默认 launch 直接报缺件。）"""
    base = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright')
    cands = []
    if os.path.isdir(base):
        for d in sorted(os.listdir(base), reverse=True):
            for rel in ('chrome-win64/chrome.exe', 'chrome-win/chrome.exe',
                        'chrome-headless-shell-win64/chrome-headless-shell.exe'):
                p = os.path.join(base, d, rel)
                if os.path.exists(p):
                    cands.append(p)
    return cands[0] if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'outputs', 'dh-probe'))
    ap.add_argument('--shots', default='idle,jaw45,jaw100,blink')
    ap.add_argument('--w', type=int, default=420)
    ap.add_argument('--h', type=int, default=900)
    ap.add_argument('--scale', type=float, default=1.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    rec = {'ok': False, 'page': PAGE, 'shots': [], 'console': []}
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, executable_path=find_chrome(), args=[
            '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
            '--allow-file-access-from-files', '--disable-web-security',
        ])
        pg = br.new_page(viewport={'width': a.w, 'height': a.h}, device_scale_factor=a.scale)
        pg.on('console', lambda m: rec['console'].append(m.type + ': ' + m.text[:300]))
        pg.on('pageerror', lambda e: rec['console'].append('pageerror: ' + str(e)[:300]))

        for name in a.shots.split(','):
            name = name.strip()
            if not name:
                continue
            p = dict(SHOTS.get(name, {}))
            url = 'file:///' + PAGE.replace('\\', '/').replace(' ', '%20')
            qs = '&'.join('%s=%s' % (k, v) for k, v in p.items())
            if qs:
                url += '?' + qs
            pg.goto(url, wait_until='load')
            try:
                pg.wait_for_function('window.__DH2D_READY === true', timeout=15000)
            except Exception:
                rec['console'].append('timeout waiting ready for ' + name)
            pg.wait_for_timeout(260)
            out = os.path.join(a.out, 'dh2d-%s.png' % name)
            pg.screenshot(path=out)
            info = pg.evaluate('(function(){var i=window.GBT_DH2D&&window.GBT_DH2D.info();'
                               'return i?{ok:i.ok,status:i.status,why:i.why,frames:i.frames,'
                               'gl:i.gl,jaw:i.jawNow,blink:i.blinkNow}:null})()')
            rec['shots'].append({'shot': name, 'params': p, 'path': out,
                                 'bytes': os.path.getsize(out) if os.path.exists(out) else -1,
                                 'info': info})
        br.close()

    rec['ok'] = all(s['bytes'] > 5000 and s['info'] and s['info'].get('ok') for s in rec['shots'])
    print('<<<GBT-DH2D-SHOT>>>')
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    if not rec['ok']:
        sys.exit(1)


if __name__ == '__main__':
    main()
