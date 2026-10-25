"""未验分支猎手（只读）—— 「诚实读数」的那些分支，**到底有没有被控制走到过**。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它
§一百五十八 逮到一条真雷：`shorts-stitch-proof.py` 里"取不到读数时报真因"的分支**写了从没触发**，
真触发即 `NameError`。**「写了没触发过」= 没验过**，而这类分支平时都不响：
`run` 一直绿 ⇒ 永远不会有人看它。
这种读数在本仓满地都是（现读 `tools/codex-scripts/`：**24 件**带「未读到/取不到/未接线」字样）。

## 它怎么量（一句话）
**把每条「诚实读数」的措辞，拿去自检函数里找** ——
找不到 ⇒ 列进**候选**（疑似从未被控制走到）；找得到 ⇒ 至少有一处自检提过它。

## 🔴 它量不了什么（先说清楚，免得把候选当成判决）
- 自检**可以间接覆盖**：`ck(…, "未读到" in out)` 这种断言**确实走到了**那条分支，
  但它不会出现那句原话 ⇒ 本工具仍会把它列为候选。**候选 ≠ 未验，必须人核**，
  人核后确认是"间接覆盖"的，就 `settle --note <原因>` 记下来（**没原因的重立 = 隐藏回退**）。
- 取材只按**字面量**：拼接出来的读数（`"**未读到**" + x`）识别不到 ⇒ 会漏。
- 口径是 **候选清单 + 每件"自检里有没有『未读到』这三个字"**，**不是判决**。

用法：
  python tools/codex-scripts/honest-branch-audit.py scan [--roots tools/codex-scripts] [--json]
  python tools/codex-scripts/honest-branch-audit.py selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOTS = ("tools/codex-scripts",)
BASE = ROOT / "state" / "honest-branch-baseline.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 🔴 单一来源：诚实读数的**标记词**只在这里列一次（空表 = 拒绝，见 selftest ⑤）
MARKERS = ("未读到", "取不到", "查不到真因", "未接线", "needs_dependency", "不可比对", "读不出来")
# 清掉标记词后还不剩这个长度 ⇒ 这条读数**没有特征字样**，本工具判不了（进"需人核"桶，不许静默丢）
MIN_FRAG = 6
_SELFTEST_DEF = re.compile(r"^def (cmd_)?selftest\s*\(", re.M)
_TOP_DEF = re.compile(r"^def ", re.M)
_STRIP = re.compile(r"[*`\[\]（）()【】「」『』：:，,。、；;!！?？\s\-—=+~>|'\"\\]+")


def _selftest_span(src: str) -> tuple[int, int] | None:
    """自检函数的**字符区间**：从 `def selftest(` / `def cmd_selftest(` 到下一个顶层 `def`。

    自检没写在函数里（散在 `if __name__` 下）的件，本工具**如实报"没找到自检"**，不猜。
    """
    m = _SELFTEST_DEF.search(src)
    if not m:
        return None
    nxt = _TOP_DEF.search(src, m.end())
    return (m.start(), nxt.start() if nxt else len(src))


def _clean(text: str) -> str:
    """把一条读数压成"特征字样"：去占位符与修饰符，**保留标记词本身**。

    🔴 第一版把标记词也去掉了 ⇒ 指纹长成 `基线内容⇒拒` 这种**没人会自然写出来**的样子，
    控制里明明写了「未读到基线内容」也匹配不上（假候选变多）。
    **标记词才是特征** —— 保留它，指纹才认得出"这条读数说的是哪件事"。
    """
    t = re.sub(r"%[sdrf]", "", text)
    return _STRIP.sub("", t)


def _off(src: str, node) -> int:
    """AST 节点在源码里的字符偏移。"""
    lines = src.splitlines(keepends=True)
    return sum(len(x) for x in lines[:node.lineno - 1]) + node.col_offset


def _docstring_ids(tree) -> set:
    """所有 **docstring** 节点的 id（模块/函数/类的第一句字符串）——
    它们是**文档**，不是"分支读数"，混进候选只会把清单淹掉。"""
    ids = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None) or []
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            ids.add(id(body[0].value))
    return ids


def scan_text(src: str, markers=MARKERS, max_len: int = 120) -> dict:
    """**只吃文本**（好上负控）。返回候选 / 已见控制 / 判不了的 / 长文本 / 自检区间。"""
    if not markers:
        raise ValueError("**标记词表是空的 = 拒绝**（空表不许念成『没有未验分支』）")
    span = _selftest_span(src)
    sel_txt = src[span[0]:span[1]] if span else ""
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"解析失败": "第 %s 行：%s" % (exc.lineno, exc.msg)}
    docids = _docstring_ids(tree)
    cand, seen, vague, blob = [], [], [], 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        lit = node.value
        if not any(mk in lit for mk in markers):
            continue
        if id(node) in docids:                      # 文档串：不算分支，静默跳过（已单列口径）
            continue
        if len(lit) > max_len:                      # 长文（HTML/帮助串/清单）：单独计数
            blob += 1
            continue
        # 🔴 自检区间**里面**的字面量是控制自己写的措辞，不算"未验分支"
        if span and span[0] <= _off(src, node) < span[1]:
            continue
        frag = _clean(lit)
        row = {"行": node.lineno, "读数": lit[:56], "特征字样": frag[:18]}
        if len(frag) < MIN_FRAG:
            row["为什么判不了"] = "清掉标记词后只剩 %d 个实义字（无特征字样）" % len(frag)
            vague.append(row)
        elif frag in sel_txt:
            seen.append(row)
        else:
            cand.append(row)
    return {"候选": cand, "已见控制": seen, "无特征字样": vague, "长文本（不算读数）": blob,
            "有自检函数": span is not None,
            "自检里提到标记词吗": (bool(sel_txt) and any(mk in sel_txt for mk in markers))}


def scan_file(path: Path) -> dict:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:                       # 🔴 读不开就写「未读到」，不拿空源当"没有候选"
        return {"文件": path.name, "**未读到**": "读不开：%s" % str(exc)[:60]}
    r = scan_text(src)
    if "解析失败" in r:
        return {"文件": path.name, "读不了": r["解析失败"]}
    return {"文件": path.name, "候选数": len(r["候选"]), "无特征字样数": len(r["无特征字样"]),
            "长文本（不算读数）": r["长文本（不算读数）"],
            "有自检函数": r["有自检函数"], "自检里提到标记词吗": r["自检里提到标记词吗"],
            "候选": r["候选"], "无特征字样": r["无特征字样"]}


def _scan_rows(roots: list[str]) -> tuple[list[dict], list[str], int]:
    rows, skipped = [], []
    for rel in roots:
        base = ROOT / rel
        if not base.is_dir():
            skipped.append(rel)
            continue
        for p in sorted(base.glob("*.py")):
            if p.name.startswith("_"):
                continue
            r = scan_file(p)
            if r.get("候选数") or r.get("无特征字样数"):
                rows.append(r)
    rows.sort(key=lambda r: (-r.get("候选数", 0), r["文件"]))
    total = sum(r.get("候选数", 0) for r in rows)
    return rows, skipped, total


def _fps(rows: list[dict]) -> list[str]:
    """候选的**指纹**（文件|特征字样）—— 按指纹对差，**改措辞不会造成假差异**。"""
    return sorted("%s|%s" % (r["文件"], c["特征字样"]) for r in rows for c in r.get("候选", []))


def cmd_scan(roots: list[str], as_json: bool) -> int:
    rows, skipped, total = _scan_rows(roots)
    no_sel = [r["文件"] for r in rows if not r.get("有自检函数")]
    out = {"口径": "**候选清单，不是判决** —— 自检可以间接覆盖（断言输出里有没有『未读到』），"
           "所以候选必须人核；拼接出来的读数本工具识别不到",
           "扫到带诚实读数的文件": len(rows), "候选合计": total,
           "没有自检函数的件": no_sel, "跳过的根": skipped, "逐件": rows}
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("候选合计 %d ｜ 带诚实读数的文件 %d ｜ 其中没有自检函数的 %d 件"
              % (total, len(rows), len(no_sel)))
        for r in rows:
            print("  %-30s 候选 %-3d 无特征 %-2d 自检=%s 自检提过标记词=%s"
                  % (r["文件"], r.get("候选数", 0), r.get("无特征字样数", 0),
                     r.get("有自检函数"), r.get("自检里提到标记词吗")))
            for c in r["候选"][:3]:
                print("      L%-4d %s" % (c["行"], c["读数"]))
    return 0


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except Exception:
        return str(p)


def gate_or_settle(roots: list[str], note: str | None,
                   base: Path | None = None) -> tuple[int, dict]:
    """**只算不打印**：`settle`（带 note，立基线）或 `gate`（候选不许变多）。

    返回 `(rc, 读数字典)`。读数带 **`类别`** 字段（`未立基线` / `未读到基线内容` / `基线缺字段` /
    `变坏` / `没变好也没变坏`）—— **判据建在结构上，不建在打印出来的文本上**
    （第一版控制写的是 `"未立基线" in txt`，被台架 D2/D6 判成文本判据，**判得对**）。

    `base` 可注入 ⇒ 那几条拒法分支才能被控制真触发（否则只能靠真基线坏掉才走到）。
    """
    base = base or BASE
    rows, _, total = _scan_rows(roots)
    fps = _fps(rows)
    if note is not None:                              # settle
        if not note.strip():
            return 2, {"ok": False, "类别": "未写原因",
                       "拒绝": "**重立基线必须写原因**（没原因的重立 = 隐藏回退）"}
        base.parent.mkdir(parents=True, exist_ok=True)
        base.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "候选合计": total, "指纹": fps, "原因": note},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        return 0, {"ok": True, "类别": "已立基线", "立基线": {"候选合计": total},
                   "原因": note, "落盘": _rel(base)}
    if not base.is_file():
        return 2, {"类别": "未立基线", "判决": "🔴 **未立基线** ⇒ 不许念成合格（先 `settle --note <原因>`）",
                   "现候选合计": total, "基线文件": _rel(base)}
    try:
        b = json.loads(base.read_text(encoding="utf-8"))
    except Exception as exc:                          # 🔴 读不开/读不成 JSON ⇒ 拒
        return 2, {"类别": "未读到基线内容", "判决": "🔴 **未读到基线内容**（%s）⇒ 拒" % str(exc)[:60]}
    lack = [k for k in ("指纹", "候选合计", "at") if k not in b]
    if lack:                                          # 🔴 缺字段 ⇒ 拒，不拿缺字段的当基准
        return 2, {"类别": "基线缺字段", "缺": lack,
                   "判决": "🔴 **基线里未读到 %s** ⇒ 拒（缺字段的基线不算基准）" % lack}
    before, old = set(b["指纹"]), b["候选合计"]
    new = [f for f in fps if f not in before]
    return (0 if not new else 1), {
        "类别": "没变坏" if not new else "变坏",
        "基线": b["at"], "基线候选": old, "现候选": total,
        "新增候选（按指纹对差）": new[:12], "新增条数": len(new),
        "判决": ("✅ 没有变坏（候选没变多）" if not new else
               "🔴 **多出 %d 条候选**（新写的诚实读数没被控制走到）⇒ 补控制，或 `settle --note` 说明为什么"
               % len(new))}


def cmd_gate(roots: list[str], note: str | None, base: Path | None = None) -> int:
    rc, d = gate_or_settle(roots, note, base)
    print(json.dumps(d, ensure_ascii=False, indent=1))
    return rc


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # 合成源码：① 只在正文的诚实读数 ② 正文里但自检提过的那条 ③ 普通路径字符串 ④ 一条自检
    BASE = (
        "def probe():\n"
        "    try:\n"
        "        raise RuntimeError('x')\n"
        "    except Exception:\n"
        "        return '**未读到**（comfy-surface 读不出来：%s）'\n"
        "\n"
        "def probe2():\n"
        "    return '**未读到**内存条不拿上次的顶替'\n"
        "\n"
        "def other():\n"
        "    return 'outputs/shorts-stitch/shorts.mp4'\n"
        "\n"
        "def selftest():\n"
        "    ck('已验的那条', True, '未读到内存条不拿上次的顶替')\n"
        "    return 0\n"
    )
    r = scan_text(BASE)
    ck("**正控：只在正文出现的诚实读数 ⇒ 列为候选**",
       any("comfy" in c["特征字样"] for c in r["候选"]), "候选 %d 条" % len(r["候选"]))
    ck("**负控：自检里提过措辞的那条 ⇒ 不许列为候选**",
       len(r["已见控制"]) == 1 and all("内存现读" not in c["读数"] for c in r["候选"]),
       "已见控制 %d 条 ｜ 候选 %d 条" % (len(r["已见控制"]), len(r["候选"])))
    ck("**负控：普通字符串（路径/键名）不许进候选**",
       all("outputs/" not in c["读数"] for c in r["候选"]), "")
    # ④ 边界：没有自检函数 ⇒ 如实报"没找到自检"，读数仍进候选（不许念成"全都验过"）
    r2 = scan_text("def probe():\n    return '**未读到**（没有自检的件里读不出来）'\n")
    ck("**边界：没有自检函数 ⇒ 如实报没找到，读数仍进候选**",
       r2["有自检函数"] is False and len(r2["候选"]) == 1,
       "有自检=%s 候选=%d" % (r2["有自检函数"], len(r2["候选"])))
    # ⑤ 边界：标记词表空 ⇒ **拒绝**（空表不许念成"没有未验分支"）
    try:
        scan_text(BASE, markers=())
        ck("**边界：标记词表空 ⇒ 拒绝**", False, "居然没拒")
    except ValueError as exc:
        ck("**边界：标记词表空 ⇒ 拒绝**", "拒绝" in str(exc), str(exc)[:44])
    # ⑥ 边界：没有特征字样的读数 ⇒ 进「需人核」，**不许静默丢**
    r3 = scan_text("def probe():\n    return '**未读到**'\n")
    ck("**边界：无特征字样的读数 ⇒ 进『需人核』桶，不许静默丢**",
       len(r3["候选"]) == 0 and len(r3["无特征字样"]) == 1,
       "无特征 %d 条" % len(r3["无特征字样"]))
    # ⑦ 边界：语法坏掉的件 ⇒ 如实报"读不了"，不许整件静默消失
    r4 = scan_text("def broken(:\n")
    ck("**边界：语法坏掉的件 ⇒ 如实报『读不了』**", "解析失败" in r4, str(r4.get("解析失败"))[:44])
    # ⑦b 边界：**docstring 不算分支读数**（否则文档会把候选清单淹掉）
    DOC = ("def probe():\n"
           "    return 1\n")
    DOCD = ('"""**未读到**：这是模块文档，不是分支读数。"""\n' + DOC)
    r5 = scan_text(DOCD)
    ck("**边界：docstring 不算分支读数**（文档不许进候选）",
       len(r5["候选"]) == 0, "候选 %d 条" % len(r5["候选"]))
    # ⑦c 边界：长文（HTML/帮助串）单列计数，不混进候选
    LONG = "def probe():\n    return '%s'\n" % ("**未读到**" + "长" * 200)
    r6 = scan_text(LONG)
    ck("**边界：长文单列计数，不混进候选**",
       len(r6["候选"]) == 0 and r6["长文本（不算读数）"] == 1,
       "长文本 %d 条" % r6["长文本（不算读数）"])
    # ⑧ 现读真件：本工具自己 + 上一轮逮到雷的那件，都扫得动
    live = [scan_file(ROOT / "tools/codex-scripts" / n)
            for n in ("shorts-stitch-proof.py", "honest-branch-audit.py", "ledger-append.py")]
    ck("**现读真件扫得动**（不许因解析失败整件丢掉）",
       all("读不了" not in x for x in live), "扫了 %d 件" % len(live))
    # ⑨–⑭ 棘轮本身（基线可注入 ⇒ 四条拒法 + 一条"会咬"全都能真触发）
    #    🔴 判据建在**结构**上（`类别`/`ok`/`缺` 字段），不建在打印出来的文本上：
    #       第一版写的是 `"未立基线" in txt`，被台架 D2/D6 判成文本判据 —— **判得对**。
    import tempfile as _tf

    with _tf.TemporaryDirectory() as tds:
        bd = Path(tds) / "base.json"
        tdir = Path(tds) / "tools"
        tdir.mkdir()
        (tdir / "one.py").write_text("def f():\n    return '**未读到**（临时靶里的诚实读数甲）'\n",
                                     encoding="utf-8")
        roots = [str(tdir)]
        rc, d = gate_or_settle(roots, None, bd)
        ck("**棘轮：没立基线 ⇒ rc=2（不许念成合格）**",
           rc == 2 and d.get("类别") == "未立基线", "类别=%s rc=%d" % (d.get("类别"), rc))
        rc, d = gate_or_settle(roots, "   ", bd)
        ck("**棘轮：settle 不写原因 ⇒ rc=2**（没原因的重立 = 隐藏回退）",
           rc == 2 and d.get("类别") == "未写原因", "类别=%s" % d.get("类别"))
        rc, d = gate_or_settle(roots, "自检用：临时靶首立基线", bd)
        ck("**棘轮：正常 settle ⇒ rc=0 且基线落盘**",
           rc == 0 and d.get("类别") == "已立基线" and bd.is_file(),
           "类别=%s 落盘=%s" % (d.get("类别"), bd.is_file()))
        bd.write_text("这不是 json", encoding="utf-8")
        rc, d = gate_or_settle(roots, None, bd)
        ck("**棘轮：基线不是 JSON ⇒ rc=2 且类别=未读到基线内容**",
           rc == 2 and d.get("类别") == "未读到基线内容", "类别=%s" % d.get("类别"))
        bd.write_text(json.dumps({"at": "x"}, ensure_ascii=False), encoding="utf-8")
        rc, d = gate_or_settle(roots, None, bd)
        ck("**棘轮：基线缺字段 ⇒ rc=2 且点名缺哪几个**",
           rc == 2 and d.get("类别") == "基线缺字段" and "指纹" in (d.get("缺") or []),
           "缺=%s" % d.get("缺"))
        gate_or_settle(roots, "自检用：再立一次基线", bd)
        (tdir / "two.py").write_text("def g():\n    return '**未读到**（新写的、没人验过的读数乙）'\n",
                                     encoding="utf-8")
        rc, d = gate_or_settle(roots, None, bd)
        ck("**棘轮：新增未验读数 ⇒ rc=1 且类别=变坏**",
           rc == 1 and d.get("类别") == "变坏" and d.get("新增条数") == 1,
           "类别=%s 新增=%s" % (d.get("类别"), d.get("新增条数")))

    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan", "gate", "settle", "selftest"])
    ap.add_argument("--roots", default=",".join(DEFAULT_ROOTS))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--note", help="settle 专用：这次为什么重立基线（**必写**）")
    a = ap.parse_args()
    roots = [x.strip() for x in a.roots.split(",") if x.strip()]
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "scan":
        return cmd_scan(roots, a.json)
    if a.cmd == "settle":
        return cmd_gate(roots, a.note if a.note is not None else "")
    return cmd_gate(roots, None)


if __name__ == "__main__":
    raise SystemExit(main())
