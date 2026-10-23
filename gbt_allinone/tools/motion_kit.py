# gbt-capability: motion_kit
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""motion_kit —— **动效引擎的口**（把人话接到 anime.js 的真 API 上，并证明吞来的引擎在本机真能跑）。

## 来历（主人令：「`juliangarnier/anime` 这个也吞噬了」）

`juliangarnier/anime`（**anime.js**）★73546 · **MIT** · `animejs` **v4.5.0** · 落 `_upstream/anime`。
**只读体检**（真跑）：`postinstall`/`prepare` **无** · 运行时 deps **0**（devDeps 12）· 可执行 **0**。
落位：`git sparse-checkout` 那一刀不听话（只落了 3 件）⇒ 改走全量浅克隆，现读 **281 文件 / 1.49 MB**。

## 🔴 为什么"克隆 + 建索引"还不够（与 `ui_kit` / `design_atlas` 同一条教训）

它的本事是 **67 个导出的 API**（`animate` / `createTimeline` / `createSpring` / `stagger` / `svg` …），
名字躺在 `dist/modules/index.js` 里；可**人话问不出**"我要一个弹跳的按钮该用哪个 API、怎么传参"。
⇒ 本件做两件事：

① **蒸成可检索面**：人话 → 哪个 API + 签名 + `文件#L行号`（签名/说明**只从 `.d.ts` 现读**，取不到留空）。
② **本机原生真跑**：`op=prove` 让 Node 直接 `import` 吞来的 `dist/modules/index.js`，真算几条纯函数
   （`clamp`/`lerp`/`mapRange`/`round`）+ 拿运行时导出数去**咬**索引里的条数。
   —— **"吞进来了"和"它真能用"是两件事**，第二件必须现证，不许念成绿。

## 铁律

1. **零出网 · 零执行上游脚本**：只读文本 + 只 `import` 引擎本体算纯函数；**绝不**跑它任何构建/示例脚本。
2. **不改 `_upstream/anime/**` 一个字节**。
3. **不编**：签名与说明只从 `dist/modules/**/*.d.ts` 现读；取不到就留空（不写"应该"）。
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "_upstream" / "anime"
_DIST = _SRC / "dist" / "modules"
_INDEX_JS = _DIST / "index.js"
_OPS = ("status", "build", "find", "api", "prove", "where")

# index.js 的三形：`export { A, B as C } from './x/y.js';` · `import * as n from '...'` · `export { n as ns };`
_E_FROM = re.compile(r"^export\s*\{([^}]*)\}\s*from\s*'([^']+)'\s*;\s*$")
# 🔴 2026-10-13 实测：`\w+` **不认 `$`** —— index.js 里 `index$1`/`index$2`/`index$3` 三个
#    命名空间导入因此被整行跳过，索引只出 64 条而运行时是 67 条（差的正是 `utils`/`svg`/`text`）。
#    这个错是 `op=prove` 的 `consistent` 咬出来的 ⇒ 标识符一律 `[\w$]+`。
_E_NS_IMPORT = re.compile(r"^import\s+\*\s+as\s+([\w$]+)\s+from\s*'([^']+)'\s*;\s*$")
_E_NS_EXPORT = re.compile(r"^export\s*\{\s*([\w$]+)\s+as\s+([\w$]+)\s*\}\s*;\s*$")

