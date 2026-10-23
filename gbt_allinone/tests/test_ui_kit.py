# -*- coding: utf-8 -*-
"""ui_kit 判据：**中文人话 → 类目桥** · 负控 0 命中 · 取件越界拒。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_ui_kit -v`
（只读，不联网、不执行组件里的任何东西。）
"""
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import ui_kit as UK   # noqa: E402


def setUpModule():
    """前置：**这次跑用的 store 里没有索引就先建**（隔离 store 下索引是空的；
    且用例名的字母序会让 "find" 类用例先跑 ⇒ 不前置就会假红）。"""
    if UK.run("status")["src_present"] and not UK.run("status")["indexed"]:
        UK.run("build")


class TestUiKit(unittest.TestCase):
    def test_index_present_or_buildable(self):
        st = UK.run("status")
        self.assertTrue(st["ok"], st)
        if not st["src_present"]:
            self.skipTest("素材不在盘（`_upstream/galaxy` 未落位）⇒ 跳过，不假装跑过")
        if st["indexed"] == 0:
            r = UK.run("build")
            self.assertTrue(r["ok"], r)
        self.assertGreater(UK.run("status")["indexed"], 0, "索引建不起来")

    def test_chinese_bridge_routes_to_the_right_category(self):
        """🔴 正控：中文「卡片」必须被**桥**接到英文类目 `Cards`。

        这条咬的是一次实测事故：`find(q="卡片", cat="Cards")` 曾是 **0 命中** ——
        因为 idf 的 **df 统计漏了桥字段** ⇒ 桥命中的词拿不到权重。
        """
        r = UK.run("find", q="卡片", cat="Cards", limit=3)
        self.assertTrue(r["ok"], r)
        self.assertGreater(r["hits"], 0, "中文桥没把「卡片」接到 Cards：%s" % r)
        self.assertTrue(all(i["cat"] == "Cards" for i in r["items"]), r["items"])

    def test_bridge_covers_the_main_categories(self):
        for cn, cat in (("按钮", "Buttons"), ("加载动画", "loaders"), ("开关", "Toggle-switches")):
            r = UK.run("find", q=cn, limit=1)
            self.assertTrue(r["hits"] > 0, "「%s」取不到件" % cn)
            self.assertEqual(r["items"][0]["cat"], cat,
                             "「%s」没接到 %s：%s" % (cn, cat, r["items"][0]))

    def test_negative_control_zero_hits(self):
        """表里没有的说法必须**0 命中**（不许硬塞候选）。"""
        r = UK.run("find", q="量子纠缠组件", limit=3)
        self.assertEqual(r["hits"], 0, "不认识的说法不许硬塞候选：%s" % r["items"])

    def test_take_refuses_outside_the_galaxy_tree(self):
        r = UK.run("take", path="gbt_allinone/api.py")
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
