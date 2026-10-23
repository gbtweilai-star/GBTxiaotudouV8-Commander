# LAYOUT.md — GBT小土豆V8 的文件家规（她自己的排布秩序）

> 本文件是框架的文件组织宪法。所有代码、数据、产物、文档必须按此排布。
> `file_hygiene` 能力按本规则自检并自动归位。乱放 = 缺陷，和代码 bug 同级。

## 一、家的边界

```
GBT小土豆V8/                ← 独立的家（与其他项目物理隔离，绝不混居）
├── README.md               ← 家的名片：身份声明 + 快速验证
├── requirements.txt        ← 依赖清单
└── gbt_allinone/           ← 框架本体（唯一代码根）
```

## 二、包内排布（每样东西有唯一的位置）

### 定位声明（先于一切排布规则）
**GBT-V8 是单纯的全能 AI 框架。** 框架源码只收 AI 能力本体（推理/执行/感知/安全/工程层）；
任何具体业务领域模块（资金/钱包/支付/交易所等）不属于框架本体——它们有自己的家
（如资金模块归 `Workspace/03_收款钱包与支付/`），需要时通过 adapters 优雅降级接入，
**实体模块永不入库**。新增任何模块前先问：这是每个 AI 框架都该有的通用能力，还是某个具体业务？
前者入库，后者归家。

### 代码（按职责分层）
| 位置 | 放什么 | 例子 |
|---|---|---|
| 包根 `*.py` | 核心层：统一接口与横切能力 | api.py, engine.py, store.py, soul.py |
| `recon/` | 自有 OSINT 侦察核心 | scanner.py, guard.py |
| `llm/` | 大脑：LLM 桥与云引擎 | bridge.py, cloud_llm.py |
| `tentacle/` | 触手：眼睛/双手/契约 | bridge.py, mcp_bridge.py, omni_* |
| `security/` | 黑客大脑（红蓝双模） | security_brain.py, abl_gateway.py |
| `adapters/`, `integration/` | 外界接轨层（可缺省；业务模块只在此留优雅降级占位，实体不入库） | workspace_adapter.py |
| `tests/` | 回归测试（60 项，动代码必跑） | test_framework.py |

> 注：`ledger/`、`wallet/`、`bridge/` 曾在此列——2026-09-13 起“纯全能 AI 框架”定位落地，
> 资金模块整体迁出归家（Workspace/03_收款钱包与支付/），框架内仅保留 api.py 的降级占位路由。

### 数据（一律进 store/，代码目录零数据）
| 位置 | 放什么 |
|---|---|
| `store/audit.jsonl` | 审计日志（唯一追加通道 store.audit） |
| `store/devoured/` | 吞天产物（知识胶囊/杂交/创新骨架） |
| `store/pipeline/` | 镜像管线三区（mirror/gate 判定/production） |
| `store/wf_runs/`, `workflows.json`, `tasks.json`, `schedules.json` | 引擎运行记录与定义 |
| `store/polish_insights.json` | 打磨领悟集（框架资产） |
| `store/pit_log.json` | 坑册（踩过的坑/根源/教训/防复发锁——开工先查，一坑不踩两次） |
| `store/work_log.jsonl` | 工作日志（开工/收工/教训；收工自动带债值快照，成长可回放） |
| `store/dc_remote.log`, `dc_remote.pid` | 桌面指挥官 remote 设备的运行日志与进程号（触手远程形态） |
| `store/mirror_space/` | 镜像多维度空间（dimension/reality/timelines/passports + 部署队列） |

### 文档（少量、各有其位）
| 位置 | 放什么 |
|---|---|
| 包根 `README.md` / `SOUL.md` / `CODING_DISCIPLINE.md` | 身份、灵魂、编码纪律（仅此三份在包根） |
| `docs/` | 专题深档（架构/验收） |
| `deploy/` | 部署脚本与配置 |
| `examples/` | 可运行示例 |
| `archived_logs/` | 历史归档（只增不删，审计轮转也进这里） |

## 三、铁律（file_hygiene 按 此判定乱放）

