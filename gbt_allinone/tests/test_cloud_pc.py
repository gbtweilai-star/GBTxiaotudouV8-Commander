# -*- coding: utf-8 -*-
"""云电脑独立窗口（tools/cloud_pc.py）用例 —— 形状 + 五条带牙。"""
from __future__ import annotations

import unittest

from gbt_allinone.tools import cloud_pc as cp


class CloudPcTests(unittest.TestCase):
    def test_status_shape(self):
        st = cp.run("status")
        self.assertTrue(st["ok"], st)
        self.assertEqual(st["kind"], "cloud_pc")
        self.assertEqual(st["domain"], "infra")
        self.assertTrue(st["requires_external_key"])
        self.assertFalse(st["key_present"])
        self.assertEqual(len(st["primitives"]), 5)
        self.assertEqual(len(st["red_lines"]), 5)

    def test_window_is_card_not_iframe(self):
        # 形态：面板卡 · 独立窗口；**不是 iframe 嵌网页**
        w = cp.run("window")["window"]
        self.assertIn("独立窗口", str(w["form"]))
        self.assertIn("不是 iframe", str(w["not_iframe"]))
        self.assertEqual(w["source_of_truth"], "local")
        self.assertIn("触手", str(w["buttons_go_through"]))

    def test_primitives_flag_money_and_irreversible(self):
        # 谁花钱、谁不可逆，必须逐个标出来（不标就会被当成「都一样」）
        pr = {p["key"]: p for p in cp.run("primitives")["primitives"]}
        self.assertTrue(pr["PROVISION"]["costs_money"])
        self.assertFalse(pr["PROVISION"]["reversible"])
        self.assertTrue(pr["PROVISION"]["needs_gate"])
        self.assertFalse(pr["RELEASE"]["reversible"])
        self.assertTrue(pr["RELEASE"]["needs_gate"])
        self.assertTrue(pr["STATUS"]["reversible"])
        self.assertFalse(pr["STATUS"]["needs_gate"])
        self.assertFalse(pr["CONNECT"]["needs_gate"])

    def test_gate_key_rejects_plaintext(self):
        # 带牙①：云凭据不许进返回值
        ok = cp.run("gate_key", payload={"note": "连接串已入库"})
        self.assertTrue(ok["ok"], ok)
        bad = cp.run("gate_key", payload={"Authorization": "Bearer sk-abcd1234efgh5678ijkl"})
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "plaintext_key")
        self.assertTrue(str(bad["masked"]).endswith("****"))

    def test_gate_budget_requires_both_readings(self):
        # 带牙②：**先算账再花钱** —— 预算与账单两读数缺一不可
        miss = cp.run("gate_budget", budget="每月 200 元", action="provision")
        self.assertFalse(miss["ok"], miss)
        self.assertEqual(miss["rule"], "budget_bill_missing")
        self.assertEqual(miss["missing"], ["bill"])
        both = cp.run("gate_budget", budget="每月 200 元", bill="本月已用 0 元",
                      action="release")
        self.assertTrue(both["ok"], both)
        # 不扩大化：只读动作不适用本闸
        na = cp.run("gate_budget", action="connect")
        self.assertTrue(na["ok"], na)
        self.assertIn("不适用", str(na["note"]))

    def test_gate_trace_requires_source_kind(self):
        # 带牙③：无痕即未发生 + source_kind 必须对
        self.assertEqual(cp.run("gate_trace")["rule"], "call_not_traced")
        wrong = cp.run("gate_trace", trace_ref="t-1", source_kind="cloud")
        self.assertFalse(wrong["ok"], wrong)
        self.assertEqual(wrong["rule"], "bad_source_kind")
        self.assertEqual(wrong["expected"], "cloud_pc")
        right = cp.run("gate_trace", trace_ref="t-1", source_kind="cloud_pc")
        self.assertTrue(right["ok"], right)

    def test_gate_official_rejects_self_built_request(self):
        # 红线④：自己拼 HTTP 请求 = 绕官方入口
        self.assertEqual(cp.run("gate_official")["rule"], "official_entry_missing")
        bad = cp.run("gate_official", entry="http post /v1/instances")
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "self_built_request")
        self.assertTrue(cp.run("gate_official", entry="cli:official")["ok"])
        self.assertTrue(cp.run("gate_official", entry="sdk:official")["ok"])

    def test_gate_identity_write_on_cloud_rejected(self):
        # 红线⑤：她住在云上，身份源仍在本地 —— 云端不许带身份改写
        ok = cp.run("gate_identity", payload={"task": "渲染一条 8 秒片子"})
        self.assertTrue(ok["ok"], ok)
        bad = cp.run("gate_identity", payload={"task": "覆盖云端身份内核"})
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "identity_write_on_cloud")

    def test_provision_is_not_implemented(self):
        # 不假装能开通：本地无凭据 ⇒ 一律 not_implemented + requires_external_key
        for op in ("provision", "connect", "snapshot", "release"):
            r = cp.run(op)
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["rule"], "not_implemented")
            self.assertTrue(r["requires_external_key"])

    def test_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            cp.run("nope")


if __name__ == "__main__":
    unittest.main()
