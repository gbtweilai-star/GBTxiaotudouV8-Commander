# 39 · 触手主干 · 原生指挥官（自有权重融合）

> 主人令 2026-10-31：「把我们的原生无限制指挥官大模型权重彻底融合进触手主干」
> 「要做到所有的触手都能通过我们自己的大模型权重」「每一项能力都要全方位不能遗漏」
>
> 本文只写**接线与口径**，不写"效果很好"这类没读数的话。所有数字都能用本文末尾的命令复现。

---

## 一、融合的是什么

主干原来把「这句话该走哪只手 / 哪个能力位」的判决，**外包给了云端大模型**
（`gbt_allinone/llm/unified.py` 的七家 key 链，过 `external_llm` 人工授权门）。外包有三笔账：

| 账 | 表现 |
|---|---|
| 要票 | 主人不在终端发 `external_llm`，主干就只能降级到词表启发式 |
| 要网 | 断网 = 判决能力归零 |
| 要钱 | 按 token 计费，问得越多越贵 |

而 **GBT 自己的总指挥权重就在盘上**（`state/weights/gbt-v8-v82-q5_0.gguf`，5.24 GB，Q5_0）。
融合 = 把这条"自己的脑子"接成主干判决的**第一顺位**，云端车道退居第二档、词表辅路保底。

## 二、结构（一条链，四个件）

```
state/weights/*.gguf          权重（自有，不在 git 里；WEIGHTS.md 有分片与 sha256）
        │
vendor/llama-server.exe       引擎（llama.cpp 官方 win-cpu 包；不用编译、不依赖 python 包）
        │  -m <gguf> -c 2048 -t N --port 8792
127.0.0.1:8792/v1/...         OpenAI 兼容端点（不出网）
        │
gbt_allinone/tentacle/commander.py   车道：权重发现 / 引擎起停 / 召回 / 判决 / 校验
        │
semantic_route.choose()       主干判决第一顺位（bridge.plan / tentacle op=plan / invoke(auto) 共用）
```

四个件各自的职责写死在代码里：

- `commander.weights()` —— **现读**盘上权重，三档来源（env → `state/weights/ACTIVE.json` → 惯例扫描），
  读不到就列出"看过哪些位置 + 怎么补"，**不编默认路径**；
- `commander.start()/stop()` —— 启动是**幂等**的（已在服务就复用，不重复起第二个进程），
  只停自己 pid 文件里的那一个（`state/commander/engine.pid`），不误杀别人的服务；
- `commander._shortlist()` —— 从**真名表**召回候选（词表强权重 + 稀有度加权的全文检索）；
- `commander.route()` —— 把候选交给权重选，**选完必须落在候选里**（不在就是幻觉，判无效）。

## 三、主干怎么用它（三处入口，一条尺子）

| 入口 | 走法 |
|---|---|
| `gbt.run_task("tentacle", {"intent": "..."})` | `bridge._invoke_core` 的 auto 腿 → `brain_exec.route` → `semantic_route` → **本机权重车道** |
| `gbt.run_task("tentacle", {"op": "plan", "intent": "..."})` | **只出判决不动手**（`bridge.plan`）：先想后动、也可以逐手核对 |
| `gbt.run_task("commander", {"op": "route", "intent": "..."})` | 直接问车道，返回 `space/name/why/candidates` |

`plan` 是 2026-10-31 新加的：它读方法表、问本机权重、返回"我会选哪个"，**一个键鼠动作都不做** ——
所以 `policy` 把它算只读（不扣 `desktop_control/privacy_read`）。这条是「想 ≠ 动」的判据，
不是给触手开口子：真落点动作（`click/type/窗口`）照旧要票。

## 四、候选池：95 只手 + 351 位能力（"全方位不能遗漏"落在这里）

- 触手方法：`semantic_route.method_table()` 现读（95 条，名 + 邻域 + 别名）；
- 本体能力：`caps_registry.BENIGN_CAPS` 现读（351 位；`data/capabilities.json` 只用来补 desc）；
- 一个池子、两种标记（`［触手］`/`［能力］`），**不做任何过滤** —— 骨架位也进池，选不选得中由读数说话。

召回（`_shortlist`）用两把**仓里原有的**尺子，不新造：

1. `data/intent-lexicon.json`（人工词表，note 原话：「命中即给强权重」）；
2. 稀有度加权的 2-gram 全文检索（`semantic_route.grams`，全仓一份）——「漏洞」比「一下」值钱。

判决（`route`）只做一件事：把召回后的 top-k 交给权重，要它回一行 JSON；**名字不在候选里 ⇒ 不采信**。
这与 `semantic_route` 对云端模型的幻觉防护是同一把尺。

## 五、降级链（三档，每档都如实标注）

