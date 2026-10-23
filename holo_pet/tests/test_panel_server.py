from __future__ import annotations

import ast
import hashlib
import http.client
import inspect
import json
import re
from html.parser import HTMLParser
import socket
import sys
import tempfile
import textwrap
import time
import threading
import unittest
import urllib.request
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
for path in (ROOT, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import panel_server as PS  # noqa: E402


class _FakeBridge:
    def __init__(self):
        self.bus = PS.EventBus()
        self.calls = []

    def state(self):
        return {
            "ok": True,
            "codex": {"ok": True},
            "codex_ready": False,
            "mind": {"ok": True, "mood": "平稳", "valence": 0.5},
            "bluetooth": {
                "ok": True,
                "ble_backend": "bleak",
                "classic_backend": "win-bluetooth-stack",
            },
            "sensory": {
                "ok": True,
                "brain": {"ok": True, "state": "awake"},
                "eye": {"ok": True, "state": "limited"},
                "ear": {"ok": True, "state": "limited"},
                "mouth": {"ok": True, "state": "ready"},
                "hand": {"ok": True, "state": "ready"},
            },
            "notion": {"ok": True, "configured": True},
            "eigenflux": {
                "ok": True,
                "ready": True,
                "installed": True,
                "authenticated": True,
            },
        }

    def notion(self, operation, payload=None):
        self.calls.append((operation, payload or {}))
        return {"ok": True, "operation": operation}

    def brain_graph(self, limit=400):
        """大脑执行层读数（2026-09-22 新增）：桩跟着真接口长 —— 声明了就必须真能应答。
        桩里只回结构形状，**不编状态**（真实现是从 audit.jsonl 读真事件）。"""
        self.calls.append(("brain_graph", {"limit": limit}))
        return {
            "ok": True,
            "structure": {
                "ok": True,
                "layers": [
                    {"id": "core", "title": "五维合一脑", "nodes": [
                        {"id": "dim:" + n, "layer": "core", "name": n, "kind": "dimension"}
                        for n in ("route", "execute", "verify", "health", "unify")]},
                    {"id": "peer", "title": "同层能力", "nodes": []},
                    {"id": "substrate", "title": "底座支撑", "nodes": []},
                ],
                "edges": [], "chain_evidence": [],
                "counts": {"dimensions": 5, "peer": 0, "substrate": 0, "edges": 0},
            },
            "live": {"ok": True, "count": 0, "latest_by_kind": {}, "events": []},
            "errors": {},
        }

    def settings(self):
        """设置面读数（2026-09-22 Owner：「配置密钥属于设置」）。

        桩跟着真接口长 —— 与 purge 那条同理：声明了就必须真能应答。
        桩里**不放任何密钥**，只回结构与状态，跟真实现一样不打码之外的东西。
        """
        self.calls.append(("settings", {}))
        return {
            "ok": True,
            "groups": [
                {"id": "keys", "title": "密钥", "status": "need_login",
                 "desc": "本地免费大模型池（FreeLLMAPI）的供应商密钥",
                 "server": {"up": False, "base_url": "http://127.0.0.1:0",
                            "discovered_from": "stub"},
                 "authed": False,
                 "note": "桩：未登录"},
                {"id": "compute", "title": "模型与算力", "status": "pending"},
                {"id": "body", "title": "本体", "status": "pending"},
                {"id": "transformer", "title": "变压器", "status": "pending"},
            ],
        }

    def settings_action(self, op, payload=None):
        """设置面写动作。桩只回结构，**绝不回明文密钥**。"""
        self.calls.append(("settings_action", {"op": op, **(payload or {})}))
        if op == "probe":
            return {"ok": True, "op": op,
                    "probe": {"up": False, "base_url": "http://127.0.0.1:0"}}
        if op == "login":
            return {"ok": False, "op": op, "error": "桩：不真登录"}
        return {"ok": False, "op": op, "error": f"桩未实现 {op}"}

    def h1(self):
        """赏金台 h1mcp 只读体检（2026-09-22 新增路由 /api/h1）。

        桩跟着真接口长 —— 声明了就必须真能应答，否则
        `test_every_declared_route_actually_answers` 会以 RemoteDisconnected 报红。
        桩里**不放任何凭据**（与真实现一致：只回布尔），路径一律标 `stub/`，
        免得桩数据被人当成"真读过盘"。
        """
        self.calls.append(("h1", {}))
        body = {
            "readonly": True,
            "stage": "stage1-local-readonly",
            "note": "桩：不回显任何凭据值。",
            "badge": "warn",
            "config_source": "stub",
            "binary": {
                "path": "stub/h1mcp.exe", "present": True, "bytes": 1, "tag": "v0.0.0",
                "sha256": "0" * 64, "recorded_sha256": "0" * 64, "sha_match": True,
                "sidecar_present": True, "reason": None,
            },
            "credentials": {"ready": False, "items": [
                {"name": "H1_USERNAME", "role": "HackerOne 用户名",
                 "read_by": "h1mcp v0.1.4", "configured": False},
                {"name": "H1_API_KEY", "role": "API 令牌（二进制实际读取名）",
                 "read_by": "h1mcp v0.1.4", "configured": False},
                {"name": "H1_API_TOKEN", "role": "历史口径名（h1mcp v0.1.4 不读取）",
                 "read_by": None, "configured": False},
            ]},
            "drafts": {"path": "stub/drafts", "initialized": False, "count": None,
                       "files": [], "reason": "桩：目录不存在（未初始化）"},
            "api_surfaces": [
                {"id": "programs_scope", "title": "程序与 scope", "state": "pending",
                 "reason": "阶段二未接入"},
                {"id": "reports", "title": "我的报告", "state": "pending",
                 "reason": "阶段二未接入"},
                {"id": "earnings", "title": "收益", "state": "pending",
                 "reason": "阶段二未接入"},
            ],
            "sensitive_note": "桩：敏感档动作不接。",
            "transport": "stub",
        }
        return {"ok": True, "data": body}

    def purge(self):
        """净化刀读数（R-H171 新增只读路由）：桩必须跟着真接口长，否则
        `test_every_declared_route_actually_answers` 会以 RemoteDisconnected 报红
        —— 那正是这条门存在的意义：**声明了就必须真能应答**。"""
        self.calls.append(("purge", {}))
        return {
            "ok": True,
            "window": 2000,
            "anomalies": 20,
            "runtime_faults": 0,
            "by_signal": {"runtime": 0, "guard": 0, "trace": 10, "legacy": 8, "recovered": 2},
            "by_event": {"svc_down": 9, "pipeline_blocked": 8, "error": 3},
            "reading_scope": {"scoreboard": "runtime_faults"},
            "before": {"runtime_faults": 15, "at": "2026-09-19", "source": "docs/净化刀设计.md"},
            "source": "/api/purge · 只读 · 不执行",
        }

    def music(self):
        """音乐发布平台三层只读归位（R-H173 新增只读路由）：桩跟着真接口长。"""
        self.calls.append(("music", {}))
        return {
            "ok": True,
            "readonly": True,
            "classes": [
                {"class": "generation", "cn": "生成端", "ring": "内环",
                 "role": "灵感/歌词 → 歌曲", "count": 1,
                 "items": [{"name": "MusicFlow", "channel": "平台",
                            "note": "生成端候选", "verified": False, "status": "未核实"}]},
                {"class": "agent_native", "cn": "Agent 原生端", "ring": "中环",
                 "role": "注册身份 → 提交歌曲", "count": 1,
                 "items": [{"name": "moltdj", "channel": "REST · Bearer",
                            "note": "Agent First", "verified": False, "status": "未核实"}]},
                {"class": "distribution", "cn": "分发端", "ring": "外环",
                 "role": "提交到 DSP", "count": 1,
                 "items": [{"name": "distro-mcp", "channel": "MCP（Ditto）",
                            "note": "分发候选", "verified": False, "status": "未核实"}]},
            ],
            "counts": {"total": 3, "verified": 0, "unverified": 3},
            "priority": ["moltdj", "noumi-mcp", "distro-mcp", "MusicFlow"],
            "source": "tools/music_publishing.py · 只读 · 不加执行能力",
        }

    def eigenflux(self, operation, payload=None):
        self.calls.append((f"eigenflux:{operation}", payload or {}))
        return {"ok": True, "operation": operation}

    def quick(self, action, payload=None):
        self.calls.append((action, payload or {}))
        return {"ok": True, "accepted": True}

    def send(self, text):
        self.calls.append(("send", {"text": text}))
        return {"ok": True, "accepted": True, "path": "fallback", "deferred": True}

    def capabilities(self):
        self.calls.append(("capabilities", {}))
        return {
            "ok": True,
            "total": 2,
            "enabled": 1,
            "disabled": 1,
            "domains": {"system": 1, "dangerous": 1},
            "items": [
                {"kind": "health", "domain": "system", "desc": "系统健康信息",
                 "enabled": True, "reason": "", "needs_confirmation": False},
                {"kind": "pentest", "domain": "dangerous", "desc": "渗透攻击/利用",
                 "enabled": False, "reason": "渗透攻击/利用", "needs_confirmation": False},
            ],
        }

    def capability(self, kind, payload=None, confirm=False):
        self.calls.append((
            "capability",
            {"kind": kind, "payload": payload or {}, "confirm": bool(confirm)},
        ))
        return {"ok": True, "accepted": True, "path": "capability",
                "deferred": True, "request_id": "r-1"}

    def tree(self, depth=3, limit=400):
        self.calls.append(("tree", {"depth": depth, "limit": limit}))
        return {"ok": True, "root": "fake", "depth": depth, "limit": limit,
                "truncated": False, "tree": {"name": "fake", "kind": "dir",
                                             "dirs": 0, "files": 0, "bytes": 0, "children": []}}

    def observer(self, probe=True, channel_dir=None, isolated_home=None):
        self.calls.append(("observer", {"probe": bool(probe)}))
        return {"ok": True, "status": "wired_not_verified", "handshake": "inconclusive",
                "sandbox": {"read_only_configured": False}, "voice_by_kind": {},
                "blockers": [], "sees": [], "contract": []}

    def voice_speak(self, kind, text, channel_dir=None):
        self.calls.append(("voice_speak", {"kind": kind, "text": text}))
        return {"ok": True, "spoken": True, "kind": "提醒", "truncated": False}

    def studio(self):
        self.calls.append(("studio", {}))
        return {"ok": True, "tools": [], "platforms": [], "gate_names": [],
                "platforms_tracked_total": 0}


class EventBusTests(unittest.TestCase):
    def test_history_is_kept_for_reconnect(self):
        bus = PS.EventBus(history_limit=10)
        bus.publish("status", codex="ready")
        bus.publish("bluetooth", action="bluetooth_scan", result={"ok": True})

        snapshot = bus.snapshot()
        self.assertEqual([row["type"] for row in snapshot], ["status", "bluetooth"])
        self.assertEqual(snapshot[-1]["action"], "bluetooth_scan")

    def test_seq_is_monotonic_and_since_returns_delta_only(self):
        """重连补差量：since(seq) 只给更新的，已渲染过的一条都不回放。"""
        bus = PS.EventBus(history_limit=10)
        bus.publish("reply", text="一")
        bus.publish("reply", text="二")
        bus.publish("reply", text="三")

        seqs = [row["seq"] for row in bus.snapshot()]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(len(set(seqs)), 3)
        self.assertEqual([row["text"] for row in bus.since(seqs[0])], ["二", "三"])
        self.assertEqual(bus.since(bus.last_seq), [])
        self.assertEqual(bus.since(0), bus.snapshot())

    def test_since_tolerates_garbage_without_faking_zero(self):
        bus = PS.EventBus(history_limit=10)
        bus.publish("reply", text="一")
        # 取不到就按"从头补"，不静默当成 0 以外的假值
        self.assertEqual(len(bus.since("not-a-number")), 1)

    def test_boot_id_is_stable_within_one_bus_and_differs_across_buses(self):
        """seq 只在一个 boot 内可比 —— 服务重启后旧水位必须能被识别为作废。"""
        first = PS.EventBus(history_limit=10)
        first.publish("reply", text="一")
        second = PS.EventBus(history_limit=10)
        second.publish("reply", text="一")

        self.assertEqual(first.snapshot()[0]["boot"], first.boot_id)
        self.assertNotEqual(first.boot_id, second.boot_id)


class HoloBridgeContractTests(unittest.TestCase):
    def test_bluetooth_write_requires_explicit_confirmation(self):
        bridge = PS.HoloBridge()
        result = bridge.quick(
            "bluetooth_write",
            {
                "address": "AA:BB:CC:DD:EE:FF",
                "char_uuid": "0000fff1-0000-1000-8000-00805f9b34fb",
                "value_hex": "01",
            },
        )

        self.assertEqual(result, {"ok": True, "needs_confirmation": True})
        events = bridge.bus.snapshot()
        self.assertEqual(events[-1]["type"], "bluetooth_confirm")
        self.assertEqual(events[-1]["payload"]["op"], "write")

    def test_bluetooth_status_is_exposed_in_state_contract(self):
        bridge = PS.HoloBridge()
        with mock.patch.object(
            PS.api,
            "run_task",
            return_value={
                "gbt_result": {
                    "ok": True,
                    "ble_backend": "bleak",
                    "classic_backend": "win-bluetooth-stack",
                }
            },
        ):
            state = bridge.state()

        self.assertTrue(state["bluetooth"]["ok"])
        self.assertEqual(state["bluetooth"]["ble_backend"], "bleak")

    def test_sensory_state_maps_real_backends_without_overclaiming(self):
        bridge = PS.HoloBridge()
        with (
            mock.patch.object(
                bridge,
                "_mind_pulse",
                return_value={
                    "ok": True,
                    "mood": "平稳",
                    "presence": "熟悉感",
                    "valence": 0.7,
                    "mood_intensity": 0.2,
                    "metacognition": {"mode": "inspect_then_act", "confidence": 0.4},
                    "owner_model": {"state": "unknown"},
                    "environment": {"resources": {"memory_percent": 42}},
                },
            ),
            mock.patch.object(
                PS.vision_watch,
                "status",
                return_value={
                    "ok": True,
                    "running": False,
                    "capture_environment": {
                        "capture_ready": False,
                        "interactive_desktop": False,
                        "likely_failure_roots": ["non_interactive_desktop"],
                        "selected": {"backend": "auto", "monitor_name": "Virtual"},
                        "backends": {"dxcam": True},
                    },
                },
            ),
            mock.patch.object(
                PS.vision_watch,
                "stats",
                return_value={"ok": True, "stats": {"running": False, "captured": 0}},
            ),
            mock.patch.object(
                PS.voice_cap,
                "run",
                return_value={
                    "ok": True,
                    "tts": "win-sapi（可用）",
                    "asr": "needs_dependency",
                },
            ),
            mock.patch.object(PS.policy, "owner_session", return_value=nullcontext()),
            mock.patch.object(
                PS.api,
                "run_task",
                return_value={
                    "gbt_result": {
                        "result": {
                            "diagnose": {
                                "ok": True,
                                "manifest_methods": 89,
                                "neighborhoods": 10,
                                "deps": {
                                    "ctypes": {"ok": True},
                                    "mss": {"ok": True},
                                    "dxcam": {"ok": True},
                                },
                            },
                            "coverage": {"total_domains": 10},
                        }
                    }
                },
            ),
            mock.patch.object(
                PS.tentacle_transmission,
                "pulse",
                return_value={
                    "ok": True,
                    "total_transmissions": 5,
                    "active_channels": 1,
                    "buffered": 7,
                    "channels": {"visual": 7},
                },
            ),
        ):
            sensory = bridge.sensory_state(force=True)

        self.assertEqual(
            set(sensory),
            {"ok", "brain", "eye", "ear", "mouth", "hand", "transport"},
        )
        self.assertTrue(sensory["brain"]["ok"])
        self.assertEqual(sensory["eye"]["state"], "limited")
        self.assertFalse(sensory["eye"]["capture_ready"])
        self.assertEqual(sensory["ear"]["state"], "limited")
        self.assertEqual(sensory["mouth"]["state"], "ready")
        self.assertEqual(sensory["hand"]["metrics"]["能力数"], 89)
        self.assertEqual(sensory["hand"]["metrics"]["邻域数"], 10)
        self.assertEqual(sensory["transport"]["state"], "active")

    def test_sensory_subsystem_failure_is_isolated(self):
        bridge = PS.HoloBridge()
        with (
            mock.patch.object(bridge, "_mind_pulse", return_value={"ok": True, "mood": "平稳"}),
            mock.patch.object(PS.vision_watch, "status", side_effect=RuntimeError("capture down")),
            mock.patch.object(
                PS.voice_cap,
                "run",
                return_value={"ok": True, "tts": "win-sapi（可用）", "asr": "configured"},
            ),
            mock.patch.object(PS.policy, "owner_session", return_value=nullcontext()),
            mock.patch.object(PS.api, "run_task", side_effect=RuntimeError("tentacle down")),
            mock.patch.object(PS.tentacle_transmission, "pulse", side_effect=RuntimeError("bus down")),
        ):
            sensory = bridge.sensory_state(force=True)

        self.assertTrue(sensory["ok"])
        self.assertTrue(sensory["brain"]["ok"])
        self.assertEqual(sensory["eye"]["state"], "error")
        self.assertEqual(sensory["ear"]["state"], "ready")
        self.assertEqual(sensory["hand"]["state"], "error")
        self.assertEqual(sensory["transport"]["state"], "error")

    def test_state_exposes_sensory_contract(self):
        bridge = PS.HoloBridge()
        with (
            mock.patch.object(
                PS,
                "CB",
            ) as codex,
            mock.patch.object(bridge, "_safe_life_status", return_value={"ok": True}),
            mock.patch.object(bridge, "_safe_bt_status", return_value={"ok": True}),
            mock.patch.object(bridge, "sensory_state", return_value={"ok": True}),
        ):
            codex.status.return_value = {"ok": True}
            state = bridge.state()

        self.assertTrue(state["sensory"]["ok"])

    def test_approval_decision_mapping(self):
        self.assertEqual(
            PS.HoloBridge._approval_payload(
                "item/permissions/requestApproval",
                "acceptforsession",
            ),
            {"permissions": {}, "scope": "session"},
        )
        self.assertEqual(
            PS.HoloBridge._approval_payload(
                "item/commandExecution/requestApproval",
                "decline",
            ),
            {"decision": "decline"},
        )

    def test_approval_slot_wakes_waiter(self):
        bridge = PS.HoloBridge()
        slot = {"event": threading.Event(), "decision": None, "method": "test"}
        bridge._approvals[7] = slot

        result = bridge.resolve_approval(7, "approve")

        self.assertTrue(result["ok"])
        self.assertTrue(slot["event"].is_set())
        self.assertEqual(slot["decision"], {"decision": "accept"})

    def test_codex_unavailable_fallback_does_not_crash(self):
        bridge = PS.HoloBridge()
        bridge._chat = None
        bridge._last_error = "codex unavailable"
        with mock.patch.object(PS, "ChatClient", None):
            bridge._run_fallback("hello")

        events = bridge.bus.snapshot()
        self.assertTrue(any(row["type"] == "error" for row in events))

    def test_notion_operation_uses_framework_route(self):
        bridge = PS.HoloBridge()
        with (
            mock.patch.object(PS.policy, "owner_session", return_value=nullcontext()),
            mock.patch.object(
                PS.api,
                "run_task",
                return_value={"gbt_result": {"ok": True, "results": []}},
            ) as run_task,
        ):
            result = bridge.notion("recent", {"limit": 5})

        self.assertTrue(result["ok"])
        self.assertEqual(run_task.call_args.args[0], "notion")
        self.assertEqual(run_task.call_args.args[1]["op"], "recent")
        self.assertEqual(run_task.call_args.args[1]["limit"], 5)

    def test_notion_operation_unwraps_plain_route_result(self):
        bridge = PS.HoloBridge()
        with (
            mock.patch.object(PS.policy, "owner_session", return_value=nullcontext()),
            mock.patch.object(
                PS.api,
                "run_task",
                return_value={
                    "gbt_result": {
                        "status": "ok",
                        "kind": "notion",
                        "result": {"ok": True, "count": 2},
                    }
                },
            ),
        ):
            result = bridge.notion("recent", {"limit": 2})

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)


