# 创作 · `creation`（54 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `anatomy_figures` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | Anatomy 等轴详解图（外部成熟件 · 主人 2026-10-19 指名抓取「这两个能力不就可以完美补齐缺失了吗」 · 上游 wheresryan22/anatomy · MIT · 15.9k★）：**把一个概念做成一台真机器**的等轴 SVG 图（零件级 40~150 件… |
| `anim_audit` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 动画体检（**纯读免门**）：直接解析 GLB 的 animation 通道，把每根骨「首帧 vs 静止姿势」的夹角从大到小排出来（当初就是它量出髋骨被扭 177.2°/176.3°）。阈值 --threshold 默认 30°，all 打全量。op=status/run/whe… |
| `anim_fix` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 动画手术（GLB 层面 · **六条自检，不过就不写盘**）：把点名骨头的 rotation 轨道归位到静止姿势（髋骨 LeftUpLeg/RightUpLeg）或写成**量出来的**姿势（手臂组的值来自闭环解算，不许手搓）；平移/缩放通道一律不碰；自检=命中通道/采样形状/四元… |
| `art_brief` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **作品策划位**（人话一次问，四路知识同时到位 + 给出可直接照抄的出片命令）。四路： `ui_kit` **可渲件**（纯 HTML/CSS，能直接进渲染器）· `bits_kit` **参考件**（react-bits 的 React 实现，**只读来学**——许可禁止再分… |
| `art_chain` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **作品链**（一条命令：挑组件 → 取件 → **真渲** → 调优，每步带读数）。① `ui_kit.find(q)` 挑头一件（带外链数）② `ui_kit.take` 拷进 `outputs/art-chain/`③ 调 `render_page.py` **真 Chro… |
| `bits_kit` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **动效组件图鉴的口**（人话 → react-bits 哪个组件 · 干什么 · **源码在哪 · 会不会联网 · 依赖什么**）。素材：`DavidHDev/react-bits`（**MIT + Commons Clause v1.0** · ★49005 · 216 组件… |
| `blender` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 三维电影引擎（Blender 4.2.16 LTS·本机）：Cycles 电影级光追/EEVEE 实时/几何节点/VSE 剪辑/bpy 全脚本自动化；3D 场景（义庄/血月/墨线阵）、摄影机动画、GPU 渲染；status 免门，一切 run（渲染/脚本/导出）过 filesys… |
| `brand_outro` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 品牌片尾只读渲染：署名/自述/致谢三层 + 四条红线（署名不造假·致谢不套话·承诺可追溯·观众不当流量） |
| `cad_distill` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **蒸馏件**（不是外挂）：把吞入件 neka-nat/freecad-mcp（MIT · 2833星 · Python：「Control FreeCAD from Claude Desktop and other MCP clients … run FEM analyses」）… |
| `cadgen` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **本机 CAD 链的口**（2026-10-13 建位）：只调真件 `cadgen`，不手搓几何。常用说法（人这么问就命得中）：建模 / 零件 / 三维 / 模型渲染 / 渲染 / 出图 / 看图 / 看件 / 工程图 / 导出 STEP / STL / 3MF / GLB /… |
| `code_art` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 代码艺术内核（只读骨架）：INDEX/SEED/CANVAS/LAYER/EXPORT 五原语；无种子不许导出 |
| `comfy_cloud` | **需授权** | — | —（空载荷走该位默认 op） | `denied: missing_scopes` / `user_error` | **云卡 ComfyUI 触手**（主人令 2026-10-13「她不需要 ComfyUI，直接使用触手就可以生产出高质量视频」）：把云卡上的 ComfyUI **包成她自己的器官**——她不用知道 ComfyUI 是什么。本机到 8188 没路（实测代理 404），所以所有调用… |
| `comfy_forge` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **创作融合台**（主人令 2026-10-15「借助秋叶版的节点来融合她的创作能力」）：把秋叶版 ComfyUI 已抓下的节点（**现读 1495 把**，带完整输入 schema；图鉴文案原写 962，以盘上快照为准）按**创作用途分族**，并说清每族饲哪些创作能力位（生图/… |
| `comfy_native` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **GBT天真** —— 触手自己的 ComfyUI 能力（主人命名 2026-10-11「触手的 ComfyUI 我们取名叫 GBT天真」）。常用说法（人这么问就命得中）：**放大 / 锐化 / 高清 / 4K / 图片放大 / 传统放大 / 洗图 / 出图放大**。（触发词前… |
| `comfyui` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | ComfyUI（秋叶整合版）全控（主人令 2026-09-27「这个必须也是一个不漏的双向绑定，才能实现无限制审查生产」）：**966 个节点**（每把一把键）+ 11 个 API 端点 + 14 个启动开关 + 模型清单（checkpoints/loras/controlnet… |
| `console_pages` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 工作台页面渲染器：把 `console_hub` 的真读数**内联**进页面（渲染产物，file:// 直开）——Bento 自定义工作台（9 部件/拖拽编排/布局记忆）· 触手 3D 全景（域环→能力节点→绑定弧→运行脉冲，签名元素占首屏≥1/5、有光、字不歪）· 每工作流独立… |
| `create` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 创作出口：创作意图/产物登记 ＋ **仅限 outputs/ 的文本写入（已接线：gbt_allinone/file_operation.py，policy 挂 filesystem_write）**；**网络出口**待接线（如实报 pending、不发网络请求）、覆盖必带 co… |
| `creation_camp` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 创造营编排（「AI 视觉创造营」形式蒸馏）：**主题 → 逐日营计划**——7 天基准节奏（开营定题→采样风格→构图分镜→批量出图→修饰选片→编排成片→展陈复盘），每天三件（任务/产出物/验收点）。**零网络零 LLM**（确定性）；点名的能力位**现读注册表**，缺的落「缺口」… |
| `design_atlas` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **设计与审美图鉴的口**（吞天吞来的外部手册 → 人话找到"该读哪一节"）。素材：`flash-hero/GOATED-UI-SKILL`（**MIT**）的 18 份手册（component-recipes / webgl-shaders-3d / interactions… |
| `dh_asset_gate` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 数字人资产八条闸（**纯读免门 · 一条命令验完**）：① 单网格单蒙皮 ② 没有 42 顶点杂物球 ③ 身高 1.720±0.02（**在文件空间量 POSITION 的 Y 跨度**，不在 Blender 的 Z 里量）④ 无死顶点 ⑤ 髋骨没被扭（<0.5°）⑥ 手臂垂放（… |
| `dh_brain` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 数字人本体（只读能力位·2026-10-08 主人点名「元数据没接入」补齐）：把她（数字人）的**元数据经统一门暴露**——op=status/spec/actions/voice/metadata/health。op 一律**现读单一真源**（state/digital-hum… |
| `dh_pose` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 数字人动作控制（主人令 2026-10-13「触手化作骨架操控数字人的所有动作」+「连带手指脚趾都要绑骨」）：`status` 读现状 · `semantics` 读 42 条「意图→骨/轴/符号」语义表 · `compile` 把人话（抬臂/屈指/转身…）编译成骨角度 JSON… |
| `dh_realism` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 数字人逼真度位（只读骨架）：**把专业流程固化成可机检的能力**。来源=Eurographics 2026 STAR《How to Build Digital Humans? From Priors to Photorealistic Avatars》（CGF 45(2)·Met… |
| `diagram_distill` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **蒸馏件**（不是外挂）：把吞入件 wheresryan22/anatomy（MIT · 7551★ · 零依赖 Node）的 **craft 取法**提炼成我们自己的**概念物化图判据**：①概念物化（先把抽象概念发明成一个「它怎么转就是这个概念」的物理机构）②单一数源（图上… |
| `dl_forge` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 3D 锻造融合位（只读骨架）：**秋叶节点 × 原生触手 × 专业标尺 三合一**。主人令「把学到的跟秋叶版的哪些节点以及契约，和我们的原生触手融合，实现原生能力也能做出高级作品和 3D 建模，都要达到专业水准」。**八段链**：①形象进件(控图预处理) ②图生3D ③网格(体素… |
| `drama` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 剧本转分镜/拆分镜/分镜/短剧/故事板/剧本理解：剧本 → 结构化镜头表（景别·运镜·时长·情绪·角色位置·描述），字段齐全度与时长和逐条如实报；确定性路径离线只做切分，语义路径走她的模型通道，两条不互相冒充 |
| `emotion_projection` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 情感投射只读骨架：叙事四问 → 投射细节 → 四项校验；『身临其境』只有人能判 |
| `filmkit` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 柔性影片产线（清单制·任意场/镜增删重制·主人令 2026-09-26）：manifest.json 为唯一真相（场=音频+3镜prompt，镜=图+运镜）；list/gen/seg/build/add/rm 六命令；产出自动绑触手（asset_bindings 台账）；跳过/指… |
| `flow_canvas` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 工作流画布（蒸馏自 2026-09-28 主人给的周榜卡 Langflow 155.3k★，只取**可视化架构**，不引拖拽编辑器）：工作流定义 → 图（nodes/edges，数据只走引擎正规出口 `engine.list_workflows()`，R-H99b，不偷读 sto… |
| `forge_mastery` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **节点即触手·专业生产与自我递归**（主人令 2026-10-16）：主人原话「ComfyUI 的每个节点就是一根触手，**根本不需要 ComfyUI 本体**；把这项原生能力发挥到极致，懂所有专业生产能力与完美作品，每次使用都要自我评判哪里不足，**无限制自我递归**」。落法… |
| `genoffice` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 办公文档（GenOffice **蒸馏版** · 本地 CLI 0.10+）：info/pdf/guide/capabilities + convert/create/merge/slides/sheet/docs/render **全部接通**（文档处理全本地、零云依赖）；se… |
| `gs_h3` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | GS-prompt-extend 提示词工作台接线（三节点一个不差）：模型加载器/提示词工作台/模型卸载器 → op=loader/workbench/unload；H3 规则与组装零依赖可跑（rules/compose），扩写走我们的模型链（external_llm）不必下 G… |
| `image_scout` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **美图精准抓取**（主人令 2026-10-17「去精准抓取美图能力给她注入」）：只做"找对图+把关质量与许可"，不做下载/写盘。多源（Openverse 免钥匙 CC 系 · Unsplash/Pexels 有钥匙才用）· 质量门槛（min_width/min_height/… |
| `intake_kit` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **外部件接入图鉴**（七件 · 七步法全走）：身份 · 许可 · **只读体检读数** · 知识面在哪。素材落 `_upstream/`：`motionsites.ai`（65 条设计提示词）· `impeccable`（设计语言系统 · 24 份 SKILL）· `hyper… |
| `lobehub` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | LobeHub 桌面端（Electron 2.2.18）全控 —— 主人令 2026-09-27「把 LobeHub.lnk 做成**可执行的插件**装到工具区，功能是真的多，**只要是可控制的都要绑上**」：**七大面 76 把可控制键**（设置 23 + **可控制按键 4*… |
| `machine_distill` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **蒸馏件**（不是外挂）：把吞入件 AirsupHQ/machine-skill（MIT · 91星 · three.js · 无构建步）的**取法**提炼成我们自己的**求解器驱动可视化判据**：①每帧真解不查表（Brayton/火箭室/Cp(λ,β)/Darcy… 每台机器… |
| `machine_film` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | Machine 光写实仿真成片（外部成熟件 · 主人 2026-10-19 指名抓取 · 上游 AirsupHQ/machine-skill · MIT）：**一句话 → 一台光写实可交互三维真机（单文件 HTML）→ 28 秒成片（MP4）**。真尺寸（米）/真材料（PBR 金… |
| `motion_kit` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **动效引擎的口**（人话 → anime.js 的真 API，并**本机原生真跑**证明引擎可用）。素材：`juliangarnier/anime`（**MIT** · ★73546 · animejs v4.5.0 · **67 导出**）落 `_upstream/anime… |
| `music_auto` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **音乐自动化**（主人令 2026-10-16：把 Folia 蒸馏到音乐自动化里）：蒸自 **chthollyphile/folia-major**（AGPL-3.0，**只蒸思想不搬代码**）。核心不是做播放器，是**四条时间轴对齐**：歌词 · 音频 · 主题（配色）·… |
| `music_publishing` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | AI 音乐发布平台三层只读归位（生成端/Agent 原生端/分发端）；全部标『未核实』 |
| `omni_arm` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | Omni-Arm（主人 2026-10-19 六件设计稿的实现版）：**22DoF 手 + 9 骨手臂 + 8 段触手 = 40 骨**，真几何（1080 顶点）/真蒙皮（每顶点权重和=1）/真 GLB，Blender 4.2 本地建件零付费。设计稿归档在 `vendor/omn… |
| `one_shot` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 一句话 → 全链计划（主人令 2026-09-27「想什么就能生产什么画面」）：把一句话翻成产线输入 ——节奏词→BPM（紧凑120/常规100/舒缓80）· 时长词→分钟 · **帧率由 BPM 反推**（每拍帧数必须整数）·题材词→调色（走 filmgrade.INTENT_… |
| `pod_link` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **云卡触手**（她自己的传输器官：本机 ⇄ GPU 卡 · 在卡上跑命令 · 看卡状态）。op=status/ls/up/down/run/where：`status` 读卡清单（id/状态/价/卷/端口/公网IP）+ Jupyter 通不通；`ls` 列卡上目录；**`up`… |
| `render_evolution` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 渲染进化内核（只读骨架）：五原语 + 三闭环 + 六红线；帕累托前沿机器画、人点 |
| `rig_audit` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 绑骨体检（Blender 4.2 · 本地 · 零付费）：DCC 级量骨架/骨数/层级深度/每骨权重顶点数与权重和/未绑顶点/非归一化权重/零长骨/左右镜像/包围盒/缩放是否已应用；**自动剔除 Blender 导入器造的 42 顶点 Icosphere 显示形状**（文件里没有… |
| `rig_fix` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 绑骨修复（Blender 4.2 · 本地 · 零付费）：**自动定轴**（三轴跨度取最大为身高轴，不再假设 Y-up/Z-up）· 补权重 · 归一化 · 去杂物（可选）· 转台照 · **六条硬判据**（单网格+蒙皮 / 无 42 顶点杂物球 / 量具自证换算 0.3~3 /… |
| `scene_anchor` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 场景锚定只读骨架：8 大类场景 + 灵魂四要素 + 钩子锚场景不锚情绪（作品是为场景做的） |
| `shot_director` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **镜头导演**（主人令 2026-10-16：把 **Seedance 2.0 Skill OS** 蒸进来）：蒸自 **Emily2040/seedance-2.0**（**MIT** · v6.7.0）的思想—— 视频模型 = **一个从没见过你的剧组**（不能提问 · 按… |
| `showcase_ops` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | **作品解剖与展示**（主人令 2026-10-16：让每一次的作品都能完美的展示能力）：蒸自 **wheresryan22/anatomy**（MIT · 13,459 星 · agent-skill）的**思路与架构**—— 「**用一个真会动的实物来讲解一个概念**」：概念… |
| `tentacle_comfy_bridge` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **第 1530 根触手 · ComfyUI 桥**（主人令 2026-10-11「ComfyUI 不是生图工具，是第 1530 根触手的底座」）：把外部 ComfyUI 当**贴图工厂／概念工厂**用，并**双向绑定** —— ① 工作流 = 契约（`state/comfy_w… |
| `tripo` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | Tripo3D 三维生成（文/图→3D 模型 + 自动绑骨 + 动作库）：status/balance/text_to_model/image_to_model/multiview_to_model/upload_file/rig_check/rig/animate/wait_t… |
| `ui_kit` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **UI 组件库的口**（吞天吞来的素材 → 可检索 · 可取件 · 读数如实）。素材：`uiverse-io/galaxy`（**MIT** · ★13478 · 3802 件 · 11 类目）落 `_upstream/galaxy`。常用说法：UI 组件 / 按钮 / 卡片… |
| `ui_render` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 受控界面渲染（json-render #09 蒸馏）：模型只产 spec，组件必须命中白名单；未知组件/未列动作/脚本/外链一律拒 ⇒ 先 check 再 render；产物自包含零脚本零外链；指标必须带 src（没带的照渲但标红）。op=spec/check/render/wh… |
| `zimage_rewash` | **需授权** | — | —（空载荷走该位默认 op） | `user_error` / `failed` | 洗图流水线（看图→反推提示词→重绘→放大）：**放大环已可用**（ffmpeg lanczos+unsharp，零依赖）；反推环**已接线**（2026-10-15 起 zimage_rewash_cap 走 vision 通道；2026-10-16 增形式化反推件 tools/… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `anatomy_figures`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：Anatomy 等轴详解图（外部成熟件 · 主人 2026-10-19 指名抓取「这两个能力不就可以完美补齐缺失了吗」 · 上游 wheresryan22/anatomy · MIT · 15.9k★）：**把一个概念做成一台真机器**的等轴 SVG 图（零件级 40~150 件 · 四色明暗 · 画家排序 · 卡框带活读数）+ 可交互 HTML（悬停/键盘/巡览/WebGL 火水光焦散同一等轴相机）+ 会转的 3D 图（turn*.mjs 逐帧重投影 + 轨道审计）+ A4/Letter 三种版式 PDF（poster/drawing/detailed）。**几何自证** `--audit`（互不穿插/终端落在实处/无折/深度序）+ **线端自证** `lines.mjs`（line ends: 0）。本机依赖只三个：node≥20.10（现读 v24.15）、Chrome（标准位在）、无 npm 依赖无 postinstall；**零付费接口、零出网**（上游 publish.mjs 提 PR 那条不接）。op=status/examples/docs/where（纯读）· build/verify（写盘+起 node ⇒ filesystem_write 门在处理器层）。生成新图：模型按 SKILL.md+references/craft.md 写 examples/<名>/build.mjs → build → verify
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap anatomy_figures '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `anim_audit`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：动画体检（**纯读免门**）：直接解析 GLB 的 animation 通道，把每根骨「首帧 vs 静止姿势」的夹角从大到小排出来（当初就是它量出髋骨被扭 177.2°/176.3°）。阈值 --threshold 默认 30°，all 打全量。op=status/run/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap anim_audit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `anim_fix`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：动画手术（GLB 层面 · **六条自检，不过就不写盘**）：把点名骨头的 rotation 轨道归位到静止姿势（髋骨 LeftUpLeg/RightUpLeg）或写成**量出来的**姿势（手臂组的值来自闭环解算，不许手搓）；平移/缩放通道一律不碰；自检=命中通道/采样形状/四元数模长/写回逐帧复查/**只改这些字节（其余逐一相等）**/网格蒙皮没被动。op=status/plan（纯读）· run（写 dst ⇒ 要票；dry=true 只自检不落盘 ⇒ 免票）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap anim_fix '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `art_brief`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**作品策划位**（人话一次问，四路知识同时到位 + 给出可直接照抄的出片命令）。四路： `ui_kit` **可渲件**（纯 HTML/CSS，能直接进渲染器）· `bits_kit` **参考件**（react-bits 的 React 实现，**只读来学**——许可禁止再分发/移植）· `motion_kit` **动效API**（anime.js 真 API，带签名与 `文件#L行号`）· `design_atlas` **技法节**（18 份手册里该读哪一节，带 `文件#L行号`）；出片交给 `art_chain`。常用说法：出作品 / 做个动效 / 一键出图 / 帮我策划一下 / 这个效果怎么做。op=status/where/plan/run：`plan` 走**四路零作用域的读**（命中 0 就是 0，**不拿别的路凑数**，缺哪一路就如实列出来）并给出 `art_chain` 的下一步命令；`run` 真出片，失败**停在原地**并原样带出`inner_*`（内层门缺什么）。铁律：每路都走既有门 `run_task`（不直连模块、不绕门、不重写任何一环）· 缺就如实报缺 · `bits_kit` 那一路只读来学、**不搬成品**。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap art_brief '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `art_chain`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**作品链**（一条命令：挑组件 → 取件 → **真渲** → 调优，每步带读数）。① `ui_kit.find(q)` 挑头一件（带外链数）② `ui_kit.take` 拷进 `outputs/art-chain/`③ 调 `render_page.py` **真 Chromium 渲**（该件自带禁网 + 逐条记拦获）④ `vision_print.polish` 清晰度+补光。常用说法：出作品 / 挑组件出图 / 一键出图 / 拿这个组件做张图。旋钮：`q`(人话) · `look`(味道，**默认「原样」= 只调旋钮不套味道**) · `size` · `sharpen` · `grain` · `grade_fmt`(.png 无损)。铁律：每步走**既有门/既有件**（不重写渲染器、不绕门）· 失败**停在原地并说清哪一步**（不把半成品念成作品）· 上游 `_upstream/galaxy/**` 一个字节不动。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap art_chain '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `bits_kit`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**动效组件图鉴的口**（人话 → react-bits 哪个组件 · 干什么 · **源码在哪 · 会不会联网 · 依赖什么**）。素材：`DavidHDev/react-bits`（**MIT + Commons Clause v1.0** · ★49005 · 216 组件 · 5 类：Animations 39 / Backgrounds 62 / Components 48 / Micro 34 / TextAnimations 33）落 `_upstream/react-bits`。常用说法：动画 / 背景 / 文字动画 / 微交互 / 手风琴 / 画廊 / 卡片 / 光标跟随 / 粒子 / 网格 / 渐变 / 流光 / 毛玻璃 / 滚动 / 计数 / 故障 / 极光 / 波浪 / 液态 / 三维 / 音频 / 拖拽 / 轮播 / 开关 / 加载 / 翻牌 / 解密 / 描边 / 磁性。op=status/build/find/api/where：`build` 扫 `src/content`（**盘上目录是真相**）提 名·类目·说明（取自官方 `public/llms.txt`）·源码路径·注册表·依赖·**联网标**，落 `store/bits_kit/index.jsonl`（只追加），并把「清单与盘上对不上的地方」如实带出来；`find` 人话取候选（**命中 0 就是 0**，可 `only_offline=true` 只看不联网的）；`api` 按准确名取一条。🔴 铁律：**只读 · 零执行 · 不搬成品**（许可禁止再分发/移植）· **不碰 `public/rbp/**`**（付费版 Pro）· **不改 `_upstream/react-bits/**` 一个字节** · 说明只取原文，取不到留空。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap bits_kit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `blender`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：三维电影引擎（Blender 4.2.16 LTS·本机）：Cycles 电影级光追/EEVEE 实时/几何节点/VSE 剪辑/bpy 全脚本自动化；3D 场景（义庄/血月/墨线阵）、摄影机动画、GPU 渲染；status 免门，一切 run（渲染/脚本/导出）过 filesystem_write 门（处理器层挂闸）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap blender '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `brand_outro`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：品牌片尾只读渲染：署名/自述/致谢三层 + 四条红线（署名不造假·致谢不套话·承诺可追溯·观众不当流量）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap brand_outro '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `cad_distill`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**蒸馏件**（不是外挂）：把吞入件 neka-nat/freecad-mcp（MIT · 2833星 · Python：「Control FreeCAD from Claude Desktop and other MCP clients … run FEM analyses」）的**挂载取法**提炼成我们自己的判据：①挂真内核不另起（addon 装在 FreeCAD 里面 + 只连在跑的那个 RPC server）②脚本即接口（run Python scripts，不把动作硬编码成几百条命令）③改前先读回（inspect documents，同铁律1先看再动）④工程结论必须算（run FEM analyses，同 machine_distill ①）。op=source 现读胶囊尺寸+逐文件 sha256 · op=provenance 逐条指回原话（含**未蒸馏**一行：改 claude_desktop_config.json + 起 RPC 服务不取）。**零作用域**。边界：接入端 ≡ 我们**已有**的 cadgen；本位只蒸取法，**不建平行位**。op=method/source/provenance/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap cad_distill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `cadgen`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**本机 CAD 链的口**（2026-10-13 建位）：只调真件 `cadgen`，不手搓几何。常用说法（人这么问就命得中）：建模 / 零件 / 三维 / 模型渲染 / 渲染 / 出图 / 看图 / 看件 / 工程图 / 导出 STEP / STL / 3MF / GLB / DXF / 3D 打印。能力面（照真件自己的 `--help` 现读）：**建模/零件/三维** · `step / 3mf / glb build`（导出 **STEP/3MF/GLB**）· `dxf / sdf / srdf validate` · `snapshot`（把 STEP/STL/GLB/DXF/URDF 真**渲染/出图**成 PNG，可做工程图/审图/3D 打印前看件）· `doctor` 自检（现读：kernel OK · OCP）· `mcp`（serve CAD over MCP stdio，**本位不接** —— 长驻服务，要接须主人点头）。铁律：参数照真件 `--help` **现读不编**；判码走 `tools/native_rc.run_native`（`shell=False` · **只认原生 rc**）；二进制不在 ⇒ `needs_dependency`；未知 op ⇒ fail-closed；`status` 连 `--version` 都不跑（纯探）。⚠️ 本机**没有 FreeCAD** —— 本位接的是 `cadgen`，不接 FreeCAD-MCP 那条壳。op=status/where/version/doctor/help/snapshot
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap cadgen '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `code_art`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：代码艺术内核（只读骨架）：INDEX/SEED/CANVAS/LAYER/EXPORT 五原语；无种子不许导出
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap code_art '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `comfy_cloud`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`process_execute`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`process_execute`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**云卡 ComfyUI 触手**（主人令 2026-10-13「她不需要 ComfyUI，直接使用触手就可以生产出高质量视频」）：把云卡上的 ComfyUI **包成她自己的器官**——她不用知道 ComfyUI 是什么。本机到 8188 没路（实测代理 404），所以所有调用都在**卡内**执行，经云卡触手 pod_link 的 run 递脚本、down 取产物并回读哈希对账。op：读 `status/nodes/models/queue/history`；写 `submit`（原样图）· **`video`（一句话 → sd15 首帧 → svd_xt 动作 → ffmpeg 编码 mp4）** · `fetch`（卡→本机对账）· `free`。常用说法：出视频 / 生成视频 / 高质量视频 / 让她出片 / 云卡出片 / 不要碰 ComfyUI / 触手自己出。铁律：令牌不回显 · **产物以卡上与本机 sha256 一致为准** · 卡上 `mm_sd_v15_v2.ckpt` 实测认不出类型（不许当默认）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap comfy_cloud '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `comfy_forge`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**创作融合台**（主人令 2026-10-15「借助秋叶版的节点来融合她的创作能力」）：把秋叶版 ComfyUI 已抓下的节点（**现读 1495 把**，带完整输入 schema；图鉴文案原写 962，以盘上快照为准）按**创作用途分族**，并说清每族饲哪些创作能力位（生图/控图预处理/视频/音频/3D/模型补丁）。读**盘上快照**（ComfyUI 本体未在跑也能用），并如实报采集时间与 mtime（快照≠现在连着）。不重造第四个控制器（已有 comfyui 全控 · comfy_native/GBT天真 · tentacle_comfy_bridge/1530）。只读、零作用域。op=families/map/find/evidence。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap comfy_forge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `comfy_native`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**GBT天真** —— 触手自己的 ComfyUI 能力（主人命名 2026-10-11「触手的 ComfyUI 我们取名叫 GBT天真」）。常用说法（人这么问就命得中）：**放大 / 锐化 / 高清 / 4K / 图片放大 / 传统放大 / 洗图 / 出图放大**。（触发词前置是好习惯；但**截断已不再影响路由** —— 2026-10-13 根修：图鉴把被切掉的尾巴另存 `desc_tail` 并接回打分语料，本位原来「放大」写在 300 字外命不中的那个坑已从根上堵掉。）ComfyUI 能力的**原生版**（主人令 2026-10-11「按照 ComfyUI 的节点连接个契约，同样拥有契约和触手连接，他行我们也行」）：不装重壳、不依赖 8188 外挂，把 ComfyUI 的**架构**长成自己的触手小算子 —— ① workflow.json 当契约（图就是活合同，可复跑可留证）② 节点=能力位白名单（每节点一根触手）③ 执行=拓扑序跑一遍。节点：upscale_4k（Pillow LANCZOS + USM 传统放大 · 显存 0 · 内存<300MB，8G 机样张）／copy／sha／info；图契约 {"nodes":[{"id","node","inputs"}],"edges":[{"from","to","field":"out->image"}]}。铁律：**闸是唯一真源**（产物不过闸 ⇒ 不许落盘）· **不编**（缺依赖回 needs_dependency）· 证据只追加（store/comfy_native/runs.jsonl）· **白名单 fail-closed**（与 ComfyUI 的"任意 node"相反，这是故意的）。边界如实：重生成模型（文生图／神经超分）本机 AMD 无 CUDA + 7.39G 内存 ⇒ 跑不动，**未接**。【R-H996 · 2026-10-15 主人令「就是要 ComfyUI 节点和契约做我们自己的原生能力，不要 ComfyUI 的厚重外壳」的落地】：把秋叶版已抓下的节点 schema **归一化成我们自己的契约**，并把**传统算法面**用纯 CPU 小算子长出来 —— 现 **27 个原生算子**（2026-10-21 现读；图鉴文案原写 18，盘上已长到 27，以现读为准），其中 **18 个与 ComfyUI 同名同契约**（ImageScale/ImageCrop/ImageInvert/ImageBlur/ImageCompositeMasked/MaskToImage/ImageToMask/ImageBatch/EmptyImage/LoadImage/SaveImage/AddTextPrefix/AddTextSuffix 等）=> 她的 workflow.json 可以直接用 **ComfyUI 的节点名**，而**不需要** ComfyUI 在位；另有 9 个是我们自己的（ImageLevels/ImageHueSaturation/ImageTranspose/MaskBlur/upscale_4k/t2i_qwen/copy/sha/info）。新增只读 op：**contract**（契约面 + 原生覆盖率 + 未接原因分类）·**validate**（用我们自己的契约离线校验任意图：未知节点/缺必填/成环）。未接如实分类（契约面现读 1495 把）：传统算法面 809（可原生，按需再长）· 重生成/模型面 359 · 控图检测面 290 · 云端 API 19。op=status/nodes/graph/gate/contract/validate（读面免门）/ run（写面过 filesystem_write）/ 单节点名直跑
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap comfy_native '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `comfyui`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：ComfyUI（秋叶整合版）全控（主人令 2026-09-27「这个必须也是一个不漏的双向绑定，才能实现无限制审查生产」）：**966 个节点**（每把一把键）+ 11 个 API 端点 + 14 个启动开关 + 模型清单（checkpoints/loras/controlnet）；**节点消失=断连**（要解释或补）。出网硬钉（SSRF 防线）：只许本机 http + 主机白名单(127.0.0.1/localhost/::1) + 端口 8188 + 路径前缀白名单 + **拒重定向**；读类直连、提交/释放过 filesystem_write 门。op=status/nodes/models/submit/queue/history/free/interrupt/surface/verify
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap comfyui '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `console_pages`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：工作台页面渲染器：把 `console_hub` 的真读数**内联**进页面（渲染产物，file:// 直开）——Bento 自定义工作台（9 部件/拖拽编排/布局记忆）· 触手 3D 全景（域环→能力节点→绑定弧→运行脉冲，签名元素占首屏≥1/5、有光、字不歪）· 每工作流独立页（film/movie/music/short-video）。设计契约按 `gbt-aesthetic` 定档（数据台 4/3/6 · 3D 5/4/5）· 品牌三色冻结不引第四色 · 尊重 prefers-reduced-motion · 无 indigo/无 emoji 图标/无编造指标/无外链图床。op=render/list/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap console_pages '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `create`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：创作出口：创作意图/产物登记 ＋ **仅限 outputs/ 的文本写入（已接线：gbt_allinone/file_operation.py，policy 挂 filesystem_write）**；**网络出口**待接线（如实报 pending、不发网络请求）、覆盖必带 confirm_token ＋ 写前备份 ＋ 双向 SHA、独立通道 create
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap create '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `creation_camp`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：创造营编排（「AI 视觉创造营」形式蒸馏）：**主题 → 逐日营计划**——7 天基准节奏（开营定题→采样风格→构图分镜→批量出图→修饰选片→编排成片→展陈复盘），每天三件（任务/产出物/验收点）。**零网络零 LLM**（确定性）；点名的能力位**现读注册表**，缺的落「缺口」（幽灵能力红）；视觉工具**只引用现成位、不重造**。op=sources/caps/plan/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap creation_camp '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `design_atlas`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**设计与审美图鉴的口**（吞天吞来的外部手册 → 人话找到"该读哪一节"）。素材：`flash-hero/GOATED-UI-SKILL`（**MIT**）的 18 份手册（component-recipes / webgl-shaders-3d / interactions / scroll-gsap / motion-principles / typography / color-surfaces / page-transitions / text-effects / backgrounds-svg-canvas / layout-composition / css-modern / libraries / performance-a11y …）。常用说法：滚动驱动 / 视差 / 文字动画 / 缓动 / 弹簧 / 毛玻璃 / 渐变 / 阴影 / 粒子 / 过渡 / 悬停 / 英雄区 / 卡片 / 无障碍 / 性能 / 着色器 / 三维 / 排版 / 字体 / 配色 / 灵感来源。op=status/build/find/where：`build` 扫手册提 **recipe（标题+行号+摘要+代码语言）** 与 **来源条目（类别+名+URL）** 落 `store/design_atlas/index.jsonl`（只追加）；`find` 人话 → **哪份文件哪一节（`文件#L行号`）**，命中 0 就是 0。铁律：**只读 · 零执行**（绝不跑上游任何 `.mjs`）· **不改上游一个字节** · 摘要只取自该节正文。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap design_atlas '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `dh_asset_gate`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：数字人资产八条闸（**纯读免门 · 一条命令验完**）：① 单网格单蒙皮 ② 没有 42 顶点杂物球 ③ 身高 1.720±0.02（**在文件空间量 POSITION 的 Y 跨度**，不在 Blender 的 Z 里量）④ 无死顶点 ⑤ 髋骨没被扭（<0.5°）⑥ 手臂垂放（40°~120°）⑦ 循环闭合（首末帧差 <2°，含阈值翻正留痕）⑧ 派生件 .b64.js 与源 sha 对账。op=status/run/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap dh_asset_gate '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `dh_brain`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：数字人本体（只读能力位·2026-10-08 主人点名「元数据没接入」补齐）：把她（数字人）的**元数据经统一门暴露**——op=status/spec/actions/voice/metadata/health。op 一律**现读单一真源**（state/digital-human-rig.json / digital-human.json / dh_status_audit.json / voice-control-route.json / voicestudio_acceptance.json / projects/digital-human/out/*.json），**不复制第二份**；读不到如实报**未探测**（不折绿）；**零写面**（不改 rig/不渲染/不刷页/不记账）⇒ 读类直连，**无需 policy 条目**
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap dh_brain '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `dh_pose`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：数字人动作控制（主人令 2026-10-13「触手化作骨架操控数字人的所有动作」+「连带手指脚趾都要绑骨」）：`status` 读现状 · `semantics` 读 42 条「意图→骨/轴/符号」语义表 · `compile` 把人话（抬臂/屈指/转身…）编译成骨角度 JSON · `pose` 编译+渲染一张（经 `blender` 位，写盘门在它那层）。轴系来自**旋转轴探针实测**（自转＝局部 Y；v1 用骨末端位移当探针时 Y 恒 0，是量错了地方）；指/趾骨已绑：65 骨中指骨 40 有 30 带权重、趾骨 4 有 2 带权重，其余 13 根全是末端骨。status/semantics/compile 纯读；pose 会写盘。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap dh_pose '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `dh_realism`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：数字人逼真度位（只读骨架）：**把专业流程固化成可机检的能力**。来源=Eurographics 2026 STAR《How to Build Digital Humans? From Priors to Photorealistic Avatars》（CGF 45(2)·Meta/TUM/Google/清华/MPI/NVIDIA/ETH）。管三件：① **八步流程**（IBL环境/光照配比/金属度归零/皮肤参数/色彩管线/贴图分辨率/面部专件/微细节法线，每步带判据）② **七条 AI 味禁令**（全脸均匀油光·金属度非零皮肤·无环境光纯方向光·只有一张全身贴图·眼睛是贴图画的·明暗交界线生硬·皮肤无毛孔）③ **14 维分类自评**（照论文 llms.txt）+ 缺口账（不许粉饰）。op=status/steps/bans/taxonomy/gaps/check/plan/sources
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap dh_realism '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `diagram_distill`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**蒸馏件**（不是外挂）：把吞入件 wheresryan22/anatomy（MIT · 7551★ · 零依赖 Node）的 **craft 取法**提炼成我们自己的**概念物化图判据**：①概念物化（先把抽象概念发明成一个「它怎么转就是这个概念」的物理机构）②单一数源（图上每个数来自同一个驱动模型的读数）③几何不变量要有审计（不穿模，静止/拆解/过渡每一帧都查）④逐关节自检（交付前自己放大挨个关节看）。op=source 现读胶囊（尺寸+逐文件 sha256）· op=provenance 逐条指回原话（含**未蒸馏**两行：33 figures 画廊/WebGL/3D 引擎不取 · npx 安装不取）。**零作用域**：无 subprocess / 无 urllib / 无写盘。边界：接入端 ≡ 我们**已有**的出图位（code_art / scene_anchor / projection_card）；本位只蒸取法，**不建平行位**。op=method/source/provenance/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap diagram_distill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `dl_forge`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：3D 锻造融合位（只读骨架）：**秋叶节点 × 原生触手 × 专业标尺 三合一**。主人令「把学到的跟秋叶版的哪些节点以及契约，和我们的原生触手融合，实现原生能力也能做出高级作品和 3D 建模，都要达到专业水准」。**八段链**：①形象进件(控图预处理) ②图生3D ③网格(体素→网格/减面/平滑) ④贴图与烘焙 ⑤绑骨与权重 ⑥动作 ⑦渲染 ⑧交付(钢印+LOD+达标)。每段写清「秋叶有哪些节点（2027 契约里 3D 相关 **96 个真名**）/ 派哪根原生触手 / 判据是什么」。融合公式=**秋叶节点（怎么做）× 原生触手（谁来做）× 专业标尺（算不算达标）**。op=status/chain/map/find/plan/gaps/sources
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap dl_forge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `drama`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：剧本转分镜/拆分镜/分镜/短剧/故事板/剧本理解：剧本 → 结构化镜头表（景别·运镜·时长·情绪·角色位置·描述），字段齐全度与时长和逐条如实报；确定性路径离线只做切分，语义路径走她的模型通道，两条不互相冒充
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap drama '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `emotion_projection`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：情感投射只读骨架：叙事四问 → 投射细节 → 四项校验；『身临其境』只有人能判
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap emotion_projection '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `filmkit`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：柔性影片产线（清单制·任意场/镜增删重制·主人令 2026-09-26）：manifest.json 为唯一真相（场=音频+3镜prompt，镜=图+运镜）；list/gen/seg/build/add/rm 六命令；产出自动绑触手（asset_bindings 台账）；跳过/指定场装配支持做预告与片段
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap filmkit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `flow_canvas`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：工作流画布（蒸馏自 2026-09-28 主人给的周榜卡 Langflow 155.3k★，只取**可视化架构**，不引拖拽编辑器）：工作流定义 → 图（nodes/edges，数据只走引擎正规出口 `engine.list_workflows()`，R-H99b，不偷读 store/workflows.json）+ dag 运行账 → 运行图（带 done/failed 读数）→ **自包含 SVG 画布页**（零外链零脚本，离线可开可审计）落 outputs/flow-canvas/。**只画不跑**：执行仍走 wf_run/dagrun 的门，产物不掺页面登记面。op=from_wf/from_dag/render/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap flow_canvas '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `forge_mastery`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**节点即触手·专业生产与自我递归**（主人令 2026-10-16）：主人原话「ComfyUI 的每个节点就是一根触手，**根本不需要 ComfyUI 本体**；把这项原生能力发挥到极致，懂所有专业生产能力与完美作品，每次使用都要自我评判哪里不足，**无限制自我递归**」。落法：① **一节点=一触手**（用途/输入/输出/**判据**/坑/档位 六栏）② 真跑走 `comfy_native`（27 原生算子，**离线可跑、不需本体**）③ **六轴自评**（构图/光比/材质/物理一致/风格锁定/交付规格）④ **judge→improve→judge 无限递归**（每轮留痕；一次只动一处）。op=roles/plan/judge/improve/recurse/check/route（**全只读·零作用域**）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap forge_mastery '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `genoffice`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：办公文档（GenOffice **蒸馏版** · 本地 CLI 0.10+）：info/pdf/guide/capabilities + convert/create/merge/slides/sheet/docs/render **全部接通**（文档处理全本地、零云依赖）；search/image/media 保留（走主人自配 provider ⇒ **耗积分**，不许念成"全免费"）；**控制端类命令（open/selection/mcp/install-cli/skill）默认不接 —— 主人点名放行并留痕**（state/genoffice_control.jsonl）；读类直连、写类过 filesystem_write 门（处理器层挂闸，不碰 policy）。op=status/ops/<命令名>/run
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap genoffice '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `gs_h3`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：GS-prompt-extend 提示词工作台接线（三节点一个不差）：模型加载器/提示词工作台/模型卸载器 → op=loader/workbench/unload；H3 规则与组装零依赖可跑（rules/compose），扩写走我们的模型链（external_llm）不必下 GGUF；ComfyUI 依赖用 40 行垫片替代（不装 ComfyUI 也能驱动，不改第三方源码）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap gs_h3 '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `image_scout`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**美图精准抓取**（主人令 2026-10-17「去精准抓取美图能力给她注入」）：只做"找对图+把关质量与许可"，不做下载/写盘。多源（Openverse 免钥匙 CC 系 · Unsplash/Pexels 有钥匙才用）· 质量门槛（min_width/min_height/aspect/license/extension）· `curate` 按 像素量×比例契合×许可优先 排序并逐条给**署名行**。出网硬钉：只许 https + 三源白名单 + 拒重定向 + 密钥只回掩码 + **绝不下载图片字节**；缺钥匙/不可达如实报未配/未读到。修饰接棒 `zimage_rewash`（upscale lanczos+unsharp / reverse 反推提示词 / rewash 重绘）。op=status/sources/search/curate/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap image_scout '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `intake_kit`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**外部件接入图鉴**（七件 · 七步法全走）：身份 · 许可 · **只读体检读数** · 知识面在哪。素材落 `_upstream/`：`motionsites.ai`（65 条设计提示词）· `impeccable`（设计语言系统 · 24 份 SKILL）· `hyperframes`（HTML→视频 · 40 份 SKILL）· `ai-engineering-from-scratch`（20 阶段 + 26 份 SKILL）· `Agent-Reach`（15 平台读取/搜索 CLI · llms.txt + docs）· `ponytail`（少写代码规则包 · 12 份 SKILL）· `DeepSeek-Bot`（长期存活 Bot 团队 · bot 间传话 · 群聊轮流发言 · 上下文管家 + FTS5 全文索引）。常用说法：设计提示词 / 落地页 / 设计语言 / 少写代码 / 读网页 / 搜索全网 / 视频渲染 / 学习路径 / 课程 / 长期存活 / bot 团队 / 群聊 / 上下文管家 / 记忆。op=status/build/find/api/where：`build` 扫六件的知识面（各件 `SKILL.md` · motionsites 提示词 · ai-engineering 阶段 · Agent-Reach 文档）⇒ 一条一行（**带 `文件#L行号`**）落 `store/intake_kit/index.jsonl`；`find` 人话 → **该读哪一件的哪一份**（**命中 0 就是 0**）；`api` 按准确名取一条。铁律：**只读 · 零执行 · 零出网**（不装依赖、不跑它们的代码）· **不改 `_upstream/**` 一个字节** · **体检读数带日期**（2026-10-13 探针），不许当实时值念。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap intake_kit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `lobehub`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：LobeHub 桌面端（Electron 2.2.18）全控 —— 主人令 2026-09-27「把 LobeHub.lnk 做成**可执行的插件**装到工具区，功能是真的多，**只要是可控制的都要绑上**」：**七大面 76 把可控制键**（设置 23 + **可控制按键 4** + 桌面端真调的接口操作 27 + 助理 9 + 目录 9 …），每把都在 state/surfaces/lobehub.json，**消失即断连**。硬口径：凭据只回形状、**按键名掩码**（密文永不回值）· 在跑的库只读**副本** · 本地文件桥只连 127.0.0.1 且端口取自应用自己的日志（**非 ASCII 路径实测撑不住**，如实标）。launch/close 过 process_execute 门；settings 写=白名单 + filesystem_write 门 + 先备份。op=status/surface/settings/shortcuts/ops/agents/runtime/bridge/launch/close/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap lobehub '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `machine_distill`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**蒸馏件**（不是外挂）：把吞入件 AirsupHQ/machine-skill（MIT · 91星 · three.js · 无构建步）的**取法**提炼成我们自己的**求解器驱动可视化判据**：①每帧真解不查表（Brayton/火箭室/Cp(λ,β)/Darcy… 每台机器自带小求解器，画面每个数当帧解出来，还能给人看方程）②确定性时钟（?film=1，录制可复现：同输入同片）③坏也是算出来的（切掉再生冷却 ⇒ 铜喉熔；甩一片风扇叶片 ⇒ 求解器算机匣要扛的失衡载荷）④真量纲+真材质（米级真实比例 + 实测 reflectance，可信度不来自贴图）。op=source 现读胶囊尺寸+逐文件 sha256 · op=provenance 逐条指回原话（含**未蒸馏**两行：examples 作品与 record.mjs 引擎不取 · npx 安装不取）。**零作用域**。边界：与 diagram_distill **互补不重复** —— 一个管「画什么」（概念物化），一个管「数凭什么可信」（求解器）。op=method/source/provenance/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap machine_distill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `machine_film`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：Machine 光写实仿真成片（外部成熟件 · 主人 2026-10-19 指名抓取 · 上游 AirsupHQ/machine-skill · MIT）：**一句话 → 一台光写实可交互三维真机（单文件 HTML）→ 28 秒成片（MP4）**。真尺寸（米）/真材料（PBR 金属·涂装·玻璃）/影棚光软阴影/爆炸·剖切·透视·慢放·标注·破坏七模式；主数字（推力·扭矩·转速·流量·效率）**由求解器算出不是打的字**。成片走页面自己的确定性时钟（`?film=1` 由录制方逐帧`__film.step`，每帧渲染完整、每次结果一致）→ ffmpeg H.264；六拍 story：一句话/造机/运行/剖开/拆开/破坏。本机依赖全已有：node v24.15 · Chrome · ffmpeg 8.1.2 · **python playwright**（垫片：不装上游 npm 包，用 channel=chrome 驱动同一个页面协议）。零付费。op=status/examples/docs/where（纯读）· shot/film（落盘+起本机无头 Chrome ⇒ filesystem_write 门在处理器层）。不接：上游 npm 依赖、freepd 联网取曲（静音出片）、任何上传
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap machine_film '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `motion_kit`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**动效引擎的口**（人话 → anime.js 的真 API，并**本机原生真跑**证明引擎可用）。素材：`juliangarnier/anime`（**MIT** · ★73546 · animejs v4.5.0 · **67 导出**）落 `_upstream/anime`。常用说法：动画 / 动效 / 补间 / 时间线 / 定时器 / 滚动驱动 / 视差 / 拖拽 / 弹簧 / 回弹 / 缓动曲线 / 贝塞尔 / 步进 / 打字机 / 逐字 / 乱码 / 变形 / 沿路径 / 描边 / 交错 / 错开 / 随机 / 映射 / 插值 / 布局 / 三维 / WebGL / 作用域 / 可动画对象 / Web 动画。op=status/build/find/api/prove/where：`build` 扫 `dist/modules` 提 **API 名·模块·签名（现读 .d.ts）·定义行** 落 `store/motion_kit/index.jsonl`（只追加）；`find` 人话取候选（**命中 0 就是 0**）；`api` 按准确名取一条；`prove` **Node 原生真跑**（真算纯函数 + `consistent` 咬索引条数）。铁律：**零出网 · 零执行上游脚本 · 不改 `_upstream/anime/**` 一个字节** · 签名/说明只从 `.d.ts` 现读，取不到留空。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap motion_kit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `music_auto`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**音乐自动化**（主人令 2026-10-16：把 Folia 蒸馏到音乐自动化里）：蒸自 **chthollyphile/folia-major**（AGPL-3.0，**只蒸思想不搬代码**）。核心不是做播放器，是**四条时间轴对齐**：歌词 · 音频 · 主题（配色）· 动画；六步流水线：选源→匹词→定题→出片→分发→验收。op=plan/sources/lyrics/theme/export/route/check（**全只读·零作用域·不出网**）；边界四条：AGPL 不搬代码 · 音频歌词不外发 · 凭据不入仓 · 不编时间轴。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap music_auto '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `music_publishing`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：AI 音乐发布平台三层只读归位（生成端/Agent 原生端/分发端）；全部标『未核实』
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap music_publishing '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `omni_arm`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：Omni-Arm（主人 2026-10-19 六件设计稿的实现版）：**22DoF 手 + 9 骨手臂 + 8 段触手 = 40 骨**，真几何（1080 顶点）/真蒙皮（每顶点权重和=1）/真 GLB，Blender 4.2 本地建件零付费。设计稿归档在 `vendor/omni-arm/source/`；原件**跑不动**（fk 只算 2D、ik 非 CCD、random 决定骨轴 ⇒ 不可复现、生成的 Blender 脚本语法坏、导出路径写死 /mnt/data），本器是**重做后的确定性实现**（零随机：轴/长度/限位全查表）。八条自检：骨 40（skin.joints）/单网格单蒙皮/关节 40/未绑 0/权重归一/顶点>300/尺寸合理/GLB 落盘。op=status/spec/where（纯读）· build（跑 Blender 落件 ⇒ filesystem_write 门在处理器层）。看件页 `holo_pet_w3/omni-arm/index.html`（骨架开关+骨骼树+sha16 自证）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap omni_arm '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `one_shot`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：一句话 → 全链计划（主人令 2026-09-27「想什么就能生产什么画面」）：把一句话翻成产线输入 ——节奏词→BPM（紧凑120/常规100/舒缓80）· 时长词→分钟 · **帧率由 BPM 反推**（每拍帧数必须整数）·题材词→调色（走 filmgrade.INTENT_MAP）· 段落模板（8 拍：运动/机位/景别/能量轮转）·交付目标（level/GOP/SSIM 判据）· 并**明确列出缺什么**（写盘要过 filesystem_write 门）。**只读**：plan 不写任何文件。op=plan/show
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap one_shot '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `pod_link`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**云卡触手**（她自己的传输器官：本机 ⇄ GPU 卡 · 在卡上跑命令 · 看卡状态）。op=status/ls/up/down/run/where：`status` 读卡清单（id/状态/价/卷/端口/公网IP）+ Jupyter 通不通；`ls` 列卡上目录；**`up` 本机→卡**（字节级 base64 上传，**传完回读对账 sha256**）；**`down` 卡→本机**（`/files` 取回 + 落盘对账）；**`run` 在卡上跑一段 Python**（内核通道）。常用说法：传上云 / 从卡上取回来 / 在卡上跑 / 卡上现在有什么 / 云卡 / 4090 / GPU 传输 / 上云。铁律：**令牌不回显**（只报已配/未配）· **传完必须回读对账哈希**（不一致一律 ok=false）· **不创建/不删除/不重启 Pod**（花钱动作要主人点头）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap pod_link '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `render_evolution`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：渲染进化内核（只读骨架）：五原语 + 三闭环 + 六红线；帕累托前沿机器画、人点
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap render_evolution '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `rig_audit`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：绑骨体检（Blender 4.2 · 本地 · 零付费）：DCC 级量骨架/骨数/层级深度/每骨权重顶点数与权重和/未绑顶点/非归一化权重/零长骨/左右镜像/包围盒/缩放是否已应用；**自动剔除 Blender 导入器造的 42 顶点 Icosphere 显示形状**（文件里没有它，别当杂物球）。op=status（纯读）· run（写派生 .js 给页吃 ⇒ filesystem_write 门在处理器层）· check（只对账 .js 与 GLB 的 sha）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap rig_audit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `rig_fix`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：绑骨修复（Blender 4.2 · 本地 · 零付费）：**自动定轴**（三轴跨度取最大为身高轴，不再假设 Y-up/Z-up）· 补权重 · 归一化 · 去杂物（可选）· 转台照 · **六条硬判据**（单网格+蒙皮 / 无 42 顶点杂物球 / 量具自证换算 0.3~3 / 身高 1.720±0.02 在**文件空间**量 / 未绑顶点归零 / 蒙皮网格被骨架带动）。⚠️ 它**不重做动作修正**（出件后必须再跑 anim_fix，否则腿折在胯上、手举过头顶 —— 2026-10-19 实栽）。op=status/plan（纯读）· run（写 outputs/rig-fix/ ⇒ 要票）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap rig_fix '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `scene_anchor`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：场景锚定只读骨架：8 大类场景 + 灵魂四要素 + 钩子锚场景不锚情绪（作品是为场景做的）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap scene_anchor '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `shot_director`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**镜头导演**（主人令 2026-10-16：把 **Seedance 2.0 Skill OS** 蒸进来）：蒸自 **Emily2040/seedance-2.0**（**MIT** · v6.7.0）的思想—— 视频模型 = **一个从没见过你的剧组**（不能提问 · 按字面渲染 · 只做第一个动作 · 跳剪忘光位站位 · 不告诉它就不移镜）。**十大坑 → 十修法**：字面但不死板（**感觉的一个普通词 + 一个物理锚**）· **一镜一动作** · 道具写手 · **每镜锁定句**（光/人/站位）· 位置与地理每镜重述 · **镜头表先于散文** · 提交前合规预筛（分类器拒的是词不是意图）。不代付生成费。op=plan/shot_table/rules/punctuation/moderation/evidence/check/route（**全只读·零作用域·不出网**）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap shot_director '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `showcase_ops`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**作品解剖与展示**（主人令 2026-10-16：让每一次的作品都能完美的展示能力）：蒸自 **wheresryan22/anatomy**（MIT · 13,459 星 · agent-skill）的**思路与架构**—— 「**用一个真会动的实物来讲解一个概念**」：概念→会动的实物（例：cache key⇒弹子锁）→**几十个小而精确的零件**（SVG+WebGL+3D）→**带标题/提示/实时读数的画框**→指针键盘下平静地动→**放大每个关节自检**→**读数同源**（图里每个数字都来自驱动零件运动的同一模型）。我们加三条护栏：署名必在 · 未验标未验 · 读数必须可指回。op=concept/parts/frame/motion/readout/selfcheck/check/route（**全只读·零作用域**）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap showcase_ops '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tentacle_comfy_bridge`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**第 1530 根触手 · ComfyUI 桥**（主人令 2026-10-11「ComfyUI 不是生图工具，是第 1530 根触手的底座」）：把外部 ComfyUI 当**贴图工厂／概念工厂**用，并**双向绑定** —— ① 工作流 = 契约（`state/comfy_workflows/*.json`，ComfyUI 原生节点连线格式）；② 产物**先过闸才允许落盘**（闸口径与 `comfy_native.gate_image` 同源：最短边/格式/非空/可解码）；③ **溯源自证**：workflow_sha256 + seed + ckpt_hash 全部落 `store/tentacle_comfy/ledger.jsonl`（只追加）。出网硬钉照抄 `comfyui_surface`：只许本机 http + 主机白名单 + 端口 8188 + 路径前缀 + 拒重定向。**不在位就如实回 needs_dependency（绝不假装出图）**；断连判据同源（节点数 < 900 = 断连）。op=status/queue/workflows/verify
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tentacle_comfy_bridge '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `tripo`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：Tripo3D 三维生成（文/图→3D 模型 + 自动绑骨 + 动作库）：status/balance/text_to_model/image_to_model/multiview_to_model/upload_file/rig_check/rig/animate/wait_task/full_pipeline。**F12 补齐** —— 同上，有 run() 却没在册。**safe=false**：出网且花平台积分（积分不代持、不代刷）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap tripo '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `ui_kit`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**UI 组件库的口**（吞天吞来的素材 → 可检索 · 可取件 · 读数如实）。素材：`uiverse-io/galaxy`（**MIT** · ★13478 · 3802 件 · 11 类目）落 `_upstream/galaxy`。常用说法：UI 组件 / 按钮 / 卡片 / 加载动画 / 开关 / 输入框 / 表单 / 复选框 / 工具提示 / 通知 / 悬浮提示 / 图案 / 霓虹 / 渐变 / 毛玻璃。op=status/build/find/take/where：`build` 扫素材提语义（类目·可见文案·效果标签·主色·外链数）落 `store/ui_kit/index.jsonl`（只追加）；`find` 人话取件（**命中 0 就是 0，不硬塞**）；`take` 拷一件到 `outputs/ui-kit/` 并**如实报它带几条外链**。铁律：**零出网 · 零执行**（不跑组件里任何东西）· **不改 `_upstream/galaxy/**` 一个字节** · 效果标签只认代码里真出现的特征串。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap ui_kit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `ui_render`

- **域**：`creation`（创作）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：受控界面渲染（json-render #09 蒸馏）：模型只产 spec，组件必须命中白名单；未知组件/未列动作/脚本/外链一律拒 ⇒ 先 check 再 render；产物自包含零脚本零外链；指标必须带 src（没带的照渲但标红）。op=spec/check/render/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap ui_render '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `zimage_rewash`

- **域**：`creation`（创作）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：洗图流水线（看图→反推提示词→重绘→放大）：**放大环已可用**（ffmpeg lanczos+unsharp，零依赖）；反推环**已接线**（2026-10-15 起 zimage_rewash_cap 走 vision 通道；2026-10-16 增形式化反推件 tools/codex-scripts/img-reverse.py）；**语义反推**仍待外部理解通道（teamorouter 401 / 本地 8111 未监听）——缺什么就写什么；重绘环**未接线**（未装 ComfyUI；pollinations img2img 需公网可达图 URL）；含降噪强度口径表 0.15→0.85 四档。⚠️ **2026-10-13 收敛（主人令「每一个调节都要触手可控」）**：本位是**历史腿**，主腿 = `comfy_native.upscale_4k`（PIL LANCZOS + USM；`vision_print.polish` 的清晰度腿走它）。收敛**分两类做、不搞假统一**：① **几何旋钮真统一** —— `scale`（新名，倍数）＝旧名 `factor`，且都接受 `size`（目标绝对宽，按源图宽换算成倍数走同一条路）；两个名字同时给且不等 ⇒ **fail-closed**。② **锐化旋钮不统一、且显式拒** —— 本位只有 `unsharp`（**ffmpeg unsharp 滤镜的 amount**），主腿是 `sharpen`（**PIL USM 的 percent 比例**），**两个算法两个量纲**；把 `sharpen` 传给本位 ⇒ **当场 fail-closed 并指路主腿**（改名冒充＝假统一，更害人）。参数判在**过门之前**（参数错不消耗授权）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap zimage_rewash '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
