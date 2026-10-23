# 微信 iLink Bot · 评审与改造清单

> 收到时间：2026-09-18（风哥同一份代码贴了三次）· 评审人：公主土豆
> **状态：未接能力库、未落原件。** 先改四处 + 两条口径，再谈接入。
> 关联挂账：`PROJECT_BLUEPRINT.md` §八 **O70**（四冲突 / 接口面 / webhook 面）

---

## 一、四个硬冲突（按严重度）

| # | 位置 | 问题 | 改法 | 仓内依据 |
|---|---|---|---|---|
| ① | `TOKEN_FILE = Path("bot_token.txt")` / `CONTEXT_FILE` | **相对路径 ⇒ 落点随 CWD 漂**；且**明文 JSON** 落盘 | 绝对路径 + **DPAPI**；日志只打掩码 | 坑册第 5 条（CWD 漂移）；仓内已有 5 个 `.dpapi` 先例（`cloudflare_api` / `deepseek_api` / `feishu_app` / `notion_api` / `xingyun_app`） |
| ② | `set_context()` 每条消息 `save()` | **每条消息整文件重写两次**，无锁、非原子 | `safe_io.atomic_write_json` / `locked_json_update`；或改 append-only 上下文日志 | O8「高频路径别全量重写」同族 |
| ③ | 无 `msg_id` 去重 | 长轮询 **35s 超时+重试是常态** ⇒ 重复回复 | 按 `msg_id`/`context_token` 去重，重复只记不重发 | 本仓幂等口径 |
| ④ | `import aiohttp` | 本仓依赖清单里的 HTTP 客户端是 **httpx**（无 aiohttp） | 改 `httpx.AsyncClient`，对得上仓口径、不新增依赖条目 | `requirements.txt` |

## 二、两条口径（不是代码问题，是纪律）

1. **失败必须结构化返回 + 原因码**。现在 `except Exception: print(...)` = 吞错；应返回
   `{ok: False, reason_code: ...}` 并落审计（不许只打屏）。
2. **对外发消息属"先问再做"**。渠道默认 `unattended_allowed: false`
   （照 `sources.json` 里 Telegram 那条登记），并进 policy 作用域。

## 三、接口面（若坚持"独立服务"形态）

### `POST /send`（App → Bot，出站）

| # | 要求 |
|---|---|
| ① | 绑定 **127.0.0.1**（`panel_server.py:777` host 白名单 + `services.json` 回环惯例） |
| ② | **必须鉴权**（裸路由 ⇒ 任何本机进程/页面 JS 都能代你发微信） |
| ③ | 走 policy 外发作用域；审计只记「谁 / 何时 / 给谁 / 字数」 |
| ④ | **幂等键**（重复调用不重复发） |
| ⑤ | 长度上限 + **收件人白名单**（照 `coze_mail_cap._check_recipient`：白名单空 ⇒ 全拒） |

### `POST /webhook`（Bot → App，入站）

Bot 是**双向中继**：对 `/send` 是服务端，对 `/webhook` 是客户端。

| # | 面 | 不做则 | 原因码 |
|---|---|---|---|
| ① | 投递可靠性（重试/退避/失败落盘） | 消息静默丢 | `webhook_delivery_failed` |
| ② | 去重 | 重复处理 ⇒ 重复回复 | `webhook_duplicate` |
| ③ | **鉴权** | 任何本机进程可**伪造"微信来信"**（伪造输入，比 /send 更阴） | `webhook_unauthorized` |
| ④ | 外发边界（App 在外网时正文出机器） | 隐私外流 | `data_export` |

## 四、推荐形态：**不开 HTTP 中继**

事实（一手）：**全仓没有 webhook 接收端先例**；既有形态是
「同机同进程 callback（`potato_pet/behavior.py`、`chat_client.py`）+ 回环服务登记（`services.json`）」。

⇒ Bot 与处理逻辑同机可达，加一层 HTTP 只是把「两处真相」制度化
（第二入口 + 第二份状态 + 第二套鉴权）。

| 项 | 值 |
|---|---|
| cap 名 | `wechat_ilink`（词边界 0 占用） |
| 面板 tab | **tools** |
| 入口文件 | `gbt_allinone/wechat_ilink.py` |
| policy 作用域 | `external_llm` + 数据外发；**未列出动作 fail-closed** |
| 常驻 | `services.json`（长期轮询，非一次调用） |
| AI 回复 | 走**已有**通道 `cloud_llm` / `deepseek-flash`（回落 `deepseek-v4-pro`），凭据用已有 `deepseek_api.dpapi` |

## 五、接入前必须先拍的两件

1. **形态**：cap op（推荐）还是 HTTP 中继（`/send` + `/webhook`）。
2. **授权**：对外发消息的许可 —— 默认关闭 + 白名单 + 先做一次"只发给自己"的真实验证。

