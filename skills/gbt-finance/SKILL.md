---
name: gbt-finance
displayName: GBT 量化职业域 · 用法规程
version: 1.0.0
description: GBT小土豆V8 的 `finance` 职业域用法规程 —— 图鉴里这个域只有 4 个能力位（`quant` / `quant_strategy` / `quant_backtest` / `quant_params`），四个全是**只读、免授权、不要参数**，走的是同一个万能插门（`five-dim.py cap` → `run_task`）。本规程逐位写清「用途 / 要不要授权 / 怎么调（真命令）/ 要什么参数 / 返回哪些字段 / 失败长什么样 / 耗时」，并附一份**真跑出来的诚实账**：`quant_strategy` 曾报 `dataclasses: []` 而文件里真有 dataclass、
`quant_backtest` 的 `class\s+(\w+)` 曾把字面量 `class` 当类名抓走（**这两处提取器缺陷已于 2026-09-22 修回源码，文件开头有修前/修后对照**）、
`quant_backtest` 的 `default_params` 抓出 `"10000.0):"` 这种明显读错地方的碎片（**未修，仍不可信**）、中文目录名在 PowerShell 管道里显示成乱码但数据本身是好的。**这不是投资建议**：本规程只讲怎么调工具、读数怎么念，任何回测/参数数值都不构成收益承诺。当用户说「跑个量化」「看策略信号」「回测」「引擎参数」「这个域有什么能力」，或要看量化读数却怀疑读错了地方时使用。
triggers:
  - "量化"
  - "回测"
  - "策略信号"
  - "仓位模型"
  - "引擎参数"
  - "动量"
  - "ATR"
  - "止损"
  - "quant"
  - "finance 域"
  - "投资建议"
---

# GBT 量化职业域 · 用法规程（`finance`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> `gbt-omni` 负责「人话落到哪个能力位」，本规程负责**这一个域**：
> **怎么调、读哪个字段、什么时候是读错了地方、什么话不许说**。

---

## 🔴 先读这一条：本文件里有**两处"已修的历史记录"**

写这份规程时（2026-09-22）真跑出来的两个**提取器缺陷**，**当天已经修回源码了**，不是留在纸上：

| 缺陷 | 修前（实测） | 修后（实测） |
|---|---|---|
| `_extract_dataclass_fields` 要求**类体首行以 `\w` 开头** ⇒ docstring 开头的类整块失配 | `cis_quant_engine` → `"dataclasses": []`（**假空**） | `[('CISPosition',[symbol,direction,entry_price,…]), ('CISConfig',[momentum_lookback,…])]`；另一个文件也补回报出 `SystemConfig` |
| `class\s+(\w+)` **没有行锚** ⇒ 从 `@dataclass` 里的 `dataclass` 起匹配，抓走下一行字面量 `class` | `backtest_engine_v3.py` → `['class','class','BaseStrategy',…]`（**2 条垃圾 + 漏 2 个真类**） | `['Position','Trade','BaseStrategy','MACDStrategy','RSIStrategy','BollingerStrategy','KDJStrategy','ATRStopStrategy','QuantEngine']`（与源码逐名一致） |

修处：`gbt_allinone/quant_tech.py`（两处正则都加了注释写明"为什么错、错在哪、证据是什么"）。

