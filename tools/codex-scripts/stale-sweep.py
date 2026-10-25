#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""旧件扫描判据（stale-sweep）—— 主人令：「旧的东西别留直接清理」

为什么要这件：本会话实测踩过两次——
  ① **人被旧件带偏**：`gbt_allinone/*.bak-*` 旧副本里还有旧分支，grep 一扫就中，
     读到的可能是旧代码；
  ② **机器人也会踩**：用 `*.old` 直扫时把 **Chromium 档案内部的 68 个 `LOG.old`**
     也当成旧件清了 —— 那不是我们的产物。所以本件**带排除面**（浏览器档案 / .git / _upstream / plugins）。

四类：C1 备份与临时后缀 · C2 被取代产物（同族多份）· C3 过期读数（文件内 at 超期）
      C4 过期文档（写了已失效的域名/端点）。负对照：四类各造一个假旧件 ⇒ 必须红。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

EXCLUDE_DIRS = (".git", "node_modules", "_upstream", "plugins", ".pylibs", "site-packages",
                "native_browser", "__pycache__", ".venv", "dist")   # 浏览器档案等**不是我们的产物**
JUNK_SUFFIX = (".bak", ".old", ".orig", ".rej", ".tmp")
JUNK_PREFIX = ("~$",)
STALE_DAYS = 7.0
DEAD_MARKERS = ("lopaycn.workers.dev",)   # 2026-10-11 已迁 paysssk；旧域名不许再出现在在役文档/代码
# 2026-10-16 对齐：**血统台账不是垃圾** —— `recipe_v*` 是参数代际真源（recipe_v25 自己写着
#   「v25 = v24 的补数据代，实参一字未改」）⇒ 只对**同名数据体**（self_knowledge_v*.jsonl）清旧。
#   白名单**带理由**，不是静默跳过。
LINEAGE_KEEP = ("recipe_v",)
CORPUS_STEM = re.compile(r"^(recipe_v|self_knowledge_v)(\d+)")


def _skip(p: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in p.parts)


def scan(root: Path = None) -> dict:
    root = root or WS
    junk, stale, dead, corpora = [], [], [], {}
    now = time.time()
    for p in root.rglob("*"):
        if p.is_dir() or _skip(p):
            continue
        try:
            if p.stat().st_size > 400_000:
                continue
        except OSError:
            continue
        name = p.name
        rel = str(p.relative_to(root)).replace(chr(92), "/")
        if name.endswith(JUNK_SUFFIX) or name.startswith(JUNK_PREFIX) or ".bak-" in name:
            junk.append(rel)
            continue
        m = CORPUS_STEM.match(name)
        if m:
            corpora.setdefault(m.group(1), []).append((int(m.group(2)), rel))
        if not name.endswith((".json", ".md", ".py", ".jsonl")):
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dm in DEAD_MARKERS:
            if dm in t:
                dead.append({"file": rel, "marker": dm})
                break
        for ts in re.findall(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d", t[:4000]):
            try:
                age = (now - time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%S"))) / 86400.0
            except ValueError:
                continue
            if age > STALE_DAYS:
                stale.append({"file": rel, "at": ts, "age_days": round(age, 1)})
            break
    superseded = []
    for fam, rows in corpora.items():
        if fam in LINEAGE_KEEP:          # 代际台账保留（见 LINEAGE_KEEP 理由）
            continue
        rows.sort()
        for ver, rel in rows[:-1]:
            superseded.append({"family": fam, "version": ver, "file": rel})
    bad = bool(junk) or bool(dead) or bool(superseded)
    return {"ok": not bad, "kind": "stale_sweep", "junk": junk[:40], "junk_count": len(junk),
            "superseded": superseded[:20], "superseded_count": len(superseded),
            "stale_readings": stale[:25], "stale_count": len(stale),
            "dead_markers": dead[:20], "dead_count": len(dead),
            "exclude_dirs": list(EXCLUDE_DIRS), "stale_days": STALE_DAYS,
            "note": "旧件三类（备份/被取代/失效标记）非零即红；过期读数只报不算红（读数本来就有时效）"}


def selftest(tmp: Path) -> dict:
    """四类各造一个假旧件 ⇒ 必须点出；空树 ⇒ 必须全绿。"""
    (tmp / "a.py.bak-20261016").write_text("x", encoding="utf-8")
    # 2026-10-16 修（实测踩过）：原来拿 `recipe_v24/v25` 当被取代的**假例**，可 recipe 进了
    #   LINEAGE_KEEP（代际台账保留）⇒ 假例不再被咬、负控变成瞎的（selftest FAIL）。
    #   假例必须用**非血统名**，否则测的是白名单，不是判据。
    (tmp / "self_knowledge_v24.jsonl").write_text("{}", encoding="utf-8")
    (tmp / "self_knowledge_v25.jsonl").write_text("{}", encoding="utf-8")
    (tmp / "doc.md").write_text("gbt-potato-cloud-10.lopaycn.workers.dev", encoding="utf-8")
    (tmp / "old.json").write_text('{"at": "2020-01-01T00:00:00"}', encoding="utf-8")
    r = scan(tmp)
    outs = {"备份被咬": r["junk_count"] >= 1, "被取代被咬": r["superseded_count"] >= 1,
            "失效域名被咬": r["dead_count"] >= 1, "过期读数被咪": r["stale_count"] >= 1,
            "负例当红": r["ok"] is False}
    empty = tmp / "empty"
    empty.mkdir(exist_ok=True)
    outs["空树全绿"] = scan(empty)["ok"] is True
    return {"ok": all(outs.values()), "kind": "stale_sweep_selftest", **outs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="旧件扫描（带排除面）")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        import tempfile
        r = selftest(Path(tempfile.mkdtemp(prefix="stale_")))
    else:
        r = scan()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("旧件扫描：%s · 备份 %d · 被取代 %d · 失效标记 %d · 过期读数 %d"
              % ("PASS" if r["ok"] else "FAIL", r.get("junk_count", 0), r.get("superseded_count", 0),
                 r.get("dead_count", 0), r.get("stale_count", 0)))
        for x in (r.get("junk") or [])[:8]:
            print("  ✖ 备份 " + x)
        for x in (r.get("superseded") or [])[:8]:
            print("  ✖ 被取代 " + x["file"])
        for x in (r.get("dead_markers") or [])[:8]:
            print("  ✖ 失效标记 " + x["file"] + " ← " + x["marker"])
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
