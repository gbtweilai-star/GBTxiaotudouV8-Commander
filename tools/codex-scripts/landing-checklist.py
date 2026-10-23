# -*- coding: utf-8 -*-
"""landing-checklist -- 全部落实清单（逐项现读验证，不采信自述）"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
import os as _os
R = _os.environ.get("CHECK_ROUND", "v45")
PY = sys.executable
OK, RED = "\u2713", "\u2717"
rows = []


def has(p, needle=""):
    f = ROOT / p
    if not f.is_file():
        return False, "缺件"
    if needle and needle not in f.read_text(encoding="utf-8", errors="replace"):
        return False, "缺关键字"
    return True, str(f.stat().st_size) + "B"


def runs(args, needle=""):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=2400)
    o = (p.stdout or "") + (p.stderr or "")
    if needle and needle not in o:
        return False, ("rc=%d " % p.returncode) + o.strip().splitlines()[-1][:60]
    return p.returncode == 0, ("rc=%d " % p.returncode) + (o.strip().splitlines()[-1][:70] if o.strip() else "")


def add(name, fn):
    try:
        ok, r = fn()
    except Exception as e:
        ok, r = False, str(e)[:70]
    rows.append((name, ok, r))


add("omission-gate", lambda: runs([PY, "-X", "utf8", "tools/codex-scripts/omission-gate.py"], "C1"))
add("训练法 TRAINING_LAW.md(第35/36条)", lambda: has("TRAINING_LAW.md", "第 36 条"))
add("纪律件追加第35/36条", lambda: has("CODING_DISCIPLINE.md", "第 36 条"))
add("纪律件备份", lambda: (any((ROOT / ".backups").glob("*CODING_DISCIPLINE.md")), "备份在"))
add("保密过滤器 paper_guard 自测", lambda: runs([PY, "-X", "utf8", "tools/codex-scripts/paper_guard.py"], "自测: OK"))
add("公账无泄露 paper_loop check", lambda: runs([PY, "-X", "utf8", "tools/codex-scripts/paper_loop.py", "check"], "违规 0"))
add("今日手记公账在盘", lambda: has("memory/papers_public/2026-10-16.md"))
add("开工自检 6件", lambda: runs([PY, "-X", "utf8", "tools/codex-scripts/selfcheck-all.py", "--quick"], "红 0"))
add("判据健康度 judge-health", lambda: runs([PY, "-X", "utf8", "tools/codex-scripts/judge-health.py"], "翻正"))
add("三段闸 round-pipeline(v43)", lambda: runs([PY, "-X", "utf8", "tools/codex-scripts/round-pipeline.py", R, "--corpus", ".scratch/self_knowledge_" + R + ".jsonl", "--launcher", ".scratch/launch_" + R + ".py"], "允许点火"))
add("题面唯一性判据", lambda: runs([PY, "-X", "utf8", "tools/train/check_instruction_unique.py", "--corpus", ".scratch/self_knowledge_" + R + ".jsonl"], "跨族重复 0"))
add("预算内存熔断 0.5GB", lambda: has("tools/codex-scripts/blueprint-first.py", "MEM_FLOOR_GB"))
add("递归 N=3 上限", lambda: has("gbt_allinone/forge_mastery.py", "N=3"))
add("直达索引 direct-index", lambda: has("state/direct-index.json", "handler"))
add("肌肉训练 muscle-drill", lambda: runs([PY, "-X", "utf8", "tools/codex-scripts/muscle-drill.py", "check", "--min-rate", "0.9"], "PASS"))
add("定海神针红0", lambda: runs([PY, "-X", "utf8", "tools/codex-scripts/context-anchor.py", "check"], "红 0"))
add("第一原理闸 PASS", lambda: runs([PY, "-X", "utf8", "tools/codex-scripts/first-axiom-gate.py"], "红 0"))
add(R + " 语料+发射器+蓝图已批", lambda: ((ROOT / ".scratch" / ("self_knowledge_" + R + ".jsonl")).is_file() and (ROOT / ".scratch" / ("launch_" + R + ".py")).is_file() and any((ROOT / "state/blueprints").glob("*" + R + "*.approved")), "三件齐"))

good = sum(1 for _, ok, _ in rows if ok)
print("落实清单：%d/%d 项通过" % (good, len(rows)))
for n, ok, r in rows:
    print("  %s %-34s %s" % (OK if ok else RED, n, r))
print("== 全部落实 %s ==" % ("PASS" if good == len(rows) else "FAIL"))
raise SystemExit(0 if good == len(rows) else 1)
