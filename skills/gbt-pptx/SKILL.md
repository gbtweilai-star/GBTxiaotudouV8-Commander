---
name: gbt-pptx
displayName: GBT · PPTX/幻灯片用法规程（技能簇 pptx-*）
version: 1.0.0
description: GBT小土豆V8 使用 PPTX/幻灯片这一技能簇的用法规程。本簇按 `state/skill_atlas.json` 里 name 前缀核定共 4 条（`pptx` · `pptx-swarm` · `pptx-html-fidelity-audit` · `pptx-generator`），其中前 3 条是真业务件、`pptx-generator` 是只指上游的目录桩。本规程把每条按意图分簇点名，钉死两道闸（① 凭据与依赖的**实测**账：`PEXELS_API_KEY` 等密钥一律未配、`python-pptx`/`markitdown`/`defusedxml`/`pptxgenjs` 全部没装、`pptx-swarm` 的 `bash` 脚本在 Windows 上要先解 bash+python3 的错位；② 出片/上传/发布成品的动作必须先问主人），并记下真跑出来的读数（`pptd_guard.py --pre-spawn` 在缺件盘上真吐 5 条 errors、`convert.sh` 要的 `pptd_dsl.pyz` 盘上**不存在**只有 `.larkcache`）与报告层红线（`pptx-swarm` 的 `0 errors, 0 warnings` 是它自己的 checker 说的、不等于成品合格；目录桩不能当能力用）。当用户要做 PPT / 幻灯片 / deck / 汇报 / 研究汇报 / 课程讲义，或要审 HTML→PPTX 的保真度、怀疑 pptx 被切掉/页脚压字/斜体丢失，或要跑 `pptx-swarm` 的工作流时使用。
triggers:
  - "PPT"
  - "PPTX"
  - "幻灯片"
  - "slide"
  - "slide deck"
  - "deck"
  - "演示文稿"
  - "汇报"
  - "讲义"
  - "pptx-swarm"
  - "pptd"
  - "保真度审计"
  - "fidelity audit"
  - "页脚压字"
  - "pptx-generator"
---

# GBT · PPTX/幻灯片用法规程（技能簇 `pptx-*`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是**我们自己的用法规程**（不是那 4 条技能官方文档的复述）。技能自身讲"每条怎么用"，
> 本文件讲"**在我们这台机器上，谁在什么条件下、按什么顺序去用它，什么已经真能跑、
> 什么还没接线、什么东西绝对不许自动发出去**"。
> 冲突时的裁决顺序：**本文件管我们的纪律** → 各技能自己的 `SKILL.md` 管命令细节。

---

## 0. 三处边界（**开工第一段就读这段**）

这一节是硬要求，三份规程各写一处，三处合起来才把"视频/幻灯片"这块地盘划清：

| 是谁 | 管什么 | 判决口径 | 它**不**管什么 |
|---|---|---|---|
| **`gbt-pptx`（本件）** | **PPTX/幻灯片这一技能簇怎么用** —— 4 条技能的选用、两道闸、真跑读数、坑 | 以本件为纲，命令细节以各技能 `SKILL.md` 为准 | 不出视频、不碰 Ark 云端、不碰 `video` 能力位 |
| **`gbt-video-tools`** | **`video-*` / `youtube-*` 这一技能簇怎么用** —— 3+3 条技能的选用、两道闸、真跑读数、坑 | 同上 | **不是**"本机视频能力位"、**不是** Ark 云端那条 |
| **`gbt-video`**（已存在，**别重名别覆盖**） | **本机 `video` 职业域的 4 个能力位**（`media_pipeline` / `libtv_skill` / `libtv_workflow` / `h3_video_gen`）—— 走 `five-dim.py cap <能力位>` 的**能力域**规程 | 图鉴口径 | 不管技能簇、不管公众号/YouTube 这类外部平台 |
| **`gbt-arkcli`**（已存在） | **Ark 云端那一条**（`arkcli +gen` / Seedream / Seedance） | 它自己的调用前缀 + 登录闸 + 账号验证闸 + 计费纪律 | **不代表**本机任何技能或能力位已接线 |

**一句话记法**：**`gbt-pptx` 管"幻灯片技能怎么用"；`gbt-video-tools` 管"视频技能怎么用"；
`gbt-video` 管"本机视频能力位在哪、要不要授权"；`gbt-arkcli` 管"Ark 云端那条"。
四者谁都不许拿对方的读数替自己说话。**

---

## 1. 它是什么 / 名单怎么核（**以图鉴现读为准**）

**核定口径**：`state/skill_atlas.json` 里 `name` 以 **`pptx`** 开头的条目。

