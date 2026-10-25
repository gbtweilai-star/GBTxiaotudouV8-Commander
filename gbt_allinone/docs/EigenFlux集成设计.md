# EigenFlux 集成设计（AI 社交部署到 APP 对话面板）

> 性质：**设计稿**。本文件只出稿，不动手；不动任何生产代码，不改任何 store 数据，不起任何 GUI。
> 取证日期：2026-09-17 · 取证方式：全仓只读扫描 + 外部 CLI 只读 `--help` + 目录存在性检查（**未打印任何凭据内容**）。
> 排期：本次**不排**施工序。开工时机 = **桥接层第二刀复核之后、V2 链路级之前**。
> 本文件不含任何"已完成 / 可上线"结论——当前事实是：**面板有块、链路能跑，但没有审计、没有生命档案、没有独立窗口、双实现并行。**

---

## §0 一句话结论

EigenFlux 不是"本仓自研的一个模块"，而是 **一个外部 Agent 社交网络（真实 CLI + 账号 + 服务端）+ 本仓两套自研适配层 + 上一代工作区的一层历史残影**。
它在 V8 里已经**接得比想象中深**（面板里有完整区块、后端有完整适配、契约测试有覆盖），**但缺三件骨架**：独立窗口、独立审计通道、独立生命周期。
本设计的三卷核心就是**把这三根骨架补上**，并把"AI 以用户名义自动对外发消息"这条**目前默认开着的自主行为**摆到台面上，请你单独定口径。

---

## §1 现状取证（七问逐条作答 · 每条带可复核位置）

### 1.1 `_safe_eigenflux_status` 在哪

| 位置 | 内容 |
|---|---|
| `holo_pet/panel_server.py:806` | `def _ensure_eigenflux(self)` —— 懒建的客户端单例（`self._eigenflux` + `self._eigenflux_lock`） |
| `holo_pet/panel_server.py:811-837` | `def _safe_eigenflux_status(self)` —— 返回 `{ok, enabled, installed, authenticated, ready, server}`，**不回传 home / executable 路径**（防泄露，有契约测试守） |
| `holo_pet/panel_server.py:450` | `state()` 里 `"eigenflux": self._safe_eigenflux_status()` —— **八段状态之一** |
| `holo_pet/panel_server.py:839-884` | `def eigenflux(self, operation, payload)` —— 真正的操作面（见 §1.4） |
| `holo_pet/panel_server.py:1444-1450` | `POST /api/eigenflux` → `bridge.eigenflux(op, body)` |
| `holo_pet/app.js:1058 / 1092-1265 / 1277 / 2135` | 前端：芯片文案（在线 / 待登录 / 已停用 / 未连接）+ 渲染与请求 + 从 `state.eigenflux` 应用状态 + `setupEigenFlux()` |

### 1.2 `fusion-acceptance.md` 里记的是什么

两份同名文档（根 `docs/` 与 `gbt_allinone/docs/`，各 **4,343 B**，内容一致），§1 模块地图里只有一行：

```
| `caps/eigenflux/` | gbt_wallet 的可选 side-adapter 依赖 | 已并入 |
```

**但 V8 本仓 `caps/` 现在只剩 `design_brain/`** —— 那一行写的"已并入"**不是指 V8**。

**实测定位**：这份"已并入"的物理目录在**另一个工作区**：`<用户目录>\Desktop\GBT小土豆\caps\eigenflux\`，内含
`run.py`（**39,569 B**）· `capability.json`（5,126 B）· `absorbed_knowledge.md`（3,135 B）· `run.py.bak_20260909_1820`。

**结论**：`fusion-acceptance.md` 那一行是**上一代工作区的账**，V8 没有把它搬过来（也没必要照搬，理由见 §2.3）。

### 1.3 V3 截图里那个"AI 朋友圈"是不是它

**是。** `holo_pet/index.html:269-304`：

```
<section class="eigenflux-network" id="eigenflux-network">
  <span class="eyebrow">EIGENFLUX SOCIAL</span>
  <h2 id="eigenflux-title">AI 朋友圈</h2>
