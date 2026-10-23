# 数字人 · 完整流水线（一套到底 · 阶段契约 + 机检门 + 回退）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份文件回答一个问题：从一张参考图到"能被网页运行时驱动、能被验收"的数字人，一整套流程长什么样。**
> 不写片段、不写"某一步的技巧"——每一环都必须有 **输入契约 / 输出契约 / 机检判据 / 失败回退**。
> 编排器：`tools/digihuman/pipeline.py`（单一入口，阶段可单跑，账本落盘）。

---

## 0. 为什么是"一整套"：热门项目的共同骨架

抓取并蒸馏后的共同结构（**每个成熟项目都是这条链，只是工具不同**）：

| 来源 | 它贡献的"整套"骨架 |
|---|---|
| **VRM / VRMC_vrm 1.0**（pixiv/UniVRM 生态的事实标准） | **交换格式契约**：`humanoid` 骨名与父子关系固定（hips→spine→(chest)→(upperChest)→(neck)→head；四肢；手指；左右眼/颌）、`springBone`（stiffness/dragForce/gravityPower/hitRadius）、`expressions`、`meta`（授权/署名） |
| **pixiv/three-vrm** | **Web 运行时契约**：`VRMLoaderPlugin` 载入 → `VRMHumanoid` 语义骨访问 → `VRMSpringBoneManager` 每帧更新 → `VRMExpressionManager` 表情权重；渲染与业务状态机解耦 |
| **Ready Player Me / Meshy / Tripo 等产品线** | **产品化分层**：素材层 → 生成层 → 资产层（LOD/贴图）→ 装配层（骨架/动画）→ 运行时层 → 交付层；每层有明确的**产物与体积/面数预算** |
| **Blender headless / gamedev MCP 工具链**（如 veilbreakers 类工具集：rigging/topology/texturing/animation/visual testing 各自的 server） | **自动化契约**：每个能力是**无头可调用的阶段**，输入输出都是文件，可被编排器串起来、可回归 |
| **Mixamo / 动捕重定向线** | **动画契约**：标准人形骨架上的 clip 可互换（重定向），循环类动画必须闭合 |
| **Eurographics STAR《How to Build Digital Humans》** | **质量分层**：几何真实感 / 材质真实感 / 运动真实感 / 交互真实感 —— 四条腿都要，缺一条观众就出戏 |

⇒ **共同的"整套"结论**：一条流水线的强度不取决于某个环节多强，而取决于**每两个环节之间有没有硬契约**。
契约松，就会出现"看着还行但进不了下一步"；契约硬，任何环节都能替换工具而链条不断。

---

## 1. 阶段总表（14 阶段 · 这是"一整套"）

| # | 阶段 | 输入契约 | 输出契约 | 机检判据（不过就停） |
|---|---|---|---|---|
| **S0** | 素材与合规 | 参考图（正面全身/半身清晰） | `raw/S0/ref.png` + `manifest.json`（来源/授权/署名） | 图有效（>512px、人脸可检测）；manifest 必填三字段 |
| **S1** | 几何生成 | ref.png | `geometry.glb`（带贴图） | 文件存在；顶点>5万；bbox 合理（高/宽 ∈ [1.5, 9]） |
| **S2** | 姿态规范（T/A-pose） | geometry.glb | `pose.glb` + 姿态读数 | 双臂近水平（±12°）· 双腿直立 · 正面朝向；**五条全过** |
| **S3** | 重拓扑 / 分部位 LOD | pose.glb | `lod_hero.glb` · `lod_mid.glb` · `lod_rt.glb` | hero 保密度（脸≥15万面）· rt ≤2万面且 <12MB（面板路由上限） |
| **S4** | UV + PBR 贴图 | 各 LOD | 每档 3 张图（baseColor/normal/ORM）+ UV 校验 | 贴图分辨率≥1024；UV 无重叠（抽样）；材质槽位解析正确 |
| **S5** | 标准骨架（VRM Humanoid） | 网格 + 角色比例 | `skeleton.json` + 骨名映射表 | **必需骨齐全**（hips/spine/head/双上臂/双下臂/双手/双大腿/双小腿/双足 = 15 必需，加 chest/neck/肩/趾等推荐）· 无环 · 平移相对父节点 |
| **S6** | 蒙皮权重 | 网格 + skeleton | `skinned.glb` + 权重读数 | 权重和 = 1.0000（每顶点）· JOINTS/WEIGHTS 齐 · 布料归髋等区域规则 |
| **S7** | 表情 / BlendShape | skinned.glb | `expressions`（preset: happy/angry/sad/relaxed/surprised + 眨眼/口型） | 每个表情有绑定且权重可驱动（0→1 无爆点） |
| **S8** | 动画 / 重定向 | skinned.glb + clip 源 | `anim_idle.glb` · `anim_walk.glb` … | **循环闭合误差 ≈0**；步幅/身高 ∈ [0.5, 0.8]；关节旋转无翻转 |
| **S9** | 次级动力学 | skinned.glb + 区域判据 | springBone 链（发/裙/带） | 每链有 stiffness/dragForce/gravityPower/hitRadius；区域内顶点已重权且根部与父骨混权；**父骨有真实激励**（否则摆动为 0） |
| **S10** | 标准格式封装 | 上述全部 | `avatar.vrm`（或 GLB + extensions） | 扩展合法：`VRMC_vrm.humanoid` 全必需骨、`VRMC_springBone`、`VRMC_vrm.expressions`、`meta`（署名/授权）；引用检查通过 |
| **S11** | Web 运行时 | avatar.vrm + 页面 | 页面（状态机 + 渲染 + 交互） | **审美审计 P0=0**；真浏览器 `__painted=true`；状态切换无硬切；HUD 读数在场 |
| **S12** | 验收（客观 + 人眼） | 运行时页面 + 各档资产 | `STATUS.json` + 验收图 + 读数 | 四条腿分别有读数：几何（面数/密度）· 材质（贴图/材质槽）· 运动（循环闭合/步幅/弹簧偏角）· 交互（状态机/帧率） |
| **S13** | 发布与账本 | 全部产物 | `manifest.json` + `ledger.json` + 署名 | 每个产物有哈希、来源、许可；**废物不许上线**（空文件/临时文件/无入口） |