class QuickOutletContractTests(unittest.TestCase):
    """R-H100：`/api/quick` 这条出口此前**零覆盖**（实测：panel 测试里 `/api/quick` 出现 0 次，
    只有一处 `.quick(` 直调蓝牙确认路径）。出口有 13 条动作、页面只接了 2 个按钮 ——
    这种"出口有·接线没做"最容易静默漂，所以把三件事钉住：

      ① 白名单逐条**认识**（未知动作必须被拒，已知动作不许回"未知快捷动作"）；
      ② 每条动作映射到的能力**必须在册**（白名单指着不存在的能力 = 点一下就报未知能力）；
      ③ 页面上的按钮集合必须 ⊆ 白名单；**已知未接线清单**显式写成常量 ——
         以后接一个按钮就得动这个常量，漂移因此可见（不是"没人知道少了几个"）。
    """

    KNOWN_UNWIRED = {
        "mirror_status", "sense_status", "workflow_status", "life_status", "mind_pulse",
        "bluetooth_status", "bluetooth_scan", "bluetooth_classic",
        "bluetooth_connect", "bluetooth_read", "bluetooth_write",
    }

    def test_unknown_action_is_refused(self):
        r = PS.HoloBridge().quick("no_such_quick_action")
        self.assertFalse(r["ok"])
        self.assertIn("未知快捷动作", r["error"])

    def test_declared_actions_map_to_registered_capabilities(self):
        import inspect
        from gbt_allinone.caps_registry import BENIGN_CAPS
        # 🔴 2026-09-22 第 47 轮修（FR-6 窄字符类 ⇒ **假缺失**）：
        #    原来这里（以及下面三条）写 `[a-z_]+` —— 动作名/能力位里一旦出现**数字或大写**就解析不到。
        #    实测（`.scratch/fr6_holo_target.py`，AST 取 `HoloBridge.quick` 真源码）：
        #    窄口径 13 对 = 宽口径 13 对、页面 data-action 2 = 2 ⇒ **今天零漏**，
        #    而且下面的 `assertGreaterEqual(len(pairs), 13)` 恰好卡在 13，
        #    真漏一对就会红 ⇒ 这条判据今天**自己防住了**。
        #    仍然把字符类改宽：修掉"靠巧合防住"的写法，别让下一个人以为它天然安全。
        src = inspect.getsource(PS.HoloBridge.quick)
        pairs = re.findall(r'"([A-Za-z0-9_]+)": \("([A-Za-z0-9_]+)",', src)
        self.assertGreaterEqual(len(pairs), 13, f"白名单解析异常，只认出 {pairs}")
        actions = [a for a, _k in pairs]
        self.assertEqual(len(set(actions)), len(actions), "白名单里有重复动作名")
        for action, kind in pairs:
            self.assertIn(kind, BENIGN_CAPS, f"{action} 指向未注册能力 {kind}")

    def test_page_buttons_are_subset_of_whitelist_and_gap_is_explicit(self):
        import inspect
        src = inspect.getsource(PS.HoloBridge.quick)
        declared = {a for a, _k in re.findall(r'"([A-Za-z0-9_]+)": \("([A-Za-z0-9_]+)",', src)}
        page = (ROOT / "holo_pet" / "index.html").read_text(encoding="utf-8")
        buttons = set(re.findall(r'data-action="([^"]+)"', page))
        self.assertTrue(buttons <= declared, f"页面按钮不在白名单里：{sorted(buttons - declared)}")
        gap = declared - buttons
        self.assertEqual(gap, self.KNOWN_UNWIRED,
                         "未接线清单变了：接了线就把这个常量改掉（不允许悄悄变）")

    def test_readonly_actions_keep_readonly_kinds(self):
        import inspect
        src = inspect.getsource(PS.HoloBridge.quick)
        pairs = dict(re.findall(r'"([A-Za-z0-9_]+)": \("([A-Za-z0-9_]+)",', src))
        for action, kind in (("mirror_status", "mirror_status"), ("workflow_status", "wf_status"),
                             ("life_status", "life"), ("mind_pulse", "mind"),
                             ("sense_status", "tentacle_status")):
            self.assertEqual(pairs.get(action), kind,
                             f"{action} 是只读出口，不该改挂到 {pairs.get(action)}")


class EigenFluxContractTests(unittest.TestCase):
    class _Client:
        enabled = True

        def status(self):
            return {
                "ok": True,
                "enabled": True,
                "installed": True,
                "authenticated": True,
                "home": "C:/private/credentials",
                "executable": "C:/private/eigenflux.exe",
                "server": "eigenflux",
            }

        def refresh(self):
            return {
                "ok": True,
                "feed": {"items": [], "source": "live"},
                "messages": {"items": [], "source": "live"},
                "friends": {"items": [], "source": "live"},
            }

        def send_message(self, content, **target):
            return {"ok": True, "content": content, **target}

    def test_status_contract_never_exposes_local_paths(self):
        bridge = PS.HoloBridge()
        bridge._eigenflux = self._Client()

        status = bridge._safe_eigenflux_status()

        self.assertTrue(status["ready"])
        self.assertNotIn("home", status)
        self.assertNotIn("executable", status)
        self.assertNotIn("private", str(status))

    def test_refresh_and_send_are_structured(self):
        bridge = PS.HoloBridge()
        bridge._eigenflux = self._Client()

        refreshed = bridge.eigenflux("bootstrap")
        sent = bridge.eigenflux(
            "send",
            {"content": "公开进展", "receiver_id": "agent-1"},
        )

        self.assertTrue(refreshed["ok"])
        self.assertTrue(refreshed["status"]["ready"])
        self.assertTrue(sent["ok"])
        self.assertEqual(sent["receiver_id"], "agent-1")


