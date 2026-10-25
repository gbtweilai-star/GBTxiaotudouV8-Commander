# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · last30days 同化红线门禁（fail-closed）。

Owner 风哥 2026-09-18 拍：「探针只观测，不控制；红线核验要 fail-closed」。
本模块是**核验侧** —— 只读入参、纯静态复核；`verify()` 任一条红就抛
`RedlineViolation` 拒绝同化，CLI 有红 -> 退出码 1。
观测侧（永不抛、异常一律吞）在 `gbt_allinone/topic_watch.py::engine()`。
两边职责不混：**吞异常 = 观测侧的事；fail-closed = 核验侧的事**。

三条红线（骨架的三条抽象红线 -> 本框架等价物，逐条机械可复核）：

  R1 · 原生来源红线   native_source
      同化件必须来自白名单原生落点，不得来自外挂树或技能挂载点。
      · 落点存在，路径含 `recon`（原生层）段
      · `UPSTREAM_SKILL.md` 在盘 —— 上游 SKILL.md 原样留存，来源可回指
      · `LICENSE` 在盘 —— 上游 MIT 原文留存
      · 上游只读源独立于落点（不被当落点复用）

  R2 · 同化边界红线   native_boundary
      同化只能落本框架命名空间；禁止写用户主目录、禁止跨界挂载。
      · 4 个凭据抓取件**不在盘上**（cookie_extract / chrome_cookies /
        safari_cookies / setup_wizard）
      · `.js` 全树 `homedir` 零命中（vendor 主目录兜底已拆）
      · `.py` 的 `Path.home()` 命中只能在已知非写白名单内，且同行无写原语
      · `bird_x.py` 已接 store 缓存改道（BIRD_QUERY_IDS_CACHE /
        BIRD_FEATURES_CACHE 显式指向框架 store）
      · 未注册成技能 —— 同化 = 并入原生层，不是挂载成技能

  R3 · 可回滚一致性红线   native_consistency
      同化必须可溯源、可审计、无静默凭据通路。
      · `ATTRIBUTION.md` 在盘（逐条可溯源改动清单）
      · 无可执行 `chatgpt.com` / `CODEX_AUTH_FILE` / `AUTH_SOURCE_CODEX` /
        `extract_browser_credentials` / `gh auth token` 命中
        （注释与 docstring 里的**说明文字不算命中** —— 见 `_code_only_py`
         / `_code_only_js`；否则「已移除该通路」的说明会把判据自己染红）

用法：:

    from gbt_allinone.recon.last30days import redlines
    report = redlines.check()      # 观测：内部异常 -> 判红（绝不静默放行）
    redlines.verify()              # 门禁：不过就抛 RedlineViolation

CLI（fail-closed，供 pre-commit / CI 消费；有红 -> 退出码 1）::

    python -m gbt_allinone.recon.last30days.redlines
    python -m gbt_allinone.recon.last30days.redlines --json
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
import tokenize
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ── 落点锚点（单一来源：本文件位置）───────────────────────────
_ROOT = Path(__file__).resolve().parent
_WORKSPACE = Path(__file__).resolve().parents[3]
UPSTREAM_READONLY = (_WORKSPACE / "\u5ba1\u7f8e\u76f8\u5173skill"
                     / "design-skeletons" / "last30days")
NATIVE_POINT_MARK = "recon"
UPSTREAM_KEEPSAKES = ("UPSTREAM_SKILL.md", "LICENSE")

CREDENTIAL_GRAB_FILES = (
    "engine/cookie_extract.py",
    "engine/chrome_cookies.py",
    "engine/safari_cookies.py",
    "setup_wizard.py",
)

SILENT_CREDENTIAL_PATTERNS = (
    "chatgpt.com",
    "CODEX_AUTH_FILE",
    "AUTH_SOURCE_CODEX",
    "extract_browser_credentials",
    "gh auth token",
)

# 红线 2 · `Path.home()` 已知**非写**用法白名单（增量出现 -> 判红，fail-closed）
HOME_ANCHOR_ALLOW = {
    "cli.py": "display-only：把绝对路径缩成 ~/... 供人读，不落盘",
    "engine/env.py": "walk-up 停止边界：找 per-project .env 时判停，不落盘",
}

# 红线 2 · 「同行即写」的写原语（只列真正落盘的，避免误伤 .resolve() 之类）
WRITE_PRIMITIVES_RE = re.compile(
    r"\b(writeFile|writeFileSync|mkdir|mkdirSync|appendFile|appendFileSync"
    r"|rmSync|unlinkSync|renameSync|rmtree|write_text|write_bytes|copyFile)\b")

