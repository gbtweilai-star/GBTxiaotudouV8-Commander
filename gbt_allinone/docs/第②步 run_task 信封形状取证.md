# 第②步 · `run_task` 信封形状取证

> 取证日期：2026-09-16
> 取证目的：第②步面板三条路径改走 `api.run_task` 后，**消费的返回值形状必须提前钉死**（取值不能猜）
> 取证方式：`.scratch/envelope_probe2.py` —— 隔离 store + 注入 Mock 共享单例；**不设 `GBT_OWNER_SESSION`**、不起 HTTP 服务、不 spawn 真 codex
> 前置：`api.py:648-681 _normalize_envelope` 读码结论 + 本文件实跑结论，二者必须一致

## 一、结论（四句话）

1. **`result` 是双层。** 能力原始载荷在 `gbt_result.result`（镜像位 `result.result` 同形）。面板若按 `r["result"]["thread"]` 取，会拿到 `None` —— **这就是「取值不能猜」的实证**。
2. **顶层恒有四字段**：`ok` / `kind` / `result` / `error`（`_normalize_envelope` 承诺），外加 `status` / `gbt_stamp` / `gbt_result`。
3. **`codex_thread_new(+非法effort)` 返回 `ok=True`，帧内无 `effort`，审计落 `codex_param_deprecated`** —— 路由层白名单（`api.py:51-68`）确认在拦，第④步的靶子已被证明可拦。
4. **`is_trusted()` 基线 = False** —— 本次取证未使用进程级全局兜底，身份结论干净。

## 二、信封完整形状

```
run_task(kind, payload) ->
{
  "ok":      bool,                    # 顶层判定，面板只读这个
  "kind":    str,                     # 回显 kind
  "status":  "ok" | "error",
  "error":   str | None,              # 失败原因（顶层）
  "gbt_stamp": { ...框架钢印... },
  "gbt_result": {                     # ① 盖章层
      "status": "ok",
      "kind":   kind,
      "result": { ...能力原始载荷... }  # ② 真载荷在这里
  },
  "result": {                         # 与 gbt_result 同形的镜像位
      "status": "ok",
      "kind":   kind,
      "result": { ...能力原始载荷... }
  }
}
```

> 实跑嵌套树（以 `codex_thread_new` 为例）见 `.scratch/envelope_probe2.out` 的「信封嵌套树」段。

## 三、三处入口的字段路径对照表

| 入口 | 调用 | 面板要取的字段 | 正确路径 | 易错写法（会拿到 None） |
|---|---|---|---|---|
| **P1** 建线程 | `api.run_task("codex_thread_new", p)` | thread id | `r["gbt_result"]["result"]["thread"]["id"]` | `r["result"]["thread"]["id"]` |
| **P1** 发一轮 | `api.run_task("codex_turn_send", p)` | turn id | `r["gbt_result"]["result"]["turn"]["id"]` | `r["result"]["turn"]["id"]` |
| **P3** 中断 | `api.run_task("codex_interrupt", p)` | 成功与否 | `r["ok"]`（载荷为空 `{}`，无字段可取） | 取 `r["result"]["ok"]` |
| **P2** 快捷动作 | `api.run_task(kind, request)` | 业务体 | `r["gbt_result"]["result"]`（代码里已有 `result.get("gbt_result", result)` 写法） | — |

**统一口诀**：判定看顶层 `ok` / `error`；载荷看 `gbt_result.result`。`r["result"]` 只是 `gbt_result` 的镜像位，**不是载荷**。

## 四、单次干净工件（实跑原文）

> `.scratch/envelope_probe2.py` 单次运行，账本先清空。`mock.recv` 恰好 4 行，与 4 次真实出网调用一一对应。

