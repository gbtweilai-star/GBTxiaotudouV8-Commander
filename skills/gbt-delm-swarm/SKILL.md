---
name: gbt-delm-swarm
description: DeLM 蒸馏件 —— 去中心多智能体（不设中央编排器）+ 共享上下文（只引用不复制正文）+ 并行要有闸。当用户说「多智能体 / 群体 / 并行跑 / 去中心 / 共享上下文 / DeLM / swarm」时使用。
---

# gbt-delm-swarm · 去中心多智能体（DeLM 蒸馏）

**出处（不许扩写）**：arXiv **2606.10662v1**《Decentralized Multi-Agent Systems with Shared Context》
（https://arxiv.org/abs/2606.10662v1）· 二手口径：VentureBeat「Stanford's DeLM cuts multi-agent costs
~50% **without a central orchestrator**」。**本件只蒸馏这三条，其余机制本仓未验、不写。**

## 三律（落成本仓既有位，**不新增算力**）

1. **不设中央编排** —— 协调走 stigmergy（信息素场地，DEPOSIT·READ·DECAY·FORAGE，整位零作用域）：
   每个体自己**放痕迹 / 读浓度**决定下一步，不许出现「总调度」角色。
2. **共享不复制** —— 上下文只进 context_vault（口径：**索引 + 检索层，不是第四处存储，只引用不复制正文**；
   sqlite3 + FTS5；按预算裁剪）。任一步要用背景，**必须现查 vault**，不许把正文复制进各自提示。
3. **并行要有闸** —— 并行只走 wf_define / wf_run（DAG · 分层并行 · 断点续跑）；
   上闸前先算**资源压强**（内存/并发），超限就**降并行度**；不可回滚或花钱的步**必须升到主人**。

## 调用法（唯一门：万能插）

    # 放一条痕迹（DEPOSIT）
    py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"deposit","kind":"plan","text":"<短句>","tags":["delm"]}'
    # 读浓度（FORAGE）—— 决定下一步往哪走
    py -3.14 tools/codex-scripts/five-dim.py cap stigmergy '{"op":"forage","tags":["delm"]}'
    # 共享上下文：查而不复制
    py -3.14 tools/codex-scripts/five-dim.py cap context_vault '{"op":"search","q":"<词>","budget":2000}'
    # 并行编排
    py -3.14 tools/codex-scripts/five-dim.py cap wf_define '{"name":"<名字>","workflow":{...}}'
    py -3.14 tools/codex-scripts/five-dim.py cap wf_run '{"name":"<名字>"}'

## 判据（机器可检 · 缺一不算成品）

- **J1 位名不漂**：四个位名必须能在 gbt_allinone/caps_registry.py 里现查到（本件落稿时实测：
  wf_define:132 · wf_run:138 · context_vault:1649 · stigmergy:1715）。
- **J2 无中央编排**：规程与产物里**不许**出现「中心编排器 / 总调度 / main orchestrator」充当 DeLM。
- **J3 共享有出处**：任一并行步骤必须写明它查的是 context_vault 的哪一次查询（口径 + 预算）。
- **J4 有闸**：并行前必须给出资源压强读数；缺读数 ⇒ 不并行。
- **J5 取不到就写未读到**：stigmergy 场地为空时如实返回空，**不许编造方向**。

## 边界

- 本件**只管「怎么组织多个体」**；单体执行仍走各自能力位（llm / engine / …）。
- **不是**新模块、不新增算力、不绕门：所有动作仍过 run_task + policy.py 作用域门。
- 与 gbt-collab（stigmergy 位本身的用法规程）是**两层**：那件讲位怎么调，本件讲**多体怎么组织**。

**回滚**：删除本目录即恢复。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
