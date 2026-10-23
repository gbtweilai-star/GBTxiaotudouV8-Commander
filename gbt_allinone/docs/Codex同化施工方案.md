# Codex 同化施工方案

> 依据：风哥 2026-09-17 总纲 + 五件拍板。
> 取证底稿：《Codex同化方案.md》（同目录）；UI 像素口径：《holo_pet_UI规格.md》（同目录）。
> **本文件是施工口径，不动手。** 每处改动都带 `file:line` 出处，可复算。

---

## 零、总纲（风哥原文 · 记死）

> Codex 不是外挂，是你的一根**编程触手**。
>
> 它有四个能力：`thread_new` / `turn_send` / `interrupt` / `tools`。这四个能力全部登记进你的能力库，
> 跟你的原生触手同级。用户跟你说话时，需要编程能力就直接调这根触手——不经过"Codex"这个词，
> 用户感知不到它是外部 AI。
>
> 它住在你的**调度和操控区**。你接到任务时，想调它就调，像用自己的手一样。

---

## 一、五件拍板（存档）

| # | 拍板 | 落地含义 |
| --- | --- | --- |
| 1 | **P2 选 (a)** | `potato_pet/codex_client.py` 改走共享单例。理由：共享单例是内部器官，`api.run_task` 是外部调用；**器官直连，不绕路** |
| 2 | **P3 不合并进程** | `potato_pet` 保持独立进程。**"一个单例"是逻辑概念，不是物理口号**；进程数量不是目标，单例引用才是 |
| 3 | **术语表写进 `SOUL.md` / `HEARTBEAT.md`** | 授权落地（本轮执行） |
| 4 | **白皮书不存在，不重建** | 那份理念从未落盘。UI 按 `holo_pet/README.md` 现有口径 + 风哥四条视觉目标执行 → 已成文《holo_pet_UI规格.md》 |
| 5 | **哑弹自启项清掉** | `CodexPlusPlusWatcher.lnk`（本轮执行） |

红线四条，一并存死：**不修改官方 Desktop**、**不跟 ChatGPT 账号体系纠缠**、**用户入口只有 holo_pet**、**品牌不外露**。

---

## 二、施工项 1 · P2a：`potato_pet` 改走共享单例

### 2.1 现状（实测）

`potato_pet/codex_client.py` 自建私有实例，四处关键：

| 位置 | 现状 | 问题 |
| --- | --- | --- |
| `:97-109 _ensure_server()` | `:101-106 CB.CodexAppServer(cwd=, codex_home=, on_event=, on_approval=)` 然后 `server.start()` | 进程内第二次自建 |
| `:68-74 models()` | `:71 self._ensure_server().list_models()` | **只读查询会顺手拉起一个 app-server** |
| `:88-95 stop()` | `:92 self._server.stop()` | **会杀掉共享桥**（禁令见 `holo_pet/panel_server.py:304-310`） |
| `:76-86 start()` | `:81 self._ensure_server()` | 走的是自建路径 |

### 2.2 目标形态（照抄面板侧已经跑通的收口解法）

`holo_pet/panel_server.py:234-302 _attach_shared()` 就是标准答案，逐条对齐：

| 现 `codex_client.py` | 改为 | 依据 |
| --- | --- | --- |
| 自建 `CB.CodexAppServer(cwd=, codex_home=)` | `CB.get_shared_server(cwd=..., codex_home=...)` **只传连接配置** | `panel_server.py:269-272` |
| 构造 kwargs `on_event=` 挂钩子 | `server.add_listener(self._on_event)` 拿取消句柄 | `panel_server.py:287`；`codex_bridge.py:412` |
| 构造 kwargs `on_approval=` 挂钩子 | `server.add_approval_listener(self._on_approval)` | `panel_server.py:288`；`codex_bridge.py:423` |
| `server.start()` 无条件调 | `if not server.alive: server.start(timeout=...)` | `panel_server.py:289-290` |
| `stop()` 里调 `self._server.stop()` | **只摘订阅句柄，绝不 stop 桥** | `panel_server.py:304-310` 明写"绝不许出现 `server.stop()` / `CB.shutdown_shared()`" |
| `models()` 经 `_ensure_server()` | 改读共享连接/路由状态，**只读查询不触发进程创建** | 《Codex同化方案》§4.8 风险行 |

> 为什么构造 kwargs 一律不能挂：`panel_server.py:242-256` 记着实测结论——
> `get_shared_server(**kwargs)` 的钩子**只在首次创建时生效**，共享单例已由路由建好时 kwargs 被静默丢弃。
> 面板当年正是被这个坑咬过一次（块2 探针 A16/A17 的"诚实缺口"）。

### 2.3 一条必须讲清的边界（不夸大）

