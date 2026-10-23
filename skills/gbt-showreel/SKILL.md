---
name: gbt-showreel
displayName: GBT · showreel.design 动效参考库操作
version: 1.0.0
description: 用 showreel.design（策展全球工作室 motion reel 的站）当动效参考库：按风格/行业/声音/年份/关键词检索 248 条 showreel、21 条品牌上市片、139 条 logo 演绎，取缩略预览与静帧做参考板，抓到成片线索与工作室官网。站点结构（4 个公开 API + 详情页 JSON-LD）与 9 条契约断言都固化成可复跑脚本，站一改就当场响。当用户要"找动效参考 / 找 motion 参考 / 看某风格的 studio reel / 找 logo 演绎参考 / 品牌片参考 / showreel 灵感"时使用。**只管找参考与拿线索，不做素材搬运** —— 站上成片是第三方作品，用法见正文边界。
triggers:
  - "showreel"
  - "showreel.design"
  - "动效参考"
  - "motion 参考"
  - "参考片"
  - "studio reel"
  - "agency reel"
  - "工作室 showreel"
  - "logo 演绎"
  - "logo animation"
  - "品牌上市片"
  - "brand launch film"
  - "动效灵感"
  - "motion inspiration"
  - "参考板"
---

# GBT · showreel.design 动效参考库操作

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 成熟度：**已实测可用** · 最后更新 2026-10-13 · 版本 1.0.0
> （当次真跑：9/9 契约断言通过、目录 248+21+139+13 条拉到、成片/预览/海报三条下载路径各自验过。）
> 站点是外部资源，随时可能变 —— 用前或报错时跑一次 `verify`。

---

## 0. 一条边界（先划清）

这个站是**策展站**：上面每一条片子都是**别家工作室 / 作者的作品**，它只是收录。

所以这条技能的正事是**找参考、拿线索**：

- ✅ 定方向：某风格 / 某行业现在流行什么样的片；
- ✅ 做参考板：缩略预览与静帧拼给用户看"我们要往这个方向走"；
- ✅ 追源头：拿到工作室名与官网，去看原创方的一手资料；
- ✅ 写进 brief / 分镜：把"参考：<工作室> · <片名> · <URL>"记下来。

不归它管的事：

- ❌ **把成片搬进我们的交付物**（片段、静帧、配乐都不行）—— 那是别人的作品；
- ❌ 二次分发 / 打包转卖 / 不留出处地复用；
- ❌ 把站上的片子当成"我方案例"呈现。

> 判定很简单：**产出的东西是"给我们自己看的"还是"要发出去的"**。前者随便用，后者只能用它的**结论**（风格词、结构、节奏），不能用它的**素材**。

## 1. 它到底给什么（一句话版）

| 想要 | 从哪拿 | 量 |
|---|---|---|
| 全部 showreel 目录 | `GET /api/videos.json` | 248 |
| 品牌上市 / 改版片 | `GET /api/launch.json` | 21 |
| logo 演绎 | `GET /api/logo-animations.json` | 139 |
| 外部课程 / 工具 | `GET /api/resources.json` | 13 |
| **成片 mp4 + 工作室官网** | `GET /videos/<slug>` 页里的 **JSON-LD** | 逐条 |
| 缩略预览（几秒循环） | API 的 `thumbnailUrl` | 逐条 |

> ⚠️ 成片 URL **推不出来**（站上两种命名混用），必须读详情页 —— 这是这条技能存在的头号理由。
> 字段全表、11 个分类值、以及踩过的坑都在 [references/site-contract.md](references/site-contract.md)。

## 2. 怎么用（脚本，别现写爬虫）

脚本：`scripts/showreel.py`（纯标准库，`python` 或 `py -3.14` 都能跑）。

