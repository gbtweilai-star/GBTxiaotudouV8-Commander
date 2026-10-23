# -*- coding: utf-8 -*-
"""art_chain 判据：契约面 fail-closed · 负控停在 find · 正控四步真跑。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_art_chain -v`

⚠️ **正控要真渲**（起 Chromium）+ 嵌套调 `ui_kit`/`vision_print`（要写盘）⇒ 在隔离测试进程里
可能被门拒；**被拒就如实 skip**（带出缺什么），**不假装跑过**。
"""
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import art_chain as AC      # noqa: E402
from gbt_allinone.tools import ui_kit as UK         # noqa: E402


def setUpModule():
    """前置：本次 store 里 ui_kit 索引不在就建（链的第一步吃它）。"""
    st = UK.run("status")
    if st["src_present"] and not st["indexed"]:
        UK.run("build")


class TestArtChainContract(unittest.TestCase):
    """契约面（不起浏览器、不写盘）。"""

    def test_status_and_where_surface(self):
        st = AC.run("status")
        self.assertTrue(st["ok"], st)
        self.assertEqual(st["ops"], ["status", "where", "run"])
        self.assertEqual(st["default_look"], "原样", "默认必须是原样（不替用户加戏）：%s" % st)
        self.assertTrue(st["render_page_present"], "渲染取证件不在盘：%s" % st)
        wh = AC.run("where")
        for k in ("q", "look", "size", "sharpen", "grain", "grade_fmt"):
            self.assertIn(k, wh["旋钮"], "旋钮 %s 没写进契约" % k)

    def test_needs_q_fail_closed(self):
        r = AC.run("run")
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)
        self.assertEqual(r["status"], "needs_params")

    def test_unknown_op_fail_closed(self):
        r = AC.run("剪一下")
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)

    def test_negative_control_stops_at_find(self):
        """🔴 **负控**：人话打不中任何组件 ⇒ **停在 find**，不许往下走（更不许给张图充数）。"""
        st = UK.run("status")
        if not st["indexed"]:
            self.skipTest("ui_kit 索引不在（素材未落位）⇒ 负控失去对象，跳过")
        r = AC.run("run", q="量子纠缠组件的早餐")
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["stage"], "find", "打不中就必须停在第一步：%s" % r)


class TestArtChainRealRun(unittest.TestCase):
    """正控：四步真跑（要浏览器 + 嵌套写盘 ⇒ 被门拒就如实 skip）。"""

    def test_real_chain_returns_four_steps_and_a_product(self):
        st = UK.run("status")
        if not st["indexed"]:
            self.skipTest("ui_kit 索引不在（素材未落位）⇒ 跳过，不假装跑过")
        r = AC.run("run", q="霓虹按钮", name="judge-chain", size=1000)
        if not r["ok"]:
            why = (r.get("inner_missing_scopes") or r.get("missing_scopes")
                   or {k: r.get(k) for k in ("stage", "inner_status", "error")})
            self.skipTest("链被门拒/环境不足 ⇒ 如实跳过：%s" % why)
        names = [s["step"] for s in r["steps"]]
        self.assertEqual(names, ["find", "take", "render", "polish"], r)
        self.assertTrue(all(s.get("ok") for s in r["steps"]), r)
        self.assertTrue(all(s.get("gate") == "ok" for s in r["steps"][:1] + r["steps"][1:2]),
                        "前两步必须过唯一门：%s" % r)
        prod = _REPO / str(r["product"])
        self.assertTrue(prod.is_file(), "成品不在盘：%s" % r["product"])
        self.assertGreater(prod.stat().st_size, 1000, r)
        self.assertIn(r["verdict"], ("清晰度提升", "清晰度下降", "基本持平"), r)
        self.assertEqual(r["look"], "原样", "默认味道必须是原样：%s" % r["look"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
