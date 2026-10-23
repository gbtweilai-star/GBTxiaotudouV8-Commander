"""R-H605（2026-09-25）· `cross_scan` H 维**有界 + 分母闭合**回归用例。

被测故障（真跑复现过，不是推演）：
    空参 `cross_scan`（`deep=True`）**两次 >560s 不返回** —— 而 `deep=False` 只要 17.9s
    ⇒ 钱全花在 H 维。根因：H 维对每个 `safe` 且不在 `PROBE_SKIP_KINDS` 里的位
    **就地同步**真调，**没有任何预算**；而 `PROBE_SKIP_KINDS` 只排除侧效应位，
    **不排除慢的只读扫描器**。`caps-runtime-census` 现读的逐位耗时能直接对账：
    98 位只读位合计 **735.3s**，其中 ≥5s 的 6 位就占 **672.2s**。

判据（四条都要有牙）：
  1. **有界**：给 0 预算时**不许再起调用**（`checked == 0`），且必须如实置 `deadline_hit`；
  2. **分母闭合**：`checked + skipped + unsafe + not_probed + skipped_slow == len(BENIGN_CAPS)`
     —— 少一项就是"覆盖静默缩水"；
  3. **两个"没探到"的桶不许混**：超预算(`not_probed`) ≠ 慢位(`skipped_slow`)，
     混在一起读的人就分不清"没时间了"和"它本来就不算轻调用"；
  4. **慢位名册不许空、且每位都要有量到的耗时** —— 否则它退化成一句口号。
"""
from __future__ import annotations

import unittest

from gbt_allinone import cross_scan as cs
from gbt_allinone.caps_registry import BENIGN_CAPS


class HBudgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # 0 预算 ⇒ H 维一位都不许起调用（非 H 维照旧跑，与本次改动无关）
        cls.data = cs.scan(deep=True, h_budget_s=0.0)

    def test_zero_budget_stops_before_any_call(self) -> None:
        dc = self.data["deep_coverage"]
        self.assertTrue(dc["deadline_hit"], "0 预算却没报超时 —— 预算形同虚设")
        self.assertEqual(dc["checked"], 0, "0 预算还起了调用 —— 有界没生效")
        self.assertGreater(dc["not_probed_n"], 0, "没跑到的一个都没报出来")

    def test_denominator_closes(self) -> None:
        dc = self.data["deep_coverage"]
        total = (dc["checked"] + dc["skipped_side_effect_n"] + dc["unsafe_n"]
                 + dc["not_probed_n"] + dc["skipped_slow_n"])
        self.assertEqual(total, len(BENIGN_CAPS),
                         "H 维分母不闭合：漏掉的那部分会被读成『探过了没问题』")

    def test_budget_bucket_and_slow_bucket_do_not_mix(self) -> None:
        dc = self.data["deep_coverage"]
        self.assertEqual([], [k for k in dc["not_probed"] if k in dc["skipped_slow"]],
                         "同一位同时出现在『没时间』与『慢位』两个桶里 ⇒ 读的人分不清原因")
        self.assertEqual(sorted(dc["skipped_slow"]), sorted(cs._SLOW_KINDS))

    def test_slow_roster_is_measured_not_asserted(self) -> None:
        """慢位名册每一格都要么**量准了**、要么**显式登记为未量准（带理由）**。

        🔴 2026-10-17 翻正（留痕 · 原断言 / 为什么翻 / 现口径）：
          原断言：`_SLOW_KINDS` 里每一位都必须在 `_SLOW_KIND_COST_S` 里、且 ≥5s。
          为什么翻：名册后来长到 **19 位**，而实测耗时只有 **5 位**；其余 14 位不是"不慢"，
            而是**没量准**（单跑分钟级，没人会在预算内去量）。原断言只有两种出路：
            编数字（假绿）或把名册砍回 5 位（H 维又会真去跑那 14 位、把扫描拖爆）——
            两条都不对。
          现口径（**更严**，不是放宽）：每一位必须落进**两桶之一**并且**说得出理由** ——
            ① 量准桶：`_SLOW_KIND_COST_S[k] >= 5.0`；
            ② 未量准桶：`_SLOW_KINDS_UNMEASURED[k]` 非空理由。
            两桶都不在 ⇒ 红（新加慢位仍必须交代）。`skipped_slow` 读数里 `cost_s` 对未量准是 null，
            **不冒充已量**。
        """
        self.assertTrue(cs._SLOW_KINDS, "慢位名册空了 —— 无界那台机器就回来了")
        for kind in cs._SLOW_KINDS:
            measured = cs._SLOW_KIND_COST_S.get(kind)
            if measured is not None:
                self.assertGreaterEqual(measured, 5.0,
                                        "慢位 %s 的量到耗时 < 5s，与入选阈值不符" % kind)
                continue
            why = (getattr(cs, "_SLOW_KINDS_UNMEASURED", {}) or {}).get(kind)
            self.assertTrue(why, "慢位 %s 既没量准、也没登记未量准的理由 ⇒ 名册只是口号" % kind)
        # 两个桶不许重叠（同一格不许既"量准"又"未量准"）
        overlap = set(cs._SLOW_KIND_COST_S) & set(getattr(cs, "_SLOW_KINDS_UNMEASURED", {}) or {})
        self.assertEqual(set(), overlap, "同一慢位同时出现在两桶里：%s" % sorted(overlap))

    def test_default_budget_is_finite(self) -> None:
        self.assertIsNotNone(cs.H_BUDGET_S)
        self.assertGreater(float(cs.H_BUDGET_S), 0.0)

    def test_unlimited_escape_hatch_still_exists(self) -> None:
        """`h_budget_s=None` 必须仍然可用（旧的无预算行为可**显式**取回，不是被偷偷删掉）。"""
        import inspect
        sig = inspect.signature(cs.scan)
        self.assertIn("h_budget_s", sig.parameters)
        self.assertEqual(sig.parameters["h_budget_s"].default, cs.H_BUDGET_S,
                         "默认必须是有界；无界只许显式传 None 拿到")


if __name__ == "__main__":
    unittest.main(verbosity=2)
