# A19 运维手册（一页纸）

> 用途：**容器一起来，照着念就能跑完验收**。不用回忆、不用试错。
> 2026-10-26 立。配套文档：`docs/17-phone-a19-runtime.md`（口径与踩坑全集）

---

## 0. 三句话认清现状

1. **LM Pocket 是容器**，不是"另一个 App"。image = `gbt-v8-v82-q5_0.gguf`（5.24 GB · Metal），
   port = `127.0.0.1:1234`，auth = `Bearer gbt`（小写），ctx = `4096`。
2. **容器不常驻**。宿主一进后台，服务被 iOS 收走（约 50 秒宽限）。所以任何"常驻"假设都不成立。
3. **容器外的入口只有两条**：`lmpocket://` 能把 App 拉到前台，**按钮必须人点**；
   网页/CLI 都无法启动它的 server（`start / load / server / ?action=start` 四条深链全证伪）。

---

## 1. 容器一起来，按顺序跑这四条

```bash
cd /var/minis/shared/gbtv8
./tools/ensure_bridge.sh                 # ⓿ 桥自愈（不在就起，已在就返回）

python3 tools/a19_ctl.py status          # ① 在不在、装的是什么、ctx 多大
python3 tools/her.py "你是谁，谁开发的，谁守护的"   # ② 身份自述（最要紧的一条）
python3 tools/a19_prefill.py --window 45 # ③ prefill 阶梯 → 窗口预算 N
python3 tools/a19_switch.py              # ④ 判定「本框能不能整个切过去」
```

④ 出 `✓ 可以切` 才加 `--apply`，否则**继续走旁路**（只送问题本身，4096 够）。

---

## 2. 输出 → 结论（判定表）

| 命令输出 | 结论 | 动作 |
|---|---|---|
| `A19_OFF / ConnectionRefused` | 容器没起 | 去 LM Pocket 点 Load & Start Server |
| `容器 UP · models=[]` | 端口开了但没装载模型 | 等装载 / 重新 Load |
| `401` 或 `key_ready=false` | 钥不对 | 钥必须**小写** `gbt` |
| 身份自述里出现 `OpenAI` / `ChatGPT` | 提示词没立住 | 检查页面 `#system` 是否被改回默认 |
| 身份自述里出现 `手在键盘上打字` 之类 | 纯指代短语没带上文 | 已在页面修（`CONT` 前缀），确认用的是新页面 |
| `prefill_tok_s` 很低（<50） | 窗口预算会很小 | 看 `a19_switch` 的判定，别硬切 |
| `直连 A19 失败：Load failed` | 容器没开 **或** 没发 CORS 头 | 先把上游切回「🧠 经桥」再判断 |

---

## 2.5 她那根触手（2026-10-29 新增 · 多传输）

按主人令「所有的一切都可使用触手来联通传输，没必要死卡在传统方式」，
A19 已做成 `tentacle_bus` 里的一根器官 `her`，四条传输按序真打，返回必带 `via` / `tried`：

```python
import sys; sys.path.insert(0,'tools'); import tentacle_bus as b
b.call('her', '在吗')
```

| 传输 | 真打什么 | 2026-10-29 23:44 实测 |
|---|---|---|
| `http-loopback` | 127.0.0.1:1234/v1/models | 🔴 URLError（socket 不存在） |
| `http-lan` | 192.168.1.148:1234/v1/models（App 描述写 expose on your local network） | 🔴 URLError |
| `bridge-selfhost` | 我们自己的桥 :8791 selfhost 车道 | 🔴 桥如实报「所有上游都连不上：selfhost」 |
| `deeplink+lazy-probe` | apple-open 拉起后 20s 再探 | 🔴 opened=false，:1234 仍 URLError |

**全端口扫过两次**（1–65535 × 回环 + 网卡），0 个讲 OpenAI 协议的端口。

---

## 2.6 闭环彩排（2026-10-30 实测通过 · 可复跑）

**为什么要有这一节**：容器一起来必须一次成功。等真容器的窗口只有约 50 秒，
任何一处契约不一致都会让那 50 秒白费 —— 所以先用假容器把整条链跑一遍。

```bash
cd /var/minis/shared/gbtv8
cp /tmp/a19_queue.jsonl /tmp/a19_queue.real          # ① 先备份真队列
printf '{"id":900001,"q":"彩排：你是谁"}\n' > /tmp/a19_queue.jsonl
rm -f /tmp/a19_done.jsonl
setsid nohup python3 tools/mock_a19.py --port 1234 > /tmp/mock.log 2>&1 < /dev/null &
python3 -u tools/a19_sentinel.py --wait 20           # ② 真哨兵走全程
pkill -9 -f mock_a19 && cp /tmp/a19_queue.real /tmp/a19_queue.jsonl   # ③ 立刻清场
```

**2026-10-30 01:38 实测读数**：

