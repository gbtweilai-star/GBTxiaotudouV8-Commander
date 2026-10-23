---
name: gbt-engine
displayName: GBT · 引擎职业域用法规程（9 个能力位）
version: 1.0.0
description: GBT小土豆V8 的 `engine` 职业域（万能插执行引擎/工作流 DAG/断点续跑/定时触发器/数据传输算子/传输缓存）用法规程。把图鉴里这 9 个能力位逐个点清：用途、只读还是改状态、怎么调、要什么参数、失败长什么样；把**静态查出来的门**钉死（9 位**全部零作用域** —— policy.py 里根本没有这 9 个位的分支）；并把本机实测读数与两处**图鉴漂移**如实记下（`sched_define` 图鉴写"无需参数"、事实必填 name+workflow+every_seconds>0；`sched_tick`/`wf_cache_clear` 会被 `omni` 判成"只读无参可直跑"、**它们其实会改状态**）。另记三条报告层红线（被拒是扁平信封 / 信封 status:ok ≠ 本体 ok:true / 退出码不可信）。当用户要「编排工作流/跑一个 DAG/断点续跑/定时无人值守/清传输缓存/在节点间搬数据」，或某个 engine 能力位报 user_error、报"工作流不存在/运行记录不存在/依赖成环"、读数看着像成功其实失败时使用。
triggers:
  - "工作流"
  - "workflow"
  - "DAG"
  - "编排"
  - "跑一个工作流"
  - "万能插执行引擎"
  - "断点续跑"
  - "续跑"
  - "定时触发器"
  - "调度"
  - "无人值守"
  - "传输算子"
  - "transfer"
  - "传输缓存"
  - "wf_define"
  - "wf_run"
  - "wf_status"
  - "wf_resume"
  - "wf_cache_clear"
  - "sched_tick"
---

# GBT · 引擎职业域用法规程（9 个能力位）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`engine` 域是框架的**手**（`gbt_allinone/engine.py` 文件头原话：
> "脑子只有一份：统一接口 run_task 做一切决策；手有很多只：本引擎的 worker 线程池并行执行节点"）。
> 它只有 9 个位，却踩三类坑：
> ① **以为要授权、其实不要**（本域 9 位**静态查出来全是零作用域** —— 见 §4）；
> ② **以为只读、其实会改生产状态**（`sched_tick` / `wf_cache_clear` 会被 `omni` 标成
> "✅ 只读无参，可直跑"，而它们一个真跑到期调度、一个真删 `transfer_cache.json`）；
> ③ **以为成功了、其实失败了**（工作流整体 `failed` 时，万能插信封照样 `status:"ok"`·
> `stamp:true`·**退出码 0** —— 见 §5）。
> 本文件把「哪个位、什么时候用、要不要门、失败长什么样、读数该看哪个字段」逐个钉死，
> 并把**本机实测过的读数与坑**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['<JSON载荷>']
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**，`five-dim.py:107`）；被门拒绝就**如实报缺什么作用域**，不绕路。
载荷一律**单引号原样包住 JSON**（`'{"name":"x"}'`）；写成 `'{\"name\":\"x\"}'` 会在 `five-dim.py:106`
的 `json.loads` 直接抛 `JSONDecodeError` —— **还没碰到门就死了**，看起来却像"命令敲错了"。

---

## 0. 这 9 个位分三簇（先认簇，再看位）

| 簇 | 位（kind） | 共 | 共同特征 | 落盘在哪（有副作用的位） |
|---|---|---|---|---|
| **A · 工作流引擎** | `wf_define` · `wf_run` · `wf_status` · `wf_resume` | 4 | 定义/执行/查/续跑 DAG；**只有 `wf_status` 是纯只读** | 定义 → `store/workflows.json`；每次运行 → `store/wf_runs/<run_id>.json` |
| **B · 定时触发器** | `sched_define` · `sched_tick` · `sched_status` | 3 | 无人值守闭环；**只有 `sched_status` 是纯只读** | 调度 → `store/schedules.json`；`tick` 会真的去跑到期工作流 |
| **C · 传输算子与缓存** | `transfer` · `wf_cache_clear` | 2 | `transfer` 是**纯变换、零副作用**；`wf_cache_clear` 删缓存 | 缓存 → `store/transfer_cache.json` |

**判据**：想把**一串能力编成图跑** → A；想让它**自己按点跑** → B；想在**节点之间搬数据/复用结果** → C。

`policy.py` 里这 9 个位**一个分支都没有** ⇒ 簇划分只影响**是否改状态**，不影响门（门都为零，见 §4）。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个位 | 只读还是要改状态 |
|---|---|---|
| 定义/覆盖一张工作流图（校验环、依赖、能力合法性） | `wf_define` | 改状态（写 `workflows.json`），**必填 `name`+`nodes`** |
| 把工作流分层并行跑掉 | `wf_run` | 改状态（写 `wf_runs/`），**必填 `name`** |
| 看跑过哪些、什么状态、节点成不成 | `wf_status` | **纯只读**（可选 `name`/`limit`/`include_workflows`） |
| 上次跑到一半断了，接着跑（复用已完成节点） | `wf_resume` | 改状态（再写一份 `wf_runs/`），**必填 `run_id`** |
| 节点间数据变形状（map/filter/merge/unique/sort/pluck/stats…） | `transfer` | **纯只读**（零副作用，见 §3 C） |
| 定义"每 N 秒自动跑一次某工作流" | `sched_define` | 改状态（写 `schedules.json`），**事实必填 `name`+`workflow`+`every_seconds>0`** |
| 扫一遍到期调度、把它们跑掉 | `sched_tick` | **改状态**：无参也真的会跑去执行到期工作流 |
| 看调度条目、上次跑成没成 | `sched_status` | **纯只读**（可选 `name`） |
| 清掉节点结果缓存（同输入复用那份） | `wf_cache_clear` | **改状态**：真删 `store/transfer_cache.json` |

