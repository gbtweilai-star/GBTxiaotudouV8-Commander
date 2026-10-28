# 19 · 量化金融 (`finance`)

> 5 能力位 · 策略信号 · 回测 · 参数读取 · 平台画像
>
> 框架只收AI能力本体；资金/钱包/支付等业务模块不入框架。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 框架/业务边界（铁律9）

**框架只收AI能力本体**：资金/钱包/支付等业务模块**不入框架**，由独立服务（`gbt_wallet/`，8097端口HTTP API）承载，框架经`integration/platform_client.py`对接。

## 能力清单

| 能力位 | 说明 |
|---|---|
| `quant_strategy` | 读取真实量化引擎，返回策略信号/仓位模型 |
| `quant_backtest` | 读取真实回测API，返回类/函数/默认参数 |
| `quant_params` | 读取真实数值型策略参数（动量/ATR/止损） |
| `platform_profile` | 读取量化项目结构（真实测绘） |
| `quant` | 量化入口（合并平台画像+引擎参数） |
| `quant_plan` | 压缩与直达（体积估算+车道映射） |

## API参考

### 策略信号

```python
import gbt_allinone as gbt

result = gbt.run_task("quant_strategy", {"symbol": "BTC/USDT"})
# 返回: {
#   ok, symbol: "BTC/USDT",
#   signal: "buy",       # buy/sell/hold
#   confidence: 0.72,
#   position: {size: 0.15, leverage: 2, stop_loss: 0.05},
#   source: "quant_tech.engine"
# }
```

### 回测

```python
result = gbt.run_task("quant_backtest", {
    "strategy": "momentum",
    "start": "2025-01-01",
    "end": "2026-01-01"
})
# 返回: {
#   ok, returns: 0.34, max_drawdown: -0.12,
#   sharpe: 1.8, win_rate: 0.58, trades: 240
# }
```

### 策略参数

```python
result = gbt.run_task("quant_params", {})
# 返回: {
#   ok, params: {
#     momentum_period: 20,
#     atr_period: 14,
#     stop_loss_pct: 0.05,
#     take_profit_pct: 0.15
#   }
# }
```

### 平台画像

```python
result = gbt.run_task("platform_profile", {})
# 返回: {
#   ok, structure: {modules: [...], entry: "main.py", deps: [...]}
# }
```

## 外部模块依赖

这些能力依赖外部业务模块 `quant_tech`：

```python
# 未挂载时如实报缺口
result = gbt.run_task("quant_strategy", {})
# 返回: {
#   ok: false,
#   status: "needs_dependency",
#   missing: "quant_tech",
#   detail: "quant_strategy 属于外部业务模块 quant_tech，本框架不内置分发；"
#           "把该模块挂回 gbt_allinone/ 即自动可用"
# }
```

**设计原则**：框架本体保持纯粹，业务模块不内置分发。模块挂回→正常调用；不在场→如实返回`needs_dependency`，**绝不伪造结果、也绝不假装能力不存在**。

## 压缩与直达（quant_plan）

### 压缩体积估算

```
每档 bits/weight ⇒ 估算体积（27B × b/w ÷ 8 × 容器开销1.3）⇒ 能否落在8GB级
```

| 量化档 | bits/weight | 体积 | 保留精度 |
|---|---|---|---|
| FP16 | 16 | ~54GB | 100% |
| Q8 | 8 | ~27GB | 99.5% |
| Q4 | 4 | ~13.5GB | 98% |
| IQ2_XXS | 2.06 | ~7GB | 92% |
| **ternary PTQ1_0** | **1.75** | **7.67GB** | **98.2%** |

**关键读数**：ternary PTQ1_0 保留98.2% FP16精度，同体积胜IQ2_XXS 12分。

### 直达路线

```
意图 ⇒ 能力位 ⇒ 车道 ⇒ 端点，每步都有固定落点、不经本机中转
```

**铁律**：本地不承载任何大模型，端点不许写`127.0.0.1`。

## 安全边界

- 量化能力只读，不下单、不动资金
- 资金操作走独立服务（`gbt_wallet/`），需 `owner_control` 授权
- 框架内无转账/支付执行路径

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
