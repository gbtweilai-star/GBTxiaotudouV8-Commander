# -*- coding: utf-8 -*-
"""gap-ledger -- 未读到/未跑通总账（分两桶：待办桶 / 已如实留痕桶）。"""
from __future__ import annotations
import json, re, time
from collections import Counter
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "open-gaps.json"
SRC_GLOBS = ["docs/*.md", "state/*.json", "state/accept/*.json", "gbt_allinone/docs/*.md"]
SELF_OUT = ("wire-gate.json", "open-gaps.json", "decorations.json", "selfcheck-all.json",
            "capbinding-gaps.json", "tool-paths.json", "wire-dispositions.json", "gap-resolutions.json")
MARKERS = ["未读到", "未验", "needs_dependency", "未跑通", "缺依赖", "待接线", "TODO", "未探测", "未接"]
KEYWORDS = ["privacy_read", "process_execute", "deploy_publish", "deploy_force", "filesystem_write",
            "audio_output", "external_llm", "data_export", "device_control", "browser_control",
            "mirror_release", "one_key_deploy", "pipeline_submit"]
# 纪律性表述 = 已经把这件事写成规矩（留痕，不是欠账）

def cls(line, ctx):
    if any(k in line or k in ctx for k in KEYWORDS):
        return "owner_key"
    if any(w in line for w in ("needs_dependency", "未装", "缺件", "不在 PATH", "未配")):
        return "needs_dep"
    if any(w in line for w in ("未验", "未跑通", "未探测", "未接")):
        return "not_verified"
    return "todo"

def actionable(f, c, line):
    if c in ("owner_key", "needs_dep"):
        return True
    return False

def main():
    todo, noted = [], []
    for g in SRC_GLOBS:
        for f in sorted(ROOT.glob(g)):
            rel = str(f.relative_to(ROOT))
            if any(s in rel for s in SELF_OUT):
                continue
            if "__pycache__" in rel or ".backups" in rel:
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, ln in enumerate(lines):
                hit = next((m for m in MARKERS if m in ln), None)
                if not hit:
                    continue
                ctx = " ".join(lines[max(0, i - 1):i + 2])
                c = cls(ln, ctx)
                row = {"file": rel, "line": i + 1, "marker": hit, "class": c, "text": ln.strip()[:150]}
                if actionable(rel, c, ln):
                    todo.append(row)
                else:
                    noted.append(row)
    by = Counter(r["class"] for r in todo)
    OUT.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                               "待办桶": len(todo), "已留痕桶": len(noted),
                               "待办分类": dict(by), "items": todo, "noted": noted[:200]},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("缺口总账：**待办 %d 项** · 已如实留痕 %d 项（落 %s）" % (len(todo), len(noted), OUT.relative_to(ROOT)))
    for k, v in by.most_common():
        print("   待办 %-13s %d" % (k, v))
    for r in todo[:16]:
        print("   [%s] %s:%d  %s" % (r["class"], r["file"], r["line"], r["text"][:86]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
