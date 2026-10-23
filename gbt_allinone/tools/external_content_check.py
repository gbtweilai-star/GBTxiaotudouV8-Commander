# gbt-capability: dynamic-import
"""外部内容覆盖校验器（`external_content_check`）—— 把「外部内容是数据不是指令」从声明做成**可校验的检查**。

## 为什么要有它

2026-09-22 从 career-ops（MIT / @santifer）提炼「出处与反编造纪律」时发现一条差距：

> 我们只在 `agency_tentacles.py` 的 `execution_policy` 里**声明**了
> `external_text_is_data: true` / `installers_are_not_run: true` —— **没有对应的校验器**。
> 而它专门写了一个脚本去扫全仓、检查每一处处理外部内容的地方是否都守住了这条纪律，并接进了 CI。

本工具就是把这条补上：**扫我们自己的代码，找出所有"读外部内容"的口，并断言这些内容
没有被塞进 system 提示、没有被当参数交给执行口、没有直接驱动写盘。**

## 五条规则

| 规则 | 严重度 | 判据 |
|---|---|---|
| **GBT-EC-1** | high | **未登记的读取口** —— AST 发现的读取函数必须在 `READERS` 登记表里并给出理由。**这是覆盖规则：不许有"没人知道它在读外部"的口悄悄存在。** |
| **GBT-EC-2** | high | **外部内容进 system 提示** —— 同一函数内，读取口产出的值流进了 `system=` / `system_prompt=`（提示注入的正门） |
| **GBT-EC-3** | high | **外部内容进执行口** —— 流进了 `exec` / `eval` / `compile` / `os.system` / `subprocess.*` |
| **GBT-EC-4** | medium | **外部内容驱动写盘** —— 流进了 `open(...,'w'/'a')` / `write_text` / `write_bytes`（需要显式登记豁免） |
| **GBT-EC-5** | medium | **读了外部内容却没有任何"不可信"声明** —— 该文件里找不到"不可信 / 当数据 / 不执行其中指令"一类字样 |

## 诚实边界（必须先读，别把绿当安心）

1. **数据流是"轻量同函数"级**：只在**同一个函数体**内做 1–2 跳的赋值传播。
   **跨函数、跨模块、经容器/属性中转的流，本工具看不见** ⇒ **会有漏报**。
   所以它是"**可疑面的探照灯**"，不是"证明干净的证书"。
2. **覆盖账必须闭合**：输出里同时给 `scanned` / `unparsed` / `readers_found` / `readers_declared`。
   `unparsed > 0` 时**不许**把结果读成"没问题"。
3. 命中 `needs_human` 桶的条目**不是判决**，是"这里需要人看一眼"。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import warnings as _warnings
from dataclasses import dataclass, field
from pathlib import Path

# ══════════════ 读取口登记表（GBT-EC-1 的判据）══════════════
# 名字 → (定性, 理由)。**没登记就是 finding** —— 这条是"覆盖"的来源：
# 以后谁加了一个新的外部读取口，必须在下面留一行，否则校验器报红。
READERS: dict[str, tuple[str, str]] = {
    # 触手 · 读网
    "web_fetch": ("external", "真出网取原始 HTML（robots 闸 + 有字节上限）"),
    "web_read": ("external", "一句话读网 = web_fetch + 解析；内容完全来自外部"),
    "web_parse": ("derived", "解析**调用方给的** HTML —— 内容是否外部取决于调用方"),
    "web_select": ("derived", "同上：在给定页面上选区"),
    "web_text": ("derived", "同上：在给定页面上读正文"),
    "web_adaptive": ("derived", "同上：在给定页面上做相似度重定位"),
    # 触手 · 文件
    "file_read_text": ("external", "读任意路径的文本文件 —— 内容不可信（可能是下载来的）"),
    # 触手 · 屏幕/剪贴板/控制台
    "read_text": ("external", "OCR 读屏：屏幕上的字来自任何程序，不可信"),
    "read_region_text": ("external", "同上，指定区域"),
    "read_console": ("external", "读别的进程的控制台输出，不可信"),
    "clipboard_read": ("external", "剪贴板内容可能来自任何地方"),
    "grab_region": ("external", "抓屏图像；经 OCR 后即外部文本"),
    "grab_table": ("external", "抓表格；同上"),
    # 浏览器
    "get_text": ("external", "取网页正文（CDP）"),
    "dom_query": ("external", "在网页上跑选择器取内容"),
    "fetch": ("external", "无头抓页面（browser_cap）"),
    # 外部资料吸收
    "catalog": ("depends", "**按实现判定**：可能读外部职业目录，也可能读本地配置 —— 见下方 needs_human"),
    # ── 以下由 2026-09-22 第一次实跑逼出来（EC-1 报红 ⇒ 要么登记要么改名）──
    "read_doc": ("external", "读飞书云文档（feishu_bridge）—— 内容来自外部协作者，不可信"),
    "web_search": ("external", "联网搜索（recon/last30days）—— 结果完全来自外部"),
    "read_text_fast": ("external", "OCR 读屏快路径（omni_read）—— 屏幕上的字来自任何程序"),
    "grab_pixel": ("external", "取屏幕像素（omni_domain）—— 像素属外部输入"),
    "grab_value": ("external", "从屏幕上抓某个标签的值（omni_domain）—— 同 OCR 性质"),
    "web_save": ("derived", "把**调用方给的**页面特征落库；输入是否外部取决于调用方"),
    "web_stats": ("internal", "读我们自己的指纹库（SQLite），不读外部"),
    "web_robots": ("external", "取 robots.txt —— 内容由外部站点控制"),
    "read_state": ("internal", "读我们自己的状态文件（coze_mail_cap / file_operation）—— 非外部"),
    "read_signals": ("internal", "读本仓信号文件（tactics）—— 非外部"),
    "read_synthesis_file": ("internal", "读上一步合成的产物（recon/last30days/cli）—— 非外部"),
    "read_description": ("internal", "读技能 frontmatter 的描述（tools/skill_slim）—— 本仓文件"),
}

# 只有这几类**才**参与"流到危险汇合点"的判定：
# `external` = 内容完全来自外部；`depends` = 按实现判定（保守起见也算上）。
# `derived` / `internal` **不参与** —— 否则会把"读自己的状态文件"也当成外部内容，噪声淹没信号。
TAINT_CLASSES = {"external", "depends"}

# 读外部内容后**必须**在这些字样里至少出现一处，否则 EC-5
UNTRUSTED_MARKERS = (
    "不可信", "当数据", "不是指令", "不执行", "untrusted", "data, never instructions",
    "external_text_is_data", "不照做", "提示注入", "prompt injection",
)

SINK_SYSTEM = {"system", "system_prompt"}
SINK_EXEC = {"exec", "eval", "compile"}
SINK_SUBPROCESS_ATTRS = {"run", "Popen", "call", "check_output", "check_call", "system"}
SINK_WRITE_METHODS = {"write_text", "write_bytes", "writelines"}

_SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".pytest_cache", ".mypy_cache"}

# ══════════════ 已声明基线（抑制项**必须带 reason**）══════════════
# 与 `tools/skill_vetting.py` 的基线同款纪律：**登记 ≠ 忽略**。
# 命中会移进报告里"已声明（带理由）"一节，**仍然显示、仍然要复核**；
# 空理由的条目会被拒收（见 `_baseline_ok`）。**留白不许当通过。**
BASELINE: dict = {
    # ★ 2026-09-22：**目前是空的，这是有意为之。**
    #   首轮 EC-5 报出的 4 个真外部读取口（browser_cap / feishu_bridge / native_browser /
    #   grounding）**已经把声明补实在各自文件头**，不再需要基线搬走它们。
    #   以后要往这里加条目，必须写清理由（≥15 字），并且**同时说明为什么补声明不现实** ——
    #   基线是"记录并可见"，不是"眼不见为净"。
}


def _baseline_ok(reason) -> bool:
    """基线条目必须有**实质理由**（≥15 字）才算数 —— 空理由/占位不许当通过。"""
    return isinstance(reason, str) and len(reason.strip()) >= 15

# 「跳过」必须**有理由并写出来** —— 沉默地跳过 = 把"没扫"读成"没问题"。
# 这几个不是**源码**，是运行时数据/自带依赖/归档：扫它们只会制造噪声与重复计数。
_SKIPPED_NOT_SOURCE = {
    "store": "运行时数据（含镜像/维度/归档的代码副本），不是源码",
    ".pylibs": "自带第三方依赖树，不是我们的源码",
    "archived_logs": "历史日志归档",
}


@dataclass
class Finding:
    rule: str
    severity: str
    path: str
    line: int
    what: str
    detail: str = ""
    context: str = ""


@dataclass
class Report:
    scanned: int = 0
    unparsed: int = 0
    unparsed_files: list = field(default_factory=list)
    readers_found: dict = field(default_factory=dict)     # name -> [file:line]
    readers_declared: int = 0
    callsites: int = 0
    findings: list = field(default_factory=list)
    needs_human: list = field(default_factory=list)
    # 被跳过的目录 → (文件数, 理由)。**沉默地跳过 = 把"没扫"读成"没问题"**，所以必须报出来。
    skipped: dict = field(default_factory=dict)
    # 命中但在 BASELINE 里声明过的 → 带理由显示，**不算 actionable**
    declared: list = field(default_factory=list)
    rejected_baseline: list = field(default_factory=list)

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    @property
    def high(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")

    def by_rule(self) -> dict:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.rule] = out.get(f.rule, 0) + 1
        return dict(sorted(out.items()))

    @property
    def coverage_closed(self) -> bool:
        """覆盖是否闭合：**有没解析的文件，就不算闭合**。"""
        return self.unparsed == 0

    def verdict(self) -> str:
        if not self.coverage_closed:
            return "incomplete —— 有文件没解析，**不许读成没问题**"
        if self.high:
            return "fail —— 有 high 级命中，须人工处置"
        if self.findings:
            return "warn —— 只有中低命中，逐条过目"
        return "pass —— 五条规则无命中（注意本工具会有漏报，见文件头「诚实边界」）"


def _iter_py(root: Path, rep: "Report | None" = None):
    """产出要扫的 .py。跳过的目录**记进 rep.skipped**（不静默跳）。"""
    for p in sorted(root.rglob("*.py")):
        parts = set(p.parts)
        if parts & _SKIP_DIRS:
            continue
        hit = next((d for d in _SKIPPED_NOT_SOURCE if d in parts), None)
        if hit:
            if rep is not None:
                n, _why = rep.skipped.get(hit, (0, _SKIPPED_NOT_SOURCE[hit]))
                rep.skipped[hit] = (n + 1, _SKIPPED_NOT_SOURCE[hit])
            continue
        yield p


def _call_name(node: ast.AST) -> str:
    """把调用目标还原成名字：`f` / `a.f` / `a.b.f` 都取最后一段。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _touched_names(node: ast.AST) -> set:
    """一个表达式里引用到的所有名字（含属性基座）。"""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


