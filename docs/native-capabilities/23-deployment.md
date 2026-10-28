# 23 · 部署系统 (`deployment`)

> 5+ 能力位 · 一键部署 · AI接管队列 · 服务巡检 · 防复发
>
> 所有假设/架构试验/反复修改全部关在镜像部署区；
> 生产只接受验证通过后的一次性全量晋升——零修改、零污染、一步到位。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单

| 能力位 | 说明 |
|---|---|
| `one_key_deploy` | 抓取(GitHub/本地)→镜像→署名注入→验证矩阵→一次性晋升 |
| `deploy_queue` | AI接管部署队列：submit入队/tick部署下一个/status全景 |
| `svc_inspect` | 服务巡检：探活已登记端口并落审计（只看不动） |
| `ghost_guard` | 防复发检测：幽灵目录/备份散件/攻击残留/注册表冲突 |
| `deployment_rehearsal` | 部署排练 |
| `mirror_*` | 镜像空间五维（见03文档） |

## 一键部署流程

```
    抓取源（GitHub/本地）
         │
    ┌────▼────┐
    │ 镜像维度 │  ← 所有改动在这里
    └────┬────┘
         │
    ┌────▼────┐
    │ 署名注入 │  文本页自动加"开发者：自由的风"
    └────┬────┘
         │
    ┌────▼────┐
    │ 验证矩阵 │  非空/无空文件/有入口/无残留
    └────┬────┘
         │
    ┌────▼────┐
    │ 一次性   │  全量写入 + 护照 + 时间线
    │ 晋升     │
    └─────────┘
```

## API参考

### 一键部署

```python
import gbt_allinone as gbt

# 从GitHub抓取并部署到镜像维度
result = gbt.run_task("one_key_deploy", {
    "source": "github:gothinkster/todomvc",
    "room": "todomvc-test"   # 显式声明落点（只写房间）
})
# 返回: {
#   ok, files: 14, ms: 3000,
#   verified: {completeness: true, signature: true, entry: true},
#   landing: "room:todomvc-test"
# }
```

**实测**：todomvc 28957★ 14文件，**3秒上线**。

### 落点声明（必填）

```python
# ✅ 写法1：只写房间（生产分毫不动）
gbt.run_task("one_key_deploy", {"source": "...", "room": "my-room"})

# ✅ 写法2：写全局生产（必须人工授权）
gbt.run_task("one_key_deploy", {
    "source": "...",
    "into_global_production": True
})

# ❌ 不声明落点 → 直接拒绝
gbt.run_task("one_key_deploy", {"source": "..."})
# 返回: {ok: false, status: "denied", reason: "必须显式声明落点"}
```

### 强制放行（需专用钥匙）

```python
# 终端先发钥匙
# python -m gbt_allinone auth grant --scope deploy_force --ttl 600

# 调用方显式声明
result = gbt.run_task("one_key_deploy", {
    "source": "...",
    "owner_override": True
})
# 返回里 steps.landing_override.route 明示它去了全局生产
# 审计记 one_key_deploy_landing_overridden
```

**纪律**：不声明落点也能放行，**但放行从不静默**。

### AI接管部署队列

```python
# 入队
gbt.run_task("deploy_queue", {
    "op": "submit",
    "task": {"name": "app-v1", "source": "github:user/app"}
})

# 推进（完一个自动下一个）
result = gbt.run_task("deploy_queue", {"op": "tick"})
# 返回: {ok, deployed: "app-v1", next: "app-v2", remaining: 3}

# 全景
result = gbt.run_task("deploy_queue", {"op": "status"})
# 返回: {ok, queue: [{name, status, ms}], done: 2, pending: 3}
```

### 服务巡检

```python
result = gbt.run_task("svc_inspect", {})
# 返回: {
#   ok,
#   services: [
#     {port: 8097, name: "gbt_wallet", alive: true, ms: 12},
#     {port: 3000, name: "web", alive: false, ms: 5000}
#   ],
#   dead: [3000]
# }
```

**并发化**：线程池并发探活，预留端口不等超时。

### 防复发检测

```python
result = gbt.run_task("ghost_guard", {})
# 返回: {
#   ok,
#   found: {
#     ghost_dirs: [],        # 幽灵目录（已删除但注册表还在）
#     backup_scatter: [],    # 备份散件（.bak/.old/.tmp）
#     attack_residue: [],    # 攻击残留（异常进程/文件）
#     reg_conflicts: []      # 注册表冲突
#   },
#   ms: 31
# }
```

**性能**：31ms（定点扫描，不做全仓rglob）。

## 验证矩阵

| 检查项 | 判据 | 不通过 |
|---|---|---|
| 非空 | 有文件 | 阻断 |
| 无空文件 | 所有文件size>0 | 阻断 |
| 无残留 | 无 `_*.py`/`.tmp`/`__pycache__` | 阻断 |
| 有入口 | `index.html`/`main.py`/`app.py`/`start.ps1` | 阻断 |
| 署名 | 文本页携带署名 | 自动注入 |
| 二进制 | 逐字节落盘 | 阻断 |

**缺一项 = 卡住，不许半成品上线。**

## 生产零修改纪律

晋升后生产区任何变动 = **漂移**（对照护照逐文件指纹），`ghost_guard` 级报警。

```python
# 检测漂移
result = gbt.run_task("mirror_status", {})
# 返回: {ok, drift: false}   # true = 生产被改过，立即报警
```

## 二进制必须逐字节

```python
# ✅ 正确：逐字节落盘
gbt.run_task("mirror_shape", {
    "path": "logo.png",
    "bytes_b64": "iVBORw0KGgo..."
})

# ❌ 错误：把PNG当文本读写 → 废物
```

把PNG/GLB/字体当文本读写 = 把镜像里的产物当场弄成废物。

## 无人值守闭环

```
wf_define（编排）
    → sched_define（定时）
    → sched_tick / run_forever（自动执行）
    → pipeline_submit（生产发布）
    → svc_inspect（巡检留痕）
```

整条链路零人工按钮。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
