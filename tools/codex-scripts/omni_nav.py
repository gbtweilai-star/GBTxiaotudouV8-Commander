# -*- coding: utf-8 -*-
# gbt-instrument: omni_nav · 万能插·自动导航（先学后做闸）
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""omni_nav · 万能插·自动导航 · 主人令 2026-10-01

主人原话：「在万能插里面加入一个自动导航——在接收到指令的时候就自动抓取核心资料、
学习透彻了再开始动手，**不许跳过**，必须把教程**全部看完吃透**，再开始分析规划动手。」

════════════════════════════════════════════════════════════════════════
三条纪律（做成判据，不是口号）：

  ① 自动：闸在收令时自动抓料 → 自动逐份**全文读入** → 自动记账 → 自动复验。
     不需要人催；材料一变（sha 变）自动判过期重学。
  ② 不许跳过：`gate()` 只认"计划内材料 100% 覆盖且哈希与现读一致"，
     缺一份/陈旧一份都**不放行** —— 没有任何绕过参数。
  ③ 吃透可核：每份材料记 全文 sha256 · 字节 · 行数 · 结构摘出（标题树）·
     与指令相关的关键行。吃透账落 `state/omni_nav.jsonl`（追加式），可回放可审计。

本模块**只读 + 只追加自己的账**：抓料=读本地文件（网络抓取走 devour 的门，不在此）；
学习=读入+摘出+记账；不执行任何能力位。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "omni_nav.jsonl"
CHUNK = 4096


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha_file(p: Path) -> str:
    return _sha_bytes(Path(p).read_bytes())


def _headers(text: str, limit: int = 16) -> list:
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if re.match(r"^#{1,4} ", s):
            out.append(s[:80])
            if len(out) >= limit:
                break
    return out


def _key_lines(text: str, terms: list, limit: int = 8) -> list:
    """与指令相关的关键行（每条材料最多 limit 条，去重）。"""
    out, seen = [], set()
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        for t in terms:
            if t and t.lower() in s.lower() and s[:60] not in seen:
                seen.add(s[:60])
                out.append(s[:120])
                if len(out) >= limit:
                    return out
    return out


def collect_materials(candidates: list) -> list:
    """候选 (路径, 为什么) **或**已收集的材料条目 ⇒ 材料清单（去重、验存在、每份带 sha/字节/行数）。
    幂等：喂已收集过的条目（dict）也成立 —— gate 复验时走的就是这条。"""
    out, seen = [], set()
    for item in candidates:
        if isinstance(item, dict):
            p, why = str(item.get("path") or ""), str(item.get("why") or "")
        else:
            p, why = item
        pp = Path(p)
        key = str(pp.resolve()) if pp.exists() else str(pp)
        if key in seen:
            continue
        seen.add(key)
        ok = pp.is_file()
        out.append({
            "path": str(pp),
            "why": why,
            "exists": ok,
            "sha256": _sha_file(pp) if ok else None,
            "bytes": pp.stat().st_size if ok else 0,
            "lines": (len(pp.read_bytes().splitlines()) if ok else 0),
        })
    return out


def learn(materials: list, topic: str = "") -> dict:
    """逐份**全文读入**并记账（这就是"全部看完"的机器证明：读不进就没法算哈希与行数）。

    任何一份不在盘上/读不了 ⇒ fail-closed（ok=False + 哪一份），**绝不带病放行**。
    `topic` 写进吃透账 —— 同主题的**新鲜复用**（gate 的省力路）靠它找回上次的记录。
    """
    mats, covered = [], 0
    for m in materials:
        p = Path(m["path"])
        if not p.is_file():
            return {"ok": False, "fail_closed": True,
                    "error": "材料不在盘上，拒绝带学：" + m["path"]}
        raw = p.read_bytes()
        text = raw.decode("utf-8", "replace")
        lines = text.splitlines()
        mats.append({
            "path": m["path"], "why": m.get("why", ""),
            "bytes": len(raw), "lines": len(lines),
            "sha256": _sha_bytes(raw),
            "chunk_n": (len(raw) + CHUNK - 1) // CHUNK,
            "headers": _headers(text),
            "read_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "覆盖": "100%",
        })
        covered += 1
    record = {"type": "learn", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "topic": str(topic)[:120],
              "materials_n": len(mats), "materials": mats}
    _append({"type": "learn", "at": record["at"], "topic": record["topic"],
             "materials_n": len(mats), "materials": mats})
    return {"ok": True, "record": record, "covered": covered}


def _last_learn(topic: str) -> dict | None:
    """吃透账里**同主题**最近一次 learn 记录（追加式台账，倒序找）。"""
    if not LEDGER.is_file():
        return None
    try:
        rows = LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(rows):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("type") == "learn" and r.get("topic") == str(topic)[:120] and r.get("materials"):
            return r
    return None


def check(record: dict, materials: list) -> dict:
    """新鲜验证：计划内材料**每份**都要 摘要里有 且 sha 与现读一致。
    返回 {fresh, missing[], stale[], fresh_n}。"""
    by_path = {m["path"]: m for m in (record.get("materials") or [])}
    missing, stale = [], []
    for m in materials:
        mp = str(m["path"]) if isinstance(m, dict) else str(m)
        p = Path(mp)
        rec = by_path.get(mp)
        if rec is None or not p.is_file():
            missing.append(mp)
            continue
        if _sha_file(p) != rec.get("sha256"):
            stale.append(mp)
    return {"fresh": not missing and not stale,
            "missing": missing, "stale": stale,
            "fresh_n": len(materials) - len(missing) - len(stale)}


