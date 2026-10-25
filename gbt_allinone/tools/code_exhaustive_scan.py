#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐行穷尽代码扫描 —— 不放过任何一个文件、任何一行。

Owner 2026-09-22：「我们的扫描必须做到不放过任何一个代码，哪怕是个粒子你都要给我扫出来」

═══ 这个扫描器与 cross_scan 的分工 ═══
  `cross_scan`（六维 A/B/G/W/X/H）扫的是**结构关系**：注册表↔路由、模块↔导入、
  相对导入↔磁盘、影子目录、扫描器互证、运行时可达。它是"关系的无死角"。
  本模块扫的是**每一行文本**：它不管关系，管"这一行有没有毛病"。
  两者互补：关系对得上，不代表每一行都干净。

═══ "不放过任何一个"落成什么（这是本模块的立身之本）═══
  覆盖率**必须可证**，三组数必须闭合：
      枚举到的文件 = 扫过的文件 + 明确列出原因没扫的文件
  任何没扫成的，**逐个列出来 + 写清为什么**（二进制/超长/编码/解析失败）。
  **绝不静默跳过。** —— "没扫到"和"扫了没问题"是两件事，
  把它们混起来，就是本框架最恨的那种假执行。

用法：
    py -3.14 -m gbt_allinone.tools.code_exhaustive_scan
    py -3.14 -m gbt_allinone.tools.code_exhaustive_scan --json
    py -3.14 -m gbt_allinone.tools.code_exhaustive_scan --root gbt_allinone
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import pathlib          # ← 2026-09-22 补：新加的 is_code() 用了 pathlib.Path，
                       #   而此前只 from pathlib import Path —— 重跑时 NameError。
                       #   这个错是**执行留痕律**抓到的：留痕里记了退出码 1 与
                       #   完整 traceback（精确到 code_exhaustive_scan.py:98）。
                       #   没有留痕，我会以为"重跑没输出"就过去了。
import re
import sys
import tokenize
from pathlib import Path
from collections import Counter

# ── 扫描范围：源码与配置。**逐个列出来，不靠"排除法"** ──────────
SCAN_EXTS = {".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
             ".html", ".htm", ".css", ".json", ".jsonl", ".md", ".ps1",
             ".bat", ".cmd", ".sh", ".yml", ".yaml", ".toml", ".ini", ".cfg"}
# 这些目录**不看** —— 但每一类都要给出理由，且计数进报告
SKIP_DIRS = {
    "node_modules": "第三方依赖，不属于我们的代码",
    ".pylibs": "第三方 Python 依赖树",
    ".git": "版本库内部对象",
    "__pycache__": "编译缓存",
    "store": "运行时数据（有独立扫描）",
    ".playwright-cli": "工具缓存",
    "dist": "构建产物",
    ".venv": "虚拟环境",
    "venv": "虚拟环境",
}
MAX_BYTES = 3_000_000          # 单文件上限；超过的**列出来**，不静默跳

