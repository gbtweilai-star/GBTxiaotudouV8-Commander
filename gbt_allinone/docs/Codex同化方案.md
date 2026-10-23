# Codex 同化方案

> 取证范围：2026-09-17 10:18 上游切 DeepSeek 直连之后的全部观测。
> 本文件只出方案，**不动手**。文中每一处结论都带 file:line 或时间戳出处，可复算。

## 零、一句话结论

Codex 现在在用户视野里是"两个东西"：一个挂在旁边的官方 Desktop，一个藏在 `potato_pet` 里的私有实例。
同化的意思是把这两个都收掉，只留下 **holo_pet 一张脸 + 一个进程内的共享单例**。
官方 Desktop 不作为主入口，但**不卸载**，降级为后台调试工具。
同化还有第二条轴：Codex 的五个能力必须**装进我自己的调度与操控区**（`~/.codex/config.toml` 的 MCP 工具表），
让我接到任何任务时随手可用——今天它们只停在能力库登记表 `caps_registry.py`，够不着。详见 §4.9。

---

## 一、取证：官方 Codex Desktop 这条入口

### 1.1 它是不是"旧上游 / 旧对话 / 旧身份"的直接来源

**是，而且是三合一的直接来源。** 三条独立证据：

| 用户看到的"旧" | 证据 | 出处 |
| --- | --- | --- |
| 旧上游 | app-server 子进程启动 **10:07:54**，早于 `~/.codex/config.toml` 的 **10:18:16**；配置只在 APP 启动那一刻读一次 | `Get-CimInstance Win32_Process` 快照 |
| 旧身份 | 进程每秒刷 `remote control requires ChatGPT authentication; API key auth is not supported`，APP 侧仍走 ChatGPT 账号体系，不认 API Key | `~/.codex/logs_2.sqlite`，process_uuid `pid:6468:*` |
| 旧对话 | `originator='Codex Desktop'` 的最后一条线程是 **09-16 09:44:41**，切上游后 APP 一条新线程都没开 | 同上库 `threads` 表 |

两条结构性事实，决定这条入口"修不掉、只能换掉"：

1. **单例不会自动重生。** 杀掉 app-server 后 50 秒内无新进程（实测 10:50:19 → 10:51:09）。它是 APP 启动时一次性拉起的子进程。所以对 Desktop 来说，"重启单例"等于"重启整个 APP"。
2. **模型选择器是 default 模式。** `.codex-global-state.json` 的 `composer-model-picker-selection-mode-v1 = "default"`，显示的就是启动时解析出的默认模型，没有第二处真源。

### 1.2 弃用后失去什么（功能面清点）

清点方式：`C:\Users\ADMIN\.codex\.codex-global-state.json`，30 个顶层键 + 193 个 `electron-persisted-atom-state` 键，按归属归并。

**A. 已经死了的（弃用零损失）**

| 功能 | 证据 |
| --- | --- |
| 云端任务 / ChatGPT Work 云线程 | `codexCloudAccess = "disabled"` |
| 远程控制 | `electron-local-remote-control-installation-id` 存在，但 app-server 卡在 ChatGPT 认证死循环 |

**B. 可以被 holo_pet + 共享单例替代的（能力面，无缺口）**

| 功能 | 现有替代物 |
| --- | --- |
| 对话 / 线程 / 回合 / 中断 | `gbt_allinone/api.py:505-523` 五条路由 `codex_status / codex_tools / codex_thread_new / codex_turn_send / codex_interrupt`，全部落到 `_CB.get_shared_server()` |
| 流式输出 | `gbt_allinone/codex_bridge.py` 的事件监听 + `holo_pet/panel_server.py` SSE |
| 审批（命令 / 改文件 / 额外权限 / 提问 / MCP elicitation） | `holo_pet/panel_server.py:234-320` `_attach_shared` + 4-A/4-B 审批侧收口 |
| 工具清单 | `codex_tools` → `codex_bridge.dynamic_tool_specs()`（gbt_* 九个） |
| 数字人 / 头像浮层 | `holo_pet`（3D 全息面板，`launch_panel.py --port 8765`） |

**C. 替代不了的（弃用代价，全部集中在"人机界面"，不在"能力"）**

| 功能 | 证据键 |
| --- | --- |
| 应用内浏览器 + 浏览器配置导入 + 网页批注 | `browser-profile-import-nux-*`、`browser-sidebar-comment-mode-coachmark-dismissed`、`desktop-link-default-destination="in-app-browser"` |
| 代码 diff 视图 / 文件树 / 摘要侧栏 | `editorDiffViewMode="unified"`、`app-shell-file-tree-open`、`app-shell-summary-panel-pinned`、`sidebar-*` |
| 插件市场 + MCP 侧栏目录 | `mcp-extension-sidebar-catalog`、`plugin-oauth-install-reconciliation-by-state-v1`、`has-opened-plugin-creator-prefill-v1` |
| GitHub Pull Request 视图 | `pull-request-last-account`、`pull-request-view:["local","github.com","paysssk-creator"]` |
| 外部 agent 导入（claude-code / claude-cowork） | `external-agent-import-sync-state` |
| computer-use 授权 UI | `has-approved-computer-use-app`、`computer-use-bundled-plugin-auto-install-disabled` |
| 权限档位 / agent 模式选择 UI | `permission-selection-by-host-id:local`、`agent-mode-by-host-id`、`full-access-warning-dismissed-at-v2` |
| 自动更新 / 托盘 / 快捷键（Electron 壳） | `electron-internal-update-cdn-enabled` |

