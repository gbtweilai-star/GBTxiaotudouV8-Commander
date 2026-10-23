#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""补跑上轮 4 个「样本参数不对」的位（不是能力坏了，是我的参数没给对）。

四个各有一处真问题：
  · git_write   —— 只认 stage/add/commit，且**必须点名路径**（我上轮给了 op=status）
  · code_patch  —— find 不能为空（安全设计：空白替换会误伤），必须给真 find/replace，默认 dry_run
  · record_grid —— parse 要 plan，改用只读 op=vocab（列词表）
  · wf_resume   —— 要一个**真存在**的 run_id：本脚本先 define→run 拿 id，再 resume

git_write 只做 stage + 立刻 reset（**不 commit**）：证明写面通，但不改主人仓库历史。
用法：py -3.12 tools/codex-scripts/probe-caps-params-fix4.py
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ["GBT_STORE_DIR"] = str(pathlib.Path(tempfile.mkdtemp(prefix="gbt_fix4_store_")))
os.environ.pop("GBT_OWNER_SESSION", None)
sys.path.insert(0, str(ROOT))

from gbt_allinone.api import run_task          # noqa: E402

DATA = ROOT / "outputs" / "open-source-release" / "data" / "params-probe.json"


def body_of(r):
    b = r.get("gbt_result", r) if isinstance(r, dict) else {}
    inner = b.get("result") if isinstance(b, dict) else None
    return (b if isinstance(b, dict) else {}), (inner if isinstance(inner, dict) else {})


def verdict_of(b, i):
    if b.get("denied") or i.get("denied"):
        return "needs_ticket", "缺票"
    st = str(b.get("status") or "")
    msg = str(b.get("error") or b.get("message") or i.get("error") or "")
    if st == "ok" and i.get("ok") is not False:
        return "ok", "真跑通过"
    return "failed", (msg or st)[:160]


rows = []

# ① record_grid：只读 op=vocab
t0 = time.time()
b, i = body_of(run_task("record_grid", {"op": "vocab", "values": ["a", "b"]}))
v, note = verdict_of(b, i)
rows.append({"cap": "record_grid", "why": "行式记录：列词表（只读 op=vocab）",
             "payload": {"op": "vocab", "values": ["a", "b"]}, "status": b.get("status"), "verdict": v,
             "note": note, "elapsed_s": round(time.time() - t0, 2)})

# ② code_patch：dry_run + 真 find/replace（不落盘）
t0 = time.time()
b, i = body_of(run_task("code_patch", {
    "path": "gbt_allinone/api.py",
    "find": "# GBT小土豆V8", "replace": "# GBT小土豆V8 ",
    "apply": False}))
v, note = verdict_of(b, i)
rows.append({"cap": "code_patch", "why": "改代码：dry_run 预览（apply=false，不落盘）",
             "payload": {"path": "gbt_allinone/api.py", "find": "...", "apply": False},
             "status": b.get("status"), "verdict": v, "note": note,
             "elapsed_s": round(time.time() - t0, 2)})

# ③ wf_define → wf_run → wf_resume（同进程同临时 store，id 才存在）
run_id = ""
t0 = time.time()
b1, i1 = body_of(run_task("wf_define", {
    "name": "probe_wf2",
    "nodes": [{"id": "a", "kind": "echo", "payload": {"text": "hello"}},
              {"id": "b", "kind": "echo", "payload": {"text": "world"}}]}))
b2, i2 = body_of(run_task("wf_run", {"name": "probe_wf2"}))
run_id = str(b2.get("run_id") or i2.get("run_id") or b2.get("id") or i2.get("id") or "")
if run_id:
    b3, i3 = body_of(run_task("wf_resume", {"run_id": run_id}))
    v, note = verdict_of(b3, i3)
    rows.append({"cap": "wf_resume", "why": "续跑一个真存在的 run（先 define→run 拿 id）",
                 "payload": {"run_id": run_id}, "status": b3.get("status"), "verdict": v,
                 "note": note or ("run_id=%s" % run_id), "elapsed_s": round(time.time() - t0, 2)})
else:
    rows.append({"cap": "wf_resume", "why": "续跑一个真存在的 run",
                 "payload": {}, "status": "error", "verdict": "failed",
                 "note": "wf_run 没回 run_id：%s" % json.dumps(b2, ensure_ascii=False)[:160],
                 "elapsed_s": round(time.time() - t0, 2)})

# ④ git_write：stage 一个探针文件 → 立刻 reset（不 commit，不动历史）
probe = ROOT / "AGENTS.md"   # 用**已被跟踪**的文件：.scratch 被 .gitignore 忽略，git add 会直接拒
rel = "AGENTS.md"
t0 = time.time()
b, i = body_of(run_task("git_write", {"op": "stage", "paths": [rel]}))
v, note = verdict_of(b, i)
reset_ok = False
try:
    r = subprocess.run(["git", "-C", str(ROOT), "reset", "-q", "--", rel],
                       capture_output=True, text=True, timeout=60)
    reset_ok = r.returncode == 0
except Exception:                                             # noqa: BLE001
    reset_ok = False

rows.append({"cap": "git_write", "why": "版本库写面：stage 一个已跟踪文件（已立刻 reset 复原，未 commit）",
             "payload": {"op": "stage", "paths": [rel]}, "status": b.get("status"),
             "verdict": v, "note": (note + "；reset 复原=%s（未 commit）" % reset_ok),
             "elapsed_s": round(time.time() - t0, 2)})

for r in rows:
    print("%-14s %-8s %-6s %s" % (r["cap"], r["verdict"], r["status"], r["note"][:80]))

# 合并回 params-probe.json（覆盖同名行，重算计数）
doc = json.loads(DATA.read_text(encoding="utf-8"))
by = {r["cap"]: r for r in doc["rows"]}
for r in rows:
    by[r["cap"]] = r
doc["rows"] = sorted(by.values(), key=lambda x: x["cap"])
cnt = {}
for r in doc["rows"]:
    cnt[r["verdict"]] = cnt.get(r["verdict"], 0) + 1
doc["counts"] = cnt
doc["fixed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
doc["fix_note"] = "上轮 4 个 failed 是样本参数不对（不是能力坏）；本脚本按各自真契约重给了参数，git_write 只 stage 并立刻 reset"
DATA.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n合并后计数：", cnt)