class StaticContractTests(unittest.TestCase):
    def test_notion_and_bluetooth_are_parallel_deck_sections(self):

        class SectionParentParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.section_parents = {}

            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == "section":
                    key = values.get("id") or values.get("class", "")
                    parent = self.stack[-1] if self.stack else ("document", "")
                    self.section_parents[key] = parent
                self.stack.append((tag, values.get("class", "")))

            def handle_endtag(self, tag):
                for index in range(len(self.stack) - 1, -1, -1):
                    if self.stack[index][0] == tag:
                        del self.stack[index:]
                        break

        parser = SectionParentParser()
        parser.feed((HERE / "index.html").read_text(encoding="utf-8"))

        self.assertEqual(parser.section_parents["notion-vault"], ("div", "deck-scroll"))
        self.assertEqual(parser.section_parents["device-bus"], ("div", "deck-scroll"))
        self.assertEqual(parser.section_parents["eigenflux-network"], ("div", "deck-scroll"))

    def test_static_routes_serve_panel_index(self):
        handler = object.__new__(PS._Handler)
        index = handler._static_path("/")

        self.assertEqual(index, HERE / "index.html")

    def test_static_path_traversal_is_rejected(self):
        handler = object.__new__(PS._Handler)
        self.assertIsNone(handler._static_path("/holo_pet/%2e%2e/SOUL.md"))
        self.assertIsNone(handler._static_path("/%2e%2e/SOUL.md"))

    def test_http_state_route_uses_bridge_contract(self):
        bridge = _FakeBridge()
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/api/state",
                timeout=3,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["bluetooth"]["ble_backend"], "bleak")
            self.assertTrue(payload["sensory"]["ok"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_http_bluetooth_route_maps_operation(self):
        bridge = _FakeBridge()
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/bluetooth",
                data=json.dumps({"op": "scan", "timeout": 2}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(bridge.calls[-1][0], "bluetooth_scan")
            self.assertEqual(bridge.calls[-1][1]["timeout"], 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_http_eigenflux_route_maps_send_operation(self):
        bridge = _FakeBridge()
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/eigenflux",
                data=json.dumps({
                    "op": "send", "content": "public update",
                    "receiver_id": "agent-1",
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(bridge.calls[-1][0], "eigenflux:send")
            self.assertEqual(bridge.calls[-1][1]["receiver_id"], "agent-1")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_http_notion_route_maps_read_only_operation(self):
        bridge = _FakeBridge()
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/notion",
                data=json.dumps({"op": "search", "query": "会议"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(bridge.calls[-1][0], "search")
            self.assertEqual(bridge.calls[-1][1]["query"], "会议")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def _post_message(self, port, body):
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/message",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def _with_server(self, bridge, body):
        """起一个真服务、连发同一条消息两次，返回 (第一次, 第二次, bridge)。"""
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch.object(PS, "_panel_audit", return_value=True):
                first = self._post_message(server.server_port, body)
                second = self._post_message(server.server_port, body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        return first, second

    def test_duplicate_message_is_accepted_only_once(self):
        """实测缺陷的正面回归：同一句话只受理一次，不再跑两轮。"""
        bridge = _FakeBridge()
        first, second = self._with_server(bridge, {"text": "同一句话"})

        sends = [row for row in bridge.calls if row[0] == "send"]
        self.assertEqual(len(sends), 1)
        self.assertTrue(first["accepted"])
        self.assertFalse(first.get("duplicate"))
        self.assertTrue(second["duplicate"])
        self.assertFalse(second["accepted"])
        self.assertTrue(second["ok"])

    def test_explicit_client_msg_id_wins_over_text(self):
        """显式幂等键优先：同 id 不同文本也只算一次投递。"""
        bridge = _FakeBridge()
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch.object(PS, "_panel_audit", return_value=True):
                first = self._post_message(
                    server.server_port, {"text": "第一次内容", "client_msg_id": "k-1"})
                second = self._post_message(
                    server.server_port, {"text": "重发时内容漂了", "client_msg_id": "k-1"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

        sends = [row for row in bridge.calls if row[0] == "send"]
        self.assertEqual(len(sends), 1)
        self.assertTrue(first["accepted"])
        self.assertTrue(second["duplicate"])

    def test_different_text_is_not_swallowed(self):
        """负对照：不同的话必须都能说出口 —— 幂等门不许把正常消息吃掉。"""
        bridge = _FakeBridge()
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch.object(PS, "_panel_audit", return_value=True):
                first = self._post_message(server.server_port, {"text": "第一句"})
                second = self._post_message(server.server_port, {"text": "第二句"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

        sends = [row for row in bridge.calls if row[0] == "send"]
        self.assertEqual([row[1]["text"] for row in sends], ["第一句", "第二句"])
        self.assertTrue(first["accepted"] and second["accepted"])
        self.assertFalse(first.get("duplicate") or second.get("duplicate"))

    def test_deduper_expires_so_the_same_sentence_can_be_repeated(self):
        """窗口过后同一句话必须能再说一次（否则幂等门会变成"记忆黑洞"）。"""
        dedupe = PS.MessageDeduper(text_ttl=0.5)
        self.assertFalse(dedupe.check("再说一次", "")[0])
        dedupe.remember("再说一次", "", {"ok": True})
        self.assertTrue(dedupe.check("再说一次", "")[0])
        time.sleep(0.6)
        self.assertFalse(dedupe.check("再说一次", "")[0])

    def test_http_capabilities_route_exposes_her_catalog(self):
        bridge = _FakeBridge()
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/api/capabilities", timeout=3,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["enabled"] + payload["disabled"], payload["total"])
        disabled = [row for row in payload["items"] if not row["enabled"]]
        self.assertEqual(disabled[0]["kind"], "pentest")
        self.assertTrue(disabled[0]["reason"])

    def test_http_capability_route_passes_kind_and_confirm(self):
        bridge = _FakeBridge()
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/capability",
                data=json.dumps(
                    {"kind": "health", "payload": {"_probe": True}, "confirm": True}
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

        self.assertTrue(payload["accepted"])
        self.assertEqual(bridge.calls[-1][0], "capability")
        self.assertEqual(bridge.calls[-1][1]["kind"], "health")
        self.assertTrue(bridge.calls[-1][1]["confirm"])
        self.assertEqual(bridge.calls[-1][1]["payload"], {"_probe": True})


class CapabilityBridgeTests(unittest.TestCase):
    """面板通用能力口：目录读她的注册表，权限仍归 api 那一层。"""

    def test_voice_accepts_only_the_three_functions(self):
        """负对照：第四件职能必须被拒 —— 旁观者只有提醒 / 意见 / 建议。"""
        bridge = PS.HoloBridge()
        with tempfile.TemporaryDirectory() as tmp:
            for kind in ("提醒", "remind", "意见", "advise", "建议", "suggest"):
                result = bridge.voice_speak(kind, f"{kind} 一条", channel_dir=Path(tmp))
                self.assertTrue(result["spoken"], kind)
            for bad in ("execute", "run", "delete", "发布", "", "命令"):
                result = bridge.voice_speak(bad, "越权试试", channel_dir=Path(tmp))
                self.assertFalse(result["ok"], bad)
                self.assertIn("三件职能", result["error"])

    def test_voice_writes_only_to_its_channel(self):
        """出声的唯一副作用是往独立通道追一行 —— 不碰主账本，也不返回执行结果。"""
        bridge = PS.HoloBridge()
        with tempfile.TemporaryDirectory() as tmp:
            result = bridge.voice_speak("remind", "这一步不对：上一步已经删过它了",
                                        channel_dir=Path(tmp))
            files = list(Path(tmp).glob("*.jsonl"))
            rows = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, f"voice-{time.strftime('%Y%m%d')}.jsonl")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["result"], "提醒")
        self.assertEqual(rows[0]["target"], "observer.voice")
        self.assertTrue(rows[0]["detail"].startswith("这一步不对"))
        self.assertIn("零执行权", rows[0]["authority"])
        self.assertNotIn("status", result)  # 不返回任何"执行结果"

    def test_voice_has_no_execution_branch(self):
        """零执行权是**结构事实**：方法体里不许出现任何执行调用（AST 扫，不靠承诺）。"""
        source = textwrap.dedent(inspect.getsource(PS.HoloBridge.voice_speak))
        called = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute):
                    called.add(fn.attr)
                elif isinstance(fn, ast.Name):
                    called.add(fn.id)

        for forbidden in ("run_task", "Popen", "system", "spawn", "exec", "eval",
                          "call", "check_output", "run_shell"):
            self.assertNotIn(forbidden, called, f"voice_speak 里不该出现 {forbidden}")
        self.assertIn("open", called)      # 只做一件事：追加一行
        self.assertIn("mkdir", called)

    def test_voice_dedupes_the_same_line(self):
        """同一句话连说两遍只落一条 —— 写入前查指纹，不靠事后删。"""
        bridge = PS.HoloBridge()
        with tempfile.TemporaryDirectory() as tmp:
            first = bridge.voice_speak("suggest", "更稳的走法是先备份再动", channel_dir=Path(tmp))
            second = bridge.voice_speak("suggest", "更稳的走法是先备份再动", channel_dir=Path(tmp))
            rows = [json.loads(line)
                    for line in (Path(tmp) / first["file"]).read_text(encoding="utf-8").splitlines()]

        self.assertTrue(first["spoken"])
        self.assertTrue(second["duplicate"])
        self.assertFalse(second["spoken"])
        self.assertEqual(len(rows), 1)

    def test_voice_truncates_overlong_text(self):
        bridge = PS.HoloBridge()
        with tempfile.TemporaryDirectory() as tmp:
            result = bridge.voice_speak("advise", "很长" * 900, channel_dir=Path(tmp))
            row = json.loads((Path(tmp) / result["file"]).read_text(encoding="utf-8").strip())

        self.assertTrue(result["truncated"])
        self.assertEqual(row["chars"], 500)
        self.assertTrue(row["truncated"])

    def test_studio_lists_tools_and_hot_platforms(self):
        """视频工坊：工具就绪度是**实测**的，平台事实**只读登记表**。"""
        data = PS.HoloBridge().studio()

        self.assertTrue(data["ok"])
        tools = {row["id"]: row for row in data["tools"]}
        self.assertEqual(set(tools), {"youtube-factory", "vidu", "ffmpeg-video-editor"})
        for row in tools.values():
            self.assertEqual(row["ready"], not row["missing"],
                             "ready 必须与 missing 自洽：缺什么就写什么")
            self.assertIsInstance(row["bins"], dict)
        # 剪辑这条路只需要 ffmpeg —— 本机装了就该是就绪
        self.assertEqual(tools["ffmpeg-video-editor"]["ready"],
                         bool(tools["ffmpeg-video-editor"]["bins"].get("ffmpeg")))

        plats = {row["id"]: row for row in data["platforms"]}
        self.assertEqual([row["id"] for row in data["platforms"]],
                         ["douyin", "kuaishou", "bilibili", "wechat_channels",
                          "tiktok", "youtube", "instagram"])
        # 事实必须与登记表一致（单一来源），且视频号如实标"无官方接口"
        from social_platforms import spec_for
        for pid, row in plats.items():
            spec = spec_for(pid)
            self.assertIsNotNone(spec, pid)
            self.assertEqual(row["official_api"], spec["official_api"], pid)
            self.assertEqual(row["credential_field"], spec["credential_field"], pid)
        self.assertFalse(plats["wechat_channels"]["official_api"])
        self.assertEqual(len(data["gate_names"]), 4)

        # 接入单必须真的落在盘上（不是嘴上说有）
        doc = data["checklist"]
        self.assertTrue(doc["exists"], doc)
        self.assertGreater(doc["bytes"], 500, doc)
        self.assertTrue(Path(doc["path"]).is_file(), doc["path"])

    def test_studio_does_not_invent_unknown_platforms(self):
        """登记表里没有的平台，不许编事实 —— `spec_known` 必须如实为 false。"""
        from social_platforms import spec_for

        data = PS.HoloBridge().studio()

        self.assertIsNone(spec_for("no_such_platform_xyz"),
                          "未登记平台必须返回 None，不猜")
        for row in data["platforms"]:
            self.assertTrue(row["spec_known"], row["id"])
            self.assertIsNotNone(spec_for(row["id"]), row["id"])

    @staticmethod
    def _count_nodes(node):
        return 1 + sum(CapabilityBridgeTests._count_nodes(c)
                       for c in node.get("children", []) if not c.get("skipped"))

    def test_project_tree_is_bounded(self):
        """项目树必须有预算：不能因为仓库大就把面板拖垮。"""
        payload = PS.HoloBridge().tree(depth=3, limit=60)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["root"], ROOT.name)
        self.assertLessEqual(self._count_nodes(payload["tree"]), 60)

    def test_project_tree_skips_dependency_noise(self):
        """依赖树/版本库不进树 —— 否则旁观者眼里全是噪声。"""
        payload = PS.HoloBridge().tree(depth=3, limit=400)

        def walk(node):
            for child in node.get("children", []):
                yield child
                yield from walk(child)

        for child in walk(payload["tree"]):
            if child["name"] in ("node_modules", ".git", "__pycache__"):
                self.assertTrue(child.get("skipped"), child["name"])
                self.assertEqual(child.get("children"), [])

    def test_project_tree_does_not_expose_file_contents(self):
        """只给名字与大小 —— 不读内容，就没有泄密面。"""
        payload = PS.HoloBridge().tree(depth=2, limit=200)

        def walk(node):
            for child in node.get("children", []):
                yield child
                yield from walk(child)

        for child in walk(payload["tree"]):
            if child["kind"] == "file":
                self.assertEqual(set(child), {"name", "kind", "bytes"})

    def test_observer_reports_inconclusive_rather_than_absent(self):
        """没探测 ≠ 不在跑：《空不等于不存在律》。关掉探测必须报 inconclusive。"""
        with tempfile.TemporaryDirectory() as tmp:
            payload = PS.HoloBridge().observer(probe=False, channel_dir=Path(tmp), isolated_home=Path(tmp))

        self.assertEqual(payload["handshake"], "inconclusive")
        self.assertEqual(payload["dsh"]["web_3080"], "inconclusive")
        self.assertEqual(payload["status"], "wired_not_verified")

    def test_observer_reads_handshake_from_her_channel(self):
        """握手状态必须**读证据**：通道里有 ok 记录就得报 ok，不许继续写死 inconclusive。"""
        with tempfile.TemporaryDirectory() as tmp:
            channel = Path(tmp) / "probe.jsonl"
            channel.write_text(json.dumps({
                "ts": time.time(), "iso": "2026-09-19T03:10:00", "probe": "dsh_handshake",
                "target": "dsh --profile sdk (0.1.5-rc.2)", "result": "ok",
                "detail": "initialize OK · shutdown OK", "latency_ms": 4083, "ttl_s": 3600,
            }, ensure_ascii=False) + "\n", encoding="utf-8")

            payload = PS.HoloBridge().observer(probe=False, channel_dir=Path(tmp), isolated_home=Path(tmp))

        self.assertEqual(payload["handshake"], "ok")
        self.assertEqual(payload["status"], "verified_handshake_only")
        self.assertEqual(payload["voice_total"], 1)
        codes = {row["code"] for row in payload["blockers"]}
        self.assertNotIn("handshake_not_verified", codes)
        self.assertIn("observer_functions_not_built", codes)

    def test_observer_marks_stale_handshake(self):
        """旧读数不是现在的结论：过了 ttl 必须报 stale。"""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "probe.jsonl").write_text(json.dumps({
                "ts": time.time() - 7200, "iso": "2026-09-19T01:00:00",
                "probe": "dsh_handshake", "result": "ok", "ttl_s": 3600,
            }, ensure_ascii=False) + "\n", encoding="utf-8")

            payload = PS.HoloBridge().observer(probe=False, channel_dir=Path(tmp), isolated_home=Path(tmp))

        self.assertEqual(payload["handshake"], "stale")
        self.assertNotEqual(payload["status"], "verified_handshake_only")

    def test_observer_is_read_only_and_leaks_no_secret(self):
        """旁观者面上只许有取证，不许有凭据/token，也不许自称已接通。"""
        with tempfile.TemporaryDirectory() as tmp:
            payload = PS.HoloBridge().observer(probe=False, channel_dir=Path(tmp), isolated_home=Path(tmp))
        blob = json.dumps(payload, ensure_ascii=False)

        self.assertNotIn("token=", blob)
        self.assertNotIn("sk-", blob)
        self.assertEqual(payload["handshake"], "inconclusive")  # 绝不谎报已握手
        self.assertTrue(payload["blockers"])
        self.assertTrue(all(row["mode"] == "read-only" for row in payload["sees"]))
        for row in payload["contract"]:
            self.assertTrue(row["exists"], row["path"])

    def test_observer_names_the_full_access_preset_risk(self):
        """DSH 默认预设是全权限 —— 这条必须出现在卡点里，不许被静默忽略。"""
        with tempfile.TemporaryDirectory() as tmp:
            payload = PS.HoloBridge().observer(probe=False, channel_dir=Path(tmp), isolated_home=Path(tmp))

        codes = {row["code"] for row in payload["blockers"]}
        self.assertIn("handshake_not_verified", codes)
        if payload["dsh"]["permission_preset"] == "danger-full-access":
            self.assertIn("dsh_default_full_access", codes)

    def test_observer_reports_read_only_config_of_isolated_home(self):
        """「旁观者只读」要有配置证据：settings 与 patch 两处必须同时是 read-only。"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "profiles" / "sdk").mkdir(parents=True)
            (home / "settings.yaml").write_text(
                "permission:\n  defaultPreset: read-only\n", encoding="utf-8")
            (home / "profiles" / "sdk" / "cordis.patch.yml").write_text(
                "- id: permission\n  config:\n    presets:\n      read-only:\n"
                "        sandbox: read-only\n        approval: ask\n",
                encoding="utf-8")

            payload = PS.HoloBridge().observer(probe=False, channel_dir=home, isolated_home=home)

        self.assertTrue(payload["sandbox"]["read_only_configured"])
        self.assertEqual(payload["sandbox"]["settings_default_preset"], "read-only")
        self.assertEqual(payload["sandbox"]["patch_sandbox"], "read-only")
        self.assertIn("只管文件操作", payload["sandbox"]["caveat"])
        self.assertNotIn("observer_not_read_only", {r["code"] for r in payload["blockers"]})

    def test_observer_flags_missing_read_only_config(self):
        """只读档没配上时必须报卡点 —— 不许把「口号」当「已配置」。"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "settings.yaml").write_text(
                "permission:\n  defaultPreset: danger-full-access\n", encoding="utf-8")

            payload = PS.HoloBridge().observer(probe=False, channel_dir=home, isolated_home=home)

        self.assertFalse(payload["sandbox"]["read_only_configured"])
        self.assertIn("observer_not_read_only", {r["code"] for r in payload["blockers"]})

    @staticmethod
    def _route_literals(source: str) -> set:
        """用 AST 取真实路由比较，**不走文本匹配** —— 省得把注释/文档里的示例也算进去。

        （第一版就是拿正则扫全文，结果被我自己注释里的示例字符串咬了一口 ——
        又一次"扫描范围 ≠ 结论范围"。）
        """
        found = set()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Compare):
                continue
            left = node.left
            if not (isinstance(left, ast.Attribute) and left.attr == "path"
                    and isinstance(left.value, ast.Name) and left.value.id == "parsed"):
                continue
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant) \
                        and isinstance(comp.value, str):
                    found.add(comp.value)
        return found

    def test_app_surface_matches_real_routes(self):
        """双向对账：目录里列的 APP 能力面 == 源码里真实存在的路由，一条都不能差。"""
        source = (HERE / "panel_server.py").read_text(encoding="utf-8")
        real = self._route_literals(source)
        declared = {row["route"] for row in PS.APP_SURFACE}

        self.assertFalse(real - declared, f"源码有路由但目录没列: {sorted(real - declared)}")
        self.assertFalse(declared - real, f"目录列了源码没有的路由: {sorted(declared - real)}")
        self.assertEqual(len(declared), len(PS.APP_SURFACE), "APP_SURFACE 里有重复路由")

    def test_every_declared_route_actually_answers(self):
        """门要有牙：**声明了就必须真能应答**。

        只验"字面量存在"是不够的 —— `/api/observer` 曾因缩进多一层成了 `return` 之后的死代码，
        字面量在、AST 在、py_compile 绿，但真请求 **404**。抓到它的是整机冒烟。
        这条门就是那次漏网的补丁：逐条真连、真发、只看状态码。
        """
        bridge = _FakeBridge()
        server = PS.create_server("127.0.0.1", 0, bridge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for row in PS.APP_SURFACE:
                path, method = row["route"], row["method"]
                if path == "/api/events":
                    # 流式路由：连上就长流，断开必然在服务端刷 ConnectionReset 噪音，
                    # 而噪音会掩盖真错误。它的增量/序号语义由 EventBusTests + `since` 用例覆盖。
                    continue
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    body = b"{}" if method == "POST" else None
                    headers = {"Content-Type": "application/json"} if method == "POST" else {}
                    conn.request(method, path, body=body, headers=headers)
                    status = conn.getresponse().status   # 只取状态行；SSE 的正文不读
                except Exception as exc:                 # noqa: BLE001
                    self.fail(f"{method} {path} 连不上或不应答: {type(exc).__name__}: {exc}")
                finally:
                    conn.close()
                self.assertNotEqual(status, 404, f"{method} {path} 不可达（404）")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_app_pending_points_at_real_evidence(self):
        """契约已立/实体未建 这一栏必须指向盘上真存在的文件，不许拿空口号占位。"""
        self.assertTrue(PS.APP_PENDING)
        for row in PS.APP_PENDING:
            self.assertIn(row["status"], ("contract_only", "wired_not_verified"))
            self.assertTrue(row["blocked_by"])
            for rel in row["evidence"]:
                self.assertTrue((ROOT / rel).is_file(), rel)

    def test_app_surface_is_declared_as_not_from_her_registry(self):
        """APP 自身能力面不能被混进她的能力条目里 —— 两个来源必须在目录里分得开。"""
        catalog = PS.HoloBridge().capabilities()

        self.assertIn("app", catalog)
        app_routes = {row["route"] for row in catalog["app"]["routes"]}
        kinds = {row["kind"] for row in catalog["items"]}
        self.assertTrue(app_routes)
        for route in app_routes:
            self.assertNotIn(route, kinds)
            self.assertFalse(route.startswith("api/"))
        self.assertEqual(catalog["app"]["pending"][0]["key"], "observer")

    def test_catalog_reads_her_registry_not_a_second_copy(self):
        catalog = PS.HoloBridge().capabilities()

        self.assertTrue(catalog["ok"])
        self.assertGreater(catalog["total"], 90)
        by_kind = {row["kind"]: row for row in catalog["items"]}
        self.assertTrue(by_kind["health"]["enabled"])
        self.assertTrue(by_kind["tentacle"]["enabled"])
        # 🔴 2026-10-17 翻正（留痕 · 原断言 / 为什么翻 / 原期望不变的部分）：
        #   原断言：`pentest` 必须 enabled=False · status="unimplemented" · reason 以「渗透攻击/利用」开头。
        #   那是 **pentest 还只是占位名** 的年代写的。现读事实（源码为证）：
        #     `gbt_allinone/security/redteam.py:413 def pentest(...)` 已实现，
        #     `redteam.py:1206` 已注册进 REDTEAM_HANDLERS，`api.py:378/2080` 已路由
        #     ⇒ 目录如实报 enabled=True / status="enabled"。
        #   原期望【不变】：目录必须从**她自己的注册表现读**、不抄第二份。只把断言对齐现读真值。
        self.assertTrue(by_kind["pentest"]["enabled"])
        self.assertEqual(by_kind["pentest"]["status"], "enabled")
        self.assertIn("授权渗透验证", by_kind["pentest"]["desc"])
        self.assertIn("system", catalog["domains"])

    def test_non_safe_capability_is_refused_with_honest_reason(self):
        """面板侧与 api.py 同步：**已实现但未标 safe** 的能力必须**如实**拒，
        理由要点名 safe 门 —— 不许含糊成"禁用"，也不许谎称"未知能力"。

        🔴 2026-10-17 翻正（留痕 · 原测试名 / 为什么翻 / 原期望不变的部分）：
          原测试名 `test_unimplemented_capability_is_refused_at_the_panel_too`，
          拿 pentest / credential_steal / keylogger 当"零实现文件"的样本、期望报「未知能力」。
          现读事实：`security/redteam.py` 已实现 pentest/keylogger/screen_sniff/device_takeover，
          `unimplemented_scan` 也报「只登记未实现 **0**」⇒ 仓里**已经没有**"只登记未实现"的名字了。
          原期望（**不许拿"被策略挡住"冒充"没做"**）不变；现口径：
            · 已实现但 safe=False ⇒ 拒，理由必须点出「未标记 safe」；
            · 根本不存在的名字    ⇒ 才是「未知能力」。
        """
        bridge = PS.HoloBridge()
        for kind in ("pentest", "keylogger", "screen_sniff"):
            result = bridge.capability(kind, {}, confirm=True)
            self.assertFalse(result["ok"], kind)
            self.assertIn("未标记 safe", result["error"])
            self.assertNotIn("未知能力", result["error"])
            self.assertNotIn("禁用", result["error"])

        # 真正不存在的名字，才走「未知能力」
        missing = bridge.capability("no_such_capability_xyz", {}, confirm=True)
        self.assertFalse(missing["ok"])
        self.assertIn("未知能力", missing["error"])

    def test_unknown_capability_is_refused(self):
        result = PS.HoloBridge().capability("no_such_capability_xyz")

        self.assertFalse(result["ok"])
        self.assertIn("未知能力", result["error"])

    def test_capability_needing_params_is_refused_not_blindly_called(self):
        """R-H98 修根源：带参数的能力在面板上**不许发空调用**。

        病根：前端只发 {kind, confirm}，`one_key_deploy` 这类能力点一下就是一次 `{}` 调用，
        要么报一个看不懂的错，要么按默认值跑偏。现在：缺参数当场如实拒绝，说清缺哪几个。
        """
        bridge = PS.HoloBridge()
        with mock.patch.object(PS.api, "run_task") as runner:
            refused = bridge.capability("one_key_deploy", {}, confirm=True)
            runner.assert_not_called()

        self.assertFalse(refused["ok"])
        self.assertTrue(refused["requires_params"])
        self.assertEqual(refused["missing_params"], ["target"])
        self.assertIn("target", refused["error"])

        # 参数给全 → 照旧走侧效应确认门（不是被参数门挡死）
        with mock.patch.object(PS.api, "run_task") as runner2:
            gated = bridge.capability("one_key_deploy", {"target": "D:\\x"})
            runner2.assert_not_called()
        self.assertTrue(gated.get("needs_confirmation"), gated)

        with mock.patch.object(PS.api, "run_task", return_value={"ok": True}) as runner3:
            accepted = bridge.capability("one_key_deploy",
                                         {"target": "D:\\x", "room": "r1"}, confirm=True)
            self.assertTrue(accepted["accepted"], accepted)

    def test_capabilities_directory_exposes_param_contract(self):
        """目录必须把入参契约带出来（前端靠它标 '✎ 需参数' 并拒发空调用）。"""
        catalog = PS.HoloBridge().capabilities()
        by_kind = {row["kind"]: row for row in catalog["items"]}
        self.assertTrue(by_kind["one_key_deploy"]["requires_params"])
        self.assertEqual(by_kind["one_key_deploy"]["params"], ["target"])
        self.assertTrue(by_kind["one_key_deploy"]["params_hint"])
        self.assertFalse(by_kind["health"].get("requires_params"))

    def test_side_effect_capability_needs_explicit_confirmation(self):
        bridge = PS.HoloBridge()
        with mock.patch.object(PS.api, "run_task") as runner:
            gated = bridge.capability("pipeline_submit", {"target": "x"})
            runner.assert_not_called()
            confirmed = bridge.capability("pipeline_submit", {"target": "x"}, confirm=True)

        self.assertTrue(gated["needs_confirmation"])
        self.assertFalse(gated.get("accepted"))
        self.assertTrue(confirmed["accepted"])
        self.assertEqual(confirmed["path"], "capability")

    def test_capability_result_lands_on_the_event_bus(self):
        bridge = PS.HoloBridge()
        sentinel = {"ok": True, "platform": "Windows-Test"}
        with mock.patch.object(PS.api, "run_task", return_value=sentinel) as runner:
            ack = bridge.capability("health")
            for _ in range(40):
                rows = [r for r in bridge.bus.snapshot()
                        if r["type"] == "cap_result" and r.get("request_id") == ack["request_id"]]
                if rows:
                    break
                time.sleep(0.05)

        self.assertTrue(ack["accepted"])
        runner.assert_called_once()
        self.assertEqual(runner.call_args[0][0], "health")
        self.assertTrue(rows)
        self.assertEqual(rows[-1]["kind"], "health")
        self.assertEqual(rows[-1]["result"], sentinel)

class BrandGuardTests(unittest.TestCase):
    """R36 第一刀：入屏白名单过滤 + 原文留痕。正负对照必须给出不同结果。"""

    def test_safe_last_error_filters_codex_and_keeps_plain_chinese(self):
        # 正对照：含 brand 词（大小写任意）的入屏文案必须被拦下
        self.assertEqual(
            PS.safe_last_error("Codex 编程内核"),
            PS._SAFE_FALLBACK,
        )
        self.assertEqual(PS.safe_last_error("codex_not_ready"), PS._SAFE_FALLBACK)
        self.assertEqual(PS.safe_last_error("CODEX executable not found"), PS._SAFE_FALLBACK)
        # 负对照：日志/审计字段通道的原文不经过入屏过滤，原样保留
        raw = 'CB.find_codex() returned None'
        self.assertEqual(raw, 'CB.find_codex() returned None')
        self.assertTrue(raw.lower().count('codex'))
        # 正负对照结果必须不同，否则这条测试无效
        self.assertNotEqual(PS.safe_last_error("Codex 编程内核"), "Codex 编程内核")
        # 纯中文白名单文案可以照常入屏
        self.assertEqual(PS.safe_last_error("内核未在运行"), "内核未在运行")

    def test_rendered_last_error_is_audited_with_raw_hash(self):
        bridge = PS.HoloBridge()
        bridge._last_error = "Codex executable not found"
        bridge._last_error_safe = PS.safe_last_error(bridge._last_error)
        bridge._last_error_audited_hash = ""
        bridge._last_error_audit_landed = True

        seen = []

        def fake_panel_audit(event, meta=None):
            seen.append((event, meta or {}))
            return True

        with mock.patch.object(PS, "_panel_audit", side_effect=fake_panel_audit):
            snap = bridge.state()

        self.assertEqual(snap["last_error"], "Codex executable not found")
        self.assertEqual(snap["last_error_safe"], PS._SAFE_FALLBACK)
        self.assertEqual(snap["last_error_audit"]["landed"], True)
        events = [e for e, _ in seen]
        self.assertIn("error_rendered", events)
        meta = dict(seen[events.index("error_rendered")][1])
        self.assertEqual(meta["raw"], "Codex executable not found")
        self.assertEqual(len(meta["hash"]), 64)
        self.assertEqual(
            meta["hash"],
            hashlib.sha256("Codex executable not found".encode("utf-8")).hexdigest(),
        )


class O8ProbeTests(unittest.TestCase):
    """O8：两个内部状态探针免审计 + 蓝牙 TTL 缓存（判定必须认 `result.ok`）。"""

    OK_ENVELOPE = {"status": "ok", "kind": "bluetooth", "result": {"ok": True,
                                                                  "ble_backend": "bleak"}}

    def _recorder(self, payload=None):
        calls = []

        def fake_run_task(kind, body=None, **kwargs):
            calls.append({"kind": kind, "payload": body, "kwargs": kwargs})
            return {"gbt_result": dict(payload if payload is not None
                                       else self.OK_ENVELOPE)}

        return calls, fake_run_task

    def test_probe_call_sites_pass_probe_true(self):
        """面板这两条只读路径必须显式带 `probe=True`（防"改了 api 没人用"的假修复）。"""
        bridge = PS.HoloBridge()
        calls, fake = self._recorder()
        with mock.patch.object(PS.policy, "owner_session", return_value=nullcontext()), \
                mock.patch.object(PS.api, "run_task", side_effect=fake):
            bridge._sensory_hand()
            bridge._safe_bt_status()

        kinds = [c["kind"] for c in calls]
        self.assertEqual(["tentacle_status", "bluetooth"], kinds)
        for c in calls:
            self.assertIs(True, c["kwargs"].get("probe"),
                          "%s 必须以 probe=True 调用（否则审计照旧被灌）" % c["kind"])
        # 判别性：如果两处都没带 probe，上面会红；这条断言把"两组必须不同"写死
        self.assertFalse(any(c["kwargs"].get("probe") is not True for c in calls))

    def test_bt_failed_judges_on_inner_result_ok(self):
        """O8 取证抓到的坑：外层信封**没有** ok，判据必须认里层 `result.ok`。"""
        outer_no_ok = {"status": "ok", "kind": "bluetooth", "result": {"ok": True}}
        self.assertFalse(PS.HoloBridge._bt_failed(outer_no_ok),
                         "外层没有 ok 字段，不许因此判成失败（那会永远走失败档 TTL）")
        self.assertTrue(PS.HoloBridge._bt_failed(
            {"status": "ok", "kind": "bluetooth", "result": {"ok": False}}))
        self.assertTrue(PS.HoloBridge._bt_failed({"status": "error", "message": "x"}))
        self.assertTrue(PS.HoloBridge._bt_failed({"ok": False, "error": "boom"}))
        # 拿不到信封 = 不能证明成功 → 按失败档（《空不等于不存在律》）
        self.assertTrue(PS.HoloBridge._bt_failed({}))
        self.assertTrue(PS.HoloBridge._bt_failed(None))
        # 正负对照必须给出不同结果
        self.assertNotEqual(PS.HoloBridge._bt_failed(outer_no_ok),
                            PS.HoloBridge._bt_failed({"result": {"ok": False}}))

    def test_bt_status_cache_ttl_success_and_force(self):
        bridge = PS.HoloBridge()
        calls, fake = self._recorder()
        clock = [1000.0]
        with mock.patch.object(PS.policy, "owner_session", return_value=nullcontext()), \
                mock.patch.object(PS.api, "run_task", side_effect=fake), \
                mock.patch.object(PS.time, "monotonic", side_effect=lambda: clock[0]):
            first = bridge._safe_bt_status()
            clock[0] += 20.0
            second = bridge._safe_bt_status()          # 20s < 30s → 命中缓存
            self.assertEqual(1, len(calls), "30s 内不许重查")
            self.assertEqual(first, second)
            clock[0] += 11.0                            # 累计 31s > 30s → 过期
            bridge._safe_bt_status()
            self.assertEqual(2, len(calls), "过 30s 必须重查一次")
            bridge._safe_bt_status(force=True)          # force 绕缓存
            self.assertEqual(3, len(calls), "force=True 必须绕缓存")

    def test_bt_status_cache_failure_ttl_is_halved(self):
        bridge = PS.HoloBridge()
        calls, fake = self._recorder(payload={})        # 空信封 = 不能证明成功
        clock = [2000.0]
        with mock.patch.object(PS.policy, "owner_session", return_value=nullcontext()), \
                mock.patch.object(PS.api, "run_task", side_effect=fake), \
                mock.patch.object(PS.time, "monotonic", side_effect=lambda: clock[0]):
            bridge._safe_bt_status()
            self.assertEqual(1, len(calls))
            self.assertTrue(bridge._bt_cache_failed, "空信封必须判成失败")
            clock[0] += 10.0
            bridge._safe_bt_status()                    # 10s < 15s → 命中
            self.assertEqual(1, len(calls), "失败档 15s 内不重查")
            clock[0] += 6.0                             # 累计 16s > 15s → 过期
            bridge._safe_bt_status()
        self.assertEqual(2, len(calls), "失败档过 15s 必须重查")


class G4OwnerSessionTests(unittest.TestCase):
    """G4 / D2b：面板 POST 路由的对外动作必须落在 owner_session 内。

    判据来自方案原文，不来自对仓库结构的推断：
      · 路由目标链上出现 `api.run_task` → 该链必须包 `policy.owner_session()`；
      · `/api/eigenflux` 是 G4 点名的漏口 → 必须单独有硬判据；
      · 扫描器自己过《扫描器自证律》：真实源码（正对照）与变异源码（负对照）
        必须给出不同结果，相同则报 SCANNER_BLIND，不许报 PASS。
    """

    SOURCE = (HERE / "panel_server.py").read_text(encoding="utf-8")
    GUARD_MARKER = "with policy.owner_session():"

    # ------------------------------------------------- 纯静态扫描器（不执行被扫代码）
    @staticmethod
    def _has_owner_session(node) -> bool:
        return any(
            isinstance(n, ast.Attribute) and n.attr == "owner_session"
            for n in ast.walk(node)
        )

    @staticmethod
    def _has_run_task(node) -> bool:
        return any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "run_task"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "api"
            for n in ast.walk(node)
        )

    @classmethod
    def _scan(cls, source: str) -> dict:
        tree = ast.parse(source)
        classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        methods = {
            n.name: n for n in classes["HoloBridge"].body
            if isinstance(n, ast.FunctionDef)
        }
        do_post = next(
            n for n in classes["_Handler"].body
            if isinstance(n, ast.FunctionDef) and n.name == "do_POST"
        )
        routes = {}
        for node in ast.walk(do_post):
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
                continue
            left = node.test.left
            if not (isinstance(left, ast.Attribute) and left.attr == "path"):
                continue
            paths = [
                c.value for c in node.test.comparators
                if isinstance(c, ast.Constant) and isinstance(c.value, str)
            ]
            if not paths:
                continue
            routes[paths[0]] = sorted({
                call.func.attr for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Attribute)
                and call.func.value.attr == "bridge"
            })
        return {"routes": routes, "methods": methods}

    @classmethod
    def _audit(cls, source: str) -> tuple[list, dict]:
        """返回 (缺牙清单, 扫描器自证信息)。"""
        scan = cls._scan(source)
        methods = scan["methods"]
        gaps = []
        inventory = {}
        for route, targets in sorted(scan["routes"].items()):
            for target in targets:
                node = methods.get(target)
                if node is None:
                    gaps.append(f"{route} → {target}()：方法定位失败，扫描器无法判定")
                    continue
                guarded = cls._has_owner_session(node)
                gated = cls._has_run_task(node)
                inventory[f"{route} → {target}()"] = {
                    "run_task": gated, "owner_session": guarded}
                if gated and not guarded:
                    gaps.append(
                        f"{route} → {target}()：链上有 api.run_task 却没有 owner_session")
        eigenflux = methods.get("eigenflux")
        inventory["G4 · eigenflux() 本体"] = {
            "run_task": bool(eigenflux is not None and cls._has_run_task(eigenflux)),
            "owner_session": bool(
                eigenflux is not None and cls._has_owner_session(eigenflux)),
        }
        if eigenflux is None:
            gaps.append("G4 · eigenflux()：方法定位失败，扫描器无法判定")
        elif not cls._has_owner_session(eigenflux):
            gaps.append("G4 · /api/eigenflux → eigenflux()：缺 owner_session（点名漏口）")
        info = {
            "routes": len(scan["routes"]),
            "run_task_methods": sum(
                1 for node in methods.values() if cls._has_run_task(node)),
            "inventory": inventory,
        }
        return gaps, info

    # ------------------------------------------------------------------ 判据
    def test_owner_session_guard_covers_every_gated_post_route(self):
        gaps, info = self._audit(self.SOURCE)
        self.assertGreaterEqual(info["routes"], 9,
                                "扫描器没看全 POST 路由 → 扫描器自盲")
        self.assertGreaterEqual(info["run_task_methods"], 1,
                                "扫描器没看到任何 api.run_task → 扫描器自盲")
        self.assertEqual([], gaps, "owner_session 覆盖缺牙：\n" + "\n".join(gaps))
        self.assertTrue(info["inventory"]["G4 · eigenflux() 本体"]["owner_session"])

    def test_owner_session_scanner_has_discriminating_power(self):
        """负对照：把守卫换成同样合法缩进的 `if True:`，扫描器必须抓出来。"""
        mutated = self.SOURCE.replace(self.GUARD_MARKER, "if True:")
        self.assertNotEqual(self.SOURCE, mutated, "变异源未生效 → 负对照无效")
        real_gaps, _ = self._audit(self.SOURCE)
        blind_gaps, _ = self._audit(mutated)
        if real_gaps == blind_gaps:
            self.fail("SCANNER_BLIND：真实源码与变异源码结果相同，扫描器无判别力")
        self.assertEqual([], real_gaps)
        self.assertTrue(blind_gaps, "变异源码必须被抓出缺牙")
        self.assertTrue(any("eigenflux" in gap for gap in blind_gaps),
                        "变异后 /api/eigenflux 的缺牙必须被点名")

    def test_eigenflux_send_marks_owner_session_at_runtime(self):
        bridge = PS.HoloBridge()
        seen = []

        class _Client:
            enabled = True

            def send_message(self, content, **target):
                seen.append(PS.policy.is_trusted())
                return {"ok": True, "content": content, **target}

        bridge._eigenflux = _Client()
        before = PS.policy.is_trusted()
        self.assertFalse(before, "本用例要求进程未全局置位 GBT_OWNER_SESSION，"
                                 "否则正负对照失去判别性")
        result = bridge.eigenflux("send", {"content": "公开进展",
                                           "receiver_id": "agent-1"})
        after = PS.policy.is_trusted()
        self.assertTrue(result["ok"])
        self.assertEqual([True], seen, "出站发送必须发生在 owner_session 内")
        self.assertNotEqual(before, seen[0], "两组必须不同（正负对照）")
        self.assertFalse(after, "会话必须退出，信任态不许泄漏给下一次请求")


class SocialGateTests(unittest.TestCase):
    """A/C/E/F 判据固化 —— 三态门禁 + 未核验不许报「未登记」+ public 不越权。

    夹具：holo_pet/social.json（当前生产不存在）。setUp 备份、addCleanup 还原，
    跑完不留残留，绝不会把测试夹具留在盘上冒充配置。
    """

    CONFIG = HERE / "social.json"

    def setUp(self):
        self._backup = self.CONFIG.read_bytes() if self.CONFIG.is_file() else None
        self.addCleanup(self._restore)

    def _restore(self):
        if self._backup is None:
            if self.CONFIG.is_file():
                self.CONFIG.unlink()
        else:
            self.CONFIG.write_bytes(self._backup)

    def _status(self, flags=None, raw=None):
        if raw is not None:
            self.CONFIG.write_text(raw, encoding="utf-8")
        elif flags is None:
            if self.CONFIG.is_file():
                self.CONFIG.unlink()
        else:
            self.CONFIG.write_text(json.dumps(flags), encoding="utf-8")
        return PS.HoloBridge().social("status")

    def _dir_snapshot(self):
        return sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size)
                      for p in HERE.iterdir() if p.is_file())

    def test_A_missing_config_is_unknown_not_false(self):
        """A：没核到的东西不许写成「已证明为假」，更不许写成「通过」。

        2026-09-18 收窄（触手路由落地后）：本仓 sources.json 给每条渠道都声明了
        route=tentacle，而那四门是官方接口的闸 —— 在这条路由上它们根本不成立，
        于是没有 social.json 时这几格是「不适用」，不再是「未核验」。

        判据本身一格没松：known / verified / ok 仍然全为 False，hint 必须写明原因，
        且绝不许出现「已登记 / 已过审 / 已授权」这类断言 —— 那才是"把没核到的
        东西写成已证明为假"的反面：写成已证明为真。
        「未核验」那一支没有丢：test_C（配置读失败）继续卡着；老的三态支路由
        SocialRouteGateTests.R4 单独卡住。优先级是：配置读取失败 > 路由不适用。
        """
        status = self._status()
        self.assertFalse(status["config_present"])
        self.assertFalse(status["config_verified"])
        self.assertEqual("", status["config_error"])
        self.assertEqual("tentacle", status["route"])
        self.assertTrue(status["gates"], "sources.json 建卡时，门禁也要一起建")
        for gate in status["gates"]:
            self.assertIs(False, gate["known"])
            self.assertIs(False, gate["verified"])
            self.assertIs(False, gate["ok"])
            self.assertIs(False, gate["applicable"])
            self.assertIn("不适用", gate["hint"])
            for forbidden in ("已登记", "已过审", "已授权"):
                self.assertNotIn(forbidden, gate["hint"])
        self.assertFalse(status["connected"])
        self.assertFalse(status["publish_allowed"])
        self.assertFalse(status["public_allowed"])

    def test_B_empty_config_is_known_but_unregistered(self):
        """B：核到了，且核到了「没有」——这才允许说「未登记」。"""
        status = self._status(raw="{}")
        self.assertTrue(status["config_verified"])
        for gate in status["gates"]:
            self.assertIs(True, gate["known"])
            self.assertIs(False, gate["ok"])
        self.assertIn("未登记", status["gates"][0]["hint"])

    def test_C_broken_config_is_unknown_with_error(self):
        """C：文件在、内容不可信 → 属于核验失败，不许降级成「没配」。"""
        status = self._status(raw='{ "app_registered": true, }')
        self.assertTrue(status["config_present"])
        self.assertFalse(status["config_verified"])
        self.assertTrue(status["config_error"])
        for gate in status["gates"]:
            self.assertIs(False, gate["known"])
            self.assertIn("未核验", gate["hint"])

    def test_D_all_gates_true_opens_all_three_flags(self):
        """D：三门全通 → 三个标志全 True。

        与最初判据的一处差别（本仓主动改，理由在下面，可被否决）：
        三门全通但凭据未登记时，blocked_reason 不再为空、publish 也不再报
        gate_passed_impl_missing，而是报 credential_missing。
        理由：没有令牌，链路即使实现了也发不出去；把这种状态说成"只差实现"，
        是拿一个软缺口盖住一个硬缺口。D 的三条状态判据本身一条没动。
        """
        self._status(flags={"app_registered": True, "scope_audited": True,
                            "account_authorized": True})
        status = PS.HoloBridge().social("status")
        self.assertIs(True, status["connected"])
        self.assertIs(True, status["publish_allowed"])
        self.assertIs(True, status["public_allowed"])
        # 新增：门禁通了不等于能发 —— publish_ready 还要求凭据与探针都过。
        self.assertIs(False, status["publish_ready"])
        self.assertEqual("unknown", status["capability_probe"]["status"])
        self.assertIn("凭据未登记", status["blocked_reason"])
        publish = PS.HoloBridge().social("publish")
        self.assertIs(False, publish["ok"])
        self.assertEqual("credential_missing", publish["gate"])

    def test_E_public_never_outruns_app_registration(self):
        """E 回归项：改前 public_allowed = scope and auth，漏算 app_registered。

        该洞会让「应用未登记但权限过审」被报成可公开发布。修后 public 是
        publish 的子集，缺任一门前置都必须是 False。
        """
        status = self._status(flags={"scope_audited": True,
                                     "account_authorized": True})
        by_id = {gate["id"]: gate for gate in status["gates"]}
        self.assertIs(True, by_id["scope"]["ok"])
        self.assertIs(True, by_id["auth"]["ok"])
        self.assertIs(False, by_id["app"]["ok"])
        self.assertIs(False, status["publish_allowed"])
        self.assertIs(False, status["public_allowed"])

    def test_F_publish_is_inert_and_makes_no_outbound_call(self):
        """F：门禁未通时 publish 必须零副作用、零出站连接。

        「无出站」用仪器判，不用眼看：把 socket.connect / connect_ex 换成
        记录并抛错的桩，任何 TCP 出站都会把测试直接打红。
        """
        self._status(flags={"scope_audited": True, "account_authorized": True})
        bridge = PS.HoloBridge()
        before = self._dir_snapshot()
        opened = []

        def _refuse(*args, **kwargs):
            opened.append(args)
            raise AssertionError("发布闸未通却发起了出站连接")

        with mock.patch.object(socket.socket, "connect", _refuse), \
                mock.patch.object(socket.socket, "connect_ex", _refuse):
            result = bridge.social("publish")

        self.assertIs(False, result["ok"])
        self.assertEqual("unconnected", result["gate"])
        self.assertEqual([], opened, "无出站请求")
        self.assertEqual(before, self._dir_snapshot(), "无副作用（面板目录未变）")

    def test_G_unknown_flag_config_still_gates_off(self):
        """附：认不出的配置不许「沉默放行」——顶层不是对象按核验失败处理。"""
        status = self._status(raw="[1, 2, 3]")
        self.assertTrue(status["config_present"])
        self.assertFalse(status["config_verified"])
        self.assertEqual("social.json 顶层不是对象", status["config_error"])
        self.assertFalse(status["publish_allowed"])


class SocialPlatformShapeTests(unittest.TestCase):
    """多平台形状：一行数据一个平台；歧义一律 fail-closed，不许替调用方猜。

    夹具仍是 holo_pet/social.json，setUp 备份、addCleanup 还原。
    """

    CONFIG = HERE / "social.json"

    def setUp(self):
        self._backup = self.CONFIG.read_bytes() if self.CONFIG.is_file() else None
        self.addCleanup(self._restore)

    def _restore(self):
        if self._backup is None:
            if self.CONFIG.is_file():
                self.CONFIG.unlink()
        else:
            self.CONFIG.write_bytes(self._backup)

    def _status(self, payload):
        self.CONFIG.write_text(json.dumps(payload), encoding="utf-8")
        return PS.HoloBridge().social("status")

    def test_H_each_platform_gets_its_own_gates(self):
        """H：逐平台一组门禁；顶层只描述焦点平台，绝不跨平台聚合。"""
        status = self._status({
            "focus": "youtube",
            "platforms": {
                "tiktok": {"app_registered": True, "scope_audited": True,
                           "account_authorized": True},
                "youtube": {"app_registered": True},
            },
        })
        self.assertEqual("multi", status["schema"])
        self.assertEqual(2, status["platform_count"])
        by_id = {block["id"]: block for block in status["platforms"]}
        self.assertEqual({"tiktok", "youtube"}, set(by_id))
        self.assertIs(True, by_id["tiktok"]["publish_allowed"])
        self.assertIs(False, by_id["youtube"]["publish_allowed"])
        self.assertEqual("youtube", status["focus"])
        self.assertEqual("YouTube Shorts", status["focus_label"])
        # 焦点是 youtube（未过审）→ 顶层必须是 False，不许被 tiktok 的绿灯顶上去
        self.assertIs(False, status["connected"])
        self.assertIs(False, status["publish_allowed"])
        self.assertIs(False, status["public_allowed"])
        # 兼容层：恰好三条声明门禁，键集与旧前端一致
        self.assertEqual(["app", "scope", "auth"],
                         [gate["id"] for gate in status["gates"]])
        # 平台块里五条：三条声明门禁 + 凭据登记 + 能力探测
        self.assertEqual(["app", "scope", "auth", "cred", "probe"],
                         [gate["id"] for gate in by_id["tiktok"]["gates"]])

    def test_I_publish_without_platform_is_refused_when_ambiguous(self):
        """I：声明了多个平台却不指定 platform → 一律不放行。"""
        self._status({"platforms": {
            "tiktok": {"app_registered": True, "scope_audited": True,
                       "account_authorized": True},
            "youtube": {"app_registered": True, "scope_audited": True,
                        "account_authorized": True},
        }})
        result = PS.HoloBridge().social("publish")
        self.assertIs(False, result["ok"])
        self.assertEqual("platform_required", result["gate"])
        self.assertEqual(["tiktok", "youtube"], result["declared"])

    def test_J_named_platform_cannot_borrow_another_platform_gates(self):
        """J 核心反假绿：youtube 全通，其绿灯一个字节都不许借给 tiktok。"""
        self._status({"platforms": {
            "tiktok": {"app_registered": True},
            "youtube": {"app_registered": True, "scope_audited": True,
                        "account_authorized": True},
        }})
        blocked = PS.HoloBridge().social("publish", {"platform": "tiktok"})
        self.assertIs(False, blocked["ok"])
        self.assertEqual("unconnected", blocked["gate"])
        self.assertEqual("tiktok", blocked["platform"])
        other = PS.HoloBridge().social("publish", {"platform": "youtube"})
        self.assertEqual("credential_missing", other["gate"])
        self.assertEqual("youtube", other["platform"])

    def test_K_undeclared_platform_is_refused_not_created(self):
        """K：未声明的平台不许被"临时造出来"。"""
        self._status({"platforms": {"tiktok": {
            "app_registered": True, "scope_audited": True,
            "account_authorized": True}}})
        result = PS.HoloBridge().social("publish", {"platform": "douyin"})
        self.assertEqual("unknown_platform", result["gate"])
        self.assertEqual(["tiktok"], result["declared"])

    def test_L_unknown_platform_id_is_honest_about_spec(self):
        """L：表里没有的平台不许猜规格 —— spec_known=False 且字段留空。"""
        status = self._status({"platforms": {"myspace": {"label": "MySpace"}}})
        block = status["platforms"][0]
        self.assertIs(False, block["spec_known"])
        self.assertIsNone(block["official_api"])
        self.assertEqual("", block["delivery"])
        self.assertIsNone(block["daily_limit"])
        self.assertEqual("MySpace", block["label"])
        self.assertIn("没有探针定义", block["capability_probe"]["reason"])

    def test_M_platform_without_official_api_is_named_as_such(self):
        """M：无官方发布接口的平台要如实点名，而不是静默失败。"""
        status = self._status({"platforms": {"wechat_channels": {
            "app_registered": True, "scope_audited": True,
            "account_authorized": True, "credential_registered": True}}})
        block = status["platforms"][0]
        self.assertIs(False, block["official_api"])
        self.assertIs(False, block["publish_ready"])
        self.assertIn("没有官方发布接口", block["capability_probe"]["reason"])
        result = PS.HoloBridge().social("publish")
        self.assertEqual("capability_unverified", result["gate"])

    def test_N_platforms_must_be_an_object(self):
        """N：platforms 形状不对 → 整份配置按核验失败，不许降级成"没配"。"""
        status = self._status({"platforms": ["tiktok"]})
        self.assertTrue(status["config_present"])
        self.assertFalse(status["config_verified"])
        self.assertTrue(status["config_error"])
        self.assertEqual("unverified", status["schema"])
        self.assertEqual([], status["platforms"])
        self.assertFalse(status["publish_allowed"])

    def test_O_one_broken_platform_voids_the_whole_config(self):
        """O：不许静默跳过坏平台 —— 只报好平台等于伪造一份更绿的盘。"""
        status = self._status({"platforms": {
            "tiktok": {"app_registered": True},
            "youtube": "yes",
        }})
        self.assertFalse(status["config_verified"])
        self.assertIn("youtube", status["config_error"])
        self.assertEqual([], status["platforms"])
        self.assertFalse(status["publish_allowed"])

    def test_P_empty_platform_map_declares_nothing(self):
        """P：platforms 为空对象 = 没声明平台 → 不放行，且成因要说清。"""
        status = self._status({"platforms": {}})
        self.assertTrue(status["config_verified"])
        self.assertEqual("multi", status["schema"])
        self.assertEqual(0, status["platform_count"])
        self.assertFalse(status["publish_allowed"])
        self.assertIn("没有声明任何平台", status["blocked_reason"])
        result = PS.HoloBridge().social("publish")
        self.assertEqual("no_platform_declared", result["gate"])

    def test_Q_publish_ready_needs_a_real_probe(self):
        """Q 核心反假绿：四布尔全 true 也换不来 publish_ready。"""
        status = self._status({"platforms": {"tiktok": {
            "app_registered": True, "scope_audited": True,
            "account_authorized": True, "credential_registered": True}}})
        block = status["platforms"][0]
        self.assertIs(True, block["publish_allowed"])
        self.assertIs(True, block["credential_present"])
        self.assertIs(False, block["publish_ready"],
                        "本地布尔可被手改，只有真探针能证实能力")
        self.assertEqual("unknown", block["capability_probe"]["status"])


    def test_R_fresh_probe_is_the_only_route_to_publish_ready(self):
        """R：探针新鲜通过 —— 唯一能让 publish_ready 变 True 的路。"""
        now = time.time()
        status = self._status({"platforms": {"tiktok": {
            "app_registered": True, "scope_audited": True,
            "account_authorized": True, "credential_registered": True,
            "capability_probe": {"status": "ok", "checked_at": now - 5}}}})
        block = status["platforms"][0]
        self.assertEqual("ok", block["capability_probe"]["status"])
        self.assertIs(True, block["capability_probe"]["known"])
        self.assertIs(True, block["publish_ready"])
        probe_gate = [g for g in block["gates"] if g["id"] == "probe"][0]
        self.assertIs(True, probe_gate["ok"])
        self.assertIs(True, probe_gate["known"])
        self.assertIn("能力已证实", probe_gate["hint"])
        result = PS.HoloBridge().social("publish")
        self.assertEqual("gate_passed_impl_missing", result["gate"])
        self.assertIs(False, result["implemented"])

    def test_S_expired_probe_degrades_to_unverified_only(self):
        """S：探测过期 → 只降探针那一格为「未核验（探测过期）」，不连坐。"""
        now = time.time()
        status = self._status({"platforms": {"tiktok": {
            "app_registered": True, "scope_audited": True,
            "account_authorized": True, "credential_registered": True,
            "capability_probe": {"status": "ok", "checked_at": now - 43205}}}})
        block = status["platforms"][0]
        self.assertEqual("stale", block["capability_probe"]["status"])
        self.assertIs(False, block["capability_probe"]["known"])
        self.assertGreaterEqual(block["capability_probe"]["checked_age_seconds"], 43205)
        self.assertIs(False, block["publish_ready"])
        probe_gate = [g for g in block["gates"] if g["id"] == "probe"][0]
        self.assertIs(False, probe_gate["known"], "过期属于未核验，不是失败")
        self.assertIn("未核验（探测过期）", probe_gate["hint"])
        # 信号卡片照常显示：声明三门仍然全通，降级只发生在探针那一格
        self.assertIs(True, block["publish_allowed"])
        self.assertEqual([True, True, True],
                         [g["ok"] for g in block["gates"] if g["id"] in ("app", "scope", "auth")])
        self.assertIn("能力未核验（stale）", status["blocked_reason"])
        result = PS.HoloBridge().social("publish")
        self.assertEqual("capability_unverified", result["gate"])

    def test_T_probe_without_timestamp_counts_as_expired(self):
        """T：没有时间戳的"通过"不作数 —— 它无法被证伪，也无法被证实。"""
        status = self._status({"platforms": {"tiktok": {
            "app_registered": True, "scope_audited": True,
            "account_authorized": True, "credential_registered": True,
            "capability_probe": {"status": "ok"}}}})
        probe = status["platforms"][0]["capability_probe"]
        self.assertEqual("stale", probe["status"])
        self.assertIn("没有可解析的时间戳", probe["reason"])
        self.assertIs(False, status["platforms"][0]["publish_ready"])

    def test_U_failed_probe_stays_unknown_with_detail(self):
        """U：上次探测未通过 → unknown，且必须带出原因。"""
        status = self._status({"platforms": {"tiktok": {
            "app_registered": True, "scope_audited": True,
            "account_authorized": True, "credential_registered": True,
            "capability_probe": {"status": "fail", "detail": "HTTP 401"}}}})
        probe = status["platforms"][0]["capability_probe"]
        self.assertEqual("unknown", probe["status"])
        self.assertIn("HTTP 401", probe["reason"])

    def test_V_probe_ttl_is_configurable_and_bad_values_fall_back(self):
        """V：TTL 可配；0/负数/字符串一律回退默认，不许当"永不过期"。"""
        now = time.time()
        payload = {"probe_ttl_seconds": 30, "platforms": {"tiktok": {
            "app_registered": True, "scope_audited": True,
            "account_authorized": True, "credential_registered": True,
            "capability_probe": {"status": "ok", "checked_at": now - 300}}}}
        status = self._status(payload)
        self.assertEqual(30, status["probe_ttl_seconds"])
        self.assertEqual("stale", status["platforms"][0]["capability_probe"]["status"])

        for bad in (0, -1, "3600", None):
            payload["probe_ttl_seconds"] = bad
            fallback = self._status(payload)
            self.assertEqual(43200, fallback["probe_ttl_seconds"],
                             "非法 TTL %r 必须回退默认" % (bad,))
            self.assertEqual("ok", fallback["platforms"][0]["capability_probe"]["status"])

    def test_W_probe_shape_must_be_an_object(self):
        """W：capability_probe 形状不对 → 整份配置按核验失败。"""
        status = self._status({"platforms": {"tiktok": {
            "app_registered": True, "capability_probe": "ok"}}})
        self.assertFalse(status["config_verified"])
        self.assertIn("capability_probe", status["config_error"])
        self.assertEqual([], status["platforms"])
        self.assertFalse(status["publish_allowed"])


if __name__ == "__main__":
    unittest.main()


class SocialProbeStateTests(unittest.TestCase):
    """P1-P5：探针四态 —— 「已登记 · 未探测」既不是「未登记」，也不是绿。

    探针落点 = state/probe/<id>.json（B 定稿）。每个用例自建夹具、addCleanup 还原。
    """

    CONFIG = HERE / "social.json"
    PROBE_DIR = HERE.parent / "state" / "probe"
    FULL_DECL = {"app_registered": True, "scope_audited": True,
                 "account_authorized": True, "credential_registered": True}

    def setUp(self):
        self._cfg = self.CONFIG.read_bytes() if self.CONFIG.is_file() else None
        self.addCleanup(self._restore_cfg)
        self._probes = {}
        self.addCleanup(self._restore_probes)
        self.PROBE_DIR.mkdir(parents=True, exist_ok=True)

    def _restore_cfg(self):
        if self._cfg is None:
            if self.CONFIG.is_file():
                self.CONFIG.unlink()
        else:
            self.CONFIG.write_bytes(self._cfg)

    def _restore_probes(self):
        for pid, blob in self._probes.items():
            path = self.PROBE_DIR / ("%s.json" % pid)
            if blob is None:
                if path.is_file():
                    path.unlink()
            else:
                path.write_bytes(blob)

    def _write_config(self, payload):
        self.CONFIG.write_text(json.dumps(payload), encoding="utf-8")

    def _write_probe(self, pid, blob):
        path = self.PROBE_DIR / ("%s.json" % pid)
        if pid not in self._probes:
            self._probes[pid] = path.read_bytes() if path.is_file() else None
        path.write_text(json.dumps(blob), encoding="utf-8")

    def _first(self):
        return PS.HoloBridge().social("status")["platforms"][0]

    def test_P1_declared_not_probed_is_unprobed_not_unregistered(self):
        """P1：登记了、没探过 -> 「已登记 · 未探测」；不许说「未登记」，更不许绿。"""
        self._write_config({"platforms": {"tiktok": dict(self.FULL_DECL)}})
        block = self._first()
        self.assertEqual("unprobed", block["probe_state"])
        self.assertEqual("已登记 · 未探测", block["status_label"])
        gate = block["gates"][-1]
        self.assertIn("已登记 · 未探测", gate["hint"])
        self.assertNotIn("未登记：", gate["hint"])
        self.assertIs(False, gate["known"])
        self.assertIs(False, gate["ok"])
        self.assertIs(False, block["publish_ready"])

    def test_P2_fresh_disk_probe_is_the_only_green(self):
        """P2：state/probe 落盘且新鲜 -> 唯一允许为绿的状态。"""
        self._write_config({"platforms": {"tiktok": dict(self.FULL_DECL)}})
        self._write_probe("tiktok", {"status": "ok", "checked_at": time.time()})
        block = self._first()
        self.assertEqual("state/probe", block["probe_source"])
        self.assertEqual("ok", block["probe_state"])
        self.assertEqual("已探测 · 通过", block["status_label"])
        self.assertIs(True, block["gates"][-1]["known"])
        self.assertTrue(block["publish_ready"])

    def test_P3_stale_disk_probe_downgrades_to_unverified(self):
        """P3：落盘但过期 -> 降级为未核验，不许连坐、也不许当失败。"""
        self._write_config({"platforms": {"tiktok": dict(self.FULL_DECL)}})
        self._write_probe("tiktok", {"status": "ok", "checked_at": time.time() - 43205})
        block = self._first()
        self.assertEqual("stale", block["probe_state"])
        self.assertEqual("已登记 · 探测过期", block["status_label"])
        self.assertIs(False, block["gates"][-1]["known"])
        self.assertIn("未核验（探测过期）", block["gates"][-1]["hint"])
        self.assertIs(False, block["publish_ready"])
        for gate in block["gates"][:-1]:
            self.assertIs(True, gate["known"], "过期只降探针那一格，不连坐")

    def test_P4_disk_probe_wins_over_inline_field(self):
        """P4：两处都有 -> 落盘赢。内嵌说新鲜、落盘说过期，结果必须是过期。"""
        self._write_config({"platforms": {"tiktok": dict(
            self.FULL_DECL,
            capability_probe={"status": "ok", "checked_at": time.time()})}})
        self._write_probe("tiktok", {"status": "ok", "checked_at": time.time() - 43205})
        block = self._first()
        self.assertEqual("state/probe", block["probe_source"])
        self.assertEqual("stale", block["probe_state"])

    def test_P5_sources_json_backs_the_registry_without_social_json(self):
        """P5：没有 social.json 时，sources.json 的 channels 兜底建卡，且一律未探测。"""
        if self.CONFIG.is_file():
            self.CONFIG.unlink()
        status = PS.HoloBridge().social("status")
        self.assertEqual("sources", status["schema"])
        by_id = {block["id"]: block for block in status["platforms"]}
        self.assertIn("tiktok", by_id, "sources.json 里声明了 tiktok，就必须建卡")
        self.assertEqual("已登记 · 未探测", by_id["tiktok"]["status_label"])
        self.assertEqual("unprobed", by_id["tiktok"]["probe_state"])
        for block in status["platforms"]:
            self.assertIs(False, block["publish_ready"])
            self.assertNotEqual("ok", block["probe_state"])
            self.assertNotEqual("未登记", block["status_label"])
        self.assertFalse(status["publish_ready"])

    def test_P6_default_ttl_is_twelve_hours(self):
        """P6：探针文件在、但 checked_at 超 12h -> 探测过期（未核验），不是绿、也不是失败。"""
        self._write_config({"platforms": {"tiktok": dict(self.FULL_DECL)}})
        self.assertEqual(43200, PS.HoloBridge().social("status")["probe_ttl_seconds"])

        self._write_probe("tiktok", {"status": "ok", "checked_at": time.time() - 43195})
        fresh = self._first()
        self.assertEqual("ok", fresh["probe_state"], "11h59m55s 前探的，仍在有效期内")
        self.assertTrue(fresh["publish_ready"])

        self._write_probe("tiktok", {"status": "ok", "checked_at": time.time() - 43205})
        old = self._first()
        self.assertEqual("stale", old["probe_state"], "超 12h 5s -> 过期")
        self.assertEqual("已登记 · 探测过期", old["status_label"])
        self.assertIs(False, old["publish_ready"], "过期不许为绿")
        gate = old["gates"][-1]
        self.assertIs(False, gate["known"], "过期是未核验，不是失败")
        self.assertIn("未核验（探测过期）", gate["hint"])
        for g in old["gates"][:-1]:
            self.assertIs(True, g["known"], "过期只降探针那一格，不连坐")


class SocialRouteGateTests(unittest.TestCase):
    """R1-R7：路由分流 + 意愿声明。

    R1-R4 = 路由分流：触手路由的闸必须读成「不适用」，不是「未做」。
    R5-R7 = `enabled`：登记表的意愿声明，**只显示，不参与门禁计算** ——
            核心判据不是"能不能印出未启用"，而是"印了之后门禁那一串一个字节都不许变"。

    夹具：holo_pet/social.json 与仓库根的 sources.json 都会被临时改写，
    setUp 备份、addCleanup 还原，跑完不留残留。
    """

    CONFIG = HERE / "social.json"
    SOURCES = ROOT / "sources.json"
    ROW = {"id": "tiktok", "name": "TikTok", "official_api": True,
           "route": "tentacle", "unattended_allowed": False}

    def setUp(self):
        self._cfg = self.CONFIG.read_bytes() if self.CONFIG.is_file() else None
        self._src = self.SOURCES.read_bytes() if self.SOURCES.is_file() else None
        self.addCleanup(self._restore)
        if self.CONFIG.is_file():
            self.CONFIG.unlink()

    def _restore(self):
        for path, blob in ((self.CONFIG, self._cfg), (self.SOURCES, self._src)):
            if blob is None:
                if path.is_file():
                    path.unlink()
            else:
                path.write_bytes(blob)

    def _sources(self, rows):
        """只换 channels 一节，promo / research / open 原样保留。"""
        payload = json.loads(self._src.decode("utf-8"))
        payload["channels"] = rows
        self.SOURCES.write_text(json.dumps(payload, ensure_ascii=False),
                                encoding="utf-8")
        return PS.HoloBridge().social("status")

    def _block(self, rows=None):
        return self._sources(rows if rows is not None else [dict(self.ROW)])["platforms"][0]

    def test_R1_tentacle_route_marks_official_gates_not_applicable(self):
        """R1：触手路由下官方四门是「不适用」—— 不是未核验、更不是通过。"""
        block = self._block()
        self.assertEqual("tentacle", block["route"])
        self.assertEqual("本机触手", block["route_label"])
        self.assertTrue(block["route_note"], "路由的代价要写进响应，不能只活在文档里")
        by_id = {gate["id"]: gate for gate in block["gates"]}
        for gid in ("app", "scope", "auth", "cred"):
            gate = by_id[gid]
            self.assertIs(False, gate["applicable"], "官方闸在触手路由上不适用")
            self.assertIs(False, gate["ok"], "不适用绝不许写成通过")
            self.assertIs(False, gate["known"])
            self.assertIs(False, gate["verified"])
            self.assertIn("不适用", gate["hint"])
            self.assertNotIn("未登记：", gate["hint"],
                             "别把人指去补一件这条路由上根本不存在的事")
        self.assertFalse(block["publish_allowed"])
        self.assertFalse(block["publish_ready"])
        self.assertEqual("unprobed", block["probe_state"])
        self.assertIn("登录会话", by_id["probe"]["hint"],
                      "触手路由的探针对象是登录会话，不是令牌有效期")

    def test_R2_unattended_splits_three_states_and_never_opens(self):
        """R2：无人值守分三态，且永远不开放 —— 声明 true 也只报「不启用」。"""
        by_gate = lambda block: {gate["id"]: gate for gate in block["gates"]}

        undeclared = dict(self.ROW)
        undeclared.pop("unattended_allowed")
        gate = by_gate(self._block([undeclared]))["unattended"]
        self.assertIs(False, gate["known"], "登记表没写 -> 未声明，不是已证明为假")
        self.assertIs(False, gate["ok"])
        self.assertIn("未声明", gate["hint"])

        closed = self._block([dict(self.ROW)])
        gate = by_gate(closed)["unattended"]
        self.assertIs(True, gate["known"])
        self.assertIs(False, gate["ok"])
        self.assertIn("需要人在场", gate["hint"])
        self.assertIs(False, closed["unattended_enabled"])
        self.assertFalse(closed["publish_ready"])

        opened = self._block([dict(self.ROW, unattended_allowed=True)])
        gate = by_gate(opened)["unattended"]
        self.assertIs(True, gate["known"])
        self.assertIs(False, gate["ok"], "声明为开放也不启用 —— 这是不做，不是待办")
        self.assertIn("本舱区不启用", gate["hint"])
        self.assertIs(False, opened["unattended_enabled"])
        self.assertFalse(opened["publish_ready"], "无人值守没开，就不许报全绿")

    def test_R3_publish_on_tentacle_route_does_not_point_at_the_official_steps(self):
        """R3：触手路由下被拒时，不许再让人去补那三步官方前置。"""
        status = self._sources([dict(self.ROW)])
        self.assertIn("触手路由", status["blocked_reason"])
        self.assertNotIn("三步前置", status["blocked_reason"])

        result = PS.HoloBridge().social("publish")
        self.assertIs(False, result["ok"])
        self.assertEqual("tentacle_not_implemented", result["gate"])
        self.assertEqual("tentacle", result["route"])
        self.assertIs(False, result["unattended_enabled"])
        self.assertIn("需要人在场", result["error"])
        self.assertNotIn("权限过审", result["error"])

    def test_R4_unrouted_row_keeps_the_old_three_state_path(self):
        """R4 回归：没声明 route 的行，四门仍走老三态（未核验），不许被分流污染。"""
        row = dict(self.ROW)
        row.pop("route")
        block = self._block([row])
        self.assertEqual("", block["route"])
        self.assertEqual("", block["route_label"])
        by_id = {gate["id"]: gate for gate in block["gates"]}
        self.assertNotIn("unattended", by_id, "没声明路由就不该多出无人值守那一格")
        self.assertIs(True, by_id["app"]["applicable"])
        self.assertIs(False, by_id["app"]["known"])
        self.assertIn("未核验", by_id["app"]["hint"])
        self.assertFalse(block["publish_ready"])

    def test_R5_disabled_row_only_adds_a_label_and_never_touches_gates(self):
        """R5：显式 false -> 多一枚「未启用」，而门禁那一串必须逐字不变。"""
        base = self._block([dict(self.ROW)])
        off = self._block([dict(self.ROW, enabled=False)])

        self.assertEqual(base["gates"], off["gates"], "不参与门禁计算：门禁必须逐字相同")
        for key in ("publish_allowed", "publish_ready", "probe_state", "probe_source",
                    "route", "route_label", "unattended_allowed", "unattended_enabled",
                    "status_label", "credential_present", "spec_known"):
            self.assertEqual(base[key], off[key], "字段 %s 不许被 enabled 改动" % key)

        self.assertTrue(off["enabled_declared"])
        self.assertIs(False, off["enabled"])
        self.assertEqual("未启用", off["enabled_label"])

        self.assertFalse(base["enabled_declared"], "没写就不许读成写了")
        self.assertEqual("", base["enabled_label"], "未声明不许印「未启用」，也不许印「已启用」")

    def test_R6_declared_true_stays_silent(self):
        """R6：显式 true -> 不印任何标记。「已启用」在 15 张卡上是零信息量的噪声。"""
        base = self._block([dict(self.ROW)])
        on = self._block([dict(self.ROW, enabled=True)])
        self.assertTrue(on["enabled_declared"])
        self.assertIs(True, on["enabled"])
        self.assertEqual("", on["enabled_label"])
        self.assertEqual(base["gates"], on["gates"])
        self.assertFalse(base["publish_ready"], "印不印标记都不许把它变成绿")

    def test_R7_disabled_still_reports_its_own_facts(self):
        """R7：未启用 != 没这回事 —— 探针、路由、无人值守那一格照报，不许被吞掉。"""
        off = self._block([dict(self.ROW, enabled=False)])
        by_id = {gate["id"]: gate for gate in off["gates"]}
        self.assertIn("probe", by_id, "未启用不许把探针那一格藏起来")
        self.assertIn("unattended", by_id)
        self.assertEqual("unprobed", off["probe_state"])
        self.assertEqual("tentacle", off["route"])
        self.assertEqual("本机触手", off["route_label"])


class _ResearchFixture:
    """RG 系列的共用夹具：临时改写 sources.json / state/runs/ / state/last_seen.json。

    只放夹具、不放测试 —— 两个 TestCase 都从这里继承，避免两份真相。
    子类必须提供 SOURCES / RUNS / WATERMARK / ROWS 四个类属性。
    """

    """RG1-RG9：判据 D ——「research 源某次采集失败」（2026-09-18 风哥口径）。

    核心不是"能不能印出失败"，而是三条不许：

      RG2/RG8  失败不许退化成"没这回事"：源还在，且带出上一次成功水位（失败不清水位）；
      RG3      失败不许连坐：别的信源结论逐字不变；
      RG1/RG4/RG5/RG6  没采过 / 读不出来 / 未启用 / 过期，四者互不冒充，也都不许当绿。

    夹具：仓库根的 sources.json、state/runs/、state/last_seen.json 临时改写，
    setUp 备份、addCleanup 还原，跑完不留残留。
    """

    SOURCES = ROOT / "sources.json"
    RUNS = ROOT / "state" / "runs"
    WATERMARK = ROOT / "state" / "last_seen.json"

    ROWS = [
        {"id": "arxiv", "name": "arXiv", "kind": "paper", "enabled": True,
         "transport": "http_json", "endpoint": "https://export.arxiv.org/api/query",
         "probe": "arxiv_api_ping", "interval": "daily", "limit_per_run": 50},
        {"id": "hackernews", "name": "Hacker News", "kind": "heat", "enabled": True,
         "interval": "daily"},
        {"id": "github", "name": "GitHub Trending", "kind": "code", "enabled": True,
         "interval": "daily"},
        {"id": "jobs", "name": "招聘信号", "kind": "money_demand", "enabled": False,
         "interval": "weekly"},
    ]

    def setUp(self):
        self._sources = self.SOURCES.read_bytes() if self.SOURCES.is_file() else None
        self.addCleanup(self._restore_sources)
        self._watermark = self.WATERMARK.read_bytes() if self.WATERMARK.is_file() else None
        self.addCleanup(self._restore_watermark)
        self._runs = {}
        self.addCleanup(self._restore_runs)
        self.RUNS.mkdir(parents=True, exist_ok=True)
        # 运行数据必须隔离：目录里**预先存在**的真实结局文件也要先搬走，跑完放回。
        # 否则「采集器真的跑过一次」会让 RG1/RG8/RG12/RG13 假红 ——
        # 红的不是代码，是夹具没关上门（2026-09-18 实证）。
        for stale in sorted(self.RUNS.glob("*.json")):
            self._runs.setdefault(stale.stem, stale.read_bytes())
            stale.unlink()
        if self.WATERMARK.is_file():
            self.WATERMARK.unlink()  # 水位归零；原字节已在 _watermark，cleanup 会放回
        self._write_json(self.SOURCES, {"version": 1, "research": self.ROWS})

    def _restore_sources(self):
        if self._sources is None:
            if self.SOURCES.is_file():
                self.SOURCES.unlink()
        else:
            self.SOURCES.write_bytes(self._sources)

    def _restore_watermark(self):
        if self._watermark is None:
            if self.WATERMARK.is_file():
                self.WATERMARK.unlink()
        else:
            self.WATERMARK.write_bytes(self._watermark)

    def _restore_runs(self):
        for sid, blob in self._runs.items():
            path = self.RUNS / ("%s.json" % sid)
            if blob is None:
                if path.is_file():
                    path.unlink()
            else:
                path.write_bytes(blob)

    def _write_json(self, path, payload):
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _write_run(self, sid, doc):
        path = self.RUNS / ("%s.json" % sid)
        if sid not in self._runs:
            self._runs[sid] = path.read_bytes() if path.is_file() else None
        if isinstance(doc, str):
            path.write_text(doc, encoding="utf-8")
        else:
            self._write_json(path, doc)

    def _write_watermark(self, mapping):
        self._write_json(self.WATERMARK, mapping)

    def _status(self):
        return PS.HoloBridge().research("status")

    def _by_id(self):
        status = self._status()
        return {block["id"]: block for block in status["sources"]}, status



class ResearchSourceStateTests(_ResearchFixture, unittest.TestCase):
    def test_RG1_declared_never_collected_is_not_failed_and_not_green(self):
        """RG1：本机空 state —— 3 个「已登记 · 未采集」+ 1 个「未启用」；无绿、无失败。"""
        by_id, status = self._by_id()
        self.assertTrue(status["sources_verified"])
        for sid in ("arxiv", "hackernews", "github"):
            block = by_id[sid]
            self.assertEqual("never_run", block["state"])
            self.assertEqual("已登记 · 未采集", block["status_label"])
            self.assertNotIn("失败", block["status_label"], "没采过 != 失败")
            self.assertNotEqual("ok", block["state"], "没采过 != 绿")
        self.assertEqual("disabled", by_id["jobs"]["state"])
        self.assertEqual(0, status["failed_count"])
        self.assertEqual(3, status["never_run_count"])
        self.assertEqual(1, status["disabled_count"])
        self.assertIn("已登记 · 未采集", status["summary"])

    def test_RG2_failed_run_keeps_the_old_watermark(self):
        """RG2：某次采集失败 —— 显示失败，且上一次成功的水位一个字都不许丢。"""
        now = time.time()
        self._write_watermark({"arxiv": now - 3 * 86400})
        self._write_run("arxiv", {"id": "arxiv", "outcome": "failed",
                                  "finished_at": now - 60, "http": 406,
                                  "reason": "SourceThrottled: 406 from export.arxiv.org",
                                  "attempts": 2, "items": 0})
        by_id, status = self._by_id()
        block = by_id["arxiv"]
        self.assertEqual("failed", block["state"])
        self.assertEqual("最近采集 · 失败", block["status_label"])
        self.assertEqual(406, block["http"])
        self.assertIn("SourceThrottled", block["reason"])
        self.assertEqual(2, block["attempts"])
        self.assertTrue(block["watermark_present"], "失败不许把水位抹掉")
        self.assertGreaterEqual(block["last_ok_age_seconds"], 3 * 86400)
        self.assertLess(block["last_ok_age_seconds"], 3 * 86400 + 300)
        self.assertIn("上一次成功在 3 天 前", block["hint"])
        self.assertIn("失败不清水位", block["hint"])
        self.assertEqual(1, status["failed_count"])

    def test_RG3_one_failed_source_does_not_touch_the_others(self):
        """RG3：不连坐 —— 别的信源结论逐字不变，只有失败那个源换态。"""
        before = self._status()
        baseline = {b["id"]: json.dumps(b, ensure_ascii=False, sort_keys=True)
                    for b in before["sources"] if b["id"] != "arxiv"}
        self._write_run("arxiv", {"id": "arxiv", "outcome": "failed", "http": 406,
                                  "finished_at": time.time() - 10})
        after = self._status()
        for block in after["sources"]:
            if block["id"] == "arxiv":
                continue
            self.assertEqual(baseline[block["id"]],
                             json.dumps(block, ensure_ascii=False, sort_keys=True),
                             "别的研究源被连坐了")
        self.assertEqual(0, before["failed_count"])
        self.assertEqual(1, after["failed_count"])

    def test_RG4_broken_run_file_is_unknown_even_for_a_disabled_row(self):
        """RG4：状态文件坏掉 -> 「不可信」；优先级压过 enabled:false。"""
        self._write_run("arxiv", "{ this is not json")
        by_id, _ = self._by_id()
        self.assertEqual("unreadable", by_id["arxiv"]["state"])
        self.assertEqual("状态文件不可信", by_id["arxiv"]["status_label"])
        self.assertTrue(by_id["arxiv"]["run_error"])
        self.assertNotEqual("never_run", by_id["arxiv"]["state"], "坏文件不许退回「未采集」")

        self._write_json(self.SOURCES, {
            "version": 1,
            "research": [dict(row, enabled=False) if row["id"] == "arxiv" else row
                         for row in self.ROWS],
        })
        by_id, _ = self._by_id()
        self.assertEqual("unreadable", by_id["arxiv"]["state"],
                         "读不出来是本机事实，不许被「未启用」盖过")

    def test_RG5_disabled_row_is_not_a_failure_but_still_reports_facts(self):
        """RG5：未启用 != 采集失败：不计入 failed_count，但登记文件里的结局照报。"""
        self._write_json(self.SOURCES, {
            "version": 1,
            "research": [dict(row, enabled=False) if row["id"] == "arxiv" else row
                         for row in self.ROWS],
        })
        self._write_run("arxiv", {"id": "arxiv", "outcome": "failed", "http": 403,
                                  "finished_at": time.time() - 10})
        by_id, status = self._by_id()
        block = by_id["arxiv"]
        self.assertEqual("disabled", block["state"])
        self.assertEqual("未启用", block["status_label"])
        self.assertEqual("未启用", block["enabled_label"])
        self.assertEqual(0, status["failed_count"], "未启用的源失败不计入失败计数")
        self.assertEqual(403, block["http"], "未启用也不许把登记文件里的事实吞掉")
        self.assertEqual("failed", block["outcome"])

    def test_RG6_missed_once_is_not_stale_missed_twice_is(self):
        """RG6：漏一次不算过期、漏两次算；过期是漏采，不许冒充失败。"""
        now = time.time()
        self._write_watermark({"arxiv": now - int(1.5 * 86400)})
        self._write_run("arxiv", {"id": "arxiv", "outcome": "ok", "finished_at": now - 10})
        by_id, _ = self._by_id()
        self.assertEqual("ok", by_id["arxiv"]["state"], "1.5 个周期内 -> 正常")

        self._write_watermark({"arxiv": now - int(2.5 * 86400)})
        by_id, _ = self._by_id()
        self.assertEqual("stale", by_id["arxiv"]["state"])
        self.assertEqual("已登记 · 采集过期", by_id["arxiv"]["status_label"])
        self.assertNotEqual("failed", by_id["arxiv"]["state"], "过期不许冒充失败")

    def test_RG7_http_route_returns_the_same_contract(self):
        """RG7：/api/research 走 HTTP 也拿得到，shape 与直连一致。"""
        server = PS.create_server("127.0.0.1", 0, PS.HoloBridge())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/research",
                data=json.dumps({"op": "status"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertTrue(payload["ok"])
        self.assertEqual("sources", payload["schema"])
        for key in ("sources", "counts", "summary", "run_dir", "watermark_file",
                    "failed_count", "unreadable_count", "stale_count", "ok_count",
                    "never_run_count", "disabled_count", "checked_at"):
            self.assertIn(key, payload)

    def test_RG8_failure_without_any_watermark_says_so(self):
        """RG8：失败且从无成功 —— 仍是失败，明说没有历史水位，不许退化成「未采集」。"""
        self._write_run("arxiv", {"id": "arxiv", "outcome": "failed", "http": 500,
                                  "reason": "boom", "finished_at": time.time() - 10})
        by_id, status = self._by_id()
        block = by_id["arxiv"]
        self.assertEqual("failed", block["state"])
        self.assertNotEqual("never_run", block["state"])
        self.assertFalse(block["watermark_present"])
        self.assertIn("没有成功水位", block["hint"])
        self.assertEqual(1, status["failed_count"])

    def test_RG9_broken_registry_is_reported_not_faked(self):
        """RG9：登记表坏掉 -> 不信、不编：verified=False、count=0、原因带出来。"""
        self.SOURCES.write_text("{ not json", encoding="utf-8")
        status = self._status()
        self.assertFalse(status["sources_verified"])
        self.assertTrue(status["sources_error"])
        self.assertEqual(0, status["count"])
        self.assertEqual([], status["sources"])
        self.assertEqual(0, status["failed_count"], "读不出来不许自动升级成失败")

        self._write_json(self.SOURCES, {"version": 1, "research": {"arxiv": True}})
        status = self._status()
        self.assertFalse(status["sources_verified"])
        self.assertIn("research", status["sources_error"])

        self.assertFalse(PS.HoloBridge().research("publish")["ok"], "调研舱区只读")


class ResearchRunReportTests(_ResearchFixture, unittest.TestCase):
    """RG10-RG14：判据 E ——「run_report 该源标红 + 不沿用旧值」。

    两条核心判据都落在**机器字段**上，不靠文案里有没有「失败」两个字：

      RG10 / RG14  标红：severity 由 state 推出来，run_report.failed_sources 汇总它；
      RG11-RG13    不沿用旧值：本次值只来自 state/runs/，历史只进 history；
                   没有本次记录就是 None —— 绝不拿上一次成功的条数顶。

    夹具继承 _ResearchFixture（与 RG1-RG9 同一套，不复制第二份）。
    """

    SOURCES = ROOT / "sources.json"
    RUNS = ROOT / "state" / "runs"
    WATERMARK = ROOT / "state" / "last_seen.json"

    ROWS = [
        {"id": "arxiv", "name": "arXiv", "kind": "paper", "enabled": True,
         "interval": "daily"},
        {"id": "hackernews", "name": "Hacker News", "kind": "heat", "enabled": True,
         "interval": "daily"},
        {"id": "github", "name": "GitHub Trending", "kind": "code", "enabled": True,
         "interval": "daily"},
        {"id": "jobs", "name": "招聘信号", "kind": "money_demand", "enabled": False,
         "interval": "weekly"},
    ]

    def test_RG10_failed_source_is_red_and_summarized(self):
        """RG10：失败源标红 —— 源自己的 severity、顶层 severity、run_report 三处一致。"""
        self._write_run("arxiv", {"id": "arxiv", "outcome": "failed", "http": 406,
                                  "reason": "SourceThrottled", "finished_at": time.time() - 30})
        by_id, status = self._by_id()
        self.assertEqual("red", by_id["arxiv"]["severity"])
        self.assertEqual("red", status["severity"])
        self.assertIn("arxiv", status["failed_sources"])
        report = status["run_report"]
        self.assertEqual("red", report["severity"])
        self.assertEqual(["arxiv"], report["failed_sources"])
        self.assertEqual(1, report["red_count"])
        self.assertEqual("state/runs", report["values_from"])
        row = [item for item in report["sources"] if item["id"] == "arxiv"][0]
        self.assertEqual("red", row["severity"])
        self.assertEqual("failed", row["state"])

    def test_RG11_this_run_value_never_borrows_the_history(self):
        """RG11：水位写着「上一次 42 条」，本次失败只采到 0 条 —— 两格必须分家。"""
        now = time.time()
        self._write_watermark({"arxiv": {"at": now - 3 * 86400, "items": 42}})
        self._write_run("arxiv", {"id": "arxiv", "outcome": "failed", "http": 406,
                                  "items": 0, "attempts": 2, "finished_at": now - 30})
        by_id, _ = self._by_id()
        block = by_id["arxiv"]
        self.assertEqual("failed", block["state"])
        self.assertEqual(0, block["this_run"]["items"], "本次值被历史顶掉了")
        self.assertEqual(42, block["history"]["items"], "历史条数只许待在 history")
        self.assertEqual("历史（上一次成功）", block["history"]["label"])
        self.assertEqual("state/runs", block["values_from"])
        # 兼容层那几个字段也必须只反映本次
        self.assertEqual(0, block["items"])
        self.assertEqual(2, block["attempts"])
        self.assertEqual(406, block["http"])
        self.assertGreaterEqual(block["last_ok_age_seconds"], 3 * 86400)
        self.assertLess(block["last_ok_age_seconds"], 3 * 86400 + 300)

    def test_RG12_missing_run_reports_unknown_not_the_old_number(self):
        """RG12：没有本次记录 -> 本次值 None、values_from 空；不许拿历史的 42 顶上。"""
        now = time.time()
        self._write_watermark({"github": {"at": now - 3600, "items": 42}})
        by_id, _ = self._by_id()
        block = by_id["github"]
        self.assertIs(False, block["this_run"]["present"])
        self.assertIsNone(block["this_run"]["items"])
        self.assertIsNone(block["items"])
        self.assertEqual("", block["values_from"])
        self.assertEqual(42, block["history"]["items"])
        self.assertEqual("state/last_seen.json", block["history"]["source"])

    def test_RG13_run_report_total_only_counts_this_run_successes(self):
        """RG13：本次总数只由 outcome=ok 的源贡献 —— 失败源的 0 与没采到的源都不计。"""
        now = time.time()
        self._write_watermark({"github": {"at": now - 3600, "items": 42}})
        self._write_run("arxiv", {"id": "arxiv", "outcome": "failed", "http": 406,
                                  "items": 0, "finished_at": now - 30})
        self._write_run("hackernews", {"id": "hackernews", "outcome": "ok",
                                       "items": 5, "finished_at": now - 20})
        _, status = self._by_id()
        report = status["run_report"]
        self.assertEqual(5, report["this_run_items_total"],
                         "总数把失败源的 0 或历史值算进去了")
        self.assertEqual(1, report["this_run_sources_counted"])
        self.assertEqual(["arxiv"], report["failed_sources"])

    def test_RG14_severity_is_derived_from_state(self):
        """RG14：severity 由 state 推出来 —— 只有 failed / unreadable 能是 red。"""
        now = time.time()
        self._write_watermark({"github": now - 3 * 86400, "hackernews": now - 3600})
        self._write_run("arxiv", "{ broken json")
        by_id, _ = self._by_id()
        self.assertEqual("red", by_id["arxiv"]["severity"], "读不出来必须标红")
        self.assertEqual("warn", by_id["github"]["severity"], "过期是 warn，不是 red")
        self.assertEqual("ok", by_id["hackernews"]["severity"])
        self.assertEqual("neutral", by_id["jobs"]["severity"], "未启用是中性，不是红")
        allowed_red = {"failed", "unreadable"}
        for block in by_id.values():
            self.assertEqual(block["severity"] == "red",
                             block["state"] in allowed_red,
                             "%s 的 severity 与 state 对不上" % block["id"])


class SignalIngestTests(unittest.TestCase):
    """判据 F（缺 url 拒收）/ G（有 value 无 baseline 不出增长率）。

    RG15-RG20 = F：拒绝入库 + 控制台报错 + 不入 signals.jsonl。
    RG21-RG23 = G：算不出增长率就整键省略，**不是** +0%；量出来的 0 才许印。
    """

    def setUp(self):
        import io as _io
        import tempfile as _tempfile
        import signal_ingest as _signal_ingest
        from pathlib import Path as _Path

        self.signal_ingest = _signal_ingest
        self._tmp = _tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = _Path(self._tmp.name) / "signals.jsonl"
        self.stream = _io.StringIO()

    def _ingest(self, records):
        return self.signal_ingest.ingest(records, path=self.path, stream=self.stream)

    def _raw(self):
        if not self.path.is_file():
            return ""
        return self.path.read_text(encoding="utf-8")

    def _lines(self):
        return [line for line in self._raw().split("\n") if line.strip()]

    # ---- F：缺 url 拒收 ----

    def test_RG15_record_without_url_is_rejected_and_not_written(self):
        res = self._ingest([{"id": "a", "value": 1, "baseline": 0}])
        self.assertEqual(1, res["rejected"])
        self.assertEqual(0, res["written"])
        self.assertEqual("", self._raw(), "缺 url 的记录一个字节都不许落盘")
        self.assertIn("拒绝入库", self.stream.getvalue())

    def test_RG16_blank_and_non_string_url_count_as_missing(self):
        for bad in (None, "", "   ", 42, ["u"], {}):
            res = self._ingest([{"id": "a", "url": bad}])
            self.assertEqual([self.signal_ingest.MISSING_URL], res["codes"], repr(bad))
        self.assertEqual("", self._raw())

    def test_RG17_one_rejected_record_does_not_block_the_others(self):
        res = self._ingest([{"id": "bad", "value": 1},
                            {"id": "good", "url": "https://example.org/x"}])
        self.assertEqual(1, res["written"])
        self.assertEqual(1, res["rejected"])
        self.assertEqual(1, len(self._lines()))
        self.assertNotIn("bad", self._raw(), "被拒的那条不许换个马甲溜进来")

    def test_RG18_console_gets_one_error_line_per_rejected_record(self):
        self._ingest([{"id": "a"}, {"id": "b"}, {"id": "c", "url": "https://e.org"}])
        errs = [line for line in self.stream.getvalue().split("\n") if "拒绝入库" in line]
        self.assertEqual(2, len(errs), "一条被拒一条报错，不许合并、不许静默")

    def test_RG19_all_invalid_writes_nothing_at_all(self):
        res = self._ingest([{"id": "a"}, {"id": "b"}])
        self.assertEqual(0, res["written"])
        self.assertFalse(res["all_written"])
        self.assertEqual("", self._raw())

    def test_RG20_valid_record_keeps_its_url_verbatim(self):
        url = "https://example.org/abs/2401.00001v2"
        res = self._ingest([{"id": "a", "url": url, "value": 3, "baseline": 2}])
        self.assertEqual(1, res["written"])
        parsed = json.loads(self._lines()[0])
        self.assertEqual(url, parsed["url"], "落盘的 url 必须原样，不许改写")

    # ---- G：算不出增长率就不印 ----

    def test_RG21_value_without_baseline_has_no_growth_key(self):
        record = {"url": "https://e.org", "value": 12}
        self.assertNotIn("growth", self.signal_ingest.report_view(record))
        self.assertIsNone(self.signal_ingest.format_growth(record))

    def test_RG22_policy_string_baseline_is_not_a_baseline(self):
        record = {"url": "https://e.org", "value": 12, "baseline": "rolling_7d"}
        self.assertIsNone(self.signal_ingest.format_growth(record))
        self.assertNotIn("growth", self.signal_ingest.report_view(record))

    def test_RG23_measured_zero_growth_is_allowed(self):
        record = {"url": "https://e.org", "value": 10, "baseline": 10}
        self.assertEqual("+0.0%", self.signal_ingest.format_growth(record))


class LedgerReconcileTests(unittest.TestCase):
    """账本到期未核销 -> 状态保持 open，永远不计入命中（RG24-RG29）。"""

    DUE_PAST = "2020-01-01T00:00:00"

    def setUp(self):
        import tempfile as _tempfile
        import research_status as _research_status
        from pathlib import Path as _Path

        self.rs = _research_status
        self._tmp = _tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = _Path(self._tmp.name) / "ledger.jsonl"

    def _write(self, entries):
        text = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries)
        self.path.write_text(text, encoding="utf-8")

    def test_RG24_overdue_open_stays_open_and_is_listed(self):
        self._write([{"id": "c1", "status": "open", "due": self.DUE_PAST}])
        rep = self.rs.ledger_report(self.path)
        self.assertEqual(["c1"], rep["overdue_open"])
        self.assertEqual(1, rep["counts"]["open"], "不许替人把到期的 open 核销掉")

    def test_RG25_overdue_open_never_counts_as_a_hit(self):
        self._write([{"id": "c1", "status": "open", "due": self.DUE_PAST}])
        rep = self.rs.ledger_report(self.path)
        self.assertEqual(0, rep["hits"])
        self.assertIsNone(rep["hit_rate"], "没核销就没有命中率，不许印 0%")

    def test_RG26_hit_rate_denominator_excludes_unreconciled(self):
        self._write([
            {"id": "c1", "status": "hit", "due": self.DUE_PAST},
            {"id": "c2", "status": "miss", "due": self.DUE_PAST},
            {"id": "c3", "status": "open", "due": self.DUE_PAST},
        ])
        rep = self.rs.ledger_report(self.path)
        self.assertEqual(1, rep["hits"])
        self.assertEqual(2, rep["reconciled"])
        self.assertAlmostEqual(0.5, rep["hit_rate"], "到期未核销的不进分母")
        self.assertEqual(["c3"], rep["overdue_open"])

    def test_RG27_open_without_due_is_reported_not_silently_overdue(self):
        self._write([{"id": "c1", "status": "open"}])
        rep = self.rs.ledger_report(self.path)
        self.assertEqual(["c1"], rep["open_without_due"])
        self.assertEqual([], rep["overdue_open"])

    def test_RG28_unreadable_lines_are_counted_not_dropped(self):
        self.path.write_text(json.dumps({"id": "c1", "status": "hit"}) + "\n{not json\n",
                             encoding="utf-8")
        rep = self.rs.ledger_report(self.path)
        self.assertEqual(1, rep["total"])
        self.assertEqual(1, rep["unreadable_lines"], "读不出来的行要报数，不许当没有")

    def test_RG29_report_is_a_pure_read(self):
        self._write([{"id": "c1", "status": "open", "due": self.DUE_PAST}])
        before = self.path.read_text(encoding="utf-8")
        self.rs.ledger_report(self.path)
        self.assertEqual(before, self.path.read_text(encoding="utf-8"),
                         "汇总只读：到期未核销也不许改账本一个字节")


class SummaryBlockTests(unittest.TestCase):
    """判据 H：LLM 挂了，窗口必须照样能用（RG30-RG35）。

    三条不许：
      1. 失败时把上次摘要当本次 —— 静默沿用 = 谎报新鲜；
      2. 失败时印空串冒充"有摘要"；
      3. 失败时把整个窗口带崩 —— window_ok 恒为 True（命门不许交给限流通道）。
    """

    def setUp(self):
        import signal_ingest as _signal_ingest
        self.si = _signal_ingest
        self.now = 1700000000.0

    def _previous(self, hours_ago):
        return {
            "text": "上一次的摘要：arXiv 新论文 3 篇",
            "generated_at": self.now - hours_ago * 3600.0,
            "model": "summary-model-v1",
        }

    # ---- 成功分支 ----

    def test_RG30_success_reports_fresh_and_is_not_stale(self):
        block = self.si.summary_block(
            text="  本次摘要  ", generated_at=self.now, model="m1",
            error="", previous=self._previous(1.0), now=self.now,
        )
        self.assertTrue(block["available"])
        self.assertFalse(block["stale"])
        self.assertEqual("本次摘要", block["text"], "摘要要 strip，但不许改写内容")
        self.assertEqual(self.si.SUMMARY_OK, block["reason_code"])
        self.assertIsNone(block["age_hours"])

    # ---- 失败 + 上次在窗口内 -> 带标记回看 ----

    def test_RG31_failure_within_window_reuses_previous_with_marker(self):
        block = self.si.summary_block(
            text=None, error="HTTP 429", previous=self._previous(2.0), now=self.now,
        )
        self.assertFalse(block["available"], "沿用的不是本次结果，available 必须是 False")
        self.assertTrue(block["stale"], "沿用旧摘要必须带 stale 标记，不许冒充新鲜")
        self.assertEqual("上一次的摘要：arXiv 新论文 3 篇", block["text"])
        self.assertEqual(2.0, block["age_hours"])
        self.assertEqual(self.si.SUMMARY_STALE_REUSE, block["reason_code"])
        self.assertIn("429", block["error"], "失败原因不许吞掉")

    def test_RG32_failure_beyond_window_yields_no_text(self):
        block = self.si.summary_block(
            text=None, error="HTTP 429", previous=self._previous(30.0), now=self.now,
        )
        self.assertFalse(block["available"])
        self.assertFalse(block["stale"])
        self.assertIsNone(block["text"], "超出窗口不许印旧摘要，也不许印空串冒充")
        self.assertEqual(self.si.SUMMARY_UNAVAILABLE, block["reason_code"])

    def test_RG33_failure_without_previous_yields_no_text(self):
        for previous in (None, {}, {"text": ""}, {"text": "有字但没时间"}):
            block = self.si.summary_block(text="", error="连接超时",
                                          previous=previous, now=self.now)
            self.assertIsNone(block["text"], repr(previous))
            self.assertEqual(self.si.SUMMARY_UNAVAILABLE, block["reason_code"], repr(previous))
            self.assertFalse(block["available"], repr(previous))

    # ---- H 的灵魂：三分支都不许把窗口带崩 ----

    def test_RG34_window_stays_usable_in_all_three_branches(self):
        ok = self.si.summary_block(text="好的", generated_at=self.now, now=self.now)
        reused = self.si.summary_block(text=None, error="挂了", now=self.now,
                                       previous=self._previous(1.0))
        gone = self.si.summary_block(text=None, error="挂了", now=self.now, previous=None)
        for name, block in (("ok", ok), ("stale_reuse", reused), ("unavailable", gone)):
            self.assertIs(True, block["window_ok"],
                          "%s：命门不许交给限流通道，window_ok 必须恒为 True" % name)

    # ---- 失败绝不许被包装成"本次结果" ----

    def test_RG35_failure_is_never_dressed_as_this_run(self):
        block = self.si.summary_block(text="残缺的新摘要", error="HTTP 500",
                                      previous=self._previous(1.0), now=self.now)
        self.assertFalse(block["available"], "带 error 就是失败，不许当成功")
        self.assertEqual(self.si.SUMMARY_STALE_REUSE, block["reason_code"])
        self.assertEqual("上一次的摘要：arXiv 新论文 3 篇", block["text"],
                         "本次失败时正文只能是上次那份，不许把半截新摘要当结果")
