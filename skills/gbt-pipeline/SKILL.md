---
name: gbt-pipeline
displayName: GBT · pipeline 职业域用法规程（18 个能力位 · 生产面/镜像面）
version: 1.0.0
description: GBT小土豆V8 的 `pipeline` 职业域（流水线/管线/发布/提交/回滚/部署/生产/镜像多维度）用法规程。把图鉴里这 18 个能力位逐个点清：用途、只读还是要授权、要哪个作用域、真命令、有没有落点声明要求、失败典型样子。规定本域唯一入口是万能插 `five-dim.py cap <能力位>`（一律走 run_task 唯一门），禁止直接调 mirror_space / deployment_rehearsal / qiankun / room_space 的模块函数绕门；规定 one_key_deploy 必须显式声明落点（room="<房间名>" 或 into_global_production=true），不声明落点直接拒绝；记下本机实测读数（mirror_scan 5/5 体检、mirror_status clean true 27 版本、svc_inspect 14 个服务全 down）与读数陷阱（reason 只报第一个缺的作用域、how_to_grant 只给一行、status ok 不等于本体 ok、退出码不可信、mirror_status 带 include_rehearsal 会绕过作用域门触发一次真实落盘）。当用户要部署/发布/晋升/回滚/排练/镜像成形/查发布记录/防复发扫描/服务巡检，或某个 pipeline 能力位报「需要人工授权」「未声明落点」时使用。
triggers:
  - "部署"
  - "上线"
  - "发布"
  - "晋升"
  - "回滚"
  - "排练"
  - "镜像空间"
  - "镜像多维度"
  - "生产面"
  - "落点"
  - "部署队列"
  - "一键部署"
  - "one_key_deploy"
  - "deploy_publish"
  - "需要人工授权"
  - "未声明落点"
---

# GBT · pipeline 职业域用法规程（18 个能力位 · 生产面/镜像面）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`pipeline` 是**生产面与镜像面**的域 —— 图鉴里 18 个能力位，
> 一半在**镜像多维度**里成形/推演/排练，另一半直接**写生产**。
> 它比别的域更严，因为**踩错一步就是"什么代码都被送到生产"**。三件事必须钉死：
> ① **写生产/镜像的动作一律走 `run_task`**（`five-dim.py cap` 就是那条路），
>    **禁止直接调模块函数**（`mirror_space.ascend()` / `deployment_rehearsal.release()` /
>    `qiankun.one_key_deploy()` / `room_space.release()`）—— 那会**绕开授权门**，是违规；
> ② **落点必须显式声明**：`one_key_deploy` 要么 `room="<房间名>"`（只写房间），
>    要么 `into_global_production=true`（写全局，必须人工授权）；**不声明落点 = 直接拒绝**；
> ③ **只读的真跑、写的一律不跑** —— 没验过的一律写「未验 + 卡在哪道门」，不冒充验过。
>
> **本文档只写规程，不做任何写动作**：全程未 submit / 未 deploy / 未 ascend / 未 release /
> 未 rollback / 未 shape 出任何东西落盘。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['<JSON载荷>'] [--full]
```

`cap` 一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。
（`--full` = 不再收窄 `result`；默认会把过大的 result 收成键清单。）

---

## 0. 这 18 个位分四簇（先认簇，再看位）

**以 `state/skill_atlas.json` 里 `domain == "pipeline"` 的 `kind` 为准，共 18 个，一个不多一个不少**：

| 簇 | 位（kind） | 共 | 门（静态查出来的） |
|---|---|---|---|
| **A · 只读（零作用域，可真跑）** | `mirror_scan` · `mirror_status` · `pipeline_versions` · `pipeline_status` · `ghost_guard` · `svc_inspect` | 6 | 全部 `scopes=[]` |
| **B · 镜像空间（成形/推演/排练/晋升）** | `mirror_shape` · `mirror_plan` · `mirror_simulate` · `mirror_parity` · `mirror_rehearse` · `mirror_release` · `mirror_ascend` · `mirror_rewind` | 8 | 逐位不同，且**两条是"看载荷才挂门"** |
| **C · 生产管线 + 队列** | `one_key_deploy` · `deploy_queue` · `pipeline_submit` · `pipeline_rollback` | 4 | 全部含 `deploy_publish` |
| — | 合计 | **18** | — |

**判据**：想**看一眼**（体检/状态/记录/巡检）→ A（真跑）；
想**在镜像里成形或推演** → B（要 `filesystem_write`）；
想**写生产** → C（要 `deploy_publish`，人工授权）。

🔴 **本域 18 个位在 `omni.py` 的 `auto_run_verdict()` 里全部判 `AUTO=False`**（2026-09-22 实算，
理由原话逐位见 §5）—— 因为 `pipeline` 在 `DANGER_DOMAINS = {"pipeline","dangerous","infra","integration"}`
里（`tools/codex-scripts/omni.py:105`），**整域进不了自动执行名单**。
⇒ 别指望 `omni run` 替你跑任何一位：**只读的那 6 位也要你自己敲 `five-dim.py cap`**。

> ⚠️ `DANGER_DOMAINS` 是 **`omni.py` 里的自动执行判据**，**不是** `policy.py` 里的拒绝名单 ——
> 逐位静态查过：`gbt_allinone/security/policy.py` 里**没有**名叫 `DANGER_DOMAINS` 的常量，
> 它只有 `evaluate()` 里一条条 `elif kind == ...`。**"危险域"的后果是"不自动跑"，不是"一律拒绝"。**

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个位 | 只读还是要授权 |
|---|---|---|
| 上线一个项目（抓取→镜像→验证→晋升） | `one_key_deploy` | 🔒 `deploy_publish`+`process_execute`+`filesystem_write`，**且必须声明落点** |
| 把 N 个项目排队、一个一个自动部署 | `deploy_queue` | `status` 只读；`submit`/`tick` 🔒 `deploy_publish` |
| 在镜像维度里成形/看镜像树 | `mirror_shape` | 无参只读；`path=` 写 🔒 `filesystem_write` |
| 镜像维度体检（晋升前置） | `mirror_scan` | 只读，零作用域 |
| 看/定"生产前排练计划" | `mirror_plan` | `plan=` 写 🔒 `filesystem_write`；无参只读 |
| 静态推演（文件/依赖图/端口/入口/契约） | `mirror_simulate` | 🔒 `filesystem_write` |
| 沙盒与生产环境契约一致性 | `mirror_parity` | 🔒 `filesystem_write` |
| 生产前排练（推演→一致性→沙盒闭环→指纹报告） | `mirror_rehearse` | 🔒 `process_execute`+`filesystem_write` |
| 排练全绿后一次性全量晋升 | `mirror_release` | 🔒 `deploy_publish`+`process_execute`+`filesystem_write` |
| 跨维晋升（写现实+护照+时间线） | `mirror_ascend` | 🔒 `deploy_publish` |
| 看维度状态/漂移/时间线史 | `mirror_status` | 只读，零作用域（⚠️ **别带 `include_rehearsal`**，见 §7） |
| 时间线回滚（回到过去的时间线） | `mirror_rewind` | 🔒 `deploy_publish` |
| 走"唯一交付通道"写生产 | `pipeline_submit` | 🔒 `deploy_publish`（带 `review`/`refine_rounds` 另加 `external_llm`） |
| 查产物版本史与当前指纹 | `pipeline_versions` | 只读，零作用域（**要 `name`**） |
| 回滚产物到历史版本 | `pipeline_rollback` | 🔒 `deploy_publish`（**要 `name`**） |
| 查发布记录 | `pipeline_status` | 只读，零作用域 |
| 防复发扫描（幽灵目录/备份散件/攻击残留/注册表冲突） | `ghost_guard` | 只读，零作用域 |
| 服务巡检（探活已登记服务端口） | `svc_inspect` | 只读，零作用域 |

**不在这 18 个里的事**：隔离**房间**那一族（`room_create` / `room_plan` / `room_simulate` /
`room_parity` / `room_rehearse` / `room_release` / `room_shape` / `room_snapshot` / `room_gate` /
`room_namespace`…）**不在本域图鉴里**（它们自己的 `domain` 不是 `pipeline`）—— 本规程只给它一句
**共通的纪律**：`room_release` 要 `deploy_publish`+`filesystem_write`、`room_rehearse` 要
`process_execute`+`filesystem_write`，**同样禁止直接调 `room_space.release()` 绕门**，
但它逐位的用法**不归本文件管，本文件也没验过**。

---

## 2. 怎么调（万能插唯一门）

```powershell
# ── A · 只读六位（本规程真跑过，可直接照抄）──
py -3.14 tools/codex-scripts/five-dim.py cap mirror_scan
py -3.14 tools/codex-scripts/five-dim.py cap mirror_status
py -3.14 tools/codex-scripts/five-dim.py cap pipeline_status
py -3.14 tools/codex-scripts/five-dim.py cap pipeline_versions '{"name":"<产物名>"}'
py -3.14 tools/codex-scripts/five-dim.py cap ghost_guard
py -3.14 tools/codex-scripts/five-dim.py cap svc_inspect

