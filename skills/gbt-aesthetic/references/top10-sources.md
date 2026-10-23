# 蒸馏来源 · 热度最高的 10 个审美技能（2026-09-22 调研）

> 本文件是 `gbt-aesthetic` 的**取材记录**。调研于 2026-09-22，**证据强弱分开标**：
> `一手` = 直接读 GitHub REST API `/repos/...`（星/叉）；`二手` = 来自第三方聚合快照
> （`github.com/LinklyAI/best-skills` 的 `data/2026-09-09/rankings/best-100.csv` 里
> `installs_skillssh` 一列），**当弱证据用**。取不到数字就写 `无数字`，不估算、不编。

| # | 技能 | 来源 | 热度（证据来源） | 独门机制（我抽走的那一条） | 形态 | 许可 |
|---|---|---|---|---|---|---|
| 1 | `frontend-design`（Anthropic） | skills.sh/anthropics/skills · github.com/anthropics/skills | 868,368 安装（**二手**）；父仓 177,592★/21,034 叉（一手） | **点名 hex 的 AI 味清单**（奶油 `#F4F1EA`+赤陶 `#D97757`、酸绿配黑、harshairline 报纸风、SaaS 卡片套件、全大写眉标、中点分隔的元信息、"→" 链接）；两遍法：先定 4–6 个命名色 + 字体角色 + ASCII 线框，再自问"这版换任何一个 brief 也成立吗" | 纯 markdown | 仓内 LICENSE.txt（API 无 SPDX） |
| 2 | `taste-skill` / 安装名 `design-taste-frontend`（Leonxlnx） | github.com/Leonxlnx/taste-skill | 89,219★/6,072 叉（一手）；458,658 安装（二手） | **三档数值转盘** `DESIGN_VARIANCE`/`MOTION_INTENSITY`/`VISUAL_DENSITY`（默认 8/6/4，公共部门站自动收紧）；brief→设计系统映射；**破折号禁令**；GSAP 骨架；改版审计协议 | markdown + assets | MIT |
| 3 | `ui-ux-pro-max`（nextlevelbuilder） | github.com/nextlevelbuilder/ui-ux-pro-max-skill | 129,759★/13,814 叉（一手，**专做设计的技能里星最多**） | 唯一带**数据+引擎**：对 CSV 做 BM25 检索（192 条行业规则、79 种风格、192 套配色、74 组字体搭配、25 类图表、119 条 UX 准则、22 个技术栈）；`uipro init`；把设计系统落到 `MASTER.md` | markdown + Python + CSV + CLI | MIT |
| 4 | `web-design-guidelines`（Vercel） | skills.sh/vercel-labs/agent-skills | 618,890 安装（二手）；仓 31,456★/2,761 叉（一手） | **规则不内置**：每次审查现拉 `raw.githubusercontent.com/.../command.md`，所以永不陈旧；只出 `文件:行` 的简短发现；**只审不生成** | 纯 markdown | API 无许可 |
| 5 | `open-design`（nexu-io）〔**相邻**：是应用/插件，不是纯技能〕 | github.com/nexu-io/open-design | 97,592★/11,332 叉（一手） | 把任意 CLI（Claude Code/Codex/Cursor/DSH/OpenCode…20+）变成设计引擎；本地优先；真文件产出 HTML/PDF/PPTX/MP4；**捆绑 `craft/` 与 `design-systems/`**（本仓那批素材即出于此） | TS 桌面应用 + 技能包 | Apache-2.0 |
| 6 | `huashu-design`（alchaincyf） | github.com/alchaincyf/huashu-design | 24,381★/2,788 叉（一手） | **品牌资产协议**：**绝不猜品牌色** —— 去 `<brand>.com/brand` + 新闻稿抓，再把下载到的 SVG/HTML 里所有 `#xxxxxx` 按出现频次排序取值；冻结 `brand-spec.md` + CSS 变量；5 学派×20 哲学 → 3 个分歧方向并行；五维打分雷达；Playwright 自点击验证 | markdown + JS 导出器 | MIT |
| 7 | `make-interfaces-feel-better`（jakubkrehel） | github.com/jakubkrehel/make-interfaces-feel-better | 3,492★/145 叉（一手） | **只做微手艺、不给审美方向**：动画、排版、图标、hover 态、光学对齐、同心圆角、阴影、点击热区 | 纯 markdown | MIT |
| 8 | `design-motion-principles`（kylezantos） | github.com/kylezantos/design-motion-principles | 1,119★/77 叉（一手） | 双模式（建/审）；按设计师（Emil Kowalski / Jakub Krehel / Jhey Tompkins）分派指导；**找出"本该有动效却没有"的地方**（缺 `AnimatePresence`/transition），按严重度排序 | markdown | MIT |
| 9 | `bencium-controlled-ux-designer`（Bencium） | github.com/bencium/bencium-marketplace | 433★/58 叉（一手） | 双模式 **受控**（生产：WCAG、响应式规格、动效约束）vs **创新**（允许破规矩）；渐进披露：约 830 行 `ACCESSIBILITY.md`、约 600 行 `RESPONSIVE-DESIGN.md`、`MOTION-SPEC.md`、`DESIGN-SYSTEM-TEMPLATE.md` | markdown + 参考文件 | MIT |
| 10 | `taste-skill`（senlindesign） | github.com/senlindesign/taste-skill | 365★/28 叉（一手） | **把某个现成网站的品味逆向成具体令牌，并连"为什么"一起搬**（不只搬 WHAT，还搬取舍理由）—— 移植的是判断，不是通用规则书 | markdown/JS | 无许可 |

