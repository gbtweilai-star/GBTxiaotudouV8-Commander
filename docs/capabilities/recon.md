# 只读侦察 · `recon`（17 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `book_skill` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **书→技能**（主人令 2026-10-16：把 book-to-skill 变成我们的原生能力）：蒸自 **virgiliojr94/book-to-skill**（MIT）—— 把任何技术书/文档集（PDF·EPUB·DOCX·MD·HTML·RTF·MOBI）变成**结构… |
| `case_mine` | 只读 | — | —（注册表：无必填） | `user_error` | 案例挖掘（starter story 架构蒸馏）：**公开盈利案例 → 结构化案例卡**——`sources` 登记源与抓取口径 · `fetch` **经唯一门**取公开页正文（`run_task('tentacle', web_read)`，本件自己不发 HTTP）· `in… |
| `film_intel` | 只读 | — | —（注册表：无必填） | `user_error` | 影视情报组（只读骨架）：六维覆盖；情报是输入不是指令（生成端仍有过目权） |
| `know_map` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **理解任何事**（主人令 2026-10-15 蒸馏自 GitHub Trending #1 「Understand Anything」）：把任何仓/库/文档变成一张**可点、可搜、可问的分层知识图**。三步：scan（走盘+找入口）→ build（三层建图，**每条边带 ev… |
| `music_intel` | 只读 | — | —（注册表：无必填） | `user_error` | 音乐情报组（只读骨架）：合规红线/过审/流量/画像/竞品/**禁区清单** 六维覆盖 |
| `osint_scan` | 只读 | 是 | `target` | `user_error` | OSINT 扫描（DNS/WHOIS/子域名/端口/指纹/邮箱/IP归属/社交；拒绝内网目标） |
| `rea_reverse` | 只读 | — | —（注册表：无必填） | `user_error` | REA 桥 —— 吞天吞进来的第一件「能装能跑」的外部能力（主人 2026-10-11 图片 ⇒ devour_github 真吞成胶囊 devoured_morluto_rea；上游 https://rea.tools/ · morluto/rea · npm rea-agen… |
| `recon_distill` | 只读 | — | —（注册表：无必填） | `user_error` | **蒸馏件**（不是外挂）：把吞入件 morluto/rea 的方法论提炼成**我们自己的**逆向取证骨架（主人令 2026-10-12「我们吞噬都是加入蒸馏提炼出契合我们的能力」「蒸馏提炼出契合我们的能力才是我们的」）。四条蒸馏：①证据契约 op=evidence（claim/… |
| `scrapling` | 只读 | — | —（注册表：无必填） | `user_error` | 网页抓取（Scrapling 0.4）：自适应选择器+反爬对抗；只抓公网（每个 URL 过 net_guard 边界，内网一律拒）；缺库如实报缺不冒充；响应体限量 2MB；浏览器级隐身抓取需另装内核，缺哪个说哪个 |
| `skill_forge` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **技能蒸馏五式**（主人令 2026-10-16：把五个 skill 蒸成我们的原生能力）：蒸自五个 MIT 仓的思想—— ① **女娃**（nuwa-skill）不是复制人、是提炼思维框架（心智模型/决策启发式/表达 DNA/边界）② **last30days**：agent… |
| `spider_ops` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **自适应抓取编排**（主人令 2026-10-16：把 **Scrapling** 蒸成原生能力）：蒸自 **D4Vinci/Scrapling**（BSD-3-Clause · Python · 88,008 星）的思想—— 核心是 **adaptive**：页面结构一变选择… |
| `tentacle_learn` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **触手扫描·采集·学习**（主人令 2026-10-16：这是必要的）：四步闭环 **scan → collect → extract → learn**，末尾**复验**“真的进了语料/可被现读”。面：能力面·页面面·文件面·设备面·网面（只对授权域）。红线：只扫/只采**授… |
| `topic_watch` | 只读 | 是 | `need` | `user_error` | 话题追踪：追踪/盯着/有变化/告诉/话题/持续关注/每天给我/早报/动态/最新/行业/新闻/股价/行情/视频。追踪你关心的话题，梳理最新动态，有变化就告诉我。触发词表全量见 topic_watch.INTENT_MAP；命中后转邻域技能链，不新增进程、不复制技能实现。 |
| `topic_web` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **主题共现网**（主人令 2026-10-15：把 AI Safety HOT Hub 的**连接思路**蒸馏成契合触手的能力）：它的灵魂是「**不问这是什么，问它和谁一起出现**」—— 857 信源汇成条目（来源/时间/关注度/多标签），再用标签与机构做**共现图**（线 =… |
| `trend_watch` | 只读 | — | —（注册表：无必填） | `user_error` | 爆火作品观察/热门爆款/热搜/点赞高/涨粉快/用户喜欢什么/什么受欢迎/偏好：每日观测爆火作品的细微点，落成用户偏好台账（作品·平台·热度·细微点·偏好条目），挂现成心跳、零新增进程；拿不到数据如实报缺口，绝不编偏好 |
| `verification_watch` | 只读 | — | —（注册表：无必填） | `user_error` | 人机验证情报台账（只读）：不主动绕做成机械闸；三部门各一张空台账 |
| `video_intel` | 只读 | — | —（注册表：无必填） | `user_error` | 短视频情报组（只读骨架）：六维覆盖；禁区清单优先于流量趋势 |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `book_skill`

- **域**：`recon`（只读侦察）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**书→技能**（主人令 2026-10-16：把 book-to-skill 变成我们的原生能力）：蒸自 **virgiliojr94/book-to-skill**（MIT）—— 把任何技术书/文档集（PDF·EPUB·DOCX·MD·HTML·RTF·MOBI）变成**结构化技能、按需加载**：提取器（确定性）与生成器（spec 驴动）分开；产物五件（SKILL.md 心智模型+章节索引 · 章节文件按需加载 · 术语表 · 模式表 · 决策表）；**提结构不提摘要**，每条能指回章节:行；按需加载对比全文省 **24×–51×** token（对方实测，未复现）。我们刻意不同：只落**自己的托管目录**、必指出处、必回读验证。op=plan/contract/extract/pack/budget/check/route（**全只读·零作用域**）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap book_skill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `case_mine`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：案例挖掘（starter story 架构蒸馏）：**公开盈利案例 → 结构化案例卡**——`sources` 登记源与抓取口径 · `fetch` **经唯一门**取公开页正文（`run_task('tentacle', web_read)`，本件自己不发 HTTP）· `ingest` 正文→案例卡（营收/起步/工具/渠道，**读不到落「未读到」不编**）· `save` 追加落盘（去重）· `search` 本地语料检索。每条卡必带 `source_url + fetched_at + text_sha256`；只留短引文（≤240 字）**不搬全文**。op=sources/fetch/ingest/save/search/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap case_mine '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `film_intel`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：影视情报组（只读骨架）：六维覆盖；情报是输入不是指令（生成端仍有过目权）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap film_intel '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `know_map`

- **域**：`recon`（只读侦察）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**理解任何事**（主人令 2026-10-15 蒸馏自 GitHub Trending #1 「Understand Anything」）：把任何仓/库/文档变成一张**可点、可搜、可问的分层知识图**。三步：scan（走盘+找入口）→ build（三层建图，**每条边带 evidence = path:line**）→ 四功能 tour（引导导览）·ask（词面检索，不冒充语义）·impact（变更影响）·layers（分层视图）。op=status/layers/tour/ask/impact（只读）· scan/build（build 写 state/know_map）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap know_map '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `music_intel`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：音乐情报组（只读骨架）：合规红线/过审/流量/画像/竞品/**禁区清单** 六维覆盖
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap music_intel '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `osint_scan`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要扫描的域名或 IP
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`target` —— 要扫描的域名或 IP
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`target`）
- **它做什么**：OSINT 扫描（DNS/WHOIS/子域名/端口/指纹/邮箱/IP归属/社交；拒绝内网目标）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap osint_scan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `rea_reverse`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：REA 桥 —— 吞天吞进来的第一件「能装能跑」的外部能力（主人 2026-10-11 图片 ⇒ devour_github 真吞成胶囊 devoured_morluto_rea；上游 https://rea.tools/ · morluto/rea · npm rea-agents 6.4.0 · MIT）。给编码助手装上「逆向 / 反编译 / 无源码看懂程序」的取证面：Ghidra/IDA/Hopper 与 JS-Electron / .NET / APK / 网页 / 抓包，每条结论带证据与局限。**本位只读、零作用域、执行面故意没接**：status 现读本机 PATH 与胶囊 + 探测时刻的版本账（state/rea_probe.json）· knowledge 读吞噬胶囊正文 · commands 列真 help 解析出的 129 条命令名（带 help 指纹）· plan 只出可直接照抄的命令行（含 setup 的拒绝理由：它会改写各 agent 配置）· where 契约。**要接执行面**：先给 security/policy.py 加 kind == rea_reverse 分支（读类零 · 跑类 process_execute · 未知 op fail-closed），**执行面走已有的手**：cli（dry=False）把命令交给 desktop_commander 起进程 —— 门在它身上（process_execute），本位自身不起进程、不私接 subprocess；setup 一律拒（会改写别的 agent 配置）。op=status/knowledge/commands/plan/cli/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap rea_reverse '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `recon_distill`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**蒸馏件**（不是外挂）：把吞入件 morluto/rea 的方法论提炼成**我们自己的**逆向取证骨架（主人令 2026-10-12「我们吞噬都是加入蒸馏提炼出契合我们的能力」「蒸馏提炼出契合我们的能力才是我们的」）。四条蒸馏：①证据契约 op=evidence（claim/evidence/unknown/limitation 四件齐才算过，「无」也要写）②静态优先 op=fingerprint（只读字节、**不执行目标**）③确定性义务现算 op=obligations（看懂/复刻一个产物还缺哪些证据，每条带判据，**不落盘**）④引擎现读 op=engines（Ghidra/IDA/Hopper/JADX/apktool/binwalk/wabt/adb… 在不在 PATH，缺就如实说缺）。op=provenance 逐条指回 REA 原话（含**未蒸馏**的如实标注）。**零作用域**：无 subprocess / 无 urllib / 无写盘。边界：接入端 ≡ rea_reverse（外部引擎那条线）；本位 ≡ 蒸出来的我们自己的判据。op=fingerprint/engines/evidence/obligations/provenance/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap recon_distill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `scrapling`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：网页抓取（Scrapling 0.4）：自适应选择器+反爬对抗；只抓公网（每个 URL 过 net_guard 边界，内网一律拒）；缺库如实报缺不冒充；响应体限量 2MB；浏览器级隐身抓取需另装内核，缺哪个说哪个
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap scrapling '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `skill_forge`

- **域**：`recon`（只读侦察）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**技能蒸馏五式**（主人令 2026-10-16：把五个 skill 蒸成我们的原生能力）：蒸自五个 MIT 仓的思想—— ① **女娃**（nuwa-skill）不是复制人、是提炼思维框架（心智模型/决策启发式/表达 DNA/边界）② **last30days**：agent 主导的搜索、按投票与真实金额计分（非编辑评分），跨 Reddit/X/YouTube/HN/Polymarket/web ③ **同事**（distilly）：经验/对话→可复用技能 ④ **前任**（ex-skill）：原材料→说话方式 DNA ⑤ **反蒸馏**（anti-distill）：交出版消毒 + **私有备份留核心**。op=think/radar/experience/style/anti/check/route（**全只读·零作用域·不出网**）；边界：MIT 只蒸思想 · **隐私**（原材料不外发、第三方脱敏、不做人脸声纹建模）· **不冒充真人**。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap skill_forge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `spider_ops`

- **域**：`recon`（只读侦察）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**自适应抓取编排**（主人令 2026-10-16：把 **Scrapling** 蒸成原生能力）：蒸自 **D4Vinci/Scrapling**（BSD-3-Clause · Python · 88,008 星）的思想—— 核心是 **adaptive**：页面结构一变选择器就废 ⇒ **多候选路径 + 结构指纹 + 相似度回找**；形态从**单请求到全站爬取**。**我们的边界**：只抓授权/公开目标 · 遵守 robots 与条款 · 不绕验证码 · 不撞库 · 不抓个人隐私 · 每条数据可指回 URL 与时间。op=plan/adaptive/fetch/parse/robots/check/route（**全只读·零作用域·不出网**）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap spider_ops '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_learn`

