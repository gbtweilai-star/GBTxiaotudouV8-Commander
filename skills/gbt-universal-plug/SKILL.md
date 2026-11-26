---
name: gbt-universal-plug
displayName: GBT万能插 · 动态接口融合层（没有固定插座 · 有连接点即自动生成接口插入调用）
version: 1.0.0
description: GBT小土豆V8 的「GBT万能插」用法规程。主人 2026-11-26 定调：「把能力全部整合融入触手，实现真正的万能插，改名 GBT万能插，没有固定插座，只要有接口和连接点就自动识别、生成接口、插入、使用、调用、操控」。本规程讲清它是什么（动态接口融合层 gbt_allinone/universal_plug.py）、与底层 omni_plug/omni_adapter 的分工、五个操作（schema/plug/ports/invoke/autoconnect）、门不绕的硬纪律、MCP 生态融入、触手调用方式、以及诚实边界（未接执行器如实标 not_wired）。当用户说万能插/GBT万能插/没有固定插座/自动识别接口/生成接口插入/插上就能调用/融入触手时使用。
triggers:
  - "GBT万能插"
  - "万能插"
  - "没有固定插座"
  - "自动识别接口"
  - "生成接口插入"
  - "插上就能调用"
  - "融入触手"
  - "gbt_universal_plug"
---

# GBT万能插 · 动态接口融合层

> 🔴 **照着就能跑的落地用法（浏览器接管/触手操作/授权/测试命令）见 `references/落地用法速查.md`** —— 用之前先翻它，别再摸索。
>
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **一句话**：没有固定插座 —— 给一个连接点（路径 / URL / 命令 / 端点），自动识别它是什么、
> 自动生成可调用的接口、落盘插上、融入触手；真执行一律过门，本层绝不绕门。

## 0. 它和 omni_plug 的分工（先分清，别混）

主人 2026-11-26 之前，"万能插"这个词散落在 8 个位（认知乱象，CHANGELOG L788-808 有账）。现在定死：

| 层 | 是什么 | 落点 | 谁用 |
|---|---|---|---|
| **GBT万能插**（本规程） | **动态接口融合层**：识别连接点→生成接口→落盘插上→触手可调 | `gbt_allinone/universal_plug.py`、能力位 `gbt_universal_plug` | 人 / 触手（高层意图） |
| omni_plug（底层插座） | 插座执行层：Socket/Pulse/discover/run，按类型过门 | `gbt_allinone/omni_plug.py`、能力位 `omni_plug` | 万能插的 invoke 转交给它 |
| omni_adapter（判类真源） | 纯分析：`classify(target)` 判 kind + `execute()` 现场生成适配器 | `tools/omni_adapter.py` | 门和执行共用同一 classify |

**关键**：门（`security/policy.py` 的 omni_plug 分支）和本层**共用同一个 `omni_adapter.classify`**
——不会出现"门按 A 类判、执行按 B 类干"。

## 1. 唯一入口（走 run_task 唯一门）

```bash
python tools/codex-scripts/five-dim.py cap gbt_universal_plug '{"op":"schema"}'       # 看契约
python tools/codex-scripts/five-dim.py cap gbt_universal_plug '{"op":"plug","target":"https://example.com","name":"web1"}'
python tools/codex-scripts/five-dim.py cap gbt_universal_plug '{"op":"ports"}'
python tools/codex-scripts/five-dim.py cap gbt_universal_plug '{"op":"invoke","name":"web1","verb":"get"}'
python tools/codex-scripts/five-dim.py cap gbt_universal_plug '{"op":"autoconnect"}'
```

一律走 `gbt_allinone.run_task`（唯一门）；本模块函数只作内部实现，不绕过门。

## 2. 五个操作（逐个点名）

| op | 做什么 | 作用域 |
|---|---|---|
| `schema` | 看契约（支持哪些 kind / ops / 未接清单） | 读类，零 |
| `plug` | 登记连接点：任意 target → `classify` → 自动生成 ops 接口描述符 → **落盘** | 零（只登记，不执行） |
| `unplug` / `ports` / `describe` | 拔掉 / 列出 / 查看接口描述符 | 零 |
| `autoconnect` | 扫本机可插面 + 已配置 MCP 工具，认得出的都插上 | 零（只登记） |
| `invoke` | **真调用**：转 `run_task("omni_plug", op=universal)` 或 `mcp_call` | 🔴 门在下游判，本层不绕 |
| `verify` | 判据自检 | 零 |

## 3. "自动生成接口"是怎么做的

给一个 target，`plug` 会：
1. `omni_adapter.classify(target)` → 判出 kind（path/dir/bin/cmd/http/tcp/ws/mcp/ssh/unix/scheme/image/unknown）
2. 按 kind 查 `_KIND_OPS` → 生成该连接点**能用的动词**（接口签名）：
   - http → `get`；tcp → `probe`；path → `read/stat/view`；bin → `exec/stat`；
     cmd → `run`；scheme → `open`；unix → `connect`；mcp → `call`
3. 写 `state/universal_plug/ports.json`（含 target/kind/ops/executor/签名），**重启还在**。

⇒ 这就是"没有固定插座"：新种类只要 `classify` 认得出、`_KIND_OPS` 有执行腿，插上就能调，不用预置格子。

## 4. 🔴 门不绕（硬纪律，拿实测守的）

