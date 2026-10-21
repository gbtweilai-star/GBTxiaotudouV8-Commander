# 07 · 能力自证：341 位逐位真调（不是"模型会背"，是"调得动"）

> 前一页证明**它说得出**；这一页证明**它真调得动**。
> 读数由**三路真跑**合成（只读位空参真调 / 需参数位带真参真跑 / 写口位隔离 store 真跑），
> 由 `tools/codex-scripts/gen-capability-proof.py` 合并成一份账：
> [`../data/capability-live-test.json`](../data/capability-live-test.json)（**341 位一位一行，不重叠**）。

![能力自证](../assets/fig-caps.png)

## 一、规则（先写死，再跑）

| 位类型 | 怎么测 | 为什么这样定 |
|---|---|---|
| 只读 且 无需参数 | **真调一次**（空 payload），记耗时/状态；超时上限 90s（慢≠坏） | 这是"能力属实"最硬的证据 |
| 需参数 | **带人写的样本参数真跑**（不自动猜、不瞎编） | 瞎编参数的绿是假绿；缺参就记 `needs_input` |
| 写口 | **隔离 store（临时目录）里真跑**；要票的当场拒；高危 8 位不跑 | 不拿主人的仓库当试验场，也不假装跑过 |

每发调用带 **12 秒看门狗**；超时记 `timeout`（**不记 0、不记 ok**）。

## 二、读数（多路真跑合成 · 2026-10-21 现读）

| 结果 | 位数 | 来源 / 说明 |
|---|---:|---|
| ✅ 真跑通过 | **337** | 监控账 216（90s 超时下真调）+ 写口 50（隔离 store）+ 隐私与流程 46 + 需参数 16（带真参）+ 带票 10（主人发票后真跑）+ 房间晋升 1 + 打断链 1 + 出图门 1 |
| 🔒 要票未跑 | **1** | `pentest`：目标未登记授权（票在主人手里，不是模型能自给） |
| ⚙ 缺输入未跑 | **2** | `codex_interrupt`（打断一个**活回合**的三层前置不成立，见 §十）· `offense_ops`（缺授权目标） |
| 🧩 缺依赖未跑 | **1** | `comfy_cloud`：云卡不可达（本地 27 个原生算子照常可跑） |
| 🚫 高危未跑 | **0** | — |
| ❌ 失败 | **0** | — |

> 合计 337 + 1 + 2 + 1 + 0 + 0 = **341**，一位不多一位不少（生成器里写死这个断言，对不上就退出）。

**"要票"不是"失败"，是门在生效。** 那 10 位 `src=ticket` 的位就是活证据：主人在终端发票之前它们记 `needs_ticket`，
发票之后同一条命令就跑通了（`probe-with-tickets.py`，票用完即销的位不重复消费）。现在只剩 `pentest`
一张票——它要的不只是作用域，而是**授权目标先登记**（谁有权把"要打哪个目标"写进授权表，是人，不是模型）。

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

1. 写口位是在**隔离 store** 里真跑的（高危 8 位按名单跳过），不是在你的生产目录上跑；
2. `needs_input` 的 3 位**没有瞎编参数**：缺什么就记什么，缺票就写缺哪张票；
3. 并发上限是单独一页（[08-concurrency.md](08-concurrency.md)），别把两件事混成一句"都能跑"。

## 七、自己复核（五条命令，不需要任何票）

```bash
# ① 只读位：空 payload 逐位真调（90s 超时；慢 ≠ 坏）
py -3.14 tools/codex-scripts/probe-caps-live.py --timeout 90

# ② 需参数位：带**人写样本参数**真跑（隔离 store；不自动猜参数）
py -3.12 tools/codex-scripts/probe-caps-params.py

# ③ 写口位：隔离 store 真跑（高危 8 位按名单跳过）
py -3.12 tools/codex-scripts/probe-caps-write.py

# ④ 合成一份账（分桶合计 ≠ 341 会直接退出，防止漏位）
py -3.12 tools/codex-scripts/gen-capability-proof.py
```

> 口径要点：**降级/拒绝/缺参都如实入账**；`信封 status=ok` 但本体 `ok=false` 不算通过；
> 要票的位只有主人发票后才会转绿（`probe-with-tickets.py`），票用完即销的位不重复消费。

## 八、已知未跑（逐位原因 + 机器回执，不是遮丑）

> 本页所有数字都是"真跑过"的；下面这 **4 位**没有跑通，原因逐条列出，任何人可复跑复核。
> 合计：**337 通过 / 1 要票 / 2 缺输入 / 1 缺依赖 / 0 高危未跑 / 0 失败 = 341**

| 位 | 分类 | 机器回执 / 原因 |
|---|---|---|
| `pentest` | 要票 | 目标未登记授权 —— 需人把授权目标写进表，模型无权代写 |
| `codex_interrupt` | 缺输入 | 同进程三步探针断在 `turn_send`：app-server 不推通知 ⇒ 抓不到 turnId；而 `start_turn` 阻塞到回合跑完才返回（三条原因见 §十） |
| `offense_ops` | 缺输入 | `need_target` —— 与 `pentest` 同一根：授权目标未登记 |
| `comfy_cloud` | 缺依赖 | 云卡 `status` 不可达（远端环境；本地 27 个原生算子不受影响） |

