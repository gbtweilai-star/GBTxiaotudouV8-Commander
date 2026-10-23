# gbt-capability: 错报审计器（把"会骗人的判据"逐个揪出来）
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""错报审计器 —— Owner 2026-09-22：「我不想看到还有错报」。

═══ 为什么需要它 ═══
"错报"在本仓不是一种小毛病，是一整类病，我自己就反复犯：
  · **假绿**：链路断了还报成功（假收口 / `_persist` 从没调用 / 导入失败被 pass 吞 / 桶标签撒谎）
  · **误报**：关键词把**注释**当调用；把本仓**已登记的例外**（家规第 10 条占位）当断链；
    正则不吃数字 ⇒ 把 `h1`/`brain`/`new` 这些**存在的**口报成"缺失"
  · **未知当缺失**：分不清"我查了、它不在"与"我没查到" —— 后者只能报 unknown
  · **拍脑袋阈值**：`模块数 < 120 才算轻量`（实测 215）
  · **断言因果的消息**：错误串写死成因（"取不到：没有接上宿主进程"），而真因是端点不存在
本器把这些**判据形态**做成可机检规则 —— 人凭印象说"没有了"不算数。

═══ 判据（每条独立规则号）═══
  FR-1 关键词判据     拿 `"x" in 文本` 当判定（"提到"被当成"用了"）
  FR-2 未知当缺失     报 missing/缺 的路径里没有 unknown 分支
  FR-3 未实测阈值     判据里出现裸数字比较，且邻近没有实测依据的注记
  FR-4 断言因果       错误/原因消息里写死因果（"因为/说明/所以/证明"）
  FR-5 静默 except    `except: pass` —— 连一行都不留（错误的沉默）
  FR-6 窄字符类       用 `[a-z_]+` 之类匹配标识符（会漏掉数字/大写 ⇒ 假缺失）
  FR-7 假绿词         报里出现"已接线/已生效/已固化/全绿/无问题"而同行无读数或断言指引

两把对照：正对照（种进去的错报形态**必须**被抓到）+ 负对照（AST/实测判据**不许**被误伤）。

用法：
    py -3.14 -m gbt_allinone.tools.false_report_audit                 # 默认扫整个 gbt_allinone/ 包
    py -3.14 -m gbt_allinone.tools.false_report_audit --scope workspace   # 整个工作区
    py -3.14 -m gbt_allinone.tools.false_report_audit --root gbt_allinone --json
    py -3.14 -m gbt_allinone.tools.false_report_audit --selftest

（上面第一行原来写的是"默认扫 tools+tentacle"，**是假的** ——
 `_targets` 还接了第三个根 `gbt_allinone` 本身，等于整包。第 46 轮改正。）
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_scope import SKIP_DIRS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# ── 扫描范围（2026-09-22 第 46 轮加）────────────────────────────────────────
# 由来：默认分母**只有包内**（gbt_allinone/ 345 个 .py），而工作区在**同一套排除目录**下
# 有 716 个 .py ⇒ **371 个（51.8%）从来没被这个审计器看过**（最大一块
# tools/codex-scripts 225 个 —— 我那批探针和审计工具自己就住在里面）。
# 屏幕上却只打「扫过 345 个 .py（排除目录：…）」——**不写范围**，
# 读者（包括我）会把「命中 0 条」读成"整个工作区没有错报"。**分母不写清 = 错报。**
# 实测（`--scope workspace` 的影响面）：会多出 **17 条**命中
# （FR-1×7 / FR-6×6 / FR-2×3 / FR-5×1），落在 tools/codex-scripts · holo_pet/tests · brain。
# ⇒ 处理办法：**范围显式上屏** + 给一个 `--scope workspace` 开关；
#    **默认值不动**（动了等于偷偷换掉基线，读数就不可比了）。
SCOPE_PACKAGE = "gbt_allinone"       # 默认：只扫本包（现状不变，与历史基线可比）
SCOPE_WORKSPACE = "workspace"        # 整个工作区（同一套 SKIP_DIRS 排除）
SCOPE_CHOICES = (SCOPE_PACKAGE, SCOPE_WORKSPACE)

RULES = {
    "FR-1": "关键词判据：把『提到』当『用了』",
    "FR-2": "未知当缺失：没有 unknown 分支，却报 missing/缺",
    "FR-3": "未实测阈值：判据里的裸数字没有实测依据注记",
    "FR-4": "断言因果：消息里写死成因",
    "FR-5": "记录形成处的静默：try 里在写账本/记录，失败却无声 ⇒ 产物看起来完整、实际缺行",
    "FR-6": "窄字符类：匹配标识符却不吃数字/大写",
    "FR-7": "假绿词：报『已完成』却没有读数或断言指引",
    "FR-8": "分母/分子不符：报了全量数字却只检查了一部分，**且没给这件事起名**",
}

# ── 已**退役**的规则：登记退役理由，不是悄悄删掉（与"登记必须带理由"同源）──────
# 判据：把真仓命中**逐条读完**之后，若 100% 是误报 ⇒ 错的是规则，不是那 N 个"问题"。
RETIRED_RULES = {
    "FR-3": (
        "未实测阈值",
        "第 16 轮真仓 58 条**逐条读完：没有一条是该病** —— HTTP 状态码(200/400/499/500/600)、"
        "ASCII 可打印区(32/126)、百分比(80/85/90)、时间预算与冷却(12/30/60s)、"
        "窗口与屏幕几何(150/200/400/700)、千分位格式化(1000)、递归深度(10/12)、"
        "产品评分线(20/30/40/50/55)、时刻分支(hour<12/14/18/23) —— 全是**领域常量**。"
        "⇒ 结论：模式判不出『这个数字有没有实测依据』；判不出来的东西报出来就是制造错报"
        "（第 26/31/32 条）。**退役。**"),
    "FR-4": (
        "断言因果",
        "第 17 轮真仓 18 条**逐条读完：没有一条是该病**。根因是一个**假朋友词**："
        "「说明」在中文里既是 explain（解释）也是 indicates（表明）—— 我的词表把它当成了"
        "『写死成因』的标记。实测命中全是 explain 义或**由数据推出的正确结论**："
        "「全是静音 —— 说明此刻系统没在出声」（实测推出）· 测试里「没抓到帧必须说明原因」·"
        "`auto_switch.py` 里那一串 `(\"推理\",\"权衡\",\"证明\",…)` **只是关键词列表**（数据）·"
        "「说明本仓其实有这一行」（名字比对推导）· 我本轮自己写的「⇒ 说明我没读到真源码」"
        "（带 未测不按绿 的诚实限定）· 「机器不能证明自己没漏」（一句**定律陈述**）。"
        "⇒ 「因为/说明/所以/证明」是**普通议论文连接词**，不是可判特征。**退役。**"),
}

# 判定性关键词上下文（出现这些词，说明该 `in` 是在**判**而不是在**找**）
JUDGE_HINT = ("if ", "return", "ok", "hit", "found", "match", "warn", "add(", "fail")
# 🔴 2026-09-22 第 45 轮删（只写不读普查抓出来的）：这里原来还躺着三张词表 ——
#    `MEASURED_HINT` / `NEG_MEASURED`（FR-3 用）/ `CAUSAL_WORDS`（FR-4 用）。
#    那两条规则已在 `RETIRED_RULES` **退役**（理由登记在那边），词表随之变成死代码：
#    全文件只有定义处、没有任何读取处（普查口径：全工作区 2655 文件 / 30.8MB 索引）。
#    ⇒ 删掉。**退役要退干净**：规则退了、它的词表还留着，下一个人会以为它还在跑。
FALSE_GREEN_WORDS = ("已接线", "已生效", "已固化", "全绿", "无问题", "已闭环", "全部通过")
NARROW_CLASS = re.compile(r"\[a-z_\+\]\s*\+|\[a-z_\]\+|\[A-Za-z_\]\+")
# 「记录/声明形成」类调用：try 里在写这些而失败无声 ⇒ **产物看起来完整**（第 31 条）。
# 第 19 轮收窄用：探测/强转类静默最坏只是功能降级，不产生假声明，故不再一律报。
RECORD_CALLS = ("audit(", "locked_append_text", "atomic_write", "json.dump(",
                ".write(", "checkpoint(", "record(", "log_event", "persist", "save(",
                "append_jsonl", "_note(", "flush(")
