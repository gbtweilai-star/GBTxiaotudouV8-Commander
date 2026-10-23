# gbt-capability: bits_kit
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""bits_kit —— **动效组件图鉴的口**（人话 → react-bits 哪个组件 · 干什么 · 源码在哪）。

## 来历（主人令：「DavidHDev/react-bits 继续吞噬」）

`DavidHDev/react-bits`（**react-bits**）★49005 · 落 `_upstream/react-bits`（稀疏浅克隆 · **21.63 MB**）。
它是"最大的开源动效 React/Next 组件库"，`src/content/` 下 **5 类共 216 个组件**：
Animations 39 · Backgrounds 62 · Components 48 · Micro 34 · TextAnimations 33。

## 🔴 许可与 galaxy / anime **不一样**（这一条决定本件只做「知识」，不做「搬运」）

`LICENSE.md` 现读 = **MIT + Commons Clause License Condition v1.0**（`Copyright (c) 2026 David Haz`）：
**可以**把组件放进你自己的应用 / 网站 / 产品里用（含商用）；**禁止**把组件本身
（**单独 / 打包 / 移植版**）再卖 · 再授权 · 再分发。
⇒ 本件**只蒸「哪个组件干什么 · 源码在哪」**，**不提供任何把组件拷出去的 op** ——
   要学就**读原文自己实现**。这条纪律写在每一处返回里（`license` / `restriction`）。

## 只读体检（真跑，不猜）

1284 文件 / 22.5 M 字符 · `postinstall`/`prepare` **无** · `child_process`/`eval`/`require`/`process.env` **0**；
`exec(` 205 处**全是正则 `.exec()`**；`await fetch(` 真联网只在 **2 个组件**（`CircularGallery` 取字体表 ·
`MetallicPaint` 取图片判 SVG）；`GridScan` 硬编码从 `cdn.jsdelivr.net` 拉 `face-api.js` 与其**模型权重**。
⇒ 没有任何安装期执行，但**有组件会在运行时联网 / 拉模型** —— 本件把它标成 `net`，用之前自己判。

## 铁律

1. **只读 · 零执行**：绝不跑上游任何脚本、绝不 `npm i`、绝不执行组件。
2. **不改 `_upstream/react-bits/**` 一个字节**；**不碰** `public/rbp/**`（那是付费版 Pro，落位时就没拉它）。
3. **不编**：说明只取自 `public/llms.txt` 的原文；清单与盘上对不上的地方**如实带出来**。
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "_upstream" / "react-bits"
_LLMS = _SRC / "public" / "llms.txt"
_CONTENT = _SRC / "src" / "content"
_REG = _SRC / "public" / "r"
_OPS = ("status", "build", "find", "api", "where")

_LICENSE = "MIT + Commons Clause License Condition v1.0"
_RESTRICTION = ("可以放进**你自己的**应用/网站/产品里用（含商用）；"
                "**禁止**把组件本身（单独 / 打包 / **移植版**）再卖 · 再授权 · 再分发。"
                "=> 本件只给**知识与出处**，**不搬成品**：要学就读原文自己实现。")

_LINE = re.compile(r"^- \[([^\]]+)\]\((https?://[^)]+)\)\s*:\s*(.+)$")
_CLI = re.compile(r"\s*CLI:\s*`([^`]+)`\s*\.?\s*$")
_FREE = {"Text Animations": "TextAnimations", "Animations": "Animations",
         "Components": "Components", "Micro": "Micro", "Backgrounds": "Backgrounds"}
_CAT_CN = {"Animations": "动画 动效", "Backgrounds": "背景 底纹",
           "Components": "组件 界面组件", "Micro": "微交互 小交互",
           "TextAnimations": "文字动画 文本动画 打字"}
_SRC_EXT = (".jsx", ".tsx", ".css", ".js")
_NET_RX = (("await fetch(", "运行时 fetch"), ("cdn.jsdelivr.net", "CDN 拉取"),
           ("XMLHttpRequest", "XHR"), ("new Worker(", "起 Worker"))
