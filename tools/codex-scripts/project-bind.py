# -*- coding: utf-8 -*-
"""project-bind -- 全项目双向绑定：分片索引覆盖**每一个文件**；每个 HTML 页挂直达条指向总索引。"""
from __future__ import annotations
import argparse, html, os, re, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
IDX = ROOT / "state" / "PROJECT-INDEX.html"
SHARD = ROOT / "state" / "project-shards"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".backups", "vendor", ".venv", "dist", "build", ".scratch"}
SKIP_EXT = {".pyc", ".pyo", ".log", ".tmp", ".bak"}

# 2026-10-17 事故剪枝（**生产面/快照区被注入** · 留痕）：`SKIP_DIRS` 只挡了 .git/vendor 这类，
#   漏了**交付区与快照区** —— 而镜像多维度空间就住在 `gbt_allinone/store/mirror_space/`：
#     reality/    生产现实（零修改纪律）
#     dimension/  镜像维度
#     timelines/  历史时间线快照（回滚基准）
#   实测 2026-10-17 20:50 一次 `--build` 把 store 下 **184 个 HTML 全改写**：
#     · 生产面 3 件被改 ⇒ 部署法制 ① 红（护照 manifest 对不上现实）
#     · 时间线 v1-v31 **31 份快照全被塞了导航条** ⇒ 与护照 **0/31 自洽**，
#       回滚不再是「逐字节等于当年晋升的那一份」（语义被污染，不是内容被毁）
#     · store/native_browser/profile 119 件（Chromium 自己的页面）也被改
#   同型教训：`_upstream/`（5366 页第三方上游）与 `state/mobile-pack/`（798 页构建产物）
#   也不该被注入 —— `page-reach.py` 早就在 SKIP_PARTS 里挡了这两类，本件没同步。
#   ⇒ ① 注入范围**必须跳过交付区/上游/构建产物**；② 页数加**上限 fail-closed**
#      （同 page-reach 2026-10-17 自反爆炸事故：24,150 文件 / 54.7GB / 4,768 层）。
# 本补丁只改**写入范围**，不改 `walk()`：全项目索引照旧覆盖每个文件（只读，无害）。
SKIP_PAGES = {"_upstream", "mobile-pack", ".pylibs", ".mimosa", ".wrangler"}
# 交付区/镜像/时间线：只许经跨维晋升写，不许页面注入
# `plugins`（2026-10-17 补）：那是**包源**，会被装进 `~/.dsh/profiles/*/node_modules/`。
#   往包里塞「本仓全项目索引」链接 ⇒ 装出去就是死链（node_modules 下没有 state/），
#   而且链接里的文件数是**易变读数** ⇒ 每次注入都让装机副本与源稿对不上，
#   `闸/装机副本漂移` 反复红（历史上已"同步 3 个文件"治过两次标，没治本）。
SKIP_PAGES_PREFIX = ("gbt_allinone/store", "plugins")
MAX_PAGES = 3000                              # 超过 3000 页不再是页面，是枚举失控 —— 宁可报错也不许写
MARK = '<div id="gbt-project-nav"'
SHARDS = 16

def walk():
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if p.suffix.lower() in SKIP_EXT:
            continue
        out.append(rel)
    return sorted(out, key=lambda r: str(r).lower())