# 🔴 **中文口语 ↔ 英文 API 名之间的桥**（实测教训同族：问「弹跳按钮」，头几件全是
#    `animate` —— 因为 API 名是英文 `spring`，中文「弹跳」永远匹配不上它）。
#    这张表就是那座桥；**只在检索时扩查询**，不动上游一个字，也不进索引行。
_CN_BRIDGE = {
    "动画": "animate animation tween", "动效": "animate animation motion",
    "补间": "tween animate", "时间线": "timeline", "序列": "timeline", "编排": "timeline",
    "定时": "timer createTimer", "计时": "timer", "循环": "loop timer",
    "滚动": "scroll onScroll", "滚动驱动": "scroll onScroll", "视差": "scroll parallax",
    "拖拽": "draggable drag", "拖动": "draggable drag", "拖放": "draggable drag",
    "弹簧": "spring createSpring", "回弹": "spring bounce", "弹性": "spring elastic",
    "弹跳": "spring bounce createSpring", "跳动": "spring bounce", "蹦": "spring bounce",
    "缓动": "easing eases cubicBezier steps", "缓动曲线": "easing cubicBezier eases",
    "贝塞尔": "cubicBezier", "步进": "steps", "阶梯": "steps",
    "打字机": "splitText scrambleText split", "逐字": "splitText split", "拆字": "split TextSplitter",
    "文字": "text splitText scrambleText", "文本": "text splitText",
    "乱码": "scrambleText scramble", "打乱": "scrambleText shuffle randomPick",
    "变形": "morphTo morph", "形状": "morphTo svg", "路径": "createMotionPath motionpath",
    "沿路径": "createMotionPath motionpath", "描边": "createDrawable drawable", "画出来": "createDrawable",
    "交错": "stagger", "错开": "stagger", "依次": "stagger",
    # 🔴 2026-10-13 实测两处：① `入场` 桥成 "animate createTimeline" ⇒ 词命中 `create`+`timeline`
    #    把 `createTimeline` 顶到 `stagger` 前面② 只留 `animate` 时仍把 `animate` 顶在 `stagger` 前。
    #    「入场/出场」是**泛词**（不指向某个 API）⇒ **不设这条桥**；问「错开入场」只靠 `错开`→`stagger` 就准。
    "打字": "splitText scrambleText",
    "随机": "random randomPick shuffle createSeededRandom",
    "取整": "round roundPad", "映射": "mapRange", "区间": "mapRange clamp", "裁剪": "clamp",
    "插值": "lerp", "角度": "degToRad radToDeg", "弧度": "degToRad radToDeg",
    "数值": "utils clamp lerp mapRange round snap wrap", "工具": "utils",
    "布局": "layout AutoLayout", "自动布局": "AutoLayout createLayout",
    "三维": "adapters three", "3d": "adapters three", "webgl": "adapters three",
    "作用域": "scope createScope", "作用范围": "scope",
    "可动画对象": "animatable createAnimatable", "对象动画": "animatable createAnimatable",
    "暂停": "pause engine timer", "播放": "play engine", "引擎": "engine", "全局": "globals",
    "目标": "targets get set remove", "选择器": "targets", "获取": "get", "设置": "set",
    "等待": "keepTime sync", "同步": "sync keepTime", "清理": "cleanInlineStyles",
    "内联样式": "cleanInlineStyles", "web动画": "waapi WAAPIAnimation", "性能": "waapi",
}


def _store_dir() -> Path:
    d = os.environ.get("GBT_STORE_DIR")
    return Path(d) if d else (_ROOT / "gbt_allinone" / "store")


def _index_path() -> Path:
    p = _store_dir() / "motion_kit"
    p.mkdir(parents=True, exist_ok=True)
    return p / "index.jsonl"


def _pkg() -> dict:
    """读 `package.json`（只看 name/version/license —— 不碰脚本）。"""
    try:
        return json.loads((_SRC / "package.json").read_text(encoding="utf-8", errors="replace"))
    except Exception:                                        # noqa: BLE001
        return {}


def _parse_public_api() -> list:
    """从 `dist/modules/index.js` 现读公开导出（**唯一真相是它自己**，不手抄名单）。"""
    if not _INDEX_JS.is_file():
        return []
    lines = _INDEX_JS.read_text(encoding="utf-8", errors="replace").splitlines()
    ns_local, rows = {}, []
    for i, ln in enumerate(lines):
        m = _E_NS_IMPORT.match(ln)
        if m:
            ns_local[m.group(1)] = m.group(2)
            continue
        m = _E_NS_EXPORT.match(ln)
        if m:
            rows.append({"name": m.group(2), "local": m.group(1), "from": ns_local.get(m.group(1), ""),
                         "line": i + 1, "ns": True})
            continue
        m = _E_FROM.match(ln)
        if m:
            for part in m.group(1).split(","):
                part = part.strip()
                if not part:
                    continue
                local, name = ([x.strip() for x in part.split(" as ", 1)] if " as " in part
                               else (part, part))
                rows.append({"name": name, "local": local, "from": m.group(2),
                             "line": i + 1, "ns": False})
    return rows


def _rel(from_path: str) -> str:
    return from_path[2:] if from_path.startswith("./") else from_path


