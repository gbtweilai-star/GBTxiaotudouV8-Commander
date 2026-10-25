# -*- coding: utf-8 -*-
# gbt-capability: media-license
"""素材许可登记（native 能力位 `media_license`）—— 三方向流程台「家规第 2 条」的数据源。

## 为什么要有它

`media_flow` 的家规第 2 条：**没有许可的素材不许进成品格**。
可它原来的判据是 `license_ok = len(_files(licenses)) > 0` ——
**只要那个目录里有任意一个文件就算过**。这条判据有两个洞：

1. **一个空文件（甚至一个 `.gitkeep`）就能把 P0 消掉** —— 判据比它要守的规矩松；
2. 它**不认到具体素材**：`04-cut` 里有 6 个件，登记 1 条许可也算过 ——
   而"素材授权清单"（十道闸之一）问的恰恰是**每一件素材的授权**。

⇒ 本能力位把许可做成**逐件的账**：每件素材一条记录（**文件 + sha256 + 出处 + 授权 + 时间**），
落在 `projects/_shared/licenses/manifest.json`。
**sha256 是随手算的**（不是让人手抄的）—— 素材被换掉，旧记录立刻对不上，这就是判据的牙。

## 红线

1. **必填字段不许空**：`source`（从哪来）与 `license`（什么授权）为空 ⇒ **当场拒绝**。
   这不是形式主义：这两格空着的"许可记录"，比没有记录更坏 —— 它让人以为查过了。
2. **只登记盘上真有的文件**（在仓内 `projects/` 之下）；不给不存在的路径发许可。
3. **同一路径换了内容 ⇒ 旧记录作废**（sha256 对不上就报出来），不许新旧并存糊过去。
4. 写面只落在 `projects/_shared/licenses/`（**只此一处**）。

## 诚实边界

本能力位**只登记与核对**，**不判定授权是否真实/充分** —— 那是主人的事。
它保证的是：**每一件进来的素材，都有一条写着出处与授权的记录，且 sha256 与盘上一致。**
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_IMPL_VERSION = "1.0"

PROJ = _ROOT / "projects"
LIC_DIR = PROJ / "_shared" / "licenses"
MANIFEST = LIC_DIR / "manifest.json"


def _paths(root=None) -> tuple:
    """(仓库根, 许可目录, 账文件)。

    `root` 可传 —— **给测试用**：生产恒为仓库根，测试传临时目录，
    这样同一条判据在两种场景下都真被执行，而不是测试里绕开它（`audio_extract` 同款设计）。
    """
    r = Path(root).resolve() if root else _ROOT
    lic = r / "projects" / "_shared" / "licenses"
    return r, lic, lic / "manifest.json"

READ_OPS = ("status", "check", "list")
WRITE_OPS = ("register", "unregister")
WRITE_ROOTS = ("projects/_shared/licenses",)

# 三个方向的抽屉根（与本能力位同层的知识；判定"哪些格是成品格"仍以 media_flow 为准）
KIND_DIRS = ("short_video", "film", "music")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(manifest: Path) -> dict:
    if not manifest.is_file():
        return {"version": 1, "note": "素材许可账 —— 逐件登记（文件 + sha256 + 出处 + 授权）", "entries": []}
    try:
        d = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"version": 1, "entries": [], "_load_error": str(e)}
    d.setdefault("entries", [])
    return d


def _save(manifest: Path, d: dict) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    tmp = manifest.with_name(manifest.name + ".tmp")   # manifest.json.tmp（with_suffix 会吃掉 .json）
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(manifest)          # 原子替换：读到半个文件比读到旧文件更坏


def _rel(p: Path, root: Path) -> str:
    try:
        return p.resolve().relative_to(root).as_posix()
    except ValueError:
        return ""


def run(op: str = "status", **kw) -> dict:
    """万能插入口：`run_task("media_license", {"op": ..., ...})` 落到这里。"""
    op = str(op or "status")
    root, lic_dir, manifest = _paths(kw.get("root"))
    d = _load(manifest)
    entries = d.get("entries") or []

    if op == "status":
        files_in_dir = [p.name for p in lic_dir.iterdir() if p.is_file()] if lic_dir.is_dir() else []
        return {"ok": True, "impl": "media_license", "version": _IMPL_VERSION,
                "kind": "media_license", "domain": "video",
                "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
                "write_roots": list(WRITE_ROOTS),
                "manifest": _rel(manifest, root), "manifest_exists": manifest.is_file(),
                "entries": len(entries), "license_dir_files": len(files_in_dir),
                "honest": "只登记与核对；**不判定授权是否真实/充分** —— 那是主人的事。"
                          "它保证每一件素材都有一条写出处与授权的记录，且 sha256 与盘上一致。"}

    if op == "list":
        return {"ok": True, "entries": entries, "manifest": _rel(manifest, root)}

    if op == "register":
        f = kw.get("file") or kw.get("path")
        if not f:
            return {"ok": False, "error": "op=register 需要 file（素材路径）"}
        p = Path(f)
        ap = (p if p.is_absolute() else (root / p)).resolve()
        if not ap.is_file():
            return {"ok": False, "error": "盘上没有这个文件：%s（**不给不存在的路径发许可**）" % f}
        rel = _rel(ap, root)
        if not rel:
            return {"ok": False, "error": "**%s** 在仓库之外 —— 许可账只登记仓内素材" % ap}
        source = str(kw.get("source") or "").strip()
        lic = str(kw.get("license") or "").strip()
        if not source or not lic:
            missing = [n for n, v in (("source（从哪来）", source), ("license（什么授权）", lic)) if not v]
            return {"ok": False, "refused": True,
                    "error": "必填为空：%s ⇒ **拒绝登记**。空着的「许可记录」比没有记录更坏 —— "
                             "它让人以为查过了" % "、".join(missing)}
        sha = _sha256(ap)
        entry = {"file": rel, "sha256": sha, "bytes": ap.stat().st_size,
                 "source": source, "license": lic,
                 "note": str(kw.get("note") or ""), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        old = [e for e in entries if e.get("file") == rel]
        if old and old[0].get("sha256") == sha and old[0].get("source") == source:
            return {"ok": True, "out": _rel(manifest, root), "entry": entry, "changed": False,
                    "note": "这条记录已经在账上（同 sha256、同出处），未改动"}
        entries = [e for e in entries if e.get("file") != rel]
        entries.append(entry)
        # 🔴 第 101 轮修：原来是「**无锁读**（第 107 行）→ 改 → `_save`」——
        #    三条链**同时**跑时，两次 register 会各自读到同一份旧账，
        #    后写的**覆盖**先写的 ⇒ **丢登记**。丢了会怎样？闸门当场报
        #    「成品格许可**没记到件**」⇒ 既是真丢数据、也是一条**假红**。
        #    （`_save` 的原子替换只保证"不读到半个文件"，**保证不了"不丢更新"**。）
        #    ⇒ 用仓里**已有**的 `locked_json_update`（跨进程协作锁：Windows msvcrt / POSIX fcntl）
        #      把**读-改-写整段**锁起来。**不另造锁。**
        from ..safe_io import locked_json_update

        def _mut(cur):
            cur = cur if isinstance(cur, dict) else {}
            es = [e for e in (cur.get("entries") or []) if e.get("file") != rel]
            es.append(entry)
            cur["entries"] = sorted(es, key=lambda e: e.get("file", ""))
            cur["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            return cur

        try:
            locked_json_update(manifest, {"entries": []}, _mut)
        except Exception as e:                                        # noqa: BLE001
            return {"ok": False, "error": "加锁写入失败：%s: %s"
                                          % (type(e).__name__, str(e)[:90])}
        # 回读**落盘后的真账**：报告的条数必须是盘上的，不是我手里那本的
        after = _load(manifest)
        return {"ok": True, "out": _rel(manifest, root), "entry": entry, "changed": True,
                "entries_on_disk": len(after.get("entries") or []),
                "replaced": bool(old), "locked": True,
                "note": ("替换了旧记录（同路径内容已变）" if old else "新登记")
                        + "；写入走 `locked_json_update`（并发安全）"}

    if op == "unregister":
        # 一笔**能改的账**才是账：删错了、素材退了、登记错了，都要能撤。
        # 但撤也**要写理由**（`why`）—— 否则"这条记录怎么没了"就查不出来。
        rel = str(kw.get("file") or kw.get("path") or "").replace("\\", "/")
        why = str(kw.get("why") or "").strip()
        if not rel:
            return {"ok": False, "error": "op=unregister 需要 file"}
        if not why:
            return {"ok": False, "refused": True,
                    "error": "撤销登记必须写 `why`（为什么撤）—— 否则账上少了一条却查不出原因"}
        hit = [e for e in entries if e.get("file") == rel]
        if not hit:
            return {"ok": False, "error": "账上没有这条：%s" % rel}
        entries = [e for e in entries if e.get("file") != rel]
        d["entries"] = entries
        d.setdefault("removed", []).append(
            {"file": rel, "why": why, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        d["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        # 🔴 第 103 轮修：这一支原来是**同一个病** —— 无锁读 → 改 → `_save`。
        #    并发撤销会互相覆盖 `removed`（留档丢笔），也会把**别人刚登记的条目**一起写没。
        #    ⇒ 与 `register` 同法：走仓里已有的 `locked_json_update`，
        #      并且**在锁内**重新确认"账上还有没有这条"（上面的 hit 是锁外的快照，不作数）。
        from ..safe_io import locked_json_update
        seen = {"hit": False}

        def _mut(cur):
            cur = cur if isinstance(cur, dict) else {}
            es = list(cur.get("entries") or [])
            seen["hit"] = any(e.get("file") == rel for e in es)
            cur["entries"] = [e for e in es if e.get("file") != rel]
            cur.setdefault("removed", []).append(
                {"file": rel, "why": why, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
            cur["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            return cur

        try:
            locked_json_update(manifest, {"entries": []}, _mut)
        except Exception as e:                                        # noqa: BLE001
            return {"ok": False, "error": "加锁写入失败：%s: %s"
                                          % (type(e).__name__, str(e)[:90])}
        after = _load(manifest)
        return {"ok": True, "removed": rel, "why": why, "locked": True,
                "in_ledger_when_locked": seen["hit"],
                "entries": len(after.get("entries") or []),
                "note": "撤销记录留档在 `removed` 里 —— **不是删掉，是记账**"
                        "；写入走 `locked_json_update`（并发安全）"}

    if op == "check":
        # 两件事：① 账上有、盘上没了（陈旧）或内容变了（sha 对不上）；② 仓内有、账上没有（漏登）
        by_file = {e.get("file"): e for e in entries}
        stale, mismatch = [], []
        for rel, e in by_file.items():
            p = root / rel
            if not p.is_file():
                stale.append(rel)
                continue
            if _sha256(p) != e.get("sha256"):
                mismatch.append(rel)
        licensed = set(by_file)
        unregistered = []
        for kd in KIND_DIRS:
            base = root / "projects" / kd
            if not base.is_dir():
                continue
            for dp, _dn, fn in _walk(base):
                for name in fn:
                    rel = _rel(Path(dp) / name, root)
                    if rel and rel not in licensed:
                        unregistered.append(rel)
        ok = not stale and not mismatch
        return {"ok": ok, "entries": len(entries),
                "stale": sorted(stale), "sha_mismatch": sorted(mismatch),
                "unregistered": sorted(unregistered),
                "note": ("账与盘一致" if ok else "🔴 账与盘对不上（上面 stale / sha_mismatch）")
                        + " ｜ `unregistered` **不算本器的红**：它只说「这些素材还没有许可记录」，"
                          "要不要它们进成品格由 media_flow 的门说话 —— **本器不越权判**。"}

    return {"ok": False, "error": "不认的 op：%s（读 %s / 写 %s）"
                                 % (op, "/".join(READ_OPS), "/".join(WRITE_OPS))}


def _walk(base: Path):
    import os
    for dp, dn, fn in os.walk(base):
        dn[:] = [x for x in dn if x not in ("__pycache__",)]
        yield dp, dn, fn