1. **零游离**：包内任何文件必须属于上表某个位置；顶层（家根）只允许框架三件（README/requirements/gbt_allinone）+ OpenClaw 运行环境文件（AGENTS/SOUL/MEMORY 等桌面端工作区配置，见 hygiene.HOME_ALLOWED 白名单）。
2. **零临时残留**：`_*.py`、`_patch*.py`、`*.tmp`、`_test*` 等工作脚本用完即删；发现的临时脚本属"散落"级问题。
3. **零缓存入库**：`__pycache__/` 是运行时产物，出现即清（不构成缺陷但每次 hygiene 顺带清掉）。
4. **空壳目录**：只含 `.gbt_dir_marker` 而无实文件的目录是残骸，直接清（真身应在 store/devoured/）。
5. **数据不越界**：代码目录里出现 `.jsonl`/`.json` 数据文件（非配置）即乱放——数据一律进 store/。
6. ** `.deploy_bak`/备份散件**：由 ghost_guard 定点扫，出现即报。
7. **归档有去向**：轮转/封存的旧数据一律进 `archived_logs/<日期-事由>/`，不散落。
8. **能力名与文件不必一一对应，但域（domain）必须落在对应目录**：新增能力时 handler 所在模块按上表选位。
9. **源码入库边界（纯全能 AI 框架铁律）**：框架源码只收 AI 能力本体。资金/钱包/支付等具体业务模块不属于框架——检测到实体模块存在（如 wallet/ ledger/ bridge/ 非空目录）即报 `foreign_module`。业务模块有自己的家（资金归 Workspace/03_收款钱包与支付/），框架内只允许 api.py 优雅降级占位。新增模块前的判定问题：“这是每个 AI 框架都该有的通用能力，还是某个具体业务？”
10. **一份源，多处装**：自有技能的**唯一真相是仓内 `skills/`**；技能枢纽（`~/.agents/skills/`）那份是**派生物**，不许手工改 —— 改完必须 `python tools/skills_sync.py sync`。`源 ≠ 装` 判红（`test_skills_install_sync`，已挂开机自检）。
11. **同源镜像逐字节相等**：同一份内容不许两处各写一份。确实需要镜像时（如根 `LAYOUT.md` ↔ `gbt_allinone/LAYOUT.md`），镜像与源必须**字节一致**并由判据盯着；否则它就是下一处分叉。
12. **大件不入库**：入库媒体判据 **≤3MB**（小样片/证据件）；成片与生成中间件不进版本库——**清单、验收结论、小样片进库**。理由不是"省地方"：实测最大一个 232.1MB，已超 GitHub 单文件 100MB 硬上限，不挡整个 push 物理失败。
13. **别人的家不进仓**：别的 AI 工具的本机状态目录（`.claude/` `.autohand/` `.codebuddy/` `.aider-desk/` `.augment/` `.windsurf/` `.dsh/` `.mimosa/` `.v2c/` `.video_agent/`）一律挡在索引外——它们里面的 `skills/` 只是**指向 `.agents/skills/` 的符号链接农场**，不是第二份源。

## 四、工作区级排布（源 · 装 · 缓存，三类分清）

> 上面管**包内**，这一节管**包外的工作区**（仓根 / 技能枢纽 / 产物区）。
> 2026-09-27 主人令「把整个框架的源代码保护好、整理摆放好，别搞得到处都是又分路分叉」后立。

### 4.1 三分法（每样东西只属于一类）

| 类别 | 判据 | 成员 | 纪律 |
|---|---|---|---|
| **源**（唯一真相） | 进 git · 有历史 · 可复核 | `gbt_allinone/` `tools/` `skills/` `docs/` `state/` `projects/`（清单与脚本） | 只改这里；改完让「装」跟上 |
| **装**（派生物） | 由源派生 · 可随时重建 | `~/.agents/skills/<名>/`（自有技能）· `.agents/skills/<名>/`（第三方技能） | **不许手工改**；改完跑 `tools/skills_sync.py sync` |
| **缓存/外部**（不入史） | 可重建或无授权 | `.scratch/` `.trash/` `.backups/` `.mimosa/` `vendor/` `_upstream/` `dist/` `my-project/` `审美相关skill/` | 挡在索引外；**真身留盘上** |

### 4.2 技能：一份源、多处装

- **唯一真相是仓内 `skills/`**，枢纽那份是派生。实测（2026-09-27）：65 个 `gbt-*` 里
  **10 个分叉 · 8 个从未安装**；`gbt-security` 源 43K / 装 31K，差 1054 行——
  即「改在盘上」没变成「改在运行时」（**F18 同型**）。
- 对账：`python tools/skills_sync.py check`（有分叉退出码非零）；
  判据 `gbt_allinone.tests.test_skills_install_sync`（已挂开机自检）。
- 覆盖前**先备份**到 `.backups/skills-hub/<时间戳>/`：**覆盖 ≠ 毁掉**。

### 4.3 大件不入库（判据是量出来的）

- 已入库的 18 个 mp4 **全部 ≤2.9MB**（小样片/证据件）；最大的未入库成片 **232.1MB**。
- ⇒ `projects/**/成片/*.mp4` 与 `projects/**/生成/` 不进版本库；**清单与验收结论进**。

### 4.4 别人的家不进仓

别的 AI 工具的本机状态目录一律挡在索引外。它们的 `skills/` 是指向 `.agents/skills/` 的
**符号链接农场**（实测每条 `-> <仓>/.agents/skills/<名>/`），不是第二份源。

## 五、自检命令

```powershell
# 她自己的整理能力（体检 + 自动归位 + 审计留痕）
python -c "import sys; sys.path.insert(0,'.'); import gbt_allinone as g; g.run_task('file_hygiene', {})"
# 深扫（含幽灵目录/备份散件/攻击残留）
g.run_task('ghost_guard', {})
# 技能源 ↔ 装 对账（分叉即红；修法：tools/skills_sync.py sync）
python tools/skills_sync.py check
```

> 家规修订需同步更新 file_hygiene 的判定规则，两者永远一致。
> **两份 `LAYOUT.md`（根 ↔ 包内）必须逐字节相同**，由 `test_skills_install_sync` 的镜像判据盯着。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
