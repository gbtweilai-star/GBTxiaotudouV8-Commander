---
name: gbt-brain
displayName: GBT · 脑职业域用法规程（2 个能力位）
version: 1.0.0
description: GBT小土豆V8 的 `brain` 职业域（做梦重演 / 吞天闭环）用法规程。把图鉴里这 2 个能力位逐个点清：用途、只读还是要授权、怎么调、有哪些 op、失败长什么样、写在哪儿；规定本域唯一入口是万能插 `five-dim.py cap <能力位>`、**2 位静态作用域全空**（不需要授权）、并记下本机实测踩到的读数陷阱（报表层 `denied:false` 而本体 `denied:true` · 顶层 `status:"ok"` 而本体 `ok:false` · 退出码不可信 · `dream_replay` 的 payload 被分派层整段吞掉导致 op 门内不可达 · `absorb_loop` 的 `limit` 门内传不进去）。**⚠️ 与记忆库规程 `gbt-brain-vault` 不是一件东西**：那一件管 Obsidian 库文件长什么样、写在哪；本件管这两个能力位怎么调、读数怎么念。当用户说「做梦/重演一下/日间念/吞天/蒸馏提炼吸收/闭环有没有闭上/吞完留没留垃圾」或这两个能力位报错、读数对不上时使用。
triggers:
  - "做梦"
  - "重演"
  - "日间念"
  - "巩固"
  - "吞天"
  - "吸收闭环"
  - "蒸馏提炼吸收"
  - "吞完清场"
  - "闭环没闭上"
  - "留垃圾"
  - "dream_replay"
  - "absorb_loop"
  - "brain"
---

# GBT · 脑职业域用法规程（2 个能力位）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **⚠️ 先分清一件事（别名冲突）**：`gbt-brain-vault` 管的是**记忆库文件长什么样、写在哪**
> （Obsidian 库根、开工三读、收集箱追加格式、junction 不许删）；
> **本件 `gbt-brain` 管的是**图鉴 `domain == "brain"` 这**两个能力位**——
> **怎么调、有哪些 op、读数怎么念、失败长什么样**。两者**不是一件东西，别互相冒充**（§6 有对照表）。
>
> **这份规程解决什么**：`brain` 域只有 2 个位，但它们是**全图鉴里"最像会动手、其实一根手指头都没动"的一域**：
> `dream_replay` 图鉴写"只读重演：不写盘、不执行"，`absorb_loop` 图鉴写"只读骨架"——
> 而外号（吞天 / 吸收 / 蒸馏 / 巩固）听起来全是**要落盘、要删东西**的动作。
> 本机实测复核的结论是：**两位都真的是只读**（源码无任何写原语、22 条契约用例全过），
> 于是本域的风险**不在"它会不会偷偷写盘"**，而在**读数会被读反**：
> ① 四条带牙闸本体判 `denied:true`，**报表层却一律印 `denied:false`**；
> ② 顶层信封 `status:"ok"` 而本体 `ok:false`；③ 同域两种错法退出码一个 0 一个 1；
> ④ `dream_replay` 的 `op` 在门里**根本传不进去**（`api.py:333` 写死 `dream_once()`），
> 你以为在调 `status`，其实每一发都跑的是同一段。
> 本文件把「哪个位、哪个 op、只读还是要授权、怎么调、失败长什么样、落在哪」逐个钉死，
> 并把**本机实测过的坑**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['<JSON载荷>']
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）。本域 2 位**静态作用域全空**（见 §4），
所以在本域里**不会**碰到授权门 —— 但"不要授权"≠"随便调都一个样"：**本域恰恰是"载荷可能被吞掉"的那一域**。

---

## 0. 这 2 个位分两簇（先认簇，再看位）

| 簇 | 位（kind） | 共 | 共同特征 |
|---|---|---|---|
| **A · 做梦重演** | `dream_replay` | 1 | 五原语（日间念→召回→变异→模拟→巩固）；**只读重演**，巩固默认不开、且**写路径没实现** |
| **B · 吞天闭环** | `absorb_loop` | 1 | 三阶段（DISTILL→REFINE→ABSORB）+ 一回灌（FED_BACK）；四条机械闸 + 五条红线；**只判不做**：只扫垃圾、只判闭环，**不删、不清、不写 store** |

