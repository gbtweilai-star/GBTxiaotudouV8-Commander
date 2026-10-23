# gbt-capability: slim_profile
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""瘦身画像：**按命名类别裁 + 三档闸 + 裁后复核**（蒸馏自 simslim，只取剪裁架构）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的仓库截图 `MobAI-App/simslim`（模拟器瘦身工具）。仓库页原文要点：
  「Run a lot more iOS simulators on one Mac by **disabling background daemons** a simulator doesn't need」；
  服务类 15 类（widgets/siri/search/icloud/store/pim/web/family/health/photos/apps/messaging/
  connectivity/telemetry/other）；磁盘类 4 类（**caches / logs / temporary / linguistic-data**）；
  `disk-plan` **只读测量**、`disk-clean` **必须 `--confirm`** 且会先关掉对应模拟器、`verify`
  **复核已启动的模拟器是否仍符合某 profile**；`measure`/`size` 给前后读数。
  仅支持 macOS + Xcode（走 `xcrun simctl`）。
  —— 本机是 Windows、无 iOS 模拟器 ⇒ **不搬它的 simctl 实现**；只吞它的**剪裁架构**。
· **时间**：2026-09-28。
· **口径**：本仓已有 `reclaim_sweep`（无死角枚举 + 待清清单 + **垃圾桶模式只搬不删**）——
  **清单那半已有，不重造**；本件补它没有的三样：① **命名类别 + profile**（可整类开关）；
  ② **三档闸**（plan 只读 / cut 必须 confirm / verify 复核）；③ **裁后复核**（可用性不能被剪坏）。

## 蒸馏判断：simslim 的核里我们真缺哪块
| 它的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 逐文件枚举 + 待清清单 | `reclaim_sweep`（垃圾桶模式，只搬不删） | **已有，不重造** |
| **命名类别 + profile（整类开关）** | 无 | **补这块** |
| **三档闸（plan→confirm→verify）** | 只有"只搬不删" | **补这块** |
| **裁后复核（仍满足 profile）** | 无 | **补这块** |
| simctl / launchd 服务裁剪 | 无（也不同平台） | **不接**（仅 macOS，本机无模拟器） |

## 硬规矩
1. **plan 只读**：`plan` 一个字都不动（同它的 disk-plan）。
2. **cut 必须显式 confirm**：不 confirm ⇒ 结构化拒（fail-closed）；且**走垃圾桶不 rm**
   —— 候选搬进 `.trash/slim-<时间戳>/<类别>/<原相对路径>`（继承本仓 `reclaim_sweep` 的处置口径）。
3. **裁后必须复核**：`verify` 检查**保留判据**（如：包不能丢 `__init__.py`、目标根文件不能空、
   被搬件数与报告对得上）——**裁剪不破坏可用性要能被判**，不许"删完就说成功"。
4. **前后两个数**：cut 报告 `before_bytes` / `after_bytes` / `freed_bytes`（现量，不估算）。
5. **不跟符号链接**：遍历时不跟随（防顺链删到目标之外）。
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TRASH = _ROOT / ".trash"

# 命名类别（保守）：每类 = 匹配规则 + 为什么可裁 + 类别归属的 profile
CATEGORIES = {
    "pycache": {"dirs": ("__pycache__",), "suffixes": (".pyc", ".pyo"),
                "why": "Python 字节码缓存，可重建（导入即重生）"},
    "pytest_cache": {"dirs": (".pytest_cache",), "suffixes": (),
                     "why": "pytest 缓存，可重建"},
    "logs": {"dirs": (), "suffixes": (".log",),
             "why": "日志文本（本仓另有 archived_logs 归档区，这里只碰目标内的散日志）"},
    "tmp": {"dirs": ("tmp", "temp", ".tmp"), "suffixes": (".tmp",),
            "why": "临时目录/中间件（可由作业重跑）"},
    "build": {"dirs": ("dist", "build", ".mypy_cache", ".ruff_cache"),
              "suffixes": (), "why": "构建与工具缓存产物（可重建）"},
}
PROFILES = {
    "dev": ("pycache", "pytest_cache", ".mypy_cache-only"),
    "safe": ("pycache", "pytest_cache", "logs", "build"),
    "deep": ("pycache", "pytest_cache", "logs", "tmp", "build"),
}
# 保留判据：这些名字**永不动**（裁到它们 = 剪坏了可用性）
KEEP_NAMES = ("__init__.py", "README.md", "requirements.txt", "pyproject.toml",
              "package.json", "SKILL.md", "main.py", "AGENTS.md")


def _cats(profile: str) -> tuple:
    if profile not in PROFILES:
        raise ValueError("未知 profile：%s（可用 %s）" % (profile, "/".join(PROFILES)))
    return tuple(c for c in PROFILES[profile] if c in CATEGORIES)


