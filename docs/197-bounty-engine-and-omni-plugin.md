# 197 · 超级万能插赏金插件 + GBT 赏金引擎桥（2026-11-07）

> 主人令：给超级万能插配置一套全自动挖洞能力；赏金平台以插件方式实现；用穿透式交叉扫描与并发让漏洞无所遁形。

## 一、交付面

| 层 | 位置 | 说明 |
|---|---|---|
| 插件框架 | `超级万能插/runtime/plugins.mjs` | 扫 `plugins/*/plugin.mjs`，静态校验后注册工具与 handler；重名/缺 handler 进 `REG.pluginErrors`（`--lint` 可见） |
| 赏金插件 | `超级万能插/plugins/bounty/` | 平台插件（hackerone/local/generic）+ 原生引擎适配 + Web 只读侦察 + 范围闸/双路验证/质量门/报告/提交门；11 个 `bounty_*` 工具 |
| 引擎桥（本仓） | `tools/bounty_engine.py` | `scan-code` / `verify-code` / `enrich` / `selfcheck`；stdout 只一个 JSON，日志走 stderr |
| 穿透扫描扩展 | `tools/penetrating_cross_scan.py` | `tree:<绝对路径>` 支持任意目录（单位用绝对路径），相对路径行为逐字未变 |
| CWE 表补齐 | `gbt_allinone/bounty_core.py` | 新增 CWE-502 / 798 / 942 / 1004 / 614（名称+修复建议），enrich 不再返回「未收录」 |

## 二、流水线（一条命令）

```
bounty_hunt(program, target)
  → scope 闸（project.authorizationRef + 资产匹配，失败即拒）
  → 代码目标：GBT 原生双 lane
       lane1 code_audit（多阶段 SAST；运行期 _ROOT 指向目标、findings/ledger 重定向）
       lane2 penetrating_cross_scan（钩子/步骤锁/≥2 路交叉读/遗漏补扫；安全面模式分诊）
  → Web 目标：只读侦察（DNS/TLS/头/CORS/cookie/robots/security.txt，每类 2 路独立读 + 第三路仲裁）
  → 第二路验证（代码：文件 sha256 + 行文本 + snippet 字面搜索三查）
  → CVSS/CWE enrich（bounty_core）
  → 去重（同文件行 CWE / 同资产 CWE 标题）
  → 质量门（scope/已验证/证据/复现/严重度/平台排除类/去重/档位）
  → 报告（Markdown + 侧车 JSON + 证据文件 sha256）
  → 提交门（level=submit + armed=true + confirm=true + 日配额）
```

`bounty_swarm` 把同一授权项目下多个 target 并发跑（异步 job，可 cancel）；`bounty_hunt async:true` 同样走任务队列，避免长扫描撞 MCP 超时。

## 三、沙箱下的一条硬约束（已处理）

DSH 的 python 子进程可能只被允许写工作区（GBT 仓），不能写 `超级万能插/state/`。所以：

- 引擎 `--out` 一律先落 `GBT/.scratch/bounty-engine/<id>/`；
- 由 MCP 进程（Node，允许写 KIT）把 `scan-code.receipt.json` / `code_audit_findings.json` / `cross_scan_trace.jsonl` 拷回 `state/bounty/runs/<runId>/`；
- 证据/报告由 Node 直接写 KIT。

不这样做的话，实测报 `PermissionError: ...state\\bounty\\runs\\...json.tmp`（已复现并修复）。

## 四、验证（真实跑过）

