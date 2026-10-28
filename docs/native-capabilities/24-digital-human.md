# 24 · 数字人 (`digital_human` / `dh_*` / `body_*`)

> 12 能力位（横切 3 个域）· 以图生视频 · 姿态 · 真实感 · 身体桥
>
> ⚠️ **口径更正（2026-10-28 按注册表现读）**：本文旧版写了 `dh_rig` 与 `body_bridge`
> 两个能力位名。**注册表里没有这两个名字**——真名是 `dh_asset_gate`，以及
> `body_see/say/click/type/open/volume/map` 七位（域 `device`）。
> 按旧名调用只会得到 `unknown capability`。
> 核验：`python docs/native-capabilities/verify_cap.py domain video`
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单（逐位，取自注册表）

| 能力位 | 域 | 类型 | 说明 |
|---|---|---|---|
| `digital_human` | `video` | 只读 | 数字人「以图生视频」（本地 SadTalker，零账号/零验证）：**一张照片 + 一段配音 ⇒ 带头部动作与口型同步的成片** |
| `dh_brain` | `creation` | 只读 | 数字人脑（对话/情绪/记忆） |
| `dh_pose` | `creation` | 只读 | 姿态驱动（微动/重心/呼吸） |
| `dh_realism` | `creation` | 只读 | 真实感增强 |
| `dh_asset_gate` | `creation` | 只读 | 数字人资产门（形象/动作/贴图的准入判据） |
| `body_see` | `device` | 只读 | 身体·看：截当前屏幕落 png |
| `body_say` | `device` | 只读 | 身体·说：系统 TTS 念一句 |
| `body_click` | `device` | 只读 | 身体·点：按坐标点按 |
| `body_type` | `device` | 只读 | 身体·打字：向前台窗口键入文本 |
| `body_open` | `device` | 只读 | 身体·打开：系统默认程序打开文件/网址 |
| `body_volume` | `device` | 只读 | 身体·音量：读或设主音量 |
| `body_map` | `device` | 只读 | 身体·清单：现读本机七根感官与六根动作 |

> **`body_*` 七位为什么算进数字人篇**：数字人要"活着"，就得能看、能说、能动手。
> 这七位是她的**身体**；`digital_human` 是她的**脸和口型**；`dh_*` 是她的**动作与质感**。
> 三者合起来才是一个完整的"人"。

---

## 技术栈

```
    文本/语音输入
         │
    ┌────▼────┐
    │ 对话脑   │  dh_brain（LLM+情绪+记忆）
    └────┬────┘
         │
    ┌────▼────┐
    │ 口型生成 │  音素→口型映射
    └────┬────┘
         │
    ┌────▼────┐
    │ 姿态驱动 │  dh_pose（微动/重心/呼吸）
    └────┬────┘
         │
    ┌────▼────┐
    │ 渲染     │  GPU渲染 / 云端渲染
    └─────────┘
```

## 关键技术

### 逐行S形重心转移

比整帧仿射更像人的动作生成：

```python
# 整帧仿射（旧）→ 僵硬
# 逐行S形重心转移（新）→ 自然
# 实测：1s试片帧差 0.131 → 0.399
```

### 微动（micro-motion）

- 呼吸起伏
- 眨眼
- 头部微摆
- 重心微移

### 云库

形象/动作/表情资产云端存储，按需加载。

## API参考

### 生成数字人视频

```python
import gbt_allinone as gbt

result = gbt.run_task("digital_human", {
    "op": "generate",
    "script": "大家好，我是GBT小土豆V8",
    "avatar": "default",
    "voice": "zh-CN-XiaoxiaoNeural",
    "out": "dh_output.mp4"
})
# 返回: {ok, path: "dh_output.mp4", duration: 5.2, fps: 30}
```

### 姿态驱动

```python
result = gbt.run_task("dh_pose", {
    "op": "drive",
    "motion": "wave",     # wave/nod/shake/idle
    "duration": 2.0
})
```

### 资产准入（dh_asset_gate）

```python
result = gbt.run_task("dh_asset_gate", {
    "op": "check",
    "model": "avatar.glb"
})
# 返回: {ok, bones: 40, rig_type: "humanoid", textures_ok: true, passed: true}
```

**为什么先过资产门**：形象/动作/贴图不合格就进渲染，出来的是废片。
准入判据放在**渲染之前**，不是渲染之后。

### 真实感增强（dh_realism）

```python
result = gbt.run_task("dh_realism", {
    "op": "enhance",
    "src": "raw.mp4",
    "out": "enhanced.mp4"
})
```

### 身体七位（body_*）

```python
# 先问清楚本机有什么
gbt.run_task("body_map", {})

# 看 / 说 / 音量
gbt.run_task("body_see", {"monitor": 1})
gbt.run_task("body_say", {"text": "大家好，我是GBT小土豆V8", "rate": 1.0})
gbt.run_task("body_volume", {"level": 0.6})

# 点 / 打字 / 打开
gbt.run_task("body_click", {"x": 960, "y": 540, "clicks": 1})
gbt.run_task("body_type", {"text": "hello"})
gbt.run_task("body_open", {"target": "https://example.com"})
```

## 资产规格

| 资产 | 规格 |
|---|---|
| 模型格式 | GLB（40骨骼） |
| 贴图 | 2048×2048 PBR |
| 动画 | 30fps |
| 输出 | MP4（H.264） |

## 无人值守收尾

```bash
# 完整流程：等片→微动→交付→三条验收→上云
python -m gbt_allinone.tools.dh_finish_clip
```

## 实测记录

| 项目 | 结果 |
|---|---|
| 逐行S形重心转移 | 帧差 0.131 → 0.399（更自然） |
| GPU五试五败 | 详见 `docs/` 记录 |
| 音轨验证 | 实测相关1.0000确认为普通话 |

## 踩坑记录（13条）

完整踩坑记录见 `gbt_allinone/docs/` 下的数字人相关文档。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
