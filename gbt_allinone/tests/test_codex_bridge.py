"""Codex App Server 桥接层协议测试（离线伪服务器，不消耗真实额度）。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

# 隔离 store，避免测试污染生产审计与产物目录
os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_codex_test_"))
os.environ.setdefault("GBT_SERVICE_DISCOVERY", "0")
# 🔴 2026-09-22 第 35 轮：owner 身份不再在 **import 期**置位（实测见 test_ai_audit.py），
#     改成"只在本模块用例期间置位、tearDownModule 还原"。
#     import 期置位 = 给整个 pytest 进程发主人身份 ⇒ 后续模块用例绕开人工授权门：
#     实测 test_framework 未置位 142 passed/0 failed；置位后同命令挂死超时（真出网/真动桌面）。
_OWNER_WAS = os.environ.get("GBT_OWNER_SESSION")


def setUpModule():
    global _OWNER_WAS
    _OWNER_WAS = os.environ.get("GBT_OWNER_SESSION")
    os.environ["GBT_OWNER_SESSION"] = "1"


def tearDownModule():
    if _OWNER_WAS is None:
        os.environ.pop("GBT_OWNER_SESSION", None)
    else:
        os.environ["GBT_OWNER_SESSION"] = _OWNER_WAS

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)

from gbt_allinone import codex_bridge as cb  # noqa: E402

FAKE_SERVER = os.path.join(_HERE, "fake_codex_app_server.py")


def _make_server(**kwargs) -> cb.CodexAppServer:
    return cb.CodexAppServer(
        cwd=_ROOT,
        command=[sys.executable, FAKE_SERVER],
        **kwargs,
    )


class TestCodexBridgeProtocol(unittest.TestCase):
    def setUp(self):
        self.server = _make_server()
        self.server.start(timeout=20)
        self.addCleanup(self.server.stop)

    def test_handshake_reports_server_info(self):
        info = self.server.server_info
        self.assertIn("userAgent", info)
        self.assertTrue(self.server.alive)
        self.assertTrue(self.server.status()["alive"])

    def test_thread_start_and_models(self):
        started = self.server.start_thread(ephemeral=True)
        self.assertEqual(started["thread"]["id"], "thread-test-1")
        self.assertEqual(started["model"], "fake-model")
        models = self.server.list_models()
        self.assertTrue(any(m.get("id") == "fake-model" for m in models))

    def test_turn_streams_events_and_calls_dynamic_tool(self):
        started = self.server.start_thread(ephemeral=True)
        thread_id = started["thread"]["id"]

        events: list[tuple[str, dict]] = []
        done = threading.Event()
        tool_calls: list[tuple[str, dict]] = []

        def on_event(method, params):
            events.append((method, params))
            if method == "turn/completed":
                done.set()

        def on_tool(name, args):
            tool_calls.append((name, args))
            return {"status": "ok", "probe": "reuse", "tool": name}

        self.server.on_event = on_event
        self.server.on_tool = on_tool
        self.server.start_turn(thread_id, "hello")
        self.assertTrue(done.wait(25), "未收到 turn/completed")

        methods = [m for m, _ in events]
        self.assertIn("item/agentMessage/delta", methods)
        self.assertIn("turn/completed", methods)
        self.assertEqual(tool_calls[0][0], "gbt_preflight")
        self.assertEqual(tool_calls[0][1]["kind"], "browser")

        delta_text = "".join(p.get("delta", "") for m, p in events
                             if m == "item/agentMessage/delta")
        self.assertIn("pong", delta_text)
        self.assertIn("reuse", delta_text)

    def test_command_approval_roundtrip(self):
        started = self.server.start_thread(ephemeral=True)
        thread_id = started["thread"]["id"]
        done = threading.Event()
        seen: list[tuple[str, dict]] = []

        def on_event(method, params):
            seen.append((method, params))
            if method == "turn/completed":
                done.set()

        def on_approval(method, params):
            self.assertEqual(method, "item/commandExecution/requestApproval")
            self.assertIn("command", params)
            return {"decision": "acceptForSession"}

        self.server.on_event = on_event
        self.server.on_approval = on_approval
        self.server.start_turn(thread_id, "approve-test please")
        self.assertTrue(done.wait(25), "审批回合未结束")

        output = "".join(p.get("delta", "") for m, p in seen
                         if m == "item/commandExecution/outputDelta")
        self.assertIn("acceptForSession", output)

    def test_default_denial_when_no_handler(self):
        started = self.server.start_thread(ephemeral=True)
        thread_id = started["thread"]["id"]
        done = threading.Event()
        seen: list[tuple[str, dict]] = []
        self.server.on_approval = None

        def on_event(method, params):
            seen.append((method, params))
            if method == "turn/completed":
                done.set()

        self.server.on_event = on_event
        self.server.start_turn(thread_id, "approve-test please")
        self.assertTrue(done.wait(25))
        output = "".join(p.get("delta", "") for m, p in seen
                         if m == "item/commandExecution/outputDelta")
        self.assertIn("cancel", output)

    def test_interrupt_returns(self):
        started = self.server.start_thread(ephemeral=True)
        result = self.server.interrupt(started["thread"]["id"], "turn-x")
        self.assertIsInstance(result, dict)


class TestCodexBridgeTools(unittest.TestCase):
    def test_dynamic_tool_specs_are_wellformed(self):
        specs = cb.dynamic_tool_specs()
        names = {s["name"] for s in specs}
        self.assertIn(cb.GBT_TOOL_CAPABILITY, names)
        self.assertIn(cb.GBT_TOOL_MIRROR, names)
        self.assertIn(cb.GBT_TOOL_PREFLIGHT, names)
        self.assertIn(cb.GBT_TOOL_UNIVERSAL_PLUG, names)
        self.assertIn(cb.GBT_TOOL_TENTACLE, names)
        self.assertIn(cb.GBT_TOOL_NATIVE_BROWSER, names)
        for spec in specs:
            self.assertEqual(spec["type"], "function")
            self.assertIsInstance(spec["description"], str)
            self.assertTrue(spec["description"])
            schema = spec["inputSchema"]
            self.assertEqual(schema["type"], "object")
            self.assertIn("properties", schema)

    def test_unknown_tool_is_reported_not_raised(self):
        result = cb.execute_gbt_tool("no_such_tool", {})
        self.assertEqual(result["status"], "error")

    def test_tool_success_checks_nested_capability_result(self):
        self.assertFalse(cb._tool_succeeded({
            "status": "ok",
            "kind": "browser",
            "result": {"ok": False, "status": "needs_browser_debug"},
        }))
        self.assertFalse(cb._tool_succeeded({
            "status": "ok",
            "gbt_result": {"status": "ok", "result": {"ok": False}},
        }))
        self.assertTrue(cb._tool_succeeded({
            "status": "ok",
            "gbt_result": {"status": "ok", "result": {"ok": True}},
        }))

    def test_mirror_op_mapping(self):
        for op in ("plan", "simulate", "parity", "rehearse", "release", "status"):
            self.assertIn(op, cb._MIRROR_OP_TO_KIND)

    def test_nexus_tool_is_exposed(self):
        specs = {s["name"]: s for s in cb.dynamic_tool_specs()}
        self.assertIn(cb.GBT_TOOL_NEXUS, specs)
        modes = specs[cb.GBT_TOOL_NEXUS]["inputSchema"]["properties"]["mode"]["enum"]
        self.assertEqual(set(modes), {"unify", "think", "sense", "rehearse"})

    def test_nexus_requires_goal(self):
        result = cb.execute_gbt_tool(cb.GBT_TOOL_NEXUS, {"mode": "sense"})
        self.assertEqual(result["status"], "error")

    def test_nexus_rejects_unknown_mode(self):
        result = cb.execute_gbt_tool(
            cb.GBT_TOOL_NEXUS, {"goal": "x", "mode": "teleport"})
        self.assertEqual(result["status"], "error")

    def test_nexus_sense_reaches_tentacle_status(self):
        from unittest import mock
        from gbt_allinone import api
        with mock.patch.object(api, "run_task",
                               return_value={"status": "ok"}) as patched:
            cb.execute_gbt_tool(cb.GBT_TOOL_NEXUS, {"goal": "同步感官", "mode": "sense"})
        self.assertEqual(patched.call_args[0][0], "tentacle_status")

    def test_nexus_unify_reaches_brain_unify(self):
        from unittest import mock
        from gbt_allinone import api
        with mock.patch.object(api, "run_task",
                               return_value={"status": "ok"}) as patched:
            cb.execute_gbt_tool(cb.GBT_TOOL_NEXUS, {"goal": "跑闭环", "mode": "unify"})
        self.assertEqual(patched.call_args[0][0], "brain_unify")
        self.assertEqual(patched.call_args[0][1].get("goal"), "跑闭环")

    def test_universal_plug_routes_to_workflow_engine(self):
        from unittest import mock
        from gbt_allinone import api
        with mock.patch.object(api, "run_task",
                               return_value={"status": "ok"}) as patched:
            cb.execute_gbt_tool(cb.GBT_TOOL_UNIVERSAL_PLUG, {
                "op": "status",
                "name": "demo",
                "limit": 3,
            })
        self.assertEqual(patched.call_args[0][0], "wf_status")
        self.assertEqual(patched.call_args[0][1]["name"], "demo")
        self.assertEqual(patched.call_args[0][1]["limit"], 3)

    def test_universal_plug_parallel_routes_to_brain_execute(self):
        from unittest import mock
        from gbt_allinone import api
        parallel = [{"kind": "health", "payload": {}}]
        with mock.patch.object(api, "run_task",
                               return_value={"status": "ok"}) as patched:
            cb.execute_gbt_tool(cb.GBT_TOOL_UNIVERSAL_PLUG, {
                "op": "parallel",
                "parallel": parallel,
            })
        self.assertEqual(patched.call_args[0][0], "brain_execute")
        self.assertEqual(patched.call_args[0][1]["parallel"], parallel)

    def test_tentacle_tool_routes_action_and_status(self):
        from unittest import mock
        from gbt_allinone import api
        with mock.patch.object(api, "run_task",
                               return_value={"status": "ok"}) as patched:
            cb.execute_gbt_tool(cb.GBT_TOOL_TENTACLE,
                                {"action": "see", "kwargs": {"ttl": 2}})
        self.assertEqual(patched.call_args[0][0], "tentacle")
        self.assertEqual(patched.call_args[0][1]["action"], "see")
        self.assertEqual(patched.call_args[0][1]["kwargs"]["ttl"], 2)

        with mock.patch.object(api, "run_task",
                               return_value={"status": "ok"}) as patched:
            cb.execute_gbt_tool(cb.GBT_TOOL_TENTACLE, {"action": "status"})
        self.assertEqual(patched.call_args[0][0], "tentacle_status")

    def test_native_browser_tool_routes_to_browser_native(self):
        from unittest import mock
        from gbt_allinone import api
        with mock.patch.object(api, "run_task",
                               return_value={"status": "ok"}) as patched:
            cb.execute_gbt_tool(cb.GBT_TOOL_NATIVE_BROWSER, {
                "action": "navigate",
                "url": "https://example.com",
            })
        self.assertEqual(patched.call_args[0][0], "browser")
        payload = patched.call_args[0][1]
        self.assertEqual(payload["op"], "native")
        self.assertEqual(payload["action"], "navigate")
        self.assertEqual(payload["url"], "https://example.com")

    def test_native_browser_schema_exposes_cookie_values_switch(self):
        specs = {s["name"]: s for s in cb.dynamic_tool_specs()}
        properties = specs[cb.GBT_TOOL_NATIVE_BROWSER]["inputSchema"]["properties"]
        self.assertEqual(properties["include_values"]["type"], "boolean")

    def test_mind_tool_routes_full_cycle_inputs(self):
        from unittest import mock
        from gbt_allinone import api
        with mock.patch.object(api, "run_task",
                               return_value={"status": "ok"}) as patched:
            cb.execute_gbt_tool(cb.GBT_TOOL_MIND, {
                "op": "pre_work",
                "task": "修复部署",
                "side_effect": True,
                "risk": 0.8,
                "certainty": 0.4,
            })
        self.assertEqual(patched.call_args[0][0], "mind")
        payload = patched.call_args[0][1]
        self.assertEqual(payload["op"], "pre_work")
        self.assertTrue(payload["side_effect"])
        self.assertEqual(payload["risk"], 0.8)

    def test_developer_instructions_carry_discipline(self):
        text = cb.default_developer_instructions("你是小土豆")
        self.assertIn("你是小土豆", text)
        self.assertIn("mirror", text.lower())
        self.assertIn("orient", text.lower())
        self.assertIn("gbt_nexus", text)
        self.assertIn("gbt_universal_plug", text)
        self.assertIn("gbt_tentacle", text)
        self.assertIn("gbt_native_browser", text)
        self.assertIn("gbt_mind", text)

    def test_status_reports_local_codex_presence(self):
        result = cb.status()
        self.assertIn("ok", result)
        self.assertIn("protocol", result)

    def test_doctor_reports_missing_codex_cleanly(self):
        from unittest import mock
        with mock.patch.object(cb, "find_codex", return_value=None):
            result = cb.doctor()
        self.assertFalse(result["ok"])
        self.assertEqual(result["checks"][0]["step"], "locate")
        self.assertIn("hint", result)

    def test_doctor_live_flag_marks_turn_step(self):
        from unittest import mock
        with mock.patch.object(cb, "find_codex", return_value=None):
            result = cb.doctor(live=True)
        self.assertTrue(result["live"])
        self.assertNotIn("turn_stream", [c["step"] for c in result["checks"]])


class TestCodexRunOnce(unittest.TestCase):
    """run_once 全链路：真实桥接层 + 伪服务器。"""

    def test_run_once_completes_and_returns_reply(self):
        result = cb.run_once(
            "hello",
            cwd=_ROOT,
            command=[sys.executable, FAKE_SERVER],
            timeout=30,
            tool_handler=lambda name, args: {"status": "ok", "probe": name},
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["thread_id"], "thread-test-1")
        self.assertIn("pong", result["reply"])
        self.assertEqual(result["tool_call_count"], 1)

    def test_run_once_rejects_empty_message(self):
        with self.assertRaises(cb.CodexAppServerError):
            cb.run_once("   ", command=[sys.executable, FAKE_SERVER])


class TestCodexApiRouting(unittest.TestCase):
    """统一入口路由：codex_* 能力必须走既有审计与授权路径。"""

    def test_codex_status_returns_stamped_result(self):
        from gbt_allinone import api
        result = api.run_task("codex_status", {})
        self.assertIn("gbt_result", result)
        self.assertEqual(result["gbt_result"]["kind"], "codex_status")

    def test_codex_chat_delegates_to_run_once(self):
        from unittest import mock
        from gbt_allinone import api
        with mock.patch.object(cb, "run_once",
                               return_value={"status": "ok", "reply": "x"}) as patched:
            result = api.run_task("codex_chat", {"message": "hi", "model": "m"})
        patched.assert_called_once()
        self.assertEqual(result["gbt_result"]["result"]["reply"], "x")

    def test_codex_chat_requires_message(self):
        from gbt_allinone import api
        result = api.run_task("codex_chat", {})
        self.assertEqual(result.get("error_class") or result.get("status"), "user_error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
