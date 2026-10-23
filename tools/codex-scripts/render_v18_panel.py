# -*- coding: utf-8 -*-
"""渲染 V18 的源码驱动能力广场（上/下两屏）。"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
OUT = BASE / ".scratch" / "render"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME, headless=True,
                           args=["--hide-scrollbars", "--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": 1680, "height": 1050}, device_scale_factor=2)
    pg.goto((BASE / "V18 GBT小土豆V8-可交互原型.html").as_uri(), wait_until="load", timeout=60000)
    pg.wait_for_timeout(2500)
    pg.click('[data-nav="square"]')
    pg.wait_for_timeout(1400)
    pg.screenshot(path=str(OUT / "v18_capsrc_top.png"))
    info = pg.evaluate("""() => {
        const b = document.getElementById('chatBody');
        return {cards: b.querySelectorAll('.card').length, html: b.innerHTML.length,
                h: b.scrollHeight, rows: b.querySelectorAll('[data-csf]').length};
    }""")
    print("能力广场:", info)
    # 点「待授权」筛选，验证交互
    pg.click('[data-csf="gated"]')
    pg.wait_for_timeout(900)
    g = pg.evaluate("() => document.getElementById('chatBody').innerHTML.length")
    pg.screenshot(path=str(OUT / "v18_capsrc_gated.png"))
    print("筛选「待授权」后 html=%d" % g)
    pg.click('[data-csf="all"]')
    pg.wait_for_timeout(800)
    pg.evaluate("() => { const b=document.getElementById('chatBody'); b.scrollTop = b.scrollHeight; }")
    pg.wait_for_timeout(700)
    pg.screenshot(path=str(OUT / "v18_capsrc_bottom.png"))
    b.close()
print("截图完成")