_WORD_SPLIT = re.compile(r"([a-z0-9])([A-Z])")
_WORD = re.compile(r"[a-z0-9]+")

# **中文口语 ↔ 英文名之间的桥**（同族教训：组件名全是英文 PascalCase，中文人话没有桥就 0 命中）
_CN_BRIDGE = {
    "动画": "animation animate motion", "动效": "animation motion",
    "背景": "background backdrop", "底纹": "background pattern",
    "文字动画": "text animation", "文本": "text", "打字": "type typing text", "逐字": "text split",
    "微交互": "micro interaction", "小交互": "micro",
    "组件": "component", "界面": "ui component",
    "手风琴": "accordion", "画廊": "gallery", "相册": "gallery", "卡片": "card",
    "光标": "cursor pointer", "鼠标": "cursor pointer mouse", "跟随": "follow cursor",
    "粒子": "particle", "网格": "grid", "点阵": "dot grid",
    "渐变": "gradient", "流光": "shiny shine shimmer", "闪光": "shine sparkle",
    "玻璃": "glass", "毛玻璃": "blur frost glass",
    "滚动": "scroll", "视差": "parallax",
    "数字": "count number", "计数": "count", "计数器": "count up",
    "故障": "glitch", "毛刺": "glitch", "赛博": "cyber glitch",
    "极光": "aurora", "星空": "star space", "星云": "nebula space",
    "波浪": "wave", "涟漪": "ripple", "水滴": "liquid drop",
    "液态": "liquid fluid", "流体": "fluid", "金属": "metal metallic",
    "三维": "three 3d", "3d": "three 3d", "体素": "voxel cube",
    "音频": "audio music", "音乐": "music audio", "频谱": "spectrum audio",
    "拖拽": "drag draggable", "轮播": "carousel", "走马灯": "carousel marquee",
    "导航": "nav menu", "菜单": "menu nav", "侧栏": "sidebar",
    "弹窗": "modal dialog", "对话框": "dialog modal", "提示": "tooltip",
    "开关": "toggle switch", "按钮": "button", "加载": "loader loading spinner",
    "进度": "progress", "骨架屏": "skeleton", "点赞": "like heart", "喜欢": "like heart",
    "通知": "notification toast", "随机": "random", "翻牌": "flap split",
    "解密": "decrypt scramble", "乱码": "scramble glitch", "模糊": "blur",
    "描边": "stroke outline", "环绕": "circular orbit", "圆形": "circle circular",
    "磁性": "magnet", "折叠": "fold", "打字机": "typewriter type",
}


def _store_dir() -> Path:
    d = os.environ.get("GBT_STORE_DIR")
    return Path(d) if d else (_ROOT / "gbt_allinone" / "store")


def _index_path() -> Path:
    p = _store_dir() / "bits_kit"
    p.mkdir(parents=True, exist_ok=True)
    return p / "index.jsonl"


def _catalog() -> dict:
    """从 `public/llms.txt` 现读**免费五类**目录：CLI id → {display,url,desc,section}。

    🔴 Pro 小节（`Pro Components (230)` 等）**不在 `_FREE` 里 ⇒ 天然不进来**（付费版不外流）。
    """
    if not _LLMS.is_file():
        return {}
    out, cur = {}, None
    for ln in _LLMS.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^## (.+)$", ln)
        if m:
            cur = m.group(1).strip()
            continue
        if cur not in _FREE:
            continue
        m = _LINE.match(ln)
        if not m:
            continue
        rest = m.group(3).strip()
        cm = _CLI.search(rest)
        if not cm:
            continue
        out[cm.group(1)] = {"display": m.group(1), "url": m.group(2),
                            "desc": _CLI.sub("", rest).strip(), "section": cur}
    return out