**判据**：想**把已有的痕迹"在脑子里过一遍"**（不执行、不写盘）→ A；
想**问"这次吞东西的流程闭没闭上、垃圾留没留、断了能不能续"** → B。
两位**都不替你做那件事**：A 不执行、B 不吞也不清。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个位（哪个 op） | 只读还是要授权 |
|---|---|---|
| 「做梦一下 / 把今天的念重演一遍」 | `dream_replay`（门内**只有** `dream_once`；见 §3 A 的载荷陷阱） | 只读，零作用域 |
| 看这五原语叫什么、召回取几条 | `dream_replay`（`op=status`）——**⚠️ 门里调不到，只有源码/编排内核可达** | 只读，零作用域 |
| 看吞天闭环的三阶段形状、现在盘上有几件垃圾 | `absorb_loop`（空参 → `op=status`） | 只读，零作用域 |
| 看三阶段的"进什么/出什么"原文 | `absorb_loop`（`op=stages`） | 只读，零作用域 |
| 只扫盘找残留垃圾（**不删**） | `absorb_loop`（`op=junk`） | 只读，零作用域（**只报不动手**） |
| 「阶段之间不许留垃圾」判一道 | `absorb_loop`（`op=gate_stage`，给 `stage` + `leftovers`） | 只读，零作用域 |
| 「三阶段齐没齐、回灌没有」判一道 | `absorb_loop`（`op=gate_loop`，给 `stages_ran` + `fed_back`） | 只读，零作用域 |
| 「盘上垃圾是清了还是登记了」判一道 | `absorb_loop`（`op=gate_junk`，给 `paths` + `declared`） | 只读，零作用域 |
| 「断了留没留续跑点」判一道 | `absorb_loop`（`op=gate_resume`，给 `state`） | 只读，零作用域 |
| 「这条料有没有出处」判一道 | `absorb_loop`（`op=gate_source`，给 `source`） | 只读，零作用域 |

**不在这 2 个里的事**：记忆**库本身**怎么建、收集箱格式、junction、断链口径 → `gbt-brain-vault`（库规程）；
**真去吞东西 / 真去清垃圾** → 本仓**没有这个实现**（见 §5 红线④ 与 §8 未验清单）；
心智/性格/情绪/预演 → `gbt-mind`；屏幕/点击 → `gbt-tentacle`。**本域不替它们干活。**

---

## 2. 怎么调（万能插唯一门）

```powershell
# ── A · 做梦重演（门内只有一发）──
py -3.14 tools/codex-scripts/five-dim.py cap dream_replay            # 只读：内部固定跑 dream_once()

# ── B · 吞天闭环（op 走 payload，门内真的传得进去）──
py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop                                        # 只读：空参默认 op=status
py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop '{"op":"stages"}'                      # 只读
py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop '{"op":"junk"}'                        # 只读扫盘（不删）
py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop '{"op":"gate_stage","stage":"DISTILL","leftovers":["build/x.tmp"]}'
py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop '{"op":"gate_loop","stages_ran":["DISTILL","REFINE","ABSORB"],"fed_back":false}'
py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop '{"op":"gate_junk","paths":["a/x.deploy_bak"],"declared":[]}'
py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop '{"op":"gate_resume","state":{"interrupted":true,"stages_done":["DISTILL"]}}'
py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop '{"op":"gate_source","source":"?"}'
```

🔴 **本域实测的传参/显示坑（都踩过）**：

1. **PowerShell 里传 JSON：用单引号原样包住**（`'{"op":"junk"}'`）。
   写成 `'{\"op\":\"junk\"}'` 会让 `five-dim.py:139` 的 `json.loads` 直接抛
   `JSONDecodeError` —— **还没碰到门就死了**，看起来却像"命令写错了"。
2. **`--full` 要加在末尾**：`five-dim.py:132-134` 只认整串参数里的 `--full`，
   默认会把过大的 `result` 收窄成键清单（`_summarize`）。本域 `op=stages` 体量小，不加也完整；
   `op=junk` 条目多时**加 `--full` 看全量**。
3. 🔴 **`dream_replay` 的 payload 会被整段吞掉**（本域最贵的坑，见 §3 A）：
   分派层 `gbt_allinone/api.py:331-333` 是 `return dream_replay.dream_once()` ——
   它**根本不读 `payload["op"]`**。所以给 `dream_replay` 传任何 op（包括 `status`、包括瞎写的 `nope`），
   跑的都是同一段，而且**不会报"未知 op"**。**别拿它的返回当"我调的那个 op 生效了"。**

---

## 3. 2 个能力位逐个点（实测读数 + 失败典型）

> 下表 `门` = 静态查出来的作用域（见 §4）；`omni` = `omni.py auto_run_verdict()` 会不会自动替你跑（本次实算）。

### A · 做梦重演

