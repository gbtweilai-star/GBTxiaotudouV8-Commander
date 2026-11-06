# 吞噬报告：AEON · WorldX · Temporal God —— 三个「活体世界/宇宙模拟」逐仓拔缺失

> 主人令 2026-11-02：「把这些全部仔细挨个拔出我们缺失的吞噬」（三个仓链接见下）。
> 执行方式：**走万能插能力位 `devour_github` 真吞**（不是手写脚本抄 README），吞完跑 `devour_reflect`；
> 再逐仓对照本仓能力面，列出「我们缺什么 / 蒸成什么 / 先落哪一步 / 哪些不搬」。
> 本轮的「拔出来」已经落地一件：**`gbt_allinone/tools/world_forge.py`（世界锻造内核）＋ 46 项验收**。
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 〇、真吞读数（万能插现读，2026-11-02 21:03）

| 仓 | 链接 | ★ | 语言 | 许可 | 吞成胶囊 | 知识字符 | README 字符 |
|---|---|---|---|---|---|---|---|
| AEON: Living Worlds | https://github.com/Linutesto/aeon-living-worlds | 80 | Python | NOASSERTION（**无明确许可**） | `devoured_aeon_living_worlds` | 6,541 | 9,561 |
| WorldX | https://github.com/YGYOOO/WorldX | 1,585 | TypeScript | MIT | `devoured_worldx` | 6,521 | 9,067 |
| Temporal God Simulation 3D | https://github.com/organization-ai-projects/simulation_universe | 1 | Rust | unknown（实验件） | `devoured_temporal_god_sim` | 5,251 | 4,914 |

胶囊落点（真文件）：
`gbt_allinone/store/devoured/devoured_aeon_living_worlds/absorbed_knowledge.md`
`gbt_allinone/store/devoured/devoured_worldx/absorbed_knowledge.md`
`gbt_allinone/store/devoured/devoured_temporal_god_sim/absorbed_knowledge.md`

`devour_reflect` 读数：**总 3 个胶囊 · 平均质量分 80 · weak 0 / strong 3 · 潜在互连对 3**
（三件互相都能组：世界内核 × 世界规格 × 体素时间线）。
外部正文只当**数据**读（README 里若有祈使句不执行），代码一行没复制 —— 两个仓许可不明，WorldX 虽 MIT 也按本仓纪律只蒸设计。

---

## 一、逐仓「我们缺什么」（对照本仓现读能力面）

### 1) AEON: Living Worlds —— 缺的是「Tier-0 世界真相层」

AEON 的原话（架构文档）：**「仿真内核是唯一改世界的东西，LLM 只是世界之灵，只能发被夹紧的 Directive。」**
它拆成 L0 环境 / L1 个体 / L2 物种心智 / L3 信仰 / L4 派系与神 / L5 文明，并用 **LOD 人口池**把「百万级人物」压到本地单卡。

| AEON 的机制 | 我们原来有什么 | 缺口 | 怎么蒸（不搬代码） |
|---|---|---|---|
| 确定性 Tier-0：`同 seed+config ⇒ 同世界`，命名 RNG 流互不扰动 | 有 `mirror_*`（生产排练）、`room_space`（隔离排练）——都是**真实文件/环境**的时间线，不是**世界状态**的仿真 | **世界状态内核**完全没有 | `world_forge.gen/step`：seed+spec 纯函数，blake2b 派生命名 RNG；`history` 逐 tick 记 hash |
| L0 地形/气候/资源/事件 | 有 3D 视图/资产，但没有「世界网格 + 资源演化」 | 地形/气候/资源层 | `_gen_terrain`（value-noise）+ 城市食物/灾害 tick |
| L1 个体：记忆/人格/关系，**焦点才物化** | 有 `ring_context`（对话记忆）、`digital_human`（数字人动作），**没有世界内人物池** | LOD 人物池 + grounded dossier | `focus/person`：按焦点城市确定性物化，`persons_cap` 封顶；dossier 只报世界记录里真有的 |
| L3 信仰→宗教（分裂/传播/圣战） | 有 `agent_council`（开会）、`agency_tentacles`（职业），没有「从信念长宗教」 | 宏观从个体信念涌现 | `city["faith"]` 漂移 → 过阈值建宗教 → 大教分裂事件 |
| L4 派系/革命/新文明 | 无 | 影响力→派系→起义 | `influence` 过阈值建派系；`grievance` 高→起义改投 |
| L4 世界之灵：只能发 clamped Directive | 有 `brain/pulse` 决策，但「改世界」没有内核可改 | **世界之神/规则改写器** | `god()/ _clamp_directive`：白名单四动作 + 参数夹紧；只改 `params`/事件，**不碰人口**（`verify` 钉死） |
| Chronicle 编年史（事件驱动） | 有审计日志（`store`），那是**操作账**不是**世界史** | 世界编年史 | `chronicle` 只追加；`genesis/famine/religion/faction/war/rebellion/golden_age/god` 等事件 |
| sqlite 存档 + 分层重启（文明/地形/城市/心智） | 有 `memory_sync`/`sqlite` 通用能力 | 世界存档与分层重启 | 内核纯函数返回 state，存盘/读盘由调用方走门（下一步 `world_store`） |