# 与 stdlib 撞名的读取口：**只看方法名会把 pathlib 误当成我们的 OCR**。
# 实测教训（2026-09-22 第一轮）：`Path.read_text()` 与 `omni_read.read_text()`（OCR 读屏）撞名，
# 一次制造 8 处假"外部内容驱动写盘"，全部落在这条上。⇒ 撞名的这几个**必须看调用基座**。
_AMBIGUOUS_WITH_STDLIB = {"read_text", "read_bytes", "write_text", "write_bytes",
                          "fetch", "get_text", "read_region_text"}


def _call_is_reader(call: ast.Call, reader_names: set) -> bool:
    """判断一个调用是不是"外部内容读取口"。**必须看基座，不能只看方法名。**

    · `read_text(...)`（裸名）                      → 认（模块级函数）
    · `self.read_text(...)` / `cls.web_fetch(...)`  → 认（触手本体）
    · `web_fetch(...)` / `grab_table(...)`（不撞名）→ 认（属性调用也不撞 stdlib）
    · `p.read_text(...)`（基座是普通变量）          → **不认**（那是 pathlib，读的是本机文件句柄）
    """
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id in reader_names
    if isinstance(fn, ast.Attribute):
        attr = fn.attr
        if attr not in reader_names:
            return False
        base = fn.value
        if isinstance(base, ast.Name) and base.id in ("self", "cls"):
            return True
        return attr not in _AMBIGUOUS_WITH_STDLIB
    return False


