---
name: gbt-autoglm
displayName: GBT · AutoGLM 家族用法规程（识图 / 生图 / 读网 / 浏览器）
version: 1.0.0
description: GBT小土豆V8 使用 AutoGLM 家族 9 条能力的用法规程。规定它们真正的凭据形态（不是环境变量，是本机 token 服务 http://127.0.0.1:18432/get_token）、两道闸（凭据闸 + 花费/出网/产图闸）、9 条技能按意图的分簇与选用、会花钱或出网或产出图片的调用必须先问主人的先后顺序与要拿的回执（image_url / oss_url / data.text / 最后一步截图）、以及与 gbt-tentacle（看屏幕点界面）、gbt-vision（视觉能力位）、browser 能力位（不在本簇）的边界，并附本机现读现状（无任何 AUTOGLM_* 环境变量、token 服务未监听、config.json 与 session_pool.json 都不存在、Pillow 12.3.0 可用）。当用户要识图、生图、改图、抠透明底、按关键词搜图、搜网页、读网页正文、用浏览器自动办事，或 autoglm 调用报取不到 token、被花费闸拦住、路由拿不准时使用。
triggers:
  - "AutoGLM"
  - "autoglm"
  - "识图"
  - "图像识别"
  - "看图"
  - "生图"
  - "文生图"
  - "图生图"
  - "改图"
  - "修图"
  - "Seedream"
  - "抠图"
  - "透明底"
  - "搜图"
  - "找图"
  - "搜网页"
  - "读网页"
  - "抓网页"
  - "浏览器自动化"
  - "上传文件"
---

# GBT · AutoGLM 家族用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是 AutoGLM 官方文档的复述）。那 9 条 `autoglm-*` 技能讲
> "这一条怎么调"，本文件讲"**在我们这儿，谁在什么条件下、按什么顺序、带什么前提去用它，
> 以及什么东西绝对不许自动发出去**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → `AGENTS.md` / `IMAGE_GENERATION.md` 管流程落点 →
> 每条 `autoglm-*` 技能自己的 `SKILL.md` 管命令细节。三层都守。

---

## 0. 它是什么 / 在哪 / 版本怎么控

| 项 | 值（2026-09-22 现读） |
|---|---|
| 是谁 | **AutoGLM 家族 9 条能力**：识图 / 生图 / 图生图 / 抠图 / 图搜 / 网搜 / 读链接 / 文件上传 / 浏览器自动化 |
| 在哪 | `C:\Users\ADMIN\.openclaw-autoclaw\skills\autoglm-*\`（**只此一处**，`root_count: 1`） |
| 通道 | **agent-skill**（按技能名加载执行）· 万能插里 `autoglm` 域是 **0 个能力位** —— 别去 `five-dim.py cap` 找它 |
| 权威名单 | `py -3.14 tools/codex-scripts/omni.py list --domain autoglm`（现读 **9 条**）与 `state/skill_atlas.json` 里 `name` 以 `autoglm-` 开头的条目**逐条对得上** |
| 后端 | 云端 `https://autoglm-api.autoglm.ai/agentdr/v1/assistant/...` ＋ 本机 token 服务 `http://127.0.0.1:18432/get_token`＋ 浏览器那一条的本地单入口 `autoglm.exe` |
| 升级 | 由 AutoClaw 技能商店分发（`_store_meta.json` 里 `source: "store"`）。**不自动升**，升之前先知道**规程结论可能跟着变** |

**版本表（现读 `_store_meta.json`）**：

| 技能 | version |
|---|---|
| `autoglm-browser-agent` | **1.1.8**（`dirName: autoglm-browser-agent-win`） |
| `autoglm-generate-image-seedream` | **1.0.2** |
| 其余 7 条 | **1.0.0** |

**落点纪律**：这 9 条**只在 managed 目录**（`~/.openclaw-autoclaw/skills`）。
🔴 **绝不要往 `~/.agents/skills/` 写**（那是别家工具的共享目录），本规程的两份也只落
「工作区源稿 + managed 安装件」两处。

---

## 1. 调用姿势（每种通道的规矩）

### 1.1 三条通道，别混着说

| 通道 | 怎么调 | 用在哪几条 |
|---|---|---|
| **A · 本地 Python 脚本** | `py -3.14 <技能目录>\<脚本>.py <参数...>` | `autoglm-image-recognition` · `autoglm-generate-image` · `autoglm-generate-image-seedream` · `autoglm-search-image` · `autoglm-websearch` · `autoglm-open-link` · `autoglm-file-upload` · `autoglm-remove-bg` |
| **B · 本地单入口命令** | `autoglm run --task "..."` | 只有 `autoglm-browser-agent` |
| **C · 纯本地库** | `py -3.14 remove-bg.py ...`（只用 Pillow，**不出网**） | `autoglm-remove-bg` |