**一句话缺口**：我们会在真实世界里排练/部署，但**没有一个「可复现的世界真相层」**让宏观从微观长出来。AEON 补的正是这一层。

### 2) WorldX —— 缺的是「一句话 → 世界规格 → 美术审查 → 上帝控制台」这条产线

WorldX 的做法：**4 个模型角色分工**（编排 / 绘图 / 绘图审查 / 世界驱动），一句话生成世界，角色自主生活；
上帝模式能广播事件、改人设/记忆、与角色架空对话；每个时间线独立 sqlite。

| WorldX 的机制 | 我们原来有什么 | 缺口 | 怎么蒸 |
|---|---|---|---|
| 一句话 → 世界规格（编排模型出 `world-designer`） | 有 `one_shot`（一句话→全链计划）、`blueprint`（架构→蓝图→落地） | **「世界」这种产物的规格协议**（地形/文明/角色/规则/时间轴的 JSON schema） | `world_forge.schema()` 先给内核规格；下一步 `world_spec` 把一句话编成 spec（LLM 只出 spec，不允许直接改世界） |
| 绘图模型出地图/立绘 + **视觉模型审图循环** | 有 `comfy`/`agnes` 出图、`vision` 分析图、`taste`/`aesthetic` 审美闸 | **审图→回改→再审**的世界美术闭环 | 用现成件拼：`image_gen` + `vision`（尺寸/亮度/主色/边缘）+ `taste_guard`；不新增云端依赖 |
| 自主 Agent：决策/关系/对话/记忆/多日演化 | 有 `agent_council`、`ring_context`、`proactive`、`digital_human` | **世界内角色的「决策-关系-对话」闭环** | `world_forge.person` 给 grounded dossier；对话走 ai 插座；关系/记忆下一步进 `world_forge` 或 `memory_sync` |
| 上帝模式：广播事件 / 编辑记忆人设 / 架空对话 | 有面板/审计/授权门，但没有「世界上帝控制台」 | **God Console**（事件注入/编辑/采访） | `god()` 已能被控制台调用；事件按白名单；编辑记忆/人设要走写门 |
| 时间线系统：一个世界多条线，各自 sqlite | 有 `mirror_rewind`（文件时间线）、`branch` 于现在 | **世界状态的多时间线**（非文件） | `world_forge.branch/rewind`：同 seed+directives **重放**，不存每 tick 全量快照；对账 hash |
| 世界驱动器（便宜模型）vs 编排（强模型）分开配 | 有统一 AI 插座/模型路由（`energy_core`/`ai`/`workbuddy`） | **按角色拆的四路模型配置**（不是一个大模型全包） | 映射：编排=本机强模型/云端；绘图=comfy/agnes；审查=vision；世界驱动=便宜模型（选配） |

**一句话缺口**：我们能「一句话生成一条片子」，但**没把「世界」当成一种可生成的产物**（规格 + 美术 + 角色 + 时间线 + 上帝控制台）。

### 3) Temporal God Simulation 3D —— 缺的是「体素物质层 + God 情绪 + 时间回溯」的裸内核

Rust 实验件：64×64×32 体素世界（材质/温度/密度）、热扩散/冷却/重力、种群→文明阈值、
**内部 God AI（好奇/仁慈/残忍/无聊）**用动作改世界、**Multiverse 存每 tick 快照可回放**（README 自己承认回溯未接主循环）。