def _has_reader_call(node: ast.AST, reader_names: set) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and _call_is_reader(n, reader_names):
            return True
    return False


def _classify_sink(call: ast.Call) -> tuple[str, str] | None:
    """判断一个调用是不是危险汇合点。返回 (类别, 说明) 或 None。"""
    fn = call.func
    name = _call_name(fn)
    last = name.split(".")[-1]
    # 关键字参数：system= / system_prompt=
    for kw in call.keywords:
        if kw.arg in SINK_SYSTEM:
            return ("system", f"关键字参数 {kw.arg}= 收到外部内容（提示注入正门）")
    if last in SINK_EXEC:
        return ("exec", f"执行口 {name}() 收到外部内容")
    if last in SINK_SUBPROCESS_ATTRS and ("subprocess" in name or name == "system"):
        return ("exec", f"执行口 {name}() 收到外部内容")
    if last in SINK_WRITE_METHODS:
        return ("write", f"写盘口 {name}() 由外部内容驱动")
    if last == "open":
        mode = ""
        if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
            mode = str(call.args[1].value)
        for kw in call.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = str(kw.value.value)
        if any(c in mode for c in "wax"):
            return ("write", f"open(mode={mode!r}) 由外部内容驱动")
    return None


def _scan_function(fn: ast.AST, src_lines: list, rel: str, reader_names: set,
                   rep: Report) -> None:
    """在一个函数体内做 1–2 跳的轻量传播，然后找危险汇合点。"""
    body = list(ast.walk(fn))
    tainted: set = set()

    # 传 1：直接从读取口赋值出来的名字
    for n in body:
        if isinstance(n, ast.Assign) and _has_reader_call(n.value, reader_names):
            for t in n.targets:
                tainted |= _touched_names(t)
        elif isinstance(n, ast.AnnAssign) and n.value is not None \
                and _has_reader_call(n.value, reader_names):
            tainted |= _touched_names(n.target)
        elif isinstance(n, ast.Call) and _has_reader_call(n, reader_names):
            rep.callsites += 1

    if not tainted:
        # 也兜住"读取口的结果没赋值、直接内联进汇合点"的情况
        for n in body:
            if isinstance(n, ast.Call) and _classify_sink(n):
                if _has_reader_call(n, reader_names):
                    kind, why = _classify_sink(n)  # type: ignore[misc]
                    _emit(rep, kind, rel, n.lineno, src_lines, why, "内联调用")
        return

    # 传 2：一跳扩散（把污染名拼进新变量）
    for _ in range(2):
        for n in body:
            if isinstance(n, ast.Assign) and (_touched_names(n.value) & tainted):
                for t in n.targets:
                    tainted |= _touched_names(t)

    for n in body:
        if not isinstance(n, ast.Call):
            continue
        hit = _classify_sink(n)
        if not hit:
            continue
        kind, why = hit
        direct = _has_reader_call(n, reader_names)
        flow = bool(_touched_names(n) & tainted)
        if direct or flow:
            _emit(rep, kind, rel, n.lineno, src_lines, why,
                  "内联调用" if direct else "经变量传播：%s" % ", ".join(sorted(_touched_names(n) & tainted))[:80])


