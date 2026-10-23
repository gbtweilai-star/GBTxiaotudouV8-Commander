# 上游 `frontend-design` 逐字对照（**纠正一条我先前的错报**）

> 取源：`https://raw.githubusercontent.com/anthropics/skills/f458cee31a7577a47ba0c9a101976fa599385174/skills/frontend-design/SKILL.md`
> （**钉死 commit**，2026-09-23 取，HTTP 200）
> 本机对照件：`~/.openclaw-autoclaw/skills/frontend-design/SKILL.md`（68 行 / 3622 B）

---

## 0. 🔴 先纠正我自己

我在 2026-09-23 的工作汇报里说过：

> 「我们盘上那份 `frontend-design` 是**改版前的旧版**……外面已经改成
> 『描述失败模式 + 六个设计原则 + **两遍流程** + 克制律 + 一整章写作』—— **差了整整一个世代**。」

**这句话有错，而且错得方式值得记下来。**

- 那个说法来自一篇**第三方文章**（DEV 上的 skill 目录站写的"深读"），**不是**上游文件本身；
- 我把上游文件真身取回来逐字读完 —— **「六个设计原则」「两遍流程」「克制律」「写作章」这四样，上游这个 commit 里一个都没有**；
- 真实差异是**三处、都比较小**（见 §2）。

⇒ **教训**：**二手报道不能当一手事实用**。我甚至在那份报告里把"描述失败模式"当成"官方改版的核心工程决策"写了进去 ——
而真身里那句话只是**把禁令折回散文**，不是一套新流程。
本仓的规矩本来就是「以源码为准」，我这次对**第三方技能**放松了这条，记在这里。

⚠️ 另一种可能（**没排除**）：官方在别的分支/更晚的 commit 上确实有那套流程，我只取了这一个 commit。
**要把"排除"做干净，得再取 `main` 与时间线对比** —— 这一步本轮没做，**如实标注为未验**。

---

## 1. 上游真身有什么（逐字要点，非全文搬运）

- frontmatter：`name` / `description` / **`license: Complete terms in LICENSE.txt`**
- `## Design Thinking`：Purpose · **Tone**（"Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic,
  organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric,
  soft/pastel, industrial/utilitarian… **Use these for inspiration but design one that is true to the aesthetic direction**"）·
  Constraints · Differentiation（"What makes this UNFORGETTABLE? What's the one thing someone will remember?"）
- `**CRITICAL**`：明确方向 + 精确执行；"Bold maximalism and refined minimalism both work - the key is **intentionality, not intensity**"
- 交付四条：production-grade / visually striking / cohesive with a clear POV / **meticulously refined in every detail**
- `## Frontend Aesthetics Guidelines`（五条，见下）
- 一段 **NEVER use generic AI-generated aesthetics…** 的散文禁令
- `**IMPORTANT**`：实现复杂度要匹配审美愿景；"Elegance comes from executing the vision well."
- 结尾 `Remember:` 一句

---

## 2. 真实的差异（**只有这三处**）

| # | 上游当前 | 本机 68 行版 | 值不值得拿 |
|---|---|---|---|
| ① | `description` **扩了触发面**：明确点名 **artifacts / posters / dashboards**，以及「**styling/beautifying any web UI**」 | 只写了 components / pages / applications | ✅ **值得** —— 触发面窄 = 该用时没被唤起 |
| ② | 禁令是**一段散文**，夹在 Guidelines 里；并加一句「**NEVER converge on common choices (Space Grotesk, for example) across generations**」 | 单列 `## Anti-Patterns` 小节 + 列表式 NEVER | ✅ **值得**（方向一致：描述 > 黑名单；且"跨次生成不要收敛到同一个选择"是**新增信息**） |
| ③ | Motion / Backgrounds 两段**更具体**：<br>· Motion："one well-orchestrated page load with **staggered reveals (animation-delay)**" · "**scroll-triggering** and hover states that **surprise**"<br>· Backgrounds："**Add contextual effects and textures that match the overall aesthetic**" | Motion 只说到"one well-orchestrated page load with staggered reveals"；Backgrounds 只有一串形式名（gradient mesh / noise / grain…） | ✅ **值得** —— "**matching the overall aesthetic**" 是判据，比形式清单有用 |

**其余部分逐字基本一致**（Tone 的形容词表、五条 Guidelines 的骨架、CRITICAL/IMPORTANT/Remember 三句都在两边）。

---

## 3. 我此前"已固化"的东西要不要撤

我在 `gbt-aesthetic` 里加的三节，**来源要重新标注**：

| 我加的 | 真实出处 | 处理 |
|---|---|---|
| §3.0 三种 AI 默认长相（暖奶油 / 近黑+亮酸 / 大报版式，带 hex） | **DEV 文章里引用的官方原文段落** —— 上游这个 commit 的文件里**没有这一段** | ⚠️ **保留，但改标为"二手引用，未在真身复现"**；它本身是有用的判据，且我们自己的自查（深空底落在"乙"）也是照着它做的 |
| §1.6 两遍流程 + 克制律 | **同上，二手**。「两遍流程」上游真身没有；「把大胆花在一个地方 / 香奈儿法则」也**不在**这个 commit 里 | ⚠️ 同上：改标来源，**不撤**（它们与 `taste-skill` 的"三档转盘 + Design Read"是一路，且实测有用） |
| §1.5 页面类别分流（门面页可花 / 数据台要静） | **不是抄的** —— 是我自己渲图渲出来的（数据台整板自转 ⇒ 满页字歪） | ✅ 来源标注本来就写对了，保持 |

**为什么不撤**：这三节的价值由**它们在实践里管不管用**决定，不由出处决定。但**出处必须标对** ——
把二手说成一手，下一个人就会拿它当"官方权威"去压别的判断，那才是真损害。

---

## 4. 本轮真正要落进 `gbt-aesthetic` 的（就三条）

1. **触发面**：把"做页面/组件"扩到 **artifact / poster / dashboard / 任何 web UI 的美化**；
   原因是**窄触发 = 该唤起时唤不起**（本仓已有同型教训：中文口语打不中英文触发词）。
2. **跨次生成不许收敛**：同一类任务连做几次，**不许每次落到同一个选择**（上游点名 Space Grotesk 这类"新默认"）。
   ⇒ 与本仓 §3.0 的"描述失败模式"合起来读：**黑名单会过期，"收敛"这个行为本身不会**。
3. **动效与背景要有判据**：page load 用 **`animation-delay` 做错落揭示**（一次编排好，好过撒一地微交互）；
   用 **scroll-trigger / hover 制造意外**；背景加**与整体审美相配的**纹理与氛围 ——
   关键词是 **matching the overall aesthetic**，不是"加个噪点就高级"。