**不在这 9 个里的事**：屏幕/点击/读网页 → `gbt-tentacle`；模型/Codex/外部 LLM → `gbt-llm`；
长程任务（`lr_submit`/`lr_tick`/`lr_status`）与生产发布（`pipeline_submit`）**是别的域**，
本域的 `wf_run` 能把它们当**节点**编进去，但**不替它们过门**（那些位有自己的作用域，节点执行时照旧逐位受门约束）。

---

## 2. 怎么调（万能插唯一门 · 真命令）

```powershell
# ── A · 工作流引擎（定义 → 跑 → 查 → 续跑）──
py -3.14 tools/codex-scripts/five-dim.py cap wf_define '{"name":"<工作流名>","nodes":[{"id":"a","kind":"health","params":{}},{"id":"b","kind":"count_words","params":{"text":"{{a.gbt_result.result.echo.text}}"},"depends_on":["a"]}]}'
py -3.14 tools/codex-scripts/five-dim.py cap wf_run '{"name":"<工作流名>"}'                  # 可选 fail_fast / max_node_retries / params
py -3.14 tools/codex-scripts/five-dim.py cap wf_status                                       # 最近 20 条运行记录
py -3.14 tools/codex-scripts/five-dim.py cap wf_status '{"name":"<工作流名>","limit":5}'      # 按工作流名过滤
py -3.14 tools/codex-scripts/five-dim.py cap wf_status '{"limit":1,"include_workflows":true}' # 顺带带回工作流定义（可视化正规出口）
py -3.14 tools/codex-scripts/five-dim.py cap wf_resume '{"run_id":"<run_id>"}'               # run_id 从 wf_status 里拿

# ── B · 定时触发器 ──
py -3.14 tools/codex-scripts/five-dim.py cap sched_define '{"name":"<调度名>","workflow":"<工作流名>","every_seconds":3600}'
py -3.14 tools/codex-scripts/five-dim.py cap sched_tick
py -3.14 tools/codex-scripts/five-dim.py cap sched_status
py -3.14 tools/codex-scripts/five-dim.py cap sched_status '{"name":"<调度名>"}'

# ── C · 传输算子与缓存 ──
py -3.14 tools/codex-scripts/five-dim.py cap transfer '{"op":"stats","data":[1,2,3]}'
py -3.14 tools/codex-scripts/five-dim.py cap transfer '{"op":"map","data":[{"name":"a"},{"name":"b"}],"field":"name"}'
py -3.14 tools/codex-scripts/five-dim.py cap wf_cache_clear
```

**模板注入语法（`wf_define` 的 `nodes[].params` 里用）**：`{{节点id.字段路径}}`
（整串保类型；混排转字符串；支持列表下标 `{{a.result.items.0.name}}`；扇入 `{{*}}` / `{{*.gbt_result.result.words}}`
收集全部上游）。**上游节点输出是双层信封**：`{{a.gbt_result.result.<字段>}}` ——
本机实测过一次踩坑：把 `{{a.gbt_result.result.echo}}`（那是 `{"text": …}` 一个 dict）喂给要字符串的
`count_words`，节点当场 `'dict' object has no attribute 'split'`（见 §3 A 失败典型）。

---

## 3. 9 个能力位逐个点（**实测读数** + 失败典型）

> `门` 列 = 静态查出来的作用域（§4）；`omni` 列 = `omni.py auto_run_verdict()` 会不会自动替你跑。
> `改状态?` 列 = `preflight._STATE_CHANGING_KINDS` 有没有登记它（登记了就有并发租约 + 幂等复用）。

### A · 工作流引擎（4 位）

#### `wf_define` —— 定义/覆盖一张工作流 DAG
- **用途**：`engine.define_workflow(name, nodes)`（`engine.py:66`）。定义时**就**校验：节点 `id` 非空且唯一、
  `depends_on` 必须存在、**依赖不成环**、`kind` 必须是注册过的能力（`BENIGN_CAPS`）、
  `timeout` 必须为正数、`routes` 必须是非空列表且分支能力已注册、`cache` 必须是布尔。
  **落盘** `store/workflows.json`（按名覆盖）。
- **门**：无（零作用域）。**改状态**：是。
- **omni**：`NO（需要参数 name,nodes）`。
- **要什么参数**：`name`（非空）+ `nodes`（**非空列表**）。
- **🔴 幂等复用（实测，很重要的坑）**：如果同名工作流的 `nodes` 与盘上**逐字段相同**，
  `preflight._observe_workflow_define` 判 `matched` ⇒ **不重写、直接复用**，返回体是
  `{"ok": true, "status": "already_satisfied", "reused": true, "fingerprint": "84c3278…", "observation": {"matched": true, "method": "workflow_definition_state", "reason": "definition_already_equal"}}`。
  **改了 `nodes` 才会真写**（实测：同名不同 `nodes` → `{"ok":true,"name":"…","nodes":1}`，定义当场被换掉）。
- **实测读数**（隔离 store，见 §6）：
  - 新定义 → `{"ok": true, "name": "engine-probe", "nodes": 2}`，信封 `status ok` · `stamp true` · exit 0；
  - 生产 store 幂等复用 → `already_satisfied`（见上），**生产 `workflows.json` 前后哈希一致**。
