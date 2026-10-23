# 平台 ↔ 收款钱包 · 接轨设计（INTEGRATION）

> 交付物 B。目标：让平台后端用**标准库**就能安全调用钱包 API，并把"链上到账"自动变成"平台内部账本余额"。
> 代码：`platform_client.py`（平台侧客户端）、`auth.py`（钱包侧可选鉴权中间件）。
> 部署侧配套：`../deploy/DEPLOY.md`。

---

## 1. 调用时序（端到端闭环）

```
 用户        平台前端        平台后端                 gbt_wallet API            链上            gbt_allinone 账本
  │             │               │                          │                    │                    │
  │ 下单/充值    │ ────────────▶ │                          │                    │                    │
  │             │               │ create_invoice(user,amt) │                    │                    │
  │             │               │ ───────────────────────▶ │ POST /invoice      │                    │
  │             │               │                          │ 派生收款地址(HD 索引单调)                 │
  │             │               │                          │ 写 invoices.json + ledger.jsonl 审计      │
  │             │               │ ◀─────────────────────── │ {invoice_id,address,amount,...}          │
  │             │               │ 登记 invoice_id→user      │                    │                    │
  │             │ ◀──────────── │  (invoice_user.json, 与到账桥共用同一文件)      │                    │
  │ ◀────────── │ 展示收款地址/二维码/金额                     │                    │                    │
  │             │               │                          │                    │                    │
  │ 转账 USDC.E  │               │                          │                    │                    │
  │ ──────────────────────────────────────────────────────────────────────────▶ │                    │
  │             │               │                          │                    │                    │
  │             │               │ scan()  ───────────────▶ │ POST /scan         │                    │
  │             │               │                          │ 增量扫描(游标断点续扫, 12 确认) ────────▶ │
  │             │               │                          │ 发票 pending→paid/partial, 写审计事件     │
  │             │               │ ◀─────────────────────── │ {found,latest,safe,ranges}               │
  │             │               │                          │                    │                    │
  │             │               │ bridge.sync() / run_task("receive_sync")       │                    │
  │             │               │ 读 invoices.json 的 paid_amount_int ──────────▶ │                    │
  │             │               │ ───────────────────────────────────────────────────────────────────▶│
  │             │               │                          │                    │  ledger.deposit(user,   │
  │             │               │                          │                    │   asset, delta,         │
  │             │               │                          │                    │   ref="chain:<inv>")   │
  │             │               │                          │                    │  逐发票幂等(credited_int)│
  │             │               │ ◀───────────────────────────────────────────────────────────────────│
  │             │ ◀──────────── │ 余额(账本派生)             │                    │                    │
  │ ◀────────── │ 展示可用余额   │                          │                    │                    │
```

**关键语义**

- 钱包只负责"钱**到了哪个收款地址**"，账本只负责"用户在平台有多少余额"；两者用
  `invoice_id` 与 `invoice_user.json` 映射绑定，**不**用邮箱/手机号等可变标识做资金主键。
- 记账去重的唯一依据是 `paid_amount_int` 的**增量**（逐发票 `credited_int` 水位），
  因此 `sync()` / `credit_from_invoices()` 可以反复执行。
- 发票是一次性的收款地址（每票一个 HD 索引），因此**不要复用**发票地址。

---

## 2. 接口清单与字段

### 2.1 平台侧客户端 `platform_client.WalletClient`

```python
from gbt_allinone.integration.platform_client import WalletClient
c = WalletClient()                        # base=GBT_WALLET_API_BASE, token=GBT_WALLET_API_TOKEN
c = WalletClient(base="http://127.0.0.1:8097", token="<token>", timeout=10.0, retries=2)
```