def _declare(rel: str, name: str) -> tuple:
    """在 `dist/modules/<rel>` 里找**定义行** ⇒ (line, kind)。找不到就 (0, '')。"""
    p = _DIST / rel
    if not p.is_file():
        return 0, ""
    kw = r"(?:export\s+)?(?:const|let|var|async\s+function|function|class)\s+"
    pat = re.compile(kw + re.escape(name) + r"\b")
    for i, ln in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines()):
        m = pat.search(ln)
        if m:
            k = "class" if "class" in m.group(0) else (
                "function" if ("function" in m.group(0) or "=>" in ln) else "const")
            return i + 1, k
    return 0, ""


def _doc_above(lines: list, idx: int) -> str:
    """声明上一格若是 JSDoc 块，取它**第一句散文**（跳过 @ 标签）。取不到留空。"""
    j = idx - 1
    while j >= 0 and not lines[j].strip():
        j -= 1
    if j < 0 or not lines[j].lstrip().startswith(("*", "*/")):
        return ""
    k = j
    while k >= 0 and "/**" not in lines[k]:
        k -= 1
    if k < 0:
        return ""
    for ln in lines[k:j + 1]:
        t = ln.strip().lstrip("/*").strip()
        if t and not t.startswith("@") and not t.startswith("*/"):
            return t[:200]
    return ""


def _sig_dts(rel: str, name: str) -> tuple:
    """从 `.d.ts` 现读 **签名 + 说明** ⇒ (sig, doc)。取不到就 ('','')。"""
    p = (_DIST / rel).with_suffix(".d.ts")
    if not p.is_file():
        return "", ""
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    decl = re.compile(r"^export\s+(?:declare\s+)?(?:abstract\s+)?"
                      r"(?:function|class|const|let|var|type|interface|enum)\s+" + re.escape(name) + r"\b")
    star = re.compile(r"^export\s*\*?\s*(?:\{[^}]*\b" + re.escape(name) + r"\b[^}]*\}|.*\b"
                      + re.escape(name) + r"\b)")
    for i, ln in enumerate(lines):
        if decl.match(ln) or (ln.startswith("export") and star.match(ln)):
            return ln.strip()[:220], _doc_above(lines, i)
    return "", ""


def build(force: bool = False, **_kw) -> dict:
    """扫 `dist/modules` 建**可检索面**（只追加；`force=False` 时已有就不重扫）。"""
    if not _INDEX_JS.is_file():
        return {"ok": False, "status": "needs_dependency", "missing": [str(_INDEX_JS)],
                "note": "引擎不在盘 ⇒ 先按七步法第 1 步落位（git clone --depth 1）"}
    idx = _index_path()
    if idx.is_file() and not force:
        items = _load()
        return {"ok": True, "reused": True, "rows": len(items), "index": str(idx),
                "note": "索引已在；要重扫给 force=true"}
    api = _parse_public_api()
    if not api:
        return {"ok": False, "error": "index.js 一条导出都解不出 ⇒ 不写空库（fail-closed）"}
    pkg = _pkg()
    rows = []
    for a in api:
        if a["ns"]:
            rows.append({"name": a["name"], "module": a["name"], "sub": "", "kind": "namespace",
                         "def": "dist/modules/index.js", "line": a["line"], "sig": "",
                         "doc": "命名空间：`%s`（由 `%s` 汇总再导出）" % (a["name"], a["from"] or "?")})
            continue
        rel = _rel(a["from"])
        line, kind = _declare(rel, a["local"])
        sig, doc = _sig_dts(rel, a["local"])
        parts = rel.split("/")
        rows.append({"name": a["name"], "module": parts[0], "sub": "/".join(parts[1:-1]),
                     "kind": kind or "export", "def": "dist/modules/" + rel, "line": line,
                     "sig": sig, "doc": doc, "alias_of": (a["local"] if a["local"] != a["name"] else "")})
    with idx.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "motion_kit_index",
                             "src": "_upstream/anime", "pkg": {"name": pkg.get("name"),
                             "version": pkg.get("version"), "license": pkg.get("license")},
                             "count": len(rows), "items": rows}, ensure_ascii=False) + "\n")
    mods: dict = {}
    for r in rows:
        mods[r["module"]] = mods.get(r["module"], 0) + 1
    return {"ok": True, "indexed": len(rows), "modules": mods,
            "with_sig": sum(1 for r in rows if r["sig"]),
            "with_doc": sum(1 for r in rows if r["doc"]),
            "with_def_line": sum(1 for r in rows if r["line"]),
            "version": pkg.get("version"), "index": str(idx)}


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
    """df 与打分**共用同一份字段**（上一刀踩过：两处口径不一致 ⇒ 假结论）。"""
    return {"name": r.get("name") or "", "module": "%s %s" % (r.get("module") or "", r.get("sub") or ""),
            "doc": r.get("doc") or "", "sig": r.get("sig") or ""}


