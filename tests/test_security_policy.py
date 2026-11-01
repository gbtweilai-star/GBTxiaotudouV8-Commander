"""test_security_policy.py · 三条最高规则

判据：
  1. 黑客全能力：AI 直接使用 → need_terminal_confirm（不放行）；
  2. 主人在终端批准一次性 token 后 → 允许一次，第二次又拦；
  3. 转账：**任何模式（含攻击模式）→ blocked_transfer**；
  4. 受攻击模式：黑客能力 → attack_self_decision（由 V8 自我决策放行），且写审计；
  5. 攻击模式有 TTL、可退出；
  6. 审计日志存在（request/approve/consume/attack 都落）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone import security_policy as SP  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)


def reset():
    try:
        SP.STATE.unlink()
    except Exception:
        pass


def main() -> int:
    reset()
    print("[1] 分类 + 默认拦截")
    check("transfer 分类", SP.classify("transfer") == "transfer")
    check("hacker 分类", SP.classify("pentest") == "hacker")
    check("guard 不算 hacker", SP.classify("selfscan") == "normal")
    check("黑客默认需终端确认", SP.check("pentest")["decision"] == "need_terminal_confirm")
    check("转账默认硬拦", SP.check("transfer")["decision"] == "blocked_transfer")

    print("[2] 终端确认一次性放行")
    req = SP.request_confirm("pentest", "授权范围内渗透测试")
    tok = req.get("token")
    check("申请给 token", bool(tok), req.get("terminal_command"))
    check("未批准仍拦", SP.check("pentest")["decision"] == "need_terminal_confirm")
    ap = SP.approve(tok)
    check("终端批准", ap.get("ok") is True, ap)
    d1 = SP.check("pentest")
    check("批准后放行一次", d1["decision"] == "allow", d1)
    d2 = SP.check("pentest")
    check("一次性：第二次又拦", d2["decision"] == "need_terminal_confirm", d2)
    check("批准其它位无效", SP.check("sec_scan")["decision"] == "need_terminal_confirm")

    print("[3] 攻击模式：V8 自我决策（转账仍拦）")
    on = SP.enter_attack_mode("检测到端口扫描攻击", evidence="edge log: 500 conn/s")
    check("进入攻击模式", on.get("ok") is True)
    check("黑客能力自我决策", SP.check("pentest")["decision"] == "attack_self_decision")
    check("攻击模式转账仍拦", SP.check("transfer")["decision"] == "blocked_transfer")
    off = SP.exit_attack_mode("攻击停止")
    check("退出攻击模式", off.get("ok") is True)
    check("退出后黑客又需确认", SP.check("pentest")["decision"] == "need_terminal_confirm")

    print("[4] TTL 到期")
    SP.enter_attack_mode("短 TTL", ttl=1)
    import time
    time.sleep(1.2)
    check("TTL 到期自动失效", SP.attack_state().get("active") is False)
    check("到期后黑客需确认", SP.check("pentest")["decision"] == "need_terminal_confirm")

    print("[5] 审计")
    txt = SP.AUDIT.read_text(encoding="utf-8", errors="replace") if SP.AUDIT.is_file() else ""
    for ev in ("request", "approve", "consume", "attack_on", "attack_off", "allow_attack"):
        check("审计含 " + ev, ('"' + ev + '"') in txt)

    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL OK —— 终端确认/攻击模式自我决策/转账硬拦/审计 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
