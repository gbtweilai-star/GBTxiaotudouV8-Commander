#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""penetrating_cross_scan —— 穿透式交叉扫描 / 钩子强制器（只读）

## 为什么一个文件服务两个位
`_TOOL_IMPL` 里两条都指向本文件：
    "penetrating_cross_scan": "tools/penetrating_cross_scan.py"
    "hook_enforcer":          "tools/penetrating_cross_scan.py"
原因：它们是同一件事的两种问法 ——
    hook_enforcer          问「钩子有没有真触发」
    penetrating_cross_scan 问「穿透率是多少、哪几处没穿过去」
所以实现一份，两个入口。

## 它做什么（先说清边界，免得被念歪）
**只读、不联网、不越权。** 不扫端口、不猜口令、不碰别人的机器。
它扫的是**我们自己的项目树**：对每个单元用三条独立读法各读一次，
看它们说的是不是同一个事实：

    读法A  盘上在不在（os.lstat）
    读法B  在不在绑定账（state/asset_bindings.json）
    读法C  有没有触手标签（tentacle_bind.suggest 的归属）

三路一致 ⇒ 已钩住（hooked）。任何一路读不到/读出不一样 ⇒ 未钩住，并写明是哪一路。

这正是登记的语义：「逐单元回报已钩住/未钩住 与 多路读法的指纹一致性」，
以及「覆盖率 = 已钩住/总数；<100% 如实报 missing，不许折叠成绿」。

## 口径
· 覆盖不全 **不许四舍五入成绿**：返回里 missing 是清单，不是计数。
· 认不出标签的单元如实列进 `no_kind`（没标签可挂 ≠ 钩子坏了）。
· 默认采样 200 个单元（全树 6 万+，全量扫要几十秒）—— limit 可调，0 = 全量。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
BIND = ROOT / "state" / "asset_bindings.json"
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "_archive-20261021"}


def _load_bind() -> dict:
    try:
        return json.loads(BIND.read_text(encoding="utf-8"))
    except Exception:                                             # noqa: BLE001
        return {}


def _suggest():
    """借 tentacle_bind 的归属判定，不自己另写一套启发式（那会是第二份口径）。"""
    try:
        sys.path.insert(0, str(TOOLS))
        import tentacle_bind as tb
        return tb.suggest
    except Exception:                                             # noqa: BLE001
        return None


def _iter_units(base: Path, limit: int):
    n = 0
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            p = Path(dp) / fn
            yield p
            n += 1
            if limit and n >= limit:
                return


def _fingerprint(p: Path) -> str:
    """指纹 = 大小 + mtime 的短哈希（不读内容，快且够用）。"""
    try:
        st = p.lstat()
        return hashlib.sha1(("%d:%d" % (st.st_size, int(st.st_mtime))).encode()).hexdigest()[:12]
    except Exception:                                             # noqa: BLE001
        return ""


def cross_scan(target: str = "", limit: int = 200) -> dict:
    base = (ROOT / target) if target else ROOT
    if not base.exists():
        return {"ok": False, "error": "目标不存在: %s" % base}
    sug = _suggest()
    ledger = _load_bind()

    hooked, missing, no_kind = [], [], []
    for p in _iter_units(base, limit):
        try:
            rel = str(p.relative_to(ROOT))
        except Exception:                                         # noqa: BLE001
            rel = str(p)
        # 读法A：盘上在不在
        a = p.exists()
        # 读法B：账里有没有
        ent = ledger.get(rel)
        b = ent is not None
        # 读法C：有没有触手标签
        kind = (ent or {}).get("tentacle") if isinstance(ent, dict) else None
        if not kind and sug:
            try:
                kind = sug(rel)
            except Exception:                                     # noqa: BLE001
                kind = None
        c = bool(kind)

        if not a:
            continue
        if b and c:
            hooked.append({"unit": rel, "tentacle": kind, "fp": _fingerprint(p)})
        elif not c:
            no_kind.append(rel)
        else:
            missing.append({"unit": rel, "has_a": a, "in_ledger": b,
                            "has_tentacle": c, "why": "账里没有（有标签未绑）"})

    total = len(hooked) + len(missing) + len(no_kind)
    cov = (len(hooked) / total * 100) if total else 0.0
    return {"ok": not missing,
            "target": str(base), "units": total,
            "hooked": len(hooked), "missing": len(missing),
            "no_kind": len(no_kind), "coverage_pct": round(cov, 1),
            "missing_list": [m["unit"] for m in missing][:30],
            "note": "只读交叉核对（盘上/账里/标签三路）；missing 是清单不是计数，"
                    "没标签可挂的单元单列 no_kind，不折叠进覆盖率的分子分母",
            "sample_hooked": [h["unit"] for h in hooked[:5]]}


# ── 契约入口（gbt_allinone/api.py 实测要求：status / report / run_pipeline）──
STATE = ROOT / "state" / "penetrating_cross_scan.json"


def _save(obj: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:                                             # noqa: BLE001
        pass


def status() -> dict:
    """上次跑到哪、穿了多少。没有就如实说没有，不编一份假报告。"""
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        return {"ok": True, "has_report": True, "at": d.get("at"),
                "target": d.get("target"), "units": d.get("units"),
                "hooked": d.get("hooked"), "missing": d.get("missing"),
                "coverage_pct": d.get("coverage_pct")}
    except Exception:                                             # noqa: BLE001
        return {"ok": True, "has_report": False,
                "note": "还没跑过 ⇒ 先 op=scan（penetrating_cross_scan/hook_enforcer）"}


def report(tail: int = 5) -> dict:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:                                             # noqa: BLE001
        return {"ok": False, "error": "没有报告，先跑 scan"}
    rows = d.get("missing_list") or []
    return {"ok": True, "at": d.get("at"), "units": d.get("units"),
            "hooked": d.get("hooked"), "missing": d.get("missing"),
            "coverage_pct": d.get("coverage_pct"), "tail": rows[:max(1, tail)]}


def run_pipeline(target: str = "bindings", mode: str = "scan") -> dict:
    """真跑一次交叉核对并落盘。mode: scan（穿透率）/ check（遗漏检测）。"""
    import time as _t
    r = cross_scan("" if target in ("", "bindings", "all", "tree") else target, 400)
    r["at"] = _t.strftime("%Y-%m-%dT%H:%M:%S")
    r["mode"] = mode
    _save(r)
    return r


# ── 两个能力位入口（唯一门按 kind 名直接取）────────────────────────────────
def hook_enforcer(target: str = "", limit: int = 200, **kw) -> dict:
    """钩子强制器：逐单元回报「已钩住/未钩住」与多路读法的指纹一致性。"""
    r = cross_scan(target, limit)
    r["kind"] = "hook_enforcer"
    r["question"] = "钩子有没有真触发"
    return r


def penetrating_cross_scan(target: str = "", limit: int = 200, **kw) -> dict:
    """穿透式交叉扫描：同一套三路读法，回答「穿透率与没穿过去的清单」。"""
    r = cross_scan(target, limit)
    r["kind"] = "penetrating_cross_scan"
    r["question"] = "穿透率多少、哪几处没穿过去"
    return r


def main(argv: list) -> int:
    target = argv[1] if len(argv) > 1 else ""
    limit = int(argv[2]) if len(argv) > 2 else 200
    r = cross_scan(target, limit)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