**低模/高模/中景三轨**是同一套骨架的三次装配（`autorig-transfer.py` 迁移骨架），不是三条独立流水线 —— 这保证了"一套流程出三个交付档"。

---

## 2. 阶段间的硬契约（真正决定成败的地方）

1. **姿态契约**：S2 的五条(T-pose)是硬门。臂展≈身高、无遮挡 —— 它决定 S5 骨架能否靠启发式正确落点。
2. **尺度契约**：所有 LOD 必须在**同一世界尺度**下（模型高 = 1.0 归一），否则骨架迁移与动画步幅全错。
3. **骨架契约**：S5 产出的 `skeleton.json` 是唯一真相源；**绝不在下游重建**（层级只由 PARENT 表重建，不复制索引）。
4. **索引契约**：`JOINTS_0` 存的是 **joints 数组下标**，不是节点号（VRM/glTF）；`inverseBindMatrices[i]` 与 `joints[i]` 一一对应。
5. **容器契约**：中间产物**一律二进制**（GLB/PLY）。文本格式（OBJ）在大量顶点时会静默错位 —— 我们实测过整头被毁。
6. **贴图槽契约**：按材质槽解析（`baseColorTexture.index → textures[i].source`）；`images[0]` 通常不是 baseColor。
7. **体积契约**：Web/面板档 <12MB（客户端路由硬上限，实测 26.88MB/61MB 均 500）；出图档不限但走本地。
8. **运动契约**：循环动画闭合误差必须≈0；**次级动力学的可见性取决于父骨激励**（激励不足时先修动画，不要调弹簧参数）。

---

## 3. 门（机检 · 每条都能跑）

| 门 | 命令（本仓） | 通过判据 |
|---|---|---|
| GLB 引用合法性 | `python tools/codex-scripts/validate-glb.py <f>` | 「引用检查: 全部合法」 |
| 骨架四门 | `python tools/codex-scripts/rig-gate-check.py <f>` | 关节≥20 · 骨名可映射 · 绑定姿势 T≈0° · JOINTS/WEIGHTS 齐 |
| 循环闭合 | `anim-make.py` 输出 | 每条 clip ≈0.00000 |
| 体积/路由 | `Invoke-WebRequest -Method Head <url>` | HTTP 200（<12MB） |
| 审美 | `python tools/codex-scripts/audit_aesthetic.py <html>` | P0 = 0 |
| 画面真出 | 页面 `__painted` | 截到非空画面 |
| 客观读数 | `measure-clarity.py` / `compare-mesh.py` | 分辨率/梯度/面数/贴图尺寸 |

---

## 4. 回退策略（每一环都要有 Plan B）

