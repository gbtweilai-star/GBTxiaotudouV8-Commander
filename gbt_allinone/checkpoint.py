#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 阶段级检查点打点器（《阶段检查点打点器设计》§五 的实现）

打点器只干一件事：在每个阶段开始之前，把"此刻的维度 + 现实 + 时间线版本号"
冻成一份可回滚的实物，并让「没打点」和「打点坏了」不可能被读成没问题。

用法：
  py -3.10 checkpoint.py --checkpoint --phase P07-03 [--goal "一句话目标"]
  py -3.10 checkpoint.py --status
  py -3.10 checkpoint.py --diff [<checkpoint_id>]
  py -3.10 checkpoint.py --restore [<checkpoint_id>] [--go]
  py -3.10 checkpoint.py --selftest [--out FILE]

退出码（退出码即结论）：
  0   成功 / 可用
  10  缺失（灰：没有检查点）
  11  损坏（有记录但不可用）
  12  自盲（CHECKPOINT_BLIND：真的不知道）
  13  完整性失败（撕裂拷贝 / 恢复校验不过）
  22  本次没有结论（锁被占 / 未指定动作 / 存储路径不可用 / 缺 phase_id）

族约定：0 成功 · 10-19 本工具裁决 · 20/21 探针族专用（不许复用）· 22 没有结论。

红线：对 dimension / reality **只读**，只写 checkpoints/ 与本工具审计；
      不写 timelines/、不写护照、不动版本号（rewind() 那条老路径必须始终有效）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

RC_OK = 0
RC_MISSING = 10
RC_DAMAGED = 11
RC_BLIND = 12
RC_INTEGRITY = 13
RC_NO_VERDICT = 22

HERE = Path(__file__).resolve().parent


class Blind(Exception):
    """自盲：路径读不到 / 枚举抛错 / 指纹函数坏 —— 「抓不到」不等于「没有」。"""


class Damaged(Exception):
    """损坏：有记录，但记录/副本不可用。"""


def _load_sibling(name: str):
    """按路径加载同目录的叶子模块（与 tests/test_mirror_space.py 同路：
    避开 gbt_allinone 包的重依赖，保证隔离开的与要落的跑的是同一份代码）。"""
    path = HERE / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"gbt_ckpt_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Paths:
    """所有路径的唯一来源（测试可显式注入，绝不隐式落到生产 store）。"""

    def __init__(self, store: Path):
        self.store = Path(store).resolve()
        self.mirror = self.store / "mirror_space"
        self.dimension = self.mirror / "dimension"
        self.reality = self.mirror / "reality"
        self.passports = self.mirror / "passports"
        self.timelines = self.mirror / "timelines"
        self.checkpoints = self.mirror / "checkpoints"
        self.audit = self.store / "audit.jsonl"


def resolve_store_dir(cli_store: str | None = None) -> Path:
    """store 基址：CLI > GBT_STORE_DIR（既有隔离机制）> gbt_allinone/store。"""
    if cli_store:
        return Path(cli_store).resolve()
    env = os.getenv("GBT_STORE_DIR")
    if env:
        return Path(env).resolve()
    return (HERE / "store").resolve()


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _ms(t0: float) -> float:
    return round((time.monotonic() - t0) * 1000, 1)


# ── 指纹（口径与 mirror_space 同源，不另立第二套）──


def tree_fingerprint(root: Path) -> dict:
    MS = _load_sibling("mirror_space")
    fn = getattr(MS, "tree_fingerprint", None)
    if fn is None:
        raise Blind("mirror_space.tree_fingerprint 公开别名缺失（设计 §九② 未落）")
    return fn(Path(root))