# ⚠️ 第 29 轮修：`"json.dump"` 是 **`json.dumps` 的前缀** ⇒ 会把"序列化成字符串"
#    误判成"写盘了"（`mcp_bridge` 那块就是 `stdin.write(json.dumps(...))` 被这么误报的）。
#    **判据里的函数名必须带左括号**，否则子串匹配会一路骗下去。


def _samples():
    """正/负对照样本（正对照里每一种错报形态各一份）。

    ⚠️ **样本之间必须留出间距**（第 37 轮实测教训）：FR-7 的判据是
    「匹配行 + 后 5 行内不许出现证据字段（checked/count/verified/total…）」——
    我把 FR-8 的样本函数**紧跟在 FR-7 那行后面**，里面有个 `checked = 0`
    正好落进那 5 行窗口 ⇒ **FR-7 的正对照被我自己的新样本压哑了**（漏=['FR-7']）。
    ⇒ FR-8 的样本放**前面**，FR-7 那行仍留在 `check()` 的末尾。
    """
    bad = '''
import re


def census(tree):                             # FR-8：分母全量、结论抽样、且没起名
    all_files = list(tree.rglob("*.json"))
    n = len(all_files)
    bad_rows = []
    for f in all_files[:150]:
        bad_rows.append(f)
    return {"json_files": n, "corrupted": bad_rows}


def check(txt, n, routes):
    if "mirror_space.ascend" in txt:          # FR-1 关键词判据
        return {"ok": False, "missing": ["x"], "why": "说明它绕过了门"}   # FR-2 + FR-4
    if n < 120:                               # FR-3 未实测阈值
        return {"ok": False}
    eps = re.findall(r"/api/([a-z_]+)", txt)  # FR-6 窄字符类
    try:
        locked_append_text("x", {"k": 1})     # ← **裸记录调用**（FR-5 收窄后的前提：
                                              #    `audit(` 已保证永不抛，故不再算）
        go()
    except Exception:
        pass                                  # FR-5 记录形成处的静默
    return {"status": "已接线"}                # FR-7 假绿词
'''
    good = '''
import ast
def check(tree):
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name == "one_key_deploy":
                calls.append(node.lineno)
    unknown = []
    missing = [c for c in calls if c not in (1, 2)]
    if unknown:
        return {"ok": False, "unknown": unknown}
    return {"ok": not missing, "missing": missing}
'''
    return bad, good


_WALK_ATTRS = {"rglob", "glob", "iterdir", "walk", "scandir"}
# 覆盖口径的**命名词表**（FR-8 的诚实边界写在函数 docstring 里：这一步是命名约定）。
# 🔴 第 42 轮补：第一版的词表里**没有第 41 轮自己立的那套词**
#    （truncated / total / examined / available / count_note）——
#    后果是**修好的代码会被自己的规则报出来**（假阳性）。
#    这是校准器抓出来的：负对照「同形状但给了口径」当时被判红。
#    ⇒ **改了判据一定要回头校准**：词表与"本仓实际用的口径词"必须同步。
_COVERAGE_WORDS = ("coverage", "checked", "verified", "sampled", "attempted",
                   "window", "ok_scope", "unreadable", "complete", "分母", "分子",
                   "truncated", "total", "examined", "available", "count_note")


