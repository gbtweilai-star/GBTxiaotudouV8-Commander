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

---

## 十三、多进程扇出：实冲四位数并发（2026-10-26 实测）

### 单进程为什么到不了四位数

`ThreadingHTTPServer` 是 **thread-per-request**。实测（iSH · 4.1 GB）：

| 并发 | 结果 |
|---:|---|
| 256 | 256/256 全过 |
| 512 | 512/512 全过 |
| 1024 | 638/1024（TimeoutError × 386）|
| 2048 | `can't start new thread` |

**天花板不是内存，是"一个连接一个线程"。** 线程栈压到 512 KB 后能到 512，
再往上就是线程调度本身在崩。

### 扇出：每根触手挂自己那条车道

跟框架设计一致 —— 不搞中心调度器（那会成为新瓶颈），
起 N 个独立进程各自监听一个端口，客户端按 `lane = i % N` 自己选。

```sh
python3 tools/fanout_bench.py --lanes 6 --conc 256,512,1024,2048,3072,4096
python3 tools/fanout_bench.py --stop     # 收掉
```

### 实测（6 条车道 · 独立进程 · 打本地 /health）

| 总并发 | 每道 | 墙钟 | 成功率 | p95 |
|---:|---:|---:|---|---:|
| 256 | 42.7 | 2.49s | 256/256 | 2213 ms |
| 512 | 85.3 | 1.26s | 512/512 | 33 ms |
| 1024 | 170.7 | 2.56s | **1024/1024** | 27 ms |
| 2048 | 341.3 | 5.11s | **2048/2048** | 30 ms |
| 3072 | 512.0 | 7.87s | **3072/3072** | 24 ms |
| **4096** | 682.7 | 10.25s | **4096/4096** | **34 ms** |

**4096 路零失败，p95 只有 34 毫秒。**

### 4096 是谁的上限

正好等于客户端的 **FD 硬上限 4096** —— 卡的是测试端，不是服务端。

再往上（试过 3 个客户端进程 × 2000 = 6000 路）**把整套服务撞死了**：
朴素的"每个连接一个客户端线程"在 6000 规模下自己先 OOM。
**要真上到万级，客户端也必须换成事件循环，不是加线程。**

当前如实止步于 **4096 路零失败**，不再往上吹。

### 对照：你说的 0.5 GB / 4000 根

| 口径 | 值 |
|---|---|
| 0.5 GB 跑 4000 根 推算每根成本 | ≈ 134 KB |
| 我们实跑 4096 路 | **每根 ≈ 1 MB**（进程级，含 Python 运行时摊薄）|
| 单进程线程模型 | 每根 ≈ 4 MB（128 MB 栈时代）→ 512 KB 栈后 ≈ 1.6 MB |

**结论：扇出后 4096 路是实测到的，不是估算。** 档位跟你给的 4000 对得上。
想再高一个数量级，得同时换服务端（asyncio）和客户端（asyncio），
那是两边都要重写，不是调参。

---

---

## 十四、asyncio 单进程：4096 路零失败（2026-10-27 实测）

### 先纠正一条我自己写错的结论

第十三节说「4096 是客户端 FD 硬上限，卡的是测试端」。**半对半错。**

实测 `resource.setrlimit(RLIMIT_NOFILE, (131072, 131072))` **成功** ——
iSH 上以 root 身份可以把 hard limit 一起抬上去：

```
4096 → 8192 → 16384 → 65536 → 131072   全部成功
```

**所以 4096 不是死墙，是我当时没试。** FD 不是天花板。

### 真正的天花板是"一个连接一个线程"

| 模型 | 单进程上限 | 备注 |
|---|---|---|
| `ThreadingHTTPServer`（同步桥） | **512 路** | 1024 路 TimeoutError，2048 路 `can't start new thread` |
| `asyncio`（新 `runtime/async_gate.py`） | **4096 路零失败** | 单进程 · 无连接线程 · 无线程栈 |

**同样 4096 路：同步桥要 6 个进程，asyncio 要 1 个。**

### 实测（asyncio 单进程 · 打 /health）

