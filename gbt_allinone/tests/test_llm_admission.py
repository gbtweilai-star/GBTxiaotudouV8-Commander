# -*- coding: utf-8 -*-
"""准入名单的回归判据（2026-11-10 主人令）。

主人原话：「只要是不能使用的就直接排除，只接入能使用的串联起来使用。」

口径：
- 确定性不可用（404 / 402 无额度 / 401-403 / 匿名额度用尽 / 上游坏格 / 空回包）
  ⇒ 进 `bad`，**直接离开环**（默认 1h），对话不会再撞它；
- 429 限流 ⇒ 只冷却，不进 bad（窗口会回补）；
- 任何一通成功 ⇒ 清掉该格的 bad 与冷却，重新准入；
- 全环都被排除 ⇒ 不永久判死，回退成整环复探一次并标 `reviving`。
"""
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.llm import key_gateway as KG       # noqa: E402


class TestAdmission(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = KG._store_dir
        KG._store_dir = lambda: Path(self._tmp.name)
        self.ring = KG.model_ring("kilo")
        self.assertGreater(len(self.ring), 2, "kilo 应当声明多格免费模型环")

    def tearDown(self):
        KG._store_dir = self._orig
        self._tmp.cleanup()

    def test_not_found_is_excluded_from_ring(self):
        bad = self.ring[0]
        KG.note_model("kilo", bad, ok=False, status=404, error="model not found")
        state = KG.ring_state("kilo")
        self.assertIn(bad, state["excluded"], "404 的格必须被排除")
        self.assertNotIn(bad, state["admitted"])
        self.assertNotIn(bad, KG.model_order("kilo"),
                         "被排除的格不许再进本轮轮询")

    def test_no_quota_is_excluded(self):
        bad = self.ring[1]
        KG.note_model("kilo", bad, ok=False, status=402, error="insufficient balance")
        self.assertIn(bad, KG.ring_state("kilo")["excluded"])

    def test_promotion_limit_is_excluded(self):
        bad = self.ring[2]
        KG.note_model("kilo", bad, ok=False, status=429,
                      error="PROMOTION_MODEL_LIMIT_REACHED")
        self.assertIn(bad, KG.ring_state("kilo")["excluded"],
                      "匿名额度本轮用尽属于「不能用」，不是普通限流")

    def test_rate_limit_only_cools(self):
        limited = self.ring[0]
        KG.note_model("kilo", limited, ok=False, status=429,
                      error="rate limit exceeded")
        state = KG.ring_state("kilo")
        self.assertNotIn(limited, state["excluded"],
                         "普通 429 只冷却，不该被永久排除")
        self.assertIn(limited, state["cooling"])
        self.assertNotIn(limited, KG.model_order("kilo"))

    def test_success_revives_excluded(self):
        back = self.ring[0]
        KG.note_model("kilo", back, ok=False, status=404, error="model not found")
        self.assertIn(back, KG.ring_state("kilo")["excluded"])
        KG.note_model("kilo", back, ok=True)
        state = KG.ring_state("kilo")
        self.assertNotIn(back, state["excluded"], "验证能用后必须重新准入")
        self.assertIn(back, state["admitted"])
        self.assertIn(back, KG.model_order("kilo"))

    def test_all_excluded_falls_back_to_revive_probe(self):
        for m in self.ring:
            KG.note_model("kilo", m, ok=False, status=404, error="model not found")
        state = KG.ring_state("kilo")
        self.assertEqual(state["admitted"], [])
        self.assertTrue(state["reviving"], "全排除时必须标记复探，而不是假装正常轮询")
        self.assertEqual(sorted(KG.model_order("kilo")), sorted(self.ring),
                         "全排除时回退成整环复探一次，不永久判死")

    def test_order_only_contains_admitted(self):
        dead = self.ring[:2]
        for m in dead:
            KG.note_model("kilo", m, ok=False, status=404, error="model not found")
        order = KG.model_order("kilo")
        self.assertTrue(order)
        self.assertTrue(set(order).isdisjoint(set(dead)),
                        "轮询顺序里不许再出现被排除的格")


if __name__ == "__main__":
    unittest.main(verbosity=2)
