# 24 · 数字人 (`digital_human`)

> 5+ 能力位 · 全身线 · 微动 · 云库 · GPU渲染
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单

| 能力位 | 说明 |
|---|---|
| `digital_human` | 数字人主控（形象/动作/口型/表情） |
| `dh_brain` | 数字人脑（对话/情绪/记忆） |
| `dh_pose` | 姿态驱动 |
| `dh_rig` | 骨骼绑定 |
| `body_bridge` | 身体桥接（动作传输） |
| `dh_realism` | 真实感增强 |

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

### 骨骼绑定

```python
result = gbt.run_task("dh_rig", {
    "op": "bind",
    "model": "avatar.glb"
})
# 返回: {ok, bones: 40, rig_type: "humanoid"}
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
