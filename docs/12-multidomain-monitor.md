# 12 · 多域监控：改一处，整面复查 —— 29 个域 236 位只读位逐位真调

> 这一页回答的是那个最难听的质疑：**"修一处坏一处，你怎么知道你只修了那一处？"**
> 答案不是"我很小心"，而是：**每次改完，把 29 个域 236 位只读位全部重跑一遍，跟基线逐位比。**
>
> 读数来自 `data/multidomain-monitor-live.json`（由 `tools/codex-scripts/multi-domain-monitor.py --diff --out …` 现跑生成）。

---

## 一、它测什么、不测什么

| | 内容 |
|---|---|
| **测** | 341 位里 `safe=true` 且**无需必填参数**的那 **236 位** —— 每一位空 payload 真调一次，判 `ok / denied / failed / timeout / exception` |
| **不测** | 105 位写口与需参数位（不越门、不瞎编参数）—— 数量**如实报**，不假装覆盖了全量 |
| **不测** | 语义正确性（"答案对不对"是评测那一层的事，见 [04](04-evaluation.md) / [07](07-capability-proof.md)） |
| **口径** | `ok` 要求"信封 status=ok **且** 本体 `ok != false`"；只读信封绿、本体红的情形**不算过**（本仓栽过这个坑） |

---

## 二、这一轮的读数（2026-10-21）

```
多域监控：29 个域 · 测 236 位只读位（另有 105 位写口/需参数不跑）
合计：221/236 通过 · 用时 306.2s
回归（改前 ok → 现在不 ok）：0
修好（改前不 ok → 现在 ok）：0
```

| 指标 | 读数 | 含义 |
|---|---:|---|
| 域数 | **29** | 341 位分布在 30 个域，含读位的域 29 个 |
| 真调 | **236** | 只读且无需参数 |
| 通过 | **221** | 真返回、本体 ok |
| 未通过 | **15** | **全部是门拒绝（denied），没有一条是 failed/timeout** |
| 未跑 | **105** | 写口 + 需参数 |
| 回归 | **0** | 基线里 ok 的，这一轮**一个都没坏** |
| 修好 | **0** | 见下：本轮确实改过代码，但没有一条是"改前不 ok"的位 |
| 用时 | 306.2s | 含安全扫描类 28~65s 的慢位；超时上限设 90s，**不把慢当坏** |

逐域（通过 / 测）：

| 域 | 读数 | 域 | 读数 | 域 | 读数 |
|---|---|---|---|---|---|
| system | 45/45 | llm | 22/25 | security | 19/19 |
| mind | 17/17 | pipeline | 9/14 | creation | 32/32 |
| tentacle | 10/12 | recon | 9/9 | data | 8/8 |
| tools | 7/7 | engine | 5/5 | video | 5/5 |
| devour | 3/4 | finance | 4/4 | voice | 3/4 |
| vision | 3/4 | integration | 3/3 | longrun | 3/3 |
| brain | 2/2 | infra | 2/2 | project | 2/2 |
| social | 2/2 | device | 0/2 | comms | 1/1 |
| collab | 1/1 | desktop | 1/1 | framework | 1/1 |
| image_video | 1/1 | life | 1/1 | — | — |

---

## 三、那 15 条"未通过"到底是什么（逐条点名，不合并）

**全部是 `denied`** —— 门在按设计拒绝，不是能力坏了。按缺的票分组：

| 缺的票 | 条数 | 具体能力位 | 门给的原话 |
|---|---:|---|---|
| `deploy_publish` | 4 | `mirror_ascend` `mirror_release` `mirror_rewind` `pipeline_submit` | 部署、晋升、回滚或写入生产交付区 |
| `process_execute` | 4 | `codex_thread_new` `mcp_call` `mcp_connect` `mirror_rehearse` | 启动进程、执行命令或连接 MCP/终端服务器 |
| `external_llm` | 2 | `codex_models` `llm_chat` | 把当前任务数据发送到外部大模型服务 |
| `device_control` | 2 | `bluetooth` `bt_control` | 连接、写入或控制蓝牙及其他外部设备 |
| `data_export` | 1 | `devour_pulse` | 把数据发送到外部服务或持久化到框架外 |
| `privacy_read` | 1 | `vision` | 读取屏幕、摄像头、麦克风或隐私载体 |
| `audio_output` | 1 | `voice` | 让本机发声（TTS 合成/播放）或写入音频产物 |
| **合计** | **15** | — | — |

> **为什么把"被拒"单列成一栏而不是算失败**：`denied` 证明的是**门在生效**；
> 把它混进"失败率"里，会让人误以为"能力坏了"，也会诱导下一个人去"修"一个本来正确的拒绝。

### 3.1 顺手修掉一条"读数被自己省掉"的毛病