| 方法 | HTTP | 返回 | 说明 |
|---|---|---|---|
| `health()` | `GET /api/gbtwallet/health` | `dict` | 服务与钱包状态 |
| `create_invoice(user, amount, currency="USDC.E", label="", expires_hours=72, idempotency_key=None)` | `POST /api/gbtwallet/invoice` | `dict`(发票 + `user`) | 开票并登记 `invoice_id→user` 映射 |
| `list_invoices(status=None, user=None)` | `GET /api/gbtwallet/invoices` | `list[dict]` | `status ∈ {pending, partial, paid}`；`user` 非空则按映射过滤 |
| `get_invoice(invoice_id)` | 同上(本地过滤) | `dict`/`None` | — |
| `scan()` | `POST /api/gbtwallet/scan` | `dict` | 触发链上增量扫描（幂等，可安全重试） |
| `balances()` | `GET /api/gbtwallet/balances` | `dict` | 各地址余额快照（走 RPC，较慢，默认超时 60s） |
| `events(since=None, limit=200)` | `GET /api/gbtwallet/events` | `list[dict]` | 事件轮询（见 §5） |
| `monitor()` | `GET /api/gbtwallet/monitor` | `dict` | 运行总览（内部/巡检用） |
| `wait_for_health(timeout=30)` | 轮询 | `dict` | 启动等待 |

模块级便捷函数：`health() / create_invoice() / list_invoices() / scan() / balances() / events()`（复用默认客户端）。

### 2.2 钱包侧接口（本次未改动的既有路由，仅列与接轨相关的）

| 路由 | 方法 | 关键字段 |
|---|---|---|
| `/api/gbtwallet/health` | GET | `ok, version, initialized, dir, master_evm, invoices, pending` |
| `/api/gbtwallet/invoice` | POST | 入：`amount, currency, label, expires_hours`；出：`invoice{invoice_id, address, amount, currency, decimals, amount_int, status, expires_at, paid_amount_int, tx_hashes[], notes[]}` |
| `/api/gbtwallet/invoices` | GET | 入：`status?`；出：`invoices[]` |
| `/api/gbtwallet/scan` | POST | 出：`closed_expired, result{found, latest, safe, ranges}` |
| `/api/gbtwallet/balances` | GET | 出：`balances{rpc_block, USDC.E[], USDC[], USDT[], WETH[]}` |
| `/api/gbtwallet/events` | GET | 入：`since?(epoch 秒), limit?`；出：`events[]`（按 `t` 倒序） |
| `/api/gbtwallet/monitor` | GET | 出：各台账计数 + pm 侧文件行数（只读） |

**内部/运营面（禁止接入用户 UI，反向代理已边缘 403）**：
`/api/gbtwallet/ops/*`、`/api/gbtwallet/engine/*`、`/api/gbtwallet/orders/*/internal`、
`/api/gbtwallet/orders/*/admin/*`、`/api/gbtwallet/monitor`、`/api/gbtwallet/receipts/summary|export`。

**发票状态机**：`pending` --(收到部分金额)--> `partial` --(累计 ≥ 应付)--> `paid`
（过期后到账只记 `notes` 与审计事件 `fund_received_expired`，不改状态、不静默吞资金。）

**金额口径**：链上金额用整数最小单位（`*_int`，如 `paid_amount_int`、`amount_int`），
人读金额 = `int / 10**decimals`；账本侧用 `Decimal` 字符串。**平台不要用 float 做金额比较**。

---

## 3. 鉴权方式

| 模式 | 触发条件 | 行为 |
|---|---|---|
| 默认（不鉴权） | 未设置 `GBT_WALLET_API_TOKEN` | 完全保持接入前行为；安全性依赖"只绑 127.0.0.1" |
| 令牌鉴权 | 设置了 `GBT_WALLET_API_TOKEN` | **所有**接口要求 `Authorization: Bearer <token>`，否则 `401` |

- 比较使用 `hmac.compare_digest`（常数时间）；方案名大小写不敏感（`Bearer`/`bearer` 均可）。
- 中间件是**纯 ASGI** 实现，不依赖 Starlette 内部 API；`OPTIONS` 预检直接放行（由外层 CORS 应答）。
- 顺序：先挂鉴权（内层）再挂 CORS（外层），因此 **401 响应也带 CORS 头**，浏览器不会把真实 401 显示成跨域错误。
- 运维核对：`auth.token_fingerprint()` 给出令牌 sha256 前 12 位（不可逆），两端比对即可确认"是否同一令牌"，
  无需传递明文。
