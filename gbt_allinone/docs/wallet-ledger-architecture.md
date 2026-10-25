# GBT 钱包 · 交易所式托管架构

> 定位：**用户钱包 = 内部数字记账；资金实体永远在平台统一资金池；转账 = 账本内划转，仅受用户自身余额约束。**
> 等同中心化交易所（CEX）的账户模型：用户看到的是「数字」，链上钱在平台的池子里。

## 1. 模块

| 路径 | 职责 |
|---|---|
| `gbt_allinone/wallet/hd.py` | 自建 HD 钱包：BIP39 助记词 + BIP44 无限派生（`m/44'/60'/0'/0/i`），纯本地 |
| `gbt_allinone/wallet/rpc.py` | Alchemy RPC **只读**适配（读 `.env` 的 `ALCHEMY_RPC_URL`；未配置不联网） |
| `gbt_allinone/wallet/consolidate.py` | 扫子地址余额 -> 规划归集到主地址（**dry-run**） |
| `gbt_allinone/ledger/core.py` | 内部账本：开户/入金/划转/出金/余额/核账；append-only、余额派生 |
| `gbt_allinone/ledger/pool.py` | 统一资金池：分配充值地址、链上入金 -> 记账到用户 |
| `gbt_allinone/examples/wallet_ledger_demo.py` | 全离线端到端演示 |

## 2. 数据流

```
用户 A                        平台                            用户 B
  |  转账到 A 的充值地址         |                               |
  +------------------------->  | 扫链检测进账 (rpc+consolidate)   |
  |                            | pool.credit_deposit()          |
  |                            | ledger: A 贷方 +100            |
  |  A 发起「转账给 B 30」        |                               |
  +------------------------->  | ledger.transfer(A,B,30)        |
  |                            |  校验 A 余额>=30 -> A借30/B贷30  |
  |                            |  (链上不动钱，仅记账)            |
  |  A 发起「提现 10 到链上地址」  |                               |
  +------------------------->  | ledger.withdraw() 扣账          |
  |                            | 真广播由执行模块负责(默认dry-run)  |
```

要点：

- **链上资金 = 平台池**（充值地址归集到池地址）；**用户余额 = 账本数字**。
- 转账**不触碰链**，因此即时、低费；只有**充值/提现**才与链交互。

## 3. 账本规则

- **复式记账**：每笔转账产生两条条目（`direction=debit` / `credit`），`ref` 相同。
- **append-only**：只追加，不修改历史；`store/ledger.jsonl` 即审计流水。
- **余额派生**：余额 = 该用户该资产所有条目之和；不单独存余额，杜绝不一致。
- **余额不足拒绝**：转账/提现前校验，不足抛 `InsufficientBalance`。
- **不允许负余额**；金额用 `Decimal`、以字符串序列化，避免浮点误差。
- **核账 `verify()`**：校验 ①无负余额 ②资产守恒（用户余额合计 = 充值 - 提现）。

## 4. 框架能力

`ledger_open_account` · `ledger_deposit` · `ledger_transfer` · `ledger_balance` ·
`ledger_withdraw`（默认 dry-run）· `pool_assign_address` · `ledger_verify` ·
`wallet_new` · `wallet_derive` · `wallet_rpc_status`

```powershell
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as gbt;print(gbt.run_task('ledger_deposit',{'user':'alice','asset':'USDT','amount':'100'}))"
python gbt_allinone/examples/wallet_ledger_demo.py
```

## 5. 安全边界

- 提现**默认 dry-run**、不广播；真广播需执行模块且显式确认。
- 助记词**从不打印明文**（默认打码）；`gbt_allinone/store/`（账本/钱包）已进 `.gitignore`。
- Alchemy Key 只放 `.env`，不写源码、不进版本库。

## 6. 待接（需 Alchemy 端点）

`.env` 写入 `ALCHEMY_RPC_URL=https://<net>.g.alchemy.com/v2/<KEY>` 后：
链上只读（`chain_id` / `balance` / `nonce`）、充值检测 -> 自动记账、扫账归集计划。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