def _net_of(d: Path, reg_json) -> list:
    """这个组件会不会**运行时联网**（只读文本判标，不执行）。"""
    marks = set()
    pool = [p for p in d.iterdir() if p.is_file() and p.suffix in _SRC_EXT] if d.is_dir() else []
    if reg_json is not None and Path(reg_json).is_file():
        pool.append(Path(reg_json))
    for p in pool:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for rx, label in _NET_RX:
            if rx in t:
                marks.add(label)
    return sorted(marks)


def _pick_main(srcs: list, name: str):
    """主件优先指**代码**（`.jsx`/`.tsx`/`.js`）且**与组件同名**那一件，其次任意代码件，最后才退到列表首。

    （首版取 `srcs[0]` ⇒ 字母序把 `Xxx.css` 排在前，`src` 指到了 CSS —— 读的人要的是 JSX。）
    """
    code = [p for p in srcs if p.suffix in (".jsx", ".tsx", ".js")]
    for p in code:
        if p.stem == name:
            return p
    return code[0] if code else (srcs[0] if srcs else None)


def _variants(name: str) -> int:
    return sum(1 for k in ("JS-CSS", "JS-TW", "TS-CSS", "TS-TW")
               if (_REG / ("%s-%s.json" % (name, k))).is_file())


def _deps(reg_json) -> list:
    if reg_json is None or not Path(reg_json).is_file():
        return []
    try:
        o = json.loads(Path(reg_json).read_text(encoding="utf-8", errors="replace"))
    except Exception:                                        # noqa: BLE001
        return []
    return o.get("dependencies") or []


def build(force: bool = False, **_kw) -> dict:
    """扫 `src/content` 建**可检索面**（**盘上目录是真相**；llms.txt 只用来补说明，对不上就如实记）。"""
    if not _CONTENT.is_dir():
        return {"ok": False, "status": "needs_dependency", "missing": [str(_CONTENT)],
                "note": "素材不在盘 => 先按七步法第 1 步落位（稀疏浅克隆）"}
    idx = _index_path()
    if idx.is_file() and not force:
        items = _load()
        return {"ok": True, "reused": True, "rows": len(items), "index": str(idx),
                "note": "索引已在；要重扫给 force=true"}
    cat = _catalog()
    rows, no_desc, net_rows, drift = [], [], [], []
    for catdir in sorted(_CONTENT.iterdir()):
        if not catdir.is_dir():
            continue
        for cd in sorted(catdir.iterdir()):
            if not cd.is_dir():
                continue
            name = cd.name
            srcs = sorted(p for p in cd.iterdir() if p.is_file() and p.suffix in _SRC_EXT)
            reg = _REG / ("%s-JS-CSS.json" % name)
            meta = cat.get(name) or {}
            if not meta:
                no_desc.append(name)
            # 清单把它归在哪一类 vs 它**在盘上**属于哪一类（**盘是真相**；对不上就点出来）
            if meta and _FREE.get(meta.get("section")) and _FREE[meta["section"]] != catdir.name:
                drift.append({"name": name, "清单归": meta["section"], "盘上归": catdir.name})
            net = _net_of(cd, reg)
            if net:
                net_rows.append({"name": name, "marks": net})
            main = _pick_main(srcs, name)
            rows.append({
                "name": name, "category": catdir.name, "cat_cn": _CAT_CN.get(catdir.name, ""),
                "display": meta.get("display") or name, "desc": meta.get("desc") or "",
                "url": meta.get("url") or "",
                "src": "%s/%s" % (cd.relative_to(_ROOT).as_posix(), main.name if main else ""),
                "src_files": [p.name for p in srcs],
                "reg": ("public/r/%s-JS-CSS.json" % name) if reg.is_file() else "",
                "variants": _variants(name), "deps": _deps(reg), "net": net,
                "bytes": sum(p.stat().st_size for p in srcs),
            })
    if not rows:
        return {"ok": False, "error": "一个组件都抽不出 => 不写空库（fail-closed）"}
    with idx.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "bits_kit_index",
                             "src": "_upstream/react-bits", "license": _LICENSE,
                             "count": len(rows), "items": rows}, ensure_ascii=False) + "\n")
    bycat = {}
    for r in rows:
        bycat[r["category"]] = bycat.get(r["category"], 0) + 1
    return {"ok": True, "indexed": len(rows), "by_category": bycat,
            "with_desc": sum(1 for r in rows if r["desc"]), "catalog_rows": len(cat),
            "盘上没有说明的": no_desc, "清单里有盘上没有的": sorted(set(cat) - {r["name"] for r in rows}),
            "清单分类与盘上分类漂移": drift,
            "运行时联网组件": net_rows, "license": _LICENSE, "index": str(idx)}


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