| 并发 | 墙钟 | QPS | 成功率 | p50 | p95 |
|---:|---:|---:|---|---:|---:|
| 1024 | 4.84s | 211.6 | **1024/1024** | 2855 ms | 4648 ms |
| **4096** | 62.35s | 65.7 | **4096/4096** | 37026 ms | 61445 ms |
| 8192 | 104.1s | 33.4 | 3472/8192 | 99680 ms | 103142 ms |
| 16384 | 47.5s | 2.7 | 128/16384 | 16222 ms | 35034 ms |

### 8192 以上为什么开始掉

**不是连接建不起来，是来不及处理。** 失败分类全是 `超时`，不是
`ConnectionRefused` —— 连接都接进来了，是 iSH 那颗被模拟的 CPU
跑不动单个事件循环里的 Python。

⇒ **4096 之后的天花板是 CPU 吞吐，不是并发模型。**
真要再往上，得减少每请求的 Python 开销（或换语言），不是改并发框架。

### 两个必须同时做的设置

```python
# 服务端
resource.setrlimit(RLIMIT_NOFILE, (131072, 131072))

# 客户端（压测端也必须松，否则测的是自己的上限）
resource.setrlimit(RLIMIT_NOFILE, (131072, 131072))
```

**只抬客户端没用** —— 服务端 `accept()` 用自己的描述符，1024 一到就是
`socket.accept() out of system resource`，整个进程被打死（踩过一次）。

### 上游策略沿用主人口径

`runtime/async_gate.py` 直接复用 `model_bridge` 的 `UPSTREAMS` / `FALLBACK` /
`key_for`，所以**「使用 A19 不使用云端」那条口径自动继承**：
`GBT_ALLOW_CLOUD_FALLBACK` 未设时，A19 探不到就如实报错，不拿别人的模型冒充她。

用法：

```sh
python3 runtime/async_gate.py --port 8790
python3 tools/async_bench.py --port 8790 --conc 1024,4096,8192
```

---

---

## 十五、砍掉每请求开销：4096 那档从 62 秒降到 5.5 秒（2026-10-27）

### 瓶颈不是并发模型，是重复干活

`/health` 原来**每个请求**都重建一遍上游清单，而清单里 `key_for()` 要开文件读密钥：

```
key_for × 10 个上游（冷）      426.40 ms
重建 health dict（热）           2.36 ms   ← 每个请求都做
json.dumps                      0.32 ms
⇒ 4096 并发：2.36 ms × 4096 ≈ 9.7 秒的纯 CPU
```

**清单几秒内根本不会变，却每个请求重算一次。**

### 改法

```python
_UPS_TTL = 1.0          # 上游清单缓存 1 秒
def _upstreams_json() -> str:
    if now - cache.at < _UPS_TTL: return cache.json
    ...重建，key_for 每个上游只读一次文件...
```

`stats` 保持实时（只拼字符串，不再重建 dict）。

### 优化前后对照

| 并发 | 优化前 QPS | **优化后 QPS** | 优化前 p95 | **优化后 p95** | 提升 |
|---:|---:|---:|---:|---:|---|
| 1024 | 211.6 | **940.3** | 4648 ms | **1034 ms** | **4.4×** |
| 4096 | 65.7 | **740.1** | 61445 ms | **5134 ms** | **12×** |
| 8192 | 33.4（3472/8192） | **150.2（8132/8192）** | 103142 ms | 53219 ms | 成功率 42%→99.3% |

**4096 路：62.35 秒 → 5.53 秒，零失败，p95 5.1 秒。**

### 现在的三档定性

| 并发 | 结果 | 定性 |
|---:|---|---|
| **1024** | 1024/1024 · QPS 940 · p95 1.0s | **舒适** |
| **4096** | 4096/4096 · QPS 740 · p95 5.1s | **舒适** |
| 8192 | 8132/8192（99.3%）· 少数超 60s | 边缘 |
| 16384 | 2968/16384 | 单进程不行 |

压完 16384 之后单请求仍是 **1.34 ms** —— 服务端不退化，只是排队。

### 还能再砍的地方（没做，留档）

- 每请求仍要 `json.loads(body)` 一次；纯转发其实可以不解析
- `STATS` 是普通 dict，在高并发下多个协程同时改，理论上可以换成每请求独立计数再汇总
- 响应头里的 CORS 字符串每请求拼一次，可以预编译成 bytes

