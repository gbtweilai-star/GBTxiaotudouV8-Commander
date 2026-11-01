"""GBT小土豆V8 · 赏金工作台（合规优先的漏洞 bounty 流程）

主人 2026-11-02：方向转为「正规挖洞」。本模块管：授权项目 / 范围闸 / 发现 / 报告 / 提交状态 / 赔付账本。

合规红线（写死在代码里）：
  1. **没有授权记录 = 一律拒绝**：program 必须带 authorization_ref；
  2. **scope 之外 = 硬拒绝**（域名后缀 / IP-CIDR）；
  3. **本模块不做任何网络动作**，只做判定与账本；扫描走既有安全能力位且必须先过范围闸；
  4. **证据可核**：报告里每个证据带 sha256；
  5. **赔付只记账**，不收钱不转账。

报告升级（2026-11-02 第二刀）：CVSS 3.1 评分与向量、CWE 映射与修复建议、复现命令、提交追踪状态机。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import fnmatch
import hashlib
import ipaddress
import json
import re
import time
from pathlib import Path

from gbt_allinone import bounty_core as core

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "state" / "bounty"
PROGRAMS = STORE / "programs.json"
FINDINGS = STORE / "findings.jsonl"
STATUS_EVENTS = STORE / "status.jsonl"
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


def _status_map() -> dict:
    out = {}
    if STATUS_EVENTS.is_file():
        for ln in STATUS_EVENTS.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                e = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            out[e.get("finding")] = {"status": e.get("to"), "at": e.get("at"),
                                     "note": e.get("note")}
    return out


# ── 项目 ───────────────────────────────────────────────────────────────
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
    _append(STORE / "scope-checks.jsonl", row)
    return {"ok": True, "blocked": False, "program": program_id, "target": target,
            "action": action, "authorization_ref": prog.get("authorization_ref")}


# ── 发现 ───────────────────────────────────────────────────────────────
def add_finding(program_id: str, title: str, severity: str, target: str,
                cwe: str = "", cvss: str = "", steps: str = "",
                impact: str = "", remediation: str = "", evidence: list | None = None,
                vector: str = "", repro: list | None = None) -> dict:
    g = check(program_id, target, action="record-finding")
    if not g.get("ok"):
        return {"ok": False, "blocked": True, "reason": g.get("reason"),
                "detail": "发现必须先过授权/范围闸，否则不允许记录"}
    # 有 CVSS 向量 → 以向量算出的分数/严重度为准；否则用传入 severity（并给默认向量）
    vec = str(vector or "").strip()
    score = None
    if vec:
        c = core.cvss3(vec)
        if not c.get("ok"):
            return {"ok": False, "reason": "CVSS 向量非法：" + str(c.get("reason"))}
        score = c["base_score"]
        sev = c["severity"]
        vec = c["vector"]
    else:
        sev = str(severity).lower()
        if sev not in SEVERITIES:
            return {"ok": False, "reason": "severity 只能是 %s" % (SEVERITIES,)}
        vec = core.default_vector(sev)
        _c = core.cvss3(vec)
        score = _c.get("base_score") if _c.get("ok") else None
    info = core.cwe_info(cwe)
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
           "severity": sev, "target": target,
           "cwe": cwe or (info.get("cwe") or ""), "cwe_name": info.get("name"),
           "cvss_vector": vec, "cvss_score": score if score is not None else None,
           "steps": steps, "impact": impact,
           "remediation": remediation or info.get("fix") or "",
           "repro": [str(x) for x in (repro or [])],
           "evidence": ev, "status": "draft",
           "authorization_ref": g.get("authorization_ref")}
    _append(FINDINGS, row)
    return {"ok": True, "finding": row}


def list_findings(program_id: str = "") -> dict:
    rows, sm = [], _status_map()
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
            cur = sm.get(d.get("id")) or {}
            d["status"] = cur.get("status") or d.get("status") or "draft"
            d["status_at"] = cur.get("at")
            rows.append(d)
    return {"ok": True, "count": len(rows), "findings": rows}


# ── 提交追踪状态机 ─────────────────────────────────────────────────────
def set_status(finding_id: str, to: str, note: str = "") -> dict:
    rows = list_findings()["findings"]
    f = next((x for x in rows if x.get("id") == finding_id), None)
    if not f:
        return {"ok": False, "reason": "没有这个 finding"}
    cur = f.get("status") or "draft"
    if to not in core.STATUSES:
        return {"ok": False, "reason": "状态只能是 %s" % (core.STATUSES,)}
    if not core.can_transition(cur, to):
        return {"ok": False, "reason": "非法流转：%s → %s（允许：%s）"
                % (cur, to, sorted(core.TRANSITIONS.get(cur, set())))}
    e = {"at": _now(), "finding": finding_id, "from": cur, "to": to, "note": note}
    _append(STATUS_EVENTS, e)
    return {"ok": True, "finding": finding_id, "from": cur, "to": to, "event": e}


def submit(finding_id: str, platform: str = "", url: str = "", note: str = "") -> dict:
    r = set_status(finding_id, "submitted", note or ("提交到 %s %s" % (platform, url)))
    if r.get("ok"):
        r["platform"] = platform
        r["url"] = url
    return r


# ── 报告 ───────────────────────────────────────────────────────────────
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
    repro = f.get("repro") or []
    if not repro:
        tgt = f.get("target") or "<target>"
        repro = ["curl -i 'http://%s/'  # 只读复现占位：把实际请求补到这里" % tgt]
    score = f.get("cvss_score")
    score_txt = ("%s（%s）" % (score, core.severity_of(score))) if score is not None else \
        ("%s（按严重度映射）" % core.severity_of({"low": 2.6, "medium": 5.4, "high": 8.1,
                                                "critical": 9.8}.get(f.get("severity"), 5.4)))
    repro_txt = "\n".join(repro)
    ev_txt = "\n".join(ev_lines) or "（无）"
    body = f"""# {f["title"]}

