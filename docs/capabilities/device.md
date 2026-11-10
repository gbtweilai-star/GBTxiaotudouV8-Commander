# 设备 · `device`（19 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `bluetooth` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | 蓝牙设备控制：扫描附近 BLE 设备、连接读写 GATT 特征（操控空调/灯/音箱等家居设备）、经典蓝牙状态报告 |
| `body_click` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·点：按坐标点按（参数 x,y,clicks） |
| `body_excrete` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·排泄（2026-11-04 主人令）：把代谢垃圾**排出体外并送进 Windows 回收站**（可还原），不是硬删 —— 「不让垃圾留在文件里当垃圾」。只排可再生代谢物（__pycache__/*.pyc/*.tmp/~$*/Thumbs.db/超期日志），源码·配置·账本… |
| `body_eye` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·眼睛（2026-11-04 主人令：把散装的视觉收成**一个入口**）。接线前实况（已核实，勿再误传）：`ocr` 与 `vision_arsenal` 早就在册、各是一个位各一套参数；但 2026-11-04 新做的 `vision_detect`(YOLO) / `vi… |
| `body_immune` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·免疫（2026-11-04 主人令）：**自我保护机制**。自己长，不外包给 Defender（实测 Defender 实时保护开着、特征库当日更新，aclui.dll.js 蠕虫在启动文件夹躺了 43 天却一条记录都没有）。六类检测：注册表 Run 指向脚本/Temp、启… |
| `body_map` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·清单：现读这台设备的七根感官与六根动作（零作用域，只读） |
| `body_open` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | 身体·打开：用系统默认程序打开文件/网址（参数 target） |
| `body_realtime` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·眼手脑同拍：采集线程持续看屏，控制环读最新帧小步闭环移动；op=status/servo（target/seconds/gain/max_step/dry_run）。动作期间采集不停，不是 see 子进程后再 click。 |
| `body_say` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·说：系统 TTS 念一句（参数 text，可调 rate） |
| `body_see` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·看：截当前屏幕落 png（可选 monitor 序号） |
| `body_sense` | 只读 | — | —（注册表：无必填） | `user_error` | 身体知觉三合一：op=proprio 本体感觉（分区×左右×机构在位，**没接机械臂就如实报 false**）；op=pain 痛觉（剧痛=身体失联 / 钝痛=部分不可用 / 酸=需票；每条带部位·原因·怎么办，追加落 state/body-pain.jsonl）；op=neig… |
| `body_type` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·打字：向前台窗口键入文本（参数 text） |
| `body_volume` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·音量：读或设主音量（参数 level 0~1；不传则只读） |
| `bt_control` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | AI 智能蓝牙操控：自然语言意图→扫描识别设备→协议匹配→组装指令→写入执行→验证（协议库只收公开文档协议，未知如实报告） |
| `hand_bridge` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·手部硬件桥（2026-11-01 蒸馏自 dexterous-hand 知识胶囊）：灵巧手 HAL —— connect/read_state/move/stop/disconnect；传输 loopback（**仿真真跑**）/ Modbus TCP（纯 stdlib 组… |
| `hand_realtime` | 只读 | — | —（注册表：无必填） | `user_error` | 手·眼手脑同拍（灵巧手 loopback）：21 点流 → hand_retarget → hand_bridge.move → read_state，同一 tick 闭环；op=status/loop（hz/seconds）。loopback 是仿真，不驱动真手。 |
| `hand_retarget` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·手语翻译（2026-11-01 蒸馏自 dexterous-hand 知识胶囊）：把 21 点手部跟踪（Vision Pro/Quest3/摄像头/IMU 手套先转 21 点）映射成目标灵巧手关节角；内置 generic_15dof / generic_20dof 模型，也… |
| `hand_vision` | 只读 | — | —（注册表：无必填） | `user_error` | 手·眼睛：本地 MediaPipe Hands 从摄像头/图片/视频取 21 点（x,y,z+左右手）；op=status/image/camera。摄像头不可用如实 needs_camera，不伪造；输出归一化坐标，接真手前需标定。 |
| `see_camera` | 只读 | — | —（注册表：无必填） | `user_error` | 身体·摄像头之眼（2026-11-04 主人令：「她的摄像头调用可用于跟用户对话，手机版和电脑版都可以，可通过摄像头陪用户看世间万物美景」）。`BODY_SENSES` 里早有 `see_camera: 摄像头`，但此前**没有任何能力位承接**——词汇在册、手是空的；这一位把它… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `bluetooth`

- **域**：`device`（设备）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`device_control`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`device_control`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：蓝牙设备控制：扫描附近 BLE 设备、连接读写 GATT 特征（操控空调/灯/音箱等家居设备）、经典蓝牙状态报告
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap bluetooth '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_click`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·点：按坐标点按（参数 x,y,clicks）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_click '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_excrete`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·排泄（2026-11-04 主人令）：把代谢垃圾**排出体外并送进 Windows 回收站**（可还原），不是硬删 —— 「不让垃圾留在文件里当垃圾」。只排可再生代谢物（__pycache__/*.pyc/*.tmp/~$*/Thumbs.db/超期日志），源码·配置·账本·能力包·解释器属器官一律保护。**默认只报不排**，要显式 dry_run=false 才动手；排完逐条验证是否真从原处消失。op=schema/status/scan/excrete/record/auto/config/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_excrete '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_eye`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·眼睛（2026-11-04 主人令：把散装的视觉收成**一个入口**）。接线前实况（已核实，勿再误传）：`ocr` 与 `vision_arsenal` 早就在册、各是一个位各一套参数；但 2026-11-04 新做的 `vision_detect`(YOLO) / `vision_embed`(CLIP) / `vision_ui`(界面元素) **根本没注册**，大脑调不到 = 做出来也白搭；且同一件事（看懂屏幕）要记 3 套调用形状。这一位把它们收成一条：op=see 一步到位（截屏→理解→回坐标，给 query 就直接定位要点的东西）；另可显式指定：ocr/boxes（读字，每行带坐标）、ui/parse（界面元素：按钮/输入框/文本/图标/容器）、find（按文字找位置 —— 「点那个写着 XX 的按钮」的正解）、outline（按类型的一句话摘要，省 token）、detect（真实照片的 COCO 80 类物体）、embed/similarity/nearest（图像特征，aHash 的补盲区：反色/深色主题）、region（找矩形区块）、template（找图标模板）、status（看这一层与 19 位矩阵现况）、matrix。**只回结构化数据+坐标，绝不回图。** 诚实边界：detect 不适用界面截图（COCO 无「按钮」类）；无 OCR 时如实报缺不猜字。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_eye '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_immune`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·免疫（2026-11-04 主人令）：**自我保护机制**。自己长，不外包给 Defender（实测 Defender 实时保护开着、特征库当日更新，aclui.dll.js 蠕虫在启动文件夹躺了 43 天却一条记录都没有）。六类检测：注册表 Run 指向脚本/Temp、启动文件夹放 .js/.vbs、计划任务用脚本宿主、脚本宿主跑临时目录、WMI 事件订阅常驻、AppData 游离脚本。判定只看**行为特征**不看文件名，系统/框架/用户程序进白名单；清剿顺序＝断自启→杀活体→送回收站；需提权的项**如实列 requires_admin，不假装做到**。op=schema/status/scan/purge/record
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_immune '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_map`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·清单：现读这台设备的七根感官与六根动作（零作用域，只读）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_map '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_open`

- **域**：`device`（设备）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`process_execute`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`process_execute`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：身体·打开：用系统默认程序打开文件/网址（参数 target）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_open '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_realtime`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·眼手脑同拍：采集线程持续看屏，控制环读最新帧小步闭环移动；op=status/servo（target/seconds/gain/max_step/dry_run）。动作期间采集不停，不是 see 子进程后再 click。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_realtime '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_say`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·说：系统 TTS 念一句（参数 text，可调 rate）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_say '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_see`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·看：截当前屏幕落 png（可选 monitor 序号）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_see '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_sense`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体知觉三合一：op=proprio 本体感觉（分区×左右×机构在位，**没接机械臂就如实报 false**）；op=pain 痛觉（剧痛=身体失联 / 钝痛=部分不可用 / 酸=需票；每条带部位·原因·怎么办，追加落 state/body-pain.jsonl）；op=neighborhood 神经邻域（器官间共享能力位的 Jaccard 邻接）；op=status 三合一现读。只报有证据的痛，没证据不编。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_sense '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_type`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·打字：向前台窗口键入文本（参数 text）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_type '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `body_volume`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·音量：读或设主音量（参数 level 0~1；不传则只读）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap body_volume '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `bt_control`

