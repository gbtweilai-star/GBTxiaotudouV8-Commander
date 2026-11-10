# 视觉 · `vision`（13 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `ocr` | 只读 | — | —（注册表：无必填） | `user_error` | **看图读字**（2026-11-04 主人令「看图片用原生视觉，别走附件系统」）：给一张**本地图片路径**，把图上的字读成**纯文本**交给脑子 —— 车道① Windows.Media.Ocr（系统内置 · 零安装 · 离线 · zh-Hans-CN）；车道② python… |
| `uia_tree` | 只读 | — | —（注册表：无必填） | `user_error` | **UIA 控件树**（Windows UI Automation · 原生结构通道 · 实测 1012ms / 6 窗口 / 14.5k 字）：读出原生窗口的结构化控件 —— 类型 + 名称 + 屏幕坐标（x/y/w/h），**可寻址、无视遮挡**，是「看」的 L1 结构层首选… |
| `vision` | 只读 | — | —（注册表：无必填） | `user_error` | 视觉/图像识别入口（良性子集，需外部依赖时留待接入） |
| `vision_arsenal` | 只读 | — | —（注册表：无必填） | `user_error` | **视觉作战区 · 唯一区块**（主人令 2026-11-04「把开源排名前十的视觉能力吞噬一遍，补齐缺失的视觉，全部整理到一个区块，让大脑执行层自动决策使用哪个视觉能力」）：19 个视觉能力位 / 4 组（读·懂·找·造），可用性**现算**不写死。开源基线（GitHub CV… |
| `vision_detect` | 只读 | — | —（注册表：无必填） | `user_error` | **目标检测**（ultralytics YOLO11n · ONNX 路线 · 不装 torch）：框出并分类画面里的**真实物体**（人/车/动物/电脑），回坐标 + 类别 + 置信度。对纯 UI 截图基本只认「一整块屏幕」—— 界面元素请用 region_scan 或 bo… |
| `vision_embed` | 只读 | — | —（注册表：无必填） | `user_error` | **语义相似度**（CLIP ViT-B/32 视觉编码器 · ONNX 352MB · 不装 torch）：判定两张图是不是「同一回事」—— 补 aHash 的盲区：主题切换/反色时 aHash 归零，它仍认得出（实测 0.94 vs 0.00）。op=similarity（i… |
| `vision_grounding` | 只读 | — | —（注册表：无必填） | `user_error` | **视觉/定位通道契约**（主人令 2026-10-11「视觉必须达到 VLX-Flow 水平，脑-手同步**不能使用传统截图**看来在操作」）：把「看」分层钉死 —— **L1 结构层**（UIA 控件树 domain_index/domain_read/domain_act/… |
| `vision_loop` | 只读 | — | —（注册表：无必填） | `user_error` | **原生四觉闭环**（主人令 2026-10-09：「她的视觉每次都要跟手分开去使用传统的**瞎子操作**……把视觉这么使用给她**钉死在上面**」「我看她每次执行任务就是**瞎还没脑**」＋「还有耳，嘴」）。**眼·耳·嘴·手四觉 → 脑 → 手 → 验**，缺一觉就不许动/说… |
| `vision_pose` | 只读 | — | —（注册表：无必填） | `user_error` | **姿态**（YOLO11n-pose · ONNX 11.3MB · 不装 torch）：人体 17 关键点 + 粗几何判定（举手 / 站坐 / 是否正对）；**不做动作语义识别**。铁律：关键点不可见就不判（实测 306~378ms/张，纯 CPU）。op=pose（imag… |
| `vision_print` | 只读 | — | —（注册表：无必填） | `user_error` | **视觉打印**（主人令 2026-10-13「看到的东西都可以原样以代码打印并渲染成看到的样子」）：五段链 —— ①see 原生眼取帧（`tentacle/omni_core._screen_capture`：dxcam→mss→pyautogui，或直接喂图）②print 码… |
| `vision_segment` | 只读 | — | —（注册表：无必填） | `user_error` | **通用分割**（slimsam-77 蒸馏版 SAM · 两段 ONNX 共 38MB · 不装 torch）：点一下或框一下，把目标**精确抠出来**（去背景、边界级 mask）。实测：encoder 3.2s（每图一次，带缓存）/ decoder 0.08~0.37s；框提… |
| `vision_track` | 只读 | — | —（注册表：无必填） | `user_error` | **目标跟踪**（贪心 IoU 关联，纯 Python 零依赖 · 不装 supervision）：跨帧认住同一个目标 —— 「还是它吗」。核心只是上一帧框 ↔ 这一帧框的配对（取最大值问题）。op=update（boxes → 关联并回 id）· track（frames →… |
| `vlx_flow` | 只读 | — | —（注册表：无必填） | `user_error` | **流式观察 + 两层记忆**（接自 om-ai-lab/VLX-Flow · 七步法第一步落 _upstream/VLX-Flow/）。上游当前是**纯文档仓**（Checkpoints: Coming soon）⇒ 按七步法「招一 纯逻辑直取」取它的**架构契约**、按「招三… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `ocr`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**看图读字**（2026-11-04 主人令「看图片用原生视觉，别走附件系统」）：给一张**本地图片路径**，把图上的字读成**纯文本**交给脑子 —— 车道① Windows.Media.Ocr（系统内置 · 零安装 · 离线 · zh-Hans-CN）；车道② python winrt（装了 winrt-* 才走）；车道③ pytesseract（装了 tesseract.exe 才走）。铁律：**只吃本地路径**（URL 会先落本地再读）· **只回文本**（图片本身永不进上下文 ⇒ 不产生远程 URL ⇒ 不会 HTTP 471 ⇒ 不吃图片 token）· 读不到就如实报「没读到字」，**绝不编字**。常用说法（人这么问就命得中）：读字 / 识别文字 / OCR / 图里写的什么 / 提取文本 / 截图转文字。参数 image（本地路径）。op=read/lanes
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap ocr '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `uia_tree`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**UIA 控件树**（Windows UI Automation · 原生结构通道 · 实测 1012ms / 6 窗口 / 14.5k 字）：读出原生窗口的结构化控件 —— 类型 + 名称 + 屏幕坐标（x/y/w/h），**可寻址、无视遮挡**，是「看」的 L1 结构层首选（先结构后像素）。真实实现是触手方法 `omni_domain.domain_index`（mixin，不是独立模块）。参数：max_windows（默认 30）· control_depth（默认 3 —— 实测 2 漏控件、4 太慢）。铁律：读不到就如实报「不在 a11y 树里」，不编控件。常用说法：控件 / 控件树 / 窗口列表 / 有哪些窗口 / 输入框在哪 / 菜单在哪 / 元素在哪 / 原生 / 软件界面。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap uia_tree '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：视觉/图像识别入口（良性子集，需外部依赖时留待接入）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_arsenal`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**视觉作战区 · 唯一区块**（主人令 2026-11-04「把开源排名前十的视觉能力吞噬一遍，补齐缺失的视觉，全部整理到一个区块，让大脑执行层自动决策使用哪个视觉能力」）：19 个视觉能力位 / 4 组（读·懂·找·造），可用性**现算**不写死。开源基线（GitHub CV 榜 2026-09-27，已 devour 吞过）：transformers 166.7k / opencv 91.0k / stable-diffusion 73.5k / ultralytics 62.0k / yolov5 58.1k / segment-anything 54.9k / supervision 51.1k / timm 37.2k / detectron2 34.7k / diffusers 34.6k。op=decide（给意图→选一位，主选必为真能跑的位，缺依赖进 missing 如实报）· status（全量体检）· matrix（四组矩阵）· template_match（图标定位·opencv·回坐标不回图·带方差守卫）· region_scan（可点区块扫描·opencv 轮廓）。铁律：主选必须真能跑 · 图不进上下文 · 降级必须自曝。常用说法（人这么问就命得中）：视觉能力 / 视觉作战区 / 视觉矩阵 / 用哪个视觉 / 视觉体检 / 视觉选型。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_arsenal '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_detect`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**目标检测**（ultralytics YOLO11n · ONNX 路线 · 不装 torch）：框出并分类画面里的**真实物体**（人/车/动物/电脑），回坐标 + 类别 + 置信度。对纯 UI 截图基本只认「一整块屏幕」—— 界面元素请用 region_scan 或 body_eye，别拿它找按钮。op=detect（image + conf/iou/max_det/imgsz/only）· status（模型就绪度）。铁律：只吃本地路径 · 图不进上下文 · 没检出如实报 0 个，不编框。常用说法：检测 / 找出来 / 有哪些物体 / 框出来 / 几个人 / 识别出 / 目标 / 照片里 / 画面里有什么。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_detect '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_embed`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**语义相似度**（CLIP ViT-B/32 视觉编码器 · ONNX 352MB · 不装 torch）：判定两张图是不是「同一回事」—— 补 aHash 的盲区：主题切换/反色时 aHash 归零，它仍认得出（实测 0.94 vs 0.00）。op=similarity（image_a + image_b → 分数）· embed（image → 512 维向量）· nearest（base + candidates 列表 → 排序）· status（模型就绪度）。铁律：只吃本地路径 · 只回数值或向量，图片本身不进上下文。常用说法：相似 / 像不像 / 同一个 / 是不是同一张 / 比对 / 指纹 / 多像 / 差多少 / 相似度。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_embed '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_grounding`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**视觉/定位通道契约**（主人令 2026-10-11「视觉必须达到 VLX-Flow 水平，脑-手同步**不能使用传统截图**看来在操作」）：把「看」分层钉死 —— **L1 结构层**（UIA 控件树 domain_index/domain_read/domain_act/domain_type · CDP DOM browser op=native · HTTP/API 读数）优先；**L2 接地层**（像素 + 模型 grounding，VLX-Flow 级）**仅兜底**（自绘 UI/Canvas/游戏/无 a11y 窗口）；**L3 回读层**（每次动手后用 L1 再读一次确认）。铁律：**先结构后像素**（用 L2 而无 L1 尝试记录 ⇒ 记违规 struct_first）· **动完没回读 ⇒ unverified** · 不编（读不到就如实报控件不在 a11y 树里）。op=channels/record/audit
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_grounding '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_loop`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**原生四觉闭环**（主人令 2026-10-09：「她的视觉每次都要跟手分开去使用传统的**瞎子操作**……把视觉这么使用给她**钉死在上面**」「我看她每次执行任务就是**瞎还没脑**」＋「还有耳，嘴」）。**眼·耳·嘴·手四觉 → 脑 → 手 → 验**，缺一觉就不许动/说：①眼 tentacle see（已实测可看）②耳 voice listen（壳已对 digital-human 放 media）③嘴 voice TTS（**没内容不说**）④手 tentacle click/type（门层**眼手同票**）· ⑤脑 System-One 契约（与云插件 c02 Laya 同一插槽）⑥验 动完再看一次比对，没变化**如实说没动成**。op=look/hear/speak/think/act/verify/loop/status。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_loop '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_pose`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**姿态**（YOLO11n-pose · ONNX 11.3MB · 不装 torch）：人体 17 关键点 + 粗几何判定（举手 / 站坐 / 是否正对）；**不做动作语义识别**。铁律：关键点不可见就不判（实测 306~378ms/张，纯 CPU）。op=pose（image + conf/kp_vis/max_people）· status。常用说法：姿态 / 姿势 / 关键点 / 手势 / 骨架 / 举手 / 举着 / 站姿 / 坐姿 / 什么姿势 / 怎么站的 / 在做什么动作。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_pose '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_print`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**视觉打印**（主人令 2026-10-13「看到的东西都可以原样以代码打印并渲染成看到的样子」）：五段链 —— ①see 原生眼取帧（`tentacle/omni_core._screen_capture`：dxcam→mss→pyautogui，或直接喂图）②print 码落地（**码由她/调用方给**，本件**不编码**）③render 真 Chromium/Edge 渲（纪律同 `render_page.py`：只放行 file:/data:/blob:，其余**逐条记拦获**；pageerror / console / requestfailed 三条都记）④diff 与所见帧比（指纹尺子**只许一把**：`tentacle/vision_bus`）⑤judge 成档。**五个现算数**：aHash 汉明距离 · 块变化率 · 平均亮度差 · **变化像素占比** · **最大块平均差**（后两个是局部敏感项 —— 本件自测实测：只改一处文字颜色时整图 aHash 距离 = 0，靠这两个数才抓到，否则就是假绿）。档位 同款/接近/不像 写在 `_BANDS`（可复核可改）。抽不出代码块 ⇒ 如实报 no_code（不拿散文去渲）；`op=ask_model` 的看图回码靠**外部视觉模型**（她的底座是 Qwen2，**没有视觉塔**），缺依赖如实报 needs_dependency。每跑一次落 `store/vision_print/ledger.jsonl`（只追加）+ 框架审计一条。op=see/print/diff/loop/ask_model/status/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_print '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_segment`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**通用分割**（slimsam-77 蒸馏版 SAM · 两段 ONNX 共 38MB · 不装 torch）：点一下或框一下，把目标**精确抠出来**（去背景、边界级 mask）。实测：encoder 3.2s（每图一次，带缓存）/ decoder 0.08~0.37s；框提示 iou 0.913 覆盖 31.3%（整人）· 点提示 iou 0.688 覆盖 1.1%（常只抠局部）。op=segment（image + point=[x,y] 或 box=[x1,y1,x2,y2] + save）· status。产物落本地文件只回路径。常用说法：抠图 / 分割 / 去背景 / 边界 / mask / 轮廓精确 / 抠出来。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_segment '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vision_track`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**目标跟踪**（贪心 IoU 关联，纯 Python 零依赖 · 不装 supervision）：跨帧认住同一个目标 —— 「还是它吗」。核心只是上一帧框 ↔ 这一帧框的配对（取最大值问题）。op=update（boxes → 关联并回 id）· track（frames → 自动检测+关联）· reset · status。常用说法：跟踪 / 追踪 / 跟随 / 连续 / 视频里 / 还是它。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vision_track '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `vlx_flow`

- **域**：`vision`（视觉）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**流式观察 + 两层记忆**（接自 om-ai-lab/VLX-Flow · 七步法第一步落 _upstream/VLX-Flow/）。上游当前是**纯文档仓**（Checkpoints: Coming soon）⇒ 按七步法「招一 纯逻辑直取」取它的**架构契约**、按「招三 手用我们自己的」语义那步留给自己的模型链。落点**长在现有眼上**：视觉缓存层复用 gbt_allinone/tentacle/vision_bus.py（snapshot / _ahash / diff_regions / stream_record / stream_replay）；语义记忆层**本件新增**，落 store/vision/semantic_memory.jsonl（**只追加**）。op=status/memory/timeline/recall/digest/remember（读面免门 · digest+remember 过 filesystem_write）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap vlx_flow '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
