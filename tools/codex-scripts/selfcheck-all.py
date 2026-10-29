# -*- coding: utf-8 -*-
"""selfcheck-all -- --quick = 8 项纯文件检查（秒级，零子进程）；无参 = 全量清册 + 15 判据。
"""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
OUT = ROOT / "state" / "selfcheck-all.json"
IDXDIR = ROOT / "state" / "project-shards"
SKIP = {".git", "node_modules", "__pycache__", ".backups", "vendor", ".venv", "dist", "build", ".scratch"}


def inventory():
    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in SKIP for part in rel.parts):
            continue
        files.append(rel)
    return sorted(files, key=lambda r: str(r).lower())


def shard_index(files, shards=16):
    IDXDIR.mkdir(parents=True, exist_ok=True)
    groups = [[] for _ in range(shards)]
    for i, rel in enumerate(files):
        groups[i % shards].append(rel)
    made = []
    for i, g in enumerate(groups):
        rows = "".join('<li><a href="../../%s">%s</a></li>' % (str(r).replace(chr(92), "/"), r) for r in g)
        (IDXDIR / ("shard-%02d.html" % i)).write_text(
            '<!doctype html><meta charset="utf-8"><body style="background:#0b0d10;color:#e8ecf1;font:14px/1.7 system-ui;padding:16px">'
            '<h1>分片 %02d · %d 个文件</h1><ul>%s</ul></body>' % (i, len(g), rows), encoding="utf-8")
        made.append((i, len(g)))
    return made


def quick():
    def rd(rel):
        f = ROOT / rel
        return f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""
    checks = [
        ("训练法第36条", "第 36 条" in rd("TRAINING_LAW.md")),
        ("纪律件同步", "第 36 条" in rd("CODING_DISCIPLINE.md")),
        ("纪律件备份", len(list((ROOT / ".backups").glob("*CODING_DISCIPLINE.md"))) > 0),
        ("直达索引", "handler" in rd("state/direct-index.json")),
        ("语音台湾腔", "zh-TW-HsiaoChenNeural" in rd("gbt_allinone/voice_cap.py")),
        ("全项目分片", len(list((ROOT / "state" / "project-shards").glob("shard-*.html"))) > 0),
 # 口径改了（2026-10-22 主人令留痕）：原来这里判 `state/PROJECT-INDEX.html` 在不在。
        #   主人看了那页（截图）+ 原话「把这页删了，你自己看看这种东西都能做出来？」⇒ 页面已移到
        #   `state/legacy/PROJECT-INDEX.html.20261022`。**原期望：在；翻成：不在才对**，
        #   所以判据改成「不在 = OK」，并保留一行说明谁删的、搬去哪 —— 不是静默翻。
        ("总索引已下线", not (ROOT / "state" / "PROJECT-INDEX.html").is_file()),
        ("接线门账本", (ROOT / "state" / "wire-dispositions.json").is_file()),
    ]
    red = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print("  %-14s %s" % (n, "OK" if ok else "RED"))
    print("== 开工自检（quick）：共 %d 件 · 红 %d ==" % (len(checks), len(red)))
    return 0 if not red else 1


def run(args, t=600):
    try:
        r = subprocess.run([PY, "-X", "utf8"] + args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT), timeout=t)
        o = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        return r.returncode, (o[-1][:120] if o else "无输出")
    except Exception as e:
        return -1, str(e)[:100]


def main():
    if "--quick" in sys.argv:
        return quick()
    files = inventory()
    made = shard_index(files)
    print("全量清册：**%d 个文件**" % len(files))
    print("分片索引：%d 片 -> state/project-shards/" % len(made))
    JUDGES = [
        ("台账-能力面", ["tools/codex-scripts/capability-audit.py"]),
        ("全项目绑定", ["tools/codex-scripts/project-bind.py", "--check"]),
        ("四目标部署", ["tools/codex-scripts/deploy-targets.py", "--check"]),
        ("缺口总账", ["tools/codex-scripts/gap-ledger.py"]),
        ("能力位缺口", ["tools/codex-scripts/capbinding-gaps.py"]),
        ("接线门", ["tools/codex-scripts/wire-gate.py"]),
        ("判据健康度", ["tools/codex-scripts/judge-health.py"]),
        ("语音默认", ["tools/codex-scripts/tts-default-check.py"]),
        ("第一原理闸", ["tools/codex-scripts/first-axiom-gate.py"]),
        ("定海神针", ["tools/codex-scripts/context-anchor.py", "check"]),
        ("肌肉训练", ["tools/codex-scripts/muscle-drill.py", "check", "--min-rate", "0.9"]),
        ("题面唯一性", ["tools/train/check_instruction_unique.py", "--corpus", ".scratch/self_knowledge_v47.jsonl"]),
        ("语义唯一性", ["tools/train/check_instruction_semantic.py", "--corpus", ".scratch/self_knowledge_v47.jsonl"]),
    ]
    rows, red = [], 0
    for name, cmd in JUDGES:
        rc, last = run(cmd)
        v = "PASS" if rc == 0 else "RED"
        if rc != 0:
            red += 1
        rows.append({"判据": name, "verdict": v, "rc": rc, "readout": last})
        print("  %-16s %-4s %s" % (name, v, last))
    OUT.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "文件总数": len(files),
                               "判据": rows, "红数": red}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("== 自检合计：%d 项 · **红 %d** ==" % (len(rows), red))
    return 0 if red == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