- **失败典型样子**（全部 `status:"error"` · `stamp:false` · `error_class:"user_error"` · **exit 1**）：
  - 无参 → `"message": "需要 name 与非空 nodes 列表"`
  - `kind` 没注册 → `"message": "节点 a 的能力未注册: not_a_real_cap"`
  - 依赖成环 → `"message": "依赖成环，无法执行"`
  - 依赖了不存在的节点 → `"message": "节点 a 依赖了不存在的节点: zzz"`

#### `wf_run` —— 分层并行执行工作流
- **用途**：`engine.run_workflow(name, params, fail_fast=True, max_node_retries=0)`（`engine.py:305`）。
  按依赖**分层**、同层用线程池并行（`max_workers=min(8, len(level))`）；上游输出经模板注入下游；
  `fail_fast` 默认真 ——**任何节点失败即停，不伪造成功**（`engine.py:11` 原话）。**每次运行落盘** `store/wf_runs/<run_id>.json`。
- **门**：无。**改状态**：是。**omni**：`NO（需要参数 name）`。
- **要什么参数**：`name`；可选 `params` / `fail_fast` / `max_node_retries`。
- **实测读数**（隔离 store）：
  - 成功 → `{"run_id": "engine-probe-ok-1790089703502", "workflow": "engine-probe-ok", "status": "ok", "nodes": {"a": "ok", "b": "ok"}, "elapsed_s": 0.014}`；
  - 节点失败（fail_fast）→ `"status": "failed"`，`"nodes": {"a":"ok","b":"error"}`，
    `results.b.message = "'dict' object has no attribute 'split'"` —— **失败照样落盘一份 run 记录**（不会因为失败就不留痕）。
- **🔴 读数陷阱**：上面这个 `failed` 的那一发，**信封还是 `status:"ok"` · `stamp:true` · exit 0**。
  判成败**只能看本体 `result.status`**（§5 红线②）。
- **失败典型样子**：无参 → `"工作流不存在: （先 wf_define）"`；名字错 → `"工作流不存在: no-such-wf（先 wf_define）"`；
  嵌套超过 5 层 → `"子工作流嵌套超过上限 5 层（疑似递归调用）"`（源码所见，未实跑）。
- **未验**：`timeout` / `when` / `fallback` / `routes` 四个节点级武器（`engine.py:348-429` 源码所见）**本次没实跑**；
  `kind=wf_run` 的层级嵌套（`MAX_WF_DEPTH=5`）**未验**。

#### `wf_status` —— 查运行记录（本域**唯一**的纯只读引擎位）
- **用途**：`engine.list_runs(name, limit=20, include_workflows=False)`（`engine.py:569`）。读 `store/wf_runs/*.json`，按 mtime 倒序。
- **门**：无。**改状态**：否（不在 `_STATE_CHANGING_KINDS` 里，**连并发租约都没有**）。**omni**：`AUTO`。
- **要什么参数**：**无必填**。可选 `name`（过滤）、`limit`（默认 20）、`include_workflows`（默认 False）。
- **实测读数**（生产 store，零写入）：
  - 无参 → `result.runs[]` 每条含 `run_id / workflow / params / status / nodes / elapsed_s / finished_at`；
    首位 `run_id "persona-evolve-1790089283387"` · `status "ok"` · `nodes {"evolve":"ok"}` · `elapsed_s 0.099` ·
    `finished_at "2026-09-22T22:01:23"`；
  - `{"name":"persona-evolve","limit":1}` → **1 条**（过滤生效）；
  - `{"limit":1,"include_workflows":true}` → 多出 `workflows[]`（每个定义给 `name/node_count/nodes[]`，
    节点里带 `id/kind/depends_on/has_fallback/routes/cache`）与 `count`；
  - `{"name":"no-such-wf"}` → `{"runs": []}`，**信封 ok · exit 0** ⇒ **查不到不是错**（对比 `sched_status` 给错名字会 user_error）。
- **失败典型样子**：**本机实测没抓到**（只读查询、给错名字返回空列表）。要留意的是"空列表 = 没有记录"，
  **不是"没查"** —— `include_workflows` 才是看"有哪些工作流定义"的正规出口（`engine.py:544` 的 R-H99b 由来）。

#### `wf_resume` —— 断点续跑（复用已完成节点）
- **用途**：`engine.resume_run(run_id, max_node_retries=0)`（`engine.py:468`）。读上次落盘的
  `store/wf_runs/<run_id>.json`，**已完成（`status:"ok"`）的节点直接复用不重跑**，只补未完成的；
  `skipped` 的保持跳过。再落一份新 run 记录（`run_id` 形如 `<工作流>-resume-<ms>`）。
- **门**：无。**改状态**：是。**omni**：`NO（需要参数 run_id）`。
- **要什么参数**：`run_id`（从 `wf_status` 里拿）；可选 `max_node_retries`。
- **实测读数**（隔离 store）：
  - 续一个**失败过**的 run → `{"run_id":"engine-probe-resume-1790089703928","resumed_from":"engine-probe-1790089696706","status":"failed","nodes":{"a":"ok","b":"error"},"reused_nodes":1}` ⇒ **`reused_nodes:1` 就是"a 没重跑"的证据**；
  - 续一个**成功**的 run → `{"status":"ok","nodes":{"a":"ok","b":"ok"},"reused_nodes":2,"elapsed_s":0.0}` ⇒ 全复用、耗时 0。
- **🔴 判据**：续跑**不是"接着那口气活过来"** —— 它按**能力重新执行**未完成节点（`run_task(node["kind"], p)`），
  未完成节点若本身还是会失败，**续跑结果照样 `failed`**（实测就是如此，如实回报）。
