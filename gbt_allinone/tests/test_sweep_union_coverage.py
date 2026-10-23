r"""「四批并集覆盖」这把尺子自己的判据（第 55 轮）。

立它的理由：第 51 轮我把全仓拆成四批跑，然后把四批的数字**并排一放**就说全仓看过了 ——
而批与批之间我还在往仓里加测试文件（124 → 125 → 126），**四批的"全 N 个"根本不是同一个 N**。
那一轮的真实覆盖是 62/125 而不是"全都跑了"。

所以这条判据守的是：**并集必须现算，且不许在缺文件时报满覆盖。**
副带守一条更细的：某批 `fails` 是空的时候，红色的**存在**仍须被报出来
（写「未记到用例名」），不许因为"说不出名字"就当它没有 ——
这正是本轮我踩过的坑：名字其实印了，是我自己的过滤器丢了它。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "sweep-union-coverage.py"


def _load():
    spec = importlib.util.spec_from_file_location("sweep_union_coverage", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


class UnionCoverageTest(unittest.TestCase):
    """判据本体：现算并集 · 缺文件必须红 · 跨批红必须并起来。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sweep_union_"))
        tests = self.tmp / "gbt_allinone" / "tests"
        tests.mkdir(parents=True)
        for n in ("test_a.py", "test_b.py", "test_c.py", "test_d.py"):
            (tests / n).write_text("# 空壳\n", encoding="utf-8")
        self.out = self.tmp / "output" / "blueprint-audit"
        self.out.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _batch(self, i: int, rows: list) -> None:
        (self.out / ("2026-09-26-满仓横扫-第%d批.json" % i)).write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def _run(self) -> tuple:
        """把被测工具指向临时仓：它靠模块级 ROOT/OUT 定位，替换后调用。"""
        old_root, old_out = MOD.ROOT, MOD.OUT
        MOD.ROOT, MOD.OUT = self.tmp, self.out
        try:
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = MOD.main()
            return rc, buf.getvalue()
        finally:
            MOD.ROOT, MOD.OUT = old_root, old_out

    def test_full_union_is_green(self) -> None:
        self._batch(1, [{"file": "test_a.py", "result": "OK", "fails": []},
                        {"file": "test_b.py", "result": "OK", "fails": []}])
        self._batch(2, [{"file": "test_c.py", "result": "OK", "fails": []},
                        {"file": "test_d.py", "result": "OK", "fails": []}])
        rc, out = self._run()
        self.assertEqual(0, rc, out)
        self.assertIn("100.0%", out)
        self.assertIn("每一个测试文件都至少进过一批", out)

    def test_missing_file_is_red_and_named(self) -> None:
        """**反空洞**：只跑了 3 个、仓里有 4 个 ⇒ 必须红，且点名缺谁。"""
        self._batch(1, [{"file": "test_a.py", "result": "OK", "fails": []},
                        {"file": "test_b.py", "result": "OK", "fails": []}])
        self._batch(2, [{"file": "test_c.py", "result": "OK", "fails": []}])
        rc, out = self._run()
        self.assertEqual(1, rc, out)
        self.assertIn("test_d.py", out)
        self.assertNotIn("100.0%", out)

    def test_no_batch_files_at_all_is_not_green(self) -> None:
        rc, out = self._run()
        self.assertEqual(2, rc, out)
        self.assertIn("一份批次 JSON 都没有", out)

    def test_red_wins_over_ok_across_batches(self) -> None:
        """同一个文件在批 1 绿、批 2 红 ⇒ 并集里必须是**红**（不许"后一次覆盖前一次"）。"""
        self._batch(1, [{"file": "test_a.py", "result": "OK", "fails": []},
                        {"file": "test_b.py", "result": "OK", "fails": []},
                        {"file": "test_c.py", "result": "OK", "fails": []},
                        {"file": "test_d.py", "result": "OK", "fails": []}])
        self._batch(2, [{"file": "test_a.py", "result": "FAILED", "fails": ["test_boom"]}])
        rc, out = self._run()
        self.assertEqual(0, rc, out)          # 覆盖是全的
        self.assertIn("test_a.py :: test_boom", out)
        self.assertIn("红集（跨四批去重）：1 条", out)

    def test_nameless_red_is_still_reported(self) -> None:
        """`fails` 为空时**不许把红吞掉** —— 要写「未记到用例名」。"""
        self._batch(1, [{"file": "test_a.py", "result": "FAILED", "fails": []},
                        {"file": "test_b.py", "result": "OK", "fails": []},
                        {"file": "test_c.py", "result": "OK", "fails": []},
                        {"file": "test_d.py", "result": "OK", "fails": []}])
        rc, out = self._run()
        self.assertIn("test_a.py :: (未记到用例名)", out)
        self.assertIn("红集（跨四批去重）：1 条", out)

    def test_timeout_is_not_counted_as_red(self) -> None:
        """超时 = 本次无法判定，**不等于红**（本仓既有口径）。"""
        self._batch(1, [{"file": "test_a.py", "result": "TIMEOUT", "fails": []},
                        {"file": "test_b.py", "result": "OK", "fails": []},
                        {"file": "test_c.py", "result": "OK", "fails": []},
                        {"file": "test_d.py", "result": "OK", "fails": []}])
        rc, out = self._run()
        self.assertIn("超时（**本次无法判定**，不等于红）：test_a.py", out)
        self.assertIn("红集（跨四批去重）：0 条", out)


class SelfDisciplineTest(unittest.TestCase):
    """这条工具自己也要守本仓的口径。"""

    def test_it_says_batched_green_is_not_the_same(self) -> None:
        src = TOOL.read_text(encoding="utf-8")
        self.assertIn("分批绿 ≠ 一次全量的绿", src,
                      "结论里必须写明这条 —— 否则分批跑会被当成「全量绿」")

    def test_it_explains_why_union_must_be_recomputed(self) -> None:
        src = TOOL.read_text(encoding="utf-8")
        self.assertIn("124 → 125 → 126", src,
                      "得把「四批的 N 不是同一个 N」这件事写在文件里")

    def test_boot_selfcheck_names_it(self) -> None:
        """点名要**点模块名**，不点标签文案 —— 标签是可以随手改的散文。"""
        boot = (ROOT / "tools" / "codex-scripts" / "boot-selfcheck.py").read_text(encoding="utf-8")
        self.assertIn("test_sweep_union_coverage", boot,
                      "开机自检没点名这条 ⇒ 覆盖口径又只靠我记着")


if __name__ == "__main__":
    unittest.main()
