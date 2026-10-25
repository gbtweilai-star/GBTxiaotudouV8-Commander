# gbt_wallet 收款钱包 · 部署设计文档

> 适用范围：把已存在的 `gbt_wallet/`(FastAPI 收款钱包) 部署为可运营服务，并与 `gbt_allinone/`
> 框架(内部账本 + 到账自动记账)接轨。
> 本文只描述**部署与接轨**，不改变钱包业务逻辑与数据格式。
> 配套文件：本目录脚本模板 + `../integration/INTEGRATION.md`(接轨设计)。

---

## 1. 拓扑与信任边界

```
  ┌──────────┐   HTTPS    ┌──────────────────┐  HTTP   ┌───────────────────┐   JSON-RPC   ┌──────────────┐
  │ 用户/平台 │ ─────────▶ │ 反向代理 (Caddy)  │ ──────▶ │  gbt_wallet API    │ ───────────▶ │ Polygon RPC  │
  │ 前端      │            │ TLS 终止 / 路由    │ 127.0.0.1│  FastAPI :8097     │  只读扫描     │ (Alchemy/    │
  └──────────┘            │ 内部路由 403       │  :8097  │  仅绑 127.0.0.1     │              │  公共节点)    │
        ▲                 └──────────────────┘         └─────────┬─────────┘              └──────────────┘
        │                                                          │ 写盘(数据根)
        │  下单/开票/余额展示                                        ▼
  ┌──────────┐  Bearer  ┌──────────────────┐                ┌──────────────────────────────┐
  │ 平台业务  │ ───────▶ │ platform_client   │                │ 数据根 GBT_WALLET_DIR          │
  │ 后端      │          │ (标准库 urllib)    │                │  master.enc / invoices.json /  │
  └────┬─────┘          └──────────────────┘                │  cursor.json / ledger.jsonl /  │
       │                                                      │  users.json / sessions.json …  │
       │ 扫描后自动记账(逐发票幂等)                             └──────────────────────────────┘
       ▼
  ┌──────────────────────┐
  │ gbt_allinone 内部账本  │  deposit_bridge: 发票 paid → ledger.deposit(幂等 credited_int)
  │ ledger(交易所式托管)   │  用户余额 = 账本条目的派生值
  └──────────────────────┘
```

**信任边界（三条硬规则）**

1. 钱包 API **永远只绑 `127.0.0.1`**；公网入口只能是反向代理，容器部署也只把端口发布到宿主回环。
2. 数据根(`master.enc` + 全部台账)**是最高敏感资产**：拿到 `master.enc` + 口令 = 拿到助记词 = 拿到资金。
3. 平台后端持有服务令牌；浏览器**永不**持有 `GBT_WALLET_API_TOKEN`(前端只调平台自己的后端)。

---

## 2. 组件职责

| 组件 | 职责 | 不负责 |
|---|---|---|
| `gbt_wallet` (FastAPI, :8097) | 派生收款地址、开发票、链上**只读**增量扫描入账、余额快照、事件流、账号/辖区台账、技术费单据、兑换订单台账 | 链上广播(本版本不做)、用户资金托管账本的记账(由框架账本负责) |
| 反向代理 (Caddy/Nginx) | TLS 终止、域名/路由、内部路由边缘 403、访问日志、请求体/超时限制 | 鉴权之外的业务逻辑；不做令牌签发 |
| 接轨层 `gbt_allinone/integration/` | 平台侧 HTTP 客户端(urllib)、可选 Bearer 鉴权中间件、CORS 白名单装配 | 不改钱包业务逻辑、不落任何密钥 |
| 框架账本 `gbt_allinone/ledger/` | 交易所式内部记账(复式、append-only、freeze/unfreeze) | 不接触链上私钥、不广播交易 |
| 到账桥 `gbt_allinone/bridge/deposit_bridge.py` | 把"发票新增已付金额"按发票幂等记账到账本；维护 `invoice_id → user` 映射 | 不判断资金合法性(风控/合规另层) |
| 运行环境 | Python ≥3.10 + `gbt_allinone/requirements.txt`；Windows 计划任务/NSSM 或 systemd 或 Docker | — |

