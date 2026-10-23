---
name: gbt-autoclaw
displayName: GBT · AutoClaw 平台能力用法规程（5 条）
version: 1.0.0
description: GBT小土豆V8 使用 autoclaw-* 技能簇的用法规程。以 state/skill_atlas.json 里 name 前缀 autoclaw- 的 5 条为准（autoclaw-design-capability / autoclaw-design-capability_noQA / autoclaw-im-cron / autoclaw-mcp-tools / autoclaw-pdf-ocr），逐条点名「什么时候用它」，按意图分成设计交付路由 / 平台数据通道 / 平台定时消息 / 文档摄取四簇；规定两道闸（凭据只报已配未配或前 4 位掩码；OCR 渲染写盘、建定时任务、装包换 MCP 配置一律先问主人），并如实记下本机现状（pdf-ocr doctor 报 ok:false 三个依赖全未配、mcporter 不在 PATH、im_remind 在本会话不存在、11 个同名设计规则文件在仓根与技能目录各存一份且内容互不相同）。当用户要跑 AutoClaw 设计能力、建 IM 定时提醒、调 MCP 工具、或对扫描件 PDF 做 OCR，或任何 autoclaw-* 名字的技能路由拿不准、pdf-ocr/mcporter 报没配好时使用。
triggers:
  - "autoclaw"
  - "AutoClaw 设计"
  - "设计能力"
  - "im_remind"
  - "定时提醒"
  - "定时任务"
  - "IM 定时"
  - "mcporter"
  - "MCP 工具"
  - "pdf-ocr"
  - "扫描件"
  - "OCR"
  - "PDF 提取"
  - "图片型 PDF"
---

# GBT · AutoClaw 平台能力用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **边界一句话**：`gbt-tentacle` 管**这台机器的桌面**（手 = 穿透操作界面、眼 = DXGI 取真帧、
> 网 = 出网读源码、耳 = 出声与听声）；**本件管 AutoClaw 平台侧那 5 条托管技能**——
> 设计规则怎么进、IM 定时怎么建、MCP 契约怎么调、扫描件 PDF 怎么 OCR。
> 两条线**不共享任何通道**：本件不取屏幕帧、不点鼠标、不碰音频；`gbt-tentacle` 也不碰这 5 条。
> 唯一看似交叉的一处是"看图"——`autoclaw-design-capability` 会用 `[图片参考描述]` 做**读图理解**，
> 那是**理解一张已有图**，**不是** `gbt-tentacle` 那种**从显卡取当前屏幕帧**。

---

## 0. 它是什么 / 在哪 / 条数怎么核（2026-09-22 现读）

