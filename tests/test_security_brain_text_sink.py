# -*- coding: utf-8 -*-
"""sec_scan 的文本落盘豁免判据（2026-11-06）。

主人令：挖洞能力不许阉割，但也不许把「自检夹具字符串里的示例」报成 critical 命令注入。
本判据只咬两件事：
  ① 写进临时 .py 的代码示例**不是**被执行代码，不报 CWE-78；
  ② 同一份临时工程里，真正写在函数体里的 `os.system(...)` **仍然**要报 CWE-78（正控）。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone.security.security_brain import HackerBrain  # noqa: E402

FAILED: list = []

FIXTURE_SRC = """from pathlib import Path
def make(p):
    (p / "real.py").write_text("# EXPECT: 命令注入 | CWE-78\\nimport os\\ndef run(u):\\n    os.system('echo ' + u)\\n", encoding="utf-8")
"""

REAL_SRC = """import os
def run(u):
    os.system('echo ' + u)
"""


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ok   " if cond else "  FAIL ") + name + ((" — " + detail) if detail else ""))
    if not cond:
        FAILED.append(name)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "fixture.py").write_text(FIXTURE_SRC, encoding="utf-8")
        (d / "real.py").write_text(REAL_SRC, encoding="utf-8")
        hb = HackerBrain()
        hb.project_root = d
        r = hb.scan_vulnerabilities(severity_filter="info",
                                   include_non_production=True, limit=50)
        vulns = r.get("vulnerabilities") or []
        c78 = [v for v in vulns if "CWE-78" in str(v.get("cwe"))]
        fixture_hits = [v for v in c78 if "fixture.py" in str(v.get("location"))]
        real_hits = [v for v in c78 if "real.py" in str(v.get("location"))]
        check("夹具字符串不报命令注入", not fixture_hits, str(fixture_hits))
        check("真实调用仍报命令注入（正控）", bool(real_hits), str(c78))
        check("只有真实调用是 critical",
              bool([v for v in c78 if v.get("severity") == "critical"])
              and all("real.py" in str(v.get("location"))
                      for v in c78 if v.get("severity") == "critical"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 夹具不误报 / 真实调用仍咬住")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