**通用纪律**：

1. **脚本就在技能自己目录里，`cd` 进去跑或写全路径**；`upload-mix.py` 在需要它的技能目录里**各有一份**
   （`autoglm-image-recognition` / `autoglm-generate-image-seedream` / `autoglm-file-upload`），
   **不是同一份**，别跨目录混用。
2. **本地图片不能直接把路径喂给云端接口**：`image_url` / `image` 必须**公网 URL** ⇒ 一律
   **先 `upload-mix.py` 拿 `data.oss_info[0].oss_url`**，再进下一步。
3. **拿到图别只报"成功"**：生图/图搜要**把图渲染成 Markdown 图片**给主人，不是给一个裸 URL。
4. **模型自己看图 ≠ 这一簇的识图**：`autoglm-image-recognition` 是**框架**的识图入口，
   **不是我的眼睛**。两者不许互相顶替（详见 §4）。

### 1.2 `autoglm-browser-agent` 的调用姿势（**照技能原文，别自由发挥**）

```
autoglm run --task "任务描述"                            # 唯一必填参数是 --task
autoglm run --task "..." --start-url "URL"               # 新开页面
autoglm run --task "..." --tab-id "123"                  # 在同一标签页上继续
autoglm run --task "..." --session-id "xxx"              # 只在"继续上一轮对话"时给
close_browser                                            # 关浏览器 + 清会话池
```

🔴 **硬约束（技能原文，照做）**：

- **必须在后台跑**（`background: true`，`timeout: 7200`）；stdout 立刻回一个 **processing 文件路径**，
  每 **15–20 秒**读它一次，出现 `[completed]` 再读 **result 文件**。
  **不许** `yieldMs`、**不许** `tail`、**不许** `--output raw` / `2>&1` / `--json` / `--raw`。
- **一轮对话只能调一次 `autoglm run`** —— 不论成功/失败/interact，都直接把结果给主人，
  **不许再来一次**；除非主人**新一轮**明确说"继续 / 再试一次"。
- **`start_url` 与 `tab_id` / `session_id` 互斥**，**绝不许同时传**。
- **新任务不带 `session_id`**（同站新任务只带 `tab_id` 复用标签页）；
  只有「主人明说继续」「interact 恢复」「在同一页继续操作」三种情况才带 `session_id`。
- **`--task` 里绝不许出现任何本地路径**（主人给的、你生成的都不行）——
  浏览器那侧**读不到本机文件系统**：图片/媒体**先上传换 URL**，文本**自己读出来把正文嵌进描述**。
- **会话信息的唯一真相是** `%USERPROFILE%\.openclaw-autoclaw\session_pool.json`；
  **不许**去 `sessions\` 目录猜 `session_id`。
- **最后一步截图必须给主人**（技能"最硬要求 1"）：回复里要带 result 文件 `[steps]` 里**最后一步**的截图，
  **不许只回文本**，也**不许**去分析别步的截图链接。
- 出现 `[INTERACT_REQUIRED]`（要登录/要确认）⇒ **停下，把问题转给主人，等回复**；
  **不许**"一边等主人登录一边去干别的"。
- 出现 `[config_required]` ⇒ 读它给的 result 文件，**把 `[prompt:xxx]` 里的问题问主人**，
  再把人给的答案**合并**写进 `config.json`（**不许覆盖**已有字段），然后重调。
  🔴 **AI 不许自己替主人填 `auto_approve`**（见 §3.3）。

---

## 2. 两道闸（顺序不能颠倒）

### 闸一 · 凭据闸（**它不是环境变量**）

🔴 **本簇最容易被写错的一处**：9 条的 `SKILL.md` 全都写着
"token is fetched automatically from the local service … **no manual environment variable setup is required**"。
**现读核对：本机没有任何 `AUTOGLM*` 环境变量**（§6 表）。凭据从来就不是 `AUTOGLM_*`。

**真凭据链（三条，缺一条就调不动）**：

| 环节 | 是什么 | 在哪 |
|---|---|---|
| ① **本机 token 服务** | `GET http://127.0.0.1:18432/get_token` → 回 `Bearer xxx`，直接当 `Authorization` 头 | 由 AutoClaw 本机侧提供 |
| ② **签名头** | `X-Auth-Appid: 100003` · `X-Auth-TimeStamp: 当前 Unix 秒` · `X-Auth-Sign: MD5(appid + "&" + 时间戳 + "&" + 盐)` | 每次请求**动态生成**，写在技能自己的脚本里 |
| ③ **签名盐** | 一串固定 hex，**写在技能自己的 `SKILL.md` / `.py` 里** | 掩码 `38d2****` —— **本规程不转载它** |

**凭据纪律（硬）**：

