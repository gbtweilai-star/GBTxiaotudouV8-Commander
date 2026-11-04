"""GBT小土豆V8 · 赏金工作台（合规优先的漏洞 bounty 流程）

主人 2026-11-02：「这套设计如果拿来正规挖洞赚钱呢？」——方向改成安全研究/赏金工作台。

合规红线（写死在代码里）：
  1. **没有授权记录 = 一律拒绝**：program 必须带 authorization_ref（授权书/平台项目链接/书面确认）；
  2. **scope 之外 = 硬拒绝**：域名用后缀匹配、IP/CIDR 用 ipaddress 判定，不在 scope 内直接 blocked；
  3. **本模块不做任何网络动作**：只做范围判定、证据/报告/赔付的账本；真正的扫描仍走既有安全能力位（且要过 scope 闸）；
  4. **证据可核**：报告里每个证据文件带 sha256，改过即对不上；
  5. **赔付走人**：payout 只记账，不收钱、不转账（转账是主人的事）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import fnmatch
import hashlib
import ipaddress
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "state" / "bounty"
PROGRAMS = STORE / "programs.json"
FINDINGS = STORE / "findings.jsonl"
PAYOUTS = STORE / "payouts.jsonl"
REPORTS = ROOT / "outputs" / "bounty"

SEVERITIES = ("critical", "high", "medium", "low", "info")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def _append(p: Path, row: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 程序（授权项目）────────────────────────────────────────────────────

def add_program(name: str, scope: list, out_of_scope: list | None = None,
                platform: str = "", url: str = "", authorization_ref: str = "",
                reward_range: str = "", rules: str = "") -> dict:
    if not name or not scope:
        return {"ok": False, "reason": "name 和 scope 必填"}
    if not authorization_ref:
        return {"ok": False, "reason": "缺 authorization_ref（授权书/项目链接/书面确认）—— 拒绝建项"}
    progs = _read_json(PROGRAMS, [])
    pid = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:40] or ("prog-" + str(len(progs) + 1))
    if any(p.get("id") == pid for p in progs):
        pid = pid + "-" + str(len(progs) + 1)
    row = {"id": pid, "name": name, "platform": platform, "url": url,
           "scope": [str(x).strip() for x in scope if str(x).strip()],
           "out_of_scope": [str(x).strip() for x in (out_of_scope or []) if str(x).strip()],
           "authorization_ref": authorization_ref, "reward_range": reward_range,
           "rules": rules, "created_at": _now()}
    progs.append(row)
    STORE.mkdir(parents=True, exist_ok=True)
    PROGRAMS.write_text(json.dumps(progs, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "program": row}


def list_programs() -> dict:
    progs = _read_json(PROGRAMS, [])
    return {"ok": True, "count": len(progs), "programs": progs,
            "notice": "没有 authorization_ref 的项目不会存在（建项时已拒绝）"}


# ── 范围闸 ─────────────────────────────────────────────────────────────

def _ip_in(cidr: str, target: str) -> bool:
    try:
        return ipaddress.ip_address(target) in ipaddress.ip_network(cidr, strict=False)
    except Exception:  # noqa: BLE001
        return False


def in_scope(program: dict, target: str) -> bool:
    t = str(target or "").strip().lower()
    if not t:
        return False
    for bad in program.get("out_of_scope") or []:
        b = bad.lower().lstrip("*.")
        if t == b or t.endswith("." + b) or _ip_in(bad, t) or fnmatch.fnmatch(t, bad.lower()):
            return False
    for pat in program.get("scope") or []:
        p = pat.lower()
        if p.startswith("ip:") or "/" in p:
            if _ip_in(p.replace("ip:", ""), t):
                return True
            continue
        p = p.lstrip("*.")
        if t == p or t.endswith("." + p) or fnmatch.fnmatch(t, pat.lower()):
            return True
    return False


def check(program_id: str, target: str, action: str = "read-only-recon") -> dict:
    """授权 + 范围判定。返回 ok/blocked；本函数不执行任何网络动作。"""
    progs = _read_json(PROGRAMS, [])
    prog = next((p for p in progs if p.get("id") == program_id), None)
    if not prog:
        return {"ok": False, "blocked": True, "reason": "没有这个项目"}
    if not prog.get("authorization_ref"):
        return {"ok": False, "blocked": True, "reason": "项目没有授权记录"}
    if not in_scope(prog, target):
        return {"ok": False, "blocked": True,
                "reason": "target 不在 scope 内（或命中 out_of_scope）",
                "target": target, "scope": prog.get("scope")}
    row = {"at": _now(), "program": program_id, "target": target, "action": action,
           "decision": "allowed", "authorization_ref": prog.get("authorization_ref")}
    _append(ROOT / "state" / "bounty" / "scope-checks.jsonl", row)
    return {"ok": True, "blocked": False, "program": program_id, "target": target,
            "action": action, "authorization_ref": prog.get("authorization_ref")}


# ── 发现（漏洞）与报告 ─────────────────────────────────────────────────

def add_finding(program_id: str, title: str, severity: str, target: str,
                cwe: str = "", cvss: str = "", steps: str = "",
                impact: str = "", remediation: str = "",
                evidence: list | None = None) -> dict:
    sev = str(severity).lower()
    if sev not in SEVERITIES:
        return {"ok": False, "reason": "severity 只能是 %s" % (SEVERITIES,)}
    g = check(program_id, target, action="record-finding")
    if not g.get("ok"):
        return {"ok": False, "blocked": True, "reason": g.get("reason"),
                "detail": "发现必须先过授权/范围闸，否则不允许记录"}
    fid = "F-" + time.strftime("%Y%m%d-%H%M%S") + "-" + hashlib.sha1(
        (title + target).encode()).hexdigest()[:6]
    ev = []
    for ep in (evidence or []):
        p = Path(ep)
        if p.is_file():
            ev.append({"path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                       "sha256": _sha256(p), "bytes": p.stat().st_size})
        else:
            ev.append({"path": str(ep), "sha256": None, "missing": True})
    row = {"id": fid, "at": _now(), "program": program_id, "title": title,
           "severity": sev, "target": target, "cwe": cwe, "cvss": cvss,
           "steps": steps, "impact": impact, "remediation": remediation,
           "evidence": ev, "status": "draft",
           "authorization_ref": g.get("authorization_ref")}
    _append(FINDINGS, row)
    return {"ok": True, "finding": row}


def list_findings(program_id: str = "") -> dict:
    rows = []
    if FINDINGS.is_file():
        for ln in FINDINGS.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                d = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            if program_id and d.get("program") != program_id:
                continue
            rows.append(d)
    return {"ok": True, "count": len(rows), "findings": rows}


def report(finding_id: str) -> dict:
    rows = list_findings()["findings"]
    f = next((x for x in rows if x.get("id") == finding_id), None)
    if not f:
        return {"ok": False, "reason": "没有这个 finding"}
    progs = _read_json(PROGRAMS, [])
    prog = next((p for p in progs if p.get("id") == f.get("program")), {})
    REPORTS.mkdir(parents=True, exist_ok=True)
    outp = REPORTS / (finding_id + ".md")
    ev_lines = []
    for e in f.get("evidence") or []:
        ev_lines.append("- `%s` sha256=`%s`%s" % (e.get("path"), e.get("sha256"),
                                                  "（缺失）" if e.get("missing") else ""))
    body = """# %s

