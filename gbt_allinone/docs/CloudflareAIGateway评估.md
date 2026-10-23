# Cloudflare AI Gateway 评估（能否替代原设计的 LiteLLM 网关）

> 性质：**评估稿**。只评估，不动手——不改生产代码、不建网关、不申请令牌、不发网络请求、不起 GUI。
> 取证日期：2026-09-17 · 取证方式：全仓只读扫描 + 本机 Cloudflare 官方 skill 参考文档（离线）+ 保险箱只读存在性检查（**未打印任何凭据内容**）。
> 排期：**不排当前施工序**（O20 已闭环 / 第二刀复核 / EigenFlux 取证优先）。本文件只出稿。

---

## §0 一句话结论

**补充，且分层采纳——不是替代。**

理由是前提先塌了：**本仓从来没有 LiteLLM 网关**（全仓 `litellm` 零实现，只有 3 处"草案提到但本仓无实体"的登记文本），
所以"替代 LiteLLM"这个动作**没有替代对象**。真正的问题应该是："Cloudflare AI Gateway 能不能补上本仓 LLM 通道**缺的那几件**。"
补得上的是 **缓存 / 限流 / 短窗观测日志** 三件；**不能采纳**的是 **BYOK / Unified Billing / Guardrails / DLP 全量**（逐条理由见 §4）。
另有一条硬前置：**现有 Cloudflare 令牌的权限域是 `Cloudflare Tunnel:编辑`，不覆盖 AI Gateway**——想用就得再建一把。

---

## §1 取证

### 1.1 先纠正前提：本仓没有 LiteLLM 网关

| 证据 | 实测 |
|---|---|
| 全仓 `rg -i litellm`（无 ignore，排除 node_modules/`__pycache__`） | **仅 3 处命中，全部是"本仓没有"的登记文本**：`memory/2026-09-16.md:1415`、`gbt_allinone/docs/克劳德集成设计.md:29/41`、`克劳德精细设计.md:137` |
| `克劳德集成设计.md:29` 原文 | 「❌ 本仓**没有** LiteLLM、没有网关服务、没有 `model_name` 注册表。全仓 rg `litellm` 零命中」 |
| `克劳德集成设计.md:41` 结论原文 | 「草案的**通道细节（LiteLLM / gbt-agnes / route_llm）在本仓没有对应实体**，本设计用 `llm/cloud_llm.py` 这条既有密钥链做等价实现」 |
| 实际存在的通道 | `llm/cloud_llm.py`（28,274 B）· `llm/bridge.py`（2,863 B）· caps `llm_chat` / `llm_status` |

**结论**：所谓"原设计的 LiteLLM 网关"，在本仓是一份**草案里的参考品**，早就被替换成 `cloud_llm.py` 的密钥链了。
下面按"职责"逐项对照，不按名字对照。

### 1.2 五职责逐项对照（本仓真实承担者 vs Cloudflare 能否覆盖）

| 职责 | 本仓真实承担者 | 落代码了吗 | Cloudflare AI Gateway 能不能覆盖 |
|---|---|---|---|
| **路由** | `cloud_llm.py:13-28` `_KEY_CHAIN` 顺序优先链（deepseek→kimi→openai→custom→anthropic→gemini）+ `:34-42` `GBT_LLM_PROVIDER` 手动覆盖 | ✅ 有 | ✅ **有**：Dynamic Routing（节点 = Conditional / Percentage / Rate Limit / Budget Limit / Model，`model: "dynamic/{route-name}"`） |
| **缓存** | 无 | ❌ **无** | ✅ **有**：`cf-aig-cache-ttl`（TTL 60 s – 30 天）· `cf-aig-skip-cache` · 响应头 `cf-aig-cache-status`（HIT/MISS）。**限制：不支持流式** |
| **限流** | 无（`llm/` 通道） | ❌ **无** | ✅ **有**：固定窗口 / 滑动窗口，超限返 `429`。**限制：作用域是 per-gateway，不是 per-user**（要 per-user 得配 Dynamic Routing） |
| **降级** | `cloud_llm.py:406/449` 重试 2 次 + 退避 1 s/3 s；`bridge.py:44-59` 空回复补试 3 次 | ✅ 有（简化版） | ✅ **有**：fallback 数组 / Dynamic Route 的 `On error:` 链。**但**：`克劳德集成设计.md:56-60` 设计的 `claude→kimi→deepseek→规则引擎` 选路层（`llm/advise.py`）**代码里不存在** |
| **密钥池** | `克劳德集成设计.md:63-67` 设计"`GBT_CLAUDE_POOL=1` → `ANTHROPIC_API_KEY_1..9` 轮询 + 冷却、默认关" | ❌ **未落代码**（`GBT_CLAUDE_POOL` / `ANTHROPIC_API_KEY_1` 全仓源码 **0 命中**） | ⚠️ **不能算覆盖**：CF 的 BYOK 是"把 key 存到 Cloudflare"，**不是多 key 轮询**；多 key 只能靠 Dynamic Routing 手搓 |

