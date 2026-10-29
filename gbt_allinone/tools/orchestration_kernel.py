# gbt-capability: orchestration_kernel
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""万能插 · 编排内核（Orchestration Kernel）· R-H190 —— **三源蒸馏**。

  BrowserUse → **状态空间**（看到什么）+ **动作空间**（能做什么）
  CrewAI     → **角色工作组**（谁来做）+ **流程状态机**（按什么顺序）
  Mastra     → **可存储图**（工作流本身是数据）+ **挂起恢复**（暂停等人类）

三层职责
  1. `to_storable_graph()` / `rehydrate()` —— 工作流**可存可恢复**
  2. `suspend()` / `resume()`          —— **人在环中**的机械载体
  3. `get_ready_nodes()` + `run()`     —— 按依赖调度（DAG）

🔴 本刀的**真调用点**（治"挂号不接线"的病根）：
  `step_type="capability"` 的节点**真的去执行能力**——但**只自动执行只读能力**
  （`_READONLY_MODULES` 里那几个，模块是**真 import**）；其余一律**拒绝**并指向
  `api.run_task`（过 auth_gate）—— **不可逆动作照卡**（人类视角执行律）。

诚实边界：内核只保证"**可序列化、可恢复、按依赖调度**"，
它**不保证"工作流跑得对"** —— 对错由门禁与复核决定。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

# 真 import（不是字符串）：编排内核与这些只读能力**真的接上了线**
from . import (a1art_skill, auto_publish, auto_switch, awesome_tools_index,
               cloud_pc, context_vault, feishu_embed, libtv_workflow,
               account_registry, ai_capability_net, brand_outro, caps_called_audit,
               code_art_kernel,
               gate_visibility,
               absorb_loop,
               director_mood, dream_replay, emotion_projection, energy_pool,
               h3_video_gen,
               hook_registry, local_brain,
               libtv_skill,
               projection_skill, render_evolution, research_intel, scene_anchor,
               coverage_auditor, meta_cognition, model_key_pool, shared_resources,
               observer_anchor, proactive_report,
               tentacle_cognition, verification_watch,
               project_drift,
               stigmergy)
from .. import tactics          # `tactics.py` 在包根，不在 tools/

