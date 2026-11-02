"""GBT小土豆V8 · 记忆同步层（单一事实源 + 乐观锁 + 触手广播）

规则：
  · 所有智能体写记忆必须走本层（不直接写库）；
  · 乐观锁：写入必须带 parent_hash（上一条的 detail_sha256 或 GENESIS），
    不匹配 = 有人已改 → 拒写，要求重读后再写（防覆盖丢失）；
  · 版本链：version = parent.version + 1（GENESIS 为 1）；
  · 触手广播：每次成功写入追加 state/memory/bus.jsonl，供各智能体订阅刷新；
  · 读：直接委托 memory_bank.recall（秒查 + 覆盖率）。

开发者：自由的风 · GBT小土豆V8
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUS = ROOT / "state" / "memory" / "bus.jsonl"


def _db():
    import sys
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import memory_bank as MB
    return MB


def _last_chain(db) -> tuple[str, int, str]:
    c = db._conn()
    row = c.execute("SELECT detail_sha256 FROM memory ORDER BY id DESC LIMIT 1").fetchone() \
        if False else None
    # detail_sha256 不落库（只返回），用 evidence_sha256+parent 链代替：
    last = c.execute("SELECT evidence_sha256, version, parent_hash FROM memory "
                     "ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    if not last:
        return "GENESIS", 0, ""
    return str(last["evidence_sha256"] or ""), int(last["version"] or 0), str(last["parent_hash"] or "")


def write(client: str, parent_hash: str, **kw) -> dict:
    db = _db()
    last_ev, last_ver, _ = _last_chain(db)
    expected = last_ev or "GENESIS"
    if str(parent_hash) != expected:
        return {"ok": False, "conflict": True,
                "reason": "乐观锁失败：parent_hash=%s，当前链头=%s（有人先写了，请重读再写）"
                          % (parent_hash, expected)}
    kw.setdefault("version", last_ver + 1)
    kw["parent_hash"] = expected
    r = db.store(**kw)
    if not r.get("ok"):
        return r
    BUS.parent.mkdir(parents=True, exist_ok=True)
    ev = {"at": kw.get("at"), "id": r.get("id"), "client": client,
          "action": kw.get("action"), "target": kw.get("target"),
          "version": kw.get("version"), "parent_hash": expected,
          "chain": kw.get("evidence_sha256"), "detail_sha256": r.get("detail_sha256")}
    with BUS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return {"ok": True, "id": r.get("id"), "version": kw.get("version"),
            "broadcast": str(BUS), "chain": kw.get("evidence_sha256"), "detail_sha256": r.get("detail_sha256")}


def subscribe(since_id: int = 0, limit: int = 100) -> dict:
    rows = []
    if BUS.is_file():
        for ln in BUS.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if int(d.get("id") or 0) > since_id:
                rows.append(d)
    return {"ok": True, "events": rows[:limit], "count": len(rows[:limit])}


def recall(q: str = "", limit: int = 50, since: str = "", until: str = "") -> dict:
    return _db().recall(q=q, limit=limit, since=since, until=until)
