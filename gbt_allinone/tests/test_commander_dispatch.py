# -*- coding: utf-8 -*-
"""指挥官派发车道的机器判据（2026-11-07）。

锁四件事：
  ① 命中安全命令目录且句子像命令 ⇒ 必须派发，不能只回模型；
  ② 纯提问（「page_scan 是什么」）或闸门未命中 ⇒ 不许误执行；
  ③ 真执行必须走 `api.run_task`，不能自己找别的执行器；
  ④ 缺票 / 缺依赖 / 真失败按三态回执，不许包装成成功。
"""
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import commander_dispatch as CD  # noqa: E402


GATE = {
    "hit": True,
    "why": "测试命中",
    "margin": 0.5,
    "top": [{"cap": "page_scan", "score": 1.0, "source": "curation"}],
}


class TestResolve(unittest.TestCase):
    def test_command_dispatches(self):
        d = CD.resolve("那你自己全量扫描一遍看看还有那些没有接好", gate_result=GATE)
        self.assertTrue(d["hit"], d)
        self.assertEqual(d["cap"], "page_scan")
        self.assertEqual(d["op"], "scan")
        self.assertEqual(d["params"], {"op": "scan"})

    def test_question_does_not_dispatch(self):
        for q in ("page_scan 是什么", "这个能力怎么用", "介绍一下页面扫描", "署名是什么"):
            d = CD.resolve(q, gate_result=GATE)
            self.assertFalse(d["hit"], "%s 不该派发：%s" % (q, d))

    def test_gate_miss_does_not_dispatch(self):
        d = CD.resolve("全量扫描一遍看看哪些没接好",
                       gate_result={"hit": False, "why": "未命中", "top": []})
        self.assertFalse(d["hit"], d)

    def test_guard_commands_dispatch(self):
        cases = (
            ("红黄警报追踪根因", "alerts", "recent", {"op": "recent"}),
            ("检查署名", "signature_guard", "", {"scope": "all"}),
            ("有没有异物", "inventory", "", {}),
            ("查旧物", "legacy_guard", "scan", {"op": "scan"}),
        )
        for q, cap, op, params in cases:
            gate = {"hit": True, "why": "测试命中", "margin": 0.5,
                    "top": [{"cap": cap, "score": 1.0, "source": "curation"}]}
            d = CD.resolve(q, gate_result=gate)
            self.assertTrue(d["hit"], "%s 应该派发：%s" % (q, d))
            self.assertEqual(d["cap"], cap, q)
            self.assertEqual(d["op"], op, q)
            self.assertEqual(d["params"], params, q)

    def test_alerts_receipt_shows_root_cause_fields(self):
        gate = {"hit": True, "why": "测试命中", "margin": 0.5,
                "top": [{"cap": "alerts", "score": 1.0, "source": "curation"}]}
        body = {"quiet": True, "runtime_faults": 0, "anomalies": 2,
                "by_signal": {"guard": 0, "trace": 1, "legacy": 1, "recovered": 0},
                "needs_a_look": False, "unregistered_footprints": ["probe"],
                "by_event": {"svc_down": 1}}
        env = {"ok": True, "status": "ok", "kind": "alerts",
               "result": {"status": "ok", "kind": "alerts", "result": body}}
        old = CD.api.run_task
        CD.api.run_task = lambda cap, payload, safe=False: env
        try:
            d = CD.resolve("红黄警报追踪根因", gate_result=gate)
            rec = CD.receipt(d, CD.execute(d), context="test")
        finally:
            CD.api.run_task = old
        self.assertEqual(rec["via"], "commander-dispatch:alerts")
        for needle in ("runtime_faults：0", "anomalies：2", "needs_a_look：False",
                       "不在册足迹：1 个"):
            self.assertIn(needle, rec["text"])


class TestExecute(unittest.TestCase):
    def test_execute_uses_unique_gate_and_renders_real_fields(self):
        calls = []
        body = {"ok": True, "op": "scan", "页数": 20, "绑好": 20, "未绑好": 0,
                "唯一能力位": 410, "实探能力位": 410,
                "绿": 380, "黄": 28, "红": 2,
                "红名单": [{"cap": "x", "why": "boom", "ms": 12}],
                "黄名单": [], "结论": "有红/有缺口 ⇒ 见名单", "用时秒": 1.2}
        env = {"ok": True, "status": "ok", "kind": "page_scan",
               "result": {"status": "ok", "kind": "page_scan", "result": body}}

        def fake_run(cap, payload, safe=False):
            calls.append((cap, payload, safe))
            return env

        old = CD.api.run_task
        CD.api.run_task = fake_run
        try:
            d = CD.resolve("全量扫描一遍看看哪些没接好", gate_result=GATE)
            ex = CD.execute(d)
            rec = CD.receipt(d, ex, context="test")
        finally:
            CD.api.run_task = old

        self.assertEqual(calls, [("page_scan", {"op": "scan"}, True)])
        self.assertTrue(ex["ok"], ex)
        self.assertEqual(rec["via"], "commander-dispatch:page_scan")
        self.assertIn("红名单", rec["text"])
        self.assertIn("绿 380", rec["text"])
        self.assertEqual(rec["result"]["红"], 2)

    def test_denied_is_not_success(self):
        env = {"ok": False, "status": "denied", "missing_scopes": ["desktop_control"],
               "result": {"ok": False, "denied": True}}

        old = CD.api.run_task
        CD.api.run_task = lambda cap, payload, safe=False: env
        try:
            d = CD.resolve("全量扫描一遍看看哪些没接好", gate_result=GATE)
            ex = CD.execute(d)
            rec = CD.receipt(d, ex, context="test")
        finally:
            CD.api.run_task = old

        self.assertFalse(ex["ok"])
        self.assertEqual(rec["status"], "denied")
        self.assertFalse(rec["ok"])
        self.assertIn("缺授权", rec["text"])
        self.assertIn("desktop_control", rec["text"])


if __name__ == "__main__":
    unittest.main()