- **域**：`device`（设备）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`device_control`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`device_control`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：AI 智能蓝牙操控：自然语言意图→扫描识别设备→协议匹配→组装指令→写入执行→验证（协议库只收公开文档协议，未知如实报告）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap bt_control '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `hand_bridge`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·手部硬件桥（2026-11-01 蒸馏自 dexterous-hand 知识胶囊）：灵巧手 HAL —— connect/read_state/move/stop/disconnect；传输 loopback（**仿真真跑**）/ Modbus TCP（纯 stdlib 组 MBAP+PDU 真帧）/ 串口 / CAN（缺 pyserial·python-can 时如实 needs_dependency）；关节表+限位+回读统一。**真机写必须给 register_map**（厂商寄存器表未吸收 ⇒ needs_config，不猜），move 默认 dry_run，真机写需 confirm=true，stop 同样要 confirm。op=status/transports/profiles/connect/read_state/move/stop/disconnect/where。诚实边界：loopback 是仿真装置，不驱动真手
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap hand_bridge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `hand_realtime`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：手·眼手脑同拍（灵巧手 loopback）：21 点流 → hand_retarget → hand_bridge.move → read_state，同一 tick 闭环；op=status/loop（hz/seconds）。loopback 是仿真，不驱动真手。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap hand_realtime '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `hand_retarget`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·手语翻译（2026-11-01 蒸馏自 dexterous-hand 知识胶囊）：把 21 点手部跟踪（Vision Pro/Quest3/摄像头/IMU 手套先转 21 点）映射成目标灵巧手关节角；内置 generic_15dof / generic_20dof 模型，也接受自定义 chain/joints/limit 模型；几何向量法（**非 IK**）：三点屈曲 + 掌平面外展 + 关节限位 + 中性位标定 + 左右手符号，纯计算零依赖。op=status/models/retarget/where。诚实边界：无接触/触觉建模；外展/对掌为掌平面近似；高精度需逆运动学求解器（本仓暂无）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap hand_retarget '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `hand_vision`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：手·眼睛：本地 MediaPipe Hands 从摄像头/图片/视频取 21 点（x,y,z+左右手）；op=status/image/camera。摄像头不可用如实 needs_camera，不伪造；输出归一化坐标，接真手前需标定。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap hand_vision '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `see_camera`

- **域**：`device`（设备）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：身体·摄像头之眼（2026-11-04 主人令：「她的摄像头调用可用于跟用户对话，手机版和电脑版都可以，可通过摄像头陪用户看世间万物美景」）。`BODY_SENSES` 里早有 `see_camera: 摄像头`，但此前**没有任何能力位承接**——词汇在册、手是空的；这一位把它接上。op=status 枚举**真能读到帧**的摄像头（读不到的不列，不拿「有设备」充数）；snapshot 抓一帧落 .scratch/camera/；watch 连拍看动态；phone 起局域网页面（手机同一 WiFi 打开即用前后摄像头拍帧回传，自动连拍 2.5s/帧）；talk 取帧→交理解层（默认 body_eye）→body_say 读出来。与 body_see/body_eye 分工：那两位看**屏幕**，本位看**真实世界**。 摄像头打不开如实 needs_camera，**不造帧、不脑补画面**。常用说法：打开摄像头 / 用摄像头看看 / 手机当摄像头 / 陪我看看外面 / 摄像头里有什么 / 看看我这边 / 拍一张 / 连拍几张。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap see_camera '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
