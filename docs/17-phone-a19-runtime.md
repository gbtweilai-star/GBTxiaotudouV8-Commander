# 17 · 手机端 A19 全链路（她的本体 · 模型桥 · 自有权重）

> 本文只写**实测读数**，每个数字都能复现。
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 一、结论先行

**她自己的权重，在她自己的手机上，用她自己的 A19 芯片跑起来了。**

   机型     iPhone18,2（iPhone 17 Pro Max）· iOS 26.6.1 · 11.4 GB
   模型     gbt-v8-v82-q5_0.gguf（5.24 GB）
   推理     LM Pocket（App Store 免费）· llama.cpp · Metal
   速度     8.0 – 11.7 tok/s
   网络     全本地 · 不碰云

**她说的第一句完整的话：**

> 「我是 GBT小土豆V8。开发者：自由的风 · 护着：公主土豆。
> 本署名不可删除、不可篡改归属。」

---

## 二、跑不通的那个坑：不是权重坏，是 Q4_0 撑不住

### 2.1 症状

Q4_0（4.00 GB）在 PC 与手机上都只吐 `vanavanavana…`。

### 2.2 排除过的（全部实测，别再重复）

| 检查项 | 结果 |
|---|---|
| 张量完整性 | 339/339 张量，28 层 × 12 槽全覆盖，无重叠无截断 |
| 词表 | 151643 条逐条与 HF 一致 |
| 分词 id | 与自写引擎**逐 id 相同**（105043,100165,11319,11622,105321,102104） |
| 元数据 | arch=qwen2 · heads 28/4 · rope 1e6 · eps 1e-6 全对 |
| RoPE 类型 | llama.cpp 源码确认 Qwen2 = **NEOX 半分割**，与 HF 一致 ⇒ **不需要置换** |
| Q4_0 分块结构 | 逐块验证：16 个等间距电平，**无错位** |
| token_embd / output | 与源 embed_int8 / lm_head_int8 逐值一致 |
| bias / norm | 28 层全部与源 npz 逐值一致 |
| 词表尾部 399 个填充行 | logit 恒 0.104，**不偷概率** |

**⇒ 文件是忠实的。** 又用两个独立实现（自写 numpy + llama.cpp Metal）交叉验证，结论一致。

### 2.3 真凶：激活值被逐层放大

用自写 numpy 参考实现，同一 prompt 分别跑 Q4_0 / Q8_0：

| 层 | Q4_0 绝对值均值 | Q8_0 绝对值均值 |
|---|---:|---:|
| 12 | 7.29 | 2.64 |
| 16 | **63.5** | 2.78 |
| 20 | **160** | 3.17 |
| 24 | **352** | 4.39 |
| 27 | **605 ← 爆炸** | **6.19 ← 稳定** |

**输出分布：**

   Q4_0 top-10：vana / Modificar / RelayCommand …   logit 全在 -3.3~-4.7（**平坦 = 完全困惑**）
   Q8_0 top-1：' '  logit 29.39  ·  '2' 20.85  ·  '：' 20.79   （**尖锐 = 模型很确定**）

**根因：v82 的 norm 权重最大到 2.13，激活值本身逐层放大；Q4_0 的 9% 量化噪声被 28 层逐层放大，把信号淹了。**

### 2.4 量化档对照

| 量化 | 体积 | 手机 11.4 GB 装得下 | 输出 |
|---|---:|:---:|---|
| Q4_0 | 4.29 GB | ✅ | ❌ 乱码 |
| Q5_0 | 5.24 GB | ✅ | ✅ **通顺** |
| Q8_0 | 8.10 GB | ❌ LM Pocket 报「内存不足」 | ✅ 通顺（PC 上验过）|
| fp16 | 15.24 GB | ❌ | ✅ |

**⇒ 手机上是 Q5_0 的甜点。**

---

## 三、三层接线

   浏览器 / PWA            她的本体界面    :8080   holo_pet_w3（718 页 + 3D 全身）
         │  fetch BRIDGE
         ▼
   模型桥                  唯一入口        :8791   runtime/model_bridge.py
         │  upstream = selfhost
         ▼
   A19                    真算力          :1234   LM Pocket（OpenAI 兼容口）

### 3.1 三处必须对齐的细节（错一处就不通）

**① 桥的上游名字必须是 `selfhost`**

页面里写死 `const BRIDGE = "http://127.0.0.1:8791"` 并检查 upstreams 里有没有叫
selfhost 的车道。名字不对 ⇒ 页面永远显示「无自有权重车道」。