1. 🔴 **不许把 token / 盐 / Authorization 头写进任何文件、任何聊天** ——
   不 echo、不落盘、不贴进规程、不贴进日报、不贴进 MEMORY。
2. 要给人看**只报**「**已配 / 未配**」，或**前 4 位掩码**（例 `38d2****`）。
3. 🔴 **不许把 token 服务返回的原文当"读数"贴出来** —— 要判"凭据链路通不通"，
   只报**端口是否在听**、**取到的串是否以 `Bearer` 开头**这种形状，**不贴值**。
4. **脚本自己会补 `Bearer` 前缀**（回值不带前缀时自动补）⇒ 看到裸串不用手改脚本。
5. **本机现状**：token 服务**现读未监听** ⇒ 依赖它的 **7 条**（除 `autoglm-remove-bg`
   与 `autoglm-browser-agent`）**现在跑不了**。正确动作是**如实报"取不到 token"**，
   **不许编读数、不许改脚本绕路**。

### 闸二 · 花费 / 出网 / 产图闸（**先问主人，见 §3**）

这一闸**比工具自己的门更靠前**：本簇 9 条**没有一条会自己弹确认**（它们不是 CLI，
没有 `--yes` / `exit 10` 那套），**全靠 §3 我们自己的条款拦**。

---

## 3. 🔴 会花钱 / 出网 / 产出图片的调用，必须先问主人（本规程的硬条款）

### 3.1 什么算"要过闸二"（9 条里只有一条不过）

| 技能 | 出网 | 花钱 | 产出/外发 | 过闸二？ |
|---|---|---|---|---|
| `autoglm-generate-image` | ✅ | ✅ 生图计费 | **产出图片** | 🔴 **必须** |
| `autoglm-generate-image-seedream` | ✅ | ✅ 生图计费 | **产出图片** | 🔴 **必须** |
| `autoglm-image-recognition` | ✅ | ✅ 消耗 token（回值里有 `tokens`） | 图/文出机器 | 🔴 **必须** |
| `autoglm-search-image` | ✅ | ✅ 检索计费 | **产出图片列表** | 🔴 **必须** |
| `autoglm-websearch` | ✅ | ✅ 检索计费 | 查询词出机器 | 🔴 **必须** |
| `autoglm-open-link` | ✅ | ✅ 计费 | 目标 URL 出机器 | 🔴 **必须** |
| `autoglm-file-upload` | ✅ | 视后端 | 🔴 **把本地文件传上云** | 🔴 **必须** |
| `autoglm-browser-agent` | ✅ | 视站点 | 🔴 会登录/发帖/下单/点赞 | 🔴 **必须** |
| `autoglm-remove-bg` | ❌（默认本地）· ✅（传 URL 时下载） | ❌ | 本地出 PNG | ⭕ 默认**不过**；传 URL 时要过 |

🔴 **两条最容易被忽略的**：

- **`autoglm-file-upload` 本身就是"数据离开本机"** —— 它把本地文件传到
  `autoglm-agent.aminer.cn`（AutoGLM 的 OSS）并回一个**公网可访问**的 `oss_url`。
  **上传 = 外发**，跟"发一条消息出去"同级，**必须过闸二**，而且要说清**哪个文件**。
- **`autoglm-remove-bg` 的 URL 模式会下载远端图** —— 默认本地 Pillow 处理不过闸；
  一旦参数给的是 `http(s)://`，它就**出网**了，要过闸二。

### 3.2 顺序（先干什么 → 拿什么回执）

1. **摊开五件事**：**哪条技能** · **目标**（`query` / `url` / **哪个本地文件**，指名道姓）·
   **是否出网** · **是否花钱**（哪一步花） · **产出什么**（图片？公网 URL？文本？）·
   **影响面**（丢出去的是不是主人的图/文件；浏览器那条会不会发帖/下单，能不能撤回）。
2. **等一次明确同意**：**只覆盖这一条 / 这一批**，不是"以后这类都同意"。
   **主人没回话 = 没同意**，停。
3. **同意后才跑**：命令按**技能原文**原样给，**不许改参数、不许加自己的"小优化"**。
4. **拿回执（必须读到业务字段，不许只说"成功了"）**：

   | 动作 | 要拿的回执 |
   |---|---|
   | 生图 / 图生图 | `data.image_url`（**渲染成 Markdown 图片**给主人）+ 本地留档路径 |
   | 识图 | `data.text`（原文格式保留）+ `data.tokens`（**这是计费量**） |
   | 图搜 | `data.results[]`（每条 `original_url` / `caption` / `source`）+ `data.count` |
   | 文件上传 | `data.oss_info[0].oss_url`（+ `oss_name`）—— **并明确告诉主人"这个文件现在在公网上"** |
   | 读链接 | `data.text` |
   | 浏览器 | **result 文件路径** + `[steps]` 里**最后一步的截图** + `session_id` / `tab_id` |

