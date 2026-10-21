# 13 · 万能插：万物皆可插 · 万物皆可控 · 反向调用云端算力

> 一句话：**万能插（`omni_plug`）不是"又一个工具集"，是把"她能碰的东西"和"她能烧的算力"统一成插座的装置。**
> 插上就有能量（本机 CPU / 云卡 GPU / 云端模型 / 任意 OpenAI 兼容端点），拔掉就落账。
> 页面里的回执都是**今天现读**的，不是设计稿。

---

## 一、它凭什么叫「万能」

它有**六类插座**，每一类对应一种"能量源"；插什么由你给，门由框架收：

| 插座 | 能插什么 | 插上之后能动什么 | 要过哪道门（作用域） |
|---|---|---|---|
| `process` | 任意可执行件 / 命令行工具 | 起进程、跑命令、拿 stdout | `process_execute` |
| `file` | 任意文件路径（含二进制） | 读 / 写 / 逐字节落盘 | 写 ⇒ `filesystem_write`；读受限面 ⇒ 视情形 |
| `api` | 任意 HTTP API | 带凭据出网调用 | `external_llm` + `data_export` |
| `web` | 任意网页 | 用她的眼+手（触手）读页/点页 | `desktop_control` + `privacy_read` |
| `app` | **任意桌面 APP** | `list_windows → see_window → click/type/hotkey` | `desktop_control` + `privacy_read` |
| `ai` | 钥匙槽（`key_env`/金库/环境）+ **任意 OpenAI 兼容端点** | 插上即"输能"：chat / tools | `external_llm` |

三条纪律（与 V9 逐字同源，写死在模块里）：

1. **不攻击**：不改目标程序、不绕它的授权校验；够不着就如实说够不着；
2. **凭据只从 env 取**，记录里只写"用了哪一份"，**绝不回显原文**；
3. **每插一次、每跑一次都落账**（谁授权、用哪份能源、花了多久）。

现读回执（`cap omni_plug '{"op":"status"}'`）：

```
名字: 万能插
插座类型: process / file / api / web / app / ai
与 V9 的分工: V9 插座无作用域门；本位把门留在 V8 的能力位边界
              （process→process_execute · file写→filesystem_write ·
                api→external_llm+data_export · web→desktop_control+privacy_read）
注: 网页/GUI 的坐标兜底走能力位 tentacle，不在本位重造一套
```

---

## 二、万物皆可控：靠的不是"插"，是"同一道门"

"可控"在这个框架里是一件**有账可查**的事，不是一句能力声明：

- **341 个能力位**（30 个域）每一个都只能从 `run_task(kind, payload)` 这一道门进；
  授权、审计、钢印都在门上，绕过去就没有留痕（无痕即不存在）。
- **触手（眼/耳/嘴/手）**：看屏幕、听声音、出声、点界面 —— 走 `tentacle` 域，
  同样过门；六条铁律见 [docs/12](12-multidomain-monitor.md) 与仓库内 `gbt-tentacle` 规程。
- **外部 CLI 编程助手**：Claude Code / CodeBuddy / Codex / Copilot 全部包成能力位
  （`cli_agent_hub` / `cli_chat`），**吃它们自己的登录态与额度**，不烧我们的 API 账单。
- **MCP / 浏览器 / 桌面**：`mcp_connect` / `mcp_call` / `browser` / `ul_tars_desktop`，
  连进程与连终端要 `process_execute`，操控浏览器/桌面要 `browser_control` / `desktop_control`。

> 所以"万物皆可控" = **万物皆有一道门 + 每一次过门都有账**。没有门的"可控"是后门。

---

## 三、反向调用云端算力（CPU / GPU）—— 这一节是重点

"反向"的意思是：**不是把我们的数据搬到云上跑一次性任务，而是把远端的 GPU 卡变成她的器官**，
在卡上跑她自己拼出来的代码，产物拿回来**逐字节对账**。

### 3.1 传输器官：`pod_link`（云卡触手）

一行说清：**本机 ⇄ GPU 卡**。13 个 op：

```
读类：status / ls / where / logs / ports / account / gpus
传类：up（推文件）· down（取回）
跑类：run（**在卡上真跑命令**）
花钱类：create / start / stop（一律必须带 confirm="主人已授权"，缺 confirm 当场 fail-closed）
```

走的是**现成的两条通道**，不新造轮子：

- **文件**：JupyterLab HTTP —— `PUT /api/contents/<path>`（base64，任何文件都行）· `GET /files/<path>` 取回；
- **命令**：JupyterLab **内核通道** —— `POST /api/kernels` 建核 + `wss://…/api/kernels/<id>/channels` 发 `execute_request`。

现读回执（今天，`cap pod_link '{"op":"status"}'`）：

```
ok: true · key_configured: true · pod_count: 15
目标卡: gbt-dh-lip（状态 EXITED 等，逐卡清单在回执 pods 里）
```

**列卡的 `gpus` 也要票**（今天实测）：`cap pod_link '{"op":"gpus"}'` → `denied`。
这不是挡你，是"看算力市场"这一步本身算外部查询 —— 缺什么票它会点名（`missing_scopes`）。

