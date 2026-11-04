# -*- coding: utf-8 -*-
"""turn_trace（轮次追踪）契约/统一门/API/视图验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import turn_trace as TT  # noqa: E402

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
    print("[1] 契约（session+间隔归并/证据/不伪造输入）")
    r = TT.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 14", r["checks"] >= 14, r["checks"])
    rows = [{"at": "2026-11-03T10:00:00", "session": "s1", "action": "run", "target": "a", "result": "ok"},
            {"at": "2026-11-03T10:00:10", "session": "s1", "action": "run", "target": "b",
             "result": "denied", "evidence": "gate-1"},
            {"at": "2026-11-03T10:02:00", "session": "s1", "action": "run", "target": "c", "result": "ok"},
            {"at": "2026-11-03T10:02:10", "session": "s2", "action": "plan", "detail": "other"},
            {"at": "bad", "session": "s1"}]
    n = TT.normalize(rows, gap_s=45)
    check("切轮", n["count"] == 3, n["count"])
    check("同 session 合并", any(t["session"] == "s1" and t["count"] == 2 for t in n["traces"]))
    check("失败标 review", any(t["status"] == "review" for t in n["traces"]))
    check("证据计数", any(t["evidence_count"] == 1 for t in n["traces"]))
    check("无输入不伪造", all(t["input"] is None for t in n["traces"]))
    check("倒序", n["traces"][0]["start"] >= n["traces"][-1]["start"])
    check("id 形态", all(t["id"].startswith("tr-") for t in n["traces"]))
    check("limit 截断", TT.normalize(rows, gap_s=10, limit=1)["count"] == 1)
    check("空 rows", TT.normalize([])["count"] == 0)
    check("gap 下限拒", _raises(lambda: TT.normalize(rows, gap_s=1)))
    check("gap 非数字拒", _raises(lambda: TT.normalize(rows, gap_s="x")))
    check("rows 非数组拒", _raises(lambda: TT.normalize("x")))

    print("[2] 统一门 / API / 视图 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 turn_trace", '"turn_trace": {' in reg and '"handler": "turn_trace"' in reg)
    check("api 分派 turn_trace", 'kind == "turn_trace"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/turns + 真实账", '"/api/turns"' in srv and "orchestration-ledger" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("console 轮次追踪视图", 'data-view="turns"' in idx and 'id="tt-list"' in idx
          and "turn-trace.js" in idx)
    js = (ROOT / "holo_pet_w3/console/turn-trace.js").read_text(encoding="utf-8")
    check("视图只读/不伪造输入", "/api/turns" in js and "不伪造" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 turn_trace",
              (payload / "gbt_allinone/tools/turn_trace.py").is_file()
              and '"turn_trace": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/173 存在", (ROOT / "docs/173-turn-trace.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— turn_trace（session+间隔/步骤/证据/不伪造输入）+ 统一门/API/视图/APP 全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except (TT.TraceError, ValueError):
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("turn_trace", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
