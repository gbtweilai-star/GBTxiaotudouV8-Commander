---
name: gbt-chinese
displayName: GBT · chinese-* 技能簇用法规程（4 条：中文工程化与研发协作规范）
version: 1.0.0
description: GBT小土豆V8 的 `chinese-*` 技能簇用法规程。这个簇共 4 条，源自 superpowers-zh 中文研发协作规范：`chinese-code-review`（代码审查话术与分级）、`chinese-commit-conventions`（Commit 与 Changelog 规范）、`chinese-documentation`（中文文档与排版指北）、`chinese-git-workflow`（国内平台 Gitee/极狐/CNB/Coding 接入与镜像）。本文件把每条逐个点名：用途、规程、核心判据、落点与适用边界。当用户需要规范化中文代码审查、中文提交日志、文档排版指北或国内 Git 平台协同配置时使用。
triggers:
  - "chinese-code-review"
  - "chinese-commit-conventions"
  - "chinese-documentation"
  - "chinese-git-workflow"
  - "中文审查"
  - "中文commit"
  - "中文文档排版"
  - "国内git"
---

# GBT · chinese-* 技能簇用法规程（4 条：中文工程化与研发协作规范）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`chinese-*` 是工程研发规范簇（4 条），落在 `skills/superpowers/chinese-*`。
> 涵盖中文代码评审、中文提交说明、中文文案排版规范以及国内 Git 平台工作流配置。
> 本文件把每条逐个点名，钉死用途、判据与适用边界。

---

## 0. 四条技能清单

| # | 技能名称 | 核心职责 | 判据与产出 |
|---|---|---|---|
| 1 | `chinese-code-review` | 中文 Code Review 话术、分级标注与反模式应对 | 标注分级（必须修复 / 建议修改 / 仅供参考），用建议代替命令 |
| 2 | `chinese-commit-conventions` | Conventional Commits 中文适配与自动化 Changelog 配置 | 提交信息格式合规、中英文混排空格规范、类型动词准确 |
| 3 | `chinese-documentation` | 中文技术文案排版指北、全半角标点与术语规范 | 符合中文排版指北（盘古之白、弯引号纠正、专有名词大小写） |
| 4 | `chinese-git-workflow` | Gitee / 极狐 GitLab / CNB / Coding 平台的配置与镜像同步 | 凭据管理、SSH/HTTPS 配置差异、CI 镜像同步脚本 |

---

## 1. 逐条点名与规范要点

### 1.1 `chinese-code-review`（代码审查沟通）
- **核心原则**：用“建议”代替“命令”，用“提问”代替“否定”，绝不因人情客套放过 bug。
- **标注体系**：
  - `[必须修复]`：阻断性缺陷、安全漏洞、严重性能倒退。
  - `[建议修改]`：代码坏味道、轻度冗余、边界不够清晰。
  - `[仅供参考]` / `[讨论]`：非阻塞性架构思考、风格探讨。

### 1.2 `chinese-commit-conventions`（提交日志）
- **格式标准**：`<type>(<scope>): <subject>`。
- **动词映射**：
  - `feat`: 新功能；`fix`: 修复 bug；`docs`: 文档变动；`style`: 格式调整；`refactor`: 重构；`perf`: 性能优化；`test`: 测试；`chore`: 构建杂务。
- **中文规则**：首字母小写或中文无须大写，结尾不加句号，中英文间留空格。

### 1.3 `chinese-documentation`（文案排版）
- **标点规则**：中文语境使用全角标点，英文/代码内使用半角。
- **排版间隙**：汉字与英文字母/数字之间增加一个半角空格（盘古之白）；遇到全角标点不加空格。
- **专有名词**：保留权威大小写（如 GitHub、Node.js、iOS、JavaScript）。

### 1.4 `chinese-git-workflow`（平台工作流）
- **平台特性**：针对国内平台（Gitee、极狐 GitLab、CNB、Coding）特有的 SSH key 规则、PR/MR 提交流程、Webhook 触发规范。
- **镜像同步**：双远端推送与备份，避免单一供应商锁定。

---

## 2. 纪律与红线

1. **零破坏性**：本簇技能属于协作与规范指引，不直接对生产环境做未经确认的代码覆写。
2. **纯文本与规范优先**：审查与文档一律按规范输出，不伪造审核通过凭据。
3. **安全凭据绝不入档**：Git 凭据、私钥严禁提交到版本库。

---

## 3. 固化与出处

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-chinese/SKILL.md` |
| 本规程（装机） | `~/.agents/skills/gbt-chinese/SKILL.md` 与 `~/.openclaw-autoclaw/skills/gbt-chinese/SKILL.md` |
| 簇登记 | `tools/codex-scripts/omni.py` 的 `DISTILLED_CLUSTERS["chinese"]` |
