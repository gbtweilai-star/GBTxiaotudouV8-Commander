# -*- coding: utf-8 -*-
"""R-H600 · ledger_note 三条带牙用例（+ 三条结构用例）。

口径：**用例要有牙** —— 不是断言「能跑」，是断言「闸真的会拒、拒了盘上不许变」。
"""
from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from gbt_allinone.tools import ledger_note as ln

SEED = "> **R-H001 补记（归口 + 登记）**：第一条\n"


class LedgerNoteTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "待落刀登记.md"
        self.path.write_text(SEED, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ── 牙①：禁半角双引号 ⇒ 拒，且**盘上一个字节都不许动** ──
    def test_gate_no_halfwidth_quote_keeps_file_untouched(self) -> None:
        before = self.path.read_bytes()
        with self.assertRaises(ln.LedgerNoteError) as ctx:
            ln.append_line("R-H002", "这里有个半角引号 " + chr(34) + "x" + chr(34),
                           path=self.path)
        self.assertEqual(ctx.exception.reason_code, "no_halfwidth_quote")
        self.assertEqual(self.path.read_bytes(), before)

    # ── 牙②：幂等 ⇒ 同 label 第二次拒，且文件只多了一个块 ──
    def test_gate_idempotent_writes_exactly_once(self) -> None:
        before = len(self.path.read_bytes())
        first = ln.append_line("R-H002", "第一次", path=self.path)
        self.assertTrue(first["ok"])
        after_first = len(self.path.read_bytes())
        self.assertGreater(after_first, before)
        with self.assertRaises(ln.LedgerNoteError) as ctx:
            ln.append_line("R-H002", "第二次", path=self.path)
        self.assertEqual(ctx.exception.reason_code, "idempotent")
        self.assertEqual(len(self.path.read_bytes()), after_first)

    # ── 牙③：缺前驱拒写 ⇒ after 不是当前最后一条 ⇒ 拒，且盘上不变 ──
    def test_gate_predecessor_required_refuses_out_of_order(self) -> None:
        before = self.path.read_bytes()
        with self.assertRaises(ln.LedgerNoteError) as ctx:
            ln.append_line("R-H003", "插队", after="R-H099", path=self.path)
        self.assertEqual(ctx.exception.reason_code, "predecessor_required")
        self.assertEqual(self.path.read_bytes(), before)

    # ── 只追加：目标末尾不是换行 ⇒ 拒写（不修、不补、不猜）──
    def test_gate_append_only_refuses_file_without_trailing_newline(self) -> None:
        self.path.write_text(SEED.rstrip("\n"), encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(ln.LedgerNoteError) as ctx:
            ln.append_line("R-H002", "接在没换行的文件后面", path=self.path)
        self.assertEqual(ctx.exception.reason_code, "append_only")
        self.assertEqual(self.path.read_bytes(), before)

    # ── 一刀一个物理行：写成功 ⇒ 只多一个物理行、行首形状对 ──
    def test_one_knife_is_one_physical_line(self) -> None:
        res = ln.append_line("R-H100", "正文", title="归口 + 登记", path=self.path)
        self.assertEqual(res["physical_lines"], 1)
        text = self.path.read_text(encoding="utf-8-sig")
        rows = [x for x in text.split("\n") if x.startswith("> **R-H100 补记")]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].startswith("> **R-H100 补记（归口 + 登记）**："))
        self.assertEqual(ln.rules(path=self.path)["last_label"], "R-H100")

    # ── 目标固定闸：能力位入口**没有 path 参数**；就算硬塞一个，也会被忽略 ──
    #    ⚠️ 这里只走**只读**的 preview，绝不调 run("append") —— 那会写进**真台账**。
    def test_run_never_forwards_a_caller_path(self) -> None:
        self.assertNotIn("path", inspect.signature(ln.run).parameters)
        res = ln.run("preview", label="R-H999", body="试试硬塞路径", path=str(self.path))
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["target"], str(ln.TARGET))
        self.assertNotEqual(res["target"], str(self.path))

    # ── 作用域闸（R-H620 改后的口径）：append 零作用域；**未列出的 op 仍 fail-closed** ──
    #    ⚠️ 这条只查 `policy.evaluate`（纯函数、只读）——**不调 run_task("append")**，
    #       那会往**真台账**写一行。
    def test_scope_append_is_zero_and_unknown_op_fails_closed(self) -> None:
        from gbt_allinone.security import policy as P
        for op in ("status", "rules", "preview", "append"):
            self.assertEqual(P.evaluate("ledger_note", {"op": op}).scopes, (),
                             "op=%s 应为零作用域" % op)
        for op in ("write", "delete", "remove", "chmod"):
            self.assertEqual(P.evaluate("ledger_note", {"op": op}).scopes,
                             ("filesystem_write",), "未列出的 op=%s 必须 fail-closed" % op)


if __name__ == "__main__":
    unittest.main(verbosity=2)