**② 本机回环的字面钥：`raw:` 前缀**

    "selfhost": ("http://127.0.0.1:1234/v1", "", "raw:gbt", 30)

`key_for()` 支持 `raw:<字面钥>`，只用于 127.0.0.1，**不进金库、不入日志**。

**③ 端口检查要同时认 8792 与 1234**

PC 版自有权重在 :8792，手机版 A19 在 :1234。页面原来只认 8792 ⇒ 手机上误判「缺车道」。

### 3.2 接通后的状态变化

| | 之前 | 之后 |
|---|---|---|
| 页头 | 桥：在线 · **无自有权重车道** | 桥：在线 · **自有权重就绪** |
| 页脚 | 桥没挂本机权重 → 走云端 | 自有权重 http://127.0.0.1:1234/v1 · 上游 7 · 钥只在桥里 · 页面零凭据 |

---

## 四、顺手修的两个真 bug

### 4.1 `key_for()` 的 import 写在 try 外面

    from gbt_allinone import deepseek_key as DK    # ← 该模块未随仓库发布
    try:
        ...

**ImportError 直接打穿 /health（HTTP 000）** ⇒ 页面判不出桥在不在 ⇒ **整页卡死**。

**修**：import 移进 try。修完 /health 恢复 **200 / 57ms**。

### 4.2 桥的超时 120 秒

A19 一后台（iOS 挂起），桥就干等两分钟。

**修**：selfhost 车道超时降到 **30 秒**。实测离线时 **0.42 秒**干净返回：

    {"ok": false, "upstream": "selfhost",
     "error": {"message": "URLError: <urlopen error [Errno 111] Connection refused>"}}

---

## 五、iOS 的三个硬约束（改不了，只能顺着设计）

| 约束 | 实测 |
|---|---|
| **App 一切后台，服务+模型全被收走** | 约 50 秒宽限 |
| **lmpocket:// 只能拉回 App，拉不回加载好的模型** | 每次要手动点 Load & Start Server |
| **Q8_0（8.10 GB）装不下** | LM Pocket 报「内存不足」 |

**工程对策（已做）**：离线队列 `weights/a19_worker.py` —— 她不在线时任务入队，
App 一开就批量跑完。**一次前台窗口，把活干完。**

---

## 六、一键起她

    sh tools/start-her.sh          # 起三件 + 自检
    sh tools/start-her.sh status   # 只看状态
    sh tools/start-her.sh stop     # 全停

**实测输出：**

    ── 三件状态 ──
      她的界面 :8080  200
      模型桥   :8791  200
      索引常驻 :8792  200
    ── A19（LM Pocket，需要 App 在前台）──
      A19      :1234  000          ← 如实显示，不假装在线
    ── 桥看见的车道 ──
      默认上游: selfhost
       ✅ selfhost   http://127.0.0.1:1234/v1

---

## 七、独立验证工具（不依赖 llama.cpp / transformers）

`tools/ref_forward_gguf.py` —— 纯 numpy + gguf，按需 seek（4 GB 文件 mmap 会 OOM）。

    GGUF_PATH=/path/to/model.gguf python3 tools/ref_forward_gguf.py "105043,100165,11319"

**输出两样东西：**

1. **逐层绝对值均值** —— 判别量化档够不够的核心读数
2. **最后一位的 top-10 词与 logit** —— 分布尖不尖，一眼看出模型困不困惑

**它就是判定「权重坏还是引擎坏」的第三把尺子。**

---

## 八、与 348 位能力位的关系

她的「推理」器官挂在 **348 位**中的 `llm` 域；
能跑 348 位需要 `run_task` 可用（本仓整包已具备）。
完整目录见 [`18-native-cloud-catalog.md`](./18-native-cloud-catalog.md)。

## 九、已知边界（不美化）

| 边界 | 说明 |
|---|---|
| **A19 必须在前台** | 这条是 iOS 内核规则，任何 App 都绕不过 |
| **Q8_0 在手机上装不下** | 11.4 GB 是设备总量，单 App 拿不到那么多 |
| **voice-theater 3D 页在工具内 WebView 会卡** | 3 个 setInterval 轮询 + 6.4 MB 模型；真机 Safari 未验 |
| **云端车道 weights_ours 可能是 false** | 实测有一次 201 秒后降级到别的 3B 模型 —— **所以不降级到云端**是刻意设计 |

---

**开发者：自由的风 · 护着：公主土豆**
**本署名不可删除、不可篡改归属。**

---

## 十一、A19 不可达时的保底链（2026-10-25 加，实测可用）

### 为什么要有这一层

