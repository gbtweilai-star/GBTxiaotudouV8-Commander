# 172 · 媒体舞台 / 音乐库 / 历史（P2-9）

> 主人 P2：「媒体舞台/音乐库/历史（只聚合既有产物）」。
> 只煎**索引/分组/历史判据**，不搬上传/转码/云存储；文件在允许根内由 console-server 服务。

## 一、四件

| 件 | 落点 |
|---|---|
| 模块/契约 | [`gbt_allinone/tools/media_library.py`](../../gbt_allinone/tools/media_library.py) · `verify()` **17 项** |
| 统一门 | 注册能力位 **`media_library`**（`run_task`，zero-scope 纯归一化） |
| API | `GET /api/media?kind=&limit=` 索引 + 历史；`GET /api/media/file?path=` 在允许根内服务（支持 Range） |
| APP 接线 | console 顶部「媒体舞台」：全部/视频/图片/音频筛选、卡片、最近产物、点开预览/播放/查看 |
| 验收 | [`tests/test_media_library.py`](../../tests/test_media_library.py) |

## 二、聚合口径

- 视频 `mp4/webm/mov/m4v/mkv`；图片 `png/jpg/jpeg/webp/gif/bmp`；音频 `mp3/wav/m4a/ogg/flac`；
- 去重（同路径）、mtime 倒序、上限 120、总扫描上限 500；不读文件内容/不生成缩略图/不转码；
- 文件服务只允许 `payload/media`、`交付成片`、`holo_pet_w3/kaleido`、`outputs` 根内，拒绝绝对路径与 `..`；
- 支持 `Range`（视频/音频拖动）；不暴露任意磁盘路径。

## 三、APP 产物同步

把既有 `交付成片/`（约 23MB）与 `holo_pet_w3/kaleido/`（约 37MB）复制成 APP `payload/media/`，让桌面版无需源码树也能聚合。真机读数：

| 项 | 读数 |
|---|---|
| `GET /api/media` | `count=28`（视频 11 / 图片 10 / 音频 7），根 `media` + `outputs` |
| 首个卡片 | `tts-20261102-231131` audio 0.08MB；点开 `<audio>` 源 `/api/media/file?path=outputs%2Fvoice-intercom%2F…wav` |
| 历史行 | 最近产物（夜灯/顶替新娘/ComfyUI/分镜…） |
| 路径穿越 | `/api/media/file?path=../secret.txt` → 404 |

![媒体舞台（APP 真机：分类/卡片/最近产物/预览）](../assets/app-media-stage.png)

## 四、边界（说死）

1. 只索引上述根内**已存在**的媒体文件；不上传/不转码/不生成缩略图；
2. `mkv/mov` 可索引但浏览器不一定能播（依赖 Electron 解码），不转码兜底；
3. 历史来自文件 mtime，不是创作流水线账（创作历史另接 `media_pipeline`）；
4. APP 的 `payload/media` 是**打包副本**（约 60MB），不是软链；源树新增媒体要重新同步；
5. 文件服务是只读 GET，无上传/删除接口。

## 五、复跑

```bash
py -3.14 -X utf8 tests/test_media_library.py
# GET http://127.0.0.1:8766/api/media
# console 顶部「媒体舞台」
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
