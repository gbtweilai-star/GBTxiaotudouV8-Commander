# -*- coding: utf-8 -*-
"""能力独立页生成器（2026-09-23 起）。

## 为什么要有这一件

风哥令：「她的能力页面都要**独立页面**，别设计的挤在一起小气的样子」。
⇒ 一条能力 = **一个真文件**（`holo_pet_w3/brain/caps/<kind>.html`），不是一个塞满小卡的页面。

## 为什么是"一模板 + N 薄页"而不是 N 份各写一遍

161 份各自维护 = 改一次样式要改 161 处（本仓最贵的教训：同一件事两份口径必然分叉）。
⇒ 版式与渲染只有一份（`cap.css` / `cap.js`），生成的每一页**只带一个 id**：
    `<body class="cap-page" data-kind="sec_scan">`。要改样子改那一份，全部页面跟着变。

## 纪律

  · 生成的页**不许手改**（文件头写明"自动生成"与重建命令）；
  · 每页都是**自包含可达的**：只引本机文件，零外链（壳要能离线跑）；
  · 顺带出一张 `caps/index.html` 总目录（161 条一眼看全）。
  · 🔴 **页面固定**（主人令 2026-10-27「不能在出现跳转页面」）：跨"扇"的入口
    （`神经工作台` / `（束）` / `回神经工作台`）一律写成 `href="#" data-panel-goto="godview"`，
    由 `cap.js` 转成 `gbtW3.panelGoto`（让**面板**在内容区切页，主人令 2026-10-04
    「不许跳转，全部内镶嵌」）。以前写的是 `href="../../index.html"` —— 那是 **APP 根首页**，
    点下去等于把整个 APP 装进 panel 的 webview 内容区。
    同一束/兄弟能力页之间的 `href="<id>.html"` **保留**：那是内容区内部的正常浏览。

## 用法

    py -3.14 tools/codex-scripts/cap-pages.py
    py -3.14 tools/codex-scripts/cap-pages.py --check    # 只报差异，不写
"""
import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
BRAIN = ROOT / "holo_pet_w3" / "brain"
OUT = BRAIN / "caps"

HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/cap-pages.py
     版式与渲染只有一份（cap.css / cap.js）；本页只负责带一个 id。 -->
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'none'" />
<title>__KIND__ · 能力页 · GBT小土豆V8</title>
<link rel="stylesheet" href="../../window.css" />
<link rel="stylesheet" href="../../deck3d.css" />
<link rel="stylesheet" href="../../skin-mission-control.css" />
<link rel="stylesheet" href="../cap.css" />
<link rel="stylesheet" href="../../page-skins.css" />
</head>
<body class="cap-page" data-kind="__KIND__">

<div class="cap-top">
  <span class="crumb">
    <a href="#" data-panel-goto="godview">神经工作台</a> /
    <a id="crumb-bundle" href="#" data-panel-goto="godview">（束）</a> /
    <span class="here" id="crumb-here">__KIND__</span>
  </span>
  <span class="spacer"></span>
  <span class="mc-badge" id="cap-state">—</span>
</div>

<header class="cap-hero">
  <h1 class="cap-id" id="cap-id">__KIND__</h1>
  <p class="cap-desc" id="cap-desc">读数据中…</p>
  <div class="cap-tags">
    <span class="mc-badge">能力位 · CAPABILITY</span>
    <span class="mc-badge">以源码为准</span>
    <span class="mc-badge">快照 <span id="cap-at">—</span></span>
  </div>
</header>