```
① 本机权重车道（lane=commander_local_weights）   ← 引擎在就优先
② 云端大模型车道（lane=cloud_llm）               ← 本机没起、云端配了
③ 词表启发式（path=heuristic, degraded=true）     ← 前两档都不行
```

降级时返回里带 `degraded_reason`，并且**两个车道各自的原因都写出来**
（本机为什么没起 / 云端为什么没配），不把"本地没答"伪装成"云端没配"。

## 六、门的口径

| op | 作用域 |
|---|---|
| `status` / `route` / `ask` | **零作用域**（本地只读、不出网、不计费） |
| `start` / `stop` | `process_execute`（起停本机进程是机制门，不是三道人工护栏之一） |

`tentacle op=plan` 同样零作用域；`tentacle` 的真落点动作仍要 `desktop_control + privacy_read`。

## 七、怎么起（三条命令）

```powershell
# 1) 权重：下分片 + 合并（WEIGHTS.md 的分片名，合并后是 state/weights/gbt-v8-v82-q5_0.gguf）
# 2) 引擎：llama.cpp 官方 win-cpu 包解到 vendor/（里面有 llama-server.exe）
# 3) 起车道（幂等；起了会落 state/commander/engine.pid 与 engine.log）
python -c "import sys;sys.path.insert(0,'.');from gbt_allinone.tentacle import commander as C;print(C.start())"
```

读数与判决：

```powershell
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as g,json;print(json.dumps(g.run_task('commander',{'op':'status'}),ensure_ascii=False)[:600])"
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as g,json;print(json.dumps(g.run_task('tentacle',{'op':'plan','intent':'帮我把这段文字塞进剪贴板'}),ensure_ascii=False)[:600])"
```

## 七点五、实测读数（2026-11-01 本机 · 16 核 / 16.8 GB · 纯 CPU）

| 项 | 读数 |
|---|---|
| 权重 | `gbt-v8-v82-q5_0.gguf` · 5.24 GB · sha256 `983f19a6…fcd262f`（与 WEIGHTS.md 逐字相同） |
| 引擎 | llama.cpp b12020 `llama-server.exe`（vendor，未编译、无 python 包依赖） |
| 冷启动到 `/health` | **2.6 s**（`-c 2048 -t 12 -ngl 0`） |
| 生成速度 | 9 token / 3.2 s ≈ **2.8 tok/s**；预填约 10–12 tok/s（Q5_0 纯 CPU，符合体量） |
| 路由实测 | 「塞进剪贴板」→ `clipboard_copy`；「扫描漏洞」→ `sec_scan`；「有哪些窗口」→ `see`（3/3 命中） |
| 单次判决耗时 | 24–44 s（prompt 260–340 token，CPU 预填为主；同 prompt 前缀命中缓存时 0.5 s） |
| 召回覆盖 | recall@20 = **478/478 = 100%**（127 触手方法 + 351 能力位） |

**格式坑（已修，记在案）**：本模型是用「JSON 动作」训练的 —— 要它回 `{"pick": ...}` 它会回
`{"op":"clip","text":"…"}`；换成**人话「只输出名字」**它一次就中（实测 `clipboard_copy`）。
现在 `route()` 走人话格式，并保留 JSON 兜底解析（`_match_name` 只认候选里的真名，认不出就判无效）。

## 八、怎么验（两份尺子，别混）
| 尺子 | 命令 | 量什么 |
|---|---|---|
| 接线契约 | `python tests/test_commander_trunk.py` | 注册↔分派、作用域口径、缺件如实报、候选池覆盖 |
| 逐项可达性 | `python tools/codex-scripts/commander-coverage.py` | 446 项（95 手 + 351 能力）逐项真跑：权重能不能选中它 |

**口径必须说清**：`commander-coverage.py` 的句子是**同表生成**（别名/desc 也是召回语料）⇒
它量的是**可达性上限**，不是泛化命中率。泛化要看留出集（`semantic_route` 的 holdout）。

## 九、诚实边界

1. **Q4_0 档不可用**：`PROOF-weights.md` 实测 Q4_0 会把激活值放大到 2600 倍、输出退化成 `vana`。
   主道是 **Q5_0**；Q8_0/fp16 与 fp16 逐 token 相同但更占内存。
2. **CPU 速度有限**：7.6B Q5_0 在纯 CPU 上生成只有个位数 tok/s，所以判决只要 96 token、
   候选只给 top-k —— 不给"把 446 条全塞进 prompt"那种必然超窗的做法（ctx 默认 2048）。
3. **不替代大脑**：车道只做"选哪一项"，具体怎么执行仍走 `bridge.invoke` / `run_task` 的原有三条腿；
   每次调用照旧落审计、带钢印。
4. **`state/weights` 与 `vendor/` 不入史**（LAYOUT.md：缓存/外部），换机器要按本文第七条重放。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
