# 原生能力全量索引 · 30 域 / 348 能力位

> 本文是 GBT小土豆V8 全部原生能力的**权威索引**。
>
> **所有数字都是现算的，不是手写的**：跑
> `python docs/native-capabilities/verify_cap.py stats`
> 得到的就是下面这张表。手写的数字会腐烂——2026-10-28 这一版就是把上一版手写错的
> 数字（"30 域"写成"31 域"、若干域位数写错）全部按注册表重算后改回来的。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 域统计（现算 · 数据源 `gbt_allinone/caps_registry.py`）

| 域 | 位数 | 只读 | 需授权 | 域级文档 |
|---|---:|---:|---:|---|
| `creation` | 54 | 32 | 22 | [25-creation.md](25-creation.md) |
| `system` | 51 | 46 | 5 | [01-system-data.md](01-system-data.md) |
| `llm` | 41 | 33 | 8 | [08-llm-gateway.md](08-llm-gateway.md) |
| `security` | 29 | 20 | 9 | [10-security.md](10-security.md) |
| `mind` | 19 | 18 | 1 | [12-mind-engine.md](12-mind-engine.md) |
| `pipeline` | 18 | 18 | 0 | [05-pipeline.md](05-pipeline.md) |
| `tentacle` | 18 | 13 | 5 | [09-tentacle.md](09-tentacle.md) |
| `recon` | 17 | 11 | 6 | [14-recon.md](14-recon.md) |
| `video` | 14 | 5 | 9 | [26-video-media.md](26-video-media.md) |
| `data` | 12 | 9 | 3 | [01-system-data.md](01-system-data.md) |
| `engine` | 10 | 9 | 1 | [02-engine.md](02-engine.md) |
| `device` | 9 | 9 | 0 | [15-device.md](15-device.md) |
| `tools` | 9 | 7 | 2 | [27-tools.md](27-tools.md) |
| `integration` | 7 | 3 | 4 | [28-integration.md](28-integration.md) |
| `devour` | 5 | 5 | 0 | [11-devour.md](11-devour.md) |
| `vision` | 5 | 4 | 1 | [16-vision.md](16-vision.md) |
| `finance` | 4 | 4 | 0 | [19-finance.md](19-finance.md) |
| `longrun` | 4 | 4 | 0 | [13-longrun.md](13-longrun.md) |
| `voice` | 4 | 4 | 0 | [17-voice.md](17-voice.md) |
| `automation` | 2 | 1 | 1 | [18-browser.md](18-browser.md) |
| `brain` | 2 | 2 | 0 | [06-brain-exec.md](06-brain-exec.md) |
| `collab` | 2 | 1 | 1 | [28-integration.md](28-integration.md) |
| `desktop` | 2 | 1 | 1 | [09-tentacle.md](09-tentacle.md) |
| `infra` | 2 | 2 | 0 | [23-deployment.md](23-deployment.md) |
| `project` | 2 | 2 | 0 | [19-finance.md](19-finance.md) |
| `social` | 2 | 2 | 0 | [28-integration.md](28-integration.md) |
| `comms` | 1 | 1 | 0 | [28-integration.md](28-integration.md) |
| `framework` | 1 | 1 | 0 | [01-system-data.md](01-system-data.md) |
| `image_video` | 1 | 1 | 0 | [26-video-media.md](26-video-media.md) |
| `life` | 1 | 1 | 0 | [12-mind-engine.md](12-mind-engine.md) |
| **合计** | **348** | **269** | **79** | — |

**读法**：`只读` = 不改状态、不出网，随便调；`需授权` = 会写盘、花钱或把数据发到外部，**必须先由人发一张票**。

---

## 25 篇专业文档

