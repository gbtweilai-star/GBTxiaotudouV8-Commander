# -*- coding: utf-8 -*-
"""art_brief 判据：**四路知识同时到位** · **plan 必须零作用域** · **不直连模块（只走门）** · 缺哪一路如实报缺。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_art_brief -v`
（只读编排；不写盘、不出片、不出网。）
"""
import ast
import importlib
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import art_brief as AB               # noqa: E402
from gbt_allinone.security import policy as POL               # noqa: E402

_LEGS_CN = ("可渲件", "参考件", "动效API", "技法节")


def setUpModule():
    """前置：隔离 store 下**四路的索引都是空的** ⇒ 不先建，`plan` 四路全「没就绪」（假红）。

    🔴 这里**直连兄弟模块建索引**（与 `test_ui_kit.py` 同款）—— 走门建需要 `filesystem_write`
    授权，测试进程里拿不到 ⇒ 首版这么写，换 `--store fresh` 当场 rc=1（真读数咬出来的）。
    直连只用于**夹具**；生产路径（`art_brief.py` 本体）**一律走门**，那条由 AST 判据守着。
    """
    for kind, _cn, _what in AB._LEGS:
        mod = importlib.import_module("gbt_allinone.tools." + kind)
        st = mod.run("status")
        if st.get("src_present") and not st.get("indexed"):
            mod.run("build")


