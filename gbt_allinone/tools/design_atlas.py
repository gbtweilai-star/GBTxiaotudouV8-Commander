# gbt-capability: design_atlas
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""design_atlas —— **设计与审美图鉴的口**（把外部手册蒸成"按人话找到该读哪一节"）。

## 来历（主人令：「GOATED-UI-SKILL 里面的全部都要吞噬，增加触手对设计还有审美能力」）

`flash-hero/GOATED-UI-SKILL`（MIT · 10.3 MB）落 `_upstream/goated-ui-skill`。
**只读体检**（真跑）：零可执行二进制 · 5 个 `.mjs` **只做本地文件读写**（`motion-audit.mjs` 只打
`http://localhost:3000` 且要显式传参）· 一处 `eval(` 是**文档示例**（`page.$$eval`）· 我们**不跑它任何脚本**。

它的本事在 **`skills/frontend-atlas/references/` 的 18 份手册 ≈ 1.9 MB**：
`component-recipes`（185 KB）· `backgrounds-svg-canvas`（145 KB）· `webgl-shaders-3d`（131 KB）·
`interactions`（130 KB）· `scroll-gsap`（121 KB）· `aesthetic-directions`（104 KB）· `page-transitions`（96 KB）·
`color-surfaces`（95 KB）· `text-effects`（94 KB）· `performance-a11y`（91 KB）· `layout-composition`（86 KB）·
`motion-principles`（87 KB）· `css-modern`（85 KB）· `libraries`（81 KB）· `scroll-css-native`（78 KB）·
`typography`（52 KB）· `inspiration-sources`（54 KB）· `INDEX`（48 KB）。

## 🔴 为什么"躺在盘上"不等于"有能力"

1.9 MB 的散文，**人话问不出**"我要一个滚动驱动的文字动画该读哪一节"。
本件把它蒸成**可检索的落点**：每条 recipe（`### N. 标题`）= 一行记录（文件 · 标题 · **行号** · 摘要 · 有无代码），
外加 `inspiration-sources.md` 的**来源条目**（类别 · 名 · URL）。
`find(人话)` ⇒ 命中**哪份文件哪一节**（带 `path#L行号`）—— 她去读那一节，而不是翻 1.9 MB。

## 铁律

1. **只读 · 零执行**：**绝不**跑上游任何 `.mjs`/脚本；只读文本。
2. **不改上游一个字节**。
3. **不编**：摘要只从**该节自己的正文**里取；取不到就留空。
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "_upstream" / "goated-ui-skill" / "skills" / "frontend-atlas" / "references"
_OPS = ("status", "build", "find", "where")

