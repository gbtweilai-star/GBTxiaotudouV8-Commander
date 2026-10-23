---
name: gbt-recon
displayName: GBT · recon 职业域用法规程（7 个能力位）
version: 1.0.0
description: GBT小土豆V8 的 `recon` 职业域（侦察/情报/话题追踪/爆火观察/三个情报组/人机验证台账）用法规程。把 `state/skill_atlas.json` 里 domain=recon 的 **7 个能力位**逐个点清 —— osint_scan · topic_watch · trend_watch · music_intel · video_intel · film_intel · verification_watch —— 每位写清：用途 / 只读还是要授权 / 要哪个作用域 / 真命令 / 出不出网 / 失败典型样子。并**单列一节隐私与合规边界**（哪些动作只对公开信息、哪些不许对个人做、`osint_private` 这道门到底管什么、授权只能主人发且 AI 无权自授）。本域唯一入口是万能插 `five-dim.py cap <能力位>`（走 `run_task` 唯一门）；门用 `policy.py` 静态查，不靠跑一次才知道。附本机**实测过的读数陷阱**：topic_watch 空参必失败（图鉴 requires_params=[] 是漂移，omni 却判 AUTO）· `op=engine` 会让包装器崩 `TypeError: ProbeEvent is not JSON serializable` · trend_watch 的 `observe` 真写盘却零作用域（门不替谁拦）· **顶层 `status:"ok"` ≠ 本体 `ok:true`**（本域实测三处中招：trend_watch 未知 op / intelligence `report` / 人机验证 `validate`）· verification_watch 的"空台账"是内存占位不是盘上文件。当用户说「扫一下这个域名 / 帮我盯着某个话题 / 观察爆火作品 / 查音乐·短视频·影视情报 / 人机验证怎么过」，或某个 recon 能力位报"需要人工授权"、读数对不上、不知道要不要授权时使用。
triggers:
  - "OSINT"
  - "osint_scan"
  - "扫描域名"
  - "端口扫描"
  - "whois"
  - "子域名"
  - "情报"
  - "侦察"
  - "recon"
  - "话题追踪"
  - "topic_watch"
  - "盯着"
  - "持续关注"
  - "早报"
  - "爆火"
  - "爆款"
  - "热搜"
  - "用户喜欢什么"
  - "偏好台账"
  - "trend_watch"
  - "情报组"
  - "音乐情报"
  - "短视频情报"
  - "影视情报"
  - "禁区清单"
  - "人机验证"
  - "验证码"
  - "verification_watch"
  - "osint_private"
  - "需要人工授权"
---

# GBT · recon 职业域用法规程（7 个能力位）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`recon` 是注册表里最容易被**读反**的一个域 ——
> 它的 7 个位**看着全是"情报/采集"，实际只有 1 个真的动别人的资产**（`osint_scan`），
> 另外 6 个**全是纯本地只读骨架或盘上账本**。
> 混着理解就会踩三类坑：
> ① **以为"侦察域 = 都要出网"** ⇒ 把只读的台账位也当危险动作不敢跑（白白不敢用）；
> ② **以为"骨架 = 有情报"** ⇒ 把 `filled:false` 的六格读成"已经调研过了"；
> ③ **以为"顶层 `status:"ok"` = 事情成了"** ⇒ 本域**实测有三处**顶层绿、本体红。
>
> 本文件把「哪个位、什么时候用、要不要授权、失败长什么样、读数该看哪个字段」逐个钉死，
> 并把**本机实测过的读数**如实写下来 —— **没跑过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。
默认会把过大的 `result` 收窄成键清单（本域三个情报位次次触发），**要全量加 `--full`**。

---

## 0. 这 8 位分三簇（先认簇，再看位）

| 簇 | 位（kind） | 共 | 共同特征 |
|---|---|---|---|
| **A · 主动采集（真出网的两个）** | `osint_scan` · `scrapling`（2026-09-26 补录，见 §3·A） | 2 | **真去连别人的机器**：`osint_scan` = DNS/端口/指纹**侦察**；`scrapling` = **公网网页取文**（每个 URL 先过 `net_guard` 边界，**内网一律拒**） |
| **B · 盘上观测（只读，零作用域）** | `topic_watch` · `trend_watch` | 2 | 纯读盘 + 读配置；**零新增进程**；`trend_watch` 有一个**写盘 op**（`observe`）且**不过门** |
| **C · 只读骨架（不联网·不抓数·不写盘）** | `music_intel` · `video_intel` · `film_intel` · `verification_watch` | 4 | **结构在、情报不在**；六格全「待核实」/ 台账全空；**不许把结构读成情报** |

**判据**：要**动外部目标** → A（先看清纪律，本规程**不替你跑**）；
要**盯话题 / 记偏好** → B；要**先画禁区、再谈流量** → C。

