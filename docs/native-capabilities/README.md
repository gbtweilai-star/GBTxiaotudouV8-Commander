# GBT小土豆V8 · 原生能力全量开源文档

> 本目录是 GBT小土豆V8 框架所有原生能力的**专业级开源文档**，按能力域独立成篇。
> 每篇含：架构设计 · 能力清单 · API 参考 · 使用示例 · 安全边界 · 实现原理 · 性能基线。
>
> **全部数字现算，不手写**：跑 `python docs/native-capabilities/verify_cap.py stats` 得到的就是下表。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 一句话

> **348 个能力位 / 30 个域**，每一个都能被单独查阅、单独核对、单独调用。
> 不是"我声称有 348 个"，是"你跑一行命令就能数出 348 个"。

```bash
python docs/native-capabilities/verify_cap.py stats    # 数一遍
python docs/native-capabilities/verify_cap.py check    # 核对文档覆盖
```

**当前对账**：`348/348 位有文档 · 0 域无域级文档 · 0 条不过`

---

## 文档索引

| 编号 | 覆盖域 | 文档 | 位数 | 讲什么 |
|---|---|---|---:|---|
| 00 | — | [00-INDEX.md](00-INDEX.md) | 348 | **全量索引**（域统计 + 25 篇导航 + 口径更正记录） |
| 01 | `system` `data` `framework` | [01-system-data.md](01-system-data.md) | 64 | 体检层 / 审计层 / 卫生层 / 数据工具 |
| 02 | `engine` | [02-engine.md](02-engine.md) | 10 | DAG 工作流 / 传输算子 / 条件分流 / 缓存 |
| 03 | `mirror_*` 十位 | [03-mirror-space.md](03-mirror-space.md) | 10 | 维度成形 / 体检 / 晋升 / 时间线回滚 |
| 04 | `room_space` | [04-room-space.md](04-room-space.md) | 1（16 op） | 隔离排练现实 / 房间正路闭环 |
| 05 | `pipeline` | [05-pipeline.md](05-pipeline.md) | 18 | 唯一交付通道 / 三阶段 / 版本化 / 回滚 |
| 06 | `brain` | [06-brain-exec.md](06-brain-exec.md) | 2 | route → execute → verify → health |
| 07 | `think_loop` | [07-think-loop.md](07-think-loop.md) | 1 | 完整心智循环七步 |
| 08 | `llm` | [08-llm-gateway.md](08-llm-gateway.md) | 41 | 密钥链 / 自主编排 / 多模态端口 / 统一密钥网关 |
| 09 | `tentacle` `desktop` | [09-tentacle.md](09-tentacle.md) | 20 | 三通道感官 / 六铁律 / MCP 契约层 / 桌面指挥官 |
| 10 | `security` | [10-security.md](10-security.md) | 29 | 攻击面测绘 / 25 条检测 / 利用链 / 蓝队防御 |
| 11 | `devour` | [11-devour.md](11-devour.md) | 5 | 吞噬 → 反思 → 消化 → 重组 → 进化 |
| 12 | `mind` `life` | [12-mind-engine.md](12-mind-engine.md) | 20 | 功能型人类心智闭环 / 12 情绪维 / 8 需求维 |
| 13 | `longrun` | [13-longrun.md](13-longrun.md) | 4 | 非 LLM 机械验收 / 重试 / 停滞升级 / 跨进程可续 |
| 14 | `recon` | [14-recon.md](14-recon.md) | 17 | OSINT 七维 / 自适应抓取 / 知识图谱 / 技能蒸馏 |
| 15 | `device` | [15-device.md](15-device.md) | 9 | 蓝牙 BLE GATT / 身体桥七位 |
| 16 | `vision` | [16-vision.md](16-vision.md) | 5 | 感知指纹 / 变化定位 / 流回放 / OCR |
| 17 | `voice` | [17-voice.md](17-voice.md) | 4 | TTS / ASR / 管弦乐 / WASAPI 回环 |
| 18 | `automation` + 网页 | [18-browser.md](18-browser.md) | 5 | 浏览器入口 / 穿透网 / 自适应抓取 / 逐页扫 |
| 19 | `finance` `project` | [19-finance.md](19-finance.md) | 6 | 策略信号 / 回测 / 参数读取 / 压缩直达 |
| 20 | `auth_gate_status` | [20-auth-gate.md](20-auth-gate.md) | 1 | 15 作用域 / 三道护栏 / 时段与一次性 |
| 21 | `brain_vault` | [21-brain-vault.md](21-brain-vault.md) | 1 | 追加式记忆 / 无删除路径 |
| 22 | `record_grid` | [22-record-grid.md](22-record-grid.md) | 1 | 七路转接 / 坏行不废整卷 / 回写自证 |
| 23 | 部署子集 `infra` | [23-deployment.md](23-deployment.md) | 6 | 一键部署 / AI 接管队列 / 服务巡检 / 防复发 |
| 24 | `digital_human` `dh_*` `body_*` | [24-digital-human.md](24-digital-human.md) | 12 | 以图生视频 / 姿态 / 真实感 / 身体桥 |
| 25 | `creation` | [25-creation.md](25-creation.md) | 54 | 镜头导演 / 节点即触手 / 作品解剖 / 音乐自动化 |
| 26 | `video` `image_video` | [26-video-media.md](26-video-media.md) | 15 | 剪辑 / 运镜 / 调色 / 音频 / 许可 / 钢印 / 发布 |
| 27 | `tools` | [27-tools.md](27-tools.md) | 9 | 改代码唯一过门入口 / 版本库读写 / 工具地图 |
| 28 | `integration` `collab` `social` `comms` | [28-integration.md](28-integration.md) | 12 | 外部系统接入 / 多智能体协作 / 社交发布 / 通信 |

