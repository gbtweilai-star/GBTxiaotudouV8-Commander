# -*- coding: utf-8 -*-
"""context_inject 契约 + 统一门 + API + 右栏面板验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import context_inject as CI  # noqa: E402

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
    print("[1] 契约（预算/过期/去重/相关度/配额）")
    r = CI.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 15", r["checks"] >= 15, r["checks"])
    cands = [
        {"id": "m1", "source": "memory", "text": "主人喜欢语音对讲", "at": 1000},
        {"id": "u1", "source": "ui_signal", "text": "当前打开数字人页", "at": 1000},
        {"id": "old", "source": "prefetch", "text": "过期缓存", "at": 1000, "ttl": 5},
    ]
    sel = CI.select("语音对讲", cands, budget=3000, now=1006)
    check("过期丢弃", sel["dropped"]["expired"] == 1, sel["dropped"])
    check("相关置顶", sel["items"][0]["id"] == "m1", [x["id"] for x in sel["items"]])
    check("预算不超", sel["used"] <= 3000 and sel["remaining"] == 3000 - sel["used"])
    check("来源计数", sel["source_counts"].get("memory") == 1)
    dup = [{"id": "a", "source": "memory", "text": "同样", "at": 1000},
           {"id": "b", "source": "memory", "text": "同样", "at": 1000}]
    check("去重", CI.select("", dup, now=1006)["count"] == 1)
    check("budget 下限拒", _raises(lambda: CI.select("x", cands, budget=1)))
    check("budget 上限拒", _raises(lambda: CI.select("x", cands, budget=99999)))
    check("candidates 非数组拒", _raises(lambda: CI.select("x", "bad")))
    check("相关度满分", CI.relevance("语音", "语音对讲") == 1.0)
    check("相关度零", CI.relevance("完全无关", "abc") == 0.0)
    big = [{"id": str(i), "source": "memory", "text": "记忆 %d" % i, "at": 1000} for i in range(20)]
    check("来源配额", CI.select("", big, budget=6000, now=1006)["source_counts"]["memory"] <= 13)
    check("空文本丢弃", CI.select("x", [{"id": "e", "text": ""}])["dropped"]["empty"] == 1)
    check("schema 有预算", "budget_default" in CI.run("schema"))

    print("[2] 统一门 / API / UI / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 context_inject", '"context_inject": {' in reg and '"handler": "context_inject"' in reg)
    check("api 分派 context_inject", 'kind == "context_inject"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/context", '"/api/context"' in srv and "context_inject" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("右栏上下文注入面板", 'id="inject-items"' in idx and "context-panel.js" in idx)
    js = (ROOT / "holo_pet_w3/console/context-panel.js").read_text(encoding="utf-8")
    check("面板只读预览", "/api/context" in js and "lastQuery" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 context_inject",
              (payload / "gbt_allinone/tools/context_inject.py").is_file()
              and '"context_inject": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/167 存在", (ROOT / "docs/167-context-inject.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— context_inject（预算/过期/去重/相关度/来源配额）+ 统一门/API/右栏面板/APP 全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except CI.InjectError:
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("context_inject", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