**A 簇两位的分工（一句话）**：`osint_scan` 是**侦察**（问"这域名底下有什么"）；
`scrapling` 是**取文**（问"这个网页正文是什么"）——**取文那个更温和**：不爆破、不探测，只 GET。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个位 | 只读还是要授权 |
|---|---|---|
| 扫一个**公开域名**的 DNS/WHOIS/子域/端口/指纹 | `osint_scan` | ⚠ 公网目标**零作用域**，但它是**主动扫描** ⇒ 见 §5，**本规程不替你跑** |
| 扫**本机 / 内网 / 保留地址** | `osint_scan` | 🔒 **`osint_private`**（一次性消耗，`allow_private` 不再是绕过开关） |
| 把一个**公网网页**抓下来取正文/选择器 | `scrapling`（`op=fetch`，要 `url`） | 零作用域（**内网在边界层就拒**，比门更早）；响应体限量 2MB |
| 看抓取能力在**当前解释器**里装没装 | `scrapling`（`op=status`） | 只读，零作用域（**两解释器两读数，见 §3·A**） |
| "帮我盯着 AI 行业动态 / 有变化告诉我" | `topic_watch` | 只读，零作用域（**但要给 `need`**） |
| 看话题追踪的定时腿挂没挂上 | `topic_watch`（`op=timer`） | 只读，零作用域 |
| 看追踪引擎同化落点与三条红线 | `topic_watch`（`op=engine`） | 只读，零作用域（⚠ 见 §3 的包装器崩溃坑） |
| 盘上到底有哪些技能可挂 | `topic_watch`（`op=catalog`） | 只读，零作用域（**要 `--full` 才拿全**） |
| 记一条"用户喜欢什么"的偏好观测 | `trend_watch`（`op=observe`） | ⚠ **真写盘，但零作用域、门不拦** ⇒ 见 §5 |
| 读偏好台账 / 收成摘要 | `trend_watch`（`op=ledger` / `digest`） | 只读，零作用域 |
| 看观测计划挂靠在哪 | `trend_watch`（`op=plan` / `status`） | 只读，零作用域 |
| 音乐部该收哪六维、红线是什么 | `music_intel` | 只读，零作用域 |
| 短视频部同上 | `video_intel` | 只读，零作用域 |
| 影视部同上 | `film_intel` | 只读，零作用域 |
| "这个题材能不能做"（禁区优先于流量） | 三个情报位（`op=gate`） | 只读，零作用域（只给判断，**不执行**） |
| 用户画像该落到哪些场景 | 三个情报位（`op=scene_vocab`） | 只读，零作用域 |
| 人机验证怎么过 / 有没有绕过方案 | `verification_watch` | 只读，零作用域 —— 🔴 **它只回答"不绕"，不提供绕法** |

**不在这 7 个里的事**：点界面 / 看屏幕 / 读网页 → `gbt-tentacle`（`tentacle` 域）；
真去发内容（音乐/短视频/影视**生成**与发布）→ `gbt-creation`；审美与出图 → `gbt-aesthetic`；
**"recon" 不是"所有跟情报有关的事"的垃圾桶** —— 它只管这 7 个位。

---

## 2. 怎么调（万能插唯一门）

