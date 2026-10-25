# 18 · 能力总目录（按「我要干什么」查）

> 现算口径：**348 个能力位** · 21 根原生桥 · 六根动作 · 12 个云源。
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 一、怎么用（三种入口，走同一道门）

    Python   →  run_task("<能力位>", {...})                    # 348 位
    Python   →  run_task("omni_plug", {"op":"body", "do":"use", "organ":"眼"})
    命令行   →  apple-vision ocr 图片.jpg                      # 原生桥直调

**所有调用都过同一道授权门**：14 个作用域（`external_llm` / `device_control` /
`filesystem_write` / `privacy_read` …），**AI 无权自授，只有主人在终端发票**。

---

## 二、原生大模型：稳定输出与无限上下文

> **这一节是「为什么她的输出敢信」的全部答案。** 不是靠提示词，是靠**代码闸**。

### 2.1 稳定输出的正主 —— `fact_gate`（机器事实直答门）

**主人令 2026-10-11：「拿实质性证据说话，禁止胡说八道」。**

机器事实类问题（在位／装了／通不通／端口／内存／有没有能力位／版本）
**不过语言模型**，走四步直答：

    ① 现读  →  ② 代码判定  →  ③ 原文引用读数  →  ④ 直答

**实证依据（写进代码注释的）：**

| 试过什么 | 结果 |
|---|---|
| 三次重训（v12 / v17 / v19） | **治不住编事实** |
| 约十轮提示词迭代 | **每加一条只换一种失败模式** |
| 把证据喂进去 | 结论层稳定正确，只剩细节层润色证据（编出处／否掉真证据）|

**⇒ 最终架构：事实段由代码直出，模型只许在后面加「所以怎么办」，不许碰事实段。**

    run_task("fact_gate", {"op":"answer", "q":"端口 8791 通不通"})

### 2.2 输出后立刻机检 —— `llm_watch`

**主人令 2026-10-13：「监控触手LLM的监控，只要发现不对主脑要第一时间知道」。**

每次 LLM 输出过后**当场过机器判据**，命中就进主脑注意力队列：

- 无证据的「已完成」声明
- 越权（自我授权）声明
- 机器事实无现读
- 自相矛盾
- claims 无 evidence
- 数字对不上

**🔴 关键纪律：只认可机检的错。语义幻觉这一层判不了，就如实写「判不了」，不冒充判过。**

    run_task("llm_watch", {"op":"review", ...})   # 逐发机检
    run_task("llm_watch", {"op":"queue"})         # 主脑注意力队列

### 2.3 无限上下文的真机制 —— `offload_distill`（内存墙）

上游 `Edge0-AI/Edge0`（Apache-2.0 · ★4612 · arXiv 2609.18063）做到
**「35B 只吃 ~2.5 GB 内存」**，四条机制：

| 机制 | 干什么 |
|---|---|
| **权重离芯** | SSD 流式 + mmap 懒读（不整包进内存）|
| **槽位 + LRU + 双缓冲** | 每步零主机同步 |
| **prerouter 提前一步预判** | IO 与前向重叠 · 吞吐最高 **+59%** |
| **Recover-LoRA** | int4 底座 + 蒸馏小适配器补质量 · **适配器不合并** |

    run_task("offload_distill", {"op":"mechanism"})  # 上游原文 → 我们的话 → 用处 → 判据
    run_task("offload_distill", {"op":"probe"})      # 只读现读本机就绪面，逐条说能不能走

**铁律：只蒸思路不搬代码 · 只读上游零执行 · 边界不许说反。**

### 2.4 压缩与直达 —— `quant_plan`

每档 bits/weight ⇒ 估算体积（`参数 × b/w ÷ 8 × 容器开销 1.3`）⇒ 判断能不能落在 8GB 级。

**一手读数**：ternary PTQ1_0 = **1.75 b/w** · 语言模型 **7.67 GB** · **保留 98.2% FP16** ·
同体积胜 IQ2_XXS **12 分**。

    run_task("quant_plan", {"op":"plan", "params":7.6, "bits":5.0})   # 估算体积
    run_task("quant_plan", {"op":"route", "intent":"..."})            # 意图→能力位→车道→端点

### 2.5 并发与稳定性 —— `energy_scheduler` / `page_scan`

**`energy_scheduler`**：批量 prompt → 多能源分配

- **每源并发上限**（按池内 status 档）
- **失败冷却**：同源连败 3 次 ⇒ 300s 不再派
- **公平**：least-load 优先，不饿死单源
- `plan` 纯本地不出网（可单测可审计）· `run` 每一发都过唯一门

**`page_scan`**：按绑定逐页并发扫（主人定的架构「触手随每一页绑定好，扫的时候按绑定一页一页传回来」）