```powershell
# ① 拉目录到本地缓存（默认 ~/.cache/showreel；只在必要时刷新）
python skills/gbt-showreel/scripts/showreel.py catalog --refresh

# ② 看清有哪些可筛的值（现算，不手抄）
python skills/gbt-showreel/scripts/showreel.py taxonomy

# ③ 检索（纯本地过滤，不进网）—— 给设计任务定方向就靠这条
python skills/gbt-showreel/scripts/showreel.py query --style cinematic-dramatic --industry tech-saas --limit 8
python skills/gbt-showreel/scripts/showreel.py query --q "logo" --year 2026 --sort date
python skills/gbt-showreel/scripts/showreel.py query --category "Studio / Agency" --sound no-sound --json

# ④ 单条 → 成片 URL + 工作室官网 + 简介（读详情页 JSON-LD）
python skills/gbt-showreel/scripts/showreel.py resolve frog-showreel-2026
python skills/gbt-showreel/scripts/showreel.py resolve instagram --feed launch   # 品牌上市片

# ⑤ 落盘做参考板：静帧（默认）／预览／成片
python skills/gbt-showreel/scripts/showreel.py get frog-showreel-2026 --kind poster --out ./refs
python skills/gbt-showreel/scripts/showreel.py get frog-showreel-2026 --kind reel --dry-run   # 先看多大
python skills/gbt-showreel/scripts/showreel.py get instagram --feed launch --kind reel --yes --out ./refs
python skills/gbt-showreel/scripts/showreel.py logo Benifex --out ./refs          # logo 演绎（按品牌匹配）

# ⑥ 站一改就当场响
python skills/gbt-showreel/scripts/showreel.py verify                 # 8 条断言（海报那条只抽 8）
python skills/gbt-showreel/scripts/showreel.py verify --posters-all   # 海报扫全量（约 3 分钟）
```

四条 feed **都闭环**：`query` 四条都能筛（`--feed videos|launch|logos|resources`），
`resolve` 支持 videos 与 launch，落盘走 `get`（videos / launch）与 `logo`（logos）。

要点：

- `catalog` 拉一次就够，之后 `query` 全是**离线**的 —— 别为了筛选反复打站。
- 成片是大文件（实测 52–68 MB）：**默认拦在 5 MB**，要下得显式 `--yes`，并且先 `--dry-run` 看大小。
- 把参考件落到任务自己的目录里（`./refs` 之类），**别堆进仓根**。
- 每条参考落地时带上 `author` / `author.url` / 页面 URL —— 出处是随件走的，不是事后补的。

## 3. 实测踩过的坑（省得再踩）

1. **`HEAD 200` ≠ 能取到**。海报 `Posters/*.jpg` 全量 248 条逐条测过：规则 248/248 适用、
   HEAD 200 = **245**、GET 200 = **242**。6 条例外是**按对象确定性**坏的（不是抖动）；
   其中最阴的是 3 条"HEAD 200 但 GET 404"。脚本对海报是 best-effort，失败了自动回退取预览
   并在输出里说明；要绕开就照 [site-contract](references/site-contract.md) §5.3 的名单。
2. **列表页的 `data-video-url` 是预览，不是成片**（实测 24/24 全指向 `Thumbnails/*.mp4` 几秒循环）。
3. **详情页 JSON-LD 的 `thumbnailUrl` 是通用 OG 图**（每页都是 `/og/og-home.jpg`），别拿它当缩略图。
4. **`contentUrl` 里是裸空格**，请求前必须 percent-encode，否则 HEAD 拿不到 `Content-Length`，
   看起来像"站点没给大小"。
5. **`tags` 只有 24/248 条非空，且大小写混用**（`2D`/`2d`、`3D`/`3d`）⇒ 主筛选维度用
   `styles` / `industries` / `soundMusic` / `year`，tags 只当补充，且比对忽略大小写。
6. **`category` 是显示名、URL 是 slug**（`Studio / Agency` ↔ `studio-agency`）—— 脚本两种写法都收。

## 4. 接到设计流程上

这条技能是**上游取材**，不是终稿工具。典型接法：

```
设计任务 → gbt-showreel 检索（定方向 / 出参考板）
          → 参考件的结论进 brief 与分镜（风格词、结构、节奏、音乐气质）
          → 真正落地用我们自己的资产或授权素材
```

和邻件的关系：

- 要**审美裁决**（这套参考好不好看、往哪一档走）→ `gbt-aesthetic`，本条不做审美判断；
- 要**生成新素材** → `gbt-fal` / `gbt-venice` / 出图能力位，本条只负责"看别人怎么做"；
- 要**出处纪律**（怎么写引用、怎么反编造）→ `gbt-provenance-discipline`；
- 要**抓别的站** → `gbt-automation`（browser 能力位）· `gbt-web`（web-* 技能簇）。

> 本条的落点是**外部策展站**，所以它既不进能力位注册表（不是我们自己的执行体），
> 也不需要任何授权作用域 —— 它只发 HTTP GET。

## 5. 维护

- 站点结构变了 → `verify` 会 🔴。**先改 `references/site-contract.md`，再改脚本**，别硬用旧口径。
- 改了这条技能 → 工作区源稿 `skills/gbt-showreel/` 是唯一真身，装到
  `~/.openclaw-autoclaw/skills/` 与 `~/.agents/skills/`，然后
  `py -3.14 tools/codex-scripts/audit-skill-roots.py` 确认三处同哈希。
