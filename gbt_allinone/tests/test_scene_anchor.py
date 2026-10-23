# -*- coding: utf-8 -*-
"""场景锚定 · 带牙用例（R-H185）。

① 8 大类场景齐，每类都有细分场景与对应情绪；
② 灵魂锚定四要素缺一 ⇒ 拒绝；
③ 场景必须具体：类别词（失恋 / 挣扎）⇒ 拒绝；具体瞬间 ⇒ 通过；
④ 钩子锚场景不锚情绪：情绪/夸张钩子 ⇒ 拒绝；场景钩子 ⇒ 通过；
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

from gbt_allinone.tools import scene_anchor as sa  # noqa: E402

GOOD_SCENE = "分手三个月后整理房间，翻到对方送的杯子"
GOOD_RESPONSE = "不是嚎啕大哭，是手停了一下，然后把它放进柜子最深处"
GOOD_RESONANCE = "每个人心里都有一个不知道该怎么处理的东西"
GOOD_BLANK = "副歌结束后的那几秒静默，让人想起自己的那个杯子"


class ClassTableTests(unittest.TestCase):
    def test_eight_classes_with_scenes_and_emotions(self):
        d = sa.classes()
        self.assertEqual(d["count"], 8)
        keys = [c["key"] for c in d["classes"]]
        for k in ("失去", "重逢", "挣扎", "突破", "孤独", "愤怒", "治愈", "怀旧"):
            self.assertIn(k, keys)
        for c in d["classes"]:
            self.assertTrue(c["scenes"], "%s 缺细分场景" % c["key"])
            self.assertTrue(c["emotions"], "%s 缺对应情绪" % c["key"])


class SoulTests(unittest.TestCase):
    def test_four_elements_all_required(self):
        out = sa.soul(GOOD_SCENE, "", GOOD_RESONANCE, GOOD_BLANK)
        self.assertFalse(out["ok"])
        self.assertIn("emotion_response", out["missing"])

    def test_category_word_is_not_a_scene(self):
        for bare in ("失恋", "挣扎", "分手", "深夜"):
            out = sa.soul(bare, GOOD_RESPONSE, GOOD_RESONANCE, GOOD_BLANK)
            self.assertFalse(out["ok"], "%s 是类别不是场景" % bare)
            self.assertIn(out.get("rule"), ("scene_not_concrete", "missing"))

    def test_concrete_scene_passes(self):
        out = sa.soul(GOOD_SCENE, GOOD_RESPONSE, GOOD_RESONANCE, GOOD_BLANK)
        self.assertTrue(out["ok"])
        self.assertEqual(sorted(out["soul"]), sorted(sa.SOUL_KEYS))


class HookTests(unittest.TestCase):
    def test_emotion_anchored_hooks_are_refused(self):
        for bad in ("这首歌太伤感了", "治愈系音乐推荐", "励志神曲，燃爆了", "快乐歌曲合集"):
            out = sa.hook(bad)
            self.assertFalse(out["ok"], "这类钩子锚的是情绪：%s" % bad)
            self.assertIn(out["rule"], ("hook_anchors_emotion", "hook_has_no_scene"))

    def test_scene_anchored_hooks_pass(self):
        good = ("分手后半夜翻到旧照片的人，别听这首歌",
                "加班到凌晨三点的人，这首歌给你",
                "面试失败第 7 次，我还在投简历")
        for g in good:
            out = sa.hook(g)
            self.assertTrue(out["ok"], "场景钩子应当通过：%s" % g)
            self.assertTrue(out["anchored_scene"])

    def test_module_has_no_network_or_write_paths(self):
        src = Path(sa.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读模块里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
