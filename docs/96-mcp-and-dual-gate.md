# 96 · 第四轮蒸馏：MCP 注册表（闭环） + 双脑确认（接进派工）

> 来源：GBT-JXDWD 的 `.omp/mcp.json` 与 `sandbox/dual_brain_gate.py`
> 主人要求：**必须全部跑通闭环并确认落实**（本文每条都有判据 + 真跑记录）。

## 一、吸收 1：MCP 注册表（闭环已验证）

v5 用一份 `mcp.json` 声明服务器（`mcpServers`: command / args / cwd / env），工具据此起进程。
我们原来只能每次手写 command 数组 ⇒ **服务器清单不可复用、不可体检**。现在补齐为注册表（5 个能力位）：

| 能力位 | 作用 | 门 |
|---|---|---|
| `mcp_register` | 读标准 mcpServers 配置 → `state/mcp-servers.json` | `filesystem_write` 门 |
| `mcp_servers` | 列出已登记服务器 | 只读 |
| `mcp_unregister` | 移除一台 | `filesystem_write` 门 |
| `mcp_health` | 每台真连一次、列一次工具、断开（up/down/tools/耗时） | `process_execute` 门 |
| `mcp_connect`（原有） | 连上（`then=tools/call` 可同进程顺手做一步） | `process_execute` 门 |

**闭环实测**（`tests/test_mcp_registry_loop.py`，12 条全绿）：

```
[1] 登记 mcp_register   → 写入 state/mcp-servers.json（gbt-demo）
[2] 列表 mcp_servers    → 能看到 gbt-demo
[3] 体检 mcp_health     → 真起子进程，up=True，tools=2
[4] 连上 list_tools     → echo / add
[5] 调工具 mcp_call     → echo("闭环OK") 原样回显
[6] 注销 mcp_unregister → 列表里没了
```

闭环用的服务器是 `tools/mcp-demo-server.py`（最小 stdio MCP：initialize / tools/list / tools/call）。

## 二、吸收 2：双脑确认（已接进 `chain_kernel` 派工路径）

v5 的 `dual_brain_gate.py`（276 行，"宪法级规则"）：推理脑 + 编程脑都点头才执行，任一否决即作废。
我们**不搬它的类体系**（本仓已有 policy 作用域门 + auth_gate 票 + 审计），只取"两道独立裁决"这一层，
落成第 385 位 `dual_gate`：

| 脑 | 我们的判据 |
|---|---|
| 推理脑 | 作用域该不该要票（读 `policy.evaluate`）· 转账金额上限（默认 10 万，`GBT_DUAL_AMOUNT_LIMIT`）· 收款人必填 · `force` 与 `dry_run` 互斥 |
| 编程脑 | 能力位必须存在（registry）· 必填参数齐 · 落点路径必须存在 |

**落实点**：`chain_kernel` 在 `approve=True` **真派工之前**先跑双脑，`both_approved=false` ⇒ 拒绝派工并
`chain_stopped`（fail-closed）。判据 `tests/test_dual_gate.py`（6 组 12 条全绿，含 4 种否决场景）。

> 边界：双脑只判"该不该/干不干得成"；**发票仍然只有主人能发**（双脑不替她兜）。

## 三、拒收（本轮）

| JXDWD 的东西 | 拒收理由 |
|---|---|
| `sandbox/orchestrator.py`（567 行：架构师/实现者/管家/裁判/看门狗） | **重复**：本仓 `orchestration` 账本 + `land` 派工 + `wf_*` 已覆盖；它的"裁判=测试框架"我们就是判据体系。**看门狗心跳**记为 backlog（未来给长任务加 lease） |
| `sandbox/decision_pipeline.py`（328 行：recall→rank→rerank） | **不契合**：那是"多候选 rerank"的推荐架构；我们的路由是能力位直取 + `trunk_reason`，没有候选池，硬搬会多一层空转 |
| `sandbox/.framework_backups/*.bak`（6 份旧版本快照） | 旧代码不进仓（我们自己的纪律） |

## 四、终检（全部跑过）

```
test_mcp_registry_loop   ALL OK —— 登记→列表→体检→连上→调工具→注销（12 条）
test_dual_gate           ALL OK —— 两脑各出裁决，任一否决即 rejected（12 条）
test_chain_kernel        ALL OK —— 七步不可跳步（双脑已接进派工前）
test_root_cause          ALL OK
test_execution_guard     ALL OK
test_proc_guard          ALL OK
test_cap_pack            ALL OK
test_skills_hub          ALL OK

cap_self 385 = 385 = 385     selfscan clean
signature clean              inventory clean
legacy clean
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