| 项 | 内容 |
|---|---|
| **用途** | 五原语只读重演：`日间念 OBSESS → 召回 RECALL → 变异 MUTATE → 模拟 SIMULATE → 巩固 CONSOLIDATE`。**只重演、不执行、不写盘**（`dream_replay.py:3-12`） |
| **门** | **零作用域**（静态查空，见 §4） |
| **omni** | **AUTO**（`required_scopes=[]` · `auto_run_verdict=(True, [])`，本次实算） |
| **门内 op** | 🔴 **只有一发**：`dream_once(consolidate=False)`。`run()` 里的 `status` / `once` 两个 op **在门里不可达**（`api.py:333` 写死不转发 payload） |
| **读落点** | `gbt_allinone\store\traces\traces.jsonl` 与 `obsessions.jsonl`（`trace_store._load`，**纯读**：只在 132-137 行 `is_file()` + 只读 `open`，无 `mkdir`） |
| **写落点** | **无**。巩固那一刀源码写明"本刀不实现写路径"（`dream_replay.py:117-120`），即便 `consolidate=True` 也只回一句"未写" |

**实测关键字段**（2026-09-22 本机实跑）：

- `five-dim.py cap dream_replay` → 顶层 `status "ok"` · `stamp true` · `denied false` · **exit 0**；
  本体：`ok true` · `steps [{"primitive":"日间念","count":0}]` · **`consolidated 0`** ·
  **`note "没有念 ⇒ 没有梦（无源之梦不成立）"`** · **`external_action false`**。
- 库是空的（实测 `traces.jsonl` / `obsessions.jsonl` 都 `is_file() False`，路径见上）
  ⇒ **如实报 0 条候选、不编一条假念** —— 这是设计，**不是坏了**。
- 模块级 CLI（源码 docstring 写 `-3.10`，**本机 3.14 实跑通过**）：
  `py -3.14 -m gbt_allinone.tools.dream_replay --json` → 同上 JSON，**exit 0**；
  不带 `--json` → 打印 `闭环：日间念(0)` / `巩固=0 · 外部动作=False · 没有念 ⇒ 没有梦（无源之梦不成立）`。
- 🔴 **载荷陷阱实证**：`cap dream_replay '{"op":"status"}'` 与 `cap dream_replay '{"op":"nope"}'`
  打出来的 `result` 与空参那一发**逐字段一致**（三发同一段）。
  ⇒ 证明 payload **完全不进 handler**；`{"op":"nope"}` **没有**触发"未知 op"报错，**exit 0**。
- **那个门里调不到的 `op=status` 到底回什么**（直调只读函数 + 编排内核 dispatch，两条都跑过）：
  `ok true` · `readonly true` · **`primitives ["日间念","召回","变异","模拟","巩固"]`** ·
  **`recall_top_n 5`** · **`default_consolidate false`**（与源码 `RECALL_TOP_N=5` 一致）。
  而 `run("nope")` 直调抛 **`ValueError 未知 op 'nope'（可用：status/once）`**（源码 `dream_replay.py:139`）。
- **第二条只读入口（源码所见 + 已跑）**：`orchestration_kernel.py:57` 把 `dream_replay` **真 import** 进
  `_READONLY_MODULES`，第 235 行真的调 `mod.run(op, **params)`，黑板 `Blackboard.write` 是**内存态**
  （`orchestration_kernel.py:143-146`，`self.rows.setdefault(...)`，无文件 I/O）。
  实测 dispatch `dream_replay + op=status` 拿到了上面那份 `primitives` 五原语 ——
  **所以 `status` 不是"不存在"，是"万能插这条路到不了它"。**

**失败典型样子**：本域**最像失败、其实不是失败**的一条就是上面那个空库读数
（`count 0` + `note "没有念 ⇒ 没有梦（无源之梦不成立）"`）。
**别把"没梦"读成"技能挂了"** —— 表空时报空是它的红线（`tests/test_dream_replay.py:33-38` 一直在测）。

### B · 吞天闭环

| 项 | 内容 |
|---|---|
| **用途** | 三阶段 + 一回灌的**纪律面**：`DISTILL 蒸馏 → REFINE 提炼 → ABSORB 吸收`，`↺ FED_BACK 回灌`；四条机械闸 + 五条红线（`absorb_loop.py:3-38`、`RED_LINES` 222-228 行） |
| **门** | **零作用域**（静态查空，见 §4） |
| **omni** | **AUTO**（`required_scopes=[]` · `auto_run_verdict=(True, [])`，本次实算） |
| **门内 op** | 8 个：`status`（空参默认）/ `stages` / `junk` / `gate_stage` / `gate_loop` / `gate_junk` / `gate_resume` / `gate_source`（`api.py:474-478` 会转发 payload） |
| **读落点** | `gbt_allinone\store\devoured` 与 `gbt_allinone\store`（`SCAN_ROOTS`，基准是仓根 `framework_gate.ROOT`）；框架导入面 `framework_gate` |
| **写落点** | **无**。源码里**一个写原语都没有**：`open(` 0 处、`write_text`/`mkdir`/`unlink`/`remove`/`rmtree`/`shutil` 全 0（唯一一处 `replace(` 是 `str.replace("\\","/")` 的字符串替换，第 98 行） |

