# -*- coding: utf-8 -*-
"""观察者锚点律 · 带牙用例（R-H703）。

① 三公理 / 六短板 / 五红线 条数与内容钉死，改动必须是有意的；
② 红线① 带**正负对照**：同方既扫又报必须拒、换 checker 必须过、匿名必须拒；
③ 红线② 审计器必须被审：orphan 如实报出来，**不许把免检的洗成已审**；
④ 红线③ 递归封顶：必须真扫得到读数（engine.MAX_WF_DEPTH=5 是已知锚点）；
⑤ 红线④ 终止点：机器**不许**自称可以宣布终点；
⑥ 红线⑤ 人在场：已知缺口必须被登记，不许藏着；
⑦ 只读纪律：AST 扫，除读数外不许有写盘 / 联网调用。
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

from gbt_allinone.tools import observer_anchor as oa  # noqa: E402


class ConstitutionTests(unittest.TestCase):
    def test_three_axioms(self):
        self.assertEqual(len(oa.AXIOMS), 3)
        self.assertEqual(oa.AXIOM_KEYS, ("separation", "self_audit", "termination"))

    def test_six_short_boards_each_with_fix(self):
        self.assertEqual(len(oa.SHORT_BOARDS), 6)
        for b in oa.SHORT_BOARDS:
            self.assertTrue(b["short"].strip(), b)
            self.assertTrue(b["fix"].strip(), b)

    def test_five_red_lines(self):
        self.assertEqual(len(oa.RED_LINES), 5)
        self.assertEqual(oa.RED_KEYS, ("no_self_report", "auditor_must_be_audited",
                                       "recursion_must_be_capped",
                                       "terminal_is_human_only",
                                       "human_present_at_key_nodes"))

    def test_core_law_says_anchor_is_human(self):
        self.assertIn("锚点", oa.CORE_LAW)
        self.assertIn("人", oa.CORE_LAW)

    def test_honest_boundary_admits_machine_cannot_self_prove(self):
        self.assertIn("不能证明自己没漏", oa.HONEST_BOUNDARY)


class SeparationTests(unittest.TestCase):
    """红线① 带正负对照 —— 扫描器必须证明自己不瞎。"""

    def test_same_party_is_denied(self):
        r = oa.check_separation("me", "me")
        self.assertFalse(r["ok"])
        self.assertTrue(r["denied"])
        self.assertEqual(r["red"], "no_self_report")

    def test_different_checker_passes(self):
        r = oa.check_separation("me", "second-brain")
        self.assertTrue(r["ok"])
        self.assertFalse(r.get("denied"))

    def test_two_controls_differ(self):
        a = oa.check_separation("me", "me")
        b = oa.check_separation("me", "other")
        self.assertNotEqual(a["ok"], b["ok"], "正负对照结果相同 ⇒ 判据瞎")

    def test_anonymous_is_denied(self):
        self.assertTrue(oa.check_separation("", "x")["denied"])
        self.assertTrue(oa.check_separation("x", "")["denied"])

    def test_case_insensitive(self):
        self.assertTrue(oa.check_separation("ME", "me")["denied"])

    def test_check_reports_only_mechanical_line(self):
        r = oa.check(observer="me", checker="me")
        self.assertTrue(r["denied"])
        self.assertIn("no_self_report", r["blocked"])
        self.assertIn("不假装", r["note"])


class AuditorTests(unittest.TestCase):
    """红线② 审计器必须被审。"""

    def test_auditors_scanned(self):
        d = oa.auditors()
        self.assertTrue(d["ok"])
        self.assertGreater(d["total"], 0, "一个审计器都没扫到 ⇒ 扫描器瞎")
        for row in d["auditors"]:
            self.assertIn("audited_by", row)

    def test_orphans_are_reported_not_whitewashed(self):
        d = oa.auditors()
        self.assertEqual(d["orphan_count"], len(d["orphans"]))
        for rel in d["orphans"]:
            row = next(r for r in d["auditors"] if r["auditor"] == rel)
            self.assertEqual(row["audited_by"], [], "orphan 必须 audited_by 为空，不许洗白")

    def test_self_is_not_counted_as_its_own_auditor(self):
        d = oa.auditors()
        for row in d["auditors"]:
            self.assertNotIn(row["auditor"], row["audited_by"], "自己审自己不算审")


class DepthCapTests(unittest.TestCase):
    """红线③ 递归封顶 —— 报得出才算封顶。"""

    def test_caps_scanned(self):
        d = oa.depth_caps()
        self.assertTrue(d["ok"])
        self.assertGreater(d["total"], 0)

    def test_engine_workflow_cap_is_visible(self):
        d = oa.depth_caps()
        hits = [c for c in d["caps"]
                if c["file"].endswith("engine.py") and c["cap"] == 5]
        self.assertTrue(hits, "engine.MAX_WF_DEPTH=5 这个已知锚点必须扫得到")

    def test_every_cap_is_positive(self):
        for c in oa.depth_caps()["caps"]:
            self.assertGreaterEqual(c["cap"], 0, c)


class TerminalTests(unittest.TestCase):
    """红线④ 终止点只能由人设。"""

    def test_machine_may_not_declare_terminal(self):
        d = oa.terminals()
        self.assertFalse(d["machine_may_declare"])
        self.assertEqual(d["machine_may_declare_list"], [])
        self.assertTrue(d["human_only"])

    def test_why_quotes_the_inside_outside_reason(self):
        why = oa.terminals()["why"]
        self.assertIn("站在外面", why)
        self.assertIn("永远在里面", why)


class PresenceTests(unittest.TestCase):
    """红线⑤ 关键节点人在场 —— 缺口要登记，不许藏。"""

    def test_known_gap_is_recorded(self):
        d = oa.presence()
        self.assertTrue(d["known_gap"].strip(), "已知缺口必须写出来")
        self.assertIn("is_trusted", d["known_gap"])

    def test_untrusted_path_described(self):
        self.assertIn("授权", oa.presence()["untrusted_path"])


class ReadOnlyDisciplineTests(unittest.TestCase):
    def _source(self) -> str:
        return (ROOT / "gbt_allinone" / "tools" / "observer_anchor.py").read_text(
            encoding="utf-8")

    def test_no_write_or_network(self):
        tree = ast.parse(self._source())
        banned = {"urlopen", "requests", "socket", "system", "popen",
                  "remove", "unlink", "rmtree", "write_text", "write_bytes", "mkdir"}
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in banned:
                offenders.append(node.attr)
        self.assertEqual(offenders, [], f"只读纪律被破：{offenders}")

    def test_no_network_imports(self):
        src = self._source()
        for lib in ("import requests", "import socket", "import urllib", "import subprocess"):
            self.assertNotIn(lib, src, f"只读模块不许引 {lib}")


class EntryPointTests(unittest.TestCase):
    def test_default_op(self):
        r = oa.run()
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["axioms"]), 3)

    def test_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            oa.run("nope")

    def test_all_ops_reachable(self):
        for op in ("axioms", "boards", "red_lines", "terminals", "presence"):
            self.assertTrue(oa.run(op)["ok"], op)


if __name__ == "__main__":
    unittest.main(verbosity=2)