_READONLY_MODULES = {
    "scene_anchor": scene_anchor,
    "hook_registry": hook_registry,
    "brand_outro": brand_outro,
    "emotion_projection": emotion_projection,
    "observer_anchor": observer_anchor,
    "proactive_report": proactive_report,
    "research_intel": research_intel,
    # R-H193 · 甲第一步（补最底层的 6 个孤儿）：都是只读面、都有 run()，**真 import** 进来。
    "account_registry": account_registry,
    "director_mood": director_mood,
    "dream_replay": dream_replay,
    "render_evolution": render_evolution,
    "shared_resources": shared_resources,
    "verification_watch": verification_watch,
    # R-H194 · 甲第二步（内调型孤儿补线，一条改动接通 4 个）
    "caps_called_audit": caps_called_audit,
    "capability_net": ai_capability_net,
    "projection_card": projection_skill,
    "tactics_advise": tactics,
    # R-H194 补：`code_art` 此前只被**注释**提过（假接线）⇒ 剥注释后露成真孤儿，这里真接上
    "code_art": code_art_kernel,
    # R-H195 · 落地即接线：认知包在**编排内核的调度面**上是必需品（缺包 = 让触手盲猜）
    "tentacle_cognition": tentacle_cognition,
    # R-H196 · 落地即接线：覆盖审计属于**调度前的自检面**（不知道有没有死角 ⇒ 不许乱调度）
    "coverage_auditor": coverage_auditor,
    # R-H197 · 落地即接线：调度前要先"借钥匙"（没有对应身份的密钥 ⇒ 拒执行并上报）
    "model_key_pool": model_key_pool,
    # R-H200 · 落地即接线：调度前后都要"自省"（哪里卡了 / 哪里靠猜了）
    "meta_cognition": meta_cognition,
    # R-H204 · 落地即接线：LibTV 技能是**门**（external），但门也要**在调度面上登记**
    # 才算真接线 —— 它是执行末端的"创作之手"（会话进展 / 切项目 / 批量下载）。
    "libtv_skill": libtv_skill,
    # R-H206 · 落地即接线：a1.art 是**存量窗口**（平台逐步停止服务），也是门 ——
    # 门同样要在调度面上有名字，否则又是"挂号不接线"。
    "a1art_skill": a1art_skill,
    # R-H223 · 落地即接线：能源池是**调度前的取油点**（没能源就别派活）
    "energy_pool": energy_pool,
    # R-H227 · 落地即接线：本地脑是**调度前的皮层**（意图解析 + 结果解释）
    "local_brain": local_brain,
    # R-H229 · 落地即接线：自动切换是**调度的决策面**（意图→分级→选能源）
    "auto_switch": auto_switch,
    # R-H230 · 落地即接线：归档库是**调度前的取上下文点**（只索引不复制）
    "context_vault": context_vault,
    # R-H239 · 落地即接线：飞书窗口是**外部入口**（走浏览器触手，不用 API）
    "feishu_embed": feishu_embed,
    # R-H246 · 落地即接线：LibTV 画布编排（节点/连线/批量跑）
    "libtv_workflow": libtv_workflow,
    # R-H248 · 落地即接线：门可见性审计是**调度前的自检面**（不知道门看不见什么 ⇒ 账实不符的种子）
    "gate_visibility": gate_visibility,
    # R-H250 · 落地即接线：H3mini 是**外部视频能源**（本地带不动 ⇒ api 模式 + requires_external_key）
    "h3_video_gen": h3_video_gen,
    # R-H258 · 落地即接线：吞天闭环是**吸收前的纪律面**（垃圾不清 ⇒ 越吞越脏）
    "absorb_loop": absorb_loop,
    # R-H284 · 落地即接线：云电脑是**算力落点**（她住云上，身份源仍在本地）
    "cloud_pc": cloud_pc,
    # R-H284 · 落地即接线：全自动发布是**不可逆动作的门**（发布那几下必须过门）
    "auto_publish": auto_publish,
    # R-H285 · 落地即接线：Awesome Tools 是**能力地图**（只引用不复制、只映射不照搬）
    "awesome_tools_index": awesome_tools_index,
    # R-H353 · 落地即接线：协作层的**间接通道**（信息素场地；与 collab_gateway 并排）
    "stigmergy": stigmergy,
    # 2026-10-25 · 落地即接线：**第三块监控**（全控变化 —— 主人 2026-10-19
    # 「多余监控还缺了一个全控变化，也就是要有一个看着整个项目变化的」）。
    # 它原来是「挂号不接线」：注册表 enabled、handler 有、只读零作用域，但入口叫
    # `run_op` 而调度面只认 `run` ⇒ **一个内部调用方都没有**，审计把它报成内调型孤儿，
    # 而真正的问题是「监控不会自己跑」。这一刀：`project_drift.run()` 薄适配 + 本行登记，
    # 默认 op=status（只读），跑一次真读数见 `test_caps_called_audit` 复绿。
    "project_drift": project_drift,
    # 注：`sec_chain`（安全面 HackerBrain）**故意不接** —— 安全面的入口语义要单独判，
    # 不随手给它造调用方（避免"为了数字好看而造假线"）。
}

STEP_TYPES = ("capability", "code", "human")

HONEST_BOUNDARY = (
    "编排内核只保证『工作流可以被序列化、恢复、按依赖调度』。"
    "它不保证『工作流一定跑得对』——工作流对错，由门禁和复核决定。"
)