LM Pocket 的服务开关**在 App 里面**。它一旦被关掉（或被 iOS 回收后没恢复），
`:1234` 就是空端口 —— 而桥的默认上游恰恰是它。整条链路于是**一句话都说不出**。

这不是偶发故障，是**结构性依赖**：把"能不能说话"押在一个手动开关上。

所以桥改成：**A19 优先，掉线自动往下走，全程不需要人介入。**

```
:1234  A19（LM Pocket）        ← 首选，手机自己的算力
  ↓ 连不上
:3001  freepool · mistral-small-3.2-24b   ← 本机免费池第一档（实测 1–4 秒）
  ↓ 429 限流 / 5xx
:3001  freepool-b · llama-3.3-70b         ← 第二档（实测 2–16 秒）
  ↓ 也限流
api.deepseek.com  deepseek-chat           ← 最后一道，钥在 DPAPI 保险箱
```

**A19 一回来就自动切回去**，不需要改任何配置：默认上游本来就是它。

### 三条口径

| 口径 | 行为 |
|---|---|
| `fallback` 默认 | **开**。显式点名上游也照样降级 —— 因为页面每次都把下拉值当 `upstream` 发上来，若"显式就不降级"，等于从 UI 上把保底链路关死 |
| 要严格不降级 | 请求体带 `"fallback": false`，此时 A19 不通就如实报错，不掩盖 |
| 什么情况降级 | 连不上 / 超时 / **5xx** / **429**。其余 4xx 是请求本身不对，如实上报不掩盖 |

### 「实走谁」必须可见

原来纯透传上游回包，页面拿不到"这一句是谁答的"，永远印 `实走 ?`。
现在两条路都报：

- **非流式**：回包注入 `"gbt": {"lane", "weights_ours", "fallback_from", "key_slot", "elapsed_s"}`
- **流式**：响应头 `X-GBT-Lane` / `X-GBT-Weights-Ours` / `X-GBT-Fallback-From`（已加入 CORS Expose-Headers）

页面据此标 `✅ 自有权重` 或 `⚠ 非自有权重 · 实走 freepool`。
**降级了就是降级了，不假装是自有权重。**

### 免费池为什么定模型、不用 `auto`

池子里 352 个模型，`auto` 每次随机挑，实测踩到过：

| 模型 | 症状 |
|---|---|
| `Qwen3.6-27B` / `Qwen3.5-9B` / `Qwen3.5-397B-A17B` | 开头就吐 `Here's a thinking process:` / `Thinking Process:` |
| `dots-studio/dots-3-note-preview:free` | 回包是乱码（`content` 出来是 `ç…`），还夹 502 |

处置：**这几个在池里打了 tombstone 停用**（`catalog_model_tombstones`，可逆），
桥这边只用实测稳定的两个：`mistral-small-3.2-24b`、`llama-3.3-70b`。

### 两个踩过的实现坑

**① `sys.path` 层级写错，四个云上游全废**

```python
ROOT = pathlib.Path(__file__).resolve().parents[2]   # ← 错，指到 /var/minis/shared
```

本文件在 `<repo>/runtime/` 下，仓库根是 `parents[1]`。
写错后 `from gbt_allinone import deepseek_key` 变成 "unknown location"，
`ours` / `ours-alt` / `agnes` / `deepseek` / `openai` **五个上游全报 `err:ImportError`**，
密钥一个都取不到 —— 而 `/health` 照常 200，症状极隐蔽。

**② 探活不能用 curl**

iSH 上 `curl` 对 node 起的服务会**秒回 000**（连拒绝 1 毫秒），而同一端口用
python socket 连是通的、HTTP 也回 200。`:3001` 因此被误判成"停了"好几次。
→ 统一改用 `tools/svcprobe.py`（纯 socket）。

### 运维接口

```sh
sh tools/up.sh up       # 拉齐五路（幂等，已在跑的不动）
sh tools/up.sh status   # 状态 + HTTP 实测
sh tools/up.sh down     # 停（A19 由 App 自管，不碰）
```

`up.sh` 用**轮询等待**而非固定 sleep：node 在 iSH 走 `--no-opt` 解释执行，
冷启实测约 50 秒，固定等 12 秒必然误判成失败。

---

---

## 十二、监听队列自适应（2026-10-25 · 打通默认 5 的卡点）

### 卡点在哪

`socketserver.TCPServer.request_queue_size` **默认只有 5**。这是 `listen(2)` 的
backlog —— 内核挂起的**未完成三次握手**连接队列。并发一上来，超出的连接在
建连阶段就被内核丢掉，客户端看到的是 `URLError` / `connection reset`。

