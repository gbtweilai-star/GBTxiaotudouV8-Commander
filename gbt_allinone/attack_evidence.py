"""GBT小土豆V8 · 受攻击举证与交代（没证据不许说被攻击）

主人 2026-11-03：「没证据被攻击你怎么给用户交代？」
—— 攻击模式必须**先举证**：有证据才进攻击模式；没证据只能如实说"未发现攻击证据"，
   绝不凭一句"感觉被攻击"就极限并发、更不对外宣称被攻击。

证据来源（本地只读采集）：
  · audit.jsonl 里 auth_denied / denied 的短时爆发（默认 60s 内 ≥10 次）
  · security-policy-audit.jsonl 里的异常请求
  · 本机连接里同一远端 IP 的高频/多端口（端口扫描特征）
  · 文件完整性：关键文件 hash 变化（本模块记录基线）
  · 主人陈述（user-report）：由主人明确说"被攻击"，带时间戳，作为证据之一

判定：强证据（denied 爆发/端口扫描/hash 篡改）≥1 条 → 允许进入攻击模式；
只有主人陈述（user-report）→ 允许进入（但标注证据等级=user-report，需主人确认）；
无任何证据 → 拒绝进入攻击模式，返回"未发现被攻击证据"的交代文案。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "state" / "attack-evidence.jsonl"
BASELINE = ROOT / "state" / "attack-baseline.json"
AUDIT = ROOT / "gbt_allinone" / "store" / "audit.jsonl"

STRONG_KINDS = {"auth_denied_burst", "port_scan", "file_tamper", "intrusion_alert"}
WEAK_KINDS = {"user_report", "policy_anomaly"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def add_evidence(kind: str, source: str, detail: str, strong: bool | None = None) -> dict:
    """证据入库：带 sha256、时间、来源。"""
    raw = str(detail)
    row = {"at": _now(), "kind": str(kind), "source": str(source)[:200],
           "detail": raw[:1000], "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
           "strong": (kind in STRONG_KINDS) if strong is None else bool(strong)}
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def list_evidence(limit: int = 200) -> list:
    rows = []
    if EVIDENCE.is_file():
        for ln in EVIDENCE.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.strip():
                try:
                    rows.append(json.loads(ln))
                except Exception:  # noqa: BLE001
                    pass
    return rows[-limit:]


def _recent(rows: list, seconds: int = 3600) -> list:
    cutoff = time.time() - seconds
    out = []
    for r in rows:
        try:
            t = time.mktime(time.strptime(r.get("at", ""), "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            continue
        if t >= cutoff:
            out.append(r)
    return out


def detect_signals(denied_burst: int = 10, window_s: int = 60) -> list:
    """本地只读检测：返回候选证据（不直接判定）。"""
    found = []
    # ① 审计里 denied 短时爆发
    if AUDIT.is_file():
        cutoff = time.time() - window_s
        n = 0
        sample = []
        for ln in AUDIT.read_text(encoding="utf-8", errors="replace").splitlines()[-5000:]:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            ev = str(d.get("event") or "")
            iso = str(d.get("iso") or d.get("at") or "")
            if ev in ("auth_denied", "denied"):
                try:
                    t = time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))
                except Exception:
                    t = 0
                if t >= cutoff:
                    n += 1
                    if len(sample) < 5:
                        sample.append({"at": iso, "event": ev})
        if n >= denied_burst:
            found.append({"kind": "auth_denied_burst", "source": "audit.jsonl",
                          "detail": "%ds 内 denied %d 次（阈值 %d）" % (window_s, n, denied_burst),
                          "sample": sample})
    # ② hash 基线变化（关键文件）
    base = {}
    try:
        base = json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception:
        base = {}
    changed = []
    for rel, h in (base.get("files") or {}).items():
        p = ROOT / rel
        if p.is_file():
            cur = hashlib.sha256(p.read_bytes()).hexdigest()
            if cur != h:
                changed.append(rel)
    if changed:
        found.append({"kind": "file_tamper", "source": "baseline",
                      "detail": "关键文件 hash 变化：%s" % ", ".join(changed[:5])})
    return found


def record_baseline(files: list | None = None) -> dict:
    """记录关键文件 hash 基线（用于发现篡改）。"""
    files = files or ["gbt_allinone/api.py", "gbt_allinone/caps_registry.py",
                      "tools/console-server.py"]
    data = {"at": _now(), "files": {}}
    for rel in files:
        p = ROOT / rel
        if p.is_file():
            data["files"][rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def admission(extra: list | None = None) -> dict:
    """举证门槛：强证据 ≥1 或 主人陈述 → 允许；否则拒绝。"""
    ev = list_evidence() + list(extra or [])
    strong = [e for e in ev if e.get("strong")]
    user = [e for e in ev if e.get("kind") == "user_report"]
    if strong:
        return {"admitted": True, "level": "strong", "evidence": strong[-5:],
                "count": len(ev), "reason": "有强证据"}
    if user:
        return {"admitted": True, "level": "user_report", "evidence": user[-3:],
                "count": len(ev), "reason": "主人明确陈述被攻击（作为证据，已记录时间戳）"}
    return {"admitted": False, "level": "none", "evidence": [], "count": len(ev),
            "reason": "未发现被攻击证据",
            "explain": "没有日志/连接/hash/主人陈述等证据 → 不能进入攻击模式，"
                       "更不能对外宣称被攻击；只能继续监控并如实报告'未见攻击证据'。",
            "hint": "如确有攻击：主人可用 --user-report 记录陈述，或先跑取证收集证据"}


def explain() -> dict:
    """给用户/审计的交代：证据清单 + 结论 + 建议。"""
    ev = list_evidence()
    recent = _recent(ev)
    adm = admission()
    return {"ok": True, "conclusion": "有攻击证据" if adm.get("admitted") else "未发现被攻击证据",
            "level": adm.get("level"), "admitted": adm.get("admitted"),
            "evidence_count": len(ev), "recent_count": len(recent),
            "recent": recent[-10:], "explain": adm.get("explain") or adm.get("reason"),
            "rule": "没证据不许说被攻击；攻击模式必须有证据门槛"}