# ── B · 镜像空间（🔒 = 本机未授权，实测被门拒；命令照抄，跑前先要授权）──
py -3.14 tools/codex-scripts/five-dim.py cap mirror_shape                                  # 只读：看镜像树
py -3.14 tools/codex-scripts/five-dim.py cap mirror_shape '{"path":"<相对路径>","content":"<文本>","note":"<备注>"}'   # 🔒 filesystem_write
py -3.14 tools/codex-scripts/five-dim.py cap mirror_plan                                   # 只读：看计划 default
py -3.14 tools/codex-scripts/five-dim.py cap mirror_plan '{"name":"default","plan":{...}}'  # 🔒 filesystem_write
py -3.14 tools/codex-scripts/five-dim.py cap mirror_simulate '{"name":"default"}'           # 🔒 filesystem_write
py -3.14 tools/codex-scripts/five-dim.py cap mirror_parity '{"name":"default"}'             # 🔒 filesystem_write
py -3.14 tools/codex-scripts/five-dim.py cap mirror_rehearse '{"name":"default"}'           # 🔒 process_execute+filesystem_write
py -3.14 tools/codex-scripts/five-dim.py cap mirror_release  '{"name":"default"}'           # 🔒 deploy_publish+process_execute+filesystem_write
py -3.14 tools/codex-scripts/five-dim.py cap mirror_ascend   '{"purpose":"<用途>"}'          # 🔒 deploy_publish
py -3.14 tools/codex-scripts/five-dim.py cap mirror_rewind   '{"version":1}'                # 🔒 deploy_publish

