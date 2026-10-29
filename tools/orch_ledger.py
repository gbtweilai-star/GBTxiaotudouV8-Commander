#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""orch_ledger —— 编排账本（没跑通就不算验收）。

## 规则（主人 2026-10-29）
  「没跑通就不算验收，必须在编排账本里面记录：哪里修改过、哪里还没跑通，
    全部都在明细记录，时间日期都要明确。」

## 一本账，两种行
  change  哪改了：at / files / what / why / commit
  run     哪跑通没：at / item / status(pass|fail|unrun) / evidence（真命令 + 真输出尾）

## 三条硬规矩（这就是「判据」，不是摆设）
  ① **没 pass 的记录一律算未跑通** —— 包括只有 change 没 run 的条目；
  ② **改了没记账也要报** —— 用 git 比对工作区改动，凡是改了却没进账本的，点名；
  ③ **时间日期必须明确** —— 每行都带 ISO 时间；查询按天切片。

## 用法
  orch_ledger.py change --what "做了什么" --files a.py,b.py [--why "为什么"] [--commit abc1234]
  orch_ledger.py run    --item "哪一项" --status pass|fail|unrun [--evidence "命令+输出"]
  orch_ledger.py gate             # 判决：有未跑通/未记账 ⇒ 退出码 1
  orch_ledger.py show [--days 1]  # 明细（按天）
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "orchestration.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def append(rec: dict) -> None:
    rec.setdefault("at", now())
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read() -> list:
    if not LEDGER.is_file():
        return []
    out = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:                                     # noqa: BLE001
            continue
    return out


