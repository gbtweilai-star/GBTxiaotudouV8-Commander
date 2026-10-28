# 05 · 生产管线 (`pipeline`)

> 8 能力位 · 唯一交付通道 · 镜像多维度空间→门禁审计→生产写入
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 架构设计

```
    ┌──────────────────────────────────────────────────┐
    │                  pipeline_submit                  │
    │                                                  │
    │  ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
    │  │ Stage 1  │──▶│ Stage 2  │──▶│  Stage 3     │ │
    │  │ 镜像精修  │   │ 分级门禁  │   │ 版本化生产   │ │
    │  │          │   │          │   │              │ │
    │  │ LLM精修   │   │ P0机械   │   │ 原子写入     │ │
    │  │ 循环N轮   │   │ P1质量   │   │ 护照+时间线  │ │
    │  │ 血缘链    │   │ LLM评分  │   │ 版本历史     │ │
    │  └──────────┘   └──────────┘   └──────────────┘ │
    │                                                  │
    │  过闸 → 原子写入生产区 + 护照 + GBT钢印            │
    │  不过 → 隔离区 + 如实报原因                       │
    └──────────────────────────────────────────────────┘
```

## 能力清单

| 能力位 | 说明 |
|---|---|
| `pipeline_submit` | 唯一交付通道：镜像多维度空间→门禁审计→生产写入 |
| `pipeline_versions` | 版本历史+当前指纹 |
| `pipeline_rollback` | 回滚到历史版本（回滚也走审计） |
| `pipeline_status` | 发布/阻断全留痕 |
| `one_key_deploy` | 一指定江山：抓取→镜像→验证→晋升一条命令上线 |
| `deploy_queue` | AI接管部署队列：submit/tick/status（完一个自动下一个） |
| `ghost_guard` | 防复发检测：幽灵目录/备份散件/攻击残留/注册表冲突 |
| `svc_inspect` | 服务巡检：探活已登记端口并落审计（只看不动） |

## 三阶段深化

### Stage 1 · 镜像精修

```python
gbt.run_task("pipeline_submit", {
    "name": "myapp.html",
    "content": "<html>...</html>",
    "refine_rounds": 3   # LLM精修循环：审查→修改→快照→复审
})
```

每轮快照带血缘链（`refined_from`），最多N轮防失控。

### Stage 2 · 分级门禁

| 级别 | 维度 | 说明 |
|---|---|---|
| P0 | 完整性 | 非空、无空文件 |
| P0 | 归属 | 署名完整（开发者：自由的风） |
| P0 | 审计 | 调用链完整 |
| P0 | 策略 | 授权门检查 |
| P1 | 质量 | `review=True`时LLM评分，阈值60 |

JSON平衡扫描 + 净化重试 + 双引擎容灾。

### Stage 3 · 版本化生产

- **原子写入**：`os.replace`（要么全成功，要么全不变）
- **护照**：版本号+血缘+逐文件指纹
- **版本历史**：`.versions/` 历史链
- **回滚**：`pipeline_rollback`（回滚也走审计）

## API参考

### 提交产物

```python
import gbt_allinone as gbt

# 基础提交
result = gbt.run_task("pipeline_submit", {
    "name": "index.html",
    "content": "<html><body>Hello</body></html>"
})
# 返回: {ok, version, passport, gbt_stamp}

# 带LLM精修
result = gbt.run_task("pipeline_submit", {
    "name": "report.md",
    "content": "...",
    "refine_rounds": 2,
    "review": True   # P1质量维度评分
})

# 不通过时
# 返回: {ok: false, stage: "gate", reason: "署名缺失", isolated: "store/quarantine/..."}
```

### 一键部署

```python
# 从GitHub抓取并部署
result = gbt.run_task("one_key_deploy", {
    "source": "github:user/repo",
    "into_global_production": False  # 默认False，只写镜像维度
})
# 实测：todomvc 28957★ 14文件 3秒上线
```

### AI接管部署队列

```python
# 入队
gbt.run_task("deploy_queue", {"op": "submit", "task": {"name": "deploy-app-v2"}})

# 推进（完一个自动下一个）
gbt.run_task("deploy_queue", {"op": "tick"})

# 全景
gbt.run_task("deploy_queue", {"op": "status"})
```

### 防复发检测

```python
result = gbt.run_task("ghost_guard", {})
# 返回: {
#   ok, found: {
#     ghost_dirs: [],      # 幽灵目录
#     backup_scatter: [],  # 备份散件
#     attack_residue: [],  # 攻击残留
#     reg_conflicts: []    # 注册表冲突
#   }
# }
```

### 服务巡检

```python
result = gbt.run_task("svc_inspect", {})
# 返回: {ok, services: [{port, name, alive, ms}], dead: [...]}
```

## 无人值守闭环

```
wf_define（编排）
    → sched_define（定时）
    → sched_tick / run_forever（自动执行）
    → pipeline_submit（生产发布）
    → svc_inspect（巡检留痕）
```

整条链路零人工按钮。

## 安全边界

- 写生产需 `deploy_publish` 授权
- 强制放行需 `deploy_force` 专用钥匙
- 不声明落点（`room=` 或 `into_global_production=`）= 直接拒绝
- 生产零修改：晋升后任何变动 = 漂移 = ghost_guard级报警

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