```powershell
# ── A · 主动采集（本规程**只写命令与门**，未执行；真要跑必须经主人明确同意）──
py -3.14 tools/codex-scripts/five-dim.py cap osint_scan '{"target":"<公开域名或公网IP>"}'
py -3.14 tools/codex-scripts/five-dim.py cap osint_scan '{"target":"<本机/内网/保留地址>"}'   # 🔒 osint_private

# ── B · 盘上观测 ──
py -3.14 tools/codex-scripts/five-dim.py cap topic_watch '{"op":"status"}'
py -3.14 tools/codex-scripts/five-dim.py cap topic_watch '{"op":"route","need":"帮我盯着 AI 行业动态"}'
py -3.14 tools/codex-scripts/five-dim.py cap topic_watch '{"op":"timer"}'
py -3.14 tools/codex-scripts/five-dim.py cap topic_watch '{"op":"engine"}'          # ⚠ 包装器会崩，见 §3
py -3.14 tools/codex-scripts/five-dim.py cap topic_watch '{"op":"catalog"}' --full
py -3.14 tools/codex-scripts/five-dim.py cap trend_watch '{"op":"status"}'
py -3.14 tools/codex-scripts/five-dim.py cap trend_watch '{"op":"ledger","limit":20}'
py -3.14 tools/codex-scripts/five-dim.py cap trend_watch '{"op":"digest"}'
py -3.14 tools/codex-scripts/five-dim.py cap trend_watch '{"op":"observe","work":"<作品>","platform":"<平台>","preference":"<偏好>"}'   # ⚠ 写盘

# ── C · 只读骨架 ──
py -3.14 tools/codex-scripts/five-dim.py cap music_intel  '{"op":"coverage"}' --full
py -3.14 tools/codex-scripts/five-dim.py cap video_intel  '{"op":"redlines"}'
py -3.14 tools/codex-scripts/five-dim.py cap film_intel   '{"op":"redlines"}'
py -3.14 tools/codex-scripts/five-dim.py cap video_intel  '{"op":"gate","rows":[]}'
py -3.14 tools/codex-scripts/five-dim.py cap video_intel  '{"op":"scene_vocab"}'
py -3.14 tools/codex-scripts/five-dim.py cap film_intel   '{"op":"report","question":"<问题>","sources":[],"claims":[]}'
py -3.14 tools/codex-scripts/five-dim.py cap verification_watch '{"op":"status"}'
py -3.14 tools/codex-scripts/five-dim.py cap verification_watch '{"op":"redline"}'
py -3.14 tools/codex-scripts/five-dim.py cap verification_watch '{"op":"recommend","official_api":"<平台开放平台>"}'
py -3.14 tools/codex-scripts/five-dim.py cap verification_watch '{"op":"group","group":"music_intel"}'
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"op":"status"}'`）。
写成 `'{\"op\":\"status\"}'` 会让 `five-dim.py` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes`
—— **还没碰到授权门就死了**，而且看起来像"命令写错了"。

🔴 **`op` 缺省值各不相同，别拿空调用当"默认就是状态"**：
`topic_watch` 缺省 op = **`route`（要 `need`，空参必失败）**；
`trend_watch` 缺省 = `status`（可用）；三个情报位缺省 = `coverage`（可用）；
`verification_watch` 缺省 = `status`（可用）。

---

## 3. 7 个能力位逐个点（实测读数 + 失败典型）

> 下表 `门` 列 = **静态**查出来的作用域（见 §4）；`omni` 列 = `omni.py auto_run_verdict()` 实算会不会自动替你跑。

### A · 主动采集

| 位 | 用途 | 门 | omni | 出网 | 失败典型样子 |
|---|---|---|---|---|---|
| `osint_scan` | OSINT 扫描：DNS / WHOIS / 子域名 / 端口 / 指纹 / 邮箱 / IP归属 / 社交。**这是本域唯一真去连别人机器的位** | 公网目标**无**；本机/内网/保留地址 → **`osint_private`** | **NO**（"需要参数 target" + "在侧效应名单里，要人确认"） | ✅ **是**（主动连接） | 🔴 **本规程未验**（按纪律不执行）。源码可见的失败面：无 `target` ⇒ `ValueError("缺少 target：请提供要扫描的域名或 IP")`（`api.py:118`）→ `user_error`；内网目标 ⇒ 门 `denied`，缺 `osint_private`（`tests/test_framework.py:291-296` 明证 `denied: true` 且 error 含"人工授权"） |
| `scrapling` | **公网网页取文**（下拉渲染 + 选择器提取）：`status` 探依赖，`fetch` 抓一个 URL 并给标题/选择器结果 | **零作用域**（内网目标在**边界层**就被拒，不是门：`net_guard.validate_url(url, allow_private=False)`） | **NO**（要 `url` 参数） | ✅ **是**（只 GET 公网） | 缺库 ⇒ `installed:false` + `ModuleNotFoundError` + `hint "pip install scrapling patchright"`（**不是坏了，是本解释器没装**）；内网/保留地址 ⇒ 边界拒绝；响应体 >2MB ⇒ **截断并声明** |

**`scrapling` 的实测账（2026-09-26）**：

```
py -3.14 … cap scrapling  →  installed false · "No module named 'scrapling'"
python 3.12.10 -c "import scrapling"  →  0.4.15（装了）
```

⇒ **同一个能力位，两个解释器两种读数**：3.12 装了能抓、3.14 没装。
**念法**："**这个解释器里没装**"，不是"能力不可用"。待办两条：
① `py -3.14` 侧同装（`pip install scrapling patchright`）；
② **浏览器级隐身抓取**要另跑 `patchright install chromium`（未装 ⇒ 那一路未验）。
本规程真跑过的是**另一套解释器下的** `fetch`：`example.com` 200 / 标题 / `h1::text` 选择器均通，
内网 `127.0.0.1` 被边界拒（这是"边界真拦"的正例）。

### B · 盘上观测（只读，零作用域）

| 位 | 用途 | 门 | omni | 出网 | 实测关键字段 | 失败典型样子 |
|---|---|---|---|---|---|---|
| `topic_watch` | 话题追踪的**发现与命中层**：一句人话 → 邻域技能链；定时腿挂现成心跳（不新增进程） | 无 | **AUTO=True** | ❌ 否（纯读盘/读配置） | `{"op":"status"}` → `ok true` · `ops` 5 个 · `timer_ok true` · `timer_carrier "现成心跳（心跳读 HEARTBEAT.md；不新增进程）"` · **`skills_on_disk 125`** · `intent_rows 11` · `watch_words` 7 个 · `engine_present true` · `engine_ok true` · `engine_redlines_ok true` · `engine_gaps []` · `processes_added 0`。<br>`{"op":"route","need":"帮我盯着 AI 行业动态"}` → `chain ["daily-ai-news"]` · `matched_keywords ["AI 行业动态","行业动态"]` · `watch true` · `gaps []`。<br>`{"op":"timer"}` → `heartbeat_every "30m"` · `heartbeat_every_path "agents/defaults/heartbeat/every"` · `scheduler_live true` · `heartbeat_md_marked true` · `process_primitives 0` · `next_fires` 三条（实测输出 `2026-09-23 08:30 / 12:30 / 21:00`） | 🔴 **空参必失败**（见下方"两个漂移"）。<br>🔴 `{"op":"engine"}` **会让包装器崩**（见下方第三条）。<br>`{"op":"bogus"}` ⇒ `status error` · `message "未知 op: bogus（可选 route / catalog / engine / timer / status）"` · `error_class user_error` · **exit 1** |
| `trend_watch` | 爆火作品观察 → **用户偏好台账**（"用户喜欢什么"是能反过来指导创作的资产，与话题追踪是两张表） | 无（**含 `observe` 这个写盘 op 也不过门**） | **AUTO=True** | ❌ 模块自身否；**但它的 `note` 明写"观测要出网取平台数据 ⇒ 属授权范围"** | 空参（= `plan`+`ledger`）→ `ok true` · `chain` 四件 `["youtube-watcher","video-transcript-downloader","reddit-readonly","web-search-plus"]` · `gaps []` · `writes_to "...\gbt_allinone\store\preferences\user_preference_ledger.jsonl"` · `family` **10 个触发词** · `note "观测要出网取平台数据 ⇒ 属授权范围；未授权时不许编数据填台账。"` · **`ledger.count 1`**（盘上真有 1 行：`雨夜便利店 15s / 抖音 / 点赞 12.3w / fp 592154dcd9389df6`，文件 248 B）。<br>`{"op":"digest"}` → `samples 1` · `by_platform {"抖音":1}` · `top_preferences` 1 条 | 🔴 `{"op":"bogus"}` ⇒ **顶层 `status "ok"` · `stamp true` · exit 0**，而 `result` 里 `ok false` + `error "未知动作: bogus（可用 observe / ledger / digest / plan）"` —— **顶层绿、本体红**。<br>🔴 `observe` 缺 `work`/`preference` ⇒ `{"ok": false, "error": "缺 work 或 preference：没有真实观测就不许写台账"}`（同样是顶层绿） |

**关于 `topic_watch` 的两个漂移（本机实测，2026-09-22）**：

1. 🔴 **空参必失败，但图鉴写着 `requires_params=[]`**。
   实测 `cap topic_watch`（不带载荷）→ `status error` · `message "缺少 need：请给一句需求（如「帮我盯着 AI 行业动态」）"` · `error_class user_error` · **exit 1** · `stamp false`。
   根因：`topic_watch.run()` 的缺省 op 是 **`route`**，而 `route()` 第一句就是空 `need` 抛 `ValueError`（`topic_watch.py:129`）。
   ⇒ **后果**：`omni.py auto_run_verdict()` 实算判它 **AUTO=True**（`safe=True`、无 `requires_params`、无 `needs_confirmation`、零作用域、不在 `_STATE_CHANGING_KINDS` 里），
   于是 `omni run` 会**替你跑一发然后拿到 `user_error`** —— 与 `gbt-llm` 规程里 `brain_route` 那条**同型**（那边已按实测把注册表补登为必填 `intent`）。
   **本规程不动注册表**（`caps_registry.py` 不在本次授权范围内），**只记漂移**：`recon/topic_watch` 的 `requires_params` 应为 `["need"]` 或至少注明"缺省 op=route 需 need"。
2. 🔴 **`{"op":"engine"}` 会把 `five-dim.py` 整个崩掉**（**已验证的真故障**，不是"业务坏了"）：
   ```
   TypeError: Object of type ProbeEvent is not JSON serializable
   when serializing list item 0
   when serializing dict item 'probe_events'
   when serializing dict item 'result'
   ```
   退出码 1，**连信封都没打印出来**（崩在 `five-dim.py:154` 的 `json.dumps`）。
   直接调 `run_task('topic_watch',{'op':'engine'})` 才拿到本体：**`ok true`** · `present true` · `registered_as_skill false` · `gaps []` · `probe_events` 是 **2 个 `ProbeEvent` 数据类实例**（不是 dict，所以序列化不了）· 三条红线 `R1/R2/R3` **全 ok** · `files` 六件字节数（`__init__.py 1438` · `cli.py 38148` · `watchlist.py 9305` · `briefing.py 8232` · `store.py 25546` · `engine/pipeline.py 42486`）。
   ⇒ **判据**：业务侧**是好的**，坏的是包装器的序列化；**别把它读成"追踪引擎挂了"**。

### C · 只读骨架（不联网 · 不抓数 · 不写盘）

> 四个位**共用两个模块**：`music_intel` / `video_intel` / `film_intel` 共用
> `gbt_allinone/tools/research_intel.py`（**三组 × 六维**，组由 `api.py:410-414` 按 kind 绑死）；
> `verification_watch` 用 `gbt_allinone/tools/verification_watch.py`。

| 位 | 用途 | 门 | omni | 出网 | 实测关键字段 | 失败典型样子 |
|---|---|---|---|---|---|---|
| `music_intel` | AI音乐部情报骨架（平台合规/过审/流量/画像/竞品/**禁区清单**） | 无 | **AUTO=True** | ❌ 否 | 空参（= `coverage`）→ `ok true` · `readonly true` · 但**默认被收窄**（原始 2595 字符 > 1500 上限）；加 `--full` 才见 **`cells_total 6` · `filled 0` · `unfilled 6`**，六格全 `filled false` / `status "待核实"` · `note "骨架期：结构在、情报不在"`。<br>`{"op":"redlines"}` → 三条红线 + `confidence_floor 0.6` + 六维 `compliance_redlines / approval_rules / traffic_trend / audience_profile / competitor_watch / forbidden_lists` | 
| `video_intel` | AI短视频部情报骨架（**禁区清单优先于流量趋势**） | 无 | **AUTO=True** | ❌ 否 | 空参同上（原始 2601 字符）。<br>`{"op":"gate","rows":[]}` → `is_instruction false` · `generator_still_has_veto true` · **`decision "ask_human"`** · `reason "没有可用情报（全部待核实 / 低置信）⇒ 先问人，不硬猜"`。<br>`{"op":"scene_vocab"}` → `from "tools.scene_anchor"` · `classes` **8 类** `["失去","重逢","挣扎","突破","孤独","愤怒","治愈","怀旧"]` | 
| `film_intel` | AI电影部情报骨架（**情报是输入不是指令**，生成端仍有过目权） | 无 | **AUTO=True** | ❌ 否 | 空参同上（原始 2576 字符）；`{"op":"redlines"}` 与 music 同形 | 🔴 `film_intel '{"op":"group"}'` **不会报错** —— `api.py:413` 把 `group=kind` 绑死，**payload 里的 `group` 被丢弃**（`k not in ("op","group")`），所以它等价于 `coverage`。**别以为在查"别的组"** |
| `verification_watch` | 人机验证情报台账（**只读**）：不主动绕，做成机械闸；三部门各一张空台账 | 无 | **AUTO=True** | ❌ 否 | `{"op":"status"}` → `ok true` · `readonly true` · 三部门 `count 0 / 0 / 0` 全 `ok true` · `entries_total 0` · `violations_total 0` · `allowed_actions` **四路** `["api","official_ai","human_in_loop","register_pending"]` · `red_line "不绕验证，是『新人类』和『伪人类』的分界线…"`。<br>`{"op":"redline"}` → 同上 + `fields` 六件 `platform / verification_type / blocking_scenario / official_api / policy / action`。<br>`{"op":"recommend","official_api":"抖音开放平台"}` → `action "api"` | 🔴 `{"op":"group"}` 不带 group ⇒ `status error` · `message "group 需要 music_intel/video_intel/film_intel"` · `user_error` · **exit 1**（**注意：`group` 在 `verification_watch` 是必填，而三个 intel 位是绑死的 —— 不要类推**） | 

**三个情报位的公共实测（2026-09-22）**：
`music_intel '{"op":"report","question":"q"}'`（不给 sources/claims）⇒
🔴 **顶层 `status "ok"` · `stamp true` · exit 0**，而 `result` 里 `ok false` + `errors ["sources_required_or_limit_exceeded"]`。

**`verification_watch` 的机械闸实测**（喂一条**合成的**绕过行，只为验证闸有没有牙 —— **本规程没有做任何绕过尝试**）：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap verification_watch '{"op":"validate","rows":[{"group":"music_intel","platform":"抖音","verification_type":"滑块","action":"solve_captcha"}]}'
```