**被排除的**：纯生图技能；`superdesign`（6,994★，产品设计 agent）；`claudedesignskills`（920★，动效库）；`frontend-design-pro-demo`（274★）；`everything-design-taste`（12★）、`ux-ui-design-taste`（1★）。

---

## 十个来源的共识（蒸馏出的公因子）

1. **动手前先点明一个具名的审美方向**，而且这个方向要**由题材决定**，不是由模型口味决定；
2. **拉黑 AI 特征**：紫渐变、居中 hero + 三张等宽卡、emoji 当图标、处处同一个圆角、清一色 `rgba(0,0,0,.1)` 阴影、全大写眉标；
3. **排版扛个性**：字体要**有意搭配**、字阶要**显式写死**、正文 <80ch；
4. **产出令牌**（4–6 个命名色、CSS 变量 / `@theme` / `MASTER.md`），让选择**能留存**；
5. **交付前清单**：对比度 4.5:1、可见焦点、`prefers-reduced-motion`、375/768/1024/1440 四档、圆角与强调色一致；
6. **克制**：大胆只放**一处**；动效只在**回应了用户动作**时才加；
7. 分发形态 = `SKILL.md` + `npx skills add`，多 agent 通用。

## 它们的真实分歧（照实记，别假装一致）

- **目录派 vs 反目录派**：`ui-ux-pro-max` 硬编码 79 种风格让你挑一种；Anthropic 警告**任何固化的观感都会变成下一代继承来的默认**；
- **生成 vs 审查**：Vercel 只审不生成，规则还远程现拉；
- **markdown vs 引擎**：确定性只有带工具的一派（`ui-ux-pro-max` 的 Python/CSV、`huashu` 的导出器+Playwright）敢声称；
- **动效取向**：`taste-skill` 推电影感 GSAP，Anthropic 只要"一个有编排的瞬间"；
- **品牌优先 vs 品味优先**：`huashu` 禁止猜品牌色，另一派在空 brief 上直接发明审美；
- **覆盖面**：`taste-skill` v2 自认**不覆盖**仪表盘/数据表/多步产品流 —— 而那恰好是 `ui-ux-pro-max` 的主场。

## 它们的共同空白（我们的机会）

1. **没有共享的评测/基准，也没有视觉回归**；唯一那个"方差降低 5 倍"是自报的；
2. **没有一个是解决「尊重我已有的设计系统，只加一个组件，别的都不许动」** —— 而这正是本仓 `AGENTS.md` 的 Redesign 分支要处理的缝；
3. 应用现实覆盖弱：数据密集表、权限、延迟/乐观 UI、空/错/载入态、i18n+RTL+长令牌；原生移动/TV/空间几乎没有；
4. 无障碍多是**清单**，不是带工具输出的**已验证审计**；
5. 安装榜顶部的**许可卫生差**（`vercel-labs/agent-skills`、`senlindesign/taste-skill`、`claudekit` 无许可）；
6. **星数奖励营销而非质量**（12.9 万★ 的"技能"主体是个 Python 检索脚本），而安装量只能靠第三方聚合。

**我们据此补的三样**（`gbt-aesthetic` 相对它们的增量）：

- **可机检的审计器** `tools/codex-scripts/audit_aesthetic.py` —— 直接回应空白 1（把"AI 味"变成能跑、能指行号、P0 会让退出码非零的检查），且**明确列出查不了的**，不用"已全面检查"糊过去；
- **§6.6 只加一个组件**（见 SKILL.md）—— 直接回应空白 2；
- **固化纪律**（§8）—— 能力必须落盘在**会被读取的目录**，不活在进程内；这是本仓踩过坑换来的。
