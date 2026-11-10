# 能力总表 · 共 428 位 / 32 个域

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。机器可读版：[`data/capabilities.json`](../data/capabilities.json)。

- **口径**：本表 = 注册表现读（428 位 / 32 域）。`data/capabilities.json`、`docs/capabilities/*.md` 与 README 徽章同源同数 —— 全部由本脚本从 `caps_registry.py` 现读生成，不手抄。

- **零作用域 390 位**（本表「只读」列）：空 payload 下不需要任何票，可直接调用。
- **挂作用域 38 位**：会写盘 / 花钱 / 出网，调用前必须先过主人给的授权门。
- **另一套口径（按 `safe`）**：不改状态 340 位 / 会改状态 88 位 —— 与上面的零作用域**不是同一个数**，别混着报。

| 域 | 中文 | 位数 | 只读 | 需授权 | 详解 |
|---|---|---|---|---|---|
| `system` | 系统 | 60 | 60 | 0 | [打开](capabilities/system.md) |
| `creation` | 创作 | 59 | 58 | 1 | [打开](capabilities/creation.md) |
| `llm` | 大模型与大脑 | 43 | 35 | 8 | [打开](capabilities/llm.md) |
| `security` | 安全 | 34 | 29 | 5 | [打开](capabilities/security.md) |
| `tentacle` | 触手（手眼网耳） | 30 | 25 | 5 | [打开](capabilities/tentacle.md) |
| `mind` | 心智 | 27 | 27 | 0 | [打开](capabilities/mind.md) |
| `device` | 设备 | 19 | 16 | 3 | [打开](capabilities/device.md) |
| `pipeline` | 流水线与发布 | 18 | 9 | 9 | [打开](capabilities/pipeline.md) |
| `recon` | 只读侦察 | 18 | 18 | 0 | [打开](capabilities/recon.md) |
| `video` | 视频 | 18 | 18 | 0 | [打开](capabilities/video.md) |
| `vision` | 视觉 | 13 | 13 | 0 | [打开](capabilities/vision.md) |
| `data` | 数据 | 12 | 11 | 1 | [打开](capabilities/data.md) |
| `engine` | 引擎（工作流/定时） | 12 | 11 | 1 | [打开](capabilities/engine.md) |
| `integration` | 集成（飞书/Notion/CLI） | 11 | 8 | 3 | [打开](capabilities/integration.md) |
| `tools` | 工具与改代码 | 9 | 8 | 1 | [打开](capabilities/tools.md) |
| `voice` | 语音 | 7 | 7 | 0 | [打开](capabilities/voice.md) |
| `devour` | 吞天（自我进化） | 6 | 5 | 1 | [打开](capabilities/devour.md) |
| `brain` | 梦境/闭环 | 4 | 4 | 0 | [打开](capabilities/brain.md) |
| `finance` | 财务 | 4 | 4 | 0 | [打开](capabilities/finance.md) |
| `longrun` | 长程任务 | 4 | 4 | 0 | [打开](capabilities/longrun.md) |
| `project` | 项目测绘 | 3 | 3 | 0 | [打开](capabilities/project.md) |
| `automation` | 浏览器自动化 | 2 | 2 | 0 | [打开](capabilities/automation.md) |
| `collab` | 协作（信息素场地） | 2 | 2 | 0 | [打开](capabilities/collab.md) |
| `comms` | 通信 | 2 | 2 | 0 | [打开](capabilities/comms.md) |
| `desktop` | 桌面智能体 | 2 | 2 | 0 | [打开](capabilities/desktop.md) |
| `infra` | 基础设施（云电脑） | 2 | 2 | 0 | [打开](capabilities/infra.md) |
| `social` | 社交发布 | 2 | 2 | 0 | [打开](capabilities/social.md) |
| `body_control` | 身体控制 | 1 | 1 | 0 | [打开](capabilities/body_control.md) |
| `framework` | 框架自省 | 1 | 1 | 0 | [打开](capabilities/framework.md) |
| `image_video` | 图像/视频生成 | 1 | 1 | 0 | [打开](capabilities/image_video.md) |
| `life` | 生命档案 | 1 | 1 | 0 | [打开](capabilities/life.md) |
| `ui` | 界面 | 1 | 1 | 0 | [打开](capabilities/ui.md) |

---

回到 [README](../README.md)