5. **失败就记失败**：原样保留 `code` / `msg` / `trace`（识别那类还会有 `data.tokens`），
   **不许把失败写成成功**，**不许**用"应该成功了"补齐。
6. **不许静默重试花钱的出网动作**：生图/图搜重试 = **再花一次钱**；浏览器重试 = **可能重复发帖**。
   重试前先确认上一次到底成没成，并**重新过闸二**。

### 3.3 浏览器那一条的**信任模式**（最容易被 AI 越权的一处）

`autoglm-browser-agent` 有个 `auto_approve` 配置（`config.json` 里）：
`true` = 敏感操作**自动执行**、技能不再逐次问；`false` = 每次回 `[INTERACT_REQUIRED]` 让你确认。

- 🔴 **AI 不许替主人把 `auto_approve` 写成 `true`**。那是"把闸关了"，
  等价于对整类不可撤回的社会动作**预先授权**。要么主人自己说"开启信任模式"，要么保持 `false`。
- 主人**已**开了信任模式时，**照技能原文**：**不许再加一层自己的确认**（不要再问"确认发布？"），
  直接调、等结果、把结果和截图给主人。
- 只有 `auto_approve: false` 时才会回 `[INTERACT_REQUIRED]` —— 那时**把问题原样转给主人，停下等**。
- **`--auto-approve` 参数只在 interact 恢复、且主人明确同意这一次敏感操作时**才传；
  **正常调用不许传**（服务自己读 `config.json`）。

---

## 4. 🔴 边界：谁管哪件事（别互相冒充）

这一节是本簇**最容易出事**的地方：识图、看图、生图、浏览器四件事**各有归属**，
名字像不等于同一件事。

### 4.1 识图 / 生图 → **本簇**

- "**给我一张图，说说里面有什么 / 把字读出来**" → `autoglm-image-recognition`（本簇）。
- "**给我生成一张图 / 按参考图改**" → 本簇（默认 `autoglm-generate-image-seedream`）。
- 工作区 `AGENTS.md` 与 `IMAGE_GENERATION.md` 已经把落点定死：
  独立生图分支的**执行层永远是 `autoglm-generate-image-seedream`**；
  本规程**不重复它的方法学**（怎么写 query、怎么迭代），**只管调它的纪律**。
- 🔴 **`AGENTS.md` 的识图先后顺序，本簇必须照办**：消息里**已有 `[图片参考描述]` 段落**时
  **直接用它，不得再调 `autoglm-image-recognition`**；**只有**该段落不存在、或明确提示
  自动识图不可用时，才调这条技能。**不许**凭我自己的视觉判断顶替它。

### 4.2 "看屏幕 / 点界面" → **`gbt-tentacle`**（不在本簇）

| 人的说法 | 走哪条 | 为什么 |
|---|---|---|
| "看一眼**屏幕**现在什么样" | `gbt-tentacle`（`{"action":"see"}`，DXGI 直读帧缓冲） | 看的是**本机显示屏**，不是一张给定的图片 |
| "帮我**点一下**这个按钮 / 在这个界面输入" | `gbt-tentacle`（`domain_index` → `domain_act` / `domain_type`，**UIA 穿透、无视遮挡**） | 操作的是**本机窗口/桌面元素** |
| "操作**这个网页**（登录/搜索/发帖/比价）" | 本簇 `autoglm-browser-agent` | 它驱动的是**浏览器里的网页语义**，不是本机桌面 |

🔴 **一句分界**：**屏幕像素和本机窗口归 `gbt-tentacle`；网页里的业务动作归本簇的
`autoglm-browser-agent`**。两边都能"看到东西"，但**看的东西不是同一个东西**，
**不许拿一条去顶替另一条**，也不许把结果互相冒充。

### 4.3 视觉能力位 → **`gbt-vision`**（不在本簇）

图鉴里的 `vision` 能力位（`kind=vision`，走 `privacy_read` 授权，
**现读可用授权 = 0 ⇒ 这一格现在是关着的**）由 `gbt-vision` 那份规程管。

⇒ 于是"看图"这件事在本机**有三条路**，`gbt-vision` 已经写了一部分，本规程把第三条补上：

| 路 | 管什么 | 规程 |
|---|---|---|
| `vision` 注册位 | 框架的视觉入口（读屏幕/摄像头/麦克风类隐私载体），**要 `privacy_read`** | `gbt-vision` |
| 触手之眼 | 看**屏幕**，只读、不要授权 | `gbt-tentacle` |
| **`autoglm-image-recognition`** | 对**一张给定的图**（本地图先上传换 URL）做云端识别 | **本规程** |

**三条路不许说成互为别名**；哪条被门挡住就说被挡住，**不许**拿能用的那条去顶替。

