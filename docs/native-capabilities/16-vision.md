# 16 · 视觉能力 (`vision`)

> **5 个能力位** · 视觉入口 · 接地通道 · 四觉闭环 · 视觉打印 · 流式观察
>
> ⚠️ **口径更正（2026-10-28 按注册表现读）**：本文旧版把
> `vision_snapshot` / `vision_diff` / `vision_stream_record` / `vision_stream_replay` / `vision_ocr` / `vision_probe`
> 写成了六个独立能力位。**注册表里没有这些名字**——前四个是
> **`tentacle` 能力位的 action**，不是独立位；`vision_ocr` / `vision_probe` 这两个名字**根本不存在**。
> 把 `vision_diff` 当能力位去调只会得到 `unknown capability`。
> 核验：`python docs/native-capabilities/verify_cap.py domain vision`
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单（逐位，取自注册表）

| 能力位 | 类型 | 说明 |
|---|---|---|
| `vision` | 只读 | 视觉/图像识别**入口**（良性子集，需外部依赖时留待接入） |
| `vision_grounding` | 只读 | **视觉/定位通道契约**：把「看」分层钉死——L1 结构层 / L2 接地层 / L3 回读层 |
| `vision_loop` | **需授权** | **原生四觉闭环**：视觉每次都要跟手分开用，不许"瞎子操作" |
| `vision_print` | 只读 | **视觉打印**：看到的东西可以原样以代码打印并渲染成看到的样子（五段链） |
| `vlx_flow` | 只读 | **流式观察 + 两层记忆**（接自 om-ai-lab/VLX-Flow · 七步法第一步） |

---

## 三层看（`vision_grounding` 的核心）

```
    L1 结构层  ← 优先
    ├─ UIA 控件树（domain_index / domain_read / domain_act / domain_type）
    ├─ CDP DOM（browser op=native）
    └─ HTTP / API 读数
         │  优先用这个：精确、不看像素、无视遮挡
         ▼
    L2 接地层  ← 仅兜底
    └─ 像素 + 模型 grounding（VLX-Flow 级）
       只用于：自绘 UI / Canvas / 游戏 / 无 a11y 窗口
         │
         ▼
    L3 回读层  ← 每次动手后必做
    └─ 用 L1 再读一次确认
```

**三条铁律**：
1. **先结构后像素**——用了 L2 而没有 L1 尝试记录 ⇒ 记违规 `struct_first`
2. **动完没回读 ⇒ `unverified`**——不许默认"点成功了"
3. **不编**——读不到就如实报"控件不在 a11y 树里"

---

## 视觉传输总线（`tentacle` 的 action，不是独立位）

眼睛的每一帧都可缓存、可定位、可回放、可进流水线：

```python
import gbt_allinone as gbt

# ① 快照缓存：aHash 感知指纹，同画面零成本复用（JPEG 编码噪声免疫）
result = gbt.run_task("tentacle", {"action": "vision_snapshot", "tag": "step1"})
# 返回: {ok, tag, path: "store/frames/step1.png", hash: "a3f5e2...", w, h, ms}

# 再抓同画面 → 指纹命中，零成本
gbt.run_task("tentacle", {"action": "vision_snapshot", "tag": "step1"})
# 返回: {ok, cached: true, hash: "a3f5e2..."}

# ② 变化定位：网格块哈希给出**变化矩形**（归一化坐标）
result = gbt.run_task("tentacle", {"action": "vision_diff", "tag": "step1"})
# 返回: {ok, changed: true,
#        rect: {x: 0.12, y: 0.34, w: 0.5, h: 0.2},
#        blocks_changed: 12, total_blocks: 400, change_ratio: 0.03}

# ③ 流记录
gbt.run_task("tentacle", {"action": "vision_stream_record", "op": "start"})
# … 一系列操作 …
gbt.run_task("tentacle", {"action": "vision_stream_record", "op": "stop"})
# 返回: {ok, stream_id: "vs-20261028", frames: 45, changes: 12}

# ④ 流回放 + 变化段提取
result = gbt.run_task("tentacle", {
    "action": "vision_stream_replay", "stream_id": "vs-20261028"
})
# 返回: {ok, timeline: [{ts, frame, changed}], change_segments: [...]}
```

**为什么用网格块哈希**：不说"变了"，而是给出**变化矩形**——知道哪一块变了，才能精确验证操作效果。

---

## 视觉打印（`vision_print` · 五段链）