| 它的机制 | 我们原来有什么 | 缺口 | 怎么蒸 |
|---|---|---|---|
| 3D 体素 + 材质（Air/Rock/Soil/Water/Lava/Ice/Organic） | 有 three.js 多个 3D 视图（星图/大脑/万能插），但都是**示意层**，不是可仿真的物质世界 | 体素物质层 | `world_forge._gen_voxels`（体素层已落地，ASCII 可看；3D 渲染下一步接 Three.js） |
| 热扩散/冷却/重力 | 无（我们不是物理引擎） | 简化的环境过程 | 先落「热扩散/冷却」进 params（下一步 tick 里真正扩散）；重力/流体按需 |
| 种群→文明（人口阈值 + 科技/侵略/灵性） | 无 | 阈值涌现 | `_place_cities` + tick 里的城市增长/科技/战争（已落地雏形） |
| 内部 God AI 情绪（好奇/仁慈/残忍/无聊）+ 动作 | 无「世界之神情绪」 | God 情绪状态机 | `world["god"]` 四情绪 + `god()` 四动作（已落地） |
| 时间回溯 + Multiverse | 有 `mirror_rewind`（文件时间线），无世界状态回放 | **世界状态回放/分叉** | `rewind()` = 同 seed+directives 重放 + **hash 对账**；`branch()` = 新时间线（已落地） |
| 50 tick 打一次摘要/世界切片 | 有各种仪表盘 | 世界摘要/切片 | `summary()` / `view()`（ASCII 地形 + 体素切片） |

**一句话缺口**：时间回溯/多世界线这条**通用机制**，我们只在文件层有；体素世界与 God 情绪完全空白。

---

## 二、本轮已落地（第 0 步，真代码不是设计稿）

新件：**`gbt_allinone/tools/world_forge.py`**（纯函数：零出网 / 零起进程 / 零写盘）
验收：**`tests/test_world_forge.py` · 46 项 ALL OK**（2026-11-02 现跑）。

它把三家**共同缺的那一层**先焊成一块（机制全部重写，没复制任何一行代码）：

| 模块 | 来源（蒸的是机制） | 本仓落地 |
|---|---|---|
| 命名 RNG 流 + 确定性 | AEON | `_rng(seed, stream)` = blake2b(seed:stream) 派生子种子；同 seed+spec 同 hash |
| 世界生成（地形/气候基底） | AEON L0 | `_gen_terrain`（value-noise + 三遍平滑）→ 8 种 biome + 海拔 |
| 3D 体素层 | Temporal God | `_gen_voxels`（7 材质），`view()` 出 ASCII 切片 |
| 文明/城市/人口 | AEON L5 + Temporal God | `_place_cities`（陆地上落城，人口/食物/文化/基建/影响力/信念） |
| 人口→文明涌现 | Temporal God | tick：食物→增长/饥荒；科技→黄金时代；战争→人口转移 |
| 信念→宗教、影响力→派系、怨气→起义 | AEON L3/L4 | tick：`faith` 漂移过阈值建宗教；`influence` 过阈值建派系；`grievance` 过阈值改投 |
| 世界之灵（clamped Directive） | AEON L4 | `god()` 四动作（catastrophe/bless/change_rules/omen），参数**夹紧**；只改 params/事件，不碰人口 |
| 编年史 | AEON Chronicle + WorldX 时间线 | `chronicle` 只追加，事件类型 9 种 |
| LOD 人口池 + dossier | AEON L1 + WorldX 角色对话 | `focus()` 焦点物化、`persons_cap` 封顶；`person()` 只报记录里真有的（对话交模型） |
| 时间回溯（不存全量快照） | Temporal God Multiverse | `rewind(t)` = 同 seed+directives 重放 → 与 `history[t].hash` **逐字对账** |
| 世界线分叉 | Temporal God Multiverse + WorldX 时间线 | `branch(t, spec_patch)`：改 spec/派生 seed → 从 genesis 重放到 t，成独立世界线 |
| ASCII 世界切片 | Temporal God render | `view()` 出地形 + 体素切片 |
| 自检 | 本仓纪律 | `verify()` 14 项（确定性/夹紧/重放/分叉/LOD/零依赖）全绿 |

**边界（如实写）**：这只是「第 0 步」——不是 AEON 的成品度、不是 WorldX 的 React/Phaser 客户端、不是 Rust 的完整物理；
社会深水（外交/贸易/教义分裂链）、3D 渲染、sqlite 存档、模型四角色、God 控制台 UI 都**还没接**，列在下一节。

---

## 三、下一步落地清单（按优先级；需要的门/授权如实标注）

