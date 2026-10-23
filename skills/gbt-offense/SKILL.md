---
name: gbt-offense
description: 进攻性安全能力（蒸馏自 vxControl/pentagi，Penetration testing AGI）+ 人工授权护栏。当用户说「渗透测试 / 授权测试 / 打一下这个靶机 / 红队 / pentagi / 攻防演练」时使用。
---

# gbt-offense · 进攻性安全（能力**不设限**，只留终端 YES 护栏）

**出处**：https://github.com/vxControl/pentagi （README 现读 HTTP 200）
上游三内核：**① 隔离**（Giving agents Docker without giving away the host）· **② 监督**（Advanced Agent Supervision）·
**③ 多租户**（tenant_id）· 换脑容易（原生支持 OpenAI/Anthropic/Gemini/Bedrock/**DeepSeek**/Ollama/Azure）。

## Owner 令（2026-10-13 · 逐字口径）

> 「**技术层面不能给她有限制只保留人工授权护栏即可**」·「**直接改成终端YES才能使用就好了有时候我需要用到的啊**」

⇒ **本件不写任何「能力禁止」条款**。危险动作照做，**唯一护栏是人工授权**，且**放行从不静默**。

## 授权护栏（唯一的一道闸 · 机制已在，不需要改 policy.py）

    # 主人在终端发一张一次性总控钥匙（AI 无权自发）：
    python -m gbt_allinone auth grant --scope owner_control --ttl 600     # 提示符敲 YES

- 机制：auth_gate.py:243-271 —— **任何缺件的作用域，可用一条 owner_control 顶掉这一次**；
  一旦动用即**写审计 auth_consumed{scope:owner_control, substituted_for:[...]} 并删除该行**（一次性消耗）。
- ⇒ 她**不需要新作用域、不需要改 security/policy.py**：缺什么，主人发一张总控即可放行。
- **AI 永远无权给自己发授权**；没有授权时如实报缺什么，**不许找旁路**。

## 三个必备工程内核（照上游抄，不是限制）

1. **隔离**：进攻性动作**在容器/沙箱里跑**，不给宿主（上游那条 Docker 设计的本意）；
2. **监督**：每一步可观察、可中断（Agent Supervision）；把每步的目标/结果写台账；
3. **留痕**：每次调用落审计（source_kind），**放行与拒绝都留**。

## 边界

- 目标合法性由**主人授权**兜底：只在主人明确指定的目标上动作（授权就是护栏，不含技术限制）。
- 与她已有位的分工：sec_*（扫描/防御验证）走安全域；本件管**进攻性**那条路。
- 课程对照：Hands-on-AA **ch14 智能体攻防** → 本件。

## 与未清事项的关系（如实记）

- owner_control 的替代逻辑**代码在**（auth_gate.py:243-271），但 2026-10-15 首次实测它在
  omni_plug → process 那条路上**没顶上**（仍报 missing_scopes:[process_execute]）⇒ **待核**：
  要么是当时授权已过期或时序问题，要么该路径没走 auth_gate。**核清前，危险动作一律先要两张：process_execute + 总控**。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
