# -*- coding: utf-8 -*-
"""全自动发布（tools/auto_publish.py）用例 —— 形状 + 六条带牙。

本文件最要紧的一条：**「全自动」不许被读成「连发布也不问」**。
"""
from __future__ import annotations

import unittest

from gbt_allinone.tools import auto_publish as ap


class AutoPublishTests(unittest.TestCase):
    def test_status_shape(self):
        st = ap.run("status")
        self.assertTrue(st["ok"], st)
        self.assertEqual(st["kind"], "auto_publish")
        self.assertEqual(st["domain"], "social")
        self.assertTrue(st["requires_external_key"])
        self.assertEqual(len(st["primitives"]), 5)
        self.assertEqual(len(st["red_lines"]), 6)

    def test_policy_boundary_is_written_down(self):
        # 「全自动」的边界必须写在纸上，而不是执行时临时拿主意
        p = ap.run("policy")
        self.assertEqual(p["auto_ok"], ["plan", "compose", "track", "settle_read"])
        self.assertEqual(p["needs_gate"], ["publish", "settle_withdraw", "price_change"])
        self.assertIn("全自动 = 除", str(p["one_line"]))

    def test_platforms_are_empty_not_invented(self):
        # 主人没给名单 ⇒ **一个平台名都不编**（未取证不引外部）
        r = ap.run("platforms")
        self.assertEqual(r["platforms"], [])
        self.assertIn("一个平台名都不编", str(r["note"]))
        self.assertEqual(ap.CURRENT["platforms_present"], 0)

    def test_gate_publish_default_is_denied(self):
        # 带牙①（最要紧）：默认 0 张令牌 ⇒ 发布一律拒
        d = ap.run("gate_publish", action="publish")
        self.assertFalse(d["ok"], d)
        self.assertEqual(d["rule"], "irreversible_needs_gate")
        self.assertEqual(d["token_given"], False)

    def test_gate_publish_confirm_or_ttl_token(self):
        # 带牙②：两种过门方式 —— 逐条确认 / 有 TTL 的令牌（缺 TTL 不算）
        one = ap.run("gate_publish", action="publish", confirmed=True)
        self.assertTrue(one["ok"], one)
        self.assertEqual(one["how"], "逐条确认")
        no_ttl = ap.run("gate_publish", action="publish", token="tok-1")
        self.assertFalse(no_ttl["ok"], no_ttl)
        self.assertEqual(no_ttl["rule"], "irreversible_needs_gate")
        with_ttl = ap.run("gate_publish", action="publish", token="tok-1",
                          ttl_seconds=600)
        self.assertTrue(with_ttl["ok"], with_ttl)
        self.assertEqual(with_ttl["how"], "有 TTL 的批量令牌")
        self.assertEqual(with_ttl["ttl_seconds"], 600.0)
        # 不扩大化：全自动允许的动作不必过门
        auto = ap.run("gate_publish", action="compose")
        self.assertTrue(auto["ok"], auto)
        self.assertFalse(auto["gated"])
        # 不在白名单 ⇒ 不许猜
        weird = ap.run("gate_publish", action="do_something")
        self.assertEqual(weird["rule"], "unknown_action")

    def test_gate_trace_and_key(self):
        # 带牙③：留痕 + 凭据不走明文
        self.assertEqual(ap.run("gate_trace")["rule"], "call_not_traced")
        self.assertEqual(ap.run("gate_trace", trace_ref="t-1",
                                source_kind="publish")["ok"], True)
        bad = ap.run("gate_key", payload={"cookie": "sk-abcd1234efgh5678ijkl"})
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "plaintext_key")

    def test_gate_accounts_one_account_one_ai(self):
        # 带牙④：一人一号 —— 共用账号必拒
        good = ap.run("gate_accounts", accounts=[
            {"account_id": "a1", "ai_id": "小土豆"},
            {"account_id": "a2", "ai_id": "小土豆"},
        ])
        self.assertTrue(good["ok"], good)
        bad = ap.run("gate_accounts", accounts=[
            {"account_id": "a1", "ai_id": "小土豆"},
            {"account_id": "a1", "ai_id": "别人"},
        ])
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "account_shared")
        na = ap.run("gate_accounts")
        self.assertTrue(na["ok"], na)

    def test_gate_withdraw_needs_auth(self):
        # 带牙⑤：收益只汇总不代提
        na = ap.run("gate_withdraw", action="settle_read")
        self.assertTrue(na["ok"], na)
        bad = ap.run("gate_withdraw", action="settle_withdraw")
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "withdraw_needs_auth")
        self.assertTrue(ap.run("gate_withdraw", action="settle_withdraw",
                               authorized=True)["ok"])

    def test_gate_metrics_no_fake_data(self):
        # 带牙⑥：数据可以难看，但不能是假的
        self.assertTrue(ap.run("gate_metrics", plan="按真实数据排期")["ok"])
        bad = ap.run("gate_metrics", plan="先买粉把数据刷上去")
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "fake_metrics")

    def test_publish_is_not_implemented(self):
        # 不假装能发：平台名单未给、凭据不在盘上
        for op in ("plan", "compose", "publish", "track", "settle"):
            r = ap.run(op)
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["rule"], "not_implemented")
            self.assertTrue(r["requires_external_key"])

    def test_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            ap.run("nope")


if __name__ == "__main__":
    unittest.main()
