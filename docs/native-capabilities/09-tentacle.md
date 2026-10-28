# 09 · 触手系统 (`tentacle`)

> 66+ 能力位 · 三通道感官 · UIA穿透 · MCP契约层 · 桌面指挥官
>
> 触手 = 框架的眼睛与双手。脑子只有一份，手有很多只。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 三通道感官

| 通道 | 技术 | 说明 | 性能 |
|---|---|---|---|
| **视觉** | DXGI 桌面复制 | 直读显卡帧缓冲，不经过GDI合成 | 28-34ms/帧 |
| **听觉** | WASAPI 回环 | 系统音频回环采集（不需虚拟声卡） | 实时 |
| **操作** | UIA 穿透 | UI Automation 控件树，无视遮挡 | <10ms |

## 六铁律

1. **先看再动** — 动手前必须先截图确认当前状态
2. **动后等稳定** — 操作后等待UI稳定再继续
3. **找不到就滚** — 找不到目标滚动查找，不盲点
4. **遇弹窗必关** — 遇到弹窗先关闭，不绕过
5. **每步亲眼验证** — 每步操作后截图验证结果
6. **不确定就对比前后截图** — 有疑问用前后帧差确认

## 能力清单（按域）

### 视觉（vision）

| 能力 | 说明 |
|---|---|
| `see` | 全屏截图（DXGI硬采，28-34ms） |
| `vision_snapshot` | 感知指纹（aHash）快照缓存，同画面零成本复用 |
| `vision_diff` | 变化区域定位——网格块哈希给出变化矩形（归一化坐标） |
| `vision_stream_record` | 视觉流帧时间线落store（指纹+变化标记） |
| `vision_stream_replay` | 流回放+变化段提取 |

### 读取（read）

| 能力 | 说明 |
|---|---|
| `read_text` | 读窗口文本（UIA穿透，无视遮挡） |
| `domain_index` | 索引（窗口/控件树） |
| `domain_read` | 读（窗口内容） |
| `list_windows` | 窗口列表（标题/句柄/进程） |

### 操作（act）

| 能力 | 说明 |
|---|---|
| `click` | 点击（UIA元素或坐标兜底） |
| `type` | 输入文本 |
| `domain_type` | 写（输入文本） |
| `domain_act` | 动作（点击等，含坐标兜底） |
| `key` | 键盘按键 |
| `mouse` | 鼠标移动/滚轮 |

### 进程（process）

| 能力 | 说明 |
|---|---|
| `process_list` | 进程列表（PID/名称/内存/CPU） |
| `process_kill` | 结束进程 |
| `process_start` | 启动进程 |

### 剪贴板（clipboard）

| 能力 | 说明 |
|---|---|
| `clipboard_get` | 读剪贴板 |
| `clipboard_set` | 写剪贴板 |

### 链式（chain）

| 能力 | 说明 |
|---|---|
| `chain` | 链式执行多个动作（每步验证） |

### 监控（monitor）

| 能力 | 说明 |
|---|---|
| `monitor` | 持续监控屏幕变化（帧差触发） |

### 音频（audio）

| 能力 | 说明 |
|---|---|
| `audio_capture` | WASAPI回环采集 |
| `audio_play` | 播放音频 |
| `vad` | 语音活动检测（Silero VAD） |

### 文件（fs）

| 能力 | 说明 |
|---|---|
| `fs_read` | 读文件 |
| `fs_write` | 写文件 |
| `fs_list` | 列目录 |
| `fs_search` | 搜索文件 |

### 窗口（window）

| 能力 | 说明 |
|---|---|
| `window_focus` | 聚焦窗口 |
| `window_move` | 移动窗口 |
| `window_resize` | 调整窗口大小 |
| `window_close` | 关闭窗口 |

### 网页（web）

| 能力 | 说明 |
|---|---|
| `web_open` | 打开网页 |
| `web_read` | 读网页内容 |
| `web_click` | 点击网页元素 |
| `web_type` | 网页输入 |

## 核心能力位

