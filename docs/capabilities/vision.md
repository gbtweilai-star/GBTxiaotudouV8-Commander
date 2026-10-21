# 视觉 · `vision`（5 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `vision` | 只读 | — | 视觉/图像识别入口（良性子集，需外部依赖时留待接入） |
| `vision_grounding` | 只读 | — | **视觉/定位通道契约**（主人令 2026-10-11「视觉必须达到 VLX-Flow 水平，脑-手同步**不能使用传统截图**看来在操作」）：把「看」分层钉死 —— **L1 结构层**（UIA 控件树 domain_index/domain_read/domain_act/… |
| `vision_loop` | **需授权** | — | **原生四觉闭环**（主人令 2026-10-09：「她的视觉每次都要跟手分开去使用传统的**瞎子操作**……把视觉这么使用给她**钉死在上面**」「我看她每次执行任务就是**瞎还没脑**」＋「还有耳，嘴」）。**眼·耳·嘴·手四觉 → 脑 → 手 → 验**，缺一觉就不许动/说… |
| `vision_print` | 只读 | — | **视觉打印**（主人令 2026-10-13「看到的东西都可以原样以代码打印并渲染成看到的样子」）：五段链 —— ①see 原生眼取帧（`tentacle/omni_core._screen_capture`：dxcam→mss→pyautogui，或直接喂图）②print 码… |
| `vlx_flow` | 只读 | — | **流式观察 + 两层记忆**（接自 om-ai-lab/VLX-Flow · 七步法第一步落 _upstream/VLX-Flow/）。上游当前是**纯文档仓**（Checkpoints: Coming soon）⇒ 按七步法「招一 纯逻辑直取」取它的**架构契约**、按「招三… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `vision`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：`privacy_read`
- **它做什么**：视觉/图像识别入口（良性子集，需外部依赖时留待接入）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_grounding`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：**视觉/定位通道契约**（主人令 2026-10-11「视觉必须达到 VLX-Flow 水平，脑-手同步**不能使用传统截图**看来在操作」）：把「看」分层钉死 —— **L1 结构层**（UIA 控件树 domain_index/domain_read/domain_act/domain_type · CDP DOM browser op=native · HTTP/API 读数）优先；**L2 接地层**（像素 + 模型 grounding，VLX-Flow 级）**仅兜底**（自绘 UI/Canvas/游戏/无 a11y 窗口）；**L3 回读层**（每次动手后用 L1 再读一次确认）。铁律：**先结构后像素**（用 L2 而无 L1 尝试记录 ⇒ 记违规 struct_first）· **动完没回读 ⇒ unverified** · 不编（读不到就如实报控件不在 a11y 树里）。op=channels/record/audit
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_grounding '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_loop`

- **域**：`vision`（视觉）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：**原生四觉闭环**（主人令 2026-10-09：「她的视觉每次都要跟手分开去使用传统的**瞎子操作**……把视觉这么使用给她**钉死在上面**」「我看她每次执行任务就是**瞎还没脑**」＋「还有耳，嘴」）。**眼·耳·嘴·手四觉 → 脑 → 手 → 验**，缺一觉就不许动/说：①眼 tentacle see（已实测可看）②耳 voice listen（壳已对 digital-human 放 media）③嘴 voice TTS（**没内容不说**）④手 tentacle click/type（门层**眼手同票**）· ⑤脑 System-One 契约（与云插件 c02 Laya 同一插槽）⑥验 动完再看一次比对，没变化**如实说没动成**。op=look/hear/speak/think/act/verify/loop/status。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_loop '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_print`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：**视觉打印**（主人令 2026-10-13「看到的东西都可以原样以代码打印并渲染成看到的样子」）：五段链 —— ①see 原生眼取帧（`tentacle/omni_core._screen_capture`：dxcam→mss→pyautogui，或直接喂图）②print 码落地（**码由她/调用方给**，本件**不编码**）③render 真 Chromium/Edge 渲（纪律同 `render_page.py`：只放行 file:/data:/blob:，其余**逐条记拦获**；pageerror / console / requestfailed 三条都记）④diff 与所见帧比（指纹尺子**只许一把**：`tentacle/vision_bus`）⑤judge 成档。**五个现算数**：aHash 汉明距离 · 块变化率 · 平均亮度差 · **变化像素占比** · **最大块平均差**（后两个是局部敏感项 —— 本件自测实测：只改一处文字颜色时整图 aHash 距离 = 0，靠这两个数才抓到，否则就是假绿）。档位 同款/接近/不像 写在 `_BANDS`（可复核可改）。抽不出代码块 ⇒ 如实报 no_code（不拿散文去渲）；`op=ask_model` 的看图回码靠**外部视觉模型**（她的底座是 Qwen2，**没有视觉塔**），缺依赖如实报 needs_dependency。每跑一次落 `store/vision_print/ledger.jsonl`（只追加）+ 框架审计一条。op=see/print/diff/loop/ask_model/status/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_print '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vlx_flow`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：**流式观察 + 两层记忆**（接自 om-ai-lab/VLX-Flow · 七步法第一步落 _upstream/VLX-Flow/）。上游当前是**纯文档仓**（Checkpoints: Coming soon）⇒ 按七步法「招一 纯逻辑直取」取它的**架构契约**、按「招三 手用我们自己的」语义那步留给自己的模型链。落点**长在现有眼上**：视觉缓存层复用 gbt_allinone/tentacle/vision_bus.py（snapshot / _ahash / diff_regions / stream_record / stream_replay）；语义记忆层**本件新增**，落 store/vision/semantic_memory.jsonl（**只追加**）。op=status/memory/timeline/recall/digest/remember（读面免门 · digest+remember 过 filesystem_write）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vlx_flow '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