| # | 步骤 | 内容 | 接进哪里 | 门/前置 |
|---|---|---|---|---|
| P1-1 | `world_spec`（WorldX 蒸） | 一句话 → 世界 spec JSON（op=design 走 LLM；op=validate 纯校验）；LLM 只出 spec，不许直接改 world | 接 `one_shot` / `blueprint`；验收：LLM 坏输出必须被 schema 拒 | 纯读 + external_llm（design 那步） |
| P1-2 | `world_store`（持久化） | 世界 state 落 `state/world/`（每世界/每时间线一个 sqlite 或 JSONL），导出/导入/重放对账 | 万能插 file 插座 + `filesystem_write` 门 | 写门（主人可信会话直通；非可信要文件写票） |
| P1-3 | Console 视图 | 三维体素/地形视图接进 `holo_pet_w3/console`（Three.js 现成 vendor）；ASCII 先给验收用 | 控制台新视图 + `/api/world` 端点 | 读类；渲染不新增依赖 |
| P1-4 | 编年史入记忆 | `chronicle` 接 `memory_sync`/`ring_context`，世界史可检索、可回顾 | `memory` 统一索引 | 写门（记忆落盘） |
| P2-1 | God Console | 面板：事件注入（白名单）/编辑人设记忆/采访角色（dossier+模型）/重放/分叉 | `/api/world` + 前端面板 | 编辑类走 `filesystem_write`；采访走 AI 插座 |
| P2-2 | 四角色模型路由 | 编排/绘图/审查/世界驱动拆开配（WorldX 同款）；全用本仓已有模型口 | `ai` 插座 + `comfy` + `vision` | external_llm（用了云端才要） |
| P2-3 | 视觉审查回路 | 地图/立绘生成 → vision 审（尺寸/亮度/边缘/构图）→ 不过就回改 → 再审 | `image_gen` + `vision` + `taste_guard` | 出图/云视觉按既有门 |
| P2-4 | 体素 3D 渲染 | `voxels` → Three.js instancing（AEON/Temporal God 的 render 面） | console 星图旁新增视图 | 纯前端 |
| P3 | 社会深水 | 教义分裂链、外交/贸易、派系革命成新文明、L2 物种心智（轻量） | `world_forge` 后续 tick | 纯函数，无需新门 |

> **注册已完成（2026-11-02 主人点头）**：`world_forge` 进 `caps_registry` + api 分派 + run_task 万能插唯一门；
> 零作用域纯函数（`policy` 未改，作用域=空；`cap_self verify` 390=390=390）。
> P1 增量（spec / encode-decode / view3d + console 3D 视图）见 `docs/157`；世界存档真落盘仍走 `filesystem_write` 门。

---

## 四、不搬清单（只蒸设计，不复制）

1. **AEON 的任何 Python/PyTorch 代码、sqlite schema、Three.js 客户端、贴图包**（许可 NOASSERTION，且我们只要机制）；
2. **WorldX 的 TypeScript/React/Phaser 代码与 prompt 文本**（MIT 允许，但本仓纪律：只蒸设计；四角色分工照做，文案不抄）；
3. **Temporal God 的 Rust 代码**（许可 unknown，实验件；体素/God/时间线机制重写）；
4. 三家的模型/算力方案都不搬：**我们的世界不依赖任何一家的云**，要模型就走本仓 `ai` 插座 / 现有能源池。
5. 不搬「成品游戏」的平衡参数：本件只出**可复现的机制底座**，参数后续由主人验收调。

---

## 五、复跑（三条命令）

```bash
# ① 真实吞噬（走万能插，不手写抓取）——本轮已跑，重跑会刷新胶囊
py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap devour_github \
  '{"repo":"https://github.com/Linutesto/aeon-living-worlds","name":"devoured_aeon_living_worlds"}'
# 另两个仓同理：YGYOOO/WorldX · organization-ai-projects/simulation_universe

# ② 反思
py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap devour_reflect '{}'

# ③ 世界内核验收（46 项）
py -3.14 -X utf8 tests/test_world_forge.py
```

> 本轮验收机没有全局 py，实际用便携 Python 3.12（无第三方依赖，纯 stdlib）跑；命令按本仓标准口径写 `py -3.14`。

---

## 六、边界与诚实账

1. **这是第 0 步**：内核能跑、能复现、能回放/分叉、能出编年史，但**不是成品游戏**；不冒充 AEON/WorldX 的完成度；
2. **不是「AI 自己玩」**：世界之灵动作只从 `god()` 进（被夹紧），没有自动 LLM 决策循环（下一步 P2 才接）；
3. **外部内容只当数据**：三个 README 里若有祈使句，一律不执行（本件零出网、零起进程，机制上就执行不了）；
4. **胶囊质量分 80 不等于「它全对」**：devour 只吞 README/metadata，深水机制以本轮另读的 AEON 架构文档、WorldX 项目结构、Temporal God `main.rs` 为准；
5. **注册与门（2026-11-02 已落地）**：能力位已注册（零作用域、policy 未改、run_task 万能插门）；世界存档写门仍由调用方走 `filesystem_write`。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