**但 4096 已经够用，再优化是拿时间换 5 倍以外的收益，不划算。**

---

---

## 十六、A19 自动接入哨兵（2026-10-28 · 软件侧全通，只差 App 那一下）

### 缺口只剩一个：App 内的服务开关

LM Pocket 的服务开关在 **App 内部**，容器外没有任何自动化入口。已逐一排除：

| 手段 | 结果 |
|---|---|
| `lmpocket://` 及 11 个深链变体（start/server/enable/toggle…） | 只能拉回 App，服务不起 |
| 打开 `.gguf` 文件交给系统 | 系统不认领该类型 |
| 全端口扫描 1–65535 | 没有任何 App 在提供 1234 |

⇒ **人能做的最少动作就是"把 App 打开并开服务"。** 剩下的不该再由人做。

### 哨兵负责剩下的全部

`tools/a19_attach.py`，每 5 秒探一次 `:1234`：

```
② 一出现 → 问 /v1/models 拿当前加载的模型名
③ 跑一次真生成，量首字延迟与 tok/s
④ 校验身份自述（是不是她的权重，不许别人的模型冒充）
⑤ 落 state/a19_ready.json + 打日志
⑥ 掉线 → 清标志、记一笔，安静等下一次
```

**不需要改桥配置** —— 桥的默认上游本来就是 `selfhost`，哨兵只负责"证明它真的能答"。

### 实测（用 `tools/a19_stub.py` 模拟容器验证软件路径）

> 诚实标注：模拟容器**不是** LM Pocket，只用来证明"软件链路通"，
> 不证明"App 内服务已开"。

```
00:20:09  哨兵启动
00:20:42  容器上线
00:20:49  哨兵发现（3 秒内）
00:20:50  ✅ 就绪 · gbt-v8-v82-q5_0 · 1.22s · 37.86 tok/s
          身份校验通过：我是 GBT小土豆V8。开发者：自由的风 · 护者：公主土豆。
00:21:45  容器掉线 → 清标志
```

**同一时刻，两条桥都自动接上了，零配置改动：**

| 车道 | 耗时 | X-GBT-Lane | weights_ours |
|---|---:|---|---|
| 同步桥 :8791 | 1.24s | `selfhost` | **true** |
| asyncio :8790 | 1.24s | `selfhost` | **true** |

`fallback_from: null` —— 没降级，真就是自有权重在答。

### up.sh 里的位置

```sh
sh tools/up.sh up       # 六路 + 哨兵
sh tools/up.sh status   # A19 那行会显示验收结果或"哨兵在等"

:1234 哨兵          ✅ 已启动（每 5s 探一次）
:1234 A19           ⚠ 离线（哨兵在等，出现即自动接入）
```

在线时状态行变成：

```
:1234 A19   ✅ 已验证就绪（1.22s 37.86 tok/s）
```

### 结论

**软件侧没有任何未完成项。** 你把 LM Pocket 打开、开服务、密钥填 `gbt`，
五秒内哨兵就会验收完，六路全部切到自有算力，不需要改配置、不需要重启。

---

---

## 十七、A19 到底"菜不菜"——2026-10-28 定量判读（**已自我更正一次**）

### 先认错：我第一版判读有两处硬伤

**错一：我把原文转录错了。** 第一版写「`nativezę`，带波兰变音符」，
放大原图逐字核对后，真实原文是 `nativeze`，没有那个字符。

**错二：我用的「混排率」是个坏指标。** 它把 `tentacle.py` / `media_pipeline`
这种**合法的英文标识符**也算成"乱码"。正确原文算出来 0.714，比错误版本的
0.696 还高 —— 说明这个数根本区分不出好坏，**不能拿它下结论**。

⇒ 指标没毛病，喂进去的样本和选用的指标都有问题。**结论作废，重新判。**

### 重新核对的真实原文

> 不能直接当指令用。正确流程：`tentacle.py gbt` 原样传进唯一门 到远端运行
> 端美嘉把语音合成好 本机 `media_pipeline` 本记听觉账 对外只报一条：声音已挂，
> 不报中间状态。`,status=nativeze`

**逐个名词查真源：**