_H2 = re.compile(r"^##\s+(.+?)\s*$")
_H3 = re.compile(r"^###\s+(.+?)\s*$")
_LINK = re.compile(r"^\s*[-*]\s*\[([^\]]+)\]\((https?://[^)\s]+)\)")
_TROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(https?://\S+?)\s*\|(.*)$")
_FENCE = re.compile(r"^\s*```([A-Za-z0-9_+-]*)\s*$")

# 🔴 **设计/审美中文桥**（2026-10-13 实测：手册标题全是英文，中文人话 0 命中）。
#    与 `ui_kit` 的类目桥同族：**中文口语 → 英文关键词**，只在检索时用，不动上游一个字。
_CN_BRIDGE = {
    "滚动": "scroll", "滚动驱动": "scroll-driven scroll-timeline", "视差": "parallax",
    "文字": "text type", "字体": "font typeface typography", "排版": "typography layout",
    "动画": "animation motion", "缓动": "easing curve", "弹簧": "spring",
    "毛玻璃": "glass blur backdrop", "模糊": "blur", "透明": "transparent opacity",
    "渐变": "gradient", "阴影": "shadow", "发光": "glow neon", "粒子": "particles sparkles",
    "背景": "background", "过渡": "transition page-transition", "悬停": "hover cursor",
    "卡片": "card", "英雄区": "hero", "首屏": "hero", "导航": "nav navbar menu",
    "性能": "performance", "无障碍": "accessibility a11y", "图标": "icon",
    "颜色": "color palette surface", "深色": "dark theme", "动效": "motion",
    "三维": "webgl 3d shader", "着色器": "shader glsl", "图片": "image",
    "加载": "loading", "滚动条": "scrollbar", "光标": "cursor",
    "灵感": "inspiration sources gallery", "素材": "assets sources", "工具": "tools",
}


def _store_dir() -> Path:
    d = os.environ.get("GBT_STORE_DIR")
    return Path(d) if d else (_ROOT / "gbt_allinone" / "store")


def _index_path() -> Path:
    p = _store_dir() / "design_atlas"
    p.mkdir(parents=True, exist_ok=True)
    return p / "index.jsonl"


def _scan_file(p: Path) -> list:
    """把一份手册切成"节"：`### N. 标题` = 一条 recipe；`inspiration-sources` 里的
    `- [名](url)` = 一条来源。**只读文本**。"""
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows, cur = [], None
    for i, ln in enumerate(lines):
        m3 = _H3.match(ln)
        if m3:
            cur = {"kind": "recipe", "file": p.name, "title": m3.group(1).strip(),
                   "line": i + 1, "summary": "", "code": "", "url": ""}
            rows.append(cur)
            continue
        if _H2.match(ln):
            cur = None                      # 出 recipe 区（如 ## Contents）⇒ 后面的正文不归任何 recipe
            continue
        if cur is None:
            continue
        f = _FENCE.match(ln)
        if f and not cur["code"]:
            cur["code"] = f.group(1) or "?"
            continue
        if not cur["summary"] and ln.strip() and not ln.lstrip().startswith(("|", "-", "#", ">")):
            cur["summary"] = re.sub(r"\s+", " ", ln.strip())[:100]
    # 来源条目（`- [名](url)`）单独成行：挂在它所属的 ### 类目上
    if p.name == "inspiration-sources.md":
        # 实测：这一份的来源是**表格**（`| 名 | URL | Best for | 怎么用 | 状态 |`），
        # 不是 `- [名](url)` —— 首版按列表抽 ⇒ **sources=0**（全是空的）。
        cat = ""
        for i, ln in enumerate(lines):
            m3 = _H3.match(ln)
            if m3:
                cat = m3.group(1).strip()
                continue
            mt = _TROW.match(ln)
            if mt and cat and "http" in mt.group(2):
                rest = re.sub(r"\s+", " ", mt.group(3)).strip(" |")
                rows.append({"kind": "source", "file": p.name, "title": mt.group(1).strip(),
                             "line": i + 1, "summary": ("%s ｜ %s" % (cat, rest))[:160],
                             "code": "", "url": mt.group(2)})
                continue
            ml = _LINK.match(ln)
            if ml and cat:
                rows.append({"kind": "source", "file": p.name, "title": ml.group(1).strip(),
                             "line": i + 1, "summary": cat, "code": "", "url": ml.group(2)})
    return rows


def build(force: bool = False, **_kw) -> dict:
    """扫 18 份手册建索引（**只追加**）。"""
    if not _SRC.is_dir():
        return {"ok": False, "status": "needs_dependency", "missing": [str(_SRC)],
                "note": "素材不在盘 ⇒ 先按七步法第 1 步落位（git clone --depth 1）"}
    idx = _index_path()
    if idx.is_file() and not force:
        items = _load()
        return {"ok": True, "reused": True, "rows": len(items), "index": str(idx),
                "note": "索引已在；要重扫给 force=true"}
    rows = []
    for p in sorted(_SRC.glob("*.md")):
        if p.name == "INDEX.md":
            continue                        # 那是它自己的索引；我们**从源文重建**，不抄它的
        rows.extend(_scan_file(p))
    if not rows:
        return {"ok": False, "error": "一条都抽不出 ⇒ 不写空库（fail-closed）"}
    with idx.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "design_atlas_index",
                             "src": "_upstream/goated-ui-skill", "count": len(rows),
                             "items": rows}, ensure_ascii=False) + "\n")
    rec = sum(1 for r in rows if r["kind"] == "recipe")
    return {"ok": True, "rows": len(rows), "recipes": rec, "sources": len(rows) - rec,
            "files": len({r["file"] for r in rows}), "index": str(idx)}


