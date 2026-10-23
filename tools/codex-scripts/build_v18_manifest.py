# -*- coding: utf-8 -*-
"""合并三份真相，生成 V18 数据层：
  ① caps_registry  —— 登记面（名字/域/说明/handler/safe/params）
  ② api.py 反查     —— 实现面（实现模块路径/行数/模块自述/op 表/公开函数）
  ③ 140 能力真调    —— 实测面（跑通 / 待授权 / 待参数）
并补上 4 个 api.py 内联实现的能力。
"""
import json
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

srcmap = json.loads((S / "capability_source_map.json").read_text(encoding="utf-8"))
matrix = json.loads((S / "capability_matrix.json").read_text(encoding="utf-8"))
man = json.loads((S / "v17_manifest.json").read_text(encoding="utf-8"))
api_src = (BASE / "gbt_allinone/api.py").read_text(encoding="utf-8-sig")

by_name = {m["name"]: m for m in matrix}


def classify(m):
    """把 140 能力真调结果分成三类。"""
    if m["kind"] == "ok":
        return "ok"
    note = m.get("note") or ""
    if "human authorization" in note:
        return "gated"
    return "needs_params" if m["kind"] == "needs_params" else m["kind"]


rows = []
for c in srcmap["caps"]:
    n = c["name"]
    r = by_name.get(n, {})
    # api.py 内联实现：分支体里直接 return，没有 from . import
    inline = None
    if not c["module"]:
        i = api_src.find('kind == "%s"' % n)
        if i < 0:
            i = api_src.find('"%s"' % n)
        inline = api_src[max(0, i - 60):i + 400] if i >= 0 else ""
    rows.append({
        "name": n, "domain": c["domain"], "desc": c["desc"],
        "handler": c["handler"], "safe": c["safe"],
        "route_line": c["route_line"],
        "module": c["module_path"], "module_lines": c["module_lines"],
        "module_doc": c["module_doc"], "public": c["module_public"] or [],
        "ops": c["module_ops"] or {},
        "inline": bool(inline is not None),
        "state": classify(r) if r else "untested",
        "ms": r.get("ms"), "note": (r.get("note") or "")[:150],
    })

from collections import Counter  # noqa: E402
print("能力 %d 个" % len(rows))
print("实测状态:", dict(Counter(x["state"] for x in rows)))
print("有实现模块: %d · api.py 内联: %d" % (sum(1 for x in rows if x["module"]),
                                     sum(1 for x in rows if not x["module"])))
print("模块行数合计: %s" % f"{sum((x['module_lines'] or 0) for x in rows):,}")
print("内联的:", ", ".join(x["name"] for x in rows if not x["module"]))

dom = Counter(x["domain"] for x in rows)
mods = {}
for x in rows:
    if x["module"]:
        mods.setdefault(x["module"], {"lines": x["module_lines"], "caps": []})
        mods[x["module"]]["caps"].append(x["name"])
print("去重后实现模块: %d 个" % len(mods))

man["capsrc"] = {
    "total": len(rows),
    "by_state": dict(Counter(x["state"] for x in rows)),
    "by_domain": dict(dom),
    "n_modules": len(mods),
    "modules": {k: v for k, v in sorted(mods.items(), key=lambda kv: -(kv[1]["lines"] or 0))},
    "caps": rows,
    "source": "caps_registry 登记面 + api.py 路由反查的实现面 + 140 能力真调的实测面；三份真相合并",
}
out = S / "v18_manifest.json"
out.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", out.name, "%.1f KB" % (out.stat().st_size / 1024))
