# showreel.design 站点契约（2026-10-13 实探）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这份是**维护件**：写清"这个站到底给了什么口子、每个口子的字段、哪些坑踩过"。
> 站点一改，`scripts/showreel.py verify` 会当场响；改完口径**先把这份改对**，再动用例。
>
> 本文所有数字都是 2026-10-13 当次真跑出来的读数；没跑过的会明确写「未验」。

---

## 1. 站点是什么

| 项 | 实测值 |
|---|---|
| 形态 | 静态站，`<meta name="generator" content="Astro v6.1.9">`，SSG 出 HTML |
| 鉴权 | **无**。没有 key、没有登录、没有 cookie 依赖 |
| `robots.txt` | `User-agent: * / Allow: /` + `Sitemap: /sitemap-index.xml` |
| sitemap | `sitemap-index.xml` → `sitemap-0.xml`，**443 条 URL** |
| 资源 CDN | `https://video.showreel.design`（视频/缩略/海报/OG 图都在这里） |
| 内容性质 | **第三方工作室作品的策展站** —— 不是它自己的作品（⇒ 见 §6 用法边界） |

sitemap 443 条按首段分布：`videos 248` · `tag 65` · `launch 22` · `style 22` ·
`industry 20` · `category 17` · `year 16` · `sound 15` · 其余为单页（`about` / `resources` /
`logo-animation` / `search` / `shorts` / `privacy` / 首页）。

## 2. 四个目录 API（**首选入口**）

| 端点 | 条数 | 一句话 |
|---|---|---|
| `GET /api/videos.json` | **248** | 全部 showreel 条目（主目录） |
| `GET /api/launch.json` | **21** | 品牌上市片 / 改版片 |
| `GET /api/logo-animations.json` | **139** | 品牌 logo 演绎 |
| `GET /api/resources.json` | **13** | 外部课程 / 工具（导流出站） |

四个都返回**顶层数组**，`200`，无需任何请求头技巧（普通 UA 即可）。

### 2.1 `/api/videos.json` 条目字段（11 个，实读全量键集合）

| 字段 | 例 | 备注 |
|---|---|---|
| `slug` | `frog-showreel-2026` | 详情页 `/videos/<slug>` |
| `title` | `Frog showreel 2026` | |
| `author` | `Frog` | 工作室 / 作者名 |
| `authorAvatar` | `null` | 248 条里非空 **165** 条 |
| `category` | `Studio / Agency` | **显示名**，5 种，见 §3.1 |
| `description` | 长文 | 就是详情页 JSON-LD 的 `description` |
| `tags` | `["motion design","3d"]` | **248 条里只有 24 条非空** ⇒ 别拿它当主筛选维度 |
| `year` | `2026` | 2019–2026 |
| `industries` | `["advertising-commercial"]` | 规范 slug，见 §3.3 |
| `styles` | `["bold-vibrant","hand-drawn"]` | 规范 slug，见 §3.2 |
| `soundMusic` | `["rock-energetic"]` | 规范 slug，见 §3.4 |
| `thumbnailUrl` | `…/Thumbnails/thumbnail_videos_<tail>.mp4` | **几秒循环预览**，不是成片 |
| `publishDate` | `2026-10-08T00:00:00.000Z` | 排序用 |

> ⚠️ **API 里没有成片 URL，也没有工作室官网 URL。** 这两个只在详情页（§4）。

### 2.2 另三个 feed

- `launch`：`slug` `title` `brand` `studio` `description` `tags` `thumbnailUrl` —— 详情页 `/launch/<slug>`。
- `logos`：`file` `brand` `agency`（**没有 slug**）—— 资源直链见 §5.3。
- `resources`：`name` `type` `description` `href`（出站 URL）`logo` `tags`。

## 3. 分类与可筛选值（全量现算）

### 3.1 `category`（5 种，**显示名**；URL slug = 小写化、空格换 `-`、斜杠吃掉）

| 显示名 | 条数 | URL |
|---|---|---|
| Motion Graphics | 95 | `/category/motion-graphics` |
| Studio / Agency | 67 | `/category/studio-agency` |
| 3D / CGI | 41 | `/category/3d-cgi` |
| UI/UX Motion | 30 | `/category/uiux-motion` |
| Branding & Identity | 15 | `/category/branding-identity` |

### 3.2 `styles`（11）

