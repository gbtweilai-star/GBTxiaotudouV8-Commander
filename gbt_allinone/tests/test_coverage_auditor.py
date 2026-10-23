# -*- coding: utf-8 -*-
"""触手覆盖审计器 · 带牙用例（R-H196）。

① 八根触手组 ↔ 八个短板，一个不缺；
② 红线①：没有触手的短板 ⇒ 记"结构性死角"，**不计入覆盖**；
③ 红线②：**不能报"我处理不了" ⇒ 也不算覆盖**（静默失败）；
④ 红线③：`audit()` 只给读数（覆盖率字符串 + 计数 + 死角台账），不给形容词；
⑤ 红线④：宣称"全覆盖"却没有任何登记死角 ⇒ **拒绝**；
⑥ 红线⑤：新场景没有触手能接 ⇒ 必须**先登记为死角**，否则拒；
⑦ 取证快照带 as_of 与出处（不是冒充实时）；只读：无网络/写盘路径。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import coverage_auditor as ca  # noqa: E402


class MatrixTests(unittest.TestCase):
    def test_eight_short_boards_and_groups(self):
        data = ca.run("matrix")
        self.assertEqual(len(data["matrix"]), 8)
        self.assertEqual(len({r["short_board"] for r in data["matrix"]}), 8)
        for row in data["matrix"]:
            self.assertTrue(row["group"], "每个短板必须有对应触手组")
            self.assertIn("（", row["group"], "组名要带『手/脑/眼/耳/口/门/网/镜』")

    def test_snapshot_is_labeled_not_fake_realtime(self):
        snap = ca.run("snapshot")
        self.assertIn("as_of", snap)
        self.assertIn("source", snap)
        self.assertIn("docs/触手覆盖矩阵.md", snap["source"])
        self.assertEqual(snap["reportable_modules"]["眼（视觉触手）"], 0,
                         "视觉面 0/5 是本刀取到的真读数（待核死角）")


class RedLineTests(unittest.TestCase):
    def setUp(self):
        self.a = ca.CoverageAuditor()

    def test_missing_tentacle_is_a_structural_gap(self):
        out = self.a.register(ca.CoverageEntry(short_board="NO_MEMORY",
                                               tentacles=[], can_report_incapable=True))
        self.assertFalse(out["covered"], "没有触手的短板不算覆盖")
        self.assertIn("结构性死角", " ".join(out["gaps"]))

    def test_cannot_report_incapable_means_not_covered(self):
        out = self.a.register(ca.CoverageEntry(short_board="NO_SELF_VIEW",
                                               tentacles=["omni_vision"],
                                               can_report_incapable=False))
        self.assertFalse(out["covered"], "不能报『做不了』= 静默失败 ⇒ 不算覆盖")
        self.assertIn("静默失败", " ".join(out["gaps"]))

    def test_covered_needs_both(self):
        out = self.a.register(ca.CoverageEntry(short_board="NO_BOUNDARY",
                                               tentacles=["auth_gate"],
                                               can_report_incapable=True))
        self.assertTrue(out["covered"])
        self.assertEqual(out["gaps"], [])
        reading = self.a.audit()
        self.assertEqual(reading["coverage_rate"], "1/8")
        self.assertEqual(reading["gaps_total"], 0)

    def test_claim_full_without_gaps_is_refused(self):
        self.a.register(ca.CoverageEntry(short_board="NO_VERIFY", tentacles=["framework_gate"],
                                         can_report_incapable=True))
        bad = self.a.audit(claim_full=True)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "claimed_full_violation")
        self.assertIn("死角", bad["why"])

    def test_new_scenario_must_be_audited(self):
        bad = self.a.register_scenario("语音克隆")
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "unregistered_gap")
        ok = self.a.register_scenario("语音克隆", gap_note="耳组没有克隆能力，先登记")
        self.assertTrue(ok["ok"])
        self.assertTrue(ok["gap"])
        with_tentacle = self.a.register_scenario("截图", tentacle="omni_vision")
        self.assertTrue(with_tentacle["ok"])
        self.assertFalse(with_tentacle["gap"])
        self.assertIn("语音克隆", self.a.audit()["unregistered_gaps"])

    def test_module_has_no_network_or_write_paths(self):
        src = Path(ca.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读审计里不该出现：%s" % bad)


class NativeFirstTests(unittest.TestCase):
    """R-H199 · 原生能力优先律：模型可换，原生栈不可换。"""

    def test_route_always_starts_native(self):
        out = ca.route("换 Agnes 再跑一遍")
        self.assertEqual(out["first_stop"], "native")
        self.assertEqual(out["route"], "native", "默认执行路径永远是原生")
        self.assertEqual(out["external_model_role"], "advisor", "外部模型只是参谋")
        cog = ca.route("写一段文案", cognition_only=True)
        self.assertEqual(cog["route"], "external_cognition")
        self.assertEqual(cog["first_stop"], "native", "即使只补认知，第一站仍是原生路由")

    def test_external_model_cannot_execute(self):
        for act in ("execute", "write_store", "bypass_route", "deploy", "publish", "grant_auth"):
            out = ca.external_model_may(act)
            self.assertFalse(out["ok"], "%s 不许由外部模型做" % act)
            self.assertEqual(out["rule"], "external_model_cannot_execute")
        self.assertTrue(ca.external_model_may("summarize")["ok"])

    def test_swapping_model_must_not_drift_the_native_stack(self):
        same = ca.assert_stack_unchanged({"手": "h1", "门": "g1"}, {"手": "h1", "门": "g1"})
        self.assertTrue(same["ok"])
        drift = ca.assert_stack_unchanged({"手": "h1"}, {"手": "h2"})
        self.assertFalse(drift["ok"])
        self.assertIn("手", drift["drifted"])
        self.assertIn("切模型把原生栈带偏了", drift["why"])

    def test_gaps_ledger_binds_to_native_surface_not_model(self):
        ok = ca.gaps_ledger([{"gap_id": "G1", "native_surface": "眼（视觉）",
                              "status": "open", "bound_by": "R-H196"}])
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["bind_to"], "native_surface（原生面）")
        bad = ca.gaps_ledger([{"gap_id": "G1", "native_surface": "眼", "model": "agnes"}])
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["problems"][0]["rule"], "gap_bound_to_model")
        missing = ca.gaps_ledger([{"gap_id": "G2"}])
        self.assertIn("missing_field", [p["rule"] for p in missing["problems"]])

    def test_native_first_lines_are_declared(self):
        self.assertEqual(len(ca.NATIVE_FIRST_LINES), 5)
        joined = " ".join(ca.NATIVE_FIRST_LINES)
        for kw in ("默认走原生", "栈不变", "只补认知", "持续打磨", "不跟着模型走"):
            self.assertIn(kw, joined)

    def test_gaps_ledger_is_structured_and_bound_to_native_surface(self):
        """R-H202：死角台账**结构化登记**（挂原生面、不许带 model），且 G1 已撤销。"""
        rep = ca.gaps_ledger(ca.GAPS)
        self.assertTrue(rep["ok"], rep["problems"])
        self.assertEqual(rep["bind_to"], "native_surface（原生面）")
        ids = {g["gap_id"]: g for g in ca.GAPS}
        self.assertEqual(ids["G1"]["status"], "closed", "G1 实测撤销（判据问题，不是死角）")
        self.assertIn("G3", ids, "G1 撤销后收窄出的真点要留账")
        self.assertIn("capture_environment", ids["G3"]["native_surface"] + ids["G3"]["note"])
        self.assertEqual(ids["G3"]["status"], "closed", "G3 已由 R-H203 收口")

    def test_gaps_ledger_default_reads_the_on_disk_ledger(self):
        """**不传参**时必须给出盘上那份台账，而且**要把内容交出来**（第 45 轮补）。

        🔴 为什么单独立这一条：上面那条一直写成 `ca.gaps_ledger(ca.GAPS)` ——
        把台账**喂**给函数，于是**默认路径从来没被验过**。
        而默认路径原来写的是 `rows or []`，实测返回 **`count=0`**：
        一个**假的"没有死角"**（盘上明明有 G1/G2/G3）。
        同一个函数还只回 `count` 不回内容 ⇒ "给我看台账"依然一条都看不到。
        判据三把：① 不传参 ⇒ count == len(GAPS) 且 >0，且 rows 真的带出来；
        ② 显式传空 ⇒ 尊重调用方（count=0）；③ 校验仍然有效（带 model 字段要拒）。
        """
        rep = ca.gaps_ledger()
        self.assertEqual(rep["count"], len(ca.GAPS), "不传参必须默认读盘上那份台账")
        self.assertGreater(rep["count"], 0, "台账非空；返回 0 就是假的『没有死角』")
        self.assertEqual(len(rep.get("rows") or []), rep["count"],
                         "count 说有 N 条，就得真的交出 N 条（收集了必须交付）")
        self.assertEqual(ca.gaps_ledger([])["count"], 0, "显式传空仍要尊重调用方")
        bad = ca.gaps_ledger([{"gap_id": "X", "native_surface": "手", "model": "m"}])
        self.assertFalse(bad["ok"], "带 model 字段的台账仍要拒（红线⑤）")


if __name__ == "__main__":
    unittest.main()