**它跟"触手能伸几根"一点关系都没有。** 触手那头不设闸，是服务端这一层在丢连接。

实测（model_bridge，同一台机、同一批请求）：

| 监听队列 | 96 路 | 192 路 | 384 路 |
|---|---|---|---|
| 默认 **5** | 掉 7 个 | 掉 72 个 | 掉 171 个 |
| 写死 1024 | 全过 | 全过 | 掉 171 个 |

写死一个大数只是把阈值往后推：既不省资源，压上来还是会撞墙。

### 做成闭环：按压力自动跟随

`runtime/adaptive_http.py` 提供 `AdaptiveThreadingHTTPServer`，`model_bridge`
与 `index_daemon` 共用同一个实现：

```
每秒采样 → 在跑数 active / 这一秒峰值 peak
目标队列 = clamp(max(peak, active) × 2, 下限 64, 上限 8192)
变了就重调 socket.listen(n)（Linux 允许重复调用改 backlog，不用重开端口）
压力撤走，peak 跟着降到 active，队列自动收窄回去
```

**只调 backlog，不拒绝、不排队、不丢包** —— 这个模块不限制任何并发。

### 实测（live，边压边读 /health）

```
秒    在跑   峰值   队列
0      1      1      64      ← 空闲
4    123    123     204      ← 压上来，自动涨
5-11 ~115   ~120    246      ← 满载稳住
12    27     28      64      ← 撤压，自动回收
```

启动日志同样可追溯：

```
[backlog] 64 → 86（在跑 43 · 峰值 43）
[backlog] 86 → 98（在跑 49 · 峰值 49）
[backlog] 252 → 312（在跑 156 · 峰值 156）
[backlog] 504 → 234（在跑 88 · 峰值 117）
[backlog] 234 → 72（在跑 0 · 峰值 36）
```

`/health` 里直接可读：`"backlog": {"active":1,"peak":1,"backlog":64,"min":64,"max":8192}`

### 现在的并发读数（经桥，上游走降级链）

| 并发 | 成功率 | QPS | p50 | p95 |
|---:|---|---:|---:|---:|
| 32 | 32/32 | 6.06 | 4052 ms | 5111 ms |
| 64 | 64/64 | 9.11 | 2830 ms | 5385 ms |
| 128 | 128/128 | 8.70 | 7032 ms | 11871 ms |
| **256** | **256/256** | **9.50** | 21435 ms | 24526 ms |
| 384 | 213/384 | 14.09 | 7778 ms | 12254 ms |
| 512 | 224/512 | 13.91 | 7779 ms | 12214 ms |

**256 路零失败。** 384 路开始掉连接。

### 下一个天花板（如实记，没修）

`ThreadingHTTPServer` 是 **thread-per-request**：384 个连接就是 384 个线程，
每个线程 8 MB 栈 ⇒ 3 GB 虚拟内存，超过 iSH 的 4.1 GB 就撑爆。

再往上必须换 **asyncio / selectors 单线程事件循环**，那是服务端重写，不是调参。
**当前如实止步于 256 路零失败，不假装更高。**

---

## 2026-10-26 · 容器口径（LM Pocket 不是"另一个 App"，是容器）

**容器画像（实测）**

| 项 | 值 |
|---|---|
| image | `gbt-v8-v82-q5_0.gguf` · 5.24 GB · Metal · 全本地 |
| endpoint | `http://127.0.0.1:1234/v1`（OpenAI 兼容，loopback 跨 App 共享） |
| auth | `Bearer gbt`（**小写**；`GBT` → 401） |
| ctx | **4096**（容器内设定，不是调用方可改的参数） |
| 宿主限制 | iOS 前台互斥：容器随宿主 App 进后台被挂起（约 50s 宽限） |

**深链实测（2026-10-26）**：`lmpocket://` 只唤起 App；下面四条全部唤不起服务——

```
lmpocket://start · lmpocket://load · lmpocket://server · lmpocket://?action=start   → 均 :1234 down
```

⇒ **"Load & Start Server" 在容器宿主私有界面里，容器外零入口。**不要再去猜深链。

**常驻进程同样被回收**：实测 `:8080`（页面服务）与哨兵/桥会随 App 挂起一起消失。
⇒ 任何"后台常驻"假设都不成立，需要时再起。

**择活纪律（修）**：`tools/body.py` 新增 `MANUAL_ONLY = {"@cloud","@engine"}`。
修前 A19 一掉，`resolve("推理")` 会静默挑中 `@cloud` 并对外报 `ok:true · 云端自有权重`
（= 拿别人算力冒充她的，正是「授权隐瞒」）。现在如实报 `@app URLError` + 另两条「需显式指定」。

