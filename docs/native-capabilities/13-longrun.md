# 13 · 长程任务 (`longrun`)

> 3 能力位 · 非LLM验收 + 重试 + 停滞升级 · 跨进程可续
>
> 无人值守执行的任务图管理。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 架构设计

```
    lr_submit（提交任务）
         │
         ▼
    ┌─────────────────────────────────────┐
    │          任务图 (task graph)         │
    │                                     │
    │  [T1] ──▶ [T2] ──▶ [T3]            │
    │           │                         │
    │           └──▶ [T4]                 │
    └──────────────┬──────────────────────┘
                   │
    lr_tick（推进）
         │
    ┌──────▼──────┐
    │  执行节点    │
    └──────┬──────┘
           │
    ┌──────▼──────────────────┐
    │  非LLM验收（机械判据）    │
    │  ├─ 通过 → 完成          │
    │  ├─ 失败 → 重试          │
    │  └─ 停滞 → 升级（报警）   │
    └─────────────────────────┘
```

## 能力清单

| 能力位 | 说明 |
|---|---|
| `lr_submit` | 提交任务（非LLM验收+重试+停滞升级，跨进程可续） |
| `lr_tick` | 推进任务图（执行→验收→完成/重试/停滞） |
| `lr_status` | 任务图进度与详情 |

## API参考

### 提交任务

```python
import gbt_allinone as gbt

result = gbt.run_task("lr_submit", {
    "name": "nightly-report",
    "tasks": [
        {
            "id": "T1",
            "kind": "osint_scan",
            "params": {"target": "example.com"},
            "accept": {"field": "ok", "equals": True}   # 机械判据
        },
        {
            "id": "T2",
            "kind": "llm_chat",
            "depends_on": ["T1"],
            "params": {"prompt": "总结: {{T1.result}}"},
            "accept": {"field": "reply", "min_len": 50},
            "max_retries": 3
        }
    ]
})
# 返回: {ok, graph_id: "lg-20261028-070600", tasks: 2}
```

### 推进任务图

```python
result = gbt.run_task("lr_tick", {"graph_id": "lg-20261028-070600"})
# 返回: {
#   ok,
#   done: ["T1"],
#   running: ["T2"],
#   retried: [],
#   stalled: [],
#   pending: []
# }
```

### 查进度

```python
result = gbt.run_task("lr_status", {"graph_id": "lg-20261028-070600"})
# 返回: {
#   ok,
#   tasks: {
#     T1: {status: "done", ms: 3200, attempts: 1},
#     T2: {status: "running", attempts: 2}
#   },
#   progress: "1/2"
# }
```

## 非LLM验收（关键设计）

验收**不靠LLM判断**，靠**机械判据**：

| 判据类型 | 说明 | 示例 |
|---|---|---|
| `field` + `equals` | 字段等于某值 | `{"field": "ok", "equals": true}` |
| `field` + `min_len` | 字段长度下限 | `{"field": "reply", "min_len": 50}` |
| `field` + `exists` | 字段存在 | `{"field": "result.path", "exists": true}` |
| `file_exists` | 文件存在 | `{"file_exists": "out/report.md"}` |
| `file_min_size` | 文件大小下限 | `{"file_min_size": 1024}` |

**为什么不用LLM验收**：LLM验收不可靠、不可复现、成本高。机械判据可复现、零成本、不撒谎。

## 重试与停滞

```
尝试1 → 失败 → 退避 → 尝试2 → 失败 → 退避 → 尝试3 → 失败
                                                        │
                                              达到max_retries
                                                        ▼
                                              标记 stalled
                                                        │
                                              升级：写入alerts
```

**停滞升级**：连续失败达到 `max_retries`（默认3）后，任务标记为 `stalled` 并写入 `alerts`，不再无限重试。

## 跨进程可续

任务图状态持久化到 `store/longrun/<graph_id>.json`，进程重启后可继续：

```python
# 进程A提交并推进一部分
gbt.run_task("lr_submit", {...})
gbt.run_task("lr_tick", {"graph_id": "..."})

# 进程B（重启后）继续
gbt.run_task("lr_tick", {"graph_id": "..."})
```

## 与万能插的区别

| 维度 | engine (wf_run) | longrun (lr_tick) |
|---|---|---|
| 执行模式 | 一次跑完 | 分次推进 |
| 验收 | 节点返回ok | 机械判据 |
| 重试 | 节点级retry_backoff | 任务级max_retries |
| 跨进程 | 否 | **是** |
| 适用场景 | 短时工作流 | 长时间无人值守 |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