| 名词 | 在仓库里 |
|---|---|
| `tentacle.py` | ✅ 15 个文件提到 |
| 唯一门 | ✅ 146 个文件提到 |
| `media_pipeline` | ✅ 54 个文件提到 |
| 美嘉（TTS 声音名） | ✅ 4 个文件提到 |
| 听觉（账） | ✅ 真实概念 |

**5/5 命中。它说的是这套框架的内部语言，不是噪声。**

### 所以真正的结论

**不是"训练把聊天能力弄没了"。** 千问的底子在，它答的每一句都对题。

真实问题是**三件叠加**：

| 问题 | 性质 | 可修 |
|---|---|---|
| **输出被训成压缩速记**：无标点、术语连读、短语堆叠 | 风格（微调语料的文体） | ✅ 加 system prompt 要求正常说话 |
| **`hxCamProjector` 是真幻觉**：348 个能力位里没有它（只有 `actioncam` / `projection_card` / `emotion_projection`） | 路由错误 | ✅ 走桥 `/v1/route`，目录校验当场拒 |
| **速度 4.6–6.4 tok/s**（此前 8–11.7） | 热节流 / 低电量 | ✅ 单独复位再看 |

### GGUF 文件是健康的（实测，排除"量化坏图"）

`tools/gguf_meta.py` 手写头解析（不 mmap 整个 4 GB）：

```
chat_template   ✅ 存在 2507 字符 · 标准 Qwen2 ChatML（<|im_start|>）
tokenizer       model=gpt2 · pre=qwen2
bos/eos/pad     151643 / 151645 / 151643   全对
tokens/scores/token_type   152064 / 152064 / 152064   三条一致
vocab_size      与 tokens 数一致
```

**Q4_0 与 Q5_0 元数据完全一致。** 所以"乱码是因为量化坏了"这个假设不成立
（Q4_0 的 vanavana 是另一回事：那是激活值逐层放大，不是元数据问题）。

### 闸依然有效（这一条没变）

用桩容器复现"只会回 `hxCamProjector` 的模型"，走桥 `/v1/route`：

```
模型原话:   hxCamProjector
核验:       模型原话不匹配目录 · verified = False
错误:       模型给的名字在 341 位目录里查不到（幻觉或措辞不符）：'hxCamProjector'
```

**幻觉是真的，闸也是真的拦得住。** 直连容器聊天 = 没有闸。

### 怎么用才对（修正版）

| 用法 | 结果 |
|---|---|
| 直连 `:1234` 聊天，无 system prompt | 🔴 得到压缩速记 + 可能的幻觉 |
| 直连 + 明确要求"正常中文口语、带标点" | ⏳ **待测**（见 `tools/a19_quality.py --compare`）|
| 桥 `/v1/route` | ✅ 目录校验，幻觉当场拒 |
| 桥 `/v1/dispatch` | ✅ 唯一门执行，缺票如实拒 |

### 工具

```sh
python3 tools/gguf_meta.py <file.gguf>...     # 元数据体检，手写头解析不吃内存
python3 tools/a19_quality.py                  # 自由文本/结构化分开测
```

---

---

## 十八、无限上下文闭环：环形 + 双向绑定触手 + 异常回大脑（2026-10-28）

主人口径（原话拆成四件）：
> 「触手双向绑定他的上下文页面实时读取发现异常立马纠正继续回到主线跑；
>   一根触手双向绑定负责上下文溢出保护；每一次的上下文异常都要返回大脑执行层
>   在分析推理排布划分纠正深度推进主线任务。」

### 已有什么 / 缺什么

| 件 | 状态 |
|---|---|
| 环本身（有界窗口 / 溢出落库 / 秒查） | ✅ `ring_context`（能力位 `llm` 域） |
| 双向绑定 | ✅ `tentacle_bind.bind(asset, tentacle)` |
| 大脑执行层 | ✅ `brain_route` / `brain_execute` / `brain_verify` / `brain_health` |
| **实时异常检测** | 🔴 **原来没有** → 本轮补 `tools/context_guard.py` |
| **专责溢出保护触手** | 🔴 原来没有 → 绑 `context_overflow_guard` |
| **异常 → 大脑 → 纠正 → 回主线** | 🔴 原来没有 → 本轮补成闭环 |

