# taste_guard 修复记录：把上帝视角首页的 10 条 FAIL 修到 0

> 2026-11-01 · 目标 `holo_pet_w3/index.html` · 工具 `taste_guard deep_audit`（上游 inspect.mjs + Node v26 + Edge）
> 判据只认真浏览器：1440/768/390 三宽度、FAIL=0 才算过。

## 一、修前 / 修后

| 项 | 修前 | 修后 |
|---|---|---|
| verdict | **FAIL** | **PASS** |
| FAIL / WARN | **10 / 9** | **0 / 2** |
| 分数 | 0 | **94** |
| 标题 | 无 h1 | 「短剧，自己拍完。」（1–2 行） |
| 真实图片 | 0 张 | 4 张成片帧 + 视频 1 条（`realPictures=5`） |
| 首屏空洞 | 2/2 屏几乎空 | 填充 0.35 / 0.73 / 0.73 |
| 边距 | 左 1 / 右 53 | 左 25 / 右 25 |
| 贴边文字 | 5 处 | 0 |
| 等宽/阴影/发丝线 | 各 1/1/4 | 0 / 0 / 0 |
| 动效元素 | 1 | **17** |
| 视图覆盖 | `.gbt-view` 绝对定位盖住首屏 | 改为文档流，不再覆盖 |

剩余 2 条 WARN（非 FAIL）：`size-count`（字号 10 档，建议约 5 档）、`name-only-title`（h1 是名字式短句）。

## 二、改了什么（都在 `holo_pet_w3/`）

| 文件 | 改动 |
|---|---|
| `index.html` | 首屏 hero（h1/说明/按钮/视频）、4 张成片帧、三条成片说明；CSP 加 `media-src 'self'`；外链 `taste-fix.css/js` |
| `taste-fix.css` | 版式/字体/去影/去线/等边距/按钮/动效/reduced-motion；`.gbt-view` 从 absolute 改 static，修“首屏被工作台盖住” |
| `taste-fix.js` | 关闭重复注入导航（`GBT_NAV_DISABLE`）；hero 按钮滚动到工作台 |
| `assets/taste/still-01..04.jpg` | 从《顶替新娘》三集成片抽的真实帧（本地，非云） |

## 三、复跑命令

```powershell
run_task("taste_guard", {"op":"deep_audit","path":"holo_pet_w3/index.html"})
```
读 `outputs/taste-guard/inspect-*/report.json` + 截图；`exit=0` 才算 0 FAIL。

## 四、边界

- 只修了 `index.html` 这一页；同目录其他生成页仍可能有各自 FAIL（`deep_audit` 可逐页扫）。
- 修的是**版式/可读性/真实性**，没有改数据契约、没有改 `window.js` 的业务刷新。
- 剩余 2 条 WARN 未强行清零：字号档位是全局壳的既有体系，h1 短句是刻意选择；要清可再收。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