def _load() -> list:
    idx = _index_path()
    if not idx.is_file():
        return []
    last = None
    for line in idx.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                last = json.loads(line)
            except Exception:                                # noqa: BLE001
                continue
    return (last or {}).get("items") or []


def find(q: str = "", limit: int = 8, kind: str = "", file: str = "", **_kw) -> dict:
    """人话 → **该读哪一份哪一节**（带行号）。命中 0 就如实报 0。"""
    items = _load()
    if not items:
        return {"ok": False, "status": "needs_build", "error": "索引不在 ⇒ 先 op=build"}
    from ..semantic_route import grams
    # 中文桥：把口语里的中文词**扩成英文关键词**再查（手册标题全是英文）——
    # 扩查询不影响 df/idf 口径（两者都基于扩后的 qg）。
    qs = str(q or "")
    qg = grams(qs) if qs.strip() else set()
    bridge_hit = [cn for cn in _CN_BRIDGE if cn in qs]
    for cn in bridge_hit:
        qg |= grams(_CN_BRIDGE[cn])
    def fvals(r):                            # df 与打分**共用同一份字段**（上一刀踩过：两处口径不一致）
        return {"title": r.get("title") or "", "summary": r.get("summary") or "",
                "file": (r.get("file") or "").replace(".md", "")}
    df: dict = {}
    if qg:
        for r in items:
            seen = set()
            for v in fvals(r).values():
                seen |= (qg & grams(v))
            for t in seen:
                df[t] = df.get(t, 0) + 1
    n = max(1, len(items))
    idf = {t: math.log(1.0 + n / (1.0 + c)) for t, c in df.items()}
    w = {"title": 2.0, "summary": 1.0, "file": 0.5}
    out = []
    for r in items:
        if kind and r["kind"] != kind:
            continue
        if file and str(file).replace(".md", "") not in r["file"]:
            continue
        v = fvals(r)
        s = 0.0
        for k in w:
            hit = qg & grams(v[k])
            if hit:
                s += w[k] * sum(idf.get(t, 0.0) for t in hit)
        if qg and s <= 0:
            continue
        out.append({**r, "score": round(s, 3), "where": "%s#L%d" % (r["file"], r["line"])})
    out.sort(key=lambda r: -r["score"])
    return {"ok": True, "q": q, "hits": len(out), "items": out[:int(limit)], "indexed": len(items),
            "_口径": "打分 = Σ(字段权重 × idf)：标题 2.0 · 摘要 1.0 · 文件名 0.5；"
                     "命中项给 `文件#L行号` ⇒ 直接去读那一节；**命中 0 就是 0**"}


def status(**_kw) -> dict:
    items = _load()
    by = {}
    for r in items:
        by[r["kind"]] = by.get(r["kind"], 0) + 1
    files = {}
    for r in items:
        files[r["file"]] = files.get(r["file"], 0) + 1
    return {"ok": True, "op": "status", "kind": "design_atlas", "src": str(_SRC),
            "src_present": _SRC.is_dir(), "indexed": len(items), "by_kind": by,
            "files": len(files), "ops": list(_OPS),
            "_口径": "素材 = flash-hero/GOATED-UI-SKILL（MIT）的 18 份手册；"
                     "本件**只读、零执行**（绝不跑它的 .mjs），不改上游一个字节"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "design_atlas",
            "entry": "run_task('design_atlas', {...})", "ops": list(_OPS),
            "what": "把外部设计手册蒸成**可检索的落点**：人话 → 该读哪份文件哪一节（带行号）",
            "why": "1.9 MB 散文躺在盘上，人话问不出「滚动驱动的文字动画读哪一节」",
            "hard_rules": ["只读 · **零执行**（绝不跑上游 .mjs）", "不改上游一个字节",
                           "摘要只从该节正文取，取不到留空", "df 与打分共用同一份字段（防口径打架）"],
            "上游": "flash-hero/GOATED-UI-SKILL（MIT）· skills/frontend-atlas/references/ 18 份",
            "下游": "读中选中的那一节 → 真写代码 → shot-page/render_page 真渲 → vision_print.polish 调优"}


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    for nm, fn in (("status", status), ("build", build), ("find", find), ("where", where)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="设计与审美图鉴的口（人话 → 该读哪一节）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}")
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
