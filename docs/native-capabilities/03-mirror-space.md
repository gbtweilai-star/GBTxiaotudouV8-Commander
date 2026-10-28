# 03 · 镜像多维度空间 (`mirror_space`)

> 10 能力位 · 所有假设与架构虚拟的最终归宿 · 生产最后的防线
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 核心理念

> 任何项目要上线，必须先在镜像空间的一个维度里成形、打磨、验证——
> 维度内随便改（假设/推翻/重来，生产永远无感知），跨维晋升才写生产：
> 一次性全量、不修改一次、不污染文件、一步到位。

## 架构设计

```
    ┌──────────────────────────────────────────────┐
    │              镜像多维度空间                    │
    ├──────────────┬──────────────┬────────────────┤
    │  dimension/  │   reality/   │   timelines/   │
    │  (镜像维度)   │  (生产现实)   │   (时间线)     │
    │  随便改       │  唯一真实     │   每次晋升快照  │
    └──────┬───────┴──────┬───────┴───────┬────────┘
           │              │               │
    ┌──────▼──────┐ ┌────▼─────┐ ┌───────▼────────┐
    │ mirror_shape│ │ mirror_  │ │ mirror_rewind  │
    │ mirror_scan │ │ ascend   │ │ (回到过去)      │
    │ mirror_plan │ │ (晋升)   │ └────────────────┘
    │ mirror_sim  │ └────┬─────┘
    │ mirror_parity│     │
    │ mirror_rehearse│   │
    └──────────────┘    │
                        ▼
              ┌─────────────────┐
              │  passports/     │
              │  跨维护照        │
              │  清单+指纹+验证  │
              └─────────────────┘
```

## 能力清单

| 能力位 | 类型 | 授权 | 说明 |
|---|---|---|---|
| `mirror_shape` | 写 | filesystem_write | 维度成形（写镜像维度——可反复、可覆盖、不设限） |
| `mirror_scan` | 只读 | 无需 | 维度体检（完整性/署名/纪律/入口——跨维晋升前置） |
| `mirror_plan` | 写 | filesystem_write | 生产前排练计划（假设/架构/步骤/验收/回滚） |
| `mirror_simulate` | 写 | filesystem_write | 静态推演（文件/依赖图/端口/入口/契约/闭环，不碰生产） |
| `mirror_parity` | 写 | filesystem_write | 沙盒与生产环境契约一致性（平台/Python/依赖/工具/密钥/路径） |
| `mirror_rehearse` | 写 | process_execute+filesystem_write | 生产前排练（静态推演→环境一致性→沙盒闭环→指纹绑定报告） |
| `mirror_release` | 写 | deploy_publish | 排练全绿后一次性全量晋升生产（树/计划指纹绑定） |
| `mirror_ascend` | 写 | deploy_publish | 跨维晋升（验证全绿才放行；一次性全量写入现实+护照+时间线） |
| `mirror_status` | 只读 | 无需 | 维度状态（镜像/现实指纹、现实漂移检测、时间线史） |
| `mirror_rewind` | 写 | deploy_publish | 时间线回滚（回到过去的时间线，同样一次性全量替换） |

## 目录结构

```
store/mirror_space/
├── dimension/          # 镜像维度（随便改）
│   ├── index.html
│   ├── main.py
│   └── ...
├── reality/            # 生产现实（唯一真实，只经晋升写入）
│   ├── index.html
│   ├── main.py
│   └── ...
├── timelines/          # 时间线（每次晋升的全量快照）
│   ├── 20261028-065700/
│   ├── 20261027-120000/
│   └── ...
└── passports/          # 跨维护照
    └── 20261028-065700.json
```

## API参考

### 维度成形

```python
import gbt_allinone as gbt

# 写入镜像维度（文本文件）
gbt.run_task("mirror_shape", {
    "path": "index.html",
    "content": "<html>...</html>"
})

# 写入二进制文件（逐字节落盘）
gbt.run_task("mirror_shape", {
    "path": "logo.png",
    "bytes_b64": "<base64编码>"
})
```

### 维度体检

```python
result = gbt.run_task("mirror_scan", {})
# 返回: {
#   ok, checks: {
#     completeness: {ok, missing_files: [], empty_files: []},
#     signature: {ok, unsigned: []},
#     discipline: {ok, violations: []},
#     entry: {ok, has_index, has_main}
#   }
# }
```

### 跨维晋升

```python
# 全量晋升（验证全绿才放行）
result = gbt.run_task("mirror_ascend", {})
# 返回: {
#   ok, passport: {version, files: {path: {sha, size}}, timeline_entry},
#   files_written: 42
# }
```

### 时间线回滚

```python
# 回到指定时间线
result = gbt.run_task("mirror_rewind", {
    "timeline": "20261027-120000"
})
```

### 现实漂移检测

```python
result = gbt.run_task("mirror_status", {})
# 返回: {
#   ok, mirror_fingerprint, reality_fingerprint,
#   drift: false/true,  # 生产区有没有被改过
#   timeline_count: 15
# }
```

## 验证矩阵（跨维晋升前置）

| 维度 | 检查项 | 说明 |
|---|---|---|
| 完整性 | 非空 | 空目录/空文件 |
| 完整性 | 无残留 | `_*.py` / `.tmp` / `__pycache__` |
| 完整性 | 有入口 | `index.html` / `main.py` / `app.py` / `start.ps1` |
| 署名 | 文本页携带 | `.md`/`.html`/`.htm`/`.txt`/`.csv` 自动注入 |
| 纪律 | 无越界 | 文件不在错误目录 |
| 纪律 | 无空壳 | 有文件名但内容为空 |

## 生产面红线

1. **生产只收成品**：所有假设/模拟/推演在镜像维度跑，生产零修改
2. **门只有一处**：写生产/镜像的动作一律走`run_task`，禁止直接调模块函数
3. **二进制逐字节落盘**：PNG/GLB/字体当文本读写=废物
4. **现实漂移=报警**：晋升后生产区任何变动=ghost_guard级报警

## v2 深化（三阶段）

### Stage 1 镜像精修
`refine_rounds=N` 开启LLM精修循环：审查→修改→快照→复审，每轮快照带血缘链

### Stage 2 分级门禁
- **P0机械维度**：完整/归属/审计/策略（恒开毫秒级）
- **P1质量维度**：`review=True` 开启LLM评分，阈值60

### Stage 3 版本化生产
原子写入（`os.replace`）+ 护照（版本号+血缘）+ `.versions/` 历史链 + `pipeline_rollback` 回滚

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
