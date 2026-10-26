# 吞噬记录 · Leonxlnx/taste-skill（深度）

> 吞噬日期：2026-10-26 ｜ 来源：https://github.com/Leonxlnx/taste-skill
> ★ 102,434 · fork 6,924 · MIT · 最近推送 2026-10-25 ｜ 文件 72 · 文本语料 ≈ 2.07 MB
> 落盘：`vendor/taste-skill/`（原库全留，供检索）· 内核：`state/taste_kernel.txt`（她 4096 窗口能吃的那份）
> 视频来源的那个卡片把作者名印成 `Leonxlinx`（多一个字母），真身是 `Leonxlnx`；`api.github.com` 直查 404 的是错拼那个。

## 它是什么

不是一个 UI 组件库，是**给编码智能体的"品味"技能**：一套判决性的家规（House rules）＋
一门手艺的法则（Laws of the craft）＋可抽签的方向库（directions/palettes/type/heroes/sections/motions）＋
一个会量数字的检查器（`inspect.mjs`；另有 `lint.mjs`）。核心主张：

> 去掉装饰不等于好看。**删掉的东西必须用「尺度、完整内容、为题材定制的图、一整片纯色」补回来**，
> 而不是换一种装饰去填。

数据来源：对 247 个真实站点的盲测评分（jurors + 测量），把"高分站与低分站的差别"写成禁令与数字。

## 语料地图（原文在哪）

| 块 | 文件 | 大小 | 里面是什么 |
|---|---|---|---|
| 主技能 | `skills/taste-skill/SKILL.md` | 39.5 KB | 流程（the run）· 家规 · 法条 · 特例 |
| 反模式登记册 | `references/tells.md` | — | 三代 slop 潮流 + 结构/文案/动效 tell |
| 深读 11 篇 | `references/{type,colour,layout,imagery,motion,copy,critique,research,scenes,app-screens,tells}.md` | ≈ 300 KB | 每域一篇判决手册 |
| 方向库 | `library/{directions,palettes,type,heroes,sections,motions}.json` | ≈ 260 KB | 抽签用的方向与素材 |
| 实站库 | `library/{sites,app,photos}.json` | ≈ 1.2 MB | 2,000+ 实站/界面/图源条目 |
| 可复用资产 | `assets/{app.css,base.css,charts.js,scenes/*}` | ≈ 90 KB | 一套能直接读的样式与图表实现 |
| 评测 | `skills/taste-skill/evals/evals.json` | — | 它自己的评分用例 |

## 一、流程（the run，1–5 步决定成败）

1. **读简报 + 读项目**：主体、读者、唯一要促成的事、技术栈、既有品牌、**以及"到底真有什么图"**。
   然后做**主体清点**：8–12 样只属于这家、不属于竞品的东西（名字与含义、地址门牌、材料、光线天气、
   人数/分钟/价格/年份这类数字、它受的限制、仪式与钟点、印刷物）。观点从这里长出来，不从品类套路长。
2. **先写论证**：整页写成"主张 + 证据"，一行一节；没有主张的节删掉。
3. **抽方向**：`draw.mjs --sector … --brief …`，得到一个方向（配色/字体/版式蓝图/动效），不是让它自由发挥。
4. **按蓝图建**：节构图来自方向库，不是卡片网格。
5. **量**：`inspect.mjs` 跑出数字，按家规逐条判；不过就改，不辩解。
6. **图**：真实照片 > 为题材定制的图 > 占位/图标/抽象形状（三者里"没有图"反而更好）。

## 二、家规（House rules，所有建造都成立）