```powershell
py -3.14 tools/codex-scripts/omni.py list --domain pptx     # ✅ 已验（宽松匹配，会带进非本簇的行）
```

`omni.py list --domain pptx` 实测打出的 **agent 技能 5 条**里混着同类项；
**权威做法是按 name 前缀从图鉴数**，实测得到 **4 条**：

| # | 技能 | 通道 | 落点 | 形态 |
|---|---|---|---|---|
| 1 | **`pptx`** | `agent-skill` | `~/.openclaw-autoclaw/skills/pptx` | **真业务件**（626 行，Part 1 设计原则 + Part 2 pptxgenjs 深用） |
| 2 | **`pptx-swarm`** | `agent-skill` | `~/.openclaw-autoclaw/skills/pptx-swarm` | **真业务件**（PPTD 中间层 + 19 个 guidline/reference 文件 + 4 个脚本） |
| 3 | **`pptx-html-fidelity-audit`** | `agent-skill` | `~/.openclaw-autoclaw/skills/pptx-html-fidelity-audit` | **真业务件**（五步审计 + 2 脚本 + 3 reference） |
| 4 | **`pptx-generator`** | `design-asset` | `<仓>/审美相关skill/skills/pptx-generator` | ⚠️ **目录桩**（42 行，只指上游 `MiniMax-AI/skills`，**无脚本、上游未装**） |

⚠️ **两处必须点名的口径**：

1. **第 4 条是"目录桩"，不是能力**。它自己的正文原话：*「This catalogue entry advertises the skill
   in Open Design so the agent discovers it during planning」* + *「Stubs intentionally do not vendor
   upstream assets」*。⇒ **它只能被"发现"，不能被"执行"**。把它念成"本机有 MiniMax 的 PPT 流水线"
   是**假读数**。
2. **`omni.py gaps` 报的是 `pptx-*  3 条`**（它按 `name.startswith("pptx-")` 数，**带横杠**）
   ⇒ 裸名 `pptx` 落在那条统计之外。**本件的覆盖口径取"更全的 4 条"**：
   验收器 `verify-distill.py --cluster pptx` 用的是带横杠口径（3 条），
   本件**额外点名裸名 `pptx`**，两侧都不漏。

**真身/技能落盘（现读）**：

```powershell
# ✅ 已验：managed 目录里本簇 3 条真业务件都在
Get-ChildItem "C:\Users\ADMIN\.openclaw-autoclaw\skills" -Directory |
  Where-Object { $_.Name -match '^(pptx)' } | Select-Object -ExpandProperty Name
# → pptx / pptx-html-fidelity-audit / pptx-swarm
```

---

## 2. 按意图分簇（4 条逐个点名）

### 簇 A · 从零造一份 deck（**主路**）

| 技能 | 什么时候用它 | 怎么用 |
|---|---|---|
| **`pptx-swarm`** | 用户说"做一份 PPT / 演示文稿 / 汇报 / 研讨会 deck / 提案 / 报告 / 课程讲义"，而且是**从零新建可编辑的 PPTX** | 走 **PPTD 中间层**：先建 workdir（`design.md` + `outline.md` + `page_manifest.json` + `<deck>.pptd` + `pages/` + `qa/` + `DELIVERY/`），再 `pptd_guard.py --pre-spawn` → 页 agent 写 `.page` → checker 到 `0 errors, 0 warnings` → `pptd_guard.py --post-pages` → `convert.sh` → QA agent → repair gate |
| **`pptx`** | 要**直接写 pptxgenjs / python-pptx 代码**、或要设计原则（配色/版式/字体/CJK/避坑清单）时 | **Part 1 是设计铁律**（三件事先行、BACKGROUND→PRIMARY→ACCENT 三色、AI 味禁令清单）；**Part 2 是 pptxgenjs API 深用**（坐标英寸、`LAYOUT_WIDE` 13.33×7.5、shape/chart/table、9 条毁文件坑） |

🔴 **两条的边界（技能自己写死的）**：`pptx-swarm` 的 ATTENTION 第 1 条原话 ——
*「Directly operating on .pptx files is strictly prohibited. All your operations should apply to
.pptd files, then use the CLI tools to convert .pptd to .pptx.」*
⇒ **选中 `pptx-swarm` 后就不许直接改 `.pptx`**；要改现成 deck 走簇 C 或 `pptx` 的编辑段。

🔴 **不许因为"页数少"就降级**：`pptx-swarm` 第 5 条原话 ——
*「once this pptx-swarm skill is selected, do not switch to the non-swarm pptx skill merely
because the deck has fewer slides」*。**页数只影响拆几个 `.page`，不影响选哪条。**

