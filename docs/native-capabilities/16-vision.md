# 16 · 视觉能力 (`vision`)

> 5+ 能力位 · 感知指纹 · 变化定位 · 流回放 · OCR
>
> 视觉不是孤立快照——眼睛的每一帧都可缓存、可定位、可回放、可进流水线。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 视觉传输总线

```
    眼睛（DXGI硬采）
         │
    ┌────▼─────┐
    │ 快照缓存  │  aHash感知指纹，同画面零成本复用
    └────┬─────┘
         │
    ┌────▼─────┐
    │ 变化定位  │  网格块哈希 → 变化矩形（归一化坐标）
    └────┬─────┘
         │
    ┌────▼─────┐
    │ 流记录    │  帧时间线落store（指纹+变化标记）
    └────┬─────┘
         │
    ┌────▼─────┐
    │ 流回放    │  变化段提取
    └──────────┘
```

## 能力清单

| 能力位 | 说明 |
|---|---|
| `vision` | 视觉/图像识别（需AutoGLM/OpenAI视觉后端） |
| `vision_snapshot` | 感知指纹（aHash）快照缓存，同画面零成本复用（JPEG编码噪声免疫） |
| `vision_diff` | 变化区域定位——网格块哈希给出变化矩形（归一化坐标） |
| `vision_stream_record` | 视觉流帧时间线落store（指纹+变化标记） |
| `vision_stream_replay` | 流回放+变化段提取 |
| `vision_ocr` | OCR文字识别 |
| `vision_grounding` | 视觉定位（自然语言→屏幕坐标） |
| `vision_print` | 视觉指纹打印 |
| `vision_probe` | 视觉探针 |

## API参考

### 快照缓存

```python
import gbt_allinone as gbt

# 抓快照（带指纹）
result = gbt.run_task("tentacle", {"action": "vision_snapshot", "tag": "step1"})
# 返回: {
#   ok, tag: "step1",
#   path: "store/frames/step1.png",
#   hash: "a3f5e2...",   # aHash 64位
#   w: 1920, h: 1080, ms: 32
# }

# 同一画面再抓 → 指纹命中，零成本
result = gbt.run_task("tentacle", {"action": "vision_snapshot", "tag": "step1"})
# 返回: {ok, cached: true, hash: "a3f5e2..."}
```

### 变化定位

```python
# 执行操作前抓基线
gbt.run_task("tentacle", {"action": "vision_snapshot", "tag": "before"})

# ... 操作 ...

# 对比
result = gbt.run_task("tentacle", {"action": "vision_diff", "tag": "before"})
# 返回: {
#   ok, changed: true,
#   rect: {x: 0.12, y: 0.34, w: 0.5, h: 0.2},   # 归一化坐标
#   blocks_changed: 12, total_blocks: 400,
#   change_ratio: 0.03
# }
```

**为什么用网格块哈希**：不说"变了"，而是给出**变化矩形**——知道哪一块变了，才能精确验证操作效果。

### 流记录与回放

```python
# 开始记录
gbt.run_task("tentacle", {"action": "vision_stream_record", "op": "start"})

# ... 一系列操作 ...

# 停止记录
gbt.run_task("tentacle", {"action": "vision_stream_record", "op": "stop"})
# 返回: {ok, stream_id: "vs-20261028", frames: 45, changes: 12}

# 回放
result = gbt.run_task("tentacle", {"action": "vision_stream_replay", "stream_id": "vs-20261028"})
# 返回: {ok, timeline: [{ts, frame, changed: true}], change_segments: [...]}
```

### 视觉识别

```python
# 需要视觉后端（AutoGLM/OpenAI）
result = gbt.run_task("vision", {
    "op": "describe",
    "image": "store/frames/step1.png"
})
# 返回: {ok, description: "一个浏览器窗口，显示登录页面..."}

# OCR
result = gbt.run_task("vision_ocr", {"image": "store/frames/step1.png"})
# 返回: {ok, text: "用户名\n密码\n登录", blocks: [{text, box, conf}]}

# 视觉定位（自然语言→坐标）
result = gbt.run_task("vision_grounding", {
    "image": "store/frames/step1.png",
    "target": "登录按钮"
})
# 返回: {ok, x: 960, y: 540, conf: 0.92}
```

## 后端依赖

| 后端 | 用途 | 环境变量 |
|---|---|---|
| AutoGLM | 图像理解 | `AUTOGLM_API_KEY` |
| OpenAI Vision | 图像理解 | `OPENAI_API_KEY` |
| PaddleOCR | 本地OCR | 本地安装 |
| Tesseract | 本地OCR | 系统安装 |

缺失时如实报 `needs_dependency`，**能力位永远在注册表、永远可调用**，不静默失败、不被删除或限制。

## 断头路修复记录

- `brain.gatekeeper` 垫片补齐，截图显式落盘走V8镜像管线（channel=mirror_pipeline）
- 视觉总线强制全屏帧（omni_core的delta局部图会破坏对比语义——这也是`tentacle_see`偶发失败的根因）

## 性能

| 操作 | 耗时 |
|---|---|
| DXGI硬采一帧 | 28-34ms |
| aHash计算 | ~2ms |
| 网格差分（400块） | ~5ms |
| OCR（本地） | ~200ms |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