> 主人令：「看到的东西都可以原样以代码打印并渲染成看到的样子」

```
    ① see     原生眼取帧（tentacle/omni_core._screen_capture：dxcam → mss → pyautogui，或直接喂图）
         │
    ② print   码落地（**码由她/调用方给**，本件**不编码**）
         │
    ③ render  真 Chromium/Edge 渲（只放行 file: / data: / blob:，其余逐条记拦获；
         │      pageerror / console / requestfailed 三条都记）
    ④ diff    与所见帧比（指纹尺子**只许一把**：tentacle/vision_bus）
         │
    ⑤ judge   成档
```

### 五个现算数（不是"看起来像"）

| 数 | 作用 |
|---|---|
| aHash 汉明距离 | 整体相似度 |
| 块变化率 | 有多少块变了 |
| 平均亮度差 | 明暗漂移 |
| **变化像素占比** | 局部敏感项 |
| **最大块平均差** | 局部敏感项 |

> **实测教训**：只改一处文字颜色时，整图 aHash 距离 = **0**——靠后两个局部敏感数才抓到。
> 只用 aHash 就是**假绿**。

### 档位

`同款` / `接近` / `不像`，判据写在 `_BANDS`（可复核可改）。

### 用法

```python
result = gbt.run_task("vision_print", {"op": "see"})
# 取帧

result = gbt.run_task("vision_print", {
    "op": "print",
    "code": "<html>...</html>"   # 码由调用方给
})

result = gbt.run_task("vision_print", {"op": "diff"})
# 与所见帧比，出五个现算数

result = gbt.run_task("vision_print", {"op": "loop"})
# 五段链一次跑完

result = gbt.run_task("vision_print", {"op": "status"})
result = gbt.run_task("vision_print", {"op": "where"})
```

**边界**：
- 抽不出代码块 ⇒ 如实报 `no_code`（**不拿散文去渲**）
- `op=ask_model` 的看图回码靠**外部视觉模型**（底座没有视觉塔），缺依赖如实报 `needs_dependency`
- 每跑一次落 `store/vision_print/ledger.jsonl`（只追加）+ 框架审计一条

---

## 视觉识别（`vision`）

```python
result = gbt.run_task("vision", {
    "op": "describe",
    "image": "store/frames/step1.png"
})
# 返回: {ok, description: "一个浏览器窗口，显示登录页面..."}
```

**关于 OCR（重要更正）**：

> **注册表里没有独立的 OCR 能力位。** 旧版写的 `vision_ocr` 是**编出来的名字**。
> 要做文字识别，只有两条真路：
> 1. 走 `vision` 入口 + **外部视觉后端**（AutoGLM / OpenAI Vision）
> 2. 走 `vision_print` 的 `op=ask_model`（同样依赖外部视觉模型）
>
> 两条都缺后端时，**如实报 `needs_dependency`**——不假装识别成功，也不返回空文本冒充结果。

---

## 流式观察（`vlx_flow`）

```python
result = gbt.run_task("vlx_flow", {"op": "observe"})
```

**两层记忆**：短期帧序列 + 长期模式，用于连续观察而非单帧快照。

---

## 后端依赖

| 后端 | 用途 | 环境变量 | 缺失时 |
|---|---|---|---|
| AutoGLM | 图像理解 | `AUTOGLM_API_KEY` | `needs_dependency` |
| OpenAI Vision | 图像理解 | `OPENAI_API_KEY` | `needs_dependency` |
| dxcam | DXGI 硬采 | 本机安装 | 降级 mss → pyautogui |
| Chromium/Edge | 渲染（vision_print） | 系统浏览器 | `needs_dependency` |

**能力位永远在注册表、永远可调用**：缺后端时如实报 `needs_dependency`，不静默失败、不被删除或限制。

---

## 断头路修复记录

- `brain.gatekeeper` 垫片补齐，截图显式落盘走 V8 镜像管线（channel=`mirror_pipeline`）
- 视觉总线**强制全屏帧**（`omni_core` 的 delta 局部图会破坏对比语义——这也是 `tentacle_see` 偶发失败的根因）

---

## 性能

| 操作 | 耗时 |
|---|---|
| DXGI 硬采一帧 | 28-34ms |
| aHash 计算 | ~2ms |
| 网格差分（400 块） | ~5ms |
| 视觉打印五段链 | ~1.5s（含 Chromium 渲染） |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