`bold-vibrant 104` · `3d-cgi 59` · `minimal-clean 53` · `futuristic-tech 37` ·
`retro-vintage 29` · `hand-drawn 26` · `geometric-abstract 21` · `cinematic-dramatic 19` ·
`organic-natural 8` · `playful-quirky 6` · `dark-moody 1`

### 3.3 `industries`（11）

`advertising-commercial 134` · `tech-saas 93` · `entertainment-media 25` · `fashion-luxury 8` ·
`food-beverage 7` · `sports-fitness 7` · `automotive 4` · `education 1` ·
`finance-banking 1` · `healthcare 1` · `other 1`

### 3.4 `soundMusic`（10）

`electronic-synth 79` · `hip-hop-urban 54` · `rock-energetic 38` · `epic-cinematic 16` ·
`no-sound 14` · `chill-ambient 8` · `voiceover-heavy 7` · `orchestral-classical 5` ·
`jazz-acoustic 3` · `sound-design-focused 2`

### 3.5 `year`

`2026 121` · `2025 79` · `2024 12` · `2023 11` · `2022 6` · `2021 2` · `2020 1` · `2019 1`

### 3.6 `tags`（64 个，**自由文本**）

大小写混着来是常态：`2D`(1) / `2d`(5)、`3D`(2) / `3d`(4)、`Showreel`(1) / `showreel`(4)。
⇒ **比对必须忽略大小写**（脚本已按此实现）。还有 `melbourne.` 这种脏值。

### 3.7 人肉浏览页

`/category|/style|/industry|/sound|/tag|/year/<slug>`（列表页带分页 `/<n>`）、
`/search?q=`（**前端**过滤，数据源就是 `/api/videos.json`）、`/launch/<slug>`、
`/videos/<slug>`、`/logo-animation`、`/resources`。

> 有 API 就别爬列表页：列表页一页 24 条、要翻页、还得解 HTML，API 一次给全。

## 4. 详情页：成片与官网的**唯一**来源

`GET /videos/<slug>`（或 `/launch/<slug>`）的 HTML 里有一块 JSON-LD：

```html
<script type="application/ld+json">
{"@type":"VideoObject","name":"Frog showreel 2026","description":"…",
 "thumbnailUrl":"https://video.showreel.design/og/og-home.jpg",
 "uploadDate":"2026-07-12T00:00:00.000Z",
 "author":{"@type":"Person","name":"Frog","url":"https://www.frog.co/"},
 "url":"https://showreel.design/videos/frog-showreel-2026",
 "contentUrl":"https://video.showreel.design/videos/Frog showreel 2026.mp4"}
</script>
```

| 要什么 | 取哪 |
|---|---|
| 成片 mp4 | `contentUrl` |
| 工作室官网 | `author.url`（**站点 HTML 里的 a[href] 抓不到**，实测出站链接为空） |
| 作者名 | `author.name` |
| 发布日期 | `uploadDate` |
| 内容简介 | `description`（与 API 同源） |

⚠️ 三个坑：

1. **`contentUrl` 的命名不统一** —— 两种都有：按 slug（`…/videos/elizabeth-laferriere-showreel.mp4`）
   与按标题带空格（`…/videos/Frog showreel 2026.mp4`）。**不可推导，必须读页**。
2. 详情页 JSON-LD 的 `thumbnailUrl` 是**通用 og 图**（`/og/og-home.jpg`，每页都一样），
   没有信息量；要缩略图回 API 的 `thumbnailUrl`。
3. `contentUrl` 里是**裸空格**，请求前要 percent-encode，否则 HEAD 拿不到 `Content-Length`。

## 5. CDN 资源与实测行为

### 5.1 成片 mp4 ✅

`HEAD` 200 + `Content-Length`；`GET` 200；`Accept-Ranges: bytes`（带 `Range` 头回 **206**）。
实测两条：`Frog showreel 2026.mp4` **68.5 MB** · `elizabeth-laferriere-showreel.mp4` **52.0 MB**。
⇒ 大文件，**先 HEAD 看大小**，支持只取前段做判断。

### 5.2 缩略预览 mp4 ✅

API 的 `thumbnailUrl` 就是它，`…/Thumbnails/thumbnail_<group>_<tail>.mp4`，
实测 **795 KB / 814 KB** 量级 —— 几秒循环，适合快速过片，**不是成片**。

列表页 HTML 上的 `data-video-url` 属性**也是这个预览**，别当成成片下载（实测 24/24 全是 Thumbnails）。

### 5.3 静帧海报（248 条**逐条**实测过）

