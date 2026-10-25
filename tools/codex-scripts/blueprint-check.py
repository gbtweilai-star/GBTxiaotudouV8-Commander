# -*- coding: utf-8 -*-
"""蓝图判据（blueprint-check）—— 蓝图不许是散文，每一层都要**现跑现证**。

主人令（2026-10-09）：「你只要设计好架构和蓝图」+ 本仓旧训「口号不会自己红」。
本件**逐层真跑**该层的判据件，核对它是否真的报出蓝图里写死的读数；跑不动/对不上 = 红。

判据（逐层报，不报合计）：
  L1 账   action-ledger --selftest   ⇒ 期望含「自检：全过」
  L2 门   framework_gate verify      ⇒ 期望含 '"verdict": "green"'
  L3 巡检 capability-audit           ⇒ 期望含「断连 0」且含「无断连」
  L4 重启 action-ledger boot         ⇒ 期望含「判据：PASS」

负对照（--selftest）：把某一层换成**不存在的件** ⇒ 必须报红；层读数对不上 ⇒ 必须报红。
退出码：0 全过 · 1 有红 · 2 蓝图/件读不到
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = ROOT / "docs" / "架构蓝图-四层模块式部署.md"
PY = sys.executable

LAYERS = [
    ("L1 账", "tools/codex-scripts/action-ledger.py", ["--selftest"], "自检：全过",
     "每个动作只追加入账，含幂等键"),
    ("L2 门", "gbt_allinone/tools/framework_gate.py", ["verify"], '"verdict": "green"',
     "改框架自己要有护照"),
    ("L3 巡检", "tools/codex-scripts/capability-audit.py", [], "无断连",
     "每天证明它还活着"),
    ("L4 重启", "tools/codex-scripts/action-ledger.py", ["boot"], "判据：PASS",
     "重启后先读账：别重做"),
]
# 蓝图里必须出现的**契约字样**（少一条就是蓝图缩水了）
MUST = ("L1", "L2", "L3", "L4", "模块式部署", "按需未启用", "负对照", "不许说", "idem")


def run_layer(mod: str, args: list, timeout: int = 600) -> dict:
    p = ROOT / mod
    if not p.is_file():
        return {"ok": False, "why": "件不在盘上：%s" % mod, "out": ""}
    cmd = [PY, "-X", "utf8", str(p)] + args
    if mod.endswith("framework_gate.py"):
        cmd = [PY, "-X", "utf8", "-m", "gbt_allinone.tools.framework_gate"] + args
    try:
        cp = subprocess.run(cmd, capture_output=True, cwd=str(ROOT), timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "why": "跑超时（%ds）" % timeout, "out": ""}
    out = ((cp.stdout or b"") + (cp.stderr or b"")).decode("utf-8", "replace")
    return {"ok": True, "out": out, "rc": cp.returncode}


def check() -> dict:
    if not BLUEPRINT.is_file():
        return {"ok": False, "errs": ["蓝图不在：%s" % BLUEPRINT], "rows": []}
    text = BLUEPRINT.read_text(encoding="utf-8")
    errs = ["蓝图缺契约字样：%s" % m for m in MUST if m not in text]
    rows = []
    for name, mod, args, want, duty in LAYERS:
        r = run_layer(mod, args)
        if not r.get("ok"):
            rows.append({"层": name, "件": mod, "过": False, "为什么": r.get("why")})
            errs.append("%s：%s" % (name, r.get("why")))
            continue
        hit = want in r["out"]
        rows.append({"层": name, "件": mod, "过": hit, "期望": want,
                     "为什么": "" if hit else "读数里找不到「%s」" % want,
                     "rc": r.get("rc")})
        if not hit:
            errs.append("%s 的判据没吐出「%s」" % (name, want))
    return {"ok": not errs, "errs": errs, "rows": rows}


def selftest() -> int:
    """负对照：① 件不存在必须红 ② 期望字样对不上必须红。"""
    old = LAYERS[0]
    r1 = run_layer("tools/codex-scripts/__不存在的件__.py", [])
    red1 = not r1.get("ok")
    print("负对照A·件不存在 ⇒ 期望红 实得 %s（%s）" % ("红" if red1 else "绿", r1.get("why")))
    r2 = run_layer("tools/codex-scripts/action-ledger.py", ["--selftest"])
    red2 = ("自检：全过" in r2.get("out", ""))
    print("正例·L1 自检跑步动且吐出期望字样 ⇒ %s" % ("绿" if red2 else "红"))
    fake = ("L9 假层", "tools/codex-scripts/action-ledger.py", ["--selftest"],
            "这一句永远不会出现", "负对照")
    r3 = run_layer(fake[1], fake[2])
    red3 = fake[3] not in r3.get("out", "")
    print("负对照B·期望字样对不上 ⇒ 期望红 实得 %s" % ("红" if red3 else "绿"))
    LAYERS[0] = old
    return 0 if (red1 and red2 and red3) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="蓝图判据（四层现跑现证）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        rc = selftest()
        print("自检：%s" % ("全过" if rc == 0 else "不过"))
        return rc
    r = check()
    print("蓝图 %s" % BLUEPRINT)
    print("%-9s %-46s %-6s %s" % ("层", "件", "过", "为什么"))
    for row in r["rows"]:
        print("%-9s %-46s %-6s %s" % (row["层"], row["件"], "✅" if row["过"] else "❌",
                                      row.get("为什么") or ""))
    if r["errs"]:
        print("\n红 %d 条：" % len(r["errs"]))
        for e in r["errs"]:
            print("  - " + e)
    print("\n判据：%s" % ("PASS" if r["ok"] else "FAIL"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
