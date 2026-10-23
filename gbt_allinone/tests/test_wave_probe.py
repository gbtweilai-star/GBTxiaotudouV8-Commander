# -*- coding: utf-8 -*-
"""wave_probe 契约测试：口径分支 · 零新增进程 · 起步期只记流水 · 白名单共用一张表。"""
from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import wave_probe as WP  # noqa: E402
from gbt_allinone import trace_store as TS        # noqa: E402


class WaveProbeTests(unittest.TestCase):
    def test_decide_covers_all_four_modes(self):
        # ① 样本不足 ⇒ 不触发（也不许外推）
        self.assertEqual(WP.decide(99, [0, 0]), (False, "insufficient", 0.0, 0.0))
        # ② σ=0 且 μ=0 ⇒ floor（K=3）
        self.assertEqual(WP.decide(2, [0, 0, 0, 0, 0, 0, 0])[1], "floor_used")
        self.assertFalse(WP.decide(3, [0] * 7)[0], "floor 是 >K，不是 ≥K")
        self.assertTrue(WP.decide(4, [0] * 7)[0])
        # ③ σ=0 且 μ>0 ⇒ 退化为 count > μ
        t, mode, mu, sd = WP.decide(6, [5, 5, 5, 5, 5, 5, 5])
        self.assertTrue(t)
        self.assertEqual(mode, "sigma_zero")
        self.assertEqual((mu, sd), (5.0, 0.0))
        # ④ 正常 3σ
        t2, mode2, mu2, sd2 = WP.decide(40, [10, 12, 11, 9, 10, 13, 11])
        self.assertEqual(mode2, "3sigma")
        self.assertTrue(t2)
        self.assertGreater(sd2, 0)
        self.assertFalse(WP.decide(11, [10, 12, 11, 9, 10, 13, 11])[0])

    def test_whitelist_is_the_same_table_not_a_copy(self):
        self.assertIs(WP.WHITELIST_EVENTS, TS.WHITELIST_EVENTS,
                      "白名单必须与 traces 共用同一张表（两处各存一份 = 两处真相）")

    def test_zero_new_process_primitives(self):
        self.assertEqual(WP.process_primitives(), [], "痕迹触手不许自己起进程（只挂在 app 心跳上）")
        src = inspect.getsource(WP)
        for bad in ("run_task(", "urlopen", "requests."):
            self.assertNotIn(bad, src, f"触手不该出现外部执行/出网原语：{bad}")

    def test_beat_writes_one_sample_and_no_trace_by_default(self):
        with tempfile.TemporaryDirectory(prefix="gbt_wave_") as tmp:
            TS._STORE = Path(tmp)
            TS.TRACE_DIR = Path(tmp) / "traces"
            out = WP.beat()
            self.assertTrue(out.get("ok"), out)
            self.assertIn(out["trigger_mode"],
                          ("3sigma", "floor_used", "sigma_zero", "insufficient"))
            self.assertEqual(out["coverage"], "half", "15 分钟窗口 × 30 分钟节律 ⇒ 必须标覆盖=半段")
            self.assertTrue(out["blind_window"])
            samples = TS._load("wave_samples")
            self.assertEqual(len(samples), 1, "一次唤醒写一条 sample")
            self.assertEqual(samples[0]["trigger_mode"], out["trigger_mode"])
            self.assertIn("baseline_mu", samples[0])
            self.assertEqual(out["traces_written"], 0)
            self.assertEqual(TS._load("traces"), [], "起步期：即使触发也不写 traces")

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="gbt_wave_dry_") as tmp:
            TS._STORE = Path(tmp)
            TS.TRACE_DIR = Path(tmp) / "traces"
            out = WP.beat(dry=True)
            self.assertTrue(out.get("ok"), out)
            self.assertFalse(out["wrote"])
            self.assertEqual(TS._load("wave_samples"), [])


if __name__ == "__main__":
    unittest.main()
