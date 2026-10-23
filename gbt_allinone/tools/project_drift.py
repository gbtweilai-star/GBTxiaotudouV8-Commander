# gbt-capability: project_drift
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""全项目变化监控（project_drift）—— 第三块监控：**从全局盯着整个项目在变什么**。

## 三块监控怎么分工（别互相冒充）
| 监控 | 回答的问题 | 实现 |
|---|---|---|
| 心跳（tentacle-pulse-check） | 每一根触手**还通不通**、多久 | 三层秒表 |
| 影响面（impact_check） | 我要动的这一刀，**会连带撞到谁** | wiring.json 邻接图 |
| **全控变化（本位）** | **整个项目从上次到现在变了什么、变得合不合理** | 基线快照 vs 现状 |

主人 2026-10-19：「多余监控还缺了一个全控变化，也就是要有一个看着整个项目变化的。」
这一位就是那一块 —— 它不回答"某处有没有病"，只回答"**谁动过、动得对不对**"。

## 为什么不是再造一个扫描器
仓里已经有基线，而且**有写手**：`outputs/repo-pack/files.jsonl`
（`repo-pack.py scan` 产出，308,075 件 / 33.41 GB，每件带 `bytes` / `mtime` / `sha16`）。
本位**不重复扫全仓去建基线**（那是几十 GB 的哈希，纯浪费）——它把那份清单收成自己的基线，
再在每次 `drift` 时**只 stat 一遍**，只对"大小或时间变了"的少数文件真算 sha16。
⇒ 变了的才算哈希，没变的一个字节都不读。

## 判据（哪算"异常变化"）
1. **在役/冻结面被动**（最重）：`holo_pet_w3/voice-theater/assets/`（在役 GLB）、
   `outputs/rig-fix/provenance-*/`（出处冻结件）、`gbt_allinone/security/`、`config/`、`.env`
2. **成批变动**：新增 > 500 或 删除 > 100（一条命令改掉半个仓，先停下来看）
3. **新增可执行件**：`.exe/.dll/.bat/.cmd/.ps1/.psm1`（可执行面自己长大 = 供应链风险）
4. **0 字节新件**（半成品落盘）
5. **基线过期**：基线超过 24 h ⇒ 读数必须带年龄，不许当"刚刚的事实"

## ops（全部纯读，除 baseline）
- `status` —— 基线在哪、多大、多旧、覆盖多少件
- `drift` —— 对比：新增/改动/删除/仅碰时间 四类 + 异常项 + 用时（**只读**）
- `baseline` —— 把现状冻结成新基线（**写盘 ⇒ 处理器层挂 filesystem_write**）
- `where` —— 落点
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

OPS = ("status", "drift", "baseline", "where")
ROOT = Path(__file__).resolve().parents[2]
DRIFT_DIR = ROOT / "state" / "drift"
BASELINE = DRIFT_DIR / "baseline.json"
PACK_FILES = ROOT / "outputs" / "repo-pack" / "files.jsonl"

# 与 repo-pack.py scan 同一口径（两处必须一致，否则"变了"会是口径差而不是真变化）
EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
EXEC_EXT = {".exe", ".dll", ".bat", ".cmd", ".ps1", ".psm1", ".com", ".scr"}
SENSITIVE_PREFIX = (
    "holo_pet_w3/voice-theater/assets/",
    "outputs/rig-fix/provenance",
    "gbt_allinone/security/",
    "config/",
    ".env",
)
MASS_ADD = 500
MASS_DEL = 100
STALE_S = 24 * 3600
HASH_BUDGET = 200           # 一次 drift 最多真算这么多件的 sha16（超了如实报"没算完"）
HASH_MAX_BYTES = 8 << 20    # 单件超过 8MB 不算（大件比值/比大小即可，别把监控拖成哈希作业）


def _is_reparse(p: str) -> bool:
    """Windows 的 junction/symlink 必须跳过：穿进去会把 .pylibs 之类当成本仓文件。"""
    try:
        st = os.lstat(p)
    except OSError:
        return False
    return bool(getattr(st, "st_file_attributes", 0) & 0x400) or os.path.islink(p)