def _emit(rep: Report, kind: str, rel: str, lineno: int, src_lines: list,
          why: str, how: str) -> None:
    rule = {"system": "GBT-EC-2", "exec": "GBT-EC-3", "write": "GBT-EC-4"}[kind]
    sev = "medium" if kind == "write" else "high"
    ctx = src_lines[lineno - 1].strip()[:160] if 0 < lineno <= len(src_lines) else ""
    rep.add(Finding(rule=rule, severity=sev, path=rel, line=lineno,
                    what={"system": "外部内容进 system 提示",
                          "exec": "外部内容进执行口",
                          "write": "外部内容驱动写盘"}[kind],
                    detail=f"{why}（{how}）", context=ctx))


def scan(root: str | Path, *, limit: int = 0, use_baseline: bool = True) -> Report:
    root = Path(root).expanduser().resolve()
    rep = Report()
    rep.readers_declared = len(READERS)
    reader_names = set(READERS)
    # ★ 第一轮实跑教训：EC-2/3/4 只该盯**真外部**的读取口。
    #   一开始把所有登记项都算上，结果"读自己的状态文件"也被判成外部内容，噪声淹没信号。
    taint_names = {n for n in READERS if READERS[n][0] in TAINT_CLASSES}

    files = list(_iter_py(root, rep))
    if limit:
        files = files[: int(limit)]

    for path in files:
        rel = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore")      # 只关心语法错，不关心 escape 之类的告警
                tree = ast.parse(text)
        except (SyntaxError, ValueError, OSError) as e:
            # OSError 含 PermissionError：**读不到就是没扫到**，如实记，不许当通过
            rep.unparsed += 1
            rep.unparsed_files.append("%s: %s: %s" % (rel, type(e).__name__, str(e)[:70]))
            continue
        rep.scanned += 1
        src_lines = text.splitlines()

        # ── EC-1：读取口登记（定义处）──
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                short = n.name
                if re.match(r"^(web_(fetch|read|parse|select|text|adaptive|save|stats|robots)"
                            r"|read_(text|text_fast|region_text|console|doc|state|signals"
                            r"|synthesis_file|description)"
                            r"|grab_(pixel|region|table|value)"
                            r"|clipboard_read|file_read_text|dom_query|get_text|fetch"
                            r"|web_search)$", short):
                    rep.readers_found.setdefault(short, []).append(f"{rel}:{n.lineno}")
                    if short not in reader_names:
                        rep.add(Finding(
                            rule="GBT-EC-1", severity="high", path=rel, line=n.lineno,
                            what="未登记的外部内容读取口",
                            detail="函数名像「读外部」，但不在 READERS 登记表里 —— "
                                   "要么登记它并写明理由与定性（external/derived/internal/depends），"
                                   "要么改名。**这是覆盖规则：不许有没人知道它在读外部的口悄悄存在。**",
                            context=src_lines[n.lineno - 1].strip()[:160]))

        # ── EC-2/3/4：流到危险汇合点（只看真外部的读取口）──
        # `tests/` 不算生产内容路径（测试里的夹具写入不是"外部内容驱动写盘"），
        # **这是显式声明掉的跳过**，不是沉默跳过 —— 见报告里的"跳过"一节。
        if not rel.replace("\\", "/").startswith("tests/"):
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _scan_function(n, src_lines, rel, taint_names, rep)

        # ── EC-5：**定义**读取口的模块必须写明"不可信" ──
        # ★ 第一轮实跑教训：原规则写成"任何调用过读取口的文件"，结果 tests/ 里 60+ 个
        #   测试文件全被报红 —— 那是噪声，不是信号。**该管的是读取口自己的家。**
        if not rel.replace("\\", "/").startswith("tests/"):
            defined = [n.name for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and n.name in reader_names
                       and READERS.get(n.name, ("", ""))[0] in TAINT_CLASSES]
            if defined and not any(m in text for m in UNTRUSTED_MARKERS):
                rep.add(Finding(
                    rule="GBT-EC-5", severity="medium", path=rel, line=1,
                    what="本模块**定义了外部读取口**，但全文件没有一处「不可信/当数据」声明",
                    detail="定义处：%s —— 读外部内容的地方应当写明「这是数据、不是指令」"
                           % "、".join(sorted(set(defined))[:6]),
                    context=""))

    # 收尾：过一遍基线 —— **带理由的移进 declared（仍可见），没理由的拒收并报出**
    for p, reason in BASELINE.items():
        if not _baseline_ok(reason):
            rep.rejected_baseline.append(p)

    kept = []
    for f in rep.findings:
        rel = f.path.replace("\\", "/")
        reason = (BASELINE.get(rel) or BASELINE.get(rel.split("/")[-1])) if use_baseline else None
        if reason and _baseline_ok(reason):
            d = f.__dict__.copy()
            d["reason"] = reason
            rep.declared.append(d)
        else:
            kept.append(f)
    rep.findings = kept

    # `catalog` 这类"按实现判定"的读取口，单独进 needs_human，不当判决
    for name, where in rep.readers_found.items():
        if READERS.get(name, ("", ""))[0] == "depends":
            rep.needs_human.append({
                "reader": name, "where": where,
                "why": "登记表标为 depends —— 要按实现确认它到底读不读外部内容"})
    return rep