def tree_hash(fp: dict) -> str:
    canon = json.dumps(fp, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def bind_mirror(paths: Paths):
    """把 mirror_space 的路径常量绑到本工具解析出的路径上，好复用它的漂移口径。
    生产下这与它自带的常量完全一致，是幂等操作。"""
    MS = _load_sibling("mirror_space")
    MS._DIM = paths.dimension
    MS._REALITY = paths.reality
    MS._TIMELINES = paths.timelines
    MS._PASSPORTS = paths.passports
    return MS


def drift_snapshot(paths: Paths) -> tuple[list, list]:
    """复用 mirror_status() 的漂移口径（not_yet_promoted / production_extra / diverged）。"""
    MS = bind_mirror(paths)
    st = MS.mirror_status()
    return list(st.get("dimension_vs_reality") or []), list(st.get("reality_drift") or [])


def timeline_version(paths: Paths) -> int:
    if not paths.passports.exists():
        return 0
    nums = []
    try:
        for p in paths.passports.glob("v*.json"):
            stem = p.stem[1:]
            if stem.isdigit():
                nums.append(int(stem))
    except OSError as exc:
        raise Blind(f"护照目录枚举失败: {exc}") from exc
    return max(nums) if nums else 0


# ── 生产树指纹（规格：docs/checkpoint生产树指纹规格.md v1）──
#
# 00001 冻的是镜像维度 + reality，覆盖不到生产树；而"改落在生产树"的批次
# （面板层第一刀改的正是 holo_pet/）回滚凭据只有文件级备份。
# 备份是文件级、checkpoint 是世界级 —— 这一节补的就是世界级那一半：
# **只打指纹，不拷文件**。

PROD_MANIFEST_NAME = "production_tree_manifest.json"
PROD_TREE_SCHEMA = "production-tree-manifest/1"
PROD_TREE_ROOTS = ("holo_pet", "gbt_allinone", "potato_pet", "config")
# 排除规则写"为什么"，不写死路径：将来 vendored 依赖迁移，改**这一行**，不改判据。
PROD_TREE_EXCLUDE_RULES = (
    ("node_modules", "第三方 JS 依赖（体积大、可重装，不属于手写源码）"),
    ("__pycache__", "派生文件（可从源码重算）"),
    (".git", "独立性：manifest 不该把版本库本身算进去"),
    (".scratch", "一次性工作区（备份/暂存/探针产物，按设计天天变）"),
    ("store", "账本与生活档案自身高频写，指纹无意义且会天天漂"),
    (".pylibs", "排除 pip 生成的 vendored 依赖目录：不是手写源码、由 pip 管理（可重装）、"
                "不在 git 索引；当前落点 .pylibs/，将来迁移则规则跟随"),
)
PROD_TREE_EXCLUDED_DIRS = tuple(name for name, _why in PROD_TREE_EXCLUDE_RULES)
PROD_TREE_MAX_BYTES = 5 * 1024 * 1024


def production_root() -> Path:
    """生产树根：GBT_PROD_ROOT（测试隔离） > 本工具所在包的上一级（仓库根）。

    与 `resolve_store_dir()` 同构 —— 测试一律显式注入，绝不隐式打真实生产树。
    """
    env = os.getenv("GBT_PROD_ROOT")
    if env:
        return Path(env).resolve()
    return HERE.parent


def _tz_offset_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def production_tree_manifest(root: Path) -> dict:
    """对生产树**只读**打指纹：只枚举、只读字节，一个字节都不写。

    抓不到不许静默（《空不等于不存在律》）：白名单根缺失 → `missing_roots` 显式登记；
    枚举抛错 → 抛 Blind（连"有没有"都不知道，不能报成"没有"）。
    """
    root = Path(root).resolve()
    files: list[dict] = []
    skipped: list[dict] = []
    missing: list[str] = []
    excluded: list[str] = []
    total = 0
    for name in PROD_TREE_ROOTS:
        base = root / name
        if not base.exists():
            missing.append(name)
            continue
        try:
            walker = sorted(base.rglob("*"))
        except OSError as exc:
            raise Blind(f"生产树枚举失败: {name}: {exc}") from exc
        for f in walker:
            try:
                if not f.is_file():
                    continue
            except OSError as exc:
                raise Blind(f"生产树条目读不到: {f}: {exc}") from exc
            rel = f.relative_to(root).as_posix()
            parts = rel.split("/")
            hit = next((d for d in parts[:-1] if d in PROD_TREE_EXCLUDED_DIRS), None)
            if hit:
                if hit not in excluded:
                    excluded.append(hit)
                continue
            st = f.stat()
            if st.st_size > PROD_TREE_MAX_BYTES:
                skipped.append({"path": rel, "bytes": st.st_size,
                                "reason": "skipped_too_large"})
                continue
            files.append({"path": rel, "bytes": st.st_size,
                          "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                          "mtime": _tz_offset_iso(st.st_mtime)})
            total += st.st_size
    files.sort(key=lambda x: x["path"])
    skipped.sort(key=lambda x: x["path"])
    return {
        "schema": PROD_TREE_SCHEMA,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": root.as_posix(),
        "root_source": ("GBT_PROD_ROOT" if os.getenv("GBT_PROD_ROOT") else "package_parent"),
        "files": files,
        "summary": {"files": len(files), "bytes": total,
                    "skipped_too_large": skipped,
                    "excluded_dirs": sorted(excluded),
                    "exclude_rules": [{"dir": d, "reason": why}
                                      for d, why in PROD_TREE_EXCLUDE_RULES],
                    "missing_roots": missing},
    }


def production_tree_drift(paths: Paths, rec: dict) -> dict:
    """只读复算（规格 §三.3）：重算生产树指纹，与检查点里的 manifest 对比。

    差异词汇用 added / removed / modified —— 与 dimension·reality 那套
    （production_extra / not_yet_promoted / diverged）**不同轴**，不硬套。
    """
    info = rec.get("production_tree_manifest")
    mpath = Path(rec["_dir"]) / PROD_MANIFEST_NAME
    if not mpath.exists():
        return {"ok": False, "state": "MISSING",
                "detail": "本检查点没有 production_tree_manifest.json",
                "recorded": info}
    man = json.loads(mpath.read_text(encoding="utf-8"))
    root = Path(man.get("root") or production_root())
    now = production_tree_manifest(root)
    want = {f["path"]: f for f in man.get("files") or []}
    got = {f["path"]: f for f in now.get("files") or []}
    drift = []
    for p in sorted(set(want) | set(got)):
        a, b = want.get(p), got.get(p)
        if a is None:
            drift.append({"file": p, "kind": "added", "detail": "检查点之后新增"})
        elif b is None:
            drift.append({"file": p, "kind": "removed", "detail": "检查点之后被删"})
        elif a.get("sha256") != b.get("sha256") or a.get("bytes") != b.get("bytes"):
            drift.append({"file": p, "kind": "modified", "detail": "检查点之后被改"})
    return {"ok": True, "state": "OK", "root": root.as_posix(),
            "files": len(got), "drift": drift, "drift_count": len(drift),
            "missing_roots": now["summary"]["missing_roots"],
            "skipped_too_large": len(now["summary"]["skipped_too_large"]),
            "recorded": info}


# ── 审计（形状与 store.audit 一致，落 <store>/audit.jsonl）──


def audit(paths: Paths, event: str, meta: dict) -> None:
    rec = {"ts": round(time.time(), 3), "iso": now_iso(), "event": event, "meta": meta or {}}
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    try:
        SIO = _load_sibling("safe_io")
        SIO.locked_append_text(paths.audit, line, align_to_existing=True)
    except Exception as exc:  # noqa: BLE001
        print("WARN 审计写入失败（本地记录，不影响结论）: %s: %s" % (type(exc).__name__, exc))


# ── 检查点读取 ──


def load_records(paths: Paths) -> tuple[list, list]:
    """返回 (records, unrecognized)。自盲抛 Blind；损坏抛 Damaged。
    真相源 = 每个 <seq>/record.json；目录名只是序号。"""
    if not paths.mirror.exists():
        raise Blind(f"镜像空间不存在: {paths.mirror}")
    cps = paths.checkpoints
    if not cps.exists():
        return [], []          # 镜像在、从没打过点 → 缺失(灰)，不是自盲
    try:
        entries = sorted(cps.iterdir(), key=lambda p: p.name)
    except OSError as exc:
        raise Blind(f"检查点目录枚举失败: {exc}") from exc

    records, unrecognized = [], []
    for ent in entries:
        if ent.name == ".lock":
            continue
        if not ent.is_dir() or not ent.name.isdigit():
            unrecognized.append(ent.name)
            continue
        rec_path = ent / "record.json"
        if not rec_path.is_file():
            unrecognized.append(ent.name + " (无 record.json)")
            continue
        try:
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise Blind(f"record.json 读不到: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise Damaged(f"record.json 非法: {ent.name}: {exc}") from exc
        if not isinstance(rec, dict):
            raise Damaged(f"record.json 不是对象: {ent.name}")
        rec["_dir"] = str(ent)
        records.append(rec)
    records.sort(key=lambda r: int(r.get("seq") or 0))
    return records, unrecognized


def get_record(paths: Paths, checkpoint_id: str | None):
    records, _ = load_records(paths)
    if not records:
        return None
    if checkpoint_id in (None, "", "latest", "last"):
        return records[-1]
    cid = str(checkpoint_id)
    if cid.isdigit():
        cid = "%05d" % int(cid)
    for rec in records:
        if rec.get("checkpoint_id") == cid or Path(rec["_dir"]).name == cid:
            return rec
    return None


def verify_record(paths: Paths, rec: dict) -> dict:
    """重算副本指纹并与记录比对；副本缺失/不符都算损坏。"""
    t0 = time.monotonic()
    d = Path(rec["_dir"]) / "dimension"
    r = Path(rec["_dir"]) / "reality"
    out = {"checkpoint_id": rec.get("checkpoint_id"), "ok": True, "detail": []}
    want_list = [("dimension", d, "dimension_manifest")]
    if not rec.get("dimension_only"):
        want_list.append(("reality", r, "reality_manifest"))
    else:
        out["detail"].append("reality: 本检查点为 --dimension-only，按设计不校验")
    for name, dst, key in want_list:
        if not dst.exists():
            out["ok"] = False
            out["detail"].append(f"{name}: 副本缺失")
            continue
        got = tree_fingerprint(dst)
        want = rec.get(key) or {}
        if got == want:
            out["detail"].append(f"{name}: 指纹一致（{len(got)} 文件）")
        else:
            out["ok"] = False
            diff = diff_trees(want, got)
            out["detail"].append(f"{name}: 指纹不符（差异 {len(diff)} 条）")
            out[name + "_diff"] = diff
    out["elapsed_ms"] = _ms(t0)
    return out


def diff_trees(want: dict, got: dict) -> list:
    """差异词汇与 mirror_status() 一致：production_extra / not_yet_promoted / diverged。"""
    out = []
    for k in sorted(set(want) | set(got)):
        a, b = want.get(k), got.get(k)
        if a is None:
            out.append({"file": k, "kind": "production_extra", "detail": "多出（记录里没有）"})
        elif b is None:
            out.append({"file": k, "kind": "not_yet_promoted", "detail": "缺失（记录里有）"})
        elif a.get("sha") != b.get("sha") or a.get("size") != b.get("size"):
            out.append({"file": k, "kind": "diverged", "detail": "分叉"})
    return out


# ── 打点 ──


def next_seq(records: list) -> int:
    nums = [int(r.get("seq") or 0) for r in records]
    return (max(nums) + 1) if nums else 1


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def do_checkpoint(paths: Paths, phase_id: str, goal: str = "", force: bool = False,
                  dimension_only: bool = False, on_copied=None,
                  prod_root=None) -> tuple[int, dict]:
    t0 = time.monotonic()
    if not phase_id or not str(phase_id).strip():
        audit(paths, "checkpoint_failed", {"phase_id": "", "reason_code": "no_phase_id"})
        return RC_NO_VERDICT, {"ok": False, "reason": "缺 phase_id：没有阶段归属的检查点无法回答该回到哪",
                               "reason_code": "no_phase_id"}
    phase_id = str(phase_id).strip()

    # 先判自盲，再建目录：盲路径下**不许留下任何痕迹**（否则"抓不到"变成"改过"）
    if not paths.mirror.exists():
        audit(paths, "checkpoint_failed", {"phase_id": phase_id,
                                           "reason_code": "blind", "detail": "镜像空间不存在"})
        return RC_BLIND, {"ok": False, "reason_code": "blind",
                          "detail": f"镜像空间不存在: {paths.mirror}"}
    if not paths.dimension.exists():
        return RC_BLIND, {"ok": False, "reason_code": "blind",
                          "detail": f"维度不存在: {paths.dimension}"}
    if not paths.reality.exists() and not dimension_only:
        return RC_BLIND, {"ok": False, "reason_code": "blind",
                          "detail": f"现实不存在: {paths.reality}"}

    SIO = _load_sibling("safe_io")
    paths.checkpoints.mkdir(parents=True, exist_ok=True)
    try:
        lock = SIO.FileLock(paths.checkpoints / ".lock", timeout=10.0)
    except Exception as exc:  # noqa: BLE001
        return RC_NO_VERDICT, {"ok": False, "reason": f"锁不可用: {exc}"}
    try:
        lock.acquire()
    except Exception as exc:  # noqa: BLE001
        audit(paths, "checkpoint_failed", {"phase_id": phase_id, "reason_code": "lock_busy"})
        return RC_NO_VERDICT, {"ok": False, "reason": f"互斥锁被占用: {exc}"}
    try:

        records, _unrec = load_records(paths)
        if not force:
            for old in records:
                if old.get("phase_id") == phase_id:
                    audit(paths, "checkpoint_reused",
                          {"phase_id": phase_id, "checkpoint_id": old.get("checkpoint_id"),
                           "reason": "同 phase_id 已有检查点，不覆盖"})
                    return RC_OK, {"ok": True, "reused": True,
                                   "checkpoint_id": old.get("checkpoint_id"),
                                   "reason": "同 phase_id 已有检查点，不覆盖（回滚点不许被悄悄挪动）"}

        src_dim_fp = tree_fingerprint(paths.dimension)
        src_real_fp = tree_fingerprint(paths.reality)
        dim_drift, real_drift = drift_snapshot(paths)
        seq = next_seq(records)
        cid = "%05d" % seq
        root = paths.checkpoints / cid
        root.mkdir(parents=True, exist_ok=False)

        _copy_tree(paths.dimension, root / "dimension")
        if not dimension_only:
            _copy_tree(paths.reality, root / "reality")
        if on_copied is not None:
            on_copied(root)

        dst_dim_fp = tree_fingerprint(root / "dimension")
        if dst_dim_fp != src_dim_fp:
            audit(paths, "checkpoint_failed",
                  {"phase_id": phase_id, "checkpoint_id": cid, "reason_code": "torn_copy"})
            return RC_INTEGRITY, {"ok": False, "checkpoint_id": cid, "reason_code": "torn_copy",
                                  "detail": "维度副本指纹 != 源指纹（拷贝期间被改？）",
                                  "diff": diff_trees(src_dim_fp, dst_dim_fp)[:10]}
        if not dimension_only:
            dst_real_fp = tree_fingerprint(root / "reality")
            if dst_real_fp != src_real_fp:
                audit(paths, "checkpoint_failed",
                      {"phase_id": phase_id, "checkpoint_id": cid, "reason_code": "torn_copy"})
                return RC_INTEGRITY, {"ok": False, "checkpoint_id": cid, "reason_code": "torn_copy",
                                      "detail": "现实副本指纹 != 源指纹",
                                      "diff": diff_trees(src_real_fp, dst_real_fp)[:10]}
        else:
            dst_real_fp = {}

        # 生产树指纹（规格 §一/§三）：只打指纹不拷文件；生成失败**不许**拖垮检查点，
        # 但**必须**在 record.json 里留痕（《静默失效律》）。
        try:
            man_root = Path(prod_root) if prod_root is not None else production_root()
            man = production_tree_manifest(man_root)
            man_text = json.dumps(man, ensure_ascii=False, indent=2)
            SIO.atomic_write_text(root / PROD_MANIFEST_NAME, man_text)
            prod_rec = {"ok": True, "path": PROD_MANIFEST_NAME,
                        "files": man["summary"]["files"], "bytes": man["summary"]["bytes"],
                        "sha256": hashlib.sha256(man_text.encode("utf-8")).hexdigest(),
                        "missing_roots": man["summary"]["missing_roots"],
                        "skipped_too_large": len(man["summary"]["skipped_too_large"])}
        except Exception as exc:  # noqa: BLE001
            prod_rec = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}

        rec = {
            "checkpoint_id": cid,
            "seq": seq,
            "phase_id": phase_id,
            "goal": str(goal or "")[:160],
            "created_at": now_iso(),
            "tz": "Asia/Bangkok",
            "timeline_version": timeline_version(paths),
            "dimension_hash": tree_hash(src_dim_fp),
            "reality_hash": tree_hash(src_real_fp) if not dimension_only else "",
            "dimension_files": len(src_dim_fp),
            "reality_files": len(src_real_fp) if not dimension_only else 0,
            "dimension_manifest": src_dim_fp,
            "reality_manifest": src_real_fp if not dimension_only else {},
            "drift_at_checkpoint": dim_drift,
            "reality_drift_at_checkpoint": real_drift,
            "dimension_only": bool(dimension_only),
            "production_tree_manifest": prod_rec,
            "tool": "checkpoint.py",
            "law": "检查点 = 回到那一刻；不许移动、不许覆盖、不许静默删除",
        }
        SIO.atomic_write_json(root / "record.json", rec)
        audit(paths, "checkpoint", {
            "phase_id": phase_id, "checkpoint_id": cid,
            "dimension_hash": rec["dimension_hash"], "reality_hash": rec["reality_hash"],
            "timeline_version": rec["timeline_version"], "created_at": rec["created_at"],
            "production_tree": {"ok": bool((prod_rec or {}).get("ok")),
                                "files": (prod_rec or {}).get("files"),
                                "bytes": (prod_rec or {}).get("bytes")}})
        return RC_OK, {"ok": True, "checkpoint_id": cid, "seq": seq, "phase_id": phase_id,
                       "dimension_files": rec["dimension_files"], "reality_files": rec["reality_files"],
                       "timeline_version": rec["timeline_version"],
                       "dimension_hash": rec["dimension_hash"][:16],
                       "reality_hash": (rec["reality_hash"] or "")[:16],
                       "production_tree": prod_rec,
                       "dir": str(root), "elapsed_ms": _ms(t0)}
    except Blind as exc:
        audit(paths, "checkpoint_failed", {"phase_id": phase_id, "reason_code": "blind",
                                           "detail": str(exc)[:160]})
        return RC_BLIND, {"ok": False, "reason_code": "blind", "detail": str(exc)}
    except Damaged as exc:
        return RC_DAMAGED, {"ok": False, "reason_code": "damaged", "detail": str(exc)}
    finally:
        try:
            lock.release()
        except Exception:  # noqa: BLE001
            pass


# ── 状态 ──


def do_status(paths: Paths) -> tuple[int, dict]:
    try:
        records, unrec = load_records(paths)
    except Blind as exc:
        return RC_BLIND, {"ok": False, "state": "BLIND", "detail": str(exc)}
    except Damaged as exc:
        return RC_DAMAGED, {"ok": False, "state": "DAMAGED", "detail": str(exc)}
    out = {"unrecognized": unrec}
    if not records:
        out.update({"ok": False, "state": "MISSING",
                    "detail": "镜像在、检查点为空 —— 灰（未启用）"})
        return RC_MISSING, out
    rec = records[-1]
    v = verify_record(paths, rec)
    out.update({"state": "OK" if v["ok"] else "DAMAGED", "ok": v["ok"],
                "total": len(records), "latest": rec.get("checkpoint_id"),
                "phase_id": rec.get("phase_id"), "created_at": rec.get("created_at"),
                "timeline_version": rec.get("timeline_version"),
                "verify": v})
    try:
        out["production_tree"] = production_tree_drift(paths, rec)
    except Exception as exc:  # noqa: BLE001
        # 复算失败 = 这条只读路径自己瞎了，必须可见（不许报成"没有差异"）
        out["production_tree"] = {"ok": False, "state": "BLIND",
                                  "detail": "%s: %s" % (type(exc).__name__, exc)}
    return (RC_OK if v["ok"] else RC_DAMAGED), out


# ── 差异 ──


def do_diff(paths: Paths, checkpoint_id: str | None) -> tuple[int, dict]:
    try:
        rec = get_record(paths, checkpoint_id)
    except Blind as exc:
        return RC_BLIND, {"ok": False, "state": "BLIND", "detail": str(exc)}
    except Damaged as exc:
        return RC_DAMAGED, {"ok": False, "state": "DAMAGED", "detail": str(exc)}
    if rec is None:
        return RC_MISSING, {"ok": False, "state": "MISSING", "detail": "没有可用检查点"}
    cur_dim = tree_fingerprint(paths.dimension) if paths.dimension.exists() else {}
    cur_real = tree_fingerprint(paths.reality) if paths.reality.exists() else {}
    dim_diff = diff_trees(rec.get("dimension_manifest") or {}, cur_dim)
    real_diff = (diff_trees(rec.get("reality_manifest") or {}, cur_real)
                 if not rec.get("dimension_only") else [])
    try:
        prod = production_tree_drift(paths, rec)
    except Exception as exc:  # noqa: BLE001
        prod = {"ok": False, "state": "BLIND",
                "detail": "%s: %s" % (type(exc).__name__, exc)}
    return RC_OK, {"ok": True, "checkpoint_id": rec.get("checkpoint_id"),
                   "phase_id": rec.get("phase_id"),
                   "dimension_changed": bool(dim_diff), "reality_changed": bool(real_diff),
                   "dimension_diff": dim_diff, "reality_diff": real_diff,
                   "production_tree": prod,
                   "production_changed": bool(prod.get("drift"))}


# ── 恢复 ──


def do_restore(paths: Paths, checkpoint_id: str | None, go: bool = False,
               reason: str = "restore") -> tuple[int, dict]:
    try:
        rec = get_record(paths, checkpoint_id)
    except Blind as exc:
        return RC_BLIND, {"ok": False, "state": "BLIND", "detail": str(exc)}
    except Damaged as exc:
        return RC_DAMAGED, {"ok": False, "state": "DAMAGED", "detail": str(exc)}
    if rec is None:
        return RC_MISSING, {"ok": False, "state": "MISSING", "detail": "没有可用检查点"}
    v = verify_record(paths, rec)
    if not v["ok"]:
        return RC_DAMAGED, {"ok": False, "state": "DAMAGED",
                            "detail": "检查点不可用，不写任何东西", "verify": v}

    dim_changed = tree_fingerprint(paths.dimension) != (rec.get("dimension_manifest") or {})
    real_changed = (not rec.get("dimension_only")
                    and tree_fingerprint(paths.reality) != (rec.get("reality_manifest") or {}))
    plan = {"checkpoint_id": rec.get("checkpoint_id"), "phase_id": rec.get("phase_id"),
            "will_write_dimension": dim_changed,
            "will_write_reality": real_changed}
    if not go:
        plan.update({"ok": True, "dry_run": True,
                     "detail": "默认只读：要真写必须显式 --go"})
        return RC_OK, plan

    SIO = _load_sibling("safe_io")
    lock = SIO.FileLock(paths.checkpoints / ".lock", timeout=10.0)
    try:
        lock.acquire()
    except Exception as exc:  # noqa: BLE001
        return RC_NO_VERDICT, {"ok": False, "reason": f"互斥锁被占用: {exc}"}
    try:
        # 持锁后**再算一次**"要不要写"：dry-run 与真写之间可能有人动过源树
        dim_changed = tree_fingerprint(paths.dimension) != (rec.get("dimension_manifest") or {})
        real_changed = (not rec.get("dimension_only")
                        and tree_fingerprint(paths.reality) != (rec.get("reality_manifest") or {}))
        plan["will_write_dimension"] = dim_changed
        plan["will_write_reality"] = real_changed
        # 备份落在 store 根下（**不在 mirror_space 里**）：否则它会变成
        # checkpoints 目录里的"未识别条目"，自己污染自己的枚举。
        backup = paths.store / "pre_restore" / ("%s-%s" % (
            rec.get("checkpoint_id"), time.strftime("%Y%m%dT%H%M%S")))
        if dim_changed:
            _copy_tree(paths.dimension, backup / "dimension")
            _copy_tree(Path(rec["_dir"]) / "dimension", paths.dimension)
        if real_changed:
            _copy_tree(paths.reality, backup / "reality")
            _copy_tree(Path(rec["_dir"]) / "reality", paths.reality)

        after_dim = tree_fingerprint(paths.dimension)
        after_real = tree_fingerprint(paths.reality)
        ok = after_dim == (rec.get("dimension_manifest") or {})
        if not rec.get("dimension_only"):
            ok = ok and (after_real == (rec.get("reality_manifest") or {}))
        dim_drift, real_drift = drift_snapshot(paths)
        drift_ok = (dim_drift == list(rec.get("drift_at_checkpoint") or [])
                    and real_drift == list(rec.get("reality_drift_at_checkpoint") or []))
        audit(paths, "rollback", {
            "phase_id": rec.get("phase_id"), "rolled_back_to": rec.get("checkpoint_id"),
            "reason": str(reason or "restore")[:120], "reported_at": now_iso(),
            "wrote_dimension": dim_changed, "wrote_reality": real_changed,
            "fingerprint_ok": ok, "drift_ok": drift_ok})
        result = dict(plan)
        result.update({"ok": ok, "dry_run": False, "backup": str(backup),
                       "fingerprint_ok": ok, "drift_ok": drift_ok,
                       "dimension_drift_now": dim_drift, "reality_drift_now": real_drift,
                       "note": "恢复完停手报人 —— 不许接着跑"})
        return (RC_OK if ok else RC_INTEGRITY), result
    finally:
        try:
            lock.release()
        except Exception:  # noqa: BLE001
            pass


# ── 自证（四臂 · 结论必须互相不同）──


def do_selftest(out_path: str | None = None) -> tuple[int, dict]:
    import tempfile

    arms = []

    def _mk_store(tag: str) -> Path:
        base = Path(tempfile.mkdtemp(prefix="gbt_ckpt_%s_" % tag))
        (base / "mirror_space" / "dimension" / "holo_pet_w3").mkdir(parents=True)
        (base / "mirror_space" / "reality" / "holo_pet_w3").mkdir(parents=True)
        (base / "mirror_space" / "passports").mkdir(parents=True)
        (base / "mirror_space" / "timelines").mkdir(parents=True)
        (base / "mirror_space" / "dimension" / "index.html").write_text("A" * 32, encoding="utf-8")
        (base / "mirror_space" / "dimension" / "holo_pet_w3" / "main.cjs").write_text("M" * 64, encoding="utf-8")
        (base / "mirror_space" / "reality" / "index.html").write_text("A" * 32, encoding="utf-8")
        (base / "mirror_space" / "reality" / "holo_pet_w3" / "main.cjs").write_text("M" * 64, encoding="utf-8")
        for v in (1, 9, 20):
            (base / "mirror_space" / "passports" / ("v%d.json" % v)).write_text("{}", encoding="utf-8")
        return base

    def _rec(tag: str, expect, rc, payload, note=""):
        arms.append({"arm": tag, "expect_rc": expect, "rc": rc,
                     "verdict": "PASS" if rc == expect else "FAIL",
                     "note": note, "payload": payload})

    # A 正对照：正常树 → 打点 → 副本指纹与源一致
    a = Paths(_mk_store("A"))
    rc_a, pay_a = do_checkpoint(a, "PA-01", goal="正对照")
    if rc_a == RC_OK:
        rec_a = get_record(a, pay_a["checkpoint_id"])
        ok = verify_record(a, rec_a)["ok"]
        _rec("A 正对照", RC_OK, RC_OK if ok else RC_INTEGRITY,
             {"verify_ok": ok, "checkpoint_id": pay_a["checkpoint_id"]}, "副本指纹 == 源指纹")
    else:
        _rec("A 正对照", RC_OK, rc_a, pay_a, "打点本就没成功")

    # B 负对照：改一个字节 → 指纹必须变（指纹不瞎）
    b = Paths(_mk_store("B"))
    fp_before = tree_hash(tree_fingerprint(b.dimension))
    f = b.dimension / "index.html"
    f.write_text(f.read_text(encoding="utf-8").replace("A", "B", 1), encoding="utf-8")
    fp_after = tree_hash(tree_fingerprint(b.dimension))
    _rec("B 指纹不瞎", True, fp_before != fp_after,
         {"before": fp_before[:16], "after": fp_after[:16]}, "改一个字节指纹必须变")

    # C 负对照：删一个文件 → 差异清单必须看得见（production_extra）
    c = Paths(_mk_store("C"))
    rc_c, pay_c = do_checkpoint(c, "PC-01")
    if rc_c == RC_OK:
        (c.dimension / "holo_pet_w3" / "main.cjs").unlink()
        rc_d, pay_d = do_diff(c, pay_c["checkpoint_id"])
        kinds = sorted({d["kind"] for d in pay_d.get("dimension_diff") or []})
        _rec("C 差异可见", True, rc_d == RC_OK and "not_yet_promoted" in kinds,
             {"diff": pay_d.get("dimension_diff"), "kinds": kinds}, "删文件必须进差异清单")
    else:
        _rec("C 差异可见", True, False, pay_c, "前置打点失败")

    # D 自盲对照：根不存在 → 必须 12（不许 0、不许 10）
    import tempfile as _tf
    d_paths = Paths(Path(_tf.mkdtemp(prefix="gbt_ckpt_D_")) / "not_created")
    rc_d2, pay_d2 = do_status(d_paths)
    _rec("D 自盲", RC_BLIND, rc_d2, pay_d2, "路径读不到 → 12，不许报 0 或 10")

    # E 撕裂拷贝（注入故障 · 白盒）：副本被篡改 → 必须 13
    e = Paths(_mk_store("E"))

    def _tamper(root):
        (Path(root) / "dimension" / "index.html").write_text("TAMPERED", encoding="utf-8")

    rc_e, pay_e = do_checkpoint(e, "PE-01", on_copied=_tamper)
    _rec("E 撕裂拷贝", RC_INTEGRITY, rc_e, pay_e, "注入故障（白盒）：副本被改必须 13")

    # F 恢复闭环：两侧都改 → --go 恢复 → 指纹回到记录
    fs = Paths(_mk_store("F"))
    rc_f, pay_f = do_checkpoint(fs, "PF-01")
    if rc_f == RC_OK:
        (fs.dimension / "index.html").write_text("CHANGED-DIM", encoding="utf-8")
        (fs.reality / "index.html").write_text("CHANGED-REAL", encoding="utf-8")
        rc_dry, pay_dry = do_restore(fs, pay_f["checkpoint_id"], go=False)
        rc_go, pay_go = do_restore(fs, pay_f["checkpoint_id"], go=True)
        rec_f = get_record(fs, pay_f["checkpoint_id"])
        back = (tree_fingerprint(fs.dimension) == (rec_f.get("dimension_manifest") or {})
                and tree_fingerprint(fs.reality) == (rec_f.get("reality_manifest") or {}))
        _rec("F 恢复闭环", True,
             rc_dry == RC_OK and pay_dry.get("dry_run") is True and rc_go == RC_OK and back,
             {"dry_run": pay_dry, "go": {k: pay_go.get(k) for k in
                                         ("ok", "fingerprint_ok", "drift_ok", "will_write_dimension",
                                          "will_write_reality")}},
             "默认只读；--go 才写；恢复后指纹回到记录")
    else:
        _rec("F 恢复闭环", True, False, pay_f, "前置打点失败")

    verdicts = [(a_["arm"], a_["rc"]) for a_ in arms]
    distinct = len({str(rc) for _n, rc in verdicts}) > 1
    ok_all = all(a_["verdict"] == "PASS" for a_ in arms)
    payload = {"ok": ok_all, "arms": arms, "distinct_codes": distinct,
               "codes": {n: rc for n, rc in verdicts},
               "note": "四臂结论必须互相不同（判别性）；这里额外多了 E/F 两臂"}
    if out_path:
        try:
            Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            payload["out"] = str(out_path)
        except Exception as exc:  # noqa: BLE001
            payload["out_error"] = str(exc)
    return (RC_OK if ok_all else RC_INTEGRITY), payload


# ── CLI ──


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    p = argparse.ArgumentParser(description="阶段级检查点打点器（对镜像只读；只写 checkpoints/）")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--checkpoint", action="store_true", help="阶段开始前打点")
    g.add_argument("--status", action="store_true", help="只读：最近检查点是否可用")
    g.add_argument("--diff", nargs="?", const="latest", help="只读：与某检查点的差异")
    g.add_argument("--restore", nargs="?", const="latest", help="恢复（默认 dry-run，加 --go 才写）")
    g.add_argument("--selftest", action="store_true", help="自证四臂 + 恢复闭环（临时目录，零生产写入）")
    p.add_argument("--phase", default="", help="phase_id（--checkpoint 必填）")
    p.add_argument("--goal", default="")
    p.add_argument("--store-dir", default=None, help="store 基址（默认 GBT_STORE_DIR 或 gbt_allinone/store）")
    p.add_argument("--go", action="store_true", help="--restore 真写（默认只读）")
    p.add_argument("--reason", default="restore", help="--restore 的恢复原因（写进 rollback 审计）")
    p.add_argument("--force", action="store_true", help="同 phase_id 重打（必须落账）")
    p.add_argument("--dimension-only", action="store_true", help="逃生开关：只冻维度")
    p.add_argument("--out", default=None, help="把结果 JSON 落文件（结果通道律）")
    args = p.parse_args(argv)

    if args.selftest:
        rc, payload = do_selftest(args.out)
    else:
        paths = Paths(resolve_store_dir(args.store_dir))
        if args.checkpoint:
            rc, payload = do_checkpoint(paths, args.phase, args.goal, force=args.force,
                                        dimension_only=args.dimension_only)
        elif args.status:
            rc, payload = do_status(paths)
        elif args.diff is not None:
            rc, payload = do_diff(paths, args.diff)
        elif args.restore is not None:
            rc, payload = do_restore(paths, args.restore, go=args.go, reason=args.reason)
        else:
            print("需要 --checkpoint / --status / --diff / --restore / --selftest 之一 —— 本次没有结论")
            return RC_NO_VERDICT
        payload = dict(payload)
        payload["store_dir"] = str(paths.store)

    if args.out and not args.selftest:
        try:
            Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            payload["out"] = str(args.out)
        except Exception as exc:  # noqa: BLE001
            payload["out_error"] = str(exc)

    print("rc=%d %s" % (rc, json.dumps(payload, ensure_ascii=False)))
    return rc


if __name__ == "__main__":
    sys.exit(main())
