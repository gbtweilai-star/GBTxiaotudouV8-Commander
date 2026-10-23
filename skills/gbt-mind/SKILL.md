---
name: gbt-mind
displayName: GBT · 心智职业域用法规程（9 个能力位）
version: 1.0.0
description: GBT小土豆V8 的 `mind` 职业域（心智/性格内核/情绪/预演/元认知/主动汇报/本地脑/自动切换/脑库接入）用法规程。把这 9 个能力位逐个点清：用途、只读还是要授权、怎么调、要什么参数、失败长什么样；规定本域唯一入口是万能插 `five-dim.py cap <能力位>`、**9 位静态作用域全是空的**（不需要授权，但"不需要授权"≠"只读"）、授权只能主人在终端发；并记下本机实测过的读数陷阱（信封 `status:"ok"` 而本体是 `user_error` 且退出码 0 · `five-dim.py` 把返回截到 1500 字 · `caps_called_audit` 的 callers 只是"名字出现过" · 能力位自报的接线与拓扑要拿 AST 复核）。当用户要「让她先预演一下/该不该说这句话/现在什么情绪/主动汇报/元认知自省/性格内核/本地脑怎么切模型/脑库读一下」，或某个 mind 能力位报 user_error、读数对不上、怀疑"接线是假的"时使用。
triggers:
  - "心智"
  - "脑库"
  - "记忆库接入"
  - "性格内核"
  - "情绪内核"
  - "预演"
  - "该不该说"
  - "元认知"
  - "自省"
  - "主动汇报"
  - "本地脑"
  - "自动切换"
  - "persona_kernel"
  - "auto_switch"
  - "mind"
---

# GBT · 心智职业域用法规程（9 个能力位）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`mind` 域是**最容易被误读的一域** —— 9 个位里有 6 个自称"只读骨架"，
> 但"只读骨架"这四个字里**藏着两类完全不同的东西**：
> ① 真·只读（怎么调都不会落盘）；② **只读的是默认 op，写口就藏在 op 列表的最后一个**
> （`persona_kernel` 的 `evolve`、`meta_cognition` 的 `persist`、`brain_vault` 的 `remember`、
> `mind` 的 `observe/remember_lesson`）。混着用就会踩两类坑：
> **以为它不会写、结果写了**，和**以为它写了、其实是空转**。
> 本文件把「哪个位、哪个 op、只读还是写盘、要不要授权、失败长什么样」逐个钉死，
> 并把**本机实测过的坑**如实记下来 —— **没验过的一律写"未验"，不冒充验过**。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['<JSON载荷>']
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）。本域 9 位**静态作用域全空**（见 §4），
所以在本域里**不会**碰到授权门；但"不要授权"不等于"只读"——**写盘那几刀靠纪律不靠门**。

---

## 0. 这 9 个位分三簇（先认簇，再看位）

| 簇 | 位（kind） | 共 | 共同特征 |
|---|---|---|---|
| **A · 主干（有真写口）** | `brain_vault` · `mind` | 2 | 一个连 Obsidian 记忆库、一个跑心智闭环；**读写同门，写口在 op 里** |
| **B · 只读判据层（只判不做）** | `director_mood` · `proactive_report` · `observer_anchor` · `persona_kernel` · `meta_cognition` | 5 | 全是"律/闸/打分/成句"；**`persona_kernel` 除 `evolve` 外全只读**、**`meta_cognition` 除 `persist` 外全只读** |
| **C · 内调型皮层骨架（不加载模型）** | `local_brain` · `auto_switch` | 2 | 骨架期**机械解析**、**不调模型、不起服务、不出网、不落盘** |