**实测关键字段**（2026-09-22 本机实跑）：

空参 `cap absorb_loop`（= `op=status`）→ 顶层 `status "ok"` · `stamp true` · **exit 0**；本体：
`ok true` · **`readonly true`** · `kind "absorb_loop"` · `domain "brain"` · `type "local"` ·
**`stages ["DISTILL","REFINE","ABSORB"]`** · **`loop "FED_BACK"`** ·
🔴 **`junk_now 2`**（盘上真有垃圾）· `junk_sample` 两条真路径：

```
gbt_allinone/store/devoured/gap_deploy/knowledge.json.deploy_bak   (.deploy_bak)
gbt_allinone/store/native_browser/profile/VariationsSeedV2ec5b209c-…tmp   (.tmp)
```

`scan_roots ["gbt_allinone/store/devoured","gbt_allinone/store"]` ·
`evidence "devour.py 无清理逻辑（grep 0 命中）；devoured 产物目录实测已留 .deploy_bak"` · `red_lines 5`。

`{"op":"stages"}` → 三段原文（`in`/`out`）：`原始料→要点` / `要点→结构` / `结构→落地物`，外加 `loop` 回灌段。

`{"op":"junk"}` → `readonly true` · **`scanned 5582`** · `junk` 同上两条 · **`count 2`** · `roots` 同上。

**四条机械闸 × 五条红线的实测返回**（都是真跑，`rule` 名逐字抄）：

| 调用 | 本体判定 | `rule` | 关键字段 |
|---|---|---|---|
| `gate_stage` `leftovers:["build/x.tmp"]` | `ok false` · **`denied true`** | `stage_dirty` | `junk ["build/x.tmp"]` · `why "阶段收尾没清场：把垃圾带进下一阶段 ⇒ 越吞越脏（红线①⑤）"` |
| `gate_stage` `leftovers:["ok.md"]`（干净） | `ok true` · `readonly true` | — | `clean true` |
| `gate_stage` `stage:"NOPE"` | `ok false` · `denied true` | `unknown_stage` | `allowed ["DISTILL","REFINE","ABSORB","FED_BACK"]` |
| `gate_loop` `["DISTILL","REFINE"]` + `fed_back:true` | `ok false` · `denied true` | `loop_not_closed` | `missing ["ABSORB"]` |
| `gate_loop` 三段齐 + **`fed_back:false`** | `ok false` · `denied true` | `loop_not_closed` | **`missing ["FED_BACK"]`** · `why "三阶段都跑了但**没回灌** ⇒ 是直线不是闭环：下次还会吞同类垃圾"` |
| `gate_loop` 三段齐 + `fed_back:true` | `ok true` · `readonly true` | — | `ran` 三条 · `fed_back true` |
| `gate_junk` `paths:["a/x.deploy_bak"]` `declared:[]` | `ok false` · `denied true` | `junk_left_silently` | `junk ["a/x.deploy_bak"]` · `count 1` |
| `gate_junk` 同路径 + `declared:["a/x.deploy_bak"]` | `ok true` · `readonly true` | — | `junk 1` · `declared ["a/x.deploy_bak"]`（**登记了就不算静默留**） |
| `gate_resume` `{interrupted:true, stages_done:["DISTILL"]}` | `ok false` · `denied true` | `not_resumable` | `stages_done ["DISTILL"]` |
| `gate_resume` 同上 + `resume_from:"REFINE"` | `ok true` · `readonly true` | — | `resume_from "REFINE"` |
| `gate_resume` 空参（没中断） | `ok true` · `readonly true` | — | `resume_from null` |
| `gate_source` 空参 | `ok false` · `denied true` | **`source_unspecified`** | `why "没写来源 ⇒ 不许吞（吞进来的每一条都要能回到出处）"` |
| `gate_source` `source:"?"` | `ok false` · `denied true` | `source_not_evidenced` | `source "?"` |
| `gate_source` `source:"owner:2026-09-20 口径"` | `ok true` · `readonly true` | — | `source` 原样回显 |

**失败典型样子**：`{"op":"nope"}` → **顶层就变脸了**：
`status "error"` · **`stamp false`** · `denied false` · 本体 `{"status":"error", "kind":"absorb_loop",
"message":"未知 op 'nope'（可用：status/stages/junk/gate_stage/gate_loop/gate_junk/gate_resume/gate_source）",
"error_class":"user_error"}` · **exit 1**。
⚠️ 注意这跟上面 9 条带牙闸**长得完全不同**（那些顶层 `status "ok"` / `stamp true` / **exit 0**）—— 见 §5。

