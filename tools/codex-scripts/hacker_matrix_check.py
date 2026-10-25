# -*- coding: utf-8 -*-
"""靶标矩阵判据（hacker_matrix_check）—— 每一类靶标**必须被 V8 自己的扫描器咬到**。

主人令（2026-10-09）：「把 hacker-mirror 房间做扎实：靶标矩阵从 1 个扩成一组（注入/弱哈希/反序列化/密钥），写判据」。

口径：
  · **靶标自带声明**：每份靶标头一行「# EXPECT: 类名 | CWE」（可多行）——判据读它，不另写一份对照表；
  · **逐件报**：一份靶标一行读数（声明几类 · 咬到几类 · 漏了哪类），**不报合计**；
  · **漏一类就红**：这类漏掉 = 扫描器对这类瞎了（本仓旧训：假绿比红更坏）；
  · **负对照**：「--selftest」造一份「声明了但代码里没有」的靶标，判据**必须报红**——证明它真会响。
用法：
  py -3.14 -X utf8 tools/codex-scripts/hacker_matrix_check.py
  py -3.14 -X utf8 tools/codex-scripts/hacker_matrix_check.py --selftest
退出码：0 全中 · 1 有漏 · 2 用法/读不动
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = (ROOT / "gbt_allinone" / "store" / "mirror_space" / "rooms"
                  / "hacker-mirror-20261009" / "dimension" / "target")
EXPECT_RE = re.compile(r"^#\s*EXPECT:\s*(.+?)\s*\|\s*(CWE-\d+)\s*$", re.M)
LIMIT_RE = re.compile(r"^#\s*LIMITATION:\s*(.+)$", re.M)


def scan_matrix(matrix: Path) -> dict:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.security.security_brain import HackerBrain
    brain = HackerBrain()
    brain.project_root = matrix              # 只扫**这一格**（房间 dimension/），不扫全仓
    res = brain.scan_vulnerabilities(severity_filter="info", limit=100000,
                                     include_non_production=True)
    return {"res": res, "pattern_errors": brain.pattern_errors}


def check(matrix: Path) -> dict:
    targets = sorted(matrix.glob("*.py"))
    if not targets:
        return {"ok": False, "error": "矩阵里一份靶标都没有：%s" % matrix}
    out = scan_matrix(matrix)
    vulns = out["res"].get("vulnerabilities") or out["res"].get("vulns") or []
    byfile: dict = {}
    for v in vulns:
        loc = str(v.get("location") or "")
        rel = loc.split(":")[0].replace("\\", "/")
        byfile.setdefault(Path(rel).name, []).append(v)

    rows, missed = [], []
    for f in targets:
        text = f.read_text(encoding="utf-8", errors="replace")
        wants = EXPECT_RE.findall(text)
        # 「# LIMITATION:」= 已登记的**已知盲区**：登记在案、不参与 PASS/FAIL（盲区要看得见，不许静默）
        lims = LIMIT_RE.findall(text)
        if lims and not wants:
            rows.append({"件": f.name, "声明": 0, "咬到": 0, "漏": [],
                         "note": "已知盲区登记：%s" % lims[0][:60]})
            continue
        if not wants:
            rows.append({"件": f.name, "声明": 0, "咬到": 0, "漏": [],
                         "note": "无 EXPECT 声明（不参与判据）"})
            continue
        got = byfile.get(f.name, [])
        hit, miss = [], []
        for title, cwe in wants:
            found = any((title in str(v.get("title") or "")) or (cwe == str(v.get("cwe") or ""))
                        for v in got)
            (hit if found else miss).append("%s|%s" % (title, cwe))
        rows.append({"件": f.name, "声明": len(wants), "咬到": len(hit), "漏": miss})
        for m in miss:
            missed.append("%s 漏了 %s" % (f.name, m))
    return {"ok": not missed, "matrix": str(matrix),
            "扫描器坏模式": out["pattern_errors"],
            "逐件": rows, "漏": missed,
            "扫描器总条数": len(vulns)}


def selftest() -> int:
    """负对照：造一份「声明了但代码里没有」的靶标 —— 判据必须报红。"""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "clean.py").write_text(
            "# EXPECT: 命令注入 | CWE-78\ndef add(a, b):\n    return a + b\n", encoding="utf-8")
        r = check(d)
        red = (not r["ok"]) and bool(r["漏"])
        print("负对照[声明了但代码干净] 预期红 => %s（%s）" % ("红" if red else "绿", r["漏"]))
        (d / "clean.py").unlink()
        (d / "real.py").write_text(
            "# EXPECT: 命令注入 | CWE-78\nimport os\ndef run(u):\n    os.system('echo ' + u)\n",
            encoding="utf-8")
        r2 = check(d)
        green = bool(r2["ok"])
        print("正例[真靶标] 预期绿 => %s（咬到 %s/%s）"
              % ("绿" if green else "红", r2["逐件"][0]["咬到"], r2["逐件"][0]["声明"]))
        return 0 if (red and green) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="靶标矩阵判据")
    ap.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        rc = selftest()
        print("自检：%s" % ("全过" if rc == 0 else "不过"))
        return rc
    m = Path(a.matrix)
    if not m.is_dir():
        print("矩阵目录不在：%s" % m)
        return 2
    r = check(m)
    print("矩阵 %s" % r["matrix"])
    print("扫描器坏模式：%s" % (r.get("扫描器坏模式") or "无"))
    print("%-26s %6s %6s  %s" % ("靶标", "声明", "咬到", "漏"))
    for row in r["逐件"]:
        print("%-26s %6s %6s  %s" % (row["件"], row["声明"], row["咬到"],
                                     "、".join(row["漏"]) or ("无声明" if not row["声明"] else "—")))
    print("\n判据：%s（漏 %d 类）" % ("PASS" if r["ok"] else "FAIL", len(r["漏"])))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