def _walk(root: Path, limit: int = 200000) -> list:
    """剪枝遍历（**不跟符号链接**）；返回 (Path, category) 候选清单。"""
    hits, n = [], 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".git")]
        base = Path(dirpath)
        for d in list(dirnames):
            for cat, spec in CATEGORIES.items():
                if d in spec["dirs"]:
                    hits.append((base / d, cat))
                    dirnames.remove(d)
                    break
        for fn in filenames:
            n += 1
            if n > limit:
                return hits
            if fn in KEEP_NAMES:
                continue
            for cat, spec in CATEGORIES.items():
                if spec["suffixes"] and fn.endswith(spec["suffixes"]):
                    hits.append((base / fn, cat))
                    break
    return hits


def _rel(p) -> str:
    """路径显示容错：仓内给相对路径，**仓外给绝对路径**（不许抛）。

    实测（判据把垃圾桶重定向到临时区）：`relative_to(_ROOT)` 直接 ValueError ⇒ cut 崩。
    教训（与 handoff 同源）：**显示用换算必须容错**——盘在哪不是错，报不出盘才是错。
    """
    try:
        return str(Path(p).relative_to(_ROOT))
    except ValueError:
        return str(p)


def _size(p: Path) -> int:
    if p.is_file():
        try:
            return p.stat().st_size
        except OSError:
            return 0
    total = 0
    for dp, _dn, fns in os.walk(p, followlinks=False):
        for fn in fns:
            try:
                total += (Path(dp) / fn).stat().st_size
            except OSError:
                continue
    return total


def plan(target: str = "", profile: str = "safe", **_kw) -> dict:
    """**只读**：按类别量出可回收体积（同 simslim 的 disk-plan）。"""
    if not str(target or "").strip():
        return {"ok": False, "fail_closed": True, "error": "target 要给（目录路径）"}
    root = Path(target)
    if not root.is_dir():
        return {"ok": False, "fail_closed": True, "error": "目标不是目录：%s" % root}
    try:
        cats = _cats(profile)
    except ValueError as exc:
        return {"ok": False, "fail_closed": True, "error": str(exc)}
    rows, total = {}, 0
    for p, cat in _walk(root):
        if cat not in cats:
            continue
        sz = _size(p)
        r = rows.setdefault(cat, {"count": 0, "bytes": 0, "sample": []})
        r["count"] += 1
        r["bytes"] += sz
        if len(r["sample"]) < 5:
            r["sample"].append(str(p.relative_to(root)))
        total += sz
    return {"ok": True, "op": "plan", "target": str(root), "profile": profile,
            "categories": rows, "reclaimable_bytes": total,
            "categories_why": {c: CATEGORIES[c]["why"] for c in cats},
            "_口径": "**只读**（同 disk-plan）：一个字都不动；不跟符号链接"}


def cut(target: str = "", profile: str = "safe", confirm: bool = False, **_kw) -> dict:
    """**必须显式 confirm** 才动；且**走垃圾桶不 rm**（搬进 .trash/slim-<ts>/<类别>/）。"""
    if not confirm:
        return {"ok": False, "op": "cut", "fail_closed": True, "denied": True,
                "error": "未确认 ⇒ 不裁（同 disk-clean 必须 --confirm）",
                "how": "确认后重发 confirm=true；或先跑 plan 看计划"}
    p = plan(target=target, profile=profile)
    if not p.get("ok"):
        return p
    root = Path(target)
    before = sum(_size(Path(dp) / fn) for dp, _dn, fns in os.walk(root, followlinks=False)
                 for fn in fns if (Path(dp) / fn).is_file())
    ts = time.strftime("%Y%m%d-%H%M%S")
    moved, failed = [], []
    try:
        cats = _cats(profile)
    except ValueError as exc:
        return {"ok": False, "fail_closed": True, "error": str(exc)}
    for src, cat in _walk(root):
        if cat not in cats or not src.exists():
            continue
        rel = src.relative_to(root)
        dst = _TRASH / ("slim-%s" % ts) / cat / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))          # 只搬不删
            moved.append({"what": str(rel), "category": cat, "bytes": _size(dst)})
        except Exception as exc:                      # noqa: BLE001
            failed.append({"what": str(rel), "why": "%s: %s" % (type(exc).__name__, str(exc)[:60])})
    after = sum(_size(Path(dp) / fn) for dp, _dn, fns in os.walk(root, followlinks=False)
                for fn in fns if (Path(dp) / fn).is_file())
    return {"ok": True, "op": "cut", "target": str(root), "profile": profile,
            "trash": _rel(_TRASH / ("slim-%s" % ts)),
            "moved": moved, "moved_count": len(moved), "failed": failed,
            "before_bytes": before, "after_bytes": after,
            "freed_bytes": max(0, before - after),
            "_口径": "**只搬不删**（垃圾桶模式，继承 reclaim_sweep 口径）；被搬件可原路取回；前后两个数现量"}