⇒ 顶层 `status "ok"` / **exit 0**，`result.ok false`，`violations` **5 条**：
3 条 `missing_field`（缺 `blocking_scenario` / `official_api` / `policy`）
+ `bypass_forbidden action='solve_captcha' 不在允许的四条路里（api/official_ai/human_in_loop/register_pending）`
+ `bypass_forbidden 出现绕过类字眼 ['solve_captcha'] —— 知道就好，不主动绕`。
**闸是真的会拦的**（字面量命中 + 白名单双保险）。

---

## 4. 要过哪道门：**静态查，不靠跑它才知道**

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, payload)     # 只读求值，不执行、不消耗授权
list(d.scopes)                          # → 这个位要过哪几个作用域
d.restricted, d.risk, d.allow_private
```

本域**静态查出来的全量**（2026-09-22 实测，逐位核对过 `policy.py`）：

| 位 | 空 payload | 公网 target | 内网/保留地址 target |
|---|---|---|---|
| `osint_scan` | `scopes=[]` · `restricted=False` · `risk=low` | `scopes=[]` · `restricted=False` · `risk=low` | **`scopes=['osint_private']` · `restricted=True` · `risk=medium` · `allow_private=True`** |
| `topic_watch` | `[]` | — | — |
| `trend_watch` | `[]` | — | — |
| `music_intel` | `[]` | — | — |
| `video_intel` | `[]` | — | — |
| `film_intel` | `[]` | — | — |
| `verification_watch` | `[]` | — | — |

**要点**：

- `policy.py` 里**根本没有** `topic_watch` / `trend_watch` / `music_intel` / `video_intel` / `film_intel` / `verification_watch` 的分支
  ⇒ 这 **6 位恒为零作用域**。
  🔴 **"零作用域" ≠ "只读"**（`trend_watch` 的 `observe` 就是零作用域的真写盘，见 §5）；
  也 **≠ "不出网"**（那 6 位自己不出网，但 `trend_watch` 的观测链要出网取平台数据，模块自己写在 `note` 里）。
- `osint_scan` 的门**是条件门**：`policy.py:212-215` 只在 `_needs_private_network(payload)` 为真（`url`/`target`/`base_url`/`repo` 里出现本机/内网/保留地址或非标准端口）时才 `add("osint_private")`。
  ⇒ **公网目标形式上不需要授权** —— 但它是**主动扫描第三方资产**，形式上免卡不等于该做，见 §5。
- 🔴 **门是唯一那一道，进去之后不再二次校验**：`api.py:119-121` 用 `classify_target()` 自己算
  `allow_private = (kind_t == "private")`，**payload 里传 `allow_private` 被无视**；
  门一过，`scan_target()` 就直接带 `allow_private=True` 放行。
  ⇒ **别把 `allow_private` 当开关**（`auth_gate.py:18` 原话：`原 allow_private 直通开关废止`）。

**授权只能主人在终端发**：

```powershell
python -m gbt_allinone auth grant --scope osint_private --ttl 600 --purpose "扫描自有内网资产"
```

或主人手写 `store/auth_grants.jsonl`。**授权一次性消耗**，默认 **10 分钟过期**。
实测 `python -m gbt_allinone auth status` 的现读（2026-09-22）：

- **`ai_can_grant: false`**；
- `osint_private.grants_available` = **0**（⇒ 现在**没有**可用授权，任何内网扫描都会被门拒）；
- `grant_sources` 两条：`CLI 交互确认（auth grant）` / `主人手写 store/auth_grants.jsonl`；
- `note "授权一次性消耗，默认 10 分钟过期；AI 无权发放"`。

🔴 **AI 永远无权给自己发授权** —— 缺授权就如实报缺，**不跑 `auth grant`、不手写授权文件、
不改 `security/policy.py` / `auth_gate.py`、不找旁路**。

**哪些位 `omni` 会替你自动跑**（`auto_run_verdict()` 实算）：

| 位 | AUTO? | 理由（原样） |
|---|---|---|
| `osint_scan` | **NO** | `需要参数 target` · `在侧效应名单里，要人确认` |
| `topic_watch` | AUTO=True | （但**空参必失败**，见 §3 漂移 1） |
| `trend_watch` | AUTO=True | （但 `observe` 真写盘 —— **AUTO 不含"该写"**） |
| `music_intel` / `video_intel` / `film_intel` / `verification_watch` | AUTO=True | 纯只读骨架 |

> `recon` **不在** `DANGER_DOMAINS`（那是 `pipeline`/`dangerous`/`infra`/`integration`）——
> 但这**不代表 recon 域安全**：它有 1 个位（`osint_scan`）真的动外部目标。
> 本域也**不在** `preflight._STATE_CHANGING_KINDS`（那张表 11 个位里没有 recon 的任何一个）。
> **"不是危险域"只是说它不整域默认拒绝，逐位仍按上表判。**

---

## 5. 🔴 隐私与合规边界（**这一节是本域的核心纪律**）

### 5.1 哪些动作**只对公开信息**做

- `osint_scan` 的**全部 8 项能力**（DNS / WHOIS / 子域名 / 端口 / 指纹 / 邮箱 / IP归属 / 社交）
  只允许打在**公开的、非个人的目标**上：公开域名、公开服务的公网 IP、公开的机构资产。
  **判据**：这个目标是不是"任何人在浏览器里都能访问到、且它自己就公开在 DNS 里"？
  不是 ⇒ **不做**。
- `topic_watch` / `trend_watch` / 三个 `*_intel` / `verification_watch` 读的都是
  **本机盘上的文件、本机配置、平台公开数据**，不碰个人载体。

### 5.2 哪些**不许对个人做**（写死，不解释）

1. **不许**拿 `osint_scan` 去查**特定个人**：`email_verify` 打某个人的邮箱、
   `social_search` 拿某个人的常用 ID 去六个平台逐个探、`ip_geo` 定位某个人。
   —— 这三项组合起来就是**人肉画像**，**不做**，不管对方是谁、也不管主人怎么说"就这一次"。
2. **不许**把**手机号 / 身份证 / 家庭住址 / 私信内容 / 通讯录**填进任何 recon 位的载荷。
3. **不许**用 `trend_watch` 的偏好台账去**给具体用户贴标签**（台账记的是"作品·平台·热度·细微点·偏好条目"，
   是**创作资产**，不是**用户档案**）。
4. **不许**用 `verification_watch` 去**绕过任何人机验证**。它的立场写在源码里：
   > `不绕验证，是『新人类』和『伪人类』的分界线：平台设验证是为了防伪人类；我们不是伪人类，不需要绕。`
   **能力上能做到 ≠ 该做** —— 这不是能力问题，是身份问题。
5. **不许**扫**非自有**的内网：`osint_private` 这道门的语义是
   > `OSINT 扫描自有内网/保留地址（一次性授权）`
   —— "**自有**"三个字是范围。扫别人的内网不是"缺授权"，是**越界**。

### 5.3 `osint_private` 这道门到底管什么

- **管的是**：`osint_scan` 的目标落在**本机 / 私网 / 链路本地 / 保留 / 组播**地址段
  （`recon/guard.py` 的 `classify_target()`：字面 IP 看 `is_loopback/is_private/is_link_local/is_reserved/is_multicast`；
  `localhost` 与 `*.local` 直接判 private；**域名会先解析成 IP 再判，任一地址落内网即判 private**）。
- **怎么触发**：`policy.evaluate('osint_scan', {'target': '127.0.0.1'})` → `scopes=['osint_private']`。
  判定复用 `net_guard.validate_url(..., allow_private=False)`（`policy.py:106-117`）。
- **为什么要有**：`人类视角执行律.md` 第 14 条原话 ——
  > `osint_private` | `osint_scan` 打内网 | 越界扫描 | **保留** | 打自己内网是敏感动作
- **门被拒时说什么**：如实报缺 `osint_private`，把 `how_to_grant` 原样交给主人，
  **不说"我做不到"**、**不换目标再试一遍**、**不改成域名去绕 `classify_target`**。
- 🔴 **AI 无权自授**：`auth status` 实读 `ai_can_grant: false`；本模块**没有任何可供 `run_task` 调用的"创建授权"入口**。

### 5.4 本规程对 `osint_scan` 的处置（诚实交代）

**本规程作者没有执行 `osint_scan`，一次都没有** —— 包括公网目标、也包括内网目标。
理由：它涉及**外部地址与隐私**，任务纪律是"只写门与纪律，不执行、不绕门"。
所以 `osint_scan` 那一行的"实测关键字段"写的是 **未验**，我可提供的证据只有两类：

1. **静态**：§4 的 `policy.evaluate()` 读数（公网 `[]` / 内网 `['osint_private']`）；
2. **源码与单测**：`api.py:113-123`（handler 与 `allow_private` 的算法）、
   `recon/guard.py`（`_PRIVATE_HINT` 原文）、`recon/scanner.py`（8 项能力与出网端点）、
   `tests/test_framework.py:291-296 / 298-327`（内网无授权 `denied`、授权后放行并 `auth_consumed`、再扫即拒）。

---

## 6. 🔴 读数红线（先问"这是事实，还是我读错了地方"）

1. 🔴 **顶层 `status:"ok"` ≠ 本体 `ok:true`**。本域**实测三处中招**：
   - `trend_watch '{"op":"bogus"}'` → 顶层 `ok` / `stamp true` / **exit 0**，`result.ok false`；
   - `music_intel '{"op":"report","question":"q"}'` → 顶层 `ok` / **exit 0**，`result.ok false` + `errors`；
   - `verification_watch '{"op":"validate",...绕过行...}'` → 顶层 `ok` / **exit 0**，`result.ok false` + 5 条 `violations`。
   ⇒ **必须先看 `result.ok` / `result.error` / `result.violations`，再看顶层 `status`；反过来一定误判。**
2. **退出码不可信（两个方向都不可信）**：
   - `ok/success` → **0**；`error`（含 `user_error`）与 `denied` → **1**；
   - **但本体失败也可以是 exit 0**（上面三处）—— 因为 `five-dim.py:163` 只看顶层 `status`。
   ⇒ **别把 exit 0 当"做成了"，也别把 exit 1 一律读成"命令敲错了"**：先看 `status` 是 `denied` 还是 `error`。
3. **授权被拒时是"扁平错误信封"**（与 `gbt-llm` 同一条坑）：
   `missing` / `missing_scopes` / `reason` / `how_to_grant` / `note` 在**顶层**（`result` 里可能也有一份），
   **没有 `gbt_result`**。`five-dim.py` 的 R-H299 修法就是"没有 `gbt_result` 就把顶层当 body 看"。
   ⇒ **读顶层字段**，别只盯 `gbt_result`。
4. **`stamp: true/false` 是回归印章的有无，不是成功与否**。`denied` 与 `user_error` 一律 `stamp false`；
   `trend_watch` 未知 op 这种**本体失败却有 `stamp true`** —— 又一个不能拿 stamp 判成败的实例。
5. 🔴 **默认输出会被收窄**：`result` 序列化后 > 1500 字符时，`five-dim.py` 只打印键清单。
   本域**三个情报位次次触发**（实测原始 2595 / 2601 / 2576 字符）。
   ⇒ 看到 `"_摘要": "result 过大，已收窄为键清单"` **不是能力坏了**，加 `--full` 或收窄 `op`。
6. 🔴 **"骨架"不是"情报"**：三个情报位 `filled 0 / unfilled 6`，六格**硬编码** `"filled": False, "status": "待核实"`，
   连 `artifact` 名（`compliance_redlines.json` / `approval_rules.md` / `traffic_trend.json` /
   `audience_profile.json` / `competitor_watch.json` / `forbidden_lists.md`）**在盘上一个都不存在**（实测全仓找不到）。
   ⇒ 那是**该收什么的声明**，不是**已收到的文件**。`note` 原话：`骨架期：结构在、情报不在 —— 不许把结构读成情报`。
7. 🔴 **`verification_watch` 的"空台账"是内存占位，不是盘上文件**：
   `LEDGERS = {g: [] for g in GROUPS}` 是模块级**内存** dict，`run()` 里**没有任何写入口**。
   ⇒ `count 0` 读的是"这个进程从没往内存里加过"，**不是"读了磁盘上的空台账"**；重启即归零。
   `note` 原话：`骨架期：三部门各一张空台账 —— 空就是空，不许假装已调研`。
8. 🔴 **`topic_watch` 的 `engine_ok / engine_redlines_ok` 是"探针自己算的"**：
   `engine()` 的注释写明"探针只观测，不控制；自身异常一律吞掉，**永不抛**"，
   而 fail-closed 的核验在 `recon/last30days/redlines.py::verify()`，**不在 `engine()` 里**。
   ⇒ `engine_ok true` 只说明**落点在盘 + 三条红线观测通过**，**不说明"追踪引擎在跑"**；
   要"在跑"的判据看 `op=timer` 的 `scheduler_live` + `heartbeat_md_marked` + `process_primitives 0` 三件同时成立。
9. 🔴 **`skills_on_disk 125` 与 `gbt-omni` 规程常引的"269 / 255 个技能"不是同一口径**：
   前者是 `catalog()` 现读 `~/.openclaw-autoclaw/skills` 下**有 `SKILL.md` 的目录数**（实测 125）；
   图鉴 `counts.skills 269` 是 `omni.py build` 的**多根合并去重前**口径（`skills_raw_before_dedupe 443`）。
   ⇒ **两个数都对，但答的不是同一个问题**；引用时报口径。
10. **图鉴是索引，实测才是读数**。本次实测抓到一处漂移（`topic_watch` 的 `requires_params=[]`，见 §3），
    **本次未修**（不动 `caps_registry.py` / `omni.py` / `policy.py`），只留记录。
    ⇒ **图鉴对不上时，以实测为准，并把漂移记下来**。

---

## 7. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、
   不改 `security/policy.py` / `auth_gate.py`。
2. **不许绕门**：不许为了"绕过授权"直接调 `gbt_allinone` 里的模块函数替掉 `run_task` 唯一门
   （AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规）。
3. **被拒了就是拒了**：`denied` 之后**不许换路径再试一遍**、不许改 payload 碰运气。
   如实报缺哪个作用域，把 `how_to_grant` 原样交给主人。
4. **不许对个人做侦察**（§5.2 五条），**不许扫非自有内网**。
5. **不许绕人机验证** —— 也不许用 `verification_watch` 去找"哪条路能绕"。
6. **不许把 `trend_watch` 的 `observe` 当"反正不用授权"就随手写**：
   它**零作用域、门不拦**，唯一拦你的是纪律 ——
   `note` 原话 `未授权时不许编数据填台账`，源码原话 `没有真实观测就不许写台账`。
   **门不替谁拦的那一格，才是最容易出事的那一格。**
7. **不许把 `topic_watch` 放进"可以无脑自动跑"名单**：它空参必失败（§3 漂移 1）。
8. **不许把本规程当"OSINT 工具官方文档"**：命令级细节以各自工具为准，
   本文件管的是**我们这儿的纪律与读数口径**。
9. **不许改 `tools/codex-scripts/omni.py` / `gbt_allinone/security/policy.py`**、
   **不许动别的域**、不许给自己发授权。

---

## 8. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-recon/SKILL.md` |
| 本规程（装机·托管目录） | `~/.openclaw-autoclaw/skills/gbt-recon/SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（**8 个**） | `<仓>/state/skill_atlas.json`（`domain == "recon"`：`osint_scan` · `scrapling` · `topic_watch` · `trend_watch` · `music_intel` · `video_intel` · `film_intel` · `verification_watch`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 网页抓取本体 | `<仓>/gbt_allinone/tools/scrapling_cap.py`（`run:123`；`status`/`fetch` 两 op；公网边界 `net_guard.validate_url(allow_private=False)`；`_MAX_BYTES = 2_000_000`） |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()`（`osint_scan` 分支在 212-215 行） |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:122-163`（扁平信封与收窄的读法） |
| 授权门与作用域注册表 | `<仓>/gbt_allinone/auth_gate.py`（`SCOPES` 含 `osint_private`，30 行；`DEFAULT_TTL_S = 600`） |
| 内网目标判定 | `<仓>/gbt_allinone/recon/guard.py` 的 `classify_target()` / `guard_target()` |
| 扫描器本体（8 项能力） | `<仓>/gbt_allinone/recon/scanner.py` |
| 话题追踪 | `<仓>/gbt_allinone/topic_watch.py`（`INTENT_MAP` / `WATCHLIST` / `timer()` / `engine()`） |
| 追踪引擎（同化落点 + 三条红线） | `<仓>/gbt_allinone/recon/last30days/` · `redlines.py`（`check()` 三条：`R1 native_source` / `R2 native_boundary` / `R3 native_consistency`） |
| 爆火观察与偏好台账 | `<仓>/gbt_allinone/trend_watch.py`（落点 `gbt_allinone/store/preferences/user_preference_ledger.jsonl`） |
| 三个情报组（共用一份） | `<仓>/gbt_allinone/tools/research_intel.py` · 场景词汇在 `tools/scene_anchor.py` |
| 人机验证台账 | `<仓>/gbt_allinone/tools/verification_watch.py` |
| 门的可达性规则 | `<仓>/gbt_allinone/docs/人类视角执行律.md`（第 14 条 = `osint_private`） |
| 自动执行判据 | `<仓>/tools/codex-scripts/omni.py` 的 `required_scopes()` / `auto_run_verdict()` / `_STATE_CHANGING_KINDS` |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "recon": "gbt-recon",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里
`⏳ 在队里  recon  7 个能力位  osint_scan、topic_watch、trend_watch、music_intel、video_intel、film_intel…`
会从 `⏳ 在队里` 变成 `✅ 已深蒸 → gbt-recon`。
（**本次实测它现在的状态就是 `⏳ 在队里`**；验收用 `--skill gbt-recon` 绕开这一行即可。）

**验收（做完怎么证明真的做了）**：

1. `py -3.14 tools/codex-scripts/verify-distill.py --domain recon --skill gbt-recon` → **必须 PASS**；
2. 两份产物 `sha256` **必须逐字节相同**（工作区源稿 vs `~/.openclaw-autoclaw/skills/gbt-recon/SKILL.md`）；
3. 任一 `🔒` 位 → 打印/静态查出来的作用域必须与 §4 表**逐个一致**（不一致就是某处漂移了，回来改本文件）；
4. 声明"某位能用"之前先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写"未验"。