| 规矩 | 替代做法 |
|---|---|
| 标题**最多两行**，任何宽度 | 先删字 → 再放宽 → 最后才缩字号 |
| 首屏有一个清楚的标题，每节都有标题 | 「名字 + 它做什么」「产品 + 给谁用」「活动 + 时间地点」 |
| 左右外边距相等，不许一节挤在一边 | 用图/第二栏/列表/图版把另一侧也占住 |
| 不许有超过半屏的**真空** | 正常节间距；"故意的留白"整页最多一次 |
| 陈述句是段落：≤36px（手机 24px）、约 25 词、三行 | 再大就是标题，两行规就适用 |
| **不许眉标**（标题上方的小标签、pill、New 角标） | 信息进标题或首句，或不要 |
| 非代码处**不许等宽字体** | 正文体；数字对齐用等宽数字 |
| **不许索引编号**（01/02/Step 2） | 用位置/字号/词序表达顺序；真有序用 `<ol>` |
| **不许发丝线**（1px 框、分隔线、网格、裁切标记） | 用留白、底色级差、尺度变化、实心形状 |
| **不许渐变**（背景/按钮/文字） | 纯色或真照片；照片上压中性遮罩是唯一例外 |
| **静止物体不许阴影/发光** | 色调级差；只有真浮起的菜单/弹窗可以 |
| **不许助手配色**（黄奶油＋陶土/铁锈、紫罗兰、靛蓝） | 用抽到的配色 |
| 不许全大写＋大字距小标签 | 句首大写、可读字号 |
| 不许图标顶置功能卡、不许一排一模一样的卡 | 用抽到的节蓝图 |
| **不许玻璃**（毛玻璃、悬浮胶囊导航） | 素导航条：字标 + 几行链接 + 一个动作 |
| 不许 emoji、渐变光斑、装饰形状、假仪表盘灰条 | 真图、真界面片段，或什么都不要 |
| 标题里不许给某个词做样式强调 | 一款字一个色，靠词本身 |
| **字体最多两款**（通常一款） | 抽到的字体系统 |

三处例外（检查器不管）：`<pre>/<code>` 里的真代码（等宽正确）、真表格与表单字段（可以有线）、
根节点带 `data-ui` 的真界面片段。

它自己给的证据（247 站，≥7.5 分 vs <6.5 分）：图标功能卡 1% vs 28%、pill 徽章 14% vs 34%、
渐变 22% vs 52%、阴影 24% vs 48%、大字距小标签 16% vs 57%。

还有一条"反潮流"的自觉：等宽标签、索引号、发丝网格在**获奖站**上其实更常见 ——
正因为生成器都在模仿它们，它们现在读起来是**戏服**。所以在它这里无例外禁掉。

## 三、法条（Laws，数字直接可用）

**字**：可见工作只靠 2–3 个字号（一个极大、一个小、中间留空）；标题/正文比中位 4.3，好的远超；
首屏最大字 8.4vw（弱站 5.0vw）。显示字字距 -0.02~-0.05em、行高 0.85–1.05；
正文 16–20px、行高 1.45–1.6、每行 45–75 字符。一页 ≤5 号字，字体 ≤2 款；左对齐默认，最多一处居中。

**空**：一套栅格、一对紧边距（16–32px）用在全站；大的东西出血到边。全页文案只有 2–3 条左基线。
不对称发生在栅格内部，不在画框上（外两条边距相等，偏一侧的标题由远侧的东西回应）。
节间距 120–240px，必须明显大于节内任何间距（研究里中位约 240）。相邻节构图必须不同，没有一节是卡片网格。

**色**：一底、一墨、一个强调；强调只落在动作上，也许再加一处。正文用满色墨（整页浅灰=没做完）。
面靠色调小级差分离，绝不靠线或阴影。可以让某一节换整块底色；任何东西都不做渐隐。

**图**：一张主导图胜过六张小图；高分站里首屏媒体覆盖半屏以上的占 68%。同裁切、同处理，
除非方向另有指定否则直角（研究里 73% 留直角）。**假图比没图更糟**；为题材画的图 > 占位；
真实世界的照片（找到并署名）更好。找到的图必须下载进项目、在页面上署名、写进报告，不许当成甲方自有。
**任何东西不许压在标题或陈述句上**（检查器直接判失败）。

**组件**：按钮纯色填充，直角或全圆，一次定死（强站 52% 直角 / 23% 全圆；9–16px"软圆角"是弱站默认）；
强首屏多数没有按钮或只有一个。导航=字标 + 3–5 个纯文字链接 + 一个动作，没有导航条装饰。
控件的形、标签、位置本身就说明怎么用；需要额外一句使用说明 ⇒ **重做控件**，别加那句话。
能取消的限制就取消（日期选择器、任意格式解析）；留下的限制（密码规则、文件类型/大小）贴在字段旁，
用 `aria-describedby` 绑住。页脚是设计出的收束，多数强站让名字整幅回归。

## 四、特例（工程侧最常用的三条）