`invoke` 一个 http 连接点的真实链路（本机实测）：
```
invoke("web1","get")
  → run_task("omni_plug", {"op":"universal","target":"https://example.com"})
  → policy 现场 classify → 挂 external_llm + data_export
  → 非 owner 会话被拒，回 how_to_grant（终端发票）
```
- 本层 `gbt_universal_plug` 本身**零作用域**（读类/登记免票）——但真执行在下游那次 `run_task` 里判。
- MCP 连接点 `invoke` 转 `mcp_call`（process_execute 门）。
- **绝不**：本层直接 `subprocess`/`urlopen`/写盘执行 —— 那等于开后门。

## 5. 融入触手（人话 → 万能插）

触手已能直接调本能力位（无需新代码）：
```python
from gbt_allinone.tentacle import bridge
bridge.is_capability("gbt_universal_plug")                       # True
bridge.call_capability("gbt_universal_plug", {"op": "ports"})     # 经 api.run_task，门照旧
```
- 两个名字空间：触手方法（see/click…）走 `bridge.route_method`；能力位（本件）走 `call_capability`。
- 触手调本件 = 走统一门，不因"是手"免检。

## 6. 融入 MCP 生态

`autoconnect` 会读已配置 MCP 服务器（`mcp_servers`）和它们的工具（`mcp_tools`），
把每个 tool 当成一个动态连接点插上；`invoke` 时转 `mcp_call`。
⇒ "整个 MCP 工具生态"自动成为万能插的接口，不用逐个写适配器。

## 7. 诚实边界（不许删）

1. **未接执行器如实标**：ws / ssh(remote) / unknown 认得出但没执行腿 → `executor=not_wired`，
   `invoke` 报 `status=not_wired`，**不冒充成功**。
2. **接口没生成的动词拒调**：`op_not_generated`，不硬猜。
3. **只登记不执行**：plug/autoconnect 只生成接口，没跑任何动作；真动作只在 invoke 且过门。
4. **零作用域 ≠ 零门**：本层零作用域是"读类/登记免票"，真执行的门在下游 omni_plug/mcp_call。
5. **凭据不落盘**：连接点只存 target/类/op 签名；密钥只写环境变量**引用名**，不回显原文。

## 8. 固化与出处

| 什么 | 在哪 |
|---|---|
| 实现（源） | `gbt_allinone/universal_plug.py` |
| 能力位登记 | `gbt_allinone/caps_registry.py`（`gbt_universal_plug`，BENIGN_CAPS 末尾） |
| 分派 | `gbt_allinone/api.py::_run_benign`（`if kind == "gbt_universal_plug"`） |
| 门（共用真源） | `gbt_allinone/security/policy.py` omni_plug 分支 + `tools/omni_adapter.classify` |
| 判据测试 | `gbt_allinone/tests/test_universal_plug.py`（9 条） |
| 连接点持久化 | `state/universal_plug/ports.json` |
| 本规程（源） | `<仓>/skills/gbt-universal-plug/SKILL.md` |
| 本规程（装机） | `~/.agents/skills/gbt-universal-plug/` 与 `~/.openclaw-autoclaw/skills/gbt-universal-plug/` |

**验收**：
```bash
python tools/codex-scripts/five-dim.py cap gbt_universal_plug '{"op":"verify"}'
python -m unittest gbt_allinone.tests.test_universal_plug -v
python tools/codex-scripts/framework_state.py    # A 面：registry/图鉴/分派三处齐
```

---

## 9. 🔴 四条操作纪律（所有对话窗口默认 · 2026-11-26 主人令）

> 本件不只讲"接口怎么插"，还钉死"插了之后怎么操作"。与 `AGENTS.md §2.5` 逐字同源。

1. **D1 主执行器 = GBT万能插**：碰触手以外的任何东西（文件/进程/HTTP/端口/页面/GUI/新连接点），默认走本件 → invoke 转 `omni_plug` 唯一门；不自己写 `subprocess`/`urllib`/裸 `open`。
2. **D2 脑·眼·手默认同开、同步执行**：看+判+动手的操作，默认一次同拍跑 `vision_loop.loop(goal, dry=False, expect=...)`：①眼 `look()` ②脑 `think()` ③手 `act()` ④验 `verify()`；眼没看到/脑 BLOCKED 就停，绝不盲动（详见 `AGENTS.md §0`）。
3. **D3 排查故障用触手监控全部关联链路**：改代码/配置前与排查时，先用 `impact_check op=impact {"targets":[...],"depth":N}`（改前查 1 跳必验 + 强依赖面，`wiring.json` 邻接图）+ 动后 `op=recent`（万能插这动撞到谁）+ `cross_scan`/`truth_scan`（跨维一致）+ `shadow_check`（影子/非限定引用），看得全才动手，避免修一处坏一处。
4. **D4 修复与部署走镜像多维空间**：全程在隔离带做——`mirror_space` 的 dimension/reality 任意改 + `mirror_plan`→`mirror_rehearse`（排练验证）→ 通过才 `mirror_release`（内部 `deployment_rehearsal.release()` → `mirror_space.ascend()` **唯一生产写入**）；复杂改动先用 `room_space` 开隔离房间（房间不碰全局 reality），`qiankun` 走完整镜像→验证→晋升链；**绝不绕过 rehearsal 直接 ascend/release**。门在 policy.py:520-544（deploy_publish/deploy_force，owner_override 不自带授权）。

**固定顺序**：`D2 开脑眼手 → D3 扫全链路 → D1 万能插执行 → D3 动后复看 → D4 镜像验证 →（通过才）晋升`。
**硬边界**：纪律只加"默认打开"，不加"免检通道"——门（policy 作用域）与生产隔离照旧。
