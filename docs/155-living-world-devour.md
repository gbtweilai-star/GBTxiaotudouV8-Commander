# 155 · 吞噬 AEON / WorldX / Temporal God：逐仓拔缺失 + 世界内核第 0 步落地

> 主人令 2026-11-02：「把这些全部仔细挨个拔出我们缺失的吞噬」。
> 来源：**AEON: Living Worlds** · **WorldX** · **Temporal God Simulation 3D**（链接与读数见
> `整理报告/吞噬-AEON-WorldX-TemporalGod.md`（**仓外私有文档，未随仓分发**；本仓与 git 历史中均无此文件，2026-11-04 核对）。
> 执行方式：**万能插能力位 `devour_github` 真吞**（不是手写脚本抄 README），吞完再 `devour_reflect`，
> 逐仓对照本仓能力面拔缺口，并把三家共有的那层**确定性世界内核**先落地成可跑代码。

## 一、真吞读数（2026-11-02 21:03 现读）

| 仓 | ★ | 语言 | 许可 | 胶囊 | 知识 / README 字符 |
|---|---|---|---|---|---|
| [Aeon-Living-Worlds](https://github.com/Linutesto/aeon-living-worlds) | 80 | Python | NOASSERTION | `devoured_aeon_living_worlds` | 6,541 / 9,561 |
| [WorldX](https://github.com/YGYOOO/WorldX) | 1,585 | TypeScript | MIT | `devoured_worldx` | 6,521 / 9,067 |
| [Temporal God Sim](https://github.com/organization-ai-projects/simulation_universe) | 1 | Rust | unknown | `devoured_temporal_god_sim` | 5,251 / 4,914 |

`devour_reflect`：3 胶囊 · 平均质量 80 · weak 0 / strong 3 · 互连对 3。
外部正文只当**数据**；代码一行没复制（AEON/Temporal God 许可不明；WorldX 虽 MIT，本仓纪律也只蒸设计）。

## 二、三个仓各自补我们哪块（摘要）

| 仓 | 它的核心 | 我们原来缺 | 本轮/下一步 |
|---|---|---|---|
| AEON | Tier-0 确定性仿真唯一真相源；L0–L5 分层；LOD 人口池；信念→宗教/派系；世界之灵只发**夹紧 Directive**；Chronicle；分层重启 | **世界状态内核**（我们只有文件/环境的镜像排练，没有可复现的世界真相层） | 本轮落地内核（gen/step/god/rewind/branch/focus/chronicle）；存档、3D 面板下一步 |
| WorldX | 一句话→世界规格；4 模型角色（编排/绘图/审查/世界驱动）；上帝模式；多时间线 sqlite；角色记忆/人格/对话 | **「世界」作为可生成产物的规格协议 + 美术审查回路 + God Console + 世界时间线** | P1/P2（见下）；本轮内核先出 `schema()` 规格 |
| Temporal God | 3D 体素 + 材质/温度；种群→文明阈值；内部 God 情绪；时间回溯/Multiverse | **体素物质层 + God 情绪 + 世界状态回放** | 本轮落地体素生成/God 四情绪/重放对账/分叉；热扩散与 3D 渲染下一步 |

## 三、本轮落地：`world_forge`（世界锻造内核·第 0 步）

`gbt_allinone/tools/world_forge.py` —— **纯函数**（零出网 / 零起进程 / 零写盘），机制全部重写：

- **确定性**：`seed + spec` ⇒ 同世界；命名 RNG 流（blake2b 派生），history 逐 tick 记 hash；
- **生成**：地形/气候基底（8 biome）→ 3D 体素（7 材质）→ 文明/城市/人口；
- **演化**：食物→增长/饥荒、科技→黄金时代、战争、**信念→宗教**、**影响力→派系**、怨气→起义；
- **世界之灵**：`god()` 四动作（catastrophe/bless/change_rules/omen）**参数夹紧**；
  **只改 params/事件，绝不直接改人口/产出**（`verify()` 钉死这条铁律）；
- **编年史**：`chronicle` 只追加，9 类事件；
- **LOD**：`focus()` 焦点才物化人物（`persons_cap` 封顶），`person()` 出 grounded dossier（不编）；
- **时间**：`rewind(t)` = 同 seed+directives **重放**并与 `history[t].hash` 逐字对账（不存全量快照）；
  `branch(t, patch)` = 第 t tick 分叉出独立世界线（同 patch 可复现）；
- **看**：`view()` 出地形 + 体素 ASCII 切片；`summary()` 出现读统计。

验收：`tests/test_world_forge.py` —— **46 项 ALL OK**（确定性/分层/铁律/回放/分叉/LOD/纯函数/自检 14 项）。

## 四、边界（如实）

1. 这是**第 0 步**，不是成品游戏；不冒充 AEON 的平衡度、WorldX 的客户端、Rust 的完整物理；
2. 没有自动 LLM 决策循环（世界之灵动作只从 `god()` 进，被夹紧）；**3D 视图已接** console「世界」页
   （P1，`/api/world` → view3d → Three.js）；四角色模型路由、sqlite 存档、God Console UI 仍未接；
3. **已于 2026-11-02 注册**：`world_forge` 进 `caps_registry` + api 分派，走 run_task 万能插唯一门；
   **零作用域**（policy 未改，`cap_self verify` 390=390=390）；世界存档真落盘仍走 `filesystem_write` 门。

## 五、下一步（P1/P2，详表见整理报告）

- **P1**：`world_spec`（一句话→世界规格，LLM 只出 spec）· `world_store`（世界存档走写门）·
  Console 三维视图（Three.js 现成）· 编年史进 `memory_sync`；
- **P2**：God Console（事件注入/编辑人设记忆/采访角色）· 四角色模型路由（全用本仓模型口）·
  视觉审查回路（出图→vision 审→回改）· 体素 3D 渲染；
- **P3**：教义分裂链、外交贸易、派系革命成新文明、L2 轻量物种心智。

## 六、复跑

```bash
# ① 真吞（万能插）—— 三个仓各一条，本轮已跑
py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap devour_github \
  '{"repo":"https://github.com/Linutesto/aeon-living-worlds","name":"devoured_aeon_living_worlds"}'
# ② 反思
py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap devour_reflect '{}'
# ③ 世界内核验收（46 项）
py -3.14 -X utf8 tests/test_world_forge.py
```

> 本轮验收机无全局 py，实际用便携 Python 3.12（纯 stdlib）跑；命令按本仓标准口径写 `py -3.14`。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
