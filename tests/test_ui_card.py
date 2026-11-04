# -*- coding: utf-8 -*-
"""ui_card（ACUI 卡片协议）契约 + 统一门 + console/APP 接线验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import ui_card as UC  # noqa: E402

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
    print("[1] 契约自检（schema/白名单/注入/TTL/动作只回事件）")
    r = UC.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 20", r["checks"] >= 20, r["checks"])
    check("白名单 kind", set(UC.KINDS) >= {"info", "selfcheck", "wake", "image",
                                           "video", "confirm", "weather"})
    check("白名单 action", set(UC.ACTION_TYPES) >= {"confirm", "dismiss", "open", "send", "link"})
    c = UC.normalize_card({"kind": "info", "title": "自检", "body": "正常",
                           "actions": [{"id": "ok", "type": "confirm", "label": "知道了"}]})
    check("合法卡归一", c["id"].startswith("uc-") and c["actions"][0]["type"] == "confirm")
    for bad in ({"kind": "evil", "title": "x"}, {"kind": "info", "title": ""},
                {"kind": "info", "title": "x", "body": "<script>x</script>"},
                {"kind": "info", "title": "x", "body": "javascript:alert(1)"},
                {"kind": "info", "title": "x", "body": "a" * 2001},
                {"kind": "info", "title": "x", "actions": [{"id": "a", "type": "exec", "label": "x"}]}):
        try:
            UC.normalize_card(bad)
            check("坏卡拒 " + str(bad.get("kind")), False, bad)
        except UC.UIError:
            check("坏卡拒 " + str(list(bad)[:2]), True)

    print("[2] 卡片板 / TTL / 动作")
    now = [1000.0]
    board = UC.CardBoard(clock=lambda: now[0])
    card = board.create({"kind": "selfcheck", "title": "自检", "ttl": 5,
                         "actions": [{"id": "ok", "type": "confirm", "label": "知道了"}]})
    check("创建入板", board.snapshot()["count"] == 1)
    ev = board.act(card["id"], "ok")
    check("动作回 ui_card_action 且 executed=false",
          ev["ok"] and ev["event"]["type"] == "ui_card_action"
          and ev["event"]["executed"] is False)
    check("未知动作拒", board.act(card["id"], "nope")["ok"] is False)
    now[0] += 10
    check("TTL 到期清", board.snapshot()["count"] == 0)

    print("[3] 统一门 / API / console / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表有 ui_card", '"ui_card": {' in reg and '"handler": "ui_card"' in reg)
    check("api 分派 ui_card", 'kind == "ui_card"' in api and "ui_card as _uc" in api)
    check("run_task 可达 ui_card", _run_task_verify())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server 有 /api/ui/cards", '"/api/ui/cards"' in srv and "ui_card" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("console 有卡片栈", 'id="ui-cards"' in idx and "ui-cards.js" in idx)
    js = (ROOT / "holo_pet_w3/console/ui-cards.js").read_text(encoding="utf-8")
    check("卡片 UI 纯文本渲染/动作回 POST",
          "textContent" in js and "/api/ui/cards" in js and "executed" not in js.split("fetch")[0][:0])
    check("卡片动作只显示回执（不在卡片层执行）",
          "已回发事件" in js and "只回事件，不执行" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 ui_card",
              (payload / "gbt_allinone/tools/ui_card.py").is_file()
              and '"ui_card": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
              and '"/api/ui/cards"' in (payload / "tools/console-server.py").read_text(encoding="utf-8"))
    check("落地文档 docs/163 存在", (ROOT / "docs/163-ui-card-acui.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— ui_card 契约（白名单/纯文本/TTL/动作只回事件）+ 统一门 + console/APP 接线全绿")
    return 0


def _run_task_verify() -> bool:
    try:
        import gbt_allinone as g
        r = g.run_task("ui_card", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
