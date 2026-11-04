# 44 · 按源码自己的推荐跑一轮诊断（2026-11-01）

> 主人令：「可以继续按照源码推荐落地」
> 落地方式：不凭我猜，**把她自己那套诊断器全跑一遍**，按它们报的东西决定修什么、不修什么。

---

## 一、跑了哪些（都是仓里现成的判据）

| 诊断器 | 用时 | 判定 | 说明 |
|---|---|---|---|
| `selfscan` | 0.2 s | **clean** | routing 354/354 · modules 37/37 · store ok · audit 无现行故障 |
| `selfscan(full=True)` | 0.3 s | clean | 深扫同结论 |
| `ghost_guard` | 1.9 s | clean | 663 个文件，0 幽灵/0 残留 |
| `signature_guard` | 0.02 s | clean | 15 页署名齐全，0 缺失 |
| `sec_defenses` | 0.2 s | **5/5 全部生效** | 危险门禁 / 内网护栏 / 管线门禁 / 注册表完整性 / 写保护 |
| `truth_scan` | 0.02 s | clean | FAKE=0（零假执行），REAL=1（只读模式） |
| `cross_scan` | 87 s | findings=7，hard=3 | 见下 |
| `inventory` | 0.03 s | foreign_found | 29 项"异物" |
| `file_hygiene` | 11.7 s | messy | 29 条 `home_stray` |

## 二、修了什么（唯一一个真缺陷）

`selfscan` 首轮报 **P0：存储异常 · 缺目录 `wf_runs`**。

按源码自己的推荐（`autofix=True` 只做安全修复：补建缺目录、损坏 JSON 备份重置）：

```
run_task("selfscan", {"autofix": True})
→ "已自动修复: 补建目录 store/wf_runs"
```

复扫：**verdict=clean，findings=[]**，`store.missing_dirs=[]`。
这是本轮唯一真缺陷，已闭合。

## 三、没修的，以及为什么不修（这部分比修更重要）

### ① 29 项"异物" + 4 个"家根影子目录" = **布局假设不成立**，不是缺陷

`inventory` / `file_hygiene` / `cross_scan` 的 W·V 维都假定：

> 家根是一个**精心收过的目录**（作者机器上是 `/var/minis/shared/gbtv8`），
> 仓库包只是在其中一个子目录里。

而当前部署是 **仓库根 = 工作目录**（`pyproject.toml`、`gbt_allinone/` 都在根上），
于是 `docs/ assets/ data/ tests/ tools/` 这些**本来就是仓库的一部分**，被判成"异物/影子"。

**不修的理由**：修它只有两条路 ——
(a) 把 29 个目录搬走/删掉 ⇒ 破坏性、且会把仓库结构搞坏；
(b) 改 `inventory` 的分类表让它变绿 ⇒ **改尺子让读数好看**，本仓最忌。

正确做法是**把假设写出来**：这份文档就是记录。真要清零，得把仓库部署回"家根 + 子目录"的形态，
那是部署选择，不是代码缺陷。

### ② `cross_scan` 的 D/E/F 三维"只有名字"——**源码自己写明不实现**

`cross_scan.py` 文件头逐字写着：

- `F`（审计↔注册表）照最自然方式写会报 **86 条假警**（参考集不存在）；
- `D`（文档↔注册表）的来源**已存在**（`audit-injection-honesty.py`），再写一遍是**抄第二份判据**；
- `E`（测试数↔测试文件）**没有"声称的测试数"来源**，写它就是"造一台报假警的机器"。

⇒ 按源码推荐：**不实现**，继续如实列在 `dims_unimplemented` 里。这才是"按源码落地"。

## 四、这一轮之后的状态

| 项 | 状态 |
|---|---|
| 她的自知（354 位） | 三源一致（注册表=快照=分派） |
| 她的声带 | 无现行故障；插口变化已接入 |
| 四合一（脉冲/量化/按需/直达） | `pulse_core.verify` 全绿 |
| 万能插 | 34 根插头（port24/ai5/file2/process3），插口变化会进 diff 与 alerts |
| 防御矩阵 | 5/5 |
| 唯一残留 | 布局类"异物"（部署形态导致，非缺陷） |

## 五、判决层（另一个任务，仍在跑）

478 项逐项过她的权重，已完成 **91 项 / 84 命中（95.6%）**，剩 42 项抽样在跑；
逐项明细 `state/commander/coverage-rows.jsonl`（可断点续跑）。

---

## 六、第二轮（按源码推荐继续落地）

第一轮剩下 5 条 findings（hard 3）。按"源码自己推荐"的口径又落了两处：

### ① `inventory` 认「部署形态」（真判据，不是把尺子调松）

旧分类器只有一种假设：**家根是收过的目录、仓库在子目录里**。当前部署是 **根即仓库**，
于是 29 个仓库自己的顶层项被判"异物"。

修法：多认一种形态 —— checkout（根上有 `pyproject.toml` + `gbt_allinone/`）下，
仓库**声明过**的顶层项归 `framework`。清单来自 `state/repo-layout.json`（由仓库快照生成，
41 项），取不到才退回页图前缀与固定件，**绝不猜**。

读数变化：

| 项 | 修前 | 修后 |
|---|---|---|
| `inventory.verdict` | foreign_found | **clean** |
| 异物数 | 29 | **0** |
| `file_hygiene.verdict` | messy（29 条 home_stray） | **clean（0 条）** |
| `cross_scan` findings | 7（hard 3） | **verdict=clean，hard=0**（剩 4 条 W 维 latent） |

判据 `tests/test_inventory_checkout.py`：checkout 下仓库项归 framework、清单外的东西**仍判 foreign**、
把开关拨回 home 形态后**旧读数不变量**（不许为了让我们绿而改别处的口径）。

### ② `signature_guard`：4 份文档缺署名，用工具自己的 restore 补回

`CHANGELOG.md` / `README.en.md` / `SECURITY.md` / `WEIGHTS.md` 缺开发者署名（仓规：每一页都要有）。
按仓里自己的安全路径 `signature_guard restore=True` 补回 → 复检 `verdict=clean`，22 页全齐。

### ③ 剩下的 W 维（4 个"影子子目录"）—— 不修，如实记

`assets / docs / tests / tools` 在根上与 `gbt_allinone/` 下同名。仓里 W 维把它标成
`exposure=latent`（潜在、非现行）。**不修的理由**：这不是缺陷，是**包内子目录 + 仓库根目录**并存的正常形态；
要"清零"只能删根目录或改包结构，两边都是破坏性动作。记在这里，等部署形态变化时再评估。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
