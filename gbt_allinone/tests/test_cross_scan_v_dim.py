"""R-H619（2026-09-25）· **cross_scan 的 V 维（视图对账）**的判据。

背景：`cross_scan` 的文档写着「十个交叉维度」，而第 41 轮现读确认 **D/E/F/V 四个
只出现在维度声明里、全文件没有第二处引用** —— 声称 10 维、实际只有 6 维能产出发现。
本轮把 **V** 真做出来（`_v_dim()`），D/E/F 仍如实留在 `dims_unimplemented` 里
（第 41 轮量过：它们的参考集还不存在，不许凭感觉挑一个来源当判据）。

V 维的两条判据（**都要能机检**）：
  ① 异物必须清零（`foreign > 0` ⇒ 有该处置的遗漏）；
  ② **双视图要算得平**：`你看到的（家根总项）` == 六类之和 ——
     只读一个数字不叫对账，**加减法要闭合**。

🔴 **本文件最要紧的一条是安全红线**：`inventory.scan(fix=True)` 会**真删文件**。
   扫描器里绝不许带清理动作 —— 所以这里**用桩记录 kwargs**，直接断言它传的是 `fix=False`。
   这条判据的存在理由就是「**扫一下**不该改动任何东西」。
"""
from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import cross_scan  # noqa: E402


def _stub(seen=0, by_class=None, foreign=0):
    by_class = by_class if by_class is not None else {"framework": [], "environment": []}
    return lambda **kw: {
        "dual_view": {"你看到的（家根总项）": seen, "异物（foreign）": foreign},
        "items": by_class, "fixed": [],
    }


class SafetyTest(unittest.TestCase):
    """安全红线：扫描器**只读**。"""

    def test_inventory_is_called_with_fix_false(self) -> None:
        got = {}

        def rec(**kw):
            got.update(kw)
            return {"dual_view": {"你看到的（家根总项）": 0, "异物（foreign）": 0}, "items": {}, "fixed": []}

        cross_scan._v_dim(check_inventory=rec)
        self.assertEqual({"fix": False}, got,
                         "V 维没有明确传 fix=False ⇒ 一旦默认值变了就会**在扫描时删文件**")
        self.assertIs(False, got["fix"], "fix 必须是布尔 False，不许是 0/None 之类的『假值』")

    def test_source_pins_the_readonly_call(self) -> None:
        """源码级复核：**判代码，不判文字**。

        ⚠️ 第一版这里写的是 `assertNotIn("fix=True", src)`，当场被自己的 docstring 判红 ——
        我在解释危险时写了「`inventory.scan(fix=True)` 会真删文件」，那是**提到**，不是**调用**。
        这正是本仓那句「提到 ≠ 用了」的又一次现形（这次栽在我自己的用例上）。
        ⇒ 改成用 **AST 找真正的调用**：扫全部 `Call` 节点里有没有 `fix=True`。
        """
        import ast as _ast

        src = (ROOT / "gbt_allinone" / "cross_scan.py").read_text(encoding="utf-8")
        tree = _ast.parse(src)
        calls_true, calls_false = [], []
        for node in _ast.walk(tree):
            if not isinstance(node, _ast.Call):
                continue
            for kw in node.keywords or []:
                if kw.arg != "fix":
                    continue
                val = kw.value
                target = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if isinstance(val, _ast.Constant) and val.value is True:
                    calls_true.append((target, node.lineno))
                elif isinstance(val, _ast.Constant) and val.value is False:
                    calls_false.append((target, node.lineno))
        self.assertEqual([], calls_true,
                         "代码里真的出现了 fix=True 调用（会在扫描中删文件）：%s" % calls_true)
        self.assertTrue(calls_false, "只读调用（fix=False）在代码里找不到 ⇒ 判据失效了")


class ReconciliationTest(unittest.TestCase):
    """两条判据 + 负控。"""

    def test_balanced_and_clean_yields_no_finding(self) -> None:
        f, st = cross_scan._v_dim(check_inventory=_stub(
            seen=3, by_class={"framework": [1], "environment": [1, 2], "foreign": []}, foreign=0))
        self.assertEqual([], f)
        self.assertTrue(st["balanced"])

    def test_unbalanced_dual_view_is_caught(self) -> None:
        """**负控**：家根总项 ≠ 六类之和 ⇒ 必须报（这才是『对账』而不是『读数』）。"""
        f, st = cross_scan._v_dim(check_inventory=_stub(
            seen=100, by_class={"framework": [1], "environment": [1, 2], "foreign": []}, foreign=0))
        self.assertFalse(st["balanced"])
        self.assertTrue(any("双视图对不上" in x["issue"] for x in f), f)
        self.assertTrue(all(x["dim"] == "V" for x in f))

    def test_foreign_not_zero_is_caught(self) -> None:
        """**负控**：有异物 ⇒ 必须报。"""
        f, _st = cross_scan._v_dim(check_inventory=_stub(
            seen=3, by_class={"framework": [1], "foreign": [1, 2], "environment": []}, foreign=2))
        self.assertTrue(any("异物未清零" in x["issue"] for x in f), f)

    def test_broken_inventory_reports_instead_of_crashing(self) -> None:
        """探针自己坏了 ⇒ 出一条 V finding，**不许把整轮扫描弄崩**。"""
        def boom(**kw):
            raise RuntimeError("桩：模拟 inventory 坏掉")

        f, st = cross_scan._v_dim(check_inventory=boom)
        self.assertTrue(any("跑不动" in x["issue"] for x in f), f)
        self.assertFalse(st["ran"], "坏掉时 ran 必须是 False（不许假装跑过）")


class DimsBookkeepingTest(unittest.TestCase):
    """口径：**声称覆盖必须等于实际覆盖**。

    整轮 `cross_scan.scan(deep=False)` 要 ~15 秒 ⇒ 这里**只跑一次**给两条用例共用
    （每条各跑一次就是 30 秒，而判的东西完全一样 —— 那是白烧时间）。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.b = cross_scan.scan(deep=False)

    def test_v_is_implemented_and_dfe_stay_honest(self) -> None:
        b = self.b
        self.assertIn("V", b["dims_implemented"], "V 已实现却没进 dims_implemented")
        self.assertIn("V", b["dims"])
        self.assertNotIn("V", b["dims_unimplemented"])
        # D/E/F 仍如实留"只有名字"（参考集不存在，见台账 F5/F12）
        self.assertEqual(["D", "E", "F"], sorted(b["dims_unimplemented"]))
        for d in ("D", "E", "F"):
            self.assertNotIn(d, b["dims_implemented"], "%s 没实现却混进了已实现名单" % d)

    def test_v_view_is_reported_so_a_human_can_recheck_the_arithmetic(self) -> None:
        v = self.b.get("v_view") or {}
        self.assertTrue(v.get("ran"), "V 维的原始读数没印出来 ⇒ 人无法自己复算那笔加减法")
        self.assertEqual(v["sum_by_class"], sum(v["by_class"].values()), "印出来的六类之和与明细不符")
        self.assertEqual(v["balanced"], v["seen"] == v["sum_by_class"])


if __name__ == "__main__":
    unittest.main()