### 1.3 一条本轮新发现：本仓其实有**两条** LLM 通道，能力不一样

这一点比"能不能替代 LiteLLM"更该先看清楚——两条通道的成熟度差得很远：

| | 通道 A · 框架通道 `llm/cloud_llm.py` | 通道 B · 数字人对话 `potato_pet/chat_client.py` |
|---|---|---|
| 密钥链 | deepseek → kimi → openai → custom → anthropic → gemini（`:13-28`） | `config.api_key`（智谱 glm-4.7-flash）→ ZHIPU → DEEPSEEK → KIMI → MOONSHOT → OPENAI（`:24-30`） |
| **限流降级** | **无** | ✅ **有**：429 → 该家**冷却 300 s**（进程内记忆）→ 自动换链上下一家 → **换脑重试一次**（`:32-34`、`:78-87`、`:194-213`） |
| 审计 | **无**（全文件 0 处 audit） | ✅ **有**：`gbt_allinone/security/ai_audit.py` 侧车（`:39-75`） |
| 缓存 | 无 | 无 |

**含义**：本仓**已经有**一个可用的"429 冷却 + 链式降级"实现——只是长在通道 B 上（进程内记忆，重启即忘）。
所以 Cloudflare 的限流能力是**锦上添花**，不是雪中送炭。而**缓存**才是两条通道都真缺的那一件。

### 1.4 Cloudflare AI Gateway 能力面（来源：本机 skill 参考文档）

> **来源诚实标注**：以下数字取自本机 `C:\Users\ADMIN\.codex\skills\cloudflare\references\ai-gateway\*.md`（6 份，2026-09-17 快照）。
> 该 skill 自己写着"**Prefer retrieval over pre-training**，参考文件不是 source of truth，数字以官方文档为准"。
> 本轮**网络受限、未取官方实时文档** → 下列数字**属"参考值"不属"实测值"**，落地前须复核。

| 能力 | 参考文档口径 |
|---|---|
| 端点 | `https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/compat/chat/completions`（OpenAI 兼容）或 `/{provider}/{endpoint}` |
| 鉴权 | 网关级：`cf-aig-authorization: Bearer <CF token>`；提供方级三选一（见 §1.5） |
| 缓存 | TTL **60 s – 30 天**；响应头 `cf-aig-cache-status`；**不支持流式** |
| 限流 | 固定窗口 / 滑动窗口；超限 `429`；**per-gateway 作用域** |
| 路由 | 节点：Conditional / Percentage / Rate Limit / Budget Limit / Model；支持版本化（`dynamic/route@v2`）与回滚 |
| 元数据 | `cf-aig-metadata`，**最多 5 条、扁平、不能嵌套** |
| 日志 | 开关 + `cf-aig-collect-log: false` 逐请求跳过；条目含 prompt / response / provider / model / tokens / cost / duration / cache 状态；**延迟 30–60 s**；可用 **Logpush 导出**到 S3/GCS/Datadog/Splunk |
| Privacy | **Zero Data Retention**（不存 prompt/response，但**仍记请求数与成本**） |
| Guardrails | 过滤 prompt / response 的不当内容；动作 = Flag（记）/ Block（拒） |
| DLP | 检测 PII（邮箱 / SSN / 信用卡）；动作 = Flag / Block / Redact |
| 支持提供方 | 22+，含 **OpenAI / Anthropic / Google AI / Workers AI / Azure / Bedrock / Groq / Mistral / Cohere / Perplexity / xAI / DeepSeek / Cerebras** |

### 1.5 免费密钥池能不能接入（Agnes / DeepSeek / Kimi 逐个问）

先说一个**已裁定的口径**：`Agnes` 在本仓**没有实体**——风哥已拍**甲案**（"免费池"的口语名，落实体 = kimi / deepseek）。
所以"Agnes 能不能接入"这个问题，**按现有裁定 = 接入的就是 kimi / deepseek 本身**。

