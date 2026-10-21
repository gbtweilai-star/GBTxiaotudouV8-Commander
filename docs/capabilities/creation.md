# 创作 · `creation`（54 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `anatomy_figures` | **需授权** | — | Anatomy 等轴详解图（外部成熟件 · 主人 2026-10-19 指名抓取「这两个能力不就可以完美补齐缺失了吗」 · 上游 wheresryan22/anatomy · MIT · 15.9k★）：**把一个概念做成一台真机器**的等轴 SVG 图（零件级 40~150 件… |
| `anim_audit` | 只读 | — | 动画体检（**纯读免门**）：直接解析 GLB 的 animation 通道，把每根骨「首帧 vs 静止姿势」的夹角从大到小排出来（当初就是它量出髋骨被扭 177.2°/176.3°）。阈值 --threshold 默认 30°，all 打全量。op=status/run/whe… |
| `anim_fix` | **需授权** | — | 动画手术（GLB 层面 · **六条自检，不过就不写盘**）：把点名骨头的 rotation 轨道归位到静止姿势（髋骨 LeftUpLeg/RightUpLeg）或写成**量出来的**姿势（手臂组的值来自闭环解算，不许手搓）；平移/缩放通道一律不碰；自检=命中通道/采样形状/四元… |
| `art_brief` | **需授权** | — | **作品策划位**（人话一次问，四路知识同时到位 + 给出可直接照抄的出片命令）。四路： `ui_kit` **可渲件**（纯 HTML/CSS，能直接进渲染器）· `bits_kit` **参考件**（react-bits 的 React 实现，**只读来学**——许可禁止再分… |
| `art_chain` | **需授权** | — | **作品链**（一条命令：挑组件 → 取件 → **真渲** → 调优，每步带读数）。① `ui_kit.find(q)` 挑头一件（带外链数）② `ui_kit.take` 拷进 `outputs/art-chain/`③ 调 `render_page.py` **真 Chro… |
| `bits_kit` | 只读 | — | **动效组件图鉴的口**（人话 → react-bits 哪个组件 · 干什么 · **源码在哪 · 会不会联网 · 依赖什么**）。素材：`DavidHDev/react-bits`（**MIT + Commons Clause v1.0** · ★49005 · 216 组件… |
| `blender` | **需授权** | — | 三维电影引擎（Blender 4.2.16 LTS·本机）：Cycles 电影级光追/EEVEE 实时/几何节点/VSE 剪辑/bpy 全脚本自动化；3D 场景（义庄/血月/墨线阵）、摄影机动画、GPU 渲染；status 免门，一切 run（渲染/脚本/导出）过 filesys… |
| `brand_outro` | 只读 | — | 品牌片尾只读渲染：署名/自述/致谢三层 + 四条红线（署名不造假·致谢不套话·承诺可追溯·观众不当流量） |
| `cad_distill` | 只读 | — | **蒸馏件**（不是外挂）：把吞入件 neka-nat/freecad-mcp（MIT · 2833星 · Python：「Control FreeCAD from Claude Desktop and other MCP clients … run FEM analyses」）… |
| `cadgen` | **需授权** | — | **本机 CAD 链的口**（2026-10-13 建位）：只调真件 `cadgen`，不手搓几何。常用说法（人这么问就命得中）：建模 / 零件 / 三维 / 模型渲染 / 渲染 / 出图 / 看图 / 看件 / 工程图 / 导出 STEP / STL / 3MF / GLB /… |
| `code_art` | 只读 | — | 代码艺术内核（只读骨架）：INDEX/SEED/CANVAS/LAYER/EXPORT 五原语；无种子不许导出 |
| `comfy_cloud` | **需授权** | — | **云卡 ComfyUI 触手**（主人令 2026-10-13「她不需要 ComfyUI，直接使用触手就可以生产出高质量视频」）：把云卡上的 ComfyUI **包成她自己的器官**——她不用知道 ComfyUI 是什么。本机到 8188 没路（实测代理 404），所以所有调用… |
| `comfy_forge` | 只读 | — | **创作融合台**（主人令 2026-10-15「借助秋叶版的节点来融合她的创作能力」）：把秋叶版 ComfyUI 已抓下的 **962 把节点（带完整输入 schema）** 按**创作用途分族**，并说清每族饲哪些创作能力位（生图/控图预处理/视频/音频/3D/模型补丁）。读… |
| `comfy_native` | 只读 | — | **GBT天真** —— 触手自己的 ComfyUI 能力（主人命名 2026-10-11「触手的 ComfyUI 我们取名叫 GBT天真」）。常用说法（人这么问就命得中）：**放大 / 锐化 / 高清 / 4K / 图片放大 / 传统放大 / 洗图 / 出图放大**。（触发词前… |
| `comfyui` | 只读 | — | ComfyUI（秋叶整合版）全控（主人令 2026-09-27「这个必须也是一个不漏的双向绑定，才能实现无限制审查生产」）：**966 个节点**（每把一把键）+ 11 个 API 端点 + 14 个启动开关 + 模型清单（checkpoints/loras/controlnet… |
| `console_pages` | 只读 | — | 工作台页面渲染器：把 `console_hub` 的真读数**内联**进页面（渲染产物，file:// 直开）——Bento 自定义工作台（9 部件/拖拽编排/布局记忆）· 触手 3D 全景（域环→能力节点→绑定弧→运行脉冲，签名元素占首屏≥1/5、有光、字不歪）· 每工作流独立… |
| `create` | 只读 | — | 创作出口：创作意图/产物登记 ＋ **仅限 outputs/ 的文本写入（已接线：gbt_allinone/file_operation.py，policy 挂 filesystem_write）**；**网络出口**待接线（如实报 pending、不发网络请求）、覆盖必带 co… |
| `creation_camp` | 只读 | — | 创造营编排（「AI 视觉创造营」形式蒸馏）：**主题 → 逐日营计划**——7 天基准节奏（开营定题→采样风格→构图分镜→批量出图→修饰选片→编排成片→展陈复盘），每天三件（任务/产出物/验收点）。**零网络零 LLM**（确定性）；点名的能力位**现读注册表**，缺的落「缺口」… |
| `design_atlas` | 只读 | — | **设计与审美图鉴的口**（吞天吞来的外部手册 → 人话找到"该读哪一节"）。素材：`flash-hero/GOATED-UI-SKILL`（**MIT**）的 18 份手册（component-recipes / webgl-shaders-3d / interactions… |
| `dh_asset_gate` | 只读 | — | 数字人资产八条闸（**纯读免门 · 一条命令验完**）：① 单网格单蒙皮 ② 没有 42 顶点杂物球 ③ 身高 1.720±0.02（**在文件空间量 POSITION 的 Y 跨度**，不在 Blender 的 Z 里量）④ 无死顶点 ⑤ 髋骨没被扭（<0.5°）⑥ 手臂垂放（… |
| `dh_brain` | 只读 | — | 数字人本体（只读能力位·2026-10-08 主人点名「元数据没接入」补齐）：把她（数字人）的**元数据经统一门暴露**——op=status/spec/actions/voice/metadata/health。op 一律**现读单一真源**（state/digital-hum… |
| `dh_pose` | **需授权** | — | 数字人动作控制（主人令 2026-10-13「触手化作骨架操控数字人的所有动作」+「连带手指脚趾都要绑骨」）：`status` 读现状 · `semantics` 读 42 条「意图→骨/轴/符号」语义表 · `compile` 把人话（抬臂/屈指/转身…）编译成骨角度 JSON… |
| `dh_realism` | 只读 | — | 数字人逼真度位（只读骨架）：**把专业流程固化成可机检的能力**。来源=Eurographics 2026 STAR《How to Build Digital Humans? From Priors to Photorealistic Avatars》（CGF 45(2)·Met… |
| `diagram_distill` | 只读 | — | **蒸馏件**（不是外挂）：把吞入件 wheresryan22/anatomy（MIT · 7551★ · 零依赖 Node）的 **craft 取法**提炼成我们自己的**概念物化图判据**：①概念物化（先把抽象概念发明成一个「它怎么转就是这个概念」的物理机构）②单一数源（图上… |
| `dl_forge` | 只读 | — | 3D 锻造融合位（只读骨架）：**秋叶节点 × 原生触手 × 专业标尺 三合一**。主人令「把学到的跟秋叶版的哪些节点以及契约，和我们的原生触手融合，实现原生能力也能做出高级作品和 3D 建模，都要达到专业水准」。**八段链**：①形象进件(控图预处理) ②图生3D ③网格(体素… |
| `drama` | 只读 | — | 剧本转分镜/拆分镜/分镜/短剧/故事板/剧本理解：剧本 → 结构化镜头表（景别·运镜·时长·情绪·角色位置·描述），字段齐全度与时长和逐条如实报；确定性路径离线只做切分，语义路径走她的模型通道，两条不互相冒充 |
| `emotion_projection` | 只读 | — | 情感投射只读骨架：叙事四问 → 投射细节 → 四项校验；『身临其境』只有人能判 |
| `filmkit` | **需授权** | — | 柔性影片产线（清单制·任意场/镜增删重制·主人令 2026-09-26）：manifest.json 为唯一真相（场=音频+3镜prompt，镜=图+运镜）；list/gen/seg/build/add/rm 六命令；产出自动绑触手（asset_bindings 台账）；跳过/指… |
| `flow_canvas` | 只读 | — | 工作流画布（蒸馏自 2026-09-28 主人给的周榜卡 Langflow 155.3k★，只取**可视化架构**，不引拖拽编辑器）：工作流定义 → 图（nodes/edges，数据只走引擎正规出口 `engine.list_workflows()`，R-H99b，不偷读 sto… |
| `forge_mastery` | **需授权** | — | **节点即触手·专业生产与自我递归**（主人令 2026-10-16）：主人原话「ComfyUI 的每个节点就是一根触手，**根本不需要 ComfyUI 本体**；把这项原生能力发挥到极致，懂所有专业生产能力与完美作品，每次使用都要自我评判哪里不足，**无限制自我递归**」。落法… |
| `genoffice` | **需授权** | — | 办公文档（GenOffice **蒸馏版** · 本地 CLI 0.10+）：info/pdf/guide/capabilities + convert/create/merge/slides/sheet/docs/render **全部接通**（文档处理全本地、零云依赖）；se… |
| `gs_h3` | **需授权** | — | GS-prompt-extend 提示词工作台接线（三节点一个不差）：模型加载器/提示词工作台/模型卸载器 → op=loader/workbench/unload；H3 规则与组装零依赖可跑（rules/compose），扩写走我们的模型链（external_llm）不必下 G… |
| `image_scout` | 只读 | — | **美图精准抓取**（主人令 2026-10-17「去精准抓取美图能力给她注入」）：只做"找对图+把关质量与许可"，不做下载/写盘。多源（Openverse 免钥匙 CC 系 · Unsplash/Pexels 有钥匙才用）· 质量门槛（min_width/min_height/… |
| `intake_kit` | 只读 | — | **外部件接入图鉴**（七件 · 七步法全走）：身份 · 许可 · **只读体检读数** · 知识面在哪。素材落 `_upstream/`：`motionsites.ai`（65 条设计提示词）· `impeccable`（设计语言系统 · 24 份 SKILL）· `hyper… |
| `lobehub` | 只读 | — | LobeHub 桌面端（Electron 2.2.18）全控 —— 主人令 2026-09-27「把 LobeHub.lnk 做成**可执行的插件**装到工具区，功能是真的多，**只要是可控制的都要绑上**」：**七大面 76 把可控制键**（设置 23 + **可控制按键 4*… |
| `machine_distill` | 只读 | — | **蒸馏件**（不是外挂）：把吞入件 AirsupHQ/machine-skill（MIT · 91星 · three.js · 无构建步）的**取法**提炼成我们自己的**求解器驱动可视化判据**：①每帧真解不查表（Brayton/火箭室/Cp(λ,β)/Darcy… 每台机器… |
| `machine_film` | **需授权** | — | Machine 光写实仿真成片（外部成熟件 · 主人 2026-10-19 指名抓取 · 上游 AirsupHQ/machine-skill · MIT）：**一句话 → 一台光写实可交互三维真机（单文件 HTML）→ 28 秒成片（MP4）**。真尺寸（米）/真材料（PBR 金… |
| `motion_kit` | 只读 | — | **动效引擎的口**（人话 → anime.js 的真 API，并**本机原生真跑**证明引擎可用）。素材：`juliangarnier/anime`（**MIT** · ★73546 · animejs v4.5.0 · **67 导出**）落 `_upstream/anime… |
| `music_auto` | **需授权** | — | **音乐自动化**（主人令 2026-10-16：把 Folia 蒸馏到音乐自动化里）：蒸自 **chthollyphile/folia-major**（AGPL-3.0，**只蒸思想不搬代码**）。核心不是做播放器，是**四条时间轴对齐**：歌词 · 音频 · 主题（配色）·… |
| `music_publishing` | 只读 | — | AI 音乐发布平台三层只读归位（生成端/Agent 原生端/分发端）；全部标『未核实』 |
| `omni_arm` | **需授权** | — | Omni-Arm（主人 2026-10-19 六件设计稿的实现版）：**22DoF 手 + 9 骨手臂 + 8 段触手 = 40 骨**，真几何（1080 顶点）/真蒙皮（每顶点权重和=1）/真 GLB，Blender 4.2 本地建件零付费。设计稿归档在 `vendor/omn… |
| `one_shot` | 只读 | — | 一句话 → 全链计划（主人令 2026-09-27「想什么就能生产什么画面」）：把一句话翻成产线输入 ——节奏词→BPM（紧凑120/常规100/舒缓80）· 时长词→分钟 · **帧率由 BPM 反推**（每拍帧数必须整数）·题材词→调色（走 filmgrade.INTENT_… |
| `pod_link` | **需授权** | — | **云卡触手**（她自己的传输器官：本机 ⇄ GPU 卡 · 在卡上跑命令 · 看卡状态）。op=status/ls/up/down/run/where：`status` 读卡清单（id/状态/价/卷/端口/公网IP）+ Jupyter 通不通；`ls` 列卡上目录；**`up`… |
| `render_evolution` | 只读 | — | 渲染进化内核（只读骨架）：五原语 + 三闭环 + 六红线；帕累托前沿机器画、人点 |
| `rig_audit` | **需授权** | — | 绑骨体检（Blender 4.2 · 本地 · 零付费）：DCC 级量骨架/骨数/层级深度/每骨权重顶点数与权重和/未绑顶点/非归一化权重/零长骨/左右镜像/包围盒/缩放是否已应用；**自动剔除 Blender 导入器造的 42 顶点 Icosphere 显示形状**（文件里没有… |
| `rig_fix` | **需授权** | — | 绑骨修复（Blender 4.2 · 本地 · 零付费）：**自动定轴**（三轴跨度取最大为身高轴，不再假设 Y-up/Z-up）· 补权重 · 归一化 · 去杂物（可选）· 转台照 · **六条硬判据**（单网格+蒙皮 / 无 42 顶点杂物球 / 量具自证换算 0.3~3 /… |
| `scene_anchor` | 只读 | — | 场景锚定只读骨架：8 大类场景 + 灵魂四要素 + 钩子锚场景不锚情绪（作品是为场景做的） |
| `shot_director` | **需授权** | — | **镜头导演**（主人令 2026-10-16：把 **Seedance 2.0 Skill OS** 蒸进来）：蒸自 **Emily2040/seedance-2.0**（**MIT** · v6.7.0）的思想—— 视频模型 = **一个从没见过你的剧组**（不能提问 · 按… |
| `showcase_ops` | **需授权** | — | **作品解剖与展示**（主人令 2026-10-16：让每一次的作品都能完美的展示能力）：蒸自 **wheresryan22/anatomy**（MIT · 13,459 星 · agent-skill）的**思路与架构**—— 「**用一个真会动的实物来讲解一个概念**」：概念… |
| `tentacle_comfy_bridge` | 只读 | — | **第 1530 根触手 · ComfyUI 桥**（主人令 2026-10-11「ComfyUI 不是生图工具，是第 1530 根触手的底座」）：把外部 ComfyUI 当**贴图工厂／概念工厂**用，并**双向绑定** —— ① 工作流 = 契约（`state/comfy_w… |
| `tripo` | **需授权** | — | Tripo3D 三维生成（文/图→3D 模型 + 自动绑骨 + 动作库）：status/balance/text_to_model/image_to_model/multiview_to_model/upload_file/rig_check/rig/animate/wait_t… |
| `ui_kit` | 只读 | — | **UI 组件库的口**（吞天吞来的素材 → 可检索 · 可取件 · 读数如实）。素材：`uiverse-io/galaxy`（**MIT** · ★13478 · 3802 件 · 11 类目）落 `_upstream/galaxy`。常用说法：UI 组件 / 按钮 / 卡片… |
| `ui_render` | 只读 | — | 受控界面渲染（json-render #09 蒸馏）：模型只产 spec，组件必须命中白名单；未知组件/未列动作/脚本/外链一律拒 ⇒ 先 check 再 render；产物自包含零脚本零外链；指标必须带 src（没带的照渲但标红）。op=spec/check/render/wh… |
| `zimage_rewash` | **需授权** | — | 洗图流水线（看图→反推提示词→重绘→放大）：**放大环已可用**（ffmpeg lanczos+unsharp，零依赖）；反推环**已接线**（2026-10-15 起 zimage_rewash_cap 走 vision 通道；2026-10-16 增形式化反推件 tools/… |

> 表格里是**摘要**（超过 140 字截断）；完整原文见 [`data/capabilities.json`](../../data/capabilities.json) 的 `desc` 字段。

---

返回 [能力总表](../03-capabilities.md)
