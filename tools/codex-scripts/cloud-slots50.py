# -*- coding: utf-8 -*-
"""把 50 槽规格编译成 Worker 内数据模块（deploy/cloud-10/src/slots.generated.js）。

为什么单独一件：Worker 是隔离环境，**读不到仓里的 JSON** ⇒ 槽位表必须编成源码随包发布。
本件只做「表 → 模块」的搬运，不改表（表是单一真源 `deploy/cloud-10/plugins50.json`）。

用法：py -3.14 tools/codex-scripts/cloud-slots50.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "deploy" / "cloud-10" / "plugins50.json"
OUT = ROOT / "deploy" / "cloud-10" / "src" / "slots.generated.js"


def main() -> int:
    data = json.loads(SPEC.read_text(encoding="utf-8"))
    mods = data.get("modules") or []
    rows = []
    for m in mods:
        rows.append({
            "seq": m["seq"], "slot": m["slot"], "group": m.get("group"),
            "role": m.get("role", ""), "driver": m.get("local_driver", ""),
            "email": (m.get("email") or {}).get("value", ""),
            "wired": bool(m.get("local_driver")),
        })
    body = (
        "// 本文件由 tools/codex-scripts/cloud-slots50.py 生成 —— 不要手改。\n"
        "// 单一真源：deploy/cloud-10/plugins50.json（改表再 gen；本件只搬运不重算）\n"
        "// 开发者：自由的风 · 守护者：公主土豆\n"
        "export const SLOTS50 = " + json.dumps(rows, ensure_ascii=False, indent=1) + ";\n\n"
        "export const EMAIL_PLANE = " + json.dumps(data.get("email_plane") or {}, ensure_ascii=False, indent=1) + ";\n\n"
        "export const SLOT_EDGES = { directed: %d, undirected: %d, self_loop: 0 };\n"
        % (len(rows) * (len(rows) - 1), len(rows) * (len(rows) - 1) // 2)
    )
    OUT.write_text(body, encoding="utf-8")
    wired = sum(1 for r in rows if r["wired"])
    print("已写 %s（槽 %d · 已接线 %d · 未接线 %d · 有向边 %d）"
          % (OUT, len(rows), wired, len(rows) - wired, len(rows) * (len(rows) - 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
