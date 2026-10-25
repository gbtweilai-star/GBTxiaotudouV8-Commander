# -*- coding: utf-8 -*-
"""由镜像探针生成"落生产后"探针：只把目标路径从镜像2 改成生产，逻辑一字不动。"""
from __future__ import annotations
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
import difflib
import hashlib
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(_GBT_ROOT)
PAIRS = [(".scratch/block2_probe.py", ".scratch/block2_probe_postland.py"),
         (".scratch/block2_m5_probe.py", ".scratch/block2_m5_probe_postland.py")]
for src_rel, dst_rel in PAIRS:
    src = (ROOT / src_rel).read_text(encoding="utf-8")
    lines = src.split("\n")
    hits = 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("MIRROR = ") and "panel_server_mirror2.py" in ln:
            indent = ln[: len(ln) - len(ln.lstrip())]
            lines[i] = indent + 'MIRROR = ROOT / "holo_pet" / "panel_server.py"  # postland: 目标=生产'
            hits += 1
    assert hits == 1, (src_rel, hits)
    out = "\n".join(lines)
    d = [x for x in difflib.unified_diff(src.splitlines(), out.splitlines(), lineterm="", n=0) if x[:1] in "+-" and x[:3] not in ("+++", "---")]
    print(src_rel, "-> 替换行数", len(d), "| 差异:", d)
    (ROOT / dst_rel).write_text(out, encoding="utf-8", newline="")
    print("  写出", dst_rel, hashlib.sha256((ROOT / dst_rel).read_bytes()).hexdigest()[:16])