def _fr8_denominator_without_coverage(txt: str, rel: str) -> list:
    """FR-8 · 结构判据（不是关键词）：**报了全量数字，却只检查了一部分，而且没给这件事起名**。

    形状（同一函数内三条同时成立）：
      ① 分母来自遍历：`n = len(X)`，X 是 `rglob/glob/iterdir/walk/scandir` 的结果
         （含一层数据流：`all_x = list(tree.rglob(...))` 之后 `len(all_x)` —— 同一件事换个写法，
          第 37 轮实测：只认一步写法会把已知样本漏掉，**报 0 的普查必须先证明自己看得见已知样本**）；
      ② 有**切片** `[:k]` 或 `islice` —— 说明只拿了一部分来干活；
      ③ `return` 的字典里带上了 ① 的分母 —— 全量数字被交了出去。

    ⚠️ **诚实边界（必须写明）**：判断"有没有起名"用到的是一份**命名词表**
    （coverage/checked/window/...）。这一步**是命名约定，不是结构推断** ——
    结构上无法知道 `{"json_files": n}` 背后是抽样还是全量。
    所以本规则的口径写死为：**"没给覆盖口径起名"**，而不是"抽样"本身。
    起了名就不开火 —— 这正是第 37 轮 selfscan 的修法（抽样是必要的：实测生产 store
    2681 个 .json 全量解析要 2317ms，超 selfscan 的 500ms 预算）。

    解析不了 ⇒ 返回空（**未知 ≠ 无罪**，但本器只报有把握的；这条边界与 source_judge 同源）。
    """
    try:
        tree = ast.parse(txt)
    except SyntaxError:
        return []
    out = []

    def walk_derived(fn) -> set:
        names, changed = set(), True
        while changed:
            changed = False
            for n in ast.walk(fn):
                if not isinstance(n, ast.Assign):
                    continue
                src = n.value
                if isinstance(src, ast.Call) and isinstance(src.func, ast.Name) \
                        and src.func.id in ("list", "sorted", "set", "tuple") and src.args:
                    src = src.args[0]
                ok = any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                         and x.func.attr in _WALK_ATTRS for x in ast.walk(src))
                if not ok and isinstance(src, ast.Name):
                    ok = src.id in names
                if ok:
                    for t in n.targets:
                        if isinstance(t, ast.Name) and t.id not in names:
                            names.add(t.id)
                            changed = True
        return names

    def _is_cap(node) -> bool:
        """是不是"切片/上限"痕迹：`x[:k]` 或 `itertools.islice(...)`。"""
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            return True
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "islice":
                return True
            if isinstance(f, ast.Name) and f.id == "islice":
                return True
        return False

    def suspect_containers(fn, walk_names) -> set:
        """可能"只装了看过的那一部分"的容器名（**本仓实测过的三种真形状**）。

        ① `x = <walk 派生>[:k]`                                  —— 直接切片
        ② `x = []` / `list()`，再在 `for … in <walk/切片>` 里 `x.append(...)` —— 边遍历边收集
        ③ ① 再经 `sorted(...)` / `list(...)` 包一层

        🔴 第 42 轮加：起因是**同一个病在本仓被修了三次**
        （`agency_tentacles.catalog` / `pipeline.list_records` / `collab_gateway.inbox`），
        而 FR-8 第一版**一个都没抓到** —— 它只认 `n = len(<walk>)` 这种"直接数遍历结果"的写法，
        而真形状是"**先切片、再在循环里收集、最后数收集到的那个 list**"或
        "**内联写成 `min(len(rows), limit)`**"。
        ⇒ 规则不认得真形状，就等于没有规则（第 64 条：报 0 的检测器必须先能命中已知样本）。
        本函数**只挑候选，不判对错**；是否开火还要看"返回值里报的是不是它的 len"且"没给覆盖口径"。
        """
        capped = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and _is_cap(n.value):
                base = n.value.value
                if (isinstance(base, ast.Name) and base.id in walk_names) or \
                        any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                            and x.func.attr in _WALK_ATTRS for x in ast.walk(base)):
                    capped |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        # ② 空容器 + append/add，且函数里存在"遍历 walk/切片"的 for
        loop_iters = []
        for n in ast.walk(fn):
            if isinstance(n, ast.For):
                it = n.iter
                if _is_cap(it):
                    loop_iters.append(True)
                elif isinstance(it, ast.Name) and it.id in (walk_names | capped):
                    loop_iters.append(True)
                elif any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                         and x.func.attr in _WALK_ATTRS for x in ast.walk(it)):
                    loop_iters.append(True)
        collectors = set()
        if loop_iters:
            emptied = {t.id for n in ast.walk(fn) if isinstance(n, ast.Assign)
                       and ((isinstance(n.value, ast.List) and not n.value.elts)
                            or (isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                                and n.value.func.id in ("list", "set", "dict")))
                       for t in n.targets if isinstance(t, ast.Name)}
            grown = {n.func.value.id for n in ast.walk(fn)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and n.func.attr in ("append", "add") and isinstance(n.func.value, ast.Name)}
            collectors = emptied & grown
        # 三个集合都交出去：suspect 用于"数的是谁"，capped/collectors 用于"内容有没有被截"
        return walk_names | capped | collectors, capped, collectors

    def _counts_container(node, suspects) -> bool:
        """这个表达式里有没有"数 suspect 容器"的动作：`len(x)` 或 `min(len(x), k)`。"""
        for c in ast.walk(node):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "len" \
                    and c.args and isinstance(c.args[0], ast.Name) and c.args[0].id in suspects:
                return True
        return False

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        walk_names = walk_derived(fn)
        suspects, capped, collectors = suspect_containers(fn, walk_names)
        if not suspects:
            continue
        # 至少要有一处"**截断/上限真的落在了数据上**"的痕迹。只认两种：
        #   ① 容器内容被截：`x = <walk>[:k]`，或 `for … in <walk/容器>[:k]`（收集到的就是一部分）
        #   ② 返回的字典里直接出现 `x[:k]`（清单被截）
        # 🔴 第 42 轮二次收紧：第一版只要求"函数里出现过任意切片" ⇒ 字符串截断
        #    （`desc = _desc_of(sk)[:180]`）把诚实函数带红；
        #    收紧到"切片基是容器"后，`devour.innovate` 仍被带红 —— 因为它的
        #    `innovations[:5]` 是**写在提示消息字符串里**的展示截断，而**返回的计数是全量**。
        #    ⇒ 再收紧：切片必须**在数据链上**（是容器的切片），或**在返回的字典里**。
        def _slice_in_returns(fn) -> bool:
            for n in ast.walk(fn):
                if not (isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)):
                    continue
                for v in n.value.values:
                    for c in ast.walk(v):
                        if isinstance(c, ast.Subscript) and isinstance(c.slice, ast.Slice):
                            base = c.value
                            if isinstance(base, ast.Name) and base.id in suspects:
                                return True
                            if any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                                   and x.func.attr in _WALK_ATTRS for x in ast.walk(base)):
                                return True
            return False

        def _cap_on_container(fn, suspects) -> bool:
            for n in ast.walk(fn):
                if not _is_cap(n):
                    continue
                base = n.value if isinstance(n, ast.Subscript) else None
                if isinstance(base, ast.Name) and base.id in suspects:
                    return True
                if base is not None and any(
                        isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                        and x.func.attr in _WALK_ATTRS for x in ast.walk(base)):
                    return True
                # islice(<walk/suspect>, k)
                if isinstance(n, ast.Call) and n.args:
                    a0 = n.args[0]
                    if isinstance(a0, ast.Name) and a0.id in suspects:
                        return True
                    if any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                           and x.func.attr in _WALK_ATTRS for x in ast.walk(a0)):
                        return True
            return False

        # ① 容器内容被截：`x = <walk>[:k]`（capped），或"收集器的来源本身被截"
        #    （`for p in <walk>[:k]: rows.append(...)` —— agency_tentacles 就是这个形状）。
        #    ⚠️ 注意：**不能**把"凡是在循环里收集"都算成截断 —— 那会把
        #    `topic_watch.catalog`（全量收集）再次带红。必须是"来源被截"。
        def collector_over_capped(fn, capped_names, collector_names, suspect_names) -> bool:
            if not collector_names:
                return False
            for n in ast.walk(fn):
                if not isinstance(n, ast.For):
                    continue
                it = n.iter
                if isinstance(it, ast.Name) and it.id in capped_names:
                    return True
                # `for x in <…>[:k]` —— **切片的基必须是遍历结果或 suspect 容器**。
                # 🔴 第 43 轮收紧：原来只要求"iter 是切片"，于是
                #    `for gap in dom_data.get("gaps", [])[:3]`（**数据结构里的展示用切片**）
                #    也被当成"来源被截"，把诚实的 `devour.innovate` 带红。
                if _is_cap(it):
                    base = it.value if isinstance(it, ast.Subscript) else (
                        it.args[0] if isinstance(it, ast.Call) and it.args else None)
                    if isinstance(base, ast.Name) and base.id in (capped_names | suspect_names):
                        return True
                    if base is not None and any(
                            isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                            and x.func.attr in _WALK_ATTRS for x in ast.walk(base)):
                        return True
            return False

        # 内容被截的两条正路（**不再**用"函数里出现过任意切片"这种松条件 ——
        # 那条会把"提示消息里的展示切片"也算成数据被截）
        contents_capped = bool(capped) or collector_over_capped(fn, capped, collectors, suspects)
        if not (contents_capped or _slice_in_returns(fn)):
            continue
        # 🔴 第 43 轮**撤回**一条尝试：我一度加过"返回值里带了全量 len(...) ⇒ 放行"，
        #    结果**把三条标准正样本全放过了**（agency_tentacles / pipeline / inbox）——
        #    因为 `suspects` 里同时含"被截的容器"和"全量来源"，
        #    `len(rows)` 这种**被截计数**也被当成了"全量分母"。
        #    要继续这条路，得先能可靠区分"这个容器自己有没有被截"，那是另一件工程。
        #    ⇒ 本轮的取舍：**不为个别假阳性把规则越改越松/越绕**；
        #      假阳性走 `KNOWN_LEGIT` 登记（**带理由、可见**），
        #      保住四条标准形状的召回。规则一旦绕到没人能复核，它自己就成了新的错报源。
        # 被报出去的数字：① 先赋值再返回（老形状）② 内联写在返回的字典里
        reported = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and _counts_container(n.value, suspects):
                reported |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)):
                continue
            keys = {k.value for k in n.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if any(w in k for k in keys for w in _COVERAGE_WORDS):
                continue          # 已经给覆盖口径起了名 ⇒ 不开火
            hit = _counts_container(n.value, suspects) or bool(
                {x.id for x in ast.walk(n.value) if isinstance(x, ast.Name)} & reported)
            if not hit:
                continue
            out.append({"rule": "FR-8", "line": n.lineno, "file": rel,
                        "detail": ("函数 %s 把『全量分母/被切片容器 %s』的条数报出去，"
                                   "而返回值里没有覆盖口径（count/total/truncated/checked…）"
                                   "⇒ 读的人会把『看过的那部分』当成『一共有多少』"
                                   % (fn.name, sorted(suspects)))})
            break
    return out


def audit_text(txt: str, rel: str = "?") -> list:
    """扫一个文件的**判据形态**。
    🔴 窄化说明（第一版 792 条里绝大多数是**本器自己的误报**，实测后逐条收紧）：
      FR-1 原来只要 `"x" in y` 就报 ⇒ 把 `if "__pycache__" not in _.parts`（路径判断）
           与 `if "effort" in payload`（字典键判断）全算成"提到当用了"。
           现要求：右侧是**文本/blob 类变量**，且字面量形如**标识符**（≥4 字符且不含 `.*`）。
      FR-4 原来只要字符串里有"因为/说明"就报 ⇒ docstring 里解释真因也被算上。
           现要求：同行还要有失败语义的键（error/why/reason/denied/missing/fail…）。
      FR-3 原来任何裸数字都报 ⇒ `65536`（缓冲区）也算。
           现要求：数字 < 1024（判据量级），且在 size/len/bytes/buffer 上下文里的不算。
      FR-7 原来 docstring 里的"已接线"也算 ⇒ 现在跳过三引号块内。
    """
    out = []
    lines = txt.splitlines()
    in_doc = False
    _dicts = _dict_spans(lines)          # FR-7 用：证据字段在**被报出去的字典**里找（不用固定行数）

    def add(rule, ln, detail):
        out.append({"rule": rule, "line": ln, "detail": detail, "file": rel})

    for i, line in enumerate(lines, 1):
        s = line.strip()
        # 三引号块跟踪（粗粒度但够用：避免把 docstring 里的词当成"报出来的话"）
        q = line.count('"""') + line.count("'''")
        if q % 2 == 1:
            in_doc = not in_doc
            continue
        if in_doc or s.startswith("#"):
            continue
        # FR-1 关键词判据：只认「拿**源码文本**判有没有用某 API」这一种病。
        # 第二轮实测又抓到 4 条我自己的误报：`"json" in content_type`（判 MIME 类型）、
        # `"result" in body`（判字典键）、`"mobile" in html`（判页面内容）都是正当判断。
        # 故加两条硬条件：变量必须是**源码类**，字面量必须**形如 API 名**（含 `_` 或 `.`，≥6 字符）。
        m1 = re.search(r'''["']([^"']{4,})["']\s+(?:not\s+)?in\s+([A-Za-z_]\w*)''', line)
        if m1 and any(h in line for h in JUDGE_HINT):
            lit, var = m1.group(1), m1.group(2).lower()
            srcish = any(k in var for k in ("src", "source", "code", "blob", "txt", "text"))
            api_like = len(lit) >= 6 and re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", lit) \
                and ("_" in lit or "." in lit)
            if srcish and api_like:
                # ⚠️ 但「文本筛 + **紧跟 AST 判**」是**正确的形状**，不是病 ——
                # 我自己在 `ghost_guard` / `stigmergy` 上就是这么修的：文本当廉价前置筛、
                # AST 当判据（真调用必然含该文本 ⇒ 语义等价且不逐文件解析）。
                # ⇒ 同行或后 3 行若有 AST 判据调用，就不算"提到当用了"。
                #   （第 17 轮补：`_uses(src, "x") if "x" in src else False` 这种**同行**写法
                #    第一版没排除掉 —— 排除范围必须包含**同一行**。）
                nxt = line + "\n" + "\n".join(lines[i:i + 3])
                if not any(k in nxt for k in ("_imports(", "_uses(", "calls_attr", "imports_module",
                                              "uses_name", "source_judge", "judge(")):
                    add("FR-1", i, "拿源码文本判『有没有用某 API』（提到 ≠ 用了）：%s" % s[:80])
        # 断言因果：**没有一条是该病** —— `RETIRED_RULES` 里登记了理由。
        # FR-5 静默 except：**只认「记录/声明形成处」的静默**（第 19 轮收窄，先剥行内注释）。
        # 原来报全部 201 处，但两者性质完全不同：
        #   · 探测 / 强转 / 签名自省 失败不吭声 ⇒ 最坏是**功能降级**，不产生假声明；
        #   · **try 里正在写记录/账本/声明**，失败却无声 ⇒ 产物**看起来完整**、实际缺行
        #     —— 这才是错报（第 31 条：有兜底的沉默比崩溃更坏）。
        # ⇒ 收窄为可判形状：**看那个 try 块里有没有"记录形成"类调用**。
        code = s.split("#")[0].strip()
        if code == "pass":
            back = "\n".join(_guarded_block(lines, i - 1))   # 只看它守护的那个 try 块
            if back and re.search(r"^\s*except\b", back, re.M):
                hit = [k for k in RECORD_CALLS if k in back]
                # ⚠️ 例外：`store.audit()` 自 2026-09-22 起**保证永不抛**
                # （内部：文件写失败转内存缓冲 + `_note_audit_failure` 计数出声；
                #   其余异常由薄包装兜住并返回带 `_audit_degraded` 标记的记录，
                #   见 `store.audit` 的 docstring 与 `audit_failures()`）。
                # ⇒ 调用方围着它写 `except: pass` **再也吞不掉记录** ⇒ 不算"记录形成处的静默"。
                #    （其它记录类调用如 `.write(` / `json.dump` 仍是裸的，照样算。）
                hit = [k for k in hit if k != "audit("]
                # ⚠️ `.write(` / `flush(` 也可能是**往 socket / 管道**，那不是"记录形成"（第 28/29 轮）：
                #   `self.wfile.write/flush(...)`（HTTP 流，客户端断连很正常）
                #   `self.proc.stdin.write/flush(...)`（JSON-RPC 管道）
                # ⇒ 接收者像流/管道的，**把这两个一起剔除**。
                #    （第 28 轮只剔了 `.write(`，`flush(` 留在命中里 ⇒ 复扫只掉 1 条而不是 3 条 —— 当场补齐。）
                if re.search(r"(wfile|stdin|stdout|stderr|sock|conn|pipe|socket)\s*\.\s*(write|flush)\(",
                             back):
                    hit = [k for k in hit if k not in (".write(", "flush(")]
                # ⚠️ 自测夹具里的"造样本失败"：失败已被**标志位**如实处理（如 `ads_made = False`），
                #    不是"产物看起来完整"。函数名带 selftest 的一律不算（第 29 轮）。
                if _in_selftest(lines, i - 1):
                    hit = []
                # 但「兜底链上的一步静默 + 链尾如实拒绝」**不是病**（第 27 轮收窄）。
                if hit and not _ends_in_honest_refusal(lines, i - 1):
                    add("FR-5", i, "记录形成处的静默：try 里在写 %s，失败却无声 ⇒ "
                                   "产物看起来完整、实际缺行（第 31 条）" % hit[0])
        # FR-6 窄字符类：第二轮实测那 2 条**全是我的误报** ——
        # 一处前面有 `\w*`（数字已被覆盖），一处同一正则里已有 `[a-z_0-9]`（数字已被覆盖）。
        # 故加两条排除：前面紧跟 `\w*`/`\w+` 的不算；同一行出现含数字的字符类的不算。
        if NARROW_CLASS.search(s):
            covered = re.search(r"\\w[*+]\s*\[a-z_", s) is not None or \
                re.search(r"\[[a-z_]*0-9", s) is not None
            # 第三类排除：`"([a-z_]+)"` 这种**值捕获**（JSON 键值形）不是标识符匹配
            value_capture = re.search(r':\s*\\s\*["\']?\(\[a-z_', s) is not None or \
                re.search(r':\s*"\(\[a-z_', s) is not None
            if not covered and not value_capture:
                add("FR-6", i, "窄字符类匹配标识符（漏数字/大写 ⇒ 假缺失）：%s" % s[:80])
        # FR-7 假绿话术：**只认「状态字段的值本身就是一个绿词」这一种形状**，
        # 且同段**没有任何证据字段**。
        # 🔴 第 15 轮实测：旧规则（"行里出现绿词就算"）38 条里绝大多数是**我自己的误报** ——
        #   · `"reason": "生产前排练未全绿，禁止晋升"` ← 绿词是**门禁条件**，还出现在**被阻断**的返回里
        #   · `"结构性检查全绿；联网段**未验证**"` ← 这是**诚实样板**，主动标了未验部分
        #   · `test_checkpoint.py` 里一句**在解释什么叫假绿**的话被当成了假绿
        #   · 我自己的 `FALSE_GREEN_WORDS` 词表被自己报了（自指噪音）
        # ⇒ 收窄为**可判形状**；判不了的**一概不报**（"误报比漏报更能毁掉检测器"）。
        m7 = re.search(r'''["'](status|verdict|state|result)["']\s*:\s*["']([^"']{0,24})["']''', line)
        if m7 and any(w in m7.group(2) for w in FALSE_GREEN_WORDS):
            # 🔴 第 38 轮修：证据字段在**被报出去的那个字典**里找（不是"后 5 行"，也不是整个函数）。
            #    固定窗口会被同函数内稍远处的一个 `checked` 压哑；而"整个函数"更糟（越大越容易被压哑）——
            #    两个方向都由**正对照**当场量过（见 _dict_spans 注释）。
            #    取不到字典（解析不了本文件 / 不是字典形状）⇒ 退回旧窗口：
            #    **未知不假装知道，但也不静默丢掉这条判据**。
            _d = _innermost_dict(_dicts, i)
            seg = ("\n".join(lines[_d[0] - 1:_d[1]]) if _d
                   else "\n".join(lines[i - 1:i + 6]))
            has_ev = any(k in seg for k in ("checked", "count", "verified", "evidence",
                                            "measured", "total", "passed", "failed",
                                            "lines", "assert", "denied", "blocked"))
            if not has_ev:
                add("FR-7", i, "状态字段报『%s』却同一条报告里无任何证据字段" % m7.group(2))
        # FR-3【已退役 · 2026-09-22 第 16 轮】原判据：行里出现 `[<>] \d{2,}` 且像判据 ⇒ 报。
        # 真仓 58 条**逐条读完，没有一条是该病**（全是 HTTP 码/字符集/百分比/时间/几何/
        # 格式化/深度/评分线/时刻）。模式判不出"这个数字有没有实测依据" ⇒ 退役。
        # 理由登记在 `RETIRED_RULES`，**不是悄悄删掉**。
        # FR-2 未知当缺失：**只对"扫描/覆盖类"文件成立**。
        # 第二轮实测：12 条里多数是我的误报 —— 授权门、权重加载报的 missing 是
        # **查过具体路径/登记表**后的确定结论，不是"没查到"。真正的病只长在扫描器里：
        # 扫到 0 个就断言"不存在"，而没有 unknown 这一档。
        _scanfile = any(k in rel.lower() for k in
                        ("scan", "sweep", "audit", "coverage", "check", "probe", "exhaust"))
        if _scanfile and re.search(r'''["']missing["']\s*[:=]''', line) and "auth" not in rel:
            ctx = "\n".join(lines[max(0, i - 12):i + 12])
            scanish = any(k in ctx for k in ("rglob", "glob(", "scandir", "listdir", "walk(",
                                             "find(", "findall", "re.find", "re.match",
                                             "search", "probe", "is_file", "exists"))
            if scanish and "unknown" not in ctx:
                add("FR-2", i, "扫描器报 missing 却无 unknown 档（查不到 ≠ 不存在）")

    # FR-8 是**函数级 AST** 判据（不是逐行），所以在逐行扫完之后单独跑一遍。
    out.extend(_fr8_denominator_without_coverage(txt, rel))
    return out


def audit(paths, root=ROOT):
    rows = []
    del LEGIT_EXCLUDED[:]           # 每次审计都重置，避免累积假读数
    for p in paths:
        try:
            txt = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/") if str(p).startswith(str(root)) else str(p)
        for f in audit_text(txt, rel):
            if _is_known_legit(f):
                f["known_legit"] = True
                LEGIT_EXCLUDED.append(f)     # 排除要**看得见**：报告里单独列出来
                continue
            rows.append(f)
    return rows


# ── 已判明为**正当用法**的例外：登记必须带理由（与"登记 ≠ 忽略"同源）─────────
# 判据：把真仓命中**逐条读完**后确认它是**对的做法**，不是病。
# 键 = `(规则, 文件, 标记串)` 或 `(规则, 文件, 标记串, 行号)`：
#   · 3 元素：按**标记串**匹配（`标记串 in detail`）—— 文件改名 / 那行被改掉 ⇒ 登记自动失效
#     （**不做文件名免检**，那会随改名失效）。
#   · 4 元素（2026-09-23 第 48 轮加）：**再钉一个行号**，只免那一行。
#     ⚠️ 什么时候**必须**用 4 元素：**当该规则的 `detail` 是固定文案时**（FR-2 就是）——
#     此时标记串**没有行特异性**，3 元素会退化成**整文件免检**：
#     "以后这个文件里任何一行再犯同类病"都会被静默放过。
#     判法（可复核）：`.scratch/legit_scope_audit.py` 逐条量"这条登记实际免掉了几处"；
#     免掉 >1 处、而你又没打算免整文件 ⇒ 就该补行号。
# ── 第 47 轮：`--scope workspace` 报出的 17 条，逐条读完之后的判词（下同）──────────
# 这一批全在被默认口径漏掉的那 371 个文件里，是第 46 轮把范围打开后才**第一次**见到的。
_LEGIT_PROTO_PAGE = (
    "**假阳性，已判明为正当写法**：这里的 `ptext` **不是被审程序的源码**，而是"
    "`PROTO.read_text()` 读进来的**可交互原型 HTML 页面**（实测各 verify_v*.py 的 `PROTO = "
    "\"V<N> GBT小土豆V8-可交互原型.html\"`）。判据问的是「**这个页面上有没有把这个名字/规格写出来**」"
    "（消息里写的就是「上屏」「标注」「界面标注」），而对一份页面产物来说，"
    "**『文本里搜得到』就是这件事唯一正确的判法** —— 不存在『被调用的 API 与注释里的提及』那种区分。"
    "⇒ FR-1 的前提（拿**源码**文本判『有没有**用**某 API』）在这里不成立。"
)
KNOWN_LEGIT = {
    ("FR-1", "gbt_allinone/tests/test_nav_etiology.py",
     '"_record_swallow" not in txt.splitlines()'):
        "测试内部的**结构性检查**：判断某处是否落在收口函数自己的定义窗口内。"
        "受众是测试自己、判的是源码窗口位置，不是『某 API 有没有被用』。",
    ("FR-1", "gbt_allinone/truth_scan.py", "'needs_dependency' in txt"):
        "判的是 **run_task 的响应载荷**（能力返回里有没有 needs_dependency / stub_gaps 标记），"
        "**不是源码** —— 对响应做键检查是正当判据（第 8 轮已逐条判明）。",
    # ── 第 30 轮登记：逐条判明为**有意为之**的静默（登记 ≠ 忽略，理由写在下面）──
    # ⚠️ marker 匹配的是 **`detail` 字段**（内容形如「记录形成处的静默：try 里在写 <记录调用>…」），
    #    所以这里只能填**记录调用的名字**，不能填源码里的注释/特征串 ——
    #    第一版我填了 `"留痕失败不能反过来把拒收变成接收"` 与 `"fh.write("`，**两条都没匹配上**（当场复扫发现）。
    #    文件路径已足够区分这两处。
    ("FR-5", "gbt_allinone/knowledge_base.py", ".write("):
        "**有意且失败方向安全**：这段写的是「拒收留痕」。留痕失败时**仍然保持拒收** —— "
        "即沉默发生在「记账」侧，而**后果侧（拒收）没有被放宽**。反过来把拒收变成接收才是灾难；"
        "代码注释里已把这条取舍写明（`knowledge_base.py:124` 行尾）。",
    ("FR-5", "gbt_allinone/deploy/codex_relay_watchdog.py", ".write("):
        "**弱**：写的是守护进程自己的**诊断日志行**（拉起代理前记一句），不是后果记录；"
        "日志缺一行的后果是「排查时少一条线索」，不是「产物看起来完整」。"
        "**未修**，如实登记为已知的弱项（不假装它不存在）。",
    # ── 第 43 轮登记：FR-8 的唯一假阳性（**逐条读完确认它是正当写法**）──
    ("FR-8", "gbt_allinone/devour.py", "created"):
        "**假阳性，已判明为正当写法**：`innovate()` 里那几处切片都不是数据被截 —— "
        "`innovations[:5]` 是**提示消息里的展示截断**、`[:50]` 是字符串截断；"
        "而被循环收集的 `created` 建的是**另一个集合**（本轮新造的 cap），"
        "返回值里同时给了 `concepts_found=len(innovations)`（全量概念数）与 "
        "`created=len(created)`（本轮造出来的个数）—— 两个数各说各的事，读者不会被误导。"
        "⚠️ 我一度想给规则加『返回值里有全量 len(...) 就放行』来消掉它，"
        "结果**把三条标准正样本一起放过了**（`suspects` 里同时含被截容器与全量来源）⇒ 撤回。"
        "**规则不能为个别假阳性越改越松**；假阳性走登记（带理由、可见）。",
    # ── 第 47 轮登记：`--scope workspace` 首次看见的 17 条（逐条读完）────────────
    # 【6 条 FR-1 · verify_v*.py】同一个理由（原型页面文本判据，见上面的 `_LEGIT_PROTO_PAGE`）。
    #   6 条共用一个判词常量，避免六份措辞慢慢漂开、下一个人要读六遍才知道是同一件事。
    #   ⚠️ 注意这些件在**默认口径之外**（`tools/codex-scripts/`）；要复核得加 `--scope workspace`。
    ("FR-1", "tools/codex-scripts/verify_v4.py", 'audit.jsonl" in ptext'): _LEGIT_PROTO_PAGE,
    ("FR-1", "tools/codex-scripts/verify_v7.py", 'list_workflows" in ptext'): _LEGIT_PROTO_PAGE,
    ("FR-1", "tools/codex-scripts/verify_v7.py", 'desktop_control" in ptext'): _LEGIT_PROTO_PAGE,
    ("FR-1", "tools/codex-scripts/verify_v9.py", 'deploy_publish" in ptext'): _LEGIT_PROTO_PAGE,
    ("FR-1", "tools/codex-scripts/verify_v9.py", 'store.audit" in ptext'): _LEGIT_PROTO_PAGE,
    ("FR-1", "tools/codex-scripts/verify_v10.py", 'workspaceFiles.list" in ptext'): _LEGIT_PROTO_PAGE,
    # 【2 条 FR-2 · quick_scan.py】本机文件系统是**权威**，不存在"查不到"这一档。
    #   FR-2 的前提是「查不到 ≠ 不存在」—— 那要求查找**可能查不成**（网络/解析/权限）。
    #   这里 `pathlib.Path(t).exists()` 是本地系统调用：要么 False（真不在），要么抛异常（不会被静默吞掉）。
    #   ⇒ 没有第三档可加，不是漏了 unknown。
    #   ⚠️ 2026-09-23 第 48 轮：**这两条必须分成两条、并各自带行号**。
    #      原来写成一条 3 元组，实测**一条免掉 2 处**（`[555, 677]`）⇒ 退化成整文件免检。
    #      行号是**规则真正开火的那一行**（含 missing 键的字典字面量）：
    #      `:695` = `scan_panels()` 的登记表字典；
    #      `:833` = 定时任务那条。
    #      ⚠️ 2026-09-24 第 94 轮：这两个行号**又漂了一次** —— 当天编辑 `quick_scan.py`
    #         （修 `_declared_covers` 的 `Path` NameError、给台账 `flags` 补面选择、
    #          加注释等）把它们从 555/693 推到 695/833。
    #      🔴 **2026-09-25 实测：又漂了一次，695/833 → 825/1119。**
    #         而且这次漂移的处置方法**就写在被审计文件自己的注释里**
    #         （`tools/codex-scripts/quick_scan.py` L1108-1111 明写「本行以上新增了注释 ⇒
    #         带 missing 键那一行的行号会变，必须同步更新 KNOWN_LEGIT 里带行号的那条登记」）——
    #         **预告了、写了办法、然后没做。** 于是 `test_false_report_audit.py`
    #         长期红着，而对外口径仍是"自检全过"。
    #         ⇒ 教训不是"锚点会漂"（那早就知道），是**红着的判据没人管**：
    #           判据立了不等于门关上了，**红必须当场处置，否则它只是一行装饰**。
    #         **没有手填**：跑 `false_report_audit.audit()` 让它自己报出 FR-2 的开火行，
    #         再按读到的数字对齐（审计的输出才是权威，记忆和推算都不是）。
    #         ⇒ 这正是下面那条判据（`test_every_line_anchored_entry_adds_something`）
    #         存在的意义：它在提交前就把这次漂移抓红了，逼我改锚点而不是让它静默失效。
    #      ⚠️ **这类行号会随编辑漂移** —— 所以第 48 轮同时立了一条判据
    #      （`test_every_line_anchored_entry_adds_something`）：
    #      锚点填错/漂移 ⇒ 那条登记**一处都免不掉** ⇒ 判据立刻变红，逼你改锚点。
    #   （FR-2 的 `detail` 是固定文案 ⇒ **标记串在这里没有行特异性，只有行号有**。）
    #      🔴 **2026-10-17 第三次漂移：825/1119 → 837/1131**（`quick_scan.py` 又长了 12 行）。
    #         处置照旧：**跑 `audit()` 让它自己报开火行**，不手推。
    #         ⚠️ 这已经是同一处锚点第三次漂 ⇒ 说明"手填行号"这条机制在漂移面前必然腐烂；
    #         真正的加固方向是**自动重算锚点**（见 2026-10-17 日报 · 待办），不是再修一次数字。
    ("FR-2", "tools/codex-scripts/quick_scan.py", "查不到 ≠ 不存在", 837):
        "本地 `Path.exists()` 是权威判定，FR-2 前提不成立（面板登记表 ↔ 盘上实物）。",
    ("FR-2", "tools/codex-scripts/quick_scan.py", "查不到 ≠ 不存在", 1131):
        "本地 `Path.exists()` 是权威判定，FR-2 前提不成立（定时任务目标）。"
        "同一行的 `missing[:4]` 另有**静默截断**问题 —— FR-8 的形，第 48 轮已修"
        "（补 `targets_total`/`outside_repo_total`/`missing_total` + `count_note`）。",
    # 【1 条 FR-2 · audit-regulations.py】它把"某个面**没按预期措辞出现**"记为 missing。
    #   第 48 轮同样加上行号 `:54`（那条登记原来也是整文件免检）。
    #   2026-10-17：`:54 → :53`（再次漂移；照旧由 `audit()` 自己报开火行，不手推）。
    ("FR-2", "tools/codex-scripts/audit-regulations.py", "查不到 ≠ 不存在", 53):
        "**登记理由（带一层保留）**：四个面是用**词形/正则**在本地全文里找的，"
        "而文本**就在本地、完整可读** —— 所以状态不是『未知』，而是『没按这套措辞出现』。"
        "本器自己在输出里写明了口径：「**本器不判内容对错**…只把四个面缺没缺变成可数读数」"
        "⇒ 它是**覆盖率指示器**，不是『不存在』的断言，读者不会被误导到「查不到=没有」。"
        "实测（第 47 轮）：59 件里只有 1 件被标缺 —— `gbt-dangerous` 缺「未验账」，"
        "而 `grep 未验 skills/gbt-dangerous/SKILL.md` **零命中** ⇒ 这一条**判对了**，不是假缺失。"
        "保留：若哪天它把『措辞不同』当成『没有』从而让人误判，就该改成显式三档（missing/unmatched）。",
    # ── 第 48 轮（续）登记：`--scope workspace` 第 2 次跑看见的最后 2 条 FR-1（逐条读完）──
    #   ⚠️ 这两条与上面 6 条 verify_v*.py **不同**：那 6 条是"判页面产物文本"，这两条不是。
    #      逐条给了各自的理由 —— **不许合并成一条共用判词**，因为它们成立的原因不一样。
    ("FR-1", "tools/codex-scripts/audit_craft_gate.py",
     'Extended_Pictographic" in V21_SRC', 40):
        "**假阳性，判明为正当写法**：这是**元审计** —— 它去读 `verify_v21.py` 的源码，"
        "为的是判断**那个文件到底发了哪一套 emoji 判据**（Unicode 属性口径 or 旧的窄字符类），"
        "好让本器选一套**与它一致**的正则去复核。"
        "被问的问题字面就是『那份文件里存在的是哪个实现』 —— **源码文本就是被检对象本身**，"
        "不存在 FR-1 说的『被调用的 API 与注释里的提及』那种区分。"
        "带行号 `:40` ⇒ 这行一改，登记自动失效。",
    ("FR-1", "tools/codex-scripts/criterion_bench.py",
     'locked_append_text" in src', 731):
        "**假阳性，判明为正当写法**：这一行**不在生产逻辑里**，而是模块级常量 "
        "`FP_PREFILTER` 的**字符串内容** —— 它是基准器自己的一条**负控样本**"
        "（故意种一个『恒真但不定胜负』的前置筛，用来证明基准器的 D6 规则**只给 🟡、不误报 🔴**）。"
        "审计器读的是**它自己源码里那段样本文本**，不是任何产品的运行时判据。"
        "带行号 `:729` ⇒ 样本一改，登记自动失效。",
}
LEGIT_EXCLUDED: list = []          # 本次审计里被登记例外排除掉的条目（**可见**，不是静默）


def _guarded_block(lines, pass_idx):
    """取这个 `except: pass` **真正守护的那个 try 块**（**不许跨 try/except 边界**）。

    第 22 轮修：原来固定往回看 9 行 —— 于是会越过 `try` 边界，把**外层 try** 里的
    `.write(` 算到**内层 except** 头上。`safe_io.py:245` 就是这么被误报的：
    那个 `pass` 守的是 `os.chmod` 失败（写入本身照旧成功），
    而往回 9 行却够到了外层 `f.write(blob)`。
    ⇒ 改为**从 pass 往回走到最近的 `try:`**，只取那一段；走太远（>14 行）就放弃。
    """
    j = pass_idx - 1
    while j >= 0 and not re.match(r"^\s*try\s*:", lines[j]):
        if j < pass_idx - 14:
            return []
        j -= 1
    return lines[max(0, j):pass_idx] if j >= 0 else []


def _dict_spans(lines):
    """文件里所有**字典字面量**的行区间与键集 `[(start, end, keys), ...]`（解析不了 ⇒ 空表）。

    🔴 第 38 轮加。起因：**FR-7 原来在"匹配行 + 后 5 行"里找证据字段**，固定窗口会两头出错 ——
    看太近就漏报；看太远就把别人的证据算进来。我第一版"修法"是把它扩到**整个函数**，
    结果**更糟**：函数越大越容易在别处撞见一个 `checked`，判据反而更容易被压哑。
    这一点是**我自己的正对照当场抓出来的**（假绿行同函数内 9 行外有个 `checked = 7`，
    期望"仍要开火"，实测 **0 命中** ⇒ 我的修法方向错了）。
    ⇒ 正确的口径是**"被报出去的那个字典"**：读者看到的是那个 dict，
      证据要么在**同一个 dict** 里，要么就等于没有。既不是行数，也不是函数。
    """
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            keys = {k.value for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            out.append((node.lineno, end, keys))
    return out


def _innermost_dict(dicts, idx):
    """包含 `idx`(1-based) 的**最内层**字典字面量；取不到返回 None。"""
    best = None
    for s, e, keys in dicts:
        if s <= idx <= e and (best is None or s > best[0]):
            best = (s, e, keys)
    return best


def _in_selftest(lines, idx) -> bool:
    """`idx` 是否落在**自测夹具**函数里（函数名含 `selftest`）。

    第 29 轮：`scan_engine.selftest` 里造 ADS 样本失败会 `pass`，但它**立刻**把
    `ads_made = False` 记下、后面据此**如实跳过**那条检查 —— 失败**没有**被藏起来，
    只是换了个形式报告。⇒ 自测夹具不算"记录形成处的静默"。
    """
    for j in range(idx, -1, -1):
        m = re.match(r"^\s*def\s+(\w+)", lines[j])
        if m:
            return "selftest" in m.group(1).lower()
    return False


def _ends_in_honest_refusal(lines, idx) -> bool:
    """`idx` 所在函数体里有没有**如实的终局拒绝**（`ok: False` / `raise`）？

    第 27 轮修（收窄 FR-5）：`room_space:576` 那种静默是**兜底链上的一步** ——
    vision_watch 取帧失败就静默退到 `_latest_visual()`，而链尾是
    `return {"ok": False, "error": "没有可共享帧；先启动 vision_watch 或传入 frame_b64"}`。
    调用方拿到的是**如实拒绝**，不是假成功 ⇒ **不算"记录形成处的静默"**。
    真正的病是「失败了却让产物看起来完整」；**有诚实终局的降级不是病**。
    """
    # 往回找所在函数的 def
    start = None
    indent = None
    for j in range(idx, -1, -1):
        m = re.match(r"^(\s*)def\s+\w+", lines[j])
        if m:
            start, indent = j, len(m.group(1))
            break
    if start is None:
        return False
    # 往后找到同/更低缩进的 def（或文件尾）
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"^(\s*)def\s+\w+", lines[j])
        if m and len(m.group(1)) <= indent:
            end = j
            break
    # ⚠️ 只认**静默那一步的下游**（`idx+1` 起）有没有诚实终局 ——
    # 函数体**前面**出现的 `"ok": False` 不算数（那是别的分支）。
    # 第 27 轮实测教训：不加这条，fixture 里位于前面的 `{"ok": False}` 会把 FR-5 压掉 ⇒
    # 正对照以"检测器漏报"的形式误报规则坏了。
    body = "\n".join(lines[idx + 1:end])
    return bool(re.search(r'["\']ok["\']\s*:\s*False', body) or re.search(r"^\s*raise\s", body, re.M))


def _is_known_legit(row) -> bool:
    """这条命中是否被 `KNOWN_LEGIT` 登记免掉。

    🔴 2026-09-23 第 48 轮修（**登记本身会藏错报**）：
      键原来是 `(规则, 文件, 标记串)`，判据是 `标记串 in detail`。
      设计意图（写在 `KNOWN_LEGIT` 上方）是"按**该行**的标记串匹配 ⇒ 那行被改掉，登记自动失效"
      —— **不做文件名免检**。但那条意图**对一部分规则实现不了**：
      **有些规则的 `detail` 是一句固定文案**，既不含行号、也不含那行代码。
      `FR-2` 就是：`detail` 恒为`扫描器报 missing 却无 unknown 档（查不到 ≠ 不存在）`。

      后果**实测**（`.scratch/legit_scope_audit.py`）：`quick_scan.py` 的那条登记
      **一条免掉了 2 处**（`[555, 677]`）⇒ 它实际是**整文件免检**：
      以后该文件**任何一行**再冒出 FR-2 形状，都会被**静默放过**。
      —— 一个为了消假阳性而开的门，**顺手把真阳性也放走了**。

      ⇒ 键允许带**第 4 个元素：行号**。带了就**只免那一行**（多行要写多条）。
        3 元素的旧登记照旧生效（向后兼容，不动既有 11 条）。
    """
    for entry in KNOWN_LEGIT:
        rule, f, marker = entry[0], entry[1], entry[2]
        want_line = entry[3] if len(entry) > 3 else None
        if row.get("rule") != rule or row.get("file") != f:
            continue
        if marker not in row.get("detail", ""):
            continue
        if want_line is not None and row.get("line") != want_line:
            continue
        return True
    return False


def _walk_py(base):
    """按同一套 SKIP_DIRS 递归收集 .py。

    **范围口径只许有这一份实现** —— 谁再手写第二份 `os.walk`，两份就会慢慢长歪，
    于是"扫过几个文件"这个分母又变成没人能核对的数字。
    """
    out = []
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f.endswith(".py"):
                out.append(Path(dp) / f)
    return sorted(set(out))


def _scope_roots(root, scope=SCOPE_PACKAGE):
    """范围的人类可读写法（上屏用）。"""
    if scope == SCOPE_WORKSPACE:
        return [str(root)]
    return [str(root / "gbt_allinone")]


def scope_inventory(root, scope=SCOPE_PACKAGE):
    """把"扫了什么 / 还有什么没扫"一次算清并交出来。

    why：只报「扫过 N 个」而不报「还有 M 个没扫」，正是本器 FR-8 那条病的
    **同形犯**（"报了全量数字却只检查了一部分，且没给这件事起名"）——
    审计器自己犯它在查的病，第 46 轮实测到的。
    返回 `outside` 与 `outside_top`：**范围外的件数和它们住哪，必须能报出来。**
    """
    targets = _targets(root, scope)
    inside = {p.resolve() for p in targets}
    outside = [p for p in _walk_py(root) if p.resolve() not in inside]
    top = {}
    for p in outside:
        try:
            rel = p.relative_to(root)
        except ValueError:
            top["<仓外>"] = top.get("<仓外>", 0) + 1
            continue
        key = rel.parts[0] if len(rel.parts) <= 2 else "/".join(rel.parts[:2])
        top[key] = top.get(key, 0) + 1
    return {"targets": targets, "outside": outside, "outside_top": top}


def _targets(root, scope=SCOPE_PACKAGE):
    if scope == SCOPE_WORKSPACE:
        return _walk_py(root)
    out = []
    for base in (root / "gbt_allinone" / "tools", root / "gbt_allinone" / "tentacle",
                 root / "gbt_allinone"):
        if not base.is_dir():
            continue
        out.extend(_walk_py(base))
    return sorted(set(out))


def selftest(verbose=True) -> int:
    # 正对照必须用**扫描类文件名**跑：FR-2 只对扫描器成立（第二轮实测的收窄），
    # 拿 `<bad>` 这种名字跑，规则根本不可能开火 ⇒ 会误判成"检测器漏报"。
    bad_hits = {f["rule"] for f in audit_text(_samples()[0], "<bad_scanner.py>")}
    good_hits = {f["rule"] for f in audit_text(_samples()[1], "<good>")}
    want = set(RULES) - set(RETIRED_RULES)
    miss = sorted(want - bad_hits)
    false = sorted(good_hits)
    # 已退役的规则**必须不再开火**（正对照样本里仍留着 FR-3 形状那行 `if n < 120:`）
    # —— 退役不是"改个文档"，是"真的不报了"。
    zombie = sorted(set(RETIRED_RULES) & bad_hits)
    if verbose:
        print("═══ 错报审计器 · 两把对照 ═══")
        print("正对照 抓到 = %s" % sorted(bad_hits))
        print("  漏掉     = %s" % (miss or "无"))
        print("负对照 误伤 = %s" % (false or "无"))
        print("退役僵尸   = %s（退役规则不许再开火）" % (zombie or "无"))
        print("已退役：%s" % ", ".join(sorted(RETIRED_RULES)))
        print("结论：%s" % ("两把对照都过 ✅" if not miss and not false and not zombie
                          else "✗ 判红：漏=%s 误=%s 僵尸=%s" % (miss, false, zombie)))
    return 0 if (not miss and not false and not zombie) else 1


def main(argv=None) -> int:                                     # pragma: no cover
    ap = argparse.ArgumentParser(description="错报审计器")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--scope", choices=SCOPE_CHOICES, default=SCOPE_PACKAGE,
                    help="扫描范围：gbt_allinone=只扫本包（默认，与历史基线可比） / "
                         "workspace=整个工作区（同一套 SKIP_DIRS 排除）")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    root = Path(a.root)
    inv = scope_inventory(root, a.scope)
    targets = inv["targets"]
    rows = audit(targets, root)
    by = {}
    for r in rows:
        by.setdefault(r["rule"], []).append(r)
    # 🔴 2026-09-22 第 42 轮修（错报治理 · **审计器自己犯了它在查的病**）：
    #    原来只打 `命中 N 条`，**不报扫了几个文件**。后果实测：
    #    `--root gbt_allinone` 会让 `_targets` 去找 `gbt_allinone/gbt_allinone`（不存在），
    #    结果**只扫了 tentacle/ 一棵树**，却照样打印「命中 0 条」——
    #    与"全仓扫过、真干净"**长得一模一样**。而我在本会话里**反复引用过那个 0**。
    #    ⇒ 分母必须跟着结论走：报扫过多少文件、排除了哪些目录；
    #      一个文件都没扫到时**必须喊出来**（"没扫" ≠ "干净"）。
    rep = {"ok": True, "readonly": True, "root": str(root),
           "scanned_files": len(targets),
           "skipped_dirs": sorted(SKIP_DIRS),
           # 🔴 2026-09-22 第 46 轮加：**范围必须自报**。
           #    实测：默认只扫包内 345 个 .py，同口径下工作区有 716 个 ⇒
           #    371 个（51.8%）从来没被看过，而屏幕上并不写这件事。
           #    「命中 0 条」于是会被读成"整个工作区干净" —— 那是错报。
           "scope": a.scope,
           "scope_roots": _scope_roots(root, a.scope),
           "out_of_scope": len(inv["outside"]),
           "out_of_scope_top": dict(sorted(inv["outside_top"].items(),
                                           key=lambda kv: -kv[1])),
           "scope_note": ("out_of_scope>0 时『命中 N 条』只对本范围成立；"
                          "全工作区口径请加 --scope workspace"),
           "coverage_note": ("命中数只在`scanned_files>0`时才等于『干净』；"
                             "扫不到文件 ≠ 没有问题"),
           "counts": {k: len(v) for k, v in sorted(by.items())},
           # 🔴 2026-09-22 第 43 轮修（错报治理 · **一句没兑现的承诺**）：
           #    `audit()` 里写着「排除要**看得见**：报告里单独列出来」，也确实往
           #    `LEGIT_EXCLUDED` 里塞了 —— 但**全文件再没人读过它**（grep 只有 reset / append / 定义）。
           #    于是"登记例外"实际上等于**静默丢弃**，跟注释承诺的正好相反。
           #    ⇒ 报告必须把它列出来（人类可读 + json 都要有）。
           "legit_excluded": LEGIT_EXCLUDED,
           "legit_excluded_count": len(LEGIT_EXCLUDED),
           "total": len(rows), "rows": rows}
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0
    print("═══ 错报审计 · %s ═══" % root)
    print("范围：%s（%s）" % (a.scope, " · ".join(_scope_roots(root, a.scope))))
    print("扫过 %d 个 .py（排除目录：%s）" % (len(targets), "/".join(sorted(SKIP_DIRS))))
    if not targets:
        print("⚠️ **一个文件都没扫到** —— 这不是『干净』，是『没扫』；"
              "请检查 --root 是否指对（仓根的正确传法是默认值，不要再传 gbt_allinone）")
    print("命中 %d 条：" % rep["total"])
    if inv["outside"]:
        # 「范围外还有多少」必须上屏：不写，读者就会把本范围的 0 读成全仓的 0。
        top = sorted(inv["outside_top"].items(), key=lambda kv: -kv[1])[:5]
        print("⚠️ 本范围**之外**还有 %d 个 .py 没扫（最大几块：%s）——"
              "所以上面的『命中 %d 条』**只对这个范围成立**，"
              "别读成『整个工作区干净』。要全工作区口径：--scope workspace"
              % (len(inv["outside"]), "、".join("%s %d 个" % kv for kv in top),
                 rep["total"]))
    if LEGIT_EXCLUDED:
        # 「登记 ≠ 忽略」：被登记的例外**必须露面**，否则读者以为规则没看见它
        print("（另有登记例外 %d 条，**可见**、不算命中）：" % len(LEGIT_EXCLUDED))
        # 🔴 2026-09-23 第 48 轮修（**版式本身害人读错**）：
        #    「登记例外」与下面的「命中」两段，原来的行版式**一模一样**
        #    （都是 `   <文件>:<行>  [规则] <detail>`）。后果**实测两次**：
        #    我用 `Select-String "\.py:\d+"` 过滤输出时，把**豁免**那些行读成了**命中**
        #    （第 46 轮一次、第 48 轮又一次，第二次还据此误判"豁免失效了"）。
        #    ⇒ 每行前面钉一个**互不相同**的标签，让"这两段长得一样"这件事从根上没了。
        for r in LEGIT_EXCLUDED[:a.limit]:
            print("   豁免 %s:%d  [%s] %s" % (r["file"], r["line"], r["rule"],
                                             r["detail"][:70]))
    for k, v in sorted(by.items()):
        print("   %-5s %-34s %3d 条" % (k, RULES.get(k, ""), len(v)))
    print()
    for k, v in sorted(by.items()):
        print("[%s] %s" % (k, RULES.get(k, "")))
        for r in v[:a.limit]:
            print("   命中 %s:%d  %s" % (r["file"], r["line"], r["detail"][:96]))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