### 簇 B · 拿别人的模板/风格造新 deck

| 技能 | 什么时候用它 | 怎么用 |
|---|---|---|
| **`pptx`**（模板段） | 用户给一份 `.pptx` 当模板，要"照这个风格做一份新的" | 先判模式：**Clone & fill**（新大纲/自由结构）vs **Fill-in**（≈1:1 换数据）；**先研究模板再写内容**，最后按 5 项机检（页序页数 / 残留占位符 / 断图 rId / 重开文件 / `[Content_Types].xml` 完整性）收口 |

🔴 **`[Content_Types].xml` 那道检是硬的**：技能原文写明"重开文件**抓不到**坏包"——
python-pptx 靠 rels + `<Default Extension="xml"/>` 兜底，丢了 slide `<Override>` 的包**照样能打开**，
但严格消费者（in-app 预览）**按 `[Content_Types].xml` 数页 ⇒ 渲染成空白 deck**。
⇒ **任何 `zipfile` 重打包或 XML 级克隆之后，必须跑那段 assert。**

### 簇 C · 审/修一份"从 HTML 导出"的 deck

| 技能 | 什么时候用它 | 怎么用 |
|---|---|---|
| **`pptx-html-fidelity-audit`** | 手里**同时有**一份 HTML 源稿 + 一份由它导出的 `.pptx`，怀疑/已见漂移（页脚压字、内容被切、斜体 `<em>` 丢了、hero 没居中、间距走样） | 五步：① `scripts/extract_pptx.py` 抽 ground truth（**信 dump 不信导出脚本的意图**）→ ② 走 HTML 结构 → ③ 建审计表（🔴/🟠/🟡/🟢 四档）→ ④ 用 **footer-rail + cursor-flow** 重导 → ⑤ `scripts/verify_layout.py` 验到 **0 violations** |

🔴 **它要求"两件都在"**：技能原文 —— *「If the user only has one of those two artifacts,
this skill doesn't apply yet」*。**只有 `.pptx` 没有 HTML 源稿 ⇒ 不该路由到它**。

### 簇 D · 只被"发现"的目录桩

| 技能 | 状态 | 怎么处置 |
|---|---|---|
| **`pptx-generator`** | ⚠️ **目录桩**：42 行，`od.mode: deck` / `od.category: slides`，上游 `https://github.com/MiniMax-AI/skills`，**未装、无脚本** | 只在规划期被"发现"。要用真流程 ⇒ 先**出网 + 主人点头**装上游包。**不许说"本机有这条流水线"。** |

**选路示例**：用户说"帮我做份 12 页的产品汇报" → **`pptx-swarm`**（不是 `pptx`）；
"这个 pptxgenjs 阴影为什么把文件写坏了" → **`pptx`**（Part 2 §Common pitfalls）；
"我这 PPT 是从 HTML 导的，页脚被压了" → **`pptx-html-fidelity-audit`**；
"用 MiniMax 那套做 PPT" → **`pptx-generator`** ⇒ **先说明它是桩、要装上游**。

---

## 3. 闸一 · 凭据与依赖（**只报已配/未配，绝不贴值**）

### 3.1 凭据（实测：**本簇要的密钥一个都没配**）

| 名字 | 谁要它 | 实测 | 怎么测的 |
|---|---|---|---|
| 无 | **`pptx-swarm`** / **`pptx`** / **`pptx-html-fidelity-audit`** | **本簇三位真业务件不要求任何 API key** | 读三份 `SKILL.md` 的依赖段（无 `requires.env`） |
| `PEXELS_API_KEY` | ⚠️ **不是本簇的** —— 它属于 `youtube-factory`（见 `gbt-video-tools`） | **UNSET** | `[Environment]::GetEnvironmentVariable` |
| 密钥池现状 | 本机全机密钥池 | **`keys_total: 0`** | `py -3.14 tools/codex-scripts/five-dim.py cap model_key_pool` |

🔴 **报法纪律**：要给人看只说 **「已配 / 未配」** 或 **前 4 位掩码**（如 `sk-a1b2****`）。
**不许 echo、不许落盘、不许贴进规程/日报/对话**。本件里**不会出现任何一个真凭据**。

### 3.2 依赖（实测：**本簇的 Python/Node 依赖基本都没装**）

```powershell
# ✅ 已验（每一条都真跑过，下面是真实返回）
py -3.14 --version                    # → Python 3.14.5
node --version                        # → v24.15.0
npm --version                         # → 11.12.1

py -3.14 -c "import pptx"             # → ModuleNotFoundError: No module named 'pptx'
py -3.14 -c "import markitdown"       # → ModuleNotFoundError: No module named 'markitdown'
py -3.14 -c "import defusedxml"       # → ModuleNotFoundError: No module named 'defusedxml'

npm ls -g --depth=0                   # → 全局列表里【没有】pptxgenjs / sharp / playwright
```