| 项 | 值（现读） |
|---|---|
| 权威条数 | **5 条**，`state/skill_atlas.json` 里 `name` 以 `autoclaw-` 开头 |
| 核对命令 | `py -3.14 tools/codex-scripts/omni.py list --domain autoclaw` → 实测 `agent 技能 5 条` |
| 通道 | **agent-skill**（按技能名加载执行）。⚠️ 万能插里 `autoclaw` 域是 **0 个能力位** —— 别去 `five-dim.py cap` 找它 |
| 装机落点 | **4 条**在 `C:\Users\ADMIN\.openclaw-autoclaw\skills\`（AGENTS.md 指定的托管目录） |
| 例外落点 | **1 条** `autoclaw-mcp-tools` 在**本仓** `skills\autoclaw-mcp-tools\`（`_store_meta.json` 都没有 ⇒ 是**本仓自有件**，不是 store 装的） |
| 来源 | `_store_meta.json` 现读：design-capability / _noqa / pdf-ocr 三条 `source: "store"`（store 安装，**会被 AutoClaw 侧更新覆盖**）；im-cron 是 `source: "local"`（`skillId: autoclaw-im-cron-local`） |
| 版本 | design-capability `1.1.2` · design-capability_noqa `1.1.2` · im-cron `1.0.0` · pdf-ocr `1.0.0` · mcp-tools 无版本字段 |
| 定义域 | `autoclaw-*` 是本机**最大的一簇外来托管技能之一**（前缀 `autoclaw-` 聚簇 5 条 ⇒ 进 `omni.py gaps` 的「技能簇 ≥3 条」榜） |

**逐条点名（一条不许漏）**：

1. `autoclaw-design-capability`
2. `autoclaw-design-capability_noQA`
3. `autoclaw-im-cron`
4. `autoclaw-mcp-tools`
5. `autoclaw-pdf-ocr`

---

## 1. 按意图分簇（4 簇，选错簇比不会用更贵）

```
用户要出设计交付物（页面/原型/看板/海报/PPT） ──→ A 设计交付路由（2 条）
用户要外部数据/资讯/行情（MCP 服务）        ──→ B 平台数据通道（1 条）
用户要建提醒/定时任务（QQ/微信/钉钉/飞书/企微）──→ C 平台定时消息（1 条）
用户要读扫描件/图片型 PDF 的文字            ──→ D 文档摄取（1 条）
```

### A 簇 · 设计交付路由（2 条）——**区别只有一处：要不要澄清阶段**

| 技能 | 什么时候用它 |
|---|---|
| **`autoclaw-design-capability`**（**默认**） | 需要设计交付物、且**允许先问用户**（`INTERACTIONS.md` 的 `question-form`）时。它把活按 `DESIGN.md` → `PRD_INGESTION.md` → `CODE_INGESTION.md` → `TASK_ROUTER.md` 走一遍，再由 `TASK_ROUTER.md` 判 **Redesign 支**（读 `REDESIGN.md`，**不读** `INDEX.md`、**不跑**三轴）还是**标准支**（读 `INDEX.md` 跑三轴）；两支最后都必须读 `OUTPUT_RULES.md`。 |
| **`autoclaw-design-capability_noQA`**（**无澄清变体**） | 同上，但**不走澄清阶段**：从用户 query / 附件 / PRD-QA 材料 / 代码基线 / skeleton 默认值 / design-system 匹配度直接**推断**缺失偏好，然后**直接进** `INDEX.md` + 三轴 + 生成。`INTERACTIONS.md` 只当 `status` / `plan` / `preview` 这类**非提问**动作的前端契约用。 |

两条**共同硬条款**（原文口径，照做）：

- 🔴 **不要调 `auto-designer` 代理** —— 当前 agent **自己读技能目录里的文件把事情做完**。
  （`agents\openai.yaml` 存在，但那**不是**给你派活用的。）
- 🔴 **不是生图技能**：独立出图 / 改图 / logo / 头像 / 插画等**主要交付物是图片**的，
  一律**不走这两条**，走专门的生图能力。
- **PPT / slides / presentation / deck** 默认用 **HTML deck skeleton + `od.mode=deck`**，
  除非用户明确要别的受支持形态。
- **不要列整棵资源树**：新产物优先取 `审美相关skill/design-skeletons/` 里的 skeleton；
  `审美相关skill/skills/` 主要用在 review / 咨询 / 抽取 / 兜底。
- 生成前**必须读**：选中的 skeleton 或 skill 的 `SKILL.md` · 有 `example.html` 就读 ·
  选中 design-system 的 `DESIGN.md`（除非 `OUTPUT_RULES.md` 明说可跳） · 每个选中的 craft 文件 ·
  选中资源 `od.mode` 要求的输出框架文件。
- App 类两文件交付（无限画布 + 可交互原型）：读 `infinite-canvas-output/SKILL.md`，
  画布底用 `infinite-canvas-output/assets/infinite-canvas-template.html`。
- Redesign 支：需要新/改配图 → 读 `visual-asset-director.md`；实现完 → 读 `UI-check.md` 并修它指出的问题；
  **只有**缺合适素材时才读 `design-assets-index/SKILL.md`（**那是工作区参考资源，不是全局技能，别按技能名调**）。

**🔴 本簇最大的读数陷阱：11 个同名文件，三处各一份，内容互不相同（本次实测）**

`autoclaw-design-capability` 说的 `DESIGN.md` / `TASK_ROUTER.md` / `INDEX.md` / … 是**技能目录内**那一套；
而本仓 `AGENTS.md` 的设计流程说的 `DESIGN.md` / `TASK_ROUTER.md` / … 是**仓根**那一套。
**同名、不同物**（本次逐文件 SHA256 实测）：

| 文件 | 仓根 B | 技能目录 B | 同一份？ |
|---|---:|---:|---|
| `DESIGN.md` | 18035 | 17569 | ❌ |
| `TASK_ROUTER.md` | 19136 | 18664 | ❌ |
| `INDEX.md` | 23050 | 22541 | ❌ |
| `REDESIGN.md` | 9788 | 9533 | ❌ |
| `OUTPUT_RULES.md` | 26235 | 25658 | ❌ |
| `INTERACTIONS.md` | 26171 | 24554 | ❌ |
| `PRD_INGESTION.md` | 3632 | 3426 | ❌ |
| `CODE_INGESTION.md` | 10711 | 10353 | ❌ |
| `IMAGE_GENERATION.md` | 47183 | 46324 | ❌ |
| `UI-check.md` | 4960 | 4751 | ❌ |
| `visual-asset-director.md` | 9915 | 9555 | ❌ |

而且 **`autoclaw-design-capability` 与 `autoclaw-design-capability_noqa` 两个目录里的同名文件也不一样**
（`DESIGN.md` ❌、`SKILL.md` ❌）——**不要拿一条的规则去跑另一条**。

⇒ **纪律**：走 `autoclaw-*` 技能时，**显式用技能目录的绝对路径读它自己那一份**；
走本仓 `AGENTS.md` 流程时，读**仓根**那一份。**两套规则不许混着引用**（这正是红线①的活样本）。

### B 簇 · 平台数据通道（1 条）

| 技能 | 什么时候用它 |
|---|---|
| **`autoclaw-mcp-tools`** | 用户要访问**已配置的 MCP 服务** / 外部数据提供方 / 股票 / 基金 / 宏观数据 / 新闻 / 文件 / 数据库，或直接提到 **mcporter / MCP 工具**时。调用格式（技能原文）：`mcporter --config C:\Users\ADMIN\Desktop\GBT小土豆V8\config\mcporter.json call <server>.<tool> key=value`；只有 `query` 参数的工具用 `query="..."`。**不要退回网页搜索**，除非对应 MCP 服务不可用或用户明确要求网页搜索。汇总答案时要**说明数据来自哪个 MCP 服务**。 |

🔴 **本机现读（2026-09-22）**：配置文件在（`config\mcporter.json` → `True`），但
**`mcporter` 不在 PATH**（`Get-Command mcporter` 无输出；`%APPDATA%\npm` 下也没有 `mcporter*`），
且技能自己的「可用工具」一栏原文就是 **「当前没有可用 MCP 工具。」**，
本会话 AGENTS.md 的 MCP 段也现读 **「No MCP tools are currently healthy.」**
⇒ **命令形状看着能跑，实际一条也跑不起来** —— 这就是「**能调 ≠ 能用**」的活样本。
要真用，得先让主人装/接 MCP server 并改 `config\mcporter.json`（**那是改配置，见 §3 闸②**）。

### C 簇 · 平台定时消息（1 条）

| 技能 | 什么时候用它 |
|---|---|
| **`autoclaw-im-cron`** | 从 AutoClaw **IM 通道**建**定时任务 / 提醒 / cron / 延时回复**，或列/删/测这类任务时。支持 5 个通道：QQ `qqbot` · 微信 `openclaw-weixin` · 钉钉 `dingtalk-connector` · 飞书 `feishu` · 企微 `wecom`。 |

**硬规则（技能原文，照做）**：

- 统一**先用 `im_remind` 工具**；从 IM 会话里创建时 **不许手工拼 `cron` JSON**。
- **不要**用 legacy 通道工具（`qqbot_remind` / `dingtalk_remind`）建新任务，**除非** `im_remind` 不可用。
- 目标**保持当前 IM 会话**，除非用户明确要别的目标**且**当前发送者被允许。
- 🔴 **创建时不问用户"最长运行多久"，一律传 `timeoutSeconds: 300`**（每个新任务从 5 分钟上限起步）。
  用户要改，**引导他去 AutoClaw「定时任务」面板里改那一条**；
  🔴 **绝不动全局 Agent timeout**（那是改系统配置）。
- **间隔型**（"每30秒执行一次" / "每隔5分钟"）→ 传 `everyMs`，或 `repeat: true` / `scheduleMode: "every"`。
  🔴 **不许把"每30秒"降级成一次性 `time: "30s"`**。
- **固定文本**（"只回复…"）→ `executionMode: "direct_reply"`。
- **要判断措辞 / 调工具 / 查数据 / 发富内容** → `executionMode: "agent_task"`。
- 拿不准 → `executionMode: "auto"`，把用户要的执行内容放进 `content`。

典型一次性调用（技能原文的 payload 形状）：

```json
{ "action": "add", "name": "example-once", "time": "1分钟后",
  "content": "只回复「[IM] once fired at 当前时间」",
  "timeoutSeconds": 300, "executionMode": "direct_reply" }