⚠️ **下面 §4.1 与 §2.3 保留的是"修前"的现场记录** —— 它们现在的作用是**这条红线的由来与证据**，
**不是当前行为**；拿本文件教人时，**别把修前的样子当成现在会看到的样子**。
**纪律不变**：`[]` 与"看起来是参数"的东西一律**回源码复核**（`backtest_api_v3.py` 真没有类，
它的 `[]` 是**真空** —— 同一个 `[]`，两种性质，这正是 §4.1 要教的）。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
python tools/codex-scripts/five-dim.py cap quant              # 总入口：工作区画像 + 引擎参数
python tools/codex-scripts/five-dim.py cap quant_strategy     # 策略/信号模型（enum + dataclass）
python tools/codex-scripts/five-dim.py cap quant_backtest     # 回测 API/引擎的类·函数·参数线索
python tools/codex-scripts/five-dim.py cap quant_params       # 引擎数值型参数
```

**口径以 `cap` 的实时输出为准**，本文件只是导读。图鉴里这个域**只有这 4 个位**
（以 `state/skill_atlas.json` 中 `domain == "finance"` 的 `kind` 为准），**一个不多一个不少**。

---

## 0. 一句话总表（4 个位，全部只读免授权）

| 能力位 | 用途 | 门 | 要参数吗 | 实测耗时 | 数据真身 |
|---|---|---|---|---|---|
| `quant` | 总入口：工作区画像 + 引擎数值参数 | **无作用域** | 否 | **0.353s** | `platform_profile()` + `quant_params()` |
| `quant_strategy` | 策略信号 / 仓位模型（枚举 + dataclass） | **无作用域** | 否 | **0.250s** | `cis_quant_engine.py` · `cis_harvesting_system_v2.py` |
| `quant_backtest` | 回测 API/引擎的类·函数·默认参数线索 | **无作用域** | 否 | **0.251s** | `backtest_api_v3.py` · `backtest_engine_v3.py` |
| `quant_params` | 引擎数值型策略参数（动量/ATR/止损） | **无作用域** | 否 | **0.234s** | 同上两个引擎文件 |

四个位的图鉴读数**完全一致**：`enabled=true` · `safe=true` · `needs_confirmation=false` ·
`requires_params=[]` · `params_hint=""` · `channel="omnipulg"` · `disabled=false`。
⇒ **四个都能直接跑，都不需要主人发授权，都不收参数。**

**这四个位读的都是 `C:\Users\ADMIN\Desktop\Workspace` 下的真文件，不是本仓的文件**：

```
01_量化收割引擎/cis_scalper/cis_quant_engine.py          26398 字节（磁盘）· 707 行
01_量化收割引擎/cis_harvesting/cis_harvesting_system_v2.py 29340 字节（磁盘）
01_量化收割引擎/backtest/backtest_api_v3.py                2704 字节（磁盘）·  82 行
01_量化收割引擎/backtest/backtest_engine_v3.py            11510 字节（磁盘）
```

> ⚠ **路径是写死在代码里的**（`gbt_allinone/quant_tech.py` 顶部 `WS = Path(r"C:\Users\ADMIN\Desktop\Workspace")`），
> **不是本仓库的工作区**。换机器 / 换用户名 → 这四个位会从"ok"变成"文件全不在"，见 §3 失败典型。

---

## 1. 总共就一道门：`run_task`

四位都走同一个门，没有别的入口：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位>          # 本规程用的形式
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> '{...}'  # 这四位都不需要这个
```

**真跑出来的门读数（四个位逐个实测，读数一致）**：

```json
{ "gate": "run_task", "kind": "<能力位>", "status": "ok", "stamp": true, "denied": false, "result": { ... } }
```

### 1.1 为什么说"无作用域"：静态查的，不是猜的

```python
from gbt_allinone.security import policy
d = policy.evaluate("quant_strategy", {})     # 只读求值，不执行
d.risk        # 'low'
d.scopes      # ()            ← 空
d.restricted  # False
d.action      # 'quant_strategy'
d.allow_private  # False
```

四个位**逐个查过**，读数完全一样：`risk='low'` · `scopes=()` · `restricted=False`。

**但有一句必须说清（这是读对地方的关键）**：`policy.py` 里 **根本没有 `quant*` 分支** ——
在那个文件里 grep `quant` **零命中**。所以它们是**落到默认放行分支**（第 123-141 行：
`scopes` 为空 ⇒ `risk='low'`），**不是因为有一条"这几个是只读"的白纸黑字规则**。
"免授权"在这四位上是**规则缺席**的结果，不是**显式声明**的结果 ——
将来谁给 `quant*` 加了分支，这里的结论就要重查，**不许把本文件当永久凭证**。

### 1.2 `missing_scopes` / `reason` / `how_to_grant` 为什么本规程里没有

任务口径要求"要授权的照 `cap` 打印的 `missing_scopes / reason / how_to_grant` 如实写"。
**如实写出来就是：这四个位都不需要授权，所以这三个字段一个都没有出现。**