| 依赖 | `pptx` 技能说它要 | 实测 |
|---|---|---|
| `pptxgenjs`（npm 全局） | ✅ 要（"创建演示文稿"） | ❌ **未装**（`npm ls -g` 里没有） |
| `python-pptx` | ✅ 要（模板段/编辑段全篇用它） | ❌ **未装**（`py -3.14` 下 ModuleNotFound） |
| `markitdown[pptx]` | ✅ 要（文本抽取） | ❌ **未装** |
| `playwright` / `sharp` | ✅ 要（HTML 渲染 / SVG 光栅化） | ❌ **未装** |
| `defusedxml` | ✅ 要（安全 XML 解析） | ❌ **未装** |
| **LibreOffice**（`soffice`） | ✅ 要（PDF 转换） | ❌ **不在 PATH**；`C:\Program Files\LibreOffice\...` 不存在 |
| **PowerPoint 本体** | （预览用） | ✅ **在**：`C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE` |
| `lxml` / `matplotlib` / `ruamel.yaml` | `pptx-swarm/scripts/requirements.txt` 要 | ❌ **未装**（`Pillow` 与 `requests` 装了） |

⚠️ **`pptx-swarm` 的脚本是 `bash`，但它的脚本头写的是 `python3`** —— 这两个在 Windows 上是**两回事**：

```powershell
# ✅ 已验（真跑）
Get-Command bash   # → C:\WINDOWS\system32\bash.exe    （在！）
Get-Command sh     # → C:\Program Files\Git\bin\sh.exe （在）
Get-Command python3 # → C:\Users\ADMIN\AppData\Local\Microsoft\WindowsApps\python3.exe
python3 --version  # → Python 3.14.5
```

⇒ **`bash` 在、`python3` 也在**，所以 `convert.sh` / `check.sh` 的**解释器那一层能起来**；
**真正缺的是它们要调的东西**（见 §4.2 那条 🔴）。

### 3.3 闸一的正确说法

**「本簇 3 位真业务件不需要任何密钥」≠「本簇能出片」** ——
`pptx-swarm` 要的 Python 依赖没装、`pptx` 要的 pptxgenjs/python-pptx 没装、
`pptx-html-fidelity-audit` 的两个脚本要 `python-pptx` 也没装。
⇒ 现在能说的最硬一句是：**"设计铁律与工作流我都读全了，工具链还没装。"**

---

## 4. 怎么调（**真命令 + 真返回**）

> 纪律：本节每一条都标了 **✅(真跑过)** 或 **(未验)**。**没跑过的不许说成跑过。**

### 4.1 `pptx-swarm` 的 guard（**唯一真跑通的脚本**）

```powershell
# ✅ 已验：在缺件的盘上跑 --help 与 --pre-spawn
Push-Location "C:\Users\ADMIN\.openclaw-autoclaw\skills\pptx-swarm"
py -3.14 scripts\pptd_guard.py --help
py -3.14 scripts\pptd_guard.py nonexistent_deck.pptd --pre-spawn
Pop-Location
```

**真返回（`--help`，原文）**：

```
usage: pptd_guard.py [-h] [--pre-spawn] [--post-pages] [--allow-extra-pages]
                     pptd

Guard rails for PPTD swarm projects.

positional arguments:
  pptd

options:
  -h, --help           show this help message and exit
  --pre-spawn
  --post-pages
  --allow-extra-pages
```

**真返回（`--pre-spawn` 打空盘，原文摘录）**：

```json
{
  "pptd": "…\\pptx-swarm\\nonexistent_deck.pptd",
  "page_count": 0,
  "page_types": {},
  "expected_missing_pre_spawn_pages": [],
  "full_slide_image_like_pages": [],
  "errors": [
    "missing pptd: …\\nonexistent_deck.pptd",
    "missing required file: design.md",
    "missing required file: outline.md",
    "missing required file: page_manifest.json",
    "missing pages/ directory",
```

🔴 **这一发就是本簇最值钱的读数**：guard **真的会咬人**，缺什么就逐条报什么，
而且它返回的是 **JSON 信封**（不是异常）。⇒ 建 workdir 时**照 `errors` 数组补件**，
补完再 `--pre-spawn`，直到它不再报 —— **这比"照着 SKILL.md 猜目录形状"可靠。**

### 4.2 `pptx-swarm` 的转换与检查（🔴 **盘上缺件，跑不了**）

