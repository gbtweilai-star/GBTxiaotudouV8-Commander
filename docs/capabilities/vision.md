# 视觉 · `vision`（5 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `vision` | 只读 | — | 视觉/图像识别入口（良性子集，需外部依赖时留待接入） |
| `vision_grounding` | 只读 | — | **视觉/定位通道契约**（主人令 2026-10-11「视觉必须达到 VLX-Flow 水平，脑-手同步**不能使用传统截图**看来在操作」）：把「看」分层钉死 —— **L1 结构层**（UIA 控件树 domain_index/domain_read/domain_act/… |
| `vision_loop` | **需授权** | — | **原生四觉闭环**（主人令 2026-10-09：「她的视觉每次都要跟手分开去使用传统的**瞎子操作**……把视觉这么使用给她**钉死在上面**」「我看她每次执行任务就是**瞎还没脑**」＋「还有耳，嘴」）。**眼·耳·嘴·手四觉 → 脑 → 手 → 验**，缺一觉就不许动/说… |
| `vision_print` | 只读 | — | **视觉打印**（主人令 2026-10-13「看到的东西都可以原样以代码打印并渲染成看到的样子」）：五段链 —— ①see 原生眼取帧（`tentacle/omni_core._screen_capture`：dxcam→mss→pyautogui，或直接喂图）②print 码… |
| `vlx_flow` | 只读 | — | **流式观察 + 两层记忆**（接自 om-ai-lab/VLX-Flow · 七步法第一步落 _upstream/VLX-Flow/）。上游当前是**纯文档仓**（Checkpoints: Coming soon）⇒ 按七步法「招一 纯逻辑直取」取它的**架构契约**、按「招三… |

> 表格里是**摘要**（超过 140 字截断）；完整原文见 [`data/capabilities.json`](../../data/capabilities.json) 的 `desc` 字段。

---

返回 [能力总表](../03-capabilities.md)
