# O8 修复方案 · `state()` 去审计化与状态探针免审计

> 性质：**方案（只出稿，不动刀）** · 批次：**待批** · 出稿：2026-09-17
> 起因：R36 第一刀观察项 O8 → 风哥 2026-09-17 批复 **升格为真缺陷**，排在 V2 链路级之前
> 相关判例：《静默失效律》《原子落地律》《边界来源律》《扫描器自证律》

---

## 一、缺陷事实（实测，非推断）

`HoloBridge.state()` 是**前端高频只读路径**，但它**每次调用都往生产审计流写账**。

取证脚本：`.scratch/_r37_o8_probe.py` · 原始数据：`.scratch/_r37_o8_probe.txt`

| 场景 | 新增审计行 | 新增字节 | `state()` 耗时 |
|---|---|---|---|
| 首次调用（sensory 缓存未命中） | **4** | 531 B | 337 ms |
| 6 秒后再调（缓存过期） | **4** | 531 B | 36 ms |
| 6 秒后再调（缓存过期） | **4** | 531 B | 30 ms |
| **立刻**再调（命中 5s 缓存） | **2** | 254 B | — |

**账目分解**（最近审计尾可见）：

| 来源 | 每条 `state()` 的审计 | 出处 |
|---|---|---|
| `_sensory_brain()` → `api.run_task("tentacle_status", {"_probe": True})` | `call` + `ok` = 2 条 | `panel_server.py:616` |
| `_safe_bt_status()` → `api.run_task("bluetooth", {"op": "status"})` | `call` + `ok` = 2 条 | `panel_server.py:690` |

**轮询口径**：`app.js:2138` `setInterval(() => refreshState({quiet:true}), 30000)` —— 面板活着就 30 秒一次。

**推算**：30 秒一次 → **+8 行/分钟 · +1,062 B/分钟 · ≈63.7 KB/小时**。
面板开 8 小时 → **≈510 KB/天**；面板常驻（V2 链路级会拉长运行时间）→ 线性增长，加速爆盘。
当前 `audit.jsonl` 已 **35.86 MB**、**288,078 行**。

**关键判定**：`audit("call", ...)` 里的 `"probe": true` 只是**多打了一个标记**，并**没有减少写入**——
现有 `_probe` 机制是「标记探针」，不是「免除探针」。**写账成本一条没省。**

---

## 二、修复目标（三条，分别可测）

1. **G1 · 热路径免写**：`state()` 的常规轮询路径 **新增审计 = 0 行 / 0 字节**；
2. **G2 · 语义不丢**：状态探针仍然**真的去查**（不把「查不到」伪装成「查过了」），
   失败/降级信息仍通过 `state()` 的返回字段与 `bus` 事件表达；
3. **G3 · 显式动作仍留痕**：用户主动触发的动作（发消息、审批、蓝牙开关、Notion 操作等）
   **一个审计字节都不许少**——本条只豁免「状态读取」。

---

## 三、改法（三层，最小面积）

### 第一层 · `gbt_allinone/api.py` 增加 `probe` 形参（新增能力，不改旧语义）

`run_task(kind, payload, stamp=True, safe=False, probe=False)`

- `probe=True` 时：本次调用**不写任何审计**（`call` / `ok` / `denied` / `user_error` / `error` / `preflight_*` 全免）；
- `probe=False`（默认）时：行为与现在**逐字节一致**——既有调用方与测试不受影响；
- 实现上把 `_probe` 从「payload 标记」升级为「函数级开关」，**并保留 payload 里的 `_probe` 兼容**（现有调用方零改动）。

> 为什么加在 `api.py` 而不是面板层自己吞：审计是在 `_run_task_core` 内部逐点写的，
> 面板层**没有**任何位置能拦住它。要真免写，就必须在写账的那一层开一个合法入口。

### 第二层 · `holo_pet/panel_server.py` 两处状态探针改走 `probe=True`

