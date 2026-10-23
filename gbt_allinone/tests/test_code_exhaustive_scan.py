"""`gbt_allinone/tools/code_exhaustive_scan.py` 的判据（2026-09-23 第 55 轮立）。

═══ 为什么轮到它 ═══
第 50 轮普查：`gbt_allinone/tools/` 80 个工具里 **21 个一条判据都没有**，
它是其中之一，而且是**我这一路引用过读数的那一个**
（`assert_in_prod 389→1` · `commented_code 12→2` 都出自它）。
**被引用的读数必须有东西守着**，否则那不是证据，是我的话。

═══ 它自己已经有一条很硬的判据（我要把它钉住，而不是重写）═══
`run()` 的返回值里有 `coverage.closed`：

    closed = (files_scanned + files_failed) == files_kept

—— 这是**分母闭合**：**每一个被留下的文件，要么被扫了、要么被记了失败原因**，
不许有第三种下场（悄悄消失）。这条判据本身就是本会话反复在打的东西，值得单独钉。

═══ 判据要钉住的四件事 ═══
① **分母闭合**（`closed` 为真，且分量对得上）；
② **正对照**：种一个已知靶子（`# TODO:`）必须被抓到、且带文件名；
③ **负对照**：干净文件不许被误伤；
④ **`LIVE_ONLY` 的语义**：`print(...)` 在活代码里要报、在 `tests/` 里**不报**
   （这条是第 44 轮修出来的语义，最容易在后续改动里被弄丢）。
另加两条诚实性判据：BOM 必须被报；**读不了的文件必须落进 `failed`，不许悄悄消失**。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from gbt_allinone.tools import code_exhaustive_scan as ces  # noqa: E402


def _mk(root: Path, name: str, text: str, *, bom: bool = False) -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    p.write_bytes((b"\xef\xbb\xbf" + data) if bom else data)
    return p


def _checks_for(rep: dict, rel: str) -> set:
    return {f["check"] for f in rep["findings"] if f["file"].replace("\\", "/") == rel}


class TestDenominatorIsClosed(unittest.TestCase):
    def test_every_kept_file_is_either_scanned_or_failed(self):
        """**分母闭合**：留下的文件 = 扫过的 + 失败的（不许有第三种下场）。"""
        with tempfile.TemporaryDirectory(prefix="gbt_ces_") as d:
            d = Path(d)
            _mk(d, "a.py", "x = 1\n")
            _mk(d, "sub/b.py", "y = 2\n")
            _mk(d, "readme.md", "# 一\n")
            rep = ces.run(d)
        c = rep["coverage"]
        self.assertEqual(c["files_scanned"] + c["files_failed"], c["files_kept"],
                         "分母不闭合：%s" % c)
        self.assertTrue(c["closed"], "`closed` 字段与分量对不上：%s" % c)
        self.assertEqual(c["files_scanned"], 3, "三个可扫文件应当都被扫到：%s" % c)
        self.assertEqual(c["files_failed"], 0)

    def test_unreadable_file_lands_in_failed_not_vanishes(self):
        """读不来的文件**必须落进 `failed`**（附原因），而且**分母照样闭合**。

        "读不了"是**未知**，不是"没问题" —— 悄悄跳过它，`closed` 就会变成一句空话。
        """
        with tempfile.TemporaryDirectory(prefix="gbt_ces_") as d:
            d = Path(d)
            _mk(d, "ok.py", "x = 1\n")
            _mk(d, "locked.py", "y = 2\n")
            real = Path.read_bytes

            def fake(self):
                if self.name == "locked.py":
                    raise PermissionError(13, "denied by judge")
                return real(self)

            with mock.patch.object(Path, "read_bytes", fake):
                rep = ces.run(d)
        c = rep["coverage"]
        self.assertEqual([f["file"].replace("\\", "/") for f in rep["failed"]], ["locked.py"],
                         "读不来的文件没进 failed：%s" % rep["failed"])
        self.assertTrue(c["closed"], "有文件读不来时分母就不闭合了：%s" % c)
        self.assertTrue(rep["failed"][0].get("why"), "failed 条目没写原因")


class TestPositiveAndNegativeControls(unittest.TestCase):
    def test_todo_debt_is_caught_and_named(self):
        """正对照：种一个 `# TODO:` 必须被抓到，并**指出是哪个文件**。"""
        with tempfile.TemporaryDirectory(prefix="gbt_ces_") as d:
            d = Path(d)
            _mk(d, "pkg/clean.py", "def f():\n    return 1\n")
            _mk(d, "pkg/debt.py", "def g():\n    # TODO: 以后再说\n    return 2\n")
            rep = ces.run(d)
        self.assertIn("todo_fixme", _checks_for(rep, "pkg/debt.py"),
                      "种了 TODO 却没报 todo_fixme：%s" % rep["by_check"])
        self.assertNotIn("todo_fixme", _checks_for(rep, "pkg/clean.py"),
                         "干净文件被误伤成 todo_fixme")

    def test_clean_tree_reports_no_findings(self):
        """负对照：一棵干净树 ⇒ 0 条命中（否则这条判据只会往一个方向咬）。"""
        with tempfile.TemporaryDirectory(prefix="gbt_ces_") as d:
            d = Path(d)
            _mk(d, "pkg/a.py", "def f():\n    return 1\n")
            _mk(d, "pkg/b.py", "VALUE = 2\n")
            rep = ces.run(d)
        self.assertEqual(rep["findings_total"], 0,
                         "干净树被误伤：%s" % rep["by_check"])


class TestLiveOnlyScope(unittest.TestCase):
    """`LIVE_ONLY` 的语义（第 44 轮修出来的，最容易在后续改动里弄丢）。"""

    def test_print_is_flagged_in_live_code_but_not_in_tests(self):
        with tempfile.TemporaryDirectory(prefix="gbt_ces_") as d:
            d = Path(d)
            _mk(d, "pkg/live.py", 'def f():\n    print("debug")\n    return 1\n')
            _mk(d, "tests/test_thing.py", 'def test_x():\n    print("debug")\n')
            rep = ces.run(d)
        self.assertIn("print_debug", _checks_for(rep, "pkg/live.py"),
                      "活代码里的 print 没被报：%s" % rep["by_check"])
        self.assertNotIn("print_debug", _checks_for(rep, "tests/test_thing.py"),
                         "`LIVE_ONLY` 失效了：测试里的 print 也被咬 —— 那会制造大量假阳性")


class TestBomIsReported(unittest.TestCase):
    def test_bom_is_a_finding(self):
        """带 BOM 的文件必须被报（踩过的坑：`caps_registry.py` 带 BOM 绊倒过静态分析）。"""
        with tempfile.TemporaryDirectory(prefix="gbt_ces_") as d:
            d = Path(d)
            _mk(d, "pkg/bom.py", "x = 1\n", bom=True)
            rep = ces.run(d)
        self.assertIn("bom", _checks_for(rep, "pkg/bom.py"), "BOM 没被报：%s" % rep["by_check"])


if __name__ == "__main__":
    unittest.main()