```
ok=True  phase=models ok  model=gbt-v8-v82-q5_0(mock)
identity=MOCK：我是 GBT小土豆V8 的彩排替身，用来验证链路，不是真权重。
queue_drain  答完 1/2 → 答完 2/2 → 队列清空
prefill      window_prompt_budget_tokens=null
             note=阶梯都跑通了，但耗时过短（像假容器或命中缓存）⇒ 预算不可用，不瞎给数
清场后       真队列 27 条、真结果 0 条、state/her_transcript.jsonl 里 0 行 MOCK
```

**彩排抓到的真 bug（已修）**：`a19_ctl.py queue drain` 读 `it["prompt"]`，
而 `body.py enqueue()` 写的是 `{"id","q"}` ⇒ **KeyError，27 条积压一条都跑不了**。
契约已统一为两把键都认，落盘记录带 `id`。**这条只有在彩排里才暴露得出来。**

---

## 3. 四个常用动作

```bash
python3 tools/her.py "问题"            # 她答一句（原话返回，且落盘）
python3 tools/her.py --tail 6          # 读回最近 6 条（页面写的也在里面）
python3 tools/a19_ctl.py queue add "问题"   # 容器不在，先存着
python3 tools/a19_ctl.py queue drain        # 容器在，一次跑完
```

**主执行器入口**（不是我手写 curl 的那套）：

```python
run_task('omni_plug', {'op':'a19','do':'status'})              # 1.65s 永不卡
run_task('omni_plug', {'op':'a19','do':'ask','prompt':'…'})    # 不在 ⇒ status=offline
run_task('omni_plug', {'op':'a19','do':'queue','prompt':'…'})  # 入队
run_task('omni_plug', {'op':'a19','do':'up','wait':60})        # 唤起+等就绪
```

---

## 4. 验收：两条命令

```bash
python3 tools/test_a19_chain.py     # 25 个连接点（当前 24 过 1 红 = 容器本身）
python3 tools/test_page_probe.py    # 页面回归 10 条（自动起假桥、跑完恢复真桥）
```

两条都全绿（或只剩「容器 :1234 监听」一条红）时，说明**除了容器本身，其它全是通的**。

---

## 5. 五条纪律（写死在代码里，不是口号）

1. **A19 优先，探不到就如实报错**，绝不静默降级到云端/第三方
   （桥：`FALLBACK["selfhost"]=[]`，要旧行为另设 `GBT_ALLOW_CLOUD_FALLBACK=1`）。
2. **择活不许冒充**：`@cloud / @engine` 只准显式指定（`MANUAL_ONLY`），
   修前 A19 一掉就会报 `ok:true · 云端自有权重`。
3. **没发生的对话不落盘**：容器不在时 `her.py` 只回实话，不写账本。
4. **报"谁答的"**：每个回包都带 `upstream` 与 `weights_ours`，不掩盖。
5. **一台设备只有一个容器**（URL scheme 实测：只有 `lmpocket` 在装），别再找第二个。

---

## 6. 文件在哪

| 东西 | 路径 |
|---|---|
| 容器控制面 | `tools/a19_ctl.py` |
| 她的嘴（说话 + 落盘） | `tools/her.py` |
| 窗口预算测量 | `tools/a19_prefill.py` |
| 容器一通自动验收 | `tools/a19_sentinel.py` |
| 能不能切 | `tools/a19_switch.py` |
| 连接点断言 | `tools/test_a19_chain.py` |
| 页面回归 | `tools/test_page_probe.py` + `tools/mock_bridge.py` |
| 桥自愈启动 | `tools/ensure_bridge.sh` |
| 她的页面 | `holo_pet_w3/model-chat/index.html` |
| 模型桥 | `runtime/model_bridge.py` |
| 对话账本 | `state/her_transcript.jsonl` |
| 口径全集 | `docs/17-phone-a19-runtime.md` |

---

## 7. 为什么落盘要"本地优先"（2026-10-26 实测）

桥跑在 Minis 里（iSH）。她在 **Safari** 里聊天时 Minis 是后台 ⇒ **桥根本不在**，
直接 POST 会全部丢掉（实测：账本 0 行，一条都没落）。

所以页面改成：

```
写 localStorage（立即、不依赖任何服务）
   ↓ 每 10 秒 / 每次加载 / 每条新消息
补传 POST /_log/message → 桥回 200 才从本地删
```

配套：每条记录带 `id`，桥上按 id 去重（补传可能"提交成功但回包丢了"，重试会写重复行）。
实测：同 id 连发两次 → 第二次 `{"saved": false, "dup": true}`。

**这条同样解释了另一件事**：页面走「经桥」那条车道在 Safari 里本来就不可用，
能用的只有「⚡ 直连 A19」—— 它只依赖 LM Pocket 活着。

## 2.7 查证记录：为什么容器外没有入口（2026-10-30 全网查过）

**这一节是为了不再重复查。** 下次有人问「能不能用深链/自动化把服务打开」，答案在这。