- **按契约判色**：绿=跑通 · 黄=需参数或需授权（不是故障）· **红=契约也满足却仍失败**
- **实测引擎 ≥4096 根零失败**，压测档位拉到 **20,000 路零失败**

### 2.6 五维合一 —— `brain_unify`

一次跑完 **route → execute → verify → health**，**是顺序串链**（route 的 best.kind 喂给 execute）。

### 2.7 免费大模型池 —— `freellmapi`

本机 OpenAI 兼容口 · **34 家供应商 / 635 免费端点** · 端口**三级发现**（env → 配置 → 默认），绝不写死。

---

## 三、原生能力：21 根桥

| 我要… | 命令 | 关键词 |
|---|---|---|
| **看** | `apple-vision ocr / classify / faces / barcode / similarity / overlap / analyze` | OCR 文字识别 识物 人脸 扫码 查重 |
| **看相册** | `apple-photos list / stats / albums / near / export / import` | 图库 照片 按地点 |
| **听** | `apple-speech transcribe` | ASR 转写 转录 |
| **说** | `apple-speak speak / voices` · `apple-media` · `apple-player` | TTS 朗读 音色 播放 |
| **理解文字** | `apple-nlp language / tokenize / pos / ner / sentiment / embed / analyze` | 语种 分词 词性 实体 情感 向量 |
| **身体数据** | `apple-healthkit <指标>` · `batch --types a,b --days N` | 步数 心率 睡眠 血氧 心肺 |
| **知道在哪** | `apple-location` · `apple-maps search / route / eta` | 定位 GPS POI 导航 车程 |
| **外面什么样** | `apple-weather current / hourly / daily / alerts` | 天气 气温 预报 预警 |
| **记事** | `apple-calendar` · `apple-reminders` · `apple-alarm` · `apple-notification` | 日程 待办 闹钟 通知 |
| **智能家居** | `apple-homekit list / get / set / scenes / trigger` | 开关灯 调温 场景 |
| **碰硬件** | `apple-bluetooth` · `apple-nfc` · `apple-device` · `apple-clipboard` · `apple-open` | BLE APDU 门禁 电量 剪贴板 |

> 健康 40+ 指标清单：`apple-healthkit types`
> **锁屏时健康数据读不到**（iOS 保护）：如实报 `Protected health data is inaccessible`

---

## 四、身体：七根感官 + 六根动作

**核心：器官是抽象的，实现是探出来的。换设备只换实现表，器官名不变 ⇒ 她不会因为换机而「不认识自己」。**

### 4.1 七根感官（`body_map` 现读）

| 感官 | 看什么 | 依赖 |
|---|---|---|
| `see_screen` | 屏幕 / 多显示器 | `mss` |
| `see_camera` | 摄像头 | `cv2` |
| `hear_mic` | 麦克风 | `sounddevice` |
| `speak_out` | 扬声器 | — |
| `feel_power` | 电量 / CPU / 内存 | — |
| `net_reach` | 网络与身份 | — |
| `bt_nearby` | 蓝牙适配器 | — |

### 4.2 六根动作（`body_*` 六个能力位）

| 能力位 | 动作 | 参数 |
|---|---|---|
| `body_see` | 截当前屏幕落 png | 可选 `monitor` |
| `body_say` | 系统 TTS 念一句 | `text` · 可调 `rate` |
| `body_type` | 向前台窗口键入文本 | `text` |
| `body_click` | 按坐标点按 | `x, y, clicks` |
| `body_volume` | 读或设主音量 | `level 0~1`（不传则只读）|
| `body_open` | 用系统默认程序打开 | `target` |
| `body_map` | 现读七感官与六根动作 | 零作用域，只读 |

    run_task("body_map", {})                       # 我现在有什么感官/动作、缺哪几个
    run_task("body_see", {"monitor": 0})           # 看一眼屏幕
    run_task("body_say", {"text": "我在"})          # 说一句

**评分口径**：`{"senses_ok": N, "senses_total": 7, "actuators": 6}` —— 缺就写缺，不假装有。

### 4.3 十一器官（语义层，挂在六根动作之上）

| 器官 | 语义 | 底下 |
|---|---|---|
| 眼 · 耳 · 嘴 · 手 | 看/听/说/动手 | 见上 |
| 记忆 · 本体 · 位置 | 外置记忆 / 本体感 / 空间感 | photos calendar · device · location maps |
| 环境 · 内感受 · 情绪 | 外环境 / 身体内部 / 读情绪 | weather homekit · healthkit · nlp |
| **推理** | 想 | **@app(A19) → @cloud → @engine** 自动择活 |

    run_task("omni_plug", {"op":"body", "do":"organs"})
    run_task("omni_plug", {"op":"body", "do":"feel"})

---

## 五、云能力：反向调用云端算力（12 个云源）

**核心设计：手机是指挥部，算力在云上，她按需反向调用。**

    run_task("cloud_plugin", {"op":"sources"})      # 12 个云源
    run_task("cloud_plugin", {"op":"primitives"})   # 五原语