### 3.2 三层铁律（少一条就会变成"云上跑没跑成只有它自己知道"）

1. **令牌一律不回显**：只报「已配/未配」；卡上的 `JUPYTER_PASSWORD` 从 API 现读、**不打进任何返回**。
2. **传完必须回读对账**（`sha256` 两头比）—— 不许拿"完成"文案当成功。
3. **不替人做花钱决定**：`create` / `start` / `stop` 是花钱动作，必须 `confirm="主人已授权"`；
   **AI 无权自放行**。

### 3.3 把卡上的 ComfyUI 变成她的器官：`comfy_cloud`

主人令原文（2026-10-13）：**「她不需要 ComfyUI，直接使用触手就可以生产出高质量视频」**。
`comfy_cloud` 干的就是这件事：该在卡里跑的 Python 由它**现拼**，走 `pod_link.run` 递进去，
产物落卡，再走 `pod_link.down` 取回并**回读哈希对账**。

- 读：`status / nodes / models / queue / history`
- 写：`submit`（原样图）· `video`（一句话 → 首帧 → SVD 动作 → mp4）· `fetch`（卡→本机对账）· `free`
- 卡上有雷（实测）：`mm_sd_v15_v2.ckpt` ComfyUI **认不出类型**，默认走 `v1-5-pruned-emaonly-fp16.safetensors`；
  卡内脚本必须**每几秒 print 一次**，否则内核通道会把 WS 晾到超时。

**诚实账**：今天 `cap comfy_cloud '{"op":"status"}'` → `ok: false`（云卡当前不可达）。
**这不影响离线出图**：本地 27 个原生算子（`comfy_native`）与 ComfyUI 同名同契约，见 [docs/10](10-gbt-tianzhen.md)。

### 3.4 云电脑：`cloud_pc`（五原语）

`PROVISION → CONNECT → STATUS → SNAPSHOT → RELEASE`。它把"云端一台机器"变成面板里的**独立窗口**
（卡片 + 触手，**不是 iframe**）。五道闸都写死了：密钥不明文、先算账再开、留痕、只走官方入口、不改身份内核。

### 3.5 云端模型：`cloud_llm`

把当前任务数据发给外部模型服务（Agnes AI 等）再收回执。
🔴 **它按 `external_llm` 收口**：要票，且数据会离开本机；`op=materialize` 这类写动作按写类 fail-closed。

### 3.6 无限扩容：`cloud_plugin`

云源注册表：**加一行就多一个云源**（现登记 10 个：云卡触手 / 云电脑 / 云卡 ComfyUI / …）。
它不是"再写一遍集成"，是把"接一个新云"这件事收敛成一条注册表记录。

---

## 四、今天的三条现读回执（不修饰）

| 调用 | 结果 | 怎么读 |
|---|---|---|
| `cap omni_plug '{"op":"status"}'` | `ok: true` · 六类插座齐 | 插头本身是好的 |
| `cap pod_link '{"op":"status"}'` | `ok: true` · `key_configured: true` · `pod_count: 15` | 云卡通道通，能列到 15 张卡 |
| `cap pod_link '{"op":"gpus"}'` | `denied`（点名缺票） | 看算力市场要票 —— 门在生效 |
| `cap comfy_cloud '{"op":"status"}'` | `ok: false`（云卡不可达） | 云卡当前没起来；本地 27 算子照常 |

---

## 五、边界（说清楚，不含糊）

1. **不攻击**：万能插不提供"改别人的程序"这条路；够不着就如实说够不着。
2. **不藏凭据**：只报「已配/未配」，任何回执里都不会出现原文。
3. **不自我放行**：花钱动作（开卡/关机/建卡）要 `confirm="主人已授权"`，AI 给不了这个字符串以外的东西。
4. **"插上"≠"跑了"**：插上只是探测式插入（文件存在性 / target 合法性）；真执行是 `op=run`，另一道门。

---

## 六、自己复核（四条命令，不花一分钱）

```bash
# ① 插头本身（零作用域，只读）
py -3.14 tools/codex-scripts/five-dim.py cap omni_plug '{"op":"status"}'

# ② 六类插座清单 + 每类要什么能源
py -3.14 tools/codex-scripts/five-dim.py cap omni_plug '{"op":"sockets"}'

# ③ 云卡通道（只读；钥匙只报已配/未配）
py -3.14 tools/codex-scripts/five-dim.py cap pod_link '{"op":"status"}'

# ④ 云卡上的 ComfyUI（云卡不可达时如实返回 ok:false，不假装）
py -3.14 tools/codex-scripts/five-dim.py cap comfy_cloud '{"op":"status"}'
```

> 口径提醒：**信封 `status=ok` ≠ 本体 `ok=true`**；被门拒是 `denied` + `missing_scopes`，
> 和"坏了"长得完全不一样 —— 两者不许混着读。

---

返回 [能力总表](03-capabilities.md) · [README](../README.md)