- **既有品牌/设计系统**：`--keep palette,type`，把品牌色与字体映射到角色上，只从抽签里拿构图。
  品牌本身要求被禁的东西（logo 在渐变里、强调色是紫罗兰）⇒ 保留品牌资产，报告里写明，并对那一条 `--allow`。
- **改版/重做既有页面**：① 先录"改前"（`inspect.mjs <url> --out .taste-skill/before`，app 界面加 `--app`）；
  ② 纯评审就停在这（按 `critique.md` 列发现 + 给出最能动结果的三处改动）；
  ③ **保留栈、内容、能用的东西**，不迁移框架/样式方案；改版顺序按影响/风险排：字体 → 颜色 → 框（边距/节律/标题）
  → 状态（hover/focus/loading/empty/error）→ 换掉库存组件；④ 再 `inspect` 到 `after`，逐宽度对比，点通所有链接与表单。
- **没有 Chrome / 没有 Node 22 / 没有网**：降级执行（`lint.mjs` 需 Node 18+；截图用现有浏览器工具；
  `assets.mjs` 取不到图就自己画），并在报告里如实写明哪一步没跑。

## 五、吞噬后我们自己做了什么

1. **L0 内核**（她的 4096 窗口能吃）：`state/taste_kernel.txt` —— 三问 → 结构 → 硬禁 → 数字 → 填空法 → 自检，
   约 1.2k token，足够在手机上直接当系统提示用。
2. **L1 蒸馏**（本文件）：分层索引，带原文路径，供检索与复查。
3. **L2 原库**：`vendor/taste-skill/` 全量保留（含 11 篇深读、2,000+ 实站库、可复用 CSS/图表）。
4. **接线**：页面「🎨 品味」一键把 L0 灌进系统提示；`her.py --taste` 让 Minis 侧读同一份内核。

## 六、我们不完全照抄的地方（诚实边界）

- 它是**编码智能体**用的技能（Node 脚本 + 检查器 + 抽签）。我们的 A19 只有 4096 窗口、跑不动 Node 工具链，
  所以只吞「判决」和「数字」，不吞它的工具流；测量类工作留给框架侧做。
- 它的数据是英文站点的盲测。中文排版的字距/行高经验值要偏保守（中文字距不要再压，行高可到 1.6–1.8）。
- 它自己也承认部分禁令是**业主口味**而非研究结论（等宽标签、索引号、发丝网格在获奖站更常见）。
  我们沿用它的禁法（因为我们同样在被生成器包围），但在报告里标明"这是口味，不是测量"。

## 七、留痕（框架原生吞噬记录）

```
get_devourer().devour_github_repo('https://github.com/Leonxlnx/taste-skill', cap_name='taste_skill')
→ ok:true · cap=taste_skill · stars=102435 · language=JavaScript
   knowledge_chars=6525 · readme_chars=15083
   absorbed_knowledge: gbt_allinone/store/devoured/taste_skill/absorbed_knowledge.md
```

框架只啃 metadata + README（6.5 KB 知识）。**它啃不到 2 MB 的 references/library** ——
那部分是我这轮手啃的：`vendor/taste-skill/` 全量落盘 + 本文件 L1 蒸馏 + `state/taste_kernel.txt` L0 内核。
两层的分工要记住：**框架留痕，我留肉**。

## 八、第一次行刑：拿她自己的页面当被试（2026-10-26）

`tools/taste_lint.py` —— 原版检查器是 Node+Puppeteer/CDP，iSH 没有 Chrome、A19 更跑不动。
改法：**用现有 WebView 量，用 Python 判**。

```
tools/taste_collect.js    在真页面里取读数（只读）
tools/taste_lint.py       按家规逐条判红，每条带原文规则出处
```

被试：`holo_pet_w3/model-chat`（她自己的对话面，390×844，26 个可见元素）

| 规则 | 结果 | 读数 |
|---|---|---|
| heading-lines | OK | 1 个标题都在两行内 |
| first-title | OK | h1「🧠 模型对话」 |
| eyebrow / index-numbering / mono / gradient / shadow-rest / upper-tracked / glass | OK | 全 0 |
| **emoji** | **FAIL** | 7 个 |
| **hairline** | **FAIL** | 16 处 1px 边框 |
| soft-radius | WARN | 14 处 9–16px「软圆角」 |
| typefaces / type-sizes / accent | OK | 1 款字 · 4 个字号 · 1 种动作色 |
| section-gap | N/A | app 界面不按落地页节律判 |

