# -*- coding: utf-8 -*-
"""模型环轮询的回归判据（2026-11-10 实测血账）。

血账：免费池是一环多格，每格是**不同上游**。实测连发 5 次只成 1 次，根因两条：
  ① `note_model(ok=False)` 不推进 `rr` ⇒ 坏格永远占环首，每通都撞同一格；
  ② `run()` 里「硬停」写在「换格」之前 ⇒ bad_request 永远轮不到换格，
     而 Cohere 那一格会把自己的转码失败包成 400（text field must not be empty）。
"""
import ast
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.llm import cloud_llm as CL          # noqa: E402
from gbt_allinone.llm import key_gateway as KG       # noqa: E402


class TestNextCell(unittest.TestCase):
    def test_wraps_around_tail(self):
        ring = ["a", "b", "c"]
        self.assertEqual(CL._next_cell(ring, 2, {"c"}), 0)   # 环尾绕回起点

    def test_skips_cells_already_tried(self):
        ring = ["a", "b", "c"]
        self.assertEqual(CL._next_cell(ring, 0, {"a", "b"}), 2)

    def test_none_when_ring_exhausted(self):
        ring = ["a", "b"]
        self.assertIsNone(CL._next_cell(ring, 1, {"a", "b"}))

    def test_single_cell_never_rotates(self):
        self.assertIsNone(CL._next_cell(["a"], 0, {"a"}))


class TestFailedCellAdvancesRing(unittest.TestCase):
    """失败也要前进 —— 否则坏格把整环堵死（实测连堵 4 通）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = KG._store_dir
        KG._store_dir = lambda: Path(self._tmp.name)

    def tearDown(self):
        KG._store_dir = self._orig
        self._tmp.cleanup()

    def test_failure_moves_round_robin_cursor(self):
        ring = KG.model_ring("kilo")
        self.assertGreater(len(ring), 2, "kilo 应当声明多格免费模型环")
        first = KG.model_order("kilo")[0]
        self.assertEqual(first, ring[0], "干净运行态应从环首开始")
        KG.note_model("kilo", first, ok=False, status=400,
                      error="Provider returned error")
        nxt = KG.model_order("kilo")
        self.assertNotEqual(nxt[0], first, "失败后环首必须离开坏格")
        # 上游包成 400 的坏格还要进短冷却（不然它会一直排在环里被撞）
        self.assertIn(first, KG.model_cooldowns("kilo"))


class TestHardStopOrder(unittest.TestCase):
    """静态接线断言：硬停必须在 `_next_cell` 之后（否则换格是死代码）。"""

    def test_rotate_call_precedes_hardstop_return(self):
        src = (Path(_REPO) / "gbt_allinone" / "llm" / "cloud_llm.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = [n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "run"][0]
        rotate = hardstop = None
        for node in ast.walk(fn):
            seg = ast.get_source_segment(src, node) or ""
            if (rotate is None and isinstance(node, ast.Call)
                    and getattr(node.func, "id", "") == "_next_cell"):
                rotate = node.lineno
            if (hardstop is None and isinstance(node, ast.Return)
                    and "why_no_failover" in seg):
                hardstop = node.lineno
        self.assertIsNotNone(rotate, "run() 里找不到 _next_cell 换格")
        self.assertIsNotNone(hardstop, "run() 里找不到硬停 return")
        self.assertLess(rotate, hardstop,
                        "换格必须发生在硬停之前，否则 bad_request 永远轮不到换格")

    def test_starved_shapes(self):
        self.assertTrue(CL._is_starved(CL.REASONING_STARVED))
        self.assertTrue(CL._is_starved(CL.BUDGET_EATEN))
        self.assertFalse(CL._is_starved(CL.EMPTY_COMPLETION))
        self.assertFalse(CL._is_starved("HTTP 500 boom"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
