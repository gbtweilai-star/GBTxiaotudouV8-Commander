# -*- coding: utf-8 -*-
"""motion_kit 判据：**中文人话 → anime.js 真 API** · **运行时与索引咬得上** · 负控 0 命中 · 无任意执行面。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_motion_kit -v`
（只读上游；`prove` 只在本机原生 `import` 引擎算纯函数，零出网、不跑上游任何脚本。）
"""
import ast
import shutil
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import motion_kit as MK   # noqa: E402


def setUpModule():
    """前置：隔离 store 下索引是空的，而用例名的字母序会让 `find`/`api` 类用例先跑 ⇒ 不前置就假红。"""
    st = MK.run("status")
    if st["src_present"] and not st["indexed"]:
        MK.run("build")


class TestMotionKit(unittest.TestCase):
    def test_index_present_or_buildable(self):
        st = MK.run("status")
        self.assertTrue(st["ok"], st)
        if not st["src_present"]:
            self.skipTest("引擎不在盘（`_upstream/anime` 未落位）⇒ 跳过，不假装跑过")
        if st["indexed"] == 0:
            r = MK.run("build")
            self.assertTrue(r["ok"], r)
        self.assertGreater(MK.run("status")["indexed"], 0, "索引建不起来")

    def test_runtime_and_index_agree(self):
        """🔴 两处真相对账：**运行时导出数** 必须与 **索引条数** 咬得上。

        这条咬的是一个真栽过的跟头：`index$1/$2/$3` 这类带 `$` 的命名空间导入被 `\\w+` 漏掉，
        索引只出 64 条而运行时 67 条（差的正是 `utils`/`svg`/`text`）。
        """
        st = MK.run("status")
        if not st["src_present"]:
            self.skipTest("引擎不在盘 ⇒ 跳过")
        if not shutil.which("node"):
            self.skipTest("本机没有 node ⇒ 原生真跑做不了（如实跳过，不假装跑过）")
        r = MK.run("prove")
        self.assertTrue(r["ok"], r)
        self.assertGreater(r["exports_runtime"], 0, r)
        self.assertTrue(r["consistent"], "运行时导出数与索引条数对不上：%s" % r)
        self.assertEqual(r["calc"]["clamp"], 3, r["calc"])
        self.assertEqual(r["calc"]["lerp"], 2.5, r["calc"])
        self.assertEqual(r["calc"]["mapRange"], 50, r["calc"])

    def test_chinese_bridge_routes_to_the_right_api(self):
        """🔴 正控：中文口语必须被**桥**接到英文 API 名（否则中文人话 0 命中 —— 同族已栽三次）。"""
        cases = {
            "弹跳的按钮": {"createSpring", "spring", "Spring"},
            "缓动曲线": {"cubicBezier", "eases", "steps"},
            "打字机": {"splitText", "TextSplitter", "scrambleText"},
            "拖拽卡片": {"Draggable", "createDraggable"},
        }
        for cn, want in cases.items():
            r = MK.run("find", q=cn, limit=3)
            self.assertTrue(r["ok"], r)
            self.assertGreater(r["hits"], 0, "「%s」取不到 API" % cn)
            got = {i["name"] for i in r["items"]}
            self.assertTrue(got & want, "「%s」头三件 %s 不含 %s" % (cn, got, want))

    def test_top_hit_is_the_obvious_one(self):
        for cn, want in (("错开入场", "stagger"), ("沿路径飞", "createMotionPath"),
                         ("时间线编排", None)):
            r = MK.run("find", q=cn, limit=1)
            self.assertGreater(r["hits"], 0, "「%s」取不到 API" % cn)
            top = r["items"][0]["name"]
            if want is None:
                self.assertIn(top, {"Timeline", "createTimeline"}, "「%s」首位是 %s" % (cn, top))
            else:
                self.assertEqual(top, want, "「%s」首位是 %s" % (cn, top))

    def test_negative_control_zero_hits(self):
        """表里没有的说法必须**0 命中**（不许硬塞候选）。"""
        r = MK.run("find", q="量子纠缠", limit=3)
        self.assertEqual(r["hits"], 0, "不认识的说法不许硬塞候选：%s" % r["items"])
        self.assertEqual(r["bridge"], [], "不该认出任何桥：%s" % r["bridge"])

    def test_api_exact_lookup_and_out_of_scope(self):
        r = MK.run("api", name="createSpring")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["hits"], 1, r)
        self.assertTrue(r["items"][0]["sig"], "签名该从 .d.ts 现读到：%s" % r["items"][0])
        self.assertEqual(r["items"][0]["name"], "createSpring")
        self.assertEqual(MK.run("api", name="no_such_api_zzz")["hits"], 0)

    def test_unknown_op_fail_closed(self):
        r = MK.run("frobnicate")
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)

    def test_no_arbitrary_execution_surface(self):
        """机检：本位只许 `subprocess`（且**绝不 shell=True**）跑 Node 探针；不许 `os.system`/`eval`/`exec`。

        扫 **AST**（不扫全文 —— 扫全文会撞上本件自己的 docstring / 注释，本会话撞过）。
        """
        tree = ast.parse(Path(MK.__file__).read_text(encoding="utf-8", errors="replace"))
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "attr", None) or getattr(fn, "id", None)
                if name == "system" or (isinstance(fn, ast.Name) and fn.id in ("eval", "exec")):
                    bad.append((name, node.lineno))
                if name in ("run", "Popen", "call", "check_output"):
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value:
                            bad.append(("shell=True", node.lineno))
        self.assertEqual(bad, [], "出现任意执行面：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
