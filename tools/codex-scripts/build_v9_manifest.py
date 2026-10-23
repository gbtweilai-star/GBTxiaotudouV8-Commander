# -*- coding: utf-8 -*-
"""V9 数据层：V8 + 插件市场蒸馏结果。"""
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

S = Path(__file__).resolve().parent
M = json.loads((S / "v8_manifest.json").read_text(encoding="utf-8"))
SCAN = json.loads((S / "plugin_market_scan.json").read_text(encoding="utf-8"))

M["market"] = {
    "scanned_at": SCAN["scanned_at"],
    "facts_from": SCAN["facts_from"],
    "local": SCAN["local"],
    "profiles": SCAN["profiles"],
    "candidates": [{"name": c["name"], "version": c["version"], "published": c["published"],
                    "maintainer": c["maintainer"], "repo": c["repo"], "license": c["license"],
                    "deps": c["deps"], "lifecycle": c["lifecycle"], "desc": c["desc"],
                    "score": c["score"], "verdict": c["verdict"], "dims": c["dims"]}
                   for c in SCAN["candidates"]],
    "dims": SCAN["dims"],
    "law": SCAN["law"],
}
(S / "v9_manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
mk = M["market"]
print("写出 v9_manifest.json · %d B" % (S / "v9_manifest.json").stat().st_size)
print("本机：%d 包 / 带清单 %d / 官方 %d" % (mk["local"]["packages"], mk["local"]["with_manifest"], mk["local"]["official"]))
print("清单类型：", mk["local"]["manifest_types"])
for c in mk["candidates"]:
    print("  %-38s %3d 分 %s" % (c["name"], c["score"], c["verdict"]))
