# -*- coding: utf-8 -*-
"""上帝视角 · 版面几何探针（改完必跑）

为什么要有它：截图只能看"当前这一屏"。内容超出视口时截图会切掉，
但**切掉 ≠ 有 bug** —— 可能只是可滚动。人眼分不清「可滚动」与「被裁死」。
本探针逐视图量 DOM 几何，把两者分清楚：

  · 内容高度 > 视口高度 且 该容器可滚动        -> SCROLL  正常（只是没滚到底）
  · 内容高度 > 视口高度 且 容器 overflow 不可滚 -> CLIP    **真 bug：内容拿不到**
  · 子元素边界超出父元素且父元素不可滚          -> OVERFLOW 真 bug
  · 元素宽度撑破视口 -> 横向滚动               -> HSCROLL 真 bug
  · 时间戳同期性：卡片「刚取」与底栏时钟时区是否一致 -> TZ

只读：不改任何文件。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright  # noqa: E402

PAGE = ROOT / "holo_pet_w3" / "index.html"
FULL = ROOT / ".scratch" / "_god_view_full.json"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
W, H = 1080, 680
TABS = [("quad", "四视图"), ("tree", "工作树"), ("matrix", "故障矩阵"),
        ("cockpit", "驾驶舱"), ("tools", "工具"), ("pets", "数字人")]

full = json.loads(FULL.read_text(encoding="utf-8"))
chan = full["channels"]


def payload(name: str):
    v = (chan.get(name) or {}).get("value")
    return v if v is not None else {"ok": False, "error": "probe 未取到该通道"}


BRIDGE_JS = """
(() => {
  const P = %s;
  const call = (n) => Promise.resolve(P[n] !== undefined ? P[n]
                    : { ok: false, error: "几何探针未取该通道: " + n });
  window.gbtW3 = {
    readonly: true,
    onEvent: () => () => {},
    state: () => call("w3:state"), tasks: () => call("w3:tasks"),
    mindmap: () => call("w3:mindmap"), matrix: () => call("w3:matrix"),
    pets: () => call("w3:pets"), tools: () => call("w3:tools"),
    ledger: () => call("w3:ledger"), selfcheck: () => call("w3:selfcheck"),
    coverage: () => call("w3:coverage"), orphans: () => call("w3:orphans"),
    gene: () => call("w3:gene"),
  };
})();
""" % json.dumps({k: payload(k) for k in (
    "w3:state", "w3:tasks", "w3:mindmap", "w3:matrix", "w3:pets",
    "w3:tools", "w3:ledger", "w3:selfcheck", "w3:coverage", "w3:orphans", "w3:gene")},
    ensure_ascii=False)

MEASURE_JS = """
(() => {
  const out = { cards: [], bad: [] };
  const vpW = document.documentElement.clientWidth;
  const vpH = document.documentElement.clientHeight;
  out.viewport = [vpW, vpH];
  document.querySelectorAll('.gbt-view[data-active="true"] .gbt-card, .gbt-view[data-active="true"] article.gbt-card').forEach((c) => {
    const cs = getComputedStyle(c);
    const scrollable = /(auto|scroll)/.test(cs.overflowY);
    const rec = {
      title: (c.querySelector('h2') || {}).textContent || '(无标题)',
      clientH: c.clientHeight, scrollH: c.scrollHeight,
      overflowY: cs.overflowY, scrollable: scrollable,
      hiddenBy: c.scrollHeight - c.clientHeight,
    };
    out.cards.push(rec);
    if (rec.hiddenBy > 2 && !scrollable) {
      out.bad.push({ kind: 'CLIP', title: rec.title, hiddenPx: rec.hiddenBy, why: '内容超出且不可滚动 —— 用户拿不到这段内容' });
    }
    // 子元素横向撑破
    c.querySelectorAll('table, pre, .gbt-tree-bar, .gbt-gap-item').forEach((el) => {
      const r = el.getBoundingClientRect(), pr = c.getBoundingClientRect();
      if (r.right - pr.right > 2) {
        out.bad.push({ kind: 'OVERFLOW', title: rec.title, el: el.className || el.tagName,
                       overPx: Math.round(r.right - pr.right), why: '子元素右侧溢出父容器' });
      }
    });
  });
  out.docScrollW = document.documentElement.scrollWidth;
  if (out.docScrollW - vpW > 2) {
    out.bad.push({ kind: 'HSCROLL', overPx: out.docScrollW - vpW, why: '页面出现横向滚动' });
  }
  const at = (id) => { const e = document.getElementById(id); return e ? e.textContent : null; };
  out.times = { clock: at('stat-clock'), cov: at('cov-at'), orph: at('orph-at'), gene: at('gene-at') };
  return out;
})()
"""


def main() -> int:
    rc = 0
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, headless=True)
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        pg.add_init_script(BRIDGE_JS)
        pg.goto(PAGE.as_uri())
        pg.wait_for_timeout(1200)
        pg.evaluate("""() => { ['coverage','orphans','gene'].forEach(n => {
            const b = document.getElementById('btn-' + n); if (b) b.click(); }); }""")
        pg.wait_for_timeout(1500)

        print("=" * 78)
        print(f"上帝视角 · 版面几何  视口 {W}x{H}")
        print("=" * 78)
        allbad = []
        for key, label in TABS:
            tab = pg.query_selector(f'.gbt-tab[data-view="{key}"], .gbt-tab[data-tab="{key}"]')
            if tab is None:
                tabs = pg.query_selector_all(".gbt-tab")
                idx = [t[0] for t in TABS].index(key)
                tab = tabs[idx] if idx < len(tabs) else None
            if tab:
                tab.click()
                pg.wait_for_timeout(500)
            m = pg.evaluate(MEASURE_JS)
            print(f"\n── {label} ({key})   视口 {m['viewport'][0]}x{m['viewport'][1]}")
            for c in m["cards"]:
                flag = "SCROLL" if (c["hiddenBy"] > 2 and c["scrollable"]) else \
                       ("CLIP" if c["hiddenBy"] > 2 else "ok")
                if flag == "CLIP":
                    rc = 1
                print(f"     [{flag:>6}] {c['title'][:34]:<34} client={c['clientH']:>4} "
                      f"scroll={c['scrollH']:>4} 超出={c['hiddenBy']:>4}px overflowY={c['overflowY']}")
            for bd in m["bad"]:
                rc = 1
                allbad.append((label, bd))
                print(f"     [!!BAD] {bd['kind']}  {bd.get('title', '')} {bd.get('el', '')} "
                      f"{bd.get('hiddenPx') or bd.get('overPx')}px  {bd['why']}")
            if key == "cockpit":
                t = m["times"]
                print(f"     时间口径: 底栏={t['clock']!r} 覆盖={t['cov']!r} "
                      f"零调用={t['orph']!r} 基因={t['gene']!r}")

        print("\n" + "=" * 78)
        if allbad:
            print(f"发现 {len(allbad)} 处真版面缺陷（内容拿不到 / 溢出 / 横向滚动）：")
            for lbl, bd in allbad:
                print(f"  · [{lbl}] {bd['kind']} {bd.get('title', '')} — {bd['why']}")
        else:
            print("无 CLIP / OVERFLOW / HSCROLL 真缺陷。（SCROLL 是可滚动，非缺陷。）")
        print("=" * 78)
        b.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
