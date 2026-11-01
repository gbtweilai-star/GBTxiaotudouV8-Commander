# 60 · GBT天真 执行引擎加固（2026-11-01）

> 等秋叶版真快照期间做的**地基活**：不依赖节点清单，让"复杂图"真的能跑、跑坏了能收场。

---

## 一、加固的四条语义

| 语义 | 字段 | 行为 |
|---|---|---|
| **条件旁路** | `skip: true` | 节点不执行，trace 记 `skipped`（对齐 ComfyUI 绕行语义） |
| **重复执行** | `times: N` | 同节点重复 N 次（上限 50，防跑飞） |
| **失败策略** | `on_error: "stop" \| "continue"` | 默认 stop；continue 时失败节点留 trace 且 ok=false，后续照跑 |
| **失败回滚** | 自动 | 首次失败时删掉**本次新建**的产物（`rolled_back` 如实列出）；**旧文件不碰** |

另外：**未接线节点明确报 `unwired`**——不装作能跑。实测还会先被白名单拦（fail-closed），两道都在。

## 二、判据（tests/test_comfy_engine.py，5 组 11 条）

```
[1] skip 旁路          3/3 ok
[2] times 重复执行      1/1 ok
[3] 失败回滚            4/4 ok（含"回滚后文件确实没了"）
[4] on_error=continue   2/2 ok
[5] 未接线节点          1/1 ok（必须明说）
ALL OK
```

## 三、为什么先做这个（而不是继续堆节点）

「一比一」要等秋叶真快照；但**图的复杂度**不依赖清单：循环、旁路、失败收场，这些是
"能不能跑生产级 workflow"的地基。地基不稳，节点再多也只是一堆孤立算子。

而且失败回滚这条是**安全线**：没有它，一次中途失败会在 store 里留半成品，
后面的人（或她自己）会把半成品当成品用 —— 这正是"静默造假"的一种。

## 四、复跑

```powershell
py -3 -X utf8 tests/test_comfy_engine.py
py -3 -X utf8 -c "from gbt_allinone.tools import comfy_native as CN; print(len(CN.NODES))"
```

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 五、顺手修的一个"自己污染自己"（判据抓到的）

加了冒烟测试后，	est_inventory_checkout **红了**：仓根多出 store（是冒烟产物落在仓库根）。
处理：冒烟产物全部改到 state/tmp/，删掉仓根 store，复跑两套判据都绿。

**这条值得记**：判据不是只测别人的，它也会抓住我自己的副作用。