def gate(topic: str, materials: list, terms: list | None = None) -> dict:
    """**先学后做闸**（自动导航主入口）：**新鲜即复用、缺/陈旧才重学**（不许跳过）。

    流程：抓料 → 查同主题吃透账 → `check()` 新鲜 ⇒ **直接复用**（零重读）；
    缺/陈旧/无账 ⇒ 逐份**全文读入**重学；学完必须 fresh 才放行。
    返回 {ok, fresh, learned(本次可真读), reused, 材料[]}；ok=False 仅当材料缺盘/读不了
    （fail-closed，此时**不许动手**）。`terms` = 指令关键 terms，用于关键行摘出。
    """
    mats = collect_materials(materials)
    unreadable = [m for m in mats if not m["exists"]]
    if unreadable:
        return {"ok": False, "fail_closed": True, "gate": "blocked",
                "error": "核心资料缺盘，拒绝动手：" +
                         "；".join(m["path"] for m in unreadable)[:200]}
    prev = _last_learn(topic)
    reused = False
    if prev is not None and check(prev, mats)["fresh"]:
        rec = prev                      # 新鲜：复用吃透账，零重读
        reused = True
    else:
        record = learn(mats, topic)     # 缺/陈旧：自动重学（不许跳过）
        if not record.get("ok"):
            return {"ok": False, "fail_closed": True, "gate": "blocked",
                    "error": record.get("error", "学习失败")}
        rec = record["record"]
    for m in rec["materials"]:
        if terms:
            m["关键行"] = _key_lines(
                Path(m["path"]).read_text(encoding="utf-8", errors="replace"), terms)
    c = check(rec, mats)
    if not c["fresh"]:
        return {"ok": False, "fail_closed": True, "gate": "blocked",
                "error": "复验不新鲜（缺 %d / 陈旧 %d）—— 不许带病放行"
                         % (len(c["missing"]), len(c["stale"]))}
    _append({"type": "gate", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "topic": str(topic)[:120], "materials_n": len(rec["materials"]),
             "fresh": c["fresh"], "reused": reused})
    return {"ok": True, "gate": "pass", "fresh": c["fresh"], "reused": reused,
            "topic": str(topic)[:120], "materials": rec["materials"],
            "learned_n": len(rec["materials"]),
            "_口径": "自动抓料→查账新鲜即复用→旧/缺才全文重读（sha+行数+标题树+关键行）"
            "→复验新鲜→放行；材料一变即判过期重学；无任何跳过参数"}


# ── 抓料：从意图/落点自动抓核心资料 ──────────────────────────────
def materials_for(intent: str, best: dict, root: Path, docs_dir: Path | None = None,
                  skill_md: str | None = None, max_docs: int = 4) -> list:
    """自动抓核心资料（本地优先；网络抓取走 devour 的门，不在此）：
      ① 落点能力页 `holo_pet_w3/brain/caps/<kind>.html`（有则抓）；
      ② 实现模块（handler 对应文件，从 invoke 里取不到就在 atlas caps 的 handler 名里找）；
      ③ docs/ 里与 kind/域关键词命中的教程（≤ max_docs 份，按 mtime 新先）；
      ④ 技能 SKILL.md（atlas skills 里 name==kind 的那一份）。
    """
    kind = str(best.get("kind") or "")
    cand: list = []
    page = root / "holo_pet_w3" / "brain" / "caps" / (kind + ".html")
    if page.is_file():
        cand.append((str(page), "落点能力页（232 位之一）"))
    handler = str(best.get("handler") or best.get("kind") or "")
    # ↑ 回落名=kind：指挥链侧传的就是 {"kind": cap}（没带 handler），而本仓 handler 名≈kind；
    if handler:
        mod = root / "gbt_allinone" / "tools" / (handler + ".py")
        if mod.is_file():
            cand.append((str(mod), "能力位实现模块（真源）"))
        mod2 = root / "gbt_allinone" / (handler + ".py")
        if mod2.is_file():
            cand.append((str(mod2), "能力位实现模块（真源·包根）"))
    if skill_md and Path(skill_md).is_file():
        cand.append((skill_md, "技能正文（atlas 登记的 SKILL.md）"))
    if docs_dir is not None and docs_dir.is_dir():
        terms = [t for t in re.findall(r"[A-Za-z_\u4e00-\u9fff]{2,}", kind + " " + intent)][:6]
        scored = []
        for f in sorted(docs_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                continue
            hit = sum(1 for t in terms if t and t in txt)
            if hit:
                scored.append((hit, f))
        for _, f in sorted(scored, key=lambda x: -x[0])[:max_docs]:
            cand.append((str(f), "docs/ 相关教程（关键词命中）"))
    return collect_materials(cand)


def _append(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="自动导航：先学后做闸（omni 用）")
    ap.add_argument("topic", help="主题（指令或技能名）")
    ap.add_argument("materials", nargs="*", help="核心材料路径（缺省=只验证已有账）")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)
    terms = re.findall(r"[A-Za-z_\u4e00-\u9fff]{2,}", ns.topic)[:8]
    r = gate(ns.topic, collect_materials([(m, "命令行指定") for m in ns.materials]), terms)
    if ns.json:
        print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])
    else:
        print("闸：%s ｜ 材料 %d 份 ｜ 新鲜：%s"
              % (r.get("gate"), r.get("learned_n", 0), r.get("fresh")))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
