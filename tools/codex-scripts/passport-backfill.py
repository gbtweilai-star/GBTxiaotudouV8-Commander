#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""框架自改门 · **按 logbook 名字级证据**分批补护照（只补有据的，不洗账）。

口径（为什么这么分）：
  · 一张护照的理由必须**真的覆盖**它认领的文件 —— 门自己写着「一张理由不符的护照会把整批
    未记账变动洗成有账（F31/F39）」。所以分组的单位是**一条 logbook 机器记录**：
    那条记录里点到了哪些文件，就只认领哪些文件。
  · 没有名字级证据的文件**一件都不认领**，如实列出来给人补。

用法：
  py -3.14 tools/codex-scripts/passport-backfill.py --dry-run     # 只打分组
  py -3.14 tools/codex-scripts/passport-backfill.py --apply      # 真开真关
  py -3.14 tools/codex-scripts/passport-backfill.py --apply --limit 3
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


def gate(*args):
    return subprocess.run([sys.executable, "-X", "utf8", "-m", "gbt_allinone.tools.framework_gate",
                           "--root", ".", "--store", STORE] + list(args),
                          cwd=ROOT, capture_output=True)


def findings(kind="no_passport"):
    r = gate("verify")
    out = r.stdout.decode("utf-8", "replace")
    i = out.find("{")
    if i < 0:
        raise SystemExit("gate verify 没回 JSON：%s" % out[:300])
    j = json.loads(out[i:])
    return [x for x in (j.get("findings") or []) if x.get("reason_code") == kind]


def logbook():
    rows = []
    p = os.path.join(ROOT, "state", "logbook.jsonl")
    for ln in open(p, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            j = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        rows.append(j)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-files", type=int, default=1)
    ap.add_argument("--include-stale", action="store_true",
                    help="连『认领但已过期』一起补：这些件有旧护照、只是护照关闭后又改过，"
                         "同样要求**名字级 + 时间窗**双证据才认领")
    a = ap.parse_args()

    raw = findings("no_passport")
    if a.include_stale:
        raw += findings("stale_passport")
    fs = [str(x.get("file") or "") for x in raw]
    rows = logbook()
    # 🔴 2026-10-22 加（第一次 dry-run 就抓到假归因）：**同名文件不许拿 basename 当凭据**。
    #    实测：logbook#127 里点了 "index.html"，我拿 basename 去配，一口气把 24 个不同的
    #    index.html 全归到那一条上 —— 那是把「名字撞了」当「证据」。现口径：
    #      · basename 在本批未认领件里**唯一** ⇒ 允许用 basename 匹配；
    #      · 不唯一 ⇒ 必须**点全路径**才算有据，否则算无据。
    counts = collections.Counter(os.path.basename(f) for f in fs)

    def entry_blob(r):
        return str(r.get("what") or "") + " " + str(r.get("where") or "")

    by_entry = collections.defaultdict(list)
    orphan = []
    for f in fs:
        base = os.path.basename(f)
        blob_needed = counts[base] > 1
        try:
            mtime = os.path.getmtime(os.path.join(ROOT, f.replace("/", os.sep)))
        except OSError:
            mtime = 0
        hits = []
        for r in rows:
            blob = entry_blob(r)
            if blob_needed:
                if f not in blob:                  # 必须点全路径
                    continue
            elif not (base and base in blob):
                continue
            # 🔴 2026-10-22 加（P1 第二次同型）：名字级**还不够** —— 同一个文件在几个月里
            #    被改过很多次，一条 9 月的记录点过它，不代表 10 月这次改动就是那一次。
            #    现口径：名字级 + **时间窗**（记录时间与文件 mtime 相差 ≤12h）双证据才算。
            try:
                ts = dt.datetime.fromisoformat(str(r.get("ts") or "").replace("Z", "+00:00")).timestamp()
            except Exception:  # noqa: BLE001
                continue
            if mtime and abs(ts - mtime) <= 12 * 3600:
                hits.append(r)
        if hits:
            hits.sort(key=lambda r: str(r.get("ts") or ""), reverse=True)
            by_entry[int(hits[0].get("n") or 0)].append(f)
        else:
            orphan.append(f)

    print("未认领 %d 件 → 可归到 %d 条 logbook 记录 · 无据 %d 件"
          % (len(fs), len(by_entry), len(orphan)))
    plans = []
    for n, files in sorted(by_entry.items(), reverse=True):
        rec = next((r for r in rows if int(r.get("n") or 0) == n), {})
        if len(files) < a.min_files:
            continue
        plans.append((n, rec, files))
    for n, rec, files in plans:
        print("  #%s %s ｜ %d 件：%s" % (n, str(rec.get("ts"))[:19], len(files),
                                        ", ".join(os.path.basename(x) for x in files[:4]) + ("…" if len(files) > 4 else "")))
    if orphan:
        print("  无据（不认领）：%s%s" % (", ".join(os.path.basename(x) for x in orphan[:8]),
                                    " …" if len(orphan) > 8 else ""))

    if not a.apply:
        print("\n（dry-run：一账未开。要落盘加 --apply）")
        return 0

    done = 0
    for n, rec, files in plans:
        if a.limit and done >= a.limit:
            break
        what = str(rec.get("what") or "").strip()
        if not what:
            continue
        reason = "历史自改补账 #%s：%s" % (n, what[:110])
        r = gate("open", "--reason", reason, "--label", "backfill-%s" % n)
        out = r.stdout.decode("utf-8", "replace")
        i = out.find("{")
        if i < 0:
            print("  🔴 #%s 开护照失败：%s" % (n, out[:160]))
            continue
        pid = json.loads(out[i:]).get("id")
        args = ["close", "--id", str(pid),
                "--evidence", "logbook#%s => %s（sha256 见 state/logbook.jsonl 该笔）" % (n, what[:120]),
                "--no-review-reason", "历史变更补账：理由是当轮 logbook 机器记录，当时没有独立复核人",
                "--no-stamp-reason", "历史变更补账：当时未盖四元组印章，本轮不伪造",
                "--rollback", "按 logbook#%s 的反向操作回滚（该笔若无可逆记录，须人来定）" % n]
        for f in files:
            args += ["--files", f]
        r2 = gate(*args)
        out2 = r2.stdout.decode("utf-8", "replace")
        ok = '"ok": true' in out2
        print("  %s #%s → %s（%d 件）" % ("✅" if ok else "🔴", n, pid, len(files)))
        if not ok:
            print("      ", out2.replace("\n", " ")[:220])
        done += 1 if ok else 0

    r = gate("verify")
    out = r.stdout.decode("utf-8", "replace")
    i = out.find("{")
    j = json.loads(out[i:])
    print("\n复跑：changed=%s · 未认领=%s · 过期=%s · 新鲜=%s · verdict=%s"
          % (j.get("changed_files"), j.get("未认领"), j.get("认领但已过期"),
             j.get("已认领且新鲜"), j.get("verdict")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
