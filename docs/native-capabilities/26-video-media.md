# 26 · 视频媒体域 (`video` / `image_video`)

> 15 能力位 · 视频生成 · 剪辑 · 音频 · 发布 · 钢印
>
> 视频不是"调一次 API"，是一条从素材到成片、到许可、到钢印的完整链路。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单（逐位，取自注册表）

| 能力位 | 类型 | 说明 |
|---|---|---|
| `actioncam` | 需授权 | 动作镜头控制系统（拍子表制）：10 种动作运镜语法（POV主观/甩镜/急推/手持抖/推拉/环绕/打击帧停格）× 4 种档位 |
| `audio_extract` | 需授权 | 从视频里取出声音（本机 ffmpeg，**零出网**）：probe/tracks 读流与音轨（只读）；extract 真提取 |
| `audio_mix` | 需授权 | 混音与母带（本机 ffmpeg，**零出网**）：`mix` 多轨合成（amix，逐路音量，显式 normalize=0） |
| `digital_human` | 只读 | 数字人「以图生视频」（本地 SadTalker，零账号/零验证）：一张照片 + 一段配音 ⇒ 带头部动作与口型同步的成片 |
| `edit_pipeline` | 需授权 | 剪辑引擎（蒸馏剪映时间线语义）：轨道→片段→目标/源时间区间→变速/音量/转场/文本，真渲染 1080×1920 成片 |
| `h3_video_gen` | 只读 | H3mini 视频生成（只读骨架·门）：四原语 T2VA / I2VA / FL2VA / Ref2VA + 三条带牙用例（密钥不走明文） |
| `libtv_skill` | 只读 | LibTV 技能（只读骨架·门）：Agent 创作平台入口（会话进展/增量轮询 + 切项目 + 批量下载） |
| `libtv_workflow` | 只读 | LibTV 节点式工作流（只读骨架·门）：五动作 create_node / connect / set_params / run |
| `look_grade` | 需授权 | 外观库触手（词即指令）：一处定义多样的味道（电影感/做旧/潮湿阴冷/热血橙青/褪色胶片/黑白纪实/赛博霓虹/**原样**） |
| `media_license` | 需授权 | 素材许可账（"没有许可的素材不许进成品格"的数据源）：`register` 逐件登记，现读 |
| `media_pipeline` | 只读 | AI 短视频/电影/音乐流水线：镜像房间编排、产物自审、版权/安全/品牌/质量检查、主人授权后发布 |
| `media_publish` | 需授权 | 三方向**发布到赚钱平台**的准备与授权门：`platforms <方向>` 读平台口径 |
| `media_run` | 需授权 | 三方向自动化工作流**执行器**：一次调用把一条链从头走到尾，每步落真件 + 同批登记许可 |
| `media_stamp` | 需授权 | 音视频**钢印**（作品出处）：把署名写进**容器元数据**（title/artist/album/comment/description） |
| `a1art_skill` | 只读 | a1.art API 技能（只读骨架·门）：五原语 LOOKUP→UPLOAD→GENERATE→OPTIMIZE→POLL |

---

## 媒体链路全景

```
    素材（图/音/视频）
         │
    ┌────▼────────┐
    │ media_license│  逐件登记许可（没许可不许进成品）
    └────┬─────────┘
         │
    ┌────▼────────┐
    │ edit_pipeline│  轨道→片段→区间→变速/转场/文本
    │ actioncam    │  运镜语法（10 种 × 4 档）
    │ look_grade   │  外观调色（词即指令）
    └────┬─────────┘
         │
    ┌────▼────────┐
    │ audio_extract│  取声
    │ audio_mix    │  混音与母带
    └────┬─────────┘
         │
    ┌────▼────────┐
    │ media_stamp  │  钢印写进容器元数据
    └────┬─────────┘
         │
    ┌────▼────────┐
    │ media_publish│  发布门（主人授权后）
    └─────────────┘
```

---

## API 参考

### 剪辑（edit_pipeline）

```python
import gbt_allinone as gbt

result = gbt.run_task("edit_pipeline", {
    "op": "render",
    "tracks": [
        {"type": "video", "clips": [
            {"src": "a.mp4", "dst_in": 0, "dst_out": 3.0,
             "src_in": 1.0, "speed": 1.0},
            {"src": "b.mp4", "dst_in": 3.0, "dst_out": 6.0,
             "transition": {"kind": "fade", "dur": 0.4}}
        ]},
        {"type": "audio", "clips": [
            {"src": "bgm.mp3", "dst_in": 0, "dst_out": 6.0, "volume": 0.35}
        ]},
        {"type": "text", "clips": [
            {"text": "GBT小土豆V8", "dst_in": 0.5, "dst_out": 3.0,
             "pos": "bottom", "size": 48}
        ]}
    ],
    "out": "final.mp4",
    "size": "1080x1920"
})
# 返回: {ok, path: "final.mp4", duration: 6.0, fps: 30, ms: 12000}
```

### 运镜（actioncam）

```python
result = gbt.run_task("actioncam", {
    "op": "plan",
    "beats": [  # 拍子表：每个 beat 一条运镜语法
        {"at": 0.0, "move": "pov", "gear": 2},
        {"at": 2.0, "move": "whip", "gear": 3},
        {"at": 3.5, "move": "punch_in", "gear": 2},
        {"at": 5.0, "move": "freeze", "gear": 1}
    ]
})
# 返回: {ok, shots: [...], total_duration: 6.0}
```

**10 种运镜语法**：POV 主观 / 甩镜 / 急推 / 手持抖 / 推拉 / 环绕 / 打击帧停格（+3 种扩展）
**4 种档位**：幅度/速度分档

### 取声与混音（零出网）

```python
# 读流与音轨（只读）
gbt.run_task("audio_extract", {"op": "probe", "src": "in.mp4"})
gbt.run_task("audio_extract", {"op": "tracks", "src": "in.mp4"})

# 真提取
gbt.run_task("audio_extract", {"op": "extract", "src": "in.mp4", "out": "a.wav"})

# 多轨合成（逐路音量，显式 normalize=0）
gbt.run_task("audio_mix", {
    "op": "mix",
    "tracks": [
        {"src": "voice.wav", "volume": 1.0},
        {"src": "bgm.mp3", "volume": 0.3}
    ],
    "out": "mixed.wav"
})
```

### 调色（look_grade）

```python
result = gbt.run_task("look_grade", {
    "op": "apply",
    "src": "in.mp4",
    "look": "电影感",   # 或 做旧 / 潮湿阴冷 / 热血橙青 / 褪色胶片 / 黑白纪实 / 赛博霓虹 / 原样
    "out": "graded.mp4"
})
```

### 素材许可（media_license）

```python
# 逐件登记（现读）
gbt.run_task("media_license", {
    "op": "register",
    "items": [
        {"path": "bgm.mp3", "source": "自购", "license": "royalty-free", "proof": "order-12345"},
        {"path": "clip.mp4", "source": "自拍", "license": "own"}
    ]
})

# 查账
gbt.run_task("media_license", {"op": "list"})
```

**家规**：没有许可的素材不许进成品格。

### 钢印（media_stamp）

```python
result = gbt.run_task("media_stamp", {
    "op": "stamp",
    "src": "final.mp4",
    "out": "final_stamped.mp4",
    "meta": {
        "title": "作品名",
        "artist": "自由的风",
        "comment": "开发者：自由的风 · GBT小土豆V8"
    }
})
```

署名写进**容器元数据**，不是画面水印——不可裁剪、不可遮挡。

### 流水线（media_pipeline）

```python
result = gbt.run_task("media_pipeline", {
    "op": "plan",
    "direction": "short_video",   # short_video / film / music
    "brief": "30秒产品介绍"
})
# 返回: {ok, steps: [...], checks: [版权/安全/品牌/质量]}
```

### 一键跑完整链（media_run）

```python
result = gbt.run_task("media_run", {
    "op": "run",
    "direction": "short_video",
    "brief": "30秒产品介绍",
    "auto_license": True
})
# 每步落真件 + 同批登记许可
```

### 发布门（media_publish）

```python
# 读平台口径
gbt.run_task("media_publish", {"op": "platforms", "direction": "short_video"})

# 发布（需主人授权）
gbt.run_task("media_publish", {"op": "publish", "platform": "douyin", "file": "final.mp4"})
```

---

## 边界与纪律

| 纪律 | 说明 |
|---|---|
| **零出网优先** | `audio_extract` / `audio_mix` 走本机 ffmpeg，不上传任何素材 |
| **许可先行** | 没登记的素材不许进成品格 |
| **钢印进容器** | 署名写元数据，不做可裁剪的水印 |
| **发布要授权** | `deploy_publish` / `data_export` 门 |
| **不代付生成费** | 外部生成 API 的费用由用户自己承担 |
| **密钥不明文** | `h3_video_gen` / `libtv_*` 走密钥网关，不落明文 |

## 依赖

| 依赖 | 用途 | 缺失时 |
|---|---|---|
| ffmpeg | 取声/混音/渲染 | 如实报 `needs_dependency` |
| SadTalker | 数字人生成 | 如实报 `needs_dependency` |
| Pillow | 图像处理 | 如实报 `needs_dependency` |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