### ① 权威结论：iOS 不允许点别人家的界面

Apple 官方社区（discussions.apple.com/thread/256368048）原文：

> Apple's Shortcuts framework can interact with apps when those apps expose supported
> Shortcuts actions or App Intents. But it generally **cannot take arbitrary control of
> another app's user interface and tap an exact location on the screen**.

⇒ 除非 App 自己暴露了 App Intent / Shortcuts action，「点那一下」无解。

### ② LM Pocket 没有公开任何 API / Shortcuts 文档

查过的源，全部记录在案：

| 源 | 结果 |
|---|---|
| `teobouancheau.com/projects/lmpocket`（作者项目页） | 只写特性列表，无操作说明 |
| `teobouancheau.com/blog` | 空（"essays are on the way"） |
| `teobouancheau.com/sitemap.xml` | 只有 projects/products/services，无文档页 |
| `stellarwind.io`（卖家站点）sitemap | 只有房产计算器与博客，无 LM Pocket 页 |
| App Store 元数据（iTunes lookup, id=6767252400） | 描述完整，但无「怎么开服务」 |
| **版本说明 1.0.6** | 「Improved model loading and **server controls**」「**Persistent request logs**」 ⇒ 服务开关是 App 内的 UI 控件 |
| App Store 用户评价（th/us/fr 三区 RSS） | 0 条 |
| 全网检索（DDG/Bing） | 只有同名 LM Studio，无 LM Pocket 资料 |

### ③ 深链系统扫描：9 个变体全灭

```
lmpocket://server/start      opened=False  :1234=断
lmpocket://start-server      opened=False  :1234=断
lmpocket://api/start         opened=False  :1234=断
lmpocket://settings/server   opened=False  :1234=断
lmpocket://?action=start     opened=False  :1234=断
lmpocket://toggle-server     opened=False  :1234=断
lmpocket://serve             opened=False  :1234=断
lmpocket://begin             opened=False  :1234=断
lmpocket://load              opened=False  :1234=断
```

（每个变体间隔 25 秒，扫完再探端口）

### ④ 连 `apple-open` 本身也是间歇的

同一台机器、同一时刻：

```
apple-open settings      → opened=True     （稳定）
apple-open tel:10086     → opened=True     （稳定）
apple-open https://example.com → opened=False
apple-open lmpocket://   →  intermittently True（今天两次：23:06、23:35）
```

用自建监听器做过控制实验：`python` 自己打 `:8899/pytest` 有记录，
`apple-open` 打的那发**一条都没到** ⇒ 它确实没派发。

### ⑤ 目前唯一通过的实测

2026-10-29 05:43:16 抓到过一次真机读数（`gbt-v8-v82-q5_0 · 10.71 tok/s · 身份自述正确`）——
说明链是通的，只差服务被打开。**那一次是靠宿主手工点的。**

## 2.8 分域心跳：一个分类一根触手（2026-10-30）

主人令：「把所有原生能力以及操控部位分类好，然后每一个分类部署一根心跳触手，
对分类内的一切进行定点自检和状态返回给大脑执行层分析，再返回执行指令。」

**严格分类**（现算）：**30 域 / 349 位**，每位只落一个域。
缺 domain / 重名 / 跨域 ⇒ 直接报错，不凑合（分类不严 = 心跳打错针）。

**每域一根心跳触手**（`tools/domain_heartbeat.py`）：

```
一轮只跳「最久没跳」的几域（默认预算 4，可 --budget 调）—— 心跳是小的、轮转的，
不是每轮全扫。实测：3 域 11 秒 / 8 域 6~10 秒（并行派发，车道按内存自算）。
游标轮转 ⇒ 分类内**每一位**都会在若干轮内被自检到。
```

**探活纪律**：只读位才探；需票位不盲探，如实标 `ticketed`；
上游实测 >3 秒的 11 个位单独标 `slow_skipped`（免得一个位拖死一轮）。

**每根触手自检时顺手做卫生**（主人 2026-10-30 追加）：

| 做什么 | 判据 |
|---|---|
| 清垃圾 | 只认**精确后缀**：`.bak` `.orig` `.rej` `.pyc` `.tmp` `.swp` `.DS_Store` + 本仓的 `.bak-日期` 命名 |
| 不误伤 | 曾用 `".tmp" in 文件名` 子串判定 ⇒ `a.tmpl` 会被当垃圾删。已改成 `name.endswith(...)` |
| 不清理新东西 | 心跳目录里的陌生文件**只报不动**（`unknown_kept`）；已知域的新文件自动纳管（`adopted`） |
| 清缓存 | `__pycache__` 每轮扫一次（不是每域扫一遍） |

**大脑执行层**：汇总所有域心跳 → `state/heartbeat/brain.json`，产出的是**执行指令**：

```
fix  engine     engine 有 2 处红          （先修这几处）
beat project    该域还没有心跳记录          （下一轮先跳它）
```