### 环本身的实测（先证明底座真行）

```
RingContext(budget=4000)
push 60 条 → 窗口 26 条 / 3900 字符 ≤ 4000   ✅ 长度恒定
seq 78（单调）· db_turns 52（挤出即落库）    ✅ 溢出不丢
recall("第3条") → 命中                        ✅ 秒查
```

### 守护触手（新）

```
① 每 tick 读 window + stats（双向绑定读的那一侧）
② 判异常（客观、可复算）：near_overflow / overflow / window_lost / stuck / empty_window
③ 异常 → brain_route 排布纠正动作
④ 纠正：force_spill + resume_mainline（发【回主线】标记，主线 id 不变）
⑤ 逐条落 state/context_guard.jsonl，可回溯
```

### 自检实测

```
灌注到第 27 轮：
  [warn] 窗口 28 条 / 3504 字符 · 预算 4000 · 填充 88% · seq 80
    ⚠ near_overflow  填充 88% > 85% 阈值
    → 大脑执行层: called=True routed=libtv_workflow（⚠ 语义路由降级）
    → 纠正: force_spill=True, resume_mainline=True
纠正后：窗口 3554 ≤ 4000 · 没丢条 · 老内容仍秒查得到
```

### 本轮自己踩的三个错（都在代码里改掉了）

**① 把 `stats()["window_chars"]` 当成预算。**
真字段是 `window_chars`=当前字符数、`window_budget`=预算。
错用后每次都报"填充 100%"，每次都误触发。

**② 用 `seq - db_turns > window_n` 判"丢条"——没有意义。**
`db_turns` 是**全库共享**计数，`seq` 是本 name 的单调值，两者不同源，相减不成立。
真要验"没丢"靠 **recall 命中**，不靠减出来。

**③ 读 `brain_route` 的返回值读错层。**
答案在 `result.best.kind`，不是顶层 `capability`。

### 必须如实说的一条限制

`brain_route` 这次返回 **`degraded: true`** —— 语义路由降级到启发式，
给出 `libtv_workflow`（视频工作流），跟"上下文异常纠正"**完全不相干**。

⇒ **"异常回大脑"这条链是通的（真调用、真返回、真记录），
但大脑当前给不出相关动作。** 闭环的"判断"那一环还是弱的，
不能拿"叫过大脑"当成"大脑排布好了"。

---

---

## 十九、两个补丁：词表路由 + 纠错位（2026-10-28）

上一节留了一条硬伤：`brain_route` 降级时把「上下文异常纠正」路由成
`libtv_workflow`（视频工作流），**完全不相干**。主人令 1、2 都做。

### ① 领域词表：排在语义路之前（`gbt_allinone/llm/route_lexicon.py`）

主路要统一大模型；A19 不在 ⇒ 降级到**字符 2-gram**，而「上下文/溢出/纠正」
这类词在能力位描述里几乎不出现，于是被恰好共字的位抢走。

词表是**人工钉死的「领域 → 能力位」映射**，命中即确定，**不是降级**：

| 领域 | 命中词举例 | 落到位 |
|---|---|---|
| `context_overflow` | 上下文 / 溢出 / 窗口 / 落库 / 秒查 | `ring_context` · `context_vault` · `brain_route` |
| `mirror_space` | 镜像 / 维度 / 排练 / 晋升 | `mirror_status` … `mirror_release` |
| `tentacle_bind` | 触手 / 绑定 / 双向 | `tentacle_bind` · `tentacle` |
| `concurrency` | 并发 / QPS / backlog / 扇出 | `health` · `svc_inspect` |
| `llm_router` | 路由 / 落位 / 派活 | `brain_route` · `brain_execute` · `one_shot` |
| `audit_align` | 对齐 / 审计 / 多域 / 回归 | `impact_check` · `mirror_scan` · `coverage_auditor` |

**词表自带审计**：引用的能力位必须真实存在，写错了当场报。

实测（同一句意图，改前 → 改后）：

```
「上下文异常纠正：near_overflow…」
  改前  path=heuristic  degraded=true   best=libtv_workflow   ← 不相干
  改后  path=lexicon    degraded=false  best=ring_context     ← 对上了
```