依据（`tools/codex-scripts/five-dim.py` 第 124-128 行）：这三个字段**只在 `denied` 为真时才写进输出**：

```python
if denied:
    out["missing_scopes"] = gr.get("missing") or gr.get("missing_scopes") or []
    out["reason"] = str(gr.get("reason") or gr.get("message") or "")[:200]
    out["how_to_grant"] = gr.get("how_to_grant") or []
```

而四个位实测全是 `denied: false` ⇒ 走不到那一段。**不是我漏抄，是它们不存在。**
**编三个字段出来才是造假。**

**万一将来被拒（真出现 `denied: true`）时怎么办（这一段是规矩，不是读数）**：
照 `cap` 打印的原文把缺的作用域抄进报告，**命令只打印不绕门**；
授权只能主人在终端发（`python -m gbt_allinone auth grant --scope <scope> --ttl 600`），
**AI 永远无权给自己发授权，不许找旁路，不许改 `security/policy.py`。**

---

## 2. 逐位规程（用途 / 怎么调 / 参数 / 真实返回 / 失败典型）

### 2.1 `quant` —— 总入口

**用途**：一次拿两样东西 —— **工作区画像**（`profile`）+ **引擎数值参数**（`engine_params`）。
组合逻辑在 `gbt_allinone/api.py:918-923`：`platform_profile()` 与 `quant_params()["engine_params"]` 拼成一个返回。

**怎么调**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap quant
```

**要什么参数**：**不要**（`requires_params: []`）。

**它读哪些数据**：
- `profile.workspace` 走 `gbt_allinone/tools/scan_scope` 的**唯一扫描口径**（剪枝发生在进入子目录之前），
  只算本仓代码面，并**把被排除的量一并报出来**（`py_excluded`）—— 免得"数字变小了却说不清小在哪"；
- `engine_params` 直接来自两个引擎文件的**源码字面量**（与 `quant_params` 同源）。

**真跑返回的关键字段（2026 实测）**：

| 字段 | 实测读数 |
|---|---|
| `result.profile.workspace` | `C:\Users\ADMIN\Desktop\Workspace` |
| `result.profile.exists` | `true` |
| `result.profile.top_level_dirs` | **15 项**：`.gbt_bridge_staging` `.playwright-cli` `.tripo` `.wrangler` `00_镜像独有文件提取_20260913` `01_量化收割引擎` `02_GBT兑换与主平台` `03_收款钱包与支付` `04_平台构建与验收脚本(开发产物)` `05_资金管道设计_2026-09-09` `__pycache__` `deploy_bundle_v1` `output` `pet-run-gbt` `work` |
| `result.profile.quant_py` | **23**（`01_量化收割引擎/` 下的 .py 数） |
| `result.profile.py_total` | **167**（Workspace 本仓代码面的 .py 数） |
| `result.profile.py_excluded` | `{}`（本机没有可排除的语料目录；**空不是"没这项功能"**） |
| `result.engine_params` | 两个文件共 **23** 个数值参数，见 §2.4 |

**跑多久**：**0.353s**（实测；含目录遍历。`platform_profile` 自带 **30 秒 TTL 缓存**，
高频连调时从第二次起会明显更快 —— 但 `cap` 每次是新进程，缓存**跨进程不生效**，所以别指望 `cap` 变快）。

**失败典型长什么样**：

```json
{ "ok": false, "status": "needs_dependency", "missing": "quant_tech",
  "capability": "quant",
  "detail": "quant 属于外部业务模块 quant_tech，本框架不内置分发；把该模块挂回 gbt_allinone/ 即自动可用",
  "reason": "<ImportError 摘要>" }
```

来源：`api.py:27-47` 的 `_external_capability()`。**这是"如实报缺口"，不是崩溃** ——
`quant_tech` 不在场时框架**绝不伪造结果、也绝不假装能力不存在**。
`exists=false` + `top_level_dirs=[]` + `quant_py=0` + `py_total=0` 是"Workspace 路径不在"的样子，
**不是"工作区是空的"** —— 两件事别读混。

---

### 2.2 `quant_strategy` —— 策略信号 / 仓位模型

**用途**：从量化引擎源码里抓 **enum 类与其成员**（信号/方向模型）、**`@dataclass` 类与字段**（持仓/配置模型）、文件字节数。

**怎么调**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap quant_strategy
```