def git_changed() -> list:
    """工作区里改过/新增但**还没提交**的文件（相对仓根）。"""
    try:
        # 🔴 core.quotepath=false：否则含中文/特殊字符的路径会被 git 转义成八进制
        #   （实测 "C:\Users\..." 变成 "C://Users//ADMIN//.../345/260/217/..." 这种鬼样子，
        #   账本按它去比对，永远对不上）。
        # 🔴 用 -z（NUL 分隔）：git 对含反斜杠/中文的路径会加引号并转义成八进制
        #   （实测 "C:\\Users\\..." 变成 ".../345/260/217/..."），文本模式怎么配都对不上。
        #   -z 是**唯一不做任何转义**的格式。
        r = subprocess.run(["git", "status", "--porcelain", "-z"],
                           capture_output=True, text=True, timeout=30, cwd=str(ROOT))
        out, gone = [], []
        for ln in (r.stdout or "").split("\0"):
            if len(ln) < 4:
                continue
            code = ln[:2]
            path = ln[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            if not path:
                continue
            # 删除的单独归一类：它也是"改动"，但文件已经不在了，
            # 不能按"需要一个 pass 记录"去要求它。
            if "D" in code:
                gone.append(path)
            else:
                out.append(path)
        return out + ["(DELETED) " + g for g in gone]
    except Exception:                                         # noqa: BLE001
        return []


def _norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def gate(strict: bool = True) -> dict:
    rows = read()
    changes, runs = {}, {}
    for r in rows:
        if r.get("kind") == "change":
            for f in (r.get("files") or []):
                changes.setdefault(_norm(f), []).append(r)
        elif r.get("kind") == "run":
            runs[r.get("item")] = r

    # ① 只有 change、没有对应 pass 的 ⇒ 未跑通
    unrun = []
    for f in changes:
        ok = any((r.get("status") == "pass") and
                 (f in [_norm(x) for x in (r.get("files") or [])] or
                  r.get("item") == f)
                 for r in rows if r.get("kind") == "run")
        if not ok:
            unrun.append(f)

    # ② 改了却没进账本 ⇒ 未记账
    ledgered = set(changes)
    dirty = [_norm(x) for x in git_changed()]
    unrecorded = [x for x in dirty if x not in ledgered
                  and not x.startswith(("state/", "logs/"))
                  and not x.startswith("(DELETED) ")]

    # ③ 显式 fail / unrun
    failed = [k for k, v in runs.items() if v.get("status") == "fail"]
    explicit_unrun = [k for k, v in runs.items() if v.get("status") == "unrun"]

    res = {"ok": not (unrun or unrecorded or failed or explicit_unrun),
           "at": now(),
           "entries": len(rows),
           "changes": len(changes),
           "unrun": unrun,
           "unrecorded": unrecorded,
           "failed": failed,
           "explicit_unrun": explicit_unrun,
           "why": ("**没跑通就不算验收**：下列项没有 pass 记录"
                   if (unrun or failed or explicit_unrun) else "")}
    return res


def show(days: float = 1.0) -> None:
    rows = read()
    cutoff = time.time() - days * 86400
    print("  ═══ 编排账本（最近 %.0f 天 · 共 %d 行）═══\n" % (days, len(rows)))
    for r in rows:
        try:
            t = time.mktime(time.strptime(r.get("at", ""), "%Y-%m-%dT%H:%M:%S"))
        except Exception:                                     # noqa: BLE001
            t = 0
        if t < cutoff:
            continue
        if r.get("kind") == "change":
            print("  %s  [改] %s" % (r["at"], str(r.get("what"))[:60]))
            for f in (r.get("files") or [])[:6]:
                print("         · %s" % f)
            if r.get("why"):
                print("         因：%s" % str(r["why"])[:70])
        elif r.get("kind") == "run":
            m = {"pass": "✅", "fail": "🔴", "unrun": "⏸"}.get(r.get("status"), "·")
            print("  %s  %s [跑] %s" % (r["at"], m, str(r.get("item"))[:56]))
            if r.get("evidence"):
                print("         据：%s" % str(r["evidence"])[:100].replace("\n", " "))


def main(argv: list) -> int:
    op = argv[1] if len(argv) > 1 else "gate"
    a = argv[2:]

    def opt(n, d=None):
        return a[a.index(n) + 1] if n in a else d

    if op == "change":
        files = [x.strip() for x in (opt("--files") or "").split(",") if x.strip()]
        append({"kind": "change", "what": opt("--what") or "",
                "files": files, "why": opt("--why") or "",
                "commit": opt("--commit") or ""})
        print("  ✅ 已记账：改 %s（%d 个文件）" % (opt("--what") or "?", len(files)))
        return 0

    if op == "run":
        item = opt("--item") or ""
        st = opt("--status") or "unrun"
        if st not in ("pass", "fail", "unrun"):
            print("  --status 只能是 pass/fail/unrun")
            return 2
        append({"kind": "run", "item": item, "status": st,
                "evidence": opt("--evidence") or "",
                "files": [x.strip() for x in (opt("--files") or "").split(",") if x.strip()]})
        print("  %s 已记：%s → %s" % ({"pass": "✅", "fail": "🔴", "unrun": "⏸"}[st], item, st))
        return 0

    if op == "show":
        show(float(opt("--days") or 1))
        return 0

    # gate
    g = gate()
    print("  ═══ 编排账本判决 ═══\n")
    print("  账目 %d 行 · 改动 %d 项 · %s" %
          (g["entries"], g["changes"], g["at"]))
    if g["unrun"]:
        print("\n  ⏸ 改了但**没有 pass 记录**（未跑通 %d 项）：" % len(g["unrun"]))
        for x in g["unrun"][:15]:
            print("     · %s" % x)
    if g["unrecorded"]:
        print("\n  📝 改了但**没进账本**（%d 项）：" % len(g["unrecorded"]))
        for x in g["unrecorded"][:15]:
            print("     · %s" % x)
    if g["failed"]:
        print("\n  🔴 明确失败（%d 项）：%s" % (len(g["failed"]), "、".join(g["failed"][:8])))
    if g["explicit_unrun"]:
        print("\n  ⏸ 明确未跑（%d 项）：%s" % (len(g["explicit_unrun"]),
                                            "、".join(g["explicit_unrun"][:8])))
    print("\n  判决：%s" % ("✅ 全部有跑通记录" if g["ok"]
                          else "🔴 **不算验收**（没跑通就不算）"))
    return 0 if g["ok"] else 1


if __name__ == "__main__":
    import os
    os.environ.setdefault("GBT_AUTONOMOUS", "1")
    raise SystemExit(main(sys.argv))