**数据根文件清单**（备份/恢复的完整口径，均位于 `GBT_WALLET_DIR`）

| 文件 | 内容 | 备份重要性 |
|---|---|---|
| `master.enc` | 加密主助记词(AES-256-GCM / PBKDF2-SHA256, 60 万轮) | **必需**，丢失=资金不可控 |
| `state.json` | 主地址 / 派生计数器 / 币种设置 | 必需（计数器回退会导致地址复用） |
| `invoices.json` | 发票与收款地址、已付金额、状态 | 必需 |
| `cursor.json` | 各链/币种扫描游标（断点续扫） | 重要（丢失只会导致重扫，不丢账） |
| `ledger.jsonl` | 钱包侧审计/资金事件(append-only) | 必需（对账依据） |
| `invoice_user.json` | 发票 → 平台用户映射（到账自动记账用） | 必需（丢失会导致无法自动入账） |
| `users.json` / `sessions.json` / `otps.json` | 账号、会话、OTP 台账 | 重要 |
| `orders.json` / `engine_tasks.json` / `receipts.json` / `settlements.json` / `bindings.json` / `activations.json` | 订单、引擎任务、技术费单据、收益结算、地址绑定、激活 | 重要 |
| `scan.log`, `logs/` | 扫描与运行日志 | 可选（排障用） |

---

## 3. 端口与环境变量

### 端口

| 端口 | 绑定 | 说明 |
|---|---|---|
| 8097 | `127.0.0.1` | 钱包 API(默认)。`GBT_WALLET_PORT` 可改；改端口需同步反向代理上游 |
| 443 / 80 | 公网 | 仅反向代理。80 仅用于 ACME 校验与跳转 443 |
| — | — | 链上 RPC 只需**出站**访问，不需要任何入站端口 |

### 环境变量

| 变量 | 必需 | 默认 | 说明 |
|---|---|---|---|
| `GBT_WALLET_PASS` | 是 | — | 钱包口令（≥16 位高熵）。**不落盘**；服务运行必须提供 |
| `GBT_WALLET_DIR` | 是(生产显式) | `%USERPROFILE%\.gbt\gbt_wallet`(Windows) / `~/.gbt/gbt_wallet` | 数据根 |
| `GBT_WALLET_PORT` | 否 | `8097` | 服务端口 |
| `GBT_WALLET_BIND_HOST` | 否 | `127.0.0.1` | 绑定地址（仅容器内需 `0.0.0.0`） |
| `GBT_WALLET_API_TOKEN` | 建议 | 空=不鉴权 | 设置后所有接口要求 `Authorization: Bearer <token>`（常数时间比较） |
| `GBT_CORS_ORIGINS` | 建议 | 空=`*` | 逗号分隔白名单；生产务必显式（`*` 仅适合本机开发） |
| `GBT_EVM_RPC` | 建议 | `https://polygon-bor-rpc.publicnode.com` | 钱包扫描/余额用 RPC（生产用专用额度节点，公共节点会限流导致漏轮次） |
| `ALCHEMY_RPC_URL` | 否 | — | 框架侧自建只读 RPC |
| `GBT_LEDGER_DIR` | 否 | `gbt_allinone/store` | 内部账本目录 |
| `GBT_WALLET_API_BASE` | 否 | `http://127.0.0.1:8097` | 平台侧客户端基址 |
| `GBT_PLATFORM_IDEM_FILE` | 否 | `gbt_allinone/store/platform_idem.json` | 平台侧开票幂等表 |
| `GBT_BACKUP_DIR` / `GBT_BACKUP_KEEP` | 否 | `%ProgramData%\gbt-wallet-backups` / `14` | 备份输出目录与保留份数 |

模板见 [`env.example`](./env.example)（全部为占位符，**禁止**填入真实值后提交）。

---

## 4. 部署路线（三选一）

### 4.1 Windows：计划任务 或 NSSM

