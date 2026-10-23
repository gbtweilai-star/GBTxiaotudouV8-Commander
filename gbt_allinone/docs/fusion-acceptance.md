# GBT 全能小土豆 · 融合验收报告

> 目标：把两个项目彻底融合成"完全属于自己的框架"，吸收原有能力，桌面 APP 形态可运行。
> 本文件是**验收依据**：逐条给出"验收标准 -> 现状 -> 证据"。

## 1. 模块地图（工作区 Desktop\Autoclaw）

| 模块 | 角色 | 状态 |
|---|---|---|
| `gbt_allinone/` | 统一框架：统一接口 + 能力注册表 + 审计后台 + 量化技术层 + 钱包/账本 | 运行中 |
| `gbt_allinone/wallet/` | 自建 HD 钱包（BIP39/BIP44）+ Alchemy RPC 只读 + 归集计划 | 接通 |
| `gbt_allinone/ledger/` | 交易所式内部账本 + 统一资金池 + 冻结/解冻（AML） | 运行中 |
| `gbt_allinone/adapters/` | Workspace 量化适配 + **gbt_wallet 收款适配** | 接通 |
| `gbt_wallet/` | 旧收款钱包（发票/收款地址/链上扫描入账）+ tests | 已并入 63/63 |
| `caps/eigenflux/` | gbt_wallet 的可选 side-adapter 依赖 | 已并入 |

## 2. 能力清单（统一接口，32 项）

- 基础/量化：health, echo, count_words, audit_query, quant_strategy, quant_backtest, quant_params, platform_profile
- 自建钱包：wallet_new, wallet_derive, wallet_rpc_status
- 内部账本：ledger_open_account, ledger_deposit, ledger_transfer, ledger_balance, ledger_withdraw, ledger_freeze, ledger_unfreeze, ledger_frozen, ledger_verify, pool_assign_address
- 收款钱包：receive_status, receive_init, receive_new_address, receive_invoice, receive_list, receive_scan, receive_balances
- 预留：vision, voice, browser, quant

## 3. 验收标准对照

| 验收项 | 现状 | 证据 |
|---|---|---|
| 源代码融合完成 | 两项目能力并入统一接口 | `gbt_allinone` 32 能力；`receive_*` 驱动 `gbt_wallet` 实测 |
| 付费功能去除 | 原 AutoClaw 付费模块未纳入；框架零付费门 | 框架为自建，无许可校验代码 |
| 桌面 APP 可运行 | 提供 CLI/API 与 GUI 入口 | `powershell -ExecutionPolicy Bypass -File launch-gui.ps1`；GUI 见 app.py（需自带 tkinter 的解释器，见 §5）；CLI 用 `python -c "import sys;sys.path.insert(0,'.');from gbt_allinone.cli import main;main(['list'])"` |
| AI 框架能力整合 | 统一接口 + 适配器 | `gbt.run_task(...)`；adapters/ |
| 文档完备 | README + docs/ | `docs/wallet-ledger-architecture.md`, 本文件 |
| 数据后台可追踪 | append-only 审计 + 账本 | `gbt_allinone/store/audit.jsonl`, `ledger.jsonl` |
| 原有能力不丢 | 只移动不删除 + 旧钱包整体并入 | `gbt_wallet` 63/63；分离归档见 DELIVERY |

## 4. 实测证据（可复跑）

```powershell
cd C:\Users\ADMIN\Desktop\Autoclaw
python gbt_allinone\tests\test_framework.py        # 10/10
python gbt_allinone\examples\wallet_ledger_demo.py # DEMO_OK
python gbt_allinone\examples\rpc_check.py          # RPC_OK (chain_id=1)
python -c "import sys;sys.path.insert(0,'.');from gbt_allinone.app import main;main()"   # 桌面壳：起不来会打印根因
powershell -ExecutionPolicy Bypass -File launch-gui.ps1   # 桌面壳：自动挑解释器启动
# 收款钱包(需先设 GBT_WALLET_PASS/GBT_WALLET_DIR)
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as g;print(g.run_task('receive_invoice',{'amount':2.5}))"
```

## 5. 假设与边界

假设：
- 数据根 `gbt_allinone/store/`（含账本/钱包）已 gitignore，不入库。
- 收款链为 Polygon（沿用旧钱包设定）；自建钱包 RPC 为 Ethereum Mainnet（用户提供）。
- GUI 需要「自带 tkinter 的解释器 + customtkinter」两个条件同时满足。本机默认 `python`
  （AutoClaw 自带解释器）**不含 tkinter**，用它跑桌面壳不弹窗（实测回退为文字提示）；
  已实测本机存在可用解释器并跑通界面构建（见下方证据）。启动请用 `launch-gui.ps1`。

不可逾越边界（与是否自用/商用无关）：
- 不解除第三方付费墙（许可规避）。
- 不把 键鼠监听/无授权远控/数据劫持/设备接管/资产锁定要挟/付费墙绕过/社工渗透 做成可执行能力。
- 冻结仅作用于**平台托管余额**；不做"托管用户外部钱包私钥"或"无期限追溯追回"。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
