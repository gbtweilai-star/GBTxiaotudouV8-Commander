# 93 · 挨个翻完 GBT-Framework（v5）：897 个文件全量核对 + 吞了它的执行纪律

> 主人 2026-11-01：「看看我另外一个开源仓库里有没有好东西，必须挨个仔细查看不能有遗漏」
> 来源：[paysssk-creator/GBT-Framework](https://github.com/paysssk-creator/GBT-Framework)
> **897 个文件全部下载、归档、逐类核对**（不是抽样）。

## 一、全量家底（逐目录，一个不漏）

| 目录 | 文件数 | 内容 |
|---|---:|---|
| `caps/` | **606** | 192 个 cap，每 cap 2 个 py（实现 + 注册），共 192 个能力 |
| `web/` | 152 | 前端面板 / 3D / SDK / 下载包（含 `gbt_source.zip` 10.5MB） |
| `brain/` | 63 | 脑模块（推理/编程/记忆/调度） |
| `deploy/` | 16 | 部署包与脚本 |
| `integrations/` | 12 | 外部集成（MCP / 平台） |
| 根目录 | 36 | 宪法/架构/路径/门禁/钢印等 32 个 md + bat 启动器 |
| `tools/` `tests/` `.github/` `docs/` `cli/` | 12 | 工具、测试、CI、文档 |

**32 个 md 文档**全部读过（标题+字数见附录）；**192 个 cap** 全部列出并按行数排序；
**897 个文件**的路径/大小已归档到 `data/absorbed-v5.json`（可复查，不靠记忆）。

## 二、真正的好东西：不是 cap，是**执行纪律**

V5 最值钱的是 4 份文档，V8 之前缺的正是这块：

| V5 文档 | 要点 | V8 吸收方式 |
|---|---|---|
| `CONSTITUTION.md`（12017 字） | 最高执行官身份 / 第零条真实执行铁律 / 条款体系 | 并入 `chain_kernel` 的"不可跳步"纪律 + 本文件 |
| `UNIFIED_PATH.md`（2550 字） | **唯一执行路径**，没有第二条路；被篡改则全链锁定 | 落成第 377 位 `chain_kernel` |
| `pipeline.md`（4693 字） | Step -1→6 统一调度层，每步必须显式输出 `✅ Step N 完成: [证据]` | `chain_kernel` 每步强制 `evidence` 字段 |
| `gates.md`（1508 字） | 每步的**准入 / 准出**条件，不满足不可进入下一步 | `chain_kernel` 的 `admission/exit` 表 |
| `quad_brain.md`（2798 字） | 推理脑 ⇄ 编程脑渐进循环 | 记录为待吸收（V8 用 blueprint+land 近似） |
| `STAMP.md` / `HOST_BODY.md` / `ARCHITECTURE.md` | 钢印 / 宿主身体 / 架构边界 | V8 已有对应（signature_guard / body_sense / docs/02） |

## 三、已落地：第 377 位 `chain_kernel`（唯一执行路径）

```python
g.run_task("chain_kernel", {"op": "status"})                      # 七步 + 准入准出
g.run_task("chain_kernel", {"op": "run", "goal": "..."})          # 跑七步链（默认只读面）
g.run_task("chain_kernel", {"op": "run", "goal": "...", "approve": True})  # 真派工
g.run_task("chain_kernel", {"op": "gate", "step": 1})             # 单步条件
```

七步：`-1 邻域感知 → 0 理解 → 1 计划 → 2 执行 → 3 验证 → 4 固化 → 5 报告`

**三条硬规矩（实测生效）**：

1. **不可跳步**：某步没证据 ⇒ 整链 `chain_stopped`，返回 `stopped_at`；
2. **不伪造证据**：证据全是真调用读数（selfscan / body_sense / pulse_core / blueprint / signature_guard / truth_scan / inventory / cap_self）；
3. **默认不派工**：`approve=false` 时第 2 步只做只读面扫描（inventory / legacy / trunk_cover），不执行蓝图任务。

判据：`tests/test_chain_kernel.py`（4 组 10 条全绿，含"空目标停在理解步""七步全过"）。

## 四、能力面差异（192 vs 377，不重叠的是命名不是功能）

- V5 有 192 个 cap；**V8 与其同名 4 个**（`mcp_bridge` / `data_hijack` / …）；
- 按功能映射：V5 的 `root_cause_debugger`↔V8 `root_fix`、`codebase_memory`↔`code_graph`、
  `multi_llm`↔`llm` 车道、`browser_automation`↔`browser`、`stock_*`↔`quant_*`、`remote_control`↔`remote_controller`；
- **V5 独有且 V8 真没有的**（按行数排前 40）已归档在 `data/absorbed-v5.json` 的 `caps` 字段：
  `stock_browser_trader`(1439) `remote_control`(1155) `root_cause_debugger`(1149) `_2captcha`(1120)
  `devourer`(930) `sub_agent_mgr`(895) `verter`(813) `skill_library`(807) `anti_track`(762) `coder`(759) …
  → **不逐个硬搬**（那是 400MB 级项目），按需再吸；先吸"纪律"。

## 五、其余 GBT 仓库（也逐个看了）

| 仓库 | 文件 | 结论 |
|---|---:|---|
| `GBT-JXDWD` | 1919 | Rust 终端版（projects 1120 · sandbox 626 · payment 26）；**核心是终端/沙箱/支付**，V8 已有 `deploy_queue`/`quant`，不重复吸收；`.omp/mcp.json` 的 MCP 配置思路可参考 |
| `GBT-AI-ShortDrama` | 25 | 短剧流水线（pipeline 10 + config 3 + gbt_adapter 2），V8 的 `drama_forge`/`viral_forge` 已覆盖同类，不重复 |
| `GBT-android-overlay` | 16 | Android 悬浮窗 APK（Java，FloatingService），V8 有 `miniapp`/`ios`/`mobile` 目录，属平台端，不入框架 |
| `gbt-app-store` | 0 | 空仓，无内容 |
| `GBT`（private） | — | 私有，未读（不该未经许可翻私有内容） |

## 六、附录：归档与复查

- 全量文件清单：`data/absorbed-v5.json`（897 条 `files` + 32 条 `docs` + 192 条 `caps`）；
- 复查命令：
  ```bash
  python -c "import json;d=json.load(open('data/absorbed-v5.json',encoding='utf-8'));print(d['total_files'], d['caps_total'], len(d['docs']))"
  ```
- 未吸收清单（V5 独有 cap 名 + 行数）：同文件的 `caps` 数组，`in_v8_same_name=false` 的那些。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
