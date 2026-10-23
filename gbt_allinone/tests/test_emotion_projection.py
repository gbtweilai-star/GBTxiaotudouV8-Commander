# -*- coding: utf-8 -*-
"""情感投射 · 带牙用例（R-H183）。

① 叙事四问缺任一 ⇒ 拒绝；只给标签 ⇒ 也拒绝；
② 投射五元素缺任一 ⇒ 拒绝；标签式描述 ⇒ 拒绝；细节动作 ⇒ 通过；
③ 校验层：机器判前三项；**"是否身临其境"只有人能判** —— 机器设 True 判违规，未判则不通过；
④ 不操纵观众：赚眼泪/带节奏/贩卖焦虑类字眼 ⇒ 拒绝；
⑤ 只读：源码不许有联网/写盘/生成路径。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import emotion_projection as ep  # noqa: E402

GOOD_WHY = "不是因为分手本身，而是明明还爱着却再也回不去了"
GOOD_SCENE = "分手三个月后整理房间，翻到对方送的杯子"
GOOD_BLANK = "副歌之后那几秒静默，让人自己填补"
GOOD_LYRIC = "我把你送的杯子收进了柜子最深处"


class NarrativeTests(unittest.TestCase):
    def test_four_questions_all_required(self):
        out = ep.narrate("一个刚分手的人", "", GOOD_SCENE, GOOD_BLANK)
        self.assertFalse(out["ok"])
        self.assertIn("why", out["missing"])

    def test_label_only_is_refused(self):
        out = ep.narrate("一个刚分手的人", "伤感", GOOD_SCENE, GOOD_BLANK)
        self.assertFalse(out["ok"])
        self.assertIn("why", out["label_only"])

    def test_good_narrative_passes(self):
        out = ep.narrate("一个刚分手的人", GOOD_WHY, GOOD_SCENE, GOOD_BLANK)
        self.assertTrue(out["ok"])
        self.assertEqual(sorted(out["narrative"]), sorted(ep.QUESTIONS))

    def test_scene_must_be_concrete_via_scene_anchor(self):
        """贯通①：四问里的"触发场景"由**场景锚定**判——类别词不算场景。"""
        self.assertIn("scene", ep.QUESTIONS, "四问必须含触发场景")
        self.assertNotIn("empathy", ep.QUESTIONS, "旧的『听众代入什么』已被触发场景取代")
        # 用"长到不被标签闸拦下、但不含任何具体化标记"的类别式场景
        bad = ep.narrate("一个刚分手的人", GOOD_WHY, "失去这种感受本身", GOOD_BLANK)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad.get("rule"), "scene_not_concrete", "类别词必须被场景锚定挡下")
        good = ep.narrate("一个刚分手的人", GOOD_WHY, GOOD_SCENE, GOOD_BLANK)
        self.assertTrue(good["ok"])


class ProjectionTests(unittest.TestCase):
    def test_all_five_elements_required(self):
        out = ep.project("某个瞬间突然上扬又落下", "", "副歌前只剩钢琴，副歌后弦乐才涌进来",
                         "第二段主歌比第一段多了半口气的颤抖", "最该说话的时候不说话")
        self.assertFalse(out["ok"])
        self.assertIn("lyric", out["missing"])

    def test_label_style_projection_is_refused(self):
        out = ep.project("悲伤的旋律", GOOD_LYRIC, "钢琴+弦乐",
                         "第二段主歌比第一段多了半口气的颤抖", "最该说话的时候不说话")
        self.assertFalse(out["ok"])
        self.assertIn("melody", out["label_only"])
        self.assertIn("arrangement", out["label_only"])

    def test_detail_style_projection_passes(self):
        out = ep.project("在某个瞬间突然上扬又落下", GOOD_LYRIC,
                         "副歌前只剩钢琴，副歌后弦乐才涌进来",
                         "第二段主歌比第一段多了半口气的颤抖", "最该说话的时候不说话")
        self.assertTrue(out["ok"])
        self.assertEqual(sorted(out["projection"]), sorted(ep.ELEMENTS))


class VerdictTests(unittest.TestCase):
    def _machine(self, **kw):
        base = {k: True for k in ep.MACHINE_CHECKS}
        base.update(kw)
        return base

    def test_machine_cannot_decide_immersive(self):
        out = ep.check({}, {}, self._machine(), immersive_by="machine", immersive_value=True)
        self.assertFalse(out["ok"])
        self.assertIn("机器不许替人", out["why"])

    def test_pending_human_means_not_passed(self):
        out = ep.check({}, {}, self._machine())
        self.assertTrue(out["machine_all_pass"])
        self.assertFalse(out["passed"], "人未判 ⇒ 不通过（不进发布队列）")
        self.assertTrue(out["immersive"]["pending_human"])
        self.assertFalse(out["publish"])

    def test_all_four_pass_only_with_human_verdict(self):
        out = ep.check({}, {}, self._machine(), immersive_by="human", immersive_value=True)
        self.assertTrue(out["passed"])
        self.assertTrue(out["publish"])
        bad = ep.check({}, {}, self._machine(narrative_complete=False),
                       immersive_by="human", immersive_value=True)
        self.assertFalse(bad["passed"], "机器校验未过 ⇒ 打回重做")


class RedLineTextTests(unittest.TestCase):
    def test_manipulation_words_are_refused(self):
        out = ep.scan_text("这段要赚眼泪，带节奏让大家都哭")
        self.assertFalse(out["ok"])
        self.assertIn("no_manipulation", [p["rule"] for p in out["problems"]])

    def test_template_words_are_refused(self):
        out = ep.scan_text("我们做一首通用伤感慢歌小调")
        self.assertFalse(out["ok"])
        self.assertIn("no_template", [p["rule"] for p in out["problems"]])

    def test_module_has_no_network_write_or_generation_paths(self):
        src = Path(ep.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读模块里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
