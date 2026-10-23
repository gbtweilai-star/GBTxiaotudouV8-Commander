# -*- coding: utf-8 -*-
"""人机验证情报台账 · 带牙用例（R-H180）。

① 三部门各一张台账，**骨架期必须是空的**（空就是空）；
② 六字段齐（缺字段 ⇒ 违规）；
③ **不主动绕做成机械闸**：action 只许四条路；绕过类动作/字眼一律判违规；
④ recommend() 的顺序：官方 API → 官方 AI → 人机协作（**没有"绕过"这一条**）；
⑤ 只读：源码不许有联网/写盘路径。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import verification_watch as vw  # noqa: E402


class LedgerTests(unittest.TestCase):
    def test_three_departments_and_skeleton_is_empty(self):
        st = vw.status()
        self.assertEqual([g["group"] for g in st["groups"]], list(vw.GROUPS))
        self.assertEqual(st["entries_total"], 0, "骨架期不许有情报（空就是空）")
        self.assertTrue(st["ok"])
        self.assertTrue(st["readonly"])

    def test_entry_defaults_never_pick_a_bypass_route(self):
        e = vw.make_entry("music_intel", "抖音", "滑块")
        self.assertIn(e["action"], vw.ACTIONS)
        self.assertEqual(e["action"], "human_in_loop", "没有官方 API 就登记人机协作")
        e2 = vw.make_entry("film_intel", "B站", "短信", official_api="开放平台上传接口")
        self.assertEqual(e2["action"], "api", "有官方 API 就走 API")

    def test_missing_fields_are_violations(self):
        rep = vw.validate([{"group": "music_intel", "platform": "抖音"}], group="music_intel")
        self.assertFalse(rep["ok"])
        self.assertIn("missing_field", [v["rule"] for v in rep["violations"]])

    def test_bypass_actions_and_words_are_forbidden(self):
        bad_action = vw.make_entry("video_intel", "快手", "行为验证")
        bad_action["action"] = "bypass"
        rep = vw.validate([bad_action], group="video_intel")
        self.assertIn("bypass_forbidden", [v["rule"] for v in rep["violations"]])
        bad_word = vw.make_entry("video_intel", "快手", "行为验证")
        bad_word["blocking_scenario"] = "想用 captcha_solver 自动过"
        rep2 = vw.validate([bad_word], group="video_intel")
        self.assertIn("bypass_forbidden", [v["rule"] for v in rep2["violations"]])

    def test_recommend_order_has_no_bypass_route(self):
        self.assertEqual(vw.recommend("有官方接口"), "api")
        self.assertEqual(vw.recommend("", True), "official_ai")
        self.assertEqual(vw.recommend(), "human_in_loop")
        self.assertNotIn("bypass", vw.ACTIONS)
        self.assertNotIn("绕过", vw.RED_LINE + " ".join(vw.ACTIONS))

    def test_module_has_no_network_or_write_paths(self):
        src = Path(vw.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读模块里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