规则（可推）：`thumbnailUrl` 尾巴 `thumbnail_videos_<tail>.mp4`
⇒ `https://video.showreel.design/Posters/poster_videos_<tail>.jpg`
（大小 11–35 KB，正适合做参考板。**注意尾巴不是 slug** —— 是缩略图文件名里的那段，
如 `scene-showreel-2026` 的尾巴是 `scene Showreel 2026`，拿 slug 去拼必 404。）

2026-10-13 全量 248 条逐条 HEAD + GET 的读数：

| 项 | 读数 |
|---|---|
| 规则适用 | **248 / 248**（没有一条推不出 URL） |
| `HEAD` 200 | **245 / 248** |
| `GET` 200 | **242 / 248** |

6 条例外分**两类**（都是**按对象确定性**的 —— 同一对象连测 3 次结果完全一致）：

- **HEAD 就 404（对象不存在）3 条**：`motionflash-back-2025-cheng-ping-li` ·
  `studiocontrecourant-showreel-graphic-design` · `what-reel-2025`
- **HEAD 200 但 GET 404（元数据在、对象取不到）3 条**：`elizabeth-laferriere-showreel` ·
  `mikey-dowdle-mikey-dowdle-showreel-vol-1` · `oliver-sin-oliver-sin-good-sin-reel-2023`

⇒ 两条口径**写死**：

1. **`HEAD 200` ≠ 能取到** —— 这是本站最容易骗人的一处，拿 HEAD 当"能下"就是假绿。
2. **它不"抖"** —— 别用抽样命中率去预测某一条（我第一次抽 5 条得 2/5、抽 60 条得 59/60，
   差别全在抽到了哪一条）。**要么按上面的名单绕开，要么取的时候试、失败回退**。

脚本因此把海报当 best-effort：GET 回 404 就自动回退取预览 mp4，并在输出里说明。
复测：`showreel.py verify --posters-all`（约 3 分钟）。

### 5.4 logo 演绎 mp4 ✅

`https://video.showreel.design/Logo Animation/<Brand>--<Agency>.mp4`（整个路径要 percent-encode）。
实测 `Benifex--For Different.mp4` → `HEAD 200` = **9,020,944 B**，落盘后**逐字节一致**。
文件名规则 = `<brand>--<agency>`。脚本：`showreel.py logo <品牌>`（按品牌/机构/文件名片段匹配）。

### 5.5 上市片 mp4 ✅

`/launch/<slug>` 的 JSON-LD `contentUrl` ⇒ `https://video.showreel.design/launch/<Title>.mp4`
（实测 `/launch/instagram` → `…/launch/Instagram.mp4`，**5,265,192 B**，落盘 `ftypisom`）。

⚠️ 两处与 videos 链**不一样**的地方（都踩过）：

1. **launch 的 JSON-LD 没有 `author`**（只有 `publisher=Showreel.design` 自己）——
   真实作者在 API 条目的 `brand` / `studio` 里，所以**没有官网字段**可选。脚本会回退到
   `brand`/`studio`，并如实写「（本条 JSON-LD 没有官网字段）」，不打印 `None`。
2. launch 的 `thumbnailUrl` 尾巴是 `launch_<Title>`，所以静帧规则变成
   `Posters/poster_launch_<Title>.jpg` —— 脚本按尾巴拼，不写死 `videos`。

## 6. 用法边界（不是技术限制，是规矩）

- 站上**每一条成片都是别人的作品**（工作室 / 自由作者），showreel.design 只是策展。
- ⇒ 取下来的东西**只能当参考**：定方向、比风格、做参考板、写 brief。
  **不许原样进我们的交付物**，不许二次分发，不许当作我方作品呈现。
- 记录出处是默认动作：`author` + `author.url` + 页面 URL 一起带走（`resolve` 已给全）。
- 站方 `robots.txt` 全放行，但不等于"可以轰"：脚本默认请求间隔 0.2 s，别并发打。

## 7. 契约怎么复验

```powershell
python skills/gbt-showreel/scripts/showreel.py verify
```

8 条断言（4 个 API 可达且是数组 · 条目字段齐全 · 详情页有 `contentUrl` · 有 `author.url` ·
成片支持 Range），外加 1 条**只报不判**的海报真 GET（默认抽 8 条，`--posters-all` 扫全量）。
任何一条 🔴 ⇒ 先改这份文档，再改脚本，别硬用旧口径。
