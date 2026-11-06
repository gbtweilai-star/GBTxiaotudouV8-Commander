# -*- coding: utf-8 -*-
"""offense_ops 原生挖洞链的判据（2026-11-06）。

主人令：「把 AI 挖漏洞以及触手大军协作排查挖洞的所有专业能力，必须以原生能力优先来执行」。
本文件只咬四件事：
  ① 知识包齐（六段工序 + CWE 表 + 原生路由）
  ② **候选 != 已证**（No exploit, no report）
  ③ **读不到 != 干净**（触手失败必须进 unread，覆盖不许报闭合）
  ④ 真跑一次能出报告，且报告能读回
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone import offense_ops as oo  # noqa: E402
from gbt_allinone.tools import code_audit as ca  # noqa: E402
from gbt_allinone.tools import llm_redteam as lr  # noqa: E402

FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ok   " if cond else "  FAIL ") + name + ((" — " + detail) if detail else ""))
    if not cond:
        FAILED.append(name)


def main() -> int:
    print("[1] 知识包")
    k = oo.knowledge()
    check("六段工序齐", len(k["phases"]) == 6, "%d 段" % len(k["phases"]))
    check("CWE 表里有命令注入", "CWE-78" in k["cwe_map"])
    check("原生路由指向 offense_ops", any("offense_ops" in str(x.get("走"))
                                         for x in k["native_route"]))
    check("LLM 面实测指向 selfcheck", any("llm_redteam op=selfcheck" in str(x.get("走"))
                                        for x in k["native_route"]),
          str(k["native_route"]))
    sec = lr._probe_secret_in_prompt()
    check("用户名/占位串不算密钥", sec.get("count") == 0
          and sec.get("skipped_placeholders", 0) >= 3, str(sec))

    print("[2] 候选 != 已证")
    lanes = [
        {"id": "owasp", "rows": [{"file": "a.py", "line": 10, "cwe": "CWE-78",
                                  "severity": "critical", "title": "命令注入",
                                  "fix": "", "lane": "owasp", "kind": "finding"}]},
        {"id": "flow", "rows": [{"file": "b.py", "line": 20, "cwe": "injection",
                                 "severity": "high", "title": "source->sink 候选",
                                 "fix": "", "lane": "flow", "kind": "candidate"}]},
    ]
    confirmed, cands, by = oo._merge(lanes)
    check("已证只收 finding", len(confirmed) == 1 and confirmed[0]["file"] == "a.py")
    check("候选单独一栏", len(cands) == 1 and cands[0]["file"] == "b.py")
    check("严重度统计只算已证", by.get("critical") == 1 and "high" not in by, str(by))

    print("[3] 读不到 != 干净")
    bad = [{"id": "sast", "ok": False, "error": "TimeoutError", "rows": [], "coverage": None}]
    cov = oo._coverage(bad)
    check("失败触手进 unread", len(cov["unread"]) == 1 and cov["unread"][0]["lane"] == "sast")
    check("覆盖不闭合", cov["coverage_complete"] is False)
    okc = oo._coverage([{"id": "sast", "ok": True, "rows": [],
                         "coverage": {"rate": 0.98, "missed": 2, "scanned": 100}}])
    check("率不足也算不闭合", okc["coverage_complete"] is False, str(okc["unread"]))
    part = oo._coverage([{"id": "flow", "ok": True, "rows": [], "coverage": None,
                          "files_fed": 200, "files_eligible": 3148,
                          "files_too_large": 2}])
    check("抽样也算不闭合", part["coverage_complete"] is False, str(part["unread"]))
    check("抽样也记账", part["files_scanned"] == 200, str(part["files_scanned"]))
    tr = oo._coverage([{"id": "owasp", "ok": True, "rows": [], "coverage": None,
                        "truncated": True, "shown": 20, "total": 53}])
    check("报告截断也算不闭合", tr["coverage_complete"] is False
          and tr["unread"][0].get("missed") == 33, str(tr["unread"]))
    owasp = [s for s in oo.LANES if s["id"] == "owasp"][0]
    check("owasp 拉满 500", owasp["params"].get("limit") == 500, str(owasp["params"]))
    n_all, ex_all = ca._eligible(["."])
    check("默认排除 pyembed 第三方运行时", "pyembed" in ex_all, str(n_all))
    n_py, _ = ca._eligible(["pyembed"])
    check("显式 target 仍可扫 pyembed", n_py > 0, str(n_py))

    print("[4] 真跑一条快触手")
    d = oo.run("hunt", lanes=["llm"])
    check("跑通", bool(d.get("ok")), str(d.get("reason") or ""))
    check("有独立回执", len(d.get("lanes") or []) == 1)
    p = Path(d.get("path") or "")
    check("报告落盘", p.is_file(), str(p))
    if p.is_file():
        back = json.loads(io.open(p, encoding="utf-8").read())
        check("报告可读回", back.get("op") == "hunt" and "coverage" in back)
    check("候选与已证分栏", "candidates" in d and "findings" in d)

    print("[5] 不认的触手要拒得清楚")
    u = oo.run("hunt", lanes=["nope"])
    check("unknown_lane", u.get("ok") is False and u.get("reason") == "unknown_lane",
          str(u.get("reason")))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 知识包/候选与已证分离/覆盖诚实/真跑落盘/拒得清楚")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())