| 位置 | 现状 | 改为 |
|---|---|---|
| `:616` `_sensory_brain()` | `api.run_task("tentacle_status", {"_probe": True})` | `api.run_task("tentacle_status", probe=True)` |
| `:690` `_safe_bt_status()` | `api.run_task("bluetooth", {"op": "status"})` | `api.run_task("bluetooth", {"op": "status"}, probe=True)` |

严格两处，不顺手扩。其它 `api.run_task` 调用点（发消息 / 审批 / 打断 / 星云 / Notion）**一个都不动**。

### 第三层 · 只读缓存（防抖，不掩盖真值）

`_safe_bt_status()` 现在每 30 秒真查一次蓝牙栈（每次 254 B + 一次系统调用）。加 **TTL 缓存**：

- 新增 `self._bt_cache` / `self._bt_cache_at` / `self._bt_cache_ttl = 30.0`；
- 命中缓存直接返回；`force=True` 参数可绕过（供「用户手动刷新」用）；
- **失败结果也进缓存**，但 TTL 减半（15s）——避免「栈真挂了却 30 秒一直报旧的好」。

> 这一层只降频，不改真值语义：TTL 内多次读到的就是同一次真实探测结果，
> 与 `sensory_state()` 现有 5s 缓存同一范式。

---

## 四、验收（五条硬口径）

| # | 闸门 | 判据 |
|---|---|---|
| V1 | **热路径零账** | 连续 `state()` × N 次（跨过 TTL），`audit.jsonl` 字节增量 **= 0** |
| V2 | **动作仍留痕** | `send()` / 审批 / `bluetooth` 开关 / `notion` 各跑一次，审计**逐条仍在**（对照基线条目） |
| V3 | **探针仍然真查** | 断开蓝牙或让 `tentacle_status` 失败 → `state()` 返回 `ok=False`（不静默变 green） |
| V4 | **既有契约不破** | `py -3.10 -m unittest holo_pet.tests.test_panel_server -v` → **22/22 绿**；全量 `test_framework.py` 红项 **= 9（基线持平）** |
| V5 | **免审计有正负对照** | 同一次 `bluetooth`：`probe=True` 写 0 条 / `probe=False` 写 2 条 → **两组结果必须不同**（否则报 `SCANNER_BLIND`） |

---

## 五、边界与风险

**边界（来自方案原文，不推断）**

- 本刀**落生产树** `gbt_allinone/api.py` + `holo_pet/panel_server.py`，**不走镜像维度**；
- 动刀前备份 + SHA256（同第一刀口径）；不跑 GUI；S7 单独批。

**风险**

1. `api.py` 是**共享入口**（所有能力都从这里走）。新增默认参数不改变任何既有行为，
   但**必须**加契约测试：`probe=True` 与 `probe=False` 各写/不写，且返回信封逐字段相同；
2. 免审计可能掩盖**真实故障**（被免掉的那次调用出错没人记）。防线：
   面板层在 `state()` 返回里明确带 `ok=False` 与错误文本，并由前端落 `addTimeline`；
   同时 `probe` 只允许在此两处出现——**新增调用点需要在评审里说明理由**；
3. 蓝牙 TTL 缓存可能让状态**滞后最多 30 秒**。这是可接受的（前端本来就 30 秒轮询），
   但「用户点刷新」必须走 `force=True`。

---

## 六、施工序（批复后）

1. 动刀前备份 `api.py` / `panel_server.py` + SHA256；
2. 改 `api.py`（`probe` 形参 + 六处 audit 加门）；
3. 改 `panel_server.py`（两处调用点 + 蓝牙 TTL）；
4. 加契约测试 `holo_pet/tests/test_panel_server.py`：`test_probe_calls_do_not_audit`
   （正负对照：同 kind 两种写法 → 一组 0 条、一组 2 条）；
5. 跑 V1–V5 五条验收 + 全量回归；
6. **到 S7 停下报风哥**，单独批 `ascend()`。

---

## 七、动刀规格（风哥复核用 · 2026-09-17 补）

> 本节是**批复前的最后一道复核材料**：先把三个悬而未决的定性问题用证据钉死，再给出手写下刀的点位。
> 本节不改前六节任何已批内容；如与前六节冲突，以本节为准。

### 7.1 复核三问 · 证据