```bash
# 技能的 SKILL.md 写的是这两条（原文）
scripts/convert.sh input.pptd -o output.pptx      # SKILL.md:29
python3 scripts/pptd_guard.py <deck>.pptd --post-pages
```

**`convert.sh` 的真实内容（✅ 已读原文）**：

```bash
PYTHON_BIN="${PPTD_DSL_PYTHON:-${PPTD_PYTHON:-python3}}"
if [ -f "$SCRIPT_DIR/pptd_dsl.pyz" ]; then
    exec "$PYTHON_BIN" "$SCRIPT_DIR/pptd_dsl.pyz" convert "$@"
fi
echo "pptd_dsl.pyz not found in $SCRIPT_DIR" >&2
exit 1
```

🔴 **真身实测：`pptd_dsl.pyz` 在盘上不存在。**

```powershell
# ✅ 已验
Get-ChildItem "C:\Users\ADMIN\.openclaw-autoclaw\skills\pptx-swarm\scripts" | Select-Object Name,Length
```

真返回（原文）：

```
Name                   Length
----                   ------
__pycache__
check.sh               452
convert.sh             454
pptd_dsl.pyz.larkcache 94724829
pptd_guard.py          6895
pptd_layout_lint.py    12979
pptx_repair_gate.py    10646
requirements.txt       123
```

⇒ **盘上只有 `pptd_dsl.pyz.larkcache`（94.7 MB，扩展名被追加成 `.larkcache`），
没有 `pptd_dsl.pyz`。** 而 `convert.sh` / `check.sh` 的判据是 `[ -f "$SCRIPT_DIR/pptd_dsl.pyz" ]`
⇒ **两脚本会直接走 `echo` + `exit 1` 分支**。
⇒ **`pptx-swarm` 的"checker 到 0 errors"与"convert 出 pptx"这两步，本机当前跑不了。**
（这**不是**我改的：本件**不动**任何 skill 文件。**要不要把 `.larkcache` 恢复成 `.pyz` 由主人定。**）

⚠️ **未验**：`bash scripts/convert.sh` / `check.sh` 的**真实执行**（因为上面那条缺件，
现在跑必然只拿到 `exit 1` 的"not found"，**我按纪律不把它包装成"跑过了"**）。
`scripts/pptx_repair_gate.py` / `pptd_layout_lint.py` 的 `--help` 与真跑也**未验**。

### 4.3 `pptx-html-fidelity-audit` 的两个脚本（**未验：依赖没装**）

```bash
# SKILL.md 原文两条
python3 scripts/extract_pptx.py <path-to.pptx> > pptx_dump.json
python3 scripts/verify_layout.py <path-to.pptx>
```

**未验**，卡在一处：两脚本都要 `python-pptx`（`extract_pptx.py` 走 `Presentation()`，
`verify_layout.py` 要走每个 shape 的 `top/height/left/width`），
而实测 `py -3.14 -c "import pptx"` ⇒ **`ModuleNotFoundError: No module named 'pptx'`**。
⇒ **要跑先装 `python-pptx`；没装之前这两条命令本件不背书。**

### 4.4 `pptx` 技能（**无脚本，是"原则 + API 手册"**）

`pptx` 没有可执行脚本（盘上只有 `SKILL.md` + `LICENSE.txt` + `_store_meta.json` + `.bundled-hash`）
—— **它是知识件**。它给的两条硬约束值得单拎：

- **`LAYOUT_WIDE` 必须显式设**：pptxgenjs 默认 `LAYOUT_16x9` = **10 × 5.625"**，
  而全篇字号（44–72pt 标题 / ~24pt 正文 / 60–72pt 数字）是按 **13.33 × 7.5"** 调的
  ⇒ **不设就系统性溢出**（这正是 §9/§10 反复要你避免的那个失败）。
- **`pip install` / `npm install -g` 是"装环境"**，会**改本机** ⇒ 属于要报备的动作（见 §6）。

---

## 5. 闸二 · 出片/上传/发布的动作**必须先问主人**

**本条高于技能自己的任何提示。** 本簇里"写出去"的动作：

