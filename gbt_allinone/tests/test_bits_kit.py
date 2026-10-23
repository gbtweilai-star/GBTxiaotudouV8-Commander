# -*- coding: utf-8 -*-
"""bits_kit 判据：**中文人话 → react-bits 真组件** · **许可纪律（不许有拷出去的 op）** · **零执行** · 负控 0 命中。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_bits_kit -v`
（只读上游；不跑任何脚本、不出网、不 npm i。）
"""
import ast
import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import bits_kit as BK   # noqa: E402


def setUpModule():
    """前置：隔离 store 下索引是空的，而用例名的字母序会让 `find`/`api` 类用例先跑 => 不前置就假红。"""
    st = BK.run("status")
    if st["src_present"] and not st["indexed"]:
        BK.run("build")


class TestBitsKit(unittest.TestCase):
    def test_index_present_or_buildable(self):
        st = BK.run("status")
        self.assertTrue(st["ok"], st)
        if not st["src_present"]:
            self.skipTest("素材不在盘（`_upstream/react-bits` 未落位）=> 跳过，不假装跑过")
        if st["indexed"] == 0:
            r = BK.run("build")
            self.assertTrue(r["ok"], r)
        self.assertEqual(BK.run("status")["indexed"], 216, "盘上就该是 216 个组件")

    def test_license_discipline_no_copy_op(self):
        """🔴 许可纪律（MIT + Commons Clause 禁止再分发/移植）：**不许有把组件拷出去的 op**。

        这条是本位与 ui_kit 的**关键区别** —— ui_kit 有 `take`（拷件），本位**故意没有**。
        """
        st = BK.run("status")
        if not st["src_present"]:
            self.skipTest("素材不在盘 => 跳过")
        ops = set(st["ops"])
        self.assertEqual(ops, {"status", "build", "find", "api", "where"}, st["ops"])
        for banned in ("take", "copy", "read", "export", "dump", "save", "write"):
            self.assertNotIn(banned, ops, "不许出现会搬成品的 op：%s" % banned)
        self.assertIn("Commons Clause", st["license"], st["license"])
        self.assertIn("不搬成品", st["restriction"], st["restriction"])
        self.assertEqual(BK.run("take"), {"ok": False, "fail_closed": True,
                                          "error": "未知 op：take", "ops": list(BK._OPS)})

    def test_pro_paid_section_is_excluded(self):
        """官方 `llms.txt` 里混着**付费版 Pro 小节**（Pro Components 230 等）=> 一个都不许进来。"""
        if not BK._LLMS.is_file():
            self.skipTest("清单不在盘 => 跳过")
        cat = BK._catalog()
        self.assertTrue(cat, "清单解不出来")
        bad = {k: v["section"] for k, v in cat.items() if v["section"] not in BK._FREE}
        self.assertEqual(bad, {}, "有付费版 Pro 条目漏进来了：%s" % list(bad)[:5])
        # 🔴 判据要按**路径段**判，不许按子串判 —— 首版用 `"/pro" in url` 把
        #    `/micro/prompt-bar` 误判成付费版（同族教训：坏判据比坏对象更危险）。
        for r in (BK.run("find", q="组件", limit=300)["items"]):
            self.assertIsNone(re.search(r"/pro(/|$)", r["url"] or ""),
                              "付费版 URL 不该出现在索引里：%s" % r["url"])

    def test_chinese_bridge_routes_to_the_right_component(self):
        """🔴 正控：中文口语必须被**桥**接到英文组件名（否则中文人话 0 命中 —— 同族已栽三次）。"""
        cases = {"手风琴画廊": {"AccordionGallery"}, "粒子背景": {"Particles", "ParticleText"},
                 "翻牌": {"SplitFlapText"}, "打字机": {"TextType"}}
        for cn, want in cases.items():
            r = BK.run("find", q=cn, limit=3)
            self.assertTrue(r["ok"], r)
            self.assertGreater(r["hits"], 0, "「%s」取不到组件" % cn)
            got = {i["name"] for i in r["items"]}
            self.assertTrue(got & want, "「%s」头三件 %s 不含 %s" % (cn, got, want))

    def test_top_hit_is_the_obvious_one(self):
        for cn, want in (("手风琴画廊", "AccordionGallery"), ("光标跟随", None)):
            r = BK.run("find", q=cn, limit=1)
            self.assertGreater(r["hits"], 0, "「%s」取不到组件" % cn)
            top = r["items"][0]["name"]
            if want:
                self.assertEqual(top, want, "「%s」首位是 %s" % (cn, top))
            else:
                self.assertIn("Cursor", top, "「%s」首位该是个光标件，实为 %s" % (cn, top))

    def test_negative_control_zero_hits(self):
        r = BK.run("find", q="量子纠缠", limit=3)
        self.assertEqual(r["hits"], 0, "不认识的说法不许硬塞候选：%s" % r["items"])
        self.assertEqual(r["bridge"], [], "不该认出任何桥：%s" % r["bridge"])

    def test_net_flag_is_real_and_filterable(self):
        """联网标必须是**真读出来的**：GridScan 硬编码 CDN，标得上；`only_offline` 要把它筛掉。"""
        st = BK.run("status")
        if not st["src_present"]:
            self.skipTest("素材不在盘 => 跳过")
        self.assertIn("GridScan", st["net_components"], st["net_components"])
        g = BK.run("api", name="GridScan")["items"][0]
        self.assertTrue(g["net"], "GridScan 该带联网标：%s" % g)
        off = BK.run("find", q="网格背景", only_offline=True, limit=300)
        self.assertTrue(all(not i["net"] for i in off["items"]), "only_offline 没筛干净")
        self.assertNotIn("GridScan", {i["name"] for i in off["items"]})

    def test_api_exact_lookup_and_miss(self):
        r = BK.run("api", name="AccordionGallery")
        self.assertEqual(r["hits"], 1, r)
        self.assertTrue(r["items"][0]["src"], "该给源码路径：%s" % r["items"][0])
        self.assertTrue(r["items"][0]["desc"], "说明该取自 llms.txt 原文")
        self.assertEqual(BK.run("api", name="no_such_bit_zzz")["hits"], 0)

    def test_unknown_op_fail_closed(self):
        r = BK.run("frobnicate")
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)

    def test_no_execution_or_network_surface(self):
        """机检：本位**零执行 · 零出网** —— 不许 `subprocess`/`urllib`/`requests`/`socket`/`eval`/`exec`。

        扫 **AST**（不扫全文 —— 扫全文会撞上本件自己的 docstring / 注释，本会话撞过）。
        """
        tree = ast.parse(Path(BK.__file__).read_text(encoding="utf-8", errors="replace"))
        banned_mods = {"subprocess", "urllib", "requests", "socket", "http", "shutil",
                       "ctypes", "importlib", "pickle", "multiprocessing"}
        banned_names = {"eval", "exec", "compile", "__import__"}
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in banned_mods:
                        bad.append(("import %s" % a.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in banned_mods:
                    bad.append(("from %s" % node.module, node.lineno))
            elif isinstance(node, ast.Call):
                fn = node.func
                # 🔴 只禁**裸名字**（`eval(...)`）；不许把 `re.compile(...)` 这种**方法**当禁词
                #    —— 首版用 `getattr(fn,"attr")` 一并抓 ⇒ `re.compile` 被误报 4 处（判据自己坏）。
                if isinstance(fn, ast.Name) and fn.id in banned_names:
                    bad.append((fn.id, node.lineno))
                nm = getattr(fn, "attr", None)
                if nm in ("system", "popen", "urlopen", "spawn", "run", "Popen"):
                    bad.append(("." + nm, node.lineno))
        self.assertEqual(bad, [], "出现执行/出网面：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