> 备注：`get_ai_reply` 里现在还是模拟实现；接入时**不新写 HTTP**，走仓内 LLM 通道。
> 另外「iLink 是腾讯官方授权、不会封号」这句**不背书**——外部声明不是判据，
> 本仓对每个渠道都要求写 `verify.how` 且默认标 `unverified`。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属


---

## 六、接口契约：`POST /send`（可直接照着实现）

```
POST /send                     仅回环 127.0.0.1；需本地令牌
Header  X-GBT-Local-Token: <由 DPAPI 凭据派生的本地令牌>
Body    {
          "to_user":         "<微信 user id>",   // 必填；必须在 allow_to 白名单内
          "text":            "<正文>",           // 必填；<= 1000 字符
          "idempotency_key": "<调用方生成的唯一键>" // 必填；重复键 => 不重复发
        }
```

| HTTP | 响应体 | 含义 |
|---|---|---|
| 200 | `{"ok": true, "delivered": true, "msg_id": "...", "duplicate": false}` | 已投递 |
| 200 | `{"ok": true, "duplicate": true}` | **幂等命中**：未重复发（不是错误） |
| 200 | `{"ok": false, "reason_code": "recipient_not_allowed"}` | 白名单外 → **拒发** |
| 200 | `{"ok": false, "reason_code": "text_too_long"}` | 超长 |
| 503 | `{"ok": false, "reason_code": "bot_not_logged_in"}` | 未扫码 / 凭据失效（**唯一该返 5xx 的一类**） |
| 401 | — | 令牌缺失或不符 |
| 422 | — | 缺必填字段（协议层错误） |

**一条口径（重要）**：**业务性拒绝返 `200 + ok:false + reason_code`，不返 5xx。**
理由：5xx 会**触发上游重试**，而"白名单外 / 超长"这类拒绝**重试一万次也不会成功** ——
返 5xx 等于把一次拒绝放大成一串重试。只有"凭据失效"这种**重试可能成功**的情况才返 503。

配套（与契约同批要做）：

- 审计每条：`time / to_user / 字数 / duplicate / reason_code`（**正文不入日志**）；
- `idempotency_key` 建议由调用方按「会话 + 轮次」生成，重复投递 30 分钟内不重发；
- 未列出的字段一律忽略（不报错），但**未知 `reason_code` 一律当失败处理**（fail-closed）。



---

## 七、接口契约：`POST /webhook`（Bot → App，可直接照着实现）

```
POST /webhook                       App 侧实现的接收端点；Bot 作为客户端投递
Header  X-GBT-Webhook-Token: <本地令牌>     鉴权（缺失/不符 => 401）
Header  X-GBT-Delivery-Id:  <唯一投递号>    幂等键（与 body.delivery_id 双写，便于只读日志核对）
Header  X-GBT-Attempt:      <第几次投递>    观测用（退避第几轮）
Body    {
          "delivery_id": "…", "msg_id": "…", "from_user": "…",
          "text": "…",                // 可选：payload_mode=signal 时**不带正文**
          "context_token": "…",       // 回传用
          "received_at": "…", "attempt": 1
        }
```

| HTTP | 响应 | Bot 的行为 |
|---|---|---|
| 200 | `{"ok":true}` | 已接收，**不再重投** |
| 200 | `{"ok":true,"duplicate":true}` | 幂等命中，同样视为成功，**不再重投** |
| 200 | `{"ok":false,"reason_code":"rejected_*"}` | **业务性拒绝：不再重投**（见下） |
| 401 / 422 | — | 协议层错误：**不重投**（重投也不会变好），落审计 |
| 5xx / 超时 | — | **退避重投**：1s → 2s → 4s → 8s → 16s（上限 5 次），耗尽落队列 |

### 三条口径（与 `/send` 同源）

1. **投递语义是 at-least-once，不是 exactly-once。** 所以接收端**必须幂等** ——
   这就是 `duplicate` 存在的理由；重复投递返回 `ok:true`，**不要返错**（返错会被无限重投）。
2. **业务性拒绝返 200，不返 5xx**（与 `/send` 同一条）：5xx/超时才会触发重投，
   而"格式不对 / 不收这类消息"重投一万次也不会成功 ⇒ 5xx 等于把一次拒绝放大成一串重试。
3. **失败要落盘，不能只留在内存里**：退避耗尽后消息进 `store/` 下的**待投递队列**，
   重启不丢；同时暴露只读水位（`pending / failed / last_error_code`）作为可见化出口。

### 一条隐私设计（建议默认开）

`payload_mode: "signal" | "full"`：

- **`signal`（建议默认）**：只投 `msg_id / from_user / received_at / 长度`，**不带正文** ——
  App 需要正文时再经能力层按需取（同机就无需外发）。
- `full`：带正文。**仅当处理逻辑在别的机器**时才用，且要走 policy 的 `data_export` 作用域。

理由：`/webhook` 是唯一会让**私聊正文离开本机**的一环（若 App 在外网）。默认不带上正文，
等于把"隐私外泄"从默认行为改成显式选择。



