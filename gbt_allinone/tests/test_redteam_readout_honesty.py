"""R-H603（2026-09-25）· 红队模块两条**机检命中**的回归用例。

两条都不是我推的，是 `python -m gbt_allinone.tools.false_report_audit` 抓出来的：
  · **FR-8** `screen_sniff(action="list")`：`count` 报**盘上全量**，`captures` 只回**最近 60 条**，
    而返回体里**没有**"被截了"这件事的名字 ⇒ 读的人以为拿到的是全部采集。
  · **FR-5** `redteam._record_input` 的兜底分支：连"写不进错误记录"这件事本身都 `pass` 掉
    ⇒ 记录文件在位、看着像完整会话日志，**分不清"这段没有输入"和"这段写盘一直在失败"**。

判据（为什么这么写）：
  · FR-8 用**真行为**验（造 65 个假采集 → count/show/truncated 三件套必须自洽）；
  · FR-5 用 **AST** 验（`本仓`的 FR-1 教训：「提到 ≠ 用了」，所以不拿源码文本判；
    这里判的是"那个 except 体是不是只有一个 pass"这个**结构事实**）。
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest import mock

from gbt_allinone.security import redteam as RT

REDTEAM_PY = Path(RT.__file__)


class ScreenSniffCoverageTest(unittest.TestCase):
    """FR-8：分母/分子必须自洽，且"被截了"要有名字。"""

    def _fake_dir(self, n: int, tmp: Path) -> Path:
        tmp.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (tmp / ("cap-%03d.png" % i)).write_bytes(b"\x89PNG\r\n\x1a\n")
        return tmp

    def test_not_truncated_when_fewer_than_60(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            d = self._fake_dir(3, Path(td) / "screen")
            with mock.patch.object(RT, "_SCREEN_DIR", d):
                res = RT.screen_sniff(action="list")
        self.assertEqual(res["count"], 3)
        self.assertEqual(res["shown"], 3)
        self.assertFalse(res["truncated"])
        self.assertEqual(len(res["captures"]), res["shown"])

    def test_truncated_is_named_when_over_60(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            d = self._fake_dir(65, Path(td) / "screen")
            with mock.patch.object(RT, "_SCREEN_DIR", d):
                res = RT.screen_sniff(action="list")
        self.assertEqual(res["count"], 65, "分母应当是盘上全量")
        self.assertEqual(res["shown"], 60, "分子应当是本次真正返回的条数")
        self.assertTrue(res["truncated"], "65 > 60 却没报被截 —— 读数在骗人")
        self.assertEqual(len(res["captures"]), res["shown"],
                         "len(captures) 与 shown 对不上 ⇒ 口径字段是假的")


class RecorderSilenceTest(unittest.TestCase):
    """FR-5：记录器的兜底分支不许是"只有一个 pass"（那等于无声）。"""

    def _fn(self, name: str):
        tree = ast.parse(REDTEAM_PY.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        return None

    def test_record_input_has_no_silent_pass_handler(self) -> None:
        fn = self._fn("_record_input")
        self.assertIsNotNone(fn, "找不到 _record_input —— 红队记录器改名了？")
        silent = []
        for node in ast.walk(fn):
            if isinstance(node, ast.ExceptHandler):
                body = [b for b in node.body
                        if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    silent.append(getattr(node, "lineno", None))
        self.assertEqual([], silent,
                         "这些 except 体只有一个 pass（吞掉且不留字）：行 %s" % silent)

    def test_start_reports_where_recorder_stderr_goes(self) -> None:
        """`start` 的返回体必须说清"写盘失败去哪儿看" —— 否则又回到无处可查。

        这里只验**键存在**（真启动子进程会留一个记录器，属副作用，不在单测里做）。
        """
        src = REDTEAM_PY.read_text(encoding="utf-8", errors="replace")
        self.assertIn("stderr_log", src)
        self.assertNotIn("stderr=subprocess.DEVNULL", src,
                         "又把子进程 stderr 丢进 DEVNULL 了 —— FR-5 回归")


if __name__ == "__main__":
    unittest.main(verbosity=2)
