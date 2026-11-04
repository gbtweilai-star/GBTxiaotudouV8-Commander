# -*- coding: utf-8 -*-
"""thought_stream（思考流/行动流）契约 + 统一门 + API + console 视图验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import thought_stream as TS  # noqa: E402

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
    print("[1] 契约（五类/坏行/过滤/脱敏）")
    r = TS.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 12", r["checks"] >= 12, r["checks"])
    rows = [
        {"at": "2026-11-02T10:00:00", "actor": "gate", "action": "run", "target": "world", "result": "ok"},
        {"at": "2026-11-02T10:00:01", "actor": "brain", "action": "plan", "detail": "先做 P0"},
        {"at": "2026-11-02T10:00:02", "actor": "gate", "action": "run", "result": "denied", "detail": "缺授权"},
        {"at": "2026-11-02T10:00:03", "kind": "result", "detail": "报告已出"},
        "bad",
    ]
    n = TS.normalize(rows, limit=80)
    check("坏行跳过", n["skipped"] == 1 and n["count"] == 4, (n["skipped"], n["count"]))
    kinds = {e["kind"] for e in n["entries"]}
    check("五类分类", {"action", "thought", "guard", "result"} <= kinds, kinds)
    check("计数", n["counts"]["action"] == 1 and n["counts"]["thought"] == 1
          and n["counts"]["guard"] == 1 and n["counts"]["result"] == 1, n["counts"])
    check("limit 截断", TS.normalize(rows, limit=2)["count"] == 2)
    check("kinds 过滤", TS.normalize(rows, kinds=["guard"])["count"] == 1)
    check("坏 rows 拒", _raises(lambda: TS.normalize("x")))
    check("limit 非法拒", _raises(lambda: TS.normalize([], limit="x")))
    red = TS.normalize([{"kind": "action", "action": "run", "detail": "api_key=sk-" + "A" * 20}])
    check("凭据脱敏", "sk-" + "A" * 20 not in str(red["entries"]))
    check("系统兜底", TS.normalize([{"foo": "bar"}])["entries"][0]["kind"] == "system")

    print("[2] 统一门 / API / console / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 thought_stream", '"thought_stream": {' in reg
          and '"handler": "thought_stream"' in reg)
    check("api 分派 thought_stream", 'kind == "thought_stream"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/stream", '"/api/stream"' in srv and "orchestration-ledger" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("console「思考流」视图", 'data-view="stream"' in idx and 'id="ts-list"' in idx
          and "thought-stream.js" in idx)
    js = (ROOT / "holo_pet_w3/console/thought-stream.js").read_text(encoding="utf-8")
    check("流 UI 只读轮询", "/api/stream" in js and "setInterval" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 thought_stream",
              (payload / "gbt_allinone/tools/thought_stream.py").is_file()
              and '"thought_stream": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/168 存在", (ROOT / "docs/168-thought-stream.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— thought_stream（五类/坏行跳过/脱敏/limit/过滤）+ 统一门/API/console/APP 全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except ValueError:
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("thought_stream", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
