"""test_lab.py · 自训靶场端到端（自有 127.0.0.1，零外部风险）

判据：
  1. 靶场能起来（healthz 200）；
  2. 只读扫描能发现 >=6 类问题（XSS/IDOR/穿越/调试泄漏/未授权管理/缺头）；
  3. 越界目标必须被拒（example.com blocked）；
  4. 每个发现都能生成报告，报告文件存在且带 sha256；
  5. 赔付只记账（0 USD 计入账本，不收钱不转账）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = str(ROOT / "pyembed" / "python.exe") if (ROOT / "pyembed" / "python.exe").is_file() else sys.executable
FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    print("[1] 跑自训靶场端到端（端口 18867）")
    r = subprocess.run([PY, "-X", "utf8", str(ROOT / "tools" / "lab" / "run_lab.py"),
                        "--port", "18867", "--json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), timeout=600)
    if r.returncode != 0:
        print("run_lab 失败 rc=%s" % r.returncode)
        print((r.stdout or "")[-800:])
        print((r.stderr or "")[-800:])
        return 1
    try:
        d = json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001
        print("输出不是 JSON：", e, (r.stdout or "")[:300])
        return 1

    check("靶场端到端 ok", d.get("ok") is True, d.get("reason"))
    check("发现 >=6 类", (d.get("found") or 0) >= 6, d.get("found"))
    check("录单 == 发现", d.get("recorded") == d.get("found"), (d.get("recorded"), d.get("found")))
    check("报告 == 录单", d.get("reports") == d.get("recorded"), (d.get("reports"), d.get("recorded")))
    check("内网允许", (d.get("gate") or {}).get("ok") is True, d.get("gate"))
    check("外部目标被拒", d.get("out_of_scope_blocked") is True)

    print("[2] 报告文件与证据")
    reps = d.get("reports_detail") or []
    check("报告列表非空", bool(reps), len(reps))
    ok_files = 0
    for rep in reps:
        p = pathlib.Path(rep.get("report") or "")
        if p.is_file() and rep.get("sha256"):
            txt = p.read_text(encoding="utf-8", errors="replace")
            if "证据" in txt and "本署名不可删除" in txt:
                ok_files += 1
    check("报告都带 sha256+签名", ok_files == len(reps), (ok_files, len(reps)))

    print("[3] 赔付只记账")
    check("赔付账本存在", "payout_total" in (d.get("summary") or {}),
          (d.get("summary") or {}).get("payout_total"))

    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL OK —— 自有靶场：扫描→录单→报告→账本 全链路")
    return 0


if __name__ == "__main__":
    sys.exit(main())
