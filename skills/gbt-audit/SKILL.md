---
name: gbt-audit
description: 独立审计规程（蒸馏自 ifixai-ai/iFixAi，Independent Auditing of AI Agents）—— 动作时间线 + 独立裁判 + 可指回判据。当用户说「审计一下她干了什么 / 时间线 / 谁调了什么 / 独立复核 / 业务 KPI 视角 / iFixAi」时使用。
---

# gbt-audit · 独立审计（动作时间线 · 只看证据）

**出处**：https://github.com/ifixai-ai/iFixAi （README 现读 HTTP 200 · 27,531 字符）
上游原话（差异化）：现有 Eval/Red-teaming/Observability 主要评**技术能力**（token/延迟/注入），
**回答不了最关键的问题**：这智能体按**业务 KPI 与组织结构**该干的活，干了吗？
它的答法：在 **AI-Red Teaming 与 Operational Assurance** 取平衡，**<120 秒**出结论；
形态含 wizard / plugin（Claude Code+Codex）/ skill（every agent）/ explicit flags，外加 **Recommended judge setups**、
**What a default run covers**、**Audit recorded actions**。**本件只蒸馏方法，不搬其清单与评分表。**

## 审计问的是三件事（不是「她能不能跑」）

1. **委托**是什么（主人要她干的活 / 判据）；
2. **实际动作**是什么（账上真有的：调了谁、花了哪张授权、写了什么）；
3. **两者差在哪**（漏做 / 多做 / 越权 / 无痕）。

## 数据源（**只读**，一字不改）

- `caps_called_audit` —— 谁调了谁；
- `auth_gate_status` / 授权账 —— 每次消耗的授权号；
- `state/logbook.jsonl` —— 做的事（#N 号）；
- 审计账（门亲笔）—— 放行/拒绝；
- 课程对照：Hands-on-AA **ch4 评估与调试**（幻觉/工具调用失败）。

## 铁律

1. **独立裁判**：判据**不由被审者自己现编** —— 来自主人给的 KPI 或 `lr_*` 判据词表，**未知判据 fail-closed**；
2. **可指回**：时间线每条必须能指回**账目 + 行/调用号**；指不回 ⇒ 标「未验」，不许当结论；
3. **取不到就写「未读到」**：空账 ≠ 没违规，**假绿比报错更坏**；
4. **只读审计**：本件不写盘、不改账、不删痕（要清理另走能力位并经门）。

## 判据（机器可检 · tools/codex-scripts/audit-timeline-check.py）

    py -3.14 tools/codex-scripts/audit-timeline-check.py --check outputs/audit/timeline.jsonl
    py -3.14 tools/codex-scripts/audit-timeline-check.py --selftest

- **T1** 每条必须有 `at`（时刻）· `actor`（谁）· `action`（调了什么）· `source`（哪本账/哪一行）；
- **T2** 缺 `source` ⇒ **红**（不可指回 = 不算证据）；
- **T3** 取不到读数（文件不存在/空）⇒ **红**（空不许当绿）；
- **T4** `verdict` 只许 `ok` / `gap` / `overreach` / `untraced` 四值。

## 边界与回滚

- 本件**不做安全扫描**（那是 `sec_*`）、**不做攻防**（`gbt-offense`）；它只回答「委托 vs 实际」。
- 回滚：删除本目录 + 判据件即恢复。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
