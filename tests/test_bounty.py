"""test_bounty.py · 赏金工作台合规闸（无授权不建项、范围外硬拒绝、报告证据可核）

判据（不是"文件存在就算过"）：
  1. 缺 authorization_ref 的建项必须被拒；
  2. 有授权项目里：scope 内允许、scope 外/out_of_scope 一律 blocked；
  3. 范围外的"发现"必须拒录；
  4. 范围内的发现能生成报告，报告里每个证据带 sha256，且与证据文件真 sha256 一致；
  5. 赔付只记账（账本条目），本模块不收钱不转账。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)


def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main() -> int:
    print("[0] 清空测试态账本（只清测试专用 store 文件）")
    store = ROOT / "state" / "bounty"
    from gbt_allinone import bounty as B

    # 独立程序名，避免污染真实工作台
    name = "selftest-lab"
    progs = B._read_json(B.PROGRAMS, [])
    progs = [p for p in progs if p.get("name") != name]
    B.PROGRAMS.write_text(json.dumps(progs, ensure_ascii=False, indent=1), encoding="utf-8")

    print("[1] 无授权建项必须拒")
    r = B.add_program(name, ["lab.local"])
    check("缺 authorization_ref 被拒", r.get("ok") is False, r.get("reason"))

    print("[2] 有授权：范围内允许、范围外拒绝")
    r = B.add_program(name, ["lab.local", "192.168.50.10"], out_of_scope=["admin.lab.local"],
                      authorization_ref="selftest · 自有靶场授权（owner）")
    pid = (r.get("program") or {}).get("id")
    check("建项 ok", r.get("ok") is True and bool(pid), pid)
    check("子域在范围内", B.check(pid, "api.lab.local").get("ok") is True)
    check("IP 在范围内", B.check(pid, "192.168.50.10").get("ok") is True)
    check("外部域被拒", B.check(pid, "evil.example.com").get("blocked") is True)
    check("out_of_scope 被拒", B.check(pid, "admin.lab.local").get("blocked") is True)

    print("[3] 范围外发现拒录")
    bad = B.add_finding(pid, "越界发现", "high", "evil.example.com")
    check("越界发现被拒", bad.get("ok") is False and bad.get("blocked") is True, bad.get("reason"))

    print("[4] 范围内发现 + 报告 + 证据 sha256")
    ev = ROOT / "state" / "bounty" / "selftest-evidence.txt"
    ev.parent.mkdir(parents=True, exist_ok=True)
    ev.write_text("selftest evidence: read-only probe from own lab\n", encoding="utf-8")
    fr = B.add_finding(pid, "selftest 示例发现", "medium", "api.lab.local",
                       cwe="CWE-000", cvss="0.0", steps="只读探测", impact="演示",
                       remediation="演示", evidence=[str(ev)])
    fid = (fr.get("finding") or {}).get("id")
    check("范围内发现 ok", fr.get("ok") is True and bool(fid), fid)
    rep = B.report(fid)
    rp = pathlib.Path(rep.get("report", ""))
    check("报告生成", rep.get("ok") is True and rp.is_file(), rep.get("report"))
    txt = rp.read_text(encoding="utf-8") if rp.is_file() else ""
    check("报告含证据 sha256", sha(ev) in txt, sha(ev)[:12])
    check("报告含授权依据", "selftest · 自有靶场授权" in txt)
    check("报告签名", "本署名不可删除" in txt)

    print("[5] 赔付只记账")
    po = B.payout(pid, fid, 0, "USD", note="selftest")
    check("payout ok", po.get("ok") is True)
    check("payout 明说只记账", "仅账本" in str(po.get("notice")))
    sm = B.summary()
    check("summary 有发现", sm.get("findings", 0) >= 1, sm.get("findings"))

    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL OK —— 授权闸/范围闸/发现/报告/赔付 全链路")
    return 0


if __name__ == "__main__":
    sys.exit(main())
