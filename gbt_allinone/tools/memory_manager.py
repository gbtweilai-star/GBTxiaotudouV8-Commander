# gbt-capability: memory_manager
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""记忆管理 + 万能精准秒搜（主人令 2026-09-27）。

主人原话：「负责帮助本体整理上下文快满了就自动压缩避免溢出丢失资料，以及**记忆管理**（全局记忆管理
储存和查找），**全局只要是一页看不到的东西全部设计一个万能精准秒搜**，想到匹配面出现的能力。」

## 它解决什么
"一页看不到的东西" = 仓里 14k 个资产 / 记忆 / 文档 / 技能 / 状态 / 能力位 —— 靠翻是找不到的。
本能力建一张 **SQLite FTS5 全文索引**（实测**中文可检索**、命中带高亮片段），秒级返回
**路径 + 类型 + 高亮片段**，并**同时把匹配的能力位端出来**（"想到匹配面出现的能力"）。

## SQL 写法纪律（写死，别再犯）
所有语句都是**内联字面量**、**全部走 `?` 占位符**；**不用变量拼 SQL、不做字符串相加**
（安全钩子的 SQL 注入判据就盯这一条 —— 实测被拦过两次，都是因为 SQL 放在变量里/做了拼接）。

## 六类源
| type | 源 |
|---|---|
| 记忆 | `memory/*.md` |
| 文档 | `docs/*.md` + 根白名单（AGENTS/LAYOUT/README/CURRENT/CODING_DISCIPLINE） |
| 技能 | `skills/*/SKILL.md` |
| 状态 | `state/*.jsonl` · `state/*.json` |
| 能力 | `caps_registry.BENIGN_CAPS`（kind + 域 + 描述）——**"匹配面出现的能力"** |
| 代理 | `~/.zcode/agents/*.md`（我们装的助理） |

