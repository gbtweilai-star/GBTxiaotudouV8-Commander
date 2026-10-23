---
name: digihuman-pipeline
description: 从一张参考图做出「清晰逼真的数字人」并绑骨、做动画、出验收图的完整本地流水线。适用于：图生 3D 数字人/角色、自动绑骨（人形骨架）、蒙皮权重、idle/walk 动画、GLB 校验与棚拍渲染、3D 资产验收读数。当用户提到数字人、虚拟人、avatar、绑骨、蒙皮、动作、GLB/glTF、低模高模、资产预览渲染时使用本技能。
---

# 数字人流水线（GBT 口径 · 本地可跑 · 每步带读数）

> 本技能固化了 2026-09-22 一整套实战：**图生 3D → T-pose → 减面 → 自建骨架 → 蒙皮 → 动画 → 棚拍渲染 → 门限验收**。
> 所有脚本在工作区 `tools/codex-scripts/`，编排脚本在本技能 `scripts/run-pipeline.ps1`。
> 专业流程来源：*How to Build Digital Humans? From Priors to Photorealistic Avatars*（Eurographics STAR 2026，Meta/TUM/Google/NVIDIA/ETH/清华）—— 蒸馏见工作区 `holo_pet/assets/digital-human/PIPELINE.md`。

## 何时用

- 要从**一张人物参考图**得到可用于面板/网页/出图的 3D 数字人；
- 要给已有网格**绑人形骨架**并验证（关节数/骨名/绑定姿势/权重四条门限）；
- 要做 **idle / walk 循环动画**并检查循环连续性、步幅；
- 要**渲染验收图**并给客观读数（而不是"看着还行"）。

## 前置条件（先自检，缺一条就停）

| 项 | 检查 | 说明 |
|---|---|---|
| Tripo CLI 已登录 | `tripo whoami` | 凭据在 `~/.tripo/config.json`（`api_key` 以 `tsk_` 开头）。**不要**用 `tcli_` 令牌，那是 CLI 登录令牌，接口不认 |
| Python 分工 | 见下 | **Playwright 脚本用 `python`**（3.12）· **图像/数值脚本用 `C:\Python310\python.exe -X utf8`** · gbt_allinone 用 3.14 |
| 本地服务 | `node plugins/gbt-master/tools/serve-digital-human.mjs` | 渲染验收需要它（8788）。用完**四步收尾** |
| 空闲内存 | ≥1GB | 大网格脚本必须分块（见踩坑） |

## 九个阶段（每阶段都有判据，不达标就停）

| # | 阶段 | 命令 | 判据 |
|---|---|---|---|
| 1 | 图生网格+贴图 | `tripo make <参考图> --then texture -o <out>` | 有 `model.glb`；顶点/贴图读数 |
| 2 | **转 T-pose** | `tripo generate image-to-image <图> --prompt "<T-pose 提示词>"` | 双臂水平·双腿直立·正面全身·无遮挡物·白底（**五条全过**才继续） |
| 3 | T-pose 建模 | `tripo make <Tpose图> --then texture` | 臂展≈身高（T-pose 实测） |
| 4 | 减面 | `tripo make <taskid> --then "decimate:10000,convert:fbx"` | 顶点降到 1–2 万；FBX 头 `Kaydara FBX Binary` |
| 5 | **量骨架** | `python tools/codex-scripts/autorig-skeleton.py <低模.glb>` | 22 关节；左右对称；落点吸附在网格实体上（出剪影叠加图） |
| 6 | **算权重+导出** | `python tools/codex-scripts/autorig-skin.py` | 权重和恒 1.0000；布料归髋；姿态测试形变无撕裂 |
| 7 | 门限复核 | `python tools/codex-scripts/rig-gate-check.py <绑骨.glb>` | 关节≥20 · 骨名可映射 · 绑定姿势 T≈0° · JOINTS_0/WEIGHTS_0 齐 |
| 8 | 动画 | `python tools/codex-scripts/anim-make.py` | 每条 clip **循环闭合误差 ≈0**；步幅/身高 0.5–0.8 |
| 9 | 渲染+验收 | `python tools/codex-scripts/shot-glb.py <glb> <out.png> <rot> [focus] [extra]` | HUD 读数 + 画面自检通过；`measure-clarity.py` 出客观读数 |

