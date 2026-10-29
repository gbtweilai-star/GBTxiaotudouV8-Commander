# -*- coding: utf-8 -*-
"""通用页面截图 + 读数（Playwright）。用于验证"可在面板里看的成品页"。
用法: python tools/codex-scripts/shot-page.py <url> <输出名.png> [等待JS] [点击选择器] [点击后等待秒]
例:   python tools/codex-scripts/shot-page.py "http://127.0.0.1:3080/xxx.html" 形象页.png "window.__ready" "#bWalk" 2.5"""
import json
import pathlib
import sys
from playwright.sync_api import sync_playwright

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

url = sys.argv[1]
name = sys.argv[2]
wait_js = sys.argv[3] if len(sys.argv) > 3 else ""
click = sys.argv[4] if len(sys.argv) > 4 else ""
after = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
out = WS / "render" / name

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME, headless=True,
                           args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1180, "height": 720})
    errs, logs = [], []
    pg.on("pageerror", lambda e: errs.append(str(e)[:180]))
    pg.on("console", lambda m: logs.append(m.type + ": " + m.text[:140]))
    pg.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url[-70:]}") if r.status >= 400 else None)
    pg.goto(url, wait_until="load", timeout=60000)
    if wait_js:
        try:
            pg.wait_for_function(f"() => {wait_js}", timeout=60000)
        except Exception as e:
            errs.append("等待超时: " + str(e)[:80])
    if click:
        try:
            pg.click(click, timeout=8000)
        except Exception as e:
            errs.append("点击失败 " + click + ": " + str(e)[:60])
    pg.wait_for_timeout(int((after or 1.5) * 1000))
    info = pg.evaluate("""() => {
        const t = (id) => { const el = document.getElementById(id); return el ? el.textContent : null; };
        const c = document.querySelector('canvas');
        return { clip: t('clip'), fps: t('fps'), verts: t('verts'), tris: t('tris'),
                 joints: t('joints'), anims: t('anims'), blend: t('blend'),
                 canvas: c ? [c.width, c.height] : null,
                 err: window.__err || '', ready: !!window.__ready };
    }""")
    pg.screenshot(path=str(out))
    print(json.dumps(info, ensure_ascii=False))
    print("问题:", errs[:4] if errs else "无")
    if logs:
        print("控制台:", logs[:3])
    print("saved:", out)
    b.close()
