# -*- coding: utf-8 -*-
"""capability-runthrough -- 摆设清单：登记了但**从未真跑通**的能力位。
口径：以审计账本（门亲笔）里出现过的调用为准；无调用记录 = 摆设（不是"没接线"的猜测）。
"""
from __future__ import annotations
import json, re, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "decorations.json"

def registry_names():
    t = (ROOT / "gbt_allinone" / "caps_registry.py").read_text(encoding="utf-8")
    m = re.search(r"BENIGN_CAPS\s*=\s*\{(.*?)\n\}", t, re.S)
    names = re.findall(r'^\s{4}"([a-z0-9_]+)"\s*:\s*\{', m.group(1) if m else t, re.M)
    return sorted(set(names)), t

def audit_files():
    cands = []
    for pat in ("store/audit*.jsonl", "state/audit*.jsonl", "logs/audit*.jsonl", "state/*audit*.jsonl", "store/*audit*.jsonl"):
        cands += list(ROOT.glob(pat))
    return sorted(set(cands))

def called(files):
    hit = {}
    for f in files:
        try:
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if not ln.strip():
                    continue
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                cap = d.get("cap") or d.get("kind") or d.get("capability") or d.get("name")
                if isinstance(cap, str) and re.fullmatch(r"[a-z0-9_]+", cap):
                    hit[cap] = hit.get(cap, 0) + 1
        except Exception:
            continue
    return hit

def main():
    names, t = registry_names()
    files = audit_files()
    hit = called(files)
    dead = [n for n in names if n not in hit]
    alive = [n for n in names if n in hit]
    OUT.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                               "登记位": len(names), "真跑过": len(alive), "摆设": len(dead),
                               "账本文件": [str(f.relative_to(ROOT)) for f in files],
                               "摆设清单": dead}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("摆设口径（以审计账本为准）：登记 **%d** 位 · **真跑过 %d** · **摆设 %d**" % (len(names), len(alive), len(dead)))
    print("  账本：%s" % ([str(f.relative_to(ROOT)) for f in files] or "未读到任何审计账本 ⇒ 这一栏如实写未读到"))
    print("  摆设前 20：%s" % ", ".join(dead[:20]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