**要什么参数**：**不要**。

**真跑返回的关键字段（2026 实测）**：

```json
{ "engine_files": ["cis_quant_engine.py", "cis_harvesting_system_v2.py"],
  "models": {
    "cis_quant_engine": {
      "enums": [
        {"enum": "CISDirection",    "members": ["LONG", "SHORT", "HOLD"]},
        {"enum": "CISEnterSignal",  "members": ["MOMENTUM_BREAKOUT", "PULLBACK_ENTRY", "TREND_FOLLOWING"]},
        {"enum": "CISExitSignal",   "members": ["STOP_LOSS", "TAKE_PROFIT", "TREND_REVERSAL", "TIME_EXIT"]}
      ],
      "dataclasses": [], "bytes": 25691 },
    "cis_harvesting_system_v2": { "enums": [], "dataclasses": [], "bytes": 28498 } } }
```

**怎么念这几个字段**（这才是"读对地方"）：

- **`enums` 是真读数**，且**自洽可验**：3 个枚举 × 成员，进出场信号名一眼能对上语义
  （进场 3 种：动量突破 / 回调入场 / 趋势跟随；出场 4 种：止损 / 止盈 / 趋势反转 / 时间退出）。
  **这是"引擎源码里声明了哪些信号种类"，不是"现在发出的是哪个信号"。**
- **⚠ `bytes: 25691` ≠ 磁盘 26398 字节** —— 差值 **707**，正好等于该文件的 **707 行**。
  原因：`read_text()` 走通用换行，**CRLF 被折成 LF**，每行少 1 字节。
  ⇒ `bytes` 是**文本编码后的字节数**，不是文件大小。**拿它当磁盘占用就是读错了地方。**
- **⚠ `dataclasses: []` 是提取器的漏，不是事实** —— 见 §4.1，**这一格不许当"没有 dataclass"用**。
- `cis_harvesting_system_v2` 的 `enums: []` 经复核**是真没有**（该文件 `(Enum)` 出现 0 次），
  与 `cis_quant_engine` 的"假空"性质**完全不同**。**同样是 `[]`，一个真一个假 —— 这就是必须复核的理由。**

**跑多久**：**0.250s**（实测）。

**失败典型长什么样**：两个文件都不在 ⇒ `{"status": "no_engine_found", "hint": "<WS 路径>"}`。
**只有一个文件在时不报错**：`engine_files` 只列存在的那个，`models` 里也只出现那一个键 ——
**"少了一个引擎"不会报错，只会静默少一项**，所以**必须看 `engine_files` 有幾项**，别只看有没有报错。

---

### 2.3 `quant_backtest` —— 回测 API / 引擎

**用途**：抓回测模块的**类名、函数名、参数线索**（正则粗提，非 AST）。

**怎么调**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap quant_backtest
```

**要什么参数**：**不要**。

**它读哪些数据**：`01_量化收割引擎/backtest/` 下两个文件。其中 `backtest_api_v3.py`（82 行）
是一个 **FastAPI 服务**：`health_check` / `list_strategies` / `run_backtest_endpoint` / `get_history` /
`get_history_item` / `delete_history` / `compare_strategies`，末尾 `uvicorn.run(app, host="0.0.0.0", port=8088)`。
`backtest_engine_v3.py` 是策略实现（`BaseStrategy` / `MACDStrategy` / `RSIStrategy` / `BollingerStrategy` /
`KDJStrategy` / `ATRStopStrategy` / `QuantEngine`）。

**真跑返回的关键字段（2026 实测，节选）**：

```json
{ "backtest_modules": [
  { "file": "backtest_api_v3.py", "classes": [],
    "functions": ["health_check","list_strategies","run_backtest_endpoint",
                  "get_history","get_history_item","delete_history","compare_strategies"],
    "default_params": {"symbol": "\"BTCUSDT\"", "initial_capital": "10000.0):",
                       "try": "run_backtest(strategy_id"} },
  { "file": "backtest_engine_v3.py",
    "classes": ["class","class","BaseStrategy","MACDStrategy","RSIStrategy",
                "BollingerStrategy","KDJStrategy","ATRStopStrategy","QuantEngine"],
    "functions": ["__init__","generate_signal","_calc_rsi","_calc_atr","run_backtest","_gen_prices","main"],
    "default_params": {"stop_loss": "(price - pos.entry_price) * pos.quantity",
                       "pnl": "0", "float": "[]", "Dict": "self.capital",
                       "1": "np.std(daily_returns)", "0": "(np.mean(daily_return" } } ] }