结论：**「删掉装饰」这条它做得不错（渐变/阴影/玻璃/眉标/索引号全 0），
栽在「装饰换了皮」上 —— emoji 当图标、1px 边框当分隔、软圆角当现代感。**
这正是原文那句的核心：删掉装饰不等于好看，也别用另一种装饰去填。

## 九、行刑后：按家规把她改了（2026-10-26）

| 项 | 改前 | 改后 | 怎么改的 |
|---|---|---|---|
| emoji | 7 个 | **0** | `🧠 模型对话`→`模型对话`、`🔥 预热`→`预热`、`🎨 品味`、`👁 看屏幕`、`🗣 说一句`、`✅/⚠️/⛔` 全换纯文字 |
| 发丝线 | 16 处 | **0** | 顶栏/底栏的 border 换成色阶 `#0c121a`；卡片与按钮改色块；表单字段保留（家规豁免） |
| 9–16px 软圆角 | 14 处 | **0** | 圆角一次定死：**面板直角（0）· 动作全圆（999px）** |
| 强调色 | 2 种 | **1 种** | 次级按钮去掉填充，只剩主动作那一个绿 |

判据复核：`FAIL 0 · WARN 0 · 通过 15`（改前 `FAIL 2 · WARN 1 · 通过 12`）。

踩到的两个 CSS 坑（都会静默失效）：

1. **`border:1px solid transparent` 仍然是 1px 边框** —— 检查器看 `border-width`，不看颜色。
2. **特异性**：`button.ghost{border:1px …}` 压过后写的 `.ghost{border:0}`；同理 `.badge` 的透明边框。
   ⇒ 覆盖必须写成 `button.ghost`、`.badge,.badge.ok,.badge.bad`。

顺带修：恢复上次对话时把账本里的 `sensor` 行当聊天渲了出来（`{"event":"container_down"}` 出现在对话区）。
现在按 `role` 过滤，只渲 `user/assistant`。

## 十、全站闸：`taste_lint --scan`（2026-10-26）

```
python3 tools/taste_lint.py --scan holo_pet_w3 --limit 8
扫了 8 页 · 有红 7 页 · 用时 17.7s（每页 ≈ 2.2s）
```

前 8 页读数（相对路径）：

```
activity/index.html            FAIL 6  WARN 2  first-title,emoji,mono,hairline
ai-board/index.html            FAIL 4  WARN 0  first-title,index-numbering,emoji,hairline
blueprint/index.html           FAIL 8  WARN 0  first-title,eyebrow,index-numbering,emoji
body/index.html                FAIL 0  WARN 1   ← 唯一干净样本
brain/caps/a1art_skill.html    FAIL 4  WARN 2  broken-css,emoji,hairline,typefaces
```

### 根因（这轮最有价值的发现）

三件套 `emoji / hairline / typefaces` **每一页都各错一遍**，不是巧合 —— 因为**站点没有共享样式层**：

```
全站 html 377 页 · 引用了不存在文件的 358 页（95%）
   ../../deck3d.css                349 页
   ../../skin-mission-control.css  349 页
   ../../window.css                349 页
   ../cap.css                      349 页
```

四个壳层样式表**在仓库里根本不存在**（全盘 find 无果）。所以每页只能各自 inline 写一套 ——
同一个 slop 决策被抄了 349 遍。`window.css` 的引用甚至写着"必须在 window.css 之后"的专业皮肤层注释，
说明它曾经存在过，后来丢了。

新增判据 `broken-css`（静态检查 `<link>/<script>` 指向的本地文件是否存在，不需要浏览器），
把这件事变成能扫出来、能拦住的规则。

## 十一、壳层重建：349 页从"裸 HTML"变回有壳（2026-10-26）

**做法（不靠猜，靠反推）**：把 358 个引用 `window.css` 的页面里出现过的 class 全数统计，
取频次前 24 个，按家规重新实现：

```
cap-sec 2437 · n 2437 · mc-tile 2088 · mc-tile-label / mc-tile-value 2088
mc-badge 1393 · kv / k / v 698 · nav-grid 698 · foot 353 · spacer 350
cap-page / cap-top / crumb / here / cap-hero / cap-id / cap-desc / cap-body / cap-tags 349
tiles / cols2 / hintline 348
```