| 动作 | 为什么算"写出去" |
|---|---|
| **上传/发布成品 deck 到任何公开或他人可见的地方**（公众号、飞书云文档、网盘分享链、Confluence、客户邮箱…） | **不可撤回的社会动作**：发出去就有人看到了 |
| **把 deck 发给真人**（作为附件/链接） | 同上 |
| **覆盖/删除用户已有的 `.pptx` 原件**（`pptx` 编辑段虽是"改副本"，但删页/覆盖落盘仍是写） | 破坏性写；`pptx` 自己也要求**先在副本上做** |
| **装环境**（`pip install` / `npm install -g` / `sudo apt-get` / 装 LibreOffice） | **改本机全局状态**，且本机现在一个都没装（§3.2） |
| **`npx skills add …` 装上游技能包**（如 `pptx-generator` 的 `MiniMax-AI/skills`） | **出网 + 改技能目录**；工作区 AGENTS.md 明令**不许往 `~/.agents/skills` 装** |
| **动 `pptx-swarm` 脚本里的 `pptd_dsl.pyz.larkcache`** | 改的是**别人技能的盘上状态**，本件**绝不擅自动手** |

**顺序（先干什么 → 拿什么回执）**：

1. **摊开四件事**：**身份**（以谁的名义）· **目标**（哪个文件/哪个链接，**指名道姓**）·
   **内容**（原文，或至少逐字摘要）· **影响面**（谁会看到、能不能撤回、覆盖了能不能恢复）。
2. **能预演就先预演**：`pptx-swarm` 的 `pptd_guard.py`（**只读 JSON，不落盘**）
   与 `pptx-html-fidelity-audit` 的 `extract_pptx.py`（**只读 dump**）都**不写任何东西** ——
   **先跑它们，把读数贴给主人看。**
3. **等一次明确同意**：**只覆盖这一次**，不是"以后这类都同意"。主人没回话 = **没同意**，停。
4. **同意后照原命令重试** —— 不是重写一条新命令。
5. **拿回执**：要读到**成品文件的绝对路径** + 页数 + 文件大小。
   `pptx-swarm` 甚至把这条写进了它的第 16 条：最终回复**必须**含绝对 `.pptx` 路径、页数、
   一句话设计摘要、已知残留缺陷，并以 `任务已结束` 结尾。
6. **失败就记失败**：原样保留错误与退出码，**不许把失败写成成功**。
7. **不许静默重试写操作**：覆盖/重打包类动作盲重试会**把产物写坏**（见 `[Content_Types].xml` 那条）。

---

## 6. 🔴 报告层红线（读数纪律）

1. **读数先问一句：这是事实，还是我读错了地方？** 本簇有三个"形状对、内容错"的陷阱：
   - **`omni.py gaps` 报 `pptx-* 3 条`**，而按更全的 `name.startswith("pptx")` 数是 **4 条**
     （裸名 `pptx` 漏在外面）⇒ **别把 3 当成本簇的全量。**
   - **`omni.py list --domain pptx` 是宽松匹配**：它会带进非本簇的行
     ⇒ **名单一律回图鉴按 `name` 前缀数**，别拿 `--domain` 的打印当权威。
   - **`pptx-generator` 是 `design-asset` 通道的目录桩** ⇒ **别拿"图鉴里有它"当"本机能跑它"。**
2. **「能调」≠「能用」**：本簇 3 位真业务件的 SKILL.md 都写得像随时能用，
   但实测 **`python-pptx` / `pptxgenjs` / `markitdown` / `defusedxml` / LibreOffice 一个都没有**，
   `pptx-swarm` 的 `pptd_dsl.pyz` **根本不在盘上**。
   ⇒ **"技能描述得很完整"和"这台机器上跑得起来"是两件事。**
3. **`0 errors, 0 warnings` 是 checker 自己的账，不是成品合格**：
   `pptx-swarm` 第 12 条要 checker 到 `0 errors, 0 warnings`，第 13 条却明说
   `pptd_layout_lint.py` 是 **advisory（顾问性的）**、"**do not fail delivery only because a
   heuristic score is low**"。⇒ **checker 绿 ≠ 版式好**；两者不许互相冒充。
4. **`pptd_guard.py` 的 `errors: []` 只说明"该有的文件都在"**，不说明"内容对"：
   它查的是 `page_manifest.json` 与 `.pptd pages:` 的**顺序一致**、`pages/` 存在等**结构**；
   **文案质量、审美、事实正确性它一概不管**。
5. **有错也照原样记**：保留错误原文与**退出码**。`convert.sh` 缺件时的 `exit 1` 是**环境缺件**，
   **不是**"命令敲错了"。
6. **不许编命令、编路径、编技能名**：本文件每条命令要么标 **✅ 已验**，要么标 **(未验)** 并写明卡在哪。
   **没跑过的不许说成跑过。**
7. **凭据只报"已配/未配"或前 4 位掩码**：本件**零凭据**，这是纪律不是遗漏。

---

## 7. 本机踩过的坑（照做，别自己解读）