```

**🔴 这三个字段的可靠性完全不同，别一视同仁**：

| 字段 | 能不能信 | 为什么 |
|---|---|---|
| `functions` | **基本可信**（真函数名，含 `__init__` 等噪声） | `def\s+(\w+)`，函数定义语法稳定 |
| `classes` | **不可信** | 见下 |
| `default_params` | **不可信，明显读错地方** | 见下 |

- **`classes` 里的字面量 `"class"` ×2 是正则缺陷的铁证**（**已于 2026-09-22 修**，见文件开头那条）：
  修前 `class\s+(\w+)` 撞上 `@dataclass\nclass Position:` 时会从 `dataclass` 尾部的 `class` 起匹配、
  把下一行的 `class` 当类名抓走 ⇒ 抓到字面量 `"class"`，
  **而 `@dataclass` 装饰的真类名（`Position` / `Trade`）反而丢了**。修前实测 `classes` 9 项里
  **有 2 项是垃圾、还漏了 2 个真类** ⇒ 修后与源码逐名一致。
  **这条教训仍然成立**：一旦某格出现"字面量当名字"这种味道，**先怀疑提取器，别怀疑数据**。
- **`default_params` 抓出 `"initial_capital": "10000.0):"`、`"try": "run_backtest(strategy_id"`、
  `"1": "np.std(daily_returns)"`、`"float": "[]"`** —— 这些**根本不是参数**，
  是正则 `(\w+)\s*:\s*[A-Za-z_][\w.]*\s*=\s*([^\n,]+)` 在**类型注解、函数默认值、表达式**上乱切出来的碎片。
  唯一勉强对得上的是 `"symbol": "\"BTCUSDT\""`（对应 `backtest_api_v3.py:46` 的
  `symbol: str = "BTCUSDT"`）与 `"initial_capital"` 的**名字**（值 `10000.0` 被截成 `"10000.0):"`）。
  ⇒ **`default_params` 只能当"这里有这么个名字"的线索，值一律回源码核对。**

**跑多久**：**0.251s**（实测）。

**失败典型长什么样**：两文件都不在 ⇒ `{"backtest_modules": []}`。
**它不抛错、不报缺** —— 空列表就是"一个都没读到"。**别把空列表读成"没有回测系统"**，
先确认 `C:\Users\ADMIN\Desktop\Workspace\01_量化收割引擎\backtest\` 在不在。

**⚠ 未验**：**本规程没有真跑过一次回测。** 跑回测要起 uvicorn 服务 / 执行引擎代码
（= `process_execute`，还要读行情数据），**超出"只读免授权"的范围，我不擅自做** ——
所以"回测跑起来要多久 / 输出什么格式的结果"这一格**写「未验」，不编**。
本规程只对"`cap quant_backtest` 能读到什么"负责。

---

### 2.4 `quant_params` —— 引擎数值型参数

**用途**：抓引擎源码里**顶格的数值型参数声明**（动量周期 / 阈值 / ATR / 止损倍数 / 仓位比例）。

**怎么调**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap quant_params
```

**要什么参数**：**不要**。

**真跑返回的关键字段（2026 实测，全量 23 项）**：