第一版监控把这 15 条的作用域全打成了 `(未报)`。根因：门把 `missing_scopes` 放在
**`gbt_result.result` 那一层**，而监控只读了顶层。现在两层都读，并从 `reason` 的原话里兜底提取作用域
（`需要人工授权（device_control）…` ⇒ `device_control`）。
**证据**：修前 15 条全是 `(未报)`，修后 7 类票全部点得出名字（上表）。

---

## 四、基线 + diff：这才是"修一处坏一处"的解药

```
第 1 次跑（不带 --diff）  → 写基线 state/monitor/domain-baseline.json（上一份自动存 .prev.json）
第 2 次跑（--diff）       → 逐位与基线比：回归列表 / 修好列表 / 计数
第 3 次跑（--diff）       → 同上（本轮连续两次 diff 都是 0 / 0）
```

三条判据（写进工具里，不靠人记）：

1. **回归必须为 0**：改完只要有一条"基线 ok → 现在不 ok"，就是**连带坏了**，`--strict` 会非零退出；
2. **修好默认应为 0**：没动读面却冒出"修好"，说明**环境变了**（例如某把钥从缺到有），要去看是不是别的改动漏了登记；
3. **报"没跑"必须是真没跑**：读不到基线就报 `没有基线可比：先跑一次不带 --diff` 并**非零退出**，不假装全绿。

### 4.1 这一轮的 0/0 是有内容的（不是"什么都没干"）

立完基线之后，我在这台机器上**真改了三处**（都在 [GBT天真那一页](10-gbt-tianzhen.md) 里写明）：

| 改动 | 文件 | 为什么它可能连累别处 |
|---|---|---|
| `LoadImage` 契约名、`out` 可选、连边按 socket 名退化 | `gbt_allinone/tools/comfy_native.py` | `comfy_native` **本身就在监控名单里**（creation 域 32 位之一） |
| `op=run` 落点支持 `filename_prefix` | 同上 | 写面路径，读面无感 |
| 拒绝回执透传 `missing_scopes` / `reason` | `gbt_allinone/brain_exec.py` | 五维合一链的执行层，所有走它的调用都受影响 |

**改完再跑整面：221/236 一条没变、15 条拒绝一条没变 ⇒ 回归 0。**
这就是本页存在的意义：**"我改的那一处没连累别的"这句话，只有整面重跑过才敢说。**

---

## 五、那 105 位为什么不跑（按域点名）

| 域 | 未跑 | 域 | 未跑 | 域 | 未跑 |
|---|---:|---|---:|---|---:|
| creation | 22 | llm | 16 | security | 10 |
| video | 9 | recon | 8 | system | 6 |
| tentacle | 6 | engine | 5 | pipeline | 4 |
| data | 4 | integration | 4 | mind | 2 |
| tools | 2 | longrun | 1 | devour | 1 |
| vision | 1 | collab | 1 | desktop | 1 |
| **合计** | **105** | | | | |

原因只有两类：

- **写口**：写盘/出网/花钱/起进程 —— 空 payload 跑它等于"拿真东西试手"，本仓纪律不许；
- **需参数**：缺必填参数就不该硬编一个假参数去凑绿（`PARAM_REQUIRED` 里逐个登记过）。

---

## 六、怎么自己跑

```bash
# ① 先立基线（改代码之前跑一次 = 有了"改前对照"）
py -3.14 tools/codex-scripts/multi-domain-monitor.py

# ② 改完再跑，与基线逐位比（--strict：有回归就非零退出，适合挂 CI）
py -3.14 tools/codex-scripts/multi-domain-monitor.py --diff --strict

# ③ 把这一轮读数（含 diff 结论）落一份给交付物/看板
py -3.14 tools/codex-scripts/multi-domain-monitor.py --diff \
    --out outputs/open-source-release/data/multidomain-monitor-live.json

# 慢位（安全扫描 28~65s）想放宽时限
py -3.14 tools/codex-scripts/multi-domain-monitor.py --timeout 120
```

---

## 七、边界（说清，别让读者高估）

1. **每位只调 1 次**：它证明"活着、调得动、没被连带弄坏"，**不证明**"在这个输入下一定对"；
2. **判决会随环境变**（有钥/没钥、有无 TTY、机器负载）：所以只把 **diff** 当归因依据，**不拿绝对条数跨机器比**；
3. **236 ≠ 341**：105 位没测，别把 221/236 念成"341 位里过了 221 位"；
4. **它不替代评测**：模型答得准不准是 [04 评测](04-evaluation.md)（335 题 PASS45 98.51%）与
   [07 能力自证](07-capability-proof.md)（221 位逐位真调）两套尺子的事，三套读数**分开报**。
