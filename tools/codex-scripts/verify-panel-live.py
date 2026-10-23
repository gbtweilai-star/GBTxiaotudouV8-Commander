# -*- coding: utf-8 -*-
"""真浏览器验收：拿一个干净页面加载本机 DSH（127.0.0.1:3080），
读出**实际装载的世代戳 / 样式表 / 品牌行文本**，并按需点开总面板截图。

为什么必须这么做：Owner 的那张页面拿的是**上一代包**，而页面自己永远判不出
"我这一代旧了"（自愈脚本里的 GEN 是随页面一起发下来的）——
所以"部署成功"只能用**新开的页面**证明，不能看老页面。

用法：
    python tools/codex-scripts/verify-panel-live.py            # 只读诊断
    python tools/codex-scripts/verify-panel-live.py --shot     # 再点开总面板并截图
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
OUT = ROOT / ".scratch"
OUT.mkdir(parents=True, exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = "http://127.0.0.1:3080/"

DIAG = r"""
() => {
  const t = (el) => (el ? (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 120) : null);
  const rail = document.querySelector('aside, [class*="sidebar" i], [class*="rail" i]');
  const brandish = [];
  document.querySelectorAll('body *').forEach((el) => {
    if (el.children.length) return;
    const s = t(el);
    if (!s) return;
    if (/GBT|HARNESS|土豆/.test(s)) {
      brandish.push({
        tag: el.tagName, cls: String(el.className || '').slice(0, 80), text: s,
        box: (() => { const r = el.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })(),
        slot: el.getAttribute('data-slot') || null,
      });
    }
  });
  const headerHits = [];
  document.querySelectorAll('[class*="gbtm" i]').forEach((el) => {
    headerHits.push({
      tag: el.tagName, cls: String(el.className || '').slice(0, 70),
      title: el.getAttribute('title') || el.getAttribute('aria-label') || null, text: t(el),
    });
  });
  return {
    url: location.href,
    gbtGen: document.documentElement.dataset.gbtGen || null,
    styleIds: [...document.querySelectorAll('style[id]')].map((s) => s.id).filter((i) => /gbt/i.test(i)),
    overlayPresent: !!document.querySelector('.gbtm-gv'),
    overlayVisible: (() => { const el = document.querySelector('.gbtm-gv'); if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; })(),
    railText: t(rail),
    brandish: brandish.slice(0, 14),
    gbtmNodes: headerHits.slice(0, 24),
  };
}
"""


def main(argv: list[str]) -> int:
    shot = "--shot" in argv
    from playwright.sync_api import sync_playwright

    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, headless=True,
                                     args=["--hide-scrollbars"])
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)[:200]))
        page.on("console", lambda m: errors.append("console.%s: %s" % (m.type, m.text[:160]))
                if m.type in ("error", "warning") else None)
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(7000)
        diag = page.evaluate(DIAG)
        diag["errors"] = errors[:12]

        if shot:
            # 会话头右上两个入口：按可见文本点第一个匹配（panel / godview）
            opened = None
            for label in ("总面板", "面板", "GBT小土豆"):
                try:
                    loc = page.get_by_text(label, exact=False).first
                    if loc.count() > 0:
                        loc.click(timeout=4000)
                        opened = label
                        break
                except Exception as e:  # noqa: BLE001
                    diag.setdefault("clickErrors", []).append("%s: %s" % (label, str(e)[:120]))
            page.wait_for_timeout(2500)
            full = OUT / "_pw_full.png"
            page.screenshot(path=str(full))
            rail = OUT / "_pw_rail.png"
            page.screenshot(path=str(rail), clip={"x": 0, "y": 0, "width": 330, "height": 1000})
            diag["clicked"] = opened
            diag["shots"] = [str(full.relative_to(ROOT)), str(rail.relative_to(ROOT))]
            diag["afterClick"] = page.evaluate(
                "() => ({gv: !!document.querySelector('.gbtm-gv'),"
                " rail: (document.querySelector('.gbtm-rail')||{}).textContent ? "
                "(document.querySelector('.gbtm-rail').textContent||'').trim().replace(/\\s+/g,' ').slice(0,300) : null,"
                " rows: document.querySelectorAll('.gbtm-row').length})")
        browser.close()

    print(json.dumps(diag, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