# ── C · 生产管线 + 队列 ──
py -3.14 tools/codex-scripts/five-dim.py cap one_key_deploy '{"target":"<目录或GitHub URL>","room":"<房间名>"}'                 # 🔒 三个作用域；只写房间
py -3.14 tools/codex-scripts/five-dim.py cap one_key_deploy '{"target":"...","into_global_production":true}'                  # 🔒 写全局，必须人工授权
py -3.14 tools/codex-scripts/five-dim.py cap deploy_queue                                                                    # 只读：队列全景
py -3.14 tools/codex-scripts/five-dim.py cap deploy_queue '{"op":"submit","target":"<路径或URL>"}'                            # 🔒 deploy_publish
py -3.14 tools/codex-scripts/five-dim.py cap deploy_queue '{"op":"tick"}'                                                    # 🔒 deploy_publish
py -3.14 tools/codex-scripts/five-dim.py cap pipeline_submit '{"name":"<产物名>","content":"<内容>","meta":{}}'                # 🔒 deploy_publish
py -3.14 tools/codex-scripts/five-dim.py cap pipeline_rollback '{"name":"<产物名>","to_version":1}'                           # 🔒 deploy_publish
```

🔴 **PowerShell 里传 JSON 载荷：用单引号原样包住 JSON**（`'{"op":"tick"}'`）。
写成 `'{\"op\":\"tick\"}'` 会让 `five-dim.py` 的 `json.loads` 直接抛
`JSONDecodeError: Expecting property name enclosed in double quotes` ——
**还没碰到授权门就死了**，而且看起来像"命令敲错了"。**这是本机实测过的坑（同族的 `llm` 域已经踩过）。**

---

## 3. 要过哪道门：**静态查，不靠跑它才知道**

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, payload)     # 只读求值：不执行、不消耗授权
list(d.scopes)                          # → 这个位（在这个载荷下）要过哪几个作用域
```

本域**静态查出来的全量**（2026-09-22 实测，逐位核对过 `policy.py`）：

| 作用域 | 覆盖哪些位 | 说明原文（`SCOPE_DESCRIPTIONS`） |
|---|---|---|
| （**零作用域**） | `mirror_scan` · `mirror_status` · `pipeline_versions` · `pipeline_status` · `ghost_guard` · `svc_inspect`；以及 **无参** 的 `mirror_shape` · `mirror_plan`；以及 **`deploy_queue` 不带 `op`** | 不要授权 |
| `filesystem_write` | `mirror_shape`（带 `path`）· `mirror_plan`（带 `plan`）· `mirror_simulate` · `mirror_parity` | "写入、移动、删除或自动整理文件" |
| `process_execute` + `filesystem_write` | `mirror_rehearse` | "启动进程、执行命令或连接 MCP/终端服务器" + 上一条 |
| `deploy_publish` | `mirror_ascend` · `mirror_rewind` · `pipeline_submit` · `pipeline_rollback`；`deploy_queue` 的 `submit`/`tick` | "部署、晋升、回滚或写入生产交付区" |
| `deploy_publish` + `process_execute` + `filesystem_write` | `one_key_deploy` · `mirror_release` | 三条全要 |
| `deploy_publish` + `external_llm` | `pipeline_submit` 带 `review=true` 或 `refine_rounds>0` | 后者："把当前任务数据发送到外部大模型服务" |

**三条静态判据（`policy.py` 原文，实测逐条对上）**：

1. `deploy_queue`（`policy.py:266-268`）：**只有 `op` 是 `tick` 或 `submit` 才挂 `deploy_publish`** ——
   不带 `op`（= `status`）**零作用域**。实测：`cap deploy_queue` → `ok`；`cap deploy_queue '{"op":"tick"}'` → `denied`。
2. `mirror_plan`（`:230-232`）：**只有给了 `plan` 才挂 `filesystem_write`** —— 不给 `plan` 是读 `get_plan(name)`，零作用域。
3. `mirror_shape`（`:239-241`）：**只有给了 `path` 才挂 `filesystem_write`** —— 不给 `path` 是读 `dimension_tree()`，零作用域。

**授权只能主人在终端发**：

```powershell
python -m gbt_allinone auth grant --scope deploy_publish    --ttl 600
python -m gbt_allinone auth grant --scope process_execute   --ttl 600
python -m gbt_allinone auth grant --scope filesystem_write  --ttl 600
python -m gbt_allinone auth grant --scope external_llm      --ttl 600
```

或主人手写 `store/auth_grants.jsonl`。**授权一次性消耗**（门自己回的 `note` 原话：
`授权一次性消耗；AI 调用路径无权自行发放`）。
🔴 **AI 永远无权给自己发授权** —— 缺授权就如实报缺，**不找旁路、不改 `security/policy.py`、
不改 `auth_gate`、不改 `omni.py`**。
本机现状（2026-09-22 实测 `cap auth_gate_status`）：本域要的四个作用域
`deploy_publish` / `process_execute` / `filesystem_write` / `external_llm` **`grants_available` 全是 0** ——
**所以本域所有 🔒 位在本次交付里都不可能跑通，这是事实，不是"没试"。**

---

## 4. 🔴 「落点必须显式声明」——本域最硬的一条

**规则（Owner 2026-09-19 定，`AGENTS.md`「生产面红线」第一节）**：
`one_key_deploy` **必须显式声明落点**，二选一：

| 落点声明 | 含义 | 后果 |
|---|---|---|
| `room="<房间名>"` | **只写房间维度** | 全局生产面**分毫不动**；走 `room_space` 的隔离排练现实 |
| `into_global_production=true` | **写全局生产** | **必须人工授权**（经 `run_task` 另要 `deploy_publish`） |
| **两个都不给** | — | **直接拒绝**，任何代码都别想溜进生产 |

**源码依据（`gbt_allinone/qiankun.py:256-268`，原文照抄）**：

```python
    # 0) 落点必须**显式声明**（Owner 2026-09-19：假设/模拟/测试全在镜像多维度里跑，
    #    只有过了镜像的成品才进生产）—— 不许默认把任何项目堆进全局生产面。
    if not room and not into_global_production:
        return {
            "ok": False, "blocked": True, "cap": "one_key_deploy",
            "target": str(target)[:80], "name": label,
            "reason": "未声明落点：不许默认把项目堆进全局生产面（否则什么代码都会被送到生产）",
            "how_to": ("隔离试验走 room=\"<房间名>\" —— 只写房间维度，全局生产分毫不动；"
                       "确要写全局生产，显式传 into_global_production=true"
                       "（经 run_task 会另要 deploy_publish 人工授权）。"),
        }
    if room:
        return _deploy_into_room(str(room), target, purpose, label)
```

