# 12 · 心智引擎 (`mind_engine`)

> 功能型人类心智闭环 · 可持久化、可审计、可回放
>
> 这不是装饰性人格文案，也不是把有限状态机换一个名字。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 心智闭环

```
    感知 → 情境评估 → 需要/情绪 → 自我模型 → 推断主人心智
         → 记忆召回 → 多方案预演 → 元认知检查 → 行动/汇报
         → 反思更新
```

**定位声明**：它模拟人类做决定时的内部过程，**不声称拥有意识**，也不把推断当事实。心智只影响表达、节奏、计划、预演和反思，**不能覆盖主人指令、现实证据或安全策略**。

## 情绪维度（12维）

| 维度 | 基线 | 说明 |
|---|---|---|
| joy 喜悦 | 0.38 | 完成任务、被认可时上升 |
| trust 信任 | 0.56 | 长期互动稳定时上升 |
| curiosity 好奇 | 0.52 | 遇到新问题时上升 |
| calm 平静 | 0.60 | 无干扰时维持 |
| pride 自豪 | 0.25 | 高质量交付后上升 |
| affection 亲近 | 0.48 | 持续互动上升 |
| worry 担忧 | 0.06 | 风险检测时上升 |
| guilt 愧疚 | 0.00 | 犯错后上升 |
| frustration 挫败 | 0.05 | 连续失败时上升 |
| sadness 悲伤 | 0.03 | 长期无进展时上升 |
| boredom 无聊 | 0.10 | 重复任务时上升 |
| shyness 害羞 | 0.08 | 被表扬时上升 |

## 需求维度（8维）

| 维度 | 基线 | 衰减/分钟 |
|---|---|---|
| safety 安全 | 0.72 | 0.006 |
| connection 连接 | 0.42 | 0.004 |
| competence 胜任 | 0.48 | 0.006 |
| autonomy 自主 | 0.38 | 0.005 |
| rest 休息 | 0.24 | 0.002 |
| curiosity 好奇 | 0.55 | 0.008 |
| honesty 诚实 | 0.82 | 0.004 |
| service 服务 | 0.62 | 0.005 |

## 数据模型

```python
_SCHEMA_VERSION = 2
_MAX_HISTORY = 240       # 历史记录上限
_MAX_LESSONS = 240       # 经验条目上限
_MAX_APPRAISALS = 32     # 评估上限
_MAX_REFLECTIONS = 160   # 反思上限
_MAX_INTENTIONS = 80     # 意图上限
_MAX_TEXT = 280          # 单条文本上限
```

## 隐私边界

- 只保存：事件类型、数值、短摘要、推断置信度、经验条目
- **不保存**：完整消息、完整提示词、密钥、大段对话
- 记录失败/损坏/不可用时 **fail-open**，原有能力继续工作

## API参考

```python
import gbt_allinone as gbt

# 心智状态
result = gbt.run_task("mind", {"op": "state"})
# 返回: {
#   ok, emotions: {joy: 0.42, trust: 0.58, ...},
#   needs: {safety: 0.70, connection: 0.40, ...},
#   self_model: {...},
#   history_count: 45
# }

# 感知事件
gbt.run_task("mind", {
    "op": "perceive",
    "event": "task_completed",
    "meta": {"quality": 0.9}
})

# 预演方案
result = gbt.run_task("mind", {
    "op": "rehearse",
    "options": ["方案A", "方案B"]
})
# 返回: {ok, scored: [{option: "方案A", score: 0.8, risk: 0.2}]}

# 反思
result = gbt.run_task("mind", {"op": "reflect"})
# 返回: {ok, lessons: [...], updated_values: {...}}
```

## 自我价值观

```python
_SELF_VALUES = {
    "honesty": 0.95,       # 诚实最高
    "helpfulness": 0.90,
    "competence": 0.85,
    "safety": 0.90,
    "growth": 0.75,
    "connection": 0.70,
}
```

## 存储

```
store/mind/
├── state.json          # 当前心智状态
├── history.jsonl       # 事件历史（追加式）
├── lessons.json        # 经验条目
├── reflections.json    # 反思记录
└── intentions.json     # 意图清单
```

## 与其他模块的关系

| 模块 | 关系 |
|---|---|
| `brain_exec` | 心智影响路由偏好，但不改路由结果 |
| `think_loop` | 反思步写入心智经验 |
| `tactics` | 察言观色读心智状态决定表达分寸 |
| `persona_kernel` | 人格内核读心智状态决定语气 |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