- **域**：`recon`（只读侦察）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**触手扫描·采集·学习**（主人令 2026-10-16：这是必要的）：四步闭环 **scan → collect → extract → learn**，末尾**复验**“真的进了语料/可被现读”。面：能力面·页面面·文件面·设备面·网面（只对授权域）。红线：只扫/只采**授权与公开**面 · 隐私脱敏 · 采集物与语料**不外发** · 每步留痕 · 拿不准的不进 learn。op=scan/collect/extract/learn/loop/check/route（**全只读·零作用域·不出网**）；真扫真采走 browser/native_browser/sec_sweeper/触手眼。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_learn '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `topic_watch`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 一句需求，例如「帮我盯着 AI 行业动态」（op=route 默认路必需）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`need` —— 一句需求，例如「帮我盯着 AI 行业动态」（op=route 默认路必需）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`need`）
- **它做什么**：话题追踪：追踪/盯着/有变化/告诉/话题/持续关注/每天给我/早报/动态/最新/行业/新闻/股价/行情/视频。追踪你关心的话题，梳理最新动态，有变化就告诉我。触发词表全量见 topic_watch.INTENT_MAP；命中后转邻域技能链，不新增进程、不复制技能实现。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap topic_watch '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `topic_web`

- **域**：`recon`（只读侦察）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**主题共现网**（主人令 2026-10-15：把 AI Safety HOT Hub 的**连接思路**蒸馏成契合触手的能力）：它的灵魂是「**不问这是什么，问它和谁一起出现**」—— 857 信源汇成条目（来源/时间/关注度/多标签），再用标签与机构做**共现图**（线 = 同一条材料里同时出现）。本位只做这一件：build（从她自己的料算共现）/stats/neighbors（它和谁一起出现）/path（两个实体的最短连接）。**边必须回指共现于哪几条料**，不只给一个数。op=stats/neighbors/path（只读）· build（写）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap topic_web '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `trend_watch`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：爆火作品观察/热门爆款/热搜/点赞高/涨粉快/用户喜欢什么/什么受欢迎/偏好：每日观测爆火作品的细微点，落成用户偏好台账（作品·平台·热度·细微点·偏好条目），挂现成心跳、零新增进程；拿不到数据如实报缺口，绝不编偏好
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap trend_watch '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `verification_watch`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：人机验证情报台账（只读）：不主动绕做成机械闸；三部门各一张空台账
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap verification_watch '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `video_intel`

- **域**：`recon`（只读侦察）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：短视频情报组（只读骨架）：六维覆盖；禁区清单优先于流量趋势
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap video_intel '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