### 4.4 本机 `browser` **能力位** → 不在本簇

图鉴里另有一个 `browser` **能力位**（`kind=browser`，`gate: run_task`，
描述是"浏览器自动化入口（良性子集）。op=open/search/fetch/automate 走 browser_cap 三级后端"）。
**它不在本簇** —— 本簇的 `autoglm-browser-agent` 是 **agent-skill 通道**（走 `autoglm.exe`），
两者**机制不同、门不同**：

| | `browser` 能力位 | `autoglm-browser-agent`（本簇） |
|---|---|---|
| 通道 | `omnipulg` / `run_task`（万能插唯一门） | agent-skill（`autoglm run`） |
| 域 | 图鉴能力位（158 条之一） | agent 技能（不在能力位表里） |
| 归属 | **归写 `browser` 能力位那条规程**（现读工作区里**还没有** `gbt-automation`，所以本规程只在此点名边界，**不代写**） | **本规程** |

🔴 **不许互相冒充**：要跑 `browser` 能力位，就走它的规程与门；
要跑网页自动化任务，就用本簇的 `autoglm-browser-agent`。**别拿一个的读数去说另一个的事。**

**旁证（已跑，见 §6）**：`py -3.14 tools/codex-scripts/five-dim.py cap browser` 现读回
`status: error` · `message: 缺少 url` · `denied: false` —— 它**要参数**，
说明它是**能力位调用**那条路，**和本簇的 `autoglm run --task` 不是一条路**。

### 4.5 读网 → 两边都有，按"要什么"分

| 想要什么 | 走哪条 |
|---|---|
| **关键词搜网页**、要 snippet + 引用列表 | 本簇 `autoglm-websearch` |
| 给**一个 URL**，要**正文全文**做摘要/抽取 | 本簇 `autoglm-open-link` |
| 要**本机触手口径的真出网读原始 HTML**、页面改版后仍能找回元素 | `gbt-tentacle` 的读网通道（`web_read` / `web_fetch` / `web_adaptive`） |
| 要在**真浏览器里登录/点击/翻页**才拿得到的内容 | 本簇 `autoglm-browser-agent` |

**分界**：**"云端检索/取正文"归本簇；"本机触手读源码、改版不失效"归 `gbt-tentacle`**。
两边的读数格式不同（`data.text` / `data.results` vs 触手信封），**不许混着念**。

### 4.6 生图 / 传图 / 抠图 三件套的顺序（别跳步）

```
本地图（要当参考图 / 要识别）
      ↓  ▼ **过闸二：上传 = 外发，先问主人**
autoglm-file-upload（upload-mix）→ data.oss_info[0].oss_url
      ↓
autoglm-image-recognition（识别）  或  autoglm-generate-image-seedream（图生图/改图）
      ↓（生图产出 image_url 后，要透明底时）
autoglm-remove-bg（本地 Pillow 抠纯色底）→ <base>-transparent.png 本地路径
      ↓  ▼ **必做质量评估**：把透明 PNG 上传 → autoglm-image-recognition 评估
残留/主体受损 → 调参重抠（换输出名）→ 回到上传评估
```

---

## 5. 按意图分簇（**9 条，一条不漏**）

**选路总则**：先按**人的意图**落到下面某一簇，再看该簇里"什么时候用它"那一列选**一条**；
每条命令动手前读**对应技能自己的 `SKILL.md`**。**名字像不算同一件事**（见 §4）。

### 5.1 底座 / 前置（**别的簇都要用它的结果**）

| 技能 | 什么时候用它 |
|---|---|
| **`autoglm-file-upload`** | 要把**本地文件**（图片、文档）变成**公网 URL** 时 —— 它是识图 / 图生图 / 浏览器那几条的**前置**（那些接口只吃公网 URL，不吃本地路径）。脚本是 `upload-mix.py`，回 `data.oss_info[0].oss_url`。🔴 **这一步就是"数据离开本机"**，必须过闸二（§3.1）。 |

### 5.2 看图（识图域，**不产图**）

| 技能 | 什么时候用它 |
|---|---|
| **`autoglm-image-recognition`** | 要**对一张给定的图**做描述 / 物体场景识别 / 类 OCR 的文字提取时。本地图**先** `upload-mix.py` 换 URL；直接给公网 URL 就跳过上传。回 `data.text`（+ `data.tokens`）。⚠️ `AGENTS.md` 已给 `[图片参考描述]` 时**不许**再调它（§4.1）。识别可能较慢，脚本注释建议超时给 **300 秒**。 |
| **`autoglm-search-image`** | 要按**关键词去"找"图**（找图源、找素材、浏览图片结果）、**不是**要生成图时。回 `data.results[]`（`original_url` / `caption` / `source` / 宽高）+ `data.count`，逐条渲染成 Markdown。 |