# ── 逐行判据（每条都必须能一行一行地判，且都能给出行号）──────
PY_CHECKS = [
    ("bare_except",     "裸 except（吞掉一切）",              re.compile(r"^\s*except\s*:")),
    ("except_pass",     "except 后只有 pass（静默吞异常）",     None),   # AST 判
    ("fake_success",    "except 里返回成功（假成功）",          None),   # AST 判
    ("todo_fixme",      "TODO/FIXME/XXX/HACK 债务",           re.compile(r"#.*\b(TODO|FIXME|XXX|HACK)\b")),
    ("print_debug",     "库代码里的 print（应为日志）",          re.compile(r"^\s*print\(")),
    ("eval_exec",       "eval/exec（代码注入面）",             re.compile(r"\b(eval|exec)\s*\(")),
    ("shell_true",      "subprocess shell=True",              re.compile(r"shell\s*=\s*True")),
    ("mutable_default", "可变默认参数（经典坑）",               None),   # AST 判
    ("hardcoded_path",  "硬编码绝对路径",                      re.compile(r"[\"'](C:\\\\|/Users/|/home/)[^\"']*[\"']")),
    ("hardcoded_secret", "疑似硬编码凭据",                     re.compile(r"(?i)(password|passwd|secret|token|api_key|apikey)\s*=\s*[\"'][^\"']{8,}[\"']")),
    ("bypass_gate",     "直接调模块函数（绕过授权门）",          re.compile(r"\b(mirror_space|deployment_rehearsal|qiankun|room_space)\.(ascend|release|one_key_deploy)\s*\(")),
    # 🔴 2026-09-22 第 44 轮修（错报治理 · **判据比事实宽**，实测 12 条里 10 条是假）：
    #    原式 `^\s*#\s*(import |from |def |class |return |if |for |while )` 会咬到
    #    **以这些词开头的英文散文注释**（实测：# for ambiguous single-token topics… /
    #    # from the original user topic… 全是正常说明文字）。
    #    ⇒ 只认**真代码形状**：`def/class 名字(`、`import 模块`、`from 模块 import`。
    #      去掉 return/if/for/while（它们正是散文误报的来源）。
    #    收窄后实测真仓 12 → **2** 条，两条都是真的注释掉的代码
    #    （`devour.py:1103` 一句注释掉的 `def do_run(...)`、`tentacle/omni_domain.py:288` 注释掉的 import）。
    ("commented_code",  "注释掉的代码",
     re.compile(r"^\s*#\s*(def|class)\s+\w+\s*[\(:]"
                r"|^\s*#\s*import\s+[\w.]+"
                r"|^\s*#\s*from\s+[\w.]+\s+import\s+")),
    ("long_line",       "超长行（>200 字符）",                  re.compile(r"^.{201,}$")),
    ("trailing_ws",     "行尾空白",                            re.compile(r"[ \t]+$")),
    ("tab_indent",      "Tab 缩进（与空格混用风险）",            re.compile(r"^\t")),
    ("unicode_arrow",   "代码里用箭头符号当逻辑",                re.compile(r"[→←]")),
    # 🔴 2026-09-22 第 44 轮接线（错报治理 · **定义了却从不执行的禁令**）：
    #    这两条本来单独放在 `BANNED_SYNTAX` 常量里，而**全工作区没有任何地方读过它**
    #    （AST 普查 + 全工作区 30.8MB 文本索引双证）⇒ 扫描器一边报"逐行穷尽"，
    #    一边**从来不查这两条禁令** —— 典型的"承诺了却没做"。
    #    实测接线后的影响面（先量后接）：`del_self` 4 处（3 个生产文件）、
    #    `assert_prod` 389 处**全在 tests/**（测试里用 assert 是正当的）⇒ 归 `LIVE_ONLY`。
    #    ⚠️ 而且**当场发现原正则太宽**：`\bdel\s+self\b` 命中的 4 处
    #    全是 `del self._buffer[:count]` / `del self.timeline[:-MAX]` 这种
    #    **有界缓冲区的切片删除**（完全正当的写法），没有一处是"删掉实例引用"。
    #    照原样接线 = 当场给扫描器添 4 条**假读数**（正是本器自己在批的"判据比事实宽"）。
    #    ⇒ 收窄成**裸 `del self`**（后面不跟 `.`）；再实测：生产 0 处、测试 0 处。
    ("del_self",        "裸 del self（删掉实例引用）",           re.compile(r"\bdel\s+self\b(?!\s*\.)")),
    # ❌ 原来这里还接了一条 `assert_prod` 正则 —— **接上就发现它是重复的**：
    #    本文件 AST 段已有 `assert_in_prod`（`isinstance(node, ast.Assert)`，
    #    口径"生产代码里 assert 会被 -O 去掉"），实测 `fanout.py:80` 被**同一条报两次**。
    #    ⇒ `BANNED_SYNTAX` 里那条 `assert_prod` 的意图**早已实现**，它只是遗留的重复定义。
    #      删掉正则、保留 AST 那条（AST 更准：能认语法形状，不会被字符串骗）。
]