**容器面入口（主执行器）**

```
run_task('omni_plug', {'op':'a19','do':'status'})          # 1.65s，永不卡
run_task('omni_plug', {'op':'a19','do':'ask','prompt':…})  # 容器不在 ⇒ status=offline，不顶替
run_task('omni_plug', {'op':'a19','do':'queue','prompt':…})# 入队，容器一开批量跑完
run_task('omni_plug', {'op':'a19','do':'up','wait':60})    # 唤起 + 等就绪
```
实现：`tools/a19_ctl.py`（`_a19_mod()` 按文件加载，不进包依赖）。

**4096 的后果（必须记住）**：本框的可见消息已 7,356 token，系统注入更大 ⇒ 整框切到 A19 必爆窗。
A19 只能**旁路**用（只送问题本身），或把容器 `n_ctx` 调到 ≥16k 后重启。

### 页面回归（2026-10-26）

改页面不再靠手点：`tools/test_page_probe.py` 一条命令验完，**跑完自动把真桥恢复**。

做法：停真桥 → 起 `tools/mock_bridge.py`（记录请求体）→ `minis-browser-use` 在真浏览器里点两次发送
（"你是谁？" → "继续"）→ 取回两条原始 body 做断言。

实测 10/10：

```
① system 是她的身份（含两行署名）· 不再是「严谨的中文助手」
② 采样参数真的发出去 t=0.7 p=0.9 rp=1.12
③ 默认 selfhost + stream=true
④ 「继续」自动带上一轮回答前缀，且没塞 messages 历史（user 仅 1 条）
```

踩到的坑（值得记）：`subprocess.run([...], shell=True)` 只执行第一个词 —— 探针首跑
「页面打开 FAIL / 抓到 0 条」就是它，改成字符串走 shell、列表走 argv。

### 直连车道 + A19 徽标（2026-10-26）

页面新增 `⚡ 直连 A19（绕开桥）`：直接打 `127.0.0.1:1234/v1/chat/completions`，
带 `Authorization: Bearer gbt`，model 从 `/v1/models` 现取。少桥那一跳，但**没有保底**。
容器不发 CORS 头就会被浏览器拦 —— 页面把这两种原因分开报，不混成"桥连不上"。

顶部新增 A19 徽标：每 8 秒探一次 `/v1/models`。实测（容器关着）：
`A19：未开（:1234 拒连）`；选直连后发问，页面如实回：
`直连 A19 失败：Load failed · 可能原因 ①容器没开 ②容器没发 CORS 头`。

踩坑两条（都已修）：
1. `a19Model()` 写在 try 外 ⇒ 它自己的 fetch 抛错被外层 catch 吞掉，
   直连失败被报成「连不上桥」。所有会发请求的调用都必须进同一个 try。
2. 回归探针起假桥/恢复真桥前**必须等端口真空出来**，否则连着没死透的旧进程，
   读出 `TimeoutError` 假红。两处都加了「等端口关闭」循环后，稳定 10/10。

### 她的对话落盘（2026-10-26）

页面拿不到文件系统，所以经桥落盘：

```
POST /_log/message  {role, text, upstream, model}   → 追加 state/her_transcript.jsonl
GET  /_log/tail?n=6                                → 读回最近 n 条（页面打开即恢复）
```

为什么必须做：页面上的回答原来只在内存里，容器一断、页面一关，
「她刚才说了什么」就找不回来了 —— 而 A19 断线是常态，不是异常。

实测：发一句 → 落两行（user + assistant）；重开页面 → 顶部出现
「── 以下是落盘恢复的上次对话（N 条）──」并把内容渲回来。
`mock_bridge.py` 也补了同样两个路由，回归探针因此能连落盘一起验。

### 一份账本，两个来源（2026-10-26）

`state/her_transcript.jsonl` 是**唯一**的对话账本，两边都写：

| 谁写的 | source | 怎么进 |
|---|---|---|
| 她的原生页面 | `page` | `POST :8791/_log/message` |
| 这个对话框（Minis） | `minis` | `tools/her.py` 落盘 |

`her.py --tail N` 能直接读回最近 N 条，**页面和本框看到的是同一份东西** ——
不会再出现「页面记得、这边不知道」。

纪律：**没发生的对话不落盘**。容器不在时 `her.py` 只回一句实话（0.9 秒），
不写账本 —— 账本里只留她真说过的话。

实测：`--tail` 读回跨来源记录正常；`source` 字段贯通桥与页面（`selftest` 行验完已剔）。
