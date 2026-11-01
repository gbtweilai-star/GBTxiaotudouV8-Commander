# 43 · 万能插·自动识别插口 + 自动配备插上（`omni_open`）

> 主人令 2026-11-01：「继续使用万能插打开万能插全部能力，以后只要使用她的全部能力必须全部自动打开，
> 而不是要我提醒」→ 随即修正：「万能插有自动识别插口，自动配备插上，**而不是固定的六插口**」

---

## 一、上一版错在哪（记下来，免得再犯）

第一版把插座写成**固定六类**（process / file / api / web / app / ai）——那是万能插的
「插座能源」分类，**不是墙上到底有几个洞**。主人要的是先看墙上有哪些洞（自动识别），
再把该插的都插上（自动配备）。写死清单等于又回到"要人提醒"。

## 二、现在的做法（四步，全自动）

```
① 识别   omni_plug.discover() 现读可插面：监听端口 / 本地模型口 / 本地DB / 命令行软件 / 窗口 / 串口 / 进程
② 配备   每个可插面 → 一根 Socket(kind, target) → Pulse().plug() 真插上
③ 落账   state/omni_open.json（哪类几根、插在哪、依据、扫描时刻、失败原因）
④ 自动   api._run_task_core_body 分派前 ensure()：快照 5 分钟内直接用，过期后台重扫（不阻塞调用）
```

**种类不是写死的**：`kinds` 由这一轮"发现了什么"决定 —— 端口→`port`、模型口→`ai`、
DB→`file`、命令行软件→`process`、窗口→`app`、串口→`serial`。发现不到就没有那一类。

## 三、本机实测（2026-11-01）

```
scan 25.1s · 插头 34 根 · 已插 34 · 未连上 5
kinds:  {"port": 24, "ai": 5, "file": 2, "process": 3}
发现面: {"监听端口": 24, "本地模型口": 5, "本地DB": 2, "命令行软件": 3, "窗口": 0, "串口": 0, "进程": 0}
```

前几根（`target` 已把 `0.0.0.0` 归一成 `127.0.0.1`，否则没法当客户端目标）：

```
port | 127.0.0.1:135    | ok=true
port | 127.0.0.1:445    | ok=true
ai   | http://127.0.0.1:8792 | ok=true    ← 她自己的指挥官引擎
ai   | http://127.0.0.1:11434| ok=false   ← ollama 没起（理由写在案）
```

**未连上 5 根**全是模型口（ollama / lmstudio / workbuddy / llamacpp / gpu-lane 都没起），
按口径登记但标 `ok=false` + `not_listening` —— **登记 ≠ 已连上**。

## 四、代价与边界

| 项 | 读数 / 口径 |
|---|---|
| 全量 discover | **25–26 s**（真实成本，不藏） |
| 调用侧代价 | `ensure()` 只读快照，**<1.5s 秒回**；过期才起后台线程重扫 |
| 快照寿命 | 5 分钟（TTL）；`op=scan` 可立刻同步重扫 |
| 插不进去的 | 记录在 `plug失败`（例如串口没有对应的能源插头类型 ⇒ "已识别、未插"） |
| 不会做的 | 不替你插危险插座、不擅自起进程（起进程仍走 `process_execute` 门） |

## 五、判据（会红的那种）

`tests/test_omni_open.py`：

- `kinds` 必须**来自发现**（⊆ port/ai/file/process/app/serial），且插头数 = 各类之和；
- 每根插头必须有 `surface + target`；`ok=false` 的必须有原因；
- `ensure()` 必须**<1.5s 秒回**（证明重扫没挂在主路上）；
- 删掉快照 → 随便调一个能力 → 快照必须被重新触发/补上（证明"自动"不是靠人记得）。

## 六、她怎么用

```
run_task("omni_open", {"op": "status"})   # 上一轮扫描的插口清单（秒回）
run_task("omni_open", {"op": "scan"})     # 现在立刻扫一遍（≈25s，同步）
run_task("omni_open", {"op": "ensure", "force": True})  # 触发后台重扫
```

正常她**不需要调** —— 钩子在唯一门里，每次调用前已经过了一遍。

---

## 七、增量对比：墙上的洞变了，必须立刻知道

插口是扫出来的，那它**变了**也得能被看见 —— 新增 / 拔掉 / 通断翻转，三种都记：

- 键 = `(kind, target)`：同名不同类不算同一个洞（`file:x` → `port:x` 算拔一根、插一根）；
- `removed` 或 `flipped` ⇒ **`alert: true`**（拔掉与断线是坏事）；
- 只 `added` 不报警（多插上一根是好事，但会记进 `history`）；
- `history` 只留最近 10 次有变化的扫描，逐次记 `{at, added, removed, flipped}`。

实测（连续两次扫描，环境没变）：

```json
{"counts": {"added": 0, "removed": 0, "flipped": 0}, "alert": false, "first_scan": false}
```

| op | 用途 |
|---|---|
| `diff` | 看最近一次扫描与上一轮的差集 + 是否报警 |
| `history` | 最近 10 次"有变化"的扫描摘要 |

判据在 `tests/test_omni_open_diff.py`（8 条，全离线，不烧 25 秒）：
第一次扫描不算漂移、拔掉/翻转必报、只新增不报、跨类改名算拔+插。
---

## 八、接进声带：插口掉了她会喊

增量对比不能只躺在 JSON 里。`selfscan.alerts()` 现在多一个 `sockets` 字段：

| 情形 | alerts 的反应 |
|---|---|
| 拔掉 / 通断翻转（`diff.alert=true`） | `needs_a_look=true` + `sockets` 里列出前 5 根掉的/翻的 |
| 只有新增 / 无变化 | `sockets.alert=false`，不虚报 |
| 首扫（`first_scan`） | 不算漂移，不报警 |
| 快照读不到 | 返回 `sockets.error`，**绝不把声带弄崩** |

实现：`selfscan._socket_alerts()` 只读 `state/omni_open.json` 的 `diff`（不重扫 —— 重扫 25s，
声带要秒回）。判据 `tests/test_alerts_sockets.py`（4 组、离线）：掉了必喊、没掉不虚报、
首扫不算、读不到不崩。

走门实测（当前快照：无变化）：

```json
{"quiet": true, "needs_a_look": false, "anomalies": 2,
 "sockets": {"alert": false, "counts": {"added": 0, "removed": 0, "flipped": 0}, "at": "2026-11-01T00:29:21"}}
```

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