**问一：`run_task` → `_run_benign` 的调用链，probe 在哪一层判？**

现有链是**两层半**，审计全部写在**上面两层**，不在能力层：

```
run_task(kind, payload, stamp, safe)             # api.py:684  契约层：形状归一化 + safe 兜底
  └── _run_task_core(kind, payload, stamp)       # api.py:713  策略层：call/denied/preflight/ok/error 逐点写账
        └── _run_benign(kind, payload, decision) # api.py:70   分派层：0 处 audit()
              └── bluetooth_cap.run(...) / TB.self_diagnose()    # 能力层：0 处 audit()
```

**判点定在 `run_task` / `_run_task_core` 层**，`_run_benign` 完全不需要知道 probe——
它本来就一个字节的账都不写，传下去只会多一个没人用的形参（撞《反空壳律》）。

**问二：两个 kind 在 `_run_benign` 里走哪条分支？账是谁写的？**

| kind | 分支 | 行为 | 该分支内的 audit() |
|---|---|---|---|
| `tentacle_status` | `api.py:495-497` | `from .tentacle import bridge as TB` → `{"diagnose": TB.self_diagnose(), "coverage": TB.coverage()}` | **0** |
| `bluetooth` | `api.py:610-618` | `from . import bluetooth_cap` → `bluetooth_cap.run(op, timeout, name_filter, address, char_uuid, value_hex)` | **0** |

**账不是能力层写的，是 `gbt_allinone/api.py` 自己逐点调 `store.audit()` 写的。** 实测证据：

```
rg -c "audit\(" gbt_allinone/api.py             → 15 处
rg -c "audit\(" bluetooth_cap.py bt_control.py  → 0 处（无输出）
```

15 处的归属（逐条列清，无一处遗漏）：

| # | 行 | 事件 | 所属函数 | probe 是否要管 |
|---|---|---|---|---|
| 1 | `:60` | `codex_param_deprecated` | `_codex_thread_params` | **否**（只在 `thread/start` 参数纠偏时触发，与探针无关） |
| 2 | `:236` | `signature.audit(...)` | `_run_benign` 的 signature 分支 | **否**（这是 signature 模块自己的审计能力返回值，不是 `store.audit`） |
| 3 | `:704` | `error` | `run_task` safe 兜底分支 | **是** |
| 4 | `:722` | `call` | `_run_task_core` | **是** |
| 5 | `:728` | `denied`（DISABLED_CAPS） | `_run_task_core` | **是** |
| 6 | `:734` | `user_error`（unknown capability） | `_run_task_core` | **是** |
| 7 | `:747` | `denied`（授权不足） | `_run_task_core` | **是** |
| 8 | `:771` | `preflight_force_ignored` | `_run_task_core` | **是** |
| 9 | `:785` | `preflight_error` | `_run_task_core` | **是** |
| 10 | `:794` | `preflight_checked` | `_run_task_core` | **是** |
| 11 | `:805` | `preflight_reuse` | `_run_task_core` | **是** |
| 12 | `:835` | `preflight_already_running` | `_run_task_core` | **是** |
| 13 | `:877` | `ok` | `_run_task_core` | **是** |
| 14 | `:896` | `user_error`（能力内用法错） | `_run_task_core` | **是** |
| 15 | `:903` | `error`（能力内异常） | `_run_task_core` | **是** |

**probe 需要管的写点是 13 处**（#3–#15）；#1 / #2 不在探针调用路径上，一行不动。

**问三：probe=True 是"整个 run_task 不写账"，还是"只有这两个 kind 不写账"？**

**整个调用不写账——按"哪一次调用"开关，不按 kind 开关。** 三条理由：

1. **按 kind 开关 = 给一个能力永久摘掉审计。** `tentacle_status` 也被 `app.py:288`、`brain_exec.py:153`、
   `cross_scan.py` 等生产路径调用——那里是**真调用**，必须留痕。kind 级豁免会让"谁调的"这件事永远消失；
   调用级豁免只影响被显式声明为内部探针的那一次。