| 能力位 | 说明 |
|---|---|
| `tentacle` | 统一调用触手的全部能力（给意图自动命中，不给方法名也行） |
| `tentacle_manifest` | 能力总纲+三通道感官+六铁律（条目数运行时现算，不手写） |
| `tentacle_status` | 自诊断（依赖分层ctypes/mss/uiautomation/dxcam + 邻域覆盖映射） |
| `tentacle_equip` | 触手自配装备与账号（先有职业再谈装备） |
| `tentacle_learn` | 触手扫描·采集·学习（scan→collect→extract→learn） |
| `tool_bay` | 装备坞（白名单15件，每件状态靠现跑探针得出） |
| `desktop_commander` | 桌面指挥官（终端+文件系统全能力，26工具） |
| `remote_confinement` | 执行者隔离（未隔离+无票⇒一律拒启） |

## API参考

### 基础调用

```python
import gbt_allinone as gbt

# 看（截图）
result = gbt.run_task("tentacle", {"action": "see"})
# 返回: {ok, path: "store/frames/xxx.png", w: 1920, h: 1080, ms: 32}

# 读文本
result = gbt.run_task("tentacle", {"action": "read_text"})
# 返回: {ok, text: "窗口内容..."}

# 点击
result = gbt.run_task("tentacle", {"action": "click", "target": "登录按钮"})
# 返回: {ok, method: "uia", element: {...}}

# 输入
result = gbt.run_task("tentacle", {"action": "type", "text": "hello"})

# 窗口列表
result = gbt.run_task("tentacle", {"action": "list_windows"})
```

### 智能意图命中

```python
# 不给方法名，只给意图
result = gbt.run_task("tentacle", {"intent": "帮我打开浏览器搜索天气"})
# 自动匹配 see → click → type 组合
```

### 视觉差分

```python
# 快照缓存
gbt.run_task("tentacle", {"action": "vision_snapshot", "tag": "before"})

# ... 执行操作 ...

# 变化定位
result = gbt.run_task("tentacle", {"action": "vision_diff", "tag": "before"})
# 返回: {ok, changed: true, rect: {x: 0.12, y: 0.34, w: 0.5, h: 0.2}}
```

### 链式执行

```python
result = gbt.run_task("tentacle", {
    "action": "chain",
    "steps": [
        {"action": "see"},
        {"action": "click", "target": "设置"},
        {"action": "wait", "ms": 500},
        {"action": "read_text"}
    ]
})
```

### 自诊断

```python
result = gbt.run_task("tentacle_status", {})
# 返回: {
#   ok, deps: {ctypes: true, mss: true, uiautomation: true, dxcam: false},
#   channels: {vision: "dxgi", audio: "wasapi", act: "uia"},
#   coverage: {window: 1.0, process: 0.95, ...}
# }
```

## MCP契约层

```python
# 连接任意MCP服务器
gbt.run_task("mcp_connect", {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
})

# 契约清单（名称+参数schema）
gbt.run_task("mcp_tools", {})

# 按契约调用
gbt.run_task("mcp_call", {
    "tool": "read_file",
    "arguments": {"path": "README.md"}
})
```

**生态红利**：官方filesystem（14工具）/ everything（13工具）/ GitHub / 数据库……成百上千MCP服务器，一行连接全变成能力。

实测：连接→握手→契约→调用全链1.5秒。

## 桌面指挥官

```python
# 一键连接（本地stdio）
gbt.run_task("desktop_commander", {"op": "connect"})

# 26工具清单
gbt.run_task("desktop_commander", {"op": "tools"})

# 调用
gbt.run_task("desktop_commander", {
    "op": "call", "tool": "list_directory", "arguments": {"path": "."}
})

# 远程形态
gbt.run_task("desktop_commander", {"op": "remote_start"})
gbt.run_task("desktop_commander", {"op": "remote_status"})
gbt.run_task("desktop_commander", {"op": "remote_stop"})
```

## 安全边界

触手涉及的操作授权：

| 作用域 | 覆盖 |
|---|---|
| `desktop_control` | 桌面触手的输入、鼠标、键盘与窗口控制 |
| `privacy_read` | 读取屏幕、摄像头、麦克风 |
| `process_execute` | 启动进程、执行命令 |
| `browser_control` | 操控系统浏览器 |
| `remote_device` | 启动远程设备中继 |

**执行者隔离**：`remote_confinement` 未隔离+无票 ⇒ 一律拒启（fail-closed）。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
