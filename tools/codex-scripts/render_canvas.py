# -*- coding: utf-8 -*-
"""真渲染 · 无限画布（改进版）：按**页元素本身**截图，而不是截整个视口。
页面宽 375，截 1680 视口只会得到一张几乎全黑的大图。"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
OUT = BASE / ".scratch" / "render" / "canvas"
OUT.mkdir(parents=True, exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CANVAS = BASE / "V21 GBT小土豆V8-无限画布.html"

problems, shots = [], []

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME, headless=True,
                                 args=["--hide-scrollbars", "--allow-file-access-from-files"])
    page = browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
    page.on("pageerror", lambda e: problems.append(("pageerror", str(e)[:200])))
    page.goto(CANVAS.as_uri(), wait_until="load", timeout=60000)
    page.wait_for_timeout(2500)
    # world 归零，让页元素落在文档坐标里，便于逐个截
    page.evaluate("""() => {
        const w = document.getElementById('world');
        w.style.transition = 'none';
        w.style.transform = 'translate(0px, 0px) scale(1)';
    }""")
    page.wait_for_timeout(400)

    handles = page.evaluate("""() => Array.from(document.querySelectorAll('.canvas-el'))
        .map((e, i) => ({i, isPage: !!e.querySelector(':scope > .design-page'),
                         label: (e.querySelector('.page-label')||{}).textContent||''}))
        .filter(x => x.isPage)""")
    print("画布页 %d 个" % len(handles))
    els = page.query_selector_all(".canvas-el")
    pages = [e for e in els if e.query_selector(":scope > .design-page")]
    for i, el in enumerate(pages, 1):
        label = page.evaluate("(e) => (e.querySelector('.page-label')||{}).textContent||''", el)
        safe = re.sub(r"[^\w\u4e00-\u9fff-]", "_", (label or "").strip())[:30] or ("page%d" % i)
        name = "%02d_%s.png" % (i, safe)
        try:
            el.scroll_into_view_if_needed(timeout=4000)
            el.screenshot(path=str(OUT / name))
            shots.append({"i": i, "label": label, "file": name})
        except Exception as e:  # noqa: BLE001
            problems.append(("shot-fail", "%s: %s" % (label[:20], str(e)[:100])))
        if i % 12 == 0 or i == len(pages):
            print("  [%2d/%d] %s" % (i, len(pages), name))

    # 全景（缩小看全貌）
    page.evaluate("""() => {
        const w = document.getElementById('world');
        w.style.transform = 'translate(30px, 20px) scale(0.075)';
    }""")
    page.wait_for_timeout(900)
    page.set_viewport_size({"width": 2200, "height": 1500})
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / "00_overview.png"))
    print("  全景已截图")
    browser.close()

(Path(BASE / ".scratch" / "render" / "canvas_report.json")).write_text(
    json.dumps({"shots": shots, "problems": problems}, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n画布截图 %d 张 · 问题 %d 条" % (len(shots), len(problems)))
for k, m in problems[:8]:
    print("  [%s] %s" % (k, m))