<main class="cap-body">

  <section class="cap-sec">
    <h2>遥测<span class="n">6 项 · 真数</span></h2>
    <div class="tiles">
      <div class="mc-tile"><div class="mc-tile-label">已实现</div><div class="mc-tile-value" id="t-implemented">—</div></div>
      <div class="mc-tile"><div class="mc-tile-label">免卡直跑</div><div class="mc-tile-value" id="t-safe">—</div></div>
      <div class="mc-tile"><div class="mc-tile-label">所属束</div><div class="mc-tile-value" id="t-bundle">—</div></div>
      <div class="mc-tile"><div class="mc-tile-label">出边</div><div class="mc-tile-value" id="t-out">—</div></div>
      <div class="mc-tile"><div class="mc-tile-label">入边</div><div class="mc-tile-value" id="t-in">—</div></div>
      <div class="mc-tile"><div class="mc-tile-label">调用</div><div class="mc-tile-value" id="t-calls">—</div></div>
    </div>
  </section>

  <section class="cap-sec">
    <h2>出处 · 这条能力位落在哪<span class="n">可回查</span></h2>
    <div id="src-files"></div>
    <div class="kv"><span class="k">注册表</span><span class="v" id="src-registry">—</span></div>
    <div class="kv"><span class="k">连接口径</span><span class="v" id="src-dispatch">—</span></div>
  </section>

  <section class="cap-sec">
    <h2>连接 · 它用谁（出边）<span class="n" id="out-n">—</span></h2>
    <div id="out-list"></div>
  </section>

  <section class="cap-sec">
    <h2>连接 · 谁用它（入边）<span class="n" id="in-n">—</span></h2>
    <div id="in-list"></div>
  </section>

  <div class="cols2">
    <section class="cap-sec">
      <h2>调用史 · 真审计事件<span class="n" id="hist-n">—</span></h2>
      <div id="hist-list"></div>
    </section>
    <section class="cap-sec">
      <h2>同束的其他能力<span class="n" id="sib-n">—</span></h2>
      <div class="nav-grid" id="sib-list"></div>
    </section>
  </div>

  <section class="cap-sec">
    <h2>全部能力页<span class="n" id="all-n">—</span></h2>
    <p class="hintline">
      161 条能力各自一页。这里不把它们铺开 —— 铺开就成了"挤在一起"，
      正是风哥要避免的样子；要看全量去总目录（那里按束分组）。
    </p>
    <div class="nav-grid">
      <a href="index.html">打开总目录 · 按束分组</a>
      <a href="#" data-panel-goto="godview">回神经工作台（3D 全脑）</a>
    </div>
  </section>

</main>

<footer class="foot">
  开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属<br />
  数据 <code>brain-data.js</code>（brain-feed.py 从真实源码算出）· 皮肤 mission-control
</footer>

<script src="../brain-data.js"></script>
<script src="../cap.js"></script>
</body>
</html>
"""

INDEX = """<!DOCTYPE html>
<html lang="zh-CN" data-page-id="cap-index">
<head>
<meta charset="utf-8" />
<!-- 自动生成。重建：py -3.14 tools/codex-scripts/cap-pages.py -->
<title>全部能力页 · GBT小土豆V8</title>
<link rel="stylesheet" href="../../window.css" />
<link rel="stylesheet" href="../../deck3d.css" />
<link rel="stylesheet" href="../../skin-mission-control.css" />
<link rel="stylesheet" href="../cap.css" />
<link rel="stylesheet" href="../../page-skins.css" />
</head>
<body class="cap-page">
<div class="cap-top">
  <span class="crumb"><a href="#" data-panel-goto="godview">神经工作台</a> / <span class="here">全部能力页</span></span>
  <span class="spacer"></span>
  <span class="mc-badge" id="ix-at">—</span>
</div>
<header class="cap-hero">
  <h1 class="cap-id">全部能力页</h1>
  <p class="cap-desc">每一条能力位各自一页（不是挤在一张卡里）。点任一进入它的独立页。</p>
</header>
<main class="cap-body">
  <section class="cap-sec"><h2>按束分组<span class="n" id="ix-n">—</span></h2><div id="ix-groups"></div></section>