def _fields(r: dict) -> dict:
    """df 与打分**共用同一份字段**（同族踩过：两处口径不一致 => 假结论）。"""
    return {"name": "%s %s" % (r.get("name") or "", r.get("display") or ""),
            "cat": "%s %s" % (r.get("category") or "", r.get("cat_cn") or ""),
            "desc": r.get("desc") or "", "deps": " ".join(r.get("deps") or [])}


def _words(s) -> set:
    """英文标识符拆词（**camelCase 要拆**：`AnimatedContent` -> {animated,content}）。"""
    return set(_WORD.findall(_WORD_SPLIT.sub(r"\1 \2", str(s)).lower()))


def _allwords(r: dict) -> set:
    out: set = set()
    for v in _fields(r).values():
        out |= _words(v)
    return out


def find(q: str = "", limit: int = 8, category: str = "", only_offline: bool = False, **_kw) -> dict:
    """人话 -> 候选组件（带**源码路径**与**会不会联网**）。**命中 0 就如实报 0**。"""
    items = _load()
    if not items:
        return {"ok": False, "status": "needs_build", "error": "索引不在 => 先 op=build"}
    from ..semantic_route import grams
    qs = str(q or "")
    bridge = [cn for cn in _CN_BRIDGE if cn in qs.lower()]
    qtext = " ".join([qs] + [_CN_BRIDGE[cn] for cn in bridge])
    qg = grams(qtext) if qtext.strip() else set()
    qw = _words(qtext)
    n = max(1, len(items))
    df, dfw = {}, {}
    if qg:
        for r in items:
            seen = set()
            for v in _fields(r).values():
                seen |= (qg & grams(v))
            for t in seen:
                df[t] = df.get(t, 0) + 1
    if qw:
        for r in items:
            for t in (qw & _allwords(r)):
                dfw[t] = dfw.get(t, 0) + 1
    idf = {t: math.log(1.0 + n / (1.0 + c)) for t, c in df.items()}
    idfw = {t: math.log(1.0 + n / (1.0 + c)) for t, c in dfw.items()}
    w = {"name": 2.5, "cat": 1.2, "desc": 1.2, "deps": 0.5}
    _WORD_W = 4.0
    out = []
    for r in items:
        if category and r["category"].lower() != str(category).lower():
            continue
        if only_offline and r["net"]:
            continue
        v = _fields(r)
        s, why = 0.0, []
        for k in w:
            hit = qg & grams(v[k])
            if hit:
                s += w[k] * sum(idf.get(t, 0.0) for t in hit)
                why.append("%s命中%d" % (k, len(hit)))
        wh = qw & _allwords(r)
        if wh:
            s += _WORD_W * sum(idfw.get(t, 0.0) for t in wh)
            why.append("词命中:" + ",".join(sorted(wh))[:60])
        if qg and s <= 0:
            continue
        out.append({**r, "score": round(s, 3), "why": why, "license": _LICENSE})
    out.sort(key=lambda r: -r["score"])
    return {"ok": True, "q": q, "hits": len(out), "items": out[:int(limit)], "indexed": len(items),
            "bridge": bridge, "license": _LICENSE, "restriction": _RESTRICTION,
            "_口径": "打分 = Σ(字段权重 x gram-idf)[名 2.5 · 类目 1.2 · 说明 1.2 · 依赖 0.5] "
                     "+ 4.0 x Σ(词-idf)[camelCase 拆词的**精确词**命中]；中文口语经**桥**扩成英文；"
                     "**命中 0 就是 0**。`net` 非空 = 该组件会运行时联网，用之前自己判"}