| 验证 | 命令 | 结果 |
|---|---|---|
| 引擎自检 | `pyembed python tools/bounty_engine.py --action selfcheck` | ok，命中仓内 pyembed 3.12.10；三模块可导入 |
| 引擎单测 | `pyembed python tests/test_bounty_engine.py` | ALL CHECKS PASSED（56 项：双 lane/needs_human 候选/去重/三查验证/enrich/BOM/超时诚实性） |
| 任意目录穿透 | `bounty_engine --action scan-code --root <仓外绝对目录>` | ok；PCS units 21/21 hooked，unread=[]；旧版同目标 ValueError（对照） |
| MCP 生产链路 | `mcp__omni__bounty_hunt`（代码靶场） | 3 verified / 3 报告 / coverage complete |
| 异步并发 | `bounty_hunt async:true` → `bounty_jobs get` | job done，progress 与 result 完整 |
| 范围闸 | `bounty_hunt` 打 scope 外 example.com | `denied: 目标不在任何 in-scope 资产内`（未发请求） |
| H1 只读 | `bounty_scope sync hackerone/security` | 真 API：26 in / 8 out / 19 exclusions / 125 weaknesses，已落库 |
| Web 双路侦察 | e2e 本机靶场（CORS 反射+凭据/缺头/cookie） | 6 findings（6 verified），2 条过质量门出报告；TLS 不适用项如实进 unread |
| 提交门 | `bounty_submit`（level=draft, armed=false） | 只建本地草稿，不对外；`needs_input` 提示三门 |

## 五、边界（如实）

- 自动化只覆盖**可只读取证**的面：代码 SAST/穿透交叉、Web 配置面；越权/业务逻辑/注入类要人工+认证上下文，不假冒覆盖。
- 引擎在**沙箱**里跑时耗时按 lane 硬超时；超时即弃该 lane 结果并写 unread，不折成「0 条=干净」。
- `code_audit` 的 `needs_human` 受上游 `[:200]` 截断；超出部分不静默丢弃，lane coverage 记 `needs_human` 计数。
- PCS 的 `_triage` 对仓外目录按绝对路径串判面；若目标根路径命中「测试夹具」类词，可能被判夹具（PCS 既有规则，不改）。
- 本机没有 nuclei/subfinder/httpx 等外挂；插件只做「显式选择才探测、缺件如实 needs_dependency」。
- H1 真实 POST /report_intents 未实测（避免在账号下留草稿），只读端点与 confirm 门已实测。

## 六、第二轮：看板 / 自动巡检 / H1 写路径（2026-11-07 夜）

### 6.1 目标看板与优先级（蒸馏 Osmedeus/Axiom/reNgine/reconFTW）

- `lib/watchlist.mjs`：项目 in-scope 资产 → 目标；打分公式（赏金+30、可提交+5、严重度上限、程序赏金/开放、资产类型、人工 priority）；冷却期默认 24h；通配资产默认跳过（本机无 subfinder，如实说明）。
- `lib/autopilot.mjs`：`dryRun=true` 只排序；`dryRun=false` 按并发跑完整 hunt，汇总到 job；可选 autoSubmit 仍受 level+armed+confirm 三重门。
- 工具：`bounty_watch`（add/list/remove/pick）、`bounty_autopilot`（dryRun/批量/并发）。

### 6.2 H1 写路径实测（发现并修复）

`POST /v1/hackers/report_intents` **必须带 `team_handle`**；原适配器只发 title/description，会 400。已修为 `attributes={title,description,team_handle:handle}` 并在缺 handle 时 `needs_input`。真实调用验证：create 201 / GET 200 / DELETE 200（intent 427163、427165 均删除），**没有提交任何报告**。

### 6.3 验证

`node tests/bounty-watch.mjs` → ALL OK (8 tests)；MCP 内 `bounty_watch add/pick` 与 `bounty_autopilot dryRun` 真跑通；`bounty_autopilot dryRun=false` 在本地代码靶场跑出 3 份报告（job 见 `state/bounty/jobs`）。

### 6.4 边界不变

- 自动化仍只覆盖只读取证面；H1 submit 未执行；外挂扫描器仍缺；通配/子域不假装枚举。
- 自动巡检不代替人审：报告质量门只拒绝「没证据/没复现/未验证」，平台是否收仍取决于发现本身。