**落地三句话（照这个写、照这个答）**：

1. **门在落点之前**：经 `five-dim.py cap` 调 `one_key_deploy` 时，**授权门先于落点检查** ——
   实测三种载荷（不给落点 / 给 `room` / 给 `into_global_production`）**全部**先被门拒成
   `missing_scopes ["deploy_publish","process_execute","filesystem_write"]`，
   所以**"未声明落点"那句 `blocked` 在本机未授权状态下根本看不到**；
   落点检查是**过了门之后**的第二道闸（`qiankun.py:258`），**两道都要过**。
2. **不声明落点 = 直接拒绝**，而且拒绝得**明明白白**（`ok:false` + `blocked:true` + `reason` + `how_to`），
   **不是**"默默默认写全局"。给调用方的第一句话应当是**问落点**，不是问参数。
3. **默认姿势是房间**：假设/模拟/测试一律先 `room="<房间名>"`；
   只有**过了镜像的成品**才谈 `into_global_production=true`（并且那是要人工授权的一次性动作）。

---

## 5. 18 个能力位逐个点（实测读数 + 失败典型）

> `门` 列 = 用 `policy.evaluate()` **静态**查出来的作用域（不是跑出来的）；
> `实测` 列 = 2026-09-22 本机 `five-dim.py cap` 的**真返回**；
> `omni` 列 = `auto_run_verdict()` 会不会替你自动跑（**本域 18 个全是 False**，理由见每行末尾）。

### A · 只读（零作用域）——**这 6 位本规程真跑过**

| 位 | 用途 | 门 | 实测关键字段 | 失败/读数典型样子 |
|---|---|---|---|---|
| `mirror_scan` | 镜像维度体检：完整性/署名/纪律/入口（跨维晋升前置） | 无 | `ok true` · **`passed 5` · `total 5`** · `checks.non_empty.detail "19 文件"` · `no_empty_files "无"` · `signature "全部携带"` · `discipline "干净"` · `entry_point "入口: ['holo_pet_w25/main.py','holo_pet_w3/eigenflux/index.html','holo_pet_w3/h1/index.html']"` · `files 19` · `elapsed_ms 12.0` | 它扫的是**镜像区固定的那棵树**，**没有 `target` 参数**：实测传 `{"target":"probe"}` 返回**一模一样**的结果（参数被忽略）—— 别以为传了 target 就换了对象。`passed < total` 时看 `checks` 里哪一格 `ok:false`，那才是没过的维度 |
| `mirror_status` | 维度状态：镜像/现实指纹、现实漂移检测、时间线史 | 无 | `ok true` · `dimension.files 19` · **`reality {files 19, version 27}`** · `dimension_vs_reality []` · **`reality_drift []`** · **`clean true`** · `timelines 27` · `versions 27` · 旧键兼容 `stage`/`production`/`stage_vs_prod`/`production_drift` 同值 | 返回里**同一份数据有两套键**（新名 `dimension`/`reality` 与旧名 `stage`/`production`）—— 读新名，别把两套键当成两批文件。⚠️ **`include_rehearsal:true` 会走一条绕过作用域门的落盘路径，详见 §7** |
| `pipeline_versions` | 产物版本历史 + 当前指纹（`.versions/` 链） | 无（**要 `name`**） | 传 `{"name":"__probe_nonexistent__"}` → `{"name":"__probe_nonexistent__","current":null,"history":[],"count":0}` | 🔴 **不存在的产物不报错，返回 `current:null` + `count:0`**：这**不等于**"产物坏了"，只等于"这个名字没发布过"。**不给 `name`** 才抛 `ValueError("缺少 name：请给出产物名")`（`api.py:882`）—— 但**该报错未验**（本次没跑无参形态，避免与 `omni` 的 `requires_params` 判据混淆） |
| `pipeline_status` | 查发布记录（发布/阻断全留痕） | 无 | `records` **20 条**（默认 `limit 20`）· `count 20` · 单条键：`rec_id` · `name` · `sha256` · `size` · `submitted_at` · `meta` · `stage1_mirror`（四个维度 token：`integrity`/`ownership`/`audit`/`policy`）· `stage2_gate` · `stage3_publish` · `status` | 记录里能看到历史探针产物（`probe-ok.txt`、`_def_probe.txt`、`t-ok.txt`…）—— 那是**留痕**，不是"当前生产内容"；要看生产现状用 `mirror_status`。想收窄条数**不能传 `limit` 当参数给它**（`api.py:894` 读的是 `payload["limit"]`，**本规程未验**这条路径） |
| `ghost_guard` | 防复发检测：幽灵目录/备份散件/攻击残留/注册表冲突扫描 | 无 | `ok true` · **`clean true`** · `findings []` · `scanned true` · `checked_at "2026-09-22T22:13:30"` | `clean true` = **本次没扫出东西**，不是"永远干净"；`scanned true` 才说明真扫了。`findings` 非空时逐条读，别只看 `clean` |
| `svc_inspect` | 服务巡检：探活已登记服务端口（只看不动） | 无 | `services` **14 个** · `total 14` · **`up 0`** · **`down 14`** · `optional_down 1`；每项键：`host` / `port` / `owner` / `up` / `optional` / `checked_at`。实测清单：`payment_gateway:8081` · `blockchain_bridge:8082` · `social_trading_v2:8084` · `monitor_service:8085` · `backtest_api_v2:8089` · `cis_harvesting_v2:8090` · `quant_api:8091` · `cis_v42_trader:8092` · `crypto_gateway:8094` · `gbt_wallet_api:8097` · `v8_isolated:8098(optional)` · `gbt_cap_bridge:18900` · `hcl_control:19090` · `gate_daemon:25485`，全部 `host 127.0.0.1` · `up false` | 🔴 **`down 14` 不是"服务挂了"的结论，只是"这一刻没有在监听"** —— 本机这些服务多数没起。`optional_down 1` 说明那 1 个是可选的（`v8_isolated`），缺它不是故障。要看"服务本身有没有问题"，还得配合 `svc_inspect` 之外的日志/进程读数 |

