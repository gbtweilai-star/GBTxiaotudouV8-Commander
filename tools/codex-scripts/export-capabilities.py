# -*- coding: utf-8 -*-
"""把注册表导出成 data/capabilities.json（桥的目录快照）。

为什么需要这一步：桥的 _catalog() 读的是 data/capabilities.json 这个**快照**，
而能力位真源是 gbt_allinone/caps_registry.py。改了注册表不刷新这个文件，
桥就会说「目录里没有这位能力位」—— 实测踩过（body_* 七位）。
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from gbt_allinone.caps_registry import BENIGN_CAPS          # noqa: E402
from gbt_allinone.security import policy                    # noqa: E402

out = []
for name, meta in sorted(BENIGN_CAPS.items()):
    try:
        d = policy.evaluate(name, {})
        scopes = list(d.scopes)
        risk = d.risk
    except Exception:                                        # noqa: BLE001
        scopes, risk = [], "unknown"
    out.append({"name": name, "domain": meta.get("domain"),
                "desc": meta.get("desc"), "safe": bool(meta.get("safe")),
                "readonly": not scopes, "scopes_static": scopes, "risk": risk})

dst = os.path.join(ROOT, "data", "capabilities.json")
os.makedirs(os.path.dirname(dst), exist_ok=True)
json.dump({"count": len(out), "at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
           "capabilities": out}, open(dst, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("导出 %d 条 → %s" % (len(out), dst))
print("其中带作用域（需要过门）%d 条" % sum(1 for c in out if c["scopes_static"]))
