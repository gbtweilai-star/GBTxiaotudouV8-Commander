# 115 · 触手职业表（21 种职业，全方位覆盖 385/385，编程是首席）

> 主人 2026-11-01：「对了最重要的，触手的编程职业呢？」
> —— 触手不是一堆能力位，是**有职业的**。这一轮把职业建成真实数据 + 认知界面第 11 视图。

## 一、数据来源（现读，不手填）

`tools/gen-professions.py` 读 `gbt_allinone.caps_registry.BENIGN_CAPS`（385 位），
按写死的职业归属（域 + 名字模式）算出每个职业的：域、能力位数、代表能力位、工具、KPI。
输出 `data/professions.json`，再由 `gen-console-data.py` 并进 `console-data.js`。

**全方位口径（主人令 2026-11-01）**：
- 每个能力位**必须有职业**：`coverage.orphans` 必须为空；有孤儿进「通用 / 机动（补位）」并在审计里如实标出；
- 每个域**必须被覆盖**：`domains_covered` 必须 = `domains_total`；
- 当前实测：**21 职业 · 覆盖 385/385 能力位 · 30/30 域 · 孤儿 0 · 补位 0**。

## 二、21 种职业（编程首席 · 全覆盖）

| 职业 | 域 | 能力位 | 工具 | KPI |
|---|---|---|---|---|
| **编程工程师（首席）** | tools/pipeline/project/automation/framework | 47 | 终端·编辑器·git_read/git_write·run_task 真跑·五处落位 | 改完即测·旧物清零·签名不丢 |
| 代码审查 | security/mind | 57 | 静态审查·五维自检·账本对账 | 0 未审合并 |
| 测试 / 验证 | pipeline/data | 37 | pytest 断言·真跑读数字·截图/哈希 | 每条结论有数字 |
| 安全 / 穿透 | security/recon | 57 | penetrating_cross_scan·无死角口径·疑点→反思→穿透 | coverage=1.0 · dead_spots=0 |
| 运维 / 守护 | system/engine/infra/device/desktop | 86 | console-server 自启·engine-on/off·服务巡检 | 服务在线·重启自动恢复 |
| 架构 / 设计 | mind/tentacle/framework | 57 | chain_kernel 七步·caps_registry·doc_counts 五处 | 能力位三处一致 |
| 数据 / 金融 | data/finance/longrun | 31 | 账本/指标·回测·数据管道 | 同一口径两处一致 |
| 视觉 / 图像 | vision/image_video/creation | 67 | 11 个视觉能力位·截图/识别/图表 | 看图说得出依据 |
| 语音 / 媒体 | voice/video/comms | 22 | 语音输入输出·视频剪辑·字幕 | 产出可播放 |
| 研究 / 侦察 | recon/devour/llm | 75 | 外部检索·蒸馏沉淀·来源标注 | 每条来源可查 |
| 文档 / 写作 | creation/social | 63 | docs/ 编号·CHANGELOG·README 同步 | docs 计数同步 |
| 协同 / 指挥 | tentacle/collab/brain/longrun | 56 | run_task 派单·orchestration-ledger·审计 | 每次派单都有账 |
| **短视频编导** | video/image_video/creation | 79 | 分镜脚本·视频生成/剪辑·封面标题·节奏钩子 | 完播率·前 3 秒留人 |
| **音乐制作** | voice/comms | 10 | 词曲生成·编曲/混音·母带·发行 | 可听成曲·响度达标·版权可查 |
| **影视 / 电影** | video/image_video | 22 | 剧本/分镜·镜头调度·生成合成·成片输出 | 镜头语言成体系·成片可交付 |
| **数字人 / 直播** | desktop/device/creation | 76 | 骨骼绑定·口型驱动·动作库·直播推流 | 口型对得上·不崩脸·能直播 |
| **设计 / 美术** | creation/image_video | 59 | 设计令牌·配色版式·品牌资产·审美闸 | 过审美闸·可复用令牌 |
| **游戏 / 3D** | creation/device | 70 | Blender·Three.js·骨骼绑定·场景搭建 | 60fps·可交互·可导出 |
| **集成 / 连接** | integration/comms/social | MCP 注册/发现·IM 桥·Webhook | 接通可验证·权限最小化 |
| **命令行 / 入口** | tools | CLI·终端·对话入口 | 一条命令能跑 |
| **生活 / 陪伴** | life | 提醒·习惯·陪伴对话 | 不打扰·不越界 |

## 三、编程职业具体干什么（不是头衔）

1. **读架构/契约**：先看 `PROJECT_BLUEPRINT.md`、`caps_registry`、五处落位规矩；
2. **改代码**：`code_patch` / `edit_pipeline` / 直接编辑；改动前先读文件（FS 观测策略）；
3. **真跑**：`run_task` 派单 + 测试；不跑不算完；
4. **五处落位**：注册表 / 派发 / 策略 scope / 测试 / 文档账本；
5. **清旧物**：旧面板/旧代码不留（legacy_guard 会查）；
6. **交付**：CHANGELOG + 账本 + 签名（不可删改归属）。

## 四、界面

- 页签：`对话 / 功能表 / 技能栏 / 3D 星图 / 大脑执行层 / 万能插 / 触手协作 / 思维导图 / 穿透扫描 / 职业 / 仪表盘`
- 地址：`http://127.0.0.1:8766/console/index.html#prof`
- 标记：`data-prof = ok:21职业+编程首席`；首席卡有 `CHIEF` 徽标 + 暖色描边
- 截图：`assets/panels/console-prof.webp`

## 五、边界（如实）

- 职业归属是**声明式映射**（域 + 名字模式），不是自动分类器；新能力位会按域自动落进对应职业；
- 能力位数会随注册表变化（当前 385 → 各职业合计 655，含跨域重复）；
- 还没做"按职业派单"的调度器（现在派单仍按能力位），下一步可加 `profession` 维度路由。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
