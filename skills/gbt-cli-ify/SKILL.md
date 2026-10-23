---
name: gbt-cli-ify
description: 软件命令化规程（蒸馏自 HKUDS/CLI-Anything，Making ALL Software Agent-Native）—— 选型闸三档（已有 CLI 就用它·有 API 就包 CLI·只有 GUI 才走触手）+ 命令化六步 + 登记表 + 判据。当用户说「把这个软件命令化 / 给它做个 CLI / 别用 GUI 点 / cli-ify / 统一 API」时使用。
---

# gbt-cli-ify · 软件命令化（CLI-Anything 蒸馏）

**出处（验真过）**：raw.githubusercontent.com/HKUDS/CLI-Anything/main/README.md（HTTP 200），标题
The Agent-Software Gap · Let Agents Take Your Workflows · **Unify Scattered APIs into One CLI** ·
**Replace or Supercharge GUI Agents** · **Fully Automated 7-Phase Pipeline** · CLI-Hub registry。
**只蒸馏它的工程思想，不搬它的代码与 registry 内容。**

## 选型闸（三档，**先判再动**）

1. 该软件**已有 CLI** ⇒ **直接用**，不许上 GUI（省时省钱、可复跑、可判据）；
2. **只有 API** ⇒ 包成 CLI 面（走「命令化六步」）；
3. **只有 GUI** ⇒ 才走触手/浏览器（`gbt-tentacle` / `browser`），并在登记表里标「只能 GUI」。

## 命令化六步（与 `gbt-vendor-intake` 同构）

1. 探接口（`--help` / API 文档 / 进程参数，**现读**不猜）；
2. 定命令面：`<tool> <verb> <args>`（动词要短、要能组合）；
3. 包成能力位或插座（走 `omni_plug` 的 process/api 插座即可，不必新模块）；
4. **登记进 `state/cli-surfaces.json`**（name / entry / verbs / evidence / status）；
5. 接路由（让「人一句话 → 哪条命令」有落点）；
6. **挂判据**：`--help` 可跑 + 至少一条真用例可复跑。

## 判据（机器可检 · `tools/codex-scripts/cli-surface-check.py`）

    py -3.14 tools/codex-scripts/cli-surface-check.py            # 查登记表
    py -3.14 tools/codex-scripts/cli-surface-check.py --selftest  # 正例绿 / 三条负例红

- **C1** 登记表可读（缺文件 ⇒ **红**，不许当空表绿）；
- **C2** 每条必须有 `name` + `entry` + 至少一个 `verb`；
- **C3** 每条必须有 `evidence`（可复跑命令或判据文件路径）；
- **C4** `status` 只能取 `cli` / `api-wrapped` / `gui-only` 三值（别的值 ⇒ 红）。

## 「新增即清旧」在这里的落法

新增一条 CLI 面时，**同一步**把该软件**旧的 GUI 路径**标为退役（`status` 改 `gui-only` + 备注指向新 CLI），
并在 `supersede-check.py --check` 里不许出现「指针仍指旧版」。

## 边界与回滚

- 本件只**造命令面与登记**，不做安装、不改远端、不动别人目录。
- 回滚：删除本目录 + 删登记表即恢复。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
