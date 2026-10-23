#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**永远不会红的判据**审计器（AST 版）。

由来（一手，2026-09-25）：
    我改面板快照时把嵌数据**写坏了**，而 `verify_v22.py` 报「49 通过」一声没吭。
    查下去发现两件事：
      · `verify_v21.py:178` / `verify_v20.py:141` 那条「原型无 undefined 字面量」
        末尾写着 **`or True`** ⇒ **恒真，从出生起就不可能红**；
      · **现行**的 `verify_v22.py` 干脆没有这一条（换代时判据丢了）。
    ⇒ **「条数」不等于「牙齿」。** 这个审计器专抓"看起来在判、其实恒真"的判据。

它查五类（全部走 **AST**，不做文本匹配 —— 文本匹配在本会话里已经误报过四次）：
  A. `or True` / `and False`：布尔吸收式 ⇒ 整条表达式恒真/恒假；
  B. `chk(...)` / `assertX(...)` 的判据是**字面常量**（`True` / `1` / `"x"` / `1 == 1`）；
  C. `if False:` / `while False:`（永不执行的块）；
  D. `try: … except …: pass` 里**只包含判据调用** ⇒ 判据抛异常被吞（等于不判）；
  E. `assert` 后的常量表达式。

用法：
  python tools/codex-scripts/audit-dead-judgments.py [--root <目录> ...] [--json]
退出码：0 = 没找到恒真判据；1 = 找到了（逐条列 file:line）。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

# 🔴 2026-10-10 修：**在 GBK 控制台上不带 -X utf8 调用时本件会当场崩**。
#    实测（真因，不是猜）：gbt_allinone/tests/test_dead_judgments.py 调本件用的是
#        subprocess.run([sys.executable, str(TOOL), "--json"], ...)
#    —— **没带 -X utf8**；而本机控制台是 GBK ⇒ 第 222 行 print(json.dumps(..., ensure_ascii=False))
#    印到字符 U+21D2 时抛
#        UnicodeEncodeError: 'gbk' codec can't encode character U+21D2
#    ⇒ **stdout 是空的** ⇒ 调用方 json.loads('') 抛 JSONDecodeError ⇒ 开机自检
#    「判据/没有恒真判据」恒红。**这不是调用方的错 —— 是工具不够硬**：
#    任何不带 -X utf8 的调用者都会踩。修法：入口处把 stdout/stderr 钉成 UTF-8。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
DEFAULT_ROOTS = ["tools/codex-scripts", "gbt_allinone"]

# 判据调用名 → **判据在第几个位置参数**。
# 🔴 这张表**逐个读过真签名**，不猜：
#     `def chk(name, ok, detail)`      ⇒ 判据在第 2 个（下标 1）
#     `def expect(cond, msg)`          ⇒ 判据在第 1 个（下标 0）
#   首跑我按"猜"把 `expect` 也当成"第 2 个是判据" ⇒ 于是把**消息字符串**当判据，
#   一口气刷出 1400+ 条假阳性（`expect(x == y, "说明")` 全被报成"判据是常量"）。
#   ⇒ 规矩：**没读过签名的名字，一律不判**（宁可漏，不许拿 msg 当判据）。
COND_ARG = {"chk": 1, "check": 1, "verify": 1, "expect": 0}
# 逐字比较类：判据是**两个操作数之间的关系** ⇒ 只有"两边都是常量"才可能恒真/恒假。
#   ⚠️ 首跑把 `assertIn` 归进"第 1 个参数是判据" ⇒ `assertIn("x", 计算出来的文本)` 全被误报
#      （`"x"` 是常量没错，但判据是"在不在里面"，能红）。⇒ 按签名分类，不按名字猜。
REL_NAMES = {"assertEqual", "assertNotEqual", "assertIn", "assertLess", "assertGreaterEqual"}
SINGLE_ARG_NAMES = {"assertTrue", "assertFalse", "assertIsNotNone"}
CHK_NAMES = set(COND_ARG) | REL_NAMES | SINGLE_ARG_NAMES
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".scratch", "archive", "dist",
             # 下面三个是**第三方 vendored 代码**（pytest / cffi / comtypes / bitarray…），
             # 不是本仓判据 —— 首跑没排它们，1780 条命中里绝大多数是它们贡献的。
             ".pylibs", "vendor", "_upstream",
             # `store/` 是**运行态产物**（账本 / 版本快照），不是源码；且里面有不可读件
             # （实测 `store/pipeline/production/.versions/run.py` PermissionError）。
             # **跳过要可见** —— 报告里把跳过名单与不可读文件都列出来，不许静默略过。
             "store"}


