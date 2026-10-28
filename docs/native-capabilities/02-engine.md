# 02 · 万能插执行引擎 (`engine`)

> 12 能力位 · DAG工作流并行执行 + 传输算子 + 条件分流 + 传输缓存
>
> 立场：框架内不依赖子代理。脑子只有一份（SOUL + run_task），手有很多只（引擎线程池）。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 架构设计

```
    ┌─────────────────────────────────────────┐
    │           wf_define(name, nodes)         │
    │     校验：id唯一/依赖存在/无环/kind注册   │
    └────────────────┬────────────────────────┘
                     │
    ┌────────────────▼────────────────────────┐
    │            wf_run(name, inputs)          │
    │   ┌─────────────────────────────┐       │
    │   │    分层并行执行（线程池）      │       │
    │   │  Layer 0: [A] [B] [C]        │       │
    │   │  Layer 1: [D←A] [E←B,C]     │       │
    │   │  Layer 2: [F←D,E]            │       │
    │   └─────────────────────────────┘       │
    │   模板注入: {{node.field.path}}          │
    │   fail_fast: 节点失败即停                │
    └────────────────┬────────────────────────┘
                     │
    ┌────────────────▼────────────────────────┐
    │         wf_status / wf_resume           │
    │    运行记录查询 / 断点续跑               │
    └─────────────────────────────────────────┘
```

## 能力清单

| 能力位 | 类型 | 说明 |
|---|---|---|
| `wf_define` | 只读 | 定义DAG工作流（校验环/依赖/能力合法性） |
| `wf_run` | 只读 | 分层并行执行，`{{node.path}}`模板注入上游输出，fail-fast |
| `wf_status` | 只读 | 运行记录查询（可按工作流名过滤） |
| `wf_resume` | 只读 | 断点续跑（复用已完成节点，只重跑未完成的） |
| `wf_cache_clear` | 只读 | 清空传输缓存 |
| `transfer` | 只读 | 数据传输算子：14个纯变换（map/filter/merge/unique/sort/pluck/collect/flatten/split/join/rename/wrap/stats/limit） |
| `sched_define` | 只读 | 定时触发器定义 |
| `sched_tick` | 只读 | 定时触发器推进 |
| `sched_status` | 只读 | 定时触发器状态 |
| `workflow_forge` | 需授权 | 工作流十式（find_skill/grill/arch_review/tdd_loop等） |

## 节点级武器（四把）

| 武器 | 说明 | 示例 |
|---|---|---|
| `timeout` | 节点超时秒数，超时如实报错 | `"timeout": 30` |
| `when` | 条件执行表达式（AST白名单求值，安全） | `"when": "node_prev.ok == true"` |
| `fallback` | 降级回退，主能力失败改走备选 | `"fallback": {"kind": "echo", "params": {"data": "降级"}}` |
| `retry_backoff` | 重试退避秒数（配合max_node_retries） | `"retry_backoff": 2` |

## 核心传输工具

### 扇入聚合

```json
// 收集全部上游结果
"params": {"all": "{{*}}"}

// 收集多路上游字段成列表
"params": {"words": "{{*.gbt_result.result.words}}"}
```

### 条件分流（routes）

```json
{
  "id": "router",
  "routes": [
    {"when": "input.type == 'text'", "kind": "llm_chat", "params": {...}},
    {"when": "input.type == 'image'", "kind": "vision", "params": {...}},
    {"when": "true", "kind": "echo", "params": {"data": "未知类型"}}
  ]
}
```

### 传输缓存

```json
{
  "id": "cached_node",
  "kind": "llm_chat",
  "cache": true,
  "cache_ttl": 300,
  "params": {"prompt": "..."}
}
```

### 层级传输（工作流嵌套）

```json
{
  "id": "sub_workflow",
  "kind": "wf_run",
  "params": {"name": "sub_task"}
}
```

深度保护：`MAX_WF_DEPTH = 5`，超出即拒。

## API参考

### 定义并执行工作流

```python
import gbt_allinone as gbt

# 定义工作流
gbt.run_task("wf_define", {
    "name": "scan_and_report",
    "nodes": [
        {"id": "scan", "kind": "osint_scan", "params": {"target": "example.com"}},
        {"id": "analyze", "kind": "llm_chat", "depends_on": ["scan"],
         "params": {"prompt": "分析扫描结果: {{scan.gbt_result.result}}"}},
        {"id": "save", "kind": "pipeline_submit", "depends_on": ["analyze"],
         "params": {"name": "report.md", "content": "{{analyze.gbt_result.reply}}"}}
    ]
})

# 执行
result = gbt.run_task("wf_run", {"name": "scan_and_report"})
```

### 传输算子

```python
# map: 对列表每个元素应用能力
gbt.run_task("transfer", {"op": "map", "items": [1,2,3], "kind": "count_words"})

# filter: 过滤
gbt.run_task("transfer", {"op": "filter", "items": [...], "field": "ok", "equals": True})

# merge: 合并多个字典
gbt.run_task("transfer", {"op": "merge", "items": [{"a":1}, {"b":2}]})
# → {"a":1, "b":2}

# sort: 排序
gbt.run_task("transfer", {"op": "sort", "items": [...], "key": "score", "desc": True})
```

## 性能基线

| 场景 | 结果 |
|---|---|
| 5路并行 | 全OK |
| 20路并发 | 全OK |
| 80路并发 | 全OK |
| **160路并发** | **ALL_OK，加速比39.77x** |
| 审计行数 | 1694行零损坏 |
| 运行记录 | 零碰撞 |

## 存储模型

```
store/workflows.json      # 工作流定义（按名幂等覆盖）
store/wf_runs/<id>.json   # 每次运行完整记录（节点状态/结果/耗时）
```

## 设计纪律

1. **纯标准库、零模型调用**——并行编排成本 ≈ 0（比LLM子代理省一个数量级）
2. **fail-fast**：任何节点失败即停，如实上报，不伪造成功
3. **模板安全**：AST白名单求值，禁函数调用
4. **层级保护**：工作流嵌套深度上限5层

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
