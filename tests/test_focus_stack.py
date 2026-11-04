# -*- coding: utf-8 -*-
"""焦点栈 + 记忆审计（focus_stack）契约/统一门/console 面板/APP 接线。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import focus_stack as FS  # noqa: E402

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
    print("[1] 契约（焦点栈）")
    r = FS.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 15", r["checks"] >= 15, r["checks"])
    now = [1000.0]
    st = FS.FocusStack(clock=lambda: now[0])
    st.push({"id": "a", "title": "做 A", "score": 60})
    st.push({"id": "b", "title": "做 B", "score": 80})
    check("top 取最高分", st.top()["id"] == "b")
    check("排序", [x["id"] for x in st.snapshot()["items"]] == ["b", "a"])
    r = st.push({"id": "a", "title": "做 A", "score": 70})
    check("同 id 提分不重复", r.get("bumped") is True and st.snapshot()["count"] == 2)
    check("pop 指定", st.pop("a")["item"]["id"] == "a")
    check("score 越界拒", _raises(lambda: st.push({"id": "x", "title": "x", "score": 101})))
    check("title 必填", _raises(lambda: st.push({"id": "x", "title": ""})))

    print("[2] 记忆审计（只读体检）")
    audit = FS.audit_records([
        {"id": "m1", "text": "主人喜欢短句", "at": "2026-11-02"},
        {"id": "m1", "text": "x", "at": ""},
        {"id": "m2", "text": "api_key=sk-" + "A" * 20, "at": "2026-11-02"},
    ])
    check("审计需复核", audit["verdict"] == "needs_review", audit["verdict"])
    check("重复 id 计数", audit["totals"]["duplicate_ids"] == 1)
    check("secret_like 识别", audit["totals"]["secret_like"] == 1)
    check("不回显凭据原文", "sk-" + "A" * 20 not in str(audit["issues"]))
    clean = FS.audit_records([{"id": "m3", "text": "正常记忆", "at": "2026-11-02"}])
    check("干净记录", clean["verdict"] == "clean")
    check("非数组拒", FS.audit_records("x")["ok"] is False)

    print("[3] 统一门 / API / UI / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 focus_stack", '"focus_stack": {' in reg and '"handler": "focus_stack"' in reg)
    check("api 分派 focus_stack", 'kind == "focus_stack"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/focus + 审计源", '"/api/focus"' in srv and "memory_bank.jsonl" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("右栏焦点面板", 'id="focus-list"' in idx and "focus-panel.js" in idx)
    js = (ROOT / "holo_pet_w3/console/focus-panel.js").read_text(encoding="utf-8")
    check("焦点 UI 只读/pop 回 POST", "/api/focus" in js and "op: \"pop\"" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 focus_stack",
              (payload / "gbt_allinone/tools/focus_stack.py").is_file()
              and '"focus_stack": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/165 存在", (ROOT / "docs/165-focus-stack-memory-audit.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— 焦点栈（上限/提分/排序/pop）+ 记忆审计（重复/缺时/secret_like）+ 统一门/UI/APP 接线全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except FS.FocusError:
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("focus_stack", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
