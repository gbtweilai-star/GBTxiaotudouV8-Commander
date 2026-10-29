# -*- coding: utf-8 -*-
"""从 block3_probe_prod.json 蒸馏出「块3 落生产前改前基线」工件。"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
PROD = ROOT / "holo_pet" / "panel_server.py"
PROBE = ROOT / ".scratch" / "block3_probe.py"
SRC = ROOT / ".scratch" / "block3_probe_prod.json"
OUT = ROOT / ".scratch" / "block3_baseline_final.json"

pb = PROD.read_bytes()
d = json.loads(SRC.read_text(encoding="utf-8"))
cells = {}
for s in d["scenes"]:
    cells[s["scene"]] = {"guard": s["guard"], "new": s["new"], "resume_count": s["resume_count"],
                         "resume_frames_in_bridge": s["resume_frames_in_bridge"],
                         "verdict": s["verdict"], "hit": s["hit"],
                         "mock_event": s.get("mock_event")}
fails = [a["tag"] for a in d["asserts"] if not a["ok"]]
art = {
    "label": "第②步·块3 —— 落生产前改前基线（同一探针 --target=prod）",
    "target": "prod",
    "target_path": "holo_pet/panel_server.py",
    "target_sha256": hashlib.sha256(pb).hexdigest(),
    "target_lines": pb.decode("utf-8").count("\n"),
    "probe_sha256": hashlib.sha256(PROBE.read_bytes()).hexdigest(),
    "asserts_total": len(d["asserts"]),
    "asserts_pass": len(d["asserts"]) - len(fails),
    "asserts_fail": len(fails),
    "failed_tags": fails,
    "scenes": cells,
    "改前两格": {
        "换连接+守卫关": {"resume_frames_in_bridge": cells["C2 换连接(守卫关)"]["resume_frames_in_bridge"],
                    "verdict": cells["C2 换连接(守卫关)"]["verdict"],
                    "hit": cells["C2 换连接(守卫关)"]["hit"],
                    "new": cells["C2 换连接(守卫关)"]["new"],
                    "定性": "静默复用陈旧 tid = 病灶"},
        "换连接+守卫开": {"resume_frames_in_bridge": cells["C1 换连接(守卫开)"]["resume_frames_in_bridge"],
                    "verdict": cells["C1 换连接(守卫开)"]["verdict"],
                    "hit": cells["C1 换连接(守卫开)"]["hit"],
                    "new": cells["C1 换连接(守卫开)"]["new"],
                    "定性": "反应式兜底（发了、被拒、才重建）"},
    },
    "判据": "落生产后用同一探针 --target=prod 复跑，应 22/22 PASS（本文件 9 项 FAIL 全转 PASS）",
    "source_artifacts": [".scratch/block3_probe_prod.json", ".scratch/block3_probe_prod.jsonl",
                         ".scratch/block3_probe_prod.mock.jsonl", ".scratch/block3_probe_prod.out.txt"],
}
OUT.write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")
print("落盘:", OUT)
print("生产 sha256[:8] =", art["target_sha256"][:8], "| 行数 =", art["target_lines"])
print("断言 %d 项 PASS %d FAIL %d" % (art["asserts_total"], art["asserts_pass"], art["asserts_fail"]))
for t in fails:
    print("   FAIL:", t)
print("改前两格:")
for k, v in art["改前两格"].items():
    print("  %s -> resume帧=%s verdict=%s hit=%s new=%s (%s)"
          % (k, v["resume_frames_in_bridge"], v["verdict"], v["hit"], v["new"], v["定性"]))