2. **审计写点本身就不是按 kind 分的**（见上表：13 处写点全是调用级上下文），调用级开关是顺着已有结构切；
   kind 级开关要新造一张 kind 白名单表 = 第五个可静默失效的面。
3. **调用级开关可被机器审计**：全仓扫 `run_task(..., probe=True)` 的调用点，白名单只放两处（见 §7.5 测试三）。
   kind 级开关回答不了"这个 kind 还有没有别的调用方在裸奔"。

**兼容口径**：payload 里的 `_probe: True` 继续认（`cross_scan.py:115` 在用），
`_probe = bool(probe) or bool(payload.get("_probe"))` —— 一条都不破。

### 7.2 O14 取证结论（前提不成立，如实报）

`PROJECT_BLUEPRINT.md` §八 O14 写的是"`state()` 调 `sensory_state()` 与 `_safe_bt_status()`，两者**都**会查蓝牙栈"。
逐路径隔离实测（`.scratch/_r39_o8_o14_probe.py` → `.scratch/_r39_o8_o14_probe.txt`）**推翻了这个前提**：

| 步骤 | 新增审计行 | 新增字节 |
|---|---|---|
| A 单独 `sensory_state(force=True)` | `call/tentacle_status` + `ok/tentacle_status` | +276 B |
| B 单独 `_safe_bt_status()` | `call/bluetooth` + `ok/bluetooth` | +254 B |
| C 整链 `state()`（sensory 缓存已过期） | `call/bluetooth` · `ok/bluetooth` · `call/tentacle_status` · `ok/tentacle_status` | +530 B |
| D 整链 `state()`（间隔 6s，缓存同样过期） | 同 C，4 行 | +530 B |

**A 组里一个 bluetooth 都没有** → `sensory_state()` 链上**没有**蓝牙查询。
真实形态是 **`state()` = 1 次 bluetooth（`:440` → `_safe_bt_status`）+ 1 次 tentacle_status（`:441` → `sensory_state` → `_sensory_hand`）**，
不是"2 次蓝牙查询"。**处置：O14 按本行改正口径，合并动作取消**——
没有第二条查询可以合并，硬合并只会把一个不存在的需求写进代码。

**自留一处错账（我自己犯的）**：D 组的标号原写"立刻重打（命中 5s 缓存）"，但脚本 `step()` 里
每步都 `time.sleep(6)`，D 与 C 间隔 6 秒 > 5s TTL，**缓存必然已过期** → D 拿到的 4 行是正确结果，
错的是我的标签。已在 `_r39_o8_o14_probe.txt` **末尾留痕改正**（标注"不改上面任何实测数字"），
错账与实测分开记，不做静默覆盖。

**同一条实测的附带收获**：`_safe_bt_status()` 的返回值形状是**双层信封**——
`{"status": "ok", "kind": "bluetooth", "result": {…bluetooth_cap 的真值…}}`，
`ok` 在里层（`result.ok`），外层没有 `ok` 字段。蓝牙 TTL 缓存的"成功/失败"判定必须认这个形状，
不许拿外层 `.get("ok")` 当判据（那会永远拿到 `None` → 永远走失败档 TTL）。

### 7.3 第一层 · `gbt_allinone/api.py`

签名（**只加一个默认形参，不动既有形参顺序**）：

```python
def run_task(kind, payload=None, stamp=True, safe=False, probe=False):
def _run_task_core(kind, payload=None, stamp=True, probe=False):
```

`run_task` 三处转调全部透传 `probe=probe`（legacy 旁路 / safe 分支 / 常路径），
safe 分支 `:704` 的 `error` 落账加 `if not probe:` 门。

`_run_task_core` 开头把标记收敛成一处，并挂一个**闭包写点**：

```python
    _probe = bool(probe) or bool(payload.get("_probe"))

    def _audit(event, meta=None):
        """本次调用是否为内部探针；为真则一处审计都不写（写账层唯一合法豁免口）。"""
        if not _probe:
            audit(event, meta)

    _audit("call", {...})   # 改前这里是 audit("call", {...})
```