- **失败典型样子**：无参/错 id → `"message": "运行记录不存在: "` / `"运行记录不存在: <你给的那个>"`，`user_error` · exit 1；
  工作流定义已被删 → `"工作流已不存在: <名>"`（源码所见，未实跑）。

### B · 定时触发器（3 位）

#### `sched_define` —— 定义"每 N 秒跑一次某工作流"
- **用途**：`schedule.define_schedule(name, workflow, every_seconds, enabled=True)`（`schedule.py:41`）。
  工作流**必须已定义**（`engine.workflow_exists`），间隔必须是**正整数**。落盘 `store/schedules.json`。
- **门**：无。**改状态**：是。**omni**：🔴 **`AUTO`（假的）**。
- **要什么参数**：🔴 **`name` + `workflow` + `every_seconds>0` 三个都是事实必填**（源码 `schedule.py:43-53`：
  缺 name → `需要 name`；工作流不存在 → `工作流不存在: X（先 wf_define）`；间隔非整数 → `every_seconds 必须是整数`；
  `<=0` → `every_seconds 必须 > 0`）。**可选** `enabled`（默认 true）。
- **🔴 图鉴漂移（本域第 1 处，未修）**：`state/skill_atlas.json` 里 `sched_define` 的
  `requires_params` 是 **`[]`**、`params_hint` 是空串 —— 与源码和实测都矛盾。
  后果不是"看起来不好看"，是**行为**：`omni.py auto_run_verdict()` 因此判它
  `AUTO = True`（实测 `why = []`），`omni ask "定义并跑一个工作流"` 打出来的原文就是
  `→ python tools/codex-scripts/five-dim.py cap sched_define   ✅ 只读无参，可直跑`。
  **它既不"只读"、也不"无参"**。⇒ 与 `gbt-llm` 里 `brain_route` 那次（图鉴写无需参数、实测无参必失败）
  **同一类病**；本规程按实测口径写，**注册表补登交主人**（本规程不擅自改 `caps_registry.py` / `omni.py`）。
- **实测读数**（隔离 store）：
  - 建新调度 → `{"ok": true, "name": "engine-sched", "workflow": "engine-probe-ok", "every_seconds": 3600}`；
  - **幂等复用**：与盘上完全一致（同 name/workflow/every_seconds/enabled）→ 不重写，
    `{"status":"already_satisfied","reused":true,"fingerprint":"c6a5a481…","observation":{"method":"schedule_definition_state","reason":"schedule_already_equal"}}`（生产 store 实测，前后哈希一致）。
- **失败典型样子**：无参 → `"message": "需要 name"`，`user_error` · exit 1。

#### `sched_tick` —— 扫描到期调度并执行
- **用途**：`schedule.tick()`（`schedule.py:85`）。遍历 `schedules.json`，把 `now - last_run_ts >= every_seconds`
  的条目**真的跑掉**（`engine.run_workflow`），回写 `last_run_ts/last_status/last_run_id`，
  并落一笔审计 `sched_tick`。**到期判定用单调推进的 `last_run_ts`，错过不补跑**（防雪崩）。
- **门**：无。**改状态**：**是**（它一定会 `_save(schedules.json)`，且到期就会真执行工作流）。
  **omni**：🔴 **`AUTO`（假的，且危险）**。
- **要什么参数**：**无**（`{"max_tasks"}` 这类参数**不认** —— `api.py:905` 直接调 `schedule.tick()`）。
- **🔴 本域第 2 处图鉴/判据漂移（未修，后果最重）**：它 `requires_params=[]`、`safe=true` ⇒ `omni` 判
  `✅ 只读无参，可直跑`。而**它不是只读**：一次无参调用就可能把生产里所有到期工作流跑掉。
  ⇒ **`omni run` 不许拿它当免卡调用**；要跑只能人明确要它跑（本规程按 `gbt-omni` 的"默认拒绝"办）。
- **实测读数**（隔离 store）：到期 → `{"ran": [{"schedule":"engine-sched","workflow":"engine-probe-ok","status":"ok","run_id":"engine-probe-ok-1790089709376"}], "count": 1}`；
  紧接着再 tick（未到期）→ `{"ran": [], "count": 0}` ⇒ **`count:0` ≠ 坏了，是"还没到期"**。
- **失败典型样子**：单个调度执行炸了 → 那条记 `{"schedule": …, "status":"error", "error": …}`，
  **不吞不瞒**（`schedule.py:106-110` 源码所见，未实跑）；其余调度照跑。
- **未验**：**生产 store 上的 `sched_tick` 本次没跑**（会动生产；见 §6）；`run_forever()` 常驻循环**未验**。

#### `sched_status` —— 查调度（只读）
- **用途**：`schedule.status(name=None)`（`schedule.py:116`）。给 `name` 返回那一条，不给返回全量。
- **门**：无。**改状态**：否（不在 `_STATE_CHANGING_KINDS` 里）。**omni**：`AUTO`（**这个是真的只读**）。
- **要什么参数**：无必填；可选 `name`。
- **实测读数**（生产 store，零写入）：无参 → `{"schedules": {"persona-evolve": {"workflow":"persona-evolve","every_seconds":600,"enabled":true,"defined_at":"2026-09-21T12:38:44","last_run_ts":1790089283.2848794,"last_status":"ok","last_run_at":"2026-09-22T22:01:23","last_run_id":"persona-evolve-1790089283387"}}, "count": 1}`。
  隔离 store 新调度 → 同样的形状，`last_status "ok"`、`last_run_id "engine-probe-ok-1790089709376"`。