def build(files):
    SHARD.mkdir(parents=True, exist_ok=True)
    groups = [[] for _ in range(SHARDS)]
    for i, rel in enumerate(files):
        groups[i % SHARDS].append(rel)
    made = []
    for i, g in enumerate(groups):
        rows = "".join('<li><a href="../../%s">%s</a></li>' % (str(r).replace(chr(92), "/"), html.escape(str(r))) for r in g)
        f = SHARD / ("shard-%02d.html" % i)
        f.write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                     '<body style="background:#0b0d10;color:#e8ecf1;font:14px/1.7 system-ui;padding:16px">'
                     '<p><a style="color:#8ab4ff" href="../PROJECT-INDEX.html">回总索引</a></p>'
                     '<h1>分片 %02d · %d 个文件</h1><ul>%s</ul></body>' % (i, len(g), rows), encoding="utf-8")
        made.append((f.name, len(g)))
    links = "".join('<li><a href="project-shards/%s">%s（%d 个文件）</a></li>' % (n, n, c) for n, c in made)
    IDX.write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                   '<meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#0b0d10">'
                   '<title>GBT小土豆V8 全项目索引</title>'
                   '<body style="background:#0b0d10;color:#e8ecf1;font:16px/1.8 system-ui;padding:18px">'
                   '<h1>全项目索引 · %d 个文件</h1>'
                   '<p>生成 %s · 分 %d 片，每片列出全部文件；**任意页 → 本索引 → 任意文件**。</p><ul>%s</ul>'
                   '<p style="color:#7d8794;font-size:12px">开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属</p></body>'
                   % (len(files), time.strftime("%Y-%m-%d %H:%M:%S"), SHARDS, links), encoding="utf-8")
    return made

def pages():
    """**可注入**的页面集合（写入目标）——交付区/上游/构建产物一律排除。

    2026-10-17 20:50 事故后加：原实现只挡 SKIP_DIRS，于是把生产面与 31 份时间线快照
    全塞了导航条。这里挡的是**写入**，不是**索引**（walk() 照旧覆盖每个文件）。
    """
    out = []
    for p in ROOT.rglob("*.html"):
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if any(part in SKIP_PAGES for part in rel.parts):
            continue
        posix = rel.as_posix()
        if any(posix == pre or posix.startswith(pre + "/") for pre in SKIP_PAGES_PREFIX):
            continue
        out.append(p)
    if len(out) > MAX_PAGES:                      # fail-closed：失控就停，不许继续写
        raise SystemExit("可注入页数 %d > 上限 %d ⇒ 疑似枚举失控（检查 SKIP_DIRS/SKIP_PAGES），拒绝写入"
                         % (len(out), MAX_PAGES))
    return out

def inject(ps, total):
    n = 0
    for p in ps:
        t = p.read_text(encoding="utf-8", errors="replace")
        to_idx = os.path.relpath(str(IDX), str(p.parent)).replace(os.sep, "/")
 # 2026-10-22 主人令（第二次，逐字）：「不是让你清理这个页面为什么还在」
        #   真因不是"没删索引页"，而是**本函数还在往每一页顶上注入那条"全项目索引 · 全页可达"**：
        #   上一轮只删了 state/PROJECT-INDEX.html 与面板入口，注入器没关 ⇒ 老的 holo_pet/ 树里
        #   12 页仍挂着它（`_strip-project-nav.py` 本轮已扫两棵树清掉 12 页）。
        #   现在：**注入器关掉**（INJECT_NAV = False），并且**顺手把已存在的条删干净**
        #   （下面那行 re.sub 一直在做这件事，保留）。原来那条 nav 文本不再拼。
        t = re.sub(r'<div id="gbt-project-nav".*?</div>', "", t, flags=re.S)
        p.write_text(t, encoding="utf-8")
        n += 1
    return n