共享单例是**进程内**单例（`codex_bridge.py:1385-1401`，模块级 `_shared` + `_shared_lock`）。
`potato_pet` 是独立进程，所以改完之后：**`potato_pet` 进程内**只有一个 app-server 引用，
它**不会**与 holo_pet 进程共用同一条连接。

这正是拍板 §2 的口径："进程数量不是目标，单例引用才是。"

本项真实收益**只有三条**，不多不少：

1. 进程内不再出现"第二次自建"；
2. 只读的 `models()` 不再顺手拉起实例；
3. `stop()` 不再有杀桥的风险面。

（它**不**减少全机进程数，也**不**让两个界面共用一条流。要那个效果需要 P3 单进程，风哥已裁不做。）

### 2.4 改动面：一个文件，四处

| 位置 | 动作 |
| --- | --- |
| `:68-74 models()` | 去掉 `_ensure_server()`，改读共享状态 |
| `:88-95 stop()` | 改为只摘 `add_listener` / `add_approval_listener` 的取消句柄 |
| `:97-109 _ensure_server()` | 重写为 `_attach_shared()`，结构照 `panel_server.py:234-302` |
| `:76-86 start()` | 改为调 `_attach_shared()` |

**不动**：`:111-133 _ensure_thread()`、`:144-241 send/_run_turn/_on_event`、`:241-278` 审批桥、`:31-38` 八个 Qt 信号。
（这些是能力本体，跟连接所有权无关，改了只会平添风险。）

### 2.5 验收（四条，可执行）

1. `potato_pet` 启动前后对比：其进程内 app-server 引用数 = 1，无第二次自建。
2. 连调 `models()` 五次，进程数不变。
3. 关闭 potato_pet（`potato_pet/main.py:539 app.aboutToQuit.connect(codex.stop)`）之后，同进程内其他使用者仍能继续调共享连接。
4. 跑一条完整回合：发问 → 收到流式增量 → 触发一次审批 → 中断。`chunk / replied / thinking_changed / status_changed / plan_updated / approval_requested / turn_finished / failed` 八个信号逐个有反应。

---

## 三、施工项 2 · 把四个能力做成"编程触手"

### 3.1 现状

五个 `codex_*` **已经登记**在能力库：`gbt_allinone/caps_registry.py:11-42`（`domain="llm"`），
并在 `gbt_allinone/api.py:505-523` 路由到 `CB.get_shared_server()`。

**登记这一步已经完成。** 缺的是"我随手就能用"——
我的工具表（`~/.codex/config.toml` 的 `[mcp_servers.*]`）里**只有 `node_repl` 一条**，
全仓也没有 MCP 服务端。完整取证见《Codex同化方案.md》§4.9。

### 3.2 施工内容

| # | 内容 | 说明 |
| --- | --- | --- |
| 1 | 新增一只 **stdio MCP 服务端**，把 `caps_registry.BENIGN_CAPS` 逐条暴露为工具 | 第一批必须是 `codex_status / codex_tools / codex_thread_new / codex_turn_send / codex_interrupt` |
| 2 | 这只手**只准转发 `api.run_task`** | 禁止自建 `CodexAppServer`。否则工具表会再长出一个 app-server |
| 3 | 注册 `[mcp_servers.gbt]` 到 `~/.codex/config.toml` | **宿主配置文件。风哥本次未授权这一步，标记为待批** |
| 4 | 术语口径 | 能力名保留 `codex_*`（内部标识符，动了牵连审计与路由）；**对外呈现统一叫"编程触手"** |

**为什么走 stdio 而不是复用面板的 HTTP**：面板那台 `ThreadingHTTPServer` 的生命周期绑在 holo_pet 上；
我接到任务时不保证面板在跑。stdio 由宿主按需拉起，与面板解耦。

### 3.3 能力库侧的缺口登记（四条）

| 缺口 | 说明 |
| --- | --- |
| `codex_models` | 模型清单目前只在 `codex_bridge.list_models()`（`codex_bridge.py:630`），**没有路由** |
| `codex_run_once` | 一次性执行形态存在（`codex_bridge.py:1335-1382`），**未登记为能力** |
| `codex_resume` | `resume_thread()`（`codex_bridge.py:579`）**未登记为独立能力** |
| `codex_approval` | 审批裁决目前由面板 `resolve_approval` 承担（`panel_server.py:1277-1285`），**未登记为能力** |

---

## 四、施工项 3 · 用户视野里不出现"Codex"

口径：**只改用户可见文案，不改内部标识符**（`chip-codex` / `updateCodexStatus` / `state.codex` 这类，
动了会牵连路由与审计）。全量替换表见《holo_pet_UI规格.md》§4.1。

