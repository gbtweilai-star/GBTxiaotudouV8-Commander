---
name: gbt-system
displayName: GBT 系统职业域 · 用法规程（21 个能力位）
version: 1.0.0
description: GBT小土豆V8 的 `system` 职业域用法规程 —— 图鉴里这个域有 21 个能力位（health / selfscan / alerts / truth_scan / root_fix / cross_scan / inventory / auth_gate_status / signature_guard / file_hygiene / trace_store / wave_probe / shared_resources / hook_registry / orchestration_kernel / caps_called_audit / tentacle_cognition / coverage_auditor / energy_pool / context_vault / ledger_note），全部走同一个万能插门（`five-dim.py cap` → `run_task`），空参调用下静态作用域全为空。本规程逐位写清「用途 / 要不要授权 / 怎么调（真命令）/ 返回哪些字段 / 怎么念这个读数 / 失败长什么样」，并附一份**真跑出来的诚实账**：`alerts` 的 `quiet=true` 与 `anomalies=2` 同时出现（字段名骗人的 R-H297 病根）、`file_hygiene` 空参也报 `cache_cleared=28` 而 `fixed=[]`、`cross_scan` 默认 `deep=True` 会轻调用 134 个能力位并耗时约 10 分钟、`five-dim.py` 出口把信封截断到 1500 字符、GBK 控制台下含 `⇒` 的信封会当场崩（要 `PYTHONIOENCODING=utf-8`）。当用户说「体检一下 / 自检 / 查毛病 / 框架健康 / 哪里有问题 / 扫一下 / 报警 / 台账 / 钩子 / 痕迹 / 覆盖率 / 归位」，或要看系统域读数却怀疑读错了地方时使用。
triggers:
  - "体检"
  - "自检"
  - "查毛病"
  - "框架健康"
  - "哪里有问题"
  - "扫一下"
  - "深度扫描"
  - "报警"
  - "授权门"
  - "台账登记"
  - "钩子矩阵"
  - "覆盖率"
  - "system 域"
---

# GBT 系统职业域 · 用法规程（`system`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> `gbt-omni` 负责「人话落到哪个能力位」，本规程负责**这一个域**：
> **怎么调、读哪个字段、什么时候是读错了地方、什么话不许说**。

**这份规程解决什么**：`system` 是**框架自己的仪表盘** —— 它不产出作品，它回答「框架现在什么状态、
哪里坏了、谁在写盘、门还开着吗」。21 个位里有 20 个是**纯读数**；读数的危险不在"跑坏东西"，
而在**把读数念反**（`quiet: true` 就以为天下太平、`cache_cleared: 28` 就以为清过缓存）。
所以本规程的重点是「字段怎么念」与「哪条命令真的在什么条件下会写盘」。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
$env:PYTHONIOENCODING='utf-8'      # ← 本机 GBK 控制台下不加这行，含 ⇒ 的信封会直接崩，见 §6
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['{"op":"..."}']
```

---

## 0. 这个域：22 个位，一张表

| 能力位 | 它回答什么问题 | 空参要不要授权 | 真实返回的关键字段（本机实测） |
|---|---|---|---|
| `health` | 机器与解释器是谁 | 不要 | `platform` / `python` / `time` |
| `selfscan` | 框架五维（路由/模块/存储/审计/桩缺口）通不通 | 不要 | `verdict` / `findings` / `sections.{routing,modules,store,audit}` |
| `alerts` | 近期异常摘要 + 根源线索 | 不要 | `quiet` / `quiet_means` / `any_signal` / `needs_a_look` / `anomalies` / `runtime_faults` / `by_signal` / `by_event` / `top_offenders` |
| `truth_scan` | 哪些能力是"假执行" | 不要 | `mode` / `REAL` / `HONEST_STUB` / `FAKE` / `NEEDS_CRED` / `verdict` |
| `root_fix` | 修复纪律（五问诊断/补丁债/根治铁律） | 不要 | `laws`（5 条）/ `note` |
| `cross_scan` | 十维穿透式交叉验证（注册↔路由↔导入↔断链↔运行时↔扫描器互证） | 不要（但**有副作用面**，见 §2.2） | `verdict` / `findings` / `dims` / `dims_unimplemented` / `deep_checked` / `scanners_verdict` / `shadow_verdict` / `elapsed_ms` |
| `inventory` | 你的视图 vs 框架的视图（归属四分类） | 不要（`fix:true` 才要写盘） | `verdict` / `dual_view` / `items.{framework,environment,foreign}` |
| `auth_gate_status` | 各作用域还剩几条可用授权 | 不要 | `scopes.<名>.{desc,grants_available}` |
| `signature_guard` | 139 个页面的开发者署名齐不齐 | 不要（`restore:true` 才要写盘） | `verdict` / `developer` / `pages_checked` / `missing` / `restored` |
| `file_hygiene` | 家根乱放/空壳/越界数据/缓存 | 不要（`fix:true` 才要写盘） | `verdict` / `findings` / `fixed` / `live_underscore_modules` / `cache_cleared` |
| `trace_store` | 痕迹库五张表各多少条 | 不要 | `readonly` / `tables.{wave_samples,traces,trace_links,promotes,obsessions}` |
| `wave_probe` | 只读量一次波动（默认只量不写） | 不要 | `count` / `samples` / `triggered` / `trigger_mode` / `coverage` / `blind_window` / `days_covered` |
| `shared_resources` | 虚拟号/邮箱池的租借账 | 不要 | `readonly` / `pools.{phone,email}` / `leases_total` / `max_lease_s` |
| `hook_registry` | 50 个钩子的位置/层级/三条红线 | 不要 | `count` / `problems` / `counts.{existing,candidate,todo}` / `hooks` / `red_lines` |
| `orchestration_kernel` | 编排内核的只读能力面/原语/图 | 不要 | `readonly_capabilities` / `step_types` / `primitives` / `honest_boundary` |
| `caps_called_audit` | 谁真的在调这些能力位（动态算 called_by） | 不要 | `scanned_files` / `total` / `wired_count` / `orphan_count` / `wired` |
| `tentacle_cognition` | 触手的任务上下文/角色边界/自检三问/红线 | 不要 | `red_lines` / `pack_fields` / `questions` / `max_depth` |
| `coverage_auditor` | 八短板↔八触手组的覆盖率与死角 | 不要 | `matrix` / `coverage_by_group` / `reportable_modules` / `known_gaps` |
| `energy_pool` | 有几路模型能源、key 在不在 | 不要 | `count` / `energies` / `dpapi_on_disk` / `dpapi_missing` / `tier_known` / `side_rules` |
| `context_vault` | 上下文归档库的预算与引擎 | 不要 | `proposition` / `positioning` / `ratio` / `cap_bytes` / `engine` / `db_default` |
| `ledger_note` | 待落刀登记台账（三原语 + 七道闸） | 不要（`op=append` 是唯一写原语，本规程**没跑**） | `readonly` / `target` / `gates`（7 道）/ `rows` / `last_label` / `honest_boundary` |
| `tentacle_bind`（2026-09-26 补录，见 §2.8） | **资产↔触手穿透式绑定**：谁连着谁、断没断、穿透率多少、有没有漏绑 | 不要（**读面四 op**：scan/coverage/gaps/ledger；写面命令只在 CLI） | `bindings` / `missing_asset` / `ghost_tentacle`；`coverage` 另给 `live/bound/pct/no_kind/skipped/unbound`；`gaps` 给漏绑清单 |

**22 位逐位静态求值（本机实测，`policy.evaluate(kind, {})`）**：`risk` 全 `low`、`scopes` 全 `[]`。
也就是说 —— **空参调用下这 22 位一位都不需要授权**。但"空参不要授权"**不等于**"这一位永远不写盘"：
有 3 位的写盘是**藏在参数里**的（§3 逐条列），另有 1 位（`cross_scan`）会**顺手轻调用别的一百多个位**（§2.2），
`tentacle_bind` 的写面（bind/unbind/auto/sweep）**只在 CLI 暴露**、api 路由只给读面（§2.8）。

---

## 1. 唯一调用口（先读这一条）

```powershell
$env:PYTHONIOENCODING='utf-8'
py -3.14 tools/codex-scripts/five-dim.py cap health
py -3.14 tools/codex-scripts/five-dim.py cap hook_registry '{"op":"verify"}'
```

**出口行为（实测，照这个读）**：

| 现象 | 含义 |
|---|---|
| `"gate": "run_task"` | 走的是唯一门，没绕 |
| `"stamp": true` + `"status": "ok"` | 真跑通了，且盖了章 |
| `"denied": true` + `"missing_scopes"` | **被门拦下**（不是"跑错了"），信封是**扁平**的，没有 `gbt_result` |
| exit code `0` / `1` | `ok`/`success` → 0；被拒或异常 → 1。**用退出码判成败比读屏可靠** |
| 信封被截断 | 五维出口固定 `[:1500]` 字符 —— 长信封（50 条钩子、84 项清单）**尾部看不到**，这不等于字段不存在 |

**JSON 参数的写法（踩过）**：PowerShell 里要**单引号包整个 JSON**：`'{"op":"verify"}'`。
写成 `'{\"op\":\"verify\"}'` 会把反斜杠原样喂给 `json.loads`，当场
`JSONDecodeError: Expecting property name enclosed in double quotes`。

---

## 2. 逐位规程

### 2.1 体检四件套（先跑这四条）

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap health
py -3.14 tools/codex-scripts/five-dim.py cap selfscan
py -3.14 tools/codex-scripts/five-dim.py cap alerts
py -3.14 tools/codex-scripts/five-dim.py cap truth_scan
```