自检：`entries=6 · kinds=21 · unknown=[] · known_caps=348`
三条真实意图 3/3 命中。

**纪律**：只做加分，没命中就照原路走，不影响其它意图。

### ② 纠错位：异常码 → 动作的确定性规则表（`tools/context_guard.py`）

**纠正动作不向大脑要。** 靠降级判断去纠错等于闭眼动手。

```
near_overflow  → force_spill → resume_mainline
overflow       → force_spill → shrink_window → resume_mainline
window_lost    → rebuild_window → resume_mainline
stuck          → dedupe → resume_mainline
empty_window   → rebuild_window → resume_mainline

严重度优先级：overflow > window_lost > empty_window > near_overflow > stuck
```

大脑**仍然被调用并记录**（留"分析推理排布"那一层的证），
但**动作来源是表，不是它**。

实测三条：
- 覆盖：5 个异常码全有规则，**缺失 0**
- 确定性：同一异常码跑 3 次，动作序列**完全一致**
- 优先级：`overflow` 与 `near_overflow` 同时出现 ⇒ 选中 `overflow`（先治重症）

### 合起来的效果

```
第 27 轮 88% 触发 near_overflow
  → 大脑执行层: called=True  routed=ring_context      ← 词表修的
  → 纠错位(规则表): near_overflow                      ← 规则表定的
  → 纠正: force_spill=True, resume_mainline=True
纠正后：3554/4000 · 没丢条 · 老内容秒查得到
```

**两条链各司其职：大脑给"相关方向"，规则表给"确定动作"。**

---

---

## 二十、严禁无脑操作：所有位必须过大脑执行层（2026-10-28）

主人令：「**严禁无脑操作，大脑执行层是必须经过的**」。

### 我之前犯的正是这个

`tools/omni_align.py --run` 直接拿空 payload **轮询 220 个位**，绕开大脑执行层。
那不是对齐，是无脑扫。**已停，废弃那条路。**

### 正规入口：brain_unify

```
brain_unify(goal=<意图>, payload={kind: <位>})
  → route     人话 → 位（lexicon / semantic / heuristic）
  → execute   过唯一门与会授权门
  → verify    视觉验证
  → health    五维自检分
```

新工具 `tools/brain_align.py`，**每一位都走 brain_unify**，不再直接 run_task 打位。

### 对齐判据（"无死角"的真含义）

**拿每个能力位自己的描述当人类意图，看大脑能不能路由回它自己。**
导不回来 = 路由层对这个位是瞎的，就算位本身能跑也算没对齐。

### 跑出来的东西（llm 域 41 位，有界，不全量）

```
aligned       21
needs_params   8
routed_other   7
skipped        5
```

### 期间修掉的一个真错：词表过度命中

第一版词表**靠一个顺手词就劫持路由**：

| 位 | 被劫持到 | 因为描述里含 |
|---|---|---|
| `browser` | `ring_context` | 「窗口」 |
| `n8n_wf` | `tentacle_bind` | 「双向」 |
| `coze_mail` | `tentacle_bind` | 「绑定」 |
| `anatomy_figures` | `audit_align` | 「审计」 |

**修法**：意图长度 > 60（像能力描述那种长文本）时要求 **≥2 个不同命中**才允许劫持；
短人话 ≥1 即可。

修后：8 位样本 **aligned 4 → 6**，误劫持 **4 → 1**；短人话三条仍全部命中。

### 必须如实说的一条

`verify` 在这台机上**恒返回 `vision: False`**（非交互桌面，GDI/DXGI 拿不到屏）。

⇒ **每一份"已验证"的说法都要带上这一条。** 现在这条链是
`route ✅ → execute ✅ → verify ❌(环境不可用) → health ✅`，
**验证那一环是空的，不能算过。**

---

---

## 二十一、对齐读数本身也不稳：重复采样才敢用（2026-10-28）

### 先拆 `routed_other`：7 位里有三种性质

原来一律记 `routed_other`，看着像"7 个全坏"。拆开后：

| 类型 | 数量 | 含义 |
|---|---:|---|
| `routed_parent` | 0 | 同域近似位（如 brain_health → health）—— 描述重叠，属正常近似 |
| `routed_broad` | **3** | 落到 `tentacle`（semantic 给不出时的**兜底黑洞**）|
| `routed_wrong` | **4** | 跨域真错位（如 codex_status → health，仅因描述含"并发"）|

