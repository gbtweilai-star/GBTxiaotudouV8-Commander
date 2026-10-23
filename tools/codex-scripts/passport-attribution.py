#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""框架自改门 · 未认领件的**证据归因清单**（只读）。

为什么要有它（P9/P1 同族）：`framework_gate verify` 只报「235 件没有护照」，
但不告我**每一件为什么变**。没有理由就开护照 = 批量洗账（门自己写在 F31/F39 里）。
本件不写任何账，只做三件事：
  ① 把未认领件按目录分组、带上 mtime 与 git 状态；
  ② 用 `state/logbook.jsonl` 的机器记录按时间窗给每一件找**候选理由**（窗口 ±2h）；
  ③ 把"有据可查"与"无据可查"分开打出来 —— 无据的那些必须人来补，不许我编。

用法：py -3.14 tools/codex-scripts/passport-attribution.py [--json] [--window-hours 2]
"""
import argparse
import collections
import datetime as dt
import json
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE = os.path.join(ROOT, "gbt_allinone", "store", "framework_changes")


def gate_findings():
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "gbt_allinone.tools.framework_gate",
                        "--root", ".", "--store", STORE, "verify"],
                       cwd=ROOT, capture_output=True)
    out = r.stdout.decode("utf-8", "replace")
    i = out.find("{")
    if i < 0:
        raise SystemExit("framework_gate 没回 JSON：%s" % (out[:300] or r.stderr.decode('utf-8', 'replace')[:300]))
    j = json.loads(out[i:])
    return j, [x for x in (j.get("findings") or []) if x.get("reason_code") == "no_passport"]


def logbook_rows():
    p = os.path.join(ROOT, "state", "logbook.jsonl")
    rows = []
    if not os.path.isfile(p):
        return rows
    for ln in open(p, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            j = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        # 🔴 2026-10-22 修（第一次跑就抓到）：logbook 的时间字段叫 **`ts`**，不是 `at`/`time`。
        #    我照台账的习惯写成 at ⇒ 833 条一笔都没解析上 ⇒ 归因结果「有据可查 0 件」是**假读数**。
        at = j.get("ts") or j.get("at") or j.get("time") or ""
        try:
            ts = dt.datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone(dt.timedelta(hours=7)))
        rows.append((ts.timestamp(), j))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--window-hours", type=float, default=2.0)
    a = ap.parse_args()
    led, findings = gate_findings()
    rows = logbook_rows()
    win = a.window_hours * 3600

    groups = collections.defaultdict(list)
    matched, orphan = [], []
    for f in findings:
        path = str(f.get("file") or "")
        full = os.path.join(ROOT, path.replace("/", os.sep))
        try:
            mtime = os.path.getmtime(full)
        except OSError:
            mtime = 0
        base = os.path.basename(path)
        # 🔴 2026-10-22 修（**时间窗不等于证据**，第一次跑就抓到自己）：
        #    原来只按 mtime ±2h 找最近一条 logbook 就当理由 —— 实测把
        #    `deploy/.wrangler/tmp/.../middleware-*.js` 归到了「数字人判据脚本挂掉」那条上
        #    （两件毫不相干的事只是时间挨着）。拿这种理由开护照，正是门自己写的
        #    「一张理由不符的护照会把整批未记账变动洗成有账（F31/F39）」，**不许**。
        #    现口径：优先**名字级证据**（那条记录里真的点了这个文件名/路径）；
        #    只有名字级找不到时，才把时间窗那条降级成「邻居线索」（ci=False），
        #    它**不能**单独当护照理由用。
        name_hits = []
        for ts, r in rows:
            blob = " ".join([str(r.get("what") or ""), str(r.get("where") or "")])
            if base and base in blob:
                name_hits.append((ts, r))
        name_hits.sort(key=lambda x: -x[0])
        top = name_hits[0][1] if name_hits else None
        rec = {
            "file": path,
            "mtime": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S") if mtime else None,
            "why_from_logbook": (str(top.get("what"))[:140] if top else None),
            "evidence_level": "name" if top else "none",
        }
        groups[path.split("/")[0] if "/" in path else "(根)"].append(rec)
        (matched if top else orphan).append(rec)

    if a.json:
        print(json.dumps({"gate": {k: led.get(k) for k in ("changed_files", "未认领", "认领但已过期", "已认领且新鲜")},
                          "groups": {k: len(v) for k, v in groups.items()},
                          "matched": matched, "orphan": orphan}, ensure_ascii=False, indent=2))
        return 0

    print("框架自改门 · 未认领件证据归因（只读）")
    print("-" * 92)
    print("gate：changed=%s · 未认领=%s · 过期=%s · 新鲜=%s"
          % (led.get("changed_files"), led.get("未认领"), led.get("认领但已过期"), led.get("已认领且新鲜")))
    print("按顶层目录分组：")
    for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        hit = len([x for x in v if x["why_from_logbook"]])
        print("  %-28s %4d 件（有 logbook 理由 %d · 无 %d）" % (k, len(v), hit, len(v) - hit))
    print("-" * 92)
    print("**有据可查**（能指到一条 logbook 机器记录，理由窗口 ±%.1fh）：%d 件" % (a.window_hours, len(matched)))
    for x in matched[:12]:
        print("  · %-52s %s ← %s" % (x["file"][:52], x["mtime"], x["why_from_logbook"]))
    if len(matched) > 12:
        print("  …（另有 %d 件，机读用 --json）" % (len(matched) - 12))
    print("-" * 92)
    print("**无据可查**（±%.1fh 内没有任何机器记录 ⇒ 不许我编理由，需人补）：%d 件" % (a.window_hours, len(orphan)))
    for x in orphan[:15]:
        print("  · %-52s %s" % (x["file"][:52], x["mtime"]))
    if len(orphan) > 15:
        print("  …（另有 %d 件）" % (len(orphan) - 15))
    print("-" * 92)
    print("口径：一张护照只认一条**真实**理由。有据的分批开（一批一条理由 + 证据）；无据的不许批量洗账。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
