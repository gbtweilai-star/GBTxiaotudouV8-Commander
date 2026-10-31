# -*- coding: utf-8 -*-
"""omni 执行纪律 + LLM 纪律（2026-10-31 · 主人令）

两条硬规矩：
  ① 执行纪律：所有执行必须走 tools/omni_adapter.execute()
  ② LLM 纪律：所有 LLM 调用必须走 tools/weights.py（我们自己的权重）

用法：
    python3 tools/omni_guard.py           # 跑两条检查，违规时报错
    python3 tools/omni_guard.py --list    # 只列不 raise
"""
from __future__ import annotations

import inspect
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

BANNED_RUN = [
    (re.compile(r"\bsubprocess\.run\s*\("),   "直接用 subprocess.run 绕过了 omni:shell"),
    (re.compile(r"\bsubprocess\.call\s*\("),  "直接用 subprocess.call 绕过了 omni:shell"),
    (re.compile(r"\bsubprocess\.Popen\s*\("), "直接用 subprocess.Popen 绕过了 omni:shell"),
    (re.compile(r"\bos\.system\s*\("),        "直接用 os.system 绕过了 omni:shell"),
    (re.compile(r"\bos\.popen\s*\("),         "直接用 os.popen 绕过了 omni:shell"),
    (re.compile(r"\burllib\.request\.urlopen\s*\("), "直接用 urllib 绕过了 omni:http"),
    (re.compile(r"\brequests\.(get|post|put|delete)\s*\("), "直接用 requests 绕过了 omni:http"),
]
RUN_EXEMPT = {"tools/omni_adapter.py", "tools/omni_guard.py"}

BANNED_LLM = [
    (re.compile(r"\bapi\.openai\.com"),                "OpenAI 端点（必须走 weights.py）"),
    (re.compile(r"\bapi\.anthropic\.com"),             "Anthropic 端点（必须走 weights.py）"),
    (re.compile(r"\bapi\.deepseek\.com"),              "DeepSeek 端点（必须走 weights.py）"),
    (re.compile(r"\bgenerativelanguage\.googleapis\.com"), "Gemini 端点（必须走 weights.py）"),
    (re.compile(r"\bapihub\.agnes-ai\.com"),           "Agnes 端点（必须走 weights.py）"),
    (re.compile(r"\bdashscope\.aliyuncs\.com"),        "阿里百炼（必须走 weights.py）"),
    (re.compile(r"\bopen\.bigmodel\.cn"),              "智谱（必须走 weights.py）"),
]
LLM_EXEMPT = {"tools/weights.py", "tools/omni_adapter.py", "tools/llm_guard.py"}


def _scan(banned, exempt):
    hits = []
    for p in ROOT.rglob("*.py"):
        rel = str(p.relative_to(ROOT))
        if rel in exempt:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for rx, why in banned:
                if rx.search(stripped):
                    hits.append({"file": rel, "line": i, "why": why, "text": stripped[:90]})
                    break
    return hits


def scan_run():
    return _scan(BANNED_RUN, RUN_EXEMPT)

def scan_llm():
    return _scan(BANNED_LLM, LLM_EXEMPT)


def require_omni(why=""):
    """必须在 omni_adapter.execute() 上下文中调用。"""
    stack = inspect.stack()
    if any("omni_adapter" in s.filename for s in stack):
        return
    lines = ["  %s:%d" % (pathlib.Path(s.filename).name, s.lineno) for s in stack[-6:]]
    msg = "纪律违犯：执行未走万能插\n调用链:\n" + "\n".join(lines)
    if why:
        msg += "\n原因：%s" % why
    msg += "\n正确做法：直接调 omni_adapter.execute(target, verb)"
    raise RuntimeError(msg)


def require_weights(why=""):
    """必须通过 weights.chat() 走 LLM。"""
    stack = inspect.stack()
    if any("weights.py" in s.filename for s in stack):
        return
    lines = ["  %s:%d" % (pathlib.Path(s.filename).name, s.lineno) for s in stack[-6:]]
    msg = "纪律违犯：LLM 调用未走 weights.py\n调用链:\n" + "\n".join(lines)
    if why:
        msg += "\n原因：%s" % why
    msg += "\n正确做法：from tools import weights; weights.chat(prompt)"
    raise RuntimeError(msg)


def main(argv):
    list_only = "--list" in argv
    v1 = scan_run()
    v2 = scan_llm()
    total = len(v1) + len(v2)

    if v1:
        print("  执行纪律违犯 %d 处（绕过 omni_adapter.execute）" % len(v1))
        for h in v1[:10]:
            print("    %s:%d  %s" % (h["file"], h["line"], h["why"]))
    if v2:
        print("  LLM 纪律违犯 %d 处（绕过 weights.py）" % len(v2))
        for h in v2[:10]:
            print("    %s:%d  %s" % (h["file"], h["line"], h["why"]))
    if not v1 and not v2:
        print("  执行纪律 + LLM 纪律 全部通过")
        return 0

    if list_only:
        return 1
    raise RuntimeError("纪律违犯 %d 处，请改完再 commit" % total)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except RuntimeError as e:
        print("\n  " + str(e))
        sys.exit(1)
