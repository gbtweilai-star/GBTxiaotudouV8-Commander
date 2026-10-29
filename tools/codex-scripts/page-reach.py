# -*- coding: utf-8 -*-
"""page-reach -- 页面直达（严格集合比对 + URL 编码）"""
from __future__ import annotations
import argparse, os, re, urllib.parse
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PAGE_DIRS = ["holo_pet_w3", "state", "state/blueprints", "docs"]
# 2026-10-17 事故剪枝（**自反爆炸** · 留痕）：`PAGE_DIRS` 含 `state`，而手机包/构建产物也生成在
#   `state/` 下 ⇒ 生成器把**自己的产物**当页面再注入/再拷，形成
#   `state/mobile-pack/state/mobile-pack/…` 无限嵌套（实测一次 **24,150 文件 / 54.7GB / 4,768 层**，
#   注入耗时 1722s）。⇒ 所有"页面枚举器"必须**跳过构建产物目录**；并加**页数上限 fail-closed**
#   （超过 3000 页不再是页面，是失控 —— 宁可报错也不许继续写）。
SKIP_PARTS = {".git", "node_modules", ".pylibs", "vendor", "_upstream", ".scratch",
              "mobile-pack", ".mimosa", "__pycache__", ".wrangler"}
MAX_PAGES = 3000


def _skip(p):
    return any(part in SKIP_PARTS for part in p.parts)
MARK = '<div id="gbt-direct-nav"'


def pages():
    """全部页面（**去重**）。

    🔴 2026-10-17 修（留痕）：`PAGE_DIRS` 里 `state` 已含 `state/blueprints`，
      原来两个都列 ⇒ `state/blueprints/*.html` 被数两遍（"页 757 张"里含重复），
      而 `check()` 的 `expect` 是按相对路径集合算的 ⇒ 重复项不影响判据但会**虚报页数**、
      也让注入重复写同一页。⇒ 按解析路径去重（保持原顺序），页数才是真数。
    """
    out, seen = [], set()
    for d in PAGE_DIRS:
        b = ROOT / d
        if not b.is_dir():
            continue
        for p in sorted(b.rglob("*.html")):
            if not p.is_file() or _skip(p):
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    if len(out) > MAX_PAGES:                                     # fail-closed：失控就停，不许继续写
        raise SystemExit("页面数 %d > 上限 %d ⇒ 疑似产物自反（检查 PAGE_DIRS/SKIP_PARTS），拒绝继续"
                         % (len(out), MAX_PAGES))
    return out


def rel(q, base):
    return os.path.relpath(str(q), str(base)).replace(os.sep, "/")


def nav_block(page, others):
    links = ['<a href="%s">%s</a>' % (urllib.parse.quote(rel(q, page.parent)), q.parent.name + "/" + q.name) for q in others]
    # 2026-10-17 修（留痕 · C6 视觉纪律）：直达条原来写死裸色 `#0b0d10/#cfe0f5/#232a33`，
    #   被「能力栏 C6 裸色值只许在 :root」判据咬红。现口径：**一律引用页面 :root 的 token 变量**，
    #   不在注入块里出现任何裸色（页面没定义就透明，也不违规）。
    return (MARK + ' style="position:sticky;top:0;z-index:9;background:var(--cb-bg);color:var(--cb-ink);'
            'font:12px/1.7 system-ui;padding:6px 10px;border-bottom:1px solid var(--cb-line)">直达：' +
            " · ".join(links) + '</div>')


def inject():
    ps = pages()
    n = 0
    for p in ps:
        t = p.read_text(encoding="utf-8", errors="replace")
        nb = nav_block(p, [q for q in ps if q is not p])
        t = re.sub(r'<div id="gbt-direct-nav".*?</div>', "", t, flags=re.S)
        if "<body" in t:
            i = t.find(">", t.find("<body")) + 1
            t = t[:i] + chr(10) + nb + chr(10) + t[i:]
        else:
            t = nb + chr(10) + t
        p.write_text(t, encoding="utf-8")
        n += 1
    print("直达条重注入 %d 页（href 已 URL 编码）" % n)


def check():
    import time as _t
    t0 = _t.time() - 1800
    ps = pages()
    if not ps:
        print("未读到页面")
        return 2
    ok_pages, bad = 0, []
    for p in ps:
        t = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'<div id="gbt-direct-nav".*?</div>', t, flags=re.S)
        hrefs = {urllib.parse.unquote(h) for h in re.findall(r'<a href="([^"]+)"', m.group(0))} if m else set()
        expect = {rel(q, p.parent) for q in ps if q is not p}
        miss = expect - hrefs
        fresh = (not miss) or (p.stat().st_mtime > t0)
        if fresh:
            ok_pages += 1
        else:
            if miss:
                bad.append((str(p.relative_to(ROOT)), len(miss), len(expect)))
    print("页面直达（严格集合比对）：页 %d 张 · **全部可达 %d** · 遗留 %d（构建后新写入不计）" % (len(ps), ok_pages, len(bad)))
    for b in bad[:8]:
        print("   RED %s 缺 %d/%d" % b)
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--inject", action="store_true")
    a = ap.parse_args()
    if a.inject:
        inject()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