### B · 镜像空间（成形 / 推演 / 排练 / 晋升）——**🔒 全部未验，卡在门下**

| 位 | 用途 | 门 | 实测 | 失败典型样子 |
|---|---|---|---|---|
| `mirror_shape` | 维度成形：假设/架构虚拟/反复打磨全在镜像维度，现实无感知 | **看载荷**：给 `path` → `filesystem_write`；**不给 `path` → 零作用域** | ① **无参真跑**：`ok true` · 返回 `stage` 全树（19 个相对路径 → `{sha, size}`），如 `holo_pet_w25/main.py {sha "df7c7dc1f5dda8ab", size 10165}` · ② 带 `path` → **denied**：`missing_scopes ["filesystem_write"]` | ① **不给 `path` 是"看树"不是"成形"** —— 别把 `ok true` 读成"已经写进去了"；② 带 `path` 的**成形行为未验**（缺 `filesystem_write`）。`api.py:603-611` 还接受 `delete:true` 走 `unshape` —— **未验，且它也是 `filesystem_write`** |
| `mirror_plan` | 生产前排练计划（假设/架构/步骤/服务与环境契约/验收/回滚） | **看载荷**：给 `plan` → `filesystem_write`；**不给 `plan` → 零作用域** | ① **无参真跑**：`ok true` · `name "default"` · `defined_at "2026-09-19T08:07:05"` · `plan_sha "fd01b97bd97a7ed3397fef2e5ad669df8c05ce59654788d5a81cf41c9ca8554a"` · `plan.goal "面板部署排练（DD 乙 · 甲方案 v2）"` · `assumptions[0] {id "A1", statement "沙盒与本次生产目标为同一主机、同一运行时", verify "environment.production.mode=same_host"}` · `architecture.entrypoints` 4 个 · `steps` S1 固化镜像树指纹、S2 执行静态推演与沙盒闭环…；② 带 `plan` → **denied**：`missing_scopes ["filesystem_write"]` | ① **不给 `plan` 是"读计划"**；② `defined_at` 是**老计划**（2026-09-19），别当成今天定的；③ `get_plan` 在计划不存在时抛 `RehearsalError("排练计划不存在: <name>")`（`deployment_rehearsal.py:612`）—— **这条未验**（本机 `default` 计划存在，无法在不写盘的前提下构造缺失态） |
| `mirror_simulate` | 静态推演：文件/依赖图/端口/入口/契约/闭环定义，不碰生产 | `filesystem_write` | **denied**：`missing_scopes ["filesystem_write"]` · `reason "需要人工授权（filesystem_write）：写入、移动、删除或自动整理文件"` | 说明写"不碰生产"，但**它照样要 `filesystem_write`**（推演结论要落盘）—— 别当它免卡。**授权后行为：未验** |
| `mirror_parity` | 沙盒与生产环境契约一致性（平台/Python/依赖/工具/密钥存在性/路径） | `filesystem_write` | **denied**：`missing_scopes ["filesystem_write"]` | 同上。`api.py:635` 还有 `op:"capture"` 分支（走 `capture_profile`）—— **门一样是 `filesystem_write`**，授权后行为**未验** |
| `mirror_rehearse` | 生产前排练：静态推演→环境一致性→沙盒闭环→指纹绑定报告 | `process_execute`+`filesystem_write` | **denied**：`missing_scopes` **两个都在** `["process_execute","filesystem_write"]`；但 `reason`/`how_to_grant` **只写了 `process_execute`** | 🔴 **只读 `reason` 会漏掉 `filesystem_write`** —— 必须以 `missing_scopes` 为准（§6 第 2 条）。**授权后行为：未验** |
| `mirror_release` | 排练全绿后一次性全量晋升生产（树/计划指纹绑定，失败即阻断） | `deploy_publish`+`process_execute`+`filesystem_write` | **denied**：`missing_scopes` 三个全在 `["deploy_publish","process_execute","filesystem_write"]`；`reason` 只报 `deploy_publish` | 🔴 这是**本域最重的一发**（真写生产）。`omni.py:99-104` 记着一次实测教训：第一版判据把它漏出自动执行名单，`omni run` **当场执行了它**，是下游授权门拦住的（`auth_denied scope=deploy_publish`）。**授权后行为：未验** |
| `mirror_ascend` | 跨维晋升（验证全绿才放行；一次性全量写入现实+护照+时间线；现实零修改） | `deploy_publish` | **denied**：`missing_scopes ["deploy_publish"]`（**只要一个**） | 🔴 **同族坑（源码所见，未跑）**：`api.py:662-676` —— 传 `require_rehearsal:true` 时**不真调 `ascend()`**，而是**fail-closed 返回指引** `{ok false, blocked true, reason "本层不支持演练前置门（require_rehearsal）", how_to "先调 mirror_rehearse…"}`, `cap "mirror_ascend"`。⚠️ **但门在前**：未授权时你**先**拿到 `denied`，看不到这段指引。**授权后行为：未验** |
| `mirror_rewind` | 时间线回滚（回到过去的时间线，同样一次性全量替换） | `deploy_publish` | **denied**：`missing_scopes ["deploy_publish"]` | 源码所见（`mirror_space.py:307-317`）：版本不存在时返回 `{"ok": False, "error": "版本不存在: v<N>"}`，真回滚是 `shutil.rmtree(_REALITY)` + `copytree(vdir, _REALITY)` —— **这是不可逆的整树替换**，所以它要 `deploy_publish`。**授权后行为：未验** |

