# -*- coding: utf-8 -*-
"""GBT万能插（动态接口融合层）判据测试。

守四条不变量：
  ① 识别 + 自动生成接口（classify → descriptor.ops）
  ② 落盘持久化（ports.json，重启还在）
  ③ 门不绕（invoke 转 omni_plug / mcp_call，policy 现场判类）
  ④ 如实报缺（未接执行器标 not_wired，不冒充可调用）
  ⑤ 融入触手（bridge.is_capability + call_capability 能调到）
"""
import unittest

from gbt_allinone import universal_plug as UP


class TestUniversalPlug(unittest.TestCase):
    def setUp(self):
        # 每个用例清空端口表，避免相互污染
        for p in list(UP._load().keys()):
            UP.unplug(p)

    def tearDown(self):
        for p in list(UP._load().keys()):
            UP.unplug(p)

    def test_verify_selfcheck(self):
        v = UP.verify()
        self.assertTrue(v["ok"], "自检必须全过：%s" % v.get("failed"))
        self.assertGreaterEqual(v["checks"], 8)

    def test_classify_and_generate_interface(self):
        # 给任意连接点 → 自动识别 → 自动生成 ops 接口
        r = UP.plug("https://example.com", name="web1")
        self.assertTrue(r["ok"])
        self.assertEqual(r["port"]["kind"], "http")
        self.assertIn("get", r["port"]["ops"])
        self.assertEqual(r["port"]["executor"], "omni_plug")

    def test_persistence(self):
        # 落盘持久化：第二次读还在（重启模拟 = 重新 _load）
        UP.plug("python", name="py1")
        again = UP._load()
        self.assertIn("py1", again)
        self.assertEqual(again["py1"]["kind"], "bin")

    def test_not_wired_is_honest(self):
        # ws/mcp/ws 未接执行器如实标，不冒充可调用
        r = UP.plug("ws://localhost:9000", name="ws1")
        self.assertEqual(r["port"]["executor"], "not_wired")
        inv = UP.invoke("ws1", "connect")
        self.assertFalse(inv["ok"])
        self.assertEqual(inv.get("status"), "not_wired")

    def test_op_not_generated_refused(self):
        # 生成接口时没有的动词，invoke 拒绝，不冒充可调
        UP.plug("https://example.com", name="web2")
        inv = UP.invoke("web2", "delete")
        self.assertFalse(inv["ok"])
        self.assertEqual(inv.get("error"), "op_not_generated")

    def test_invoke_delegates_to_gate(self):
        # 🔴 门不绕：invoke http → 转 omni_plug → policy 挂 external_llm+data_export
        from gbt_allinone.security import policy as P
        d = P.evaluate("omni_plug", {"op": "universal", "target": "https://example.com"})
        self.assertIn("external_llm", d.scopes)
        self.assertIn("data_export", d.scopes)
        self.assertTrue(d.restricted)
        # 新 kind 本身零作用域（读类/登记免票），真执行在下游门判
        d2 = P.evaluate("gbt_universal_plug", {"op": "invoke", "name": "web2"})
        self.assertEqual(d2.scopes, ())

    def test_autoconnect(self):
        r = UP.autoconnect(["python", "127.0.0.1:8080", "ws://x"])
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(r["added"], 2)
        self.assertTrue(any(s.get("kind") == "ws" for s in r["skipped"]),
                        "ws 执行器未接必须进 skipped 如实报")
        self.assertEqual(UP.ports()["count"], r["added"])

    def test_tentacle_integration(self):
        # 融入触手：ability 名册认它 + call_capability 能调到
        from gbt_allinone.tentacle import bridge
        self.assertTrue(bridge.is_capability("gbt_universal_plug"))
        UP.plug("https://example.com", name="t1")
        out = bridge.call_capability("gbt_universal_plug", {"op": "ports"})
        self.assertTrue(out.get("ok"))
        self.assertGreaterEqual(out.get("count", 0), 1)

    def test_via_run_task(self):
        # 走唯一门 run_task 全通
        from gbt_allinone import api
        for op, p in [("schema", {}), ("plug", {"target": "python", "name": "r1"}),
                      ("ports", {}), ("describe", {"name": "r1"}),
                      ("unplug", {"name": "r1"}), ("verify", {})]:
            r = api.run_task("gbt_universal_plug", {"op": op, **p})
            body = r.get("gbt_result", r)
            self.assertEqual(body.get("status"), "ok", "%s 应 ok：%s" % (op, str(body)[:200]))


if __name__ == "__main__":
    unittest.main()