def _is_const_bool(node) -> bool:
    """这个表达式是不是**字面常量**（与输入无关）？"""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return all(_is_const_bool(e) for e in ast.iter_child_nodes(node))
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        lft, r = node.left, node.comparators[0]
        if _is_const_bool(lft) and _is_const_bool(r):
            return True
    return False


# 逐条读过、**不是"恒真判据"**的三处（照 `false_report_audit.KNOWN_LEGIT` 的先例：
# 豁免要**带理由、可见**，不是静默放过）。键 = (文件, 行号, 规则)。
KNOWN = {
    ("tools/codex-scripts/pack-receipt.py", 98, "B/判据是常量"):
        "**记录失败用的惯用法**：`chk(name, False, 为什么)` —— 这一条**就是要报红**"
        "（包不在盘上），不是恒真。它判的是『这一格该红』，不是『条件成立』。",
    ("tools/codex-scripts/pack-receipt.py", 130, "B/判据是常量"):
        "同上：读不动窗口注册表时**主动记红**的惯用法。",
    ("gbt_allinone/llm/genoffice_bridge.py", 977, "B/判据是常量"):
        "**空转防护的备案写法**：本机没装代理时，A5/A6 那两条对照（『代理挡路会伪装成没起』）"
        "无事可做 ⇒ 这一格**故意记 PASS 并写明原因**（`getproxies()={}` 就在 detail 里）。"
        "它判的不是『条件成立』，而是『这台机器上这条对照不适用』—— 换成有代理的机器，"
        "走的是上面 `bool(_defbad)` 那条真判据。**属『已读并接受』，不是恒真判据。**",
    ("tools/codex-scripts/mock-vllm-endpoint.py", 161, "A/and False"):
        "**假端点**报告里的**故意死分支**（`… if False else '见 selftest'`）—— 用来避免真发那记 404 请求。"
        "属 mock 的写法，不是判据。",
    # ── 2026-10-17 补两条（跑真数据咬出来的）──
    ("gbt_allinone/api.py", 2725, "C/永不执行"):
        "**主人令的显式回滚开关**：`if False:` 是有注释的「代码保留、永不生效」——"
        "2026-10-15 因为「AI 路径无权动用主人总控」当场回滚（账 #532），"
        "主人日后要放开只需改这一行。属**已读并接受的死分支**，不是漏执行。",
    ("gbt_allinone/tools/edit_core.py", 843, "B/判据是常量"):
        "**记录失败用的惯用法**（与 `pack-receipt.py:98` 同构）：`chk(name, False, …)` "
        "在『vendored 模板不在盘』时**主动记红**，不是恒真；另一半 `not miss` 才是真判据。",
    ("tools/codex-scripts/gbt-model-accept.py", 196, "B/判据是常量"):
        "**记录失败用的惯用法**：`codex` 不在盘时 `check(…, False, …)` **主动记红**"
        "（C6 端到端这一格必然失败）；codex 在场时走的是下面 `ok = \"GBT-TOOL-OK\" in out …` 真判据。",
    ("tools/codex-scripts/gbt-model-accept.py", 232, "B/判据是常量"):
        "**异常兜底记红**：`except Exception: check(…, False, str(exc))` —— 这一格的作用就是"
        "把「这一步抛异常」记成红，属必然红不是恒真。",
    # ── 2026-10-17 补 8 条「**分支内备案式放行**」────────────────────────────────
    #   共同句型：`条件成立后 mark/add(…, True, 读数)` —— 能执行到这一行本身就证明了条件，
    #   `True` 是**结论/备案**，不是与输入无关的判据；失败路径另在 `else`/`except` 里判红。
    #   这不是"恒真判据"，是"把已成立的事实写进读数"——本工具看不见分支上下文，故在此可见登记。
    ("tools/codex-scripts/capability-autobind.py", 437, "B/判据是常量"):
        "**只读性备案**：`scan` 不写盘由代码结构保证（只读台账+已见集合），此格把它写进读数。",
    ("tools/codex-scripts/capability-nerve.py", 337, "B/判据是常量"):
        "**真源现读后的备案**：走到 `else` 说明假执行名单已从 truth_scan 真源取到，`True` 是结论。",
    ("tools/codex-scripts/key-hygiene.py", 118, "B/判据是常量"):
        "**显式 `--offline` 降级**：detail 明写「跳过（--offline 显式降级）—— 不许念成全绿」；"
        "把降级状态记进读数，online 走的是真判据。",
    ("tools/codex-scripts/shared-endpoint-queue.py", 167, "B/判据是常量"):
        "**负控断言**：上一行刚 `throw`，能走到 `ck(…, True, …)` 就证明负控通过。",
    ("tools/codex-scripts/tentacle-watch.py", 92, "B/判据是常量"):
        "**口径备案**：把「插数上限 3」钉进读数；上下各有一条真判据（坏行不炸 / 行数不超）。",
    ("gbt_allinone/tools/media_run.py", 945, "B/判据是常量"):
        "**分支内结论**：上行 `parse` 成功才 `mark(… True …)`；失败走 `except` 判红。",
    ("gbt_allinone/tools/media_run.py", 952, "B/判据是常量"):
        "**分支内结论**：`set(m[\"tempos\"])` 已取到才 mark；空列表另有判红分支。",
    ("gbt_allinone/tools/media_run.py", 965, "B/判据是常量"):
        "**分支内结论**：`if m[\"key\"]:` 为真才 mark；`else` 才是判红。",
    # ── 下面两条 2026-09-25 已修（保留记录，说明"曾经是已知弱项、现在不是了"）──
    #   `merge-4k-rig.py:40` 的 `or True` → 删掉被中和的合取项（行为不变），并把"那条校验没实现"写进注释
    #   `scan_engine.py:380` 的 `if name_traps or True:` → 去条件、保留无条件块（行为不变）
}

