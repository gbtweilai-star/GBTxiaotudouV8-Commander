# -*- coding: utf-8 -*-
"""intake_kit 判据：**六件全在 + 许可读数对得上** · **体检台账有出处** · **零执行零出网** · 中文桥与负控。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_intake_kit -v`
（只读上游；不装依赖、不跑外部件的代码、不出网。）
"""
import ast
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import intake_kit as IK              # noqa: E402
from gbt_allinone.security import policy as POL              # noqa: E402

_SEVEN = {"motionsites.ai", "impeccable", "hyperframes",
          "ai-engineering-from-scratch", "Agent-Reach", "ponytail", "DeepSeek-Bot"}


def setUpModule():
    """前置：隔离 store 下索引是空的 ⇒ 不先建，find/api 会假红（同族已栽两次）。"""
    st = IK.run("status")
    if st["indexed"] == 0 and any(p["on_disk"] for p in st["件"]):
        IK.run("build")


class TestIntakeKit(unittest.TestCase):
    def test_seven_pieces_on_disk_with_verified_licenses(self):
        """七件必须在盘，且**许可读数**要与 `gh api` 现读一致（这一条防"把许可写错"）。"""
        st = IK.run("status")
        self.assertTrue(st["ok"], st)
        got = {p["name"]: p for p in st["件"]}
        self.assertEqual(set(got), _SEVEN, got)
        want = {"motionsites.ai": "MIT", "impeccable": "Apache-2.0", "hyperframes": "Apache-2.0",
                "ai-engineering-from-scratch": "MIT", "Agent-Reach": "MIT", "ponytail": "MIT",
                "DeepSeek-Bot": "Apache-2.0"}
        for n, lic in want.items():
            self.assertEqual(got[n]["license"], lic, "「%s」许可读数不对：%s" % (n, got[n]))
        missing = [n for n, p in got.items() if not p["on_disk"]]
        if missing:
            self.skipTest("这些件没落位：%s ⇒ 跳过，不假装跑过" % missing)

    def test_health_ledger_has_readings_and_key_verdicts(self):
        """体检台账必须有读数；三处 `hardcoded_key` 必须**逐条落实**，且**不许说成泄漏**。"""
        st = IK.run("status")
        if not any(p["on_disk"] for p in st["件"]):
            self.skipTest("六件不在盘 ⇒ 跳过")
        led = st["体检台账_20261013"]
        for n in _SEVEN:
            self.assertIn(n, led, "「%s」缺体检读数" % n)
            self.assertIn("files", led[n], led[n])
            self.assertIn("hit", led[n], led[n])
        hits = [n for n, v in led.items() if v["hit"].get("hardcoded_key")]
        self.assertEqual(set(hits), {"hyperframes", "ai-engineering-from-scratch", "Agent-Reach"},
                         "hardcoded_key 命中面变了，落实结论要重写：%s" % hits)
        for n in hits:
            v = st["hardcoded_key_落实"][n]
            self.assertIn("不是泄漏", v, "只许如实说'不是泄漏'并给理由：%s" % v)

    def test_build_indexes_all_seven(self):
        st = IK.run("status")
        if not any(p["on_disk"] for p in st["件"]):
            self.skipTest("件不在盘 ⇒ 跳过")
        if st["indexed"] == 0:
            self.assertTrue(IK.run("build")["ok"])
        by = IK.run("status")["by_piece"]
        self.assertEqual(by.get("motionsites.ai"), 65, "motionsites 就是 65 条提示词：%s" % by)
        self.assertEqual(by.get("ponytail"), 12, "ponytail 就是 12 份 SKILL：%s" % by)
        self.assertGreater(by.get("DeepSeek-Bot", 0), 0, "DeepSeek-Bot 一条都没进索引")
        for n in _SEVEN:
            self.assertGreater(by.get(n, 0), 0, "「%s」一条都没进索引" % n)

    def test_chinese_bridge_routes_to_the_right_piece(self):
        """🔴 正控：中文口语必须被**桥**接到英文名，并落到**对的那一件**上。"""
        cases = {"落地页提示词": "motionsites.ai", "少写代码": "ponytail",
                 "小红书": "Agent-Reach", "无障碍": "impeccable", "群聊": "DeepSeek-Bot"}
        for cn, piece in cases.items():
            r = IK.run("find", q=cn, limit=5)
            self.assertTrue(r["ok"], r)
            self.assertGreater(r["hits"], 0, "「%s」取不到东西" % cn)
            got = {i["piece"] for i in r["items"]}
            self.assertIn(piece, got, "「%s」头几件来自 %s，不含 %s" % (cn, got, piece))

    def test_find_rows_carry_source_line(self):
        r = IK.run("find", q="设计", limit=3)
        self.assertGreater(r["hits"], 0, r)
        for i in r["items"]:
            self.assertTrue(i["path"].startswith("_upstream/"), i)
            self.assertIn("#L", i["where"], i)

    def test_negative_control_zero_hits(self):
        r = IK.run("find", q="量子纠缠", limit=3)
        self.assertEqual(r["hits"], 0, "不认识的说法不许硬塞：%s" % r["items"])
        self.assertEqual(r["bridge"], [], r["bridge"])

    def test_api_and_fail_closed(self):
        self.assertEqual(IK.run("api", name="no_such_thing_zzz")["hits"], 0)
        u = IK.run("frobnicate")
        self.assertFalse(u["ok"], u)
        self.assertTrue(u["fail_closed"], u)
        p = IK.run("api")
        self.assertFalse(p["ok"], p)
        self.assertTrue(p["fail_closed"], p)

    def test_scope_shape(self):
        """`find`/`status`/`api`/`where` = 纯读（**零作用域**）· `build` 写盘 · 未知名 fail-closed。"""
        for op in ("", "status", "where", "find", "api"):
            self.assertEqual(tuple(POL.evaluate("intake_kit", {"op": op}).scopes), (), op)
        self.assertEqual(tuple(POL.evaluate("intake_kit", {"op": "build"}).scopes),
                         ("filesystem_write",))
        self.assertEqual(tuple(POL.evaluate("intake_kit", {"op": "nope"}).scopes),
                         ("filesystem_write",), "未知名必须 fail-closed")

    def test_no_execution_or_network_surface(self):
        """机检：本位**零执行 · 零出网** —— 不许 subprocess/urllib/requests/socket/eval/exec（扫 AST）。"""
        tree = ast.parse(Path(IK.__file__).read_text(encoding="utf-8", errors="replace"))
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
                if isinstance(fn, ast.Name) and fn.id in banned_names:
                    bad.append((fn.id, node.lineno))
        self.assertEqual(bad, [], "出现执行/出网面：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