ops：index（增量）/ find（秒搜）/ store（存记忆·过写门）/ stats
"""
from __future__ import annotations

import glob
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DB = _ROOT / "state" / "memory_fts.db"
_META = _ROOT / "state" / "memory_index_meta.json"
_MAX_DOC_BYTES = 400_000
_AGENTS = Path.home() / ".zcode" / "agents"


def _sources() -> list:
    out = []
    for pat, t in (("memory/*.md", "记忆"), ("docs/*.md", "文档"),
                   ("skills/*/SKILL.md", "技能"), ("state/*.jsonl", "状态"),
                   ("state/*.json", "状态")):
        for f in glob.glob(str(_ROOT / pat)):
            out.append((t, Path(f)))
    for f in glob.glob(str(_AGENTS / "*.md")):
        out.append(("代理", Path(f)))
    for name in ("AGENTS.md", "LAYOUT.md", "README.md", "CURRENT.md", "CODING_DISCIPLINE.md"):
        p = _ROOT / name
        if p.is_file():
            out.append(("文档", p))
    return out


def _caps_docs() -> list:
    try:
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
    except Exception:                                          # noqa: BLE001
        return []
    return [("能力", f"cap:{k}", f"{k} [{v.get('domain')}] {v.get('desc', '')}")
            for k, v in BENIGN_CAPS.items()]


def _read(p: Path) -> str:
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return t[:_MAX_DOC_BYTES] + ("\n…〔超 400KB 已截断〕" if len(t) > _MAX_DOC_BYTES else "")


def index(force: bool = False, **_kw) -> dict:
    db = sqlite3.connect(str(_DB))
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(type, path, label, body)")
    db.execute("CREATE TABLE IF NOT EXISTS meta(path TEXT PRIMARY KEY, mtime REAL, sha TEXT)")
    prev = {r[0]: (r[1], r[2]) for r in db.execute("SELECT path, mtime, sha FROM meta")}
    added = updated = skipped = 0
    rows, metas = [], []
    # 全量源路径（**判"谁真的不见了"要用全量**，不能用"本次变化的" —— 实测因此丢过 344 条索引）
    live_all = set()
    for _t, _p in _sources():
        try:
            live_all.add(str(_p.relative_to(_ROOT)).replace("\\", "/"))
        except ValueError:
            live_all.add(str(_p))
    for t, p in _sources():
        try:
            rel = str(p.relative_to(_ROOT)).replace("\\", "/")
        except ValueError:
            rel = str(p)
        try:
            mt = p.stat().st_mtime
        except OSError:
            continue
        body = _read(p)
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        old = prev.get(rel)
        if not force and old and abs(old[0] - mt) < 0.001 and old[1] == sha:
            skipped += 1
            continue
        if old:
            updated += 1
        else:
            added += 1
        rows.append((t, rel, t, body))
        metas.append((rel, mt, sha))
    for t, key, body in _caps_docs():
        rows.append(("能力", key, key, body))
    # ⚠️ 血账（2026-09-27 实测）：**增量时不许整表清空** —— 早先 `DELETE FROM docs` 会把
    # 本次「跳过」（mtime+sha 未变）的文档一起删掉 ⇒ 二次索引后 docs 从 535 掉到 192（**丢索引**）。
    # 正确做法：只对**本次变化的** path 做「删旧行 + 插新行」。
    if rows:
        db.executemany("DELETE FROM docs WHERE path = ?", [(r[1],) for r in rows])
        db.executemany("INSERT INTO docs(type, path, label, body) VALUES (?,?,?,?)", rows)
    # 源文件消失了 ⇒ 索引里也要跟着消失（否则搜到的是幽灵）
    for (path_,) in db.execute("SELECT path FROM meta").fetchall():
        if path_ not in live_all and not path_.startswith("cap:"):
            db.execute("DELETE FROM docs WHERE path = ?", (path_,))
            db.execute("DELETE FROM meta WHERE path = ?", (path_,))
    db.executemany("INSERT OR REPLACE INTO meta(path, mtime, sha) VALUES (?,?,?)", metas)
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    by_type = dict(db.execute("SELECT type, COUNT(*) FROM docs GROUP BY type").fetchall())
    db.close()
    at = time.strftime("%Y-%m-%dT%H:%M:%S")
    _META.write_text(json.dumps({"at": at, "docs": n, "by_type": by_type, "added": added,
                                 "updated": updated, "skipped": skipped},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "op": "index", "docs": n, "by_type": by_type,
            "added": added, "updated": updated, "skipped": skipped, "at": at,
            "_口径": "**增量**：源文件 mtime+sha 未变则跳过；能力位每次重收（它们活在代码里）"}


def find(q: str = "", type: str = "", limit: int = 12, **_kw) -> dict:
    """**秒搜**：FTS5 全文（中文可检索）+ 高亮片段 + 类型 + 同场出现的**能力位**。"""
    if not _DB.is_file():
        return {"ok": False, "why": "还没有索引 ⇒ 先跑 run_task('memory_manager', {'op':'index'})"}
    t0 = time.perf_counter()
    db = sqlite3.connect(str(_DB))
    try:
        rows = db.execute(
            "SELECT type, path, label, snippet(docs, 3, '【', '】', ' … ', 14) FROM docs "
            "WHERE docs MATCH ? AND (? = '' OR type = ?) ORDER BY rank LIMIT ?",
            (q, type, type, int(limit)),
        ).fetchall()
    except sqlite3.OperationalError as e:
        db.close()
        return {"ok": False, "error": f"检索语法：{str(e)[:100]}（短语可用引号包起来）", "q": q}
    db.close()
    ms = (time.perf_counter() - t0) * 1000
    return {"ok": True, "op": "find", "q": q, "hits": len(rows), "ms": round(ms, 2),
            "results": [{"type": r[0], "path": r[1], "label": r[2], "snippet": r[3]} for r in rows],
            "capabilities": [{"kind": r[1].replace("cap:", ""), "why": "名字/描述命中 —— 能干这活的触手"}
                             for r in rows if r[0] == "能力"],
            "_口径": "查 FTS5 索引（**不扫盘**）；【】内是高亮命中；能力位命中 = 「匹配面出现的能力」"}


def store(text: str = "", title: str = "", **_kw) -> dict:
    """存一条记忆：过 filesystem_write 门 → 追加进 `memory/<当天>-随手记.md`（只增不删）。"""
    if not text.strip():
        return {"ok": False, "error": "text 不能为空", "fail_closed": True}
    try:
        from .. import auth_gate
        from ..security import policy as _policy
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        import gbt_allinone as _g                             # noqa: F401
        from gbt_allinone import auth_gate                    # type: ignore
        from gbt_allinone.security import policy as _policy   # type: ignore
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("filesystem_write", detail="memory_manager.store")
        if not gate.get("ok"):
            return {"ok": False, "denied": True, "gate": "filesystem_write",
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant")}
    p = _ROOT / "memory" / f"{time.strftime('%Y-%m-%d')}-随手记.md"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(p, "a", encoding="utf-8") as fh:
        if title:
            fh.write(f"\n## {title}（{stamp}）\n\n")
        fh.write(f"- {text.strip()}\n")
    return {"ok": True, "op": "store", "path": str(p.relative_to(_ROOT)), "at": stamp}


def stats(**_kw) -> dict:
    if not _DB.is_file():
        return {"ok": False, "why": "还没索引"}
    db = sqlite3.connect(str(_DB))
    n = db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    by = dict(db.execute("SELECT type, COUNT(*) FROM docs GROUP BY type").fetchall())
    db.close()
    meta = json.loads(_META.read_text(encoding="utf-8")) if _META.is_file() else {}
    return {"ok": True, "op": "stats", "docs": n, "by_type": by,
            "db_kb": round(_DB.stat().st_size / 1024, 1), "last_index": meta.get("at"),
            "_口径": "索引里同时含能力位（每根触手一行）⇒ 搜索能直接告诉你'谁能干这事'"}


def run_op(op: str = "stats", **params) -> dict:
    op = (op or "stats").lower()
    for name, fn in (("index", index), ("find", find), ("store", store), ("stats", stats)):
        if op == name:
            return fn(**params)
    return {"ok": False, "error": f"未知 op:{op}（index/find/store/stats）", "fail_closed": True}
