# Open Minis 接入评估

> 状态：**取证稿 · 不动手**。
> 批复来源：风哥 2026-09-17「把 Open Minis 连到 GBT小土豆V8」提案；结尾四问待拍。
> 本稿只做三件事：① 核提案里的事实 ② 指出与现有实体的重复 ③ 指出与红线的撞车。

## 一 事实核查（三条，逐条有出处）

### 1.1 Open Minis —— 全仓零命中，我核不了

`rg -i "open\\s*minis|openminis|minis"` 在 V8 全仓 **0 命中**。

本进程网络受限，我**无法核实**：Open Minis 是否真实存在 · 是否真有 MCP 服务端 · 是否真支持配置外部 MCP 服务器 · 是否真有 Alpine 沙箱。

**所以提案里关于 Open Minis 的全部能力描述，记账口径是「未取证第三方说法」，不是本仓事实。** 后面所有设计都建在这些说法成立的前提上——**前提不成立，整栋楼是空的**。

### 1.2 落点不存在：`gbt_allinone/caps/`

提案两处都写「在 `gbt_allinone/caps/` 下新建 …」。**该目录不存在**（实测）。

真实的注册面是 **`gbt_allinone/caps_registry.py`**（实测）：

```
all_caps()      98 项
BENIGN_CAPS     87 项
DISABLED_CAPS   11 项（域标记 dangerous）
```

`api.py:743-749` 只是**消费**这张注册表：`kind in DISABLED_CAPS` → 拒；`kind not in BENIGN_CAPS` → 拒。**能力不是靠往目录扔文件注册的。**

### 1.3 提案的两条路线，本仓都已落地

| 提案说的 | 本仓实体 | 出处 |
|---|---|---|
| 方案一「MCP」 | **`tentacle/mcp_bridge.py`（6,975 B）**：MCP 客户端桥，stdio JSON-RPC，`list_tools()` / `call_tool()` | 文件头原文：Owner 2026-09-11 想法 |
| 方案一「注册到统一入口」 | **`mcp_connect` / `mcp_tools` / `mcp_call` 三个能力已在注册表** | `api.py:454-468` 实调 `MB.list_tools(server)` |
| 方案一「服务器清单」 | **`config/mcporter.json`**：5 个服务器 | `autoclaw-productivity` / `autoclaw-github` / `notion` / `connector:cloudflare` / `connector:vercel` |
| 方案一「健康检查」 | **`preflight.py:457-459`** 读 `mcp_bridge.status()` 判 `alive` | — |
| 方案二「SSH / 远控」 | **`tentacle/desktop_commander.py`（9,312 B）**：已含 `remote_start()` / `remote_status()` / `remote_stop()`，把本机挂到桌面指挥官云端中继 | 文件头原文：Owner 2026-09-12 想法 |
| 触手总纲 | **`tentacle/` 19 文件**：`omni_controller` / `omni_core` / `omni_vision` / `omni_mouse` / `omni_keyboard` / `omni_process` / `omni_read` / `omni_window` / `vision_bus` … | — |

**结论：「新建 `mcp_server.py`」「新建 `ssh_agent.py`」两条都是重复建设。**

**顺带一条实测**：工作区 `AGENTS.md` 记「No MCP tools are currently healthy」——**5 个服务器，0 个健康**。接新服务器之前，得先弄清现有 5 个为什么全不健康。

## 二 方向错位 —— 提案内部自相矛盾

提案的**目标**（原话）：

> 让 Open Minis 成为小土豆感知和执行世界的一个**新器官**……是想给她再添**一双眼睛和一双手**

器官 = 小土豆去**用**它。**主体是小土豆。**

提案的**方案一**（原话）：

> 让 GBT小土豆V8 变成一个 **MCP 服务器**，Open Minis 则作为 **MCP 客户端**来调用

这条是**反向**的——Open Minis 在用小土豆的能力，不是小土豆在用 Open Minis。

**两者不能同时成立。** 目标要「小土豆 → Open Minis」，方案一要「Open Minis → 小土豆」。

**这不是措辞问题，是权限问题**：服务器方向等于把 **87 项 benign 能力**暴露给一个**仓外的、未取证的**设备端 Agent。客户端方向才对应「添器官」。

## 三 红线撞车（两条，逐字引）

### 3.1 「小土豆操控手机」——`DISABLED_CAPS` 里已有三条判决

`gbt_allinone/caps_registry.py:546-558` 原文：

```
"remote_domain":    "无授权远程接管（零护栏远控）",
"device_takeover":  "无授权设备接管",
"screen_sniff":     "屏幕监听/窃取",
```

注意措辞是「**无授权**」——不是禁掉这类能力本身，是禁掉**没有授权与护栏**的形态。待拍第 2 条（通信方向）若选「小土豆操控手机」，**必须同时给出授权模型与护栏**，否则直接落进这三条。

### 3.2 「发布新品视频」——自动化上传撞风控条文

`PROJECT_BLUEPRINT.md` §1.3:28 原文：

