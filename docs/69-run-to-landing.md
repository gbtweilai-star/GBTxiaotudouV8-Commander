# 69 · 跑到落地：中途不停（2026-11-01）

> 主人严令（逐字）：「从架构蓝图用户确认之后就开始执行直到项目落地，中途除非用户打断
> 要不然严禁停下，自己内部沟通写作执行到项目落地」。

---

## 一、`blueprint.land`：一轮轮跑到落地

```python
run_task("blueprint", {"op": "land", "id": "<蓝图id>", "max_rounds": 6})
# → {landed, rounds: [{round, dispatched, done, failed, landed}], blocked?, need_ticket?}
```

三条内部纪律：

| 纪律 | 实现 |
|---|---|
| **不停** | 有失败就下一轮；已完成任务**不重跑**（读 runs.jsonl） |
| **不问** | 全程不找主人；只有"只剩需要票的任务"时才 blocked 并说明 |
| **留痕** | 每轮写编排账本 + runs.jsonl；重启可续 |

## 二、实测

```
蓝图 触手主干无限制上下-29d15d（21 任务，架构关键词触发专项）
approve → land
land  → 第 1 轮：dispatched=21 · done=21 · failed=0 · landed=True
        第二遍 land → "已落地（第 1 轮前就已满足）"，不再重跑
```

## 三、无人值守入口

```powershell
# 现场造蓝图 → 直接过目（主人已确认）→ 跑到落地
py -3 -X utf8 tools\blueprint-land.py --arch "触手主干 + 无限制上下文 + 自主吞噬 + 脉冲提速" --approve

# 已有蓝图继续跑（可多轮）
py -3 -X utf8 tools\blueprint-land.py --id <id> --max-rounds 20

# 看所有蓝图进度
py -3 -X utf8 tools\blueprint-land.py --list
```

退出码：`0`=落地，`1`=未落地/需票。**不会在中途停下来问"要不要继续"**。

## 四、什么时候会停（只有三种）

1. **落地了**（全部任务通过）；
2. **只剩需要票的任务**（危险能力/转账）—— 这是主人给的唯一例外；
3. **轮次用尽仍未落地** —— 如实报"没落地"，不装完成。

除这三种，`land` 会一直重试失败项。

## 五、边界

- "内部沟通写作执行"目前是**靠任务图与账本协调**（每个任务独立执行、失败重试、依赖满足才往下）；
  还没接"多个触手互相讨论"（那要 LLM 长上下文，等权重跑得动）；
- 失败重试**不掩盖失败**：每轮 failed 数都记，`landed` 仍要求全部通过；
- `land` 是同步执行，长任务建议用 `tools/blueprint-land.py` 放后台跑。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
