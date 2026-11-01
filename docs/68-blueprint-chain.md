# 68 · 蓝图主链：架构 → 蓝图 → 过目 → 思维导图 → 派遣 → 落地（2026-11-01）

> 主人口径（逐字）：「必须由 GBT小土豆V8 根据用户给的架构框架来生成蓝图，用户看了没问题
> 就分析推理然后派遣思维导图任务指引给触手去执行任务，直至项目落地」。

这一串是**主链**：前面所有能力（能力位、覆盖、判据、账本）都是零件，这条链才是把它们串起来干活的东西。

---

## 一、五段（每段都有落盘产物）

| 段 | op | 做什么 | 产物 |
|---|---|---|---|
| ① 蓝图 | `make` | 架构 → 目标/阶段/任务/验收/风险 | `state/blueprints/<id>.json` + `.md` |
| ② 过目 | `approve` | **唯一允许的交互**（主人看蓝图）；批准即进入自主模式 | `<id>.approved.json` + autonomy.declare |
| ③ 思维导图 | `mindmap` | 分析推理 → 任务图（节点=任务，边=依赖）+ mermaid | `<id>.mindmap.json` + `.mmd` |
| ④ 派遣 | `dispatch` | 按依赖拓扑派遣触手（只跑安全能力位） | `<id>.runs.jsonl`（逐任务留痕） |
| ⑤ 落地 | `status` | 进度 / 是否落地（landed = **全部**任务 ok） | — |

## 二、纪律（写死在代码里）

1. **蓝图不过目不派遣**：dispatch 入口直接拒（实测返回 `user_error: 蓝图未过目不派遣`）；
2. **过目之后不许再问主人**：approve 里自动 `autonomy.declare`，此后除 danger/transfer 不打扰；
3. **只派遣安全能力位**：注册表里存在的位才派；危险能力/转账另走票；
4. **不装成功**：`landed` 要求**全部**任务通过；失败会列出 `failed_tasks`。

## 三、实测（一次完整闭环）

```
make     → id=gbt小土豆v8触手主-217c19 · 12 个任务（勘察4 / 设计2 / 实现2 / 验证2 / 固化2）
dispatch → 未过目 ⇒ 拒绝
approve  → approved=true，自动进入自主模式
mindmap  → 12 任务，依赖串好（先勘察→设计→实现→验证→固化）
dispatch → dispatched=12 · done=12 · failed=0 · skipped=0 · landed=True
status   → progress=1.0 · landed=True
```

## 四、顺手修的一个真问题（判据太窄会误杀）

第一版 `dispatch` 用 `gbt_result.ok` 判任务通过，结果 **12 个任务全被判失败**：
因为不同能力位回的信封不一样 —— `selfscan` 回 `verdict=clean` 没有 `ok`。
改成统一判据 `_task_ok()`：信封 ok + 结果里 `ok` + `verdict`（bad/fail/error 才算失败）。
**修完 done=12、landed=True。**

这条教训：**判据要按"有哪个看哪个"来**，拿单一字段当真理会把干净当失败。

## 五、判据（`tests/test_blueprint.py`，5 组 15 条）

蓝图生成 / 任务 ≥10 / json+md 落盘 / 未过目拒派 / 过目进入自主模式 /
思维导图有依赖有验收 / 派遣 done==dispatched / landed=True / progress=1.0。

## 六、边界

- 蓝图是**模板化生成**（五阶段 + 12 个安全任务），还没有接"用 LLM 按架构自由拆解"——
  那一步要等权重跑得动更长的上下文，现在先把**链路**打通并有判据；
- `dispatch` 只跑安全能力位（读面为主），真正写盘/发布类任务仍要走门；
- 每张蓝图的任务图/运行记录都在盘上，重启后可续跑。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 七、架构驱动：蓝图**照着主人的架构长**（同轮跟进）

第一版蓝图是五阶段固定模板（12 个任务）。主人给了完整架构后，单纯模板不够 ——
所以加了 **架构关键词 → 专项任务**（`ARCH_HINTS`）：

| 架构里说到 | 追加的专项任务（都只挑安全能力位） |
|---|---|
| 触手 / 主干 / 覆盖 | `trunk_cover scan`（orphan=0）、`omni_open scan`（插口动态发现） |
| 权重 / 大模型 / 推理 | `commander status`、`energy_core status` |
| 上下文 / 无限制 | `context_guard status`（窗口/溢出/落库） |
| 吞噬 / 进化 | `devour_auto tick`（只吃缺口且留痕） |
| 脉冲 / 提速 / 直达 | `pulse_core verify` + `pulse_core direct`（0 token 命中） |
| 图像 / 天真 / 秋叶 | `comfy_native harvest` + `coverage` |
| 自主 / 蓝图 / 落地 / 不打扰 | `autonomy status`、`orchestration panel` |
| 身体 / 器官 / 痛觉 | `body_sense status` |

## 八、真实架构跑通（2026-11-01）

主人那句架构（触手主干+权重能源核心+代码全覆盖+无界上下文+自主吞噬+脉冲提速+不打扰到落地）喂进去：

```
make      → id=gbt小土豆v8触手主-5d1942 · 23 任务（12 模板 + 11 架构专项）
approve   → 已过目，自动进入自主模式
mindmap   → 23 任务，依赖串好；mermaid 思维导图落盘
dispatch  → dispatched=23 · done=23 · failed=0 · skipped=0 · landed=True · 49s
status    → progress=1.0 · landed=True
```

**这就是「直至项目落地」的样子**：不是我说"做完了"，是 23 条任务逐条跑过、逐条留痕、
全部通过才算落地。

## 九、边界

- 专项任务按**关键词**触发，不是语义理解（LLM 自由拆解仍未接）；
- 派遣仍只跑安全能力位（读面为主）；写盘/发布类任务要过门；
- 蓝图 md 是**给主人过目的唯一界面**：里面逐条写清"哪根触手、验收是什么"。