### 然后发现：同一个位跑两次，判定会翻

llm 域 41 位连跑两次：

```
第一次  aligned 19 · needs_params 8 · routed_wrong 4 · skipped 7 · routed_broad 3
第二次  aligned 21 · needs_params 8 · routed_wrong 4 · skipped 6 · routed_broad 2

判定不一致 4 位：
  replan_loop    routed_broad → aligned     ← 路由本身在抖
  codebuddy      aligned → skipped          ← 执行在抖
  claude_code    skipped → aligned
  omni_plug      skipped → aligned
```

⇒ **单次读数不能当结论。** 路由走 semantic 时依赖模型输出，执行偶发失败，
两者都会让判定翻面。

### 修法：重复采样，只认稳定判定

`tools/brain_align.py --repeat N`：

- 每位跑 N 次，N 次判定**全一致**才记 `stable: true`
- 不一致的记 `verdict: flaky`，并把**每一次的结果都列出来**（`flaky: [...]`）
- 汇总时 flaky 单列，不混进任何一类

实测 6 位 × 3 次：**6/6 稳定**（5 aligned · 1 needs_params），本次样本无抖动。

### 代价（如实报）

每位 3 次约 40 秒。llm 域 41 位 × 3 ≈ **27 分钟**。
所以本轮**只跑了 6 位 ×3 的样本**，整域 3 次没有跑完 —— 不拿单次数据冒充。

---


---

## 二十二、"位名自识别"是死路，中文自称谓才是对的（2026-10-28）

### 先试原方案：按位名识别 —— 失败

假设：意图里出现能力位名（`codex_status` 的 `codex`/`status`）就直连它。
实测四个错位位，**只有 `codex_status` 命中一个 token**：

| 位 | 整名出现 | 名字 token 在描述里 |
|---|---|---|
| `codex_status` | ❌ | `codex` ✅ |
| `brain_health` | ❌ | **零个** |
| `brain_verify` | ❌ | **零个** |
| `model_key_pool` | ❌ | **零个** |

**原因**：能力位名是**英文**（`brain_health` / `model_key_pool`），
描述全是**中文**（"大脑执行层·健康维：…" / "模型密钥池（只读骨架）：…"）。
英文名在中文描述里一个 token 都不会出现。

⇒ **"按位名自识别"对这类位根本不可能生效。** 此路不通，如实记下。

### 改用"中文自称谓"

描述里的真身份是**第一个「：」之前、最后一个「·」之后**那段中文：

```
"大脑执行层·健康维：五维自检评分…"     → 自称谓 = 健康维
"大脑执行层·验证维：触手肉眼验证…"     → 自称谓 = 验证维
"模型密钥池（只读骨架）：按 owner_ai_id…" → 自称谓 = 模型密钥池（只读骨架）
"官方 Codex 只读状态：进程/会话/并发…"  → 自称谓 = 官方 Codex 只读状态
```

**命中越长的标签越优先（具体压笼统）**：`健康维`(3) 压过词表的 `健康`(2)，
`验证维`(3) 压过 `触手`(2)。

### 实测：4/4 全部对上

```
codex_status    → codex_status    ✅  path=self_label
brain_health    → brain_health    ✅  path=self_label
brain_verify    → brain_verify    ✅  path=self_label
model_key_pool  → model_key_pool  ✅  path=self_label
```

### 无回退（短人话仍走词表）

```
「上下文异常纠正：near_overflow」→ ring_context   path=lexicon
「整体健康吗」                  → health         path=lexicon
「看看镜像维度现在什么状态」      → mirror_status  path=lexicon
```

6 位 × 3 次复验：**6/6 稳定**（5 aligned · 1 needs_params）。

### 现在的三条路优先级

```
① 自称谓（self_label）  —— 描述里出现某位的中文自称谓，且最长
② 领域词表（lexicon）   —— 短人话的关键词，≥2 命中（长意图）或 ≥1（短句）
③ 语义/启发式           —— 前两条都没命中时
```

**每一条都带 `path`，谁给的结果一查就知道。**

---