1. ✅ **`pptx-swarm` 的 `convert.sh` / `check.sh` 现在必然 `exit 1`。**
   真因：判据是 `[ -f "$SCRIPT_DIR/pptd_dsl.pyz" ]`，盘上**只有 `pptd_dsl.pyz.larkcache`**
   （94.7 MB）。**别把这读成"PPTD 工具坏了"或"命令敲错了"** —— 是**缺件**。
2. ✅ **`pptx-swarm` 的脚本是 `bash` + `python3` 的组合。**
   Windows 上 `bash`（`C:\WINDOWS\system32\bash.exe`）与 `python3`
   （`…\WindowsApps\python3.exe`，实测 **3.14.5**）**都在**，
   所以"Windows 上跑不了 bash"这个猜测**是错的** —— **卡点在缺件，不在解释器。**
3. ✅ **`py -3.14` 与 `python3` 现在是同一个版本（3.14.5）**，
   但 `py -0p` 显示本机有 **3.14 / 3.13 / 3.12 / 3.10** 四个版本外加 4 个 uv 装的 CPython。
   ⇒ **`pip install` 之前先想清楚装到哪个解释器**，否则"装了还是 ModuleNotFound"。
4. ✅ **`pptx` 技能的 `pip install` 列表里 `sudo apt-get install libreoffice` 是 Linux 写法**，
   本机是 Windows ⇒ **照抄那条必然失败**。本机**没有** LibreOffice，**有** PowerPoint
   （`…\Office16\POWERPNT.EXE`）。
5. ✅ **`pptx` 技能明说"不要在 QA 里调外部 VLM 看幻灯片"**（原文：
   *「Do not call external vlm to check slides for visual QA」*）
   ⇒ **别自作聪明拿识图技能去"看一眼版式"。**
6. ✅ **`pptx-html-fidelity-audit` 明确放弃了"视觉 diff"路线**，理由是
   **平台锁定 + 精度差（1–2 mm 溢出被抗锯齿抹掉）+ 环境成本**，
   改走 **geometry-based verification**（纯 `python-pptx` 量坐标）。
   ⇒ **别给它加 Keynote/magick 那条链**，那是它**已经淘汰**的旧法。
7. ✅ **目录桩不会自己告诉你它是桩。** `pptx-generator` 的 frontmatter 里
   `od.mode: deck` 看着像业务件，**"这是桩"这句写在正文第 30 行之后**。
   ⇒ **触发一个 design-asset 技能前，先看它正文有没有"install the upstream bundle"。**
8. ⚠️ **（未验）`pptx-swarm` 的页 agent / QA agent 编排。**
   技能第 9–15 条讲得极细（每 agent 2–4 页、不许把整 deck 给一个 worker、
   独立 QA agent 写 `qa/subagent_qa.md`），但**本规程没真跑过一次多 agent 编排**。
   **这是"读到的规程"，不是"跑过的经验"。**

---

## 8. 未验清单（**如实列，不许拿它当通过**）

| 项 | 卡在哪 / 为什么不做 |
|---|---|
| **`pptx-swarm` 真出一条 `.pptx`** | **未验**。卡在 `pptd_dsl.pyz` 缺件（§4.2）+ `python-pptx`/`lxml`/`matplotlib`/`ruamel.yaml` 未装（§3.2）。两条任一条都不该由我擅自补 |
| **`check.sh` 跑到 `0 errors, 0 warnings`** | **未验**。同上卡在 `pptd_dsl.pyz`；**"checker 说 0 错"本身也不等于成品合格**（§6.3） |
| **`pptx_repair_gate.py` / `pptd_layout_lint.py` 真跑** | **未验（未跑）**。它们要 `qa/judge/summary.json` + `packet.json` + 渲染出的 slide 图 —— 本机**一次 deck 都没造过**，没有这些输入 |
| **`extract_pptx.py` / `verify_layout.py` 真跑** | **未验**。要 `python-pptx`（未装）+ 一份真实的 `.pptx`（本机没现成样本） |
| **`pptx` 的 pptxgenjs 全流程** | **未验**。要 `npm install -g pptxgenjs` = **改本机全局环境** + 出网（§5 要报备） |
| **`pptx` 的模板段（Clone & fill / Fill-in）** | **未验**。要一份用户提供的 `.pptx` 模板 + `python-pptx` |
| **`pptx-generator` 的上游包** | **未验（且本件不装）**。要 `npx skills add https://github.com/MiniMax-AI/skills` = **出网 + 主人点头 + 改技能目录** |
| **本簇是否该进 `omni.py` 的 `DISTILLED_CLUSTERS`** | **未验（且本件不擅自动手）**。登记是交付报告里给主人的一行，**本件不自己写进 `omni.py`**（见 §10） |
| **本簇除这 4 条外还有没有隐藏成员** | **未验（口径性未验）**。图鉴是**现扫产物**（`python tools/codex-scripts/omni.py build`），重建后需重查 |

