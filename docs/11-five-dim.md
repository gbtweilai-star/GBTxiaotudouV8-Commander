# 11 · 五维合一：一句话进去，route → execute → verify → health 一条链出来

> 入口只有一个：**`run_task("brain_unify", {"goal": "…"})`** —— 与万能插
> `five-dim.py cap brain_unify` 走的是**同一道门**（授权、审计、钢印都在门上）。
>
> 本页所有回执来自 `data/five-dim-live.json`（由 `tools/codex-scripts/gen-native-live.py` 每次真跑生成）。

---

## 一、五个维度到底是什么

`brain_exec` 把"大脑执行层"拆成五件事，每一件都能单独调、也能串成一条链：

| 维度 | 函数 | 它负责什么 | 关键字段 |
|---|---|---|---|
| ① **route** | `route(intent)` | 语义路由：统一大模型在**真方法表**里选一个最佳落点（带幻觉防护） | `best` · `candidates` · `path` · `degraded` · `degraded_reason` |
| ② **execute** | `execute(kind, payload, parallel)` | 万能插执行：单能力直调，或 `parallel` 线程池多路并发；**全部走 `run_task` 同一道门** | `ok` · `status` · `missing_scopes` · `reason` |
| ③ **verify** | `verify(expectation, window)` | 触手肉眼验证：抓全屏帧 + 感知指纹（可选读回目标窗口内容） | `checks.vision.fingerprint` |
| ④ **health** | `health()` | 执行层自检评分：route / execute / tentacle / vision / audit 五维各自 ok 或否 | `score` · `healthy_dims` |
| ⑤ **unify** | `unify(goal, payload)` | 把 ①~④ **顺序串链**一次跑完：**route 的 `best.kind` 喂给 execute**，再 verify、再 health | `chain.*` · `elapsed_s` |

**两件容易读错的事，先钉死：**

1. **它是顺序串链，不是星形**：`route → execute → verify → health` 依次走，数据顺着链往下流
   （README 里早前那句"星形"是错的，已按实测改正）；
2. **`verify` 不是"业务结果对不对"**：它是"现实看得见" —— 抓帧 + 指纹。
   所以**即使 execute 被门挡住，verify 仍可能为 true**（机器确实看得见屏幕），这是两个不同的问题，别混成一句"全绿"。

---

## 二、五条真跑回执（2026-10-21，原样，未挑好看的）

| # | 人话（goal） | route 落点 | path / 降级 | 候选 | execute | health | 用时 |
|---|---|---|---|---:|---|---|---:|
| 1 | 统计一下这段话有多少个词 | `count_words`（data） | semantic · **degraded=True**（主路判"方法表里没有合适项"） | 5 | ✅ ok | 5/5 | 20.8s |
| 2 | 看一下本机能力位总共有多少位、分哪些域 | `tentacle.available_actions` | semantic · degraded=False | 56 | 🔒 **denied** | 5/5 | 10.4s |
| 3 | 查一下本机系统健康信息（平台、Python、版本、时间） | `tentacle.diagnose` | semantic · degraded=False | 118 | 🔒 **denied** | 5/5 | 13.1s |
| 4 | 看看当前屏幕上有哪些窗口 | `tentacle.list_windows` | semantic · degraded=False | 9 | ✅ ok | 5/5 | 4.2s |
| 5 | 指定能力直跑：echo（显式 `kind=echo`） | 路由仍留痕（`brain_execute.invoke`），执行按指定 `kind` | semantic · degraded=False | 120 | ✅ ok | 5/5 | 23.3s |

被挡那两条的**完整拒绝回执**（这就是"缺票要说得清"的样子）：

```
status   = denied
missing_scopes = ['desktop_control', 'privacy_read']
reason   = 需要人工授权（desktop_control / privacy_read）
```

> **三条必须如实说的事**：
>
> 1. **第 4 条的标签是我跑之前起的（"会被门挡住"），结果它是 ok** —— 预期被读数推翻，我**不改标签也不删这一行**。
>    `list_windows` 在方法表里是只读窗口枚举，门不放票、放行是对的。
> 2. **同一条人话，两次跑可能落到不同格**：第 3 条这句话，早前一次跑落到只读位 `health`（execute ok），
>    这一次落到 `tentacle.diagnose`（要桌面控制票 ⇒ denied）。这是**语义路由的抖动**，本页写的是这一轮的真实回执，
>    不拿"好看的那一次"当结论。
> 3. **第 1、3、5 条是 `degraded=True`**：主路（统一大模型）跑通了、但判"方法表里没有合适项"，于是**如实降级**到
>    本体能力启发式，并把原因写进 `degraded_reason`。**降级不是失败，假装没降级才是。**

---

## 三、这条链上"门"是怎么起作用的

| 位置 | 门管不管 | 说明 |
|---|---|---|
| `route` | 不管 | 只选落点，不动现实；语义路由不可用时**降级并自曝原因** |
| `execute` | **管** | 派下去仍走 `run_task`；要票的位当场 `denied` + `missing_scopes` |
| `verify` | 部分 | 抓屏属隐私载体（`privacy_read`）；本机当前放行，回执里带指纹 |
| `health` | 不管 | 只跑自检（selfscan / wf_status / tentacle_status / eye / 审计计数） |

**为什么坚持"execute 必须从门里过"**：一旦给执行层开一条直调模块的近路，
"授权/审计/钢印"三件事就同时在那一刻失效了 —— 本仓真的这么翻过车（绕过门调 `mirror_space.ascend()`），
所以现在写死：**执行层只有一条入口 `run_task`。**

---

## 四、怎么自己跑

```bash
# 单个意图（人话进去，全链出来）
py -3.14 -m gbt_allinone run brain_unify '{"goal":"统计一下这段话有多少个词"}'

# 指定能力直跑（跳过"选哪个"，但门照旧）
py -3.14 -m gbt_allinone run brain_unify '{"goal":"指定能力直跑","kind":"echo"}'

# 万能插口径（同一个门，多一层包装：信封 + 邻域同视）
py -3.14 tools/codex-scripts/five-dim.py cap brain_unify '{"goal":"看看当前屏幕上有哪些窗口"}'
```

---

## 五、边界

1. **语义路由依赖统一大模型通道**：通道不可用 ⇒ `path=heuristic` · `degraded=true` · `degraded_reason` 写明缺什么（不静默换道）。
2. **路由会抖动**：同一句话不同轮次可能落到不同能力位（本页第二节第 2 条已实证），所以它适合"给个落点建议"，
   需要确定性时**显式传 `kind`**。
3. **`verify` 只证明"看得见"**，不证明"做对了"；业务正确性要靠各能力位自己的 `ok` 与产物闸。
4. **`health=5/5` 是执行层自检**，不等于"348 位能力全健康" —— 那是多域监控（[12](12-multidomain-monitor.md)）与能力自证（[07](07-capability-proof.md)）各自的事。