class TestArtBrief(unittest.TestCase):
    def test_status_four_legs_reachable(self):
        st = AB.run("status")
        self.assertTrue(st["ok"], st)
        self.assertEqual(set(st["ops"]), {"status", "where", "plan", "run"}, st["ops"])
        got = {leg["路名"]: leg for leg in st["四路"]}
        self.assertEqual(set(got), set(_LEGS_CN), got)
        for cn, leg in got.items():
            self.assertEqual(leg["gate"], "ok", "「%s」那一路走门不通：%s" % (cn, leg))
        self.assertIn("from", st["出片"])
        self.assertEqual(st["出片"]["from"], "art_chain")

    def test_plan_gives_all_four_legs(self):
        if not any(AB.run("status")["四路"][i]["在位"] for i in range(4)):
            self.skipTest("四路素材都不在盘 => 跳过，不假装跑过")
        r = AB.run("plan", q="复古霓虹按钮的动效", limit=2)
        self.assertTrue(r["ok"], r)
        self.assertEqual(set(r["四路"]), set(_LEGS_CN), r["四路"])
        for cn in _LEGS_CN:
            self.assertGreater(r["四路"][cn]["hits"], 0, "「%s」没给到东西" % cn)
            self.assertTrue(r["四路"][cn]["头几件"], "「%s」头几件是空的" % cn)
        # 每一路该带的**关键格**都要在（否则等于给了个空壳）
        self.assertTrue(r["四路"]["可渲件"]["头几件"][0].get("path"), "可渲件该带 path")
        ref = r["四路"]["参考件"]["头几件"][0]
        self.assertTrue(ref.get("src"), "参考件该带源码路径")
        self.assertIn("Commons Clause", ref.get("license", ""), "参考件该把许可带出来")
        self.assertTrue(r["四路"]["动效API"]["头几件"][0].get("where"), "动效API 该带 文件#L行号")
        self.assertTrue(r["四路"]["技法节"]["头几件"][0].get("where"), "技法节该带 文件#L行号")
        self.assertEqual(r["缺哪一路"], [], r["缺哪一路"])
        self.assertIn("art_chain", r["下一步"], r["下一步"])

    def test_plan_negative_control_reports_gaps_honestly(self):
        """说不认识的 ⇒ 四路都该 0 命中，并**如实列出缺哪四路**（不许拿别的路凑数）。"""
        r = AB.run("plan", q="量子纠缠")
        self.assertTrue(r["ok"], r)
        for cn in _LEGS_CN:
            # 先咬「这一路是**就绪**的」—— 否则 hits=None（没就绪）会被误读成"命中 0"，判据自己骗自己
            self.assertTrue(r["四路"][cn]["ready"], "「%s」没就绪 ⇒ 这条负控不能成立：%s" % (cn, r["四路"][cn]))
            self.assertEqual(r["四路"][cn]["hits"], 0, "「%s」不该硬塞：%s" % (cn, r["四路"][cn]))
        self.assertEqual(len(r["缺哪一路"]), 4, r["缺哪一路"])
        for gap in r["缺哪一路"]:
            self.assertIn("命中 0", gap["为什么"], gap)

    def test_plan_needs_params_and_fail_closed(self):
        r = AB.run("plan")
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)
        u = AB.run("frobnicate")
        self.assertFalse(u["ok"], u)
        self.assertTrue(u["fail_closed"], u)

    def test_scope_shape_plan_is_zero_run_is_loud(self):
        """🔴 判据按「实际做什么」定：`plan` 只读（**零作用域**）· `run` 起进程+写盘 · 未知名 fail-closed。"""
        self.assertEqual(tuple(POL.evaluate("art_brief", {"op": "plan"}).scopes), (),
                         "plan 是纯读编排，不该要任何作用域")
        for op in ("status", "where", ""):
            self.assertEqual(tuple(POL.evaluate("art_brief", {"op": op}).scopes), (), op)
        self.assertEqual(tuple(POL.evaluate("art_brief", {"op": "run"}).scopes),
                         ("process_execute", "filesystem_write"))
        self.assertEqual(tuple(POL.evaluate("art_brief", {"op": "frobnicate"}).scopes),
                         ("process_execute", "filesystem_write"), "未知名必须 fail-closed")

    def test_unready_leg_is_reported_not_faked_as_zero(self):
        """🔴 一路**没就绪**（索引还没建）时必须如实说「没就绪」，**不许**给出看着像"命中 0"的读数。

        这条咬的是换 `--store fresh` 后当场 rc=1 的那个真跟头：内层返回 `needs_build`，
        **根本没有 `hits` 键** ⇒ 首版给 `hits: null`，与真正的「命中 0」长得一样。
        """
        real = AB._cap

        def fake(kind, payload):
            if kind == "bits_kit":
                return {"status": "ok", "denied": False, "missing_scopes": None,
                        "result": {"ok": False, "status": "needs_build",
                                   "error": "索引不在 => 先 op=build"}}
            return real(kind, payload)

        AB._cap = fake
        try:
            r = AB.run("plan", q="霓虹按钮", limit=1)
        finally:
            AB._cap = real
        leg = r["四路"]["参考件"]
        self.assertFalse(leg["ready"], leg)
        self.assertIsNone(leg["hits"], "没就绪就不该给一个像 0 的数：%s" % leg)
        gaps = {g["from"]: g["为什么"] for g in r["缺哪一路"]}
        self.assertIn("bits_kit", gaps, gaps)
        self.assertIn("没就绪", gaps["bits_kit"], gaps)

    def test_work_type_ask_is_decomposed(self):
        """🔴 真跑咬出来的洞：人话问的是**作品类型**（落地页/首屏），四路收的却是**组件名/API名/小节名**。

        不拆解 ⇒ 问「产品落地页首屏」，四路里**只有 design_atlas 一路**命中。拆解后**四路都该有货**。
        """
        r = AB.run("plan", q="产品落地页首屏", limit=1)
        self.assertTrue(r["ok"], r)
        self.assertIn("拆解", r, "该给出拆解账（用了哪张表、加了什么词）：%s" % list(r))
        self.assertIn("落地页", r["拆解"]["作品类型"], r["拆解"])
        for cn in _LEGS_CN:
            self.assertGreater(r["四路"][cn]["hits"], 0, "拆解后「%s」仍没货：%s" % (cn, r["四路"][cn]))

    def test_out_of_scope_ask_says_so_instead_of_faking(self):
        """四路管不着的（视频/音频）⇒ **如实说范围外**并指向该去的域，**不许硬凑候选**给它。"""
        r = AB.run("plan", q="短视频片头", limit=1)
        self.assertTrue(r["ok"], r)
        self.assertIn("范围外提示", r, "视频类提问该给范围外提示：%s" % list(r))
        self.assertIn("视频/成片", r["范围外提示"]["域"], r["范围外提示"])
        for cn in _LEGS_CN:
            self.assertEqual(r["四路"][cn]["hits"], 0,
                             "四路本就不管视频，不该硬凑：%s" % r["四路"][cn])

    def test_no_direct_module_call_only_through_the_door(self):
        """机检：本位是**编排位** —— 只许 `run_task(kind, payload)` 走门，**不许直连兄弟模块**。

        扫 **AST**（不扫全文 —— 会撞上本件自己的 docstring / 注释）。
        """
        tree = ast.parse(Path(AB.__file__).read_text(encoding="utf-8", errors="replace"))
        sibs = {"ui_kit", "bits_kit", "motion_kit", "design_atlas", "art_chain", "vision_print"}
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = (node.module or "")
                for a in node.names:
                    if a.name in sibs or mod.split(".")[-1] in sibs:
                        bad.append(("from %s import %s" % (mod, a.name), node.lineno))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[-1] in sibs:
                        bad.append(("import %s" % a.name, node.lineno))
        self.assertEqual(bad, [], "编排位不许直连兄弟模块（要走 run_task 的门）：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
