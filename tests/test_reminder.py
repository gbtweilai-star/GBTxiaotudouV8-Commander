# -*- coding: utf-8 -*-
"""reminder（提醒能力位）契约 + 写面门 + API + 面板验收。"""
from __future__ import annotations

import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import reminder as RM  # noqa: E402

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
    print("[1] 契约（创建/列出/取消/due/写面门）")
    r = RM.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 15", r["checks"] >= 15, r["checks"])
    d = pathlib.Path(tempfile.mkdtemp(prefix="gbt-rem-test-"))
    st = RM.ReminderStore(path=d / "r.json", gate_fn=lambda _x: None, clock=lambda: 1000.0)
    x = st.create({"title": "回主人", "due_at": "2026-11-03T10:00"})
    check("创建 pending", x["ok"] and x["reminder"]["status"] == "pending", x)
    check("落盘", (d / "r.json").is_file())
    check("list", st.list()["count"] == 1 and st.list()["pending"] == 1)
    due_ts = __import__("time").mktime(__import__("time").strptime("2026-11-03 10:00", "%Y-%m-%d %H:%M"))
    check("due 到点", st.due(due_ts)["count"] == 1)
    check("due 未到", st.due(due_ts - 3600)["count"] == 0)
    check("取消", st.cancel(x["reminder"]["id"])["reminder"]["status"] == "cancelled")
    check("重复取消拒", st.cancel(x["reminder"]["id"])["ok"] is False)
    y = st.create({"title": "第二个", "due_at": "2026-11-03 11:00"})
    check("完成", st.complete(y["reminder"]["id"])["reminder"]["status"] == "done")
    check("空 title 拒", _raises(lambda: st.create({"due_at": "2026-11-03T10:00"})))
    check("缺 due 拒", _raises(lambda: st.create({"title": "x"})))
    check("due 格式拒", _raises(lambda: st.create({"title": "x", "due_at": "明天"})))
    check("repeat 白名单", _raises(lambda: st.create({"title": "x", "due_at": 1, "repeat": "hourly"})))
    denied = RM.ReminderStore(path=d / "deny.json",
                              gate_fn=lambda _x: {"ok": False, "denied": True, "gate": "filesystem_write"})
    check("写面门拒", denied.create({"title": "x", "due_at": "2026-11-03T10:00"})["ok"] is False)
    check("门拒不落盘", not (d / "deny.json").exists())
    check("id 非法取消", st.cancel("bad")["ok"] is False)

    print("[2] 统一门 / API / 面板 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 reminder", '"reminder": {' in reg and '"handler": "reminder"' in reg)
    check("api 分派 reminder", 'kind == "reminder"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/reminders", '"/api/reminders"' in srv and "reminder" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("右栏提醒面板", 'id="rem-list"' in idx and "reminder-panel.js" in idx)
    js = (ROOT / "holo_pet_w3/console/reminder-panel.js").read_text(encoding="utf-8")
    check("提醒 UI 创建/取消", "/api/reminders" in js and "op: \"cancel\"" in js)
    check("提醒到点弹 ACUI 卡", "/api/ui/cards" in js and "notifyDue" in js)
    check("卡片确认回写 complete", "gbt:ui-card-action" in js and "op: \"complete\"" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 reminder",
              (payload / "gbt_allinone/tools/reminder.py").is_file()
              and '"reminder": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/170 存在", (ROOT / "docs/170-reminder.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— reminder（创建/列出/取消/due + filesystem_write 写面门）+ 统一门/API/面板/APP 全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except (RM.ReminderError, ValueError):
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("reminder", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
