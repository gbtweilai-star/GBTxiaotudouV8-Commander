# -*- coding: utf-8 -*-
"""交付物 · 审美体检（静态 + 运行期 · 只读）。

上几轮分散查过单点（令牌漂移、emoji）。本工具把体检做全，**静态 + 运行期两块**：

  静态（读文件）：
    · 七宗罪 #1 默认靛蓝（规则书列的完整 7 值）
    · 七宗罪 #2 双色「信任感」渐变
    · 七宗罪 #3 emoji 当界面图标（**宽式**判据，白名单只有 `→` 并写明理由）
    · 形状一致性：圆角取值是否落在声明的档位里

  运行期（真渲染，Playwright）：
    · **对比度**：正文/按钮/次要文字 对 其实际背景，按 WCAG AA（正文 4.5:1 · 大字 3:1）
    · 横向溢出
    —— 对比度**必须实渲染才能算**，静态读 CSS 猜不出层叠后的真实背景。

用法：py -3.14 tools/codex-scripts/audit_deliverable_craft.py [文件名…]
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "codex-scripts" / fname)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TC = _load("tc2", "audit_token_context.py")

# 宽式 emoji 判据（与生成器侧同口径）。窄式会漏 ←→↔⇒①②③◇⌘。
try:
    import regex as _regex
    EMOJI = _regex.compile(r"[\p{Extended_Pictographic}\p{Emoji_Presentation}"
                           r"\u2190-\u21FF\u2300-\u23FF\u2460-\u24FF"
                           r"\u25A0-\u25FF\u2B00-\u2BFF]")
except ImportError:
    EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF"
                       "\u2300-\u23FF\u2460-\u24FF\u25A0-\u25FF\u2B00-\u2BFF\uFE0F]")

# 唯一白名单：`→` 是**序列记号的排版分隔符**，不承担图标职能（理由同生成器侧）。
EMOJI_WHITELIST = {"\u2192"}

INDIGO = ["#6366f1", "#4f46e5", "#4338ca", "#3730a3", "#8b5cf6", "#7c3aed", "#a855f7"]

# 运行期对比度探针：取可见文本元素，回溯到第一个不透明背景，算 WCAG 比值
CONTRAST_JS = r"""
(() => {
  const lum = (r,g,b) => { const f = v => { v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); };
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); };
  const parse = s => { const m = String(s).match(/rgba?\(([^)]+)\)/); if(!m) return null;
    const p = m[1].split(',').map(x=>parseFloat(x)); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}; };
  const bgOf = el => { let n = el;
    while (n && n !== document.documentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.5) return c;
      n = n.parentElement; }
    return {r:0,g:0,b:0,a:1}; };
  const ratio = (c1,c2) => { const a = lum(c1.r,c1.g,c1.b), b = lum(c2.r,c2.g,c2.b);
    const hi = Math.max(a,b), lo = Math.min(a,b); return (hi+0.05)/(lo+0.05); };
  const out = [];
  document.querySelectorAll('body *').forEach(el => {
    const txt = (el.innerText||'').trim();
    if (!txt || el.children.length) return;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.15) return;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    const fg = parse(cs.color); if (!fg || fg.a < 0.3) return;
    const bg = bgOf(el);
    const cr = ratio(fg, bg);
    const px = parseFloat(cs.fontSize) || 14;
    const bold = (parseInt(cs.fontWeight,10) || 400) >= 700;
    const large = px >= 24 || (bold && px >= 18.66);
    const need = large ? 3 : 4.5;
    if (cr < need) out.push({ text: txt.slice(0,40), ratio: Math.round(cr*100)/100,
      need, px, color: cs.color, bg: `rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})`,
      cls: (el.className||'').toString().slice(0,40) });
  });
  return { low: out.slice(0, 40), total: out.length,
           vw: document.documentElement.clientWidth, docW: document.documentElement.scrollWidth };
})()
"""


def static_checks(text: str) -> list[tuple[str, bool, str]]:
    out = []
    hit = [v for v in INDIGO if v in text.lower()]
    out.append(("七宗罪#1 无默认靛蓝", not hit, f"命中 {hit}" if hit else "0/7"))
    g = re.findall(r"linear-gradient\([^)]*(?:purple|indigo|#8b5cf6|#6366f1|#7c3aed)[^)]*\)", text, re.I)
    out.append(("七宗罪#2 无双色信任渐变", not g, f"命中 {len(g)} 条" if g else "0"))
    em = sorted({m.group() for m in EMOJI.finditer(text)} - EMOJI_WHITELIST)
    out.append(("七宗罪#3 无 emoji 当图标（宽式·扣白名单）", not em,
                f"命中 {em}" if em else "0（白名单 → ×%d）" % len(re.findall("\u2192", text))))
    radii = re.findall(r"border-radius:\s*([^;{}]+);", text)
    tokv = {r.strip() for r in radii if r.strip().startswith("var(")}
    decl = {r.strip() for r in radii if r.strip() in ("0", "50%", "999px", "9999px", "inherit")}
    bare = [r.strip() for r in radii if r.strip() not in tokv | decl]
    tok_defs = re.findall(r"--r(?:adius)?-[\w-]*\s*:\s*([^;]+);", text)
    # 判据不是"有没有裸值"（圆角天生就有多种），而是**令牌体系有没有被真用**：
    # 定义了令牌却大量走裸值 = 体系形同虚设。这一条比"发现裸值"有信息量。
    used = len(radii) - len(bare)
    cov = (used / len(radii) * 100) if radii else 100.0
    from collections import Counter
    top = Counter(bare).most_common(6)
    ok = len(tok_defs) == 0 or cov >= 60
    out.append(("形状一致性（圆角令牌覆盖率 ≥60%）", ok,
                f"覆盖率 {cov:.0f}%（{used}/{len(radii)}）· 声明 {len(tok_defs)} 个令牌"
                f" · 裸值 {len(set(bare))} 种 高频 {top}"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*",
                    default=["V22 GBT小土豆V8-无限画布.html", "V22 GBT小土豆V8-可交互原型.html"])
    a = ap.parse_args()
    rc = 0
    print("=" * 92)
    print("交付物 · 审美体检（静态 + 运行期）")
    print("=" * 92)

    from playwright.sync_api import sync_playwright
    CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, headless=True)
        for name in a.files:
            p = ROOT / name
            if not p.is_file():
                print(f"\n[跳过] 不存在：{name}")
                rc = 2
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            print(f"\n{'─'*92}\n  {name}   ({p.stat().st_size:,} B)\n{'─'*92}")
            print("  静态：")
            for label, ok, note in static_checks(text):
                print(f"    {'✔' if ok else 'x'} {label:42} {note}")
                if not ok:
                    rc = max(rc, 1)

            # 令牌漂移（复用语境判据）
            b2 = TC.classify(text)
            d = set()
            for z in TC.DRIFT:
                d |= set(b2.get(z, {}))
            print(f"    {'✔' if not d else 'x'} {'令牌漂移 去重 ≤ 12':42} "
                  f"{'0（清零）' if not d else str(len(d)) + ' ' + str(sorted(d))}")
            if d:
                rc = max(rc, 1)

            print("  运行期（真渲染）：")
            pg = b.new_page(viewport={"width": 1440, "height": 900})
            pg.goto(p.as_uri(), wait_until="load")
            pg.wait_for_timeout(1600)
            r = pg.evaluate(CONTRAST_JS)
            print(f"    {'✔' if r['docW'] - r['vw'] <= 2 else 'x'} "
                  f"{'无横向滚动':42} 视口 {r['vw']} · 文档 {r['docW']}")
            if r["docW"] - r["vw"] > 2:
                rc = max(rc, 1)
            if r["total"] == 0:
                print(f"    ✔ {'对比度 全部达 WCAG AA':42} 0 处不达标（{r['total']} 处）")
            else:
                print(f"    x {'对比度 达 WCAG AA':42} **{r['total']} 处不达标**")
                for x in r["low"][:10]:
                    print(f"        {x['ratio']}:1 (需 {x['need']}) {x['px']}px "
                          f"{x['color']} on {x['bg']}  «{x['text']}»")
                rc = max(rc, 1)
            pg.close()
        b.close()
    print(f"\n{'='*92}")
    print("说明：对比度**必须实渲染才算**（层叠后的真实背景静态读不出来）；")
    print("      emoji 用宽式判据，白名单只有 `→`（序列分隔符，不承担图标职能）。")
    print(f"{'='*92}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