---

## 八、三条缺口修补（风哥 2026-09-18 评审）

### 缺口一（最要紧，真泄漏）：失败路径不能绕开 `payload_mode`

原契约写「401 / 422 → 不重投，落审计」——**没写落什么**。而协议层错误（尤其鉴权失败）
恰恰发生在**请求来源不可信**时：若"落审计"落整个请求体，正文就**绕过 `payload_mode` 从失败路径漏进本机审计流**。

**改为**：

```
401 / 422 落审计的字段 = Header 摘要 + delivery_id + 长度 + 拒绝原因码
  · 不落正文（无论 payload_mode 为何）
  · 理由：协议层拒绝的请求来源不可信，其内容不应进入本机审计流
```

**并且补一条限定（风哥）**：`signal` 模式**去掉的是内容，不是元数据**。
`msg_id / from_user / received_at / 长度` 四样合起来，足以重建「谁在什么时间发了多长的消息」——
**那是社交图谱**。原文"默认不带正文 = 把隐私外泄改成显式选择"成立，但不能读成"signal 就安全"。

### 缺口二：幂等窗口必须与退避窗口写在一起

原契约只写了投递语义，没写 `delivery_id` **保留多久**：

| 保留窗口 | 后果 |
|---|---|
| 无上限 | 集合永远涨（在 `audit.jsonl` 上刚吃过一次） |
| **短于重投窗口** | 后几次重投被当新投递 ⇒ **幂等形同虚设，正文被处理多次** |
| ≥ 最大重投窗口 + 余量 | ✅ |

**改为**：

```
delivery_id 保留 >= max_retry_window x 安全系数
  发送端 31 秒内最多重投 5 次  =>  接收端至少留 31s，建议留到分钟级
  且 **按条数封顶**：TTL 与条数**双约束**
    单靠 TTL -> 一次突发会把内存吃光
    单靠条数 -> 慢速重投会被挤掉
```

### 缺口三：`X-GBT-Attempt` 的执法方要写清

原契约写「上限 5 次」，但**没说是谁数**——靠一个"观测头"执法，那它就不是上限，是建议。

```
发送端（Bot）：按自己的 attempt 计数自我限流，达 5 次即停（权威计数在这里）
接收端（App）：**不依赖该头做限流**；它只是观测值；重复投递照常幂等处理
=> 两边职责分开，不互相假设
```

---

## 九、决策记录

| 项 | 决定 | 备注 |
|---|---|---|
| **webhook 要不要** | ✅ **要**（风哥 2026-09-18） | 理由：它是 `/send` 的对称面；没有回程，"Bot 作客户端投递"这个定位就少一半 |

**已知代价（如实记）**：选 webhook ⇒ 形态落在「**HTTP 中继**」。我方原建议是"不开中继、改 cap op"，
主要顾虑是「第二用户入口 + 第二份状态 + 第二套鉴权」与「用户入口只有 `holo_pet` 一个」的张力。
**风哥已拍，按此执行**；该代价记在此处，便于日后复核（不是反对票，是留存）。

---

## 十、待拍八条 · 选项摊开（便于一次拍完）

| # | 项 | 选项 | 我方建议 |
|---|---|---|---|
| 1 | **合并红线** | (a) 合并成一条完整红线 · (b) 保持分处但在 1305 加指针指向 R-H7 增补 · (c) 不动 | **(b)**（一行成本，消掉"只读到一半"的风险） |
| 2 | **云 ASR key** | (a) 现在给（A 基线当天作废，需重新冻结）· (b) 先用 3.10 把 A 的②③交叉验证做完再给 · (c) 不给，A 停在 3/4 | **(b)**（先把零依赖价值榨干再引入 key） |
| 3 | **O64 授权（切桌面）** | (a) 授权自动 attach · (b) 只允许显式开关（`GBT_CAPTURE_ATTACH=1`），默认不越界 · (c) 不授权 | **(b)**（能力拿到，边界仍在手里） |
| 4 | **H3 名字/网址** | (a) 给准确名字/网址（我核） · (b) 放弃 H3，改走有 API 的视频模型 · (c) 搁置 | 需你给输入；若拿不出选 (b) |
| 5 | **`audio_output` 作用域** | (a) 加定义 **并**挂到 `voice.tts`（非 trusted 会话下 tts 变需授权）· (b) 只加定义不挂 · (c) 不动 | **(a)**（影响面小：面板 tts 本就标 `blocked_identity`） |
| 6 | **3.10 交叉复跑** | (a) 跑（零依赖，提升 A 基线可信度）· (b) 不跑 | **(a)** |
| 7 | **`prompt_bridge`** | (i) 直接做最小一刀 · (ii) 先只出设计 | **(i)** |
| 8 | **微信 Bot 形态** | (a) cap op（不开 HTTP 中继）· (b) HTTP 中继（`/send` + `/webhook`） | 你已选 webhook ⇒ 实际落在 **(b)**，请确认 |

