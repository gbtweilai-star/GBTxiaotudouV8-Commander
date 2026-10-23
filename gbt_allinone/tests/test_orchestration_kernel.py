# -*- coding: utf-8 -*-
"""编排内核 · 带牙用例（R-H190）。

① 可存储图：`to_storable_graph()` → `rehydrate()` 往返一致（JSON 兼容，可存可恢复）；
② 流程调度：`get_ready_nodes()` 尊重 `depends_on`（依赖没完成就不 Ready）；
③ 人在环中：`run(stop_before=...)` 在可挂起节点处**挂起并留下快照**；`resume()` 能恢复；
④ **真调用点**：只读能力（scene_anchor 等）节点**真的被执行**并产出读数；
⑤ **不可逆照卡**：非只读能力 ⇒ 内核**拒绝自动执行**，指向 run_task（过 auth_gate）；
⑥ 发令枪：没 arm 就 fire ⇒ 拒。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import orchestration_kernel as ok_  # noqa: E402


def _orch():
    o = ok_.OmniPlugOrchestrator()
    o.register(ok_.OrchestrationNode(node_id="a", role="情报员", goal="查场景大类",
                                     step_type="capability", capability="scene_anchor",
                                     params={"op": "classes"}))
    o.register(ok_.OrchestrationNode(node_id="b", role="钩子手", goal="校发布钩子",
                                     step_type="capability", capability="hook_registry",
                                     params={"op": "redlines"}, depends_on=["a"],
                                     is_suspendable=True,
                                     observation="前面的场景大类已取到"))
    return o


class StorableGraphTests(unittest.TestCase):
    def test_graph_round_trip_is_json_compatible(self):
        o = _orch()
        snap = o.to_storable_graph()
        blob = json.dumps(snap, ensure_ascii=False)
        self.assertIn("nodes", snap)
        o2 = ok_.OmniPlugOrchestrator()
        o2.rehydrate(json.loads(blob))
        self.assertEqual(sorted(o2.nodes), sorted(o.nodes))
        self.assertEqual(o2.nodes["b"].depends_on, ["a"])
        self.assertTrue(o2.nodes["b"].is_suspendable)

    def test_ready_respects_dependencies(self):
        o = _orch()
        self.assertEqual(o.get_ready_nodes(), ["a"])
        o.completed.append("a")
        self.assertEqual(o.get_ready_nodes(), ["b"])


class DispatchTests(unittest.TestCase):
    def test_readonly_capability_is_really_executed(self):
        """真调用点：只读能力**真跑**，并回真读数（场景锚定 8 大类）。"""
        o = _orch()
        res = o.dispatch("a")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["capability"], "scene_anchor")
        self.assertIn("classes", res["result"])
        self.assertEqual(res["result"]["count"], 8)
        self.assertIsNotNone(o.board.read("a"), "黑板必须记下这一笔")

    def test_newly_wired_orphans_are_really_callable(self):
        """甲第一步（R-H193）：6 个底层孤儿接进只读派发表，且**真能跑出读数**。"""
        st = ok_.run("status")
        for kind in ("account_registry", "director_mood", "dream_replay",
                     "render_evolution", "shared_resources", "verification_watch",
                     "caps_called_audit", "capability_net", "projection_card",
                     "tactics_advise", "code_art"):
            self.assertIn(kind, st["readonly_capabilities"], "%s 应当已接线" % kind)
        self.assertNotIn("sec_chain", st["readonly_capabilities"],
                         "安全面故意不接：入口语义要单独判（不造假线）")
        o = ok_.OmniPlugOrchestrator()
        o.register(ok_.OrchestrationNode(node_id="d", step_type="capability",
                                         capability="dream_replay", params={"op": "status"}))
        res = o.dispatch("d")
        self.assertTrue(res["ok"], res)
        self.assertTrue(res["result"]["readonly"])

    def test_non_readonly_capability_is_refused_by_the_kernel(self):
        """不可逆照卡：内核**不许**自动执行非只读能力。"""
        o = ok_.OmniPlugOrchestrator()
        o.register(ok_.OrchestrationNode(node_id="w", step_type="capability",
                                         capability="create", params={"op": "write"}))
        res = o.dispatch("w")
        self.assertFalse(res["ok"])
        self.assertEqual(res["rule"], "not_readonly")
        self.assertIn("run_task", res["why"])

    def test_gun_must_be_armed(self):
        o = ok_.OmniPlugOrchestrator()
        self.assertFalse(o.gun.fire()["ok"])
        o.register(ok_.OrchestrationNode(node_id="x", step_type="code"))
        self.assertTrue(o.gun.arm(o.nodes)["ok"])
        self.assertTrue(o.gun.fire()["ok"])


class HumanInTheLoopTests(unittest.TestCase):
    def test_run_suspends_at_human_gate_and_resumes(self):
        o = _orch()
        out = o.run(stop_before="b")
        self.assertIn("suspended", out, "可挂起节点处必须挂起")
        self.assertEqual(out["suspended"]["suspended_at"], "b")
        self.assertEqual(o.completed, ["a"], "挂起前只该完成 a")
        self.assertIsNotNone(o.graph_snapshot, "挂起必须留下快照")
        back = o.resume()
        self.assertTrue(back["ok"])
        self.assertEqual(sorted(o.nodes), ["a", "b"])

    def test_honest_boundary_is_declared(self):
        st = ok_.run("status")
        self.assertIn("不保证", st["honest_boundary"])
        self.assertIn("scene_anchor", st["readonly_capabilities"])

    def test_module_has_no_network_or_write_paths(self):
        src = Path(ok_.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读内核里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