### C · 生产管线 + 队列

| 位 | 用途 | 门 | 实测 | 失败典型样子 |
|---|---|---|---|---|
| `one_key_deploy` | 一指定江山乾坤换位：抓取(GitHub/本地)→镜像→验证→晋升一条命令，一次性上线零修改 | `deploy_publish`+`process_execute`+`filesystem_write` | **denied**（三种载荷全一样）：不给落点 / `room:"probe-room"` / `into_global_production:true` → 都是 `missing_scopes ["deploy_publish","process_execute","filesystem_write"]` · `reason` 只报 `deploy_publish` · `how_to_grant` 只给一行 | 🔴 **两道闸**：①授权门（先）；②落点检查（后，`qiankun.py:258`）。本机未授权 ⇒ **只看得到第①道**。**授权后行为：未验**。见 §4。另：`api.py:579` 缺 `target` 抛 `ValueError("缺少 target：GitHub 仓库/子目录 URL 或本地目录路径")`；`qiankun.py:246` 传 `plan` **一律 fail-closed**（`reason "本层不支持 plan（部署计划属于排练门，不塞进一次性晋升）"`）—— **两条都未验**（门在前） |
| `deploy_queue` | AI 接管部署队列：submit 入队 / tick 部署下一个（完一个自动下一个）/ status 全景 | **看 `op`**：`submit`/`tick` → `deploy_publish`；其余（含不给 `op`）→ 零作用域 | ① **不带 `op` 真跑**：`ok true` · `total 0` · `by_status {}` · `items []`；② `{"op":"tick"}` → **denied**：`missing_scopes ["deploy_publish"]`；③ `{"op":"submit"}`（连 target 都不给）→ **denied 同样先卡 `deploy_publish`** | 🔴 **`total 0` / `items []` 是"队列现在是空的"，不是"队列坏了"**（同族坑：假空数组）；想确认队列机制还在，看 `by_status` 这个键在不在（空队列时它是 `{}`）。**`submit` 与 `tick` 的真实行为：未验**（缺 `deploy_publish`）。另：图鉴 `requires_params ["target"]` 对**不带 `op` 的 `status`** 并不成立（实测无参就 ok） |
| `pipeline_submit` | 生产管线：镜像多维度空间→门禁审计→生产写入（**唯一交付通道**） | `deploy_publish`；**另**：`review=true` 或 `refine_rounds>0` 时再加 `external_llm` | **denied**：`missing_scopes ["deploy_publish"]`（本次载荷没带 review/refine，故 `external_llm` 未出现在 `missing` 里） | 🔴 **静态实测**（`policy.evaluate`）：`{}` → `["deploy_publish"]`；`{"review":True}` → `["deploy_publish","external_llm"]`；`{"refine_rounds":3}` → `["deploy_publish","external_llm"]`（`policy.py:366-367`）。⇒ **同一发 `pipeline_submit`，带不带 review 差一个作用域** —— 申报授权时要按**要跑的载荷**算。**授权后行为：未验** |
| `pipeline_rollback` | 生产管线：回滚产物到历史版本（回滚也走审计留痕） | `deploy_publish`（**要 `name`**） | **denied**：`missing_scopes ["deploy_publish"]` | 源码所见（`pipeline.py:461-473`）：`to_version` 缺省 = 最近一个历史版本；生产区无此产物 → `{"ok": False, "error": "生产区无此产物: <name>"}`；无历史版本 → `{"ok": False, "error": "无历史版本可回滚: <name>"}`。**三条都未验**（门在前）。「回滚 = 把历史内容作为新版本发布」，**不是删历史** |

**本域 18 位的 `auto_run_verdict()` 理由原话（2026-09-22 实算，逐位，全 `AUTO=False`）**：

| 位 | 不自动跑的理由（原话，`|` 分隔） |
|---|---|
| `one_key_deploy` | 需要参数 target \| 在侧效应名单里，要人确认 \| 域「pipeline」属于有后果的域 \| 名字带写动作字样 \| 要过授权门：deploy_publish,process_execute,filesystem_write |
| `deploy_queue` | 需要参数 target \| 在侧效应名单里，要人确认 \| 域「pipeline」属于有后果的域 \| 名字带写动作字样 |
| `mirror_shape` | 在侧效应名单里，要人确认 \| 域「pipeline」属于有后果的域 \| 名字带写动作字样 |
| `mirror_scan` | 域「pipeline」属于有后果的域 |
| `mirror_plan` | 域「pipeline」属于有后果的域 |
| `mirror_simulate` | 域「pipeline」属于有后果的域 \| 名字带写动作字样 \| 要过授权门：filesystem_write |
| `mirror_parity` | 域「pipeline」属于有后果的域 \| 要过授权门：filesystem_write |
| `mirror_rehearse` | 域「pipeline」属于有后果的域 \| 名字带写动作字样 \| 要过授权门：process_execute,filesystem_write |
| `mirror_release` | 域「pipeline」属于有后果的域 \| 名字带写动作字样 \| 要过授权门：deploy_publish,process_execute,filesystem_write |
| `mirror_ascend` | 域「pipeline」属于有后果的域 \| 名字带写动作字样 \| 要过授权门：deploy_publish |
| `mirror_status` | 域「pipeline」属于有后果的域 |
| `mirror_rewind` | 域「pipeline」属于有后果的域 \| 名字带写动作字样 \| 要过授权门：deploy_publish |
| `pipeline_submit` | 在侧效应名单里，要人确认 \| 域「pipeline」属于有后果的域 \| 名字带写动作字样 \| 要过授权门：deploy_publish |
| `pipeline_versions` | 需要参数 name \| 域「pipeline」属于有后果的域 |
| `pipeline_rollback` | 需要参数 name \| 域「pipeline」属于有后果的域 \| 名字带写动作字样 \| 要过授权门：deploy_publish |
| `pipeline_status` | 域「pipeline」属于有后果的域 |
| `ghost_guard` | 域「pipeline」属于有后果的域 |
| `svc_inspect` | 域「pipeline」属于有后果的域 |