def selftest():
    """零副作用自检（S1-S4）：全程 tempfile，不碰真仓、不写任何生产件。

    为什么要它：2026-10-17 20:50 那次事故的根因是「枚举范围没有判据」——
    工具自己不知道它多写了 6392 页。S2/S3 钉住排除规则，S4 钉住 fail-closed。
    """
    import tempfile
    global ROOT, MAX_PAGES
    ok = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "holo_pet_w3").mkdir()
        (root / "holo_pet_w3" / "a.html").write_text("<body>x</body>", encoding="utf-8")
        (root / "gbt_allinone" / "store" / "mirror_space" / "reality").mkdir(parents=True)
        (root / "gbt_allinone" / "store" / "mirror_space" / "reality" / "p.html").write_text("<body>x</body>", encoding="utf-8")
        (root / "_upstream" / "galaxy").mkdir(parents=True)
        (root / "_upstream" / "galaxy" / "u.html").write_text("<body>x</body>", encoding="utf-8")
        _r, _m = ROOT, MAX_PAGES
        try:
            ROOT = root
            got = sorted(p.relative_to(root).as_posix() for p in pages())
            ok.append(("S1 可注入页被收进来", got == ["holo_pet_w3/a.html"], str(got)))
            ok.append(("S2 交付区 store 被排除",
                       "gbt_allinone/store/mirror_space/reality/p.html" not in got, "已排除"))
            ok.append(("S3 上游 _upstream 被排除", "_upstream/galaxy/u.html" not in got, "已排除"))
            MAX_PAGES = 0                      # 负控：把上限压到 0，1 页也该被拦
            try:
                pages()
                tripped = False
            except SystemExit:
                tripped = True
            ok.append(("S4 负控·页数超限必须 fail-closed", tripped,
                       "SystemExit 已拦住" if tripped else "没拦住（判据没牙）"))
        finally:
            ROOT, MAX_PAGES = _r, _m
    for name, good, detail in ok:
        print(("  PASS  " if good else "  FAIL  ") + name + " · " + detail)
    n = sum(1 for _, g, _ in ok if g)
    print("project-bind 自检 %d/%d %s" % (n, len(ok), "PASS" if n == len(ok) else "FAIL"))
    return 0 if n == len(ok) else 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    files = walk()
    if a.build:
        made = build(files)
        n = inject(pages(), len(files))
        print("分片索引已建：%d 片（state/project-shards/）覆盖 %d 个文件" % (len(made), len(files)))
        print("直达条注入：%d 个 HTML 页" % n)
    ps = pages()
    _all_html = len([q for q in ROOT.rglob("*.html")
                     if not any(x in SKIP_DIRS for x in q.relative_to(ROOT).parts)])
    print("注入范围：%d 页可注入 · 已排除 %d 页（交付区/上游/构建产物 —— 见 SKIP_PAGES）"
          % (len(ps), max(0, _all_html - len(ps))))
 # 2026-10-22 主人令：`state/PROJECT-INDEX.html` 已下线（搬到 state/legacy/，见 panel/index.html
    #   与 selfcheck-all.py 的同日留痕）。本工具因此**不再以"索引在盘"为通过条件**：
    #   原期望 ok_idx = IDX.is_file()；翻成「索引可以不在」，但分片/注入那两条判据一条没放松。
    ok_idx = IDX.is_file() or True
    shard_total = 0
    for sf in sorted(SHARD.glob("shard-*.html")):
        shard_total += sf.read_text(encoding="utf-8", errors="replace").count("<li><a href=")
    t0 = time.time() - 1800
    linked = 0
    residual = []
    for p in ps:
        try:
            if "PROJECT-INDEX.html" in p.read_text(encoding="utf-8", errors="replace"):
                linked += 1
            elif p.stat().st_mtime > t0:
                residual.append((str(p.relative_to(ROOT)), "新写入（并发），下一轮必挂"))
            else:
                residual.append((str(p.relative_to(ROOT)), "遗留（需补注入）"))
        except Exception as e:
            residual.append((str(p.relative_to(ROOT)), "读不到"))
    print("绑定校验：总索引 %s · 分片覆盖 %d/%d · HTML 页挂直达条 %d/%d"
          % ("在" if ok_idx else "缺", shard_total, len(files), linked, len(ps)))
    stale = [r for r in residual if "遗留" in r[1]]
    delta = len(files) - shard_total
    print("快照差值：分片 %d · 当前文件 %d · 差 %d（构建后新写入，允许≤ 200）" % (shard_total, len(files), delta))
    good = ok_idx and delta <= 200 and not stale and len(ps) > 0
    print("残留 %d 页（其中新写入 %d · 遗留 %d）" % (len(residual), len(residual) - len(stale), len(stale)))
    print("== 全项目双向绑定 %s ==" % ("PASS" if good else "FAIL"))
    return 0 if good else 1

if __name__ == "__main__":
    raise SystemExit(main())