### 1.3 结论

- **可以弃用为主入口**：B 类已全部有替代物，A 类本来就没在工作。
- **不可以卸载**：C 类是人机界面，不是能力；卸载它等于把"排障时能直读 app-server 行为"的唯一官方窗口也关掉。
- **定位改为**：后台调试工具。定义见 §4.6。

### 1.4 谁在拉起官方 Desktop（自启面穷尽 · 2026-09-17 11:0x 实测）

结论：**全机没有任何自启项指向官方 Desktop。** 用户看到的"APP 还是旧的"是**进程寿命问题**，不是自启问题。

| 排查面 | 复算命令 | 结果 |
| --- | --- | --- |
| `HKCU\...\CurrentVersion\Run` | `Get-ItemProperty` | 7 项：`PotatoDesktopPet` / `Wechat` / `Docker Desktop` / `MicrosoftEdgeAutoLaunch` / `Lark` / `cn.coze.desktop` / `Chrome`。**无 `ChatGPT.exe`、无 `OpenAI.Codex`** |
| `HKLM\...\CurrentVersion\Run` | `Get-ItemProperty` | 4 项：`SecurityHealth` / `RtkAudUService` / `tvncontrol` / `AweSun`。**无 `ChatGPT.exe`** |
| 启动文件夹 · 快捷方式 | `WScript.Shell.CreateShortcut` 逐个解析 | 3 个：`CodexPlusPlusWatcher.lnk` → `C:\Users\CodexSandboxOffline\AppData\Local\Programs\Codex++\codex-plus-plus.exe --debug-port 9229`；`GBT WebSocket.lnk` → `powershell -WindowStyle Hidden -File C:\Users\ADMIN\Desktop\GBT小土豆\start_ws.ps1`；`Ollama.lnk` → `...\Ollama\ollama app.exe` |
| 启动文件夹 · 批处理 | 读文件内容 | `start_bridge.bat` → `python gbt_cap_bridge.py --port 18900`；`start_ws.bat` → `python .openclaw\tmp\ws_server_v2.py`；`start_ws_server.bat` → `python caps\websocket_server\run.py start`。**三条全部指向本机桥 / WS，与 Desktop 无关** |
| 计划任务 | `Get-ScheduledTask` 过滤 `ChatGPT` / `Codex` | 命中三个，全是中继 / 看门狗：`\CodexRelay`（Ready）、`\GBT\CodexRelayWatchdog`（Ready）、`\GBT-CodexWatchdog`（**Disabled**）。**无一拉起官方 Desktop** |
| 脚本面 | `rg -i -e 'ChatGPT\.exe' -e 'OpenAI\.Codex' -e 'shell:AppsFolder'`，范围：桌面 / 文档 / 开始菜单 / `~/.codex/config.toml` / AutoClaw workspace | 生产脚本 **0 命中**。全部命中只有三类：`.backups\codexpp-uninstall-20260915\settings.json`（Codex++ 卸载残留）、`.scratch\_restart_app_gui.ps1`（我上一轮排障时自写的重启脚本）、`memory\` 与 `HEARTBEAT.md` 与本方案（叙述性文字） |

**顺带定性一个哑弹**：`CodexPlusPlusWatcher.lnk` 的 TargetPath
`C:\Users\CodexSandboxOffline\AppData\Local\Programs\Codex++\codex-plus-plus.exe` **不存在**（`Test-Path = False`），
Codex++ 已于 2026-09-15 卸载（残留备份 `.backups\codexpp-uninstall-20260915\`）。
这条自启每次登录都会尝试拉起并静默失败——属静态噪声，不是 Desktop 的拉起源。是否清掉留给风哥，本方案不动手。

**由此收敛出的因果**：官方 Desktop 之"旧"，源于它**在旧配置上活着**——app-server 只在 APP 启动那一刻读一次配置（§1.1 第 1 条）。
所以修复口径不是"封某个自启脚本"，而是"只要它以旧配置活着，用户切到它就看到旧上游"。
这正是 §4.5-P4 把它降级为后台调试工具的直接理由。

---

## 二、取证：`potato_pet/codex_client.py:101` 这条残留入口

### 2.1 它还在被谁调用

| 调用方 | 位置 | 性质 |
| --- | --- | --- |
| `potato_pet/main.py` | `:179` `from codex_client import CodexPanelClient` → `:180` 实例化 | **唯一生产调用方** |
| `potato_pet/tests/test_codex_client.py` | `:56` | 测试 |

`potato_pet` 由 `potato_pet/启动小土豆.bat` 拉起（探测装了 PySide6 的解释器，最后 `%PY% main.py`）。
桌面/开始菜单里**没有任何 GBT 快捷方式指向 potato_pet**；`GBT小土豆.lnk` 指向 AutoClaw，`GBT 小土豆.lnk` / `GBT.lnk` 指向 `C:\Users\CodexSandboxOffline\...`（另一个用户目录，已失效）。
实测当前 `potato_pet` 未运行。

### 2.2 它是什么、能做哪些事

`CodexPanelClient`（`QObject`）是 **Qt 适配层**：把 `gbt_allinone.codex_bridge` 的流式事件、审批请求、工具活动翻译成 Qt 信号。

| 能力 | 位置 | 说明 |
| --- | --- | --- |
| `start / stop / status / models / available` | `:55-92` | 生命周期与只读状态 |
| `new_thread` | `:136-139` | 新会话 |
| `send` | `:141-151` | 后台线程发起回合 |
| `interrupt` | `:171-180` | 中断 |
| `_ensure_thread` | `:108-130` | resume 失败则新建线程 |
| `_on_event` | `:182-239` | 流式增量 / 命令执行 / 文件变更 / plan / turn 完成 / error |
| `_on_approval` + `resolve_approval` | `:241-278` | 阻塞式审批桥（`threading.Event`，超时 300s），覆盖 4 种审批方法 |
| 8 个 Qt 信号 | `:31-38` | `chunk / replied / thinking_changed / status_changed / plan_updated / approval_requested / turn_finished / failed` |

### 2.3 它现在是"第二个 app-server"

```python
# potato_pet/codex_client.py:94-106
def _ensure_server(self):
    if self._server is not None and self._server.alive:
        return self._server
    server = CB.CodexAppServer(
        cwd=self.cwd,
        codex_home=codex_cfg.get("codex_home") or None,
        on_event=self._on_event,        # ← 构造 kwargs
        on_approval=self._on_approval,  # ← 构造 kwargs
    )
