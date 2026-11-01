# 61 · 秋叶版取食器：只取我们缺的、用得上的（2026-11-01）

> 主人口径（逐字）：「秋叶版机器跑一次，这一步不需要直接吞噬我们需要的权重即可，
> 没用且我们有的不需要」。

---

## 一、为什么要"取食器"而不是"整包一比一"

秋叶整包 ~1495 把里，**大部分对我们没用**：采样器/加载器/VAE/ControlNet 要 GPU 与权重，
本机 AMD 无 CUDA；云端 API 要 key。整包吞下来只会让仓库变胖、让读数变好看但**没有一棵能跑**。

所以流程改成两条命令：**采集（秋叶机）→ 取食（只筛我们缺且能用的）**。

## 二、取食规则（表里写死，不临场发挥）

| 类 | 判据 | 处置 | 本轮读数（核心面 127） |
|---|---|---|---|
| **已有** | 我们 `NODES` 同名已实现 | ❌ 不要 | 17 |
| **可用缺口** | 我们没有 + 纯 CPU 传统算子 | ✅ 取 | **0** |
| **模型面** | 采样/加载/VAE/条件/ControlNet/合并 | ❌ 不取（无 CUDA，**权重一个不下**） | 103 |
| **云端** | 需 key 的 API 节点 | ❌ 不取 | 0 |
| 不认识 | 静态无法归类 | ⏸ 先不动（不假设能实现） | 7 |

`state/comfy-harvest.json` 落全部清单，`useful_list` 就是"下一批该补什么"。

## 三、顺手修的两个真问题

1. **分类顺序错了**：`ModelMergeFlux1` / `ModelSamplingFlux` 因为含 "Flux" 被当成云端 API，
   实际是**模型合并/采样**节点。改为**模型面优先于云端**（两个工具都修）。
   修完：云端 2 → **0**，模型面 101 → **103**（更诚实）。
2. **Loop 结构性节点缺失**：秋叶图里的 `StartLoop`/`EndLoop`/`LoopIteration`/`LoopResult`/`LoopProgress`
   是**结构性标记**（不产图），我们没有 ⇒ 秋叶的图进来直接白名单拒。
   已补 5 个（`writes=False`），真正循环仍由引擎 `times` 语义执行，`EndLoop` 会校验与 `StartLoop` 配对。

## 四、当前读数

| 指标 | 数值 |
|---|---|
| 我们节点 | **55**（50 + 5 Loop 结构） |
| 同名覆盖（核心面 127） | **17 = 13.4%** |
| traditional 缺口 | **0** |
| needs_model | 103（如实不接） |
| needs_cloud | 0 · unknown 7 |

## 五、两条命令（秋叶机上跑一次，之后只筛不吞）

```powershell
# ① 秋叶机器（ComfyUI 已启动，只读一个 GET）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\collect-object-info.ps1

# ② 回到仓库：只筛我们缺的、用得上的
py -3 -X utf8 tools/comfy-harvest.py --top 40
```

第 ② 步的输出就是"下一批要补的节点名清单"，**不含权重、不含模型节点、不含我们已有的**。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 六、校验期就能看见「全部未接线」（同轮跟进）

以前 `validate` 只在执行期才炸（白名单拦），而且**只报第一个**；现在：

| 能力 | 之前 | 现在 |
|---|---|---|
| 一张图里未接线的节点 | 执行时炸，只报第一个 | **校验期就列全**（`unwired_nodes`，每个带处置说明） |
| 整个契约面覆盖 | 没有入口 | 新增 **`op=coverage`**：契约数/原生数/缺失数/覆盖率/按类（traditional·model·cloud·unknown） |
| 契约快照缺失 | 直接 `no_contract_snapshot` | 退到**核心面参照**（标 `core_ref_fallback`，不冒充秋叶） |

实测：

```
coverage：契约 127 · 原生 17 · 缺失 110 · 覆盖 13.4%
          按类 {traditional: 0, model: 103, cloud: 0, unknown: 7}
validate：图里 KSampler + VAEDecode ⇒ 两个都被列出，各带 how（"要 GPU/权重，本机不接"）
```

判据也补上了（`test_comfy_engine` 第 [6] 组 5 条）：覆盖能读、契约数 >0、覆盖率是数、
**两个未接线节点都被列出（不是只报第一个）**、每个未接线带处置说明。

---

## 七、覆盖读数进记忆条 + 校验留痕（同轮跟进）

### 1. 记忆条（1053 字符，每次判决默认注入）

> 构图：GBT天真 55 个原生节点（纯 CPU；对 ComfyUI 核心面 traditional 缺口 0）、
> **契约面覆盖 13.4%（17/127）**，模型面/采样面无 CUDA 如实不接；
> 秋叶整包要一比一 ⇒ 在秋叶机跑 `tools/collect-object-info.ps1`。

读的是 `state/comfy-parity.json`（小文件，毫秒级），不是每次去算 127 把。

### 2. 校验留痕

以前 `validate` 校验完**不留记录**，等于"验过但无法证明"。
现在每次校验追加一行到 `state/comfy-validate.jsonl`（时间/节点数/错误数/未接线数）。

判据补第 [7] 组：**校验后审计行数必须 +1**。

---

## 八、取食器接成能力位（她自己能"看菜下锅"）

以前只有 CLI（要我手动跑）。现在 `comfy_native op=harvest` 走门即可调用：

```python
run_task("comfy_native", {"op": "harvest", "limit": 30})
# → {contract_total, ours_total, have, useful, skip_model, skip_cloud, unknown,
#     useful_list, rule}
```

实测（核心面参照）：

```
contract 127 · ours 55 · have 17 · useful 0 · skip_model 103 · skip_cloud 0 · unknown 7
rule：已有不要 / 模型面与云端不取（无 CUDA 无 key）/ 只取纯 CPU 传统算子的契约；权重一个不下
```

拿到秋叶真快照后，她**自己**就能回答：「我缺哪些、哪些值得补、哪些根本不该取」，
不用等我跑脚本。判据补第 [8] 组 3 条（能读/有分类计数/规则说清）。