**`health`** —— 最小读数，只用来确认"解释器口径对不对"。
实测：`{"platform":"Windows-11-10.0.26200-SP0","python":"3.14.5","time":"2026-09-22T22:00:11"}`。
**读法**：`python` 必须是本仓声明的 **3.14.5 / cpython-314**；不是就别拿后面的读数当可比读数。

**`selfscan`** —— 五维自检，**这个域的当家位**。
实测：`verdict: "clean"`、`findings: []`，`sections` 四块各有自己的 `ok`：

- `routing`：`registered 147 / routed 147 / unrouted [] / ghost_routes [] / ok true`
- `modules`：`checked 37 / failed [] / ok true`
- `store`：`json_files 2661 / missing_dirs [] / corrupted [] / ok true`
- `audit`：`window 500 / anomalies 2 / runtime_faults 0 / by_event {pipeline_blocked:1, svc_down:1} / by_signal {trace:1, legacy:1, 其余 0} / errors_by_kind {…}`

**读法（关键）**：`verdict: "clean"` **不是**"什么都没发生"。它上面那块 `audit` 同时报
`anomalies: 2` 和 `runtime_faults: 0`。这个域自己的源码里写死了口径（`reading_scope`）：
`anomalies` 是**窗口内 _ANOMALY_EVENTS 的全部事件数**（含已恢复），**不是净化成绩**；
**记分牌是 `runtime_faults`**。`errors_by_kind` 才是**分服务/分能力**的那张表 ——
逐项带 `runtime/guard/trace/legacy/recovered` 五档。**别拿 `anomalies` 当成绩公布。**

**`alerts`** —— 声带：近期异常摘要 + 根源线索，**本域最容易念反的一屏**。
实测（同一时刻）：

```json
{"quiet": true,
 "quiet_means": "窗口内没有**现行故障**（runtime_faults=0）；但异常事件数不为 0 ⇒ 仍需人逐条看一眼",
 "any_signal": true, "needs_a_look": true,
 "anomalies": 2, "runtime_faults": 0,
 "by_signal": {"runtime":0,"guard":0,"trace":1,"legacy":1,"recovered":0},
 "by_event": {"pipeline_blocked":1,"svc_down":1},
 "top_offenders": [{"capability":"…","runtime":0,"guard":0,"trace":1,"legacy":0,"total":1}, …]}
```

**读法**：**先看 `needs_a_look`，再看 `quiet`**。
`quiet: true` 只等于"没有**现行故障**"；`needs_a_look: true` 才等于"要人看"。
两条同时出现**不是矛盾，是设计**（R-H297 根因修复：旧版 `quiet` 长得像"一切正常"，
读的人扫一眼就不往下看了，那几条 `svc_down`/`pipeline_blocked` 会一直挂着没人碰）。
分服务口径在 `errors_by_kind`（`selfscan` 里）与 `top_offenders`（`alerts` 里，按
`runtime×100 + guard×10 + trace + legacy` 排序取前 5）。

**`truth_scan`** —— 真实性审计层（零假执行铁律）。
实测：`mode: "readonly"`、`REAL: 1`、`HONEST_STUB: 0`、`FAKE: 0`、`NEEDS_CRED: []`、
`verdict: "clean"`，`detail.REAL` 里写着 `readonly-mode(探针关闭，副作用类能力未验证)`。
**读法**：**只读模式下的 `FAKE: 0` 是一个弱结论** —— 它自己的 `detail` 就把边界说清了：
副作用类能力这次压根没验。别把 `FAKE: 0` 说成"全框架零假执行"。

### 2.2 追根与穿透

**`root_fix`** —— 根治环的**纪律读数**（不是自动修复器）。
实测只回 `laws`（五条）与 `note`：症状消失≠修复 / 禁新增判例法 / 禁枚举白名单追新 /
修复前后债必须下降 / 修复必须带防复发锁。**读法**：把它当"修复 PR 的验收清单"，别当"它替你修好了"。
⚠️ 一处口径不一致（实测）：`policy` 给它零作用域，但**preflight 把它记成 `side_effect: true`**
（审计账本 22:00:36 `preflight_checked kind=root_fix status=acquired side_effect=true`）。
两处口径不齐，照"它可能有副作用"谨慎对待。