## 摘要
- **项目**: {prog.get("name", f.get("program"))}（{prog.get("platform", "")}）
- **目标**: {f.get("target")}
- **严重度**: {f.get("severity")} · CVSS: {f.get("cvss_vector") or "-"}
- **CVSS 分数**: {score_txt}
- **CWE**: {f.get("cwe") or "-"}（{f.get("cwe_name") or "未收录"}）
- **状态**: {f.get("status")}
- **授权依据**: {f.get("authorization_ref")}
- **发现时间**: {f.get("at")}

## 复现命令
```bash
{repro_txt}
```

## 复现步骤
{f.get("steps") or "（待补）"}

## 影响
{f.get("impact") or "（待补）"}

## 修复建议
{f.get("remediation") or "（待补）"}

## 证据（sha256 可核）
{ev_txt}

## 提交建议
- 平台: {prog.get("platform") or "（未指定，自建项目）"}
- 提交前确认：只在授权 scope 内、证据齐全、复现命令可逐条跑通
- 报告 SHA256 与发现 JSON 一起提交（侧车文件 `{outp.stem}.json`）

---
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
    outp.write_text(body, encoding="utf-8")
    side = REPORTS / (finding_id + ".json")
    side.write_text(json.dumps({"finding": f, "program": prog, "report_md": str(outp),
                                "report_sha256": _sha256(outp)}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return {"ok": True, "report": str(outp), "json": str(side), "sha256": _sha256(outp),
            "bytes": outp.stat().st_size}


# ── 赔付 ───────────────────────────────────────────────────────────────
def payout(program_id: str, finding_id: str, amount: float, currency: str = "USD",
           status: str = "pending", note: str = "") -> dict:
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
    by_sev, by_status = {}, {}
    scores = []
    for f in finds:
        by_sev[f.get("severity")] = by_sev.get(f.get("severity"), 0) + 1
        by_status[f.get("status") or "draft"] = by_status.get(f.get("status") or "draft", 0) + 1
        if isinstance(f.get("cvss_score"), (int, float)):
            scores.append(float(f["cvss_score"]))
    total = {}
    for p in pays:
        c = p.get("currency") or "USD"
        total[c] = round(total.get(c, 0) + float(p.get("amount") or 0), 2)
    return {"ok": True, "programs": len(progs), "findings": len(finds),
            "by_severity": by_sev, "by_status": by_status,
            "avg_cvss": round(sum(scores) / len(scores), 2) if scores else None,
            "payouts": len(pays), "payout_total": total,
            "reports_dir": str(REPORTS)}
