# -*- coding: utf-8 -*-
"""vision-unified-check -- 视觉必须走统一入口 vision op=see，不许散用 analyze/ocr。
允许名单：实现件本身（vision_cap / vision_unified / vision_ocr）。
"""
from __future__ import annotations
import re, sys
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
ALLOW = ("vision_cap.py", "vision_unified.py", "vision_ocr.py", "vision-unified-check.py")
BAD = [("op=analyze", re.compile(r'"op"\s*:\s*"analyze"')),
       ("op=ocr", re.compile(r'"op"\s*:\s*"ocr"')),
       ("散调 image_to_string", re.compile(r"image_to_string\("))]
SKIP = ("__pycache__", ".backups", "vendor", ".scratch")


def main():
    hits = []
    for p in list(ROOT.glob("tools/**/*.py")) + list(ROOT.glob("gbt_allinone/**/*.py")):
        s = str(p)
        if any(x in s for x in SKIP):
            continue
        if any(a in p.name for a in ALLOW):
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, ln in enumerate(lines, 1):
            if ("image" not in ln) and ("vision" not in ln.lower()):
                continue
            for name, rx in BAD:
                if rx.search(ln):
                    hits.append((str(p.relative_to(ROOT)), i, name, ln.strip()[:90]))
    if not hits:
        print("视觉统一检查：未命中（全部走 op=see 或在允许名单内）")
        return 0
    print("视觉统一检查：**散用 %d 处**（应改为 cap vision {op:see}）" % len(hits))
    for f, i, n, t in hits[:12]:
        print("   RED [%s] %s:%d  %s" % (n, f, i, t))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
