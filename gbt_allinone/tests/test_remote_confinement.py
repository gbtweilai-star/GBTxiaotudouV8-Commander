# -*- coding: utf-8 -*-
"""执行者隔离 判据（主人 2026-10-09 点破：沙盒隔离了靶标，没隔离执行的人）。

锁四件事：
  ① **默认拒启**：未隔离 + 无票 ⇒ remote_start 必须被挡住（fail-closed），不许「先跑起来再说」；
  ② **两件事分开念**：confined_now（现在是否真隔离）≠ profiles_available（路在不在）；
  ③ **路要真验**：指定隔离档必须**验过能跑**才放行（WSL 里没 node、Docker 守护没起 ⇒ 不算）；
  ④ **门按 op 挂**：会起探针的读类也挂 process_execute（别把「只是看看」念成零作用域）。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone.security import policy  # noqa: E402
from gbt_allinone.tentacle import remote_confinement as RC  # noqa: E402


class RemoteConfinementTest(unittest.TestCase):

    def test_verdict_separates_now_from_available(self):
        v = RC.run("verdict")
        self.assertIn("confined_now", v)
        self.assertIn("profiles_available", v)
        self.assertIn("profiles_verified", v)
        self.assertIsInstance(v["confined_now"], bool)
        self.assertTrue(v["why"])

    def test_guard_refuses_without_the_owner_ticket(self):
        g = RC.guard_start()
        self.assertFalse(g["ok"])
        self.assertEqual(g["reason"], "needs_grant")
        self.assertEqual(g["scope"], "remote_device")
        self.assertIn("auth grant", g["how_to_grant"])

    def test_guard_refuses_when_unconfined(self):
        g = RC.guard_start(grant="owner-gave-it")
        self.assertFalse(g["ok"])
        self.assertEqual(g["reason"], "unconfined_refused")
        self.assertIn("宿主", str(g["why"]))
        self.assertTrue(g["enable"], "拒了必须给启用路径")

    def test_profile_must_be_verified_not_merely_present(self):
        g = RC.guard_start(grant="owner-gave-it", profile="docker")
        if g["ok"]:
            self.skipTest("本机 Docker 真的通了（守护在跑且能拉起 node），跳过")
        self.assertEqual(g["reason"], "profile_unverified")
        self.assertTrue(g["why"])

    def test_explicit_acknowledgement_is_recorded_not_hidden(self):
        g = RC.guard_start(grant="owner-gave-it", acknowledge_host_execution=True)
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["profile"], "host_acknowledged")
        self.assertIn("主人显式确认", g["note"])

    def test_remote_start_is_blocked_by_the_guard(self):
        """**最要紧的一条**：闸焊进了 launcher —— 未隔离无票时中继起不来。"""
        from gbt_allinone.tentacle import desktop_commander as DC
        r = DC.remote_start(wait=0)
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("blocked"), "必须是被闸挡住的，不是别的原因")
        self.assertIn((r.get("拒绝") or {}).get("reason"), ("needs_grant", "unconfined_refused"))

    def test_gate_scopes(self):
        for op in ("verdict", "assess", "guard", "weird"):
            d = policy.evaluate("remote_confinement", {"op": op})
            self.assertEqual(set(d.scopes), {"process_execute"}, "会起探针的 op 必须挂门：%s" % op)
        for op in ("ttl", "grant"):
            d = policy.evaluate("remote_confinement", {"op": op})
            self.assertEqual(set(d.scopes), set(), "纯读文件才是零作用域：%s" % op)


if __name__ == "__main__":
    unittest.main()
