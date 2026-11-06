# 吞噬报告：Shannon —— 自治 AI 渗透测试器「No exploit, no report」那一层

> 主人令 2026-11-02：「这个顺便也全部吞噬了」（来源视频里那个 Shannon：把网站丢给它，90 分钟自主打穿 juice-shop）。
> 执行方式：**走万能插能力位 `devour_github` 真吞**，吞完跑 `devour_reflect`；
> 再逐条对照本仓安全域，拔「我们缺什么」，把最值钱的一层**真落地成代码**（不是抄，只蒸机制）。
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 〇、真吞读数（万能插现读，2026-11-02 21:35）

| 项 | 读数 |
|---|---|
| 上游 | [KeygraphHQ/shannon](https://github.com/KeygraphHQ/shannon)（原 `laikhtman/shannon`） |
| ★ / 语言 / 许可 | **50,944★** · TypeScript · **AGPL-3.0**（只蒸设计，**零代码复制**，不引入 AGPL 依赖） |
| 定位 | 自治 AI 渗透测试器（Web/API）：读源码 → 找攻击路径 → **真跑 exploit 证明** → 报告；「**No exploit, no report**」 |
| 吞成胶囊 | `devoured_shannon`（`gbt_allinone/store/devoured/devoured_shannon/`，knowledge.json/run.py 齐全） |
| 吞入知识 / README | 6,620 / 26,583 字符 |
| `devour_reflect` | 4 胶囊 · 均分 **80** · weak **0** / strong **4** · 互连对 **6** |
| 上游硬边界（照抄它的安全口径） | 只对**自有/书面授权**目标；**不许生产**；会**改目标状态**（建号/提交/触发外联）；代码可能被 prompt injection；报告需人工复核；全跑约 1–1.5h 且烧模型费 |

**它的流水线（README/架构现读）**：
`源码 → ① Recon+漏洞分析（Injection/XSS/SSRF/Auth/AuthZ 专精代理）＋ ② Agentic 安全代码分析（架构/信任边界/接口/数据流/高风险资产）→ ③ 对账去重（两流合并）→ ④ 利用队列 → ⑤ Exploitation agents 真打 → ⑥ 验证（没复现就丢）→ ⑦ PDF/Markdown/JSON/SARIF 2.1.0 → ⑧ CI/CD 闸（只对 exploited 且严重度 ≥ 阈值失败）`。
外围：每次扫描 ephemeral Docker worker（只读挂载源码、隔离工作区）、可续跑 workspace、认证测试配置（登录/TOTP/邮件）、多 provider BYOK（含 Ollama/vLLM/LM Studio）、GitHub Action / GitLab CI。

---

## 一、我们原来有什么（对照面）

| 域 | 已有能力位 | 说明 |
|---|---|---|
| 安全思维 | `sec_surface`（攻击面测绘）· `sec_scan`（OWASP/CWE 扫自有代码）· `sec_chain`（利用链推演）· `sec_defenses`（蓝队防御验证）· `sec_llm`（独立推理通道） | 思路齐，但**各自为战**，没有「双流 → 对账 → 队列 → 验证 → 报告/闸」的契约 |
| 自主渗透编排 | `offense_ops`（蒸自 pentagi 的编排框架）· `pentest_distill`（蒸自 CyberStrike） | 有编排/授权纪律，但输出不是「只认 PoC」的契约 |
| 代码审计 | `code_audit`（多阶段 + 机器可读 findings + 独立验证 + 可复现） | 接近「代码侧」，仍缺与运行时候选的对账 |
| 授权渗透 | `pentest`（只对**已登记授权**目标做非破坏检查：TCP/TLS/安全头）· `bounty`（赏金工作台/授权闸/scope 闸）· `own_lab`（6 类漏洞真跑 → 录单 → 报告 sha256 → 账本） | 授权与账本齐，但**没有「无 PoC 不上报」的统一验证闸与 SARIF/CI 出口** |
| 门与隔离 | `auth_gate` / `policy` / `action_gate` / `mirror_*` / `room_space` / `remote_confinement` | 授权作用域与隔离有现成机制，可直接复用 |

---

## 二、逐条拔出的缺口（Shannon 有、我们缺）

| # | Shannon 的机制 | 我们缺什么 | 严重度/优先级 | 怎么蒸（不搬代码） |
|---|---|---|---|---|
| 1 | **双流对账**：运行时 recon 候选 × 源码 SAST 候选，合并去重成一张利用队列 | 没有统一候选契约与去重（sec_* 各自出结论） | P0 | `pentest_flow.reconcile()`：签名=类别+host+path+param；证据合并、严重度取高、置信度取大、保留 file/line |
| 2 | **利用队列按类派单**给 Injection/XSS/SSRF/Auth/AuthZ 专精代理 | 没有「按 OWASP 类派给专精角色」的队列层 | P0 | `exploit_queue()`：只出队列与派单；执行仍在既有手 |
| 3 | **验证闸 No exploit, no report**：只有可复现 PoC 进报告/CI | 我们报告体系（bounty/own_lab）有证据，但没有一个**统一闸**把「假设」挡在报告外 | **P0（最值钱）** | `validate()`：`reproduced=true` + 真实请求行 + 回读证据 + 复现步骤，缺一即 `dropped`，并算 `proof_sha256` |
| 4 | Markdown/JSON/**SARIF 2.1.0** 三格式 + CI 闸（只对 exploited ≥ 阈值失败） | 没有 SARIF 出口、没有「代码假设不失败流水线」的 CI 语义 | P0 | `report()` + `sarif()` + `gate()` |
| 5 | 可续跑 workspace（断点不重复已完成工作） | 长跑有账本（`longrun`/`ledger`），但没有扫描级 stage/queue/validated 续跑面 | P1 | `workspace()/resume()`（纯 dict，序列化即续跑） |
| 6 | 源码攻击面图：架构/信任边界/接口/数据流/高风险资产 → 攻击路径 | 有 `code_graph`（AST 图）与 `sec_surface`，缺「信任边界/数据流 → 攻击路径」的**边** | P1 | 在 `code_graph` 上蒸「source→sink + trust boundary」两层边，产出直接喂 `reconcile(sast=…)` |
| 7 | 认证测试配置：登录流/凭证/TOTP/邮件/ROE/聚焦区 | 有授权门与钥匙槽，缺**目标认证流程 DSL**（且绝不能吞明文凭据） | P1 | 只收**槽名/引用**；流程 DSL 走 `process_execute`/隐私门；明文密钥拒收（本轮已写进授权闸） |
| 8 | 每次扫描 ephemeral Docker worker（只读源码、隔离工作区） | 有 `mirror/room/remote_confinement` 隔离，但没有「扫描级临时工」 | P2 | 复用现有隔离件，不引 Docker 依赖；本机用一次性目录 + 只读挂载语义 |
| 9 | GitHub Action / GitLab CI 官方集成 | 无 CI 组件 | P2 | 先出一键脚本 + SARIF 文件（本轮已能出 SARIF）；平台集成按需 |
| 10 | 多 provider BYOK（Anthropic/OpenAI/xAI/Bedrock/Ollama/vLLM/LM Studio） | 已有 `ai` 插座/能源池/BYOK（更宽） | 已覆盖 | 不新增：用现有 AI 插座按扫描阶段选模型 |
| 11 | 商业版：黑盒渗透/SCA/secret 扫描/findings 管理/修 PR/Jira | 本仓有各自零散件（`redteam_recon`/`sec_scan`/`ledger`） | 不追 | OSS 版没有；我们**不冒充**有黑盒/企业面 |

---

## 三、本轮已落地（第 0 步，真代码）

新件：**`gbt_allinone/tools/pentest_flow.py`** —— 授权渗透流水线内核（**纯函数**：不攻击/不发请求/不起进程/不出网/不写盘）

| 层 | 本仓落地 | 对应 Shannon |
|---|---|---|
| 授权闸 | `scope()` / `target_in_scope()`：必须 `authorization_ref`+`scope`；只接 http(s)；**生产默认拒**（需 `allow_production`+`confirm=主人已授权`）；禁写路径拦；**明文密钥拒收、只收槽名** | Safety/Scope + 认证配置的凭据纪律 |
| 双流对账 | `reconcile(recon, sast)`：签名去重、双方证据合并、严重度取高、置信度取大、带 file/line | Finding reconciliation |
| 利用队列 | `exploit_queue()`：按 Injection/XSS/SSRF/Auth/AuthZ 分组派单 | Exploitation agents 队列 |
| 验证闸 | `validate(candidate, proof)`：缺 PoC 字段/`reproduced!=true`/请求行不合法 ⇒ `dropped`；通过 ⇒ `exploited`+`proof_sha256` | Validation（No exploit, no report） |
| 报告 | `report()`：Markdown + JSON + **SARIF 2.1.0**；**只收 exploited**，dropped 只计数 | Reporting |
| CI 闸 | `gate()`：只对 exploited 且严重度 ≥ 阈值失败；代码假设/未复现不失败 | CI/CD severity gate |
| 续跑 | `workspace()/resume()`：stage/queue/validated 纯 dict，断点续跑 | Resumable workspaces |
| 端到端 | `pipeline()`：scope→reconcile→queue→validate→report→gate，返回可复现 hash | 全链 |

验收：**`tests/test_pentest_flow.py` · 64 项 ALL OK**（授权 fail-closed / 对账去重 / 验证闸 / SARIF 结构 / CI 闸 / 续跑 / 纯函数 AST 探针）。
**它不执行任何攻击**：真 exploit 由既有授权手（`offense_ops` / `pentest` / `bounty` / `own_lab`）在那道门里跑；本件只做账、闸、报告。

---

## 四、下一步（P1/P2，按优先级）

| # | 步骤 | 接进哪里 | 门/前置 |
|---|---|---|---|
| P1-1 | 源码攻击面图（source→sink + trust boundary + data flow） | `code_graph` 加边，输出喂 `reconcile(sast=…)` | 只读 |
| P1-2 | 五类专精代理运行时（Injection/XSS/SSRF/Auth/AuthZ） | 本仓 AI 插座/Codex/Claude Code 编排，结论必须走 `validate()` 才进报告 | external_llm（用云端才要） |
| P1-3 | 认证测试流程 DSL（登录/TOTP/邮件；只收槽名） | 流程执行走 `process_execute`/隐私门；凭据只留槽名 | process_execute + privacy_read |
| P1-4 | 把 `pentest_flow` 接进 `bounty`/`own_lab` 的出报告路径 | 出报告前统一过验证闸 + CI 闸 | 写门（报告落盘） |
| P2-1 | 一键 CI 脚本 + SARIF 上传（本地能跑，不依赖云） | `tools/pentest_ci.py`（候选能力位待点头） | 无（读文件+写 SARIF → filesystem_write） |
| P2-2 | 扫描级隔离（一次性目录/只读挂载语义） | 复用 `mirror_room`/`remote_confinement` | 现有门 |
| P2-3 | 报告 PDF（可选） | 复用 `genoffice`/PDF 能力 | filesystem_write |
| 不追 | 黑盒渗透 / SCA / secret 扫描历史 / findings 管理 / 修 PR / Jira | 商业版功能 | 不冒充 |

> **注册已完成（2026-11-02 主人点头）**：`pentest_flow` 进 `caps_registry` + api 分派 + run_task 万能插唯一门；
> 零作用域纯函数（policy 未改；`cap_self verify` 390=390=390）；真执行仍在既有授权手。
> P1 增量（源码攻击面图 / 五类代理派单 / agent_ingest 接 validate）见 `docs/157`。

---

## 五、不搬清单（AGPL-3.0 纪律）

1. **不复制 Shannon 任何 TypeScript/Node 源码、prompt 文本、agent runtime**（AGPL-3.0；本仓只蒸设计）；
2. **不引入 Docker worker / Playwright / 其依赖**（本机纯 stdlib 实现流水线契约）；
3. **不复制 exploit payload / 攻击脚本**：本件 `validate()` 只校验「PoC 证据形状」，不生成 payload；
4. **不冒充商业版能力**（黑盒/SCA/secrets/findings 管理/修 PR）——OSS 版没有，我们也没有；
5. 上游的 96.15% XBOW 战绩是**它的**读数，不搬来当我们的成绩；我们只记「机制已蒸、真执行仍走授权手」。

---

## 六、复跑（三条命令）

```bash
# ① 真吞（万能插）
py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap devour_github \
  '{"repo":"https://github.com/KeygraphHQ/shannon","name":"devoured_shannon"}'

# ② 反思
py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap devour_reflect '{}'

# ③ 流水线内核验收（64 项）
py -3.14 -X utf8 tests/test_pentest_flow.py
```

> 本轮验收机无全局 py，实际用便携 Python 3.12（纯 stdlib）跑；命令按本仓标准口径写 `py -3.14`。

---

## 七、边界与诚实账

1. 本件**不是攻击工具**：零网络、零进程、零 payload；它只把「授权渗透的候选/证据/报告/闸」做成可复核的契约；
2. 上游 90 分钟打穿 juice-shop 是**视频里它的**案例；本仓没有、也不声称复现（执行面要主人授权 + 既有手 + 授权目标）；
3. `devour_github` 只吞 README/metadata（26,583 字），深水（docs/safety.md、配置、CI 语义）以本轮另读的 README/架构现读为准；
4. AGPL-3.0 是强 copyleft：**只蒸设计、零复制**；不新增 AGPL 依赖；
5. 报告与 SARIF 只能证明「有 PoC 的漏洞」；模型生成的判断仍需人工复核（上游也这么写，我们照写）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