**判据**：想**读/写记忆** → A；想**判一句话该不该说、现在什么情绪、这条律守没守住** → B；
想**看"本地模型/自动切换"这套设计长什么样、判据齐不齐** → C（它们**不替你切模型**）。

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个位 | 只读还是要授权 |
|---|---|---|
| 把记忆接上（记忆总纲 + 收集箱最近几条） | `brain_vault`（`op=recall`） | 只读，零作用域 |
| 看脑库在哪、多少笔记、有没有断链 | `brain_vault`（`op=status`，**空参默认**） | 只读，零作用域 |
| 往收集箱记一笔 | `brain_vault`（`op=remember`） | 🔴 **会写盘**（工作区外的 Obsidian 库）· 未验 |
| 看心智现在什么状态（情绪/心境/自评/推主） | `mind`（空参 → `op=status`） | 只读，零作用域 |
| 「这句话/这件事该不该说、说多长」 | `mind`（`op=decide`） | 只读，零作用域 |
| 开工前预演（评估/需要/推主/方案/元认知） | `mind`（`op=simulate` / `op=metacognition`） | 只读，零作用域 |
| 推进心智循环、沉淀一条阅历 | `mind`（`op=observe` / `op=remember_lesson`） | 🔴 **会写盘**（`store/mind_state.json`）· 未验 |
| 看导演现在什么情绪、这情绪会不会改事实 | `director_mood`（空参 → `status`） | 只读，零作用域（进程内状态） |
| 让导演"进入"一种情绪（看镜头怎么着色） | `director_mood`（`op=feel`） | 只读**不落盘**（进程内，进程退即失） |
| 一条消息值不值得主动上报、几道门拦没拦 | `proactive_report`（空参 → `model`；`op=decide`） | 只读，零作用域（**只判不说**） |
| 覆盖矩阵全表 + 缺口登记 | `proactive_report`（`op=coverage`） | 只读，零作用域 |
| 观察者锚点律（三公理/六短板/五红线） | `observer_anchor`（空参 → `axioms`） | 只读，零作用域 |
| 「这份报告是不是同一方既扫又报」 | `observer_anchor`（`op=check`，给 observer/checker） | 只读，零作用域 |
| 全仓审计器有没有免检的、递归封顶在哪 | `observer_anchor`（`op=auditors` / `op=depth_caps`） | 只读，零作用域 |
| 关键节点人在不在场 | `observer_anchor`（`op=presence`） | 只读，零作用域（**会照实报一个已知缺口**） |
| 看性格内核（外温十律 / 内刚四基石 / 十条红线） | `persona_kernel`（空参 → `constitution`） | 只读，零作用域 |
| 拿外温十律闸一句话 | `persona_kernel`（`op=check`） | 只读，零作用域 |
| 拿内刚四基石闸一个动作类型 | `persona_kernel`（`op=action`） | 只读，零作用域 |
| 驱动心智演化 + 给情绪上色 | `persona_kernel`（`op=evolve`） | 🔴 **唯一写口**（经 `mind_engine` 落 `store/mind_state.json`）· 未验 |
| 元认知五红线 / 缺口类型 / 知识落点 | `meta_cognition`（空参 → `law`） | 只读，零作用域 |
| 查外部资料要哪三个作用域 | `meta_cognition`（`op=external_scopes`） | 只读，零作用域（**只是"说要授权"，自己不出网**） |
| 「现在该硬做还是先查先问」 | `meta_cognition`（`op=decide`） | 只读，零作用域 |
| 把自省出的缺口落进 `work_log` | `meta_cognition`（`op=persist`） | 🔴 **会写盘**（`store/work_log.jsonl`）· 未验 |
| 本地脑的链路/硬件门槛/候选模型 | `local_brain`（空参 → `status`；`op=layers` / `hardware` / `models`） | 只读，零作用域 |
| 「这句话该用哪个本地模型」 | `local_brain`（`op=route`） | 只读，零作用域（**只是选名，不加载**） |
| 切换序列 / 空闲卸载策略 | `local_brain`（`op=plan_switch` / `check_idle`） | 只读，零作用域（**只排步骤，不真切**） |
| 自动切换引擎的形状/四层/19 条短板 | `auto_switch`（空参 → `status`） | 只读，零作用域 |
| 机械解析一句话的意图 + 置信度 | `auto_switch`（`op=analyze`） | 只读，零作用域（**骨架期不调模型**） |
| 置信度够不够、要不要先问主人 | `auto_switch`（`op=gate_intent`） | 只读，零作用域 |
| 歧义分类 / 跨语言 / 否定条件句 / 难度阈值 | `auto_switch`（`op=ambiguity` / `language` / `negation` / `difficulty`） | 只读，零作用域 |

**不在这 9 个里的事**：记忆**库本身**怎么建、收集箱格式、junction、断链口径 → `gbt-brain-vault`（那是库规程）；
屏幕/点击/读网页 → `gbt-tentacle`；要过 `external_llm` 的自主环与 Codex 桥 → `gbt-llm`；
Ark 云端生图/账单 → `gbt-arkcli`。**本域不替它们干活**。

---

## 2. 怎么调（万能插唯一门）

```powershell
# ── A · 主干 ──
py -3.14 tools/codex-scripts/five-dim.py cap brain_vault                                  # 只读：空参默认 op=status
py -3.14 tools/codex-scripts/five-dim.py cap brain_vault '{"op":"recall","limit":3}'      # 只读
py -3.14 tools/codex-scripts/five-dim.py cap brain_vault '{"op":"remember","text":"…"}'   # 🔴 写盘（追加收集箱）· 未验
py -3.14 tools/codex-scripts/five-dim.py cap mind                                         # 只读：空参默认 op=status
py -3.14 tools/codex-scripts/five-dim.py cap mind '{"op":"decide","event":"task_failed","importance":0.9}'   # 只读
py -3.14 tools/codex-scripts/five-dim.py cap mind '{"op":"simulate","event":"pre_work"}'  # 只读
py -3.14 tools/codex-scripts/five-dim.py cap mind '{"op":"observe","event":"task_started"}'  # 🔴 写盘 · 未验
py -3.14 tools/codex-scripts/five-dim.py cap mind '{"op":"remember_lesson","situation":"…","lesson":"…"}'  # 🔴 写盘 · 未验

# ── B · 只读判据层 ──
py -3.14 tools/codex-scripts/five-dim.py cap director_mood
py -3.14 tools/codex-scripts/five-dim.py cap director_mood '{"op":"feel","emotion":"喜","drive":"闻","intensity":0.8,"trigger":"本规程实测"}'
py -3.14 tools/codex-scripts/five-dim.py cap proactive_report
py -3.14 tools/codex-scripts/five-dim.py cap proactive_report '{"op":"coverage"}'
py -3.14 tools/codex-scripts/five-dim.py cap observer_anchor
py -3.14 tools/codex-scripts/five-dim.py cap observer_anchor '{"op":"presence"}'
py -3.14 tools/codex-scripts/five-dim.py cap observer_anchor '{"op":"auditors"}'
py -3.14 tools/codex-scripts/five-dim.py cap observer_anchor '{"op":"depth_caps"}'
py -3.14 tools/codex-scripts/five-dim.py cap observer_anchor '{"op":"check","observer":"甲方","checker":"乙方"}'
py -3.14 tools/codex-scripts/five-dim.py cap persona_kernel                               # 只读：空参默认 op=constitution
py -3.14 tools/codex-scripts/five-dim.py cap persona_kernel '{"op":"laws"}'
py -3.14 tools/codex-scripts/five-dim.py cap persona_kernel '{"op":"check","text":"<要闸的那句话>"}'
py -3.14 tools/codex-scripts/five-dim.py cap persona_kernel '{"op":"action","action_type":"passive_waiting"}'
py -3.14 tools/codex-scripts/five-dim.py cap persona_kernel '{"op":"evolve","cycles":1}'  # 🔴 唯一写口 · 未验
py -3.14 tools/codex-scripts/five-dim.py cap meta_cognition                               # 只读：空参默认 op=law
py -3.14 tools/codex-scripts/five-dim.py cap meta_cognition '{"op":"external_scopes"}'
py -3.14 tools/codex-scripts/five-dim.py cap meta_cognition '{"op":"decide","guess":true}'
py -3.14 tools/codex-scripts/five-dim.py cap meta_cognition '{"op":"persist","gaps":[{"type":"missing_context","note":"…"}]}'  # 🔴 写盘 · 未验

# ── C · 内调型皮层骨架 ──
py -3.14 tools/codex-scripts/five-dim.py cap local_brain
py -3.14 tools/codex-scripts/five-dim.py cap local_brain '{"op":"route","task":"帮我写个 Python 脚本"}'
py -3.14 tools/codex-scripts/five-dim.py cap local_brain '{"op":"plan_switch","current":"Qwen2.5-7B-Instruct","target":"Qwen2.5-Coder-7B","resident":["Qwen2.5-7B-Instruct"]}'
py -3.14 tools/codex-scripts/five-dim.py cap local_brain '{"op":"check_idle","keep_alive_s":300}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_switch
py -3.14 tools/codex-scripts/five-dim.py cap auto_switch '{"op":"analyze","text":"帮我写个 Python 脚本"}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_switch '{"op":"gate_intent","confidence":0.5}'
py -3.14 tools/codex-scripts/five-dim.py cap auto_switch '{"op":"negation","text":"不要删这个文件"}'
```