@dataclass
class OrchestrationNode:
    """一个编排节点 = 状态 + 动作 + 角色 + 流程位置 + 可存储性。"""

    node_id: str
    role: str = ""
    goal: str = ""
    backstory: str = ""
    observation: Optional[str] = None            # BrowserUse：状态空间
    available_actions: List[str] = field(default_factory=list)   # BrowserUse：动作空间
    step_type: str = "capability"                # capability / code / human
    capability: str = ""                         # step_type=capability 时：能力名
    params: Dict[str, Any] = field(default_factory=dict)
    is_suspendable: bool = False                 # Mastra：可挂起
    depends_on: List[str] = field(default_factory=list)


class Blackboard:
    """黑板（记分牌）：**只记结果，不改事实**；写入即留痕。"""

    def __init__(self) -> None:
        self.rows: Dict[str, List[dict]] = {}

    def write(self, node_id: str, payload: dict) -> dict:
        row = dict(payload or {})
        self.rows.setdefault(node_id, []).append(row)
        return {"ok": True, "readonly": True, "node_id": node_id,
                "depth": len(self.rows[node_id])}

    def read(self, node_id: str) -> Optional[dict]:
        rows = self.rows.get(node_id) or []
        return dict(rows[-1]) if rows else None

    def dump(self) -> dict:
        return {k: list(v) for k, v in self.rows.items()}


class StartingGun:
    """发令枪：统一启动（**所有节点都 Ready 才允许开跑**）。"""

    def __init__(self) -> None:
        self.armed = False

    def arm(self, nodes: Dict[str, OrchestrationNode]) -> dict:
        if not nodes:
            return {"ok": False, "denied": True, "why": "没有节点，不许起跑"}
        self.armed = True
        return {"ok": True, "readonly": True, "armed": True, "nodes": len(nodes)}

    def fire(self) -> dict:
        if not self.armed:
            return {"ok": False, "denied": True, "why": "没 arm 就想 fire —— 统一起跑失败"}
        return {"ok": True, "readonly": True, "fired": True}


