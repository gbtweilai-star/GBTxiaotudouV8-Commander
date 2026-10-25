# -*- coding: utf-8 -*-
"""代码审美审计器 · 把「AI 代码味」从感觉变成能跑的检查。

这一版补了什么（第二轮 · 2026-09-23）
--------------------------------------
上一版把 M1–M6 六条打成「只能人看」。这一版**把其中能机检的部分全部补上**，
并且**每条新判据都配了正负对照**（`--selftest` 一条命令全验）：

| 原来只能人看 | 现在 | 机检到什么程度 |
|---|---|---|
| M1 命名是否反映意图 | **P1-13** | 只抓三种可机检形状：布尔名不带 is/has/can、超通用函数名、类内上下文重复 |
| M2 抽象是否过度 | **P1-12** | 只给**数量**（单方法类 / 只转发参数的包装），**判不出该不该** |
| M3 与既有约定一致 | **P1-14** | 只查**同一文件内**命名/缩进混用；跨文件约定仍要人读 |
| M4 注释是否诚实 | **P0-6** | 只抓「完成声明 + 空实现」这一种最硬的谎 |
| M5 错误处理是否分级 | **P1-4** | 给**比例**（generic 占比）与**重复**（复制粘贴的 catch） |
| M6 JS/TS 结构度量 | **P1-5 / P1-6** | **已补**：纯 Python 零依赖块匹配（字符串/注释/正则先剥掉再配对花括号） |

另补：**P1-11 跨文件重复块**（原来只查文件内）· **中文叙述性注释**（有界词典）·
**多语言行级判据**（`.php/.rb/.go/.rs/.vue` 只查占位与调试残留，**不做结构度量**）·
**`--selftest`**（校判据 + 校 JSON 结构）· **`--sensitivity`**（量阈值敏感性）。

诚实口径（照仓里《零猜测律》与《资料核实律》）
----------------------------------------------
- Python 走 `ast`；JS/TS 走**自研块匹配**（不引依赖 —— 引了就得管它的安装与版本）；
- 每条规则都有**误报代价**：判据宽一格就会淹掉真问题。所以：排除目录写在 `EXCLUDE_DIRS`、
  行内豁免 `code-taste: ignore-line`、整文件豁免 `code-taste: ignore-file`、阈值全在常量区；
- **没命中 ≠ 有品味。** 人看的清单（M1–M6）每次都会打印，并**标明哪几条现在是"部分机检"**。

用法：
    py -3.14 tools/codex-scripts/audit_code_taste.py <文件或目录> [...]
    py -3.14 tools/codex-scripts/audit_code_taste.py --json out.json <路径>
    py -3.14 tools/codex-scripts/audit_code_taste.py --selftest
    py -3.14 tools/codex-scripts/audit_code_taste.py --sensitivity <路径>

退出码：0 = P0 为 0（P1/P2 可非 0）· 1 = 有 P0（或 selftest 不达预期）· 2 = 用法错或没找到可审的代码。
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())

PY_SUFFIX = {".py"}
JS_SUFFIX = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
# 多语言：**只做行级判据**（占位 / 调试残留 / 空 catch）。结构度量、命名分析**一律不做**。
OTHER_SUFFIX = {".php", ".rb", ".go", ".rs", ".vue"}

# 排除目录：生成物 / 镜像 / 归档 / 第三方。这不是「藏起来」，是「这些不该按本仓手艺判」。
EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "site-packages",
                "dist", "build", ".dsh", ".shadow-repo", "archive", "vendor",
                "_upstream", ".backups", ".trash", ".mypy_cache", ".pytest_cache",
                ".pylibs", "Extensions", "native_browser", "generated-images",
                "infinite-canvas-output", "video-out", "outputs", "render",
                "store", "mirror_space", "room_space", "checkpoints"}

# ── 阈值（都放这里；改之前先跑 --sensitivity 量一遍）──────────────────────
MAX_FUNC_LINES = 80
MAX_NEST_DEPTH = 5
DUP_BLOCK_LINES = 8
SUFFIX_ABUSE_MIN = 3
GENERIC_CATCH_RATIO = 0.5      # P1-4：generic handler 占比阈值
GENERIC_CATCH_MIN = 3          # P1-4：至少这么多个才报（少于此不构成"一把抓"）
JS_CATCH_REPEAT_MIN = 3        # P1-4：同一个 catch 体重复这么多次
MIXED_CONVENTION_MIN = 3       # P1-14：两种命名各至少这么多个才算"混用"

PLACEHOLDER_NAMES = {"foo", "bar", "baz", "qux", "dummy", "placeholder",
                     "mydata", "data1", "data2", "result1", "temp1", "tmp1", "myvar"}

# M1：**超通用函数名**。刻意只收这几个 —— `run`/`get`/`set` 是正当公开 API，收进来就是喊狼来了。
GENERIC_FN_NAMES = {"handle", "process", "do_stuff", "stuff", "misc", "deal_with",
                    "manage", "do_it", "temp_func"}
BOOL_PREFIXES = ("is", "has", "can", "should", "need", "want", "allow", "enable", "use", "was")
# M1 布尔名：🔴 2026-09-23 误报修 —— 第一版**只认前缀**，于是 `in_str = True` / `esc_next = False`
# 这些**合格的状态短语**被判违规（真仓实测 63 文件/155 处噪声）。判据收窄成
# **「什么都没说」的布尔名**（flag/result/value/temp…）；`in_str`/`isLoading` 一律不报。
MEANINGLESS_BOOL = {"flag", "result", "res", "value", "val", "temp", "tmp", "data",
                    "status", "ret", "check", "test", "success", "ok", "done", "todo"}
# M1 叙述性注释：英文路要求**至少一个动作词** —— 否则段落标题里含标识符就会误报
# （实测：`# 2) UI_STRINGS 整体替换`、`# ── gbt_allinone 包内 ──` 都被误判成"复述代码"）。
ACTION_VERBS = {"create", "get", "set", "read", "write", "save", "delete", "remove", "update",
                "check", "validate", "verify", "parse", "load", "compute", "send", "request",
                "return", "build", "init", "scan", "print", "render", "export", "append",
                "insert", "find", "fetch", "convert", "format", "sort", "filter", "merge",
                "split", "connect", "clean", "reset", "start", "stop", "walk", "collect"}
# 只转发型的包装：调的是**内建/全局**就不算"多余的间接层"（`return str(x)` 有它自己的语义）。
PY_BUILTINS = {"str", "int", "float", "bool", "len", "list", "dict", "set", "tuple", "print",
               "format", "repr", "sorted", "sum", "min", "max", "open", "range", "enumerate",
               "zip", "map", "filter", "bytes", "bytearray", "type", "isinstance"}
JS_BUILTINS = {"String", "Number", "Boolean", "Object", "Array", "JSON", "parseInt",
               "parseFloat", "Math", "Date", "Promise", "Symbol", "BigInt", "Error"}

SUFFIX_ABUSE = re.compile(r"(?:Helper|Manager|Util|Utils|Wrapper)$")

PLACEHOLDER_TEXT = [
    r"raise\s+NotImplementedError",
    r"#\s*your code here",
    r"#\s*placeholder",
    r"#\s*implement (?:me|this|later)",
    r"#\s*fill in",
    r"return\s+None\s*#\s*temporary",
]
# M4：**完成声明**的词表（中英都要收 —— 只收英文就是漏报一半）。
DONE_CLAIM = re.compile(
    r"(已实现|已完成|已修复|已接好|已接线|搞定|做好了|可以用了|没问题了|"
    r"\b(?:implemented|completed|finished|fixed|works now|it works|all good|done)\b)", re.I)
# M4：**空实现**的形状（注释挨着这些才算"说谎"）。
EMPTY_IMPL = re.compile(
    r"^\s*(?:pass|\.\.\.|raise\s+NotImplementedError.*|"
    r"return\s+None\s*(?:#.*)?|#\s*TODO.*|//\s*TODO.*|"
    r"throw\s+new\s+Error\(\s*[\"']?(?:not implemented|todo|未实现)[\"']?\s*\)\s*;?)\s*$", re.I)

DEBUG_RESIDUE_PY = [
    (r"\bbreakpoint\(\)", "breakpoint()"),
    (r"\bpdb\.set_trace\(\)", "pdb.set_trace()"),
    (r"(?<![.\w])var_dump\(", "var_dump("),
    (r"(?<![.\w])dd\(", "dd("),
]
OUTPUT_RESIDUE_PY = [(r"(?<![.\w])dump\(", "dump("), (r"^\s*print\(", "print(")]
OUTPUT_SCRIPT_PREFIXES = ("verify_", "probe_", "build_", "check_", "scan_", "report_", "run_", "audit_")

JS_EMPTY_CATCH = re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}")
JS_PLACEHOLDER = re.compile(r"//\s*(?:your code here|placeholder|implement me|todo:\s*implement|fill in)", re.I)
JS_DEBUG_RESIDUE = [(r"(?<![\w.])debugger\s*;", "debugger;"),
                    (r"(?<![.\w])var_dump\(", "var_dump(")]
JS_OUTPUT_RESIDUE = [(r"\bconsole\.log\(", "console.log("), (r"(?<![\w.])alert\(", "alert(")]
JS_TYPE_ESCAPE = [(r"\bas\s+any\b", "as any"), (r"@ts-ignore", "@ts-ignore"),
                  (r"@ts-expect-error", "@ts-expect-error")]
JS_TAUTOLOGY = [(r"expect\(\s*true\s*\)\.toBe\(\s*true\s*\)", "expect(true).toBe(true)"),
                (r"expect\(\s*1\s*\)\.toBe\(\s*1\s*\)", "expect(1).toBe(1)"),
                (r"assert\.ok\(\s*true\s*\)", "assert.ok(true)")]
JS_CONTROL_WORDS = {"if", "for", "while", "switch", "catch", "do", "else", "return",
                    "typeof", "case", "with", "function"}

# 多语言：占位与调试残留（**只有这些**；不做结构度量）
OTHER_PLACEHOLDER = [
    (r"not\s+implemented", "not implemented"),
    (r"//\s*TODO:?\s*implement", "// TODO: implement"),
    (r"#\s*TODO:?\s*implement", "# TODO: implement"),
    (r"你的代码", "你的代码"),
    (r"在此实现", "在此实现"),
]
OTHER_DEBUG = [
    (r"(?<![.\w])var_dump\(", "var_dump("),
    (r"(?<![.\w])dd\(", "dd("),
    (r"(?<![.\w])print_r\(", "print_r("),
    (r"\bbinding\.pry\b", "binding.pry"),
    (r"\bbyebug\b", "byebug"),
    (r"\bdbg!\(", "dbg!("),
]
# 要看语境的输出口子（同 JS 的 console.log）：**入口/可执行文件豁免**。
OTHER_OUTPUT = [
    (r"console\.log\(", "console.log("),
    (r"fmt\.Println\(", "go: fmt.Println("),
    (r"(?<![.\w])println!\(", "rust: println!("),
]
OTHER_EMPTY_CATCH = [
    (r"catch\s*\([^)]*\)\s*\{\s*\}", "php: 空 catch 块"),
    (r"rescue[^\n]*\n\s*end", "ruby: 空 rescue"),
    (r"if\s+err\s*!=\s*nil\s*\{\s*\}", "go: 空 err 分支"),
]

# 中文叙述性注释的**有界词典**（≈70 词）。**不在表里的词 = 查不了，不是没问题。**
ZH_TO_EN = {
    "创建": ("create",), "新建": ("create",), "获取": ("get",), "取得": ("get",),
    "读取": ("read",), "写入": ("write",), "保存": ("save",), "存储": ("store",),
    "删除": ("delete",), "移除": ("remove",), "更新": ("update",), "修改": ("update",),
    "检查": ("check",), "校验": ("validate",), "验证": ("verify",), "解析": ("parse",),
    "加载": ("load",), "计算": ("compute",), "发送": ("send",), "请求": ("request",),
    "响应": ("response",), "返回": ("return",), "配置": ("config",), "设置": ("set",),
    "用户": ("user",), "订单": ("order",), "文件": ("file",), "数据": ("data",),
    "列表": ("list",), "缓存": ("cache",), "路径": ("path",), "目录": ("dir",),
    "名称": ("name",), "错误": ("error",), "异常": ("exception",), "消息": ("message",),
    "记录": ("record",), "日志": ("log",), "状态": ("status",), "结果": ("result",),
    "任务": ("task",), "计划": ("plan",), "注册": ("register",), "启动": ("start",),
    "停止": ("stop",), "初始化": ("init",), "清理": ("clean",), "构建": ("build",),
    "生成": ("generate",), "转换": ("convert",), "格式": ("format",), "排序": ("sort",),
    "过滤": ("filter",), "合并": ("merge",), "拆分": ("split",), "连接": ("connect",),
    "扫描": ("scan",), "上报": ("report",), "打印": ("print",), "输出": ("output",),
    "输入": ("input",), "时间": ("time",), "计数": ("count",), "总数": ("total",),
    "金额": ("amount",), "地址": ("address",), "账号": ("account",), "密钥": ("key",),
}

MANUAL_RULES = [
    ("M1", "P1", "命名是否反映意图（A/HC/LC 用对没有）—— **部分机检**（P1-13 只抓三种可机检形状）；"
                 "「这个词准不准」仍要人看"),
    ("M2", "P1", "抽象是否过度（只有一个实现的接口 / 只被调一次的包装）—— **部分机检**"
                 "（P1-12 只给数量）；「该不该立」判不出"),
    ("M3", "P0", "是否与既有约定一致（一致性优先于风格偏好）—— **部分机检**"
                 "（P1-14 只查同一文件内混用）；跨文件/跨仓的约定仍要人读上下文"),
    ("M4", "P0", "注释是否诚实 —— **部分机检**（P0-6 只抓「完成声明 + 空实现」这一种最硬的谎）；"
                 "措辞层面的乐观仍要人看"),
    ("M5", "P1", "错误处理是否分级 —— **部分机检**（P1-4 给比例与重复）；「该分几级」要人看"),
    ("M6", "P1", "**非 Python/JS 语言的结构度量**（函数长度 / 嵌套深度）—— 仍未做；"
                 "JS/TS 侧已补（P1-5/P1-6），.php/.rb/.go/.rs/.vue **只做行级占位与调试残留**"),
]


def _iter_code_files(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (PY_SUFFIX | JS_SUFFIX | OTHER_SUFFIX):
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        yield p


def _find(lines, pattern, limit=6):
    rx = re.compile(pattern)
    hits = []
    for i, ln in enumerate(lines, 1):
        if rx.search(ln):
            hits.append({"line": i, "text": ln.strip()[:150]})
            if len(hits) >= limit:
                break
    return hits


def _is_output_script(path: Path, text: str) -> bool:
    """这个文件是不是**靠输出干活**的（CLI / 报告脚本 / 可执行入口）。

    `console.log` 在库代码里是调试残留，在 `verify_*.js` 里就是**本职**。
    判据刻意机械：文件名前缀 + 入口标志，**不猜「这段代码重要不重要」**。
    """
    if path.name.lower().startswith(OUTPUT_SCRIPT_PREFIXES):
        return True
    head = text[:4000]
    return ('if __name__ == "__main__"' in text
            or text.startswith("#!")
            or "process.argv" in head
            # 多语言的"可执行入口"：Go 的 `func main()`、Rust 的 `fn main(`、PHP/Ruby 的 CLI 脚本
            or "func main()" in text
            or "fn main(" in text
            or path.name.lower() in ("main.go", "main.rs", "cli.rb", "cli.php"))


def _norm_windows(text: str):
    """把文件切成规范化后的 N 行窗口 → {窗口元组: 行号}（空行与注释不参与）。"""
    norm = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            norm.append(None)
        else:
            norm.append(re.sub(r"\s+", " ", s))
    out = {}
    for i in range(len(norm) - DUP_BLOCK_LINES + 1):
        win = norm[i:i + DUP_BLOCK_LINES]
        if any(w is None for w in win):
            continue
        out.setdefault(tuple(win), i + 1)
    return out


def _dup_blocks(text: str, limit: int = 4):
    """同一文件内连续 N 行规范化后重复 ⇒ 复制粘贴味。"""
    seen: dict[tuple, int] = {}
    hits = []
    norm = []
    for ln in text.splitlines():
        s = ln.strip()
        norm.append(None if (not s or s.startswith("#") or s.startswith("//"))
                    else re.sub(r"\s+", " ", s))
    for i in range(len(norm) - DUP_BLOCK_LINES + 1):
        win = norm[i:i + DUP_BLOCK_LINES]
        if any(w is None for w in win):
            continue
        key = tuple(win)
        if key in seen:
            hits.append({"line": i + 1, "text": "与第 %d 行起的 %d 行完全相同：%s"
                         % (seen[key] + 1, DUP_BLOCK_LINES, win[0][:80])})
            if len(hits) >= limit:
                return hits
        else:
            seen[key] = i
    return hits


def _cross_file_dup(windows: dict, cross_index: dict, self_rel: str, limit: int = 3):
    """P1-11：**跨文件**重复块（原来只查文件内，那是真空白）。

    🔴 2026-09-23 噪声修：重叠窗口会把**同一坨重复报好几遍**
    （实测 `anim-make.py:199/200/201` 报的是同一段）。所以这里把
    「行号连续 + 对方文件相同」的窗口**合并成一处**。
    """
    hits = []
    last_line = -10
    last_partner = ""
    for key, line in sorted(windows.items(), key=lambda kv: kv[1]):
        owners = cross_index.get(key)
        if not owners:
            continue
        others = sorted((f, ln) for f, ln in owners if f != self_rel)
        if not others:
            continue
        partner = others[0][0]
        if line == last_line + 1 and partner == last_partner:
            last_line = line
            continue      # 同一坨的下一行，已经在上一处报过了
        where = "、".join("%s:%d" % (f, ln) for f, ln in others[:2])
        hits.append({"line": line, "text": "%d 行与 %s 完全相同：%s"
                     % (DUP_BLOCK_LINES, where, key[0][:70])})
        last_line, last_partner = line, partner
        if len(hits) >= limit:
            break
    return hits


def _commented_out_code(lines, limit: int = 3):
    """连续 ≥3 行注释，且其中 ≥2 行像代码 ⇒ 注释掉的代码块。"""
    hits = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("#") or s.startswith("//"):
            j = i
            while j < len(lines) and (lines[j].strip().startswith("#")
                                      or lines[j].strip().startswith("//")):
                j += 1
            block = [lines[k].strip() for k in range(i, j)]
            if len(block) >= 3:
                codelike = sum(1 for b in block
                               if re.search(r"[=()\[\]]|:\s*$|\breturn\b|\bdef\b|\bif\b", b))
                if codelike >= 2:
                    hits.append({"line": i + 1, "text": "连续 %d 行注释掉的内容：%s"
                                 % (len(block), block[0][:90])})
                    if len(hits) >= limit:
                        return hits
            i = j
        else:
            i += 1
    return hits


def _ident_tokens(text: str) -> set:
    """把代码里的标识符切成小写词元（给「叙述性注释」用）。

    🔴 2026-09-23 误报修（实测抓到的**漏报**，夹具当场抓到）：
    第一版先按 `_` 切、再单独抽「大写开头的词」，于是 `createUserRecord` 只切出
    user / record，**把首词 create 丢了** ⇒ 这条判据在 camelCase 的语言（JS/TS）上
    **等于没查**。现在统一走一个词元器：`createUserRecord` 与 `create_user_record`
    都切成 create / user / record。
    """
    tokens = set()
    for ident in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text):
        for part in re.split(r"_+", ident):
            if not part:
                continue
            tokens.update(w.lower() for w in
                          re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", part))
    return tokens


def _narrative_comments(lines, limit: int = 5):
    """P1-9 叙述性注释：注释把下一行代码又说了一遍。

    两条路：① 英文 —— 注释词逐个命中下一行标识符词元；
    ② 中文 —— 走**有界词典**（`ZH_TO_EN`）把中文词折成英文再比。
    ⚠️ 边界：词典外的中文词**查不到**（这就是「没查」，不是「没问题」）。
    """
    hits = []
    for i in range(len(lines) - 1):
        s = lines[i].strip()
        m = re.match(r"(?:#|//)\s*(.+)$", s)
        if not m:
            continue
        body = re.split(r"❌|（|\(|#|:|—|→|\|", m.group(1))[0]
        nxt = lines[i + 1]
        if not nxt.strip() or nxt.strip().startswith("#") or nxt.strip().startswith("//"):
            continue
        tokens = _ident_tokens(nxt)

        # ① 英文路：**只在纯英文注释上走**。为什么 —— 实测中英混写注释里常"提到实体名"
        #    （文件名 `verify_delete.py`、函数名 `_find_gatekeeper`、词 `UI-check`），
        #    其中一个又恰好是动作词，于是被误判成"复述代码"（真仓抓到的第二类误报）。
        #    中英混写改走下面的中文词典路。
        if not re.search(r"[\u4e00-\u9fff]", body):
            words = re.findall(r"[a-zA-Z]{2,}", body.lower())
            words = [w for w in words if w not in
                     {"the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "if", "is",
                      "this", "that", "with", "from", "by", "at", "as", "it", "we", "you"}]
            if len(words) >= 2 and any(w in ACTION_VERBS for w in words) \
                    and all(w in tokens for w in words):
                hits.append({"line": i + 1, "text": "%s  ← 下一行把它整个写进了标识符（%s）"
                             % (s[:80], ", ".join(words))})
                if len(hits) >= limit:
                    break
                continue

        # ② 中文路（有界词典）
        found = {}
        for zh, ens in ZH_TO_EN.items():
            if zh in body:
                found[zh] = ens
        if len(found) >= 2:
            mapped = [en for ens in found.values() for en in ens]
            if all(en in tokens for en in mapped):
                hits.append({"line": i + 1, "text": "%s  ← 中文注释折成英文后命中标识符（%s）"
                             % (s[:80], "/".join(found))})
                if len(hits) >= limit:
                    break
    return hits


# ── JS/TS：自研块匹配（零依赖）────────────────────────────────────────────
def _strip_js(text: str) -> str:
    """剥掉字符串/模板/注释/正则，**保留换行与长度**（行号不漂）。"""
    out = list(text)
    i, n = 0, len(text)

    def blank(k):
        if 0 <= k < n and out[k] != "\n":
            out[k] = " "

    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                blank(i)
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            blank(i)
            blank(i + 1)
            i += 2
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                blank(i)
                i += 1
            blank(i)
            blank(i + 1)
            i += 2
        elif c in "\"'`":
            quote = c
            blank(i)
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\":
                    blank(i)
                    blank(i + 1)
                    i += 2
                    continue
                blank(i)
                i += 1
            blank(i)
            i += 1
        elif c == "/" and _regex_start(text, i):
            blank(i)
            i += 1
            while i < n and text[i] != "/":
                if text[i] == "\\":
                    blank(i)
                    blank(i + 1)
                    i += 2
                    continue
                blank(i)
                i += 1
            blank(i)
            i += 1
        else:
            i += 1
    return "".join(out)


def _regex_start(text: str, i: int) -> bool:
    j = i - 1
    while j >= 0 and text[j] in " \t":
        j -= 1
    if j < 0:
        return True
    return text[j] in "(,=:[!&|?{};+-*%~^<>"


def _match_brace(s: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _js_functions(s: str, cap: int = 4000):
    """返回 [(名字, 起始行, 结束行, 花括号内起始下标, 结束下标)]。

    候选起点三种：`function name(...)` · `(...) => {` · `name(...) {`（方法简写），
    **排除控制关键字**（if/for/while/switch/catch…）。
    """
    pat = re.compile(
        r"(?:\bfunction\s*\*?\s*([\w$]*)\s*\([^)]*\)"
        r"|(?:\([^)]*\)|[\w$]+)\s*=>"
        r"|([\w$]+)\s*\([^)]*\))\s*\{")
    out = []
    for m in pat.finditer(s):
        name = m.group(1) or m.group(2) or "(arrow)"
        if name in JS_CONTROL_WORDS:
            continue
        open_idx = m.end() - 1
        close_idx = _match_brace(s, open_idx)
        if close_idx < 0:
            continue
        start_line = s.count("\n", 0, m.start()) + 1
        end_line = s.count("\n", 0, close_idx) + 1
        out.append((name, start_line, end_line, open_idx, close_idx))
        if len(out) >= cap:
            break
    return out


def _js_params_before(s: str, oi: int):
    """从花括号前面的签名里取出参数名（给"只转发的包装"比对用）。"""
    m = re.search(r"\(([^()]*)\)\s*(?:=>\s*)?$", s[:oi])
    if not m:
        return None
    raw = m.group(1)
    if not raw.strip():
        return []
    return [p.strip().split(":")[0].split("=")[0].strip().lstrip(".") for p in raw.split(",")]


def _js_max_depth(s: str, open_idx: int, close_idx: int) -> int:
    depth = 0
    best = 0
    for i in range(open_idx + 1, close_idx):
        if s[i] == "{":
            depth += 1
            best = max(best, depth)
        elif s[i] == "}":
            depth -= 1
    return best


def _js_params(sig: str):
    inner = sig[sig.find("(") + 1:sig.rfind(")")]
    return [p.strip().split(":")[0].strip().lstrip(".") for p in inner.split(",") if p.strip()]


# ── 审计：Python ─────────────────────────────────────────────────────────
def _index_parts(index):
    """兼容两种传参：仓级索引（含 cross/calls/subs）或裸的跨文件索引。"""
    if not index:
        return None, None, None
    if "cross" in index:
        return index.get("cross"), index.get("calls"), index
    return index, None, None


def audit_py(path: Path, text: str, lines, is_out: bool = False,
             index: dict | None = None, self_rel: str = "") -> list[dict]:
    cross_index, calls, full = _index_parts(index)
    findings: list[dict] = []

    def add(rid, tier, title, hits, note=""):
        if hits:
            findings.append({"id": rid, "tier": tier, "title": title,
                             "count": len(hits), "hits": hits, "note": note})

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        findings.append({"id": "X-1", "tier": "P2",
                         "title": "语法解析失败（该文件的 AST 类判据全部没跑）",
                         "count": 1, "hits": [{"line": exc.lineno or 0, "text": str(exc)[:120]}],
                         "note": "如实报：**这份文件的结构类检查等于没做**"})
        tree = None

    if tree is not None:
        handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]

        # P0-1 静默吞错
        hits = []
        for node in handlers:
            body = [b for b in node.body if not (isinstance(b, ast.Expr)
                                                 and isinstance(b.value, ast.Constant)
                                                 and isinstance(b.value.value, str))]
            if body and all(isinstance(b, ast.Pass)
                            or (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant)
                                and b.value.value is Ellipsis) for b in body):
                hits.append({"line": node.lineno,
                             "text": "except%s: pass  ← 吞掉了，且没留痕"
                                     % ("" if node.type is None else " " + ast.unparse(node.type))})
        add("P0-1", "P0", "静默吞错（`except: pass` / `except ...: ...`）", hits,
            "本仓《编程纪律》第一条：吞错必须显式上报；查不到不报 = 假成功")

        # P1-4 错误处理一把抓（M5 机检部分）
        generic = [h for h in handlers
                   if h.type is None or (isinstance(h.type, ast.Name)
                                         and h.type.id in ("Exception", "BaseException"))]
        if handlers and len(generic) >= GENERIC_CATCH_MIN \
                and len(generic) / len(handlers) >= GENERIC_CATCH_RATIO:
            add("P1-4", "P1", "错误处理一把抓（%d/%d 个 handler 是 generic）"
                % (len(generic), len(handlers)),
                [{"line": h.lineno, "text": "except %s  ← generic"
                  % (ast.unparse(h.type) if h.type else "(bare)")} for h in generic[:6]],
                "**这是比例信号不是判决**：不同错误该分开处理，但「该分几级」要人看")

        # P1-5 函数过长
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                span = (node.end_lineno or node.lineno) - node.lineno + 1
                if span > MAX_FUNC_LINES:
                    hits.append({"line": node.lineno, "text": "%s() 共 %d 行（阈值 %d）"
                                 % (node.name, span, MAX_FUNC_LINES)})
        add("P1-5", "P1", "函数过长（一个函数干了太多件事）", hits[:6],
            "拆分点是「它做了几件事」，不是行数本身 —— 行数只是信号")

        # P1-6 嵌套过深
        NEST = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Match)

        def depth_of(node, d=0):
            best = (d, node)
            for child in ast.iter_child_nodes(node):
                cand = depth_of(child, d + 1) if isinstance(child, NEST) else depth_of(child, d)
                if cand[0] > best[0]:
                    best = cand
            return best

        if isinstance(tree, ast.Module):
            d, node = depth_of(tree)
            if d >= MAX_NEST_DEPTH:
                findings.append({"id": "P1-6", "tier": "P1",
                                 "title": "嵌套过深（叠了 %d 层，阈值 %d）" % (d, MAX_NEST_DEPTH),
                                 "count": 1, "hits": [{"line": getattr(node, "lineno", 0),
                                                       "text": "最深一处在这个节点"}],
                                 "note": "早返回 / 提取函数 / 把条件翻过来，都比再缩进一层好"})

        # P0-4 空壳测试 + 恒真断言
        is_test = path.name.startswith("test_") or path.name.endswith("_test.py")
        if is_test:
            hits = []
            taut = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                    body_src = ast.dump(ast.Module(body=node.body, type_ignores=[])).lower()
                    if not any(k in body_src for k in ("assert", "raises", "fail(")):
                        hits.append({"line": node.lineno, "text": "%s() 里没有任何断言/期望" % node.name})
                    elif re.search(r"assert\s+true\b", body_src):
                        taut.append({"line": node.lineno, "text": "%s() 只有 `assert True`" % node.name})
            add("P0-4", "P0", "空壳测试（名字叫测试，实则恒真）", hits,
                "没有断言的测试给的是「覆盖率幻觉」；它比没有测试更坏")
            add("P0-4b", "P0", "恒真断言（`assert True`）", taut, "同上：它在证伪什么？")

        # P1-12 抽象数量信号（M2 机检部分）
        single_method = []
        wrappers = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [b for b in node.body
                           if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and not b.name.startswith("__")]
                # 🔴 私有类不报：实测 `_BlindEye` / `_GoodEye` 这类**测试替身**就是单方法类，
                # 那是正当写法（鸭子类型的假件）。判据只对**公开类**提这个问题。
                # 🔴 有基类的也不报：实测 `class NoRedirect(HTTPRedirectHandler)` 只覆写一个方法，
                # 那是**正当的子类扩展**，不是"该变成函数的单方法类"。
                if len(methods) == 1 and not node.name.startswith("_") and not node.bases:
                    single_method.append({"line": node.lineno,
                                          "text": "%s 只有一个方法 %s" % (node.name, methods[0].name)})
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
                body = [b for b in node.body if not (isinstance(b, ast.Expr)
                                                     and isinstance(b.value, ast.Constant)
                                                     and isinstance(b.value.value, str))]
                if len(body) == 1:
                    stmt = body[0]
                    call = stmt.value if isinstance(stmt, ast.Return) else (
                        stmt.value if isinstance(stmt, ast.Expr) else None)
                    if isinstance(call, ast.Call) and not call.keywords \
                            and isinstance(call.func, ast.Name) \
                            and call.func.id not in PY_BUILTINS:
                        args = [a.id for a in call.args if isinstance(a, ast.Name)]
                        if args and args == params:
                            used = calls.get(node.name, 0) if calls is not None else None
                            extra = "" if used is None else "（扫描面内被调用 %d 次）" % used
                            wrappers.append({"line": node.lineno,
                                             "text": "%s() 只是原样转发给 %s()%s"
                                             % (node.name, ast.unparse(call.func), extra)})
        add("P1-12", "P1", "抽象数量信号：单方法类（%d 个）" % len(single_method),
            single_method[:6], "**数量不是判断** —— 只有一个方法也可能是正当封装；要人看")
        add("P1-12b", "P1", "抽象数量信号：只转发参数的包装（%d 个）" % len(wrappers),
            wrappers[:6], "同上：有第二个调用者就正当，只有一个就该问「为什么要这一层」")

        # P1-12c 单个实现的基类/接口（M2 里"只有一个实现的接口"那一半）
        if full:
            subs = full.get("subs") or {}
            known = full.get("known_classes") or set()
            single_impl = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name in known:
                    impls = sorted(subs.get(node.name, ()))
                    if len(impls) == 1:
                        single_impl.append({"line": node.lineno,
                                            "text": "%s 只有 %s 一个实现" % (node.name, impls[0])})
            add("P1-12c", "P1", "抽象数量信号：单个实现的基类/接口（%d 个）" % len(single_impl),
                single_impl[:6],
                "**这正是 M2 里「只有一个实现的接口」** —— 第二个实现出现前，这一层是纯成本；"
                "但例外与测试替身也长这样，**仍要人看**")

        # P1-13 命名意图信号（M1 机检部分）
        bool_hits = []
        generic_fn = []
        ctx_dup = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name.lower() in GENERIC_FN_NAMES and not node.name.startswith("_"):
                    generic_fn.append({"line": node.lineno, "text": "%s()  ← 名字没说做什么" % node.name})
            if isinstance(node, ast.Assign):
                value = node.value
                is_bool = isinstance(value, ast.Constant) and isinstance(value.value, bool)
                if is_bool:
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id.lower() in MEANINGLESS_BOOL:
                            bool_hits.append({"line": node.lineno,
                                              "text": "%s = %s  ← 这个名字什么都没说"
                                              % (t.id, value.value)})
            if isinstance(node, ast.ClassDef):
                low = node.name.lower()
                for b in node.body:
                    if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                            and b.name.lower().startswith(low + "_"):
                        ctx_dup.append({"line": b.lineno,
                                        "text": "%s.%s()  ← 类名已在上下文里，方法名又重复一遍"
                                        % (node.name, b.name)})
        add("P1-13", "P1", "命名意图信号：布尔名不带 is/has/can/should…", bool_hits[:6],
            "**只是形状信号**：读起来像一句话的布尔名（isLoading / hasPermission）最好")
        add("P1-13b", "P1", "命名意图信号：超通用函数名（handle / process / stuff…）",
            generic_fn[:6], "**只是形状信号**：名字该说做什么")
        add("P1-13c", "P1", "命名意图信号：上下文重复（类名在方法名里又来一遍）",
            ctx_dup[:6], "A/HC/LC 里的「高上下文」重复了")

        # P1-14 约定混用信号（M3 机检部分）
        snake, camel = [], []
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.arg):
                names = [node.arg]
            for nm in names:
                if nm.isupper() or nm.startswith("_"):
                    continue
                if "_" in nm and nm.islower():
                    snake.append(nm)
                elif re.search(r"[a-z][A-Z]", nm):
                    camel.append(nm)
        if len(snake) >= MIXED_CONVENTION_MIN and len(camel) >= MIXED_CONVENTION_MIN:
            add("P1-14", "P1", "约定混用：同一文件里 snake_case（%d）与 camelCase（%d）并存"
                % (len(snake), len(camel)),
                [{"line": 0, "text": "snake 例：%s" % "、".join(sorted(set(snake))[:4])},
                 {"line": 0, "text": "camel 例：%s" % "、".join(sorted(set(camel))[:4])}],
                "**只查文件内**；跨文件/跨仓的约定仍要人读（M3）")
        # P1-14b 与**仓内主导约定**比对（M3 的跨文件那一半 —— 单文件永远判不了）
        if full:
            conv = (full.get("conv") or {}).get("py") or {}
            repo_snake, repo_camel = conv.get("snake", 0), conv.get("camel", 0)
            repo_major = "snake" if repo_snake >= repo_camel else "camel"
            if repo_major == "snake" and len(camel) > len(snake) and len(camel) >= MIXED_CONVENTION_MIN:
                add("P1-14b", "P1", "与仓内主导约定相反：这份文件 camelCase（%d）多于 snake_case（%d）"
                    % (len(camel), len(snake)),
                    [{"line": 0, "text": "仓内 py 主导：snake %d / camel %d" % (repo_snake, repo_camel)}],
                    "**M3 的跨文件那一半**：一致性优先于风格偏好 —— 要么跟随本仓，要么整仓统一（要人定）")
            elif repo_major == "camel" and len(snake) > len(camel) and len(snake) >= MIXED_CONVENTION_MIN:
                add("P1-14b", "P1", "与仓内主导约定相反：这份文件 snake_case（%d）多于 camelCase（%d）"
                    % (len(snake), len(camel)),
                    [{"line": 0, "text": "仓内 py 主导：camel %d / snake %d" % (repo_camel, repo_snake)}],
                    "同上：要人定")

        # P1-8 占位命名
        hits = []
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Name):
                names = [node.id]
            elif isinstance(node, ast.arg):
                names = [node.arg]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
            for nm in names:
                if nm.lower() in PLACEHOLDER_NAMES:
                    hits.append({"line": getattr(node, "lineno", 0), "text": "标识符 `%s`" % nm})
        add("P1-8", "P1", "教程味占位命名（foo / bar / baz / dummy / temp1 …）", hits[:6],
            "占位名在正式代码里出现 = 这段从没被认真对付过")

        # P1-10 后缀滥用
        suffix_hits = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                    and SUFFIX_ABUSE.search(node.name):
                suffix_hits.append({"line": node.lineno, "text": "%s" % node.name})
        if len(suffix_hits) >= SUFFIX_ABUSE_MIN:
            add("P1-10", "P1", "`*Helper` / `*Manager` / `*Util` 后缀滥用（≥%d 个）" % SUFFIX_ABUSE_MIN,
                suffix_hits[:6], "这类名字说明「职责没想清楚」，不是一个类别")

    # P0-6 注释说谎（M4 机检部分：完成声明 + 空实现）
    hits = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not (s.startswith("#") or s.startswith("//")):
            continue
        body = re.sub(r"^[#/]+\s*", "", s)
        if not DONE_CLAIM.search(body):
            continue
        for j in range(i + 1, min(i + 3, len(lines))):
            nxt = lines[j]
            if not nxt.strip() or nxt.strip().startswith(("#", "//")):
                continue
            if EMPTY_IMPL.match(nxt):
                hits.append({"line": i + 1, "text": "%s  ← 紧接着的是空实现：%s"
                             % (s[:70], nxt.strip()[:50])})
            break
    add("P0-6", "P0", "注释说谎（说「已实现/已完成」，紧接着是空实现）", hits[:6],
        "本仓《严禁假执行》：注释不许比代码乐观。**要人确认**：也可能是措辞不准")

    # P0-2 / P0-3 / P1-3 / P2-3
    hits = []
    for pat in PLACEHOLDER_TEXT:
        hits += _find(lines, pat)
    add("P0-2", "P0", "占位 / 未实现残留（NotImplementedError · your code here · placeholder）",
        hits[:6], "要么真做，要么按本仓纪律显式返回 needs_dependency")

    hits = []
    for pat, label in DEBUG_RESIDUE_PY:
        for h in _find(lines, pat):
            h["text"] = "%s  ← %s" % (h["text"], label)
            hits.append(h)
    add("P0-3", "P0", "调试残留（breakpoint / pdb.set_trace / var_dump / dd）", hits[:6],
        "断点类残留永不正当 —— 它只可能是在调试时留下的")

    if not is_out:
        hits = []
        for h in _find(lines, OUTPUT_RESIDUE_PY[0][0]):
            if re.match(r"\s*(?:async\s+)?def\s+dump\b", lines[h["line"] - 1]):
                continue
            hits.append(h)
        add("P1-3", "P1", "输出残留（`dump(`，且不是 json.dump / def dump）", hits[:6],
            "库代码要报错就抛异常、要上报就落审计 —— 别用输出")
        add("P2-3", "P2", "非入口文件里的 `print(`", _find(lines, OUTPUT_RESIDUE_PY[1][0])[:6],
            "CLI / 入口脚本已豁免（打印是它的本职）；这里只报库代码")

    add("P1-7", "P1", "文件内重复块（连续 %d 行完全相同）" % DUP_BLOCK_LINES, _dup_blocks(text),
        "复制粘贴是把「读的成本」转嫁给下一个人")
    if cross_index is not None:
        add("P1-11", "P1", "跨文件重复块（与另一个文件逐行相同）",
            _cross_file_dup(_norm_windows(text), cross_index, self_rel),
            "同一坨代码抄到第二个文件 —— 改一处忘一处就从这儿开始")
    add("P1-9", "P1", "叙述性注释（注释把下一行代码又说了一遍）", _narrative_comments(lines),
        "好注释说的是「为什么」；中文走有界词典，词典外的词查不到")
    add("P2-11", "P2", "注释掉的代码块（连续 ≥3 行）", _commented_out_code(lines),
        "版本控制已经记住它了；留在文件里只会让读的人犹豫")
    add("P2-12", "P2", "闭合括号标签（`# end if` / `} // end`）",
        _find(lines, r"(?:#|//)\s*end\s+(?:if|for|while|function|def|block|class)\b", limit=4))
    return findings


# ── 审计：JS / TS（自研块匹配）──────────────────────────────────────────
def audit_js(path: Path, text: str, lines, is_out: bool = False,
             index: dict | None = None, self_rel: str = "") -> list[dict]:
    cross_index, calls, full = _index_parts(index)
    findings: list[dict] = []
    stripped = _strip_js(text)

    def add(rid, tier, title, hits, note=""):
        if hits:
            findings.append({"id": rid, "tier": tier, "title": title,
                             "count": len(hits), "hits": hits, "note": note})

    hits = []
    for i, ln in enumerate(lines, 1):
        if JS_EMPTY_CATCH.search(ln):
            hits.append({"line": i, "text": ln.strip()[:140]})
    add("P0-1", "P0", "静默吞错（空 catch 块）", hits[:6], "吞错必须显式上报")

    add("P0-2", "P0", "占位 / 未实现残留（// your code here · placeholder）",
        _find(lines, JS_PLACEHOLDER.pattern)[:6])

    hits = []
    for pat, label in JS_DEBUG_RESIDUE:
        for h in _find(lines, pat):
            h["text"] = "%s  ← %s" % (h["text"], label)
            hits.append(h)
    add("P0-3", "P0", "调试残留（debugger / var_dump）", hits[:6], "断点类残留永不正当")

    if not is_out:
        hits = []
        for pat, label in JS_OUTPUT_RESIDUE:
            for h in _find(lines, pat):
                h["text"] = "%s  ← %s" % (h["text"], label)
                hits.append(h)
        add("P1-3", "P1", "输出残留（console.log / alert，非输出型文件）", hits[:6],
            "库代码里不该有输出 —— 报告脚本 / 入口已豁免（打印是它的本职）")

    hits = []
    for pat, label in JS_TYPE_ESCAPE:
        for h in _find(lines, pat):
            h["text"] = "%s  ← %s" % (h["text"], label)
            hits.append(h)
    add("P0-5", "P0", "类型逃逸（as any / @ts-ignore）", hits[:6],
        "类型系统的口子开在最难推断的地方，就是把风险留给未来的自己")

    hits = []
    for pat, label in JS_TAUTOLOGY:
        for h in _find(lines, pat):
            h["text"] = "%s  ← %s" % (h["text"], label)
            hits.append(h)
    add("P0-4", "P0", "空壳 / 恒真测试（expect(true).toBe(true)）", hits[:6],
        "空壳测试的 JS 版；先问「它在证伪什么」，答不出就是空壳")

    # ── 结构度量（M6 补上：函数长度 + 块深度）──
    funcs = _js_functions(stripped)
    long_hits = []
    deep_hits = []
    for name, start, end, oi, ci in funcs:
        span = end - start + 1
        if span > MAX_FUNC_LINES:
            long_hits.append({"line": start, "text": "%s() 共 %d 行（阈值 %d）"
                              % (name, span, MAX_FUNC_LINES)})
        depth = _js_max_depth(stripped, oi, ci)
        if depth >= MAX_NEST_DEPTH:
            deep_hits.append({"line": start, "text": "%s() 块深度 %d（阈值 %d）"
                              % (name, depth, MAX_NEST_DEPTH)})
    add("P1-5", "P1", "函数过长（JS/TS · 块匹配）", long_hits[:6],
        "**本版补上**：不再只有 Python 有结构度量")
    add("P1-6", "P1", "嵌套过深（JS/TS · 块深度）", deep_hits[:6],
        "块深度含对象/数组字面量，比 Python 侧略宽 —— 阈值同为 %d" % MAX_NEST_DEPTH)

    # P0-6 注释说谎（同 Python 判据）
    hits = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not (s.startswith("#") or s.startswith("//")):
            continue
        body = re.sub(r"^[#/]+\s*", "", s)
        if not DONE_CLAIM.search(body):
            continue
        for j in range(i + 1, min(i + 3, len(lines))):
            nxt = lines[j]
            if not nxt.strip() or nxt.strip().startswith(("#", "//")):
                continue
            if EMPTY_IMPL.match(nxt) or re.match(r"^\s*//\s*(?:TODO|not implemented)", nxt, re.I):
                hits.append({"line": i + 1, "text": "%s  ← 紧接着是空实现：%s"
                             % (s[:70], nxt.strip()[:50])})
            break
    add("P0-6", "P0", "注释说谎（说「已实现/已完成」，紧接着是空实现）", hits[:6],
        "《严禁假执行》：注释不许比代码乐观。**要人确认**")

    # P1-4 错误处理：重复的 catch 体
    bodies = defaultdict(list)
    for m in re.finditer(r"catch\s*(?:\([^)]*\))?\s*\{", stripped):
        oi = m.end() - 1
        ci = _match_brace(stripped, oi)
        if ci < 0:
            continue
        body = re.sub(r"\s+", " ", stripped[oi + 1:ci]).strip()
        if body:
            bodies[body].append(stripped.count("\n", 0, m.start()) + 1)
    rep = []
    for body, lns in bodies.items():
        if len(lns) >= JS_CATCH_REPEAT_MIN:
            rep.append({"line": lns[0], "text": "同一个 catch 体出现了 %d 次：%s"
                        % (len(lns), body[:70])})
    add("P1-4", "P1", "错误处理一把抓（同一 catch 体重复 ≥%d 次）" % JS_CATCH_REPEAT_MIN,
        rep[:6], "**比例/重复信号不是判决**：不同错误该分开处理")

    # P1-12 抽象数量（单方法类 / 只转发的包装）
    sm = []
    wr = []
    for m in re.finditer(r"\bclass\s+([\w$]+)(\s+extends\s+[\w$.]+)?[^{]*\{", stripped):
        if m.group(2):
            continue      # 有 extends 的子类：单方法覆写是正当写法（同 Python 侧口径）
        oi = m.end() - 1
        ci = _match_brace(stripped, oi)
        if ci < 0:
            continue
        inner = stripped[oi + 1:ci]
        methods = [x for x in _js_functions(inner) if x[0] not in JS_CONTROL_WORDS]
        if len(methods) == 1:
            sm.append({"line": stripped.count("\n", 0, m.start()) + 1,
                       "text": "%s 只有一个方法 %s" % (m.group(1), methods[0][0])})
    for name, start, end, oi, ci in funcs:
        body = stripped[oi + 1:ci].strip()
        one = re.fullmatch(r"return\s+([\w$]+)\(([^;]*)\)\s*;?", body)
        if not one:
            continue
        callee = one.group(1)
        # 🔴 2026-09-23 判据 bug 修：第一版**只看了"函数体是一次调用"**，没比参数 ⇒
        # `esc()`/`map()`/`dshShort()` 这些**有自己语义**的包装全被误判（真仓 61 文件/95 处）。
        # 现在必须：① 参数逐个相同；② 不是方法调用；③ 目标不是内建。三者全中才算"多余的间接层"。
        if "." in callee or callee in JS_BUILTINS:
            continue
        params = _js_params_before(stripped, oi)
        args = [a.strip() for a in one.group(2).split(",") if a.strip()]
        if params and params == args:
            wr.append({"line": start, "text": "%s() 只是原样转发给 %s()" % (name, callee)})
    add("P1-12", "P1", "抽象数量信号：单方法类（%d 个）" % len(sm), sm[:6],
        "**数量不是判断**；要人看")
    add("P1-12b", "P1", "抽象数量信号：只转发参数的包装（%d 个）" % len(wr), wr[:6],
        "同上：有第二个调用者就正当")
    if full:
        subs = full.get("subs") or {}
        known = full.get("known_classes") or set()
        js_single = []
        for m in re.finditer(r"\bclass\s+([\w$]+)[^{]*\{", stripped):
            nm = m.group(1)
            if nm in known and len(subs.get(nm, ())) == 1:
                js_single.append({"line": stripped.count("\n", 0, m.start()) + 1,
                                  "text": "%s 只有 %s 一个实现" % (nm, sorted(subs[nm])[0])})
        add("P1-12c", "P1", "抽象数量信号：单个实现的基类/接口（%d 个）" % len(js_single),
            js_single[:6], "M2 里「只有一个实现的接口」；例外与测试替身也长这样，**仍要人看**")

    # P1-13 命名意图信号
    bool_hits = []
    for m in re.finditer(r"\b(?:const|let|var)\s+([\w$]+)\s*(?::\s*boolean\s*)?=\s*(true|false)\b", stripped):
        if m.group(1).lower() in MEANINGLESS_BOOL:
            bool_hits.append({"line": stripped.count("\n", 0, m.start()) + 1,
                              "text": "%s = %s  ← 这个名字什么都没说" % (m.group(1), m.group(2))})
    generic_fn = []
    for name, start, *_ in funcs:
        if name.lower() in GENERIC_FN_NAMES:
            generic_fn.append({"line": start, "text": "%s()  ← 名字没说做什么" % name})
    add("P1-13", "P1", "命名意图信号：布尔名不带 is/has/can/should…", bool_hits[:6],
        "**只是形状信号**")
    add("P1-13b", "P1", "命名意图信号：超通用函数名（handle / process / stuff…）",
        generic_fn[:6], "**只是形状信号**")

    # P1-14 约定混用
    snake = sorted(set(re.findall(r"\b(?:const|let|var)\s+([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b", stripped)))
    if len(snake) >= MIXED_CONVENTION_MIN:
        add("P1-14", "P1", "约定混用：JS/TS 里出现 %d 个 snake_case 局部名" % len(snake),
            [{"line": 0, "text": "例：%s" % "、".join(snake[:5])}],
            "**只查文件内**；JS 的既有约定通常是 camelCase（跨文件仍要人读）")
        if full:
            conv = (full.get("conv") or {}).get("js") or {}
            repo_snake, repo_camel = conv.get("snake", 0), conv.get("camel", 0)
            if repo_camel > repo_snake:
                add("P1-14b", "P1", "与仓内主导约定相反：这份文件 snake_case 多于 camelCase",
                    [{"line": 0, "text": "仓内 js 主导：camel %d / snake %d" % (repo_camel, repo_snake)}],
                    "**M3 的跨文件那一半**：跟随本仓还是统一，要人定")

    hits = _find(lines, r"\b(foo|bar|baz|qux|dummy|placeholder|temp1|tmp1|myvar)\b")
    add("P1-8", "P1", "教程味占位命名", hits[:6])

    suffix_hits = _find(lines, r"(?:function\s+|const\s+|class\s+)([A-Za-z_$][\w$]*(?:Helper|Manager|Util|Utils|Wrapper))\b")
    if len(suffix_hits) >= SUFFIX_ABUSE_MIN:
        add("P1-10", "P1", "`*Helper` / `*Manager` / `*Util` 后缀滥用", suffix_hits[:6])

    add("P1-7", "P1", "文件内重复块（连续 %d 行完全相同）" % DUP_BLOCK_LINES, _dup_blocks(text))
    if cross_index is not None:
        add("P1-11", "P1", "跨文件重复块（与另一个文件逐行相同）",
            _cross_file_dup(_norm_windows(text), cross_index, self_rel))
    add("P1-9", "P1", "叙述性注释（注释把下一行代码又说了一遍）", _narrative_comments(lines))
    add("P2-11", "P2", "注释掉的代码块（连续 ≥3 行）", _commented_out_code(lines))
    add("P2-12", "P2", "闭合括号标签（`} // end`）",
        _find(lines, r"//\s*end\s+(?:if|for|while|function|block|class)\b", limit=4))
    return findings


# ── 审计：多语言（只做行级，不做结构度量）────────────────────────────────
def audit_other(path: Path, text: str, lines, is_out: bool = False) -> list[dict]:
    findings: list[dict] = []

    def add(rid, tier, title, hits, note=""):
        if hits:
            findings.append({"id": rid, "tier": tier, "title": title,
                             "count": len(hits), "hits": hits, "note": note})

    hits = []
    for pat, _label in OTHER_PLACEHOLDER:
        hits += _find(lines, pat)
    add("P0-2", "P0", "占位 / 未实现残留（多语言行级）", hits[:6],
        "**这一族只做行级判据**：没有结构度量、没有命名分析")

    hits = []
    for pat, label in OTHER_DEBUG:
        for h in _find(lines, pat):
            h["text"] = "%s  ← %s" % (h["text"], label)
            hits.append(h)
    add("P0-3", "P0", "调试残留（多语言行级）", hits[:6], "断点/转储类残留永不正当")

    if not is_out:
        hits = []
        for pat, label in OTHER_OUTPUT:
            for h in _find(lines, pat):
                h["text"] = "%s  ← %s" % (h["text"], label)
                hits.append(h)
        add("P1-3", "P1", "输出残留（多语言行级 · 非入口文件）", hits[:6],
            "入口 / 可执行文件已豁免（`func main()` / `fn main(` / main.go / main.rs）")

    # 空 catch / rescue / err 分支：**必须整篇扫**（`{` 与 `}` 常不在同一行）
    hits = []
    for pat, label in OTHER_EMPTY_CATCH:
        for m in re.finditer(pat, text, re.S):
            ln = text.count("\n", 0, m.start()) + 1
            hits.append({"line": ln, "text": "%s  ← %s" % (text.splitlines()[ln - 1].strip()[:90], label)})
            if len(hits) >= 6:
                break
    add("P0-1", "P0", "静默吞错（多语言行级空 catch/rescue/err 分支）", hits[:6],
        "吞错必须显式上报")

    add("P2-11", "P2", "注释掉的代码块（连续 ≥3 行）", _commented_out_code(lines))
    return findings


def audit_file(path: Path, index: dict | None = None) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    if any("code-taste: ignore-file" in ln for ln in lines[:40]):
        return {"file": rel, "bytes": path.stat().st_size, "findings": [], "p0": 0, "p1": 0,
                "p2": 0, "skipped": "code-taste: ignore-file", "manual_rules_not_implemented": []}
    is_out = _is_output_script(path, text)
    suffix = path.suffix.lower()
    if suffix in PY_SUFFIX:
        findings = audit_py(path, text, lines, is_out, index, rel)
    elif suffix in JS_SUFFIX:
        findings = audit_js(path, text, lines, is_out, index, rel)
    else:
        findings = audit_other(path, text, lines, is_out)
    cleaned = []
    for f in findings:
        keep = [h for h in f["hits"]
                if not (0 < h["line"] <= len(lines)
                        and "code-taste: ignore-line" in lines[h["line"] - 1])]
        if keep:
            cleaned.append(dict(f, hits=keep, count=len(keep)))
    findings = cleaned
    return {"file": rel, "bytes": path.stat().st_size, "findings": findings,
            "p0": sum(1 for f in findings if f["tier"] == "P0"),
            "p1": sum(1 for f in findings if f["tier"] == "P1"),
            "p2": sum(1 for f in findings if f["tier"] == "P2"),
            "manual_rules_not_implemented": [{"id": i, "tier": t, "what": w} for i, t, w in MANUAL_RULES]}


def collect(targets) -> list[Path]:
    out: list[Path] = []
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.is_dir():
            out += list(_iter_code_files(p))
        elif p.is_file() and p.suffix.lower() in (PY_SUFFIX | JS_SUFFIX | OTHER_SUFFIX):
            # 传一个 `README.md` 绝不静默通过（那是假绿）—— 只收真代码后缀。
            out.append(p)
    return out


def _lang_of(path: Path) -> str:
    s = path.suffix.lower()
    if s in PY_SUFFIX:
        return "py"
    if s in JS_SUFFIX:
        return "js"
    return "other"


def _py_classes(tree) -> dict:
    """{类名: [基类名]} —— 给「单个实现的接口」用。"""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(b.attr)
            out[node.name] = bases
    return out


def _call_counts(path: Path, text: str, stripped: str) -> dict:
    """扫描面内**每个函数被调了几次**（M2 要的信息：只被调一次的包装最可疑）。

    Python 走 AST（`ast.Call` 精确，不会把 `def f(` 算成调用）；
    JS/TS 走剥壳后的正则，并排掉 `function f(` / `new f(`。
    """
    counts: dict[str, int] = defaultdict(int)
    if path.suffix.lower() in PY_SUFFIX:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return counts
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    counts[f.id] += 1
                elif isinstance(f, ast.Attribute):
                    counts[f.attr] += 1
        return counts
    for m in re.finditer(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(", stripped):
        name = m.group(1)
        if name in JS_CONTROL_WORDS:
            continue
        head = stripped[max(0, m.start() - 12):m.start()]
        if re.search(r"(?:function|new|class)\s*$", head):
            continue
        counts[name] += 1
    return counts


def build_repo_index(files: list[Path]) -> dict:
    """**仓级索引**：跨文件重复 · 调用次数 · 子类关系 · 每种语言的主导命名约定。

    为什么非要有它：M2「只被调一次的包装」与 M3「与既有约定一致」**本来就是跨文件的** ——
    只看单个文件永远判不了。这个索引把这两件事从"只能人看"变成"可算的读数"。
    它**只在本器一次扫多个文件时才有内容**；单文件审计时索引为空、相关判据自动不报
    （如实降级，不假报）。
    """
    idx = {"cross": {}, "calls": defaultdict(int), "subs": defaultdict(set),
           "known_classes": set(), "conv": {k: {"snake": 0, "camel": 0} for k in ("py", "js", "other")}}
    window_owners: dict[tuple, list] = defaultdict(list)
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
        lang = _lang_of(p)
        for key, line in _norm_windows(text).items():
            window_owners[key].append((rel, line))
        for name, n in _call_counts(p, text, _strip_js(text) if lang == "js" else text).items():
            idx["calls"][name] += n
        classes: dict[str, list] = {}
        if lang == "py":
            try:
                classes = _py_classes(ast.parse(text))
            except SyntaxError:
                classes = {}
        else:
            for m in re.finditer(r"\bclass\s+([\w$]+)(?:\s+extends\s+([\w$.]+))?", text):
                classes[m.group(1)] = [m.group(2).split(".")[-1]] if m.group(2) else []
        for name, bases in classes.items():
            idx["known_classes"].add(name)
            for b in bases:
                idx["subs"][b].add(name)
        # 主导约定：按**语言族**分别累计（拿 JS 的 camelCase 去比 Python 的 snake_case 是错的）
        for m in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)", text):
            nm = m.group(1)
            if "_" in nm and nm.islower():
                idx["conv"][lang]["snake"] += 1
            elif re.search(r"[a-z][A-Z]", nm):
                idx["conv"][lang]["camel"] += 1
        if lang == "py":
            for m in re.finditer(r"\bdef\s+([a-z_][\w]*)\s*\(([^)]*)\)", text):
                for nm in [m.group(1)] + [a.strip() for a in m.group(2).split(",")]:
                    if not nm or nm in ("self", "cls"):
                        continue
                    if "_" in nm and nm.islower():
                        idx["conv"][lang]["snake"] += 1
                    elif re.search(r"[a-z][A-Z]", nm):
                        idx["conv"][lang]["camel"] += 1
    idx["cross"] = {k: v for k, v in window_owners.items() if len({f for f, _ in v}) > 1}
    return idx


def build_cross_index(files: list[Path]) -> dict:
    """保留旧接口（跨文件索引），内部走仓级索引。"""
    return build_repo_index(files)["cross"]


def _print_report(results: list[dict]) -> tuple[int, int, int]:
    total_p0 = total_p1 = total_p2 = 0
    for r in results:
        total_p0 += r["p0"]
        total_p1 += r["p1"]
        total_p2 += r["p2"]
        flag = "🔴" if r["p0"] else ("🟡" if r["p1"] else "✅")
        print("\n%s %s  (P0 %d · P1 %d · P2 %d)" % (flag, r["file"], r["p0"], r["p1"], r["p2"]))
        for fd in r["findings"]:
            print("   [%s] %s %s —— 命中 %d" % (fd["tier"], fd["id"], fd["title"], fd["count"]))
            for h in fd["hits"][:2]:
                where = ("第 %d 行" % h["line"]) if h["line"] else "合计"
                print("        %s: %s" % (where, h["text"][:120]))
            if fd.get("note"):
                print("        → %s" % fd["note"])
        if not r["findings"]:
            print("   机器可查的规则全部通过（**不等于有品味**，见下方人看清单）")
    print("\n" + "=" * 84)
    print("机器查不了的（照样列出来，不假装查过；**哪几条现在是「部分机检」也写清楚了**）")
    for i, t, w in MANUAL_RULES:
        print("   [%s] %s  %s" % (t, i, w))
    print("=" * 84)
    print("命中合计（**文件×规则** 计数，不是「处数」）：P0 %d · P1 %d · P2 %d %s"
          % (total_p0, total_p1, total_p2, "⇒ 有 P0" if total_p0 else "⇒ P0 为 0"))
    print("读法：本器只判**机器可查的那部分**；P0 为 0 不等于代码好看。"
          "豁免写法：行内 `code-taste: ignore-line` · 整文件 `code-taste: ignore-file`。")
    return total_p0, total_p1, total_p2


# ── 自检：判据 + JSON 结构（一条命令全验）─────────────────────────────
SELFTEST_EXPECT = {
    "tools/codex-scripts/fixtures/code-taste-sins.py": {
        "must": {"P0-1", "P0-2", "P0-3", "P0-6", "P1-4", "P1-5", "P1-6", "P1-7", "P1-8",
                 "P1-9", "P1-10", "P1-12", "P1-12b", "P1-13", "P1-13b", "P1-13c", "P1-14",
                 "P2-11", "P2-12"},
        "p0_min": 3},
    "tools/codex-scripts/fixtures/code-taste-sins.ts": {
        "must": {"P0-1", "P0-4", "P0-5", "P0-6", "P1-4", "P1-5", "P1-6", "P1-7", "P1-8",
                 "P1-9", "P1-10", "P1-12", "P1-12b", "P1-13", "P1-13b", "P1-14", "P2-11"},
        "p0_min": 3},
    "tools/codex-scripts/fixtures/code-taste-cross-a.py": {
        "must": {"P1-11", "P1-9"}, "p0_min": 0},
    "tools/codex-scripts/fixtures/code-taste-cross-b.py": {
        "must": {"P1-11"}, "p0_min": 0},
    "tools/codex-scripts/fixtures/code-taste-sins.php": {
        "must": {"P0-1", "P0-2", "P0-3"}, "p0_min": 3},
    "tools/codex-scripts/fixtures/code-taste-sins.rb": {
        "must": {"P0-1", "P0-3"}, "p0_min": 2},
    "tools/codex-scripts/fixtures/code-taste-sins.go": {
        "must": {"P0-1", "P0-2"}, "p0_min": 2},
    "tools/codex-scripts/fixtures/code-taste-sins.rs": {
        "must": {"P0-3"}, "p0_min": 1},
    "tools/codex-scripts/fixtures/test_code_taste_ghost.py": {"must": {"P0-4"}, "p0_min": 1},
    "tools/codex-scripts/fixtures/code-taste-clean.py": {"must": set(), "p0_min": 0, "all_zero": True},
    "tools/codex-scripts/fixtures/code-taste-clean.ts": {"must": set(), "p0_min": 0, "all_zero": True},
}


def cmd_selftest() -> int:
    print("=" * 84)
    print("判据自检（`--selftest`）：负对照必须逐条命中 · 正对照必须全零")
    print("=" * 84)
    files = [ROOT / rel for rel in SELFTEST_EXPECT]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        print("🔴 夹具不在盘上：%s" % "、".join(missing))
        return 1
    cross = build_repo_index(files)
    bad = 0
    for rel, exp in SELFTEST_EXPECT.items():
        r = audit_file(ROOT / rel, cross)
        got = {f["id"] for f in r["findings"]}
        miss = sorted(exp["must"] - got)
        extra = sorted(got - exp["must"]) if exp.get("all_zero") else []
        ok = not miss and r["p0"] >= exp.get("p0_min", 0) and not extra \
            and (r["p0"] == 0 if exp.get("all_zero") else True)
        if exp.get("all_zero"):
            ok = ok and r["p1"] == 0 and r["p2"] == 0
        print("%s %-56s P0 %d · P1 %d · P2 %d" % ("✅" if ok else "🔴", rel, r["p0"], r["p1"], r["p2"]))
        if miss:
            print("      缺命中：%s" % "、".join(miss))
        if extra:
            print("      正对照不该有：%s" % "、".join(extra))
        bad += 0 if ok else 1

    # JSON 结构自检（缺口 7：逐字段核对，不只"能落盘"）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "selftest.json"
        payload = {"results": [audit_file(ROOT / k, cross) for k in SELFTEST_EXPECT],
                   "p0_total": 0, "p1_total": 0, "p2_total": 0}
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        back = json.loads(out.read_text(encoding="utf-8"))
    schema_bad = []
    if not isinstance(back.get("results"), list) or len(back["results"]) != len(SELFTEST_EXPECT):
        schema_bad.append("results 不是长度正确的列表")
    for r in back.get("results", []):
        for k, t in (("file", str), ("bytes", int), ("p0", int), ("p1", int), ("p2", int)):
            if not isinstance(r.get(k), t):
                schema_bad.append("%s.%s 类型不对" % (r.get("file"), k))
        if not isinstance(r.get("findings"), list) or not isinstance(
                r.get("manual_rules_not_implemented"), list):
            schema_bad.append("%s.findings/manual 不是列表" % r.get("file"))
        for f in r.get("findings", []):
            for k, t in (("id", str), ("tier", str), ("title", str), ("count", int)):
                if not isinstance(f.get(k), t):
                    schema_bad.append("finding.%s 类型不对" % k)
            for h in f.get("hits", []):
                if not isinstance(h.get("line"), int) or not isinstance(h.get("text"), str):
                    schema_bad.append("hit.line/text 类型不对")
    print("-" * 84)
    print("JSON 结构自检：%s" % ("✅ 逐字段类型都对" if not schema_bad
                            else "🔴 " + "；".join(sorted(set(schema_bad)))))
    print("结论：%s（不达预期的夹具 %d 个）" % ("✅ 判据与 JSON 结构都过" if not bad and not schema_bad
                                   else "🔴 不过", bad))
    return 1 if (bad or schema_bad) else 0


def cmd_sensitivity(targets: list[str]) -> int:
    """阈值敏感性：**没有外部基准，就量自己的敏感性**（缺口 5）。"""
    files = collect(targets)
    if not files:
        print("没找到可审的代码文件")
        return 2
    cross = build_cross_index(files)
    global MAX_FUNC_LINES, MAX_NEST_DEPTH, DUP_BLOCK_LINES
    base = (MAX_FUNC_LINES, MAX_NEST_DEPTH, DUP_BLOCK_LINES)
    print("=" * 84)
    print("阈值敏感性 · %d 个文件（改阈值会改读数 —— 所以改之前先看这张表）" % len(files))
    print("=" * 84)
    print("%-34s %6s %6s %6s" % ("阈值", "P0", "P1", "P2"))
    grid = [(40, 4, 6), (60, 5, 8), (80, 5, 8), (120, 6, 12), (200, 8, 16)]
    for fl, nd, db in grid:
        MAX_FUNC_LINES, MAX_NEST_DEPTH, DUP_BLOCK_LINES = fl, nd, db
        p0 = p1 = p2 = 0
        for f in files:
            r = audit_file(f, cross)
            p0 += r["p0"]
            p1 += r["p1"]
            p2 += r["p2"]
        mark = "  ← 现用" if (fl, nd, db) == (80, 5, 8) else ""
        print("%-34s %6d %6d %6d%s" % ("函数%d行/嵌套%d层/重复%d行" % (fl, nd, db), p0, p1, p2, mark))
    MAX_FUNC_LINES, MAX_NEST_DEPTH, DUP_BLOCK_LINES = base
    print("-" * 84)
    print("读法：P0 不随这三个阈值变化（它们只影响 P1 的 5/6/7）—— 所以调阈值**只改 P1 读数**。")
    return 0


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    json_out = None
    if "--json" in argv:
        i = argv.index("--json")
        if i + 1 < len(argv):
            json_out = Path(argv[i + 1])
            args = [a for a in args if a != argv[i + 1]]
    if "--selftest" in argv:
        return cmd_selftest()
    if not args:
        print(__doc__)
        return 2
    if "--sensitivity" in argv:
        return cmd_sensitivity(args)

    files = collect(args)
    if not files:
        print("没找到任何可审的代码文件（收 .py/.js/.jsx/.ts/.tsx/.mjs/.cjs/.php/.rb/.go/.rs/.vue）")
        return 2

    print("=" * 84)
    print("代码审美审计 · %d 个文件（Python 走 AST · JS/TS 走块匹配 · 多语言只做行级）" % len(files))
    print("=" * 84)
    cross = build_repo_index(files)
    results = [audit_file(f, cross) for f in files]
    total_p0, total_p1, total_p2 = _print_report(results)

    if json_out:
        json_out.write_text(json.dumps(
            {"results": results, "p0_total": total_p0, "p1_total": total_p1, "p2_total": total_p2},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print("落盘: %s" % json_out)
    return 1 if total_p0 else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