🔴 **两条本机实测的传参/读数坑（都踩过）**：

1. **PowerShell 里传 JSON：用单引号原样包住**（`'{"op":"recall","limit":3}'`）。
   写成 `'{\"op\":\"recall\"}'` 会让 `five-dim.py:106` 的 `json.loads` 直接抛
   `JSONDecodeError: Expecting property name enclosed in double quotes`
   —— **还没碰到门就死了**，而且看起来像"命令写错了"。**本次实测重现了一次。**
2. **`five-dim.py` 把返回截到 1500 字**（`five-dim.py:130` 的 `[:1500]`）。
   实测：`cap proactive_report` 的 `sources` 列表**在半截处断掉**（第 10 条 "赚钱机会" 后面就没了）。
   ⇒ 要看全量请**换一条同样过门的路**（同样的 `run_task`，只是不截断）：

   ```powershell
   py -3.14 -c "import gbt_allinone as g, json; r=g.run_task('proactive_report',{'op':'coverage'}); e=r.get('gbt_result') or r; print(json.dumps(e.get('result') if isinstance(e.get('result'),dict) else e, ensure_ascii=False, indent=1))"
   ```

   **这不是绕门**：走的还是 `run_task` 同一道门，只是去掉了显示层截断。

---

## 3. 9 个能力位逐个点（实测读数 + 失败典型）

> 下表 `门` = 静态查出来的作用域（见 §4）；`omni` = `omni.py auto_run_verdict()` 会不会自动替你跑（本次实算）。

### A · 主干（读写同门）

| 位 | 用途 | 门 | 参数 | omni | 实测关键字段 | 失败典型样子 |
|---|---|---|---|---|---|---|
| `brain_vault` | Obsidian 脑库接入：`status`（体检）/ `recall`（接记忆）/ `remember`（追加一条） | 无 | 空参→`status`；`recall` 可带 `limit`；`remember` 要 `text` | AUTO | 空参：`vault "C:\\Users\\ADMIN\\Documents\\Codex\\ObsidianVault"` · **`notes 10`** · **`wikilinks 25`** · **`unresolved []`** · `canvas 1` · `inbox_exists true` · `main_note_exists true` · `checked_at "2026-09-22T22:07:21"`；`recall`：`main_note` 头是 `# 记忆总纲` · **`inbox_lines 2`** · `recent ["# 所有记录","这里会自动按时间追加 QuickAdd 记下的内容。"]` | 🔴 **未知 op 是"信封 ok、本体 error"**：`{"op":"nope"}` → 顶层 `status "ok"` · `stamp true` · 而本体 `{"status":"error","message":"未知动作: nope","error_class":"user_error"}`（**连 `ok` 键都没有**）· **退出码 0**。见 §5 红线②③ |
| `mind` | 心智引擎：状态 / 感知 / 预演 / 召回 / 反思 | 无 | 空参→`status`；`op` 可为 `status/pulse/observe/cycle/appraise/infer_owner/simulate/metacognition/remember_lesson/recall/decide/pre_work` | AUTO | 空参：`state "awake"` · `mood "平稳"` · `expression "happy"` · `presence "可靠搭档"` · `lesson_count 0` · **`history_count 240`** · **`reflection_count 14`** · `owner_model.state "focused"` · `owner_model.confidence 0.36` · `operations` 12 条；`{"op":"decide","event":"task_failed","importance":0.9}` → **`action "speak_now"`** · `priority 88` · `reason "失败与阻塞必须如实汇报"` · `mode "inspect_then_act"` · `selected_option "ask"` · `posture "steady_problemsolve"` · `confidence 0.6262` · 内嵌 **`persona_gate.advisory "clean"`**（真接线，见 §5 红线④） | 未知 op：`status error` · `message "未知 op: nope（可用: …）"` · `error_class user_error` · **exit 1**（与 `brain_vault` 的 exit 0 **不是一回事**） |