class OmniPlugOrchestrator:
    """编排引擎：注册 → 调度 → 执行（只读能力）→ 记分 → 挂起/恢复。"""

    def __init__(self) -> None:
        self.nodes: Dict[str, OrchestrationNode] = {}
        self.board = Blackboard()
        self.gun = StartingGun()
        self.completed: List[str] = []
        self.graph_snapshot: Optional[dict] = None

    # ── 注册 ────────────────────────────────────────────────
    def register(self, node: OrchestrationNode) -> dict:
        if not str(node.node_id or "").strip():
            raise ValueError("node_id 不能为空")
        if node.step_type not in STEP_TYPES:
            raise ValueError("未知 step_type %r（可用：%s）" % (node.step_type, "/".join(STEP_TYPES)))
        self.nodes[node.node_id] = node
        return {"ok": True, "readonly": True, "node_id": node.node_id,
                "nodes": len(self.nodes)}

    # ── Mastra：可存储图 ────────────────────────────────────
    def to_storable_graph(self) -> dict:
        return {"nodes": [asdict(n) for n in self.nodes.values()],
                "completed": list(self.completed),
                "version": "orchestration-kernel/v1"}

    def rehydrate(self, snapshot: dict) -> dict:
        snap = dict(snapshot or {})
        self.nodes = {}
        for row in snap.get("nodes") or []:
            self.nodes[row["node_id"]] = OrchestrationNode(**{
                k: v for k, v in row.items() if k in OrchestrationNode.__dataclass_fields__
            })
        self.completed = list(snap.get("completed") or [])
        return {"ok": True, "readonly": True, "nodes": len(self.nodes),
                "completed": len(self.completed)}

    # ── CrewAI：流程调度 ────────────────────────────────────
    def get_ready_nodes(self, completed: Optional[List[str]] = None) -> List[str]:
        done = set(self.completed if completed is None else completed)
        return [n.node_id for n in self.nodes.values()
                if n.node_id not in done and all(d in done for d in n.depends_on)]

    # ── 真调用点：只读能力真执行；其余拒绝 ──────────────────
    def dispatch(self, node_id: str) -> dict:
        node = self.nodes.get(node_id)
        if node is None:
            return {"ok": False, "denied": True, "why": "节点不存在：%s" % node_id}
        if node.step_type != "capability":
            return {"ok": True, "readonly": True, "node_id": node_id, "skipped": True,
                    "why": "step_type=%s 不由内核执行（code 交给调用方，human 等人）" % node.step_type}
        mod = _READONLY_MODULES.get(node.capability)
        if mod is None:
            return {"ok": False, "denied": True, "node_id": node_id,
                    "rule": "not_readonly",
                    "why": "编排内核**只自动执行只读能力**；『%s』不是只读面 ⇒ "
                           "请走 api.run_task（过 auth_gate）" % (node.capability or "?")}
        params = dict(node.params or {})
        op = params.pop("op", "status")
        try:
            out = mod.run(op, **params)
        except TypeError:
            out = mod.run(op)
        self.board.write(node_id, {"capability": node.capability, "op": op, "ok": out.get("ok", True)})
        return {"ok": bool(out.get("ok", True)), "readonly": True, "node_id": node_id,
                "capability": node.capability, "op": op, "result": out}

    # ── 调度循环（跑到完成 / 挂起 / 步数上限）────────────────
    def run(self, max_steps: int = 20, stop_before: str = "") -> dict:
        self.gun.arm(self.nodes)
        gun = self.gun.fire()
        if not gun.get("ok"):
            return gun
        steps = []
        for _ in range(int(max_steps)):
            ready = self.get_ready_nodes()
            if not ready:
                break
            nid = ready[0]
            if stop_before and nid == stop_before and self.nodes[nid].is_suspendable:
                out = self.suspend(nid, reason="人在环中：这一步要人过目")
                return {"ok": True, "readonly": True, "steps": steps, "suspended": out}
            res = self.dispatch(nid)
            steps.append({"node_id": nid, "ok": res.get("ok"), "skipped": res.get("skipped", False)})
            self.board.write(nid, {"ok": res.get("ok"), "capability": self.nodes[nid].capability})
            if res.get("ok"):
                self.completed.append(nid)
            else:
                break
        return {"ok": True, "readonly": True, "steps": steps,
                "completed": list(self.completed),
                "remaining": sorted(set(self.nodes) - set(self.completed))}

    # ── Mastra：挂起 / 恢复 ─────────────────────────────────
    def suspend(self, node_id: str, reason: str = "") -> dict:
        node = self.nodes.get(node_id)
        if node is None or not node.is_suspendable:
            return {"ok": False, "denied": True, "reason": "node_not_suspendable"}
        self.graph_snapshot = self.to_storable_graph()
        return {"ok": True, "readonly": True, "suspended_at": node_id,
                "reason": str(reason or "")[:200],
                "snapshot_nodes": len(self.graph_snapshot["nodes"])}

    def resume(self) -> dict:
        if not self.graph_snapshot:
            return {"ok": False, "denied": True, "reason": "no_snapshot"}
        self.rehydrate(self.graph_snapshot)
        return {"ok": True, "readonly": True, "resumed_from_snapshot": True,
                "nodes": len(self.nodes), "completed": len(self.completed)}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / graph / honest。不落盘、不出网、不自动执行非只读能力。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True,
                "readonly_capabilities": sorted(_READONLY_MODULES),
                "step_types": list(STEP_TYPES),
                "primitives": ["状态空间", "动作空间", "角色工作组", "流程状态机",
                               "可存储图", "挂起恢复"],
                "honest_boundary": HONEST_BOUNDARY}
    if op == "honest":
        return {"ok": True, "readonly": True, "honest_boundary": HONEST_BOUNDARY}
    raise ValueError("未知 op %r（可用：status/honest）" % (op,))