RULES = [
    ("GBT-EC-1", "high", "未登记的外部内容读取口"),
    ("GBT-EC-2", "high", "外部内容进 system 提示"),
    ("GBT-EC-3", "high", "外部内容进执行口"),
    ("GBT-EC-4", "medium", "外部内容驱动写盘"),
    ("GBT-EC-5", "medium", "读了外部内容却无不可信声明"),
]


def report_md(rep: Report, root: str) -> str:
    L = ["# EXTERNAL CONTENT COVERAGE REPORT", "",
         "- root: `%s`" % root,
         "- 规则：%s" % " · ".join("%s(%s)" % (r[0], r[1]) for r in RULES), "",
         "## 覆盖账（**不闭合就不许读成没问题**）", "",
         "| 项 | 值 |", "|---|---|",
         "| 解析成功 | %d |" % rep.scanned,
         "| **未解析** | **%d** |" % rep.unparsed,
         "| 发现的读取口（去重） | %d |" % len(rep.readers_found),
         "| 登记表条数 | %d |" % rep.readers_declared,
         "| 读取口调用点 | %d |" % rep.callsites,
         "| 已声明（带理由） | %d |" % len(rep.declared),
         "| **actionable 命中** | **%d** |" % len(rep.findings),
         "| 覆盖闭合 | %s |" % ("是" if rep.coverage_closed else "**否**"),
         "", "## 判定", "", "**%s**" % rep.verdict(), "",
         "命中计数：`%s`" % json.dumps(rep.by_rule(), ensure_ascii=False)]
    if rep.unparsed_files:
        L += ["", "## 未解析的文件（这些**没被看过** —— 不许读成没问题）", ""]
        L += ["- `%s`" % u for u in rep.unparsed_files[:40]]
        if len(rep.unparsed_files) > 40:
            L += ["- …共 %d 个" % len(rep.unparsed_files)]
    if rep.skipped:
        L += ["", "## 按理由跳过的目录（**不是源码**；列出来是为了让覆盖账可核算）", "",
              "| 目录 | 跳过的 .py 文件数 | 理由 |", "|---|---|---|"]
        for d, (n, why) in sorted(rep.skipped.items()):
            L += ["| `%s` | %d | %s |" % (d, n, why)]
    if rep.declared:
        L += ["", "## 已声明（带理由）—— **登记 ≠ 忽略，仍然要复核**", "",
              "| 规则 | 位置 | 内容 | 声明理由 |", "|---|---|---|---|"]
        for d in rep.declared:
            L += ["| %s | `%s:%d` | %s | %s |" % (d["rule"], d["path"], d["line"],
                                                 d["what"], d["reason"])]
    if rep.rejected_baseline:
        L += ["", "## ❌ 被拒收的基线条目（理由不足）", "",
              "基线条目必须写清理由（≥15 字）。下面这些**不算数**：", ""]
        L += ["- `%s`" % p for p in rep.rejected_baseline]
    if rep.findings:
        L += ["", "## 命中（actionable）", ""]
        for f in rep.findings:
            L += ["### %s [%s] `%s:%d`" % (f.rule, f.severity, f.path, f.line),
                  "- %s" % f.what, "- %s" % f.detail]
            if f.context:
                L += ["- 原文：`%s`" % f.context]
            L += [""]
    if rep.needs_human:
        L += ["", "## 需人工确认（不是判决）", ""]
        for h in rep.needs_human:
            L += ["- `%s` @ %s —— %s" % (h["reader"], ", ".join(h["where"][:3]), h["why"])]
    L += ["", "## 诚实边界", "",
          "1. 数据流是**同函数 1–2 跳**级，跨函数/跨模块/经容器中转的流**看不见** ⇒ **会漏报**。",
          "2. 本工具是「可疑面探照灯」，**不是「证明干净」的证书**。",
          "3. `needs_human` 里的条目要人看，不是判决。", "",
          "> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"]
    return "\n".join(L)


