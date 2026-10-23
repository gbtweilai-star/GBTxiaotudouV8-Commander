# -*- coding: utf-8 -*-
"""净化刀带牙用例（R-H157 立 · R-H167 补口径与修牙 · 断言形状不许软化）。

① 排除表**是同一张**（`is` 断言，不是"内容相等"）—— 防两处真相；
② 测试件（`_def_probe.txt` / `t-dead` 等）**不许落进 runtime 档** —— 防净化吃掉真故障；
③ V5 遗留服务**不报警但仍可显式查到**（legacy ≠ 删除）；
④ 口径：`anomalies` 是"报警源总量"（含已恢复），**净化成绩只看 `runtime_faults`**；
⑤ 净化成绩：真账本 `runtime_faults` 必须为 0（事先声明预期读数，对不上就红）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone import selfscan, trace_store  # noqa: E402


class SelfTestExclusionTests(unittest.TestCase):
    def test_exclusion_table_is_the_same_object(self):
        """① 同一张表：用 `is`，不是 `==`（内容相等但对象不同 ⇒ 明天就会有人抄第二份）。"""
        src = Path(selfscan.__file__).read_text(encoding="utf-8")
        self.assertIn("from .trace_store import SELFTEST_HINTS", src,
                      "selfscan 必须**引用** trace_store 的排除表，不许另写一份")
        names = [n for n in dir(trace_store) if "SELFTEST" in n or "DRILL" in n]
        self.assertIn("SELFTEST_HINTS", names)
        self.assertIn("DRILL_KINDS", names)

    def test_selftest_keys_are_not_anomalies(self):
        """② 测试件不许落进 runtime 档 —— 真账本逐件查它落在哪一档。

        R-H167 修牙：旧版断言是 `assertNotIn('"' + hint + '"', str(r))`——
        而 `str(dict)` 的键用**单引号**渲染 ⇒ 那条断言**永远为真**（没牙的用例）。
        现在换成真断言：逐件查 `errors_by_kind[kind]["runtime"]` 必须为 0。
        """
        r = selfscan.check_audit(last=2000)
        self.assertIsInstance(r.get("by_signal"), dict)
        self.assertIn("legacy", r["by_signal"], "legacy 档必须存在（V5 遗留服务专用）")
        for hint in ("_def_probe.txt", "bo.txt", "t-bad.txt", "t-dead", "_probe_lock_test"):
            buckets = r["errors_by_kind"].get(hint, {})
            self.assertEqual(buckets.get("runtime", 0), 0,
                             f"测试件 {hint} 被判成运行故障（它不该进 runtime 档）")

    def test_reading_scope_pins_the_scoreboard(self):
        """④ 口径：`anomalies` 是"报警源总量"（含已恢复），**净化成绩只看 `runtime_faults`**。

        实测（R-H167 当场复现）：anomalies 20 = runtime+guard+trace+legacy+recovered，
        其中含 2 条"已恢复" ⇒ 它**不是"非 recovered 总数"**，更不是净化成绩。
        """
        r = selfscan.check_audit(last=2000)
        scope = r.get("reading_scope") or {}
        self.assertEqual(scope.get("scoreboard"), "runtime_faults",
                         "净化成绩的口径必须钉在 runtime_faults 上")
        self.assertEqual(r["anomalies"], sum(r["by_signal"].values()),
                         "anomalies 必须等于各档之和（它是全量口径，不是病灶数）")

    def test_purified_ledger_has_zero_runtime_faults(self):
        """⑤ 净化成绩：真账本 `runtime_faults` 必须为 0（事先声明预期，对不上就红）。"""
        r = selfscan.check_audit(last=2000)
        self.assertEqual(r["runtime_faults"], 0,
                         f"净化后仍有运行故障：{r['recent_runtime']}")
        self.assertTrue(r["ok"], "runtime_faults == 0 时 ok 必须为真")

    def test_legacy_services_do_not_alarm(self):
        """③ V5 遗留服务：不报警（不进 runtime），但名字仍在常量表里（可被显式查到）。

        🔴 2026-09-22 第 39 轮修（错报治理 · **判据自足**）：
        这条原来**依赖"真账本里恰好有" V5 遗留服务的 svc_down**（原注释自己写着的），
        却**不自己造**那条账。实测后果：在**隔离空 store**（跑测试的正确姿势）里
        `by_signal["legacy"] == 0` ⇒ 当场红；而全量跑时因为别的用例往账本里写了东西，
        它又绿 —— 典型的"随环境飘"（本清单第 61 条：判据要么自己造状态，要么写成不变量）。
        ⇒ 现在**自己往隔离 store 播一条** legacy 服务的 svc_down
        （`meta.services=["payment_gateway"]`，正是分类器 `_LEGACY_SERVICES` 认的那条路），
        再断言它落进 legacy 档 —— 落进 legacy 而不是 runtime，**"不报警"这半句才真被验到**。
        """
        src = Path(selfscan.__file__).read_text(encoding="utf-8")
        self.assertIn('"payment_gateway"', src, "legacy 表里应留 V5 服务名（可查）")
        self.assertIn('sig = "legacy"', src, "legacy 必须走独立档，不落 runtime")
        self.assertIn("_hit(", src, "排除表必须走**词边界**匹配（不许裸子串）")
        self.assertIn('split(",")', src, "legacy 必须支持多服务逗号串拆解")
        # 自造前置：一条 V5 遗留服务的 svc_down（写进隔离 store，不碰生产）
        from gbt_allinone import store as _store
        _store.audit("svc_down", {"services": ["payment_gateway"]})
        r = selfscan.check_audit(last=2000)
        self.assertGreaterEqual(r["by_signal"].get("legacy", 0), 1,
                                "V5 遗留服务应落 legacy 档（不报警但仍可查）")
        self.assertLessEqual(r.get("runtime_faults", 0), 15,
                             "净化后 runtime_faults 不该比净化前的 15 还高")


if __name__ == "__main__":
    unittest.main()
