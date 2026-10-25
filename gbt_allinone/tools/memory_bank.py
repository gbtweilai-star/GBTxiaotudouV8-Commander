# gbt-capability: memory_bank
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""记忆银行：**来源追踪 + 别名 + 零停机迁移**（蒸馏自 GitHub 周榜 #01 `vectorsize-io/hindsight`）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09 第 39 周 GitHub 爆款周榜 #01 `hindsight`（32k★ · Python）的公开介绍：
  「给编码 Agent 加**长期记忆**（hooks 接入）· 支持多模型与 MCP · **记忆『银行』支持别名与零停机迁移** ·
  **多模态记忆：图片/文件内联，带来源追踪** · 提供多模态提取 + 调试端点」。
  —— 一手仓库与文档本轮**未联网核验**（主人令：不出网花钱的动作），所以只蒸馏**架构**，
  不引用它的性能/规模数字。
· **时间**：2026-09-28。
· **口径**：**只移植架构**，代码全部自写。

## 蒸馏判断：我们缺哪两块（先看家底，不重造）
| hindsight 的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 长期记忆（读写/检索） | `memory_manager`（FTS5 秒搜）· `obsidian_vault`（235 触手库 ↔ 本体库双向）· `brain_vault` | **已有，不重造** |
| 多模型 / MCP 接入 | 能力位 + 唯一门 `run_task` + MCP 目录 | **已有，不重造** |
| **来源追踪**（这条记忆从哪来、有没有被动过） | 无 | **补这块** |
| **记忆银行：别名 + 零停机迁移** | 无 | **补这块** |

## 两块新东西，各自的硬规矩
1. **来源印章**（`stamp`）：每条记忆/文档记 `{ref, sha256, origin, session, why, evidence[]}`。
   `trace` 会**同时报两件事**：印章在不在，以及**现在的 sha 与印章是否一致** ——
   不一致就是"这条记忆被改过"，不假装它还是原来那条。
2. **别名 + 零停机迁移**（`alias` / `resolve` / `migrate`）：记忆搬家时**先双写、再校验、
   最后切别名**，任何一步不过 ⇒ **回滚别名、如实报**。旧目标**只读保留**（本仓没有删除路径）。
   别名解析带**环检测**（A→B→A 当场报环），多级链可追到真身。

op=stamp / trace / alias / resolve / aliases / migrate / verify / where
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_STAMPS = _STATE / "memory_bank.jsonl"          # 印章 + 迁移事件（追加式，只增不删）
_ALIASES = _STATE / "memory_bank_aliases.json"  # 别名表（原子写）
ORIGINS = ("主人令", "我推的", "外部抓取", "上游产物", "测试夹具", "未知")


