# -*- coding: utf-8 -*-
"""门盲区守护 判据（R-H990 · 主人令「绝对不能有任何盲区」）。

它只锁一件事：**未决定（门盲区）必须为 0**。
盲区定义与判法**只从门本体读**（`gate_visibility` 直接调）—— 本文件不复刻第二份范围表。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class BlindSpotZeroTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from gbt_allinone.tools import gate_visibility as GV
        cls.GV = GV
        cls.rows = GV.scan()["files"]

    def test_scan_is_not_empty(self):
        """§45：扫描到 0 个文件不许当通过（空清单不是绿）。"""
        self.assertGreater(len(self.rows), 1000, "扫描结果过小，可能扫描本身坏了")

    def test_zero_undecided(self):
        """⚡ 主判据：未决定（门盲区）必须为 0。"""
        und = [r for r in self.rows if r["state"] == "未决定"]
        sample = "\n".join("  %s —— %s" % (r["path"], r["why"]) for r in und[:15])
        self.assertEqual(len(und), 0, "仍有 %d 件未决定：\n%s" % (len(und), sample))

    def test_three_states_only(self):
        states = {r["state"] for r in self.rows}
        self.assertTrue(states <= {"已纳入", "显式不纳入", "未决定"}, states)

    def test_nothing_is_watched_without_rule(self):
        """§三判据：已纳入的每一条都得能说出凭据（不允许"空白当绑好"）。"""
        for r in self.rows:
            if r["state"] == "已纳入":
                self.assertTrue(r["why"], r["path"])

    def test_declared_non_watch_always_carries_reason(self):
        """显式不纳必须带理由与出处（不许无标注的不纳）。"""
        for r in self.rows:
            if r["state"] == "显式不纳入" and r["path"].endswith((".toml", ".tpl", ".py", ".ts", ".cmd")):
                self.assertTrue(r["why"], r["path"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