```
受信基线 is_trusted() = False （须为 False）
共享单例（Mock）= alive: True
### codex_status
   顶层键: ['error', 'gbt_result', 'gbt_stamp', 'kind', 'ok', 'result', 'status']
   gbt_result.status                          = 'ok'
   gbt_result.result.codex_path               = 'C:\\Users\\ADMIN\\AppData\\Local\\Programs\\OpenAI\\Codex\\bin\\codex
   gbt_result.result.connected                = True
### codex_tools
   顶层键: ['error', 'gbt_result', 'gbt_stamp', 'kind', 'ok', 'result', 'status']
   gbt_result.result.tools                    = ['gbt_capability', 'gbt_mirror', 'gbt_preflight', 'gbt_nexus', 'gbt_un
### codex_thread_new
   顶层键: ['error', 'gbt_result', 'gbt_stamp', 'kind', 'ok', 'result', 'status']
   gbt_result.result.thread.id                = 'thread-mirror-1'
   gbt_result.result.model                    = 'mock-v2-model'
### codex_turn_send
   顶层键: ['error', 'gbt_result', 'gbt_stamp', 'kind', 'ok', 'result', 'status']
   gbt_result.result.turn.id                  = 'turn-mirror-1'
### codex_interrupt
   顶层键: ['error', 'gbt_result', 'gbt_stamp', 'kind', 'ok', 'result', 'status']
   gbt_result.result                          = {}
### codex_thread_new(+非法effort)
   顶层键: ['error', 'gbt_result', 'gbt_stamp', 'kind', 'ok', 'result', 'status']
   gbt_result.result.thread.id                = 'thread-mirror-1'
   gbt_result: dict
   thread/start     effort存在=False raw=None     type=None  verdict=warn
   turn/start       effort存在=True  raw='high'   type=str   verdict=accept
   thread/start     effort存在=False raw=None     type=None  verdict=warn
   thread/start     effort存在=False raw=None     type=None  verdict=warn
   小计：mock.recv 4 行
```

逐条对照：

| # | 调用 | ok | 关键路径取值 |
|---|---|---|---|
| 1 | `codex_status` | True | gbt_result.result.codex_path = 'C:\\Users\\ADMIN\\AppData\\Local\\Programs\\Ope |
| 2 | `codex_tools` | True | gbt_result.result.tools = ['gbt_capability', 'gbt_mirror', 'gbt_preflight' |
| 3 | `codex_thread_new` | True | gbt_result.result.thread.id = 'thread-mirror-1' |
| 4 | `codex_turn_send` | True | gbt_result.result.turn.id = 'turn-mirror-1' |
| 5 | `codex_interrupt` | True | gbt_result.result = {} |
| 6 | `codex_thread_new` | True | gbt_result.result.thread.id = 'thread-mirror-1' |

## 五、`codex_thread_new` + 非法 `effort` 的完整证据链

这是第④步（去掉面板侧 `:685` 非法 `effort=`）的前置证明：**即使面板继续传，路由也不会放它出网**。

| 环节 | 证据 |
|---|---|
| 面板传入 | payload 含 `effort="high"`（类型 `str`） |
| 路由拦截 | `api.py:59-67` 命中 → 从白名单结果中剔除，不进入 `thread/start` 参数 |
| 出网帧 | `mock.recv` 行：`method=thread/start`、`received=False`（**帧内无 effort**） |
| 审计留痕 | `codex_param_deprecated`：`{kind, param, raw_value, type, note}` |
| 帧指纹 | `frame_bytes_hash` 与「不带 effort 的 thread/start」一致（同为 255 B 级载荷） |

## 六、读账本的一个陷阱（本轮踩过，如实记录）

`mock_v2_server.py` 的帧日志里，`mock.in` 与 `mock.recv` 有**同名字段不同语义**：

| 事件 | `received` 含义 | `type` 含义 |
|---|---|---|
| `mock.in` | **该帧存在**（恒 True） | `"request"` |
| `mock.recv` | **该帧带 effort** | effort 的 Python 类型 |

我第一版取证脚本误把 `mock.in.received` 读成 effort 存在，一度报出「`initialize` 都带 effort」的假象。定性：**我的读数 bug，不是 mock 的 bug**。只看 `mock.recv` 行才是 effort 语义。

## 七、证据文件

| 文件 | 内容 |
|---|---|
| `.scratch/envelope_probe2.py` | 信封取证探针（修正路径版） |
| `.scratch/envelope_probe2.out` | 单次干净运行原文 |
| `.scratch/envelope_probe.json` | 结构化结果 |
| `.scratch/envelope_probe.mock.jsonl` | Mock 账本（`mock.recv` 4 行） |
| `.scratch/envelope_probe.py` / `.out` | v1（字段路径写浅了一层的那版，留档对照） |

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
