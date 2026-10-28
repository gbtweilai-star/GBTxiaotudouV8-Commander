# 07 · 推演环 (`think_loop`)

> 1 能力位 · 完整心智循环七步 · 从理解到反思的闭环
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 设计来源

按AI的完整心智模型设计——下达任务→自己理解需求→调用工具→自我纠错→反向延伸→反思进取→整理结果。

吸收Copilot Learn / Manus / Agent的精髓，但全部落在V8自己的纪律上：
- LLM只有提案权，无执行权
- 推演在镜像维度，现实只收成品

## 七步循环

```
    ┌─────────────────────────────────────────┐
    │            think_loop(goal)              │
    └────────────────┬────────────────────────┘
                     │
    ┌────────────────▼────────────────────────┐
    │ 1. 理解    LLM复述任务+约束              │
    │            （防理解偏差，只出理解不出代码）│
    └────────────────┬────────────────────────┘
                     │
    ┌────────────────▼────────────────────────┐
    │ 2. 推演    方案在镜像维度dry-run          │
    │            （不碰现实；假设/模拟全在这里） │
    └────────────────┬────────────────────────┘
                     │
    ┌────────────────▼────────────────────────┐
    │ 3. 执行    万能插真跑（调用工具）          │
    └────────────────┬────────────────────────┘
                     │
    ┌────────────────▼────────────────────────┐
    │ 4. 纠错    失败自动诊断根因               │
    │            LLM提案→改方案→重试            │
    └────────────────┬────────────────────────┘
                     │
    ┌────────────────▼────────────────────────┐
    │ 5. 反向延伸 结果反推                      │
    │            下一步工作+最脆弱一环           │
    └────────────────┬────────────────────────┘
                     │
    ┌────────────────▼────────────────────────┐
    │ 6. 反思    领悟提炼落盘                   │
    │            polish_insights 永久资产       │
    └────────────────┬────────────────────────┘
                     │
    ┌────────────────▼────────────────────────┐
    │ 7. 整理    结构化结果+审计留痕            │
    └─────────────────────────────────────────┘
```

## API参考

```python
import gbt_allinone as gbt

result = gbt.run_task("think_loop", {
    "goal": "分析example.com的安全状况并生成报告"
})
# 返回: {
#   ok,
#   steps: {
#     1_understand: {ok, understanding: "..."},
#     2_simulate: {ok, plan: [...]},
#     3_execute: {ok, autopilot: {...}},
#     4_correct: {ok, needed: false/true, ...},
#     5_extend: {ok, next_steps: [...], weakest: "..."},
#     6_reflect: {ok, insight: "...", saved: true},
#     7_organize: {ok, result: "...", audit_id: "..."}
#   },
#   gbt_stamp: {...}
# }
```

## 各步实现

### Step 1 · 理解

```python
def _step_understand(goal):
    """LLM复述任务要点（防偏差）。失败则原样返回。"""
    reply = _llm(
        f"用不超过5行复述这个任务要达成什么、关键约束是什么、怎样算完成"
        f"（只复述理解，不写方案不写代码）：\n{goal[:600]}",
        max_tokens=300, timeout=45)
```

### Step 2 · 推演

```python
def _step_simulate(goal, understanding):
    """镜像维度生成方案草案（autopilot dry_run——只拆解校验，不执行）。"""
    r = autopilot(goal, max_rounds=1, dry_run=True)
```

### Step 3 · 执行

```python
def _step_execute(goal):
    """万能插真跑（autopilot实跑=调用工具+自检）。"""
    r = autopilot(goal, max_rounds=3)
```

### Step 4 · 纠错

```python
def _step_correct(goal, exec_result):
    """失败时诊断根因并给出修正方向（LLM提案，人/上层定夺）。"""
```

### Step 5 · 反向延伸

```python
def _step_extend(goal, exec_result):
    """结果反推：下一步工作+最脆弱一环。"""
```

### Step 6 · 反思

```python
def _step_reflect(goal, steps_so_far):
    """领悟提炼落盘（polish_insights——永久资产）。"""
```

### Step 7 · 整理

```python
def _step_organize(goal, steps_so_far):
    """结构化结果+审计留痕。"""
```

## LLM调用纪律

```python
def _llm(prompt, max_tokens=600, timeout=60):
    # 统一走 llm.unified.ask（框架内所有模块必须经此口调用模型）
    from .llm import unified as LLM
    r = LLM.ask(prompt, max_tokens=max_tokens, timeout=timeout, purpose="think_loop")
```

- 模块自己import bridge视为漂移
- 返回与bridge.chat同形（ok/reply/provider/model）
- 多一样：`drift`（落到别家会如实报，不静默降级）

## 领悟资产

反思步的领悟落盘到 `store/polish_insights.json`，是框架的**永久资产**——每次推演环的反思都在积累，不只是跑完就丢。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