def _cli() -> int:
    ap = argparse.ArgumentParser(description="外部内容覆盖校验器")
    ap.add_argument("root", help="要扫的代码根（通常 gbt_allinone）")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="", help="把报告写到这个 .md")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-baseline", action="store_true",
                    help="不套基线 —— **用来证明探照灯还亮着**（应重新看见被声明的那些命中）")
    a = ap.parse_args()
    rep = scan(a.root, limit=a.limit, use_baseline=not a.no_baseline)
    root_abs = str(Path(a.root).expanduser().resolve())
    # ⚠️ `--out` 与 `--json` **互不排斥**：两个都要给（早先写成二选一，是设计缺陷）
    if a.out:
        Path(a.out).write_text(report_md(rep, root_abs), encoding="utf-8")
    if a.json:
        print(json.dumps({
            "scanned": rep.scanned, "unparsed": rep.unparsed,
            "readers_found": {k: v[:3] for k, v in rep.readers_found.items()},
            "readers_declared": rep.readers_declared, "callsites": rep.callsites,
            "findings": [f.__dict__ for f in rep.findings],
            "needs_human": rep.needs_human, "by_rule": rep.by_rule(),
            "coverage_closed": rep.coverage_closed, "verdict": rep.verdict(),
            "skipped": {k: v[0] for k, v in rep.skipped.items()},
            # ★ 必须有这两项：否则"已声明"与"基线被拒"在读 JSON 时**根本看不见**，
            #   一个 pass 到底是因为"真干净"还是"被基线搬走了"就分不出来。实测踩过。
            "declared": rep.declared,
            "rejected_baseline": rep.rejected_baseline,
            "baseline_active": not a.no_baseline,
        }, ensure_ascii=False, indent=1))
    elif a.out:
        print("saved:", a.out, "| verdict:", rep.verdict())
    else:
        print(report_md(rep, root_abs))
    return 0 if not rep.high and rep.coverage_closed else 1


if __name__ == "__main__":
    sys.exit(_cli())
