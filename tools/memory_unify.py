#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""memory_unify —— 把她的记忆统一成一册（一个索引，跨源可查）。

## 为什么需要
实测她现在的记忆散在四处，各查各的：
  · ring_context   对话全史（SQLite FTS5，1986 条，但大半是测试会话）
  · context_vault  索引层（几乎空：docs 1 条 / postings 3 条 —— 建了没用起来）
  · devoured       吞进来的知识胶囊（2 个）
  · state/*.jsonl  事件账（context_guard / duty_patrol …）

⇒ 问一句"我之前说过什么"，得知道去哪个库查。这不是记忆，这是四个抽屉。

## 统一层做什么（不搬数据）
  ① 只读遍历各源，**建一份统一索引**（自己的 sqlite，不碰原库）
  ② 每条带 `src` / `ref` / `name` / `at`，可指回原处
  ③ recall(q) 一句查全册，按源分组返回
  ④ 测试会话**单列**（tag=test），默认不混进正经记忆

## 与 context_vault 的分工（两个库，不是一个库塞两用）
  · `context_vault` = 框架自己的**索引层**：只存**引用与词**，不存正文，带 source_ref，按预算裁剪。
    适合"知道在哪、要时去取"。
  · `memory_unify`   = **检索前置**：为了让一句 query 能出**可读片段**并注入人设，
    它**确实存了正文副本**（`text` 列）。这是副本，不是权威 —— 权威永远在原库。

## 铁律
  · **副本必须承认是副本**：这里存 text 是为了出片段；原文与出处以 src/ref 为准
  · **不删原库**：只读遍历，一个字节都不改
  · **测试噪音不冒充记忆**：按 name 规则标 test，账上看得见
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

IDX = ROOT / "gbt_allinone" / "store" / "memory_unify" / "unified.sqlite3"
RING = ROOT / "gbt_allinone" / "store" / "ring_context" / "ring.db"
VAULT = ROOT / "gbt_allinone" / "store" / "context_vault" / "index.sqlite3"
DEVOURED = ROOT / "gbt_allinone" / "store" / "devoured"
STATE = ROOT / "state"

# 测试会话名（我这一场建的）：这些不进"正经记忆"，单列 tag=test
TEST_NAME = re.compile(
    r"^(acc_ring|acc_guard|reg\d|rg\d|dbg|duptest|xproc|unl|unl2|final|page-test|"
    r"probe|v\d{6,}|m\d{6,}|g\d{6,}|w\d{6,}|xproc\d|ba_|guardtest|reg[A-Z])")


def _conn():
    IDX.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(IDX))
    # 与 ring_context 同理：iSH 的 mmap 每进程私有，WAL 跨进程不可见 ⇒ 用 DELETE
    try:
        c.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.OperationalError:
        pass
    c.execute("CREATE TABLE IF NOT EXISTS mem ("
              "h TEXT PRIMARY KEY, src TEXT, ref TEXT, name TEXT, at TEXT, "
              "role TEXT, text TEXT, tag TEXT)")
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(text, tokenize='unicode61')")
    except sqlite3.OperationalError:
        pass
    return c


def _hash(*parts) -> str:
    import hashlib
    return hashlib.sha1("\x00".join(str(x) for x in parts).encode("utf-8")).hexdigest()[:20]


def survey() -> dict:
    """盘点：各源多少条、多大。"""
    out = {}
    if RING.is_file():
        c = sqlite3.connect(str(RING))
        rows = c.execute("select name, count(*) from turns group by name").fetchall()
        c.close()
        out["ring_context"] = {
            "file": str(RING.relative_to(ROOT)),
            "turns": sum(r[1] for r in rows),
            "sessions": len(rows),
            "test_sessions": [r[0] for r in rows if TEST_NAME.match(str(r[0] or ""))],
            "real_sessions": [r[0] for r in rows if not TEST_NAME.match(str(r[0] or ""))],
        }
    if VAULT.is_file():
        c = sqlite3.connect(str(VAULT))
        try:
            n = c.execute("select count(*) from docs").fetchone()[0]
        except Exception:                                     # noqa: BLE001
            n = 0
        c.close()
        out["context_vault"] = {"file": str(VAULT.relative_to(ROOT)), "docs": n}
    if DEVOURED.is_dir():
        cap = [d.name for d in DEVOURED.iterdir() if d.is_dir()]
        out["devoured"] = {"dir": str(DEVOURED.relative_to(ROOT)), "capsules": cap}
    if STATE.is_dir():
        ev = [f.name for f in STATE.glob("*.jsonl")]
        out["state_events"] = {"files": ev}
    return out


def index(sources: tuple = ("ring", "devoured")) -> dict:
    """建统一索引。只读各源，不改原库。"""
    c = _conn()
    added = {"ring": 0, "devoured": 0}
    rows = []

    if "ring" in sources and RING.is_file():
        r = sqlite3.connect(str(RING))
        for seq, at, role, content, name in r.execute(
                "select seq, at, role, content, name from turns"):
            nm = str(name or "default")
            tag = "test" if TEST_NAME.match(nm) else "real"
            rows.append((_hash("ring", seq, nm), "ring_context",
                         "ring.db#seq=%s" % seq, nm, at, role, str(content or ""), tag))
        r.close()

    if "devoured" in sources and DEVOURED.is_dir():
        for d in DEVOURED.iterdir():
            f = d / "absorbed_knowledge.md"
            if not f.is_file():
                continue
            txt = f.read_text(encoding="utf-8", errors="replace")[:200000]
            rows.append((_hash("devoured", d.name), "devoured",
                         str(f.relative_to(ROOT)), d.name,
                         time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime)),
                         "knowledge", txt, "real"))

    for row in rows:
        cur = c.execute("select 1 from mem where h=?", (row[0],)).fetchone()
        if cur:
            continue
        c.execute("insert into mem (h,src,ref,name,at,role,text,tag) values (?,?,?,?,?,?,?,?)", row)
        c.execute("insert into mem_fts (rowid, text) values ((select rowid from mem where h=?), ?)",
                  (row[0], row[6]))
        added[row[1] if row[1] in added else "ring"] += 1
    c.commit()
    c.close()
    return {"ok": True, "added": added, "index": str(IDX.relative_to(ROOT))}


# 最小双语桥：中文问句 ↔ 英文语料。
# 🔴 2026-10-29 实测：胶囊多是英文原文（arxiv / GitHub README），
#   中文问句「怎么做设计才有品味」用 FTS 命中 0 —— **不是检索坏了，是跨语言**。
#   这里只做**有限的一组常用词**（不假装是翻译引擎）：命中中文词时补上对应英文词一起查。
#   没在表里的词不猜 —— 查不到就如实查不到。
BRIDGE = {
    "设计": "design", "品味": "taste", "审美": "aesthetic", "风格": "style",
    "配色": "color palette", "排版": "typography", "字体": "font",
    "布局": "layout", "界面": "interface ui", "交互": "interaction",
    "注意力": "attention", "显存": "memory vram", "缓存": "cache",
    "推理": "inference", "量化": "quantization", "训练": "training",
    "模型": "model", "权重": "weights", "上下文": "context",
    "记忆": "memory", "检索": "retrieval search", "索引": "index",
    "投影": "projection", "摄像": "camera", "数字人": "digital human",
    "动捕": "motion capture", "骨骼": "rig skeleton", "渲染": "render",
    "并发": "concurrency", "性能": "performance", "延迟": "latency",
    "安全": "security", "审计": "audit", "权限": "permission",
    "蒸馏": "distill", "吞噬": "devour", "触手": "tentacle",
}


STOP = set("的 了 我 你 他 她 是 在 有 和 就 也 都 而 及 或 吗 呢 吧 啊 怎么 什么 为什么 "
           "如何 怎样 这个 那个 一个 可以 应该 需要 请问 能不能 有没有".split())


def _terms(q: str) -> list:
    """把 query 切成可检索的词。中文按 2 字滑窗，英文按空格。"""
    q = re.sub(r"[^\w\u4e00-\u9fff]+", " ", str(q or ""))
    q = re.sub(r"\b(%s)\b" % "|".join(sorted(STOP, key=len, reverse=True)), " ", q)
    out = []
    for seg in q.split():
        if re.fullmatch(r"[\u4e00-\u9fff]+", seg):
            if len(seg) >= 2:
                out += [seg] if len(seg) <= 4 else [seg[i:i + 2] for i in range(len(seg) - 1)]
        elif len(seg) >= 2:
            out.append(seg)
    # 双语桥：中文词补上对应的英文词（只补表里有的，不猜）
    for seg in list(out):
        for zh, en in BRIDGE.items():
            if zh in seg:
                out += en.split()
    seen, uniq = set(), []
    for t in out:
        t = t.strip()
        if t and t not in seen and t.lower() not in seen:
            seen.add(t)
            seen.add(t.lower())
            uniq.append(t)
    return uniq[:16]


def recall(q: str, k: int = 10, include_test: bool = False) -> dict:
    """一句查全册。默认**不含**测试噪音。"""
    c = _conn()
    tag_clause = "" if include_test else " and m.tag='real'"
    try:
        rows = c.execute(
            "select m.src, m.ref, m.name, m.at, m.role, m.text, m.tag from mem_fts f "
            "join mem m on m.rowid=f.rowid where mem_fts match ?" + tag_clause +
            " order by rank limit ?", (q, k)).fetchall()
    except sqlite3.OperationalError:
        rows = c.execute(
            "select src, ref, name, at, role, text, tag from mem "
            "where text like ?" + (" and tag='real'" if not include_test else "") +
            " order by at desc limit ?", ("%" + q + "%", k)).fetchall()
    if not rows:                                  # 词面兜底：拆词再查（**中文必须按字切**）
        # 🔴 2026-10-29 实测：问「怎么做设计才有品味，别那么套路？」
        #   FTS 与按空格切都命中 0 —— **中文没有空格**，整句被当成一个超长 token。
        #   和 self_intake 的 known 是同一类 bug。这里按 2 字滑窗切，逐词 LIKE 并计分。
        toks = _terms(q)
        seen, got, score = set(), [], {}
        real_clause = "" if include_test else " and tag='real'"
        for t in toks:
            try:
                rr = c.execute(
                    "select m.src, m.ref, m.name, m.at, m.role, m.text, m.tag from mem_fts f "
                    "join mem m on m.rowid=f.rowid where mem_fts match ?" + tag_clause +
                    " order by rank limit ?", (t, k)).fetchall()
            except sqlite3.OperationalError:
                rr = []
            if not rr:
                rr = c.execute(
                    "select src, ref, name, at, role, text, tag from mem "
                    "where text like ?" + real_clause + " order by at desc limit ?",
                    ("%" + t + "%", k)).fetchall()
            for x in rr:
                key = (x[0], x[1])
                score[key] = score.get(key, 0) + 1        # 命中词数越多越相关
                if key not in seen:
                    seen.add(key)
                    got.append(x)
        got.sort(key=lambda x: -score.get((x[0], x[1]), 0))
        rows = got[:k]
    c.close()
    hits = [{"src": r[0], "ref": r[1], "name": r[2], "at": r[3],
             "role": r[4], "text": (r[5] or "")[:300], "tag": r[6]} for r in rows]
    by = {}
    for h in hits:
        by.setdefault(h["src"], []).append(h)
    return {"ok": True, "query": q, "total": len(hits),
            "by_src": {k2: len(v) for k2, v in by.items()}, "hits": hits}


SRC_RE = re.compile(r"来源[:：]\s*(https?://[^\s|)）]+)")


def resolve_source(capsule_dir: pathlib.Path):
    """找出处。**三种格式都认**，不只看护照文件。

    🔴 2026-10-29 实测踩到的判据太窄：`taste_skill` 的出处明明写在胶囊头部
       （`来源: https://github.com/Leonxlnx/taste-skill`），但它是 10-26 由
       `devour_tentacle` 生成的，那时还没有 self_intake 的护照机制 ⇒ 没有
       passport.json ⇒ 我的 feed_vault 把它当"无出处"跳过了。
       **有出处却被当成无出处，等于把真知识扔掉。**

    顺序：护照文件 → 胶囊头部「来源: URL」→ knowledge.json 里的 repo/url。
    """
    name = capsule_dir.name
    passport = ROOT / "store" / "trace" / (name + ".passport.json")
    if passport.is_file():
        return str(passport.relative_to(ROOT)), "passport"
    f = capsule_dir / "absorbed_knowledge.md"
    if f.is_file():
        head = f.read_text(encoding="utf-8", errors="replace")[:2000]
        m = SRC_RE.search(head)
        if m:
            return m.group(1), "header_url"
    kj = capsule_dir / "knowledge.json"
    if kj.is_file():
        try:
            d = json.loads(kj.read_text(encoding="utf-8"))
            for k in ("source", "repo", "url", "upstream"):
                v = d.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    return v, "knowledge_json"
        except Exception:                                     # noqa: BLE001
            pass
    return None, None


def feed_vault() -> dict:
    """把 devoured 胶囊灌进 context_vault（框架自己的索引层，只存引用与词）。

    为什么要喂：实测 context_vault 的 docs 只有 1 条 —— 它建好了、能搜、
    但**从来没被喂过**。而它的纪律是对的（db_add 强制 source_ref）。
    胶囊自带护照（store/trace/<topic>.passport.json），正好当 source_ref。

    口径：**只喂有出处的**。没有护照的一律不喂，并在账上列出来。
    """
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.api import run_task
    if not DEVOURED.is_dir():
        return {"ok": False, "why": "devoured 目录不存在"}
    fed, skipped = [], []
    for d in DEVOURED.iterdir():
        f = d / "absorbed_knowledge.md"
        if not f.is_file():
            continue
        src, how = resolve_source(d)
        if not src:
            skipped.append({"capsule": d.name, "why": "护照/头部/元数据三处都找不到出处 ⇒ 按纪律不喂"})
            continue
        r = run_task("context_vault", {"op": "db_add", "doc_id": d.name,
                                       "title": "胶囊 · " + d.name,
                                       "source_ref": src,
                                       "text": f.read_text(encoding="utf-8", errors="replace")[:20000]})
        res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        (fed if res.get("ok") else skipped).append(
            {"capsule": d.name, "ok": res.get("ok"), "terms": res.get("terms"),
             "src": src, "how": how, "why": res.get("why")})
    return {"ok": True, "fed": fed, "skipped": skipped}


def stats() -> dict:
    c = _conn()
    tot = c.execute("select count(*) from mem").fetchone()[0]
    bysrc = c.execute("select src, tag, count(*) from mem group by src, tag").fetchall()
    c.close()
    return {"total": tot,
            "by_src_tag": [{"src": a, "tag": b, "n": n} for a, b, n in bysrc]}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--feed-vault", action="store_true")
    ap.add_argument("--recall", default="")
    ap.add_argument("--include-test", action="store_true")
    a = ap.parse_args()
    if a.survey:
        print(json.dumps(survey(), ensure_ascii=False, indent=1))
        return 0
    if a.index:
        print(json.dumps(index(), ensure_ascii=False))
        print(json.dumps(stats(), ensure_ascii=False))
        return 0
    if a.stats:
        print(json.dumps(stats(), ensure_ascii=False, indent=1))
        return 0
    if a.feed_vault:
        print(json.dumps(feed_vault(), ensure_ascii=False, indent=1))
        return 0
    if a.recall:
        print(json.dumps(recall(a.recall, include_test=a.include_test), ensure_ascii=False, indent=1))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
