# -*- coding: utf-8 -*-
"""部署反查（audit-deployed）：**把"文档说设计了、代码里没有"的账算清楚**。

主人 2026-11-01（逐字）：「我设计了无数原生能力，有些估计压根你就没给我部署上去过，哎」

所以这个脚本不猜，只做三张清单（全部可从源码/文档复现）：

  A. **标了但没登记**：源码里写了 `# gbt-capability: X` 标记、X 却不在注册表
     （例：`tools/context_guard.py` 曾经就是这样 —— 有实现、没能力位）
  B. **文档提了但没登记**：`docs/**/*.md` 里以反引号出现、且上下文含"能力/位/run_task/op="
     的 snake_case 名字，不在注册表 —— 即"文档吹了、代码没有"
  C. **登记了但没实现**：注册表有、handler 模块找不到（这条本来由 cap_self 兜，这里再独立验一次）

用法：
    python tools/codex-scripts/audit-deployed.py            # 三张清单 + 摘要
    python tools/codex-scripts/audit-deployed.py --json state/audit-deployed.json --limit 40
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

CAP_RE = re.compile(r"#\s*gbt-capability:\s*([A-Za-z0-9_]+)")
CODE_EXT = {".py", ".js", ".cjs", ".mjs"}
SKIP_DIRS = {"node_modules", ".pylibs", "vendor", "mirror_space", "__pycache__", ".git",
             "dist", "_upstream", "archives", ".scratch", ".trash", "outputs", "state"}
NAME_RE = re.compile(r"`([a-z][a-z0-9_]{3,40})`")

# 强证据：明确写了"用哪个能力位"的行（比裸反引号可信得多）
STRONG_RE = re.compile(
    r"run_task\(\s*['\"]([a-z][a-z0-9_]{3,40})|"
    r"kind\s*==\s*['\"]([a-z][a-z0-9_]{3,40})|"
    r"能力位\s*`([a-z][a-z0-9_]{3,40})|"
    r"`([a-z][a-z0-9_]{3,40})`\s*(?:能力位|这个能力|这个位)")
CONTEXT_WORDS = ("能力", "能力位", "run_task", "op=", "capability", "capabilities", "cap ")
# 反引号里常见但**不是能力位**的词（避免噪音）
COMMON_NOT_CAP = {
    "true", "false", "none", "null", "ok", "error", "status", "result", "data",
    "json", "jsonl", "yaml", "utf", "ascii", "http", "https", "stdout", "stderr",
    "python", "powershell", "bash", "shell", "windows", "linux", "macos",
    "state", "store", "audit", "docs", "tools", "tests", "src", "lib", "bin",
    "readme", "changelog", "license", "todo", "fixme", "note", "notes",
}


def _registry() -> dict:
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return dict(BENIGN_CAPS)


def _iter_files(exts, dirs=None):
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if dirs:
            rel = os.path.relpath(dirpath, ROOT).replace("\\", "/")
            if not any(rel == d or rel.startswith(d + "/") for d in dirs):
                continue
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in exts:
                yield os.path.join(dirpath, fn)


def marked_but_unregistered(caps: set) -> list:
    out = []
    for path in _iter_files(CODE_EXT):
        try:
            text = open(path, encoding="utf-8", errors="replace").read(40000)
        except OSError:
            continue
        if 'def run(' not in text:          # 不像能力模块（没有 run 接口）⇒ 不算
            continue
        for m in CAP_RE.finditer(text):
            name = m.group(1)
            if name not in caps:
                out.append({"name": name, "file": os.path.relpath(path, ROOT).replace("\\", "/"),
                            "line": text[: m.start()].count("\n") + 1})
    return out


def documented_but_unregistered(caps: set, limit: int) -> tuple[list, int]:
    counts: dict[str, int] = {}
    files: dict[str, str] = {}
    for path in _iter_files({".md"}, dirs=["docs"]):
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        try:
            for ln in open(path, encoding="utf-8", errors="replace"):
                # 强上下文优先：run_task('x') / kind == "x" / 能力位 x
                strong = [g for m in STRONG_RE.finditer(ln) for g in m.groups() if g]
                if strong:
                    for name in strong:
                        if name in caps or name in COMMON_NOT_CAP:
                            continue
                        counts[name] = counts.get(name, 0) + 3   # 强证据加权
                        files.setdefault(name, rel)
                    continue
                if not any(w in ln.lower() for w in CONTEXT_WORDS):
                    continue
                for name in NAME_RE.findall(ln):
                    if name in caps or name in COMMON_NOT_CAP:
                        continue
                    if len(name) < 4 or name.isdigit():
                        continue
                    counts[name] = counts.get(name, 0) + 1
                    files.setdefault(name, rel)
        except OSError:
            continue
    ranked = sorted(((n, c) for n, c in counts.items() if c >= 2), key=lambda kv: -kv[1])
    rows = [{"name": n, "mentions": c, "sample_file": files.get(n)} for n, c in ranked]
    return rows[:limit], len(rows)


def registered_but_no_impl(caps: dict) -> list:
    out = []
    for name, meta in caps.items():
        handler = str(meta.get("handler") or name)
        # 实现要么在 gbt_allinone/<handler>.py，要么在子包里，要么在 api.py 内联
        cands = [os.path.join(ROOT, "gbt_allinone", handler + ".py"),
                 os.path.join(ROOT, "gbt_allinone", "tentacle", handler + ".py")]
        pkg = os.path.join(ROOT, "gbt_allinone", "tentacle", handler)
        if not any(os.path.exists(c) for c in cands) and not os.path.isdir(pkg):
            txt = ""
            try:
                txt = open(os.path.join(ROOT, "gbt_allinone", "api.py"), encoding="utf-8",
                           errors="replace").read()
            except OSError:
                pass
            if ('kind == "%s"' % name) in txt or ('kind in (' in txt and '"%s"' % name in txt):
                continue
            out.append({"name": name, "handler": handler})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    caps = _registry()
    names = set(caps)
    a = marked_but_unregistered(names)
    b, b_total = documented_but_unregistered(names, args.limit)
    c = registered_but_no_impl(caps)

    print("== 部署反查 ==")
    print("注册表能力位：%d" % len(caps))
    print()
    print("A. 标了 gbt-capability 但没登记：%d 个" % len(a))
    for x in a[:10]:
        print("   %-28s %s:%s" % (x["name"], x["file"], x["line"]))
    print()
    print("B. 文档提了但没登记：%d 个（展示前 %d）" % (b_total, len(b)))
    for x in b[:10]:
        print("   %-28s 提及 %2d 次  %s" % (x["name"], x["mentions"], x["sample_file"]))
    print()
    print("C. 登记了但找不到实现：%d 个" % len(c))
    for x in c[:10]:
        print("   %-28s handler=%s" % (x["name"], x["handler"]))

    out = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
           "registry": len(caps),
           "marked_but_unregistered": a,
           "documented_but_unregistered": {"total": b_total, "top": b},
           "registered_but_no_impl": c}
    if args.json:
        dst = args.json if os.path.isabs(args.json) else os.path.join(ROOT, args.json)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\n落盘：", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