def _sha16(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _walk_now() -> tuple:
    """stat 一遍全仓（不读内容）。返回 ({rel: [bytes, mtime]}, 扫不到的路径数, 用时)。

    留痕（2026-10-19 实测）：第一版用 `os.walk` + 每文件再 `os.stat`，30 万件要 2 分钟以上，
    作为"每小时一次"的监控太慢。改用 `os.scandir` 递归：DirEntry 自带 stat 缓存
    （Windows 上由 FindFirstFile 一次给出），省掉每件一次额外系统调用。
    junction / symlink 一律跳过（穿进 .pylibs 会把别人的仓当成本仓文件）。
    """
    t0 = time.time()
    seen, unreadable = {}, 0
    stack = [str(ROOT)]
    while stack:
        cur = stack.pop()
        try:
            it = os.scandir(cur)
        except OSError:
            unreadable += 1
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name in EXCLUDE_DIRS:
                            continue
                        # 重解析点（junction）不穿：REPARSE_POINT = 0x400
                        if getattr(e.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
                            continue
                        stack.append(e.path)
                        continue
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    unreadable += 1
                    continue
                try:
                    rel = str(Path(e.path).relative_to(ROOT)).replace("\\", "/")
                except ValueError:
                    continue
                seen[rel] = [int(st.st_size), int(st.st_mtime)]
    return seen, unreadable, time.time() - t0


def _load_baseline() -> tuple:
    if BASELINE.is_file():
        try:
            d = json.loads(BASELINE.read_text(encoding="utf-8"))
            return d, None
        except (OSError, ValueError) as e:
            return None, {"ok": False, "error": "baseline_corrupt", "why": str(e)}
    return None, None


def _baseline_from_pack() -> dict:
    """把 repo-pack 的 files.jsonl 收成基线（**不重新哈希**：那份清单已经带 sha16）。"""
    files, n = {}, 0
    pack_at = None
    with PACK_FILES.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            p = r.get("path")
            if not p:
                continue
            files[p] = [r.get("bytes"), r.get("mtime"), r.get("sha16")]
            n += 1
    summ = ROOT / "outputs" / "repo-pack" / "summary.json"
    if summ.is_file():
        try:
            pack_at = json.loads(summ.read_text(encoding="utf-8")).get("at")
        except ValueError:
            pack_at = None
    return {"at": pack_at or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": str(PACK_FILES.relative_to(ROOT)),
            "files": files, "count": n,
            "note": "基线来自 repo-pack 清单（带 sha16），不是重新哈希；source 与 at 就是它的出处"}


def _op_status() -> dict:
    base, err = _load_baseline()
    if err:
        return {"ok": False, "op": "status", **err}
    pack = PACK_FILES.is_file()
    if not base:
        return {"ok": True, "op": "status", "baseline": None,
                "可以建基线": True,
                "how": "op=baseline（先试 from_pack=true 用 repo-pack 清单，零哈希）",
                "repo_pack_清单": str(PACK_FILES.relative_to(ROOT)) if pack else "（不存在）",
                "verdict": "还没有基线 ⇒ 还不知道项目变没变（**这不是『没变化』**）"}
    at = base.get("at") or ""
    age = None
    try:
        age = time.time() - time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        pass
    return {"ok": True, "op": "status",
            "baseline": str(BASELINE.relative_to(ROOT)),
            "at": at, "age_s": round(age) if age is not None else None,
            "stale": bool(age is not None and age > STALE_S),
            "files": base.get("count") or len(base.get("files") or {}),
            "source": base.get("source"),
            "bytes": BASELINE.stat().st_size,
            "verdict": ("基线已过期（>24h）—— 读数必须带这个年龄" if age and age > STALE_S
                        else "基线新鲜")}


def _op_drift(top: int = 40, scope: str = "") -> dict:
    base, err = _load_baseline()
    if err:
        return {"ok": False, "op": "drift", **err}
    if not base:
        return {"ok": False, "op": "drift", "error": "no_baseline",
                "why": "还没有基线 ⇒ 无法判断『变了什么』（不许把没有基线念成没变化）",
                "how": "先跑 op=baseline"}
    old = base.get("files") or {}
    now, unreadable, walk_s = _walk_now()

    # 基线的 `at` 是**清单完成时刻**；而 repo-pack scan 是"可续跑 append"，
    # 早扫的文件带着更早的时刻 ⇒ 有些差异其实在基线那一秒就已经在了。
    # 判据：文件自己的 mtime 早于基线时刻 ⇒ 归"旧差异/基线漏收"，不当新变化报。**这是留痕，不是放宽。**
    try:
        base_ts = time.mktime(time.strptime(base.get("at") or "", "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        base_ts = None

    prefix = str(scope or "").replace("\\", "/")
    added, deleted, modified, touched = [], [], [], []
    predates = []
    hashed = 0
    hash_skipped = 0
    for rel, (nb, nm) in now.items():
        if prefix and not rel.startswith(prefix):
            continue
        prev = old.get(rel)
        if prev is None:
            row = {"path": rel, "bytes": nb}
            if base_ts is not None and nm <= base_ts:
                row["note"] = "mtime 早于基线 ⇒ 基线漏收了它（不是新增）"
                predates.append(row)
            else:
                added.append(row)
            continue
        pb, pm = prev[0], prev[1]
        psha = prev[2] if len(prev) > 2 else None
        if pb == nb and pm == nm:
            continue
        if base_ts is not None and nm <= base_ts:
            predates.append({"path": rel, "bytes_before": pb, "bytes_after": nb,
                             "note": "mtime 早于基线时刻 ⇒ 差异在基线那一秒就存在（清单是分批扫的）"})
            continue
        if pb != nb:
            modified.append({"path": rel, "bytes_before": pb, "bytes_after": nb})
            continue
        # 同大小、时间变了 ⇒ 只有真算哈希才能说"内容没变"（不然就是猜）
        if nb > HASH_MAX_BYTES:
            touched.append({"path": rel, "bytes": nb,
                            "note": "mtime 变了；单件 >8MB 不哈希，内容未验"})
            continue
        if hashed >= HASH_BUDGET:
            hash_skipped += 1
            touched.append({"path": rel, "bytes": nb, "note": "mtime 变了；哈希预算用完，未验内容"})
            continue
        hashed += 1
        try:
            nsha = _sha16(ROOT / rel)
        except OSError:
            touched.append({"path": rel, "bytes": nb, "note": "读不到，无法算哈希"})
            continue
        if psha and nsha != psha:
            modified.append({"path": rel, "bytes_before": pb, "bytes_after": nb,
                             "sha16_before": psha, "sha16_after": nsha})
        else:
            touched.append({"path": rel, "bytes": nb, "note": "内容未变（sha16 相同），只碰了时间"})
    for rel in old:
        if prefix and not rel.startswith(prefix):
            continue
        if rel not in now:
            deleted.append({"path": rel, "bytes_before": old[rel][0]})

    # ── 异常判定（不是"变了就有罪"：逐条给理由）──
    flags = []
    for item in added + modified:
        p = item["path"]
        ext = os.path.splitext(p)[1].lower()
        if ext in EXEC_EXT:
            flags.append({"级别": "高", "为什么": "新增/改动了可执行件", "path": p})
        if any(p == sp or p.startswith(sp) for sp in SENSITIVE_PREFIX):
            flags.append({"级别": "高", "为什么": "在役/冻结/敏感面被动", "path": p})
        if item in added and not item.get("bytes"):
            flags.append({"级别": "中", "为什么": "0 字节新件（半成品落盘）", "path": p})
    for item in deleted:
        p = item["path"]
        if any(p == sp or p.startswith(sp) for sp in SENSITIVE_PREFIX):
            flags.append({"级别": "高", "为什么": "在役/冻结/敏感面被删", "path": p})
    if len(added) > MASS_ADD:
        flags.append({"级别": "高", "为什么": "成批新增 %d 件（阈值 %d）" % (len(added), MASS_ADD),
                      "path": "(全仓)"})
    if len(deleted) > MASS_DEL:
        flags.append({"级别": "高", "为什么": "成批删除 %d 件（阈值 %d）" % (len(deleted), MASS_DEL),
                      "path": "(全仓)"})

    at = base.get("at") or ""
    age = None
    try:
        age = time.time() - time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        pass
    return {"ok": True, "op": "drift",
            "baseline_at": at,
            "baseline_age_s": round(age) if age is not None else None,
            "baseline_stale": bool(age is not None and age > STALE_S),
            "scope": prefix or "(全仓)",
            "scanned_now": len(now),
            "scanned_before": len(old),
            "unreadable": unreadable,
            "walk_s": round(walk_s, 2),
            "hash_checked": hashed,
            "hash_skipped": hash_skipped,
            "added_count": len(added), "modified_count": len(modified),
            "deleted_count": len(deleted), "touched_only_count": len(touched),
            "predates_baseline_count": len(predates),
            "added": added[:top], "modified": modified[:top],
            "deleted": deleted[:top], "touched_only": touched[:top],
            "predates_baseline": predates[:top],
            "flags": flags[:top],
            "verdict": ("没有变化" if not (added or modified or deleted)
                        else "变化：新增 %d · 改 %d · 删 %d · 仅碰时间 %d"
                             % (len(added), len(modified), len(deleted), len(touched))),
            "口径": "同大小、只变 mtime 的件，**只有算过 sha16 才敢说内容没变**；"
                    "哈希预算 %d 件/次，超了就如实写『未验内容』" % HASH_BUDGET}


def _op_baseline(from_pack: bool = True) -> dict:
    DRIFT_DIR.mkdir(parents=True, exist_ok=True)
    if from_pack:
        if not PACK_FILES.is_file():
            return {"ok": False, "op": "baseline", "error": "missing_pack_list",
                    "why": "没有 outputs/repo-pack/files.jsonl —— 先跑 repo-pack.py scan，"
                           "或改用 from_pack=false（现场 stat 建基线，带不了 sha16）"}
        data = _baseline_from_pack()
        data["mode"] = "from_pack"
    else:
        now, unreadable, walk_s = _walk_now()
        data = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "source": "live_stat", "mode": "live_stat",
                "files": {k: [v[0], v[1], None] for k, v in now.items()},
                "count": len(now), "unreadable": unreadable, "walk_s": round(walk_s, 2)}
    BASELINE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "op": "baseline",
            "path": str(BASELINE.relative_to(ROOT)),
            "mode": data.get("mode"), "at": data["at"],
            "files": data["count"], "source": data["source"],
            "bytes": BASELINE.stat().st_size,
            "note": ("基线来自 repo-pack 清单（带 sha16，零哈希）" if from_pack
                     else "基线来自现场 stat（**没有 sha16**：只能比值和大小，说不了内容变没变）")}


def _op_where() -> dict:
    return {"ok": True, "op": "where",
            "module": "gbt_allinone/tools/project_drift.py",
            "baseline": "state/drift/baseline.json",
            "基线来源": "outputs/repo-pack/files.jsonl（repo-pack.py scan 产出，带 sha16）",
            "cli": "py -3.14 tools/codex-scripts/drift.py  (零引号入口)",
            "同类不能冒充": ["selfscan（框架五维自检）", "impact_check（影响面）",
                             "inventory（盘点分类）", "file_hygiene（布局卫生）"]}


def _gate(what: str):
    """写面挂 filesystem_write（**不碰 security/policy.py**，与本仓其它位同一手法）。"""
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    got = auth_gate.check_and_consume("filesystem_write", detail=str(what)[:60])
    if got.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": got.get("error"), "how_to_grant": got.get("how_to_grant"),
            "why": "op=baseline 要写 state/drift/baseline.json —— 请主人在终端发票"}


def run_op(op: str = "status", **params) -> dict:
    op = str(op or "status").strip() or "status"
    if op not in OPS:
        return {"ok": False, "error": "unknown_op", "op": op, "ops": list(OPS),
                "why": "project_drift 没有这个 op —— 拒绝而不是悄悄当 status"}
    if op == "where":
        return _op_where()
    if op == "status":
        return _op_status()
    if op == "drift":
        return _op_drift(top=params.get("top", 40), scope=params.get("scope", ""))
    gated = _gate("project_drift/baseline")
    if gated:
        return {"op": "baseline", **gated}
    from_pack = params.get("from_pack", True)
    if isinstance(from_pack, str):
        from_pack = from_pack.strip().lower() not in ("0", "false", "no")
    return _op_baseline(from_pack=bool(from_pack))


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="全项目变化监控（project_drift）")
    ap.add_argument("op", nargs="?", default="status", choices=list(OPS))
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--scope", default="")
    ap.add_argument("--no-pack", action="store_true", help="baseline 时不用 repo-pack 清单")
    a = ap.parse_args(argv)
    out = run_op(a.op, top=a.top, scope=a.scope, from_pack=not a.no_pack)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