**写口在哪（源码/AST 复核，不抄自报）**：
- `gbt_allinone/mind_engine.py` 里 `locked_json_update` 只出现在两处 —— `observe()`（1546 行）与
  `remember_lesson()`（1600 行）；其余 `status/pulse/decide/appraise/infer_owner/simulate/metacognition/recall`
  只 `load_json`（1584/1629/1673/1701/1709/1722/1743/1797）⇒ **读 op 不落盘**。
- `brain_vault.py` 的 `open` 3 处（61/73 读、**129 是 `"a"` 追加**），
  **全文件没有 `unlink/remove/rmtree/truncate`** ⇒ "没有任何删除路径"在源码层成立。
  但 `remember` 写的是**工作区外**的 `Documents\Codex\ObsidianVault\收集箱.md`。

> ⚠️ **本规程不跑写口**：`remember` / `observe` / `remember_lesson` 一律**未验**（原因见 §6 末"未验清单"）。

### B · 只读判据层（只判不做）

| 位 | 用途 | 门 | 参数 | omni | 实测关键字段 | 失败典型样子 |
|---|---|---|---|---|---|---|
| `director_mood` | 导演情绪内核：七情 + 六欲 + 半衰期 + 镜头 | 无 | 空参→`status`；`feel` 要 `emotion`（七情），可带 `drive/intensity/trigger/half_life_s` | AUTO | 空参：`emotion "平静"` · `intensity 0.0` · `calm true` · **`half_life_s 1800.0`** · `lens {affect:"不额外着色，照读数呈现", never:"平静不等于没立场：该报的红照报"}`；`feel 喜/闻/0.8` → 返回 `ok true` · `drive_meaning "看见真相"` · **`intensity 0.8`** · `since 1790089728.5195618` · `age_s 0.0` · `calm false` · **`lens.never "不许把『待认领』写成『已完成』"`** | 🔴 **情绪不跨进程**：`feel` 只改进程内状态，`feel` 与随后的 `status` 是**两次独立进程** ⇒ 下次 `cap director_mood` 一定回 `平静`。这是设计（源码红线③④：不写盘、低阈值自动退回平静），**不是坏了**。非法情绪名会被 `run()` 抛错（`未知情绪`）→ 走 `status error` 那条路 |
| `proactive_report` | 主动汇报判据层：四类汇报 + 八维打分 + 七道门 + 成句 + 渠道 | 无 | 空参→`model`；`op` 可为 `model/sources/kinds/dimensions/gates/channels/coverage/score/threshold/gate/compose/route/decide/budget/idle_hunt` | AUTO | 空参：`readonly true` + `sources` 13 条（**被 1500 字截断**）；`coverage` → **`cells 2912`** · **`gap_count 2`** · `gaps` 两条：源 `external_world`（趋势源未接·不擅自出网）+ 渠道 `tray`（托盘通知没做口）· `threshold_now 0.55` · axes = 源13 / 维度8 / 门7 / 渠道4 / 反馈3；`decide`（机会类带 url/value 0.8）→ **`speak true`** · `score 0.586` · `channels ["timeline","observer"]` · `text "[赚钱机会] 发现一个能变现的新工具，附带链接。"` · 门 `blocked []` | 🔴 **它只判不说**：`decide` 恒返 **`delivered: false`** —— 出声是宿主的事。**别把 `speak:true` 读成"已经说了"**。`score` 里凡没给证据的维度都标 `assumed(...)`，**那不是已核实** |
| `observer_anchor` | 观察者锚点律：三公理 + 六短板 + 五红线读数 | 无 | 空参→`axioms`；`op` 可为 `axioms/boards/red_lines/check/auditors/depth_caps/terminals/presence` | AUTO | 空参：三公理（分离/自审/终止点）+ `core_law "系统最终要靠一个「不会被系统自己改写」的锚点，这个锚点只能是人。"`；`presence` → **`trusted_owner_session_now false`** · **`known_gap "可信主人会话下 policy.authorize() 直接放行受限动作…"`**；`auditors` → **`total 23` · `orphan_count 4`** · orphans = `deploy/selfcheck_configs.py` · `tools/false_report_audit.py` · `holo_pet/_h1_verify.py` · `holo_pet/deploy_check.py`；`depth_caps` → **`total 5`**（engine 5 / data_policy 8 / auto_switch 3 / tentacle_cognition 3 / visual_cortex **0**）；`check` 同方既扫又报 → `ok false` · `denied true` · `blocked ["no_self_report"]` | `check` 的 `note` 明说：五条红线里**只有"同一方不许既扫又报"能单次机械判定**，其余四条是**全仓读数**（用 `auditors/depth_caps/terminals/presence` 取），**不假装一次调用就能判完**。`depth_caps` 里 `cap 0` 那条（`visual_cortex`）**不是"封顶为 0"**，是扫到的字面量 |
| `persona_kernel` | 性格内核 v4.0：外温表达十律 + 内刚四基石 + 十条机械红线 | 无 | **有默认**（空参→`constitution`）；`op` 可为 `constitution/laws/bedrocks/red_lines/check/action/scan/color/evolve` | **NO（"需要参数 op"）** | 空参：`version "4.0"` · `guardian "公主土豆"` · `outer.laws` 10 条（**machine 5**：short/warm/sincere/calm/measure；**human 5**：linger/precise/blank/awake/empathy）· `inner.bedrocks` 4 条原文一字不差；`check`（"加油，你一定行。你应该马上开始。抱歉，抱歉。"）→ `ok false` · **`denied true`** · 4 hits（鸡汤×2 / 说教×1 / 道歉≥2×1）· `machine_laws_checked [short,warm,sincere,calm,measure]` · **`human_pending [linger,precise,blank,awake,empathy]`**；`action passive_waiting` → `bedrock "initiative"` · `red "no_passive_wait"` · `red_layer "action"` | 🔴 ① **`check` 判 `denied:true` 时退出码仍是 0**（信封 `status ok`）；② **`human_pending` 那五律没判**，返 `note` 明说"未判 ⇒ 不声称通过" —— **别把 `ok:true` 读成"十律全过"**；③ `op` 非法 → `status error` · `message "未知 op 'nope'（可用：…）"` · `error_class user_error` · exit 1 |
| `meta_cognition` | 元认知循环：五红线 + 缺口类型 + 查内/查外/问主人/沉淀 | 无 | 空参→`law`；`op` 可为 `law/knowledge_spots/external_scopes/reflect/reflections/short_boards/decide/persist` | AUTO | 空参：五红线原文 · `gap_types` 4（missing_context/uncertain/unknown_topic/missing_param）· `scopes` 5（tentacle/brain/router/gate/audit）· **`log_ref "root_fix.work_log"`** · **`persisted_reflections 0`** · 自己点名 **`non_readonly_op "persist（会写 root_fix.work_log）"`**；`external_scopes` → `scopes ["network_private","external_llm","data_export"]` · `note "查外部资料必须先拿这三个作用域之一（主人发授权）"`；`decide guess=true` → `ok false` · `denied true` · `rule "no_guessing"` | 🔴 **`short_boards` 在单进程里必然报不达标**：本次实测 → `ok false` · `rule "brain_not_covered"` · `scopes_seen []` · `reflections 0`。原因是**自省记录是内存态**（`MetaCognitionLoop` 每次新建进程即空），所以"大脑也自省"这条**永远过不了单次调用**。**这不是缺陷，是它把自省口与落盘口分开了** —— 要留痕必须显式点名 `persist`（唯一写盘 op，本次**未验**）；`external_scopes` **只说要授权，它自己不出网** |

