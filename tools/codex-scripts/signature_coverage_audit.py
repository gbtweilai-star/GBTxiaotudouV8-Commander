"""署名守卫**覆盖面**审计（只读）—— 「署名不可删除」这条红线到底管住了哪些树。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要这个
`gbt_allinone/signature.py::_scan_pages()` 只扫三处：
  ① `gbt_allinone/**/*.md`（排除 store/pycache/…）
  ② 家根 `*.md`（**且只签 inventory 判为 framework 的**）
  ③ `gbt_allinone/store/pipeline/production/**` 的文本产物
⇒ 家根下其它树（`outputs/` `holo_pet/` `docs/` `memory/` `plugins/` `tools/` …）**根本不在扫描面里**。
⇒ 那些树里的页面**带了署名也无人验、丢了署名也无人报** —— 红线在这些树上**没有技术强制**。

本脚本把这件事**量出来**：每棵树的页面数 / 带署名数 / 缺署名数 + 缺口样例。
**只读**：不注入、不修改、不落盘（除 stdout）。

用法：python tools/codex-scripts/signature_coverage_audit.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.soul import SIGNATURE as SIG_MARK        # 单一真源，不硬编码
except Exception:                                              # 进不去就退回字面量并**标注**
    SIG_MARK = "开发者：自由的风"

PAGE_SUFFIX = {".md", ".html", ".htm"}       # **页面**：要带署名的
TEXT_SUFFIX = {".txt", ".csv"}               # **文本产物**：另一类，单独数，不当违规

# 家根下值得查的树（守卫的 _scan_pages 只覆盖其中很少一部分）
TREES = ["outputs", "holo_pet", "docs", "memory", "plugins", "tools", "state",
         "scripts", "config", "gbt_allinone"]

# 🔴 守卫**声明覆盖**的树（与 _scan_pages 逐条对应，改动这里必须同时改那里）
GUARD_COVERS = {
    "gbt_allinone": "仅 **.md**（且排除 store/__pycache__/.pylibs/archived_logs）",
    ".": "仅家根顶层 **.md**，且只签 inventory 判为 framework 的",
    "gbt_allinone/store/pipeline/production": "文本/网页产物（.txt/.md/.html/.htm/.csv）",
}


def _is_data(p: Path) -> bool:
    """数据/草稿区 —— **不是页面**，不计违规。

    🔴 第一版把 `.out.txt` 草稿和 `store/` 数据都算成页面，一次报了 **874 "缺署名"**
    （`tools/` 76 条全是 `_*.out.txt`、`gbt_allinone` 769 条全在 `store/`）——
    **判据太宽 = 坏判据**。这里对齐守卫自己的口径：
      - 路径含 `store` 的不算（**但 `store/pipeline/production` 例外**，那是守卫明说自己扫的）；
      - `__pycache__` / `.pylibs` / `node_modules` / `.git` 不算；
      - 文件名以 `_` 开头的算草稿，不算。
    """
    parts = p.parts
    for t in ("__pycache__", ".pylibs", "node_modules", ".git"):
        if t in parts:
            return True
    if "store" in parts and "production" not in parts:
        return True
    return p.name.startswith("_")


def tree_stats(rel: str) -> dict:
    d = ROOT / rel
    if not d.is_dir():
        return {"树": rel, "在": False}
    total, signed, unsigned, ex, texts = 0, 0, 0, [], 0
    for p in sorted(d.rglob("*")):
        if not p.is_file() or _is_data(p):
            continue
        if p.suffix.lower() in TEXT_SUFFIX:
            texts += 1
            continue
        if p.suffix.lower() not in PAGE_SUFFIX:
            continue
        total += 1
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if SIG_MARK in t:
            signed += 1
        else:
            unsigned += 1
            if len(ex) < 4:
                ex.append(str(p.relative_to(ROOT)))
    return {"树": rel, "在": True, "页面数": total, "带署名": signed,
            "缺署名": unsigned, "缺署名样例": ex, "文本产物": texts,
            "守卫扫吗": rel in GUARD_COVERS}


# 🔴 **可盖章的树**（交付物）—— `--stamp` 只认这两棵，别的一律拒（fail-closed）
STAMPABLE = ("outputs", "holo_pet")

# 🔴 **明确排除**（带理由）—— 盖章会**弄坏它自己的用途**，所以不盖也不判违规
EXCLUDE = {
    "tools/codex-scripts/fixtures/aesthetic-sins.html":
        "**测试夹具**：故意做坏的页面，盖章会让它不再是「坏页」，弄坏对应的测试",
}


def _excluded(p: Path) -> bool:
    return str(p.relative_to(ROOT)).replace("\\", "/") in {
        k.replace("\\", "/") for k in EXCLUDE}


def do_stamp(trees) -> dict:
    """用**守卫自己的 `inject()`** 补署名（不自己造页脚格式）。

    🔴 只允许 `STAMPABLE` 里的树；写前写后各记 sha 与字节，**逐条可复核**。
    """
    bad = [t for t in trees if t not in STAMPABLE]
    if bad:
        return {"ok": False, "拒绝": "这些树不在可盖章清单里：%s（可盖章的只有 %s）"
                % (bad, list(STAMPABLE))}
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import signature as _sg
    except Exception as e:
        return {"ok": False, "拒绝": "取不到守卫的 inject()：%s" % e}

    import hashlib
    changed, skipped = [], []
    for rel in trees:
        for p in sorted((ROOT / rel).rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() not in PAGE_SUFFIX or _is_data(p) or _excluded(p):
                if _excluded(p) and p.suffix.lower() in PAGE_SUFFIX:
                    skipped.append({"件": str(p.relative_to(ROOT)),
                                    "为什么没盖": EXCLUDE[str(p.relative_to(ROOT))]})
                continue
            old = p.read_text(encoding="utf-8", errors="replace")
            if SIG_MARK in old:
                continue
            new = _sg.inject(old, p)                     # ← 用守卫自己的实现
            if new == old:
                skipped.append({"件": str(p.relative_to(ROOT)), "为什么没盖": "inject 没改动"})
                continue
            # 🔴 **必须写字节，不能 write_text**：`Path.write_text` 在 Windows 上把 `\n`
            #    翻成 `\r\n` ⇒ 声称"只加了一行署名"，实际**改了整个文件的换行**
            #    （实测踩过：holo_pet/index.html 凭空 +590 字节 = 全文 590 个换行）。
            #    写字节可保证**除署名外逐字节不变**。
            before = p.read_bytes()
            p.write_bytes(new.encode("utf-8"))
            after = p.read_bytes()
            # 硬闸：新增字节必须**正好等于**署名文本的字节数（多一个字节都算改多了）
            add = len(after) - len(before)
            want = len(new.encode("utf-8")) - len(old.encode("utf-8"))
            changed.append({
                "件": str(p.relative_to(ROOT)),
                "旧sha": hashlib.sha256(old.encode("utf-8")).hexdigest()[:12],
                "新sha": hashlib.sha256(new.encode("utf-8")).hexdigest()[:12],
                "字节": "%d → %d（+%d，署名本身 %d）" % (len(before), len(after), add, want),
                "只多了署名": add == want,
                "注入位置": "`</body>` 之前" if p.suffix.lower() in (".html", ".htm") else "末尾",
            })
    return {"ok": True, "可盖章树": list(trees), "补了 %d 页" % len(changed): changed,
            "跳过": skipped}


def gate(trees) -> dict:
    """闸：可盖章树里**任何一个页面缺署名**即不过（rc=1）。

    🔴 2026-09-25 根因修法：`--trees` 默认只有 `STAMPABLE`（`outputs`/`holo_pet`），
    而体检正是用默认值跑 `--gate` ⇒ **`docs/` 从来没被看过** ⇒
    `docs/体检报告.md`、`docs/待授权清单一页.md` 两份**自动生成的页**长期无署名而不报警。
    ⇒ **闸一律把 `docs/` 并进来**（盖章仍只允许 STAMPABLE —— 那是写盘权限，不是扫描面）。
    """
    trees = list(dict.fromkeys(list(trees) + ["docs"]))
    rows = [tree_stats(t) for t in trees]
    loose, judged = [], 0
    for r in rows:
        if not r.get("在"):
            continue
        d = ROOT / r["树"]
        for p in sorted(d.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in PAGE_SUFFIX:
                continue
            if _is_data(p) or _excluded(p):
                continue
            # 🔴 与判据**同宽**：只数真被判过的页。
            #    第一版这里用的是 `tree_stats` 的「页面数」求和，而 `tree_stats`
            #    **不过滤 `_excluded()`** ⇒ 读数比判据宽：排除表里的夹具会被**算进页数
            #    却从未被读**（读物比判据宽 = 下一页的坏判据）。
            judged += 1
            try:
                if SIG_MARK not in p.read_text(encoding="utf-8", errors="replace"):
                    loose.append(str(p.relative_to(ROOT)))
            except Exception:
                pass
    return {"闸": "署名覆盖面（%s）" % "、".join(trees), "页面": judged,
            "缺署名": loose, "过": not loose}


def selftest() -> int:
    """判别性自检：**判据必须能分开"页面/数据/夹具"**，否则闸是假的。"""
    from pathlib import Path as _P
    checks = []

    def ck(name, cond, detail):
        checks.append(("%s %s — %s" % ("✓" if cond else "✗", name, detail), bool(cond)))

    ck("草稿（`_` 开头）不算页面", _is_data(_P("state/_c1.txt")) is True, "state/_c1.txt")
    ck("`store/` 数据不算页面", _is_data(_P("gbt_allinone/store/a/b.html")) is True,
       "gbt_allinone/store/a/b.html")
    ck("**但 store/pipeline/production 例外**（守卫明说扫它）",
       _is_data(_P("gbt_allinone/store/pipeline/production/x.html")) is False,
       "store/pipeline/production/x.html")
    ck("__pycache__ 不算页面", _is_data(_P("tools/__pycache__/x.html")) is True, "")
    ck("**测试夹具被排除**（盖章会弄坏它自己的用途）",
       _excluded(ROOT / "tools/codex-scripts/fixtures/aesthetic-sins.html") is True,
       "aesthetic-sins.html")
    ck("普通交付物**不在排除表里**",
       _excluded(ROOT / "holo_pet/index.html") is False, "holo_pet/index.html")
    g = gate(STAMPABLE)
    ck("真树现读：可盖章树全页带署名", g["过"] is True,
       "%d 页 · 缺 %d" % (g["页面"], len(g["缺署名"])))
    # 🔴 **覆盖面控制**（2026-09-25 §一百五十一 那一类：闸**悄悄跳过一整棵树**）
    #    口径：闸报的页数 == 独立走一遍同一批树、用同一套过滤数出来的页数。
    #    两者不同宽 ⇒ 要么闸漏树、要么读数比判据宽，两种都必须红。
    _trees = tuple(dict.fromkeys(list(TREES) + ["docs"]))
    _exp = 0
    for _t in _trees:
        _d = ROOT / _t
        if not _d.is_dir():
            continue
        for _p in _d.rglob("*"):
            if (_p.is_file() and _p.suffix.lower() in PAGE_SUFFIX
                    and not _is_data(_p) and not _excluded(_p)):
                _exp += 1
    _g_all = gate(TREES)
    ck("**闸的页数与独立走树同宽**（漏树/读数偏宽都红）", _g_all["页面"] == _exp,
       "闸 %d ｜ 独立数 %d" % (_g_all["页面"], _exp))
    # 🔴 负控：只给它一棵子树 ⇒ 页数必须**严格更少且非空**。
    #    闸若**忽略入参、偷偷扫全树**，这里就会相等 ⇒ 负控咬住。
    _g_one = gate(("docs",))
    ck("**负控：收窄到单棵树 ⇒ 页数必须变少且非零**",
       _g_one["页面"] > 0 and _g_one["页面"] < _exp,
       "docs %d ｜ 全 %d" % (_g_one["页面"], _exp))
    # 🔴 负控：造一个**真缺署名**的临时页，判据必须报出来
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        f = _P(td) / "page.html"
        f.write_text("<html><body>x</body></html>", encoding="utf-8")
        loose = SIG_MARK not in f.read_text(encoding="utf-8")
        ck("**负控：造一个缺署名的页 ⇒ 必须判为缺**", loose, str(f.name))

        # 🔴 负控：`write_text` 会**偷偷把 \n 翻成 \r\n**（实测踩过：index.html 凭空 +590 字节）
        raw = "<html><body>\nx\ny\n</body></html>\n"
        g = _P(td) / "eol.html"
        g.write_bytes(raw.encode("utf-8"))
        b0 = g.read_bytes()
        g.write_text(raw, encoding="utf-8")                 # 默认 newline=None ⇒ 会翻
        b1 = g.read_bytes()
        g.write_bytes(raw.encode("utf-8"))                  # 本工具用的写法
        b2 = g.read_bytes()
        ck("**write_text 偷偷翻换行、write_bytes 逐字节不变**（这个坑的负控）",
           b1.count(b"\r\n") > 0 and b2.count(b"\r\n") == 0 and b0 == b2,
           "write_text 后 CRLF=%d ｜ write_bytes 后 CRLF=%d ｜ 复原一致=%s"
           % (b1.count(b"\r\n"), b2.count(b"\r\n"), b0 == b2))

    bad = sum(0 if ok else 1 for _, ok in checks)
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": [c for c, _ in checks]}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stamp", action="store_true", help="给可盖章树补署名（用守卫自己的 inject）")
    ap.add_argument("--gate", action="store_true", help="缺署名即 rc=1")
    ap.add_argument("--selftest", action="store_true", help="判别性自检")
    ap.add_argument("--trees", default=",".join(STAMPABLE))
    a = ap.parse_args()
    trees = tuple(t.strip() for t in a.trees.split(",") if t.strip())

    if a.selftest:
        return selftest()
    if a.stamp:
        r = do_stamp(trees)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 2
    if a.gate:
        g = gate(trees)
        print(json.dumps(g, ensure_ascii=False, indent=1))
        print(("✅ 盖章树全页带署名（%d 页）" % g["页面"]) if g["过"]
              else "🔴 **有页面缺署名**：%s" % g["缺署名"])
        return 0 if g["过"] else 1

    rows = [tree_stats(t) for t in TREES]
    live = [r for r in rows if r.get("在")]
    tot = sum(r["页面数"] for r in live)
    uns = sum(r["缺署名"] for r in live)
    uncovered = [r for r in live if not r["守卫扫吗"] and r["页面数"]]
    hard_gap = [r for r in uncovered if r["缺署名"]]

    if a.json:
        print(json.dumps({"署名标记": SIG_MARK, "守卫声明覆盖": GUARD_COVERS,
                          "逐树": rows, "合计页面": tot, "合计缺署名": uns,
                          "守卫根本不扫且确有缺署名的树": [r["树"] for r in hard_gap]},
                         ensure_ascii=False, indent=1))
    else:
        print("署名标记：%s（取自 gbt_allinone.soul，不硬编码）" % SIG_MARK)
        print("%-14s %8s %8s %8s %8s  %s" % ("树", "页面数", "带署名", "缺署名", "文本产物", "守卫扫吗"))
        for r in rows:
            if not r.get("在"):
                print("%-14s %8s" % (r["树"], "（不在）"))
                continue
            print("%-14s %8d %8d %8d %8d  %s"
                  % (r["树"], r["页面数"], r["带署名"], r["缺署名"], r["文本产物"],
                     "✅ 声明覆盖" if r["守卫扫吗"] else "🔴 **不在扫描面**"))
        print()
        print("合计页面 %d ｜ 缺署名 %d" % (tot, uns))
        print()
        print("🔴 守卫**根本不扫**、而且**确有缺署名**的树（红线在这些树上没有技术强制）：")
        for r in hard_gap:
            print("   %-12s 缺 %d / %d ｜ 样例 %s"
                  % (r["树"], r["缺署名"], r["页面数"], r["缺署名样例"]))
        if not hard_gap:
            print("   （无）")
        print()
        print("📌 注意：**不在扫描面 ≠ 一定缺署名**。有些树自己带署名（例如 outputs/ 的页面"
              "由生成器写了页脚），但**丢了也没人报** —— 缺口是「无校验」，不是「已违规」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