_WORD_SPLIT = re.compile(r"([a-z0-9])([A-Z])")
_WORD = re.compile(r"[a-z0-9]+")


def _words(s) -> set:
    """英文标识符拆词（**camelCase 要拆**：`onScroll`→{on,scroll}、`createMotionPath`→{create,motion,path}）。

    🔴 2026-10-13 实测：纯字符 2-gram 打分对**英文 API 名**太糊 —— `滚动动画`（桥出 `scroll`）
    会把 `JSAnimation` 顶到第一位（因为它与 `animate/animation` 共享 `an/im/ma` 等 gram）。
    标识符是**词**组成的，就该按词算：`scroll` 精确命中的是 `onScroll`/`ScrollObserver`。
    """
    return set(_WORD.findall(_WORD_SPLIT.sub(r"\1 \2", str(s)).lower()))


def _allwords(r: dict) -> set:
    out: set = set()
    for v in _fields(r).values():
        out |= _words(v)
    return out


def find(q: str = "", limit: int = 8, module: str = "", **_kw) -> dict:
    """人话 → **该用哪个 API**（带签名与 `文件#L行号`）。**命中 0 就如实报 0**。"""
    items = _load()
    if not items:
        return {"ok": False, "status": "needs_build", "error": "索引不在 ⇒ 先 op=build"}
    from ..semantic_route import grams
    qs = str(q or "")
    bridge = [cn for cn in _CN_BRIDGE if cn in qs.lower()]     # 中文口语 → 英文关键词
    qtext = " ".join([qs] + [_CN_BRIDGE[cn] for cn in bridge])
    qg = grams(qtext) if qtext.strip() else set()
    qw = _words(qtext)
    n = max(1, len(items))
    # 两套频次都**只统计一次/行**（df 与打分共用同一份字段 —— 上一刀踩过的口径打架）
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
    w = {"name": 2.5, "module": 1.2, "doc": 1.2, "sig": 0.6}
    _WORD_W = 4.0                       # 词级命中的权重（精确词比 2-gram 值钱得多）
    out = []
    for r in items:
        if module and r["module"].lower() != str(module).lower():
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
        out.append({**r, "score": round(s, 3), "why": why,
                    "where": "%s#L%d" % (r["def"], r["line"]) if r["line"] else r["def"]})
    out.sort(key=lambda r: -r["score"])
    return {"ok": True, "q": q, "hits": len(out), "items": out[:int(limit)], "indexed": len(items),
            "bridge": bridge,
            "_口径": "打分 = Σ(字段权重 × gram-idf)[名 2.5 · 模块 1.2 · 说明 1.2 · 签名 0.6]"
                     " + 4.0 × Σ(词-idf)[camelCase 拆词后的**精确词**命中]；"
                     "中文口语经**桥**扩成英文关键字（`找桥` 列出来）；**命中 0 就是 0**（不硬塞）"}


def api(name: str = "", **_kw) -> dict:
    """按**准确 API 名**取一条（含签名/说明/出处）。**名字对不上就是 0**。"""
    if not str(name or "").strip():
        return {"ok": False, "fail_closed": True, "error": "要 name（用 op=find 拿候选名）"}
    items = _load()
    if not items:
        return {"ok": False, "status": "needs_build", "error": "索引不在 ⇒ 先 op=build"}
    nm = str(name).strip()
    hit = [r for r in items if r["name"] == nm] or [r for r in items if r["name"].lower() == nm.lower()]
    return {"ok": True, "name": name, "hits": len(hit),
            "items": [{**r, "where": "%s#L%d" % (r["def"], r["line"]) if r["line"] else r["def"]}
                      for r in hit]}


_PROBE_JS = r"""
const A = await import('__ENTRY_URL__');
const names = Object.keys(A).sort();
const r = {
  exports: names.length, names,
  calc: { clamp: A.clamp(5, 0, 3), lerp: A.lerp(0, 10, 0.25), mapRange: A.mapRange(5, 0, 10, 0, 100),
          round: A.round(1.2345, 2), degToRad180: A.degToRad(180), snap: A.snap(1.234, 0.5),
          wrap: A.wrap(7, 0, 5) },
  kinds: { animate: typeof A.animate, createTimeline: typeof A.createTimeline,
           createTimer: typeof A.createTimer, createSpring: typeof A.createSpring,
           stagger: typeof A.stagger, utils: typeof A.utils, easings: typeof A.easings },
  ns: { utils: Object.keys(A.utils || {}).length, easings: Object.keys(A.easings || {}).length,
        svg: Object.keys(A.svg || {}).length, text: Object.keys(A.text || {}).length }
};
console.log(JSON.stringify(r));
"""


