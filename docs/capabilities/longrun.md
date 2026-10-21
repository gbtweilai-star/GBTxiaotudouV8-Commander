# 长程任务 · `longrun`（4 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `lr_status` | 只读 | — | 长程任务层：任务图进度与详情 |
| `lr_submit` | 只读 | 是 | 长程任务层：提交任务（非LLM验收+重试+停滞升级，跨进程可续） |
| `lr_tick` | 只读 | — | 长程任务层：推进任务图（执行→验收→完成/重试/停滞） |
| `tactics_advise` | 只读 | — | 察言观色层：识别沟通信号→给出表达分寸（只调怎么说，不改事实） |

> 表格里是**摘要**（超过 140 字截断）；完整原文见 [`data/capabilities.json`](../../data/capabilities.json) 的 `desc` 字段。

---

返回 [能力总表](../03-capabilities.md)
