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

    print("[4b] 报告升级：CVSS 3.1 / CWE / 复现命令 / 状态机")
    from gbt_allinone import bounty_core as core
    for vec, want in (("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
                      ("AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 8.8),
                      ("AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1),
                      ("AV:N/AC:H/PR:N/UI:R/S:U/C:N/I:N/A:N", 0.0)):
        got = core.cvss3("CVSS:3.1/" + vec)
        check("CVSS " + vec[:18], got.get("base_score") == want, (got.get("base_score"), want))
    check("CWE-79 映射", core.cwe_info("CWE-79").get("name") == "跨站脚本（XSS）")
    md = pathlib.Path(rep["report"]).read_text(encoding="utf-8")
    for sec in ("CVSS", "CWE", "复现命令", "修复建议", "sha256", "提交建议"):
        check("报告含 " + sec, sec in md)
    check("报告侧车 JSON", pathlib.Path(rep.get("json", "")).is_file())
    bad = B.set_status(fid, "paid")
    check("draft→paid 非法", bad.get("ok") is False, bad.get("reason"))
    check("提交 → submitted", B.submit(fid, "HackerOne").get("to") == "submitted")
    check("→ triaged", B.set_status(fid, "triaged").get("to") == "triaged")
    check("→ paid", B.set_status(fid, "paid").get("to") == "paid")
    check("summary 有状态计数", "paid" in (B.summary().get("by_status") or {}))

    print("[4c] 时间分/环境分 + 修复 diff + 附件 + 可提交包")
    tvec = ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H/E:P/RL:O/RC:C")
    tc = core.cvss3(tvec)
    check("Temporal 8.8（9.8×0.94×0.95）", tc.get("temporal_score") == 8.8, tc)
    evec = ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H/CR:H/IR:H/AR:H")
    ec = core.cvss3(evec)
    check("Environmental 算得出", isinstance(ec.get("env_score"), float)
          and 0 <= ec["env_score"] <= 10, ec)

    ev2 = ROOT / "state" / "bounty" / "selftest-attach.png"
    try:
        from PIL import Image
        Image.new("RGB", (64, 40), (30, 40, 60)).save(ev2)
    except Exception:  # noqa: BLE001
        ev2.write_bytes(b"\x89PNG\r\n")
    f2 = B.add_finding(pid, "带 diff 与附件的发现", "high", "api.lab.local",
                       cwe="CWE-89", cvss="", steps="只读探测", impact="演示",
                       remediation="参数化查询", evidence=[str(ev)],
                       vector=tvec, fix_diff="--- a/app.py\n+++ b/app.py\n- q = \"...\" + user\n+ q = \"SELECT ... WHERE id=?\"; exec(q,(user,))",
                       attachments=[str(ev2)])
    fid2 = (f2.get("finding") or {}).get("id")
    check("带向量发现 ok", f2.get("ok") is True and bool(fid2), fid2)
    rep2 = B.report(fid2)
    md2 = pathlib.Path(rep2["report"]).read_text(encoding="utf-8")
    for sec in ("CVSS Temporal", "CVSS Environmental", "修复 Diff", "附件"):
        check("报告含 " + sec, sec in md2)
    bd = B.bundle(fid2)
    check("提交包目录", bd.get("ok") is True and pathlib.Path(bd.get("dir", "")).is_dir(), bd.get("dir"))
    check("提交包 ZIP", pathlib.Path(bd.get("zip", "")).is_file(), bd.get("zip"))
    mf = pathlib.Path(bd.get("manifest", ""))
    check("manifest 有 sha256", mf.is_file() and '"sha256"' in mf.read_text(encoding="utf-8"))

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