- **失败典型样子**：🔴 **给不存在的 `name` 会 `user_error`，不是返回空**：
  `{"status":"error","message":"调度不存在: no-such-sched","error_class":"user_error"}` · **exit 1**
  （和 `wf_status` 的空列表语义**相反**，别记混）。

### C · 传输算子与缓存（2 位）

#### `transfer` —— 数据变换算子（**纯读，零副作用**）
- **用途**：`transfer.transfer(payload)`（`transfer.py:50`）。**14 个纯变换算子**：
  `collect / map / pluck / filter / merge / unique / sort / limit / flatten / split / join / rename / wrap / stats`。
  模块头原话："纯数据变换、零副作用、零外部依赖、零模型调用"。`filter` 复用引擎的 AST 白名单求值器
  （`expr` 里禁函数调用）。
- **门**：无。**改状态**：否（`transfer` 不在 `_STATE_CHANGING_KINDS` 里）。**omni**：`AUTO`（**真只读**）。
- **要什么参数**：**无必填** —— `op` 缺省是 `collect`（不是报错）。可选 `data`/`field`/`key`/`expr`/`count`/`sep`/`mapping`/`reverse`。
- **实测读数**（生产 store，零写入）：
  - `{"op":"stats","data":[{"id":"a","kind":"health"},{"id":"b","kind":"echo"}]}` → 本体
    `{"ok": true, "op": "stats", "data": {"type": "list", "len": 2, "items_type": ["dict"]}}`；
  - `{"op":"map","data":[{"name":"a"},{"name":"b"}],"field":"name"}` → `{"ok": true, "op": "map", "count": 2, "data": ["a","b"]}`；
  - `{"op":"nope"}` → 本体 `{"ok": false, "error": "未知算子: nope", "supported": [14 个算子名]}`，
    **但信封 `status:"ok"` · `stamp:true` · exit 0** ⇒ 这是 §5 红线②③的**活证据**。
- **失败典型样子**：未知算子 → 本体 `ok:false` + `supported` 清单（**exit 仍 0**，看 §5）；
  取不存在的字段路径 → 本体 `{"ok": false, "op": "map", "error": "KeyError: 路径不存在: <p>"}`（`transfer.py:144-145` 收口，源码所见，未实跑）。

#### `wf_cache_clear` —— 清空传输缓存
- **用途**：`engine.cache_clear()`（`engine.py:292`）。删掉 `store/transfer_cache.json`，返回清理条数。
  这份缓存是**节点级 `cache: true`** 写进去的：同 `(kind, 参数指纹)` 命中即复用，`cache_ttl` 默认 300 秒，上限 500 条。
- **门**：无。**改状态**：**是**（删生产文件）。**omni**：🔴 **`AUTO`（假的，且会动手）** ——
  `omni ask "清一下传输缓存"` 打出来的原文是 `✅ 只读无参，可直跑`。**它不是只读**。
- **要什么参数**：无。
- **幂等闸（实测）**：缓存**本来就是空的**时，`preflight._observe_cache_clear` 判 `matched` ⇒
  **不删、直接 `already_satisfied`**；缓存非空才会真删。**这不是"安全"，是"恰好没得删"。**
- **实测读数**（隔离 store）：先让一个 `cache:true` 节点把缓存写出来，再清 →
  `{"ok": true, "cleared": 1}`，且该文件随后真的不存在了。
  缓存命中侧的读数：同一工作流第二次跑，`elapsed_s` 从 `0.085` 掉到 `0.002`，
  节点结果里多出 `"gbt_cached": {"fingerprint": "a3f860300d9502a51243"}`。
- **失败典型样子**：**本机实测没抓到**（无参、无前置校验、清不存在的缓存文件也返回 `cleared: 0`）。
- **🔴 未验**：**清生产 store 的缓存本次没跑**（生产 `transfer_cache.json` 里现有一条
  `vision:1111111111111111` 的真缓存，删不得；见 §6）。

---

