# 第②步 · 第④步：去非法 effort + ACK 去假绿 方案

> 目标文件：`holo_pet/panel_server.py`（本方案落生产前，该文件 sha256 `d5a1fbddedb7f298da3100a48cb72973cc36af7a86dddfd16e9dcb6ae0ea3e4a`，1344 行，LF）
> 本方案不动 `gbt_allinone/api.py`（路由白名单已是正确实现）、不动 `gbt_allinone/codex_bridge.py`。

## 一、取证结论

判据全部来自**源码行号 + 全仓 rg**，未拿文档字面量当代码。

| 编号 | 位置 | 事实 |
|---|---|---|
| D4-1 | `panel_server.py:846-852` | `_ensure_thread()` 向 `api.run_task("codex_thread_new", {...})` 传 `"effort"`；thread/start（app-server v2）无该参数 |
| D4-2 | `gbt_allinone/api.py:50-68` | `_codex_thread_params` 白名单：`if "effort" in payload:` 落 `codex_param_deprecated` 审计并**剔除**，不下发 |
| D4-3 | `panel_server.py:796` | `_run_turn()` 向 `codex_turn_send` 传 `"effort"` —— **turn/start 合法**，本步不动 |
| D4-4 | `codex_bridge.py:601-602` | `start_turn` 内 `if effort: params["effort"] = effort` —— turn/start 带 effort 合法 |
| D4-5 | `panel_server.py:761-774` | `send()` 即时 ACK `{"ok": True, "accepted": True}`：**ACK 绿 ≠ 本轮走 Codex**，真绿假绿同形 |
| D4-6 | `panel_server.py:196-207` | `_codex_ready` 已是派生属性（块2）：`server.alive` 或 `CB.status().connected` —— 是 ACK 里 `path` 的唯一真值源 |
| D4-7 | `panel_server.py:104-110` | `_panel_audit(event, meta)`，自动加 `panel_` 前缀 → `panel_ack_deferred` |
| D4-8 | `holo_pet/app.js:501` | `await postJson("/api/message", { text: value })` —— 前端**不读** ACK 体 → 新增字段零破坏 |
| D4-9 | `holo_pet/tests/test_panel_server.py:22-65` | HTTP 层测试用自带 `_FakeBridge` 桩，不走真实现 |
| D4-10 | `panel_server.py:1081-1141` | `quick()` 也有同形即时 ACK `{"ok": True, "accepted": True}`（`:1141`） |

## 二、`:1141` 定性结论

`:1141` 是 **`HoloBridge.quick()`（`:1081` 起）的即时 ACK**，不是 `codex_thread_new` 的 ACK。

- `quick()` 把 `{action -> (kind, request)}` 映射成路由任务（`:1100-1117`），工作体在后台线程 `gbt-holo-{action}` 里跑（`:1127-1138`），结果经事件总线 `quick_result` 回传
- 它**不经过 Codex 双路**，因此不存在 `codex` / `fallback` 之分
- 但它与 `send()` 共享**同一个假绿形态**：ACK 在真正执行之前就返回 `ok=True`，执行异常只落总线 `error`，调用方从 ACK 上完全看不出来

**结论：`:1141` 属于同一契约，本步一并改**（按主人指令「不许漏一处」）。
形状与 `send()` 一致（`path` + `deferred` 两字段），取值按实况区分（见第四节）。

## 三、`test_panel_server.py:65` mock 取证结论

`:65` 的 `return {"ok": True, "accepted": True}` 是 **`_FakeBridge.quick()`（`:63-65`）的方法体**，不是 `send()`。

- `_FakeBridge` 是 HTTP 层测试用的**假 bridge**，只记录 `self.calls` 并回一个最小合法体；它**不路由真实现**
- 全仓 rg：`test_panel_server.py` 内**没有**任何断言读取 `accepted`（唯一命中就是 `:65` 这个定义处）
- 因此：**mock 不跟改**（跟改等于给桩加一个没人读的字段，是噪音）；改为在**探针**里对**真** `HoloBridge.send()` / `HoloBridge.quick()` 断言 `path` / `deferred` 确实出现（见第六节 E3/E4/E7）
- 若后续希望回归测试也覆盖，另立一条**直接实例化真 `HoloBridge`** 的用例，不改 `_FakeBridge`