`result.engine_params["cis_quant_engine.py"]`（15 项）：
`momentum_lookback=14.0` · `momentum_threshold=0.03` · `atr_period=14.0` · `sl_atr_multiplier=1.5` ·
`max_sl_pct=0.05` · `add_position_threshold=0.02` · `add_position_pct=0.3` · `max_additions=3.0` ·
`max_hold_days=3.0` · `min_profit_target=0.03` · `base_position_pct=0.1` · `max_position_pct=0.3` ·
`high_watermark=0.0` · `atr=0.0` · `pnl_pct=0.0`

`result.engine_params["cis_harvesting_system_v2.py"]`（8 项）：
`CIS_MOMENTUM_PERIOD=14.0` · `CIS_MOMENTUM_THRESHOLD=0.03` · `CIS_MAX_HOLD_DAYS=3.0` ·
`CIS_BASE_POSITION=0.1` · `CIS_MAX_POSITION=0.3` · `INITIAL_CAPITAL=100000.0` ·
`RISK_PER_TRADE=0.02` · `UPDATE_INTERVAL=5.0`

**怎么念（这里最容易读错）**：

- 抓的是 `^\s*(\w+)\s*:\s*(?:int|float)\s*=\s*([0-9.]+)` ——
  **只抓"名字: int|float = 数字"顶格写法**，`int`/`float` 之外的注解一律漏掉。
- ⇒ 它是 **"源码里写了哪些字面量"，不是"当前生效的配置"**。
  `high_watermark=0.0` / `atr=0.0` / `pnl_pct=0.0` 三个明显是**运行时状态字段的初值**，
  混在策略参数里 —— **别把它们念成"策略参数被设成了 0"**。
- 两个引擎里**同一批语义参数各有一套**（`momentum_lookback` vs `CIS_MOMENTUM_PERIOD`，
  `max_hold_days` vs `CIS_MAX_HOLD_DAYS`）：**值一致（14 / 3）但名字不同**。
  ⇒ 读数时要**指出是哪一份引擎的**，不能混着念成"系统参数是 14"。
- **注意口径**：这里的 `cis_quant_engine.py` 参数是 `quant_params()` 抓的，
  与 `quant` 总入口 `result.engine_params` 里那份**是同一份数据**（同一次调用同一个函数），
  **不是两份互相印证的独立证据** —— 别拿它"交叉验证"出虚假的可靠性。

**跑多久**：**0.234s**（实测，四个位里最快）。

**失败典型长什么样**：文件不在 ⇒ 该文件的键**整个消失**（不报错、不占位）；
两个都不在 ⇒ `{"engine_params": {}}`。
**空字典是"一个文件都没读到"，不是"引擎没有数值参数"。**

---

## 3. 四位的失败典型 · 一页速查

| 现象 | 真因 | 怎么念 |
|---|---|---|
| `status: needs_dependency` · `missing: quant_tech` | 外部业务模块 `quant_tech` 没挂回 `gbt_allinone/` | **如实报缺口**，不是崩溃，也**不是"能力不存在"** |
| `exists: false` + 全 0 | `C:\Users\ADMIN\Desktop\Workspace` 不在（换机/换用户名） | 是**路径不在**，不是"工作区是空的" |
| `no_engine_found` + `hint` | 两个引擎文件都不在 | 照 `hint` 给的路径去核对 |
| `engine_files` 只 1 项 | 其中一个引擎文件不在 | **静默少一项，不报错** —— 必须数项数 |
| `backtest_modules: []` | 回测目录不在 | 是"一个都没读到"，不是"没有回测系统" |
| `dataclasses: []` | **可能是提取器漏了**（§4.1） | **先复核源码再下结论** |
| `default_params` 里的怪值 | 正则乱切（§2.3） | **回源码核对，不许当契约** |
| 中文目录名显示成 `����` | PowerShell 管道解码口径 | **数据本身是好的**（§4.2） |

---

## 4. 🔴 读数陷阱（**这三条是真跑出来的，不是想象**）

> **报告层红线**：读数出口前**先问一句「这是事实，还是我读错了地方」**。
> 下面三条全是"看起来像事实、实际是读错地方"的实例 —— **它们就是这条红线的由来**。