**自报复核（不抄它的话，逐条验过）**：

- 它自己那句 `evidence`（"`devour.py` 无清理逻辑（grep 0 命中）"）—— 我独立 grep 了
  `gbt_allinone\devour.py` 的 `清理|cleanup|清场`：**命中 0 行**，**属实**。
- `HONEST_BOUNDARY`（"保证不了『吞噬引擎已经自动跑通闭环』；真接线要改 `devour.py`"）——
  我 grep 了 `devour.py` 里的 `absorb_loop`：**命中 0**，**属实**（它确实没接进吞噬引擎）。
- 但它**真的被接进了编排内核**：`orchestration_kernel.py:99` 真 import 进 `_READONLY_MODULES`，
  第 235 行真调 `mod.run(op, **params)` —— 实测 dispatch `absorb_loop + op=status` 拿到完整 status 本体。
  ⇒ **"没接进吞噬引擎"与"被编排内核真调用"两句同时为真，不是矛盾。**

---

## 4. 要过哪道门：**静态查，不靠跑它才知道**

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, {})          # 只读求值，不执行、不消耗授权
list(d.scopes)                          # → 这个位要过哪几个作用域
```

**本域静态查出来的全量（2026-09-22 实测，逐位 × 逐 payload 都查过）**：

| 作用域 | 覆盖哪些位 |
|---|---|
| （**零作用域**） | **全部 2 个**：`dream_replay` · `absorb_loop` |

逐条实测（`restricted` 一律 `False`、`risk` 一律 `low`、`details` 一律空）：

- `dream_replay`：`{}` / `{op:status}` / `{op:once}` / `{op:nope}` / `{op:once,consolidate:true}` → `scopes []`
- `absorb_loop`：`{}` / `{op:status}` / `{op:junk}` / `{op:gate_loop,…}` / `{op:nope}` → `scopes []`

**根因**：`security/policy.py` 的 `evaluate()` 里**没有 `brain` 这两个 kind 的分支**（全文只有 `dream_replay`/`absorb_loop` 之外的那些 kind），
函数末尾 `return PolicyDecision(... scopes=tuple(scopes))` 而 `scopes` 仍为空 ⇒ **两位都零作用域**。

**那授权怎么发（本域用不上，但口径要留）**：只能主人在终端发

```powershell
python -m gbt_allinone auth grant --scope <作用域> --ttl 600
```

或主人手写 `store/auth_grants.jsonl`。**授权一次性消耗；AI 永远无权给自己发授权** ——
缺授权就如实报缺，**不找旁路、不改 `security/policy.py`、不改 `auth_gate`**。

**两位 `omni` 都判 AUTO**（`auto_run_verdict()` 本次实算，两个都是 `(True, [])`）。
⚠️ **"在 AUTO 名单里"只表示"无参调用不会立刻死在门上"，不表示"跑了就有用"**：
`dream_replay` 无参会跑 `dream_once()` 拿到"没有念"；`absorb_loop` 无参只回 status 形状 ——
**想判某一刀，必须点名 op 并把 `leftovers`/`stages_ran`/`paths`/`state`/`source` 喂进去。**

> `brain` **不在** `DANGER_DOMAINS`（那是 `pipeline`/`dangerous`/`infra`/`integration`）——
> 但**不是因为"brain 域安全"**，只是因为它是普通域。**逐位逐 op 判，别整域放行。**

---

## 5. 🔴 报告层红线（先问"这是事实，还是我读错了地方"）

1. 🔴🔴 **报表层的 `denied` 会漏掉"本体被拒"**（本域**最值钱**的一条，实测抓到的真缺陷）。
   `five-dim.py:147-151` 判 `denied` 时读的是 **`gr.get("denied")`（信封层）**，
   **不读 `gr["result"]["denied"]`（本体层）**。本域 `absorb_loop` 有四条带牙闸，
   被拒时 `denied:true` 写在**本体**里，而信封层干干净净 ⇒ 打出来是：
   **`"status": "ok"` · `"denied": false` · `"stamp": true` · exit 0，而本体是 `ok:false, denied:true, rule:"loop_not_closed"`。**
   ⇒ **门说"不许过"，报表说"没拒、还是 ok"。** 判 `absorb_loop` 的闸，**一律看 `result.rule` 与 `result.ok`**，
   **不许看顶层 `denied`**。
   （⚠️ 诚实说明：R-H299 修的是**另一类**——授权拒绝的**扁平信封**（那时压根没有 `gbt_result`）。
   本域零作用域，**碰不到那类**；本条是同一家族、但**没被修到**的那一半：**嵌套在 result 里的 denied**。
   本域**没有**"授权被拒"的真读数，所以 §5 开头这条的**扁平信封**部分是**纪律转述**，不是本域实测。）
2. **信封 `status:"ok"` ≠ 本体 `ok:true`**（本域实测抓到）：`{"op":"nope"}` 之外的 9 条带牙闸，
   顶层 `status "ok"` · `stamp true`，本体 `ok false` · `denied true`。
   ⇒ **顶层 `status` 只说明"门放行了"，不说明"判过了"**。永远看本体。
   尤其 `stamp true`：本域它出现在**被拒**的读数里 ⇒ **印章的有无与成败无关**。
3. **退出码不可信**（本域实测同时抓到两种）：同一天同一条命令形状下 ——
   `absorb_loop` 的**未知 op** → **exit 1**（顶层 `status "error"`）；
   `absorb_loop` 的**四条带牙闸被拒** → **exit 0**（顶层 `status "ok"`）；
   `dream_replay` 传瞎写的 `{"op":"nope"}` → **exit 0 而且毫无报错**（载荷被吞）。
   ⇒ **退出码只能当"命令跑起来了没有"，既不能当成功也不能当失败**；判定一律回到本体字段。
4. **自报不等于事实 —— 但"不属实"也不许先入为主**。本域两处自报（`evidence` / `HONEST_BOUNDARY`）
   经我独立 grep **都属实**；而**图鉴 desc 与实现之间确实有缝**：
   `dream_replay` 图鉴写"**五原语**闭环"，实测门内**只跑到 1 个原语**（`日间念 count 0` 就早返回了，
   源码 `dream_replay.py:101-104`）—— 原因是**库空**；五原语那串只在 `run("status")` 里，
   而**那个 op 门内到不了**（红线见 §3 A）。
   ⇒ **"图鉴写的话"要有条件地读**：它描述的是**设计**，读数要看**当次跑出来什么**。
5. **"只读"要自己复核，别只信图鉴**（本域正是这么做的）：
   任务前提之一是"`absorb_loop` 可能会写盘/吸收素材"，**源码 + AST + 22 条用例复核后证伪** ——
   全模块**无任何写原语**，五条红线里的"清场/清理"是**判据不是动作**（它只报"有垃圾"，从不删）。
   ⇒ **该域真正的风险是"读数被读反"，不是"它偷偷写了盘"。**
6. **同一个 `result` 字段名，两个位含义不同**：`dream_replay` 的 `external_action` 是**它对"有没有做外部动作"的自答**（恒 `false`）；
   `absorb_loop` 的 `readonly` 是**它对自己只读属性的自答**（恒 `true`）。
   **两位都没有"我刚刚真的动了手"这种字段** —— 因为它们本来就不动手。
7. **`limit` 在门内传不进去**（实测）：`scan_junk(root, roots, limit=5000)` 收三个形参，
   但 `run()` 的 `op=junk` / `op=status` 分支**只转发 `params.get("root")`**（`absorb_loop.py:191,206`）。
   实测 `{"op":"junk","limit":1}` 仍然 `scanned 5582` · `count 2` ⇒ **`limit` 被忽略**。
   ⚠️ 顺带一条**源码所见**：就算传进去也不硬 —— `scan_junk` 第 93-94 行的 `break` **只跳出内层文件名循环**，
   `os.walk` 会继续走下一个目录 ⇒ 实测 `scanned 5582 > limit 5000`。
   **别把 `scanned` 当"扫完了"的证据。**

---

## 6. 与 `gbt-brain-vault` 的分工（**别互相冒充**）

`gbt-brain-vault`（工作区里已有一份）讲的是**那座 Obsidian 记忆库本身**；
本件讲的是图鉴 `domain == "brain"` 的**两个能力位**。两者**不是一回事**，撞在一起就会互相冒充：

| 谁 | 管什么 | 不管什么 |
|---|---|---|
| **`gbt-brain-vault`**（库规程） | 库根 `C:\Users\ADMIN\Documents\Codex\ObsidianVault` · 开工三读（记忆总纲 / MOC-总览 / 收集箱）· 收集箱**追加格式**（一行一条·带时间戳）· `.obsidian\plugins` 是 **junction** 不许当普通目录删 · `模板/` `地图/` `日记/` 用途 · 链接要写全路径否则图谱断链 | ❌ **它一个能力位都没点名**，**不是**这 2 个能力位的用法规程；不规定命令、门、参数、失败形状 |
| **`gbt-brain`**（本件） | 图鉴 brain 域 2 个能力位**怎么调**：`dream_replay` 的五原语与那个**载荷被吞**的分派层坑、`absorb_loop` 的 8 个 op / 四条机械闸 / 五条红线 / 真实垃圾读数、两位**零作用域**、失败形状（带牙闸拒了但报表说 `denied:false`） | ❌ **不重写记忆库结构**、不定收集箱格式、不说 junction 怎么处理、**不碰 Obsidian 库一个字节** —— 那些去读 `gbt-brain-vault` |

**一句话**：**`gbt-brain-vault` 管"记忆库文件长什么样、写在哪"；本件管"这两个能力位怎么调、读数怎么念"。**

> ⚠️ 名字像不代表同源：别因为都叫 `brain*` 就把两件合并；
> 也**别拿本件当"记忆库怎么用"的替代**（本件从头到尾**没读过库、没写过库**，
> 连 `gbt-brain-vault` 那条库根都没有引用过 —— 因为本域 2 位**跟那座库没有任何数据往来**：
> `dream_replay` 读的是 `gbt_allinone\store\traces\`，`absorb_loop` 扫的是 `gbt_allinone\store\`）。

---

## 7. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不许为了"绕开授权"直接调 `gbt_allinone` 里的模块函数替掉 `run_task` 唯一门
   （AGENTS.md 明令：那是**未经授权的写入**）。⚠️ 本域 2 位**都不需要授权**，所以**在本域根本没有"绕门"的借口**。
   本规程里唯一两处"直调只读函数"（`dream_replay.run("status")`、编排内核 `dispatch`）**都是零作用域、源码确认无 I/O、且是为了证明"门里到不了它"**，已在文中逐处标注；**不许把这个先例扩大成"以后可以直调模块"**。
3. **不许把 `absorb_loop` 的"判了"说成"清了"**：它**从不删任何东西**，
   `gate_junk` 通过只表示"要么清了、要么登记了 —— **按你给的 `declared` 算的**"，
   它**没有验证盘上那条真的被清了**。**别把 `ok:true` 读成"垃圾已消失"**。
4. **不许把 `absorb_loop` 说成"会吞素材/会写 store"**：写面在**本能力位里不存在**；
   真去吞的是 `devour` 那条线，而**它压根没引用 `absorb_loop`**（实测 grep 0 命中）。
5. **不许把 `dream_replay` 的"没有念"说成"技能坏了"**：库空时报空是它的红线。
6. **不许给 `dream_replay` 传 op 然后声称"那个 op 生效了"**：分派层吞掉 payload（§3 A）；
   想读 `status` 只能走源码/编排内核，不能在 `cap` 里假装读到了。
7. **不许把 `status:"ok"` 当成功、不许把顶层 `denied` 当判据、不许把退出码当判据**（§5 红线①②③）。
8. **不许抄能力位的自报当事实**：`evidence` / `HONEST_BOUNDARY` / `note` 是话术层，
   **源码与当次运行才是事实层**（§5 红线④，本域已有"图鉴 desc 与实现有缝"的实例）。
9. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
   **不许动别的域**、不许改 `policy.py`、不许改验收器、不许改 `gbt-brain-vault/SKILL.md`。
10. **不许装到 `~/.agents/skills/`**（本仓 AGENTS.md 明令禁止）。

---

## 8. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-brain/SKILL.md` |
| 本规程（装机·托管目录） | `~/.openclaw-autoclaw/skills/gbt-brain/SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（2 个） | `<仓>/state/skill_atlas.json`（`domain == "brain"`：`dream_replay` · `absorb_loop`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 注册表登记（图鉴的上游） | `gbt_allinone/caps_registry.py:697`（`dream_replay`）· `:910`（`absorb_loop`）—— 两条都 `safe: True`，都**没有** `requires_params` / `needs_confirmation` |
| 授权判据（**单一真相**） | `gbt_allinone/security/policy.py` 的 `evaluate()` —— **本域 2 位都没有分支 ⇒ 零作用域** |
| 门与信封读法 | `gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:131-172`（`cap` 的显示层：`--full`、`_summarize`、**`denied` 只读信封层**） |
| 自动执行判据 | `tools/codex-scripts/omni.py` 的 `required_scopes()` / `auto_run_verdict()` —— 两位都判 AUTO |
| 本域源码 | `gbt_allinone/tools/dream_replay.py`（160 行）· `gbt_allinone/tools/absorb_loop.py`（236 行） |
| 分派入口 | `gbt_allinone/api.py:331-333`（`dream_replay` —— 🔴 写死 `dream_once()`，**不转发 payload**）· `:474-478`（`absorb_loop` —— 转发 `op` 与其余参数） |
| 只读接线（第二条入口） | `gbt_allinone/tools/orchestration_kernel.py:46` `_READONLY_MODULES` · `:57` `dream_replay` · `:99` `absorb_loop` · `:235` `mod.run(op, **params)` · `:143-146` 黑板在内存 |
| 读落点 | `gbt_allinone/store/traces/{traces,obsessions}.jsonl`（`trace_store.py:132-146` 纯读）· `gbt_allinone/store/devoured` 与 `gbt_allinone/store`（`absorb_loop.SCAN_ROOTS`） |
| 契约用例（机器可复核） | `gbt_allinone/tests/test_dream_replay.py`（5 条）· `gbt_allinone/tests/test_absorb_loop.py`（17 条）—— 本次实跑 **22 条全过**（`Ran 22 tests … OK`），跑法见下 |
| 库规程（**分工件·别混**） | `<仓>/skills/gbt-brain-vault/SKILL.md` |

**跑契约用例的正确姿势**（直接 `unittest` 会被**生产 store 守卫**挡下 —— 本次实测踩到）：
测试包 `gbt_allinone/tests/__init__.py:29` 会拒绝在绑定**生产 store** 的进程里跑测试。
必须先起隔离 store：

```powershell
$env:GBT_STORE_DIR="$env:TEMP\gbt_test_store_brain"
py -3.14 -m unittest gbt_allinone.tests.test_dream_replay gbt_allinone.tests.test_absorb_loop -v
```

**未验清单（如实记，别读成"验过了"）**：

| 哪一刀 | 为什么未验 |
|---|---|
| `dream_replay` **有念时**的 `replayed` 路径（`mutate` / `simulate` / 巩固闸） | 本机痕迹库是空的（`traces.jsonl` / `obsessions.jsonl` 都 `is_file() False`）⇒ **门内跑不到那条分支**。唯一的机器证据是 `test_recall_orders_by_intensity_and_default_no_consolidate`（用 temp store）——**那是 unittest 的 temp store，不是经由门** |
| `dream_replay` 的 `consolidate=True` 分支（`dream_replay.py:117-120`） | 同上：库空 ⇒ `dream_once` 在 101 行就早返回了，**那一支没跑到**。源码所见：即便跑到也只返回一句"本刀不实现写路径"，**仍不写盘** |
| `dream_replay` 的 `op=status` / `op=once` **在门内** | `api.py:333` 写死 `dream_once()`，payload 被吞 ⇒ **门内没有这两个 op 的读数**。我已用两条门外只读路径（直调 `run("status")` + 编排内核 `dispatch`）拿到真实返回，但**必须标明"那不是走 `cap` 拿到的"** |
| `absorb_loop` 的 `scan_junk(limit=...)` **在门内** | `run()` 只转发 `root`，`limit` 传不进去（实测 `limit:1` 仍 5582）⇒ **门内不可验**。直调已验"上限不硬"（`break` 只跳内层循环） |
| **真删垃圾 / 真清场** | 本仓**没有这个实现**：`absorb_loop` 只判不做，`devour.py` 里**0 处引用** `absorb_loop`（实测 grep） |
| **真吸收落地**（结构 → 能力位/文档/口径 + 登记） | 同上：三阶段是**形状与闸**，落地动作不在本能力位内 |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "brain": "gbt-brain",
```