```

典型间隔型：

```json
{ "action": "add", "name": "example-free", "everyMs": 30000,
  "content": "结合当前时间，自由发挥提醒我检查今天的任务进展。",
  "timeoutSeconds": 300, "executionMode": "agent_task" }
```

⚠️ **本会话实测**：`im_remind` **不是本会话（DSH）的工具**——本次工具清单里没有它，
仓内 `*.md` / `*.py` 全文检索 `im_remind` **零命中**。它属于 **AutoClaw 宿主侧工具**。
⇒ 在本会话里**无法实测 `im_remind`**（标 **未验**，见 §6）；
要真建任务，得在**能加载 `autoclaw-im-cron` 的 AutoClaw 会话**里做。

### D 簇 · 文档摄取（1 条）

| 技能 | 什么时候用它 |
|---|---|
| **`autoclaw-pdf-ocr`** | 用户要**读/提取/摘要/翻译/分析扫描件 PDF**、**纯图片型 PDF**、或**内嵌文字缺失/乱码/被水印污染**的 PDF；或内嵌文字抽取对某些页返回空/不可靠、而用户要真页文字；或**本技能先前渲染的页图还需 OCR**（失败/跳过/加页）时，对保留的 images 目录再跑 `ocr` 子命令。**它只给每页的字面文字 + 页级完整性账**；**图片的语义理解**（场景/物体/图表画的是什么）**不在它范围**。 |

**硬规则（技能原文，照做）**：

- **用自带的确定性客户端**。🔴 **不许装 Poppler、不许调 `pdftoppm`、不许复用旧页图、
  不许自己 fetch `/get_token`、不许自己调远端 OCR 端点**。（这条直接对 §3 闸②"装包先问主人"。）
- **一次 OCR 请求 = 正好一张图**；客户端自动用 **2 个 worker**，主进程 broker 把上游总并发**封顶 8**。
  🔴 **这两个值不是 CLI 选项，不许覆盖，也不许并行起多个 OCR CLI 进程**。
- 🔴 **`complete` 不为 `true`、或不是每一页都成功时，绝不许声称"全覆盖"**。
  部分结果要**逐页点名缺哪些页**，并避免下依赖缺失页的结论。
- 🔴 **不许打印 / 查看 / 落盘 / 暴露 OCR 代理凭据**。

就绪检查与调用（**技能原文命令**）：

```bash
node "$OPENCLAW_STATE_DIR/skills/autoclaw-pdf-ocr/scripts/pdf-ocr.mjs" doctor --json
node "$OPENCLAW_STATE_DIR/skills/autoclaw-pdf-ocr/scripts/pdf-ocr.mjs" run --pdf "/absolute/path/document.pdf" --pages "1-40" --json
node "$OPENCLAW_STATE_DIR/skills/autoclaw-pdf-ocr/scripts/pdf-ocr.mjs" ocr --input-dir "/task/directory/images" --pages "7,12" --output-dir "/task/directory" --json
```

⚠️ **本机实测的坑（照做）**：`OPENCLAW_STATE_DIR` **未配**（现读：未设置），
所以上面三条**原样照抄会拼出 `/skills/...` 这种不存在的路径**。
装机的真实路径是 `C:\Users\ADMIN\.openclaw-autoclaw\skills\autoclaw-pdf-ocr\`。
本次就是用**真实绝对路径**跑的 doctor（见 §5 实测账）。
⇒ **要么让主人配 `OPENCLAW_STATE_DIR`，要么显式写绝对路径**；别照抄变量形式后报"文件不存在"。

---

## 2. 两道闸（顺序不能颠倒）

### 闸① · 凭据闸（**只报已配/未配或前 4 位掩码，绝不贴值**）

本簇唯一声明凭据需求的是 `autoclaw-pdf-ocr`，它的 frontmatter `metadata.openclaw.requires` 写着：

```yaml
requires: { bins: ["node"], env: ["AUTOCLAW_OCR_PROXY_URL", "AUTOCLAW_OCR_PROXY_TOKEN", "AUTOCLAW_CLAWPDF_MODULE_PATH"] }
```

**本机现读（2026-09-22 · 只报状态，不报值）**：

| 变量 / 依赖 | 状态 |
|---|---|
| `OPENCLAW_STATE_DIR` | **未配** |
| `AUTOCLAW_OCR_PROXY_URL` | **未配** |
| `AUTOCLAW_OCR_PROXY_TOKEN` | **未配** |
| `AUTOCLAW_CLAWPDF_MODULE_PATH` | **未配** |
| `node` | ✅ 已装 · `C:\Program Files\nodejs\node.exe` · **v24.15.0** |

**凭据纪律（硬）**：

1. 🔴 **不许把任何凭据写进任何文件、任何聊天** —— 不 echo、不落盘、不贴进规程、不贴进日报、不贴进 MEMORY。
   包括 OCR 代理 URL / TOKEN，以及任何 MCP 服务的 key。
2. 要给人看**只报**「**已配 / 未配**」，或**前 4 位掩码**（例 `sk-a1b2****`）。
3. 🔴 **不直接读也不直接写 MCP / OCR 的配置存储** —— 一律走工具命令，让密钥保持掩码。
4. 本文件里**没有出现任何凭据值**；出现的一切都只是**变量名**与**状态**。

### 闸② · 🔴 会改系统配置 / 装包 / 写盘的动作，**必须先问主人**

**本簇命中这条的动作多且都很"顺手"，逐条点名**：

| 动作 | 属于 | 为什么必须先问 |
|---|---|---|
| `pdf-ocr … run` / `ocr` | **写盘** | 它会**渲染新 PNG**、**建唯一 task 目录**、写 `manifest.json` / `combined.txt` / 每页 JSON+text。**不是只读**。 |
| 装 Poppler / 换 OCR 客户端 / 调 `pdftoppm` | **装包 + 改环境** | 技能原文**明文禁止**；真要装也得主人点头。 |
| 建 / 改 / 删 IM 定时任务 | **改平台配置** | 任务**会自己跑**（默认 5 分钟上限），而且**会往 IM 会话真发消息**。 |
| 改全局 Agent timeout | **改系统配置** | 技能原文**禁止**；只允许改**单条任务**的设置。 |
| 装 / 换 / 改 MCP server、动 `config/mcporter.json` | **改配置 + 装包** | 会改变后续所有 MCP 调用的落点；`mcporter call` 本身还会**出网**。 |
| 写设计交付物（HTML / 页面 / 原型 / deck） | **写盘** | 生成前先摊开**落点路径 + 文件名 + 是否覆盖**，等一次明确同意。 |
| 改 `~/.openclaw-autoclaw/skills/autoclaw-*` 托管件本体 | **改托管件** | 那 3 条 `source: "store"` 会被 AutoClaw 侧更新覆盖；**要改口径就写我们自己的规程（本件），别改托管件**。 |

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份**（在哪个会话/哪个 agent 上跑，`im_remind` 尤其看这个）· **目标**
   （PDF 绝对路径 + 页范围 / 会话与通道 / 配置文件名，**指名道姓**）· **内容**（要发什么、要 OCR 哪几页）· **影响面**
   （写哪些文件、发到哪个会话、能不能撤回、覆盖了什么）。
2. **只读的先跑**：`doctor --json`、`--help`、`omni.py ask/list/gaps`、`Test-Path` —— **这些不写任何东西，不需要许可**。
3. **等一次明确同意**：**只覆盖这一条**，不是"以后这类都同意"。主人没回话 = **没同意**，停。
4. **同意后执行**：在**自己的原始参数**上加东西（不重写一条新命令）；能 `--dry-run` 就先 dry-run。
5. **拿回执**：`pdf-ocr` 要读回 **`manifest.json` 的 `complete == true`** + 逐页成功数；
   `im_remind` 要拿回**任务 id / name**。
6. **失败就记失败**：原样保留返回与退出码，**不许把失败写成成功**（见 §4）。

---

## 3. 本簇不吃授权门 —— 但有两条别搞混

**现读**：`autoclaw-*` 是 **agent-skill 通道**，万能插里 `autoclaw` 域 **0 个能力位**
⇒ **不经过** `gbt_allinone` 的 `auth grant` / `run_task` 门，**没有作用域要申请**。

但 **"不吃授权门" ≠ "可以随便动"**，两条务必分清：

1. 🔴 **平台自己的门在那儿**：`im_remind` 建任务、`mcporter call` 出网，
   走的是 **AutoClaw 宿主侧**的许可，**不是** `gbt_allinone` 的门。
   ⇒ **别拿"我们这边没门"当"可以自动跑"** —— 本件的**闸②**就是给它补上的那道。
2. 🔴 **诊断类只读命令任何时候都该先跑**：`doctor --json` / `--help` / `omni.py …`
   不写盘、不出网、不要许可。**"没配好"不能成为"没查"的借口** —— 查了才知道是**未配**还是**坏了**。

---

## 4. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？** 本簇有**三个**会静默给你"对的形状 + 错的内容"的地方：
   - 🕳 **11 个同名规则文件**（§1 A 簇）：读错目录 = **拿别一套规则跑活**，全程不报错；
   - 🕳 **`_noqa` 目录**：名字里 `noQA` 是**大写**（`_store_meta.json` 里 `skillKey`、
     `SKILL.md` frontmatter `name` 都是 `autoclaw-design-capability_noQA`），
     而**磁盘目录名是全小写 `autoclaw-design-capability_noqa`** ⇒ **Windows 上照跑，Linux/区分大小写的机器上会找不到**；
   - 🕳 **`autoclaw-mcp-tools` 不在托管目录**，在**本仓** `skills\` 下 ⇒ 去
     `~/.openclaw-autoclaw/skills/` 找它**会扑空**，然后被误报成"没装"。
   ⇒ **报数前先确认：条数（5）· 落点（4 托管 + 1 本仓）· 读的是哪一个目录**，三件事对得上。
2. **"能调" ≠ "能用"（本簇的招牌）**：
   - `mcporter` **命令形状完整、配置也在**，但**二进制不在 PATH**、技能自己写着"没有可用 MCP 工具"
     ⇒ **一条也跑不起来**。**别因为文档里写着命令就报"可用"**。
   - `autoclaw-pdf-ocr` **脚本在（22936 B）、node 在（v24.15.0）**，
     但 `doctor` 现读 **`ok: false`**（3 个依赖全 false）
     ⇒ **"文件都在" ≠ "功能可用"**。
3. **不许把"命令跑通了"当"事情办成了"**：`pdf-ocr run` 打出的是**紧凑 manifest**，
   **正文永远不在 stdout**；要判成败**必须读 `manifest.json` 的 `complete`**。
4. **不许编命令、编路径、编技能名**：本文件出现的每条命令，要么**本次实测过**（§5 逐条列），
   要么明确标 **（未验）**。**没跑过的不许说成跑过。**
5. **不许报凭据细节**：只报**已配 / 未配**或**前 4 位掩码**（§2 闸①）。
6. **`ok: false` 要原样报，别软化成"可能有点问题"**：`doctor` 的退出码是 **1**，
   `checks` 里 `proxyUrl` / `proxyToken` / `clawpdfModule` 三个 false **逐项点名**。

---

## 5. 本机真跑过的命令（逐条：命令 → 关键返回 → 判定）

| # | 命令 | 关键返回（抄真实） | 判定 |
|---|---|---|---|
| 1 | `py -3.14 tools/codex-scripts/omni.py list --domain autoclaw` | `── 能力位 0 条` + `── agent 技能 5 条`，逐条列出 5 个名字 | ✅ **条数=5，与 atlas 一致**；本簇**不吃授权门** |
| 2 | `py -3.14 tools/codex-scripts/omni.py list --domain sandbox` | `── agent 技能 3 条` | ✅ 供 gbt-sandbox 用 |
| 3 | `… omni.py ask "用 AutoClaw 的设计能力做一个落地页"` | 「走 agent 技能」段命中 `autoclaw-design-capability`(10.8) · `_noQA`(10.8) · `autoclaw-pdf-ocr`(10.8) · `autoclaw-mcp-tools`(9.6) | ✅ **人话 → 技能**这一环通；但 **`autoclaw-im-cron` 未命中**（那句话里没"定时"语义，属正常） |
| 4 | `… omni.py gaps` | `autoclaw-*  5 条  ⏳ 在队里（有技能，但无 GBT 口径规程）` | ⚠️ **交付前的读数**；本条**不会因为本件交付而自动变**（§7.2） |
| 5 | `… verify-distill.py --cluster autoclaw` | `"skill": null` · `fail: ["omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇"]` · `facts.skills_in_atlas: 5` · `verdict: "FAIL"` · exit 1 | ⚠️ **机检入口对本簇不可用**（红线禁止改 `omni.py`）；**但 `skills_in_atlas: 5` 这个数是对的** |
| 6 | `… verify-distill.py --cluster lark`（对照） | `"skill": "gbt-lark"` · `identical: true` · `skills_covered: 28` · `verdict: "PASS"` | ✅ 证明工具本身没坏，只是 **autoclaw/sandbox 两个簇没登记** |
| 7 | `node "C:\Users\ADMIN\.openclaw-autoclaw\skills\autoclaw-pdf-ocr\scripts\pdf-ocr.mjs" doctor --json` | `{"ok": false, "checks": {"proxyUrl": false, "proxyToken": false, "clawpdfModule": false, "nodeVersion": true}, "auth": {"available": false, "source": "missing"}}` · **exit 1** | ❌ **未就绪**：缺 3 个依赖；`nodeVersion` 是唯一的 true（诚实账，不夸大） |
| 8 | env 逐项查（`OPENCLAW_STATE_DIR` / `AUTOCLAW_OCR_PROXY_URL` / `…_TOKEN` / `…_CLAWPDF_MODULE_PATH`） | **四个全"未配"** | ❌ 见 §2 闸①；**只报状态，不报值** |
| 9 | `node --version` | `v24.15.0` · `C:\Program Files\nodejs\node.exe` | ✅ bins 需求满足 |
| 10 | `Get-Command mcporter` + 扫 `%APPDATA%\npm` | **无输出 / 无 `mcporter*`** | ❌ **不在 PATH** ⇒ B 簇命令**一条也跑不起来** |
| 11 | `Test-Path config\mcporter.json` | `True` | ✅ 配置在，**但缺可执行体** |
| 12 | 读 `_store_meta.json` × 4 | store 1.1.2 / 1.1.2 / local 1.0.0 / store 1.0.0 | ✅ 落点与来源判清（§0） |
| 13 | `Get-FileHash` 逐文件比对 11 个同名规则文件（仓根 vs 技能目录）+ 两技能目录互比 | **全部 False**（字节数差 300–860 B） | 🔴 **§1 A 簇的坑，实测坐实** |
| 14 | `Get-ChildItem` 两簇落点扫描 | `sandbox-*`：托管目录 **0**、`.claude` **3**；`autoclaw-*`：托管 **4** + 本仓 **1** | ✅ 落点判清（别去错目录找） |
| 15 | `Get-ChildItem autoclaw-pdf-ocr -Recurse` | `scripts\pdf-ocr.mjs 22936` · `_store_meta.json 231` · `.bundled-hash 16` · `SKILL.md 3059` | ✅ **脚本真在**（所以"未就绪"是**依赖未配**，不是**文件缺失**） |

**没跑过 / 跑不了的（标未验，不许说成跑过）**：

- 🔴 **`im_remind` 的任何调用** —— **本会话没有这个工具**（DSH 工具清单里无它；仓内
  `*.md`/`*.py` 检索 `im_remind` **零命中**）。**未验**。
  ⇒ C 簇的 payload 形状是抄**技能原文**，**不是**本机实测结果。
- 🔴 **`mcporter --config … call …`** —— `mcporter` **不在 PATH**，配置里也**没有可用 MCP 工具**。**未验**。
- 🔴 **`pdf-ocr.mjs run` / `ocr`** —— `doctor` 已 **`ok: false`**（3 项依赖未配），
  本次**故意不跑**（跑了会**写盘**，且必然失败）。**未验**。
- 🔴 **任何 Cloudflare Sandbox 相关命令** —— 见 `gbt-sandbox`（另一份规程），这里不重复。
- ⚠️ **`autoclaw-design-capability` 的完整路由链**（`DESIGN.md`→…→`OUTPUT_RULES.md`）
  —— 本次**只核了文件存在性与哈希**，**没有真跑一遍设计交付**。**未验**。
  它的规则细节以**它自己目录里那份 md** 为准。

---

## 6. 固化位置（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>\skills\gbt-autoclaw\SKILL.md` |
| 本规程（装机） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-autoclaw\SKILL.md`（**与源稿逐字节相同**） |
| 被规程管的 5 条 | 4 条在 `~\.openclaw-autoclaw\skills\autoclaw-*`；**1 条 `autoclaw-mcp-tools` 在本仓 `skills\autoclaw-mcp-tools\`**（**不由本件代管，别改**） |
| 能力名册（现读） | `py -3.14 tools/codex-scripts/omni.py list --domain autoclaw` · `<仓>\state\skill_atlas.json`（`name` 以 `autoclaw-` 开头） |
| 人话入口 | `py -3.14 tools/codex-scripts/omni.py ask "用 AutoClaw 的设计能力做一个落地页"` → 落到 `autoclaw-design-capability` |
| 队列读数 | `py -3.14 tools/codex-scripts/omni.py gaps` |

**纪律**：本规程**不代替**那 5 条技能，也不代替它们目录里的规则文件。
`omni.py` 与 `security/policy.py` **不是本件该动的东西** —— 本件只加一份规程，**不动门**。
🔴 **绝不写 `~/.agents/skills/`**（那是别家工具的共享目录）。

---

## 7. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 5 条**点名、分簇、定了纪律**；
   每条技能的深度用法**以它自己的 `SKILL.md` 与它目录里那份规则文件为准**，本件**不替代**。
2. **⚠️ 机检入口对本簇现读是 FAIL，且本件不许去修它。**
   `verify-distill.py --cluster autoclaw` 报的是
   **「omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇」**（`facts.skills_in_atlas: 5`）。
   要让它 PASS，需要在 `tools/codex-scripts/omni.py` 的 `DISTILLED_CLUSTERS` 里加一行 `"autoclaw": "gbt-autoclaw"` ——
   **那是改 `omni.py`，本次红线明令禁止**。⇒ **本件只保证"两份产物逐字节相同"（哈希口径），
   不保证 omni 的登记表已更新**；登记留给主人/父代理决定。
   同理，`omni.py gaps` 里 `autoclaw-*` **仍会显示「⏳ 在队里」** —— **那是登记表的账，不是本件没交付**。
3. **本次实跑的全是只读/诊断类**：`omni.py list/ask/gaps` · `verify-distill` · `pdf-ocr doctor`
   · `node --version` · `Get-Command` · `Test-Path` · `Get-FileHash` · `Get-ChildItem`。
   **任何 OCR 真跑、任何 IM 任务创建、任何 mcporter 调用、任何设计交付，本次都没跑**（§5 末段已逐条标未验）。
4. **本机状态是 2026-09-22 的现读快照**（5 条 · 4 托管 + 1 本仓 · store 1.1.2/1.0.0 · node v24.15.0）。
   **换机器、AutoClaw 侧更新、换 store 版本后必须重新现读**，别把这份读数当永久事实。
5. **凭据只报"已配/未配"**：本文件里出现的 `AUTOCLAW_OCR_PROXY_URL` 等**只是变量名**，
   **不是**任何可用凭据；`_store_meta.json` 里的 `skillId` 是**安装标识**，**不是**密钥。
6. **上游会覆盖**：3 条 `source: "store"` 的托管件（design-capability / _noqa / pdf-ocr）
   **可能被 AutoClaw 更新整体替换**；届时本件的路由结论**需要在更新后重新现读**。
