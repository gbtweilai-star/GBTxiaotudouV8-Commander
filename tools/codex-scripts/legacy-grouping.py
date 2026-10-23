#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F22 的 223 件历史遗留 —— 摊成一张**可圈选**的表（只读）。

F22 现状：2026-10-19 基线上来那批变动里，223 件在 logbook 查不到名字级证据，
按纪律**不补假理由**；处置是"明示遗留"（`state/framework-passports-legacy.json`）。
本件不改任何账，只把这 223 件按**顶层模块**分组，并为每件标三个信号：
  ① 还在不在盘上（缺的可能是删了/改名了）；
  ② 有没有别的文件引用它的名字（被引用的 = 还活着，重要度高）；
  ③ 最后一次改动时间（越久越像"早就稳了"）。
输出：`outputs/framework-legacy/223件分组.md` + `state/framework-legacy-groups.json`

用法：py -3.14 tools/codex-scripts/legacy-grouping.py
"""
import json
import os
import re
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "state", "framework-passports-legacy.json")
OUT_MD = os.path.join(ROOT, "outputs", "framework-legacy", "223件分组.md")
OUT_JSON = os.path.join(ROOT, "state", "framework-legacy-groups.json")
SKIP = {".git", "node_modules", "__pycache__", ".venv", "site-packages", "store", ".scratch",
        "_upstream", "dist", "build", ".pylibs"}


def build_reference_index():
    """一遍扫仓，记下"哪些文件名字在别处被提到"（粗索引，只用于打标，不判语义）。"""
    idx = {}
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            p = os.path.join(dp, f)
            if os.path.splitext(f)[1].lower() not in (".py", ".js", ".mjs", ".ts", ".html", ".md", ".json", ".yml", ".yaml", ".toml"):
                continue
            if os.path.getsize(p) > 2_000_000:
                continue
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for m in re.finditer(r"[A-Za-z0-9_\-\.]{4,80}\.(?:py|js|mjs|ts|html|json|md|yml|toml|j2|css)", txt):
                idx.setdefault(m.group(0), set()).add(os.path.relpath(p, ROOT))
    return idx


def main():
    if not os.path.isfile(SRC):
        print("遗留清单不在：%s" % SRC)
        return 2
    items = json.load(open(SRC, encoding="utf-8")).get("items") or []
    idx = build_reference_index()

    groups = {}
    for it in items:
        p = str(it.get("file") or "").replace("/", os.sep)
        top = p.split(os.sep)[0] if os.sep in p else "(根)"
        full = os.path.join(ROOT, p)
        exists = os.path.isfile(full)
        base = os.path.basename(p)
        refs = sorted(idx.get(base, set()) - {p})
        row = {
            "file": str(it.get("file")),
            "kind": it.get("kind"),
            "exists": exists,
            "refs": len(refs),
            "ref_by": refs[:4],
            "mtime": None,
        }
        if exists:
            try:
                row["mtime"] = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(full)))
            except OSError:
                pass
        groups.setdefault(top, []).append(row)

    summary = {k: {"count": len(v),
                   "missing": sum(1 for x in v if not x["exists"]),
                   "referenced": sum(1 for x in v if x["refs"] > 0)} for k, v in groups.items()}
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "total": len(items),
           "by_top": summary, "groups": groups}
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT_JSON)

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# F22 · 223 件历史遗留：按模块分组（供圈选）", "",
             "> 生成：`py -3.14 tools/codex-scripts/legacy-grouping.py` · %s" % out["at"],
             "> 口径：**这批不留理由、也不补理由**（明示遗留）；本表只给三个信号帮你圈：还在不在盘上 · 有没有别的文件引用它 · 最后改动日期。",
             "> 处置建议：**被引用且还在** 的留（说明还在役）· **已缺** 的可以标「已不存在」· **无引用且久未动** 的标 `accepted-legacy`（认账，不补理由）。",
             "", "## 汇总（按顶层目录）", "",
             "| 顶层 | 件数 | 已缺 | 被引用 |", "|---|---|---|---|"]
    for k, v in sorted(summary.items(), key=lambda kv: -kv[1]["count"]):
        lines.append("| `%s` | %d | %d | %d |" % (k, v["count"], v["missing"], v["referenced"]))
    for k, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        lines += ["", "## `%s`（%d 件）" % (k, len(rows)), "",
                  "| 文件 | 类型 | 在盘 | 被引用 | 最后改动 |", "|---|---|---|---|---|"]
        for r in rows:
            lines.append("| `%s` | %s | %s | %d | %s |"
                         % (r["file"], r["kind"] or "-", "✅" if r["exists"] else "❌缺",
                            r["refs"], r["mtime"] or "-"))
    tmp_md = OUT_MD + ".tmp"
    with open(tmp_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp_md, OUT_MD)

    print("遗留 %d 件 · 分组 %d 个" % (len(items), len(groups)))
    for k, v in sorted(summary.items(), key=lambda kv: -kv[1]["count"]):
        print("  %-24s %3d 件（缺 %d · 被引用 %d）" % (k, v["count"], v["missing"], v["referenced"]))
    print("  人读：%s" % OUT_MD)
    print("  机读：%s" % OUT_JSON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