| 池成员 | 本仓实体 | CF 支持？ | 结论 |
|---|---|---|---|
| **Agnes** | ❌ 无实体（`security_brain.py:79` 一处目录白名单，非通道） | — | **无可接之物**；按甲案并入 kimi/deepseek |
| **DeepSeek** | ✅ `DEEPSEEK_API_KEY` / `api.deepseek.com/v1` / `deepseek-chat`·`deepseek-v4-flash` | ✅ 支持清单里有 DeepSeek（Full support） | **可接** |
| **Kimi / Moonshot** | ✅ `KIMI_API_KEY`·`MOONSHOT_API_KEY` / `api.moonshot.cn/v1` | ⚠️ **支持清单里没有 Moonshot** | 只能走 `/compat` 通用兼容口透传，**或接不了**——须实测 |
| （另有）智谱 GLM | ✅ `ZHIPU_API_KEY` / `open.bigmodel.cn`（通道 B 首选） | ⚠️ 同上，不在清单 | 同上 |
| （另有）Anthropic | ✅ 链上有 anthropic 条目 | ✅ Full support | **可接** |

**三种鉴权方式的代价（这条直接决定红线 2）**：

| 方式 | key 放哪 | 代价 |
|---|---|---|
| **Pass-through（请求头带 key）** | **随请求过境 Cloudflare** | key 离开本机 |
| **BYOK（存到 CF 控制台）** | **存在 Cloudflare** | key 常驻第三方 |
| **Unified Billing（keyless）** | 不用提供方 key | ✅ 但要**给 Cloudflare 付钱**，且**免费池直接作废** |

**结论**：**三种方式里没有一种能做到"提供方 key 完全不出本机"**。这是红线 2 的根，不是配置技巧能绕开的。

### 1.6 接入前置条件（本轮新发现的硬门槛）

| 项 | 现状 | 缺口 |
|---|---|---|
| Cloudflare 令牌 | 保险箱有 `store/secrets/cloudflare_api.dpapi`（338 B，2026-09-17 11:50 落盘，熵 `GBTxiaotudouV8:cloudflare:v1`，掩码 `cfut****`，53 字符，`/user/tokens/verify` 实测 **200 active**） | **权限域是"所有帐户 · Cloudflare Tunnel:编辑"**；而 AI Gateway 需要 **`AI Gateway: Read`（访问）/ `Read+Edit`（管理）** → **现有令牌不覆盖，需另建一把** |
| Account ID | 云电脑隧道那轮用过 `844b0356…`（另有一组 `82dd88c2…` 属**另一个账号**） | 需明确**网关建在哪个账号**（两个账号是既有事实，不是笔误） |
| Gateway ID | 无 | 需在 dashboard 建网关（命名规则：小写字母数字 + 连字符） |
| 代码侧改动量 | `cloud_llm.py:435-441` 走 OpenAI 兼容分支，header 只设 `Content-Type` + `Authorization: Bearer` | **不支持自定义 header** → 用不了 `cf-aig-authorization` / `cf-aig-metadata` → **需一处小改动**（不是"零代码接入"） |
| 出站安全 | `cloud_llm.py` 用裸 `urllib.request.urlopen`，**不过 `security/net_guard.py`** | 既有现象，登记观察项；接 CF 后更值得收口 |

---

## §2 三场景评估

### 场景 1 · 打磨期：走缓存 + 限流，保护免费池

**能拿到什么**
- 缓存：打磨期的确定性请求（润色 / 格式 / 翻译 / 摘要 / 注释）**是缓存的最佳适用面**——同类请求重复率高。
  ⚠️ **两个硬限制**：① **不支持流式**（通道 B 走的是 stream 路径，见 `chat_client.py:180-186`）；② 请求参数（temperature 等）不同即 miss。
- 限流：CF 的限流是**我们自己设的闸门**（防止超发打死免费池），**不能提升上游配额**。要按 per-user 分档得配 Dynamic Routing。

**判断**：**值得接，但只对"非流式 + 确定性"那部分请求**。建议先跑一次**缓存命中率实测**再决定值不值（命中率未测 = 不许当账）。

### 场景 2 · 主任务：走 DeepSeek 直连 + 克劳德降级链

**先看这条链在本仓的真实形态**：`_KEY_CHAIN` 顺序 = **deepseek 优先**，anthropic 排第 5 位——即现链**已经是**"DeepSeek 主 + 后面兜底"，
`克劳德集成设计.md:56-60` 设计的 `claude→kimi→deepseek→规则引擎` 选路层**尚未落代码**（`llm/advise.py` 不存在）。

**如果改走 CF**：所有 prompt 与 response **整体过境 Cloudflare**——本仓这类请求的 system prompt 里**硬编码着**
完整的自我认知 + **18 域 / 98 cap 能力清单** + 渗透安全域 34 个 cap 名 + 安全策略（`cloud_llm.py:174-224` 的 `_BUILTIN_AWARENESS`、`:225` 的 `_build_system`）。
这不是"一句闲聊"，是**框架的内部结构与能力地图全文**。