### 4.1 `dataclasses: []` 是假的（提取器漏了，文件里真有）—— **已修，此处为现场记录**

`quant_strategy` 对 `cis_quant_engine.py` 报 **`"dataclasses": []`**。
**但那种文件里真有 2 个 `@dataclass`**：

```
@dataclass
class CISPosition:      # CIS持仓模型
@dataclass
class CISConfig:        # CIS交易配置
```

**为什么漏**：提取正则要求类体**第一行就以 `\w` 开头**：

```python
r"@dataclass\s*\nclass\s+(\w+):\n((?:[ \t]+\w+.*\n)+)"
```

而这两个类的**首行都是文档字符串（`"""CIS持仓模型"""`）或注释**，`"` 和 `#` 都不是 `\w`
⇒ **整块匹配失败**，于是报 `[]`。

**实测对照**：`re.findall(r"@dataclass[^\n]*\nclass\s+(\w+)", t)`（放宽版）→ `['CISPosition', 'CISConfig']`；
严格版 → **命中 0**。**同一份文件，两个正则给出相反结论。**

**纪律**：见到 `dataclasses: []` **不许直接写成"这个引擎没有 dataclass"** ——
要么回源码数一遍，要么写"提取器报空，未复核"。
**这格是本域最容易被念反的一处。**

### 4.2 中文目录名的"乱码"是抓取口径，不是数据坏了

在 PowerShell 里直接看 `cap quant` 输出，`top_level_dirs` 里中文项显示成：

```
"00_��������ļ���ȡ_20260913"
```

**先别急着报"工具把中文搞坏了"。** 实测复核（把值直接从 Python 里取出来、用 UTF-8 自己落盘再读回）：

```
['00_镜像独有文件提取_20260913', '01_量化收割引擎', '02_GBT兑换与主平台', '03_收款钱包与支付', ...]
has U+FFFD: False
```

⇒ **数据本身完全正确，没有 U+FFFD**；乱码只发生在**我这层管道的解码口径**里
（设了 `[Console]::OutputEncoding = UTF8` 也没纠正过来，重定向到文件读回仍是 U+FFFD ——
说明乱码是在 PowerShell 接管管道那一跳产生的）。
**判据**：要读中文目录名，**别信终端显示**，用 Python 取 `platform_profile()['top_level_dirs']` 自己落盘核对。

### 4.3 `bytes` 不是磁盘字节数

`quant_strategy` 报 `bytes: 25691`，磁盘上 `cis_quant_engine.py` 是 **26398 字节**。
差值 **707 = 该文件行数**（CRLF→LF 每行少 1 字节）。
⇒ 这个字段是**文本编码后的字节数**，`read_text()` 已经做过换行折叠。
**要报文件大小时用磁盘读数，别用这个字段。**

---

## 5. 🔴「这不是投资建议」的边界（**这段不许删、不许软化**）

**本规程只讲两件事**：
1. **怎么调这四个工具**（命令、门、参数）；
2. **读出来的字段怎么念**（哪些是真读数、哪些是提取器的噪声、哪些是源码字面量）。

**本规程不做、也不许替它做的事**：

- ❌ **不许把回测结果、引擎参数、信号枚举念成收益预期、胜率承诺、或"该买/该卖"**。
  `CISEnterSignal` 的 `MOMENTUM_BREAKOUT` 只说明**源码里声明了这么一种进场信号**，
  **不说明它现在触发了，更不说明它有效**。
- ❌ **不许把"参数是多少"念成"这套参数好/能赚钱"**。
  §2.4 那些数值是**源码字面量**，可能已经过期、可能只在一份引擎里生效、
  可能只是运行时状态字段的初值（`high_watermark=0.0` 就是）。
- ❌ **不许把"读到了回测 API"念成"回测过了"**。
  `cap quant_backtest` 只读了**文件里的类和函数名**，**一次回测都没跑**（§2.3 标了「未验」）。
