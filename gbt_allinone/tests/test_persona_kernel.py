# -*- coding: utf-8 -*-
"""性格内核 v4.0 · 带牙用例（R-H700）。

① **一字不差**：四大基石原文逐字对上（含「从从」与「只都是事实故事前」）；
② **不分主次**：四基石并列，没有优先级字段，也不许被排序；
③ 外温十律 = 10 条，且**机器可判的只有 5 条**——另外 5 条必须老实标 human，
   不许被冒充成"已判过"；
④ 十条红线 = 10 条，语言层 7 / 行动层 3，分层不许串；
⑤ 表达闸**带正负对照**（《扫描器自证律》）：干净文本必须过，违规文本必须拦，
   两例结果必须不同——相同 = 扫描器瞎；
⑥ 行动闸：四种行动类型各归其位；未知类型不误拦；
⑦ 上色只调倾向：数值有界 [0,1]，且**不许改入参**；
⑧ 只读纪律：除 evolve 外，源码里不许有写盘 / 联网调用（AST 扫）。
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import persona_kernel as pk  # noqa: E402

VERBATIM = {
    "止损律": "不管什么关系，只都是事实故事前，不考虑你的感受和利益时，你就该及时止损了。",
    "主动律": "世界上好的东西都是抢来的，只有弱者才会等待分配。",
    "洞察律": "制定规矩的最不守规矩，规矩只不过是，弱者的脚链，强者的工具而已。",
    "静待律": "不要报复，烂掉的苹果，会自己从从树上掉下来。",
}


class VerbatimTests(unittest.TestCase):
    """① 一字不差 —— 这条是本次立项的第一硬约束。"""

    def test_four_bedrocks_verbatim(self):
        got = {b["name"]: b["quote"] for b in pk.CORE_BEDROCK}
        self.assertEqual(sorted(got), sorted(VERBATIM))
        for name, want in VERBATIM.items():
            self.assertEqual(got[name], want, f"{name} 原文被改动了")

    def test_repeated_chars_survive(self):
        """原文的重复字（从从）不许被"顺句"顺手删掉。"""
        q = next(b["quote"] for b in pk.CORE_BEDROCK if b["name"] == "静待律")
        self.assertIn("从从", q, "静待律的『从从』被抹掉了 —— 一字不差优先于通顺")

    def test_verbatim_note_exists(self):
        self.assertTrue(str(pk.VERBATIM_NOTE).strip())
        self.assertIn("一字不差", pk.VERBATIM_NOTE)

    def test_sources_are_the_four_named(self):
        got = {b["name"]: b["source"] for b in pk.CORE_BEDROCK}
        self.assertEqual(got["止损律"], "郝伯特")
        self.assertEqual(got["主动律"], "狄更斯")
        self.assertEqual(got["洞察律"], "毛姆")
        self.assertEqual(got["静待律"], "洛克菲勒")


class BedrockTests(unittest.TestCase):
    """② 四基石并列。"""

    def test_four_and_no_priority_field(self):
        self.assertEqual(len(pk.CORE_BEDROCK), 4)
        for b in pk.CORE_BEDROCK:
            for forbidden in ("priority", "weight", "rank", "order", "level"):
                self.assertNotIn(forbidden, b, f"{b['name']} 带了优先级字段 ⇒ 违反并列")

    def test_action_types_unique_and_complete(self):
        types = [b["action_type"] for b in pk.CORE_BEDROCK]
        self.assertEqual(len(set(types)), 4, "行动类型必须一一对应，不许重复")
        self.assertEqual(set(pk.BEDROCK_BY_ACTION), set(types))

    def test_each_has_red_line_and_verdict(self):
        for b in pk.CORE_BEDROCK:
            self.assertTrue(b["red_line"].strip(), b["name"])
            self.assertTrue(b["verdict"].strip(), b["name"])


class LawTests(unittest.TestCase):
    """③ 外温十律 —— 机器能判的归机器，人才能判的归人。"""

    def test_ten_laws(self):
        self.assertEqual(len(pk.EXPRESSION_LAWS), 10)
        self.assertEqual(pk.LAW_KEYS, ("short", "warm", "linger", "precise", "blank",
                                       "awake", "sincere", "calm", "measure", "empathy"))

    def test_machine_is_five_and_human_is_five(self):
        self.assertEqual(len(pk.MACHINE_LAWS), 5)
        self.assertEqual(len(pk.HUMAN_LAWS), 5)
        self.assertEqual(set(pk.MACHINE_LAWS) | set(pk.HUMAN_LAWS), set(pk.LAW_KEYS))
        self.assertEqual(set(pk.MACHINE_LAWS) & set(pk.HUMAN_LAWS), set())

    def test_human_laws_are_not_claimed_as_machine(self):
        r = pk.check_expression("今天把镜像和工作区对齐了。")
        for k in pk.HUMAN_LAWS:
            self.assertNotIn(k, r["machine_laws_checked"],
                             f"{k} 是『只有人能判』的律，不许混进机器判定")

    def test_human_pending_is_reported_not_hidden(self):
        r = pk.check_expression("短句。")
        self.assertEqual(set(r["human_pending"]), set(pk.HUMAN_LAWS))
        self.assertIn("不声称通过", r["note"])


class RedLineTests(unittest.TestCase):
    """④ 十条红线，分层不许串。"""

    def test_ten_lines_and_split(self):
        self.assertEqual(len(pk.RED_LINES), 10)
        self.assertEqual(len(pk.LANGUAGE_RED), 7)
        self.assertEqual(len(pk.ACTION_RED), 3)
        self.assertEqual(set(pk.LANGUAGE_RED) | set(pk.ACTION_RED), set(pk.RED_KEYS))
        self.assertEqual(set(pk.LANGUAGE_RED) & set(pk.ACTION_RED), set())

    def test_numbering_is_one_to_ten(self):
        self.assertEqual([r["no"] for r in pk.RED_LINES], list(range(1, 11)))

    def test_layers_are_explicit(self):
        for r in pk.RED_LINES:
            self.assertIn(r["layer"], ("language", "action"), r["name"])


class ExpressionGateTests(unittest.TestCase):
    """⑤ 表达闸带正负对照 —— 扫描器必须证明自己不瞎。"""

    def test_positive_control_clean_text_passes(self):
        r = pk.check_expression("镜像落后三天，工作区才是真的。")
        self.assertTrue(r["ok"], r)
        self.assertFalse(r["denied"])
        self.assertEqual(r["hits"], [])

    def test_negative_control_chicken_soup_denied(self):
        r = pk.check_expression("加油，你可以的！")
        self.assertFalse(r["ok"])
        self.assertTrue(r["denied"])
        self.assertTrue(any(h["key"] == "no_chicken_soup" for h in r["hits"]))

    def test_two_controls_differ(self):
        a = pk.check_expression("镜像和工作区已经对齐。")
        b = pk.check_expression("加油！你可以的！")
        self.assertNotEqual(a["denied"], b["denied"], "正负对照结果相同 ⇒ 扫描器瞎")

    def test_preaching_denied(self):
        r = pk.check_expression("你应该早点说。")
        self.assertTrue(r["denied"])
        self.assertTrue(any(h["key"] == "no_preaching" for h in r["hits"]))

    def test_apology_loop_needs_two(self):
        one = pk.check_expression("抱歉，这条我说错了。")
        self.assertFalse(one["denied"], "只道歉一次不该被拦")
        two = pk.check_expression("抱歉。抱歉。")
        self.assertTrue(two["denied"], "两次道歉必须触发内耗式道歉红线")

    def test_emotion_act_denied(self):
        r = pk.check_expression("宝子，我懂你。")
        self.assertTrue(r["denied"])

    def test_anxiety_denied(self):
        r = pk.check_expression("再不弄就晚了。")
        self.assertTrue(r["denied"])

    def test_rambling_needs_more_than_three(self):
        three = pk.check_expression("一。二。三。")
        self.assertFalse(three["denied"], "三句以内不该被短律拦")
        four = pk.check_expression("一。二。三。四。")
        self.assertTrue(four["denied"], "超过三句必须触发短律")

    def test_empathy_and_measure_flagged(self):
        self.assertTrue(pk.check_expression("你错了。")["denied"])
        self.assertTrue(pk.check_expression("照我说的做。")["denied"])


class ActionGateTests(unittest.TestCase):
    """⑥ 行动闸：四种行动类型各归其位。"""

    def test_each_action_type_hits_its_bedrock(self):
        pairs = {
            "consuming_relationship": ("stop_loss", "止损律"),
            "passive_waiting": ("initiative", "主动律"),
            "blind_obedience": ("insight", "洞察律"),
            "entanglement": ("wait_ruin", "静待律"),
        }
        for at, (key, name) in pairs.items():
            r = pk.check_action(at)
            self.assertFalse(r["ok"], at)
            self.assertTrue(r["denied"], at)
            self.assertEqual(r["bedrock"], key, at)
            self.assertEqual(r["bedrock_name"], name, at)
            self.assertTrue(r["message"].strip(), at)
            self.assertIn(r["red"], pk.RED_KEYS, f"{at} 挂的红线不在十条之内")
            self.assertEqual(r["red_layer"], pk.RED_LAYER[r["red"]], at)

    def test_bedrock_to_redline_mapping_is_exact(self):
        """基石↔红线映射逐条钉死，改动必须是有意的。"""
        self.assertEqual(pk.BEDROCK_RED, {
            "stop_loss": "no_endless_forbearance",
            "initiative": "no_passive_wait",
            "insight": "no_rule_captivity",
            "wait_ruin": "no_entanglement",
        })

    def test_layer_asymmetry_is_recorded_not_papered_over(self):
        """行动层红线只有 3 条，基石有 4 条 —— 这个非对称必须被显式记下。"""
        self.assertEqual(len(pk.ACTION_RED), 3)
        self.assertEqual(len(pk.CORE_BEDROCK), 4)
        r = pk.check_action("entanglement")
        self.assertEqual(r["red_layer"], "language",
                         "静待律只能借语言层第 10 条 —— 层级要如实带出来")
        self.assertIn("静待律", r["layer_note"], "非对称必须带说明，不许静默")

    def test_action_layer_reds_cover_three_bedrocks(self):
        covered = {k for k, v in pk.BEDROCK_RED.items() if pk.RED_LAYER[v] == "action"}
        self.assertEqual(covered, {"stop_loss", "initiative", "insight"})

    def test_unknown_action_type_does_not_false_block(self):
        r = pk.check_action("totally_unknown")
        self.assertTrue(r["ok"])
        self.assertFalse(r.get("denied"))
        self.assertEqual(sorted(r["available"]), sorted(pk.BEDROCK_BY_ACTION))

    def test_empty_action_type_is_ok(self):
        self.assertTrue(pk.check_action("")["ok"])


class ColorTests(unittest.TestCase):
    """⑦ 上色只调倾向，不改入参，数值有界。"""

    def test_bounded_and_input_untouched(self):
        src = {"joy": 0.5, "calm": 0.99, "affection": 0.01, "curiosity": 0.5,
               "pride": 0.5, "boredom": 0.02, "trust": 0.01,
               "frustration": 0.01, "sadness": 0.01}
        frozen = dict(src)
        r = pk.color(src)
        self.assertEqual(src, frozen, "上色不许改入参")
        for name, v in r["emotions"].items():
            self.assertGreaterEqual(v, 0.0, name)
            self.assertLessEqual(v, 1.0, name)

    def test_wait_ruin_lowers_frustration(self):
        r = pk.color({"frustration": 0.5, "calm": 0.5}, bedrock_keys=["wait_ruin"])
        self.assertLess(r["emotions"]["frustration"], 0.5, "静待律必须压住挫败")
        self.assertGreater(r["emotions"]["calm"], 0.5)

    def test_initiative_raises_curiosity(self):
        r = pk.color({"curiosity": 0.5}, bedrock_keys=["initiative"])
        self.assertGreater(r["emotions"]["curiosity"], 0.5)

    def test_unknown_keys_ignored(self):
        r = pk.color({"nope": 0.5})
        self.assertEqual(r["emotions"], {"nope": 0.5})


class ReadOnlyDisciplineTests(unittest.TestCase):
    """⑧ 只读纪律：除 evolve 外不许有写盘 / 联网调用。"""

    def _source(self) -> str:
        return (ROOT / "gbt_allinone" / "tools" / "persona_kernel.py").read_text(encoding="utf-8")

    def test_no_network_or_write_outside_evolve(self):
        tree = ast.parse(self._source())
        banned = {"urlopen", "requests", "socket", "system", "popen", "run",
                  "remove", "unlink", "rmtree", "mkdir", "write_text", "write_bytes"}
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name == "evolve":
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Attribute) and sub.attr in banned:
                    offenders.append(f"{node.name}:{sub.attr}")
                if isinstance(sub, ast.Name) and sub.id in banned:
                    offenders.append(f"{node.name}:{sub.id}")
        self.assertEqual(offenders, [], f"只读纪律被破：{offenders}")

    def test_module_does_not_import_network_libs(self):
        src = self._source()
        for lib in ("import requests", "import socket", "import urllib", "import subprocess"):
            self.assertNotIn(lib, src, f"只读模块不许引 {lib}")


class EntryPointTests(unittest.TestCase):
    """能力入口契约。"""

    def test_default_op_is_readonly_constitution(self):
        r = pk.run()
        self.assertTrue(r["ok"])
        self.assertTrue(r.get("readonly"))
        self.assertEqual(r["version"], "4.0")
        self.assertEqual(len(r["outer"]["laws"]), 10)
        self.assertEqual(len(r["inner"]["bedrocks"]), 4)
        self.assertEqual(len(r["red_lines"]), 10)

    def test_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            pk.run("nope")

    def test_honest_boundary_present(self):
        self.assertIn("教养", pk.HONEST_BOUNDARY)
        self.assertIn("底线", pk.HONEST_BOUNDARY)


class EvolveTests(unittest.TestCase):
    """演化驱动：真跑循环并落心境。"""

    def test_evolve_runs_cycles(self):
        r = pk.evolve(2, events=["state_probe", "idle_reflection"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["cycles"], 2)
        self.assertEqual(len(r["trace"]), 2)
        self.assertTrue(r["status"]["ok"])

    def test_evolve_clamps_cycles(self):
        self.assertEqual(pk.evolve(0)["cycles"], 1)
        self.assertEqual(pk.evolve(999)["cycles"], 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)