</main>
<footer class="foot">开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属</footer>
<script src="../brain-data.js"></script>
<script>
(function () {
  "use strict";
  var D = globalThis.GBT_BRAIN;
  if (!D) return;
  document.getElementById("ix-at").textContent = D.at;
  var nodes = D.nodes || [], bundles = D.bundles || [];
  document.getElementById("ix-n").textContent = nodes.length + " 页";
  var host = document.getElementById("ix-groups");
  function link(n) {
    return '<a href="' + encodeURIComponent(n.id) + '.html">' + n.id + "</a>";
  }
  host.innerHTML = bundles.map(function (b) {
    var list = nodes.filter(function (n) { return n.impl && n.bundle === b.id; });
    if (!list.length) return "";
    return '<div class="kv"><span class="k">' + b.label + "（" + b.id + "）</span>" +
           '<span class="v"><span class="nav-grid">' + list.map(link).join("") + "</span></span></div>";
  }).join("") +
  '<div class="kv"><span class="k">仅登记未实现</span><span class="v"><span class="nav-grid">' +
  nodes.filter(function (n) { return !n.impl; }).map(link).join("") + "</span></span></div>";
})();
</script>
</body>
</html>
"""


def _data() -> dict:
    p = BRAIN / "brain-data.js"
    if not p.is_file():
        return {}
    t = p.read_text(encoding="utf-8")
    i = t.find("=")
    return json.loads(t[i + 1:].rstrip().rstrip(";")) if i > 0 else {}


def main() -> int:
    ap = argparse.ArgumentParser(description="生成每一条能力位的独立页")
    ap.add_argument("--check", action="store_true", help="只报差异，不写盘")
    a = ap.parse_args()

    d = _data()
    nodes = d.get("nodes") or []
    if not nodes:
        print("读不到 brain-data.js 里的 nodes —— 先跑 brain-feed.py")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    wrote, skipped = 0, 0
    want = set()
    for n in nodes:
        kind = str(n.get("id") or "").strip()
        if not kind:
            continue
        want.add(kind + ".html")
        f = OUT / (kind + ".html")
        html = HEAD.replace("__KIND__", kind)
        if f.is_file() and f.read_text(encoding="utf-8") == html:
            skipped += 1
            continue
        if not a.check:
            f.write_text(html, encoding="utf-8")
        wrote += 1
    ix = OUT / "index.html"
    ix_stale = not (ix.is_file() and ix.read_text(encoding="utf-8") == INDEX)
    if ix_stale and not a.check:
        ix.write_text(INDEX, encoding="utf-8")
    # 孤儿页：盘上有这个文件、能力数据里已经没有它 —— 删掉一条能力却留着它的页 = 旧页面。
    # 原来不查这一项，所以"数据减了、页面不减"永远不会被发现。
    orphans = sorted(p.name for p in OUT.glob("*.html")
                     if p.name not in want and p.name != "index.html")

    print("=" * 74)
    print("能力独立页生成 · 一条能力 = 一个真文件")
    print("=" * 74)
    print("  能力位 %d 条 ⇒ %s" % (len(nodes), OUT))
    print("  %s %d 页 · 内容未变 %d 页 · 目录页 %s"
          % ("将写" if a.check else "已写", wrote, skipped,
             "待更新" if ix_stale else "未变"))
    if orphans:
        print("  🔴 孤儿页 %d 个（能力数据里已经没有）：%s"
              % (len(orphans), ", ".join(orphans[:8])))
        if len(orphans) > 8:
            print("       … 另 %d 个" % (len(orphans) - 8))
    print("  总目录：caps/index.html")
    print("  重建：py -3.14 tools/codex-scripts/cap-pages.py")
    if a.check:
        # 🔴 原来这里无条件 return 0 —— 挂进闸就是假绿（有差异也报成功）。
        bad = wrote + (1 if ix_stale else 0) + len(orphans)
        if bad:
            print("  🔴 FAIL —— %d 处与能力数据不一致（要修就跑不带 --check）" % bad)
            print("→ 本次退出码 = 1")
            return 1
        print("  ✅ PASS —— %d 个能力页与数据逐条一致，无孤儿页" % skipped)
        print("→ 本次退出码 = 0")
        return 0
    print("→ 本次退出码 = 0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