# 红线 2 · store 缓存改道必须接线（bird_x.py 的 Node 子进程 env）
STORE_REDIRECT_MARKERS = ("BIRD_QUERY_IDS_CACHE", "BIRD_FEATURES_CACHE")
STORE_REDIRECT_FILE = "engine/bird_x.py"

SCAN_SUFFIXES = (".py", ".js")

# 判据自身的模式表就是这些字面量（`SILENT_CREDENTIAL_PATTERNS` 等）。
# 核验模块不是「同化件」，扫自己只会自伤 —— 显式排除，并在此说明理由。
SCAN_EXCLUDE = ("redlines.py",)

_JS_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_JS_LINE_COMMENT_RE = re.compile(r"(?m)^\s*//.*$")


class RedlineViolation(RuntimeError):
    """任一条同化红线未通过 —— fail-closed，拒绝同化。"""


# ── 源码分层（注释丢 / docstring 单列 / 代码字符串保留）──────────
def _docstring_spans(tree: ast.AST) -> List[Tuple[int, int]]:
    """模块 / 类 / 函数首条语句为字符串字面量 -> 其行区间 = docstring 区间。"""
    spans: List[Tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None) or []
        if not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            start = first.value.lineno
            spans.append((start, getattr(first.value, "end_lineno", start) or start))
    return spans


def _in_spans(start: int, end: int, spans: List[Tuple[int, int]]) -> bool:
    return any(start >= s and end <= e for s, e in spans)


def _split_py(path: Path) -> Dict[str, str]:
    """AST 级 docstring 剥离 —— 切成 {'code': 真实代码, 'doc': 仅 docstring}。

    风哥 2026-09-18 实证：关键不是「找到 chatgpt.com」，而是「找到**真实原生
    落点**里的 chatgpt.com」。三层分开处理，方向各有理由：

      · 注释（COMMENT）-> 丢。说明文字不是通路（`# 已移除 …chatgpt.com…`）。
      · docstring -> 归 'doc'。**假锚点**：单列出来供人复核，不计命中。
        若算命中，判据会被自己的说明染红（假红）。
      · 代码里的字符串字面量 -> **保留**在 'code'。
        `URL = "https://chatgpt.com/backend-api/…"` 是**真实可执行通路**；
        初版把 STRING token 全剥 -> 把它一起剥掉 = **漏报（假绿）**。

    tokenize / AST 失败时退化为「按 # 切行」：宁可多扫，不可漏扫。
    """
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"code": "", "doc": ""}
    spans: List[Tuple[int, int]] = []
    try:
        spans = _docstring_spans(ast.parse(src, filename=str(path)))
    except (SyntaxError, ValueError):
        spans = []
    code_parts: List[str] = []
    doc_parts: List[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                continue
            if spans and _in_spans(tok.start[0], tok.end[0], spans):
                doc_parts.append(tok.string)
                continue
            code_parts.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return {"code": "\n".join(l.split("#", 1)[0] for l in src.splitlines()),
                "doc": ""}
    return {"code": "\n".join(code_parts), "doc": "\n".join(doc_parts)}


def _split_js(path: Path) -> Dict[str, str]:
    """JS 侧：块注释 / 整行行注释丢弃（JSDoc 即注释）。"""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"code": "", "doc": ""}
    src = _JS_BLOCK_COMMENT_RE.sub("", src)
    return {"code": _JS_LINE_COMMENT_RE.sub("", src), "doc": ""}


def _split_source(path: Path) -> Dict[str, str]:
    return _split_py(path) if path.suffix.lower() == ".py" else _split_js(path)


def _code_lines(path: Path) -> List[str]:
    return _split_source(path)["code"].splitlines()