现在 `python tools/codex-scripts/omni.py gaps` 里它仍是
**`⏳ 在队里  brain  2 个能力位  dream_replay、absorb_loop`**（本次实测原文）。
加完后会变成 `✅ 已深蒸  brain  2 个能力位  → gbt-brain`。

**验收（做完怎么证明真的做了）**：

1. `py -3.14 tools/codex-scripts/verify-distill.py --domain brain --skill gbt-brain` → **必须 PASS**；
2. `py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop` → 拿 `junk_now` / `junk_sample` / `stages` / `red_lines`；
3. `py -3.14 tools/codex-scripts/five-dim.py cap absorb_loop '{"op":"gate_loop","stages_ran":["DISTILL","REFINE"],"fed_back":true}'`
   → 必须回 **本体 `ok:false` · `denied:true` · `rule "loop_not_closed"` · `missing ["ABSORB"]`**，
   **而顶层 `status` 仍是 `"ok"`、`denied` 仍是 `false`、exit 仍是 0** —— 复现一次 §5 红线①，才算真读懂本域；
4. `py -3.14 tools/codex-scripts/five-dim.py cap dream_replay` → 拿 `steps` / `consolidated 0` / `note "没有念…"` / `external_action false`；
5. 声明"某位只读/某位能写"之前先问自己：**这是实测读数 + 源码复核，还是我读错了地方？**
   拿不准就写"未验" —— 本域已有一处"任务前提说会写盘、实测证伪"的实例（§5 红线⑤）。
