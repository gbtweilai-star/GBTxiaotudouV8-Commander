# 98 · 能力位到底几位？（341 / 348 / 368 / 375 / 385 的来龙去脉）

> 主人 2026-11-01 发火：「怎么能力位你是搞不清还是什么？341 的 348 的 375 的我也是醉了」
> 这篇不是辩解，是**把账摊开**：每个数字从哪来、现在以谁为准、以后怎么不再犯。

## 一、现读（唯一真源）

```
cap_self verify  →  registry = 385 · snapshot = 385 · dispatched = 385
                         只读 300 位 / 需授权 85 位（按 safe 字段现算）
```

**今天起，只有一个数：385。** 其他数字若出现在"当前口径"的位置，都是 bug。

## 二、那些数字是怎么来的（按时间）

| 数字 | 出处 | 性质 |
|---|---|---|
| **341** | 2026-10-21 **权重发布快照**（`data/capability-live-test.json` 那一轮普查） | 历史事实，保留 |
| **348** | 更早的注册表读数（当时文档手抄进 docs/02、11、13、15） | 过期快照 |
| **368** | 某次 docs/01 模型卡手抄的"现读" | 过期快照 |
| **375** | README / docs/03 / docs/90 上一版手抄的"现读" | 过期快照 |
| **385** | **现在注册表**（375 + skills_hub 376 + chain_kernel 377 + root_cause 378 + execution_guard 379 + cap_pack 380 + 4 个 MCP 位 + dual_gate385） | 唯一现读 |

**根因**：能力位一直在加，但 README/docs 里的数字是**手写**的 —— 没有"改代码就改文档"的硬约束，
于是同一个仓里同时躺着好几个"当前数"。这不是"搞不清"，是**没装护栏**（现在装了）。

## 三、修法（已落地）

1. **真源唯一**：`caps_registry.BENIGN_CAPS`（`cap_self verify` 三数对账）；
2. **文档齿轮** `gbt_allinone/tentacle/doc_counts.py`：
   - 扫 README + 7 份会写"当前数"的文档；
   - 只改"当前数"写法（`N 个能力位` / `N 位能力` / Caps 徽章 / 实测表 / 架构图注释 / docs/03 标题）；
   - **子集数重算**（只读位 / 写口位 / 改状态出网 按 `safe` 字段现算，不套总数）；
   - **docs/03 逐域表格**（位数 / 只读 / 需授权）按注册表重算；
   - **历史口径不动**（含 快照/当时/评估基准/2026-10-21 的行跳过，341 的说明原样保留）；
3. **一条命令同步**：`python tools/sync-cap-counts.py --check` / `--apply`；
4. **能力位自查**：`gbt.run_task("cap_self", {"op":"docs"})` → `clean / stale`（以后问"几位"先跑这个）；
5. **判据防回退**：`tests/test_doc_counts.py`（现读一致 + 历史口径保留，7 条全绿）。

## 四、本次同步清单（改前 → 改后）

| 文件 | 改了什么 |
|---|---|
| `README.md` | 徽章 375→385、正文 375→385、代码注释、标题、实测表、架构图注释 |
| `docs/01-model-card.md` | "368 个能力位"→385（341 快照说明**保留**） |
| `docs/02-architecture.md` | "348 位 × 30 域"→385；只读位 262→**300**；写口位 79→**85**；`safe=true/false` 两处同步 |
| `docs/03-capabilities.md` | 标题"共 375 位"→385；口径行"（375 位）"→385；只读 290→**300**；逐域表按注册表重算 |
| `docs/11-five-dim.md` / `docs/13-omni-plug.md` / `docs/15-tentacle-counter.md` | 348 → 385 |
| `docs/90-what-she-can-do.md` | 从注册表重新生成（标题 385 位） |

## 五、以后怎么问都不会再乱

```bash
python -c "import gbt_allinone as g; print(g.run_task('cap_self', {'op':'verify'})['gbt_result']['result']['counts'])"
python -c "import gbt_allinone as g; print(g.run_task('cap_self', {'op':'docs'})['gbt_result']['result']['verdict'])"
python tools/sync-cap-counts.py --check
```

三个命令都指向同一个真源；任何一个报 stale，就是有人又手写了数字 —— 跑 `--apply` 即可。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