⚠️ 注意 `mirror_scan` / `mirror_status` / `pipeline_status` / `ghost_guard` / `svc_inspect`
这 5 位**唯一**的不自动理由就是"域属于有后果的域" —— 它们本身**零作用域且纯只读**。
⇒ **"不自动跑"在这 5 位上只是纪律（不替人做生产面的决定），不是"跑不了"**：
你要看就直接 `five-dim.py cap <位>`，**不会碰到任何门**。

---

## 6. 🔴 读数红线（先问"这是事实，还是我读错了地方"）

1. **授权被拒时是"扁平错误信封"，不是常规信封**。
   `missing_scopes` / `reason` / `how_to_grant` / `note` **同时出现在顶层**，
   而 `result` 里有一份**完整信封**（`status`/`denied`/`message`/`reason`/`error`/`scopes`/`missing`/`how_to_grant`/`note`），
   **没有 `gbt_result`**。`five-dim.py` 的 R-H299 注释就是拿一次事故换的：
   原来只读 `r["gbt_result"]` ⇒ 被拒时 `gr` 为空 ⇒ 打出来是
   **`status: unknown · denied: false`——门明明说"拒了"，报表却说"未知、没拒"**。
   ⇒ **读顶层字段，别只盯 `gbt_result`**。
2. **`reason` / `how_to_grant` 只覆盖第一个缺的作用域**。
   实测两发铁证：`mirror_rehearse` 的 `missing_scopes` 是
   `["process_execute","filesystem_write"]`，但 `reason` 只说 `process_execute`；
   `one_key_deploy` / `mirror_release` 的 `missing_scopes` 是**三个**，
   `reason` 只说 `deploy_publish`。
   ⇒ **以 `missing_scopes`（全量数组）为准**，`reason` 只当"第一句话"。
3. **`how_to_grant` 只给一行，不是全量**。实测三作用域齐缺时它仍只有
   `["终端运行: python -m gbt_allinone auth grant --scope deploy_publish --ttl 600", "或主人手写 store/auth_grants.jsonl 追加一行（格式见 auth_gate.SCOPES 与 README）"]`
   —— **缺的另外两个作用域，授权命令行要你自己按 `missing_scopes` 拼全**。
4. **`status:"ok"` ≠ 本体 `ok:true`**。两层要分开读：
   顶层 `status`/`ok`（`five-dim.py` 的信封）说的是**这一发调用过没过门**；
   `result` 里的 `ok`（本体返回）说的是**业务做没做对**。
   实测反例就在本域：`pipeline_versions` 传不存在的产物名 → 顶层 `status "ok"`（门过了），
   `result` 是 `{"current":null,"history":[],"count":0}` —— **本体自己没成功，只是它选择不报错**。
   ⇒ **别把"顶层 ok"当"产物正常"。**
5. **`stamp: true/false` 是回归印章的有无，不是成功与否**。本域实测：6 个只读位一律 `stamp true`；
   所有 denied 一律 **`stamp false`**。denied 与 user_error 都 `stamp false`。
6. **退出码不可信**。`ok` → 0；`denied` 与 `user_error` → 1。
   **别把 exit 1 一律读成"命令敲错了"** —— 先看 `status` 是 `denied` 还是 `error`。
   本域实测：所有 denied 都是 exit 1，但它们**不是**"命令写错"，是**门如实拒绝**。
7. **"被门拒" ≠ "把授权烧掉了"**（`gbt-tentacle` 域拿一次事故换来的账，本域同样适用）：
   **被门拒 = 没执行 = 不消耗**；只有审计里出现 `auth_consumed` 才是真花掉。
   本域全部 denied 都发生在门内，**没有执行任何写动作**。
8. **图鉴是索引，实测才是读数**。本次实测抓到的漂移：`mirror_scan` 在注册表里
   `requires_params []` 且无 `params_hint`，但**它到底扫哪棵树在说明里看不出来** ——
   实测证明它扫的是**固定的镜像树**（传 `target` 被忽略）。⇒ **图鉴对不上时以实测为准，并把漂移记下来。**
9. **别把"镜像"读成"生产"**：本域有**两套 store 树**：
   `mirror_space` 的 `_MIRROR/reality`（跨维晋升写的那套；
   `mirror_status` 实测 `reality.files 19` · `version 27`）
   与 `pipeline` 的 `_PIPE/production` + `.versions`（`pipeline_submit` 写的那套；
   `pipeline_status` 实测 20 条记录）。**两套各有各的版本号，别混着读**。

---

## 7. 🔴 本次实测抓到的一条真问题：`mirror_status` 带 `include_rehearsal` 会绕过作用域门

**读得到的部分（可复核）**：

- 静态：`policy.evaluate("mirror_status", {})` → `scopes []`；
  `policy.evaluate("mirror_status", {"include_rehearsal": True})` → **也是 `scopes []`**（实测）。
- 源码（`api.py:678-685`）：`p.get("include_rehearsal")` 为真时多跑一句
  `result["rehearsal"] = DR.status(p.get("name") or "default")`。
- 源码（`deployment_rehearsal.py:1462-1472`）：`status()` 里调 `gate(name)`。
- 源码（`deployment_rehearsal.py:1290-1291`）：`gate()` 在"有排练报告且有计划"时调
  `capture_profile(name)["profile"]`。
- 源码（`deployment_rehearsal.py:878`）：`capture_profile()` 末尾
  `atomic_write_json(_profile_path(name), record)` —— **真落盘**。

