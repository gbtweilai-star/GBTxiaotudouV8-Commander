# -*- coding: utf-8 -*-
"""gate-blindspot-scan -- 门盲区扫描：现读 policy 分支 + 各模块 ops，
列出「有副作用但 policy 里没挂作用域」的所有条目（不猜：只读代码）。
"""
from __future__ import annotations
import json, re
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
POL = ROOT / "gbt_allinone" / "security" / "policy.py"
REG = ROOT / "gbt_allinone" / "caps_registry.py"
OUT = ROOT / "state" / "gate-blindspots.json"
ACT = ("run", "listen", "capture", "write", "send", "deploy", "release", "apply", "start", "stop", "kill", "install")


def main():
    pol = POL.read_text(encoding="utf-8", errors="replace") if POL.is_file() else ""
    reg = REG.read_text(encoding="utf-8", errors="replace")
    names = re.findall(r'^\s{4}"([a-z0-9_]+)":\s*\{', reg, re.M)
    rows = []
    for n in names:
        mod = ROOT / "gbt_allinone" / (n + ".py")
        ops = []
        if mod.is_file():
            mt = mod.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"OPS\s*=\s*\(([^)]*)\)", mt)
            if m:
                ops = [x.strip().strip(chr(34)).strip(chr(39)) for x in m.group(1).split(",") if x.strip()]
        action_ops = [o for o in ops if o.lower() in ACT]
        in_policy = (chr(34) + n + chr(34)) in pol
        if action_ops and not in_policy:
            rows.append({"cap": n, "action_ops": action_ops, "in_policy": False,
                         "why": "有副作用 op 但 policy 里找不到这个能力位的分支 ⇒ 无作用域可挂（盲区）"})
    OUT.write_text(json.dumps({"ts": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
                                "policy_has_voice_branch": ("voice" in pol),
                                "scanned": len(names), "blindspots": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("门盲区扫描：能力位 %d 个 · **有副作用但无作用域分支 %d 个**" % (len(names), len(rows)))
    for r in rows[:12]:
        print("   盲区 %-22s ops=%s" % (r["cap"], r["action_ops"]))
    return 0 if not rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