**`cross_scan`** —— 十维穿透式交叉验证，**这个域最重的一发**。

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap cross_scan                  # 默认 deep=True
py -3.14 tools/codex-scripts/five-dim.py cap cross_scan '{"deep":false}' # 省时档（跳过 H 维）
```

实测（deep 默认档，**耗时 `elapsed_ms: 598158.4` ≈ 10 分钟**）：
`verdict: "findings"`、`ok: false`、
`findings` 两条（都是 W 维**家根影子子目录**：`deploy` / `tools`，`exposure=latent`）、
`dims: [A,B,G,W,X,H]`、`dims_unimplemented: [D,E,F,V]`、
`deep_checked: 134`、
`scanners_verdict {selfscan:"P0", truth_scan/ghost_guard/file_hygiene/signature_guard/inventory:"clean"}`、
`verdict_exemptions.selfscan {exempted:true, why:"隔离/空 store 下的数据态…关键区块 routing+modules 均 ok"}`、
`shadow_verdict: "RED_SHADOW_PRESENT"`、`shadow_exposure: "latent"`。

实测（`{"deep":false}` 省时档，**耗时 `elapsed_ms: 16091.9` ≈ 16 秒**）：
`dims: [A,B,G,W,X]`、`deep_checked: 0`、`coverage_note` 改口成"有实现的维度 **5** 个"，
其余（`findings` 两条 W 维 / `scanners_verdict` / `verdict_exemptions` / `shadow_verdict`）与 deep 档一致。
**⇒ 两档只差 H 维那一项**：deep 档 `dims` 6 个、`deep_checked: 134`、~10 分钟；
省时档 `dims` 5 个、`deep_checked: 0`、~16 秒。**要结论又要快，就走省时档。**

**三条必须照写的读法**：
1. **`dims` 就是声明覆盖**，不是十维。它自己的 `coverage_note` 写死了：
   「另有 4 个维度（D/E/F/V）**只有名字、没有实现**，已从 dims 中剔除 ——
   不许把『声明过』读成『扫过了』」。**别对外说"十维扫描通过"，实际是 6 维有实现。**
2. **`deep=True` 是有副作用面的**：H 维会对**134 个安全且不在侧效应名单里的能力位**
   逐个发一次 `run_task(kind, {"_probe": True})` 轻调用。它**没有绕门**（受限位全被门拦下，
   我这次实跑在审计账本上留下约 50 条 `auth_denied`、并**没有消耗任何授权**），
   但**耗时 ~10 分钟**、**给台账留一堆噪音**。这也是它被列进 `PROBE_SKIP_KINDS` 的原因：
   「扫描器不能扫自己（无限递归——穿透实测发现）」，所以 `omni run` 默认拒绝自动跑它。
3. **`scanners_verdict.selfscan: "P0"` 不等于框架 P0**：看紧跟的 `verdict_exemptions` ——
   隔离 store 下的数据态被豁免了，`routing`/`modules` 真绿。**豁免要连着读，不能只看 P0 两个字。**

### 2.3 归属 / 卫生 / 署名

**`inventory`** —— 全息盘点：**你的视图 vs 框架的视图**（归属四分类）。
实测：`verdict: "clean"`、
`dual_view {"你看到的（家根总项）":84, "框架管辖（framework）":3, "环境托管（environment）":81, "异物（foreign）":0}`、
`items.framework ["gbt_allinone","README.md","requirements.txt"]`、`items.environment`（81 项）。
**读法**：`foreign: 0` 才算干净；`framework` 只有 3 项是**正常的**
（框架本体就一个包 + 两个入口文件），别把 81 项 `environment` 当成"框架管得少"。

**`file_hygiene`** —— 按 `LAYOUT.md` 家规自检乱放（散落/空壳/越界数据/缓存）。
实测（空参）：`verdict: "clean"`、`findings: []`、`fixed: []`、
`live_underscore_modules: ["recon\\last30days\\_pids.py"]`、`cache_cleared: 28`、`elapsed_ms: 4273`。
**读法（本域第二个"字段名骗人"）**：`cache_cleared: 28` 是**数出来的 `__pycache__` 目录数**，
**空参（`fix=False`）时它一个都没删** —— 证据是同一屏里 `fixed: []`。
**别把 `cache_cleared: 28` 报成"清了 28 个缓存"。**
写盘档见 §3。

**`signature_guard`** —— 署名守卫（开发者：自由的风，禁止删除）。
实测：`verdict: "clean"`、`developer: "自由的风"`、`pages_checked: 139`、
`missing: []`、`restored: []`、`elapsed_ms: 383.6`。
**读法**：`missing: []` 是"139 个页面全都带署名"；`restored: []` 是"这次一个都没补"
（空参不补）。写盘档见 §3。

### 2.4 门与台账

**`auth_gate_status`** —— 人工授权门状态（只读；授权只能人发放）。
实测：`ok: true`，`scopes` 里 15 个作用域**逐个带 `desc` 与 `grants_available`**，
本机当时**全部为 0**。
**读法**：这是"**发授权前先看还剩几张**"的那一屏。
⚠️ 它回的是**快照** —— 授权是**一次性消耗**的，别人刚跑一发就可能把你看的那张用掉了，
**别拿几秒前的读数当作"现在还有"**。

**`ledger_note`** —— 台账登记（三原语：`RULES` 读七道硬闸 / `PREVIEW` 只读预演 / `APPEND` 唯一写原语）。
实测（空参 → 只读档）：
`readonly: true`、`target: "…\gbt_allinone\docs\待落刀登记.md"`、
`gates`（7 道：`target_fixed` / `append_only` / `single_physical_line` / `no_halfwidth_quote` /
`row_shape` / `idempotent` / `predecessor_required`）、`rows: 160`、`last_label: "R-H642"`、
`honest_boundary: "不判内容对错 · 不碰图纸 · 不出网 · 不装环境 · 不登记别的能力位"`。
**读法**：七道闸是**机械闸，不是口号**：目标固定（调用方传不了路径）· 只追加 ·
单物理行 · 禁半角双引号（中文串用「」）· 行首必须是 `> **<label> 补记` · 同 label 幂等拒写 ·
给了 `after` 就必须是当前最后一条。**`policy` 特意让 `op=append` 零作用域**（源码注释：
"闸挂了，路没通"的教训）—— 但**本规程没跑 append**（§8）。

### 2.5 痕迹与波动

**`trace_store`** —— 痕迹库只读读数。实测：`readonly: true`、
`store: "…\gbt_allinone\store\traces"`、
`tables {wave_samples:0, traces:0, trace_links:0, promotes:0, obsessions:0}`。
**读法**：**五个 0 是真空**（骨架期还没落库），不是"读数失败"。
它自己把落库路径写出来（`record_wave_sample` / `append_trace` / `append_obsession` / `promote`），
`0` 就是 `0` —— **别编"数据在别处"**。

**`wave_probe`** —— 痕迹触手只读量一次波动（默认只量不写）。
实测：`window_s: 900`、`count: 0`、`baseline_mu: 0.0`、`baseline_sigma: 0.0`、
`samples: [0,0,0,0,0,0]`、`triggered: false`、**`trigger_mode: "floor_used"`**、
**`coverage: "half"`**、`blind_window: ["2026-09-22T22:00:00","22:15:00"]`、
`outlier_days: ["2026-09-14","2026-09-21"]`、`days_covered: 9`。
**读法（第三个"别念反"）**：`triggered: false` **不等于"没有波动"** ——
它自己报了 `coverage: "half"`（半覆盖）、`trigger_mode: "floor_used"`（用了地板值）、
`baseline_mu/sigma` 都是 `0.0`（没样本）。**判据不全时只能说"没触发"，不能说"平静"。**

### 2.6 只读骨架：共享资源 / 钩子 / 编排 / 接线

**`shared_resources`** —— 共享资源池（只读骨架）。
实测：`readonly: true`、`pools {phone:{total:0,idle:0,leased:0}, email:{…全 0}}`、
`leases_total: 0`、`leases_active: 0`、`active_leases: []`、`max_lease_s: 1800.0`、
`note: "资源可共享，身份不共享（一 AI 一号）；骨架期池子为空 —— 空就是空"`。
**读法**：**"空就是空"** —— 别把 0 池说成"资源充足"或"读数异常"。

**`hook_registry`** —— 钩子矩阵只读注册表。空参走 `catalogue`（50 条 `hooks` 明细），
但**五维出口 1500 字符截断，尾部 `counts` 看不到**。要看总数/自检，走另两个只读 op：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap hook_registry '{"op":"verify"}'
py -3.14 tools/codex-scripts/five-dim.py cap hook_registry '{"op":"redlines"}'
```

实测：`verify` → `count: 50`、`problems: []`、`counts {existing:4, candidate:1, todo:45}`；
`redlines` → 三条红线（L3 审计钩子必须挂触手外面 / 钩子失败必须隔离 /
钩子链必须可中断）、`layers {L1 框架级, L2 业务级, L3 审计级}`、
`namespace_rules {hook.general. / hook.business. / hook.audit.}`、
`categories {A 生命周期, B 触手操作, C 编排调度, D 证据审计, E 内容发布, F 系统元}`。
**读法**：`existing 4 / candidate 1 / todo 45` —— **45 条待建今天一条都没接线**
（源码 `HONEST_BOUNDARY` 原文如此）。注册表"清楚"≠"钩子在跑"。

**`orchestration_kernel`** —— 编排内核只读面。
实测：`readonly: true`、`readonly_capabilities`（37 个位名）、
`step_types ["capability","code","human"]`、
`primitives ["状态空间","动作空间","角色工作组","流程状态机","可存储图","挂起恢复"]`、
`honest_boundary: "编排内核只保证『工作流可以被序列化、恢复、按依赖调度』。它不保证『工作流一定跑得对』——工作流对错，由门禁和复核决定。"`
**读法**：那句 `honest_boundary` 要**照着转述**，不许升格成"编排内核保证正确性"。

**`caps_called_audit`** —— 能力位调用点审计（动态算 `called_by`）。
实测：`readonly: true`、`scanned_files: 280`、`total: 147`、
**`wired_count: 141`**、**`orphan_count: 0`**、`wired`（逐位的 `callers` / `self_refs` / `cap_type`）。
**读法**：**同名模块自称不算接线**（源码口径）—— `self_refs` 与 `callers` 是两栏，别混。
这次 `orphan_count: 0` 是好读数，但它是**只读快照**：新加位没接线它下次才会变。