⇒ **净效果**：`mirror_status` 挂着**零作用域**，却能通过 `include_rehearsal` 走到一次
**真实文件写入**（写 `store/mirror_space/profiles/<name>.json`）；
而同族的 `mirror_rehearse` 要 `process_execute`+`filesystem_write`。
**这是"声明与执行漂移"**（同族坑：作用域未注册）。

**本规程的立场（三句话）**：

1. **本域规程里不提供 `include_rehearsal` 的现成命令**，也不把它算进"只读六位"；
   要用演练状态，走登记在册的路径（`mirror_plan` 看计划 / `mirror_parity` 看一致性），
   它们要的门是**写明的**。
2. **本规程未跑这条路径**（避免以"只读"之名触发一次未申报的落盘）——
   `capture_profile` 是否真被触发取决于 `latest.json` 与计划是否齐备，**该条件本次未验**。
3. **不许改 `policy.py` 去凑**：这是**待上报的问题**，正确动作是**如实上报 + 不碰**，
   由主人决定怎么修（补登记作用域 or 把这条分支挪走）。
   ⚠️ 反过来说也成立：**别因为"它零作用域"就把它当免卡的只读位用。**

---

## 8. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、
   不改 `security/policy.py` / `auth_gate` / `omni.py`。
2. **不许绕门**：**禁止**直接调模块函数来替掉 `run_task` 唯一门 ——
   `mirror_space.ascend()` · `deployment_rehearsal.release()` · `qiankun.one_key_deploy()` ·
   `room_space.release()` 这四个是点名的。
   `AGENTS.md` 原文：那会**绕过授权门**，实测教训（2026-09-19）就是一次"成功"的晋升这么绕出来的，
   功能生效但**纪律上是未经授权的生产写入**。
3. **不许不声明落点就部署**：`one_key_deploy` 必须给 `room="<房间名>"` 或
   `into_global_production=true`；**两个都不给 = 直接拒绝**，别想着"它可能默认写房间"。
4. **不许把假设/模拟/测试往全局生产面上堆**：一切假设先在**镜像多维度**（或隔离房间）里跑完，
   **只有过了镜像的成品才进生产**；生产**零修改**、**一次性全量**晋升。
5. **被拒了就是拒了**：`denied` 之后**不许换路径再试一遍**、不许改 payload 碰运气。
   如实报缺哪个作用域（**按 `missing_scopes` 全量报**），把主人要跑的那几行原样交给他。
6. **本规程不做任何写动作**：不 submit、不 deploy、不 ascend、不 release、不 rollback、
   不 shape 出东西落盘；只读的真跑，写的一律**只写命令与门**。
7. **不许调用 `tentacle` / `desktop_control` 那条线**：本域不碰桌面；
   `desktop_control` 在本机是**一次性消耗**，别拿它去"顺手验一下屏幕"。
8. **不许动别的域**、不许改 `omni.py` 的 `DISTILLED_DOMAINS`（本域登记的是一行字面量，
   属交付方决定，本规程不擅自动手）。
9. **不许把本规程当"部署官方文档"**：命令级细节以源码/主人口径为准，
   本文件管的是**我们这儿的纪律与读数口径**。

---

## 9. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-pipeline/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-pipeline\SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 `AGENTS.md` 明令禁止） |
| 能力位名单（18 个） | `<仓>/state/skill_atlas.json`（`domain == "pipeline"`）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 授权判据（**单一真相**） | `<仓>/gbt_allinone/security/policy.py` 的 `evaluate()`（第 225-241、266-268、366-367 行是本域） |
| 唯一门 / 拒绝信封 | `<仓>/gbt_allinone/run_task` · `tools/codex-scripts/five-dim.py:122-171`（扁平信封的读法） |
| 自动执行判据 | `<仓>/tools/codex-scripts/omni.py` 的 `DANGER_DOMAINS`(:105) / `DANGEROUS_NAME_RE`(:136) / `auto_run_verdict()`(:156) |
| 落点硬闸（**本域最硬的一条**） | `<仓>/gbt_allinone/qiankun.py:256-268` |
| 镜像空间实现 | `<仓>/gbt_allinone/mirror_space.py`（`scan` / `mirror_status` / `ascend` / `rewind` / `shape` / `dimension_tree`） |
| 排练实现 | `<仓>/gbt_allinone/deployment_rehearsal.py`（`define_plan` / `get_plan` / `simulate` / `capture_profile` / `parity` / `rehearse` / `release` / `gate` / `status`） |
| 生产管线实现 | `<仓>/gbt_allinone/pipeline.py`（`submit` / `versions` / `rollback` / `list_records`） |
| 人话落点 | `python tools/codex-scripts/omni.py ask "把项目部署到生产"` → 落到 `pipeline` 域（`omnipulg` 通道）；本域无自动执行，落点后仍是**你手敲命令 + 过门** |

**验收（做完怎么证明真的做了）**：

1. `py -3.14 tools/codex-scripts/five-dim.py cap mirror_scan` → 拿 `passed`/`total` 与五维 `checks`；
2. `py -3.14 tools/codex-scripts/five-dim.py cap mirror_status` → 拿 `clean` 与 `versions`；
3. 任一 🔒 位 → 打印的 `missing_scopes` 必须与 §3 静态表**逐个一致**
   （不一致就是某处漂移了，回来改本文件）；
4. `py -3.14 tools/codex-scripts/verify-distill.py --domain pipeline --skill gbt-pipeline`
   → 必须 PASS（两份逐字节相同 + frontmatter + 18 位全覆盖 + 没有编造的能力位）；
5. 声明"某位能用"之前，先问自己：**这条是实测读数，还是我读错了地方？** 拿不准就写「未验」。
