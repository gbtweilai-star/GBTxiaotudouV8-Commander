# -*- coding: utf-8 -*-
"""工程规范包判据（2026-11-04）· 「吞噬」到底完成没有。

## 什么叫「吞噬完成」（四步，断一步就没完成）

    规范在文档/代码里  →  harvest()  →  for_scene(scene)  →  认知包.standards

  A 抓得到   —— 四个真源必须都抓得到；条数与真源一致（不抄，所以不能寄）
  B 挑得出   —— 不同场景带进来的组**必须不同**（全都一样 = 没挑）
  C 不漂移   —— 工序顺序与 PHASES 键一致；宪章与 CHARTER.md 一致
  D 接上了   —— `bridge.build_cognition()` 的返回里真有 `standards`

## 为什么这几条要写成判据

这套规范以前是**散在各模块里、只写在文档里**的。文档不会自己执行，
所以「她到底知不知道这些规矩」这个问题没有答案。
接进认知包之后这个答案变成可机检的：调用一次 bridge，看回执里有没有。

## 缺源的正确姿势

生产树可能不带 AGENTS.md / docs（运行时树）。那**不是错**，是 `absent`。
但 `coding` 与 `redlines` 两个核心源**必须** ok —— 它们在本仓代码里，
不在就没有"吞噬"可言。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone import coding_discipline as CD  # noqa: E402
from gbt_allinone.tools import standards_pack as SP  # noqa: E402


# ── A · 抓得到 ──────────────────────────────────────────────────────────────
class TestHarvest(unittest.TestCase):
    """A · 四个真源都抓得到，且条数与真源一致。"""

    def test_core_sources_ok(self):
        """coding / redlines 是核心源（在代码里）—— 它们必须 ok。"""
        h = SP.harvest()
        for key in ("coding", "redlines"):
            src = h["sources"][key]
            self.assertTrue(src.get("ok"),
                            "核心源 %s 抓不到：%s" % (key, src.get("why")))

    def test_counts_match_source(self):
        """条数必须与真源**当场一致** —— 这条防"抄了一份"。

        如果有人把 PHASES 复制进 JSON，改了 PHASES 而没改副本，
        这条会红。这正是"只建索引不复制正文"的价值。
        """
        h = SP.harvest()["counts"]
        self.assertEqual(h["phases"], len(CD.PHASES), "工序条数与 PHASES 不一致")
        self.assertEqual(h["invariants"], len(CD.INVARIANTS), "不变量条数与 INVARIANTS 不一致")
        self.assertEqual(h["verification"], len(CD.VERIFICATION_ORDER),
                         "证据阶梯条数与 VERIFICATION_ORDER 不一致")
        self.assertEqual(h["charter"], len(CD.CHARTER_TITLES), "章数与 CHARTER_TITLES 不一致")

    def test_redlines_count(self):
        from gbt_allinone.tools import tentacle_cognition as TC
        self.assertEqual(SP.harvest()["counts"]["redlines"], len(TC.RED_LINES),
                         "红线条数与 RED_LINES 不一致")

    def test_missing_source_reported_not_raised(self):
        """源不在本树时：**如实报 ok=False + why**，不许抛、不许假装。"""
        with mock.patch.object(SP, "ROOT", Path("__绝对不存在的根__")):
            r = SP._from_agents()
        self.assertFalse(r["ok"], "源不在时不许报 ok")
        self.assertTrue(r.get("why"), "源不在时必须给 why，不许静默")


# ── B · 挑得出 ──────────────────────────────────────────────────────────────
class TestSceneRouting(unittest.TestCase):
    """B · 不同场景带进来的组必须不同 —— 全都一样等于没挑。"""

    def test_classify_basics(self):
        cases = [
            ("写代码修 bug 并跑测试", "code", True),
            ("发布上线到生产", "release", True),
            ("写文件落盘", "write", True),
            ("今天天气怎么样", "general", True),
            # 单字「图」的假阳性回归（2026-11-04 当场抓到过）
            ("看屏幕截图识别界面", "vision", True),
        ]
        for text, want, _ in cases:
            got = SP.classify(text)
            self.assertIn(want, got, "%r 应当归入 %s，实得 %r" % (text, want, got))

    def test_screenshot_is_not_write(self):
        """回归：截图/识图里含「图」字，但不该被判成「写文件」。"""
        got = SP.classify("看屏幕截图识别界面")
        self.assertNotIn("write", got,
                         "「看屏幕截图识别界面」被判成 write —— 单字关键词误命中了：%r" % got)

    def test_coding_scene_gets_more_than_vision(self):
        """编程场景必须比视觉场景多带工序/证据阶梯/宪章。"""
        code = SP.for_scene("修复 bug 跑测试")
        vis = SP.for_scene("看屏幕截图")
        self.assertIn("phases", code["standards"], "编程场景没带工序")
        self.assertIn("verification_order", code["standards"], "编程场景没带证据阶梯")
        self.assertNotIn("phases", vis["standards"],
                         "视觉场景不该带 8 工序 —— 看屏幕不需要镜像预演律")
        # 但两边都必须带红线与不变量（这两样不分场景）
        for r in (code, vis):
            self.assertIn("redlines", r["standards"])
            self.assertIn("invariants", r["standards"])

    def test_limit_lines_does_not_truncate_count(self):
        """`limit_lines` 只截展示的正文，**不许截条数** —— 否则触手以为规矩就这几条。"""
        full = SP.for_scene("修复 bug")
        cut = SP.for_scene("修复 bug", limit_lines=2)
        ph = cut["standards"]["phases"]
        self.assertEqual(ph["total"], len(CD.PHASES), "limit_lines 把条数也截了")
        self.assertEqual(len(ph["shown"]), 2, "limit_lines 没生效")
        self.assertEqual(cut["standards"]["invariants_total"], len(CD.INVARIANTS))


# ── C · 不漂移 ──────────────────────────────────────────────────────────────
class TestNoDrift(unittest.TestCase):
    """C · 与真源不漂移。"""

    def test_phase_order_matches_phases(self):
        self.assertEqual(tuple(CD.PHASES.keys()), tuple(CD.PHASE_ORDER),
                         "PHASE_ORDER 与 PHASES 键顺序不一致 —— 有人只改了一边")
        order = SP.for_scene("修复 bug")["standards"]["phases"]["order"]
        self.assertEqual(tuple(order), tuple(CD.PHASE_ORDER), "抓出来的顺序与真源不一致")

    def test_verify_ok(self):
        v = SP.verify()
        self.assertTrue(v["ok"], "verify 没过：%r" % (v.get("problems"),))

    @unittest.skipUnless((ROOT / "CHARTER.md").is_file(), "CHARTER.md 不在本树")
    def test_charter_not_drifted(self):
        """宪章摘要与 CHARTER.md 不许漂移（复用既有的 charter_drift）。"""
        d = CD.charter_drift()
        self.assertTrue(d.get("ok"), "宪章漂移：missing=%r extra=%r"
                                     % (d.get("missing"), d.get("extra")))


# ── D · 接上了 ──────────────────────────────────────────────────────────────
class TestWiredIntoCognition(unittest.TestCase):
    """D · 真的接进认知包了 —— 这是「吞噬完成」的最终证据。"""

    def test_build_cognition_carries_standards(self):
        from gbt_allinone.tentacle import bridge
        r = bridge.build_cognition(method="code_patch", intent="修复一个 bug 并跑测试")
        self.assertTrue(r.get("ok"), "认知包本身没过：%r" % (r.get("why"),))
        std = r.get("standards")
        self.assertIsInstance(std, dict, "认知包里没有 standards：keys=%r" % sorted(r))
        self.assertTrue(std, "standards 是空的")
        self.assertIn("redlines", std, "standards 里缺红线")
        self.assertIn("invariants", std, "standards 里缺不变量")
        self.assertTrue(r.get("standards_ok"), "standards_ok 不为 True：%s"
                                               % (r.get("standards_why"),))

    def test_scene_really_switches_in_bridge(self):
        """同一个入口，换意图 → 带进来的规范组必须变。"""
        from gbt_allinone.tentacle import bridge
        a = bridge.build_cognition(method="x", intent="修复 bug 跑测试").get("standards") or {}
        b = bridge.build_cognition(method="x", intent="看屏幕截图").get("standards") or {}
        ka = sorted(k for k in a if isinstance(a[k], list))
        kb = sorted(k for k in b if isinstance(b[k], list))
        self.assertNotEqual(ka, kb,
                            "换了意图但规范组完全一样 ⇒ 场景没真的切换：%r" % (ka,))
        self.assertIn("phases", a, "编程意图没带工序")
        self.assertNotIn("phases", b, "视觉意图不该带工序")

    def test_failure_is_visible_not_silent(self):
        """standards 抓不到时，认知包**不许整体失败**，但必须留下可见标记。"""
        from gbt_allinone.tentacle import bridge
        with mock.patch.object(SP, "harvest",
                               side_effect=RuntimeError("模拟真源炸了")):
            r = bridge.build_cognition(method="x", intent="任意")
        # 认知包五件仍应通过（standards 不是五件之一）
        self.assertTrue(r.get("ok"), "standards 失败不该让整个认知包失败")
        self.assertFalse(r.get("standards_ok"), "standards 失败必须标 False，不许静默")
        self.assertTrue(r.get("standards_why"), "standards 失败必须给 why")


if __name__ == "__main__":
    unittest.main(verbosity=2)