| key | 名字 | 类型 | 计费 |
|---|---|---|:---:|
| `pod_link` | 云卡触手（本机 ⇄ GPU 卡 · 传输回读校 sha256）| gpu_card | 💰 |
| `cloud_pc` | 云电脑 | vm | 💰 |
| `comfy_cloud` | 云卡 ComfyUI | service | 💰 |
| `energy` | 能源池 | llm_fuel | 免费 |
| `key_gateway` | 统一密钥网关（铸/核/吊销，一把钥两边用）| key | 免费 |
| `freellmapi` | 免费模型池 | llm_local | 免费 |
| `h3_video_gen` | H3mini 文生视频 | api | 💰 |
| `a1art` | a1.art | api | 💰 |
| `libtv` | LibTV | api | 💰 |
| `tripo` | Tripo3D 文生 3D | api | 💰 |
| `cloud_brain` | 主脑云插件 | worker | 免费 |
| **`cloud_compute`** | **借算力云插件（插座）** | worker | 免费 |

**五原语**：`PROVISION`（开通·不可逆·花钱·要过门）/ `CONNECT`（连上）/ `STATUS`（读数）/
`EXPAND`（扩容，幂等）/ `TEARDOWN`（拆掉·要过门）

**「加一行 SOURCES 就扩容」—— 代码里就是这么写的。**

**自有权重云端车道**：Cloudflare Worker（网关）→ RunPod（vLLM）。
回执里 `weights_ours: true/false` 逐发可见。
**⚠️ 实测有一次等 201 秒后返回 `false` —— 降级跑了别人的 3B。所以本地链路刻意设计成「不通就排队，绝不降级」。**

---

## 六、348 个能力位

**逐位总表见 [`能力总表.md`](./能力总表.md)（30 个域）。分域详情见 [`capabilities/`](./capabilities/)。**

| 域 | 位数 | 域 | 位数 |
|---|---:|---|---:|
| creation | 54 | pipeline | 18 |
| llm | 41 | mind | 19 |
| data | 12 | security | 12 |
| engine | 10 | device | 8 |
| … 共 30 个域 | **348** | | |

**探针实测（341 位那一轮，348 之前）**：ok 263 · denied 32（门拦，设计正确）·
error 28（已逐条定性）· timeout 18（扫描类天生慢）。
**新增的 7 个 `body_*` 位**见第四节，是这一轮新增的原生动作。

---

## 七、搜索关键词总表

| 你想干的事 | 搜这些词 |
|---|---|
| **输出敢不敢相信** | `fact_gate` `禁止胡说` `事实直答` `现读` `机检` |
| **输出后自动纠错** | `llm_watch` `守望` `queue` `判据` |
| **省内存 / 大模型** | `offload_distill` `内存墙` `权重离芯` `mmap` `LRU` `prerouter` `Recover-LoRA` |
| **压缩 / 量化 / 体积估算** | `quant_plan` `bits/weight` `PTQ1_0` `IQ2_XXS` |
| **并发 / 稳定 / 不饿死** | `energy_scheduler` `并发上限` `失败冷却` `least-load` `page_scan` |
| **五维自检 / 串链** | `brain_unify` `brain_health` `route execute verify health` |
| **免费大模型** | `freellmapi` `34 家` `635 端点` `免费模型池` |
| **反向调云算力** | `cloud_plugin` `sources` `PROVISION` `pod_link` `cloud_compute` |
| **认字 / 看图 / 扫码** | `vision` `ocr` `文字识别` `classify` `barcode` |
| **说话 / 朗读 / 转写** | `speak` `speech` `TTS` `ASR` `语音` |
| **理解文字** | `nlp` `分词` `情感` `实体` `embedding` |
| **健康 / 运动 / 睡眠** | `healthkit` `步数` `心率` `睡眠` `血氧` `vo2-max` |
| **定位 / 导航 / 天气** | `location` `maps` `weather` `POI` `预报` |
| **日程 / 待办 / 闹钟** | `calendar` `reminders` `alarm` `日程` `提醒` |
| **智能家居** | `homekit` `场景` `开关灯` `调温` |
| **蓝牙 / NFC / 硬件** | `bluetooth` `nfc` `BLE` `APDU` `门禁` |
| **截屏 / 点按 / 打字 / 音量** | `body_see` `body_click` `body_type` `body_volume` `六根动作` |
| **她有几根感官 / 动作** | `body_map` `七根感官` `六根动作` |
| **谁在拦我 / 为什么被拒** | `policy` `auth_gate` `作用域` `scopes` `how_to_grant` |
| **监控 / 体检** | `monitor` `conn_check` `verify` `探针` `连接点` |

---

**开发者：自由的风 · 护着：公主土豆**
**本署名不可删除、不可篡改归属。**