```powershell
# 0) 依赖(缺失时按需安装; 不装新第三方库, 仅 requirements.txt)
python -m pip install -r gbt_allinone\requirements.txt

# 1) 钱包初始化(只做一次; 助记词只显示一次 -> 离线抄录, 不要截图/不要进剪贴板历史)
$env:GBT_WALLET_DIR = "$env:ProgramData\gbt-wallet\data"
$env:GBT_WALLET_PASS = "<强口令,>=16位>"
python -c "import sys;sys.path.insert(0, r'<仓库根>');sys.argv=['gbt_wallet.cli','init','--pass-env'];import runpy;runpy.run_module('gbt_wallet.cli',run_name='__main__')"

# 2) 密封口令(DPAPI 加密写 env 文件, 明文不落盘; 需管理员)
powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\install_service_windows.ps1 `
    -Action Seal -EnvFile "$env:ProgramData\gbt-wallet\wallet.env"

# 3) 注册服务(二选一)
powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\install_service_windows.ps1 `
    -Action Install -Mode Task -EnvFile "$env:ProgramData\gbt-wallet\wallet.env"     # 方式 A: 计划任务
powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\install_service_windows.ps1 `
    -Action Install -Mode Nssm -EnvFile "$env:ProgramData\gbt-wallet\wallet.env" -NssmPath C:\tools\nssm\nssm.exe  # 方式 B: NSSM

