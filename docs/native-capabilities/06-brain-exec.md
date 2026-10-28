# 06 · 大脑执行层 (`brain_exec`)

> 5 能力位 · 五维合一的统一调度头 · route→execute→verify→health
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 架构设计

```
                    ┌─────────────┐
                    │  brain_unify │ ← 五维合一总入口
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
    │  route    │   │  execute  │   │  verify   │
    │ 意图→能力  │   │ 并行执行   │   │ 触手验证   │
    │ 语义匹配   │   │ 万能插DAG │   │ 视觉+UIA  │
    └───────────┘   └───────────┘   └───────────┘
                           │
                    ┌──────▼──────┐
                    │   health    │
                    │ 五维自检评分 │
                    └─────────────┘
```

**串链语义**：route 的 `best.kind` 喂给 execute → execute 的结果喂给 verify → verify 的结果喂给 health。数据顺着走，不是星形分调。

## 能力清单

| 能力位 | 说明 |
|---|---|
| `brain_route` | 意图→能力动态路由（语义匹配注册表+备选建议） |
| `brain_execute` | 单能力直调或多能力并行（万能插线程池） |
| `brain_verify` | 触手肉眼验证现实（视觉指纹+UIA穿透读回） |
| `brain_health` | 五维自检评分（路由/执行/触手/视觉/审计） |
| `brain_unify` | 五维合一：一次跑完 route→execute→verify→health |

## 五维详解

### Route · 路由维

```python
import gbt_allinone as gbt

result = gbt.run_task("brain_route", {"intent": "扫描example.com的DNS信息"})
# 返回: {
#   ok, best: {kind: "osint_scan", score: 0.92},
#   alternatives: [{kind: "recon_distill", score: 0.45}],
#   understanding: "用户想扫描example.com的DNS..."
# }
```

**语义匹配**：从注册表描述字段提取关键词，与用户意图做语义相似度匹配。

### Execute · 执行维

```python
# 单能力直调
result = gbt.run_task("brain_execute", {"kind": "osint_scan", "params": {"target": "example.com"}})

# 多能力并行
result = gbt.run_task("brain_execute", {
    "parallel": [
        {"kind": "osint_scan", "params": {"target": "example.com"}},
        {"kind": "sec_scan", "params": {"target": "."}}
    ]
})
```

### Verify · 验证维

```python
result = gbt.run_task("brain_verify", {
    "kind": "tentacle",
    "action": "see"
})
# 用触手肉眼验证：截屏→视觉指纹→UIA穿透读回
```

**五维穿透**（UIA无视遮挡）：
- `domain_index` 索引（窗口/控件树）
- `domain_read` 读（窗口内容）
- `domain_type` 写（输入文本）
- `domain_act` 动作（点击等，含坐标兜底）
- 视觉（vision_bus 全屏帧）——先看再动的"看"

### Health · 健康维

```python
result = gbt.run_task("brain_health", {})
# 返回: {
#   ok, scores: {
#     routing: 1.0,     # 路由完整性
#     execution: 0.95,  # 执行成功率
#     tentacle: 0.88,   # 触手可用率
#     vision: 0.92,     # 视觉通道
#     audit: 1.0        # 审计完整性
#   },
#   overall: 0.95
# }
```

### Unify · 五维合一

```python
result = gbt.run_task("brain_unify", {"intent": "扫描example.com并验证"})
# 自动执行: route → execute → verify → health 全链
# 返回: {ok, route: {...}, execute: {...}, verify: {...}, health: {...}}
```

## 进出成对事件（span）

每次调用维度的进出各一条审计事件：

```jsonl
{"event":"brain_enter","dim":"route","intent":"扫描example.com"}
{"event":"brain_exit","dim":"route","ok":true,"ms":45}
{"event":"brain_enter","dim":"execute","kind":"osint_scan"}
{"event":"brain_exit","dim":"execute","ok":true,"ms":3200}
```

- 进了没出 → 忙（真在跑）
- 进了超时还没出 → 卡（真卡住）
- 出了 → 成/败（带真实耗时ms）

## 最小结果契约

每一维出厂自带验收（不依赖外部声明）：
- 是dict、非空
- 至少有一个结果指示字段（`ok`/`status`/`result`/`kind`/`found`/`caps`/`dims`/`reply`）

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