def prove(timeout: int = 90, **_kw) -> dict:
    """**本机原生真跑**：Node 直接 `import` 吞来的引擎，真算几条纯函数 + 拿运行时导出数咬索引条数。"""
    node = shutil.which("node")
    if not node:
        return {"ok": False, "status": "needs_dependency", "missing": ["node"],
                "note": "本机没有 node ⇒ 原生真跑做不了（**如实报**，不假装跑过）"}
    if not _INDEX_JS.is_file():
        return {"ok": False, "status": "needs_dependency", "missing": [str(_INDEX_JS)]}
    script = _PROBE_JS.replace("__ENTRY_URL__", _INDEX_JS.as_uri())
    try:
        p = subprocess.run([node, "--input-type=module", "-e", script],
                           capture_output=True, timeout=timeout)
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    out = (p.stdout or b"").decode("utf-8", "replace").strip()
    err = (p.stderr or b"").decode("utf-8", "replace")[-300:]
    try:
        got = json.loads(out.splitlines()[-1]) if out else {}
    except Exception:                                        # noqa: BLE001
        got = {}
    items = _load()
    rt = got.get("exports")
    res = {"ok": bool(p.returncode == 0 and got), "rc": p.returncode, "node": shutil.which("node"),
           "engine": _INDEX_JS.as_uri(), "exports_runtime": rt,
           "exports_indexed": (len(items) or None), "consistent": (rt == len(items)) if items else None,
           "calc": got.get("calc"), "kinds": got.get("kinds"), "ns": got.get("ns"),
           "sec": None, "err": err,
           "_口径": "ok = Node **真跑通**且解出 JSON；`consistent` = 运行时导出数 与 索引条数 **咬得上**"
                    "（两处真相对不上 ⇒ 索引过期或解析漏了，宁可红）；真值在 calc/kinds 里"}
    return res


def status(**_kw) -> dict:
    pkg = _pkg()
    items = _load()
    return {"ok": True, "op": "status", "kind": "motion_kit", "src": str(_SRC),
            "src_present": _SRC.is_dir(), "entry": str(_INDEX_JS.relative_to(_ROOT)),
            "engine": pkg.get("name"), "version": pkg.get("version"), "license": pkg.get("license"),
            "node": shutil.which("node"), "indexed": len(items),
            "ops": list(_OPS),
            "_口径": "素材 = juliangarnier/anime（**MIT** · animejs v4.5.0）；"
                     "本件**零出网 + 只读上游**；`prove` 只在本机原生跑引擎算纯函数"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "motion_kit",
            "entry": "run_task('motion_kit', {'op':'find','q':'弹跳的按钮'})", "ops": list(_OPS),
            "what": "把人话接到 anime.js 的真 API 上（名 + 签名 + `文件#L行号`），并**本机原生真跑**证明引擎可用",
            "读这一节的规矩": "命中项给 `dist/modules/...#L行号`；要读**原始可读源码**看 `_upstream/anime/src/**`（同结构）",
            "hard_rules": ["零出网 · 零执行上游脚本（只 import 引擎本体算纯函数）",
                           "不改 `_upstream/anime/**` 一个字节",
                           "签名/说明只从 `.d.ts` 现读，取不到留空（不编）",
                           "df 与打分共用同一份字段（防口径打架）"],
            "上游": "juliangarnier/anime（MIT · ★73546 · animejs v4.5.0 · 67 导出）",
            "下游": "design_atlas（该学哪一节）· ui_kit（挑哪件组件）· art_chain（出作品）· render_page.py（真渲）"}


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    for nm, fn in (("status", status), ("build", build), ("find", find), ("api", api),
                   ("prove", prove), ("where", where)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":                                   # 主人的终端入口
    import argparse
    import sys
    try:                        # 本机控制台默认 GBK ⇒ 中文/`⇒` 直接打会 UnicodeEncodeError
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                    # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="动效引擎的口（人话 → anime.js 真 API）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}")
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