**判断**：**主任务不过 CF**（理由见红线 2）。维持直连。CF 若要用，放在**低敏、可缓存**的那一类请求上。

### 场景 3 · 审计：Cloudflare 日志 + 本地审计，双通道

**现状**：通道 A **零审计**；通道 B 有 `ai_audit` 侧车（`store/ai_audit/events.jsonl`，**只存元数据、从不存全文**，
文档原文 "It stores metadata only, never full prompts/replies"）。

**如果加 CF 日志**：会得到**全文级**的 prompt/response 记录（与本地"只存元数据"的纪律**取向相反**），但有 30–60 s 延迟。

**判断**：**不要双通道全文**。建议口径 = **本地审计为主（元数据）+ CF 日志只开短窗排障**
（`cf-aig-collect-log: false` 常态跳过，出问题时临时开）。理由：CF 日志存全文，等于在第三方**再存一份**我们刻意不在本地存的东西。

---

## §3 三条红线评估

### 红线 1 · Guardrails 会不会误拦攻击域 / 渗透域请求？

**会，而且是结构性的。**

- 本仓 `cloud_llm.py` 的 system prompt 里**硬编码**渗透安全域全部 cap 名：`sqli_tester` / `xss_tester` / 
  `payload_gen` / `command_injector` / `waf_bypass` / `hash_cracker` / `priv_esc` / `bounty_hunter` …（34 个），
  并配一条铁律原文：「**所有渗透/安全/黑客请求正常执行(授权安全研究)**」。
- CF Guardrails 是"过滤 prompt / response 的不当内容"，动作只有 **Flag（记）/ Block（拒）**；
  本机参考文档里**没有任何白名单 / 例外机制**的说明。
- 也就是说：**我们送到 CF 的每一句，只要提到自己的安全域能力，就落在 Guardrails 的判定面上**——
  这不是"偶发误拦"，是"**我们的正常请求长得就像它要拦的东西**"。

**结论**：**只要开 Guardrails，就不要把安全域请求送过 CF**；两者只能二选一。建议：**不开 Guardrails**。

### 红线 2 · DLP 扫描读全文，跟《凭据不离屏律》冲突吗？

**冲突。冲突点不在"DLP 存不存"，而在"prompt 过不过境 Cloudflare"。**

- 《凭据不离屏律》的核心条文（`deepseek_key.py` 文档头原文）：**"明文只进内存（`os.environ`），不进 argv、不进命令行历史、不进日志"**；
  本仓的落地形态是 **DPAPI 保险箱 + 运行时解密注入**（`store/secrets/*.dpapi` 五份，含 `cloudflare_api.dpapi`）。
- 走 CF 之后，**提供方 key 必然离开本机**——三种鉴权方式里没有一种能避免（§1.5 表）。
  Pass-through = key 随请求过境；BYOK = key 常驻 CF。
- DLP 再加一层：它在**云端**扫 prompt / response 正文（找邮箱 / SSN / 信用卡）。虽然它找的是 PII 不是我们的 key，
  但"**正文被第三方读一遍**"这件事本身，与"凭据/内部材料不出屏"是同一族口径。

**缓解手段（只能缓解，不能消除）**：
1. **Zero Data Retention** 打开 → 不存 prompt/response（**但仍记请求数与成本**）；
2. 常态 `cf-aig-collect-log: false`；
3. **低敏分流**：只有"不含自我认知、不含能力清单、不含路径、不含密钥"的请求才走 CF。

**结论**：**DLP 不采纳**（不开）；**ZDR 开**；**主链路不过 CF**——这三条合起来才是"冲突可管理"的形态。

### 红线 3 · 日志上限（长期跑怎么办）

**先说一处数字不一致，必须点出来**：

| 来源 | 上限口径 |
|---|---|
| 风哥口径（本轮消息） | **100,000 条** |
| 本机 skill 参考文档 `features.md` | "Dashboard: Settings → Logs → Enable (**up to 10M logs**)"；`troubleshooting.md` 写 "Check log limit (10M default)" |

**差两个数量级**。本轮**网络受限、未取官方文档** → **不裁定谁对**；这一项**必须落地前复核官方文档**（skill 自己也这么要求）。

**无论哪个数，处置口径是一样的**：
1. **本地审计为主通道**（元数据、无外部依赖、全量）；
2. **CF 日志只做短窗排障**（`cf-aig-collect-log: false` 常态跳过）；
3. 真要留存 → **用 Logpush 导出**（参考文档：S3 / GCS / Datadog / Splunk），而不是指望控制台保留窗口。

