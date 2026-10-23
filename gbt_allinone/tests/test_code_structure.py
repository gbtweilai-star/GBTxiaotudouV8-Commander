# -*- coding: utf-8 -*-
"""`project_context` 的**代码结构四面** · 契约测试（2026-09-23 接）。

守四件事：
  ① **四面真能跑**：symbols / deps / tests 各出该有的字段；`structure` 是三面速览
  ② **结果必须可 JSON 序列化** —— 本轮实测踩到的真坑：`call_graph.find()` 返回 `Symbol`
     **活对象**，直接交出去会让能力位返回体、审计落盘、面板渲染**全都炸**。
     这一条把所有面的"活对象泄漏"一次挡住。
  ③ **计数必须自洽**：`提到 + 没提到 + 跳过 == 源文件数`。
     本轮实测踩到：`mentioned` 以 **stem 为键**，同名文件被折叠 ⇒ 167+78+16=261 ≠ 266。
     **计数不平就是读数坏了**，不许当四舍五入。
  ④ **边界必须跟着结果走**：调用图带 `unresolved_ratio`，测试面带"不是行覆盖"，
     依赖面带"只看 import 语句" —— 少了这些，读的人会把缺口当结论。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_cs_test_"))

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone import project_context as PC            # noqa: E402
from gbt_allinone.tools import code_structure as CS       # noqa: E402


class ReachabilityTests(unittest.TestCase):
    """① 四面真能跑（不 mock —— 就在真仓上读）。"""

    def test_symbols_finds_a_known_top_level_def(self):
        r = PC.run("symbols", name="run_task")
        self.assertEqual("ok", r["status"])
        self.assertTrue(r["symbols_total"] > 1000, "符号总数太少 ⇒ 范围口径可疑")
        self.assertTrue(r["matches"], "run_task 是顶层函数，应当能找到")
        m = r["matches"][0]
        for k in ("path", "name", "kind", "line"):
            self.assertIn(k, m)
        self.assertTrue(m["path"].endswith(".py"))

    def test_symbols_nonsense_name_yields_no_match(self):
        r = PC.run("symbols", name="绝不存在的符号名XYZ")
        self.assertEqual([], r["matches"])

    def test_deps_reports_internal_edges_and_external_names(self):
        r = PC.run("deps", limit=5)
        self.assertGreater(r["internal_edges_n"], 0, "内部 import 边一条都没有 ⇒ 口径坏了")
        self.assertTrue(r["external_top"], "外部三方名一个都没有 ⇒ 口径坏了")
        self.assertIn("import 语句", r["boundary"])

    def test_tests_face_reports_both_buckets(self):
        r = PC.run("tests", limit=5)
        self.assertGreater(r["test_files_n"], 0)
        self.assertGreater(r["mentioned_n"], 0)
        self.assertIn("不是行覆盖", r["boundary"])

    def test_structure_is_the_three_fast_faces(self):
        r = PC.run("structure", limit=3)
        for k in ("symbols", "deps", "tests"):
            self.assertIn(k, r)
        self.assertNotIn("calls", r, "structure 里不该有调用图（那一面 4.2s，要按需单独调）")


class SerializationTests(unittest.TestCase):
    """② 结果必须可 JSON 序列化 —— 活对象泄漏会炸掉返回体/审计/面板。"""

    def test_every_face_is_json_serializable(self):
        cases = [("symbols", {"name": "run_task"}), ("deps", {"limit": 3}),
                 ("tests", {"limit": 3}), ("structure", {"limit": 3}),
                 ("calls", {"what": "find", "name": "run_task"})]
        for op, kw in cases:
            with self.subTest(op=op):
                r = PC.run(op, **kw)
                try:
                    json.dumps(r, ensure_ascii=False)
                except TypeError as e:
                    self.fail("%s 的返回里有活对象（不可 JSON 序列化）：%s" % (op, e))

    def test_calls_find_returns_plain_dicts(self):
        r = PC.run("calls", what="find", name="run_task")
        self.assertTrue(r["find"], "run_task 至少该在 api.py 里定义一次")
        first = r["find"][0]
        self.assertIsInstance(first, dict, "callers/find 返回的不是纯数据")
        json.dumps(first, ensure_ascii=False)


class ArithmeticTests(unittest.TestCase):
    """③ 计数自洽。"""

    def test_tests_buckets_add_up(self):
        r = PC.run("tests")
        tot = r["mentioned_n"] + r["unmentioned_n"] + r["skipped_n"]
        self.assertEqual(r["source_modules_n"], tot,
                         "提到 %s + 没提到 %s + 跳过 %s = %s，而源文件数是 %s —— 计数不平"
                         % (r["mentioned_n"], r["unmentioned_n"], r["skipped_n"],
                            tot, r["source_modules_n"]))

    def test_duplicate_stems_are_reported(self):
        """同名文件（同名 stem）必须**报出来** —— 那正是第一版折叠计数的地方。"""
        r = PC.run("tests")
        self.assertIn("duplicate_stems_n", r)


class BoundaryAndErrorTests(unittest.TestCase):
    """④ 边界随结果走 + 用法错误带机读码。"""

    def test_calls_carries_unresolved_ratio(self):
        r = PC.run("calls", what="find", name="run_task")
        self.assertIn("unresolved_ratio", r["stats"],
                      "调用图没带未解析率 ⇒ 读的人会把缺口当结论")
        self.assertIn("未解析率", r["boundary"])

    def test_bad_what_is_a_coded_user_error(self):
        with self.assertRaises(CS.CodeStructureError) as cm:
            CS.calls(what="nonsense", name="x")
        self.assertEqual("bad_what", cm.exception.code)

    def test_root_outside_repo_refused(self):
        outside = Path(tempfile.gettempdir())
        with self.assertRaises(CS.CodeStructureError) as cm:
            CS.symbols(str(outside))
        self.assertEqual("outside_repo", cm.exception.code)

    def test_unknown_project_context_op_still_says_error(self):
        r = PC.run("绝不存在的op")
        self.assertEqual("error", r["status"])

    def test_doc_faces_still_work(self):
        """加成不该把原来的文档面弄坏（brief 是默认 op）。"""
        r = PC.run("brief")
        self.assertEqual("ok", r["status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
