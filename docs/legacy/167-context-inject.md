# 167 · 上下文注入 context_inject（P1）

> 主人 P1：「context_inject」。
> 对照上游参考项目的 ACI / 动态上下文注入 / 预取缓存 / UI 信号：只蒸**选择判据**，不搬 SQLite/embedding。
> 纯确定性：不调模型、不出网、不写盘。

## 一、四件

| 件 | 落点 |
|---|---|
| 模块/契约 | [`gbt_allinone/tools/context_inject.py`](../../gbt_allinone/tools/context_inject.py) · `verify()` **17 项** |
| 统一门 | 注册能力位 **`context_inject`**（`run_task`，zero-scope） |
| API | `GET/POST /api/context`：query + 真实候选（焦点栈 / memory_bank 印章 / 最近编排账）→ 选择结果；POST 可传自有 candidates/budget |
| APP 接线 | 右栏「上下文注入」：按最后一条用户消息预览；显示选中项（来源/分数）、预算 used/budget、丢因计数 |
| 验收 | [`tests/test_context_inject.py`](../../tests/test_context_inject.py) |

## 二、选择判据

- **过期**（`at+ttl < now`）直接丢；空文本丢；坏候选计入 invalid；
- **去重**：同文本只留最高分；
- **相关度**：query 与候选的 trigram/词覆盖（完全相同=1）；score = 0.6·rel + 0.25·priority + 0.15·freshness；
- **来源优先级**：主人令 1.0 / focus 0.95 / memory 0.85 / tool_result 0.7 / ui_signal 0.6 / prefetch 0.5；
- **配额**：同一 source 最多 1/3（40 条上限）；
- **预算**：200..12000 字符（默认 3000），打包不超；`remaining` 如实。
- 无 query 时按 priority/新鲜度选；结果带 `dropped` 明细与 `provenance`。

## 三、真机读数（2026-11-02 APP）

| 项 | 读数 |
|---|---|
| `GET /api/context?query=语音&budget=3000` | 真实候选 30（焦点/memory_bank/编排账）；selected 1；`used=3`；丢重复 29 |
| POST select 夹具 | query「语音对讲」→ memory 相关项置顶（score 0.825, relevance 1.0）；过期 1 丢；重复 1 丢；预算不超 |
| UI | 右栏显示 focus 项「盯构建」+ tool_result「run」，预算 `6/3000`，候选/丢因行 |
| 能力数 | 395 |

![上下文注入预览（APP 真机右栏）](../assets/app-context-inject.png)

## 四、边界（说死）

1. 只是**选择/预览**，**没有**自动注入到 `/api/chat` 的 prompt（下一步接主循环才叫真注入）；
2. 真实候选目前来自焦点栈 / memory_bank 印章 / 最近编排账；UI 信号只作为可选 source 支持，未从页面事件采集；
3. 未用语义 embedding，只用确定性字符/词覆盖；这是刻意的零依赖口径；
4. 零作用域，不读写盘；预算/配额是硬上限，宁缺不超。

## 五、复跑

```bash
py -3.14 -X utf8 tests/test_context_inject.py
# GET/POST http://127.0.0.1:8766/api/context
# CDP: window.__contextRefresh()
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