- ⚠ **"设了令牌" ≠ "令牌生效"**：若服务进程没加载到本接轨层（依赖被裁剪、导入失败），
  `api.py` 会降级为原行为 —— **不鉴权**，此时环境变量里的令牌形同虚设。
  部署后请用 `deploy/healthcheck.ps1` 复核：它会在 `auth_enabled=True` 时主动发一次**无令牌**请求，
  只有被拒（401）才判定"鉴权确实生效"，否则以退出码 4 报错。

### 3.1 接入方式（已落地，最小侵入）

`gbt_wallet/api.py` 顶部只增加一段"导入即装配"，**默认行为不变**：

```python
app = FastAPI(title="GBT Wallet API", version="0.5.0")
try:   # 正常运行: 项目根在 sys.path 上
    from gbt_allinone.integration.auth import install_middleware as _install_mw
except Exception:
    try:   # 兜底: 以本文件位置推算项目根后重试
        import sys as _sys; from pathlib import Path as _Path
        _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
        from gbt_allinone.integration.auth import install_middleware as _install_mw
    except Exception:
        _install_mw = None

if _install_mw is not None:
    _install_mw(app)                      # 读 env: 令牌 + CORS 来源
else:
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

- 集成层不可用时**自动降级**为原有 CORS 行为，服务仍可启动（不会因接轨层缺失而起不来）。
- 需要手工装配（例如裁剪部署、或想给别的 FastAPI 服务复用同一套中间件）时：

```python
from gbt_allinone.integration.auth import install_middleware
install_middleware(app)                                   # 读环境变量
install_middleware(app, token="<token>", cors_origins=["https://app.example.com"])   # 显式传参
```

- 独立校验函数（自测/自定义中间件用）：`verify_bearer(header_value, token)`、`is_authorized(headers, token=None)`。

---

## 4. 错误与重试

| 现象 | 客户端表现 | 处理建议 |
|---|---|---|
| 服务未启动 | `WalletApiError`(retryable=True, 无 status) | 退避重试；持续失败 → 告警（`healthcheck.ps1` 退出码 1） |
| `401` | `WalletApiError(status=401, retryable=False)` | **不重试**；检查两端令牌是否一致（比对 `token_fingerprint`） |
| `400`（金额/币种非法等） | `WalletApiError(status=400)` | **不重试**；修正入参（币种必须在白名单内，金额 > 0） |
| `404`（单据/订单不存在） | `WalletApiError(status=404)` | **不重试**；核对 id |
| `500`（扫描失败/RPC 异常） | `WalletApiError(status=500, retryable=True)` | 自动退避重试；仍失败则告警并等待 RPC 恢复 |
| 超时 / 连接被拒 | `WalletApiError`(retryable) | 自动重试（仅 GET 与 `/scan`） |

**重试策略（客户端内置）**

- 默认 `retries=2`，退避 `0.4s → 0.8s`（指数）。
- **只对幂等调用重试**：所有 `GET` + `POST /api/gbtwallet/scan`。
  `POST /api/gbtwallet/invoice` **默认不重试**（非幂等）—— 需要重试时使用下面的幂等键。
- HTTP `4xx` 一律不重试；`5xx` 与网络错误才重试。

**超时**：默认 10s；`/scan` 与 `/balances` 走 RPC，默认放宽到 60s，可用 `timeout=` 覆盖。

---

## 5. 幂等约定

### 5.1 开票（平台侧幂等键）

```python
inv = c.create_invoice("u_1001", 19.9, "USDC.E", idempotency_key="order-20260910-0001")
```

- 幂等表默认落在 `GBT_PLATFORM_IDEM_FILE`（默认 `gbt_allinone/store/platform_idem.json`）。
- 条目结构 `{ "<key>": {"base": <服务基址>, "ts": <epoch>, "invoice": {...}} }`；
  **仅当 `base` 与当前客户端一致时才命中** —— 换基址/重建钱包后不会返回已失效的发票号。
- **钱包恢复（见 DEPLOY.md §7.3）后必须删除该文件**，避免命中历史条目。
- 未提供 `idempotency_key` 时不做客户端缓存，需由调用方自己保证不重复下单。

### 5.2 扫描入账（服务端幂等）

- `/scan`：按 `cursor.json` 游标推进，同一区间不会重复入账；重复调用只会推进游标或返回 `found: 0`。
- **到账记账**：`deposit_bridge.credit_from_invoices()` 以每张发票的 `paid_amount_int` 水位
  （`credited_int`）做增量记账，`ref="chain:<invoice_id>"`。因此 `sync()` 可以按任意频率重复执行，
  余额只增一次。
- **发票状态**：`pending→partial→paid` 单调前进；重复扫描同一 tx 不会重复累计（`tx_hashes` 去重）。

### 5.3 调用方建议

- 平台下单接口自身也要幂等（例如用业务单号做键），与钱包侧幂等键一一对应。
- 记账动作（`bridge.sync()`）用**巡检定时任务**驱动即可（建议 1–5 分钟），不必在用户请求里同步等待。

---

## 6. 事件轮询（`/events?since=`）

```
GET /api/gbtwallet/events?since=<epoch秒>&limit=200
→ {"ok": true, "events": [ {t, ts, kind, ...}, ... ]}     # 按 t 倒序
```

- `since` 为 **epoch 秒**（含边界，`t >= since`），不传则返回最近 `limit` 条；`t` 是事件时间。
- 事件源是钱包数据根的 `ledger.jsonl`（append-only 审计），**不是**消息队列：不保证 exactly-once，
  轮询方必须自己按 `(kind, invoice_id, tx)` 或 `t` 水位去重。
- 典型事件：`invoice_create`、`receive_addr`、`scan_done`、`scan_error`、`fund_received`、
  `fund_received_expired`、`wallet_init`，以及单据/订单/结算相关审计。
- **推荐轮询姿势**：持久化"上次最大 `t`"，下轮用 `since=lastT`（可回退 60s 防边界丢事件），
  处理完再推进水位；重启后从水位续读即可（`ledger.jsonl` 不删除、只追加）。
- `content`: 事件里可能包含地址、tx hash、invoice_id —— 属于运营/对账数据，**不要**直接下发到浏览器。

---

## 7. 自测（可复跑）

```bash
python gbt_allinone/integration/smoke_test.py          # 13 项断言: 鉴权/CORS/401/200/真 HTTP 回环/幂等
python gbt_allinone/integration/smoke_test.py --no-live # 只跑 TestClient 层(不起 uvicorn)
```

覆盖范围：默认无令牌 200、设令牌后 401/401/200、其它路由同样受保护、CORS 默认 `*` 与白名单生效、
401 响应带 CORS 头、`auth.py` 22 项函数断言、真 HTTP 回环下开票/幂等/列表/按用户过滤/事件、
以及"换基址不命中旧幂等条目"。全部写盘都在系统临时目录内，结束后删除。

---

## 8. 边界与注意事项

1. 客户端**只用标准库 urllib**，不引入任何新第三方依赖。
2. 客户端不做本地重试队列/持久化队列；需要"至少一次"语义请由平台侧任务系统保证。
3. 令牌是静态共享密钥，无签发/过期/吊销；轮换 = 改两端环境变量并重启服务。
4. 事件流不是流式推送（无 SSE/WebSocket）；需要近实时可缩短轮询间隔（注意 RPC 与磁盘压力）。
5. `invoice_user.json` 是钱包数据根内的文件，由到账桥与客户端共同读写 ——
   **同一数据根只允许一个写入方**（单进程约束，见 DEPLOY.md §10）。
6. 平台不要直接连 `8097` 之外的地址；跨机部署请把客户端指向反向代理域名，并由代理侧做访问控制。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