- **项目**: %s (%s)
- **目标**: %s
- **严重度**: %s · CWE: %s · CVSS: %s
- **授权依据**: %s
- **发现时间**: %s

## 复现步骤
%s

## 影响
%s

## 修复建议
%s

## 证据（sha256 可核）
%s

---
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
""" % (f["title"], prog.get("name", f.get("program")), prog.get("platform", ""),
       f.get("target"), f.get("severity"), f.get("cwe") or "-", f.get("cvss") or "-",
       f.get("authorization_ref"), f.get("at"),
       f.get("steps") or "（待补）", f.get("impact") or "（待补）",
       f.get("remediation") or "（待补）", "\n".join(ev_lines) or "（无）")
    outp.write_text(body, encoding="utf-8")
    return {"ok": True, "report": str(outp), "sha256": _sha256(outp),
            "bytes": outp.stat().st_size}


def payout(program_id: str, finding_id: str, amount: float, currency: str = "USD",
           status: str = "pending", note: str = "") -> dict:
    """只记账，不收钱不转账（转账是主人的事）。"""
    row = {"at": _now(), "program": program_id, "finding": finding_id,
           "amount": amount, "currency": currency, "status": status, "note": note}
    _append(PAYOUTS, row)
    return {"ok": True, "payout": row,
            "notice": "仅账本记录；收付款/转账由主人处理"}


def summary() -> dict:
    progs = _read_json(PROGRAMS, [])
    finds = list_findings()["findings"]
    pays = []
    if PAYOUTS.is_file():
        for ln in PAYOUTS.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.strip():
                try:
                    pays.append(json.loads(ln))
                except Exception:  # noqa: BLE001
                    pass
    by_sev = {}
    for f in finds:
        by_sev[f.get("severity")] = by_sev.get(f.get("severity"), 0) + 1
    total = {}
    for p in pays:
        c = p.get("currency") or "USD"
        total[c] = round(total.get(c, 0) + float(p.get("amount") or 0), 2)
    return {"ok": True, "programs": len(progs), "findings": len(finds),
            "by_severity": by_sev, "payouts": len(pays), "payout_total": total,
            "reports_dir": str(REPORTS)}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "summary":
        print(json.dumps(summary(), ensure_ascii=False, indent=2))
    elif cmd == "programs":
        print(json.dumps(list_programs(), ensure_ascii=False, indent=2))
    elif cmd == "findings":
        print(json.dumps(list_findings(sys.argv[2] if len(sys.argv) > 2 else ""),
                         ensure_ascii=False, indent=2))
    elif cmd == "check" and len(sys.argv) >= 4:
        print(json.dumps(check(sys.argv[2], sys.argv[3]), ensure_ascii=False))
    elif cmd == "report" and len(sys.argv) >= 3:
        print(json.dumps(report(sys.argv[2]), ensure_ascii=False))
    else:
        print("usage: bounty.py summary|programs|findings [program]|check <program> <target>|report <finding>")