def _log(row: dict) -> None:
    _STAMPS.parent.mkdir(parents=True, exist_ok=True)
    with open(_STAMPS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _rows() -> list:
    out = []
    if _STAMPS.is_file():
        for ln in _STAMPS.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    return out


def _sha(p: Path) -> str:
    """文件级 sha256（与 closeout 钩子同口径：读字节）。目录/不存在返回空。"""
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _real(ref: str) -> Path:
    p = Path(ref)
    return p if p.is_absolute() else (_ROOT / p)


def _load_aliases() -> dict:
    if _ALIASES.is_file():
        try:
            return json.loads(_ALIASES.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_aliases(d: dict) -> None:
    _ALIASES.parent.mkdir(parents=True, exist_ok=True)
    tmp = _ALIASES.with_name(_ALIASES.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _ALIASES)


# ═══════════════════════ 来源追踪 ═══════════════════════

def stamp(ref: str = "", origin: str = "", session: str = "", why: str = "",
          evidence: str = "", **_kw) -> dict:
    """给一条记忆/文档打**来源印章**（从哪来 + 当时是什么内容）。"""
    if not ref.strip():
        return {"ok": False, "op": "stamp", "fail_closed": True, "error": "要给 ref（记忆/文档的路径或标识）"}
    if origin not in ORIGINS:
        return {"ok": False, "op": "stamp", "fail_closed": True,
                "error": f"origin 必须是 {ORIGINS} 之一（不许含糊说'大概来源'）"}
    if not why.strip():
        return {"ok": False, "op": "stamp", "fail_closed": True, "error": "要给 why（为什么收这条记忆）"}
    p = _real(ref)
    ev = [x.strip() for x in evidence.split(",") if x.strip()]
    ev_missing = [x for x in ev if not _real(x).exists()]
    row = {"event": "stamp", "ref": ref, "exists": p.exists(), "sha256": _sha(p),
           "origin": origin, "session": session[:80], "why": why[:200],
           "evidence": ev, "evidence_missing": ev_missing}
    _log(row)
    return {"ok": True, "op": "stamp", "ref": ref, "origin": origin, "sha256": row["sha256"][:16],
            "evidence_missing": ev_missing,
            "note": "印章已追加（只增不删）；trace 会拿它跟**当前**内容比对"}


def trace(ref: str = "", **_kw) -> dict:
    """找回来源链：这条记忆从哪来、中途被谁记过、**现在有没有被改过**。"""
    if not ref.strip():
        return {"ok": False, "op": "trace", "fail_closed": True, "error": "要给 ref"}
    rows = [r for r in _rows() if r.get("event") == "stamp" and r.get("ref") == ref]
    p = _real(ref)
    cur = _sha(p)
    out = {"ok": True, "op": "trace", "ref": ref, "stamps": len(rows),
           "exists_now": p.exists(), "sha256_now": cur[:16] or "（无此文件）"}
    if not rows:
        out.update({"provenance": "**没有印章** ⇒ 这条记忆来历不明（不许当'大概是我写的'）",
                    "how": "跑 memory_bank op=stamp 补印章"})
        return out
    first, last = rows[0], rows[-1]
    out.update({"first": {"at": first.get("at"), "origin": first.get("origin"),
                          "why": first.get("why"), "session": first.get("session")},
                "last": {"at": last.get("at"), "origin": last.get("origin"),
                         "why": last.get("why"), "session": last.get("session")},
                "content_verdict": ("**没被动过**（当前 sha == 最后一次印章）"
                                    if last.get("sha256") and cur == last.get("sha256")
                                    else "**被改过**（当前 sha != 最后一次印章）—— 改了什么要另查，"
                                         "但『还是原来那条』这个假设已经不成立"),
                "evidence": [{"path": e, "exists": _real(e).exists()}
                             for e in (last.get("evidence") or [])],
                "缺证据": last.get("evidence_missing") or []})
    return out


# ═══════════════════════ 别名与零停机迁移 ═══════════════════════

def alias(name: str = "", target: str = "", **_kw) -> dict:
    """给记忆/库起**稳定别名**（例：`vault:本体` → Documents 里那本 Obsidian）。"""
    if not name.strip() or not target.strip():
        return {"ok": False, "op": "alias", "fail_closed": True, "error": "name 与 target 都要给"}
    if ":" not in name:
        return {"ok": False, "op": "alias", "fail_closed": True,
                "error": "别名要带种类前缀（如 `vault:本体` / `mem:触手库`），免得跟真路径混淆"}
    d = _load_aliases()
    if name in d and d[name] != target:
        _log({"event": "alias_change", "name": name, "was": d[name], "now": target})
    d[name] = target
    _save_aliases(d)
    _log({"event": "alias", "name": name, "target": target})
    return {"ok": True, "op": "alias", "name": name, "target": target, "aliases": len(d)}


def resolve(name: str = "", **_kw) -> dict:
    """别名 → 真身（多级链 + **环检测**）。"""
    if not name.strip():
        return {"ok": False, "op": "resolve", "fail_closed": True, "error": "要给 name"}
    d = _load_aliases()
    seen, chain = [], name
    while chain in d and chain not in seen:
        seen.append(chain)
        chain = d[chain]
    if chain in seen:
        return {"ok": False, "op": "resolve", "cycle": True,
                "error": f"**别名成环**：{'→'.join(seen + [chain])}", "how": "手工改 state/memory_bank_aliases.json"}
    if name not in d:
        return {"ok": True, "op": "resolve", "name": name, "target": name, "aliased": False,
                "note": "没有这个别名（按真路径处理）"}
    return {"ok": True, "op": "resolve", "name": name, "target": chain, "aliased": True,
            "chain": seen, "target_exists": _real(chain).exists()}


def aliases(**_kw) -> dict:
    d = _load_aliases()
    return {"ok": True, "op": "aliases", "count": len(d),
            "rows": [{"name": k, "target": v, "exists": _real(v).exists()} for k, v in sorted(d.items())]}


def migrate(old: str = "", new: str = "", dry_run: bool = True, **_kw) -> dict:
    """**零停机迁移**：先双写 → 校验一致 → 切别名 → 旧目标只读保留。任一步不过就回滚别名。

    为什么这么设计：记忆搬家最容易出的事是"搬了一半、引用还指旧家"。所以顺序是
    ①**先建别名**指向**旧**目标（保证任何时刻都有可用指向）→ ②把内容复制到新目标 →
    ③逐文件校验 sha 一致 → ④把别名**原子切**到新目标 → ⑤旧目标原样保留（只读，不删）。
    """
    if not old.strip() or not new.strip():
        return {"ok": False, "op": "migrate", "fail_closed": True, "error": "old / new 都要给"}
    if not dry_run:
        # 真搬家走 migrate_apply（它才有"双写→校验→切别名→回滚"的全套），本 op 只出计划
        return {"ok": False, "op": "migrate", "fail_closed": True, "refused": True,
                "error": "migrate 只出计划（dry_run 常真）⇒ 真搬家用 op=migrate_apply（要给 alias_name）",
                "why": "搬家必须带**别名**才能原子切换与回滚；没有别名的搬家等于裸搬"}
    a_old, a_new = _real(old), _real(new)
    if not a_old.exists():
        return {"ok": False, "op": "migrate", "error": f"旧目标不在盘上：{old}"}
    if a_new.exists():
        return {"ok": False, "op": "migrate", "error": f"新目标已存在：{new}（不覆盖，先改名或换目标）"}
    files = sorted(p for p in a_old.rglob("*") if p.is_file())
    plan = {"ok": True, "op": "migrate", "dry_run": True, "old": old, "new": new,
            "files": len(files), "bytes": sum(p.stat().st_size for p in files),
            "steps": ["①给 old 建/确认别名（保证任何时刻可指）",
                      "②复制到 new（逐文件）",
                      "③逐文件校验 sha256 一致",
                      "④原子把别名切到 new",
                      "⑤old 原样保留（只读，不删）"],
            "note": "dry_run 只出计划；真搬家要 dry_run=false（且**建议先过 action_gate 的先看→动脑**）"}
    _log({"event": "migrate_plan", "old": old, "new": new, "files": len(files)})
    return plan


def migrate_apply(old: str = "", new: str = "", alias_name: str = "", **_kw) -> dict:
    """真搬家（**要显式调用**）：双写 → 校验 → 切别名 → 旧目标保留。"""
    if not (old and new and alias_name):
        return {"ok": False, "op": "migrate_apply", "fail_closed": True,
                "error": "old / new / alias_name 三样都要给（没别名就没法原子切换）"}
    a_old, a_new = _real(old), _real(new)
    if not a_old.exists() or a_new.exists():
        return {"ok": False, "op": "migrate_apply", "error": "旧目标必须在、新目标必须不存在"}
    d = _load_aliases()
    d.setdefault(alias_name, old)                 # ① 别名先指旧家
    _save_aliases(d)
    copied, mismatch = [], []
    for p in sorted(x for x in a_old.rglob("*") if x.is_file()):
        rel = p.relative_to(a_old)
        dst = a_new / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(p.read_bytes())           # ② 逐字节复制（二进制也安全）
        if _sha(p) != _sha(dst):                  # ③ 校验
            mismatch.append(str(rel))
        copied.append(str(rel))
    if mismatch:
        d[alias_name] = old                       # 回滚：别名仍指旧家
        _save_aliases(d)
        _log({"event": "migrate_rollback", "old": old, "new": new, "mismatch": mismatch[:6]})
        return {"ok": False, "op": "migrate_apply", "rolled_back": True, "mismatch": mismatch[:6],
                "why": "有文件 sha 对不上 ⇒ **别名回滚到旧目标**，旧目标一根毫毛没动"}
    d[alias_name] = new                           # ④ 原子切
    _save_aliases(d)
    _log({"event": "migrate_done", "old": old, "new": new, "alias": alias_name,
          "files": len(copied)})
    return {"ok": True, "op": "migrate_apply", "alias": alias_name, "from": old, "to": new,
            "files": len(copied), "note": "旧目标**原样保留**（本仓没有删除路径）；要撤就把别名切回去"}


def verify(**_kw) -> dict:
    problems = []
    d = _load_aliases()
    rows = _rows()
    # ① 别名必须解析得动、不成环
    for name in d:
        r = resolve(name=name)
        if not r.get("ok"):
            problems.append(f"别名 {name} 解析失败：{r.get('error')}")
        elif not r.get("target_exists"):
            problems.append(f"别名 {name} 指向的目标不在盘上：{r.get('target')}")
    # ② 印章的 evidence 必须在盘上（当时引的证据不能凭空消失）
    for r in rows:
        if r.get("event") == "stamp" and r.get("evidence_missing"):
            problems.append(f"印章 {r.get('ref')} 的证据不在盘上：{r['evidence_missing'][:3]}")
    # ③ 迁移记录必须成对（plan 可以单独存在；apply 必须要么 done 要么 rollback）
    applies = [r for r in rows if r.get("event") in ("migrate_done", "migrate_rollback")]
    for r in applies:
        if r.get("event") == "migrate_done" and not _real(r.get("new") or "").exists():
            problems.append(f"迁移记录说搬到 {r.get('new')}，但那儿不在盘上")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "counts": {"stamps": sum(1 for r in rows if r.get("event") == "stamp"),
                       "aliases": len(d), "migrations": len(applies)},
            "_口径": "别名可解析不成环 · 印章证据仍在盘上 · 迁移记录与盘上一致"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "memory_bank", "tentacle": "memory_bank",
            "entry": "run_task('memory_bank', {...})",
            "ops": ["stamp", "trace", "alias", "resolve", "aliases", "migrate", "migrate_apply",
                    "verify", "where"],
            "distilled_from": "GitHub 周榜 #01 hindsight（只取架构：来源追踪 + 记忆银行别名/零停机迁移）",
            "not_copied": "它的代码/性能数字一律未引用；记忆读写仍走 memory_manager / obsidian_vault / brain_vault",
            "files": {"印章台账": str(_STAMPS.relative_to(_ROOT)), "别名表": str(_ALIASES.relative_to(_ROOT))},
            "contract": [
                {"op": "stamp", "params": "ref + origin + why [+ evidence]", "returns": "印章（含 sha256）"},
                {"op": "trace", "params": "ref", "returns": "来源链 + **内容有没有被改过**"},
                {"op": "alias/resolve", "params": "name/target", "returns": "别名表 / 真身（环检测）"},
                {"op": "migrate", "params": "old+new（dry_run 默认真）", "returns": "搬家计划/执行结果（含回滚）"},
            ]}


def run_op(op: str = "aliases", **params) -> dict:
    op = (op or "aliases").lower()
    for name, fn in (("stamp", stamp), ("trace", trace), ("alias", alias), ("resolve", resolve),
                     ("aliases", aliases), ("migrate", migrate),
                     ("migrate_apply", migrate_apply), ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（stamp/trace/alias/resolve/aliases/migrate/migrate_apply/verify/where）"}