随后**把该函数内其余 11 处 `audit(` 原样改成 `_audit(`**——事件名、字段、顺序、dict 字面量一律不动。
净改动 = 1 个形参 + 3 处透传 + 1 个闭包 + 12 处一词替换。

`**({"probe": True} if _probe else {})` 这些既有字段**全部保留**（probe=False 时必须逐字节不变，
它们正是既有行为的一部分）。

### 7.4 第二层 · `holo_pet/panel_server.py`（严格两处）

| 行 | 现状 | 改为 |
|---|---|---|
| `:616`（`_sensory_hand`） | `api.run_task("tentacle_status", {"_probe": True})` | `api.run_task("tentacle_status", probe=True)` |
| `:690`（`_safe_bt_status`） | `api.run_task("bluetooth", {"op": "status"}).get("gbt_result", {})` | 见下（加 `probe=True` + TTL 缓存） |

**命名更正一处**：方案前文写 `:616` 属于 `_sensory_brain()`，实测该行在 `_sensory_hand()`（`:613` 起）。
行号正确、方法名写错。**改动只按行号落，不按方法名落。**

`:690` 的形态（只读缓存层，不改真值语义）：

```python
        self._bt_cache: dict | None = None     # __init__ 新增
        self._bt_cache_at = 0.0
        self._bt_cache_ttl = 30.0
        self._bt_cache_fail_ttl = 15.0

    @staticmethod
    def _bt_failed(payload: dict) -> bool:
        """失败判定只认既有信封的真值字段（里层 result.ok / status / error），不新造字段。"""

    def _safe_bt_status(self, *, force: bool = False) -> dict:
        # 命中缓存直接返回；成功档 30s、失败档 15s（失败也缓存，但不许拿旧的好骗满 30 秒）
        # 真查走 api.run_task("bluetooth", {"op": "status"}, probe=True)
```

`force` 与同文件 `sensory_state(force=...)` **同形**；HTTP 侧**不新开参数**——
用户手动刷新走的是已有的 `/api/bluetooth` → `quick("bluetooth_status")` → `:1194` 的**审计版**路径，
不受本缓存影响，动作照旧留痕。`force` 由测试与探针调用，不留空壳。

### 7.5 第三层 · 契约测试（五处，核心三处）

落点按《测试跟着被测对象走》：**被测物是 `gbt_allinone/api.py` 的测试落 `gbt_allinone/tests/`，
被测物是面板调用点与缓存的落 `holo_pet/tests/`。**

| # | 测试 | 落点 | 判据（必须可判别） |
|---|---|---|---|
| 1 | `test_probe_true_writes_nothing_probe_false_writes_two` | `gbt_allinone/tests/test_api_probe.py`（新） | 同 kind（`bluetooth`/status）在隔离 store 里各跑一次：`probe=True` **0 行**、`probe=False` **2 行**；**两组结果必须不同**，相同 → 断言失败并明确报 `SCANNER_BLIND`（不是 PASS） |
| 2 | `test_default_behavior_unchanged` | 同上 | 同一确定性序列在隔离 store 跑两遍：**默认调用（不传 probe）**的审计行去掉 `ts`/`iso` 两个天然时变字段后**逐字节相同**；对照组 `probe=True` 的行必须**不同**（否则测试自己瞎了） |
| 3 | `test_probe_true_call_sites_are_whitelisted` | 同上 | AST 扫全仓 `.py`：`run_task(...)` 调用里带 `probe=True` 关键字的调用点**只允许** `holo_pet/panel_server.py` 两处；多一处即红。含**正对照**（合成 `run_task("x", probe=True)` 必须被扫出）＋**负对照**（`probe=False` / 裸 `run_task` 不许误报） |
| 4 | `test_probe_call_sites_pass_probe_true` | `holo_pet/tests/test_panel_server.py`（追加） | mock `api.run_task`，断言面板这两个路径确实以 `probe=True` 调用（防"改了 api 没人用"的假修复） |
| 5 | `test_bt_status_cache_ttl` | 同上 | 30s 内连打 `_safe_bt_status()` 只真查一次（mock 计数 = 1）；`force=True` 绕缓存（计数 = 2）；失败结果走 15s 档（`result.ok=False` 的缓存过 15s 即重查） |

