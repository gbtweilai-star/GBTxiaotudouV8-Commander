# 46 · 判决层抽样结果 + 7 个 miss 的根因（2026-11-01）

> 两件事：① 按域抽样的逐域命中率；② 把 miss 逐个查根因，分清"召回问题"还是"判决问题"。

---

## 一、抽样读数（60 项 = 30 域 × 2，真跑本机权重）

**56/60 = 93.3%**（触手方法 4/4 = 100%，本体能力 52/56 = 92.9%）。

| 域 | 抽样 | 命中 | 域 | 抽样 | 命中 |
|---|---|---|---|---|---|
| system | 2 | 2 | security | 2 | 2 |
| creation | 2 | 2 | llm | 2 | 2 |
| mind | 2 | 2 | pipeline | 2 | 2 |
| video | 2 | 2 | tentacle | 2 | 2 |
| vision | 2 | 2 | voice | 2 | 2 |
| automation | 2 | 2 | collab | 2 | 2 |
| data | 2 | 2 | desktop | 2 | 2 |
| device | 2 | 2 | devour | 2 | 2 |
| engine | 2 | 2 | infra | 2 | 2 |
| integration | 2 | 2 | longrun | 2 | 2 |
| social | 2 | 2 | tools | 2 | 2 |
| 媒体域 | 2 | 2 | 读网域 | 2 | 2 |
| **brain** | 2 | **1** | **finance** | 2 | **1** |
| **project** | 2 | **1** | **recon** | 2 | **1** |
| comms / framework / image_video / life | 各 1 | 1 | | | |

4 个 miss：`absorb_loop`、`quant`、`platform_profile`、`case_mine`（全是能力位，且都是"近义兄弟"）。

## 二、根因：**7 个 miss 全是判决问题，不是召回问题**

把每个 miss 的"目标在本轮候选里的排名"算出来（离线、秒级）：

| miss | 在候选里排第几 | 判决结果 | 归类 |
|---|---|---|---|
| `audio_voices` | **1** | 没给出合法名字 | 判决 |
| `enter` | **1** | 回了 `operate_on_thing`（**不在候选里**，模型自己造的） | 判决 |
| `grab_pixel` | **1** | 没给出合法名字 | 判决 |
| `quant` | **1** | 选了孪生位 `quant_backtest` | 判决 |
| `platform_profile` | 4 | 选了孪生位 `quant` | 判决 |
| `absorb_loop` | 9 | 选了孪生位 `offload_distill` | 判决 |
| `case_mine` | 9 | 没给出合法名字 | 判决 |

**召回层（recall@10/12）没有问题**：目标项全在候选里，最差排第 9。
⇒ 之前担心的"漏项/覆盖不足"不成立；现在是**7.6B 模型对近义兄弟的辨别力**不够。

## 三、试过"纠错重试"，**结论是不加**（有读数）

做法：第一次不合理就把清单压成一行、约束放最后，再问一次。

同 4 条实测：

| 意图 | 单次 | 加重试 |
|---|---|---|
| 取像素看这个点的颜色 | 失败 | **grab_pixel ✓** |
| 吞天闭环只读骨架蒸馏 | offload_distill ✗ | **absorb_loop ✓** |
| 回车确认键 | 诚实失败（无效名） | **absorb_loop ✗（错答案）** |
| 量化回测入口外部业务模块 | quant_backtest ✗ | quant_backtest ✗ |

救回 2 条，却把 1 条**从"诚实失败"变成"错误答案"**（只因为 `absorb_loop` 排在清单第一个被抄了）。

⇒ 按本仓铁律「**宁可如实报错，绝不静默造假**」：**回退成单次判决**，认不出就判无效。
只保留一个无争议的改进：JSON 兜底多认一个键 `action`（这模型训练时用 action 命名动作）。

## 四、剩下的 miss 属于"模型容量"，不是接线

- `quant` / `quant_backtest` / `quant_strategy` / `quant_params` / `quant_plan` 五个孪生位，
  描述都以"量化"开头，7.6B 在 10 个候选里挑错属正常；
- `absorb_loop` / `offload_distill` / `bi_distill` / `cad_distill` 同理（都是"蒸馏"家族）。

**不做的"优化"**：不给它们加特判、不把答案写进 prompt、不做模糊匹配把错名字硬掰回对名字 ——
那三类都会把"读数好看"做得比"真能用"更优先，本仓明令禁止。

## 五、复现

```powershell
python tools/codex-scripts/commander-coverage.py --sample 2 --k 10 \
    --json state/commander/coverage-sample.json
```

行级明细：`state/commander/coverage-rows.jsonl`（可断点续跑）。
全量 478 项此前跑到 115 项（93.9%），剩余项可用同一命令继续。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 全量终值（2026-11-01 485 项跑完）

口径：**逐项 true 跑**（每项一句由能力位 desc 生成的意图，k=12，判模型选没选中）。

| 空间 | 命中 | 总数 | 命中率 |
|---|---|---|---|
| 触手方法 | 119 | 127 | **93.7%** |
| 本体能力 | 254 | 358 | **70.9%** |
| **合计** | **373** | **485** | **76.9%** |

按域（命中率从低到高，只列 <80%）：

| 域 | 命中/总数 | 命中率 |
|---|---|---|
| pipeline | 6/18 | 33.3% |
| brain | 1/2 | 50.0% |
| project | 1/2 | 50.0% |
| mind | 12/20 | 60.0% |
| engine | 6/10 | 60.0% |
| vision | 3/5 | 60.0% |
| creation | 34/54 | 63.0% |
| recon | 11/17 | 64.7% |
| system | 34/52 | 65.4% |
| tentacle | 16/23 | 69.6% |
| security | 21/29 | 72.4% |
| video | 11/15 | 73.3% |
| finance | 3/4 | 75.0% |
| llm | 34/41 | 82.9% |
| data | 10/12 | 83.3% |
| integration | 6/7 | 85.7% |
| tools | 8/9 | 88.9% |
| device / devour / longrun / automation 等 13 域 | — | **100%** |

**最值钱的一条发现**：今晚新加的 8 个器官（`energy_core`/`pulse_core`/`trunk_cover`/`body_sense`/
`trunk_reason`/`context_guard`/`devour_auto`/`orchestration`）**全部 MISS** ——
有实现、有名分、**但词表没写 ⇒ 路由不可达 = 等于没长**。
已把它们的口语说法补进 `data/intent-lexicon.json`（+8 条），下一步用同一把尺子复测这 8 项。

**口径声明**：这是"可达性上限"（题库来自 desc，孪生位存在歧义，见 docs/51）；
真实可用性看人写基准（24 条：16/24 命中，召回 24/24，见 docs/54）。
**补齐后复测**：把 8 个新器官的口语说法写进词表、并去掉工作流条目里的裸"编排"（它抢权重）后，
脉冲直达 8/8 命中（0 token）：能源核心→energy_core、脉冲→pulse_core、代码覆盖→trunk_cover、
身体状态→body_sense、动脑想想→trunk_reason、上下文→context_guard、吞噬→devour_auto、
编排面板→orchestration。