## 4. 要过哪道门：**静态查，不靠跑它才知道**（结论：本域**无门**）

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, {})          # 只读求值，不执行、不消耗授权
list(d.scopes)                          # → 这个位要过哪几个作用域
```

**逐个静态查出来的全量（`policy.py` 全文过了一遍，2026-09-22）**：

| 能力位 | `risk` | `scopes` | `restricted` |
|---|---|---|---|
| `wf_define` | low | `[]` | False |
| `wf_run` | low | `[]` | False |
| `wf_status` | low | `[]` | False |
| `wf_resume` | low | `[]` | False |
| `transfer` | low | `[]` | False |
| `wf_cache_clear` | low | `[]` | False |
| `sched_define` | low | `[]` | False |
| `sched_tick` | low | `[]` | False |
| `sched_status` | low | `[]` | False |

- **9/9 零作用域** —— `gbt_allinone/security/policy.py` 里**这 9 个位名一个都没出现**
  （不是"没查到"，是**真的没有分支**）。换载荷也不变（`{}` 与 `{"op":"clear"}` / `{"name":"x"}` 结果一致）。
- ⇒ **本域**目前**不会**产生 `denied` 信封，**也没有 `missing_scopes` / `how_to_grant` 可抄** ——
  本规程**不编一个门出来**。若将来有人给某个位挂上作用域，授权**只能主人在终端发**：

  ```powershell
  python -m gbt_allinone auth grant --scope <作用域> --ttl 600
  ```
  （实测 `py -3.14 -m gbt_allinone auth --help` 原文：`用法: gbt_allinone auth [status|grant --scope <s> --ttl <s> --purpose <text>]`；
  `auth_gate.py:201-202` 的 `how_to_grant` 原文是 `终端运行: python -m gbt_allinone auth grant --scope <s> --ttl 600`。
  **AI 永远无权给自己发授权**，缺授权就如实报缺。）

**🔴 但"零作用域"绝不等于"只读"** —— 这是本域最容易读错的地方，两道判据分开看：

| 判据 | 来源 | 说的是什么 |
|---|---|---|
| `policy.evaluate().scopes` | `security/policy.py` | **要不要人工授权**（本域全不要） |
| `preflight.is_side_effect()` / `_STATE_CHANGING_KINDS` | `preflight.py:47-59` | **会不会改框架自身状态**（本域**6 个会**） |

`preflight._STATE_CHANGING_KINDS` 里属于本域的 6 个：**`wf_define` · `wf_run` · `wf_resume` ·
`wf_cache_clear` · `sched_define` · `sched_tick`**（`preflight.py` 的注释原话：
"安全策略没有覆盖、但会改变框架自身状态的动作；新增动作默认在这里显式声明，**不能靠"没写 scope"就当只读**"）。
⇒ 这 6 个带**并发动作租约**（`store/action_guard/`，同参数动作在跑时第二发返回
`{"status":"already_running","reused":true,"in_flight":true,…}` 而**不重复动手**）与**幂等复用闸**（§3 实测）。

**哪些位 `omni` 会替你自动跑**（`auto_run_verdict` 实算，**6 个 AUTO**）：

| 位 | omni 判 | 这个 AUTO 可信吗 |
|---|---|---|
| `wf_status` | AUTO | ✅ 真只读 |
| `sched_status` | AUTO | ✅ 真只读 |
| `transfer` | AUTO | ✅ 真只读（纯变换） |
| `wf_cache_clear` | AUTO | ❌ **假的**：它会删 `transfer_cache.json` |
| `sched_tick` | AUTO | ❌ **假的**：它会真跑去执行到期工作流 |
| `sched_define` | AUTO | ❌ **假的**：它事实必填 name+workflow+every_seconds |
| `wf_define` / `wf_run` / `wf_resume` | NO | 理由：`需要参数 name,nodes` / `name` / `run_id` |

⇒ **"在 AUTO 名单里"从来不等"只读"。** 本规程的用法：**只让 `omni` 自动跑前 3 个**；
后 3 个哪怕 `omni` 说"可直跑"，也**必须人明确要它跑**才动。

> `engine` **不在** `DANGER_DOMAINS`（那是 `pipeline`/`infra`/`dangerous`/`integration`）——
> 但这**不代表本域安全**：它是**会改框架自身状态**的域（A/B 两簇共 6 个位），逐位仍按上表判。

---

## 5. 🔴 读数红线（先问"这是事实，还是我读错了地方"）

1. **被拒时是"扁平错误信封"，不是常规信封**。
   `missing_scopes`（或 `missing`）/ `reason` / `how_to_grant` / `note` 在**顶层**，
   **没有 `gbt_result`**。`five-dim.py:108-118` 的 R-H299 注释就是拿一次事故换的：
   原来只读 `r["gbt_result"]` ⇒ 被拒时为空 ⇒ 打出来是
   **`status: unknown · denied: false` —— 门明明说"拒了"，报表却说"未知、没拒"**。
   ⇒ **读顶层字段**，别只盯 `gbt_result`。
   **本域实况**：9 位零作用域 ⇒ **本域目前跑不出 `denied`**，这条红线是从 `llm` 域继承的**报告层纪律**，
   **本域实例：未验**。将来若挂了门，照抄 `missing_scopes`（**全量数组**，别只抄 `reason` ——
   `reason`/`how_to_grant` 只覆盖第一个缺的作用域）。
2. **信封 `status:"ok"` ≠ 本体 `ok:true`** —— 本域**两个活例**：
   - `transfer` 未知算子：信封 `status:"ok"` · `stamp:true`，本体 `{"ok": false, "error": "未知算子: nope"}`；
   - `wf_run` 工作流整体失败：信封 `status:"ok"` · `stamp:true`，本体 `"status": "failed"` · `nodes` 里有 `"error"`。
   ⇒ **判成败只看本体**（`result.ok` / `result.status`），**不看万能插信封**。
3. **退出码不可信**：`five-dim.py:131` 只在 `status ∈ (ok, success)` 时返回 0，
   `denied` / `user_error`（信封 `status:"error"` 且 `error_class:"user_error"`）才返回 **1**。
   ⇒ **业务拒绝也 exit 0**（`transfer` 未知算子实测 exit 0）；反过来 **exit 1 也别一律读成"命令敲错了"**，
   先看 `status` 是 `error` 还是 `denied`，再看 `error_class` 是不是 `user_error`。
4. **`stamp: true/false` 是回归印章的有无，不是成功与否**：本域实测 —— 成功/已满足/空结果都是
   `stamp true`；`user_error` 一律 **`stamp false`**（连 `denied:false` 也是 false）。
5. **"没参数"和"参数错"要看位**：`wf_status` 给错名字 → **空列表 · exit 0**（不是错）；
   `sched_status` 给错名字 → **`user_error` · exit 1**（是错）。**同一个域里两种语义并存**，别套用。
6. **`already_satisfied` ≠ "这次干了活"**：`wf_define` / `sched_define` / `wf_cache_clear` 都有幂等复用闸，
   返回 `{"status":"already_satisfied","reused":true}` 时**盘上什么都没改**。
   要证"真改了"，看 `observation.reason`（`definition_already_equal` / `schedule_already_equal` / `cache_already_empty`）
   与**调用前后文件哈希**，不看返回体的 `ok:true`。
7. **`result.status:"ok"` 也不能只看一层**：`wf_run` 会把**节点自身声明的 `blocked`/`failed`** 当成节点失败
   （`engine.py:401-409`：`能力深层状态: …`）—— 深层失败不会被"信封 ok"洗白。
8. **图鉴是索引，实测才是读数**。本次实测抓到本域**两处漂移**（都**未修**，`common` 待办）：
   `sched_define` 图鉴 `requires_params=[]` 而事实必填三参（源码 `schedule.py:43-53` + 实测无参报 `需要 name`）；
   `sched_tick` / `wf_cache_clear` 被 `omni` 判 `AUTO`（"只读无参可直跑"）而**它们会改状态**。
   ⇒ **图鉴/判据对不上时以实测为准，并把漂移记下来**；修注册表要动 `caps_registry.py` / `omni.py`，
   **本规程不擅自动手**。

---

## 6. 🔴 隔离实测账（哪些是现场真跑、哪些没验、凭什么这么说）

**纪律**：本域 6 个位会改状态，其中 `wf_run`/`sched_tick` 这类"真跑一个工作流"**落盘**、`wf_cache_clear` **删文件**。
本规程的做法是 —— **生产 store 零写入**，凡是要落盘的**都在隔离 store 里跑**：

- 隔离机制是**仓库自带的**：`gbt_allinone/_paths.py` 的 `GBT_STORE_DIR`（注释原文："支持 GBT_STORE_DIR 隔离（测试用）"；
  另有 `verify_store_binding()` 防"绑定与环境不一致"的静默走旧绑定）。**它不改任何门、不消耗任何授权**
  （本域本来也没有授权门），只是把 store 指到临时目录。
- 实测环境：`GBT_STORE_DIR=%TEMP%\gbt-engine-probe`（临时目录，跑完已删除）。

**生产 store 前后自证（这一条是"零写入"的证据；快照时刻 2026-09-22 22:06 → 22:09）**：

| 文件/目录 | 跑之前 | 跑之后 |
|---|---|---|
| `store/workflows.json` | 10968 B · `E25950D6…8A2E0` | 10968 B · `E25950D6…8A2E0` |
| `store/schedules.json` | 318 B · `2052F682…8EF821` | 318 B · `2052F682…8EF821` |
| `store/transfer_cache.json` | 136 B · `44EF7103…7C301E` | 136 B · `44EF7103…7C301E` |
| `store/wf_runs/` | 183 份 | 183 份 |
| `store/action_guard/` | 325 个 | 325 个 |

（唯一因**本规程**而增长的是 `store/audit.jsonl` —— 那是**唯一门 `run_task` 固有行为**：每一次调用（含纯只读的
`wf_status`）都会落审计。本规程所说的"零写入" = **零业务产物、零状态文件改动**。）

**🔴 但生产 store 是"活的"，别把别人的账记到自己头上**（本次实测踩到）：
- 生产里**另有一条常驻调度**在跑 —— `sched_status` 实测只有一条 `persona-evolve`（`every_seconds: 600`），
  它按点自行改写 `store/schedules.json` 并往 `store/wf_runs/` 里加记录。观察期间就能看到
  `persona-evolve-<新时间戳>.json` 冒出来、`schedules.json` 的 `last_run_ts/last_run_id` 自己往前跳。
- 同一台机上**可能有别的会话/别的进程**也在调能力位（本次观察窗口内 `store/transfer_cache.json`
  就被**别的进程**清掉了 —— **不是本规程**：本规程的 `wf_cache_clear` 全程在隔离 store 里跑，
  临时目录里能自证"缓存是在隔离目录里生成、又在隔离目录里被清掉"）。
⇒ **纪律**：证"我没写生产"要**同时点前后各拍一次快照**并**记下时刻**，
不能拿"这个文件永远长这样"当判据；`store` 里出现变化时，先查是**常驻调度**还是**别的会话**，
再决定要不要算到自己账上。

**逐位验收状态**：

| 位 | 现场真跑过吗 | 跑在哪 | 没验的是什么 |
|---|---|---|---|
| `wf_status` | ✅ 真跑（无参 / 按名过滤 / `include_workflows` / 错名） | 生产 store（纯只读） | — |
| `sched_status` | ✅ 真跑（无参 / 错名） | 生产 store（纯只读） | — |
| `transfer` | ✅ 真跑（`stats` / `map` / 未知算子） | 生产 store（纯变换） | `filter`/`sort`/`rename` 等其余 11 个算子逐一的读数 |
| `wf_define` | ✅ 真跑（幂等复用✅生产；新定义/覆盖/bad kind/成环/悬空依赖✅隔离） | 生产=**零写入**的那条复用路径；其余=隔离 | **在生产 store 上新定义或覆盖**：未验（会写生产） |
| `sched_define` | ✅ 真跑（幂等复用✅生产；新调度/无参✅隔离） | 生产=零写入复用路径；其余=隔离 | **在生产 store 上新建/改调度**：未验 |
| `wf_run` | ✅ 真跑（成功✅ / 节点失败 fail_fast✅ / 未知名字✅） | **全部隔离**（会写 `wf_runs/`） | **在生产 store 上跑工作流**：未验；`timeout`/`when`/`fallback`/`routes`/5 层嵌套：未验 |
| `wf_resume` | ✅ 真跑（续失败 run / 续成功 run） | **全部隔离** | **在生产 store 上续跑**：未验 |
| `wf_cache_clear` | ✅ 真跑（`cleared: 1`） | **全部隔离** | **清生产缓存**：未验（快照时生产 `transfer_cache.json` 里确实躺着一条真缓存 `vision:1111111111111111`，删不得）；`already_satisfied` 分支：源码所见 |
| `sched_tick` | ✅ 真跑（到期 `count:1` / 未到期 `count:0`） | **全部隔离** | **在生产 store 上 tick**：未验（会真跑去执行到期调度）；`run_forever()`：未验 |

**为什么生产侧的落盘路径"不做"**：`AGENTS.md` 的生产面红线（"生产只收成品"、"门只有一处"）
与 Owner 的硬要求一致 —— **只读的绝不写入生产**；要落盘/产生副作用的一律**不在生产里真跑**。
本次把这类动作挪到**隔离 store** 拿真实读数，**生产分毫未动**（上表自证）。
⇒ **要说"在生产里跑过工作流"，本规程没有这个读数，如实写「未验」。**

---

## 7. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不为了"绕过授权/绕过隔离"直接调 `gbt_allinone` 里的模块函数替掉 `run_task` 唯一门、
   或直接读写 `store/workflows.json` / `store/schedules.json` / `store/transfer_cache.json` 冒充能力层
   （`engine.py:544` 的 R-H99b 由来就是为治"偷读盘、口径散掉"）。
3. **不许把 `sched_tick` / `wf_cache_clear` 当只读**（它们在 `omni` 的 AUTO 名单里，**会改状态**）；
   **不许把 `sched_define` 当无参**（它必填三参）。
4. **不许把"信封 `status:ok`"当成功**：`transfer` 未知算子、`wf_run` 整体 `failed`，信封都是 `ok`。
5. **不许在生产 store 里跑落盘动作**（`wf_run`/`wf_resume`/`sched_tick`/`wf_cache_clear`/新 `wf_define`/新 `sched_define`）
   —— 要验就在 `GBT_STORE_DIR` 隔离 store 里验，并留生产前后哈希。
6. **不许把 `already_satisfied` 说成"这次干成了"**（那是"盘上已经一样、没动手"）。
7. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
   **不许动别的域**、不许改 `caps_registry.py` 的既有契约（漂移只记录，补登交主人）。
8. **不许把本规程当"万能插官方文档"**：节点级武器（`timeout`/`when`/`fallback`/`routes`/`cache`）
   的语义以 `gbt_allinone/engine.py` 源码为准，本文件管的是**我们这儿的纪律与读数口径**。

---

## 8. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-engine/SKILL.md` |
| 本规程（装机·托管目录） | `<用户目录>/.openclaw-autoclaw/skills/gbt-engine/SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 `AGENTS.md` 明令禁止） |
| 能力位名单（9 个） | `<仓>/state/skill_atlas.json`（`domain == "engine"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 执行引擎实现（**单一真相**） | `<仓>/gbt_allinone/engine.py`（定义/执行/续跑/缓存/`_topo_levels`/`_substitute`/`_eval_when`） |
| 定时触发器实现 | `<仓>/gbt_allinone/schedule.py` |
| 传输算子实现 | `<仓>/gbt_allinone/transfer.py` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()` —— 本域 9 位**均无分支** |
| "会不会改状态"判据 | `<仓>/gbt_allinone/preflight.py` 的 `_STATE_CHANGING_KINDS` / `is_side_effect()` / `_observe_workflow_define` / `_observe_schedule_define` / `_observe_cache_clear` |
| 门与拒绝信封 | `<仓>/gbt_allinone/api.py` 的 `run_task` / `_run_task_core`（唯一门）· `tools/codex-scripts/five-dim.py:101-131`（扁平信封的读法） |
| 自动执行判据 | `<仓>/tools/codex-scripts/omni.py` 的 `required_scopes()` / `auto_run_verdict()` / `DANGEROUS_NAME_RE` |
| store 落点与隔离 | `<仓>/gbt_allinone/_paths.py`（`store/workflows.json` · `store/wf_runs/` · `store/schedules.json` · `store/transfer_cache.json` · `store/action_guard/`；`GBT_STORE_DIR` 隔离） |
| 人话落点 | `python tools/codex-scripts/omni.py ask "定义并跑一个工作流"` → 落到 `wf_define`（`omnipulg` 通道） |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "engine": "gbt-engine",
```

加完后 `python tools/codex-scripts/omni.py gaps` 里 `engine 9 个能力位` 会从
`⏳ 在队里` 变成 `✅ 已深蒸 → gbt-engine`（本次实测它现在的状态原文就是
`⏳ 在队里  engine  9 个能力位  wf_define、wf_run、wf_status、wf_resume、transfer、wf_cache_clear…`）。

**验收（做完怎么证明真的做了）**：

```powershell
py -3.14 tools/codex-scripts/verify-distill.py --domain engine --skill gbt-engine
```

1. 两份产物（工作区源稿 + managed 安装件）**逐字节相同**（SHA-256 一致）；
2. 任一 `user_error` 位 → 打出来的 `message` 必须与 §3 的"失败典型样子"**逐字一致**（不一致就是哪漂移了，回来改本文件）；
3. 任一"改状态"位 → 跑之前**先记下 store 文件哈希**，跑之后**再记一次**；生产侧不一致 = 越界，即刻如实上报；
4. 声明"某位只读"之前，先过两道判据：`policy.evaluate()` 的 `scopes` **AND** `preflight._STATE_CHANGING_KINDS`
   —— **两道都过才叫只读**；拿不准就写"未验"。
