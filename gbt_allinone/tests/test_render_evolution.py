# -*- coding: utf-8 -*-
"""渲染进化内核 · 带牙用例（R-H191）。

① 五原语齐，且**诚实标注盘上状态**（只有 HyperFrames/Remotion 有影子，三者盘上没有）；
② 红线①：无基线不许进化；
③ 红线②：无种子不许复现（基线无种子 ⇒ 拒；无种子基因记实验 ⇒ 拒）；
④ 红线③：未测不按绿（缺客观指标 ⇒ metrics_missing）；
⑤ 红线④：机器不替人判（缺人审分 ⇒ human_verdict_missing）；
⑥ 红线⑤：不许单目标牺牲（某一维掉超容差 ⇒ single_objective_sacrifice）；
⑦ 红线⑥：每轮可回滚；⑧ 帕累托前沿只画点，点由人定。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import render_evolution as rev  # noqa: E402


def _kernel():
    k = rev.RenderEvolutionKernel()
    k.register_baseline(rev.RenderGenome(genome_id="g0", seed=20260920,
                                         primitives=list(rev.PRIMITIVES)))
    return k


class PrimitiveTests(unittest.TestCase):
    def test_five_primitives_and_disk_status(self):
        st = rev.run("status")
        self.assertEqual([p["key"] for p in st["primitives"]], list(rev.PRIMITIVES))
        on_disk = {p["source"]: p["on_disk"] for p in st["primitives"]}
        self.assertEqual(on_disk["MoonRay"], "none", "盘上没有就是没有，不许写成已接入")
        self.assertEqual(on_disk["Filament"], "none")
        self.assertEqual(on_disk["DiffusionRenderer"], "none")
        self.assertTrue(on_disk["HyperFrames"].startswith("skill"))


class RedLineTests(unittest.TestCase):
    def test_no_baseline_no_evolution(self):
        k = rev.RenderEvolutionKernel()
        out = k.propose("missing", {"samples": 128})
        self.assertFalse(out["ok"])
        self.assertEqual(out["rule"], "no_baseline")

    def test_seed_is_mandatory_for_baseline_and_experiment(self):
        k = rev.RenderEvolutionKernel()
        bad = k.register_baseline(rev.RenderGenome(genome_id="noseed"))
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "seed_missing")
        k2 = _kernel()
        g = k2.propose("g0", {"samples": 128})["genome_id"]
        k2.genomes[g].seed = None
        out = k2.record_experiment(rev.RenderExperiment(genome_id=g, baseline_id="g0",
                                                        realism_metrics={"psnr": 30.0}))
        self.assertFalse(out["ok"])
        self.assertEqual(out["rule"], "seed_missing")

    def test_untested_cannot_be_marked_green(self):
        k = _kernel()
        g = k.propose("g0", {"samples": 128})["genome_id"]
        out = k.promote(g)
        self.assertFalse(out["ok"])
        self.assertEqual(out["rule"], "metrics_missing")

    def test_machine_cannot_decide_realism_or_smoothness(self):
        k = _kernel()
        g = k.propose("g0", {"samples": 128})["genome_id"]
        k.record_experiment(rev.RenderExperiment(genome_id=g, baseline_id="g0",
                                                 realism_metrics={"psnr": 32.0},
                                                 smoothness_metrics={"fps": 60.0}))
        out = k.promote(g)
        self.assertFalse(out["ok"])
        self.assertEqual(out["rule"], "human_verdict_missing")

    def test_single_objective_sacrifice_is_refused(self):
        k = _kernel()
        k.genomes["g0"].realism_score = 0.90
        k.genomes["g0"].smoothness_score = 0.50
        g = k.propose("g0", {"samples": 8, "target_fps": 120})["genome_id"]
        k.record_experiment(rev.RenderExperiment(genome_id=g, baseline_id="g0",
                                                 realism_metrics={"psnr": 0.50},
                                                 smoothness_metrics={"fps": 0.95}))
        k.genomes[g].human_realism = 3.0
        k.genomes[g].human_smoothness = 5.0
        out = k.promote(g)
        self.assertFalse(out["ok"], "为了流畅把逼真拉掉 ⇒ 必须拒")
        self.assertEqual(out["rule"], "single_objective_sacrifice")

    def test_happy_path_promotes_and_can_rollback(self):
        k = _kernel()
        k.genomes["g0"].realism_score = 0.80
        k.genomes["g0"].smoothness_score = 0.80
        g = k.propose("g0", {"samples": 128, "target_fps": 120})["genome_id"]
        k.record_experiment(rev.RenderExperiment(genome_id=g, baseline_id="g0",
                                                 realism_metrics={"psnr": 0.85},
                                                 smoothness_metrics={"fps": 0.86}))
        k.genomes[g].human_realism = 4.5
        k.genomes[g].human_smoothness = 4.5
        self.assertTrue(k.promote(g)["ok"])
        self.assertIn(g, k.status()["winners"])
        self.assertTrue(k.rollback(g)["ok"])
        self.assertNotIn(g, k.status()["winners"])

    def test_pareto_front_is_drawn_but_not_picked(self):
        k = _kernel()
        k.genomes["g0"].realism_score = 0.80
        k.genomes["g0"].smoothness_score = 0.40
        g = k.propose("g0", {"samples": 256})["genome_id"]
        k.record_experiment(rev.RenderExperiment(genome_id=g, baseline_id="g0",
                                                 realism_metrics={"psnr": 0.95},
                                                 smoothness_metrics={"fps": 0.30}))
        pf = k.pareto_front()
        self.assertEqual(pf["points"], 2)
        self.assertEqual(len(pf["front"]), 2, "两个互不支配的点都在前沿上")
        self.assertIn("人决定", pf["note"])

    def test_module_has_no_render_network_or_write_paths(self):
        src = Path(rev.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store",
                    "import bpy", "import torch", "remotion", "subprocess.run"):
            self.assertNotIn(bad, src, "只读内核里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