**「逐字节不变」的口径必须说清**：审计记录里 `ts`（`round(time.time(),3)`）与 `iso` 是天然时变字段，
两次运行不可能取到同一时刻。判据落在 **`{"event","meta"}` 的 JSON 序列化逐字节一致**——
这不是把判据放松，是把"不可能相同的字段"从判据里摘出去；除此之外一个字节都不许差。

### 7.6 前六节五条验收的落点复用

V1–V5 按前文 §四原样执行，本次只补两条口径：

- **V1**：连续 `state()` × N 次跨过两个 TTL（sensory 5s / bt 30s），**生产 `audit.jsonl` 字节增量 = 0**；
- **V2**：动作仍留痕的对照条目里，**必须包含 `/api/bluetooth` 那条 `bluetooth_status`**——
  它是"读状态的审计版"，用来证明本刀没有把蓝牙整条路径免掉。

### 7.7 边界（来自方案原文，不推断）

- 本刀落**生产树**：`gbt_allinone/api.py` + `holo_pet/panel_server.py`，**不走镜像维度**；
- 动刀前已备份：`.scratch/_o8_backup_20260917T171123/`（含 `MANIFEST.json`），
  `api.py` 40,365 B / `fd72d385f4d084768930c64e7bc415a984c3f2913e3b3b9eec4bc7f06298577d`，
  `panel_server.py` 62,249 B / `cb6f8f64e21e29081d86b716ba3a562ebc7696348f95f07a3dddd090f0781570`；
- **不跑 GUI**；**不碰** `codex_bridge.py`（第二刀）；**不碰** `:1194` 那条显式动作路径；
- 到 **S7 停下报风哥**，`ascend()` 单独批。

---

## 八、动刀实测留痕（2026-09-17 · 批复后执行）

### 8.1 落点与字节

| 文件 | 改前 | 改后 | 说明 |
|---|---|---|---|
| `gbt_allinone/api.py` | 40,365 B | **41,418 B** | 1 形参 ×2 函数 + 3 处透传 + `_audit` 闭包 + 12 处一词替换 |
| `holo_pet/panel_server.py` | 62,249 B | **65,112 B** | `:616→624` 与 `:690→739` 两个调用点 + 蓝牙 TTL 缓存 + `_bt_failed` |
| `gbt_allinone/tests/test_api_probe.py` | — | **新增** | 3 个测试类 · 9 条用例 |
| `holo_pet/tests/test_panel_server.py` | 21,802 B | 追加 `O8ProbeTests` | 4 条用例 |

**行号漂移说明**：方案原文写 `:616` / `:690`，那是**动刀前**的行号；改动后为 `:624` / `:739`。
契约测试因此**不按行号白名单**，按「文件 + 外层函数名」白名单——行号会漂，函数名不会，
这正是《边界来源律》里「照抄行号就会改错行」那条的机器侧形态。

### 8.2 五道闸门实测

| 闸门 | 判据 | 实测 | 结论 |
|---|---|---|---|
| **V1 热路径零账** | 连续 `state()` 跨两个 TTL，生产 `audit.jsonl` 字节增量 = 0 | **+0 B** · sha256 不变 · 三次耗时 220.9 / 19.1 / 20.0 ms | ✅ |
| **V2 动作仍留痕** | 默认路径与面板动作路径照旧留痕 | 默认 `bluetooth` 状态 **+254 B** · 面板 `quick("bluetooth_status")` **+254 B**（各 2 条 `call`/`ok`） | ✅ |
| **V3 探针仍然真查** | 真查拿真数据；探针失败不许静默变绿 | 真查返回外层 `[kind,result,status]`、内层 `[ble_backend,classic_backend,note,ok,ops]`；负对照（打断探针）→ `ok=False / error=probe broken` | ✅ |
| **V4 既有契约不破** | 面板测试全绿 + 全量回归红 9 | `test_panel_server` **26/26**（原 22 + 新 4）· `test_api_probe` **9/9** · `test_framework` **104 项 / 红 9**，红项集合与基线**逐项一致**（bluetooth · devour_github_real · mcp_full_chain · sec_llm_configured · tentacle×5） | ✅ |
| **V5 免审计正负对照** | 同 kind：`probe=True` 0 条 / `probe=False` 2 条，两组必须不同 | **+0 B / +254 B**，两组不同 = True | ✅ |

