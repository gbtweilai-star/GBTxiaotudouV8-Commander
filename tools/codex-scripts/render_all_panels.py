# -*- coding: utf-8 -*-
"""真渲染：把可交互原型的**每一个面板**逐一切换并截图（Playwright 驱动系统 Chrome）。
顺带收集 console 错误与页面异常 —— 这是真正的渲染级验证，不是合成样张。
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# 本目录自 .scratch/ 迁到 tools/codex-scripts/ 后深度 +1：原来的 .parent.parent
# 落在 …\tools\（tools 下 0 个 html）。向上找根标记。
BASE = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
OUT = BASE / ".scratch" / "render" / "panels"
OUT.mkdir(parents=True, exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def _latest_proto(base):
    """取根目录里版本号最大的可交互原型 —— 不再把 V17 写死。

    旧版 PROTO 硬编码 V17，而交付物已是 V21：docstring 自称「真正的渲染级验证」，
    实测跑的却是两版之前的文件，报告也没有任何东西会因此变红。
    """
    cands = [f for f in base.glob("V*.html") if "可交互原型" in f.name]

    def _ver(f):
        m = re.match(r"V(\d+) ", f.name)
        return int(m.group(1)) if m else -1
    return max(cands, key=_ver)


PROTO = _latest_proto(BASE)

problems = []
shots = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME, headless=True,
                                 args=["--hide-scrollbars", "--allow-file-access-from-files"])
    page = browser.new_page(viewport={"width": 1680, "height": 1050}, device_scale_factor=1)
    page.on("console", lambda m: problems.append(("console." + m.type, m.text[:200]))
            if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(("pageerror", str(e)[:260])))
    page.goto(PROTO.as_uri(), wait_until="load", timeout=60000)
    page.wait_for_timeout(2500)

    nav = page.evaluate("""() => Array.from(document.querySelectorAll('#navList [data-nav]'))
        .map(b => ({key: b.dataset.nav, label: (b.textContent||'').trim()}))""")
    print("导航项 %d 个" % len(nav))
    for i, n in enumerate(nav, 1):
        key, label = n["key"], n["label"]
        try:
            page.click('[data-nav="%s"]' % key, timeout=8000)
        except Exception as e:  # noqa: BLE001
            problems.append(("click-fail", "%s: %s" % (key, str(e)[:120])))
            continue
        page.wait_for_timeout(750)
        # 面板内容是否真的画出来了
        info = page.evaluate("""() => {
            const b = document.getElementById('chatBody');
            if (!b) return {len: 0, cards: 0, h: 0};
            return {len: b.innerHTML.length, cards: b.querySelectorAll('.card').length,
                    h: b.scrollHeight, title: (document.getElementById('chatTitle')||{}).textContent||''};
        }""")
        safe = re.sub(r"[^\w\u4e00-\u9fff-]", "_", label)[:28]
        name = "%02d_%s_%s.png" % (i, key, safe)
        page.screenshot(path=str(OUT / name))
        shots.append({"i": i, "key": key, "label": label, "file": name, **info})
        print("  [%2d/%d] %-14s %-16s cards=%-3d html=%-7d h=%-6d %s"
              % (i, len(nav), key, info["title"][:14], info["cards"], info["len"], info["h"], name))
        if info["len"] < 300:
            problems.append(("empty-panel", "%s(%s) 只画了 %d 字符" % (label, key, info["len"])))

    # 上帝视角
    try:
        page.click("#godBtn")
        page.wait_for_timeout(1600)
        page.screenshot(path=str(OUT / "98_god.png"))
        g = page.evaluate("() => (document.getElementById('godBody')||{}).innerHTML?.length || 0")
        print("  上帝视角 godBody=%d" % g)
        if g < 300:
            problems.append(("empty-panel", "上帝视角只画了 %d 字符" % g))
    except Exception as e:  # noqa: BLE001
        problems.append(("god-fail", str(e)[:160]))

    # 亮色主题
    try:
        page.click("#godClose")
        page.wait_for_timeout(400)
        page.click("#themeBtn")
        page.wait_for_timeout(900)
        page.click('[data-nav="brain"]')
        page.wait_for_timeout(900)
        page.screenshot(path=str(OUT / "99_light_brain.png"))
        print("  亮色主题已截图")
    except Exception as e:  # noqa: BLE001
        problems.append(("light-fail", str(e)[:160]))

    browser.close()

(BASE / ".scratch" / "render_report.json").write_text(
    json.dumps({"shots": shots, "problems": problems}, ensure_ascii=False, indent=1), encoding="utf-8")

print("\n" + "=" * 84)
print("问题汇总: %d 条" % len(problems))
seen = set()
for kind, msg in problems:
    k = (kind, msg[:60])
    if k in seen:
        continue
    seen.add(k)
    print("  [%s] %s" % (kind, msg))
print("\n截图 %d 张 → %s" % (len(shots), OUT))

# 空面板 / 点击失败 / 页面异常必须让退出码非零 —— 旧版只 append 到 problems
# 就收工，报告里躺着 empty-panel 也照样 exit 0，等于「报告是绿的所以没事」。
BLOCKING = ("empty-panel", "click-fail", "pageerror", "god-fail", "light-fail")
block = [p for p in problems if p[0] in BLOCKING]
if block:
    print("\n阻断交付的问题 %d 条（退出码 1）：" % len(block))
    for kind, msg in block:
        print("   - [%s] %s" % (kind, msg))
sys.exit(1 if block else 0)
