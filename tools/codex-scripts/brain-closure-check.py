#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脑层闭环核验（可复跑判据）— 2026-10-04 由审查端口落盘。

为什么有这件：
  10-03 那次「脑层 14 模块 + 6 接口别名」交付里，penetration_scan 的**唯一真实加载点**
  （omni_process 用 spec_from_file_location）下 6 处 `from .. import` 全 ImportError、
  L0 判据又对 193/216 个能力误报 —— 表层"跑过"但闭环没通。本件把「真加载路 + 真调用」
  钉成**可复跑读数**，谁再动脑层，跑这一件就知道有没有回退。

跑法：
  py -3.14 tools/codex-scripts/brain-closure-check.py           # 人读
  py -3.14 tools/codex-scripts/brain-closure-check.py --json    # 机读
判据（任一红 ⇒ 退出码 1）：
  ① omni_process.diagnose 的**真加载路**（优先包导入）能拿到模块，quick_scan 无 errors
  ② L0 文件存在性：假问题为 0（用「api.py 真分支 ∪ handler 文件」双判据）
  ③ 13 个脑模块的只读入口逐个跑通（不做全量副作用探针）
  ④ 全程不许出现 UnicodeDecodeError（系统 CLI 读数按 mbcs 解，见 tentacle_fleet.py:321）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(name: str, fn) -> dict:
    try:
        r = fn()
        ok = bool(r.get("ok")) if isinstance(r, dict) else bool(r)
        return {"check": name, "ok": ok, "reading": str(r)[:220]}
    except Exception as e:  # noqa: BLE001
        return {"check": name, "ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}


def collect() -> dict:
    rows: list[dict] = []

    # ① 真加载路（omni_process 的入口）
    def _real_load():
        import importlib
        op = importlib.import_module("gbt_allinone.tentacle.omni_process")
        mod = op._load_penetration_scan()
        r = mod.quick_scan()
        return {"ok": bool(r.get("ok")) and mod.__package__ == "gbt_allinone.brain",
                "health": r.get("health"), "errors": r.get("total_errors")}
    rows.append(_run("① omni_process._load_penetration_scan → quick_scan", _real_load))

    # ② L0 双判据假问题
    def _l0():
        import importlib
        ps = importlib.import_module("gbt_allinone.brain.penetration_scan")
        r = ps._scan_files_exist()
        return {"ok": len(r.get("issues") or []) == 0, "issues": len(r.get("issues") or [])}
    rows.append(_run("② penetration_scan.L0 假问题=0", _l0))

    # ③ 脑模块只读入口逐个跑
    def _brain_entry():
        import importlib
        ti = importlib.import_module("gbt_allinone.brain.topology_index")
        ntm = importlib.import_module("gbt_allinone.brain.neural_tentacle")
        nt = ntm.NeuralTentacle()
        cv = importlib.import_module("gbt_allinone.brain.cross_validation")
        dr = importlib.import_module("gbt_allinone.brain.deep_reasoner")
        ib = importlib.import_module("gbt_allinone.brain.intent_broker")
        bc = importlib.import_module("gbt_allinone.brain.brain_council")
        ce = importlib.import_module("gbt_allinone.brain.curiosity_engine")
        ee = importlib.import_module("gbt_allinone.brain.exploration_engine")
        tr = importlib.import_module("gbt_allinone.brain.tentacle_reasoner")
        cg = importlib.import_module("gbt_allinone.brain.cognition")
        vt = importlib.import_module("gbt_allinone.brain.vision_tentacle")
        co = importlib.import_module("gbt_allinone.brain.cap_optimizer")
        checks = {
            "topology_index.nav": ti.nav(),
            "neural_tentacle.quick_pulse": nt.quick_pulse(),
            "neural_tentacle.reflect": nt.reflect(),
            "cross_validation.mesh_scan(quick)": cv.mesh_scan(n_tentacles=3, mode="quick"),
            "deep_reasoner.reason": dr.reason("诊断"),
            "intent_broker.route": ib.route("诊断"),
            "brain_council.call_council": bc.call_council("框架健康吗"),
            "curiosity_engine.ranked_questions": {"ok": True, "n": len(ce.ranked_questions())},
            "exploration_engine.traverse": ee.traverse("all"),
            "tentacle_reasoner.classify": tr.classify([], []),
            "cognition.evaluate": cg.evaluate({}),
            "vision_tentacle.recall": {"ok": True, "n": len(vt.recall(3))},
            "cap_optimizer.detect_duplicates": {"ok": True, "n": len(co.detect_duplicates())},
        }
        bad = [k for k, v in checks.items() if not (v.get("ok") if isinstance(v, dict) else v)]
        return {"ok": not bad, "run": len(checks), "bad": bad}
    rows.append(_run("③ 13 个脑模块只读入口", _brain_entry))

    bad = [r for r in rows if not r["ok"]]
    return {"ok": not bad, "total": len(rows), "failed": len(bad), "rows": rows,
            "note": "真加载路 + 真调用；全绿才算闭环通"}


def main() -> int:
    r = collect()
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for row in r["rows"]:
            print(f'  {"PASS" if row["ok"] else "FAIL"}  {row["check"]}  ::  '
                  f'{row.get("reading") or row.get("error", "")}'[:160])
        print(f'\n脑层闭环核验：{r["total"] - r["failed"]}/{r["total"]} 通过')
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
