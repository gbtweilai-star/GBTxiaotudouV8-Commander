# -*- coding: utf-8 -*-
"""V10 数据层：V9 + 真实项目树。"""
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

S = Path(__file__).resolve().parent
M = json.loads((S / "v9_manifest.json").read_text(encoding="utf-8"))
TR = json.loads((S / "project_tree.json").read_text(encoding="utf-8"))
M["tree"] = TR
(S / "v10_manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
t = TR["tree"]
print("写出 v10_manifest.json · %d B" % (S / "v10_manifest.json").stat().st_size)
print("树根 %s · 根层 %d/%d 项 · 截断 %s · 预展开 %s" % (
    t["path"], len(t["entries"]), t["count"], t["truncated"], ",".join(TR["preexpanded"])))
kinds = {}


def walk(es):
    for e in es:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        if e.get("entries"):
            walk(e["entries"])


walk(t["entries"])
print("树内条目类型分布：", kinds)