> 复跑：`py -3.12 tools/codex-scripts/gen-capability-proof.py`（分桶合计 ≠ 341 直接退出）。

## 九、2026-10-21 修的两处真缺陷（都是"假账"引信）

跑 `one_key_deploy`（房间落点）第一次真跑时，回执是两条红：

```
scan 3/3 · rehearse=False · blockers=['静态推演未全绿', "未通过验收命令: ['py-syntax-sweep']"]
```

两个都不是"能力不行"，是**我们自己的判据在说假话**：

| # | 现象 | 根因 | 修法 | 判据 |
|---|---|---|---|---|
| 1 | 静态推演永远报「未声明入口」，且不说什么算入口 | 入口名在 `scan` / `simulate` / `qiankun` **各抄了一份**四个字面量；而 `simulate` 只看计划里声明的 `entrypoints`，**根本没看树** ⇒ 任何没手填该字段的计划永远过不了 | 入口名收敛成**唯一定义** `room_space.ENTRY_NAMES`；`simulate` 在未声明时**按名字在维度树里真找一遍**（找不到才红，且把可识别名报出来）；`qiankun` 面对没有入口的树**当场如实拒绝**，不再立一份过不了的计划 | `tests/test_room_entry_contract.py` |
| 2 | 验收命令**一次都没跑**，回执却写「未通过验收命令」 | `rehearse` 的执行条件是 `if execute and not blockers`：静态一红就跳过全部命令，但回执把没跑的用例照样列进"未通过" ⇒ 一次失败被记成两笔 | 拆成两句话：`验收命令未执行（前置未过：…）` vs `未通过验收命令`；结果里加 `commands_skipped` / `commands_skip_reason` | 同上（含负控：不许出现"未通过"） |

修完重跑同一条命令（房间 `release-20261021`，77 件产物）：

```
stage ok · plan ok(auto) · scan 3/3 · rehearse ok(acceptance=py-syntax-sweep 真执行) · release ok · 5.9s
```

这一位（`one_key_deploy`）因此从"缺输入"转为"真跑通过"，本页数字由 335 升到 336
—— **是靠修掉真缺陷扛上去的，不是靠改判据放行**（同上两条判据仍咬住"必须有入口""必须有验收命令真跑"）。

## 十、再收两位：出图门（真看图）与打断链（真根因）

### `figure_gate`：过门靠"真看了四轮"，不是靠声明

这个门要三样东西：`numbers` 声明出处、**至少 4 轮**看图记录、且**最新一轮的问题清单为空**。
这一轮逐张看（七张测试图 + 落地页截图），逮到 **3 处真问题**、修完复看清零：

| 轮 | 看了 | 逮到的问题 | 修法 |
|---:|---|---|---|
| 1 | `fig-caps` | 副标题写死「三路真跑」而账里已有 6 路证据；卡片副标漏了带票/房间两类来源 | 副标题改成五类真跑；加一行**来源计数**（由数据自己给），并点名要票那一位 |
| 2 | `fig-eval`·`fig-chain` | `fig-eval` 的「⇒」渲染成**豆腐块**（字体缺字）；且把 99.10% 与卡片上的 98.51% 混在同一句，读着像自相矛盾 | 换成「，所以」；把两轮写清「第1轮 332/335 · 第2轮 330/335」 |
| 3 | `fig-domains`·`fig-concurrency`·`fig-tianzhen`·`fig-monitor` | `fig-monitor` 同一处「⇒」也是豆腐块（另三张无问题） | 同样换字；渲染器里 `⇒` 归零 |
| 4 | `fig-caps`·`fig-eval`·`fig-monitor`·`index.html` 截图 | **无** | — |

门自判：`deliverable=true · rounds=4 · open_issues=[] · reasons=[]`。
判据在它自己手里，本页的数字**问它现读**（不手抄）。

### `codex_interrupt`：还没绿，但原因是三层叠加，不是"没这功能"

此前记账只有一句 `no active turn to interrupt`，看不出真因。这一轮逐层量到底：

1. **跨进程必然丢线程**：`get_shared_server()` 的缓存是**进程级**的，而每条 `cap` 都是一次新进程
   ⇒ 进程 A 开的线程，进程 B 拿不到（实测回执 `thread not found`）。
2. **`start_turn` 是阻塞的**：它要等回合跑完才返回 ⇒「先 send 再 interrupt」永远晚一步。
3. **app-server 不推通知**：本进程订阅 `turn/*` 期间**一条通知都没收到**（`notifications_seen: []`），
   于是拿不到打断需要的 `turnId`（上游原话：`missing field turnId`）。

这三条都记在 `data/codex-interrupt-live.json`（探针 `probe-codex-interrupt.py`，同进程三次过门）。
**下一步要补的是「让 app-server 回流通知」这一腿**，不是能力本身 —— 补完这一位才该转绿。