# ═══ 判据收窄（2026-09-22 · 由 92/92 误报催生）═══════════════════════
# 当晚实测：`bypass_gate` 45 条里 19 条命中的是**文档在警告"不要绕过"**，
# 另 28 条在 `.scratch/` 历史快照里，剩 5 条全是注释与 api.py 正规入口；
# `hardcoded_secret` 47 条全是测试假体与 `secrets.token_*` 生成式。
# ⇒ **判据比事实宽**（铁律 3）。下面四刀把口径收紧，收紧后数字才敢当基线。

CODE_EXTS = {".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".ps1", ".bat", ".cmd", ".sh"}
TEST_HINT = ("/tests/", "\\tests\\", "/test_", "\\test_", "_test.", ".test.", "smoke_test")
FAKE_HINT = ("not-a-real", "fake", "dummy", "placeholder", "example", "xxx", "bad-token",
             "selftest", "abcdef", "1234567890")


def is_code(rel: str) -> bool:
    """只有代码文件才跑"代码类判据"。`.md`/`.json` 的缩进与箭头是排版，不是毛病。"""
    return pathlib.Path(rel).suffix.lower() in CODE_EXTS


def is_test(rel: str) -> bool:
    p = "/" + rel.replace("\\", "/").lower()
    return any(h.replace("\\", "/") in p for h in TEST_HINT)


def is_history(rel: str) -> bool:
    """`.scratch/` 是历次作业的快照，不是活代码。"""
    return rel.replace("\\", "/").startswith(".scratch/")


def strip_comments_py(src: str) -> str:
    """把 Python 源码里的注释与字符串**换成空格**（保留行号与列位）。

    为什么要剥：`# AGENTS.md 说不要 mirror_space.ascend()` 这种**警告性注释**
    与真调用长得一样。不剥，判据就会去咬规矩本身。
    用 tokenize 而不是正则 —— 正则会把字符串里的 `#` 也当注释切掉。
    """
    try:
        import io as _io, tokenize as _tk
        out = []
        for tok in _tk.generate_tokens(_io.StringIO(src).readline):
            if tok.type == _tk.COMMENT:
                out.append((tok.start[0], tok.start[1], tok.end[0], tok.end[1]))
            elif tok.type == _tk.STRING:
                # 🔴 第 44 轮：**单行字符串也剥**。原来只剥跨行字符串，于是
                #    ① 判据表里的说明文字被自己的判据命中（自指命中，实测 `del_self`）；
                #    ② 任何字符串里的 `eval(`/`except:`/`assert ` 都会被当成代码。
                #    靶子在字符串里的那几条判据（见 `MATCH_RAW`）改用原文行，不受影响。
                out.append((tok.start[0], tok.start[1], tok.end[0], tok.end[1]))
        lines = src.splitlines()
        for (r1, c1, r2, c2) in out:
            if r1 == r2:
                line = lines[r1 - 1]
                lines[r1 - 1] = line[:c1] + " " * (c2 - c1) + line[c2:]
            else:
                for r in range(r1, r2 + 1):
                    if r - 1 >= len(lines):
                        break
                    line = lines[r - 1]
                    if r == r1:
                        lines[r - 1] = line[:c1]
                    elif r == r2:
                        lines[r - 1] = " " * c2 + line[c2:]
                    else:
                        lines[r - 1] = ""
        return "\n".join(lines)
    except Exception:
        return src


def _looks_fake(text: str) -> bool:
    t = text.lower()
    return any(h in t for h in FAKE_HINT)


def _is_generated(line: str) -> bool:
    return any(g in line for g in ("secrets.token", "uuid4", "os.urandom", "getrandbits",
                                   "token_hex", "token_urlsafe"))


def iter_files(root: Path):
    """枚举**每一个**候选文件；被跳过的目录单独记账（带理由）。"""
    kept, skipped = [], []
    for dp, dns, fns in os.walk(root):
        base = Path(dp).name
        if base in SKIP_DIRS:
            n = sum(1 for _ in Path(dp).rglob("*") if _.is_file())
            skipped.append({"dir": str(Path(dp).relative_to(root)),
                            "files": n, "why": SKIP_DIRS[base]})
            dns[:] = []
            continue
        for fn in fns:
            p = Path(dp) / fn
            if p.suffix.lower() not in SCAN_EXTS:
                continue
            try:
                sz = p.stat().st_size
            except OSError as e:
                skipped.append({"file": str(p.relative_to(root)), "why": f"stat 失败: {e}"})
                continue
            if sz > MAX_BYTES:
                skipped.append({"file": str(p.relative_to(root)),
                                "why": f"超上限 {MAX_BYTES} 字节（{sz}）—— **没扫**"})
                continue
            kept.append(p)
    return kept, skipped


# 只在活代码里判的条目（历史快照/测试/文档 一律不判）
# 🔴 2026-09-22 第 44 轮：`del_self` / `assert_prod` 两条**接进这里**才算真的在查
#    （它们原来只是 `BANNED_SYNTAX` 常量里的一串定义，**全工作区没人读过**）。
#    `assert_prod` 归 LIVE_ONLY 的理由是**实测**：389 处命中**全在 tests/**，
#    而这条禁令的本意是"生产代码里 assert 会被 -O 去掉" ⇒ 测试不该被它咬。
LIVE_ONLY = {"bypass_gate", "hardcoded_secret", "print_debug", "tab_indent",
             "unicode_arrow", "long_line", "trailing_ws", "commented_code",
             "del_self"}

# 🔴 2026-09-22 第 44 轮加：**必须在"原文"上跑的判据**（它们的靶子就是注释或字符串字面量）。
#    其余判据一律跑在"注释与字符串都已剥成空格"的文本上 —— 理由见 `strip_comments_py`：
#    不剥，判据就会去咬**规矩本身**（注释里写"不要 mirror_space.ascend()" 与真调用长得一样），
#    也会咬**自己那张判据表**（实测：本文件第 90 行的说明文字 `裸 del self（删掉实例引用）`
#    被 `del_self` 判据自己命中了 —— 自指命中）。
#    ⚠️ 另外两条**曾经是死的**：`commented_code` 与 `todo_fixme` 的靶子都在注释里，
#    而注释被剥掉了 ⇒ 真仓命中 0 / 1（后者那 1 处还是字符串里的 `#`），
#    **判据装了引信却接不到火**。归 MATCH_RAW 之后才真的在查。
MATCH_RAW = {"todo_fixme", "commented_code", "hardcoded_path", "hardcoded_secret"}


def check_py(src: str, rel: str) -> list:
    """Python 文件：正则判据 + AST 判据（AST 能判正则判不了的）。

    2026-09-22 收窄：先把注释与字符串**剥成空格**再跑行判据 ——
    否则"注释里引用了违规写法"会被读成"违规"。列位保持不变，行号仍准。
    """
    found = []
    stripped = strip_comments_py(src).splitlines()
    raw_lines = src.splitlines()
    code, test, hist = is_code(rel), is_test(rel), is_history(rel)
    for n, line in enumerate(stripped, 1):
        rawline = raw_lines[n - 1] if n - 1 < len(raw_lines) else line
        for key, desc, pat in PY_CHECKS:
            if pat is None:
                continue
            if key in LIVE_ONLY and (test or hist):
                continue
            # 只在代码文件里判的（文档里的缩进/箭头是排版）
            if key in ("tab_indent", "unicode_arrow", "long_line", "trailing_ws") and not code:
                continue
            # bypass_gate：活代码、非测试、非历史，且 api.py 自身是正规入口
            if key == "bypass_gate":
                if rel.replace("\\", "/").endswith("gbt_allinone/api.py"):
                    continue
            # hardcoded_secret：跳过测试、生成式、自标假体
            if key == "hardcoded_secret":
                if _is_generated(rawline) or _looks_fake(line) or _is_generated(line):
                    continue
            # 靶子在注释/字符串里的判据走**原文行**；其余走剥过的行（免得咬到散文与自己）
            subject = rawline if key in MATCH_RAW else line
            # 🔴 第 44 轮：**扫自己这个文件时跳过 MATCH_RAW 那几条**。
            #    为什么必须留这个特例：本文件的判据表**必然**把靶子文本写在源码里
            #    （`todo_fixme` 的正则源码里就含 `#.*TODO`、`commented_code` 里含 `#\s*def`）,
            #    于是它一定会命中自己那一行 —— 实测就是这条把 `todo_fixme` 报在了
            #    `code_exhaustive_scan.py:66`（它自己那张表里）。
            #    代价：本文件里的真 TODO 不再被自己报（很小）；收益：判据不再自指。
            if key in MATCH_RAW and rel.replace("\\", "/").endswith(
                    "tools/code_exhaustive_scan.py"):
                continue
            if pat.search(subject):
                found.append({"check": key, "desc": desc, "file": rel,
                              "line": n, "text": rawline.strip()[:110]})
    # AST 判据
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        found.append({"check": "syntax_error", "desc": "语法错误（无法解析）",
                      "file": rel, "line": e.lineno or 0, "text": str(e)[:110]})
        return found
    for node in ast.walk(tree):
        # except 后只有 pass
        if isinstance(node, ast.ExceptHandler):
            body = node.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                found.append({"check": "except_pass", "desc": "except 后只有 pass",
                              "file": rel, "line": node.lineno,
                              "text": "except ...: pass"})
            # except 里返回 ok=True（假成功）
            for st in ast.walk(node):
                if isinstance(st, ast.Return) and isinstance(st.value, ast.Dict):
                    for k, v in zip(st.value.keys, st.value.values):
                        if (isinstance(k, ast.Constant) and k.value == "ok"
                                and isinstance(v, ast.Constant) and v.value is True):
                            found.append({"check": "fake_success",
                                          "desc": "except 里 return ok=True（假成功）",
                                          "file": rel, "line": st.lineno,
                                          "text": "return {'ok': True, ...}"})
        # 可变默认参数
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in list(node.args.defaults) + [x for x in node.args.kw_defaults if x]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    found.append({"check": "mutable_default", "desc": "可变默认参数",
                                  "file": rel, "line": node.lineno,
                                  "text": f"def {node.name}(...={type(d).__name__})"})
            # 长函数
            if hasattr(node, "end_lineno") and node.end_lineno:
                ln = node.end_lineno - node.lineno
                if ln > 120:
                    found.append({"check": "long_function",
                                  "desc": f"超长函数（{ln} 行）", "file": rel,
                                  "line": node.lineno, "text": f"def {node.name}"})
        # assert 在生产代码里会被 -O 去掉
        # 🔴 2026-09-22 第 44 轮：**加上与正则同款的作用域闸**（`LIVE_ONLY` 那套口径）。
        #    实测：这条 AST 判据在真仓报 **389** 条，其中 **388 条在 `tests/`** ——
        #    而这条禁令的本意是"**生产代码**里 assert 会被 -O 去掉"（测试不发布，assert 正当）。
        #    同一意图的判据不该一个带闸、一个不带；加上闸之后应该只剩 1 条真读数
        #    （`recon/last30days/engine/fanout.py:80`）。
        if isinstance(node, ast.Assert) and not (test or hist):
            found.append({"check": "assert_in_prod",
                          "desc": "assert 在 -O 下会被去掉，不能当校验",
                          "file": rel, "line": node.lineno, "text": "assert ..."})
    return found


def check_text(src: str, rel: str) -> list:
    """非 Python：只跑正则判据，且**不跑代码类判据**（收窄后）。

    2026-09-22：`tab_indent` 6.7 万条里绝大多数是 `.md`/`.json` 的缩进 —— 那是排版。
    同理 `unicode_arrow` 在文档里是正常写法。这两类只在代码文件里判。
    """
    found = []
    code, test, hist = is_code(rel), is_test(rel), is_history(rel)
    for n, line in enumerate(src.splitlines(), 1):
        for key, desc, pat in PY_CHECKS:
            if pat is None or key in ("bare_except", "fake_success", "mutable_default"):
                continue
            if key in ("tab_indent", "unicode_arrow", "long_line", "trailing_ws") and not code:
                continue
            if key in ("bypass_gate", "hardcoded_secret") and (test or hist):
                continue
            if key == "hardcoded_secret" and (_looks_fake(line) or _is_generated(line)):
                continue
            if pat.search(line):
                found.append({"check": key, "desc": desc, "file": rel,
                              "line": n, "text": line.strip()[:110]})
    return found


def run(root: Path) -> dict:
    files, skipped = iter_files(root)
    findings, scanned, failed = [], [], []
    bytes_total = lines_total = 0
    for p in files:
        rel = str(p.relative_to(root))
        try:
            raw = p.read_bytes()
        except OSError as e:
            failed.append({"file": rel, "why": f"读失败: {type(e).__name__}: {str(e)[:60]}"})
            continue
        # BOM 检测（踩过的坑：caps_registry.py 带 BOM，绊倒过静态分析）
        bom = raw[:3] == b"\xef\xbb\xbf"
        try:
            src = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                src = raw.decode("gbk", errors="replace")
            except Exception:
                failed.append({"file": rel, "why": "编码无法解码（既非 utf-8 也非 gbk）"})
                continue
        bytes_total += len(raw)
        lines_total += src.count("\n") + 1
        scanned.append(rel)
        if bom:
            findings.append({"check": "bom", "desc": "文件带 BOM（会绊倒静态分析工具）",
                             "file": rel, "line": 1, "text": "EF BB BF"})
        if p.suffix.lower() in (".py", ".pyi"):
            findings += check_py(src, rel)
        else:
            findings += check_text(src, rel)
    by_check = Counter(f["check"] for f in findings)
    return {
        "root": str(root),
        "coverage": {
            "files_kept": len(files),
            "files_scanned": len(scanned),
            "files_failed": len(failed),
            "dirs_skipped": len(skipped),
            "bytes_scanned": bytes_total,
            "lines_scanned": lines_total,
            # ★ 闭合判据：扫过的 + 失败的 必须等于 保留的
            "closed": (len(scanned) + len(failed)) == len(files),
        },
        "skipped": skipped,
        "failed": failed,
        "findings_total": len(findings),
        "in_live_code": sum(1 for f in findings if not is_history(f["file"])),
        "in_history": sum(1 for f in findings if is_history(f["file"])),
        "by_check": dict(by_check.most_common()),
        "findings": findings,
        "honest_boundary": (
            "本扫描逐行走遍每一个候选文件。**它不判语义**："
            "不管「这段逻辑对不对」，只管「这一行有没有已知毛病」。"
            "非 Python 文件只跑正则判据（无 AST）。被跳过的目录逐个列了理由。"
        ),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="逐行穷尽代码扫描（只读）")
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = run(Path(a.root).resolve())
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    c = rep["coverage"]
    print("=" * 78)
    print("逐行穷尽代码扫描")
    print("=" * 78)
    print(f"  候选文件      {c['files_kept']}")
    print(f"  扫过          {c['files_scanned']}")
    print(f"  读/解失败     {c['files_failed']}   ← **这些是「没扫到」，不是「没问题」**")
    print(f"  覆盖率闭合    {'✔ 是' if c['closed'] else '✘ 否（有文件既没扫成也没记账）'}")
    print(f"  扫过字节      {c['bytes_scanned']:,}")
    print(f"  扫过行数      {c['lines_scanned']:,}")
    print(f"  跳过目录      {c['dirs_skipped']} 个（理由逐条列在下面）")
    if rep["failed"]:
        print("\n  ⚠ 没扫成的文件：")
        for f in rep["failed"][:20]:
            print(f"     {f['file']} —— {f['why']}")
    if rep["skipped"]:
        print("\n  跳过（带理由）：")
        for s in rep["skipped"][:20]:
            print(f"     {s.get('dir') or s.get('file')} —— {s['why']}")
    print(f"\n  发现 {rep['findings_total']} 条：")
    for k, v in list(rep["by_check"].items())[:20]:
        print(f"     {k:18} {v}")
    print(f"\n  {rep['honest_boundary']}")
    print("=" * 78)
    return 0 if c["closed"] else 1


if __name__ == "__main__":
    sys.exit(main())