### 5.3 生图 / 修图（**产出图片**，一律过闸二）

| 技能 | 什么时候用它 |
|---|---|
| **`autoglm-generate-image-seedream`** | **默认的生图/改图入口**：文生图（只给 `query`）与图生图（`query` + 参考图公网 `image`，本质是修图：改风格、换元素、局部改、扩图、上色、去水印、换装、换背景）。工作区 `IMAGE_GENERATION.md` 的独立生图分支**点名的唯一执行层**就是它。回 `data.image_url`。 |
| **`autoglm-generate-image`** | **不带 seedream 的直连文生图**入口（更早的一条，只吃 `{"text": "..."}`，没有参考图参数）。**只有**明确要用它、或 seedream 那条不可用时才选；工作区的独立生图流程不点它。回 `data.image_url`。 |
| **`autoglm-remove-bg`** | 要把 **AI 生成的 logo / 图标 / 主视觉**从**纯色/近纯色底**抠成**透明底 PNG**、好放到任意背景上时。**本地 Pillow 处理，不重新调文生图模型**（生图不产真透明图，还常带边框水印）。默认 `flood` 泛洪模式；圆角卡片底/两色卡片底用 `--edge-to-edge`；还有 `--min-area=N`、`--dominant-frac=F`（默认 0.06）、容差（默认 40）。输出 `<base>-transparent.png`。🔴 **抠完必做质量评估**（用 `autoglm-image-recognition` 走一遍"背景是否干净 + 主体是否完整"），**评估通过才算可交付素材**；参数耗尽或连续两次无变化就**如实告知残留**，别硬说干净。 |

### 5.4 读网（出网只读，一样过闸二）

| 技能 | 什么时候用它 |
|---|---|
| **`autoglm-websearch`** | 要**在线搜索 / 要最新信息 / 要实时网搜结果**时。Body 是 `{"queries": [{"query": "..."}]}`，回 `data.results[].webPages.value[]` 的 `name` / `url` / `snippet`。**答案要按 `snippet` 归纳，并在末尾附引用列表**。 |
| **`autoglm-open-link`** | 手上有**一个具体 URL**，要**它的正文全文**（用于摘要、信息抽取、深读）时。Body 是 `{"url": "..."}`，回 `data.text`。🔴 **接口报错就照原样显示错误，绝不许编内容**。 |

### 5.5 浏览器自动化

| 技能 | 什么时候用它 |
|---|---|
| **`autoglm-browser-agent`** | 主人提到**任何网站名 / URL**，或要在**网页上完成一件真事**时：开页面、搜信息、浏览社媒、点赞/评论/分享/收藏、发帖/发消息、登录、填表、抓网页内容、比价购物、读新闻、操作在线文档。它是**自主子代理**（`autoglm run --task "..."`），浏览器在内网/扩展那一侧，**读不到本机文件系统**。🔴 **它的能力边界照原文死守**：**截图/下载到本地/本地文件管理/F12 控制台/浏览器设置/长文写入网页/引用本地路径**这几类**它一定失败**，必须**先剥离或换别的工具**（§1.2、§4）。🔴 **发帖/下单/点赞这类不可撤回动作，过闸二（§3）**。 |

**选路示例**：
"这张图里是什么字" → `autoglm-image-recognition`；
"给我做一张海报" → `autoglm-generate-image-seedream`（并走 `IMAGE_GENERATION.md`）；
"把这个 logo 抠成透明底" → `autoglm-remove-bg`（+ 评估重试）；
"帮我找几张猫的图" → `autoglm-search-image`；
"搜一下今天的汇率" → `autoglm-websearch`；
"把这篇长文的正文抓下来" → `autoglm-open-link`；
"去小红书搜一下并截图给我" → `autoglm-browser-agent`；
"看一眼我屏幕现在什么样" → **`gbt-tentacle`**（不是本簇）。

---

## 6. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？**
   本簇最容易读走样的三处：
   - **凭据不是环境变量** ⇒ 看 `AUTOGLM_*` 全是"未配"**不代表"没配好"**，真凭据是本机 token 服务；
   - **`autoglm-generate-image` 与 `autoglm-generate-image-seedream` 是两条**，
     前者名字短、后者才是工作区指定入口，**别按前缀认亲**；
   - **云端识图 ≠ 触手看屏幕 ≠ `vision` 能力位**（§4），**别把一条的读数说成另一条的**。
2. **有错也照原样记，不许把失败写成成功。** 保留 `code` / `msg` / `trace`，以及**退出码**。
   浏览器那条保留 `[INTERACT_REQUIRED]` / `[config_required]` / `[step_timeout]` / `[timeout]` 标记原文 ——
   **`[INTERACT_REQUIRED]` 是"等主人"，不是失败**，两者不许混着报。
