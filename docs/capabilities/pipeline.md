# 流水线与发布 · `pipeline`（18 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `deploy_queue` | 只读 | 是 | `target` | `user_error` | AI 接管部署队列：submit 入队 / tick 部署下一个（完一个自动下一个）/ status 全景 |
| `ghost_guard` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 防复发检测：幽灵目录/备份散件/攻击残留/注册表冲突扫描 |
| `mirror_ascend` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：跨维晋升（验证全绿才放行；一次性全量写入现实+护照+时间线；现实零修改） |
| `mirror_parity` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：沙盒与生产环境契约一致性（平台/Python/依赖/工具/密钥存在性/路径） |
| `mirror_plan` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：生产前排练计划（假设/架构/步骤/服务与环境契约/验收/回滚） |
| `mirror_rehearse` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：生产前排练（静态推演→环境一致性→沙盒闭环→指纹绑定报告） |
| `mirror_release` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：排练全绿后一次性全量晋升生产（树/计划指纹绑定，失败即阻断） |
| `mirror_rewind` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：时间线回滚（回到过去的时间线，同样一次性全量替换） |
| `mirror_scan` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：维度体检（完整性/署名/纪律/入口——跨维晋升前置） |
| `mirror_shape` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：维度成形（假设/架构虚拟/反复打磨全在镜像维度，现实无感知） |
| `mirror_simulate` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：静态推演（文件/依赖图/端口/入口/契约/闭环定义，不碰生产） |
| `mirror_status` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 镜像空间：维度状态（镜像/现实指纹、现实漂移检测、时间线史） |
| `one_key_deploy` | 只读 | 是 | `target` | `user_error` | 一指定江山乾坤换位：抓取(GitHub/本地)→镜像→验证→晋升一条命令，一次性上线零修改 |
| `pipeline_rollback` | 只读 | 是 | `name` | `user_error` | 生产管线：回滚产物到历史版本（回滚也走审计留痕） |
| `pipeline_status` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 生产管线：查发布记录（发布/阻断全留痕） |
| `pipeline_submit` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 生产管线：镜像多维度空间→门禁审计→生产写入（唯一交付通道） |
| `pipeline_versions` | 只读 | 是 | `name` | `user_error` | 生产管线：产物版本历史与当前指纹（.versions/ 链） |
| `svc_inspect` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 服务巡检：探活已登记服务端口并落审计（只看不动） |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `deploy_queue`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 仅 op=submit 需要：要入队的项目路径/URL
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`target` —— 仅 op=submit 需要：要入队的项目路径/URL
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`target`）
- **它做什么**：AI 接管部署队列：submit 入队 / tick 部署下一个（完一个自动下一个）/ status 全景
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap deploy_queue '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `ghost_guard`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：防复发检测：幽灵目录/备份散件/攻击残留/注册表冲突扫描
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap ghost_guard '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_ascend`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`deploy_publish`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：跨维晋升（验证全绿才放行；一次性全量写入现实+护照+时间线；现实零修改）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_ascend '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_parity`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`filesystem_write`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：沙盒与生产环境契约一致性（平台/Python/依赖/工具/密钥存在性/路径）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_parity '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_plan`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：生产前排练计划（假设/架构/步骤/服务与环境契约/验收/回滚）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_plan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_rehearse`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`process_execute`、`filesystem_write`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：生产前排练（静态推演→环境一致性→沙盒闭环→指纹绑定报告）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_rehearse '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_release`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`deploy_publish`、`process_execute`、`filesystem_write`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：排练全绿后一次性全量晋升生产（树/计划指纹绑定，失败即阻断）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_release '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_rewind`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`deploy_publish`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：时间线回滚（回到过去的时间线，同样一次性全量替换）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_rewind '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_scan`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：维度体检（完整性/署名/纪律/入口——跨维晋升前置）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_scan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_shape`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：维度成形（假设/架构虚拟/反复打磨全在镜像维度，现实无感知）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_shape '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_simulate`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`filesystem_write`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：静态推演（文件/依赖图/端口/入口/契约/闭环定义，不碰生产）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_simulate '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `mirror_status`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：镜像空间：维度状态（镜像/现实指纹、现实漂移检测、时间线史）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap mirror_status '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `one_key_deploy`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— GitHub 仓库/子目录 URL 或本地目录路径；且必须显式声明落点 room="<房间名>" 或 into_global_production=true
- **要哪张票（静态）**：`deploy_publish`、`process_execute`、`filesystem_write`
- **必填载荷**：`target` —— GitHub 仓库/子目录 URL 或本地目录路径；且必须显式声明落点 room="<房间名>" 或 into_global_production=true
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`target`）
- **它做什么**：一指定江山乾坤换位：抓取(GitHub/本地)→镜像→验证→晋升一条命令，一次性上线零修改
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap one_key_deploy '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `pipeline_rollback`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 产物名（可选 to_version）
- **要哪张票（静态）**：`deploy_publish`
- **必填载荷**：`name` —— 产物名（可选 to_version）
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`name`）
- **它做什么**：生产管线：回滚产物到历史版本（回滚也走审计留痕）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap pipeline_rollback '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `pipeline_status`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：生产管线：查发布记录（发布/阻断全留痕）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap pipeline_status '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `pipeline_submit`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`deploy_publish`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：生产管线：镜像多维度空间→门禁审计→生产写入（唯一交付通道）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap pipeline_submit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `pipeline_versions`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 产物名
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`name` —— 产物名
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`name`）
- **它做什么**：生产管线：产物版本历史与当前指纹（.versions/ 链）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap pipeline_versions '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `svc_inspect`

- **域**：`pipeline`（流水线与发布）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：服务巡检：探活已登记服务端口并落审计（只看不动）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap svc_inspect '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