**低模/高模双轨**：低模（1–2 万顶点）用于实时/网页；高模（数十万）用于出图。两者用 `autorig-transfer.py` 共享同一套骨架（同一次生成 ⇒ 尺度比≈1，可精确迁移）。

## 一键编排

```powershell
pwsh -File C:\Users\ADMIN\.openclaw-autoclaw\skills\digihuman-pipeline\scripts\run-pipeline.ps1 `
     -Stage all -Input "C:\path\to\ref.png" -Name mychar
```
阶段可单跑：`-Stage tpose|model|decimate|rig|weight|anim|render|gate`；`-DryRun` 只打印命令。

## 🧭 一整套流程（14 阶段 · 单编排器 · Owner 2026-09-22 要求"别学一段一段的"）

> **完整契约（阶段/输入输出/机检门/回退/与热门项目差距）见 `references/full-pipeline.md`。**
> 单一入口：`python tools/digihuman/pipeline.py`（纯标准库，任何解释器可跑）

```powershell
$PY = "C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe"
& $PY tools\digihuman\pipeline.py map        # 阶段地图（输入/输出/命令/回退）
& $PY tools\digihuman\pipeline.py status     # 全链机检门 + 写账本 .digihuman/ledger.json
& $PY tools\digihuman\pipeline.py run S9     # 单跑某阶段（工具 + 门）
& $PY tools\digihuman\pipeline.py run S9 --dry
```

**阶段（S0→S13）**：素材合规 → 几何 → T-pose → 分部位LOD → UV/PBR贴图 → **标准骨架(VRM Humanoid)** →
蒙皮权重 → 表情 → 动画/重定向 → 次级动力学 → **标准格式封装(VRM 1.0)** → Web 运行时 → 验收 → 发布账本。

**实测现状（2026-09-22 · `status` 读数 10/14）**：
| 通过 | 未过（真缺口） |
|---|---|
| S1 几何 · S3 LOD(3.96MB<12MB) · S4 贴图 · S5 骨架 · **S6 权重（VRM 必需骨缺 0，权重和 1.0000）** · S8 动画(闭合 0.00000) · S9 弹簧骨 · S11 运行时 · S12 验收 · S13 账本 | **S0**（契约路径缺 ref.png·指到真实参考图即可）· **S2**（T-pose 五条需人眼）· **S7 表情未做** · **S10 VRM 封装未做** |

**关键发现**：自建的 `mixamorig` 22 骨**已能完整映射 VRM Humanoid 全部 15 根必需骨** ⇒ S10 封装主要工作是加
`VRMC_vrm.humanoid` / `VRMC_springBone` / `VRMC_vrm.expressions` / `meta` 四段扩展，不是重绑骨。

## 必须遵守的硬规则（血泪换来的）

1. **判据必须自证找到了目标** —— 自动 ROI 曾把 HUD 文字当人脸，整组读数作废。ROI 要检查肤色占比、排除 HUD 文字区。
2. **大网格（>10 万顶点）脚本必须分块 + float32** —— 曾用 `(n,4,4,4)` 张量打爆内存，宿主连子进程都起不来（`0xC0000142`）。
3. **glTF 层级里子节点平移必须相对父节点**；层级只由 `PARENT` 表**重建**，绝不复制索引（偏 1 ⇒ 自环 ⇒ 求解死循环）。
4. **GLB 块必须 4 字节对齐**（JSON 补空格、BIN 补零），且 `bufferView` 索引要写进**同一个 JSON 对象**（深拷贝后共享状态会写出越界索引）。
5. **贴图语义必须按材质槽位解析**（`baseColorTexture.index → textures[i].source`），不要假设 `images[0]` 是 baseColor（那通常是法线）。
6. **凡"求父链/世界坐标"都要带环保护**，坏数据要报错不能转死。
7. **渲染前先确认画面真的画出来了**（WebGL 会掉上下文）：页面暴露 `__painted`，截图工具等它。
8. **Tripo 自家 rig 过不了我们的门限**（实测 14 关节、骨名无语义）—— 走本地自建骨架，或 T-pose→Mixamo。

## 交付物命名约定

```
raw/phaseN/…           各阶段原始产物（含 tripo 任务号）
raw/rig/model-rigged.glb      低模绑骨（实时）
raw/rig/model-rigged-hi.glb   高模绑骨（出图）
raw/rig/skeleton.json         骨架定义（唯一真相源）
render/<角色>-<视图>.png       验收图
STATUS.json                   唯一状态源：读数/花费/缺口/下一步
```

---

## 🔴 默认执行路径（Owner 2026-09-22 定 · 不可省）

**任何任务都必须走「五维合一同步执行 + 万能插」，不许东一榔头西一棒子地单点调用。**

```powershell
$FIVE = "C:\Users\ADMIN\Desktop\GBT小土豆V8\tools\codex-scripts\five-dim.py"
$PY314 = "C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe"