### 2.7 只读骨架：认知 / 覆盖 / 能源 / 上下文

**`tentacle_cognition`** —— 触手认知包（只读骨架）。
实测：`readonly: true`、`red_lines`（五条：未测不按绿 / 盲猜即违规 / 无痕即未发生 /
无自检不许执行 / 能力全息上下文聚焦）、`pack_fields`（task_id, goal, scene, boundary, capabilities）、
`questions`（what 我要做什么 / why_allowed 我凭什么做 / rollback 做错了怎么回滚）、`max_depth: 3`。
**读法**：这三问是**执行前的自检门**；答不出 ⇒ 拒执行（这是它自己的红线，照抄，别软化）。

**`coverage_auditor`** —— 触手覆盖审计（只读骨架）。
实测：`readonly: true`、`matrix` 8 行（八短板 key/short_board/group/expected_modules/reportable_modules）、
`coverage_by_group: "8/8 已有（无结构性死角）"`、
**`reportable_modules: "21/39（53.8%）"`**、
`known_gaps ["G1 视觉面（眼）0/5 无显式上报形状（待核）", "G2 手/脑/门/网/镜 的上报未满"]`。
**读法**：**两个数必须一起说** —— 「8/8 无结构性死角」与「上报 21/39（53.8%）」。
只说前者就是报喜不报忧；`known_gaps` 是它自己登记的死角。

**`energy_pool`** —— 能源池（只读骨架·内调）。
实测：`readonly: true`、`count: 2`、
`energies [{name:"agnes", key_ref:"store/secrets/agnes_api.dpapi", env:"AGNES_API_KEY", on_disk:true, tier:"unknown"},
{name:"deepseek", key_ref:"store/secrets/deepseek_api.dpapi", env:"DEEPSEEK_API_KEY", on_disk:true, tier:"unknown"}]`、
`dpapi_on_disk: ["agnes","deepseek"]`、`dpapi_missing: []`、**`tier_known: []`**、
`note: "**免费/付费盘上判不出**（没有该字段）⇒ 标 unknown，不编；能源可换，原生栈不动"`、
`side_rules`（输出永不以模型自居 / 衍生码不能绕路由 / 不许硬编偷密钥）。
**读法**：**`tier: "unknown"` 是它自己承认判不出，不是"免费"**。
**只报"在不在盘上"（`on_disk`），永远不 echo key 值**。

**`context_vault`** —— 上下文归档库（只读骨架·内调）。
实测：`readonly: true`、`proposition: "**内存多大，上下文就多长**（按**可用**内存算）"`、
`positioning: "**索引 + 检索层**，不是第四处存储（正文引用不复制）"`、
`ratio: 0.25`、`cap_bytes: 67108864`、
`engine: "**真库：sqlite3 + FTS5**（零依赖 · 纯本地 · R-H236 起）"`、
`db_default: "…\gbt_allinone\store\context_vault\index.sqlite3"`。
**读法**：`cap_bytes 67108864` = 64 MiB，**是按可用内存算出来的预算**，不是常量；
内存不足时它**降级并如实报**（照它自己的口径）。**别把它读成"第四处存储"**。

### 2.8 `tentacle_bind` —— 资产↔触手穿透式绑定（2026-09-26 补录）