### C · 内调型皮层骨架（不加载模型）

| 位 | 用途 | 门 | 参数 | omni | 实测关键字段 | 失败典型样子 |
|---|---|---|---|---|---|---|
| `local_brain` | 本地原生脑骨架：模型=皮层（可换）/ 主机=纪律层（不可换）；五层链路 + 五红线 + 多模型路由/切换序列 | 无 | 空参→`status`；`op` 可为 `status/layers/redlines/hardware/models/check_exec/check_irreversible/check_params/check_trace/check_identity/multi_model/route/plan_switch/check_idle` | AUTO | 空参：`type "internal"` · **`model_steps [2,8]`** · **`layers 8`** · `positioning "本地模型 = **原生脑皮层**（可换）；主机 = **纪律层**（门禁/审计/身份内核，不可换）"`；`route "帮我写个 Python 脚本"` → `model "Qwen2.5-Coder-7B"` · `matched "编程 / 自动化脚本"`；`plan_switch` → `steps [unload Qwen2.5-7B-Instruct, load Qwen2.5-Coder-7B(keep_alive_s 300)]` · `note "先卸后载（不许新旧重叠）"` | 🔴 **判据比说法窄（实测踩到）**：`route "今天天气怎么样"` → `ok false` · `rule "no_model_for_task"`。它**不是坏了**：路由 `kw` 是字面词表（中文/聊天/通用/问答/写作…），"今天天气怎么样"一个都没命中 ⇒ **如实报不匹配，不许随便挑一个顶上**（源码原话）。`check_idle` 不给 `keep_alive_s` → `denied` · `rule "idle_policy_missing"` · `default_keep_alive_s 300`。⚠️ **它不加载模型、不起服务** —— "真切模型"这件事在本仓**没有实现**，所以那一刀**不存在可验读数**（如实记：未验） |
| `auto_switch` | 自动化切换引擎骨架：四层 + 一回灌；19 条短板登记 | 无 | 空参→`status`；`op` 可为 `status/pipeline/intent_layers/switch_rules/audit/redlines/analyze/classify/pick/gate_intent/cross_check/check_exec/log_model/gate_irreversible/check_identity/layers_v2/short_boards/ambiguity/language/negation/difficulty/degradation/concurrency/dispatch_reason/depth/exec_trace/intermediate/matches/independent_checker/feedback/drift` | AUTO | 空参：`threshold 0.8` · `version "v2.0（R-H232 蒸馏 + 补短板）"` · `pipeline` 四层（意图/调度/执行/校验）· `feedback_loop`（校验层→意图层）· **`short_boards 19`** · **`wiring "**接线点只有一个：Intent JSON**"`**；`analyze "帮我写个 Python 脚本"` → `parsed.action "代码"` · **`confidence 0.9`** · `needs_clarification false`；`gate_intent 0.5` → `ok false` · `denied true` · `rule "low_confidence_ask_owner"`；`negation "不要删这个文件"` → `needs_care true`；`cross_check`（只给一次）→ `denied` · `rule "cross_check_incomplete"` · **`confidence 0.0`** | 🔴 **自报的 `wiring` 是设计口径，不是可测接线**：AST 实测 `analyze_intent` 全仓**只有一个调用点**（它自己 `run()` 的 619 行），`Intent(...)` 也只在 `analyze_intent` 里构造，**盘上没有第二处生产/消费 Intent JSON 的地方**。⇒ 别拿 `wiring` 那句话当"已经接好了"的证据（见 §5 红线④）。`cross_check` 只给一次复述时**置信度按 0 算**，不许拿单模型输出当已证 |

