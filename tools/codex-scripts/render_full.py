# -*- coding: utf-8 -*-
"""真渲染 · 全量：55 面板 + 上帝视角 + 亮色 + 三个视口 + 浏览器级 UI-check。
这是**真渲染级验证**（Playwright 驱动系统 Chrome），不是合成样张。
"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
OUT = BASE / ".scratch" / "render"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROTO = BASE / "V21 GBT小土豆V8-可交互原型.html"

# 浏览器里跑的 UI-check：横向溢出 / 文字裁切 / 元素越界
UI_CHECK_JS = """() => {
  const bad = [];
  const vw = window.innerWidth;
  document.querySelectorAll('#chatBody *, #navList *, .top *, .composer *').forEach(el => {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    // 越出视口右/左边界
    if (r.right > vw + 1 || r.left < -1) {
      bad.push({kind: 'out-of-viewport', tag: el.tagName, cls: (el.className||'').toString().slice(0,40),
                left: Math.round(r.left), right: Math.round(r.right), vw});
    }
    // 文字被裁切（overlay 隐藏或 nowrap 溢出且没省略号）
    if (el.scrollWidth > el.clientWidth + 2 && st.overflowX !== 'auto' && st.overflowX !== 'scroll') {
      const clip = st.textOverflow === 'ellipsis' || st.overflow === 'hidden';
      if (!clip) bad.push({kind: 'text-clipped', tag: el.tagName, cls: (el.className||'').toString().slice(0,40),
                           scrollW: el.scrollWidth, clientW: el.clientWidth});
    }
  });
  return {
    docScrollW: document.documentElement.scrollWidth,
    innerW: window.innerWidth,
    hScroll: document.documentElement.scrollWidth > window.innerWidth + 1,
    issues: bad.slice(0, 12),
    nIssues: bad.length,
  };
}"""

problems, shots, uicheck = [], [], []

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME, headless=True,
                                 args=["--hide-scrollbars", "--allow-file-access-from-files"])
    for tag, w, h in (("desktop", 1680, 1050), ("mid", 1280, 800), ("mobile", 390, 844)):
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        page.on("pageerror", lambda e: problems.append(("pageerror", str(e)[:200])))
        page.on("console", lambda m: problems.append(("console." + m.type, m.text[:160]))
                if m.type == "error" else None)
        page.goto(PROTO.as_uri(), wait_until="load", timeout=60000)
        page.wait_for_timeout(2000)
        nav = page.evaluate("""() => Array.from(document.querySelectorAll('#navList [data-nav]'))
            .map(b => ({key: b.dataset.nav, label: (b.textContent||'').trim()}))""")
        # 窄屏下侧栏是抽屉，点不到导航项 —— 先开抽屉（真渲染才发现这一点）
        narrow = w < 900
        if narrow:
            try:
                page.click("#navToggle", timeout=4000)
                page.wait_for_timeout(500)
            except Exception as e:  # noqa: BLE001
                problems.append(("drawer-fail", str(e)[:120]))
        print("[%s %dx%d] 导航 %d 项%s" % (tag, w, h, len(nav), "（抽屉模式）" if narrow else ""))
        for i, n in enumerate(nav, 1):
            key, label = n["key"], n["label"]
            try:
                if narrow:
                    page.click("#navToggle", timeout=4000)
                    page.wait_for_timeout(260)
                page.click('[data-nav="%s"]' % key, timeout=8000)
            except Exception as e:  # noqa: BLE001
                problems.append(("click-fail", "%s/%s: %s" % (tag, key, str(e)[:100])))
                continue
            page.wait_for_timeout(450)
            info = page.evaluate("""() => {
                const b = document.getElementById('chatBody');
                return b ? {len: b.innerHTML.length, cards: b.querySelectorAll('.card').length} : {len:0,cards:0};
            }""")
            uic = page.evaluate(UI_CHECK_JS)
            if uic["nIssues"]:
                uicheck.append({"viewport": tag, "panel": key, **uic})
            if info["len"] < 600:
                problems.append(("thin-panel", "%s/%s 只画了 %d 字符" % (tag, label, info["len"])))
            if tag == "desktop":
                safe = re.sub(r"[^\w\u4e00-\u9fff-]", "_", label)[:26]
                name = "%02d_%s_%s.png" % (i, key, safe)
                page.screenshot(path=str(OUT / "panels" / name))
                shots.append({"i": i, "key": key, "label": label, "file": name, **info})
        # 上帝视角 + 亮色
        if tag == "desktop":
            page.click("#godBtn")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / "panels" / "98_god.png"))
            page.click("#godClose")
            page.wait_for_timeout(400)
            page.click("#themeBtn")
            page.wait_for_timeout(800)
            page.click('[data-nav="brain"]')
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / "panels" / "99_light_brain.png"))
            page.click("#themeBtn")
            page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / ("viewport_%s.png" % tag)))
        page.close()
    browser.close()

rep = {"shots": shots, "problems": problems, "uicheck": uicheck}
(OUT / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n" + "=" * 86)  # noqa: E402
print("面板截图 %d 张 · 问题 %d 条 · UI-check 命中面板 %d 个" %
      (len(shots), len(problems), len(uicheck)))
for k, m in problems[:12]:
    print("  [%s] %s" % (k, m))
import collections  # noqa: E402
c = collections.Counter(i["kind"] for u in uicheck for i in u["issues"])
print("  UI-check 明细:", dict(c) or "无")
for u in uicheck[:6]:
    print("    %s/%s: %s" % (u["viewport"], u["panel"], json.dumps(u["issues"][:3], ensure_ascii=False)[:200]))