3. **不许把"脚本跑通了"当"事情办成了"**：生图要拿 `data.image_url`、
   上传要拿 `oss_url`、浏览器要拿 **result 文件 + 最后一步截图**，才算有回执（§3.2）。
4. **不许编命令、编路径、编技能名**：本文件里每条命令要么**本次实跑过**（§7 清单标 ✅），
   要么明确标 **（未验）**。**没跑过的不许说成跑过。**
5. **不许报凭据细节**：只报**已配 / 未配**或**前 4 位掩码**（`38d2****` 是掩码，**不是**任何可用凭据）。
6. **"端口不通"不许说成"技能坏了"**：token 服务没在监听 ⇒ **取不到凭据**，
   这是**环境现状**，不是技能有缺陷；也**不许**因此改脚本或伪造读数。

---

## 7. 本机踩过的坑 / 现读现状（照做，别自己解读）

### 7.1 现读现状（**2026-09-22 实测**）

| 项 | 现读 | 判定 |
|---|---|---|
| **`AUTOGLM*` 环境变量** | **一条都没有**（逐个点名：`AUTOGLM_TOKEN` / `AUTOGLM_API_KEY` / `AUTOGLM_API_TOKEN` / `AUTOGLM_BASE_URL` / `AUTOGLM_APPID` / `AUTOGLM_SIGN_SECRET` / `OPENCLAW_TOKEN` **全部未配**） | ✅ 已验 —— 凭据**不走环境变量** |
| **本机 token 服务** `127.0.0.1:18432` | 🔴 **TCP 未监听**（`目标计算机积极拒绝`） | ✅ 已验 —— **7 条依赖它的技能现在取不到 token** |
| `autoglm` 命令 | ✅ 在 PATH：`C:\Users\ADMIN\.openclaw-autoclaw\bin\autoglm.exe` | ✅ 已验 —— 浏览器那一条的入口**在** |
| `config.json` | ❌ **不存在** | ✅ 已验 —— 首调会 `[config_required]`，问题要问主人（§1.2） |
| `session_pool.json` | ❌ **不存在** | ✅ 已验 —— **没有历史会话可复用** |
| Python | `py -3.14` → **3.14.5**；`python` → `C:\Python312\python.exe` | ✅ 已验 |
| Pillow | ✅ **12.3.0** | ✅ 已验 —— `autoglm-remove-bg` 的依赖**在** |
| 技能落点 | `~/.openclaw-autoclaw/skills/autoglm-*`，**9 条** | ✅ 已验 —— **只有这一处**，`~/.agents/skills` 里没有 |

### 7.2 坑（**照做**）

1. ✅ **凭据不是 `AUTOGLM_*` 环境变量。** 9 条全部从
   `http://127.0.0.1:18432/get_token` 取 `Bearer` 串。**去找 `AUTOGLM_*` 会一无所获**，
   然后误判成"没配好"。（本次实测：环境变量全无，而 9 条技能各自的 `SKILL.md` 都写着
   "no manual environment variable setup is required"。）
2. ✅ **token 服务现在没在监听** ⇒ 8 条里除 `autoglm-remove-bg`（纯本地）与
   `autoglm-browser-agent`（走 `autoglm.exe`）之外的 **7 条**都会在**第一步取 token 时就失败**。
   报的时候说**"取不到 token + 端口没在听"**，**不许**说成"技能不存在"或编造返回。
   ⚠️ **（未验）**"服务会不会被按需拉起"本次**没验** —— 不许替它保证。
3. ✅ **`autoglm-browser-agent` 的技能目录名与技能名不一样**：
   `_store_meta.json` 里 `skillKey = autoglm-browser-agent`，而 `dirName = autoglm-browser-agent-win`，
   但**实际目录名是 `autoglm-browser-agent`**（现读）。⇒ **按技能名找目录，别信 `_store_meta` 里的 `dirName`。**
4. ✅ **`browser` 能力位要参数，不是"坏的"**：
   `five-dim.py cap browser` 现读回 `status: error` · `message: 缺少 url` · `denied: false` ——
   那是**参数校验**，**不是**"能力位不可用"，**也不是**本簇的技能。别把它读成"浏览器能力没问题"。
5. ✅ **（2026-09-22 已验，原"未验/别名桩"作废）`python3` 在本机是真解释器。**
   现读 `python3` → `...\WindowsApps\python3.exe`（**Microsoft Store 执行别名**），
   但 `python3 --version` → **`Python 3.14.5`（exit 0）**，`sys.executable` 落到
   `...\pythoncore-3.14-64\python.exe` ⇒ **别名后面真接着解释器**。
   另有 `py -3.14` → **3.14.5**、`python` → `C:\Python312\python.exe`（**3.12.10**）。
   技能原文里的示例写的是 `python` / `python3`；本规程**仍建议显式用 `py -3.14`** ——
   但理由从"免得落到别名桩"改成**"两个解释器环境不同（3.12.10 vs 3.14.5），依赖装在哪一个上不确定"**。
   ✅ **本次真跑过 `python3`**（见 §9 第 2 条的 `remove-bg` 实跑）。
