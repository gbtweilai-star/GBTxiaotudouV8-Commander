# 25 · 创作域 (`creation`)

> 10+ 能力位 · 镜头导演 · ComfyUI节点 · 作品解剖 · 音乐自动化
>
> 把专业生产能力变成原生能力，不依赖外部软件本体。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单

| 能力位 | 说明 |
|---|---|
| `shot_director` | 镜头导演（十大坑→十修法，镜头表先于散文） |
| `forge_mastery` | 节点即触手·专业生产与自我递归（六轴自评+无限递归） |
| `comfy_native` | ComfyUI原生算子（27算子，离线可跑，不需本体） |
| `comfy_forge` | ComfyUI锻造 |
| `showcase_ops` | 作品解剖与展示（概念→会动的实物） |
| `music_auto` | 音乐自动化（四条时间轴对齐） |
| `art_brief` | 艺术简报 |
| `art_chain` | 艺术链 |
| `a1art_skill` | A1艺术技能 |
| `filmkit_cap` | 影视工具箱 |
| `drama` | 短剧生成 |
| `brand_outro` | 品牌片尾 |

## 镜头导演（shot_director）

### 核心理念

> 视频模型 = **一个从没见过你的剧组**
> （不能提问 · 按字面渲染 · 只做第一个动作 · 跳剪忘光位站位 · 不告诉它就不移镜）

### 十大坑 → 十修法

| 坑 | 修法 |
|---|---|
| 字面但死板 | **感觉的一个普通词 + 一个物理锚** |
| 一镜多动作 | **一镜一动作** |
| 道具不明 | 道具写手 |
| 光位漂移 | **每镜锁定句**（光/人/站位） |
| 位置遗忘 | 位置与地理每镜重述 |
| 散文式描述 | **镜头表先于散文** |
| 提交被拒 | 提交前合规预筛（分类器拒的是词不是意图） |

### API参考

```python
import gbt_allinone as gbt

# 生成镜头表
result = gbt.run_task("shot_director", {
    "op": "shot_table",
    "concept": "一个人在雨中奔跑"
})
# 返回: {
#   ok, shots: [
#     {no: 1, action: "奔跑", lock: "暖黄路灯/全身/左前45度", duration: 3},
#     {no: 2, action: "回头", lock: "同前", duration: 2}
#   ]
# }

# 检查规则
gbt.run_task("shot_director", {"op": "rules"})

# 标点检查
gbt.run_task("shot_director", {"op": "punctuation", "text": "..."})

# 合规预筛
gbt.run_task("shot_director", {"op": "moderation", "text": "..."})
```

## 节点即触手（forge_mastery）

### 核心理念

> ComfyUI 的每个节点就是一根触手，**根本不需要 ComfyUI 本体**；
> 把这项原生能力发挥到极致，懂所有专业生产能力与完美作品，
> 每次使用都要自我评判哪里不足，**无限制自我递归**。

### 一节点=一触手（六栏）

| 栏 | 内容 |
|---|---|
| 用途 | 这个节点做什么 |
| 输入 | 需要什么 |
| 输出 | 产出什么 |
| **判据** | 怎么算做对了 |
| 坑 | 常见错误 |
| 档位 | 参数范围 |

### 六轴自评

| 轴 | 判据 |
|---|---|
| 构图 | 三分法/黄金分割/引导线 |
| 光比 | 主辅光比/高光不溢出/暗部有细节 |
| 材质 | 反射/粗糙度/次表面散射 |
| 物理一致 | 光影方向一致/透视正确 |
| 风格锁定 | 与参考风格一致 |
| 交付规格 | 分辨率/色彩空间/格式 |

### 无限递归

```
judge（六轴打分）→ improve（改进一处）→ judge → improve → ...
```

每轮留痕；**一次只动一处**。

```python
# 自评
result = gbt.run_task("forge_mastery", {
    "op": "judge",
    "image": "output.png"
})
# 返回: {
#   ok, scores: {composition: 0.85, lighting: 0.72, material: 0.68, ...},
#   weakest: "material", suggestions: [...]
# }

# 递归改进
gbt.run_task("forge_mastery", {
    "op": "recurse",
    "image": "output.png",
    "max_rounds": 5
})
```

## ComfyUI原生算子（comfy_native）

**27个原生算子，离线可跑，不需ComfyUI本体。**

```python
# 列出算子
gbt.run_task("comfy_native", {"op": "list"})
# 返回: {ok, nodes: ["load_image", "resize", "blur", "sharpen", ...]}

# 执行
gbt.run_task("comfy_native", {
    "op": "run",
    "graph": [
        {"node": "load_image", "params": {"path": "in.png"}},
        {"node": "resize", "params": {"w": 1024, "h": 1024}},
        {"node": "sharpen", "params": {"amount": 0.5}},
        {"node": "save_image", "params": {"path": "out.png"}}
    ]
})
```

## 作品解剖（showcase_ops）

### 核心理念

> **用一个真会动的实物来讲解一个概念**

流程：
```
概念 → 会动的实物（例：cache key⇒弹子锁）
     → 几十个小而精确的零件（SVG+WebGL+3D）
     → 带标题/提示/实时读数的画框
     → 指针键盘下平静地动
     → 放大每个关节自检
     → 读数同源（图里每个数字都来自驱动零件运动的同一模型）
```

### 三条护栏

1. 署名必在
2. 未验标未验
3. 读数必须可指回

```python
# 概念→零件
gbt.run_task("showcase_ops", {
    "op": "concept",
    "idea": "解释什么是缓存键"
})
# 返回: {ok, metaphor: "弹子锁", parts: [...], readouts: [...]}

# 自检
gbt.run_task("showcase_ops", {"op": "selfcheck"})
```

## 音乐自动化（music_auto）

### 四条时间轴对齐

```
歌词 ─┐
音频 ─┼─→ 对齐 → 成品
主题 ─┤  （配色）
动画 ─┘
```

### 六步流水线

```
选源 → 匹词 → 定题 → 出片 → 分发 → 验收
```

### 边界

- AGPL不搬代码（只蒸思想）
- 音频歌词不外发
- 凭据不入仓
- 不编时间轴

## 授权门

| 作用域 | 覆盖 |
|---|---|
| `external_llm` | 调用外部生成模型 |
| `filesystem_write` | 写入产物 |
| `data_export` | 上传到外部服务 |

**不代付生成费**：视频/图像生成的外部API费用由用户自己承担。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