# ── 锚点豁免（**抗行号漂移** · 2026-10-17 加）──────────────────────────────────
#   上面 `KNOWN` 按 (文件, 行号, 规则) 钉死 —— 精确、但**随文件长大而失效**：
#   实测 `gbt_allinone/api.py` 那条主人令回滚开关的 `if False:` 从 2720 漂到 2725，
#   豁免原地失效 ⇒ 判据报**假红**，而代码一行没改。
#   ⇒ 补第二档：**同文件 + 同规则 + 该行源码里出现锚点文本**才算同一条。
#   为什么不会放过新长出来的死分支：新分支的源码行里没有这段锚点文本。
#   命中走锚点时，报告里 `matched_by` 会写「anchor(行号漂移)」—— **漂移可见，不静默**。
ANCHORS = {
    ("gbt_allinone/api.py", "C/永不执行"): "if False:   # 🔴 2026-10-15 回滚",
}


def scan_file(path: Path) -> tuple:
    """返回 (hits, unreadable)。**读不到不算"干净"** —— 记下来、如实报。"""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [], "%s: %s" % (str(path.relative_to(ROOT)).replace("\\", "/"),
                               type(e).__name__)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [], "%s: SyntaxError line %s" % (
            str(path.relative_to(ROOT)).replace("\\", "/"), e.lineno)
    hits = []
    # 路径可能**不在仓内**（用例会喂临时目录的合成样本）⇒ 相对化失败就退成绝对路径，
    # 别让"打印文件名"这种小事把整条判据弄崩（首跑就是这么崩的）。
    try:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        rel = str(path).replace("\\", "/")

    _src_lines = src.splitlines()

    def add(node, rule, why):
        _ln = getattr(node, "lineno", 0)
        # 2026-10-17 加 `src`：豁免表按行号钉死会随文件长大而失效（实测 api.py 那条
        # `if False:` 从 2720 漂到 2725 ⇒ 判据报**假红**，代码一行没改）。
        # 把命中那一行的源码带出来，给下面的 `ANCHORS` 做第二档匹配。
        hits.append({"file": rel, "line": _ln, "rule": rule, "why": why,
                     "src": (_src_lines[_ln - 1].strip() if 0 < _ln <= len(_src_lines) else "")})

    # 🔴 2026-10-17 加（根治一类假阳性 · 留痕）：
    #   `COND_ARG` 是**按名字写死下标**的。实测 `tools/codex-scripts/gbt-model-accept.py` 的
    #   本地助手签名是 `check(cid, name, ok, detail)` —— 判据在**下标 2**，而表里 `check: 1`
    #   ⇒ 把第 2 个位参 `name`（字面字符串）当判据，一口气误报 **8 条**"判据是常量"。
    #   ⇒ 现在**先看本地定义**：同名函数若在本文件里定义，按**参数名**定位判据位
    #   （ok / cond / condition / criterion / judge / passed / good）；找不到才回落 `COND_ARG`。
    #   这是本文件既有纪律「按签名分类、不按名字猜」的延伸。
    _CRIT_PARAM_NAMES = ("ok", "cond", "condition", "criterion", "judge", "passed", "good")
    _local_sigs = {}
    for _n in ast.walk(tree):
        if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _local_sigs[_n.name] = [a.arg for a in _n.args.args]

    def _cond_index(fname):
        # ⚠️ 2026-10-17 边界（第二次收）：只对**逐个读过签名的判据助手**（COND_ARG 里那四个）
        #    做"按本地签名定位判据位"；`add/j/mark/c` 这类**业务助手**一律不判
        #    （它们第 N 个位参常是状态标签/读数文本，判它会一口气刷出 51 条假阳性）。
        if fname not in COND_ARG:
            return None
        params = _local_sigs.get(fname)
        if params:
            for _i, _p in enumerate(params):
                if _p.lower() in _CRIT_PARAM_NAMES:
                    return _i
        return COND_ARG.get(fname)

    # 🔴 2026-10-10 修（**真因，有证据**）：A 类原来扫**任何** BoolOp 里的 True/False 常量，
    #    **不分它站在什么位置** ⇒ 把**测试替身**错报成恒真判据。
    #    实测：开机自检「判据/没有恒真判据」一直红，咬住的是
    #        gbt_allinone/tests/test_deepseek_bridge.py:262
    #            BR.clip_write = lambda text: seen.update(text=text) or True
    #    那是**故意的存根**（把真函数换成永远成功的假函数），dict.update() 返回 None，
    #    None or True = True —— 它是**被赋值的表达式值**，**不是判据**，永远不会出现在任何判决里。
    #    ⇒ 收紧成：**只在判据位置报 A 类** —— If/While/Assert/IfExp 的条件位、推导式的 if 位。
    #      这正是本文件文档里举的两个真例子站的位置
    #      （verify_v21.py:178 的判据内 or True · scan_engine.py:380 的 if name_traps or True:）。
    #    **判据位** = ① 条件槽（If/While/Assert/IfExp/推导式的 if）
    #              ∪ ② **判据助手调用的那个参数**（chk 的第 2 个位参看 COND_ARG）
    #    它自己的负控样本就长这样：chk("x", ("undefined" not in t) or True, "note")
    #    —— or True 是 chk 的**参数**，不是条件槽 ⇒ 只按条件槽收会**漏掉真判据**（实测漏了）。
    _judgment_positions = set()
    _cond_holders = (ast.If, ast.While, ast.Assert, ast.IfExp, ast.comprehension)
    for node in ast.walk(tree):
        if isinstance(node, _cond_holders):
            t = getattr(node, "test", None)
            if t is None:
                t = getattr(node, "if_", None)
            if t is not None:
                for sub in ast.walk(t):
                    _judgment_positions.add(id(sub))
        if isinstance(node, ast.Call):
            _fn = ""
            _attr = False
            if isinstance(node.func, ast.Name):
                _fn = node.func.id
            elif isinstance(node.func, ast.Attribute):
                _fn = node.func.attr
                _attr = True
            if _attr and not _fn.startswith("assert"):
                _fn = ""
            _slots = []
            _ci = _cond_index(_fn)
            if _ci is not None and len(node.args) > _ci:
                _slots.append(node.args[_ci])
            elif _fn in SINGLE_ARG_NAMES and node.args:
                _slots.append(node.args[0])
            elif _fn in REL_NAMES and len(node.args) >= 2:
                _slots.extend(node.args[:2])
            for _sl in _slots:
                for sub in ast.walk(_sl):
                    _judgment_positions.add(id(sub))

    for node in ast.walk(tree):
        # A. or True / and False —— **只在判据位**
        if isinstance(node, ast.BoolOp) and id(node) in _judgment_positions:
            for v in node.values:
                if isinstance(v, ast.Constant):
                    if isinstance(node.op, ast.Or) and v.value is True:
                        add(node, "A/or True", "布尔吸收：整条恒真")
                    elif isinstance(node.op, ast.And) and v.value is False:
                        add(node, "A/and False", "布尔吸收：整条恒假")
        # B/E. 判据是字面常量
        #   ⚠️ 首跑这一条太粗：`assertEqual("a","a")` 这种**纯函数期望值**是正当写法，
        #      而我把"参数里有常量"一律报成恒真 ⇒ 噪音淹掉真信号。
        #      ⇒ 收紧成**可证明恒真**的三种：chk 的 cond 是常量 · assertTrue 的参是常量 ·
        #        assertEqual 两边都是常量**且相等**（不等是恒假，另标）。
        if isinstance(node, ast.Call):
            fname = ""
            _is_attr = False
            if isinstance(node.func, ast.Name):
                fname = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fname = node.func.attr
                _is_attr = True
            # 🔴 第五类假阳性（跑真数据才发现）：`ep.check({}, {}, …)` 里的 `check`
            #    是**那个能力位自己的函数**，不是测试助手 —— 我按 `attr` 取值就把它当判据助手了。
            #    ⇒ 规矩：`chk/check/verify/expect` 这些**本地助手**只认**裸名字调用**；
            #      `self.assertEqual(...)` 这类 unittest 断言才允许带点。
            if _is_attr and not fname.startswith("assert"):
                fname = ""
            _ci = _cond_index(fname)
            if _ci is not None and len(node.args) > _ci:
                # ⚠️ 口径**保持原样**：`chk(name, False, why)` 这类「记录失败」惯用法**照旧报出来**，
                #    再由 KNOWN 逐条可见豁免 —— 这是 `test_dead_judgments` 钉住的既有契约
                #    （"不许它悄悄变成没报"）。2026-10-17 只改"判据位怎么定位"，不改"报不报"。
                if _is_const_bool(node.args[_ci]):
                    add(node, "B/判据是常量",
                        "%s() 的第 %d 个位置参数（判据）是字面常量 ⇒ 与输入无关"
                        % (fname, _ci + 1))
            elif fname in SINGLE_ARG_NAMES and node.args:
                if _is_const_bool(node.args[0]):
                    add(node, "B/判据是常量", "%s() 的判据是字面常量" % fname)
            elif fname in REL_NAMES and len(node.args) >= 2:
                a0, a1 = node.args[0], node.args[1]
                if _is_const_bool(a0) and _is_const_bool(a1):
                    try:
                        same = ast.literal_eval(a0) == ast.literal_eval(a1)
                    except Exception:                            # noqa: BLE001
                        same = False
                    add(node, "B/常量相比",
                        "%s 两边都是字面常量 ⇒ 结果在写的时候就定了（%s）"
                        % (fname, "恒真" if same else "恒假/恒错"))
        if isinstance(node, ast.Assert) and _is_const_bool(node.test):
            try:
                truthy = bool(ast.literal_eval(node.test))
            except Exception:                                    # noqa: BLE001
                truthy = True
            add(node, "E/assert 常量", "assert 的条件是字面常量（%s）"
                % ("恒真" if truthy else "恒假"))
        # C. if False / while False
        if isinstance(node, (ast.If, ast.While)):
            t = node.test
            if isinstance(t, ast.Constant) and t.value is False:
                add(node, "C/永不执行", "%s False 块" % type(node).__name__.lower())
        # D. except 里吞掉判据
        if isinstance(node, ast.Try):
            for h in node.handlers:
                body = [b for b in h.body
                        if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    # 只报"try 里全是判据调用"的：那种吞了就等于不判
                    calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
                    names = {n.func.id for n in calls
                             if isinstance(n.func, ast.Name)} | \
                            {n.func.attr for n in calls if isinstance(n.func, ast.Attribute)}
                    if names & CHK_NAMES:
                        add(node, "D/判据被吞", "try 里的判据抛异常后 pass ⇒ 等于不判")
    return hits, None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="恒真判据审计（只读）")
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    roots = a.root or DEFAULT_ROOTS
    hits, files, unread = [], 0, []
    for r in roots:
        base = ROOT / r
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if any(s in p.parts for s in SKIP_DIRS):
                continue
            files += 1
            h, bad = scan_file(p)
            hits += h
            if bad:
                unread.append(bad)
    def _resolve(h):
        """这条命中该挂哪一条豁免？先精确（文件+行+规则），再按锚点容错。

        返回**KNOWN 的键**（理由照它取），没有豁免则返回 None。
        """
        k = (h["file"], h["line"], h["rule"])
        if k in KNOWN:
            return k
        for (f, rule), anchor in ANCHORS.items():
            if f != h["file"] or rule != h["rule"] or not anchor:
                continue
            if anchor not in str(h.get("src") or ""):
                continue
            for kk in KNOWN:                      # 沿用同 (文件, 规则) 那条的理由
                if kk[0] == f and kk[2] == rule:
                    return kk
        return None

    _keys = [_resolve(h) for h in hits]
    exempt = [h for h, k in zip(hits, _keys) if k]
    live = [h for h, k in zip(hits, _keys) if not k]
    known_open = [h for h, k in zip(hits, _keys) if k and "已知弱项" in KNOWN.get(k, "")]
    rep = {"ok": True, "readonly": True, "files": files, "hits": live, "count": len(live),
           "exempt": [{"file": h["file"], "line": h["line"], "rule": h["rule"],
                       "why": KNOWN[k],
                       "matched_by": ("line" if (h["file"], h["line"], h["rule"]) == k
                                      else "anchor(行号漂移 %d→%d)" % (k[1], h["line"]))}
                      for h, k in zip(hits, _keys) if k],
           "known_open_count": len(known_open),
           "unreadable": unread, "skipped_dirs": sorted(SKIP_DIRS), "roots": roots,
           "note": ("走 AST，不做文本匹配（文本匹配在本会话误报过四次）。"
                    "A/B/C/E = **恒真或恒假**；D = 判据被 `except: pass` 吞掉。"
                    "**本器不判『这条判据该不该存在』** —— 只判『它还有没有可能红』。")}
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("═══ 恒真判据审计 ═══")
        print("扫了 %d 个 .py（根：%s）· **待处理 %d 条** · 已登记豁免 %d 条（其中**已知弱项未修 %d 条**）"
              % (files, "、".join(roots), len(live), len(rep["exempt"]), rep["known_open_count"]))
        print("跳过的目录：%s（**跳过可见**，不静默）" % "、".join(rep["skipped_dirs"]))
        if unread:
            print("读不到/解析不了 %d 个（**不算干净**）：" % len(unread))
            for u in unread[:8]:
                print("   · %s" % u)
        for h in live:
            print("  🔴 [%s] %s:%d —— %s" % (h["rule"], h["file"], h["line"], h["why"]))
        if rep["exempt"]:
            print("  ── 已登记豁免（**带理由、可见**）──")
            for e in rep["exempt"]:
                print("  ⚪ [%s] %s:%d\n       %s" % (e["rule"], e["file"], e["line"], e["why"]))
        if not live:
            print("  ✅ 没有『还活着』的恒真/恒假判据（豁免项见上）")
        print("边界：%s" % rep["note"])
    return 1 if rep["hits"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
