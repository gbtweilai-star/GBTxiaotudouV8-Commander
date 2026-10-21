# 07 · 能力自证：341 位逐位真调（不是"模型会背"，是"调得动"）

> 前一页证明**它说得出**；这一页证明**它真调得动**。
> 全部读数来自 `tools/codex-scripts/probe-caps-live.py` 的一次真跑，机器可读结果在
> [`../data/capability-live-test.json`](../data/capability-live-test.json)。

![能力自证](../assets/fig-caps.png)

## 一、规则（先写死，再跑）

| 位类型 | 怎么测 | 为什么这样定 |
|---|---|---|
| 只读 且 无需参数 | **真调一次**（空 payload），记耗时/状态 | 这是"能力属实"最硬的证据 |
| 只读 但 需要业务参数 | **不跑**，标 `needs_params` | 不瞎编参数（瞎编出来的绿是假绿） |
| 写盘 / 花钱 / 出网 | **一律不跑**，标 `needs_auth` | 开源测试不越授权门 |

每发调用带 **12 秒看门狗**；超时记 `timeout`（**不记 0、不记 ok**）。

## 二、读数（一次全量跑，231 秒）

| 结果 | 位数 | 说明 |
|---|---:|---|
| ✅ 真调通过 | **221** | 其中 4 位是"慢但通"（见下节），初测超时、给足时间后全绿 |
| 🔒 只读但要票 | **15** | 门如实拒绝，并带回**缺哪个作用域** |
| ⚙ 需参数 | **26** | 不瞎编，如实记 |
| 🚫 写口未跑 | **79** | 不越授权门 |
| ❌ 仍未通 | **0** | — |

> 合计 221 + 15 + 26 + 79 = **341**，没有"没归类"的。

**"只读但要票"的 15 位不是失败，是结构在生效**：

```
codex_models / llm_chat              → 缺 external_llm（把数据发给外部大模型）
codex_thread_new / mcp_connect / mcp_call → 缺 process_execute（起进程/连终端）
mirror_rehearse                      → 缺 process_execute
mirror_release / mirror_ascend / mirror_rewind / pipeline_submit → 缺 deploy_publish
vision                               → 缺 privacy_read（读屏幕/摄像头/麦克风）
voice                                → 缺 audio_output（让本机发声）
bluetooth / bt_control               → 缺 device_control
devour_pulse                         → 缺 data_export
```

这正是 [架构页](02-architecture.md) 那条硬约束的实测证据：**写口/隐私/花钱的动作，AI 自己拿不到票。**

## 三、跑这一轮逮到的两个真问题（都已修）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | `lr_submit` 报 `需要 description`，却被记成"跑了但失败" | **注册表没登记它的必填参数**（`PARAM_REQUIRED` 缺一条） | 补登记；现在它被判为 `needs_params`，不再污染"失败"计数 |
| 2 | 4 条安全扫描（`sec_surface` / `sec_scan` / `sec_chain` / `cross_scan`）记 `timeout` | 看门狗 12 秒太短：它们要真扫 | 给足 180 秒后复测：**28.1 / 63.2 / 54.3 / 47.0 秒全部 OK** ⇒ 是"慢"，不是"坏" |

> 两条都属于同一类病：**读数的分类口径不对，会把好能力记成坏能力。**

## 四、按域分布（只列前 12 大域）

| 域 | 真调通过 | 只读要票 | 需参数 | 写口未跑 |
|---|---:|---:|---:|---:|
| creation | 32 | 0 | 0 | 22 |
| system | 45 | 0 | 1 | 5 |
| llm | 22 | 3 | 8 | 8 |
| security | 19 | 0 | 1 | 9 |
| mind | 17 | 0 | 1 | 1 |
| pipeline | 9 | 5 | 4 | 0 |
| tentacle | 10 | 2 | 1 | 5 |
| recon | 9 | 0 | 2 | 6 |
| data | 8 | 0 | 1 | 3 |
| engine | 5 | 0 | 4 | 1 |
| tools | 7 | 0 | 0 | 2 |
| video | 5 | 0 | 0 | 9 |

## 五、怎么复算（一条命令）

```bash
py -3.14 tools/codex-scripts/probe-caps-live.py            # 全量
py -3.14 tools/codex-scripts/probe-caps-live.py --limit 40 # 先试跑 40 位
```

输出 `data/capability-live-test.json`，每一位带：`result` / `ms` / `status` / `missing_scopes` / `error`。
**没有"未归类"的结果**——这是这份账能被复核的前提。

## 六、边界（说清楚，不含糊）

1. 只覆盖**只读**面；79 个写口位需要人发票才能测（那次测试的账是另一本）；
2. `needs_params` 的 26 位没有真跑（不瞎编参数）；
3. 并发上限是单独一页（[08-concurrency.md](08-concurrency.md)），别把两件事混成一句"都能跑"。