---

## 4. 要过哪道门：**静态查，不靠跑它才知道**

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, {})          # 只读求值，不执行、不消耗授权
list(d.scopes)                          # → 这个位要过哪几个作用域
```

**本域静态查出来的全量（2026-09-22 实测）**：

| 作用域 | 覆盖哪些位 |
|---|---|
| （**零作用域**） | **全部 9 个**：`brain_vault` · `mind` · `director_mood` · `proactive_report` · `observer_anchor` · `persona_kernel` · `meta_cognition` · `local_brain` · `auto_switch` |

**逐位 × 逐 op 都查过，且是 payload 无关的**（本次实测，`restricted` 一律 `False`、`reason` 一律空）：

- `brain_vault`：`{op:remember}` / `{op:recall}` / `{op:nope}` → `scopes []`
- `mind`：`{op:observe}` / `{op:remember_lesson}` / `{op:pre_work}` / `{op:nope}` → `scopes []`
- `persona_kernel`：`{op:evolve}` / `{op:constitution}` / `{op:nope}` → `scopes []`
- `meta_cognition`：`{op:persist}` / `{op:law}` → `scopes []`
- `director_mood` / `proactive_report` / `observer_anchor` / `local_brain` / `auto_switch` → `scopes []`

🔴 **本域最重要的一句话**：**"不要授权" ≠ "只读"**。
上面 4 个真写口（`brain_vault.remember` · `mind.observe/remember_lesson` · `persona_kernel.evolve` ·
`meta_cognition.persist`）**一个作用域都不要**，门**不会**替你拦 —— **写盘与否全靠纪律**。

**那授权怎么发（本域用不上，但口径要留）**：只能主人在终端发

```powershell
python -m gbt_allinone auth grant --scope <作用域> --ttl 600
```

或主人手写 `store/auth_grants.jsonl`。**AI 永远无权给自己发授权** —— 缺授权就如实报缺，
**不找旁路、不改 `security/policy.py`、不改 `auth_gate`**。

**哪些位 `omni` 会替你自动跑**（`auto_run_verdict()` 本次实算，**8 个 AUTO / 1 个 NO**）：

- **AUTO（8）**：`brain_vault` · `mind` · `director_mood` · `proactive_report` · `observer_anchor` ·
  `meta_cognition` · `local_brain` · `auto_switch`
- **NO（1）**：`persona_kernel` —— 理由实测原文 **`需要参数 op`**

⚠️ **"在 AUTO 名单里"只表示"无参调用不会立刻死在门上"，不表示"跑了就有用"**：
`brain_vault` 的 `remember`、`persona_kernel` 的 `evolve` 都要**点名 op 才动**；
而 `persona_kernel` 之所以判 NO，是注册表把它登记成"必填 op"（`caps_registry.PARAM_REQUIRED`，
`api.py:390` 的兜底其实是 `constitution`）—— **契约与实现有缝，按契约判。**

> `mind` **不在** `DANGER_DOMAINS`（那是 `pipeline`/`dangerous`/`infra`/`integration`）——
> 但这**不代表 mind 域安全**：它有 4 个真写口，且**都不需要授权**。逐位逐 op 判，别整域放行。

---

## 5. 🔴 报告层红线（先问"这是事实，还是我读错了地方"）

1. **被拒时是"扁平错误信封"，不是常规信封**。
   授权被拒时，`missing_scopes` / `reason` / `how_to_grant` / `note` 在**顶层**，
   **没有 `gbt_result`**。`five-dim.py:108-113`（R-H299 注释）就是拿一次事故换的：
   原来只读 `r["gbt_result"]` ⇒ 被拒时 `gr` 为空 ⇒ 打出来是
   **`status: unknown · denied: false`——门明明说"拒了"，报表却说"未知、没拒"**。
   ⇒ **读顶层字段**，别只盯 `gbt_result`。
   ⚠️ **本域内的诚实说明**：本域 9 位作用域全空，所以**本次没有一条"被门拒绝"的真读数**；
   上面这条是**报告层纪律**（依据 `five-dim.py` 注释 + `gbt-llm` 域实测），不是本域实测出来的。
   **将来某位若被挂了作用域，按 `missing_scopes / reason / how_to_grant` 三件套读，不绕门。**
2. **信封 `status:"ok"` ≠ 本体 `ok:true`**（本域实测抓到，**最值钱的一条**）：
   `{"op":"nope"}` 打给 `brain_vault` → 顶层 `status "ok"` · `stamp true` · `denied false`，
   而本体是 `{"status":"error","message":"未知动作: nope","error_class":"user_error"}`，**连 `ok` 键都没有**。
   ⇒ **永远看本体**；顶层 `status` 只说明"门放行了"。
3. **退出码不可信**（同一次实测）：上面那条 `brain_vault` 的 `user_error` **退出码是 0**；
   而 `mind` 的同类 `user_error` **退出码是 1**。两者**都是错的活的**——
   退出码既不能当"成功"也不能当"失败"，**只能当"命令跑起来了没有"**。
   判定一律回到本体字段（`ok` / `status` / `error_class` / `denied`）。
4. **自报不等于事实（要拿源码/AST 复核，别抄它的话）**。本域实测抓到**两处**：
   - 🔵 **跨域的那个著名例子**（`gbt-llm` 已登记，**本次我自己的 AST 独立复核过**）：
     某位自报 `note "五维合一：route→execute→verify→health 全链留痕"`，而 AST 实测
     `brain_unify`（`brain_exec.py:394-436`）是**星形** —— 分别直调 `route`(405) / `execute`(419) /
     `verify`(423) / `health`(428) 四维，**不是串链**；并且 `execute` 内部还会再调 `route`(259)。
     ⇒ **"全链留痕"是话术层，拓扑是事实层。**
   - 🔴 **本域自己的一处**：`auto_switch` 自报 `wiring "**接线点只有一个：Intent JSON**"`，
     AST 实测 `analyze_intent` 全仓只有**一个调用点**（它自己 `run()` 的 619 行），
     且全仓**没有任何第二处**构造或消费 Intent JSON ⇒ **这是设计口径，不是接线**。
     （对照：`mind_engine._persona_check` 自报"真接线"，AST 实测它**真的**在 1169 行
     `from .tools import persona_kernel` 并调 `check_expression`，`mind` 的返回里也**真的**带着
     `persona_gate` —— **这一处自报属实**。⇒ 自报要**逐条**验，不能整体信也不能整体不信。）
5. **`caps_called_audit` 的 `callers` 是"名字在代码里出现过"，不是"真被调用"**。
   本次实测该位：`total 147` · `wired_count 141` · `orphan_count 0`，
   本域 9 位的 `callers` 全部非空 —— **但其中至少三条是假接线**：
   `auto_switch` 的 callers 含 `tools/awesome_tools_index.py`（一张映射表里的字面量）与
   `tools/local_brain.py`（一句 docstring），**两处都不是调用**。
   ⇒ **`callers` 非空只说明"有人提过它的名字"**；要证真接线，**读那个文件的调用行**。
6. **读 op 与写 op 混在一个 `op` 里**：默认无参一定是只读 op（本域 9 位都如此），
   但**写口就在 op 列表的末尾**（`evolve` / `persist` / `remember` / `observe` / `remember_lesson`）。
   ⇒ 报"某位是只读的"之前，先问：**是"默认 op 只读"，还是"整位只读"？**
7. **`director_mood` 的情绪不跨进程**：每次 `cap` 都是新进程，所以 `status` 永远回 `平静`。
   **别把它读成"情绪没生效"**——`feel` 的返回里 `intensity 0.8` / `lens` 都在，只是它**不落盘**（设计如此）。
8. **能力位自报的数字要看它"数的是什么"**：`observer_anchor.depth_caps` 报 `visual_cortex` 的
   `cap 0`，那是**扫到的字面量 0**，不是"封顶为 0"；`meta_cognition.reflections` 报 `count 0`
   是**这个进程里没自省过**，不是"从来没自省过"。

---

## 6. 与 `gbt-brain-vault` 的分工（**别互相冒充**）

`brain_vault` 这个能力位**属于 mind 域**，而 `skills/gbt-brain-vault/SKILL.md` 讲的是
**那座 Obsidian 库本身**。两者**不是一回事**，撞在一起就会互相冒充：

| 谁 | 管什么 | 不管什么 |
|---|---|---|
| **`gbt-brain-vault`**（库规程） | 库根 `C:\Users\ADMIN\Documents\Codex\ObsidianVault` · 开工三读（记忆总纲/MOC-总览/收集箱）· 收集箱**追加格式**（一行一条·带时间戳）· `.obsidian\plugins` 是 **junction** 不许当普通目录删 · `模板/` `地图/` `日记/` 的用途 · 链接要写全路径否则图谱断链 | ❌ **它一个能力位都没点名**，**不是**这 9 个能力位的用法规程；不规定命令、门、参数、失败形状 |
| **`gbt-mind`**（本件） | `brain_vault` 能力位**怎么调**：`status` / `recall` / `remember` 三个 op 的命令、返回字段（`notes` / `wikilinks` / `unresolved` / `inbox_lines`）、**`remember` 是写盘那一刀**、失败形状（未知 op 是信封 ok + 本体 error + exit 0） | ❌ **不重写库结构**、不定收集箱格式、不说 junction 怎么处理 —— 那些去读 `gbt-brain-vault` |

**一句话**：**`gbt-brain-vault` 管"记忆文件长什么样、写在哪"，`gbt-mind` 管"用哪条命令去读它/写它、返回的字段怎么读"。**
实测交叉印证：`brain_vault status` 的 `vault` 字段回的就是 `gbt-brain-vault` 写的那条库根，
`main_note_exists true` / `inbox_exists true` 对应它说的"记忆总纲 + 收集箱"两篇 —— **两边口径一致，各说各的那一半**。

**本件不碰的**：不改 `gbt-brain-vault/SKILL.md`、不往库里写任何东西（`remember` 未验）、
不改 `security/policy.py`、不改 `tools/codex-scripts/omni.py`、不动别的域。

---

## 7. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不许为了"绕过授权"直接调 `gbt_allinone` 里的模块函数替掉 `run_task` 唯一门
   （AGENTS.md 明令：那是**未经授权的写入**，纪律上就是违规）。
   ⚠️ 本域 9 位**都不需要授权**，所以**在本域根本没有"绕门"的借口** —— 更要守纪律。
3. **不许把写口当只读口跑**：`brain_vault.remember` · `mind.observe/remember_lesson` ·
   `persona_kernel.evolve` · `meta_cognition.persist` 这 5 处**要写盘**；
   本规程**一律不代跑**，只给命令并标"未验"。
4. **不许把"信封 ok"说成"做成了"**：`status:"ok"` 只说明门放行了（§5 红线②）。
5. **不许把退出码当判据**：同一种 `user_error`，本域实测既有 exit 0 也有 exit 1（§5 红线③）。
6. **不许抄能力位的自报当事实**：`note` / `wiring` / `rule` 是话术层，
   **源码与 AST 才是事实层**；本域已有两处反例（§5 红线④）。
7. **不许把 `proactive_report.speak:true` 说成"已经汇报了"**：它恒返 `delivered:false`，只判不说。
8. **不许把 `local_brain` / `auto_switch` 说成"会切模型"**：它们**不加载模型、不起服务**，
   "真切换"在本仓没有实现 ⇒ 只能说"排了序列 / 判了意图"。
9. **不许把 `gbt-brain-vault` 当本件的替代**，也不许把本件当库规程（§6）。
10. **不许改 `tools/codex-scripts/omni.py`**（本域登记行由交付报告给出，不擅自动手）；
    **不许动别的域**、不许改 `policy.py`、不许改验收器。

---

## 8. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-mind/SKILL.md` |
| 本规程（装机·托管目录） | `~/.openclaw-autoclaw/skills/gbt-mind/SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 能力位名单（9 个） | `<仓>/state/skill_atlas.json`（`domain == "mind"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()`；放行口在 `authorize()`（**376 行** `if not decision.restricted or is_trusted(): return ok=True`） |
| 门与拒绝信封 | `<仓>/gbt_allinone/run_task`（唯一门）· `tools/codex-scripts/five-dim.py:101-131`（扁平信封读法 + **1500 字截断**） |
| 自动执行判据 | `<仓>/tools/codex-scripts/omni.py` 的 `required_scopes()` / `auto_run_verdict()` |
| 本域源码 | `gbt_allinone/brain_vault.py` · `gbt_allinone/mind_engine.py` · `gbt_allinone/tools/{director_mood,proactive_report,observer_anchor,persona_kernel,meta_cognition,local_brain,auto_switch}.py` |
| 分派入口 | `<仓>/gbt_allinone/api.py`（`mind` 在 138-144；`meta_cognition` 334-337；`proactive_report` 378-381；`observer_anchor` 382-385；`persona_kernel` 386-390；`director_mood` 419-423；`local_brain` 439-443；`auto_switch` 444-448；`brain_vault` 551-563） |
| 库规程（**分工件**） | `<仓>/skills/gbt-brain-vault/SKILL.md` |
| 人话落点 | `python tools/codex-scripts/omni.py ask "把记忆接上"` → 落到 `brain_vault`（`omnipulg` 通道） |

**未验清单（如实记，别读成"验过了"）**：

| 哪一刀 | 为什么未验 |
|---|---|
| `brain_vault` 的 `op=remember` | **会写盘**，且写的是**工作区外**的 `Documents\Codex\ObsidianVault\收集箱.md` —— 本规程不代跑 |
| `mind` 的 `op=observe` / `cycle` / `pre_work` / `remember_lesson` | **会写盘**（`store/mind_state.json` + audit + 镜像生命档案）—— 本规程不代跑 |
| `persona_kernel` 的 `op=evolve` | **本模块唯一写口**（AST 实测：只有 `evolve` 引用 `mind_engine.observe/mental_cycle`）—— 本规程不代跑 |
| `meta_cognition` 的 `op=persist` | **唯一写盘 op**（AST 实测：`work_log`/`mkdir` 只在 `persist_reflections` 里）—— 本规程不代跑 |
| `local_brain` 的"真加载/真切换模型" | **本仓没有实现**（骨架期不加载模型、不起服务）⇒ 没有可跑的读数 |
| `auto_switch` 的"真调模型做 L2 交叉验证" | **未接**（骨架期机械解析）⇒ 没有可跑的读数 |
| `proactive_report` 的**真实出声投递** | 本层恒 `delivered:false`；出声由宿主做，不在本能力位内 |
| "被门拒绝"的信封 | 本域 9 位作用域全空 ⇒ **本域内没有一条真拒绝读数**（§5 红线① 的诚实说明） |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_DOMAINS` 加一行

```python
    "mind": "gbt-mind",
```

现在 `python tools/codex-scripts/omni.py gaps` 里它仍是 **`⏳ 在队里  mind  9 个能力位`**（本次实测原文）。
加完后会变成 `✅ 已深蒸 → gbt-mind`。

**验收（做完怎么证明真的做了）**：

1. `py -3.14 tools/codex-scripts/verify-distill.py --domain mind --skill gbt-mind` → 必须 PASS；
2. `py -3.14 tools/codex-scripts/five-dim.py cap brain_vault` → 拿 `notes` / `wikilinks` / `unresolved`；
3. `py -3.14 tools/codex-scripts/five-dim.py cap mind` → 拿 `state` / `mood` / `history_count` / `operations`；
4. 声明"某位能用"之前先问自己：**这是实测读数，还是我读错了地方？**
   拿不准就写"未验" —— 本域已有两处"自报≠事实"的反例（§5 红线④）。