**一句话**：**每一个产出物都连着一根触手**——绑定账在盘上、追加式台账只增不删、
"故障"只剩一种形态：**某根触手断连**。

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap tentacle_bind
# ⇒ ok true · bindings 4302 · missing_asset [] · ghost_tentacle []
py -3.14 tools/codex-scripts/five-dim.py cap tentacle_bind '{"op":"coverage","dir":"skills"}'
py -3.14 tools/codex-scripts/five-dim.py cap tentacle_bind '{"op":"gaps"}'
py -3.14 tools/codex-scripts/five-dim.py cap tentacle_bind '{"op":"ledger"}'
```

**读面四 op（api 路由只暴露这四个）**：

| op | 返回 | 实测值（2026-09-26） |
|---|---|---|
| `scan`（默认） | `bindings` / `missing_asset` / `ghost_tentacle` | **4302 绑定 · 0 缺失 · 0 不在册** ⇒ 断连 0 |
| `coverage`（要 `dir`） | `live` / `bound` / `pct` / `no_kind` / `skipped` / `unbound` | `pct` 老口径（全活文件）、`ok` 门槛仍 `>= 95.0`；`no_kind` 与 `skipped` 分开报（**不挪门线**） |
| `gaps` | `missing` / `no_kind` / `scanned` / `sample` | **漏绑巡检**：有标签可挂却没绑 = 真缺口；实测 0 |
| `ledger` | `path` / `lines` | 追加式台账 `state/asset_bindings.jsonl` 行数 |

**写面命令（CLI 专属，api 路由不给）**：`bind` / `unbind` / `auto <目录> <标签>` /
`sweep <目录>`（按启发式补绑）/ `autobind`（产出即绑，手动触发版）。
**api 路由只给读面**是有意的：写面会改账，账是"证据面"，**证据面的写动作必须走人手里的 CLI**。

**设计事实（源码现读 · 2026-09-26 大修后）**：

- **标签有两层**：① **能力位 `kind`**（178 个，注册表为准）② **`domain:<域>`**（30 个职业域）——
  第二层是为"代码也要有归属"加的：`gbt_allinone/security/policy.py` → `domain:security`。
  `scan` 的"不在册"判据按**两层标签**验（`_valid_labels()`），乱挂标签照样抓得出来；
- **三级判定顺序**：后缀/路径启发式 → **实现文件归位**（`文件名 == 某 kind`，如
  `tools/filmkit.py` → `filmkit`、`genoffice_cap.py` → `genoffice`，**只认精确同名**）→
  **域归属**（`gbt_allinone/<域>/…` → `domain:<域>`，目录名与注册表域同名才成立）；
- **产出即绑接在总闸上**（`api.py::run_task` 非 probe 分支 → `_autobind_hook`）：
  任何一次能力调用返回后，把**这次调用期间新出现/新改动的资产**自动绑标签。
  三条保险：只看资产根（不遍历 `_upstream`）· 模块内 **3 秒节流** · **异常全吞**（绝不许弄坏一次真调用）。
  水位线 `state/.bind_watermark`：**首次只立基线不绑**（"新于 0"= 全部历史文件，那是存量，
  存量归 `sweep`；产出即绑只管此后新增）；
- **性能（实测三次迭代，同一个钩子从 14.3 秒降到 0.28 秒）**：
  ① `Path.rglob`+`Path.stat` → **`os.scandir`**（Windows 上 `entry.stat()` 免额外系统调用）；
  ② `_rel()` 里的 `Path.resolve()` → **`_rel_fast` 切前缀**（cProfile 实证：31693 次
  `nt._getfinalpathname` 烧掉 11.3 秒）；
  ③ `suggest()` 的后缀**每文件只算一次** + 域集合缓存（否则 12817 文件 × 40 条启发式
  构造 50 万个 Path 对象）。
  **联接点（junction）例外**：`skills/remotion-*` 这类要按**解析后的真实路径**记账
  （不解析会与 `.agents/skills/...` 老账重影 —— 实测 161 条 fake gap），只解析联接点本身；
- **跳过面（三层，全部实测踩过才定）**：① 任意位置：`.git`/`__pycache__`/`.scratch`/`node_modules`/`.vscode`/`.mimosa`；
  ② **仓根锚定**：`store`/`state`/`config`/`vendor`/`.pylibs`/`snapshots`/`.backups`
  （踩坑：用全局子串会误伤第三方仓内部的 `src/config/*.rs` 源码目录）；
  ③ **`gbt_allinone/store/` 用白名单** `STORE_KEEP`（`devoured`/`life_vault`/`visual_memory`/`vision`/`life`
  进账，其余含 **store 根文件**默认跳过——踩坑：黑名单只列子树 ⇒ `store/audit.jsonl` 漏网被绑给了 `echo`）；
  ④ **运行足迹**：`_*.py`/`_*.txt`/`*.tmp`/`*.deleted`（与 `inventory` 的 transient 判据逐字对齐）；
- **映射的 kind/域必须真在注册表里**——曾经映射过不存在的名字（`image_gen`/`state`/`notes`）
  导致 91 条"触手不在册"，被 `scan` 抓出来后修正（这就是"断连只剩一种形态"的用法）。

**🔴 本规程修过它的一个真缺陷（2026-09-26）**：`scan()` / `coverage()` 原来把**人读行直接打 stdout**，
而 api 路由调的就是这两个函数 ⇒ **JSON 契约被污染**（`five-dim.py cap tentacle_bind` 的输出无法被
`json.load` 解析）。修法：两函数加 `verbose` 参数，**CLI 传 True、api 走默认 False** ——
保留人读、保证机读。**同类位都要按这条检查**（凡"有人读行 + 被 api 调用"的模块都有这个坑）。

---

## 3. 授权门：哪一位在什么条件下要什么作用域

**空参调用**：21 位**全部零作用域**（§0 已逐位实测）。
**写盘藏在参数里**，逐条核过 `gbt_allinone/security/policy.py`：

| 能力位 | 触发写盘的条件 | 需要的作用域 | 写什么 |
|---|---|---|---|
| `file_hygiene` | `{"fix": true}` | `filesystem_write` | 删 `.tmp`、清 `__pycache__`、删空壳目录、`*.jsonl` 归位到 `store/`、补署名 |
| `inventory` | `{"fix": true}` | `filesystem_write` | 按归属四分类归位 |
| `signature_guard` | `{"restore": true}` | `filesystem_write` | 把缺失的开发者署名注回页面 |
| `ledger_note` | `{"op":"append"}` | **无**（policy 显式放行） | 追加一行到 `gbt_allinone/docs/待落刀登记.md` |

**其余 17 位**在 `policy.evaluate` 里**根本没有条目** ⇒ 任何参数下都零作用域（fail-closed 的是
"未列出的**动作**"，不是"未列出的位"；这 17 位的 handler 本身就是只读读数）。

**被门拦住时长什么样（本机真实原文，`cap file_hygiene '{"fix":true}'`）**：

```json
{"gate":"run_task","kind":"file_hygiene","status":"denied","stamp":false,"denied":true,
 "result":{"status":"denied","denied":true,
   "message":"capability requires human authorization",
   "reason":"需要人工授权（filesystem_write）：写入、移动、删除或自动整理文件",
   "scopes":["filesystem_write"],"missing":["filesystem_write"],
   "how_to_grant":["终端运行: python -m gbt_allinone auth grant --scope filesystem_write --ttl 600",
                   "或主人手写 store/auth_grants.jsonl 追加一行（格式见 auth_gate.SCOPES 与 README）"],
   "note":"授权一次性消耗；AI 调用路径无权自行发放"},
 "missing_scopes":["filesystem_write"], …}
```

**三条照写的纪律**：
1. **拒绝信封是扁平的**：被门拦下时**没有 `gbt_result`**，`denied`/`missing`/`how_to_grant` 全在顶层
   —— 五维出口已经修成"没有 `gbt_result` 就把顶层当 body 看"（R-H299）。**别把它读成 `status: unknown`。**
2. **授权只能主人在终端发**：`python -m gbt_allinone auth grant --scope <scope> --ttl 600`
   （或主人手写 `store/auth_grants.jsonl`）。**AI 永远无权给自己发授权。**
   缺授权就**如实报缺**，**不找旁路、不改 `security/policy.py`**。
3. **一次性消耗**：`auth_gate_status` 显示的可用条数是快照；别人跑一发就少一张。
   本规程全程**没有为自己申请过任何授权**。

---

## 4. 🔴 零猜测律：读数先问一句「这是事实，还是我读错了地方」

**这一节是本域的核心，因为本域的坑全是"念反"，不是"跑坏"。**
每读一个字段，先问：**它名字说的，和它实际量的，是同一件事吗？**

**判例一 · `quiet: true` 与 `anomalies: 2` 同时出现（字段名骗人）**
`alerts` 的 `quiet` **只等价于 `runtime_faults == 0`**（"窗口内没有现行故障"），
它长得却像"一切正常"。源码把病根写死了（R-H297）：后果不是难看，是**给故障喘息**。
**规则**：看到 `quiet: true`，**必须同时看 `anomalies` 与 `needs_a_look`**；
后两个不为 0/不为 false ⇒ **要人逐条看**，不许写"框架正常"。

**判例二 · `cache_cleared: 28` 而 `fixed: []`（数字是真的，含义不是你想的那个）**
`file_hygiene` 空参（`fix=False`）**照样把 `__pycache__` 数目数出来**，但**一个都没删**。
只报 `cache_cleared: 28` 就是**把"数了"说成"清了"**。
**规则**：凡"动作类"字段名（`cleared`/`fixed`/`restored`/`deployed`），
**必须找同屏的 `fixed`/`restored` 数组对账**；对不上就按"没做"报。

**判例三 · `triggered: false` 不等于"平静"**
`wave_probe` 同时报了 `coverage: "half"`、`trigger_mode: "floor_used"`、
`baseline_mu/sigma: 0.0`。**判据不全时，只能报"没触发"**，不许报"没有波动"。
**规则**：报"无异常/无波动"之前，先看**覆盖率 / 盲区 / 基线样本**三样齐不齐；
`coverage` 不是 `full`、或 `blind_window` 非空 ⇒ 结论要带"覆盖不足"。

**判例四 · `verdict: "clean"` 只是它那一层干净**
`selfscan` 的 `clean` 说的是"我没发现 P0 断连"，同屏的 `audit.anomalies: 2` 依旧在；
`cross_scan` 的 `scanners_verdict.selfscan: "P0"` 后面紧跟 `verdict_exemptions` 说它被豁免了。
**规则**：`clean`/`P0` 这类**结论字段必须连着它的证据字段一起读**（`findings`/`exemptions`/`known_gaps`）；
**有豁免、有 findings、有 known_gaps 的，一律照抄出来**。

**判例五（工具层）· 出口截断 1500 字符**
`hook_registry` 空参的 `counts`、`inventory` 的尾部清单，**在屏幕上就是看不到**。
**规则**：看不到 ≠ 字段不存在，也 ≠ 值为 0。
要么换个只读 op 把它读出来（`'{"op":"verify"}'`），要么**如实写"出口截断，未读到"**。

---

## 5. 报告层红线（对主人说话时）

1. **不许把"没触发"说成"没问题"**；不许把 `quiet: true` 单独贴出来当结论。
2. **不许把"声明覆盖"说成"实际覆盖"**：`cross_scan` 是 **6 维有实现**，不是十维。
3. **不许报喜不报忧**：`coverage_auditor` 的 `8/8` 必须与 `21/39（53.8%）` 一起出现。
4. **不许把骨架说成能力**：`hook_registry` 的 45 条 todo、`trace_store` 的五个 0、
   `shared_resources` 的空池 —— **空就是空**，不许脑补成"正在建设中所以很好"。
5. **不许 echo 任何密钥**：`energy_pool` 只报 `on_disk` / `env` 名 / `key_ref` 路径，
   `key_ref` 是 `.dpapi` 文件引用，**不是明文 key**；`tier` 一律 `unknown`，**不猜免费还是付费**。
6. **不许替框架保证它自己没保证的事**：`orchestration_kernel.honest_boundary`、
   `truth_scan` 的只读模式边界、`ledger_note.honest_boundary` —— **原样转述，不升格**。

---

## 6. 本机实测过的坑（照做，别自己解读）

1. **GBK 控制台下含 `⇒` 的信封会当场崩**。
   `py -3.14 tools/codex-scripts/five-dim.py cap alerts`（不带环境变量）在本机实测报：
   `UnicodeEncodeError: 'gbk' codec can't encode character '\u21d2' in position 192`，
   **退出码 1**。`omni.py` 自己会 `reconfigure(encoding="utf-8")`，`five-dim.py` **不会**。
   ⇒ **每条命令前加 `$env:PYTHONIOENCODING='utf-8'`**（或 `chcp 65001`）。
   **这不是能力位坏了** —— 是出口编码坏了；别据此报"alerts 有故障"。
2. **出口固定截断 1500 字符**。长信封读不全时，换只读 op 或如实标"未读到"。
3. **PowerShell 里 JSON 要用单引号包**：`'{"op":"verify"}'`。
   反斜杠转义写法会让 `json.loads` 抛 `JSONDecodeError`。
4. **`cross_scan` 默认 `deep=True`，约 10 分钟（实测 `elapsed_ms: 598158.4`）**，
   会给审计账本留约 50 条 `auth_denied` 噪音。**它是零作用域、不消耗授权、不绕门**，
   但**别在急着要结论时跑它**；省时用 `'{"deep":false}'`（实测 `elapsed_ms: 16091.9` ≈ 16 秒，
   代价只是 H 维不跑：`deep_checked: 0`）。
5. **`root_fix` 的两处口径不一致**：policy 零作用域 vs preflight `side_effect: true`。
6. **中文目录名在 PowerShell 管道里会显示成乱码**，但**数据本身是好的**；
   判断真假要看字段与退出码，**别看屏上的中文有没有花**。

---

## 7. 不许做什么

- 不许**绕门**：写盘档跑不动就报缺 `filesystem_write`，不许改 `security/policy.py`、不许自签授权、
  不许直接调 `hygiene.scan(fix=True)` 之类的模块函数（那就是绕开 `run_task` 唯一门）。
- 不许**给自己发授权**，也不许替主人"预支"授权。
- 不许**把 1500 字符截断的屏幕当完整信封**，据此推断字段缺失。
- 不许把**没跑过的命令**（含本文件里任何一条）说成"我验过了"。§8 就是为此存在的。
- 不许动**别的域**：本规程只讲 `system` 的 21 位。
- 不许删除或篡改开发者署名（`signature_guard` 就是守这条的）。

---

## 8. 诚实账：本规程**没验过**的部分（不许当已验）

| 没验的 | 为什么 |
|---|---|
| `file_hygiene {"fix": true}` 真写盘 | 要 `filesystem_write`；本机当时 `grants_available: 0` ⇒ **被门拦下**（原文见 §3），**没有绕门** |
| `inventory {"fix": true}` 真归位 | 同上，要 `filesystem_write` |
| `signature_guard {"restore": true}` 真补署名 | 同上，要 `filesystem_write` |
| `ledger_note {"op":"append"}` 真追加 | `policy` 显式给它零作用域，**但它真写台账文件**（有后果动作）—— 本规程**没跑**；命令：`py -3.14 tools/codex-scripts/five-dim.py cap ledger_note '{"op":"append", …}'` |
| `hook_registry {"op":"register_check"}` / `{"op":"publish_check"}` | 只读计算，但**本次没跑**（只跑了 `catalogue` / `verify` / `redlines`） |
| `wave_probe` 的写档 / `truth_scan` 的 probe 模式 | 会写盘或带副作用探针，**未跑**（`truth_scan` 自己报 `readonly-mode(探针关闭…)`） |

**一条硬口径**：**「未验」必须写成「未验」**。上面每一条的"为什么"就是它的缺什么作用域 / 缺什么条件。

---

## 9. 固化位置与机检验收

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-system/SKILL.md` —— 随仓版本管理，是真身 |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-system/SKILL.md`（本仓 AGENTS.md 指定的托管目录） |
| 图鉴登记 | `tools/codex-scripts/omni.py` 的 `DISTILLED_DOMAINS` 里 `"system": "gbt-system"` |
| 能力位名单（唯一真相） | `state/skill_atlas.json` 里 `domain == "system"` 的 **22 条**（原 21 + `tentacle_bind`） |
| 绑定系统本体 | `<仓>/tools/tentacle_bind.py`（`scan:160` / `coverage:184` / `main:208`；账 `state/asset_bindings.json` + 台账 `state/asset_bindings.jsonl`） |
| 绑定系统的分派 | `<仓>/gbt_allinone/api.py` 的 `if kind == "tentacle_bind":`（**只给读面三 op**） |
| 授权策略（只读核对） | `gbt_allinone/security/policy.py` |
| 万能插本体 | `tools/codex-scripts/five-dim.py`（走的仍是 `run_task` 唯一门） |

**机检验收（照跑，别只看人眼）**：

```powershell
$env:PYTHONIOENCODING='utf-8'
py -3.14 tools/codex-scripts/verify-distill.py --domain system
py -3.14 tools/codex-scripts/omni.py gaps
```

`verify-distill.py` 会替人判四件可判定的事：两份产物**逐字节相同**、
frontmatter 有 `name`/`description`、规程里点名的**每个能力位在图鉴里真存在**、
以及**这个域 22 位一个都没漏点**。

---

## 附：写这份规程时**真跑过**的命令（一行一条）

```text
py -3.14 tools/codex-scripts/five-dim.py cap health                          → platform/python/time
py -3.14 tools/codex-scripts/five-dim.py cap selfscan                        → verdict clean · routing 147/147 · audit anomalies 2 / runtime_faults 0
py -3.14 tools/codex-scripts/five-dim.py cap alerts                          → quiet true · any_signal true · needs_a_look true · anomalies 2
py -3.14 tools/codex-scripts/five-dim.py cap truth_scan                      → mode readonly · REAL 1 · FAKE 0 · verdict clean
py -3.14 tools/codex-scripts/five-dim.py cap root_fix                        → laws×5 · note
py -3.14 tools/codex-scripts/five-dim.py cap cross_scan                      → verdict findings · dims A/B/G/W/X/H · deep_checked 134 · elapsed 598158.4ms
py -3.14 tools/codex-scripts/five-dim.py cap cross_scan '{"deep":false}'     → dims A/B/G/W/X · deep_checked 0 · elapsed 16091.9ms
py -3.14 tools/codex-scripts/five-dim.py cap inventory                       → verdict clean · dual_view 84/3/81/0
py -3.14 tools/codex-scripts/five-dim.py cap auth_gate_status                → scopes×15 · grants_available 全 0
py -3.14 tools/codex-scripts/five-dim.py cap signature_guard                 → clean · pages_checked 139 · missing []
py -3.14 tools/codex-scripts/five-dim.py cap file_hygiene                    → clean · findings [] · fixed [] · cache_cleared 28
py -3.14 tools/codex-scripts/five-dim.py cap trace_store                     → readonly · 五张表全 0
py -3.14 tools/codex-scripts/five-dim.py cap wave_probe                      → count 0 · triggered false · coverage half · trigger_mode floor_used
py -3.14 tools/codex-scripts/five-dim.py cap shared_resources                → readonly · 池全 0 · max_lease_s 1800
py -3.14 tools/codex-scripts/five-dim.py cap hook_registry                   → catalogue（出口截断）
py -3.14 tools/codex-scripts/five-dim.py cap hook_registry '{"op":"verify"}'   → count 50 · problems [] · existing 4 / candidate 1 / todo 45
py -3.14 tools/codex-scripts/five-dim.py cap hook_registry '{"op":"redlines"}' → red_lines×3 · layers L1/L2/L3 · categories A–F
py -3.14 tools/codex-scripts/five-dim.py cap orchestration_kernel            → readonly_capabilities 37 · step_types 3 · primitives 6
py -3.14 tools/codex-scripts/five-dim.py cap caps_called_audit               → scanned_files 280 · total 147 · wired 141 · orphan 0
py -3.14 tools/codex-scripts/five-dim.py cap tentacle_cognition              → red_lines×5 · questions×3 · max_depth 3
py -3.14 tools/codex-scripts/five-dim.py cap coverage_auditor                → matrix×8 · 8/8 · reportable 21/39（53.8%）
py -3.14 tools/codex-scripts/five-dim.py cap energy_pool                     → count 2 · dpapi_on_disk [agnes,deepseek] · tier_known []
py -3.14 tools/codex-scripts/five-dim.py cap context_vault                   → ratio 0.25 · cap_bytes 67108864 · engine sqlite3+FTS5
py -3.14 tools/codex-scripts/five-dim.py cap ledger_note                     → readonly · gates×7 · rows 160 · last_label R-H642
py -3.14 tools/codex-scripts/five-dim.py cap file_hygiene '{"fix":true}'     → status denied · missing_scopes [filesystem_write]（被门拦下，未绕门）
```

---

## 变压器 + 任务管理器（主人令 2026-09-27）

### 一、变压器：为什么"老是能源供给不足"——它**从来没接线**
**排查结论（不是猜）**：
- 09-22 设计稿写明「**网关前置的两级变压器**（压缩 + 快速输出，**带前后两个数**）」；
- 09-26 日报结论：「`panel_server.py` 登记 pending · **从未接线**」；
- 全仓 grep `变压器` ⇒ 只命中设计稿与交付单，**零实现**。
⇒ **不是池子小，是该装的变压器没装**：每次调用全量送模型，token 不降 ⇒ 能源必然紧。
（原设计的"最低能源律"第 4、5 条就是：压缩体积 + 变压增强缩短线路。）

**现在按原设计接上了**（能力位 `transformer`）：

| op | 干什么 | 读数 |
|---|---|---|
| `compress` | 输入侧：去重 → 重复 JSON 折叠 → 裁陈旧上下文 | 实测 **2339 → 1451 字符（省 38%）** |
| `cache_get`/`cache_put` | 输出侧：命中就**根本不叫模型**（最大一笔能源账） | 命中率记在台账里 |
| `stats` | 累计省下多少字符 / 省下多少次调用 | `state/transformer_ledger.jsonl` |
| `selftest` | 判据自检（含反向自检：故意砍掉命令段必须被检出） | 全过 |

**硬判据（照原设计 §1.4）**：必给**前后两个数**；**字面量包含关系**（identifiers/files/commands
压前后必须一个不丢）不成立或没省下来 ⇒ **fail-open 回原样**（宁可没省，不许压坏）。

```python
g.run_task("transformer", {"op": "compress", "text": "<长 prompt>"})     # 拿前后两个数
g.run_task("transformer", {"op": "cache_get", "text": "<同一个问题>"})    # 命中=省一次调用
g.run_task("transformer", {"op": "stats"})                              # 省了多少，账面说话
```

**还没修的一处（诚实）**：`energy_pool` 的 9 个能源 **`tier` 全是 unknown** ⇒ 设计里的
**"免费优先"实际没生效**（池子认不出哪个是免费的）。修法：给池子加 tier 判定（按 provider/profile 归类），
属**改能源池语义**，留给主人一句话。

### 二、任务管理器（能力位 `task_manager`）

一屏看全 **任务 / 归属 / 内存占用 / CPU / 端口 / 进程 ID**（照主人给的那张系统任务管理器的列）。

```python
g.run_task("task_manager", {"op": "list", "limit": 25})   # 真进程快照（psutil）
g.run_task("task_manager", {"op": "stop", "pid": 1234})   # 停任务：过 process_execute 门
g.run_task("task_manager", {"op": "page"})                # 出静态页（快照内联）
```
页面：`holo_pet/assets/task-manager/index.html` —— 深色 + 青/橙 + **SVG 图标、无 emoji**
（我们原有的视觉语言）；快照**内联**（`file://` 直接打开就能看），served over http 时 5 秒自刷新。

**三条诚实口径（踩过坑才写得出）**：
1. **CPU 要两次采样** —— `process_iter` 的 `info` 是首次缓存，第二遍必须**直接再调** `cpu_percent()`
   （否则永远是 0.0；实测用忙进程验证过：System Idle 531.7% 真读数）；
2. **归属按进程名优先** —— 只看命令行会把 `chrome`（它的 `--user-data-dir` 里有我们的路径）
   误认成"框架服务"（实测踩过）；
3. **"网络"列是"它占着的端口"，不是流量** —— 本机取不到 per-process 流量，**不编**；
   另外剔除 System Idle / MemCompression 这类**不是任务**的噪声行。

---

## 变压器 v2（**核心吃透后重做**）+ 记忆秒搜 + 安全棒的垃圾/加速（2026-09-27 晚）

主人令：「变压器你最好**从新精准抓取能力核心学习吃透了再把细节看一遍**再动手，免得老是接不上用不了」
+ 「上下文快满了就自动压缩避免溢出丢失资料」+「记忆管理（全局储存和查找）」
+「**全局只要是一页看不到的东西全部设计一个万能精准秒搜**，想到匹配面出现的能力」
+「框架加速和框架垃圾清理都要安全棒来做」。

### 1. 变压器 v2：两个成熟成品的**核心**（一手源，含它自己写的坑）
| 源 | 核心 | 它的坑（我们照抄，避免踩） |
|---|---|---|
| **LLMLingua**（microsoft） | 小模型给 token 打**重要性分** + **显式预算**（`rate`/`target_token`）+ **段落可 `compress=False` 保护**（"ICL 与推理必须保留"）；实测 2365→211 tokens | 压完文本"**看得见的破碎**"· 需要一个小模型（有开销）· 域外数据效果差 |
| **GPTCache**（zilliztech） | **语义近似命中**（嵌入 + 向量库 + `similarity_threshold`）；宣称 10x 成本/100x 速度 | **假命中（返回错答案）比不命中更坏**· 假不命中· 按行数淘汰会 OOM |

**我们的落地（取核心、避坑、诚实标注能力边界）**：
- **指令保真**：分段 = 指令 / 结构 / 参考；**只有参考段允许压**，指令与结构**一个字不动**；
- **显式预算**：`rate=` / `target_chars=` 只作用于参考段；
- **近似缓存 + 假命中禁令**：simhash 汉明距离做近似命中，**但近似命中默认只报告、不返回答案**
  （要答案须调用方显式 `allow_approx=true`）—— 这是 GPTCache 那条最贵的教训；
- **真"语义"要嵌入模型**：本机没有本地嵌入 ⇒ **如实标为"近似"**，升级路径写清（换嵌入 + 向量库）；
- **autosize**：上下文超阈值才压，**原文先落 `state/context_spill/`** ⇒ 压完还能回原文，**资料不丢**。

**自检读数（全过）**：指令保真 2068→300（比 0.145）· 关键信息 584→200（**不旁路**）·
autosize **48900→1206（40×）+ 原文落档** · 近似命中=扣住答案 · 远查询=miss（无假命中）。

**修掉的三处"接上了用不了"（都是实测逮的，不是推演）**：
1. **字面量判据太严** —— 早先"全部 identifiers 必须留"⇒ 真实长文本**永远旁路、一次也省不下来**；
   改成只保**关键**字面量（files / commands / **指令行里**的标识符）；
2. **短行被当结构** —— 早先"<12 字符也算结构"⇒ 80 行短文本**全被保护**（`protected_lines` = 全部）；
3. **命令判据不稳** —— 早先抓"命令词 + 后 60 字符"⇒ 周边文本一变就误判"丢了"；改成只抓稳定前缀。

### 2. 记忆管理 + 万能秒搜（能力位 `memory_manager`）
SQLite **FTS5 全文索引**（实测**中文可检索**，命中带【高亮】）· 六类源：记忆/文档/技能/状态/**能力位**/代理。
```python
g.run_task("memory_manager", {"op": "index"})                     # 增量建索引（mtime+sha 未变即跳过）
g.run_task("memory_manager", {"op": "find", "q": "变压器"})        # 秒搜：路径+类型+片段+**匹配的能力位**
g.run_task("memory_manager", {"op": "store", "text": "…"})         # 存记忆（过 filesystem_write 门）
```
**"想到匹配面出现的能力"**：索引里同时含 191 条能力位 ⇒ 搜到什么，就告诉你**哪根触手能处理它**。
**两处血账**：① 增量时**整表清空**丢过 344 条索引（改成只动变化的 path）；② SQL 放进变量/拼接被安全钩子拦两次
（改成**内联字面量 + `?` 占位符**）。