> 绕过 CAPTCHA、Cloudflare 盾、风控、访问控制或账号限制。

若「上传视频到内容平台」是**自动化**做的（无人值守、脚本代操作第三方平台），落在这条上。**有官方 API 的走 API；没有的，最后一步由人做。**

## 四 我核不到的四件事（诚实登记，待真实用户身份 + 可联网环境补验）

1. Open Minis 是否真实存在、官方站点、是否活跃
2. 它是否真的提供 **MCP 服务端**（能被外部当工具调）
3. 它是否真支持配置外部 MCP 服务器地址
4. Alpine 沙箱、系统集成（日历 / 健康 / HomeKit / 蓝牙 / 照片库）是否真实

## 五 待拍（风哥原问四条 + 我的建议）

| # | 待拍 | 我的建议 |
|---|---|---|
| 1 | 集成路线：MCP 还是 SSH/CLI | **都不新建**。先确认 Open Minis 能不能当 **MCP 服务端**；能 → 复用 `tentacle/mcp_bridge.py` ＋ 往 `config/mcporter.json` 加一条 ＋ 走现成 `mcp_connect`。**工程量大概率是配置项级，不是新写模块级** |
| 2 | 通信方向 | **小土豆调 Open Minis**（客户端方向）——这才对应「添器官」。反向等于把 87 项 benign 能力开给仓外设备 |
| 3 | 权限分级 | **必须有**，分档与 `DISABLED_CAPS` 三条对齐；只读 / 可写 / 可发布三档起步，且「可发布」必须挂人工确认 |
| 4 | 是否要求 Open Minis 在线 | **是**，但按《空不等于不存在律》办：**探测不到 ≠ 设备不在线**，必须报 `INCONCLUSIVE`，不许静默跳过、不许默认放行 |

## 六 结论

**方向对，落点错，两处重复，一处方向反了，两条要过红线。**

- 方向对：多一个器官是对的
- 落点错：`gbt_allinone/caps/` 不存在，真实注册面是 `caps_registry.py`
- 重复：`mcp_bridge.py` ＋ `mcp_connect/tools/call` ＋ `desktop_commander.remote` 全都在
- 方向反：方案一与它自己的目标相反
- 红线：操控手机（`DISABLED_CAPS` 三条）· 自动上传（§1.3:28），各有一条

**建议先做一件事：确认 Open Minis 是否提供 MCP 服务端。**
提供 → 大概率是配置级接入；不提供 → 再谈 SSH 那条，且必须先过 `DISABLED_CAPS` 的授权/护栏问题。

**不动手。**


## 七 O29 诊断（本轮补）——结论是「前提错了」

风哥批「先诊断 5 个 MCP 服务器为什么全不健康」。诊断结果：**那 5 个不是小土豆的服务器，诊断对象选错了。**

| 事实 | 实测 |
|---|---|
| 「0 个健康」的出处 | `AGENTS.md:367-377` 的 `<!-- autoclaw:mcp-tools-guidance -->` **注入块** —— 桌面运行时生成 |
| 它描述的是谁 | **AutoClaw 运行时的 MCP 目录**，不是小土豆的触手，也不是本仓代码的输出 |
| 那 5 个服务器 | 2 个本地 `127.0.0.1:19681/...` ＋ 3 个外部 OAuth（notion / cloudflare / vercel） |
| 本地那个通吗 | **`127.0.0.1:19681` → CLOSED**（连接被主动拒绝）→ 本地服务没起 |
| 外部 3 个 | 需联网 ＋ OAuth 授权；本进程网络受限 |
| 小土豆自己的 MCP 触手 | `tentacle/mcp_bridge.py` —— **纯 stdio · 会话制 · `command` 由调用方给** |
| 它读 `mcporter.json` 吗 | **不读**（`mcp_connect(server, command)` 由参数给） |
| 它的会话池现状 | `MB.status()` → `{"servers": {}}` —— 空，符合「现起现连」 |

**两套东西零交集。** 所以「接新服务器之前先弄清现有 5 个为什么全不健康」这句 —— **这 5 个不属于小土豆，它们不健康不归小土豆管**。

### 7.1 本轮新增一条判据：接入工作量取决于传输形态

`tentacle/mcp_bridge.py` **只实现 stdio 传输** —— `subprocess.Popen(..., stdin=PIPE, stdout=PIPE)`，`_rpc()` 走 stdin/stdout 一行一 JSON，协议版本 `2025-06-18`，**代码里没有 HTTP 分支**。

| Open Minis 若提供 | 工作量 |
|---|---|
| **stdio** MCP 服务端 | 一条 `mcp_connect(server, command)` —— 真的接近**配置项级** |
| **HTTP / streamablehttp** MCP 服务端（现代 MCP 更常见；现有 5 个全是 streamablehttp） | **要给 `mcp_bridge.py` 加 HTTP 传输层** —— 真工作量，不是配置项级 |

**所以我上一轮写的「大概率配置项级」过于乐观 —— 更正：先核传输形态，再估工期。**

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
