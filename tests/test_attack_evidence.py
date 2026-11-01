"""test_attack_evidence.py · 没证据不许说被攻击

判据：
  1. 无任何证据 → admit 拒绝，explain 明说"未发现被攻击证据"；
  2. 主人陈述（user_report）→ 允许进入攻击模式，但证据等级=user_report；
  3. 强证据（auth_denied_burst/port_scan/file_tamper/intrusion_alert）→ 允许，等级=strong；
  4. 攻击记录带 evidence_level/evidence_count/evidence_ids（sha256）；
  5. explain() 给出证据清单/结论/规则；
  6. respond() 无证据时不进入攻击模式，返回"未发现被攻击证据"的交代。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone import attack_evidence as AE  # noqa: E402
from gbt_allinone import security_policy as SP  # noqa: E402
from gbt_allinone import attack_forensics as AF  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)


def reset():
    for f in (SP.STATE, AE.EVIDENCE, SP.AUDIT):
        try:
            Path(f).unlink()
        except Exception:
            pass


def main() -> int:
    reset()
    print("[1] 无证据：拒绝进入攻击模式")
    adm = AE.admission()
    check("无证据不放行", adm.get("admitted") is False, adm)
    check("明说未发现证据", adm.get("reason") == "未发现被攻击证据")
    check("有解释文案", "不能进入攻击模式" in (adm.get("explain") or ""))
    r = SP.enter_attack_mode("感觉被攻击", "")
    check("enter_attack_mode 被拒", r.get("ok") is False and r.get("not_admitted") is True, r)
    check("拒绝也写审计", '"attack_refused"' in (Path(SP.AUDIT).read_text(encoding="utf-8")
                                             if Path(SP.AUDIT).is_file() else ""))

    print("[2] 主人陈述 = 证据（等级 user_report）")
    r2 = SP.enter_attack_mode("主人说被攻击了", "主人陈述：03:30 发现异常登录",
                              user_report=True)
    check("用户陈述可进", r2.get("ok") is True, r2)
    atk = (r2.get("attack") or {})
    check("证据等级 user_report", atk.get("evidence_level") == "user_report", atk.get("evidence_level"))
    check("证据有 sha256", bool((atk.get("evidence_ids") or [None])[0]), atk.get("evidence_ids"))
    SP.exit_attack_mode("test")

    print("[3] 强证据：允许（等级 strong）")
    ev = AE.add_evidence("auth_denied_burst", "test", "60s 内 denied 50 次", strong=True)
    check("证据入库带 sha256", len(ev.get("sha256") or "") == 64, ev.get("sha256"))
    adm2 = AE.admission()
    check("强证据放行", adm2.get("admitted") is True and adm2.get("level") == "strong", adm2)
    r3 = SP.enter_attack_mode("检测到暴力破解", "")
    check("强证据可进攻击模式", r3.get("ok") is True, r3)
    check("攻击记录证据数", (r3.get("attack") or {}).get("evidence_count", 0) >= 1)
    SP.exit_attack_mode("test")

    print("[4] explain 交代")
    ex = AE.explain()
    check("有结论", ex.get("conclusion") in ("有攻击证据", "未发现被攻击证据"), ex.get("conclusion"))
    check("有规则", "没证据不许说被攻击" in (ex.get("rule") or ""))
    check("有证据清单", isinstance(ex.get("recent"), list))

    print("[5] respond 无证据 → 不进入攻击模式（清空证据后）")
    try:
        AE.EVIDENCE.unlink()
    except Exception:
        pass
    SP.exit_attack_mode("clear")
    resp = AF.respond("感觉被打", agents=4, reclaim=False, incident="TEST-EVIDENCE-NONE")
    check("respond 拒绝", resp.get("ok") is False and resp.get("not_admitted") is True, resp)
    check("结论=未发现被攻击证据", resp.get("conclusion") == "未发现被攻击证据", resp.get("conclusion"))
    check("攻击模式没被打开", SP.attack_state().get("active") is False)

    for pth in (ROOT / "outputs" / "forensics").glob("TEST-EVIDENCE*"):
        try:
            shutil.rmtree(pth, ignore_errors=True) if pth.is_dir() else pth.unlink()
        except Exception:
            pass

    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL OK —— 举证门槛：无证据拒绝/用户陈述/强证据/交代文案 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
