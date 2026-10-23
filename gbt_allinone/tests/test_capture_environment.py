# -*- coding: utf-8 -*-
"""capture_environment · G3 死角收口用例（R-H203）。

① 失败时必返回**结构化否决**（不是裸异常、不是空返回）；
② 失败返回里带 `reason` 与 `next`（不是空）；
③ **静默失败 ⇒ 拒**（`assert_not_silent` 守卫）；
④ 成功路径不被这套出口污染（交互桌面时 `ok=True`、`next=None`）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tentacle import capture_environment as ce  # noqa: E402


class FailureExitTests(unittest.TestCase):
    def test_capacity_always_has_a_failure_exit(self):
        out = ce.capacity()
        self.assertIn("ok", out, "必须有可判定的 ok")
        self.assertIn("reason", out)
        self.assertIn("next", out)
        if out["ok"] is False:
            self.assertTrue(str(out["reason"]).strip(), "失败必须说清为什么")
            self.assertTrue(str(out["next"]).strip(), "失败必须说清下一步怎么办")
        self.assertTrue(ce.assert_not_silent(out, where="capacity")["ok"],
                        "capacity 的返回必须过静默失败守卫")

    def test_status_always_has_a_failure_exit(self):
        out = ce.status()
        for k in ("ok", "reason", "next", "capture_ready", "likely_failure_roots"):
            self.assertIn(k, out, "status 缺字段：" + k)
        if out["ok"] is False:
            self.assertTrue(str(out["reason"]).strip())
            self.assertTrue(str(out["next"]).strip())
        self.assertTrue(ce.assert_not_silent(out, where="status")["ok"])

    def test_silent_failure_is_refused(self):
        bad = ce.assert_not_silent({"ok": False, "reason": "non_interactive_desktop"},
                                   where="poisoned")
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "silent_failure")
        self.assertIn("next", bad["missing"])
        only_next = ce.assert_not_silent({"ok": False, "next": "换个通道"}, where="poisoned")
        self.assertIn("reason", only_next["missing"])
        good = ce.assert_not_silent({"ok": False, "reason": "r", "next": "n"})
        self.assertTrue(good["ok"], "reason+next 齐 ⇒ 不算静默失败")


if __name__ == "__main__":
    unittest.main()
