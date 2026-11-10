# 194 · 对话步骤实时可见（Codex 同款执行面）

> 2026-11-07 主人令：
> 「我要的是跟 Codex 一样的显示，而不是直接显示出来，这样我都不知道她每一个步骤，
> 我需要的是她开始执行任务每一步都要能看到她在干嘛执行到哪里每一个步骤都要精细显示出来。」

## 1. 结论

APP 对话面从「整包回执到了才一次刷出」改成「每跨一个阶段就长出一行」：

```
接收指令 · 已收到                      12ms
扫描能力位 · 4 个候选                  26.9ms
拆交办单 · 任务                        4.7ms
路由任务 · file/read                   18.8ms
原生取帧 · 1 帧                        96.2ms
交付回执 · 完成                        73ms
```

- 标题与耗时**都来自实测**：`time.perf_counter()` / 回执里的 `ms` 字段。
  没有实测就少一行，**不补假值**。
- 当前正在执行的那一步自动展开详情，历史步骤自动收起（Codex 同款读法）。
- 最终回执带回 `steps`，前端收尾时原样沿用 —— 不会拿粗粒度折行覆盖她真走过的过程。
- 普通 `/api/chat`（不带 `stream`）**行为一字不变**：仍是单个 JSON，
  旧调用方与 `tests/test_capability_router.py` 不受影响。

## 2. 协议

`POST /api/chat` 的请求体加 `"stream": true` ⇒ 响应 `text/event-stream; charset=utf-8`。

每条事件都是 `data: <json>`：

```json
{"type":"step","seq":4,"title":"路由任务 · file/read",
 "rows":[["判定","命中能力位，准备真执行"],["目标","README.md"]],
 "ms":18.8,"state":"done","at_ms":73}
```

```json
{"type":"final","result":{"ok":true,"via":"capability_router","text":"…",
 "steps":[ "本轮全部 step 原样回带" ]}}
```

- `seq`：从 1 连续递增；前端按它去重，乱序/重复不会画两次。
- `ms`：**这一步自己的耗时**；`null` 表示该阶段没有可测耗时。
- `at_ms`：相对本轮开始的累计时刻；`running` 行用它做活计时。
- `state`：`running` / `done`。`running` 先到，完成行随后到；
  若中途异常没有完成行，最终收尾会按 `at_ms` 落定，不留「永远转圈」。

服务端每 10 秒没有事件会发 `: ping` 心跳；客户端断线只中止这一轮。

## 3. 代码位置

| 位置 | 作用 |
|---|---|
| `tools/console-server.py` · `class _ChatSteps` | 逐步记录器：`seq` / `title` / `rows` / `ms` / `state` / `at_ms` |
| `tools/console-server.py` · `_chat(..., on_step=None)` | 每个阶段调用 `prog.step(...)`；没有回调时是空操作 |
| `tools/console-server.py` · `Handler._chat_stream` | SSE 通道 + 后台线程执行 `_chat` |
| `holo_pet_w3/console/app.js` · `beginTurn().step` | 到达一条追加一行，当前行展开、历史行收起 |
| `holo_pet_w3/console/app.js` · `_readChatStream` | 解析 `data:` 事件；没有 `final` 就如实报「流已断开」 |
| `holo_pet_w3/console/app.js` · `buildSteps` | 优先用 `j.steps`（实测路径），否则退回按回执折行 |

## 4. 覆盖的阶段

正常对话至少 5 步；命中能力位/触手/模型车道时会更多：

1. 接收指令
2. 扫描能力位（算子闸门）
3. 拆交办单
4. 读取附图 / 读取附件（有附件时）
5. 路由任务（`capability_router`）
6. 原生取帧（看屏时，带帧数与首帧路径）
7. 触手直达 / 方法直达（命中或拒绝都如实写）
8. 触手提示
9. 组装提示词
10. 免费车道 / 云端车道 / 本机 omni / 本机 energy_core（先 `running`，后完成）
11. 交付回执

## 5. 判据

```powershell
$env:PYTHONIOENCODING='utf-8'
.\pyembed\python.exe tests\test_chat_live_steps.py
.\pyembed\python.exe tools\codex-scripts\run-tests.py gbt_allinone.tests.test_console_chat_print
.\pyembed\python.exe tests\test_capability_router.py
```

`tests/test_chat_live_steps.py` 真的起一个 `ThreadingHTTPServer`，用假 `_chat`
验证：3 条 `step` 按序到达、只有 1 条 `final` 且在最后、`final.result.steps` 回带 3 条、
不带 `stream` 时仍是单个 JSON。

## 6. 边界（写死）

- **不许**把「没测到」写成 `0ms`；`ms=None` 就显示 `—`。
- **不许**在流断在半路时把已收到的片段当成完整回答；必须报「没有收到最终回执」。
- **不许**为了好看把 `running` 一律写成 `done`；异常路径按 `at_ms` 落定并保留标题。
- 这一步只改**可观测性**，不改任何执行权：写盘/授权仍走万能插的门。

## 7. 对话区文字可选中、可复制（2026-11-07）

- 症状：对话区里的文字框选不了，`Ctrl+C` 也复制不到。
- 根因：`holo_pet_w3/console/app.css` 的 `body { user-select: none }` —— 那是给标题栏/按钮防误拖用的，但会被所有子元素继承。
- 修法：**不删**全局那条，只在对话区开白名单：`#chat-messages` 及其子节点、`.msg` / `.msg-text` / `.meta`、
  `.msg-steps` / `.step-head` / `.step-title` / `.step-ms` / `.step-body` / `.step-row`、`.chat-composer textarea`
  一律 `user-select: text`；`.step-head` 仍保留 `cursor: pointer`（步骤行还要能点开）。
- 边界：`body.electron-app .app-titlebar` 带 `-webkit-app-region: drag`，**不许**放进白名单 ——
  放进去会把标题栏变成拖窗口、反而选不了字。

## 8. 判据（文字可选中）

- 对话区单击空白处 → `Ctrl+A` → `Ctrl+C`，剪贴板应得到回答正文（2026-11-07 实测得到 115 字）。
- 步骤行仍可点开/收起；标题栏仍可拖窗口。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
