# -*- coding: utf-8 -*-
"""把注册表导出成 data/capabilities.json（桥的目录快照）。

为什么需要这一步：桥的 _catalog() 读的是 data/capabilities.json 这个**快照**，
而能力位真源是 gbt_allinone/caps_registry.py。改了注册表不刷新这个文件，
桥就会说「目录里没有这位能力位」—— 实测踩过（body_* 七位）。
"""
from __future__ import annotations
import json, os, sys

# 编码守门（2026-10-24 补 · encoding-guard-check 报的「新增违规」之一）：
# 不带 -X utf8 调用时中文不静默变空。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from gbt_allinone.caps_registry import all_caps             # noqa: E402
from gbt_allinone.security import policy                    # noqa: E402

# 🔴 2026-11-04 修：原先直接遍历 BENIGN_CAPS，而 BENIGN_CAPS 的 meta 只有
#   desc/domain/handler/safe 四个键 —— `requires_params` 是 `all_caps()` 从
#   PARAM_REQUIRED 派生出来的，绕过它导出 ⇒ data/capabilities.json 里这些位
#   的 requires_params 恒为缺失。后果：任何拿快照判断「这位要不要参数」的人
#   （多域监控、审计脚本）都会把 browser / tentacle / wf_run 这类要参数的位
#   误判成「只读不成参、本该被测却没测」。改走 all_caps() 并显式带出契约。
out = []
for row in sorted(all_caps(), key=lambda r: r["name"]):
    name = row["name"]
    try:
        d = policy.evaluate(name, {})
        scopes = list(d.scopes)
        risk = d.risk
    except Exception:                                        # noqa: BLE001
        scopes, risk = [], "unknown"
    out.append({"name": name, "domain": row.get("domain"),
                "desc": row.get("desc"), "safe": bool(row.get("safe")),
                "requires_params": bool(row.get("requires_params")),
                "params": list(row.get("params") or []),
                "params_hint": str(row.get("params_hint") or ""),
                "readonly": not scopes, "scopes_static": scopes, "risk": risk})

dst = os.path.join(ROOT, "data", "capabilities.json")
os.makedirs(os.path.dirname(dst), exist_ok=True)
json.dump({"count": len(out), "at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
           "capabilities": out}, open(dst, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("导出 %d 条 → %s" % (len(out), dst))
print("其中带作用域（需要过门）%d 条" % sum(1 for c in out if c["scopes_static"]))