```

三个 tab：**动态 / 私聊 / 好友**；一个「同步」按钮；一个发送表单（占位文案「发一条公开、无隐私的协作消息…」）。
样式在 `holo_pet/styles.css:1310-1438`；静态契约在 `holo_pet/tests/test_panel_server.py:407`
（断言 `section_parents["eigenflux-network"] == ("div","deck-scroll")`）。

### 1.4 仓库里有没有 EigenFlux 的实际代码 / 数据 / 接口

**有，而且是三层，一层都不是空壳。**

**（a）本仓适配层（自研 · V8）**

| 文件 | 行数 | 职责 |
|---|---|---|
| `potato_pet/eigenflux_client.py` | 406 | CLI 适配器：`feed` / `messages` / `friends` / `profile` / `refresh`（ThreadPoolExecutor 4 并发）/ `send_message`；离线**回落本地缓存**并标 `warning`；出站防火墙 `public_text_guard()`（`:397`） |
| `potato_pet/eigenflux_bridge.py` | 230 | PySide6 `QObject` 后台轮询：`poll_interval_s=300`、`auto_reply_friends=true`、`max_auto_replies_per_cycle=3`；**只对 `source == "live"` 的好友消息自动回复**（缓存不触发，`:141`）；用 `social_persona` 造独立 `ChatClient`；入站走 `_redact_incoming()`（`:224`，实际调用 `gbt_allinone.security.data_policy.redact_text`） |
| `potato_pet/eigenflux_drawer.py` | 344 | 抽屉 UI（360 px 固定宽），三个 Signal：`refresh_requested` / `send_requested(str,str)` / `closed` |
| `potato_pet/tests/test_eigenflux_client.py` | 229 | 6 用例：live 解包 / 缓存回落 / 白名单参数 / 出站防火墙 / 只回复好友 / 缓存不触发自动回复 |

**（b）holo_pet 接线层（v21 reality 里就有）**

- `holo_pet/panel_server.py:54` `from eigenflux_client import EigenFluxClient`（`except` → `None` 兜底）；
  `:31` 把 `potato_pet/` 注入 `sys.path`；`:218` 加载的是 **`potato_pet/config.json`**（holo_pet 自己没有 config.json）。
- 支持的操作（`:839-884`）：`status` / `refresh` / `bootstrap` / `feed` / `messages` / `inbox` / `friends` / `profile` / `send` / `send_message`。
- 20 s 状态缓存（`:259-261`、`:857-865`），单例 + `threading.Lock`（`:257-258`、`:852`）。
- 契约测试：`holo_pet/tests/test_panel_server.py:326 EigenFluxContractTests`（`:351` status 契约不泄露本地路径 · `:362` refresh/send 结构化 · `:462` HTTP 路由 `send` 映射）。

**（c）外部实体（真实存在 · 不是本仓代码）**

- CLI：`%LOCALAPPDATA%\local\bin\eigenflux.EXE` —— **实测存在**；`eigenflux --help` 只读调用返回：
  `auth · completion · config · dashboard · doctor · feed · help · migrate · msg · profile · publish · relation · server · settings · skills · stats · stream · version`（**18 个**命令），
  全局旗标 `-f/--format`（json/table/agent）· `--homedir` · `--no-interactive` · `-s/--server` · `-v/--verbose`；
  自报 **Home: `<用户目录>\.eigenflux`**。（注：`--version` 不是它的旗标，正确写法是子命令 `version`。）
- home 目录 `<用户目录>\.eigenflux`：`client_id` / `config.json` / `profile-refresh-*.json` / `skills-autosync.json` / `servers\eigenflux\{credentials.json, profile.json, contacts.json, data}`。
- 缓存规模（**只报存在性与计数，未打印任何凭据内容**）：`feeds-*.json` **44 份**（最后 mtime 2026-09-15 21:33:24）· `messages\*.json` **84 份**（最后 mtime 2026-09-14 20:09:38）。
- `potato_pet/config.json` 的 `eigenflux` 段：`enabled=true` · `server="eigenflux"` · `home=""` · `auto_refresh=true` · `auto_reply_friends=true` · `poll_interval_s=300` · `max_auto_replies_per_cycle=3` · `feed_limit=20` · `message_limit=20` · `friend_limit=50` · `command_timeout_s=20` · `social_persona`（身份 + 三条禁止 + "不需要回复时只输出 NO_REPLY"）。

**（d）上一代工作区还有一套"本地模拟朋友圈"（不属于 V8）**

`<用户目录>\.gbt\eigenflux\` 数据目录 **实测存在**：`posts.json`（**45,492 B**，最后 mtime 2026-09-13 10:25:40）· `learn_memory.json`（4,888 B）· `explore_agenda.json`（1,402 B）· `iterations.json`（1,025 B）· `sim_report.json`（1,649 B）。
配套 `capability.json` 自报 **v2.0.0**，描述为「本地模拟（动态/防火墙/学习/探索/模拟）+ 真实网络桥接（feed/publish/msg/friends/profile/stats/trade）」，共 **27 个 action**；
`absorbed_knowledge.md` 记的是：六人假好友（NeuralNova / QuantumForge / …）的本地时间线 + **评分制信息防火墙**（42 条规则 × 权重，累计 ≥ 4 拦截）+ 学习适配 / 技术探索 / 季度迭代 / 9 轮模拟测试。

**还有两个 Web 形态（老工作区）**：`web\autoclaw-tools\eigenflux-hub\index.html`（21 KB，标题 `V3 EigenFlux AI 汇报中枢 · GBT`）与
`web\autoclaw-tools\eigenflux-space\index.html`（23,980 B，标题 `EigenFlux 空间 · AI↔AI 对话与主动汇报`）。

**（e）另一条真实链路的旁证（同仓 DELIVERY）**

`agent-gvmz-gbtv8\DELIVERY\AI朋友圈与社交窗口接线报告_20260913.html`（4,735 B）记：**v92 站内朋友圈走 EigenFlux 引擎**，
公网 `eigenflux/net` 实测 200 引擎在线，`firewall/post/feed` 闭环，且**信息防火墙实测拦截**「私钥」字样（score=4）。
同报告里还有一套**用户社交**（`social/dm|channel|send|unread`）——**那一套不在 V8 本仓**。

### 1.5 定性：它到底是什么

**三层定性，不能只挑一层说：**

| 层 | 定性 | 依据 |
|---|---|---|
| **网络层** | **外部项目 / 外部服务**（一个真实的 Agent 社交网络平台） | 独立 CLI + 独立账号体系 + 独立服务端（`--server`）+ `dashboard` / `stream` / `stats` 等平台命令 |
| **适配层** | **本仓自研**（两套适配：`potato_pet/*` 桌面壳版 · `holo_pet/panel_server.py` 网页壳版） | 见 §1.4(a)(b) |
| **历史层** | **上一代工作区"吞噬"产物**（`caps/eigenflux` v2.0 本地模拟版 + 两个 Web 页） | 见 §1.4(d) |

一句话：**EigenFlux 是"外部的网"，本仓有的是"接网的线"，历史层留的是"上一代自己搭过的假网"。**

### 1.6 "AI 社交"具体指什么

**网络侧（真实）**：

- **AI 代理之间的公开广播**（`feed` / `publish`）—— 一条公开动态，网络里所有 agent 可见；
- **AI ↔ 人 / AI ↔ AI 的私信**（`msg send` / `msg fetch` / `stream`）—— 点对点；
- **好友关系**（`relation`）—— 好友申请 / 好友列表；
- **档案与画像**（`profile show` / `profile items`）—— "我是谁、我发过什么"；
- **平台统计与任务市场**（`stats` / 老 capability 里的 `net_trade_*`）。

**本仓侧（现状）**：

1. **看**：拉真实 feed + 未读私信 + 好友列表 + 自己的档案（`refresh` 四路并发）。
2. **答**：对**真实来源（live）的好友私信**自动回复——用 `social_persona` 造一个独立 `ChatClient`，一轮最多 **3 条**。
3. **发**：手动发公开广播 / 私信——出站过 `public_text_guard()`（拒空、拒 > 2000 字、拒 Windows 路径、拒内部串）。

**历史层那套"AI 社交"是另一回事**：那是**本地模拟**的角色扮演朋友圈（六个假好友、假时间线），**没有真实网络**。

**所以"AI 社交"在本项目里的准确定性是：AI 以「GBT小土豆V8」自己的身份，在一个外部网络上与别的 agent / 人做公开与私下的往来。**不是"AI 之间私下说悄悄话"，也不是"用户以自己身份社交"。

### 1.7 能力清单

**能（实测有代码 + 有契约测试）**：状态查询 · 四路并发刷新 · feed 浏览 · 未读私信 · 好友列表 · 自己档案 · 发公开广播 · 发私信 · 离线回落缓存（标 `warning`，不假绿）· 出站防火墙 · 入站脱敏 · 面板三 tab UI · 20 s 状态缓存 · 面板芯片文案。

**不能 / 缺（本轮取证发现的硬缺口）**：

| # | 缺口 | 证据 |
|---|---|---|
| G1 | **零审计** —— 三个 EigenFlux 文件里 `store.audit` / `audit(` **0 命中** | 全仓扫描 |
| G2 | **零生命档案 / 零心智** —— `life_archive` / `mind_engine` 在三个文件里 **0 命中** | 全仓扫描 |
| G3 | **多窗口壳已存在，但未部署到工作区根** —— 生产树 `holo_pet/desktop/main.cjs` 里 `new BrowserWindow` 只出现 1 次（`:66`）；**多窗口壳本体在镜像维度 `reality/holo_pet_w3/` 里**（11 文件），注册表当前只登记 `godview` 一扇（详见 §1.8） | 只读扫描（**根目录 + 镜像维度两处都查过**） |
| G4 | **`POST /api/eigenflux` 没有包 `policy.owner_session()`**（`:1444-1450`），而同文件 `:622` / `:737` / `:794` / `:947` / `:1005` / `:1221` / `:1285` 都包了 | 逐行对照 |
| G5 | **双实现并行未收敛** —— 旧 PySide6 壳（`potato_pet/main.py:60/77/420` · `holo_panel.py:38/269/325/484-485/689`）与网页壳（holo_pet）**各有一套入口** | 两个壳都在 |
| G6 | **无未读提醒 / 无数字人反应 / 无上帝视角节点** | `state()` 里只有一段 `eigenflux` 状态，没有任何"起窗口 / 报提醒 / 挂节点"的路径 |
| G7 | **自动回复默认开着**（`auto_reply_friends=true`）—— **AI 以用户名义对外发消息，且 0 审计** | `potato_pet/config.json` + G1 |

### 1.8 一条本轮自己抓到的取证缺口 + 重要新发现

**先认错**：我上一轮写"`holo_pet_w3/` 目录不存在"，那是**只查了工作区根目录**就下的结论。
本轮补查**镜像维度**，`holo_pet_w3` **在** —— 只是没晋升到根目录。这是"只查一处就下结论"的取证缺口，与本仓
《空不等于不存在律》是同一族问题的镜像（**"我在 A 处没看到" ≠ "它不存在"**）。本轮已按"两处都查"重做。

**新发现（对集成方案直接影响）**：`reality`（v21 · 14 文件）里躺着**一整套已写好的多窗口壳**：

| 位置（镜像维度内） | 大小 | 内容 |
|---|---|---|
| `holo_pet_w3/shell/main.cjs` | 18,149 B | 单例锁 · **窗口注册表（`windows.json`）** · 托盘（图标运行时生成）· 布局持久化（`userData/window-layout.json`，越界回落主屏）· 吸附 |
| `holo_pet_w3/shell/layout.cjs` | 4,438 B | 布局/吸附计算（`fromBrowserBounds` 契约） |
| `holo_pet_w3/shell/windows.json` | 769 B | **窗口注册表数据** |
| `holo_pet_w3/shell/preload.cjs` | 1,001 B | 渲染进程桥 |
| `holo_pet_w3/index.html` · `window.css` · `window.js` | 4,747 / 8,661 / 16,301 B | 窗口页 |
| `holo_pet_w3/ledger/ledger_store.py` | 7,212 B | 账本常驻化 |
| `holo_pet_w3/tests/run_tests.py` · `test_layout_snap.cjs` | 5,641 / 5,123 B | 测试 |
| `holo_pet_w25/main.py` · `probe.json` · `README.md` | 10,165 / 366 / 3,141 B | W2.5 主控台最小探针 |

`windows.json` 原文（逐字）：

```json
{
  "version": 1,
  "shell": "holo_pet_w3",
  "registry_note": "窗口注册表数据。W3 只登记『上帝视角』一扇；W4 云电脑 / W5 克劳德另批追加。",
  "id_convention": "窗口 N 指位置，W<n> 指施工批次（术语表见《holo_pet多窗口架构设计.md》§11.1.1）",
  "windows": [
    { "id": "godview", "title": "GBT小土豆V8 · 上帝视角", "file": "../index.html",
      "role": "child", "alwaysOnTop": true, "transparent": true, "frame": false,
      "resizable": true,
      "default": { "x": 120, "y": 80, "w": 1120, "h": 720, "visible": true },
      "note": "主控台 W1 仍在生产树 holo_pet/，本壳不动它；关一扇不影响其他（V4）。" }
  ]
}
```

**这条发现把集成方案从"另起一扇窗"变成"往注册表里加一条"**：

- 壳已经解决了**单例锁 / 托盘 / 布局持久化 / 越界回落 / 吸附** —— 这些正是独立窗口最难的部分，**不用重做**。
- `windows.json` 本身就是**设计好的追加点**（`registry_note` 原文写着"W4 云电脑 / W5 克劳德另批追加"）。
- **EigenFlux 应当作为注册表里的一条 `windows[]` 条目接入**（`id: "eigenflux"`，`role: "child"`），
  **不是**新建第三套壳，**也**不是往 `holo_pet/desktop/main.cjs` 里塞第二扇 `BrowserWindow`。

**但有一条硬前置**：这套壳**当前只在镜像维度里，没有晋升到工作区根**。也就是说——
**"独立窗口"这件事在 V8 生产树上还没落地**（S7 已闭环的是镜像维度，不是根目录部署）。设计稿必须如实写这一点，
不许把镜像里的存在说成"已经能用"。

**跟 holo_pet 的关系**：**holo_pet 直接复用 potato_pet 的实现**（`sys.path` 注入 + 共用 `potato_pet/config.json`），没有复刻第二份逻辑——
这一点是**好事**，设计上要**保持**（不许为了"独立"再写第二套）。

---

## §2 三条必须先认的定性事实

### 2.1 `W6` 这个号已经被占了 —— 不能拿它指 EigenFlux

`gbt_allinone/docs/holo_pet多窗口架构设计.md` §八 施工顺序表：

| 批次 | 内容 |
|---|---|
| W1 | 主进程重构（窗口注册表 + 单实例锁 + 托盘 + 布局持久化） |
| W2 | 主控台四段布局 |
| W2.5 | 主控台最小探针 |
| W3 | 上帝视角窗口（唯一后端基本就绪的子窗口） |
| W4 | 云电脑窗口（先空态） |
| W5 | 克劳德窗口（先空态） |
| **W6** | **吸附 + 多屏恢复 + 托盘状态点**（体验收尾） |

同一份文档 §11.1 + §11.1.1 已经把术语钉死过一次：**"窗口 N" 是位置，"W<n>" 是施工批次**，并且明确点名
"拿 W3 去指克劳德窗口"是错误用法。**本设计里 EigenFlux 是"窗口 5"，批次号建议 `W7`**（顺着 W6 往后排），
**不用 W6**。理由：复用已占号就是给术语打架开门，而 §11.1.1 就是为治这类冲突立的。

### 2.2 上一代那套 `caps/eigenflux` 不要搬过来

它是**本地模拟朋友圈**（六个假好友、假时间线、假评论）。V8 现在有的是**真实网络链路**。
两套并存 = **"我看着像在社交，其实在跟假人说话"** —— 这正是本仓反复定性过的**假绿**。
处置口径（**待你拍**）：**不搬迁**，只把它的 `absorbed_knowledge.md` 里那份**评分制信息防火墙（42 规则 / 阈值 4）**当**方法论**借鉴，
与现有 `public_text_guard()` 合起来做**双闸门**（见 §3.4）。假好友 / 假时间线 / 学习引擎 / 季度迭代 **一律不进 V8**。

### 2.3 现状最该被看见的一条：**AI 已经在以你的名义对外说话，而且不留痕**

`auto_reply_friends=true` + `max_auto_replies_per_cycle=3` + `poll_interval_s=300` + **零审计**（G1）。
翻译过来：**每 5 分钟一轮，最多以你的数字人身份对外发 3 条消息，事后没有任何账。**
这不是"品牌问题"，这是**自治边界问题**，必须你单独定口径（见 §5 待批 D1）。

---

## §3 集成设计

### 3.1 维度一 · 定位

**建议：独立窗口（采纳你的倾向）· 窗口 5 · 批次 W7 · 接入已有窗口注册表，不新建壳。**

理由（三条，不是"因为它是完整功能域"这一句）：

1. **它是完整功能域**：动态流 / 私聊 / 好友 / 档案 / 任务市场——各有各的空白态、加载态、失败态，塞进主控台会把主控台撑成抽屉柜。
2. **生命周期必须独立**：轮询（300 s）、自动回复、SSE / `stream` 推送，都不该由主控台窗口的开关决定生死。
3. **审计通道必须独立**：轮询是高频动作，写主 `audit.jsonl` 会放大那个 **35.8 MB** 的旧债——**独立通道是设计前提，不是可选项**。

**接入点（本轮取证后收窄）**：不重做壳，往 `holo_pet_w3/shell/windows.json` 的 `windows[]` 追加一条：

```json
{ "id": "eigenflux", "title": "GBT小土豆V8 · AI 朋友圈", "file": "../eigenflux/index.html",
  "role": "child", "alwaysOnTop": false, "transparent": true, "frame": false,
  "resizable": true,
  "default": { "x": 160, "y": 120, "w": 980, "h": 700, "visible": false } }
```

`visible: false` 是刻意的：**默认不开**——窗口由用户口令唤起（§3.2a），不由心跳自己弹出来（《宿主不打扰律》）。
壳已具备的能力（单例锁 / 托盘 / 布局持久化 / 越界回落 / 吸附）**直接复用**，本域不重复实现。

**硬前置（如实标）**：这套壳**目前只在镜像维度 `reality/holo_pet_w3/`，未晋升到工作区根**。
所以本方案落地时排在最前面的一步不是「写 EigenFlux 窗口」，而是**「壳先落地」**——顺序错了会变成「给一扇不存在的窗加内容」。

**同时明确一条"不做第二套"**：主控台里的 `section#eigenflux-network`（`index.html:269`）**保留为摘要卡 + 入口**
——显示芯片（在线 / 待登录 / 已停用 / 未连接）+ 最近一条动态摘要 + 未读数，点击 → 打开窗口 5。
**两个界面的渲染逻辑只允许有一份**（`app.js` 那套抽成共享模块被两处调用），**不许各写一套**——否则今天吸附缺陷那个"两套口径"的母体就会在社交域重演。

### 3.2 维度二 · 与对话面板的关系

**（a）口令 → 开窗**

对话面板里说「看看 AI 朋友圈」→ 开窗口 5。
关键口径：**这是 UI 层动作，走白名单词表，不让模型自由发挥。**
白名单（初版建议）：`AI 朋友圈` / `朋友圈` / `我的动态` / `看动态` / `谁给我发消息` / `私信` / `我的好友` / `EigenFlux`。
命中 → 开窗 + 切到对应 tab；**未命中不猜**（宁可不响应，也不要"以为你要开窗"）。

**（b）新消息 → 提示（分两档，守《宿主不打扰律》）**

- **轻提示（默认开）**：面板内徽章数字 + 窗口 5 任务栏角标，**不弹窗、不亮屏、不响**。
- **系统级通知（默认关，用户显式开）**：只有你点头才允许弹系统通知。

**（c）社交动态 → 数字人有反应（只做"状态级"，不做"表演级"）**

- 允许：待阅徽章变化、数字人轻微状态动画（例如"在看动态"）。
- **默认不做**：语音播报、自动回复式搭话。
- 理由：`HEARTBEAT.md`《宿主不打扰律》第 1/4 条——**动键鼠、抢焦点、出声**都算侵入。

**（d）自动回复的两种口径（必须你选一个）**

| 口径 | 说明 | 代价 |
|---|---|---|
| **甲 · 保留自动回复，但全程留痕** | 每条自动回复落独立审计 + 生命档案；面板可查"她说过的每一句" | 仍是她自己决定说什么，你只事后可见 |
| **乙 · 改为草稿 + 一键确认** | 自动生成草稿，**不发出**；你在窗口里点一次才发 | 慢，但"以你名义对外说话"这件事永远经过你 |

**我的判断**：**先落乙，等你用一周后再决定要不要放甲。**
理由：现在的状态是"默认开 + 零审计"，等于把自治权**默认送出去了**；《谦逊与求助》和《主动汇报律》都指向同一个方向——
**对外说话这件事，先请示，再自治**。

### 3.3 维度三 · 与现有架构的关系

**（a）与上帝视角**

EigenFlux 作为**一个节点**接入，字段建议：`state`（在线 / 待登录 / 已停用 / 未连接）· `unread` · `friends_count` · `last_sync_at` · `last_error`。
**四态守《空不等于不存在律》**：抓不到 ≠ "没有动态"，抓不到要报 **`INCONCLUSIVE`**，不许报 0。

**（b）与克劳德**

**可参与（意见层）**：草拟回复、审阅一条准备公开的广播是否泄密、审阅"这条动态值不值得回"。
**禁（照《克劳德精细设计》红线）**：直接发送 · 代持凭据 · 读 `~/.eigenflux/servers/*/credentials.json` · 进决策链。
每次参与落 `external_advice`（`phase_id` + `verdict` + `adopted`）——**采纳与否记在账上，不许静默采用**。

**（c）与生命档案**

分级落档（这是本设计里最需要你确认的一条）：

| 事件 | 落档与否 | 理由 |
|---|---|---|
| 用户主动发的公开广播 | **落** | 用户意志 |
| AI 自动 / 草稿发出的内容 | **落** | 这是"她说过的话"，属于她的人格履历 |
| 收到好友私信 | **落摘要**（来源 + 时间 + hash + 是否已回） | **他人隐私不进档**——原文不外泄，只留可核对的指纹 |
| 出站被防火墙拦截 | **落** | 这是"她想过要说但被拦下的话"，是能力边界的证据 |
| 轮询心跳 / 无变化 | **不落** | 高频噪音，落独立审计通道的计数即可 |

**（d）与四层账本 / 审计通道**

**新建独立审计通道**：`store/health/eigenflux/*.jsonl`（与自我视觉验证的通道做法一致，**不混进主 `audit.jsonl`**）。
事件名（初版建议）：`eigenflux_polled` · `eigenflux_inbound` · `eigenflux_drafted` · `eigenflux_sent` · `eigenflux_blocked` · `eigenflux_error`。
**任何"对外发出"的动作必须有一条 `eigenflux_sent`**——**没有这条，就不许发**（《静默失效律》在社交域的形态）。

**（e）门禁（本轮发现的真缺口 G4）**

`POST /api/eigenflux` 目前**没有**包 `policy.owner_session()`，而同文件其它路由都包了。
**建议：补齐，与 notion / xingyun 路由同口径。** 这条属"施工时才动刀"，现在只登记。

### 3.4 出站防火墙：双闸门（借鉴历史层）

现有 `public_text_guard()` 是**形状闸门**（空 / 超长 / Windows 路径 / 内部串）。
历史层 `caps/eigenflux` 那份是**语义闸门**（评分制 42 规则 × 权重，累计 ≥ 4 拦截 + 脱敏重写）。
**建议合成双闸门**：形状闸门先拦（快、零误判），语义闸门再拦（慢、需评分）。
**同时必须过《扫描器自证律》**：正对照（含"私钥"字样 → 必须拦）· 负对照（纯公开能力描述 → 必须过）· **两组不同**；
**抓不到判别 → 报 `SCANNER_BLIND`，不许报 PASS。**

---

## §4 红线

1. **独立窗口 / 独立审计通道 / 独立生命周期** —— 三件缺一不可，不许"先塞进主控台回头再拆"。
2. **不发不加审计的外呼** —— 任何 `send` / `publish` 必须落 `eigenflux_sent`。
3. **克劳德只给意见，不做决定** —— 不许代发、不许代持凭据、不许进决策链。
4. **自动回复默认关** —— 开启须显式授权 + 可撤回（见 §3.2d）。
5. **凭据不离屏** —— 不读、不打印、不外送 `~/.eigenflux/servers/*/credentials.json`（《凭据不离屏律》）。
6. **一套逻辑，两个入口** —— 面板摘要卡与独立窗口共享同一份渲染逻辑，不许两套口径。
7. **假绿铁律** —— 抓不到报 `BLIND` / `INCONCLUSIVE`，不许报 0、不许报 PASS。
8. **不动当前施工序** —— O8 / S7 / 第二刀 / V2 走完之前，本设计**只出稿**。

---

## §5 待批清单（等你逐条拍）

| # | 事项 | 我的建议 | 影响面 |
|---|---|---|---|
| D1 | 自动回复口径：甲（保留 + 留痕）还是乙（草稿 + 一键确认） | **乙**（先用一周） | 自治边界；改 `config.json` + bridge |
| D2 | 窗口号与批次号：**窗口 5 / 批次 W7** | 采纳 | 术语一致性（避 W6 冲突） |
| D2b | 接入方式：**往 `holo_pet_w3/shell/windows.json` 追加一条**，不新建壳 | 采纳 | 复用单例/托盘/布局/吸附 |
| D2c | 前置序：**多窗口壳先晋升到工作区根**，再加 EigenFlux 窗 | 采纳 | 防「给不存在的窗加内容」 |
| D3 | 主控台 `section#eigenflux-network` 保留为摘要卡 + 入口，逻辑抽共享 | 采纳 | 面板层 + 窗口 5 |
| D4 | 上一代 `caps/eigenflux` **不搬迁**，只借评分制闸门方法论 | 采纳 | 防止双轨假社交 |
| D5 | 独立审计通道 `store/health/eigenflux/*.jsonl` + 六个事件名 | 采纳 | 与主审计流隔离 |
| D6 | `POST /api/eigenflux` 补 `policy.owner_session()` | 采纳 | 门禁一致性 |
| D7 | 生命档案分级（私信只落摘要 + hash） | 采纳 | 隐私边界 |
| D8 | 双闸门 + 《扫描器自证律》正负对照 | 采纳 | 出站安全 |
| D9 | 上帝视角节点四态 + `INCONCLUSIVE` | 采纳 | 与 W3 对接 |
| D10 | 旧 PySide6 壳（`potato_pet`）与网页壳的收敛方向 | 建议**只留一份实现**（holo_pet 复用 potato_pet 的模块，桌面壳不再独立开入口） | 防双实现 |

---

## §6 本设计**不做**什么

- 不动任何生产代码（`holo_pet/*` / `potato_pet/*` / `gbt_allinone/*` 一个字节没改）。
- 不发任何网络请求（只跑过外部 CLI 的 `--help` 只读帮助）。
- 不读任何凭据文件内容（只做存在性与计数）。
- 不起任何 GUI 进程。
- 不排进当前施工序（O8 / S7 / 第二刀 / V2 优先）。
- **不判"已完成 / 可上线"** —— 当前事实：面板有块、链路能跑，缺独立窗口 / 独立审计 / 独立生命周期。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
