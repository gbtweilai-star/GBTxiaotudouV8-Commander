# 01 · 系统/数据域 (`system` / `data`)

> 51+ 能力位 · 框架的体检层、声带、自检体系与数据工具
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 架构设计

系统/数据域是框架的**自我认知层**——它让框架知道自己健不健康、哪里有毛病、审计账本记了什么、文件有没有乱放。

```
┌─────────────────────────────────────────────────────┐
│                   系统/数据域                        │
├───────────┬───────────┬───────────┬─────────────────┤
│  体检层    │  审计层    │  卫生层    │  数据工具       │
│ selfscan  │audit_query│file_hygiene│ count_words    │
│  alerts   │ truth_scan │ signature  │ record_grid    │
│ cross_scan│  root_fix  │  _guard    │   echo         │
│ inventory │ readiness  │            │                │
└───────────┴───────────┴───────────┴─────────────────┘
```

## 能力清单

### 体检层

| 能力位 | 类型 | 说明 |
|---|---|---|
| `selfscan` | 只读 | 五维扫描（路由/模块/存储/审计/桩缺口），P0断连第一时间报警，autofix可安全修复 |
| `alerts` | 只读 | 框架声带：近期异常摘要+根源线索（runtime/guard/trace/recovered分级） |
| `cross_scan` | 只读 | 深度穿透式交叉验证（注册↔路由↔导入↔断链↔运行时，十维互证） |
| `inventory` | 只读 | 全息盘点：你的视图+框架的视图（归属四分类：框架/环境/数据/异物） |
| `root_fix` | 只读 | 根治环：症状五问诊断/补丁债量化/根治纪律 |
| `truth_scan` | 只读 | 真实性审计：逐能力验证真执行，零假执行铁律（probe模式含副作用探针） |

### 审计层

| 能力位 | 类型 | 说明 |
|---|---|---|
| `audit_query` | 只读 | 只读查询统一数据后台日志 |
| `readiness` | 只读 | 依赖就绪自检：探测外部后端/密钥是否就位，缺则如实报needs_dependency |
| `auth_gate_status` | 只读 | 人工授权门状态（各作用域可用授权数） |

### 卫生层

| 能力位 | 类型 | 说明 |
|---|---|---|
| `file_hygiene` | 只读 | 按LAYOUT.md家规自检乱放+自动归位（散落/空壳/越界数据/缓存） |
| `signature_guard` | 只读 | 扫描全框架页面开发者署名完整性，缺失可自动补回（禁止删除） |

### 数据工具

| 能力位 | 类型 | 说明 |
|---|---|---|
| `health` | 只读 | 系统健康信息（平台/Python/时间） |
| `echo` | 只读 | 回显传入数据，用于联调 |
| `count_words` | 只读 | 统计文本词数/字数 |
| `record_grid` | 只读 | 行式记录网格：陌生文本结构画像/草案/逐行解析/回写自证/词表校验 |

## API参考

### `selfscan` — 框架五维体检

```python
import gbt_allinone as gbt

# 基础体检（只读）
result = gbt.run_task("selfscan", {})
# 返回: {ok, dims: {routing, modules, storage, audit, stubs}, p0_issues}

# 自动修复缺目录与损坏JSON
result = gbt.run_task("selfscan", {"autofix": True})
# 返回: {ok, dims, fixed: ["mkdir:store/cache", "rewrite:store/config.json"]}
```

**五维说明**：
- **路由完整性**：注册↔路由双向对账，确保每个注册能力都有分派路径
- **模块健康**：检查关键模块是否可导入，有无编码损坏
- **存储健康**：store目录结构完整、JSON文件可解析
- **审计异常**：四级信号分级（runtime要追的病/guard护栏正常/trace测试足迹/recovered历史掉线已恢复）
- **桩缺口**：如实清点UNIMPLEMENTED_CAPS，不冒充已有

### `cross_scan` — 深度穿透式交叉验证

```python
result = gbt.run_task("cross_scan", {"deep": True})
# 返回: {ok, dims: 10, checks: [...], disconnects: [], score}
```

**十维互证**：注册表↔路由分派↔模块导入↔断链检测↔运行时验证↔多扫描器互证

### `truth_scan` — 真实性审计

```python
# 只读验证（无副作用）
result = gbt.run_task("truth_scan", {"mode": "verify"})

# 探针模式（含副作用——真跑一次确认）
result = gbt.run_task("truth_scan", {"mode": "probe", "caps": ["health", "echo"]})
```

**零假执行铁律**：每个能力位必须真执行，返回`{"ok": True}`但什么都没做=假执行=红线

### `alerts` — 框架声带

```python
result = gbt.run_task("alerts", {"limit": 20})
# 返回: {ok, alerts: [{cap, level, msg, source, at}]}
# level: runtime(要追的病) / guard(护栏正常) / trace(测试足迹) / recovered(已恢复)
```

## 安全边界

- 全部只读，不修改状态、不出网
- `autofix=True` 的selfscan只修复缺目录和损坏JSON，不改代码
- `truth_scan`的probe模式有副作用（真跑一次），但不改变持久状态

## 性能基线

| 能力 | 冷启动 | 热路径 | 说明 |
|---|---|---|---|
| `health` | ~160ms | <1ms | 含解释器+框架加载 |
| `selfscan` | ~175ms | ~175ms | 进程内缓存后 |
| `cross_scan(deep=True)` | ~2s | ~2s | 全框架穿透 |
| `alerts` | ~50ms | ~50ms | 近期异常聚合 |

## 实现原理

### 审计后台（store.py）

追加式JSONL日志，每次调用记录`call → ok/error/denied`全链：

```python
# 审计记录格式（每行一条JSON）
{"event":"call","cap":"selfscan","at":"2026-10-28T06:56:53","caller":"main"}
{"event":"ok","cap":"selfscan","at":"2026-10-28T06:56:53","ms":175,"dims":5}
```

**并发安全**：进程内所有写入持同一把锁（`_audit_lock`），保证JSONL每行完整。160路并发实测1694行零损坏。

**脱敏**：写入前统一脱敏（`security/data_policy.sanitize_for_audit`），凭证掩码、对话类内容只留指纹。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