```

这与 `holo_pet/panel_server.py` **收口前**的形态逐字同形，因此踩的是同一个坑：
`codex_bridge` 的构造 kwargs 只在"首次创建"时生效，共享单例已存在时这两个钩子会被**静默丢弃**。

另外两处必须一起看：

- `:65-68` `models()` 会调 `self._ensure_server()`。**只是问一句模型清单，也会顺手拉起一个私有 app-server。**
- `:85-92` `stop()` 会调 `self._server.stop()`。`panel_server.py:307-309` 已把这条写成禁令：
  > 不要 `server.stop()` / `CB.shutdown_shared()` —— 那会顺手把路由正在用的桥干掉。

### 2.4 改走共享单例，功能会不会降级

**功能面不降级。** 共享单例提供的是同一组方法：`start_thread / resume_thread / start_turn / interrupt / list_models`，`potato_pet` 用到的全在里面。

会变的是**三处挂法**，且三处都已有现成解法可抄（`panel_server.py` 4-A/4-B 已跑通）：

| 要变的地方 | 现状 | 改后 | 现成参考 |
| --- | --- | --- | --- |
| 事件钩子 | 构造 kwargs `on_event=` | `server.add_listener(...)` 挂/摘 | `panel_server.py:242-255` |
| 审批钩子 | 构造 kwargs `on_approval=` | 共享单例的审批槽位 + 面板裁决回传 | `panel_server.py:250-255`、`:1082` |
| 生命周期 | `stop()` 直接杀 server | 只摘钩子，不碰桥 | `panel_server.py:307-309` |
| 线程归属 | 自带 `self._thread_id` | 带连接令牌防跨进程 resume | `panel_server.py:173`、`:885` |

### 2.5 如果废掉，会断掉什么

- `potato_pet/main.py:275-278` 的 Codex 优先分支消失 → 桌宠只剩 `config.json` 的 `chat` 兜底（`glm-4.7-flash`），**从"能干活"退回"只能聊天"**。
- 用户会看到兜底文案：`:431-432`「Codex 内核还没连上，我先用原有大脑陪你聊…」。
- 测试 `potato_pet/tests/test_codex_client.py` 失效，需同步删除或改写。
- `:455`/`:460`「当前大脑」命令降级为 LLM 说明。

### 2.6 一个必须先说清的架构事实

共享单例是**进程内单例**：`gbt_allinone/codex_bridge.py:1385-1401` 的模块级 `_shared` + `_shared_lock`。
`holo_pet` 与 `potato_pet` 是两个进程 → **即使两边都改走共享单例，仍然是两个 app-server。**
要真正做到"一个单例"，前提是"一个进程"。这正是 §4.5 入口收敛要解决的事。

---

## 三、现状里的品牌泄漏点（全量清单）

用户视野里出现"Codex"字样的位置，逐条列全（不含 `archive/`、`tests/`）：

**`holo_pet/index.html`**

| 行 | 内容 |
| --- | --- |
| 104 | `aria-label="Codex 全息对话面板"` |
| 111 | `<h1>Codex 编程内核</h1>` |
| 112 | `<p id="kernel-state">正在连接 App Server</p>` |
| 221 | `面板、心智、Codex 与系统能力准备中` |
| 409 | `<span class="status-chip" id="chip-codex">Codex · 连接中</span>` |

**`holo_pet/app.js`**

| 行 | 内容 |
| --- | --- |
| 223 | `chip.textContent = "Codex · App Server 在线"` |
| 224 | `kernel.textContent = "真实 Codex 流式通道已连接"` |
| 226 | `chip.textContent = "Codex · 正在建立通道"` |
| 227 | `"已找到 Codex，正在初始化"` |
| 229 | `chip.textContent = "Codex · 降级可用"` |
| 230 | `"未找到本机 Codex，保留 LLM 降级"` |
| 527 | `addTimeline("已新建会话", "下一条消息进入全新 Codex 线程", "system")` |
| 550 | `"Codex 请求继续当前操作。"` |
| 603 | `addTimeline(summary.title || "Codex 请求审批", ...)` |
| 617 | `"已授权 Codex 继续"` |
| 1275 | `addTimeline("本地事件流已连接", "Codex / 心智 / 设备总线", "system")` |
| 1295 | `"Codex App Server 已连接"` / `"Codex 通道状态变化"` |
| 1329 | `addTimeline(title, "Codex 计划更新", "plan")` |

**`potato_pet/main.py`**

| 行 | 内容 |
| --- | --- |
| 427 | `"Codex 内核已就绪，直接把任务说给我就行——"` |
| 431-432 | `"Codex 内核还没连上…"` / `"本机装好 Codex 后重启面板即可接管编程任务～"` |
| 437 | `"当前没有可中断的 Codex 任务哦～"` |
| 455 | `f"当前大脑：真 Codex 内核｜生效模型 {current}｜可选：{shown}"` |
| 460 | `f"当前大脑：真 Codex 内核（{ua}）"` |

**`potato_pet/codex_client.py`**

| 行 | 内容 |
| --- | --- |
| 82 | `f"Codex 内核启动失败：{exc}"` |
| 147 | `self.failed.emit("Codex 未就绪")` |

> **行号更正（2026-09-17 11:15 实测复核）**：上表两行是过时行号，实际为
> **`:85`**（`self.failed.emit(f"Codex 内核启动失败：{exc}")`）与 **`:150`**（`self.failed.emit("Codex 未就绪")`）。
> 另漏记 `potato_pet/main.py:225`（`panel.add_message("assistant", f"Codex 通道暂时不可用：{err}")`）——同样在用户视野内。
> 口径与完整清单以《Codex同化施工方案.md》§四为准。

> 备注：`potato_pet/main.py:193/215` 里的 `"Codex 回合"` 只进 `mind.observe(...)`，落审计不落屏幕，可不改；
> `:230` 是 `logger.warning`，属日志面，不在用户视野。

---

## 四、《Codex 同化方案》本体

### 4.1 目标（风哥口径，原文照录）

1. 用户入口只有 `holo_pet` 一个。
2. Codex 的所有能力（`thread_new / turn_send / interrupt / tools`）全部登记进土豆公主的能力库。
3. 土豆公主调用 Codex 时，用户感知不到"这是一个外部 AI"。
4. 数字人呈现结果，不在面板里露出"Codex"品牌。
5. 官方 Codex Desktop 降级为"后台调试工具"，不作为主入口。

### 4.2 分层架构

```
L0 用户视野层    只有一个进程：holo_pet（数字人 + 一条对话流 + 一个状态条）
                 ↑ 看不到任何内核名词