---

## 9. 不许做什么（红线）

1. **不许动 `tools/codex-scripts/omni.py` / `security/policy.py`** —— 本件只加一份规程，**不改门、不改登记表**。
2. **不许改 `~/.openclaw-autoclaw/skills/pptx*` 下任何技能文件**（包括那个 `.larkcache`）——
   **本件是被管对象的规程，不是它的补丁。**
3. **不许往 `~/.agents/skills/` 写任何东西**（工作区 AGENTS.md 明令：那是别的工具的共享目录）。
4. **不许擅自装环境**：`pip install` / `npm install -g` / 装 LibreOffice / `npx skills add`
   都要**出网 + 改本机 + 主人点头**。
5. **不许把目录桩念成能力**：`pptx-generator` 无脚本、上游未装，**它不能被"执行"**。
6. **不许把 `0 errors, 0 warnings` 念成"成品合格"**，也**不许**把
   `pptd_guard.py` 的 `errors: []` 念成"内容对"（§6.3 / §6.4）。
7. **不许把 `pptd_dsl.pyz` 缺件念成"PPTD 工具坏了"** —— 是**缺件**（§7.1）。
8. **不许把本规程当官方文档**：本簇 4 条技能的**命令级细节以它们自己的 `SKILL.md` 为准**；
   本文件管的是**我们这儿的纪律、读法、诚实账**。
9. **不许不发成品就报"做完了"**：`pptx-swarm` 第 16 条要绝对路径 + 页数 + 摘要 + 残留缺陷；
   **没有真文件就不许说交付。**

---

## 10. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源 · 真身） | `<仓>/skills/gbt-pptx/SKILL.md` |
| 本规程（装机 · 托管目录） | `~/.openclaw-autoclaw/skills/gbt-pptx/SKILL.md`（**与源稿逐字节相同**） |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 技能名单（4 条） | `<仓>/state/skill_atlas.json`（`name` 以 `pptx` 开头）· 现扫可重建：`python tools/codex-scripts/omni.py build` |
| 被管的 3 条真业务件 | `~/.openclaw-autoclaw/skills/`（`pptx` · `pptx-swarm` · `pptx-html-fidelity-audit`）—— **不由本件代管，别改** |
| 被管的 1 条目录桩 | `<仓>/审美相关skill/skills/pptx-generator`（`design-asset` 通道） |
| 人话入口 | `python tools/codex-scripts/omni.py ask "帮我把这份 HTML 做成 PPT"` |
| 验收 | `py -3.14 tools/codex-scripts/verify-distill.py --cluster pptx` |

**深蒸登记（应加、本次未擅自动手）**：`omni.py` 的 `DISTILLED_CLUSTERS` 加一行

```python
    "pptx": "gbt-pptx",               # 4 条（3 真业务件 + 1 目录桩）：按意图分簇 + 两道闸
```

加完后 `verify-distill.py --cluster pptx` 才会从 **`FAIL: 没登记这个簇`** 变 PASS。
（本次**没改** `omni.py` —— 交付报告里给主人这一行，**没交付就会 FAIL，不会静默变绿**。）

---

## 11. 诚实边界（这段不许删）

1. **本件是"用法规程"，不是"能力已具备"。** 它把 4 条技能**分簇、点名、定了纪律**；
   **每条技能的深度用法以它自己的 `SKILL.md` 为准**，本件**不替代**。
2. **本次实跑的都是只读命令**：`omni.py list` · 图鉴前缀清点 · `Get-Command` · `--version` ·
   `npm ls -g` · `import` 探针 · `pptd_guard.py --help` / `--pre-spawn`（打空盘）·
   `Get-ChildItem` 列脚本。**没有产出过任何一份 `.pptx`，没有装过任何依赖，没有改过任何技能文件。**
3. **本机状态是现读快照**（Python 3.14.5 · Node v24.15.0 · npm 11.12.1 · 缺 `pptd_dsl.pyz` ·
   缺 `python-pptx`/`pptxgenjs`/LibreOffice · 有 PowerPoint）。
   **换机器、装完依赖、或图鉴重建后，本件的读数都要重查。**
4. **凭据只报"已配/未配"**：本件**不出现任何凭据**，因为本簇**不需要密钥**、且实测全机密钥池 `keys_total: 0`。
5. **`gbt-pptx` 与 `gbt-video` / `gbt-video-tools` / `gbt-arkcli` 的边界**见 §0；
   **谁都不许拿对方的读数替自己说话。**