# 4) 日常
... -Action Status | Start | Stop | Uninstall [-Mode Task|Nssm]
```

- 两种方式都把启动动作交给 [`run_wallet.ps1`](./run_wallet.ps1)（路径无关、端口守卫生效），**服务里不写明文口令**。
- DPAPI 的边界：同机管理员/SYSTEM 仍可解密；它防的是"文件被拷走/误提交"，不防"主机已被完全接管"。
- 手工/调试启动（不装服务）：
  ```powershell
  $env:GBT_WALLET_PASS = '<口令>'
  powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\run_wallet.ps1 -EnvFile <env文件> -DryRun   # 先自检
  powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\run_wallet.ps1 -EnvFile <env文件>            # 后台启动
  ```

### 4.2 Linux：systemd

```bash
sudo useradd --system --home /var/lib/gbt-wallet gbtwallet
sudo install -d -m 0750 -o gbtwallet -g gbtwallet /var/lib/gbt-wallet
sudo install -d -m 0750 /etc/gbt-wallet
sudo cp gbt_allinone/deploy/env.example /etc/gbt-wallet/wallet.env   # 改值
sudo chown root:root /etc/gbt-wallet/wallet.env && sudo chmod 600 /etc/gbt-wallet/wallet.env
sudo cp gbt_allinone/deploy/gbt-wallet.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now gbt-wallet
systemctl status gbt-wallet && journalctl -u gbt-wallet -f
```

### 4.3 Docker Compose

```bash
cd gbt_allinone/deploy
cp env.example .env         # 改值；.env 已被 .gitignore 覆盖，严禁提交
docker compose up -d --build
docker compose ps && docker compose logs -f
```

- 端口只发布到宿主回环 `127.0.0.1:8097:8097`；容器内为 `0.0.0.0`（容器网络命名空间内）。
- 数据在命名卷 `wallet-data`；根文件系统只读，仅 `/data` 可写。
- **不要**把数据根 bind mount 到仓库目录（避免误提交）。

---

## 5. 反向代理（Caddy 示例）

[`Caddyfile`](./Caddyfile) 已包含：TLS 自动证书、安全响应头、请求体/超时限制、访问日志，以及
**内部/运营面边缘 403**（`/ops/*`、`/engine/*`、`/monitor`、`/orders/*/internal`、`/orders/*/admin/*`、
`/receipts/summary|export`）——这些接口只允许内网/跳板机直连。

```bash
caddy validate --config gbt_allinone/deploy/Caddyfile
GBT_PUBLIC_HOST=wallet.example.com GBT_WALLET_API_TOKEN=<token> caddy run --config gbt_allinone/deploy/Caddyfile
```

> Nginx 等价配置要点：`proxy_pass http://127.0.0.1:8097;`、`proxy_set_header Authorization $http_authorization;`
> （不要吞掉 Authorization 头）、`client_max_body_size 256k;`、`proxy_read_timeout 120s;`，
> 并对上表内部路径 `return 403;`。

---

## 6. 上线检查清单

**部署前**

- [ ] 解释器：Python ≥3.10，`python -m pip install -r gbt_allinone/requirements.txt` 成功
- [ ] 钱包已初始化，助记词已**离线**抄录并双人复核（不拍照、不进聊天工具、不进剪贴板历史）
- [ ] 数据根目录权限收紧（Windows：去掉 Users 组；Linux：`chmod 700`，属主=服务账号）
- [ ] `GBT_WALLET_PASS` 只存在于密钥管理/DPAPI 密封文件或交互输入，不在脚本/仓库/工单里
- [ ] `GBT_WALLET_API_TOKEN` 已生成（`python -c "import secrets;print(secrets.token_urlsafe(32))"`）并双方一致
- [ ] `GBT_CORS_ORIGINS` 已填真实前端域名（不是 `*`）
- [ ] `GBT_EVM_RPC` 为专用节点且已验证可用（公共节点限流会漏扫描）
- [ ] 备份目录已就位、**在数据根之外**、且已配置异地/离线同步
- [ ] 反向代理已 `caddy validate` 通过，证书可自动签发（80/443 可达）

**启动与冒烟**

- [ ] `run_wallet.ps1 -DryRun`（或直接启动）退出码 0
- [ ] `GET /api/gbtwallet/health` → 200 且 `ok=true`；带错令牌 → 401
- [ ] 公网探测：`curl -sS https://<域名>/api/gbtwallet/health -H "Authorization: Bearer $TOKEN"` → 200
- [ ] 公网探测内部路由：`.../api/gbtwallet/monitor` → 403（边缘拦截生效）
- [ ] 端口探测：`8097` 在公网 IP 上**不可达**（只监听 127.0.0.1）
- [ ] 接轨冒烟：`python gbt_allinone/integration/smoke_test.py` → 全部 PASS，退出码 0
- [ ] `healthcheck.ps1` → exit 0

**业务闭环（真实小额）**

- [ ] 平台侧 `create_invoice(user, amount, currency)` 拿到发票与地址
- [ ] 用户小额真实支付 → `scan()` → 发票 `status=paid`（`GET /invoices` 可见）
- [ ] `python -m gbt_allinone.bridge`(或 `run_task("receive_sync")`) → 账本余额增加，且重复执行**不重复记账**
- [ ] 平台展示余额与账本一致；`GET /events?since=<t>` 能看到 `invoice_create` / `fund_received` / `scan_done`
- [ ] 技术费单据口径与 `fees.py` 一致（10% / 3% / 5%）

**运营就绪**

- [ ] 监控与告警已接入（见 §8），告警通道实测收到过一条测试告警
- [ ] 备份任务已排期（见 §7），并**实际做过一次恢复演练**
- [ ] 回滚方案与责任人已确认（见 §9）

---

## 7. 密钥与备份策略

### 7.1 密钥分层

| 资产 | 存放 | 泄露后果 | 轮换 |
|---|---|---|---|
| 助记词(离线) | 纸/金属助记词板，离线保管，双人分持 | 资金全部失控 | 只能换钱包（新建 `GBT_WALLET_DIR` 并迁址） |
| `GBT_WALLET_PASS` | 密钥管理系统 / DPAPI 密封文件 / 交互输入 | 配合 `master.enc` = 同上 | 需重建钱包（换口令要重新加密助记词） |
| `GBT_WALLET_API_TOKEN` | 平台后端与钱包服务的环境变量 | 可调用钱包接口（不能直接动链上资产，但可开票/触发扫描） | 随时轮换：改两端 env → 重启服务 |
| 备份介质 | 离线/异地，加密存储 | 配合口令 = 资金失控 | 按备份策略滚动 |

**绝对禁止**：把以上任何值写进仓库、脚本、镜像层、CI 日志、工单或聊天记录。示例文件一律占位符。

### 7.2 备份

```powershell
# Windows(建议计划任务: 每天 1 次 + 每周异地同步)
powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\backup.ps1 -Zip
# 指定路径与保留份数
... -DataDir D:\gbt\gbt_wallet -OutDir E:\backups\gbt -Keep 30 -Zip
```

```bash
# Linux(等价做法; 数据根只读快照更稳, 例如 LVM/ZFS 快照或先 systemctl stop)
sudo systemctl stop gbt-wallet
sudo tar -czf /backup/gbt-wallet-$(date +%F).tgz -C /var/lib gbt-wallet
sudo systemctl start gbt-wallet
```

- 备份内容为 §2 的完整文件清单；`backup.ps1` 生成 `manifest.json`（每文件 sha256 + 大小 + 主机 + UTC 时间）。
- 在线备份可接受：`invoices.json` 等用**原子替换**(写临时文件 + `os.replace`)，`ledger.jsonl` 为**追加写**，
  因此单文件拷贝不会读到半截 JSON；但多文件之间**不是同一时刻的快照**，恢复口径以 `ledger.jsonl` 为准做核对。
- **权限收紧提示**：`backup.ps1` 会断开备份目录的继承权限，只保留 `SYSTEM` / `Administrators` / 当前用户；
  Linux 请 `chmod 700` 备份目录并加密后异地保存。备份介质与数据根**不要在同一台机器/同一块盘**。
- 助记词离线备份与数字备份**分开保管**：两者同时泄露 = 资金失控。

### 7.3 恢复（演练过的顺序）

1. **停机**：停止钱包服务（`Stop-ScheduledTask`/`nssm stop`/`systemctl stop`/`docker compose down`），
   确认 8097 无监听进程。
2. **隔离现场**：把现有数据根**改名保留**（如 `gbt_wallet.broken-<日期>`），不要直接覆盖删除。
3. **还原文件**：把备份中的 `master.enc` 与各台账复制回 `GBT_WALLET_DIR`（保持原文件名）。
4. **核对完整性**：用 `manifest.json` 里每个文件的 sha256 逐项校验（`Get-FileHash` / `sha256sum`）。
5. **口令可用性验证**（只读，不动资金）：
   ```
   GET /api/gbtwallet/health      -> initialized=true 且 master_evm 与备份时一致
   GET /api/gbtwallet/invoices    -> 发票数量/状态与备份时间点吻合
   ```
   若 `master_evm` 与记录不符，立即停止后续步骤，回到第 3 步重新核对备份。
6. **明文助记词重建（最可靠的兜底）**：若 `master.enc` 丢失但离线助记词还在，
   在**全新数据根**用同一助记词导入重建（当前版本无导入命令，需按 `gbt_wallet/hd.py` 的 BIP44 路径
   `m/44'/60'/0'/0/i` 重新派生并重建台账；此路径属于人工操作，务必先在测试网/小额地址演练验证）。
   > 注意：地址派生索引必须与 `state.json` 的 `counters` 对齐，否则会出现地址复用。
7. **重建映射与账本对账**：恢复 `invoice_user.json`（否则到账无法自动入账）；
   用 `gbt_allinone` 的账本核对历史余额，必要时按 `ledger.jsonl` 逐笔重建。
8. **清幂等缓存**：删除平台侧 `GBT_PLATFORM_IDEM_FILE`（幂等表按服务基址与数据根绑定，
   恢复后继续复用旧缓存会拿到**已不存在的发票号**）。
9. **启动并观察**：先 `-DryRun` 自检，再启动；确认 `health` 200、`pending` 与发票一致；
   执行一次 `scan()` 确认游标继续推进（`cursor.json` 丢失会触发有限回扫，属正常）。
10. **复盘**：记录恢复点(RPO)/恢复耗时(RTO)与差异（人工补记的账目必须留痕）。

---

## 8. 监控与告警

**核心指标（都可从现有接口取，无需改代码）**

| 指标 | 来源 | 建议阈值/动作 |
|---|---|---|
| 服务存活 | `GET /api/gbtwallet/health` 200 且 `ok=true` | 连续 3 次失败 → 告警（`healthcheck.ps1` 退出码 ≠ 0） |
| 未付发票积压 | `health.pending` | 持续增长且无 `scan_done` 事件 → 检查 RPC 与扫描计划 |
| 扫描是否在推进 | `ledger.jsonl` 的 `scan_done.latest`（`GET /events`） | `latest` 长时间不变或与链高差 > 阈值 → RPC 异常告警 |
| 扫描错误 | 事件 `scan_error` | 出现即告警（RPC 限流/节点故障） |
| 过期收到款 | 事件 `fund_received_expired`、`overpay` | 出现即人工介入（资金照实留痕，不静默吞） |
| 账本与钱包侧差异 | 发票 `paid_amount_int` 合计 vs 账本入账合计 | 每日对账，出现差异即冻结相关提现流程 |
| 待审账号/风控 | `GET /api/gbtwallet/ops/review_queue` | 有积压 → 运营处理 |
| 磁盘/备份新鲜度 | 数据根所在卷使用率；最近一次备份时间戳 | 使用率 >80% 或备份 >48h 未更新 → 告警 |

**巡检（建议每 5 分钟）**

```powershell
powershell -ExecutionPolicy Bypass -File gbt_allinone\deploy\healthcheck.ps1 -Json
# 退出码位掩码: 1=钱包HTTP 2=框架自检 4=接轨层; 0=正常
```

**日志**：Windows 服务/任务 → `%GBT_WALLET_DIR%\logs\wallet-*.out|err.log`；systemd → `journalctl -u gbt-wallet`；
Docker → `docker compose logs`（已配置 json-file 滚动）。反向代理访问日志（含客户端 IP）是**对账与审计的
关键证据**，保留 ≥180 天并异地归档。

---

## 9. 回滚步骤

回滚的目标是"恢复到上一个已知良好状态"，且**不丢失已入账资金记录**。

1. **判断类型**：
   - 仅服务/配置问题（新版本起不来、配置写错）→ 走 A。
   - 数据损坏或多进程写坏数据根 → 走 B（按 §7.3 恢复）。
2. **A：配置/版本回滚**
   1. 停止服务（任务/NSSM/systemd/compose）。
   2. 还原上一版代码（`git revert`/切回上个发布目录）与环境文件（保留旧 `GBT_WALLET_API_TOKEN`、`GBT_CORS_ORIGINS`）。
   3. 启动并跑 §6 的冒烟项（health / 401 / 内部路由 403）。
   4. 若回滚涉及**端口或代理上游**变化，同步改反向代理后 `reload`，再验证公网 200。
3. **B：数据回滚**：严格执行 §7.3，且注意：
   - 回滚后**必须**删除平台侧幂等缓存，并对回滚窗口内的链上到账做人工补记（以 `ledger.jsonl` 与链上 tx 为准）。
   - 回滚窗口内已开出的发票地址**不要复用**（`state.json` 计数器只前进不回退）。
4. **回滚后**：跑一次 `scan()` + 一次 `bridge.sync()`，确认发票状态与账本一致；记录时间线与差异。
5. **禁止**：为"让数据看起来一致"而手改 `ledger.jsonl` / `invoices.json` 的历史行；一切修正都以新记录追加。

---

## 10. 已知限制

1. **不广播链上交易**：钱包只做只读扫描与本地记账；提现/转出不在本版本能力内。
2. **单进程文件存储**：数据根是 JSON/JSONL 文件，**不支持多个服务进程同时写**（无文件锁）。
   请确保同一 `GBT_WALLET_DIR` 只被一个服务实例使用。
3. **鉴权是可选的**：未设 `GBT_WALLET_API_TOKEN` 时接口不鉴权，安全性完全依赖"只绑 127.0.0.1"这一条边界。
   任何把 8097 直接暴露到内网/公网的做法都会让接口裸奔。
   ⚠ 反向陷阱：**"设了令牌"不等于"令牌生效"**。若服务进程没加载到接轨层（依赖被裁剪等），`api.py` 会降级为
   原行为（不鉴权），环境变量里的令牌被静默忽略。上线时用 `healthcheck.ps1` 复核 —— 它会主动发一次
   **无令牌**请求，只有被拒(401)才判定鉴权生效，否则以退出码 4 报错（见 §8 巡检）。
4. **令牌是静态共享密钥**：没有签发/过期/吊销机制，等同于平台后端的长期凭据；轮换需改两端并重启。
5. **反向代理不做限流**：钱包层没有速率限制。若公网开放用户面，建议在边缘加限流/防爆破。
6. **RPC 依赖**：公共 Polygon 节点会限流/抖动，扫描按 `max_blocks` 有界推进，长时间停机后需多轮追赶；
   生产请用专用节点。
7. **确认数固定 12**：`CONFIRM_TARGET=12`，小额可下调，但下调会降低重组安全性。
8. **币种白名单**：只识别 `USDC.E / USDC / USDT / WETH`（Polygon）；原生 `MATIC` 只读余额、不收。
9. **CORS 默认 `*`**：与接入前行为一致，仅适合本机；生产必须显式白名单。
10. **账号/OTP 通道是最小实现**：`/account/*` 与 `/ops/*` 为本地台账版，非生产级身份系统。
11. **Windows 计划任务模式**：任务停止不保证杀掉子进程，脚本用"端口占用进程"兜底清理；
    NSSM 模式由服务管理器托管更干净。
12. **Docker 模式**：容器根文件系统只读，任何需要写根路径的改动都会失败；数据只能落 `/data` 卷。
13. **备份一致性**：在线备份非同一时刻快照（见 §7.2），跨文件一致性以 `ledger.jsonl` 为准。
14. **本机解释器差异**：某些打包发行版 Python（例如带 `python3xx._pth` 的嵌入式/内置解释器）
   在隔离路径模式下**不会**把当前目录与 `PYTHONPATH` 放进 `sys.path`，`python -m gbt_wallet.api` 会报
   找不到模块。`deploy/` 内脚本已用"显式 `sys.path` 注入 + runpy"的引导方式规避，
   手工命令请照抄同样的引导写法（见 §4.1 第 1 步）。

---

## 11. 本次交付的自验证据（可复跑）

| 项 | 命令 | 结果 |
|---|---|---|
| 语法编译 | `python -m py_compile gbt_allinone/integration/*.py gbt_allinone/deploy/selfcheck_configs.py` | 退出码 0 |
| 接轨冒烟 | `python gbt_allinone/integration/smoke_test.py` | 13/13 PASS，退出码 0（含真 HTTP 回环 + 401/200 断言） |
| 配置自检 | `python gbt_allinone/deploy/selfcheck_configs.py` | 59/59 通过，退出码 0（compose/Dockerfile/Caddyfile/systemd/env.example/api.py 接入痕迹） |
| PowerShell 语法 | `[ScriptBlock]::Create((Get-Content -Raw <file>))` | 4 个脚本全部 PARSE-OK |
| 启动器 | `run_wallet.ps1 -DryRun` / 真实启动 / 重复启动 | 退出码 0 / 0 / 0（重复启动识别为"已在运行"） |
| 自检脚本 | `healthcheck.ps1 -Port 8099 -Token …` | 四项全绿，退出码 0；无令牌时正确报 401（退出码 1） |
| 备份脚本 | `backup.ps1 -DataDir … -OutDir … -Keep 3 -Zip` | 退出码 0；manifest 含 sha256；ACL 已收紧；数据根内备份被拒绝 |
| 反代/容器配置 | `docker compose config` / `caddy validate` | 本机无 docker/caddy，未实机验证（见交付说明的偏差项）；已用标准库结构校验替代 |

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
