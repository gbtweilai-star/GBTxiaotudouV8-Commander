# -*- coding: utf-8 -*-
"""重启硬指令的判据 —— 咬「重启后到底做没做」（主人令 2026-10-11，逐字）

主人原话：
  「……可能**重启再问她她都不懂了**，这说明了你**没有接通上帝视角**……
    还有就是给大模型**重启机制下达一条硬性指令**，重启之后**必须查看框架使用以及自动自检**，
    发现**故障和黄色警报不能无视，必须追踪根因给我彻底修复**，然后**登记写发现了什么这么修复的**，
    然后**在下一步**。」

硬指令正文落在 HEARTBEAT.md 顶部那一节（重启之后按 6 步走）。
**本件是它的机器判据** —— 因为「靠自觉」正是主人说的那个病。

## 咬三件（每一件都要有真跑痕迹，不是文档承诺）
  ① 接通上帝视角：审计账本里近期有 gods_eye 的调用（event=ok / meta.kind=gods_eye）
  ② 自动自检：state/ 下近期有 boot-selfcheck 的落痕
  ③ 把发现登记：state/action-ledger.jsonl 近期有条目（发现 → 修法 → 证据）

## 判据档位（不许把「没做」念成「没关系」）
  ✅ 三件都有近期痕迹 ⇒ 绿
  ⚠️ 缺哪件就点名哪件（这是黄警：不许无视，要按硬指令补做）
  退出码：0 = 三件齐；1 = 有缺（黄警必须处理）

## 负控（真植入）
  窗口缩成 0 秒（等于刚重启、什么都还没做）⇒ 三件必须全缺、必须报黄；
  再喂一条合成的 gods_eye 记录 ⇒ 第一件必须变绿（证明它真在读账，不是恒绿/恒红）。

用法: py -3.14 -X utf8 tools/codex-scripts/restart-mandate-check.py [--hours N] [--json] [--selftest]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass

WS = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_HOURS = 24.0


def _store() -> pathlib.Path:
    sd = os.environ.get("GBT_STORE_DIR")
    if sd:
        return pathlib.Path(sd)
    return WS / "gbt_allinone" / "store"


def _tail_jsonl(path: pathlib.Path, max_lines: int = 4000) -> list:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            rows.append(ln)
            if len(rows) > max_lines:
                rows.pop(0)
    out = []
    for ln in rows:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:                       # noqa: BLE001
            continue
    return out


def _recent_iso(iso: str, hours: float, now: float) -> bool:
    try:
        t = time.mktime(time.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:                           # noqa: BLE001
        return False
    return (now - t) <= hours * 3600.0


def check(hours: float = DEFAULT_HOURS, store=None,
          rows_audit=None, rows_ledger=None) -> dict:
    st = pathlib.Path(store) if store else _store()
    now = time.time()
    audit = rows_audit if rows_audit is not None else _tail_jsonl(st / "audit.jsonl")
    ledger = (rows_ledger if rows_ledger is not None
              else _tail_jsonl(WS / "state" / "action-ledger.jsonl"))

    eye = [r for r in audit
           if (r.get("meta") or {}).get("kind") == "gods_eye"
           and _recent_iso(r.get("iso") or "", hours, now)]

    # 自检落痕：boot-selfcheck 由 unittest 驱动、不写 audit ⇒ 看 state 下的产物。
    # 口径从宽：任何近期的自检痕迹都算（本件先咬"做没做"，不咬"哪个文件"）。
 # 2026-10-11 自纠：glob 原来只写了下划线的 boot_selfcheck* / selfcheck*，
    #    而 boot-selfcheck.py 落的痕叫 **boot-selfcheck-last.json（连字符）** ⇒
    #    落痕明明写出来了，判据却报"没有"（实测首跑就是这样）。
    #    ⇒ 两种写法都认，别让命名风格把判据弄瞎。
    marks = []
    for pat in ("boot_selfcheck*", "boot-selfcheck*", "selfcheck*"):
        for f in (WS / "state").glob(pat):
            try:
                marks.append((f.name, f.stat().st_mtime))
            except OSError:
                continue
    sc_recent = [m for m in marks if (now - m[1]) <= hours * 3600.0]

    led = [r for r in ledger
           if _recent_iso(r.get("at") or r.get("iso") or "", hours, now)]

    items = {
        "接通上帝视角": {
            "ok": bool(eye),
            "evidence": ("近 %.0f 小时 %d 次 gods_eye 调用" % (hours, len(eye)))
                        if eye else "近期没跑过 gods_eye ⇒ 上帝视角没接通"},
        "自动自检": {
            "ok": bool(sc_recent),
            "evidence": ("近期 %d 个自检落痕：%s" % (len(sc_recent), sc_recent[0][0]))
                        if sc_recent
                        else ("state/ 下近期没有自检落痕（找到 %d 个，都不在窗口内）" % len(marks))},
        "把发现登记": {
            "ok": bool(led),
            "evidence": ("近 %.0f 小时 %d 条台账" % (hours, len(led)))
                        if led else "近期台账没有新条目 ⇒ 发现了什么、怎么修的没留痕"},
    }
    missing = [k for k, v in items.items() if not v["ok"]]
    return {"ok": not missing, "hours": hours, "missing": missing, "items": items,
            "store": str(st), "audit_rows": len(audit), "ledger_rows": len(ledger)}


def selftest() -> int:
    ok = []
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    real = check()
    ok.append(("真件·三件齐（重启后真做过）", bool(real.get("ok")),
               "缺：%s" % (real.get("missing") or "无")))
    zero = check(hours=0.0)
    ok.append(("真植入负控·窗口 0 秒 ⇒ 三件必须全缺（不许恒绿）",
               len(zero.get("missing") or []) == 3, "缺 %s" % zero.get("missing")))
    planted = [{"iso": now_iso, "meta": {"kind": "gods_eye"}}]
    r2 = check(hours=DEFAULT_HOURS, rows_audit=planted, rows_ledger=[])
    ok.append(("真植入负控·合成一条 gods_eye ⇒ 第一件必须变绿",
               r2["items"]["接通上帝视角"]["ok"] is True,
               str(r2["items"]["接通上帝视角"]["evidence"])))
    ok.append(("真植入负控·台账为空 ⇒ 第三件必须缺",
               r2["items"]["把发现登记"]["ok"] is False,
               str(r2["items"]["把发现登记"]["evidence"])))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d in ok:
        print("  %-46s %s  (%s)" % (n, "✅" if c else "❌", d))
    print("")
    print("restart-mandate-check 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="重启硬指令判据")
    ap.add_argument("--hours", type=float, default=DEFAULT_HOURS)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = check(a.hours)
    print("=" * 74)
    print("重启硬指令审查 —— 重启后到底做没做（主人令 2026-10-11）")
    print("=" * 74)
    print("  窗口：近 %.0f 小时 · 账本 %d 行 · 台账 %d 行"
          % (r["hours"], r["audit_rows"], r["ledger_rows"]))
    for k, v in r["items"].items():
        print("  %s %-14s %s" % ("✅" if v["ok"] else "⚠️", k, v["evidence"]))
    print("")
    if r["missing"]:
        print("  ⚠️ 黄警（硬指令要求：不许无视，按 HEARTBEAT.md 那一节补齐）：%s"
              % "、".join(r["missing"]))
    else:
        print("  ✅ 三件都做了：接通上帝视角 · 自动自检 · 把发现登记")
    print("")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
