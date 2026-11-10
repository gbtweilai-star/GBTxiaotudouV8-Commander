# 197 · 媒体舞台 / 视频舱：计数、工具栏与空态

日期：2026-11-07
范围：`holo_pet_w3/console/{media-stage.js,video-hub.js,app.css,index.html}`

## 体检发现的真问题

用 1600×1000 的 CDP 打开两页（本机有 28 件产物 / 33 个视频能力位），逐项量了 DOM 矩形：

| 问题 | 实测证据 |
|---|---|
| 媒体页把计数对象直接 JSON 摊在标题栏 | `28 件 · {"video":11,"image":10,"audio":7}` |
| 小于 1 MB 的产物全显示 `0.0 MB` | 81936 B 的 wav → `0.0 MB` |
| 视频页标题写死「六段」，实际渲染 7 列 | `#vh-stages .vh-stage` = 7，`/api/video` → `count:33, stages:7`（6 段 + 「其他」） |
| 两页工具栏右侧被页面角标压住 | `.ms-bar` 右缘 1183、`.page-pulse` 左缘 1102 ⇒ 重叠 81px；`刷新` 整颗被盖住；视频页 `全段联跑` 被盖 72px |
| 空态只有一句「暂无」，不告诉你该干什么 | `这个分类暂无产物` / `没有视频编目` |

## 改了什么

1. **计数可读**：媒体页改成 `28 件 · 视频 11 · 图片 10 · 音频 7`（按 `counts` 的 key 映射中文，未知 key 原样显示）。
2. **体积单位**：`humanSize` 增加 KB 档（<1 MB 显示 `82 KB`，最小 1 KB，不再是 `0.0 MB`）。
3. **视频计数跟真实阶段走**：`33 件 · 7 组阶段（六段可联跑）`；空编目时只显示 `0 件`，不硬凑「0 组阶段」。
   联跑摘要从写死的「六段全通」改成实数：`6/6 段通 · 未生成视频`（有段失败时带「（有段未通）」）。
4. **工具栏让位角标**：`.ms-bar` / `.vh-bar` 各加 `padding-right: 96px`，按钮右缘收到 1087，角标左缘 1102/1111 ⇒ 不再重叠。
5. **有引导空态**：
   - 媒体页：`还没有媒体产物。` + `产物来自产品目录 outputs/（语音互通 / 创作 / 视频）。跑一次对应任务后会自动出现在这里，也可以点右上「刷新」。`
     若在某一分类下为空，则提示「切回『全部』看看其它类型」。
   - 视频页：`没有读到视频编目。` + `点「刷新」重试；仍为空说明 /api/video 没返回任何能力位，先查后端再联跑。`
6. **按钮文案**：「六段联跑」→「全段联跑（只读探针）」，并把六段名字写进 `title`，避免和 7 列编目打架。

## 判据（可复跑）

```
node .scratch/probe-mv2.mjs     # 有数据态
  media.count  = "28 件 · 视频 11 · 图片 10 · 音频 7"
  media.size   = ["audio · 82 KB · …", "video · 2.9 MB · …"]
  video.count  = "33 件 · 7 组阶段（六段可联跑）"
  video.stages = 7
  run          = "… 6/6 段通 · 未生成视频"
  bar kids 右缘 1087 < pulse 左缘 1102 ⇒ 重叠 0

node .scratch/probe-empty.mjs   # 空数据态（CDP Fetch 域把 /api/media、/api/video 改写成空）
  media = "还没有媒体产物。\n产物来自产品目录 outputs/…"
  video = "没有读到视频编目。\n点「刷新」重试；…"
  videoCount = "0 件"
```

空态验证走 **CDP `Fetch` 域改写响应**，不改后端、不落盘、不删产物；验完已 `Fetch.disable` 并重新导航回真实数据态。

## 回归

- `node .scratch/audit2.mjs`：21 页 `errors: []`、`net: []`。
- `tools/codex-scripts/run-tests.py gbt_allinone.tests.test_console_chat_print` → 7 条 OK。
- `tests/test_chat_live_steps.py` → ALL OK。

## 注意

`media-stage.js` / `video-hub.js` 文件头带钢印，本轮只改实现体，钢印与文件头一字未动；
`media-stage.js` 是 **CRLF**，`video-hub.js` / `app.css` 是 **LF**，补丁脚本按文件实际行尾归一化后再写回。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