### 3. 安全棒新增两件事（主人追加：「框架加速和垃圾清理都归安全棒」）
| op | 干什么 | 实测 |
|---|---|---|
| `tidy` | 垃圾清理（**默认干跑**）：字节码缓存 / 测试缓存 / 临时件 / **空壳目录** | 可回收 1.6MB（6 处 `__pycache__` · 10 临时件 · **152 空目录**）；真删过 `filesystem_write` 门 |
| `accelerate` | 框架加速（**必给前后两个数**） | 资产索引重建后查询 **2717ms → 28ms（97×）**；死绑定退账 |

**⚠️ 计划任务这条被宿主封死**：本会话自身就跑在计划任务里 ⇒ 新建/修改自动化都被拒
（`Cannot create a scheduled task inside a session that already belongs to a scheduled task`）。
**"每半天"的安全棒要落地，二选一**：① 主人**新开一个会话**让我建；② 主人把上面 ⑥ 段（安全棒那几条命令）
贴进现有那条 6 小时自动化的提示词里 —— 两条路任选，我这边随时可执行。

---

## 上帝之眼（`gods_eye` · 主人令 2026-09-27）

主人原话：「上帝之眼是能看到**创作页面**这些；里面的**克劳德**给意见和建议、商量架构与方向，**决策权在你这里**；
把 **CodeBuddy 也部署进上帝之眼**，做杂事，**主项目她没有执行权**，只服从安排、随时候命；以及**每日的
GBT 探针汇报和每日全量扫描**指出**缺点、短板、卡点**；然后你自己跟克劳德在里面计划优化、提升整体实力。」