证据：`.scratch/_r42_o8_v1_v5.py` → `.scratch/_r42_o8_v1_v5.json/.txt`。

### 8.3 改前 / 改后逐字节对照（不只是"没改坏"，是"改前那一刻的字节"）

`.scratch/_r41_o8_default_golden.py` 把**备份里的 `api.py`** 以 `gbt_allinone._api_pre` 载入
（相对导入照旧落在本包），与当前树跑**同一序列**、各自独立 store：

- 全序列（含 `bluetooth` / `tentacle_status`）：改前 **10 行** vs 改后 **10 行**，`{"event","meta"}` 逐字节一致 = **True**；
- 纯序列（环境无关的 `echo` / `count_words` / 未知能力）：**6 行 golden 固化成契约测试**
  （`DefaultBehaviorTests.PURE_GOLDEN`），长期守这条不变量；
- 两条对照臂都不同：`probe=True` → **0 行**；payload `_probe=True` → **0 行**（默认都是 2 行）。

**判据口径（已按风哥批复修正）**：`ts` / `iso` 是天然时变字段，逐字节判据落在
`{"event","meta"}` 的 JSON 序列化上——**摘掉不可能相同的字段，不是放松判据**。这条已写进测试注释。

### 8.4 判据与口径的两处补充（我拍的，报备）

1. **`_bt_failed` 的"空信封"口径**：除了认 `result.ok` / `status` / `error`，我把
   **拿不到信封（空 dict / None）判为失败**——"不能证明成功"就该走 15s 失败档，
   不许拿"没读到"当好结果（《空不等于不存在律》）。代价极小：真失败时多查一次，方向安全。
2. **`force=True` 不是空壳**：HTTP 侧**不新开参数**——用户手动刷新走的是
   `/api/bluetooth` → `quick("bluetooth_status")` 的**审计版**路径，与缓存无关；
   `force` 由契约测试与探针调用，与同文件 `sensory_state(force=...)` 同形。

### 8.5 两处自留账（我自己犯的，都改了）

1. **白名单扫描器第一版把扫描面切错**：直接全仓 `rglob("*.py")` → 扫出 vendored
   `gbt_allinone/.pylibs/numpy/**` 的一堆 `PARSE_ERROR`，以及外来工作区
   （`agent-gvmz-gbtv8/`、`.openclaw/tmp/`）的临时脚本。**已改成显式排除**：
   VCS/缓存/第三方 vendored · 临时与外来工作区 · 镜像数据面（`store`）。
   排除表就写在测试里（可审），并保留「生产面出现解析失败 = 判红」这条——
   **自盲必须可见，不许静默跳过**。
2. **我的契约测试自己就是 `probe=True` 调用点**（`gbt_allinone/tests/test_api_probe.py` 两处），
   第一版白名单测试因此判红。处置**不是**把测试文件按文件名免检（改名就失效），
   而是把豁免规则做成**结构性的**：`tests/` 目录下的文件可额外命中，其余一律判红；
   生产面必须**恰好**是白名单两处。
   顺手补了一个**语法盲区**：原扫描器只认 `probe=True` 关键字写法，
   `api.run_task("x", **{"probe": True})` 能绕过闸门 —— 已加正对照 B 把它堵上
   （**留盲区等于给绕过留门**），负对照同时覆盖 `**{"probe": False}` / `**kwargs` / docstring 字样。

### 8.6 状态快照

维度 14 · reality 12 · 护照 v20 · timelines 20 · `clean=True` · `scan()` 5/5 ·
`signature.audit` clean / 58 页 / `missing=[]` · checkpoints 1 份（`00001` + 工具自带 `.lock`） ·
**S7 未批** · 本轮**未起任何 GUI 进程** · 串行无并发。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