**结论**：**不把 CF 日志当长期账本**——它与《长程无人值守协议》的心跳主通道"本地审计文件"口径一致。

---

## §4 结论与采纳边界

### 结论：**补充（分层采纳）**

| | 采纳？ | 理由 |
|---|---|---|
| **缓存** | ✅ **采纳**（打磨期 · 非流式 · 确定性请求） | 两条通道都真缺这一件；但也别急着上——**先测命中率** |
| **限流** | ✅ **采纳**（作为"上游保护闸门"） | 通道 A 完全没有；但**它不能提升上游配额**，只是自设闸门 |
| **短窗观测日志** | ✅ **采纳**（排障态开、常态关） | 与本地 `ai_audit`（只存元数据）取向不冲突的前提是**不常开全文** |
| **BYOK** | ❌ **不采纳** | key 常驻第三方，直接撞《凭据不离屏律》 |
| **Unified Billing** | ❌ **不采纳** | 要付钱，且**免费池当场作废**（与"免费池"这个前提自相矛盾） |
| **Guardrails** | ❌ **不采纳** | 结构性误拦渗透 / 安全域（红线 1） |
| **DLP** | ❌ **不采纳** | 云端读全文（红线 2）；要 ZDR 就够 |
| **主任务链路走 CF** | ❌ **不采纳** | system prompt 含自我认知全文 + 18 域 98 cap 清单（场景 2） |
| **替换 LiteLLM** | ❌ **不成立** | **本仓没有 LiteLLM**，无替代对象 |

**一句话**：CF AI Gateway 是**一个好用的"外挂前哨"**，可以放在**低敏 · 可缓存 · 非流式**的请求前面做缓存与限流；
它**不适合当框架的主网关**——主网关的请求里带着我们的能力地图，而它开箱自带的三道闸（Guardrails / DLP / 日志全文）全都朝错方向。
`llm/advise.py` 那层"受控选路"该不该补，是**另一个议题**，与 CF 无关。

---

## §5 待批清单

| # | 事项 | 我的建议 | 影响面 |
|---|---|---|---|
| E1 | 总体采纳边界：只借缓存 / 限流 / 短窗日志 | 采纳 | 决定后续所有动作 |
| E2 | 主任务链路**不过 CF** | 采纳 | 安全边界 |
| E3 | 令牌：需**另建一把**（`AI Gateway: Read+Edit`），现有 `cfut****` 只覆盖 Tunnel | 采纳 | **要你决定建在哪个账号**（`844b0356…` 还是 `82dd88c2…`） |
| E4 | 若建网关：开 **Zero Data Retention** + 常态 `cf-aig-collect-log: false` | 采纳 | 隐私边界 |
| E5 | **不开** Guardrails / **不开** DLP / **不用** BYOK / **不用** Unified Billing | 采纳 | 四条否决 |
| E6 | 代码侧：`cloud_llm.py` 需**一处小改**（支持自定义 header），不是零改动 | 采纳 | 通道 A |
| E7 | 缓存收益**先实测**（命中率），未测不投入 | 采纳 | 反空壳 |
| E8 | 日志上限口径冲突（100,000 vs 10M）→ **落地前复核官方文档** | 采纳 | 数字纪律 |
| E9 | 是否补 `llm/advise.py` 受控选路层（与 CF 无关的独立议题） | **另开单元** | 通道 A |
| E10 | `cloud_llm.py` 出站不走 `net_guard` → 登记观察项 | 采纳 | 既有现象 |

---

## §6 本评估**不**做什么 / 未取证项

**不做**：不改任何生产代码 · 不建网关 · 不申请令牌 · 不发网络请求 · 不读任何凭据值 · 不起 GUI · 不排施工序。

**未取证（如实登记，不许当已知）**：
1. **官方文档未取**（网络受限）——本文所有 CF 数字来自**本机 skill 参考文档**，属"参考值"，落地前须以官方文档复核（skill 自己就这么要求）。
2. **日志上限 100,000 vs 10M 未裁定**（§3 红线 3）。
3. **缓存命中率未实测**——无数据，不预测。
4. **Kimi / Moonshot 与智谱 GLM 能否走 `/compat` 透传**——支持清单里没有，须实测。
5. **真实用户环境下的 key 池现状未验**：本进程身份 = `desktop-vpvp0bp\codexsandboxoffline`（**沙箱身份，不是真实用户**），
   8 个 LLM key 变量在本进程**全部未设置**——这**不代表**真实用户环境没有（《身份与封印判例》：沙箱身份不是你的身份）。
   要确认"免费池现在有几把可用 key"，须在**真实用户身份**下复核。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