| op | 干什么 | 实测 |
|---|---|---|
| `see` | 看得见**创作页面** + 服务端口（真连） | **7/7 页面**（console3d/automation/structure/godview/health-panel/task-manager/music）· 服务 FreeLLMAPI 🟢 · ComfyUI 🟢 |
| `advisors` | 两位顾问的**权限表**（机器可读 may / may_not）+ 可用性 | Claude available=**False**（缺 CLI）· CodeBuddy available=**True** |
| `ask` | 真咨询（过各自能力位） | Claude：如实报"未装"+ 安装命令；**CodeBuddy 碰主项目 ⇒ 拒**（`refused=True · hit=['projects/']`） |
| `daily` | **探针汇报 + 全量扫描** ⇒ 缺点/短板/卡点（**每条带 src**） | 缺点 1（未清故障 9）· 短板 4（未实现登记/密钥槽/顾问位）· 卡点 1（ComfyUI CPU） |
| `plan` | 提案 + **决策**（采纳/搁置，**决策权在主体**） | 6 条真提案已落账 `state/gods_eye_plan.jsonl` |
| `panel` | 上帝之眼页面（我们视觉语言 · 快照内联） | `holo_pet/assets/godview/index.html` |

**两位顾问的权限（写死，不是口头约定）**
- **Claude**：可=出意见/建议/评审/商量架构方向；**不可=决策、直接改主项目**；决策权在主体。
- **CodeBuddy**：可=杂事（路径排查/日志整理/取数）；**不可=对主项目有执行权、决策、改主项目文件** ⇒
  给它派活时只要点了主项目路径（`projects/` `gbt_allinone/` `skills/` `tools/` `state/`）**一律拒**。

