# 41 · 四合一原生位 `pulse_core` —— 为什么它以前总"没实现"，这次怎么焊死

> 主人 2026-10-31：「把这套量化脉冲提速，直达压缩按需激活的理念化为她的原生能力，
> 这样就不会出现遗漏和丢失了，要不然这套方案我从开始设计到现在说了不止一百次，
> 但是每次你查都有没实现的，我就很纳闷问题所在」

---

## 一、病根（三条，按严重度排）

### ① 它一直不是"能力位"，只是"描述"
这个仓自己有一条铁律：**注册 ↔ 分派 ↔ 门 ↔ 审计 ↔ 测试，五处齐才算存在**。
而这套理念此前只活在三处——`docs/` 的段落、`tools/codex-scripts/` 的一次性脚本、对话里的说法。
**注册表里没有它** ⇒ `run_task("…")` 叫不出来 ⇒ 任何一次"查一下有没有"，查的都是文档，
文档永远写着"有"。这是"每次查都说有、真用却没有"的第一层原因。

### ② 每一轮只实现一个切片，没有"总量"约束
理念包含四件事（脉冲/量化/按需/直达），但它们从没被写成**同一张判据表**。
于是每轮我读到的是一段描述，做掉其中最显眼的一段（比如把权重跑起来），
剩下三段既没有 FAIL 也没有计数 ⇒ 没人拦得住"做一半"。

### ③ 没有"红"的机制
仓里最有效的防复发件是 `ghost_guard`/`selfscan` 这类**会红**的检查。
而这套理念没有任何检查会因为它缺失而变红 ⇒ 它只能靠人记得。
**靠人记得的东西，一定会丢。**

## 二、这次的做法：把它做成一条能力位，自带判据

新增能力位 **`pulse_core`**（`gbt_allinone/tentacle/pulse_core.py`），四条焊在一起：

| 条 | 实现点 | 判据（verify 会真跑） |
|---|---|---|
| 脉冲提速 | `bridge.pulse()` 一次成包 | `capabilities_total > 300` 且 49ms 内返回 |
| 量化压缩 | `state/weights/ACTIVE.json` → Q5_0 5.24GB | 相对 fp16 14.19GB **≥ 2×**（实测 2.71×） |
| 按需激活 | `--sleep-idle-seconds 600` + `start/stop` 幂等 | `idle_sleep_s > 0` 且 引擎 bin 在位；唤醒过 `process_execute` 门 |
| 精准直达 | 召回兜住 351 能力位 + 127 触手方法 | recall@20 **≥ 99%**（实测 478/478 = 100%） |

五处齐，缺一即红：

1. **注册**：`caps_registry.py` 有 `pulse_core` 条目；
2. **分派**：`api.py` 有 `if kind == "pulse_core"` 分支；
3. **门**：`security/policy.py` —— `status/verify/plan/route` 零作用域；`wake/stop` 与 `route+wake` 收 `process_execute`；
4. **审计**：走唯一门，`call/ok/error` 照常落账；
5. **测试**：`tests/test_pulse_core.py` —— 15 条断言，**ALL OK**。

## 三、怎么问"它还在不在"（一条命令，机器答，不用读文档）

```powershell
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as g,json;print(json.dumps(g.run_task('pulse_core',{'op':'verify'}),ensure_ascii=False)[:800])"
```

当前读数（2026-11-01 实测）：

```json
{"ok": true, "checks": [
  {"name": "脉冲提速", "ok": true, "reading": {"capabilities_total": 352, "ms": 49}},
  {"name": "量化压缩", "ok": true, "reading": {"file": "gbt-v8-v82-q5_0.gguf", "size_gb": 5.24, "ratio_vs_fp16": 2.71}},
  {"name": "按需激活", "ok": true, "reading": {"awake": true, "idle_sleep_s": 600, "cold_start_s": 2.6}},
  {"name": "精准直达", "ok": true, "reading": {"candidates": 479, "recall_at_k": {"total": 478, "hit": 478, "rate": 1.0}}}
], "failed": []}
```

`failed` 非空时，缺哪条报哪条 —— 这就是"不会遗漏、不会丢失"的机器形态。

## 四、她怎么用它（不是给人看的，是给她自己走的）

| op | 做什么 |
|---|---|
| `status` | 四件套现读（只读） |
| `verify` | **真跑四条判据**，任一不成立即 `ok=false` |
| `route` | 一句话走完整条链：脉冲 → 按需（醒着复用/睡着如实报 needs_activation）→ 直达判决 |
| `plan` | 只出计划不动手（给上层看这一步会怎么走） |
| `wake` / `stop` | 起停本机引擎（过 `process_execute` 门，幂等） |

`route` 默认**不擅自起进程**：引擎睡着就返回 `needs_activation` + 唤醒命令 ——
"要不要花一张票唤醒"由主人决定，她不替主人拍板（这是本仓一贯的门口径）。

## 五、防复发（写这条是为了以后不再重演）

以后凡是"理念级"的东西，**必须**同时落地这五样，缺一视为没做：

1. 注册表条目（带 desc，写清 op 与边界）；
2. `api.py` 分派分支；
3. `policy.py` 的作用域口径；
4. `tests/test_*.py` 里**会红的**断言（不是打印）；
5. 一条 `verify` 型 op，让任何人（包括我）不读文档就能拿到 PASS/FAIL。

只写在 docs 里的，从今天起按"未实现"对待 —— 这一条本身就是对"说了上百次"的正面回答：
问题不在记性，在**没有判据**。有了判据，丢一次就会红一次。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