- ❌ **不许把历史表现、模拟结果说成未来收益**。任何"过去这样、所以将来也这样"的表述都不出本规程。
- ❌ **不许因为读数漂亮就建议下单**。这四位**全是只读**，`quant_tech.py` 顶部的模块文档写得很明确：
  *「只读：解析量化引擎/回测 API 的类、信号、参数模型。**不读取 .env/密钥，不触发任何交易**。」*
  **本域没有、也不该有一个"能下单"的能力位。**
- ✅ 要说市场判断 / 是否值得投，**那是用户自己的决定**，且必须有**投资人适当性与真实行情数据**支撑 ——
  本规程给不了，**也不假装能给**。

**一句话**：这里读的是**代码长什么样**，不是**钱会怎么变**。两者之间隔着一整个真实市场，别跨。

---

## 6. 验收（做完怎么证明真做了）

1. **四个位逐个真跑** —— 不许只跑一个然后"其余类似"（四位读的文件不同、返回结构不同）；
2. **报字段前先分类** —— 真读数 / 提取器噪声 / 源码字面量，**三类分开写**；
3. **提取器给的空值必须复核**（§4.1：`[]` 可真可假，**同一个 `[]` 两种性质**）；
4. **跑不动的写「未验」** —— 本域如实账：**回测真跑 = 未验**（要 `process_execute`，不擅自做）；
5. **子串清单**：`fields_map.py` 之类的"同型件"要**照抄结构与颗粒度**，不照抄读数。

**机检入口**：

```powershell
py -3.14 tools/codex-scripts/verify-distill.py --domain finance --skill gbt-finance
```

它检查：A 两份产物逐字节相同 · B frontmatter 有 `name`/`description` ·
C 这个域已登记为已深蒸 · D 规程里每个 `cap <能力位>` **在图鉴里真存在**（抓编命令）·
E 这个域的**每个**能力位都被点到（抓遗漏）。
**不可判定的部分（叙述质量、坑准不准）它不假装能判** —— 那些靠本文件的诚实账自己扛。

---

## 7. 固化与出处

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-finance/SKILL.md` |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-finance/SKILL.md` |
| 能力位注册 | `gbt_allinone/caps_registry.py`（`quant_strategy:87` · `quant_backtest:94` · `quant_params:108` · `quant:628`） |
| 真身实现 | `gbt_allinone/quant_tech.py`（`quant_strategy:46` · `quant_backtest:63` · `quant_params:112` · `platform_profile:81`） |
| 分发与缺口报告 | `gbt_allinone/api.py`（`_external_capability:27` · 量化分支 `:101-111` · `quant` 组合 `:918-923`） |
| 授权门 | `gbt_allinone/security/policy.py`（**本域无分支 ⇒ 走默认放行**，见 §1.1） |
| 数据真身 | `C:\Users\ADMIN\Desktop\Workspace\01_量化收割引擎\`（**不在本仓**） |
| 图鉴口径 | `state/skill_atlas.json`（`domain == "finance"` 的 4 个 `kind`） |
| 人话落点 | `python tools/codex-scripts/omni.py ask "跑个量化看看"` |

**⚠ 不许写进 `~/.agents/skills/`**（工作区 AGENTS.md 明令禁止）；装机只落 `~/.openclaw-autoclaw/skills/`。

---

## 8. 未验清单（**如实列，不许拿它当通过**）

| 项 | 为什么未验 |
|---|---|
| **真跑一次回测 / 看真实回测结果** | 要起 uvicorn（8088）或执行引擎代码 = `process_execute`，且要读行情数据；**超出只读免授权范围，不擅自做** |
| **`quant_tech` 未挂载时的缺口输出原文** | 本机 `quant_tech` 在场，没触发那条分支；**§2.1 贴的是 `api.py:37-47` 的源码构造，不是实测打印** |
| **换机 / 换用户名的表现** | 本机 `C:\Users\ADMIN\Desktop\Workspace` 在场；路径写死带来的行为是**从源码读出来的推断** |
| **`cap` 输出乱码的确切发生位置** | 已确认"数据本身正确"（§4.2），但**没定位到 PowerShell 的哪一跳**（设 UTF-8 也无效） |
| **四位之外这个域还有没有隐藏能力** | 按图鉴口径只有 4 个；**图鉴是现扫产物，重建后需重查** |
