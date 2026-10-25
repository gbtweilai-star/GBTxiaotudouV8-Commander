# -*- coding: utf-8 -*-
"""自动化切换引擎 · 带牙用例（R-H229）。

① 五层链路齐，且**接线点只有一个 Intent JSON**；
② 意图三层（L1 解析 / L2 交叉验证 / L3 置信度）——**两次不一致 ⇒ 先问主人**；
③ 五条红线各有闸：低置信先问 / 不许直接执行 / 每次切换记 model_used /
   不可逆二次确认 / 身份不许改写；
④ 切换规则按任务画像选能源（**切换由大脑决策，不由模型自选**）；
⑤ 只读骨架不许有网络/写盘/调模型路径；登记在册且**落地即接线**。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import auto_switch as asw  # noqa: E402
from gbt_allinone.tools import orchestration_kernel as ok  # noqa: E402
from gbt_allinone import caps_registry as CR  # noqa: E402


class PipelineTests(unittest.TestCase):
    def test_five_layers_in_order(self):
        st = asw.run("status")
        # R-H232：v1 五层**已蒸馏**为 v2 四层 + 一回灌；v1 仍保留可查（pipeline_v1）
        self.assertEqual(st["pipeline_v1"],
                         ["意图分析", "任务分级", "模型切换", "原生执行", "验证/审计"])
        self.assertEqual(st["pipeline"], ["意图层", "调度层", "执行层", "校验层"])
        self.assertIn("回灌", st["feedback_loop"]["what"])
        self.assertEqual(st["short_boards"], 19)
        self.assertIn("Intent JSON", st["wiring"], "**接线点只有一个**")
        self.assertEqual(st["threshold"], 0.8)

    def test_intent_three_layers(self):
        ls = asw.run("intent_layers")["layers"]
        self.assertEqual([x["layer"] for x in ls], ["L1", "L2", "L3"])
        self.assertIn("第二个模型", ls[1]["action"])
        self.assertIn("误解", ls[2]["guards"])


class IntentTests(unittest.TestCase):
    def test_analyze_is_mechanical_in_skeleton(self):
        i = asw.run("analyze", text="帮我写个 Python 脚本")
        self.assertEqual(i["parsed"]["action"], "代码")
        self.assertGreaterEqual(i["confidence"], 0.8)
        self.assertFalse(i["needs_clarification"])
        empty = asw.run("analyze", text="")
        self.assertEqual(empty["confidence"], 0.0)
        self.assertTrue(empty["needs_clarification"], "**宁可低，不硬猜**")

    def test_irreversible_goes_into_constraints(self):
        i = asw.run("analyze", text="帮我删除这些文件")
        self.assertIn("不可逆", i["parsed"]["constraints"])

    def test_l2_cross_check_disagreement_asks_owner(self):
        same = asw.cross_check({"action": "查询"}, {"action": "查询"})
        self.assertFalse(same["needs_clarification"])
        self.assertAlmostEqual(same["confidence"], 0.95)
        diff = asw.cross_check({"action": "查询"}, {"action": "删除"})
        self.assertTrue(diff["needs_clarification"],
                        "**两次不一致 ⇒ 低置信 + 先问主人**")
        self.assertAlmostEqual(diff["confidence"], 0.5)
        one = asw.cross_check({"action": "查询"}, None)
        self.assertEqual(one["rule"], "cross_check_incomplete",
                         "只有一次 ⇒ 置信度按 0 算（不许单模型自证）")

    def test_confidence_gate_blocks_below_threshold(self):
        self.assertEqual(asw.gate_intent(0.5)["rule"], "low_confidence_ask_owner")
        self.assertEqual(asw.gate_intent(None)["rule"], "missing_confidence")
        self.assertTrue(asw.gate_intent(0.9)["ok"])


class ClassifyAndPickTests(unittest.TestCase):
    def test_classify_four_dimensions(self):
        prof = asw.classify({"raw": "帮我删除这些文件", "parsed": {"action": "执行"}})
        self.assertFalse(prof["profile"]["reversible"], "删文件 = 不可逆")
        rt = asw.classify({"raw": "查一下天气", "parsed": {"action": "执行"}})
        self.assertTrue(rt["profile"]["realtime"])

    def test_pick_energy_by_profile(self):
        code = asw.pick_energy({"type": "代码", "difficulty": "简单"})
        self.assertIn("Coder", code["prefer"])
        multi = asw.pick_energy({"type": "多模态", "difficulty": "简单"})
        self.assertIn("云端", multi["prefer"])
        self.assertIn("本地无视觉", multi["prefer"], "本地没有视觉 ⇒ 如实说")
        hard = asw.pick_energy({"type": "推理", "difficulty": "高难"})
        self.assertIn("R1-Distill", hard["prefer"])


class RedLineTests(unittest.TestCase):
    def test_five_redlines(self):
        r = asw.run("redlines")
        self.assertEqual(len(r["red_lines"]), 5)
        for s in ("阈值", "不许直接执行", "model_used", "二次确认", "身份"):
            self.assertTrue(any(s in x for x in r["red_lines"]), "少了：%s" % s)

    def test_no_direct_exec(self):
        self.assertEqual(asw.check_no_direct_exec({"raw": "cmd /c dir"})["rule"],
                         "model_direct_exec")
        self.assertTrue(asw.check_no_direct_exec({"capability": "echo"})["ok"])

    def test_switch_must_log_model_used(self):
        self.assertEqual(asw.must_log_model_used("")["rule"],
                         "no_model_used_logged")
        self.assertTrue(asw.must_log_model_used("deepseek")["ok"])

    def test_irreversible_and_identity(self):
        self.assertEqual(asw.gate_irreversible({"action": "删除文件"})["rule"],
                         "irreversible_needs_confirm")
        self.assertTrue(asw.gate_irreversible({"action": "删除文件"},
                                              confirmed=True)["ok"])
        self.assertEqual(asw.check_identity_text("我是 GPT-4")["rule"],
                         "identity_rewritten")
        self.assertTrue(asw.check_identity_text("我是 GBT小土豆")["ok"])

    def test_audit_matrix_four_entries(self):
        m = asw.run("audit")["matrix"]
        self.assertEqual(len(m), 4)
        # 判据别太字面：数据里带加粗标记（`**model_used**`），先归一化再比
        flat = [str(x["log"]).replace("*", "") for x in m]
        self.assertIn("model_used", flat)
        self.assertTrue(any("degraded" in x for x in flat))


class SkeletonAndWiringTests(unittest.TestCase):
    def test_module_has_no_model_or_network_paths(self):
        src = Path(asw.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket",
                    "import ollama", "subprocess.run(", ".write_text("):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)

    def test_registered_and_wired(self):
        cap = CR.BENIGN_CAPS.get("auto_switch")
        self.assertIsNotNone(cap)
        self.assertEqual(cap["domain"], "mind")
        self.assertIn("auto_switch", ok._READONLY_MODULES)
        self.assertIs(ok._READONLY_MODULES["auto_switch"], asw)


class V2ShortBoardTests(unittest.TestCase):
    """R-H232 · v2.0：四层 + 一回灌 + **19 条短板逐条可测**。"""

    def test_distillation_five_to_four_plus_loop(self):
        r = asw.run("layers_v2")
        self.assertEqual([x["layer"] for x in r["layers"]],
                         ["意图层", "调度层", "执行层", "校验层"])
        self.assertIn("分级 + 选能源", r["layers"][1]["does"],
                      "②③ 合并为调度层（**分级是为了切换**）")
        self.assertIn("已蒸馏", r["supersedes"])

    def test_nineteen_short_boards_registered_with_evidence(self):
        r = asw.run("short_boards")
        self.assertEqual(r["count"], 19)
        for x in r["boards"]:
            self.assertIn(x["covered"], ("yes", "partial", "no"))
            self.assertTrue(str(x["evidence"]).strip(), "#%d 缺取证" % x["n"])
        self.assertEqual(sum(r["stats"].values()), 19)
        self.assertEqual(r["stats"]["yes"], 1,
                         "**取证口径严格**：真正有机械判据的只有 1 条（独立 checker）")
        self.assertGreaterEqual(r["stats"]["no"], 10, "待补占多数 ⇒ 如实")
        self.assertIn("关键词命中 ≠ 覆盖", r["note"])

    def test_intent_layer_four_boards(self):
        amb = asw.run("ambiguity", text="帮我删了它，或者先备份")
        self.assertEqual(amb["ambiguity"], "一类多解")
        self.assertIn("请点一个", amb["clarify"], "歧义要配澄清模板")
        self.assertFalse(asw.run("ambiguity", text="查一下天气")["needs_clarification"])
        self.assertEqual(asw.run("language", text="帮我 check 一下 latency")["language"],
                         "mixed")
        neg = asw.run("negation", text="不要删这个文件")
        self.assertTrue(neg["needs_care"])
        self.assertIn("不要", neg["negation"])
        self.assertEqual(asw.run("negation", text="如果失败就重试")["conditional"], ["如果"])

    def test_dispatch_layer_four_boards(self):
        self.assertEqual(asw.difficulty_by_threshold(5)["difficulty"], "高难")
        self.assertEqual(asw.difficulty_by_threshold(1)["difficulty"], "简单")
        chain = asw.run("degradation")["chain"]
        self.assertEqual([c["source"] for c in chain][-1], "拒执行（如实报缺）")
        self.assertTrue(chain[1]["degraded"], "每降一级都带 degraded")
        self.assertEqual(asw.check_concurrency(load=3, base=4)["concurrency"], 1,
                         "负载越高并发越低（动态上限）")
        self.assertEqual(asw.must_dispatch_reason("")["rule"], "no_dispatch_reason")
        self.assertTrue(asw.must_dispatch_reason("本地无视觉 ⇒ 上云端")["ok"])

    def test_execution_layer_four_boards(self):
        self.assertEqual(asw.check_depth(4)["rule"], "depth_exceeded")
        self.assertTrue(asw.check_depth(3)["ok"])
        self.assertEqual(asw.check_execution_trace([])["rule"], "no_execution_trace")
        ok = asw.check_execution_trace([{"state": "ok"}, {"state": "failed"}])
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["last_state"], "failed", "断点要能说清卡在第几步")
        self.assertEqual(asw.check_intermediate_report([], long_task=True)["rule"],
                         "no_intermediate_report")

    def test_verify_and_loop_layer(self):
        m = asw.matches_intent({"ok": True}, {"parsed": {}})
        self.assertIsNone(m["matches_intent"],
                          "**执行成功 ≠ 符合意图**；符合与否不许机器替人判")
        self.assertEqual(asw.check_independent_checker("a", "a")["rule"],
                         "same_checker", "单方证据不能自证")
        self.assertEqual(asw.check_independent_checker("a", "b")["ok"], True)
        self.assertFalse(asw.feedback_to_intent(3)["updated"], "未到频率不更新")
        f = asw.feedback_to_intent(10)
        self.assertTrue(f["updated"])
        self.assertTrue(f["rollback_available"], "回灌**可撤销**")
        self.assertEqual(asw.feedback_to_intent(10, drift=True)["rule"],
                         "drift_detected", "**漂移即停**")
        d = asw.detect_drift({"a": 1, "b": 1}, {"a": 9, "b": 9})
        self.assertTrue(d["drifted"])
        self.assertEqual(d["action"], "stop_feedback")


if __name__ == "__main__":
    unittest.main()
