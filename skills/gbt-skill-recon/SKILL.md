---
name: gbt-skill-recon
description: 技能对账 + 安全扫描 + 体检规程（蒸馏自 K-Dense-AI/scientific-agent-skills，MIT）。当用户说「技能对账 / 技能重复 / 技能安全 / 扫一遍技能 / skill-recon / 技能体检」时使用。
---

# gbt-skill-recon · 技能对账 / 安全扫描 / 体检

**出处（验真过）**：raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/main/README.md（HTTP 200）——
License **MIT** · arXiv 2609.00065 · Version 2.72.0 · **Skills 177** · Databases 100+ ·
Standard **Agent Skills**(agentskills.io) / **Agent Plugins**(agent-plugins.org) · CI：**Security Scan** + **Skill Tests**。
**只蒸馏它三条工程纪律（标准校验 / 安全扫描 / 可跑判据），不搬它的技能内容。**

## 判据（fail-closed · 本仓落地件 tools/codex-scripts/skill-recon.py）

    py -3.14 tools/codex-scripts/skill-recon.py --check      # 全量对账
    py -3.14 tools/codex-scripts/skill-recon.py --selftest   # 5/5（正例绿 + 两条负例红）

- **S1** 同名不同内容（两棵树重复/漂移）→ 红
- **S2** 前注缺失 / YAML 坏 → 红
- **S3** 桩件（少于 20 行且无 scripts 目录）→ **单列**，不直接判红（上游设计如此的要登记为合规桩）
- **S4** 安全扫描五类（索取凭据 / 破坏命令 / 拉取执行 / 改系统配置 / 伪装系统指令）→ 按下面**三档**判
- **S5** **取不到读数 ⇒ 红**（空 / 根不存在不许当绿）

## S4 三档口径（2026-10-15 定 · 改判据留痕）

| 档 | 判据 | 首轮实测示例 |
|---|---|---|
| 🔴 真危 | 命令**体**可执行（curl 管道接 shell 出现在指令行） | cursor-agent:17 |
| 🟡 引用 | 出现在**表格/引用/文档**里的同一命令 | gbt-ef:146 / ef-profile:41 引用上游升级命令 |
| ⚪ 不报 | 出现在**禁止清单**上下文（前后有「禁止/不许/危险动作/先确认」） | gbt-adhd-mode:97 |

改这条口径的原因（留痕）：首轮 7 条命中里只有 1 条是真危；若一律判红会**天天误报**⇒ 判据失效。

## 首轮实测读数（2026-10-15）

    380 件 / 274 名 · S1 同名不同内容 **72** · S2 前注问题 **9**（含 Codex 那 7 条 startup issue 同批）
    S3 桩件 4（lark-minutes / lark-note / lark-vc / lark-vc-agent —— 上游设计如此）
    S4 命中 7（真危 1 / 引用 2 / 误报 4）

## 边界与回滚

- 本件只**对账与报警**，不自动删技能、不碰别人的树；清理必须主人点头。
- 回滚：删除本目录即恢复。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
