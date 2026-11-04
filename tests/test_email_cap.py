# -*- coding: utf-8 -*-
"""email_cap 审计别名：必须指向真实 coze_mail 实现，不演“0 能力”。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import gbt_allinone as G  # noqa: E402

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
    print("[1] 注册表/统一门别名")
    from gbt_allinone.caps_registry import BENIGN_CAPS
    check("email_cap 已登记", "email_cap" in BENIGN_CAPS)
    check("coze_mail 本体在", "coze_mail" in BENIGN_CAPS)
    check("handler=email_cap", BENIGN_CAPS["email_cap"].get("handler") == "email_cap")
    r = G.run_task("email_cap", {"op": "status"}, safe=True)
    inner = (r.get("gbt_result") or {}).get("result") or {}
    check("统一门可达", r.get("ok") is True)
    check("真实现 channel=coze_mail", inner.get("channel") == "coze_mail", inner)
    check("如实 needs_dependency", inner.get("status") == "needs_dependency", inner.get("status"))
    check("不伪造已连接", inner.get("connected") is False, inner.get("connected"))
    check("配额/白名单口径在", inner.get("quota_limit") == 20, inner.get("quota_limit"))

    print("[2] 接线/文档")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("api 分派别名", '("coze_mail", "email_cap")' in api)
    check("文档 183", (ROOT / "docs/183-email-cap.md").is_file())
    payload = ROOT.parent / "GBT小土豆V8桌面版" / "payload"
    if payload.is_dir():
        reg = (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
        check("APP payload 注册", '"email_cap": {' in reg)
    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— email_cap 指向真实 coze_mail；闸门/配额在；transport 未接线如实报")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