## 四、改动设计（三处，均为最小面）

### 改动 1：`_ensure_thread()` 删除非法 `effort=`（`:846-852`）

改前（`:846-852`）：

```
        # S1-P1：线程创建同样走路由，并包 owner_session。
        # effort 此处故意保留——第④步才移除，保留是为了实证路由白名单确实在拦。
        with policy.owner_session():
            result = api.run_task("codex_thread_new", {
                "model": _cfg.get("model") or None,
                "sandbox": _cfg.get("sandbox", "workspace-write"),
                "effort": _cfg.get("effort") or None,
                "developer_instructions": self._instructions(),
```

改后：

```
        # S1-P1：线程创建同样走路由，并包 owner_session。
        # 第④步：effort 已移除——thread/start（app-server v2）无该参数。
        # 路由白名单虽会拒收并落审计，但面板不该再塞非法参数（D4-1 / D4-2）。
        with policy.owner_session():
            result = api.run_task("codex_thread_new", {
                "model": _cfg.get("model") or None,
                "sandbox": _cfg.get("sandbox", "workspace-write"),
                "developer_instructions": self._instructions(),
```

- 删 **1 行**（`"effort": _cfg.get("effort") or None,`）；注释 2 行 → 3 行
- 锚点（唯一命中）：上文 `"sandbox": _cfg.get("sandbox", "workspace-write"),` ／ 下文 `"developer_instructions": self._instructions(),`
- `:847` 那句「留给第④步」的标记注释**一并清掉**（已并入上面新注释的第二行）

### 改动 2：`send()` ACK 去假绿（`:774`）

改前（`:774`）：`        return {"ok": True, "accepted": True}`

改后：

```
        ready = self._codex_ready
        if not ready:
            _panel_audit("ack_deferred", {
                "reason": "codex_not_ready",
                "method": "panel.send",
                "thread_id": self._thread_id,
            })
        return {
            "ok": True,
            "accepted": True,
            "path": "codex" if ready else "fallback",
            "deferred": not ready,
        }
```

- 净 **+9 行**
- 锚点：上文 `        ).start()`（`:773`）／ 下文 `    def _set_activity(`（`:776`）

### 改动 3：`quick()` ACK 去假绿（`:1141`）

改前（`:1141`）：`        return {"ok": True, "accepted": True}`

改后：

```
        return {
            "ok": True,
            "accepted": True,
            "path": "route",
            "deferred": True,
        }
```

- 净 **+4 行**
- 锚点：上文 `threading.Thread(target=run, name=f"gbt-holo-{action}", daemon=True).start()`（`:1140`）／ 下文 `class _Handler(BaseHTTPRequestHandler):`（`:1144`）
- **不落** `panel_ack_deferred`：`quick()` 的 deferred 是**常态**（工作恒在后台线程），不是降级；落审计即噪音

## 五、`panel_ack_deferred` 审计字段规格

只在 **`send()` 且 `path == "fallback"`** 时落一条：

| 字段 | 值 | 说明 |
|---|---|---|
| `reason` | `"codex_not_ready"` | 本次降级原因（目前唯一分支；后续可扩展字符串枚举） |
| `method` | `"panel.send"` | 触发点标识 |
| `thread_id` | `self._thread_id`（可为 `None`） | 当时持有的 thread_id，便于与 `panel_thread_*` 审计对账 |

落盘经 `_panel_audit("ack_deferred", {...})` → 实际事件名 `panel_ack_deferred`，写入 `store/audit.jsonl`（record = `{ts, iso, event, meta}`）。
审计层不可用时**绝不反向打断对话路径**（既有 `_panel_audit` 约定）。

## 六、镜像验证（七窗口）

