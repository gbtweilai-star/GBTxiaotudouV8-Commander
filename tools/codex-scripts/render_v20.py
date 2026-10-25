# -*- coding: utf-8 -*-
"""渲染 V20 的 AI朋友圈关系场 + 上帝视角里的关系场缩略图。"""
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
    pg.goto((BASE / "V21 GBT小土豆V8-可交互原型.html").as_uri(), wait_until="load", timeout=60000)
    pg.wait_for_timeout(2500)
    pg.click('[data-nav="socialgraph"]')
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(OUT / "v20_graph_top.png"))
    info = pg.evaluate("""() => {
        const b = document.getElementById('chatBody');
        return {cards: b.querySelectorAll('.card').length, svg: b.querySelectorAll('svg').length,
                circles: b.querySelectorAll('svg circle').length,
                lines: b.querySelectorAll('svg line').length,
                html: b.innerHTML.length, h: b.scrollHeight};
    }""")
    print("关系场:", info)
    pg.evaluate("() => { const b=document.getElementById('chatBody'); b.scrollTop = 460; }")
    pg.wait_for_timeout(700)
    pg.screenshot(path=str(OUT / "v20_graph_mid.png"))
    pg.evaluate("() => { const b=document.getElementById('chatBody'); b.scrollTop = b.scrollHeight; }")
    pg.wait_for_timeout(700)
    pg.screenshot(path=str(OUT / "v20_graph_bottom.png"))
    # 上帝视角
    pg.click("#godBtn")
    pg.wait_for_timeout(2000)
    pg.screenshot(path=str(OUT / "v20_god.png"))
    b.close()
print("截图完成")