`window.css` 现在是 **213→216 行**：token（面/墨/强调/圆角/字号/间距/字体）+ 元素默认 + 上面这些布局类。
另建三个**刻意最小**的兼容基座（`deck3d.css` / `skin-mission-control.css` / `brain/cap.css`），
只保证不 404 并暴露 token 别名 —— 不覆盖各页既有 inline 设计。

**效果**

```
引用了不存在文件的页面：358 页 → 5 页（剩下的是几个缺失 js 与 eye.css，与本次无关）
a1art_skill.html：FAIL 4 → FAIL 3（broken-css 消掉；余 emoji/hairline/typefaces 是它自己的 inline 债）
页面横向溢出：scrollWidth 497 → 390（= 视口，修好 overflow-wrap + 卡片字号）
```

**踩到的坑（这次是真坑）**：WebView **按 URL 缓存 CSS**。改完 `window.css` 再 navigate 同一个页面，
读到的仍是旧样式表（实测 `cssRules` 停在 27 条，而磁盘上已 50+ 条；`.cap-page` 计算值 padding=0）。
必须**关掉标签、新开一个**才拿到新版本 —— 这解释了「我明明改了却看不到效果」。
需要频繁改样式的页面，最好给 `<link>` 加版本号（`window.css?v=20261026`）。

## 十二、缓存版本化 + `.n` 定死语义（2026-10-26）

**① 样式版本化**：WebView 按 URL 缓存 CSS，改完看不到效果（见第十一节）。
给 356 页的 `<link href="…window.css">` 统一加 `?v=20261026`（幂等：已有版本号就跳过）。

```
改动 356 页 · 已是新版跳过 2 页 · 仍无版本号的引用 0
清单：state/css_version_manifest.json（356 条，可逐条回滚）
实测：href=…window.css?v=20261026 · cssRules=63 · scrollWidth=390（无横向溢出）
```

**② `.n` 定死为「计数/单位」**：2437 个页面在用它，不定义就会被拿去当 01/02 索引号（家规第 8 条）。
现在明确：跟在本体后面、等宽数字对齐、无徽章外形、无前导零、`text-transform:none`、字体继承。
真要表达顺序用真 `<ol>`；另给一个 `.ordinal` 排版壳，只给样式、不制造编号。

**每页的 inline 债仍在**：抽样 6 页里 5 页还有红，全是各页自己写死的 emoji / 1px 边框 / 三款字体。
壳是分母（改一次全站受益），inline 是分子（得一页一页还）—— 这条判断没变。

## 十三、缓存才是真凶：一处改，687 页（2026-10-26）

### 现象

清完 7 页正文 emoji 后复扫 30 页，emoji **只从 29 掉到 27** —— 像是"改了没用"。

### 追下去

1. 页面里的 emoji 不在 HTML，也不在 `<script>` 内联里 —— 在**共享脚本** `holo_pet_w3/brain/cap.js:142`：
   ```js
   var head = el("div", null, "⛓ 调用能力位 ");
   ```
   这一行被 **687 页**共用。
2. 改掉它之后复扫，emoji **还是 27 页** —— 因为 WebView 按 URL 缓存 **JS**，页面读的还是旧 cap.js。
3. 给 369 页的 `<script src="*.js">` 统一加 `?v=20261026`（771 处），复扫：

```
扫 30 页 · 全绿 1 页  →  全绿 24 页
emoji 27 页 → 2 页
```

### 结论（比修 bug 更重要）

**缓存会让"已经修好"看起来像"根本没修"。** 任何评估前必须先确认读到的是新版资源：
CSS 与 JS 都要版本化（本轮：css 356 页 + js 369 页/771 处）。
否则所有测量都是对着旧代码做的，越认真越错。

### 剩余债务（30 页抽样）

```
index-numbering 4 · first-title 3 · hairline 3 · emoji 2 · mono 2 · glass 1 · typefaces 1 · gradient 1
```
这些是**各页自己的** inline 债，没有共享来源可一处修 —— 得一页一页还。

清单（可回滚）：
`state/css_version_manifest.json` · `state/emoji_clean_manifest.json` · `brain/cap.js` 备份在 `/tmp/cap.js.bak`
