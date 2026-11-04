# -*- coding: utf-8 -*-
"""页面 ↔ 触手双向绑定验收：每页有根、每根有页、page_scan 读得到。"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import bind_pages as B  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:200])


def main() -> int:
    print("[1] 唯一真源 state/page-bindings.json")
    p = ROOT / "state/page-bindings.json"
    check("文件存在", p.is_file())
    d = json.loads(p.read_text(encoding="utf-8"))
    check("20 页", d.get("页数") == 20, d.get("页数"))
    check("20 页全绑好", d.get("绑好") == 20 and d.get("未绑好") == 0,
          (d.get("绑好"), d.get("未绑好")))
    rows = d.get("逐页") or []
    check("每页有落点", all(r.get("落点在盘") for r in rows))
    check("每页有正向能力位", all(r.get("正向_能力位") for r in rows))
    caps = B.registry()
    page_caps = {c for r in rows for c in (r.get("正向_能力位") or [])}
    check("能力位无未登记", page_caps <= set(caps), sorted(page_caps - set(caps))[:5])
    check("每根能力位都落页", set(caps) <= page_caps,
          sorted(set(caps) - page_caps)[:5])
    cap_rows = d.get("能力位") or []
    check("反向表 410 条", len(cap_rows) == len(caps), len(cap_rows))
    check("反向无空页", all(x.get("页面") for x in cap_rows))

    print("[2] page_scan 读同一份源")
    import gbt_allinone as G
    r = G.run_task("page_scan", {"op": "status"}, safe=True)
    inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
    check("status 20 页", inner.get("页数") == 20, inner.get("页数"))
    check("status 20 绑好", inner.get("绑好") == 20 and inner.get("未绑好") == 0,
          (inner.get("绑好"), inner.get("未绑好")))
    check("无未绑好", inner.get("未绑好") == 0, inner.get("未绑好"))
    check("文档 184", (ROOT / "docs/184-page-bindings.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— 20 页 ↔ 410 能力位双向；page_scan 无漏网")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
