"""GBT小土豆V8 · 自训靶场端到端跑通（零外部风险）

流程：起靶场(127.0.0.1) → 只读扫描 → 授权/范围闸 → 录发现 + 证据 → 生成报告 → 赔付账本 → 关靶场

用法：
    python tools/lab/run-lab.py            # 默认端口 18866
    python tools/lab/run-lab.py --port 18877 --json

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "lab"))

from gbt_allinone import bounty as B  # noqa: E402
import lab_scan  # noqa: E402


def wait_up(base: str, timeout: float = 15.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(base + "/healthz", timeout=1.5).read()
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    return False


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18866)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv[1:])

    lab_root = Path(tempfile.mkdtemp(prefix="gbt-lab-"))
    py = str(ROOT / "pyembed" / "python.exe") if (ROOT / "pyembed" / "python.exe").is_file() else sys.executable
    proc = subprocess.Popen([py, "-X", "utf8", str(ROOT / "tools" / "lab" / "vuln_lab.py"),
                             str(a.port), str(lab_root)],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    base = "http://127.0.0.1:%d" % a.port
    out = {"ok": False, "port": a.port}
    try:
        if not wait_up(base):
            out.update({"reason": "靶场没起来"})
            return 1
        findings = lab_scan.scan(base)
        out["found"] = len(findings)

        # 授权项目（自有靶场）
        progs = B.list_programs().get("programs") or []
        prog = next((p for p in progs if p.get("name") == "own-lab-selftest"), None)
        if not prog:
            r = B.add_program("own-lab-selftest", ["127.0.0.1", "localhost"],
                              authorization_ref="自有靶场（owner 授权，仅本机）",
                              platform="self", reward_range="n/a",
                              rules="只读；不测外部；不破坏")
            prog = r.get("program") or {}
        pid = prog.get("id") or "own-lab-selftest"
        gate = B.check(pid, "127.0.0.1")
        out["gate"] = {"ok": gate.get("ok"), "program": pid}
        if not gate.get("ok"):
            out.update({"reason": "范围闸拒绝：" + str(gate.get("reason"))})
            return 2

        # 越界必须被拒（自证）
        evil = B.check(pid, "example.com")
        out["out_of_scope_blocked"] = bool(evil.get("blocked"))

        evdir = ROOT / "state" / "bounty" / "lab-evidence"
        evdir.mkdir(parents=True, exist_ok=True)
        recorded, reports = [], []
        for i, f in enumerate(findings, 1):
            ev = evdir / ("finding-%02d-%s.txt" % (i, f["cwe"]))
            ev.write_text(f["title"] + "\n\n" + f.get("evidence", "") + "\n", encoding="utf-8")
            fr = B.add_finding(pid, f["title"], f["severity"], "127.0.0.1",
                               cwe=f["cwe"], cvss=f["cvss"], steps=f["steps"],
                               impact=f["impact"], remediation=f["remediation"],
                               evidence=[str(ev)])
            if fr.get("ok"):
                fid = fr["finding"]["id"]
                recorded.append({"id": fid, "title": f["title"], "severity": f["severity"]})
                rep = B.report(fid)
                if rep.get("ok"):
                    reports.append({"finding": fid, "report": rep["report"],
                                    "sha256": rep.get("sha256")})
        out.update({"recorded": len(recorded), "reports": len(reports),
                    "findings": recorded, "reports_detail": reports,
                    "summary": B.summary(), "ok": True})
        B.payout(pid, recorded[0]["id"] if recorded else "", 0, "USD", note="selftest lab")
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print("靶场: %s" % base)
            print("发现: %d | 录单: %d | 报告: %d" % (out["found"], out["recorded"], out["reports"]))
            for f in recorded:
                print("  [%s] %s → %s" % (f["severity"], f["title"], f["id"]))
            print("范围闸: 内网允许=%s · 外部拒绝=%s" % (out["gate"]["ok"], out["out_of_scope_blocked"]))
            print("赔付账本:", out["summary"].get("payout_total"))
        return 0
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()
        shutil.rmtree(lab_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
