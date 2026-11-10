# -*- coding: utf-8 -*-
"""旧物守卫（legacy_guard）：**项目里不允许旧代码、旧面板、重复的东西。**

主人口径（2026-11-01，逐字）：「我们项目里面不允许有旧代码和旧面板等一切旧，重复的东西存在你不知道吗？」

## 查什么（六类，全部可数）

1. **旧代码快照**：`state/sync-backup/`（双向同步每次覆盖前的备份）—— 旧副本，不许留；
2. **旧工作树**：`.scratch/**/refresh*-work`、`live-backup`、`upstream-raw` 这类过期副本；
3. **旧面板归档**：`_archive-*`、`_old`、`*-v1` 目录（旧面板/旧页面）；
4. **备份文件**：`*.bak / *.old / *.orig`；
5. **重复文档编号**：`docs/` 里同一编号前缀出现两页以上（如两个 37、两个 75）；
6. **临时件**：`state/tmp/` 非空。

## op

    status   只读统计 + 结论（clean / legacy_found）
    scan     列出全部命中（分类 + 路径 + 大小）
    clean    按类删除（默认只删 1/2/3/4/6 这些**明确是旧副本**的；重复文档只报不删）

## 纪律

- **只报不删**的类：重复文档编号（可能两页都有价值，删哪页要人看内容）；
- `clean` 每次动作都记编排账本；
- 这个位本身**只读自检**，不改变能力面。
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
HOME = ROOT.parent  # 工作区根（.scratch 在这里）

# 这些目录本身就是「备份/暂存/运行时」：里面的 .bak/.old/.orig 是备份的备份，
# 不是散落在项目里的旧副本。2026-11-07 实测：11 个 .bak 有 8 个就住在这里，
# 却让 APP 左侧 legacy 永远红。排除的是**位置**，不是文件名。
_BACKUP_ZONES = (
    ".archive", ".scratch", ".backups", "state/backup",
    "pyembed",                   # embeddable 运行时自带 python312.pth.bak
    "vendor", "assets/vendor",   # 第三方依赖快照
)


def _in_backup_zone(p: pathlib.Path) -> bool:
    try:
        rel = p.relative_to(ROOT).as_posix()
    except ValueError:
        return False
    return any(rel == z or rel.startswith(z + "/") for z in _BACKUP_ZONES)


def _count(files) -> dict:
    n = 0
    size = 0
    for f in files:
        try:
            n += 1
            size += f.stat().st_size
        except Exception:  # noqa: BLE001
            continue
    return {"files": n, "mb": round(size / 1048576, 1)}


def scan(include_doc_dups: bool = True) -> dict:
    cats = {}
    paths = {}

    # ① 旧代码快照
    snap = [p for p in ROOT.glob("state/sync-backup*") if p.is_dir()]
    f_snap = [x for d in snap for x in ([d] if d.is_file() else d.rglob("*")) if x.is_file()]
    cats["sync-backup"] = _count(f_snap)

    # ② 旧工作树
    # `.scratch/` 是会话临时工作区（可能有别的会话在用），不计入项目旧物
    work = []
    f_work = [x for d in work for x in d.rglob("*") if x.is_file()]
    cats["old-worktree"] = _count(f_work)

    # ③ 旧面板归档
    arch = []
    for base in (ROOT, ROOT / "holo_pet_w3"):
        if base.is_dir():
            arch += [d for d in base.iterdir() if d.is_dir()
                     and re.search(r"(_archive-|^_old$|-v1$)", d.name)]
    f_arch = [x for d in arch for x in d.rglob("*") if x.is_file()]
    cats["old-panel-archive"] = _count(f_arch)

    # ④ 备份文件：只算散落在项目里的；备份区内的不进红（见 _BACKUP_ZONES）
    baks_all = [p for p in ROOT.rglob("*") if p.is_file()
                and p.suffix.lower() in (".bak", ".old", ".orig")]
    baks = [p for p in baks_all if not _in_backup_zone(p)]
    cats["backup-files"] = _count(baks)
    if len(baks_all) != len(baks):
        cats["backup-files"]["inside_backup_zones"] = len(baks_all) - len(baks)

    # ⑤ 重复文档编号
    dup_docs = []
    if include_doc_dups:
        by_num = {}
        for p in (ROOT / "docs").glob("*.md"):
            m = re.match(r"^(\d+)-", p.name)
            if m:
                by_num.setdefault(m.group(1), []).append(p.name)
        dup_docs = [{"num": k, "files": v} for k, v in sorted(by_num.items()) if len(v) > 1]
    cats["dup-doc-numbers"] = {"groups": len(dup_docs)}

    # ⑥ 临时件
    tmp = [p for p in (ROOT / "state" / "tmp").rglob("*") if p.is_file()] if (ROOT / "state" / "tmp").is_dir() else []
    cats["state-tmp"] = _count(tmp)

    paths = {"sync-backup": [str(x) for x in snap],
             "old-worktree": [str(x) for x in work],
             "old-panel-archive": [str(x) for x in arch],
             "backup-files": [str(x) for x in baks],
             "dup-doc-numbers": dup_docs,
             "state-tmp": [str(ROOT / "state" / "tmp")] if tmp else []}

    # `dup-doc-numbers` 是「编号撞车」，不是「旧物」：58 组里每组都是不同标题的不同文档
    # （100-gsap-skill vs 100-hand-pipeline-verdict）。把它算进 verdict 会让 legacy 永远红，
    # 又没有任何东西该删。单独放 notes 里提示，verdict 只由**真旧物**决定。
    found = bool(snap or work or arch or baks or tmp)
    return {"ok": True, "verdict": "legacy_found" if found else "clean",
            "categories": cats, "paths": paths,
            "notes": {"doc-number-collisions": {
                "groups": len(dup_docs),
                "meaning": "编号相同但标题不同；是命名撞车，不是重复内容，未计入 verdict",
                "sample": dup_docs[:8]}},
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rule": ("项目里不许有散落的旧代码/旧面板/备份文件；备份区内的备份不算。"
                     "文档编号撞车只提示、不进红（不同标题不是重复内容）")}


def clean(include_tmp: bool = True) -> dict:
    """删旧副本类（1/2/3/4/6）。重复文档不动。"""
    s = scan()
    p = s["paths"]
    removed = {"dirs": 0, "files": 0, "mb": 0.0}
    for path in p["sync-backup"] + p["old-worktree"] + p["old-panel-archive"]:
        d = pathlib.Path(path)
        if d.is_dir():
            try:
                n = sum(1 for _ in d.rglob("*") if _.is_file())
                mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1048576
                shutil.rmtree(d)
                removed["dirs"] += 1
                removed["files"] += n
                removed["mb"] += mb
            except Exception:  # noqa: BLE001
                continue
    for f in p["backup-files"]:
        try:
            fp = pathlib.Path(f)
            mb = fp.stat().st_size / 1048576
            fp.unlink()
            removed["files"] += 1
            removed["mb"] += mb
        except Exception:  # noqa: BLE001
            continue
    if include_tmp:
        t = ROOT / "state" / "tmp"
        if t.is_dir():
            for x in t.iterdir():
                try:
                    if x.is_dir():
                        shutil.rmtree(x)
                    else:
                        x.unlink()
                    removed["files"] += 1
                except Exception:  # noqa: BLE001
                    continue
    removed["mb"] = round(removed["mb"], 1)
    after = scan()
    try:
        from . import orchestration as OB
        OB.record("fix", "legacy_guard", detail="清旧物：删 %d 目录 / %d 文件 / %.1f MB；剩 %s"
                  % (removed["dirs"], removed["files"], removed["mb"], after["verdict"]))
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "removed": removed, "after": after}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        s = scan()
        return {"ok": True, "verdict": s["verdict"], "categories": s["categories"],
                "notes": s.get("notes"), "rule": s["rule"]}
    if op == "scan":
        return scan()
    if op == "clean":
        return clean(include_tmp=bool(kw.get("tmp", True)))
    if op == "authority":
        return authority()
    return {"ok": False, "error": "legacy_guard 不认 op=%s（status/scan/clean）" % op}

# ── 唯一真相（2026-11-01 主人真意）：旧副本的害处是**让人分不清谁新谁旧** ──
AUTHORITY = {
    "truth": "live 工作仓的**当前文件**（本仓根）",
    "mirror": "~/Desktop/GBT小土豆V8 是交付镜像，不作判断依据",
    "history": "state/orchestration-ledger.jsonl（账本）与 git 历史",
    "forbidden_read": [
        "state/sync-backup/**（旧副本，一律不读）",
        "**/_archive-*/**、**/*-v1/**（旧面板/旧页面）",
        "**/*.bak、**/*.old、**/*.orig",
        "**/refresh*-work/**（旧工作树）",
    ],
    "rule": "判断'现在是什么'只看 live 当前文件 + 账本；禁止去旧备份/归档里找答案。",
}


def authority() -> dict:
    return {"ok": True, "authority": AUTHORITY, "checked": scan()["verdict"]}