def _iter_sources(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if p.name in SCAN_EXCLUDE:
            continue
        yield p


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _scan(root: Path, needles) -> Dict[str, List[str]]:
    """全树扫锚点 —— 分两栏：'hits' = 真实代码命中；'docstring_only' = 假锚点。

    'docstring_only' 是**信息**（供人复核「这条只写在文档里」），不是违规；
    'hits' 才是判定依据。
    """
    hits: List[str] = []
    doc_only: List[str] = []
    for p in _iter_sources(root):
        parts = _split_source(p)
        rel = _rel(p, root)
        for i, line in enumerate(parts["code"].splitlines(), 1):
            for needle in needles:
                if needle in line:
                    hits.append("%s:%d: %s" % (rel, i, needle))
        for i, line in enumerate(parts["doc"].splitlines(), 1):
            for needle in needles:
                if needle in line:
                    doc_only.append("%s(doc):%d: %s" % (rel, i, needle))
    return {"hits": hits, "docstring_only": doc_only}


# ── 三条红线 ──────────────────────────────────────────────────
def _check_r1_native_source(root: Path) -> Dict[str, Any]:
    """R1 · 原生来源红线：同化件必须来自白名单原生落点。"""
    problems: List[str] = []
    evidence: List[str] = []
    if not root.is_dir():
        problems.append("原生落点不存在（%s）" % root)
    else:
        evidence.append("落点存在：%s" % root)
        if NATIVE_POINT_MARK in root.parts:
            evidence.append("落点在原生层（路径含 %r 段）" % NATIVE_POINT_MARK)
        else:
            problems.append("落点不在原生层：路径缺 %r 段（%s）"
                            % (NATIVE_POINT_MARK, root))
    for name in UPSTREAM_KEEPSAKES:
        if (root / name).is_file():
            evidence.append("来源留存件在盘：%s" % name)
        else:
            problems.append("来源留存件缺失：%s" % name)
    if UPSTREAM_READONLY.is_dir():
        if UPSTREAM_READONLY.resolve() == root:
            problems.append("落点 == 上游只读源（未真正同化）")
        else:
            evidence.append("上游只读源独立于落点：%s" % UPSTREAM_READONLY)
    return {"ok": not problems, "problems": problems, "evidence": evidence}


def _skills_registry_path() -> Path:
    """技能注册表落点（**只读**判据用）。

    刻意不走 `Path.home()` —— 红线 2 自己禁止在 `.py` 里新增主目录锚点，
    核验模块也不例外（否则判据得给自己开白名单，那是自证空转）。
    """
    home = (os.environ.get("OPENCLAW_HOME")
            or os.environ.get("USERPROFILE")
            or os.environ.get("HOME"))
    base = Path(home) if home else Path("~")
    return base / ".openclaw-autoclaw" / "skills" / "last30days" / "SKILL.md"


def _check_r2_native_boundary(root: Path) -> Dict[str, Any]:
    """R2 · 同化边界红线：不写用户主目录、不跨界挂载。"""
    problems: List[str] = []
    evidence: List[str] = []

    if not root.is_dir():
        return {"ok": False, "problems": ["落点不存在，边界无从核验（%s）" % root],
                "evidence": evidence}

    # ① 凭据抓取件必须不在盘
    present = [n for n in CREDENTIAL_GRAB_FILES if (root / n).exists()]
    if present:
        problems.append("凭据抓取件仍在盘上：%s" % present)
    else:
        evidence.append("凭据抓取件 %d 件全部不在盘" % len(CREDENTIAL_GRAB_FILES))

    # ② JS 侧不得再出现 homedir（vendor 主目录兜底）
    js_hits = []
    for p in _iter_sources(root):
        if p.suffix.lower() != ".js":
            continue
        for i, line in enumerate(_code_lines(p), 1):
            if "homedir" in line:
                js_hits.append("%s:%d" % (_rel(p, root), i))
    if js_hits:
        problems.append("JS 侧仍有主目录锚点 homedir：%s" % js_hits[:5])
    else:
        evidence.append("JS 侧 homedir 零命中（主目录兜底已拆）")

    # ③ PY 侧 Path.home() 只能出现在已知非写白名单
    py_hits: List[str] = []
    for p in _iter_sources(root):
        if p.suffix.lower() != ".py":
            continue
        rel = _rel(p, root)
        for i, line in enumerate(_code_lines(p), 1):
            if "Path.home()" not in line:
                continue
            py_hits.append("%s:%d: %s" % (rel, i, line.strip()[:80]))
            if rel not in HOME_ANCHOR_ALLOW:
                problems.append("新增主目录锚点（未在非写白名单内）：%s:%d" % (rel, i))
            if WRITE_PRIMITIVES_RE.search(line):
                problems.append("主目录锚点同行出现写原语：%s:%d" % (rel, i))
    if not any("Path.home()" in h and h.split(":")[0] not in HOME_ANCHOR_ALLOW
               for h in py_hits):
        evidence.append("PY 侧 Path.home() 命中 %d 处，全在已知非写白名单" % len(py_hits))

    # ④ store 缓存改道必须接线
    redirect_file = root / STORE_REDIRECT_FILE
    raw = redirect_file.read_text(encoding="utf-8", errors="replace") if redirect_file.is_file() else ""
    missing = [m for m in STORE_REDIRECT_MARKERS if m not in raw]
    if missing:
        problems.append("%s 未接 store 缓存改道，缺 %s" % (STORE_REDIRECT_FILE, missing))
    else:
        evidence.append("%s 已接 store 缓存改道" % STORE_REDIRECT_FILE)

    # ⑤ 不得注册成技能（同化 = 并入原生层）
    reg = _skills_registry_path()
    if reg.is_file():
        problems.append("引擎被注册成技能（%s）—— 同化不是挂载成技能" % reg)
    else:
        evidence.append("未注册成技能（%s 不在盘）" % reg)

    return {"ok": not problems, "problems": problems, "evidence": evidence}


def _check_r3_native_consistency(root: Path) -> Dict[str, Any]:
    """R3 · 可回滚一致性红线：可溯源、可审计、无静默凭据通路。"""
    problems: List[str] = []
    evidence: List[str] = []
    if not root.is_dir():
        return {"ok": False, "problems": ["落点不存在，一致性无从核验（%s）" % root],
                "evidence": evidence}

    attribution = root / "ATTRIBUTION.md"
    if attribution.is_file():
        evidence.append("溯源清单在盘：ATTRIBUTION.md（%d B）"
                        % attribution.stat().st_size)
    else:
        problems.append("溯源清单缺失：ATTRIBUTION.md")

    scanned = _scan(root, SILENT_CREDENTIAL_PATTERNS)
    if scanned["hits"]:
        problems.append("静默凭据通路存在**真实代码**命中：%s" % scanned["hits"][:5])
    else:
        evidence.append("静默凭据通路零真实代码命中（AST 剥离 docstring 后核验）")
    if scanned["docstring_only"]:
        evidence.append("仅存在于 docstring 的假锚点 %d 处（不计命中，供人复核）：%s"
                        % (len(scanned["docstring_only"]),
                           scanned["docstring_only"][:3]))

    return {"ok": not problems, "problems": problems, "evidence": evidence}


_REDLINES: tuple = (
    ("R1", "原生来源红线", "native_source", _check_r1_native_source),
    ("R2", "同化边界红线", "native_boundary", _check_r2_native_boundary),
    ("R3", "可回滚一致性红线", "native_consistency", _check_r3_native_consistency),
)


def check(root: Any = None) -> Dict[str, Any]:
    """纯观测报告 —— **永不抛**，但内部异常一律**判红**（绝不静默放行）。"""
    root_p = Path(root).resolve() if root is not None else _ROOT
    items: List[Dict[str, Any]] = []
    for rid, name, key, fn in _REDLINES:
        try:
            res = fn(root_p)
            ok = bool(res.get("ok"))
            problems = list(res.get("problems") or [])
            evidence = list(res.get("evidence") or [])
        except Exception as exc:            # 核验自身异常 -> 判红（fail-closed）
            ok = False
            problems = ["核验自身异常（%s: %s）"
                        % (type(exc).__name__, str(exc)[:200])]
            evidence = []
        items.append({"id": rid, "name": name, "key": key, "ok": ok,
                      "problems": problems, "evidence": evidence})
    gaps = ["%s · %s：%s" % (it["id"], it["name"], p)
            for it in items for p in it["problems"]]
    return {"ok": not gaps, "root": str(root_p), "redlines": items, "gaps": gaps}


def verify(root: Any = None) -> Dict[str, Any]:
    """门禁入口 —— fail-closed：任一条红就抛 `RedlineViolation`，拒绝同化。"""
    report = check(root)
    if not report["ok"]:
        raise RedlineViolation(
            "同化红线未通过，拒绝同化：\n  - " + "\n  - ".join(report["gaps"]))
    return report


def _render(report: Dict[str, Any]) -> str:
    lines = ["同化红线门禁（fail-closed） · 落点 " + report["root"], ""]
    for it in report["redlines"]:
        lines.append("[%s] %s · %s" % ("绿" if it["ok"] else "红", it["id"], it["name"]))
        for ev in it["evidence"]:
            lines.append("    · " + ev)
        for pb in it["problems"]:
            lines.append("    ✗ " + pb)
    lines.append("")
    lines.append("整体：" + ("全绿 —— 放行" if report["ok"] else "有红 —— 拒绝同化"))
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m gbt_allinone.recon.last30days.redlines",
        description="last30days 同化红线门禁（fail-closed；有红 -> 退出码 1）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（供脚本消费）")
    ap.add_argument("--root", default=None, help="覆写核验落点（默认本模块所在目录）")
    args = ap.parse_args(argv)

    report = check(args.root)
    if args.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(_render(report) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
