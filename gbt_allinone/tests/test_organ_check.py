"""`gbt_allinone/tools/organ_check.py` 的判据（2026-09-23 第 57 轮立）。

═══ 为什么轮到它（**按"被引用过没有"排序的结果**）═══
第 50 轮普查出 21 个无判据工具；第 55 轮定下规矩：**优先级按"这份读数被引用过没有"排**，
不按代码长短排。第 57 轮把剩下 18 个按引用次数排了一遍
（`.scratch/rank_unjudged_tools.py`，AST 口径算"已有判据"的集合，**不手写名单**）：

    1  organ_check              15 次引用 / 6 处     ← 本轮挑它
    2  html_video               12 次引用 / 4 处
    3  vision_probe / host_security_scan   10 次 / 5 处
    …

**而且我去读了那几处引用本身**（脚本自己提醒过"文本出现 ≠ 我引用过它的读数"）：
`memory/2026-09-19.md:2263` 记着**真跑过**「`python -m gbt_allinone.tools.organ_check`」；
`memory/2026-09-22-假绿与自伤清单.md:409` 还记着**它被修过一次真错报** ——

> 「**FR-2 唯一那条改成真修**（不是退役）：`organ_check._probe_err` 原来只给 `missing`，
>  ……这一支是**探针量不了**，不是"这个器官不存在"」

⇒ 它的读数**既被引用过、也被修正过** —— 正属于"错了会污染结论"的那一类。

═══ 判据要钉住的四件事 ═══
① **`_probe_err` 的"未测 ≠ 不存在"**（上面那次真修，最容易在后续改动里被弄丢）；
② **`_score` 的《反假绿律》**：`True` 才算绿，**`未测`（None）不许按绿算**；
③ `_grade` / `_mark` 的三态语义（`未测` 是第三种，不是"红"也不是"绿"）；
④ `_pad` 的东亚宽度 —— 表格对齐靠它，错了就是"读数看着歪"。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from gbt_allinone.tools import organ_check as oc  # noqa: E402


class TestProbeErrSaysUnmeasuredNotMissing(unittest.TestCase):
    """**这是它被修过的那件事**：探针量不了 ⇒ 必须同时给 `missing` 与 `unknown`。

    机器只读 `missing` 会得出"缺件"的错误结论；`unknown`（未测）才是真相。
    """

    def _err(self):
        try:
            raise ImportError("no module named 'x'")
        except ImportError as e:
            return oc._probe_err("vision", e)

    def test_carries_both_missing_and_unknown(self):
        d = self._err()
        self.assertIn("missing", d, "`missing` 被删了 ⇒ 会破坏既有消费者")
        self.assertIn("unknown", d,
                      "**`unknown` 没了 ⇒ 又回到『未测被读成不存在』**（第 409 行记的那次真修）")
        self.assertEqual(d["missing"], ["vision"])
        self.assertEqual(d["unknown"], ["vision"])

    def test_declares_itself_unavailable_and_not_denied(self):
        d = self._err()
        self.assertIs(d["ok"], False)
        self.assertIs(d["unavailable"], True, "量不了却没标 unavailable")
        self.assertIs(d["denied"], False, "量不了 ≠ 被门拒绝（两件事，不许混）")
        self.assertEqual(d["rule"], "organ_probe_unavailable")

    def test_note_states_the_口径_and_why_keeps_the_exception_type(self):
        d = self._err()
        self.assertIn("未测", d["note"], "note 没写清口径：%r" % d["note"])
        self.assertIn("不等于", d["note"], "note 没写『未测 ≠ 不存在』：%r" % d["note"])
        self.assertIn("ImportError", d["why"], "why 里没有异常类型 ⇒ 机器仍然读不出成因")
        self.assertIn("err ImportError", d["text"], "保留的可读文本变了")


class TestScoreNeverCountsUnmeasuredAsGreen(unittest.TestCase):
    """`_score` 的《反假绿律》：**未测（None）不按绿算**（源码注释原话）。"""

    def test_only_true_counts(self):
        self.assertEqual(oc._score([True, True, True, True]), 100)
        self.assertEqual(oc._score([True, False, False, False]), 25)
        self.assertEqual(oc._score([False, False, False, False]), 0)

    def test_none_is_not_green(self):
        """**核心**：一条真、三条未测 ⇒ 25 分，**不是 100 分**。

        这条是本文件存在的理由：`未测` 若被算成绿，整台体检器就会**假绿**。
        """
        self.assertEqual(oc._score([True, None, None, None]), 25,
                         "`未测` 被按绿算了 ⇒ 假绿（这正是本轮要钉住的）")
        self.assertEqual(oc._score([None, None, None, None]), 0)
        self.assertEqual(oc._score([None, True, None, True]), 50)

    def test_score_stays_on_the_quartile_grid(self):
        """不变量：四条各 25% ⇒ 取值只能是 {0,25,50,75,100}（写成集合，不写死单个值）。"""
        import itertools
        for combo in itertools.product((True, False, None), repeat=4):
            self.assertIn(oc._score(list(combo)), {0, 25, 50, 75, 100},
                          "组合 %s 算出了网格外的分：%s" % (combo, oc._score(list(combo))))


class TestGradeAndMarkAreThreeState(unittest.TestCase):
    def test_grade_mapping(self):
        for score, want in ((100, "器官"), (75, "准器官"), (50, "半功能"),
                            (25, "功能"), (0, "未落地")):
            self.assertEqual(oc._grade(score), want)
        self.assertEqual(oc._grade(37), "", "网格外的分应当没有档位（不许硬凑一个）")

    def test_mark_is_three_state(self):
        self.assertEqual(oc._mark(True), "绿")
        self.assertEqual(oc._mark(False), "红")
        for other in (None, "unknown", 0, "", []):
            self.assertEqual(oc._mark(other), "未测",
                             "%r 被标成了 %s —— 非 True/False 一律是『未测』" % (other, oc._mark(other)))


class TestPadAccountsForCjkWidth(unittest.TestCase):
    def test_cjk_counts_as_two_columns(self):
        """表格对齐靠它：一个汉字算 2 列、ASCII 算 1 列。"""
        from unicodedata import east_asian_width
        for text in ("abc", "中文", "混排abc中", ""):
            out = oc._pad(text, 12)
            used = sum(2 if east_asian_width(ch) in ("W", "F") else 1 for ch in out)
            self.assertGreaterEqual(used, 12, "%r 补完还不到 12 列：%r" % (text, out))
            self.assertTrue(out.startswith(text), "补空格把原文本改了：%r" % out)

    def test_overlong_text_still_gets_a_separator(self):
        """超宽文本不许被截断，但**至少留一个空格**（否则两列会粘在一起）。"""
        out = oc._pad("一二三四五六七八九十", 4)
        self.assertTrue(out.startswith("一二三四五六七八九十"))
        self.assertTrue(out.endswith(" "), "超宽时没留分隔空格：%r" % out)


if __name__ == "__main__":
    unittest.main()