L1 同化层        土豆公主的能力路由：api.run_task → caps_registry
                 术语表把内核词汇换成"内在/后台/预算"类说法
                 ↑ 只有路由知道下面有内核
L2 内核层        codex app-server 共享单例（进程内唯一）
                 只有三个合法接触点：路由调用 / 面板 attach / 审批槽位
```

同化的判定标准只有一条：**在 L0 的任何像素上，都找不到"Codex"这个词。**
（风哥 2026-09-17 补定义后，判定标准扩展为两条，见 §零 与 §4.9：
L0 无品牌词，**且**在我自己的工具表里能直接摸到内核的五个能力。）

### 4.3 品牌清洗（对应目标 3、4）

原则：**能力名可以留着（内部标识符不动，动了会牵连审计与路由），只清用户可见文案。**

| 位置 | 现状 | 改为 |
| --- | --- | --- |
| `holo_pet/index.html:104` | `Codex 全息对话面板` | `全息对话面板` |
| `holo_pet/index.html:111` | `Codex 编程内核` | `小土豆·内核` |
| `holo_pet/index.html:112` | `正在连接 App Server` | `正在唤醒内核` |
| `holo_pet/index.html:221` | `面板、心智、Codex 与系统能力准备中` | `面板、心智与系统能力准备中` |
| `holo_pet/index.html:409` | `Codex · 连接中` | `内核 · 连接中` |
| `holo_pet/app.js:223` | `Codex · App Server 在线` | `内核 · 在线` |
| `holo_pet/app.js:224` | `真实 Codex 流式通道已连接` | `内核通道已连接` |
| `holo_pet/app.js:226` | `Codex · 正在建立通道` | `内核 · 正在建立通道` |
| `holo_pet/app.js:227` | `已找到 Codex，正在初始化` | `内核已就位，正在初始化` |
| `holo_pet/app.js:229` | `Codex · 降级可用` | `内核 · 降级可用` |
| `holo_pet/app.js:230` | `未找到本机 Codex，保留 LLM 降级` | `内核未就绪，走备用大脑` |
| `holo_pet/app.js:527` | `下一条消息进入全新 Codex 线程` | `下一条消息进入全新会话` |
| `holo_pet/app.js:550` | `Codex 请求继续当前操作。` | `需要你确认下一步` |
| `holo_pet/app.js:603` | `Codex 请求审批` | `请求授权` |
| `holo_pet/app.js:617` | `已授权 Codex 继续` | `已授权继续` |
| `holo_pet/app.js:1275` | `Codex / 心智 / 设备总线` | `心智 / 设备总线` |
| `holo_pet/app.js:1295` | `Codex App Server 已连接` | `内核已连接` |
| `holo_pet/app.js:1329` | `Codex 计划更新` | `计划更新` |
| `potato_pet/main.py:427/431-432/437/455/460` | 见 §三 | 若保留 potato_pet，同口径替换；若不保留，随 §4.5 一起下线 |
| `potato_pet/codex_client.py:82/147` | `Codex 内核启动失败` / `Codex 未就绪` | `内核启动失败` / `内核未就绪` |

**术语表（统一口径，避免各处自己造词）**

| 旧说法 | 新说法 |
| --- | --- |
| Codex / Codex App Server | 内核 |
| Codex 线程 | 会话 |
| Codex 回合 | 这一轮 |
| Codex 审批 | 授权 |
| LLM 降级 / 原有大脑 | 备用大脑 |

### 4.4 能力库登记（对应目标 2）

**已登记（`gbt_allinone/caps_registry.py:13-43`，5 项，domain=llm）**

| 能力 | 读/写 | 路由 |
| --- | --- | --- |
| `codex_status` | 只读 | `api.py:509-510` |
| `codex_tools` | 只读 | `api.py:511-512` |
| `codex_thread_new` | 写（需 `process_execute`） | `api.py:514-517` |
| `codex_turn_send` | 写（并发上限 1） | `api.py:520-522` |
| `codex_interrupt` | 写 | `api.py:523` |

登记与路由是**原子单元**（能力注册 ↔ 路由分发），五项对齐，无孤儿。这一层是干净的，同化不需要重做。

**缺口（本次取证新发现，需补登记）**

| 缺口 | 现状证据 | 建议形态 |
| --- | --- | --- |
| 模型清单未能力化 | `potato_pet/codex_client.py:65-68` 直接调私有实例 `list_models()`；`holo_pet/app.js:1258` 只能从 `state.codex.server.model` 里读 | 新增只读能力 `codex_models` |
| 一次性执行未能力化 | `codex_bridge.run_once` 存在（`codex_bridge.py` 内私建实例），但没有对应 `caps_registry` 项 | 新增 `codex_run_once`（写，需授权）或明确标注"仅供 CLI/自检，不对外" |
| 线程 resume 未能力化 | `_ensure_thread` 里的 resume 只在客户端内部发生 | 视需要新增 `codex_resume`，否则写进 `codex_thread_new` 的语义说明 |
| 审批裁决不是能力 | 审批走事件回调 + `resolve_approval`，不经 `api.run_task` | 面板侧可保持事件制；若要跨进程/跨入口，才需要能力化 |

**注意**：补登记时，`caps_registry.py` 与 `api.py` 必须**同一次落地**，否则 `selfscan` 会按"能力注册 ↔ 路由分发"原子单元报路由断连。

### 4.5 入口收敛（对应目标 1、5）

阶段划分，逐段可验证，不设中间态：

| 阶段 | 动作 | 判定 |
| --- | --- | --- |
| P0 取证冻结 | 记录三处入口的现状指纹（`panel_server.py`、`potato_pet/main.py`、`codex_client.py` 的 SHA256 + mtime） | 指纹落档，后续改动逐条对照 |
| P1 品牌清洗 | 落 §4.3 全部条目（纯文案） | 面板与桌宠的所有文案里搜不到 `Codex`（`index.html` / `app.js` / `main.py` / `codex_client.py`） |
| P2 potato_pet 收口 | 二选一：**(a)** `codex_client.py` 改走共享单例（按 §2.4 三处挂法）；**(b)** 把桌宠的编程能力改为调用 `api.run_task`，删除 `CodexAppServer(` 私有构造 | 生产代码里 `CodexAppServer(` 只剩 `codex_bridge.py` 两处（`_shared` 与 `doctor`）；`grep -c "CodexAppServer(" potato_pet` = 0 |
| P3 单进程化 | 让用户只启动一个进程（holo_pet 面板）；桌宠若要保留，改为面板的一个视图而不是独立进程 | 全机同时只有一个 `codex app-server`（排除官方 Desktop 的调试实例） |
| P4 Desktop 降级 | 按 §4.6 执行 | 桌面无 GBT 快捷方式指向官方 Desktop；`originator='Codex Desktop'` 无新增线程 |

**P2 的推荐选择**：先 (a)。理由：改动面最小、有 `panel_server.py` 现成解法可抄、不触碰能力语义；等 P3 决定桌宠是否并入面板后再考虑 (b)。

### 4.6 "后台调试工具"的操作定义（对应目标 5）

官方 Desktop 降级后，允许与禁止各四条：

**允许**

1. 排障时人工双击启动，直读 app-server 的原生行为（模型解析、线程协议、审批帧）。
2. 作为 A/B 对照：同一份 `~/.codex/config.toml`，比对官方壳与框架壳的行为差异。
3. 用于验证"某个能力是不是内核本身不具备"，还是"我们接错了"。
4. 保留其自身数据（会话、项目），不迁移不删除。

**禁止**

1. 不作为用户的日常入口（不放进桌面/开始菜单的主位置，不设开机自启）。
2. 不作为唯一真源。配置真源永远是 `C:\Users\ADMIN\.codex\config.toml`。
3. 不把它的界面当验收依据（它的启动时刻快照会长期与真源不一致）。
4. 改了 `config.toml` 后，不靠"重启单例"期望它生效——它是单例的父进程，必须整机重启 APP。

**已知的永久性限制（写进档案，避免下次又当 bug 查）**

- Desktop 的 remote-control 类功能走 ChatGPT 账号体系，`API key auth is not supported`。DeepSeek API Key 对它无效，属设计如此，非故障。

### 4.7 验收标准（对应目标 3）

同化完成的判定，逐条可执行：

1. **品牌零残留**：在 `holo_pet/` 与 `potato_pet/` 的用户可见文件里搜 `Codex`，命中数 = 0（`archive/`、`tests/` 除外）。
2. **能力全覆盖**：`caps_registry.BENIGN_CAPS` 中 `domain="llm"` 的项，与 `api.py` 的路由分支**一一对应**，`selfscan` 路由断连 = 0。
3. **单例唯一性**：用户正常使用路径下，全机 `codex app-server` 进程数 = 1（官方 Desktop 未启动时）。
4. **用户视野无外部 AI**：走一遍完整任务（新建会话 → 发问 → 触发一次工具 → 触发一次审批 → 中断），面板上不出现任何内核名词。
5. **入口唯一**：桌面与开始菜单中，指向 GBT 的快捷方式有且只有一个，目标为 holo_pet 面板启动器。
6. **触手可达**：在一个全新宿主会话里，我的工具表直接出现 `codex_status / codex_tools / codex_thread_new / codex_turn_send / codex_interrupt` 五项，**不需要 shell、不需要面板在跑**。
7. **单例不增殖**：经工具表调一次 `codex_thread_new` 之后，全机 `codex app-server` 进程数仍 = 1。

### 4.8 风险与未决

| 项 | 说明 |
| --- | --- |
| 审批语义漂移 | `codex_client.py:269-278` 的 `_decision_payload` 对 `item/permissions/requestApproval` 固定返回 `scope: turn/session` 且 `permissions: {}`。改走共享单例时若照抄，要确认面板侧的裁决口径与它一致，不能一边 accept 一边空权限 |
| 私有实例"顺手拉起" | `models()` 会拉起 app-server。P2 落地后要确认"只读状态查询"不再触发进程创建 |
| 单例是进程内的 | §2.6 已述。**风哥裁：P3 不合并进程**——"一个单例"是逻辑概念，进程数量不是目标，单例引用才是 |
| 官方 Desktop 的自动更新 | 它自己会更新（`electron-internal-update-cdn-enabled`）。降级后若要冻结版本，需要单独裁决，本方案不涉及 |
| 术语表落点 | **已落地**（2026-09-17 授权）：写进 `SOUL.md`（"同化口径"节）与 `HEARTBEAT.md`（每次心跳复读）。 |
| holo_pet UI 规格缺源 | **已结案**：白皮书从未落盘（风哥确认），不重建。规格已落成《holo_pet_UI规格.md》，四条视觉目标中有三条本已落地、仅布局未落地。 |
| 哑弹自启项 | **已清**（2026-09-17 授权）：`CodexPlusPlusWatcher.lnk` 已从启动文件夹移除，原件归档在 `.scratch/archive/CodexPlusPlusWatcher.lnk.20260917.bak`（SHA256 一致）。 |

### 4.9 触手化：把 Codex 装进"调度与操控区"

> 风哥补定义（2026-09-17）："把 Codex 安装进你的**调度和操控区**，在你接收到任务时候，你可以在这些地方去使用触手操控任何东西，就像使用自己的原生能力一样。"

这句话把重心从"面板不露品牌"挪到了"**接到任何任务时，这四个能力已经在我手里**"。两者不是同一件事，前者是外皮，后者是器官。

#### 4.9.1 我的"调度与操控区"到底有几层（实测）

| 层 | 落点 | 现状 |
| --- | --- | --- |
| T1 · 我的工具表（原生触手位） | `~/.codex/config.toml` 的 `[mcp_servers.*]` | **只有 `node_repl` 一条**。没有任何 GBT / Codex 条目 |
| T2 · 工作区 MCP 目录 | `config/mcporter.json` | 5 条，全是外部（`autoclaw-productivity`、`autoclaw-github`、[notion](https://mcp.notion.com/mcp)、`connector:cloudflare`、`connector:vercel`）。且 `AGENTS.md` 自述 "No MCP tools are currently healthy" |
| T3 · GBT 内部能力库 | `gbt_allinone/caps_registry.py:13-43` + `gbt_allinone/api.py:505-523` | **Codex 五项已登记、已路由**，`caps` 与路由一一对应、无孤儿 |
| T4 · 面板 HTTP 面 | `holo_pet/panel_server.py:1230-1329` | 8 个 POST 端点，但 `/api/quick` 是**16 条白名单**（`:1100-1133`），**里面一个 `codex_*` 都没有**；且它 `deferred=True` 异步返回，结果只往 SSE 推 |
| T5 · 触手基础设施 | `gbt_allinone/tentacle/` | `mcp_bridge.py` 是 **MCP 客户端**（GBT 把外部 MCP 当触手消费）；`omni_*` 七域是硬件触手。**全仓没有 MCP 服务端** |

#### 4.9.2 结论：Codex 现在停在 T3，而 T3 不是"操控区"

`caps_registry` 只是**登记表**。我接到任务时要真动它，今天只有两条路，两条都不叫"原生"：

1. 走 `holo_pet` 的对话流（`panel_server.py:809 / :866 / :1082`）——那是**给人用的 UI 触发**，我按不到；
2. 我在 shell 里手工 `py -3.10 -c "...api.run_task('codex_thread_new', ...)"`——**手工触手**：一次一个进程、要自己拼 payload、退出即失效，而且会另起一个 app-server（§2.6）。

**缺口的准确描述**：全仓 `rg -e 'FastMCP' -e 'mcp\.server' -e 'stdio_server'` **零命中**。
GBT 会把外部 MCP 当触手用，却从没把自己暴露成 MCP 服务器——所以**我的工具表里永远看不到 GBT 自己的手**。

#### 4.9.3 方案：加一只"手"——把能力库暴露成 MCP 服务端，注册进 T1

| 项 | 设计 |
| --- | --- |
| 形态 | stdio JSON-RPC MCP 服务器实现，宿主按需拉起（命名与入口留到落地时定，例如 `py -3.10 -m gbt_allinone.mcp_server`） |
| 工具面 | 把 `caps_registry.BENIGN_CAPS` 逐条暴露为 MCP tool；**第一批必须是 `codex_status / codex_tools / codex_thread_new / codex_turn_send / codex_interrupt`** |
| 实现纪律 | 这只手**只准转发 `api.run_task`**，不准自己构造 `CodexAppServer`。否则 T1 会再长出一个 app-server，"两个进程"变"三个" |
| 注册位置 | `~/.codex/config.toml` 的 `[mcp_servers.gbt]`——**宿主配置文件，改动需风哥显式授权** |
| 为什么 stdio 而不是复用 T4 的 HTTP | T4 那台 `ThreadingHTTPServer` 的生命周期绑在 holo_pet 上；我接到任务时不保证面板在跑。stdio 与面板解耦，谁在跑都能伸手 |
| 与 T4 的关系 | 两条通道最终都落到同一个 `api.run_task` → 同一个 `get_shared_server()`。**同源，不是两套** |

#### 4.9.4 与 §4.5 入口收敛的关系

两条线并行，互不替代：

- **§4.5（P0-P4）** 管"用户只看见一张脸"——视野收敛。
- **§4.9** 管"我伸手就够得着"——操控收敛。

只做前者，Codex 是被藏起来的旁路；只做后者，Codex 是长在我身上的手但还会在 APP 里露脸。**两条都做完，才叫同化。**

#### 4.9.5 一处顺带取证

启动文件夹的 `start_bridge.bat` 指向 `C:\Users\ADMIN\Desktop\GBT小土豆\gbt_cap_bridge.py`——
该文件在 V8 树里**不存在**（`Get-ChildItem -Recurse -Filter` 零命中），指向的是旧目录。
与 §1.4 的 `CodexPlusPlusWatcher.lnk` 同类：**第二条哑弹自启**。记录在案，不在本方案内清理。

---

## 五、取证命令附录（可复算）

| 目的 | 命令 / 位置 |
| --- | --- |
| 单例进程与启动时刻 | `Get-CimInstance Win32_Process -Filter "Name='ChatGPT.exe' or Name='codex.exe'"` |
| 配置真源与改动时刻 | `Get-Item "$env:USERPROFILE\.codex\config.toml"` |
| Desktop 身份死循环 | `~/.codex/logs_2.sqlite`，`process_uuid like 'pid:<n>:%'` |
| 线程来源与上游指纹 | `~/.codex/state_5.sqlite`，`threads` 表的 `originator / source / model_provider / model` |
| Desktop 功能面 | `~/.codex/.codex-global-state.json`（顶层键 + `electron-persisted-atom-state`） |
| 能力登记 | `gbt_allinone/caps_registry.py` |
| 能力路由 | `gbt_allinone/api.py:505-523` |
| 共享单例 | `gbt_allinone/codex_bridge.py:1385-1401` |
| 面板 attach 参考实现 | `holo_pet/panel_server.py:234-320` |
| 桌面主入口指向 | `C:\Users\ADMIN\Desktop\GBT小土豆.lnk` → `C:\Program Files\AutoClaw\AutoClaw.exe --gbt-workspace ...` |
| 自启面（注册表） | `Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"` 与 `HKLM:` 同名键 |
| 自启面（启动文件夹） | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`，用 `New-Object -ComObject WScript.Shell` + `CreateShortcut` 解析 TargetPath / Arguments |
| 自启面（计划任务） | `Get-ScheduledTask` 过滤 `ChatGPT` / `Codex`；详见 §1.4 |
| 拉起源穷尽搜索 | `rg -i -e 'ChatGPT\.exe' -e 'OpenAI\.Codex' -e 'shell:AppsFolder'`，范围限定桌面 / 文档 / 开始菜单 / `~/.codex/config.toml` / AutoClaw workspace，`-g` 白名单 `*.ps1 *.bat *.cmd *.vbs *.lnk *.json *.toml *.md` |
| 我的工具表（T1） | `Get-Content "$env:USERPROFILE\.codex\config.toml"` 的 `[mcp_servers.*]` 段；当前只有 `node_repl` |
| 工作区 MCP 目录（T2） | `config/mcporter.json` 的 `mcpServers` 键 |
| 面板 HTTP 面（T4） | `holo_pet/panel_server.py:1230-1329`（`do_GET` / `do_POST`）；`/api/quick` 白名单见 `:1100-1133` |
| 是否已有 MCP 服务端（T5） | `rg -e 'FastMCP' -e 'mcp\.server' -e 'stdio_server' gbt_allinone holo_pet` → 零命中 |
| 哑弹自启 · 第二条 | `Get-ChildItem -Recurse -Filter gbt_cap_bridge.py` → 零命中（`start_bridge.bat` 指向不存在的 V8 路径） |

## 六、状态

- 本文件为**方案**，未改任何生产代码。
- 三处入口当前均未运行：官方 Desktop 仅在我上一轮排障时重启过（10:51:40），`holo_pet` 与 `potato_pet` 未启动。
- **五件拍板已下（2026-09-17）**：P2 选 **(a)** 改共享单例；P3 **不合并进程**（"一个单例"是逻辑概念）；
  术语表 **已写进** `SOUL.md` / `HEARTBEAT.md`；白皮书 **不存在、不重建**；哑弹自启项 **已清**。
  施工口径见《Codex同化施工方案.md》。
- **第二条同化轴已取证完毕（§4.9）**：Codex 五个能力停在 `caps_registry` 登记表，**我的工具表（`~/.codex/config.toml` 的 `[mcp_servers.*]`）里只有 `node_repl` 一条**，
  全仓没有 MCP 服务端。要"像原生能力一样"用，需要新增一只 MCP 手并把 `[mcp_servers.gbt]` 写进宿主配置——**该配置属宿主，改动需风哥显式授权**。
  本轮未动手。
- **"白皮书"结案**：风哥确认它从未落盘——是风哥与数字叔叔在对话里聊出来的理念。
  仓库内确实不存在该文件（`rg` 全量扫过），**不重建**。
  UI 规格已按 `holo_pet/README.md` 现有口径 + 风哥四条视觉目标落成《holo_pet_UI规格.md》。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