& $PY314 $FIVE open  "<这一步要干什么>" [观察目标路径...]   # ① 开步（耳：先听清）
#  ……干活……                                                # ② 手：真做
& $PY314 $FIVE cap   <能力位> ['{"k":v}']                   # 万能插：一切能力调用走 run_task 唯一门
& $PY314 $FIVE close <step_id> "<证据1>" "<证据2>" ...      # ③ 眼+嘴：交证据说结论（证据不足判 partial）
& $PY314 $FIVE ruler                                        # ④ 健康：量无脑操作率 / 收步率
```

**铁律**：
- 五维 = `route → execute → verify → health → unify`（纵向）；四觉 = `耳(先听清)/眼(看现实)/手(真做)/嘴(说出结论含"没做到什么")`（横向）。**缺一条如实报 `needs_dependency`，绝不假装齐了。**

---

## ✅ 一整套流程的最终读数（2026-09-22 · round 7）

```powershell
$PY="C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe"
& $PY tools\digihuman\pipeline.py status        # 14/14（S2 需人工复核记录，见下）· 纯标准库 · 秒级
& $PY tools\digihuman\pipeline.py status --deep # 追加 **官方 three-vrm 运行时** 验收
& $PY tools\digihuman\pipeline.py providers     # 模型无关：能力位 → 后端 + 可用性
& $PY tools\digihuman\pipeline.py run S3 --provider blender   # 换后端 / 不可用则如实回退
# S2 是**人工复核门**（源码 run-pipeline.ps1:73）：机器只给代理读数，人看过图才落记录
& $PY tools\digihuman\tpose-check.py                            # 无记录 ⇒ 判「待人工确认」
& $PY tools\digihuman\tpose-check.py --confirm "<复核人>"        # 人看过图后落 .digihuman/S2-human-ok.json
```

> 🔴 **判据口径以源码为准，不以我的判断为准**（2026-09-22 被 Owner 当场纠正过一次：我把"必做人工复核"的 S2
> 折叠成了机检并误报 14/14）。同类自我纠错见 `references/pitfalls.md` §16.4。
- **14 阶段通过（S2 含人工复核记录）**：S0 素材 · S1 几何 · **S2 姿态（机器只给代理读数 臂展/身高 0.98 等；通过要件是人工复核记录）** · S3 分部位LOD · S4 贴图 · S5 骨架 ·
  S6 蒙皮(权重和 1.0000) · S7 表情(3 morph · 自证落在头区) · S8 动画(闭合 0.00000) · S9 弹簧(7 链 × 2 关节) ·
  S10 **VRM 1.0 封装** · S11 运行时 · S12 验收 · S13 账本。
- **官方运行时验收**：three-vrm 读出 **21 根语义骨 / 3 表情 / 7 弹簧关节 / meta 署名** ⇒ `avatar.vrm` 合规。
- 台账：`.digihuman/{config,ledger}.json` · 门与后端解耦（`providers.py`）· 详契约见 `references/full-pipeline.md`。
- **省 `verify` 是翻车之源** —— 本技能 pitfalls 里那 4 次自己打回自己，全发生在"以为不用验"的地方。
- 能力调用一律 `run_task`（唯一门）；被门拒绝就**如实报缺哪个作用域**，**不绕路、不自己发授权**（授权只能主人在终端发）。
- 收步必须有**真证据**（文件哈希/读数/截图），"改完就说完成"会被判 partial。
- 允许开步不关步 = 无纪律；`ruler` 里的 `agent_close_rate` 就是量这个的。