| 窗口 | 前置 | 断言 |
|---|---|---|
| E1 出网帧无 effort | mock 已起，`_ensure_thread()` 新建线程 | mock 账本 `thread/start` 帧**不含** `effort`；本次 `codex_param_deprecated` 审计条数 = 0（改前 = 1） |
| E2 turn/start 仍带 effort | `codex.effort = "high"` | `turn/start` 帧 `params.effort == "high"`（改动 1 不误伤合法路径） |
| E3 ACK 真绿 | 共享连接 alive | `ack == {"ok": True, "accepted": True, "path": "codex", "deferred": False}`；无 `panel_ack_deferred` |
| E4 ACK 假绿被揭 | 共享连接不可用（`CB.status().connected = False`） | `ack["ok"] is True` 且 `accepted is True`（旧调用方兼容）；`ack["path"] == "fallback"`；`ack["deferred"] is True`；`panel_ack_deferred` 落盘且 `reason / method / thread_id` 三键齐备 |
| E5 `quick()` 同契约 | 任一 action | `quick()` ACK 含 `path == "route"`、`deferred is True`；**无** `panel_ack_deferred` |
| E6 AST 取证 | 全文件 | `_ensure_thread` 函数体内**无** `"effort"` 字面键；`send()` / `quick()` 返回的 dict 各含 `path` 与 `deferred` 两个 key |
| E7 不回归 | — | `_run_turn` 的 `codex_turn_send` 仍带 effort；`owner_session` 包裹点仍 **7** 处；无 `server.stop()`、无 `shutdown_shared`；`CB.get_shared_server(` 仍 3 处 |

判据分离：`expect=None` 的走 observations，不参与 PASS/FAIL。
**真绿判据**：只有 `ack["path"] == "codex"` 才算本轮真走 Codex。

## 七、落生产后的验收标尺

- `gbt_allinone/tests/test_codex_bridge.py` —— 红 1 维持（既有红项，块6 转绿）
- `holo_pet/tests/test_panel_server.py` —— 20/20
- `gbt_allinone/tests/test_framework.py` —— 红 9 不上升
- 七窗口在 `--target=prod` 复跑全绿
- 生产 `panel_server.py` 改动前后 SHA256 + 行号区间对照
- 回滚点：`.scratch/panel_server.py.preblock4.bak`（写盘前就位，与改前生产逐字节相同）

## 八、与既有铁律的对照

- **S2（stop 只解挂、不销毁）**：本步不碰 `stop()`，零影响
- **S3（谁挂谁摘）**：本步不碰挂载/摘除逻辑，零影响
- **《生产禁猜律》**：本步全部判据来自源码行号 + rg 扫描 + 探针实测；`:1141` 与 `test_panel_server.py:65` 均为先取证后定性
- **《主动汇报律》**：`quick()` 的 `path="route"` 与「不落 ack_deferred」是本次判定，已在方案里显式标注，供主人确认或改判
- **《响应体优先律》**：ACK 只承诺「已受理 + 走哪条路」，终局真值仍在事件总线（`error`）与 `state()`（`codex_ready` / `last_error`）——这一层口径写进 `send()` docstring，避免 ACK 长出第二个假绿

## 九、挂账观察点

- `potato_pet/codex_client.py:101` 第三个 app-server 实例（非共享单例，另案待裁决）
- `panel_server.py:1124` `quick()` 蓝牙写确认分支返回 `{"ok": True, "needs_confirmation": True}` —— 属「未执行」而非「已受理」，是否也纳入 ACK 契约，待主人裁决

## 十、deferred 字段语义约定

`path` 与 `deferred` 成对出现，语义按**组合**分叉，读这两个字段的人一眼要能分清：

- `path="codex"` + `deferred=False` —— **真绿**：本轮确实走 Codex 受理；**不落审计**
- `path="fallback"` + `deferred=True` —— **降级**：ACK 先回「已受理」，实际可能没走 Codex；**落 `panel_ack_deferred`**（三键：`reason` / `method` / `thread_id`）
- `path="route"` + `deferred=True` —— **异步常态**：`quick()` 本身就是后台线程执行，非降级；**不落审计**（落审计反而是噪音）

一句话口径：**`deferred=True` 只在 `path="fallback"` 时代表降级**；`path="route"` 的 `True` 是常态语义。

判据对应：探针断言 `ack["path"] == "codex"` 才叫真绿；一旦出现 `path="fallback"`，审计里必须能查到对应那一条 `panel_ack_deferred`。

## 十一、宿主规矩

串行、无并发、跑完即停。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