def api(name: str = "", **_kw) -> dict:
    """按**准确组件名**取一条（含源码路径 / 注册表 / 依赖 / 联网标）。名字对不上就是 0。"""
    if not str(name or "").strip():
        return {"ok": False, "fail_closed": True, "error": "要 name（用 op=find 拿候选名）"}
    items = _load()
    if not items:
        return {"ok": False, "status": "needs_build", "error": "索引不在 => 先 op=build"}
    nm = str(name).strip()
    hit = [r for r in items if r["name"] == nm] or [r for r in items if r["name"].lower() == nm.lower()]
    return {"ok": True, "name": name, "hits": len(hit), "items": hit,
            "license": _LICENSE, "restriction": _RESTRICTION}


def status(**_kw) -> dict:
    items = _load()
    by = {}
    for r in items:
        by[r["category"]] = by.get(r["category"], 0) + 1
    return {"ok": True, "op": "status", "kind": "bits_kit", "src": str(_SRC),
            "src_present": _SRC.is_dir(), "catalog_present": _LLMS.is_file(),
            "indexed": len(items), "by_category": by, "ops": list(_OPS),
            "license": _LICENSE, "restriction": _RESTRICTION,
            "net_components": [r["name"] for r in items if r.get("net")],
            "_口径": "素材 = DavidHDev/react-bits（**MIT + Commons Clause v1.0** · 49005 星 · 216 组件）；"
                     "本件**只读 · 零执行**，**不提供把组件拷出去的 op**（许可禁止再分发/移植）"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "bits_kit",
            "entry": "run_task('bits_kit', {'op':'find','q':'手风琴画廊'})", "ops": list(_OPS),
            "what": "人话 -> react-bits 哪个组件 · 干什么 · **源码在哪 · 会不会联网 · 依赖什么**",
            "许可": {"license": _LICENSE, "restriction": _RESTRICTION},
            "怎么用": "`find` 拿到 `src`（如 `_upstream/react-bits/src/content/Components/AccordionGallery/"
                     "AccordionGallery.jsx`）与 `reg`（`public/r/<名>-JS-CSS.json` 含**四种变体**的完整源码）"
                     "=> **自己去读原文、照着手写实现**；本件**不搬成品**。",
            "hard_rules": ["只读 · 零执行（不跑上游脚本、不 npm i）",
                           "不改 `_upstream/react-bits/**` 一个字节",
                           "**不碰 `public/rbp/**`**（那是付费版 Pro，落位时就排除在外）",
                           "说明只取自 `public/llms.txt` 原文，取不到留空（不编）",
                           "df 与打分共用同一份字段（防口径打架）"],
            "上游": "DavidHDev/react-bits（MIT + Commons Clause v1.0 · 49005 星 · 216 组件 · 5 类）",
            "下游": "design_atlas（该学哪一节）· motion_kit（anime.js 动效 API）· ui_kit（纯 HTML/CSS 组件）· art_chain（真渲出图）"}


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    for nm, fn in (("status", status), ("build", build), ("find", find), ("api", api),
                   ("where", where)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":                                   # 主人的终端入口
    import argparse
    import sys
    try:                        # 本机控制台默认 GBK => 中文直接打会 UnicodeEncodeError
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                    # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="动效组件图鉴的口（人话 -> react-bits 哪个组件）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}")
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