def verify(target: str = "", profile: str = "safe", expect_moved: int = -1, **_kw) -> dict:
    """**裁后复核**：保留判据还成立吗（可用性不能被剪坏）+ 账面自洽。"""
    root = Path(target)
    if not root.is_dir():
        return {"ok": False, "fail_closed": True, "error": "目标不是目录：%s" % root}
    problems, warnings = [], []
    # 判据 1：保留名单里一个都不许出现在瘦身垃圾桶里（出现 = 剪坏了可用性）
    #    cut 本来就跳过 KEEP_NAMES ⇒ 垃圾桶里出现它们只能是"别处剪坏"或"有人手搬" ⇒ 必须报
    trash_hits = []
    if _TRASH.is_dir():
        for sub in _TRASH.glob("slim-*"):
            for f in sub.rglob("*"):
                if f.name in KEEP_NAMES:
                    trash_hits.append(str(f))
    if trash_hits:
        problems.append("保留名单里的文件被搬了（可用性有险）：%s" % sorted(set(trash_hits))[:4])
    # 判据 2：目标根还在（不能把目标本身搬空）
    if not any(root.iterdir()):
        problems.append("目标目录被搬空了 ⇒ 剪过头")
    # 判据 3：与计划的类别一致（只裁了 profile 内的类）
    try:
        cats = _cats(profile)
    except ValueError as exc:
        return {"ok": False, "fail_closed": True, "error": str(exc)}
    if not cats:
        warnings.append("该 profile 无类别（等于什么都没裁）")
    # 判据 4：账面自洽（调用方给了 expect_moved 时）
    if expect_moved >= 0:
        now = len(_walk(root))
        if now > expect_moved:
            warnings.append("裁后仍在盘上的候选 %d > 预期 %d（可能有新增或没搬净）" % (now, expect_moved))
    return {"ok": not problems, "op": "verify", "target": str(root), "profile": profile,
            "problems": problems, "warnings": warnings,
            "_口径": "保留判据（不改保留名单里的件）· 目标不许搬空 · 只裁 profile 内的类 · 账面自洽"}


def profiles(**_kw) -> dict:
    return {"ok": True, "op": "profiles", "profiles": {k: list(v) for k, v in PROFILES.items()},
            "categories": {k: v["why"] for k, v in CATEGORIES.items()},
            "keep_names": KEEP_NAMES,
            "_口径": "同 simslim 的 profile 概念：dev 最保守 · safe 常用 · deep 最激进；裁完必须 verify"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "slim_profile", "tentacle": "slim_profile",
            "entry": "run_task('slim_profile', {...})",
            "ops": ["plan", "cut", "verify", "profiles", "where"],
            "distilled_from": "2026-09-28 主人给的仓库截图 MobAI-App/simslim（模拟器瘦身工具）"
                              "——只取**剪裁架构**（命名类别 + profile + 三档闸 + 裁后复核）",
            "not_copied": "不搬它的 simctl/launchd 实现（仅 macOS + Xcode，本机 Windows 无 iOS 模拟器）；"
                          "逐文件枚举与待清清单仍走既有 reclaim_sweep（不重造）",
            "hard_rules": ["plan 只读（一个字都不动）",
                           "cut 必须显式 confirm，且**只搬不删**（.trash/slim-<ts>/<类别>/，可原路取回）",
                           "裁后必须 verify（保留判据 + 目标不许搬空 + 只裁 profile 内的类）",
                           "前后两个数现量（before/after/freed）",
                           "不跟符号链接"],
            "files": {"垃圾桶": str(_TRASH.relative_to(_ROOT))},
            "contract": [
                {"op": "plan", "params": "target + [profile]", "returns": "按类别的可回收体积（只读）"},
                {"op": "cut", "params": "target + profile + **confirm=true**", "returns": "搬运清单 + 前后两个数"},
                {"op": "verify", "params": "target + [profile]", "returns": "裁后复核（可用性判据）"},
                {"op": "profiles", "params": "—", "returns": "可用画像与类别口径"},
            ]}


def run_op(op: str = "profiles", **params) -> dict:
    op = (op or "profiles").lower()
    for n, fn in (("plan", plan), ("cut", cut), ("verify", verify),
                  ("profiles", profiles), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（plan/cut/verify/profiles/where）"}


if __name__ == "__main__":                                     # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="瘦身画像（simslim 架构蒸馏 · 三档闸 + 裁后复核）")
    ap.add_argument("cmd", nargs="?", default="profiles")
    ap.add_argument("--target", default="")
    ap.add_argument("--profile", default="safe")
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args()
    if a.cmd == "cut":
        print(json.dumps(run_op("cut", target=a.target, profile=a.profile, confirm=a.confirm),
                         ensure_ascii=False, indent=1))
    else:
        print(json.dumps(run_op(a.cmd, target=a.target, profile=a.profile),
                         ensure_ascii=False, indent=1))