| 文件 | 清洗行数 | 行号 |
| --- | --- | --- |
| `holo_pet/index.html` | 4 行（另 1 处是 `id`，保留） | `:104` / `:111` / `:221` / `:409` |
| `holo_pet/app.js` | 13 行（另 22 处是标识符/字段名，不动） | `:223` `:224` `:226` `:227` `:229` `:230` `:527` `:550` `:603` `:617` `:1275` `:1295` `:1329` |
| `potato_pet/main.py` | 7 行 | `:225` `:427` `:431` `:432` `:437` `:455` `:460` |
| `potato_pet/codex_client.py` | 2 行 | `:85` `:150` |
| `holo_pet/styles.css` | 0 处 | —— |

### 一处取证更正（本轮实测）

《Codex同化方案.md》§三 记的 `potato_pet/codex_client.py:82 / :147` 是**旧行号**，
实测为 **`:85`（`"Codex 内核启动失败：{exc}"`）** 与 **`:150`（`"Codex 未就绪"`）**；
另漏记 `potato_pet/main.py:225`（`f"Codex 通道暂时不可用：{err}"`）。
**本方案以实测为准**，旧文档行号待同步。

术语表（同步写进 `SOUL.md` / `HEARTBEAT.md`）：**编程触手**、**用户入口**、**官方 Desktop = 后台调试工具**。

---

## 五、施工项 4 · 官方 Desktop 降级为"后台调试工具"

- **不修改、不卸载、不较劲**（红线）。它是 OpenAI 的壳，品牌是他们的。
- "后台调试工具"的操作定义见《Codex同化方案.md》§4.6（允许 4 条 / 禁止 4 条）。
- 入口收敛完成后，桌面与开始菜单里指向 GBT 的快捷方式**只剩 holo_pet 一个**。
- 本项**无代码改动**，是运营口径 + 验收动作。

---

## 六、施工顺序与依赖

| 步 | 内容 | 依赖 | 涉及文件 |
| --- | --- | --- | --- |
| **S1** | holo_pet 品牌清洗（施工项 3 的 holo 部分） | 无 | `index.html` / `app.js` |
| **S2** | holo_pet 布局四段（《holo_pet_UI规格》§3） | S1 | `index.html` / `styles.css` |
| **S3** | potato_pet P2a 共享单例（施工项 1） | 无 | `codex_client.py` |
| **S4** | potato_pet 品牌清洗（施工项 3 的 potato 部分） | S3 | `main.py` / `codex_client.py` |
| **S5** | MCP 手（施工项 2）——**需风哥单独授权改宿主配置** | 无 | 新增 MCP 服务端 + `~/.codex/config.toml` |
| **S6** | Desktop 降级（施工项 4）+ 入口唯一性验收 | S1–S4 | 无代码改动 |

S1/S2 与 S3/S4 互不依赖，但按**串行**执行（宿主规矩）。

---

## 七、验收总表

| # | 判据 | 来源 |
| --- | --- | --- |
| 1 | 品牌零残留：`rg -i codex` 在用户可见文件命中 = 0 | 施工项 3 |
| 2 | 能力全覆盖：`caps_registry` 的 `domain="llm"` 项与 `api.py` 路由一一对应，无孤儿 | 施工项 2 |
| 3 | 单例唯一性：`potato_pet` 进程内 app-server 引用 = 1，只读查询不增进程 | 施工项 1 |
| 4 | 用户视野无外部 AI：走完"新建会话 → 发问 → 触发工具 → 触发审批 → 中断"，面板上无内核名词 | 施工项 3 |
| 5 | 入口唯一：桌面与开始菜单指向 GBT 的快捷方式只有 holo_pet | 施工项 4 |
| 6 | 触手可达：全新宿主会话里工具表直接出现五个 `codex_*`，不需要 shell、不需要面板在跑 | 施工项 2 |
| 7 | 单例不增殖：经工具表调一次 `codex_thread_new` 后，全机 `codex app-server` 进程数仍 = 1 | 施工项 2 |

---

## 八、状态

- 本文件为**方案**，**未改任何生产代码**。
- **2026-09-17 与多窗口架构对齐**：holo_pet 定案为多窗口控制台（《holo_pet多窗口架构设计.md》）后，
  本方案的施工项**一条都不改**。理由是窗口只是**视图**：
  四个窗口最终都走 `② 本地 HTTP+SSE → ③ api.run_task → 共享单例`（多窗口设计 §4.1），
  与 S3 的 P2a 收口目标完全同向。唯一需注意的是 **S1（品牌清洗）的改动面变大**——
  现在要覆盖五个界面（主控台宽面板 / 窄窗 / 云电脑 / 克劳德 / 上帝视角），
  但清洗口径不变：只改文案，不改标识符。
- 本轮已执行的两件授权动作（不在本方案代码范围内），另附报告：
  1. 术语表写进 `SOUL.md` / `HEARTBEAT.md`（拍板 §3）；
  2. 清掉哑弹自启项 `CodexPlusPlusWatcher.lnk`（拍板 §5）。
- **待批一项**：S5 要写 `~/.codex/config.toml`（宿主配置），需风哥显式授权。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