---

## 逐位核对工具

`verify_cap.py` 是这个目录的**可信度来源**——它把文档钉到源码上。

```bash
python docs/native-capabilities/verify_cap.py list            # 按域列出全部 348 位
python docs/native-capabilities/verify_cap.py show <能力位>    # 看某一位的完整登记
python docs/native-capabilities/verify_cap.py domain <域名>    # 看某域全部能力位
python docs/native-capabilities/verify_cap.py check            # 逐位与文档覆盖面对账
python docs/native-capabilities/verify_cap.py stats            # 域统计
python docs/native-capabilities/verify_cap.py json             # 机器可读全量导出
```

**边界（写死）**：
- **只读**：`ast.parse` 解析源码，**绝不 import 包、绝不执行任何能力**——可以放心在 CI 里跑
- **不猜**：注册表没登记 `requires_params` 就报「未登记」，不脑补
- **不假绿**：对账失败就红，不因为「文档写得挺像」而放过

它已经抓出过 5 处真实错误（详见 [00-INDEX.md](00-INDEX.md) 的「口径更正记录」）：

| 旧说法 | 现读事实 |
|---|---|
| `room_space` 是 19 个能力位 | **1 个能力位 + 16 个 op** |
| `native_browser` / `scrapling_cap` | 真名 `browser` / `scrapling` |
| `dh_rig` / `body_bridge` | 真名 `dh_asset_gate` / `body_*` 七位 |
| `device` 域 2 位 | **9 位** |
| "348+ 能力位" | **348 位**（`+` 号去掉，因为没有第 349 位） |

---

## 架构总览

```
                    ┌─────────────────────────────────┐
                    │         SOUL (理念层)            │
                    │  听从指令 · 给意见 · 一起想办法    │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │    run_task (统一入口)            │
                    │    全行为落审计 + GBT钢印          │
                    └────────────┬────────────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
    ┌──────▼──────┐      ┌──────▼──────┐      ┌──────▼──────┐
    │  能力注册表   │      │  授权门      │      │  审计后台    │
    │ caps_registry│      │ auth_gate   │      │  store.py   │
    │  348 位      │      │ 15 作用域    │      │ JSONL 追加  │
    └──────┬──────┘      └──────┬──────┘      └─────────────┘
           │                     │
    ┌──────▼─────────────────────▼──────────────────────┐
    │              30 个能力域 / 348 能力位              │
    ├──────┬──────┬──────┬──────┬──────┬──────┬──────┬───┤
    │system│engine│mirror│brain │tentacle│security│devour│...│
    └──────┴──────┴──────┴──────┴──────┴──────┴──────┴───┘
```

---

## 五条核心设计原则

1. **统一入口**：`run_task(kind, payload)` 分发一切能力，全行为落审计
2. **脑子只有一份**：SOUL + run_task 做决策；手有很多只：引擎线程池并行执行
3. **不伪造**：不确定就说不确定，坏结果如实报，零假执行铁律
4. **门是开关不是限制**：授权门开着，技术全在；AI 永远无权给自己发授权
5. **镜像隔离**：所有假设/推演/试验在镜像维度跑，生产只收成品

---

## 能力位形态的两种写法（易混，单独说明）

注册表里有两种形态，**别混着记**：

| 形态 | 例子 | 调用 |
|---|---|---|
| **一位一动作** | `mirror_shape` / `mirror_ascend` / `wf_run` | `run_task("mirror_shape", {...})` |
| **一位多 op** | `room_space`（16 op）· `tentacle`（66 动作）· `key_gateway`（10 op） | `run_task("room_space", {"op": "shape", ...})` |

**判据**：把 `room_create` 当能力位去调会报 `unknown capability`——因为它不是能力位，
是 `room_space` 的一个 `op` 值。**先 `verify_cap.py show <名字>` 确认，再写调用。**

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
