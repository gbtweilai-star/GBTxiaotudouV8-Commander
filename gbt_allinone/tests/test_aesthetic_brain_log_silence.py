"""R-H604（2026-09-25）· `brain/aesthetic_brain.py` 的 FR-5 回归用例。

被测故障（**机检命中**，不是推演）：
    `python -m gbt_allinone.tools.false_report_audit --scope workspace`
      → 命中 `brain/aesthetic_brain.py:18  [FR-5] 记录形成处的静默`
    `_log()` 写 `scores.jsonl` 失败时是裸 `pass` ⇒ 日志文件在位、**看着像完整评分史**，
    实际**静默少行**，下游任何趋势/统计都会安静地算错。

判据（两条都要有牙）：
  1. **结构**：`_log` 的 except 体不许只有一个 `pass`（用 AST 判结构事实，
     不用源码文本判 —— 避开本仓 FR-1 那条「提到 ≠ 用了」）；
  2. **行为**：写盘真失败时必须**留痕到 stderr**，且**仍然不抛**
     （评审打分不该因为日志写不进去就整个失败 —— 这是它原来吞异常的唯一正当理由，
      修的是"无声"，不是"吞"）。
"""
from __future__ import annotations

import ast
import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "brain" / "aesthetic_brain.py"


def _load():
    spec = importlib.util.spec_from_file_location("aesthetic_brain_under_test", TARGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AestheticBrainSilenceTest(unittest.TestCase):
    def test_log_except_body_is_not_a_bare_pass(self) -> None:
        tree = ast.parse(TARGET.read_text(encoding="utf-8", errors="replace"))
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_log"), None)
        self.assertIsNotNone(fn, "找不到 _log —— 改名了？")
        silent = []
        for node in ast.walk(fn):
            if isinstance(node, ast.ExceptHandler):
                body = [b for b in node.body
                        if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    silent.append(getattr(node, "lineno", None))
        self.assertEqual([], silent, "这些 except 体只有一个 pass（吞掉且不留字）：行 %s" % silent)

    def test_write_failure_leaves_a_line_and_does_not_raise(self) -> None:
        mod = _load()
        # 把落点指向一个**不可能是文件**的位置（目录）⇒ 打开必失败
        bad = Path(mod.LOG_FILE).parent / "scores.jsonl" / "nested"
        with mock.patch.object(mod, "LOG_FILE", bad):
            buf = io.StringIO()
            with redirect_stderr(buf):
                mod._log("probe", {"score": 1})       # 不许抛
            left = buf.getvalue()
        self.assertIn("评分没落盘", left, "写失败一个字都没留 —— FR-5 回归")
        self.assertIn("_log", left)

    def test_success_path_still_writes(self) -> None:
        import tempfile
        mod = _load()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "scores.jsonl"
            with mock.patch.object(mod, "LOG_FILE", p):
                mod._log("probe", {"score": 7})
            self.assertTrue(p.is_file(), "正常路径反而写不进去了")
            self.assertIn('"score": 7', p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