| 编号 | 文档 | 覆盖 |
|---|---|---|
| — | [README.md](README.md) | 总纲（架构图 + 设计原则 + 索引） |
| 00 | [00-INDEX.md](00-INDEX.md) | 本文（全量索引） |
| 01 | [01-system-data.md](01-system-data.md) | `system` · `data` · `framework`（体检层/审计层/卫生层） |
| 02 | [02-engine.md](02-engine.md) | `engine`（DAG / 传输算子 / 条件分流 / 缓存） |
| 03 | [03-mirror-space.md](03-mirror-space.md) | `mirror_*` 十位（成形/体检/晋升/回滚） |
| 04 | [04-room-space.md](04-room-space.md) | `room_space`（1 位 · 16 op） |
| 05 | [05-pipeline.md](05-pipeline.md) | `pipeline`（唯一交付通道 / 三阶段 / 版本化） |
| 06 | [06-brain-exec.md](06-brain-exec.md) | `brain`（route→execute→verify→health） |
| 07 | [07-think-loop.md](07-think-loop.md) | `think_loop`（完整心智循环七步） |
| 08 | [08-llm-gateway.md](08-llm-gateway.md) | `llm`（密钥链 / 自主编排 / 多模态端口） |
| 09 | [09-tentacle.md](09-tentacle.md) | `tentacle` · `desktop`（三通道感官 / 六铁律 / MCP） |
| 10 | [10-security.md](10-security.md) | `security`（25 条检测 / 红蓝双模） |
| 11 | [11-devour.md](11-devour.md) | `devour`（吞噬→反思→消化→重组→进化） |
| 12 | [12-mind-engine.md](12-mind-engine.md) | `mind` · `life`（12 情绪维 / 8 需求维） |
| 13 | [13-longrun.md](13-longrun.md) | `longrun`（非 LLM 机械验收 / 跨进程可续） |
| 14 | [14-recon.md](14-recon.md) | `recon`（OSINT 七维 / 知识图谱 / 技能蒸馏） |
| 15 | [15-device.md](15-device.md) | `device`（蓝牙 BLE + 身体桥七位） |
| 16 | [16-vision.md](16-vision.md) | `vision`（感知指纹 / 变化定位 / 流回放） |
| 17 | [17-voice.md](17-voice.md) | `voice`（TTS / ASR / 管弦乐 / WASAPI） |
| 18 | [18-browser.md](18-browser.md) | `automation` + 穿透网 / 自适应抓取 / 逐页扫 |
| 19 | [19-finance.md](19-finance.md) | `finance` · `project`（策略 / 回测 / 压缩直达） |
| 20 | [20-auth-gate.md](20-auth-gate.md) | `auth_gate_status`（15 作用域 / 三道护栏） |
| 21 | [21-brain-vault.md](21-brain-vault.md) | `brain_vault`（追加式 / 无删除路径） |
| 22 | [22-record-grid.md](22-record-grid.md) | `record_grid`（七路转接 / 回写自证） |
| 23 | [23-deployment.md](23-deployment.md) | `pipeline` 部署子集 · `infra`（一键部署 / 接管队列） |
| 24 | [24-digital-human.md](24-digital-human.md) | `digital_human` · `dh_*` · `body_*`（12 位） |
| 25 | [25-creation.md](25-creation.md) | `creation`（镜头导演 / 节点即触手 / 作品解剖） |
| 26 | [26-video-media.md](26-video-media.md) | `video` · `image_video`（剪辑 / 音频 / 许可 / 钢印） |
| 27 | [27-tools.md](27-tools.md) | `tools`（改代码唯一过门入口 / 版本库读写） |
| 28 | [28-integration.md](28-integration.md) | `integration` · `collab` · `social` · `comms`（12 位） |

---

## 怎么自己核对（三步）

```bash
# 1) 看某一位的真实登记
python docs/native-capabilities/verify_cap.py show mirror_ascend

# 2) 看某域全部能力位
python docs/native-capabilities/verify_cap.py domain security

# 3) 逐位对账：每个能力位是否都指得到一篇存在的文档
python docs/native-capabilities/verify_cap.py check
```

**当前对账结果**：`348/348 位有文档 · 0 域无域级文档 · 0 条不过`

对账脚本只读 AST，**不 import 包、不执行任何能力**——可以放心在 CI 里跑。

---

## 调用方式

```python
import gbt_allinone as gbt

# 列出全部可调能力
caps = gbt.list_capabilities()

# 调用任意能力
result = gbt.run_task("<能力位名>", {<参数>})
```

---

## 安全边界（只禁一小撮，无绕过入口）

按名禁用的危险行为（返回 `denied`，无执行路径）：

- 付费墙绕过
- 会话 / 数据劫持
- 无授权远程接管
- 键鼠监控
- 屏幕窃取
- 设备接管
- 渗透攻击（非授权目标）
- 资产冻结要挟
- 凭证窃取
- 社工钓鱼

> 拒绝的永远只是**具体行为的风险**，不是这个人：说清为什么不行，再给出怎样才行。

---

## 口径更正记录（诚实账）

| 日期 | 旧说法 | 现读事实 |
|---|---|---|
| 2026-10-28 | "30 域 / 348+ 能力位"（手写） | **30 域 / 348 位**（现算）；`+` 号去掉，因为没有第 349 位 |
| 2026-10-28 | `room_space` 是 19 个能力位 | **1 个能力位 + 16 个 op** |
| 2026-10-28 | `native_browser` / `scrapling_cap` | 真名 `browser` / `scrapling` |
| 2026-10-28 | `dh_rig` / `body_bridge` | 真名 `dh_asset_gate` / `body_*` 七位 |
| 2026-10-28 | `device` 域 2 位 | **9 位**（含 `body_*` 七位） |

> 这些更正全部由 `verify_cap.py check` 抓出。**工具抓出来的错，比自己读三遍都可靠。**

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
