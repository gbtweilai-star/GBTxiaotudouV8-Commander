# gbt-showreel · showreel.design 动效参考库操作

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 成熟度：已实测可用 · 最后更新 2026-10-13 · 版本 1.0.0

## 这是什么

把 [showreel.design](https://showreel.design)（策展全球工作室 motion reel 的站）变成一条能复跑的取参考命令：
按风格 / 行业 / 声音 / 年份 / 关键词，从 **248 条 showreel · 21 条品牌上市片 · 139 条 logo 演绎** 里捞出
对口的那几条，拿到缩略预览、静帧、成片线索与**工作室官网**，把这些结论喂给设计任务定方向。

不用它也行 —— 你会得到的是：每次现写一遍爬虫、每次重新发现"成片 URL 推不出来"、
以及最糟的那种结果：**把几秒循环的预览当成成片下下来**。

## 什么时候用

- "帮我找几条 cinematic 的 studio reel 看看" / "找个 3D CGI 风格的参考"
- 给某个行业的项目定动效方向（`--industry tech-saas` 之类）
- 需要 logo 演绎 / 品牌上市片的参考
- 想知道某个工作室的作品和官网（`resolve`）

## 什么时候别用

- **要"拿走"素材进交付物** —— 站上每条片子都是第三方工作室的作品，只作参考，不许进我们的成品、不许二次分发。
  要能发出去的东西，用我们自己的资产或授权素材（见 `gbt-fal` / `gbt-venice` / 出图能力位）。
- **要审美裁决**（这套参考好不好看、走哪一档）—— 那是 `gbt-aesthetic` 的活，本条不做审美判断。
- **要抓别的站** —— 走 `gbt-automation` 的 browser 能力位或 `gbt-web` 技能簇。
- **只想"生成"而不是"找参考"** —— 本条只负责看别人怎么做，不产出新素材。
- **要做机器可读的大批量镜像 / 长期归档** —— 这是外部策展站，别把它当数据源来囤。

## 反模式（出现这些词就是错了）

- **假绿**：`HEAD 200` 就当"能下载"。本站海报全量 248 条里 HEAD 245 通、GET 只 242 通，
  且失败的 6 条是**按对象确定性**的（3 条 HEAD 都 404，3 条 HEAD 200 而 GET 404）——
  脚本对海报是 best-effort，失败会**回退**取预览并在输出里说明，不会静默给你一个空文件。
- **说反**：把列表页 `data-video-url` 或 API 的 `thumbnailUrl` 读成"成片"。它们都是**几秒循环预览**。
- **过期**：站点结构改了还硬用旧口径。任何报错先跑 `verify`，🔴 就**先改文档再改脚本**。
- **跳过**出处：参考件落地不带 `author` / 官网 / 页面 URL。出处随件走，不做事后补。
- **误报**：拿 `tags` 当主筛选维度做统计 —— 它 248 条里只有 24 条非空，得出的分布是错的。

## 怎么跑

```powershell
python skills/gbt-showreel/scripts/showreel.py catalog --refresh          # 拉目录（一次就够）
python skills/gbt-showreel/scripts/showreel.py taxonomy                   # 有哪些可筛的值
python skills/gbt-showreel/scripts/showreel.py query --style minimal-clean --limit 8
python skills/gbt-showreel/scripts/showreel.py resolve frog-showreel-2026 # 成片 + 官网
python skills/gbt-showreel/scripts/showreel.py get <slug> --kind poster --out ./refs
python skills/gbt-showreel/scripts/showreel.py logo <品牌> --out ./refs    # logo 演绎
python skills/gbt-showreel/scripts/showreel.py verify                     # 契约自检（--posters-all 扫全量）
```

细节、字段全表、11 个风格值、以及 6 条踩坑记录见 [SKILL.md](SKILL.md) 与
[references/site-contract.md](references/site-contract.md)。

## 相关技能

- `gbt-aesthetic` —— 拿到参考之后的**审美裁决**（本条只取材，不裁决）
- `gbt-provenance-discipline` —— 出处与反编造纪律（参考件进 brief 时照它写）
- `gbt-fal` / `gbt-venice` —— 要**生成**新素材时走这两条
- `gbt-automation` / `gbt-web` —— 要抓**别的**站时走这两条
- 边界：本条只发 HTTP GET，不进能力位注册表，不需要任何授权作用域
