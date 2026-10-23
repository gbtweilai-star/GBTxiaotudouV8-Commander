# -*- coding: utf-8 -*-
"""做梦技能（只读骨架）契约测试：**不执行 · 不造念 · 默认不巩固**。"""
from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone import trace_store as TS              # noqa: E402
from gbt_allinone.tools import dream_replay as DR       # noqa: E402


class DreamReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gbt_dream_")
        TS._STORE = Path(self.tmp.name)
        TS.TRACE_DIR = Path(self.tmp.name) / "traces"

    def tearDown(self):
        self.tmp.cleanup()

    def test_five_primitives_present(self):
        self.assertEqual([p.value for p in DR.DreamPrimitive],
                         ["日间念", "召回", "变异", "模拟", "巩固"])

    def test_empty_library_reports_empty_not_fake(self):
        out = DR.dream_once()
        self.assertEqual(out["consolidated"], 0)
        self.assertIs(out["external_action"], False)
        self.assertIn("没有念", out["note"], "空表必须报空，不许编一条念")
        self.assertEqual(TS._load("obsessions"), [])

    def test_dangling_source_obsession_is_dropped(self):
        # 直接塞一条"悬空源"的念（绕过写入校验），obsess 必须把它剔掉
        TS.TRACE_DIR.mkdir(parents=True, exist_ok=True)
        (TS.TRACE_DIR / "obsessions.jsonl").write_text(
            '{"id":"ob-x","subject":"事","obsession_type":"未了念","intensity":0.9,'
            '"source_trace_ids":["nope"],"half_life_s":3600}\n', encoding="utf-8")
        got = DR.obsess()
        self.assertEqual(got["count"], 0, "源查不到 ⇒ 这条念不成立")

    def test_recall_orders_by_intensity_and_default_no_consolidate(self):
        TS.TRACE_DIR.mkdir(parents=True, exist_ok=True)
        (TS.TRACE_DIR / "traces.jsonl").write_text(
            '{"id":"t1","subject":"a"}\n{"id":"t2","subject":"b"}\n', encoding="utf-8")
        (TS.TRACE_DIR / "obsessions.jsonl").write_text(
            '{"id":"ob1","subject":"a","obsession_type":"未了念","intensity":0.3,'
            '"source_trace_ids":["t1"],"half_life_s":86400}\n'
            '{"id":"ob2","subject":"b","obsession_type":"过阈念","intensity":0.9,'
            '"source_trace_ids":["t2"],"half_life_s":86400}\n', encoding="utf-8")
        rec = DR.recall()
        self.assertEqual([r["subject"] for r in rec["recalled"]], ["b", "a"], "必须按 intensity 降序")
        out = DR.dream_once()
        self.assertEqual(out["consolidated"], 0, "默认不巩固（起步期只重演）")
        self.assertIs(out["external_action"], False)
        self.assertTrue(all(r["half_life_s"] > 0 for r in out["replayed"]))

    def test_no_external_action_primitives_in_source(self):
        # 只扫**代码**：先去掉文档字符串与注释 —— 否则"文档里提到 run_task(" 会被误判成命中
        import ast
        src = inspect.getsource(DR)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(getattr(node.body[0], "value", None), ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    node.body.pop(0)
        code = ast.unparse(tree)
        code = "\n".join(l.split("#", 1)[0] for l in code.splitlines())
        for bad in ("run_task(", "subprocess", "Popen", "os.system", "urlopen", "requests."):
            self.assertNotIn(bad, code, f"做梦不执行：源码里不该有 {bad}")


if __name__ == "__main__":
    unittest.main()
