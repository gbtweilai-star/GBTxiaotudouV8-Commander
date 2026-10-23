# -*- coding: utf-8 -*-
"""skill_finder -- 技能检索器（蒸馏自 skills.sh find-skills：只蒸思想）。
op=find（q=一句需求）→ 候选技能 + 三列（来源/装机与否/风险）；op=vet（name）→ 供应链体检报告。
不装任何东西、不出网；只读本机技能目录 + 图鉴。
"""
from __future__ import annotations
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "state" / "skill_atlas.json"
DIRS = [Path.home() / ".openclaw-autoclaw" / "skills", ROOT / "skills", ROOT / ".claude" / "skills"]
RISK_PAT = {
    "要密钥": re.compile(r"(API[_-]?KEY|TOKEN|SECRET|PASSWORD|密钥|凭据)", re.I),
    "破坏命令": re.compile(r"(rm\s+-rf|del\s+/f|format\s+[A-Z]:|Remove-Item[^\n]*-Recurse[^\n]*-Force)", re.I),
    "外发": re.compile(r"(curl\s+-X\s*POST|requests\.post|fetch\(|webhook|ngrok)", re.I),
    "改系统": re.compile(r"(reg\s+add|Set-ItemProperty|sudo\s+|chmod\s+777|Add-Type)", re.I),
    "装包": re.compile(r"(pip\s+install|npm\s+i(nstall)?\b|pnpm\s+add|npx\s)", re.I),
}


def _atlas() -> list:
    if not ATLAS.is_file():
        return []
    try:
        d = json.loads(ATLAS.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    out = []
    def walk(o):
        if isinstance(o, dict):
            if o.get("name"):
                out.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(d)
    return out


def _installed() -> dict:
    m = {}
    for base in DIRS:
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.is_dir() and (p / "SKILL.md").is_file():
                m[p.name] = p
    return m


def _grams(s: str):
    s = "".join(ch for ch in s.lower() if ch.isalnum() or "一" <= ch <= "鿿")
    return {s[k:k + 2] for k in range(max(0, len(s) - 1))} or ({s} if s else set())

def _score(q: str, item: dict) -> float:
    gq = _grams(q)
    if not gq:
        return 0.0
    name = _grams(str(item.get("name", "")))
    desc = _grams(str(item.get("description", "")) + str(item.get("desc", "")))
    # 名字命中权重 2倍：名字对上比描述对上更说明问题
    return round((len(gq & name) * 2 + len(gq & desc)) / (len(gq) * 3), 3)

def find(q: str, limit: int = 12) -> list:
    inst = _installed()
    rows = []
    for it in _atlas():
        n = str(it.get("name", ""))
        if not n:
            continue
        s = _score(q, it)
        if s <= 0:
            continue
        rows.append({"name": n, "score": round(s, 2), "installed": n in inst,
                     "source": str(it.get("source") or it.get("path") or it.get("repo") or "图鉴"),
                     "desc": str(it.get("description") or it.get("desc") or "")[:90]})
    for n, p in inst.items():
        if not any(r["name"] == n for r in rows) and _score(q, {"name": n, "description": n}) > 0:
            rows.append({"name": n, "score": 0.01, "installed": True, "source": str(p), "desc": ""})
    rows.sort(key=lambda r: (-r["score"], not r["installed"]))
    return rows[:limit]


def vet(name: str) -> dict:
    inst = _installed()
    p = inst.get(name)
    if not p:
        return {"ok": False, "status": "user_error", "message": "本机没装这个技能：%s（先 find，再读全文审）" % name}
    f = p / "SKILL.md"
    t = f.read_text(encoding="utf-8", errors="replace")
    flags = sorted({k for k, rx in RISK_PAT.items() if rx.search(t)})
    return {"ok": True, "name": name, "path": str(f), "bytes": f.stat().st_size,
            "risk_flags": flags, "verdict": ("需人审" if flags else "未命中风险特征"),
            "rule": "装任何外部技能前：读全文 → 查密钥/破坏命令/外发/改系统 → 出 VETTING REPORT → 主人确认。本位只出报告，不装不改。"}


def run(payload: dict) -> dict:
    p = payload or {}
    op = p.get("op") or "find"
    if op == "find":
        q = p.get("q") or p.get("query") or ""
        if not q.strip():
            return {"ok": False, "status": "user_error", "message": "缺少 q（一句需求）"}
        rows = find(q, int(p.get("limit") or 12))
        return {"ok": True, "q": q, "count": len(rows), "candidates": rows,
                "note": "候选来自本机图鉴+技能目录（不出网）；装前必过 op=vet 供应链闸"}
    if op == "vet":
        n = p.get("name") or ""
        if not n:
            return {"ok": False, "status": "user_error", "message": "缺少 name"}
        return vet(n)
    return {"ok": False, "status": "user_error", "message": "未知 op：%s（find | vet）" % op}
