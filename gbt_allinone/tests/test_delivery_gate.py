# -*- coding: utf-8 -*-
"""交付闸 判据（主人令 2026-10-09：「每一个能力必须单独跑通闭环才能交付，要不然我直接丢垃圾桶」）。

锁四件事：
  ① **逐位判定**：读最近一次全量扫账，247 位一位一条结论，**不报合计**；
  ② **禁交付是真禁**：要参数/缺依赖/真坏/未扫 ⇒ 可交付=False（不是"提示一下"）；
  ③ **登记才放行**：参数型输入口必须在 DECLARED_NEEDPARAM 里**显式登记**才放行；
     没登记的「要参数」照旧禁交付；
  ④ **硬闸会拒**：gate(不可交付的位) ⇒ ok=False。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 🔴 仓约定（照 test_framework.py:11-16）：**先设隔离 store 再导入被测模块** ——
#    否则仓里的保护闸会拒（"拒绝在绑定：真 store，改的就是真（成品）测试"）。
#    我原来四个判据文件都没设 ⇒ 体检里用 pytest 跑时全部 rc=2（实测撞了）。
os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_test_store_"))

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import delivery_gate as DG  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


class DeliveryGateTest(unittest.TestCase):

    def test_status_counts_every_position(self):
        r = DG.run("status")
        self.assertTrue(r["ok"], r)
        self.assertGreaterEqual(r["总位"], 200, "能力位应该 200+")
        # 口径（2026-10-09 统一）：**可交付 = 总数**（含带缺票说明），细分另列；
        # 四细分之和必须等于总位（不许丢件）。
        self.assertEqual(r["可交付"] + r["禁交付"], r["总位"], "可交付+禁交付 必须等于总位")
        self.assertEqual(r["其中_闭环直通"] + r["其中_已登记放行"] + r["其中_带缺票说明"]
                         + r["禁交付"], r["总位"], "四细分之和必须等于总位（不许丢件）")
        a = DG.run("audit")
        self.assertEqual((r["可交付"], r["禁交付"]), (a["可交付"], a["禁交付"]),
                         "status 与 audit 必须同口径（两处说法不一致 = 本仓最恨的错）")

    def test_blocked_is_really_blocked(self):
        r = DG.run("audit")
        bad = [x for x in r["禁交付逐条"] if x["档"] in ("真坏", "超时")]
        self.assertEqual(bad, [], "真坏/超时一条都不许有：%s" % bad)
        for x in r["禁交付逐条"]:
            self.assertIn(x["档"], ("要参数", "缺依赖", "真坏", "未扫"), x)

    def test_declared_needparam_lets_through(self):
        self.assertTrue(DG.DECLARED_NEEDPARAM, "登记表不许是空的（空表=没设计）")
        for kind, why in list(DG.DECLARED_NEEDPARAM.items())[:3]:
            self.assertTrue(why.strip(), "%s 登记了但没写理由" % kind)
        # 造一个**没登记**的「要参数」位 ⇒ 必须仍然禁交付
        real = dict(DG.DECLARED_NEEDPARAM)
        try:
            DG.DECLARED_NEEDPARAM.clear()
            r = DG.deliverable("browser")
            self.assertFalse(r["可交付"], "没登记的『要参数』必须禁交付")
        finally:
            DG.DECLARED_NEEDPARAM.update(real)

    def test_declared_dependency_is_not_a_silent_bypass(self):
        """「已登记·主人侧依赖」必须**逐条带出处**，且**没登记的不许放行**（防成后门）。"""
        self.assertTrue(DG.DECLARED_DEPENDENCY, "登记表不许空（空表=没设计）")
        for kind, why in DG.DECLARED_DEPENDENCY.items():
            self.assertTrue(str(why).strip(), "%s 登记了但没写理由" % kind)
            self.assertIn("出处", str(why), "%s 的登记必须带出处（可复核）" % kind)
        # 造一个**没登记**的「缺依赖」⇒ 必须仍然禁交付
        real = dict(DG.DECLARED_DEPENDENCY)
        realv = DG.verdict_of
        try:
            DG.DECLARED_DEPENDENCY.clear()
            DG.verdict_of = lambda k: {"kind": k, "verdict": "缺依赖", "reason": "假造"}
            r = DG.deliverable("coze_mail")
            self.assertFalse(r["可交付"], "没登记的『缺依赖』必须禁交付")
        finally:
            DG.DECLARED_DEPENDENCY.update(real)
            DG.verdict_of = realv

    def test_gate_is_hard(self):
        r = DG.run("gate", kind="__没有这个能力位__")
        self.assertFalse(r["ok"], "不存在的位必须拒")
        self.assertEqual(r["档"], "未扫")

    def test_gate_scopes(self):
        for op in ("status", "gate"):
            self.assertEqual(set(policy.evaluate("delivery_gate", {"op": op}).scopes), set(),
                             "%s 是纯读账，应零作用域" % op)
        for op in ("check", "audit", "weird"):
            self.assertEqual(set(policy.evaluate("delivery_gate", {"op": op}).scopes),
                             {"process_execute"}, "%s 会起子进程，要挂门" % op)


if __name__ == "__main__":
    unittest.main()