**"每日"怎么保证**：宿主的自动化功能**不接受从计划任务会话里再建任务**（实测原文
`Cannot create a scheduled task inside a session that already belongs to a scheduled task`）
⇒ "每日"不靠宿主，靠**开机判据**兜：`test_gods_eye` 的 **F 条**每次开工自检日报新鲜度（≤26h），
过期即红并直说"该跑日报了"。**要真自动跑**，二选一：① 主人新开会话让我建一个每日自动化；
② 把下面这段贴进现有 6 小时环的提示词：

```
⑦ 上帝之眼日报：python -c "import gbt_allinone as g; print(g.run_task('gods_eye', {'op':'daily'}))"
   再 python -c "import gbt_allinone as g; print(g.run_task('gods_eye', {'op':'panel'}))"
   有新的缺点/短板/卡点 ⇒ gods_eye plan op=add 记提案；决策用 plan op=decide decision=采纳|搁置
```

### 上帝之眼 · 交付后当天抓出的三条「接上了用不了」（都已修 + 都有判据盯）

| 病 | 真身 | 判据 |
|---|---|---|
| **问顾问永远问不到** | `cli_agents.run` 认 `prompt`/`q`，而 `gods_eye.ask` 只传了 `text=` ⇒ 授权给了也只会回「缺少 prompt」 | `test_gods_eye` **H**（`_ask_payload` 必须带 `prompt`） |
| **「要授权」这条卡点从没出现过** | `_scan_findings` 按文件路径装 `auth_gate.py`，它的第一行 `from . import _paths` 直接 ImportError，又被 `except: pass` 吞了 ⇒ 静默降级 | `test_gods_eye` **J/K**（读数必须读得到、结论必须由读数推出） |
| **免费算力池假红** | `freellmapi.probe()` 回 `up`，密钥口只读 `ok` ⇒ 端口在听也判「不可达」，一路传到 `health.json` 再由日报报成短板 | `test_automation_keys` **A**（结论必须与自带的原始读数一致） |

**教训一句话**：跨模块传参/取数时，**键名不一致 ≠ 服务不在**；`except: pass` 包住读数是
把"没读数"变成"没这回事"。凡是被上层当结论用的读数，都要有一条"结论 vs 原始读数"的自洽判据。

**被门拒 ≠ 顾问答了**：`ask` 被拒时**不许**把拒绝理由塞进 `answer`，要单独给 `denied` +
`how_to`（授权只能主人在终端发）。

### 上帝之眼 · 四岗分工（主人令 2026-09-28，决策口径以此为准）

主人原话：「把 **Jev 的推理模型**接入上帝之眼来做决策，设计好**要以 Jev 来做决策**，克劳德给意见和
建议以及可以商量，这么来好了之后**由 Jev 做决策**，**Codex 专注编程**，**DeepSeek Harness 专注执行层**。」

| 岗 | 干什么 | 不许干什么 | 真身/怎么接 |
|---|---|---|---|
| **Jev（推理模型）** | **拍板**（裁决 · 在候选里选 · 否掉不成熟 · 定优先级） | **无证据拍板** · 绕过授权门 · 自己动手执行 | 快慢双脑（与 `tools/control_loop.py` 同一套 Jev 协议）：快脑出候选+置信度 → 不够升慢脑 → 慢脑没有 / 回话解析不出候选 ⇒ **挂起** |
| **Claude** | 意见 · 建议 · 评审 · **可商量** | **决策** · 直接改主项目 | `claude_code`（CLI 已装；真问要 `process_execute`+`external_llm` 时段授权） |
| **Codex** | **专注编程**：写码/改码/重构/评审/跑测试 | 决策 · 跳过判据直接改生产 | `codex_chat` / `codex_turn_send`（并发 1） |
| **DeepSeek Harness** | **专注执行层**：执行动作/跑链/落地 | 决策 · 自作主张改方向 | `llm_chat` 的 DeepSeek 密钥链 + `brain_execute` |
| **主体（我）** | 编排 · 留痕 · 兜底 | —— | **Jev 挂起时决策也挂起**（不许谁替它拍） |

**`decide` 的三条硬规矩**（都落成判据，`test_gods_eye::TestJevDecides`）：
1. **没证据不许拍板**：`evidence` 必给，证据不在盘上直接拒（"无脑决策比无脑操作更贵"）；
2. **选不出不许硬猜**：快脑置信度 < `0.6` ⇒ 升慢脑；慢脑调不动或回话解析不出候选 ⇒
   **挂起**（`blocked`）并给 `how_to_unblock`；
3. **预算闸**：每分钟最多 `6` 次决策（照 `control_loop` 的成本口径自设），超了拒 —— 别拿决策刷分。

**快脑是确定性的、不装成模型**：打分 = 短板权重命中 + 读数命中 + **风险词扣分**（上线/删除/改生产…）。
台账 `state/gods_eye_decisions.jsonl`；上帝之眼页面上有「四岗分工 · 谁拍板」与「最近决策（Jev）」两块。