6. ⚠️ **（未验）`upload-mix.py` 是同名多份。** 它在
   `autoglm-file-upload` / `autoglm-image-recognition` / `autoglm-generate-image-seedream`
   三个目录里**各有一份**（现读文件都在）。本规程按"进哪个技能的目录就用哪份"记，
   **没验过三份是否逐字节相同**。
7. ⚠️ **（未验）`autoglm-generate-image` 目录里有一个遗留 `.pyc`**
   （`generate-image.cpython-313.pyc`，现读存在）—— 说明它**曾被 cpython-3.13 跑过**。
   本机声明口径是 3.14.5。**这算不算隐患本次没判**，只是如实记下。
8. 🔴 **本簇 9 条没有一条会自己拦"花钱/出网/产图"。** 它们不是 CLI，
   没有 `--yes` / `exit 10` / `Risk: high-risk-write` 这类机制 ⇒ **闸二只存在于本规程**。
   **别拿"技能没拦我"当"可以发"。**

---

## 8. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-autoglm/SKILL.md` |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-autoglm/SKILL.md`（**与源稿逐字节相同**） |
| 被规程管的 9 条能力 | `~/.openclaw-autoclaw/skills/autoglm-*`（**不由本件代管，别改**） |
| 能力名册（现读） | `py -3.14 tools/codex-scripts/omni.py list --domain autoglm` · `<仓>/state/skill_atlas.json`（`name` 以 `autoglm-` 开头） |
| 人话入口 | `py -3.14 tools/codex-scripts/omni.py ask "识别一下这张图"` → 落到 `autoglm-image-recognition`（`agent-skill` 通道） |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster autoglm`（**需簇先在 `omni.py` 的 `DISTILLED_CLUSTERS` 里登记**） |

**纪律**：本规程**不代替**那 9 条技能，也**不代替**它们的运行环境。
token 服务取不到 / 浏览器入口不在，就**如实报"取不到"**，**不许编读数、不许改脚本绕路**。
`omni.py` 与 `security/policy.py` **不是本件该动的东西** —— 本件只加一份规程，**不动门**。

---

## 9. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 9 条技能**分簇、点名、定了两道闸与边界**；
   每条技能的深度用法**以它自己的 `SKILL.md` 为准**，本件**不替代**。
2. **本次实跑的都是只读/参数校验类命令**（§7 清单）：`omni.py list` · `omni.py ask` ·
   `five-dim.py cap browser`（缺 url 的参数校验）· `verify-distill.py --domain autoglm` ·
   环境变量点名 · 端口探测 · `_store_meta.json` 与技能目录列举 · Python/Pillow 版本。
   ✅ **2026-09-22 补：9 条里有一条真跑成功过** —— `autoglm-remove-bg`（本地 Pillow 抠透明底）：
   `py -3.14 ~/.openclaw-autoclaw/skills/autoglm-remove-bg/remove-bg.py <in.png> <out.png>`
   → **exit 0**，产物 **RGBA**、四角 `(0,0,0,0)`（**两方独立复现**：L6 深读一次、总规程复核一次）。
   🔴 **一条规程没写过的真事实**：它会**把输出裁剪到主体 bbox**，**不是**原尺寸加透明通道 ——
   探针 256×256 进，出图 **137×137**（L6 另一次是 129×129）⇒ **下游按原始尺寸对齐的步骤会错位**。
   🔴 **其余 8 条一次都没真调过**（不跑花钱/出网；其中 4 条要先取 token ⇒ 实测
   `WinError 10061` 目标计算机积极拒绝，另 3 条先查参数 ⇒ 打印 usage）。
   凡涉及真实返回形状的地方，本件均按**技能原文**记录，**未标 ✅ 的都是（未验）**。
3. **本机状态是 2026-09-22 的现读快照**（无 `AUTOGLM*` 环境变量 · token 服务未监听 ·
   `config.json` 与 `session_pool.json` 都不存在 · Pillow 12.3.0）。
   🔴 **token 服务一旦起来、或主人写了 `config.json`，本节的现状就得重新现读**，
   别把这份读数当永久事实。
4. **本件不碰 `~/.agents/skills/`**：那 9 条**只在 managed 目录**，本规程的两份也只落源稿与 managed 两处。
5. **凭据只报"已配/未配"或前 4 位掩码**：本文件出现的 `38d2****` 是**掩码**，
   **不是**任何可用凭据；`100003` 是**签名用的 appid**（技能原文公开值），也不是密钥。