| 环节 | 主路 | 回退 |
|---|---|---|
| S1 几何 | Tripo `make --then texture` | 换模型/多视图；或接受更低真实感 |
| S3 减面 | 服务端 `decimate` | **本地 QEM（pymeshlab 走 PLY 通道）**；再不行 DCC(Blender) |
| S5 骨架 | 本地启发式 | T-pose → Mixamo 自动绑骨 |
| S7 表情 | 网格 morph | 材质/贴图驱动（省几何） |
| S8 动画 | 自建关键帧 | 动捕重定向 / 动画库 |
| S10 格式 | VRM 1.0 | 纯 GLB + 自定义扩展（降低互操作性） |
| S11 运行时 | three-vrm | 纯 three.js + 自定义 springBone（本仓已实现） |

---

## 5. 与"热门项目"的差距清单（诚实版）

| 维度 | 他们 | 我们现状 | 下一步 |
|---|---|---|---|
| 交换格式 | **VRM 1.0**（骨名/弹簧/表情/授权四件套） | 自建 GLB + 自写 springBone | **加 S10 封装层**（把现有骨架映射到 VRM 骨名） |
| 表情 | BlendShape/ARKit 52 | 无 | S7 从 0 做（先用 5 个 preset） |
| 动画来源 | Mixamo/动捕库 + 重定向 | 自建 2 条 clip | 接重定向（同骨架即可换库） |
| 工具链 | 每能力一个无头 server + 编排 | 脚本集合 + PowerShell | **本次交付：Python 单编排 + 阶段注册表** |
| 质量门 | CI 化、逐阶段可回归 | 手工跑 | 账本 + `verify` 全阶段扫 |

---

## 6. 出处与归属

- VRM 规范（humanoid/springBone/expressions/meta）：[vrm-c/vrm-specification](https://github.com/vrm-c/vrm-specification) · [humanoid 原文](https://raw.githubusercontent.com/vrm-c/vrm-specification/master/specification/VRMC_vrm-1.0/humanoid.md)
- Web 运行时：[pixiv/three-vrm](https://github.com/pixiv/three-vrm) · [VRM 官方站点](https://vrm.dev/en/univrm/springbone/univrm_secondary/)
- 工具链范式：[Sharks820/veilbreakers-gamedev-toolkit](https://github.com/Sharks820/veilbreakers-gamedev-toolkit)（rigging/animation/topology/texturing/visual-testing 各一无头 server）
- 自动绑骨服务：[animede/rig-service](https://github.com/animede/rig-service)
- 学术蒸馏：*How to Build Digital Humans? From Priors to Photorealistic Avatars*（Eurographics STAR 2026）→ 本仓 `holo_pet/assets/digital-human/PIPELINE.md`
- 本仓实证：`references/pitfalls.md` §1–§15（29 条，全部带渲染/读数留档）

---

## 7. 模型无关（Owner 2026-09-22 定：「蒸馏成用什么模型都能完成，而不是规定模型」）

**原则**：**契约与门固定，模型/服务可换**。

- 阶段只声明**能力位**（capability），不写死厂商：
  `geom.generate` · `geom.texture` · `mesh.decimate` · `mesh.convert` · `mesh.spring` · `skin.auto` ·
  `rig.auto` · `anim.make` · `anim.retarget` · `expr.make` · `pack.vrm` · `render.shot` · `gate.check`
- **后端注册表**：`tools/digihuman/providers.py` —— 每个后端声明 `caps / probe(探活) / auth / cost / notes(坑) / cmds(命令模板)`。
  已登记：**local**（本仓脚本）· **tripo** · **meshy** · **hunyuan3d** · **comfyui**（插件即能力，如 SkinTokens）· **blender** · **mixamo**。
- **解析顺序**：显式指定（`--provider`）→ 配置（`.digihuman/config.json`，`use <能力位>=<后端>`）→ 注册表顺序 + 探活。
  都不行时**如实报"缺什么"并列出已试后端与原因**，绝不假装能跑。
- **换模型只改一行**：`pipeline.py use mesh.decimate=blender`；流水线其余部分（契约/门/账本）一律不动。
- **诚实注记写进注册表**（例：Tripo 的 `rig` 骨名无语义 ⇒ `rig.auto` 默认给 **local** 自建骨架；
  Tripo `decimate` 上限 2 万面 ⇒ 保 UV 减面应换 blender/pymeshlab(PLY 通道)）。

```powershell
$PY="C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe"
& $PY tools\digihuman\pipeline.py providers                 # 本机后端可用性 + 每个能力位会落到谁
& $PY tools\digihuman\pipeline.py run S3 --provider blender  # 指定后端（不可用会如实回退并说明）
& $PY tools\digihuman\pipeline.py use mesh.decimate=blender  # 固化到配置
```
