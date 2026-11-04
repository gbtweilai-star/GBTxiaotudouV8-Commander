# 156 · 吞噬 Shannon：把「No exploit, no report」蒸成授权渗透流水线

> 主人令 2026-11-02：「这个顺便也全部吞噬了」（视频里那个 90 分钟自主打穿 juice-shop 的 Shannon）。
> 执行方式：**万能插 `devour_github` 真吞** + `devour_reflect`；逐条拔缺口，把最值钱的契约层**真落地成代码**。
> 详细报告：`整理报告/吞噬-Shannon.md`（**仓外私有文档，未随仓分发**；本仓与 git 历史中均无此文件，2026-11-04 核对）。

## 一、真吞读数（2026-11-02 21:35 现读）

| 项 | 读数 |
|---|---|
| 上游 | [KeygraphHQ/shannon](https://github.com/KeygraphHQ/shannon) · **50,944★** · TypeScript · **AGPL-3.0** |
| 定位 | 自治 AI 渗透测试器（Web/API）：读源码 → 攻击路径 → **真跑 exploit 证明**；「No exploit, no report」 |
| 胶囊 | `devoured_shannon`（`gbt_allinone/store/devoured/devoured_shannon/`，3 件齐全） |
| 吞入知识 / README | 6,620 / 26,583 字符 |
| `devour_reflect` | 4 胶囊 · 均分 **80** · weak 0 / strong 4 · 互连对 6 |

流程图（它的架构）：`Recon+漏洞分析（Injection/XSS/SSRF/Auth/AuthZ） ＋ 安全代码分析（架构/信任边界/接口/数据流）→ 对账去重 → 利用队列 → exploitation agents → 验证 → PDF/MD/JSON/SARIF → CI 闸`；外围：ephemeral Docker、可续跑 workspace、认证测试配置、多 provider BYOK、GitHub Action/GitLab CI。

## 二、拔出的缺口（摘要）

| # | Shannon 有 / 我们缺 | 优先级 |
|---|---|---|
| 1 | 双流（recon × SAST）候选对账去重，保留双方证据 | **P0** |
| 2 | 利用队列按 OWASP 类派给专精代理（Injection/XSS/SSRF/Auth/AuthZ） | **P0** |
| 3 | **验证闸：没有可复现 PoC 的一律不进报告/CI**（我们原来的短板） | **P0** |
| 4 | SARIF 2.1.0 + CI 闸（只对 exploited 且严重度 ≥ 阈值失败） | **P0** |
| 5 | 可续跑 workspace（stage/queue/validated） | P1 |
| 6 | 源码攻击面图：信任边界/数据流 → 攻击路径（有 `code_graph`/`sec_surface`，缺边） | P1 |
| 7 | 认证测试流程 DSL（登录/TOTP/邮件；只收凭据槽名） | P1 |
| 8 | 扫描级临时隔离工（有 mirror/room/confinement 雏形，无扫描级 worker） | P2 |
| 9 | GitHub Action / GitLab CI 官方集成 | P2 |
| 10 | 黑盒 / SCA / secrets / findings 管理 / 修 PR / Jira（商业版） | **不追** |

## 三、本轮落地：`pentest_flow`（授权渗透流水线内核·第 0 步）

`gbt_allinone/tools/pentest_flow.py` —— **纯函数**（不攻击/不发请求/不起进程/不出网/不写盘）：

- **授权闸**：必须 `authorization_ref` + `scope`；只接 http(s)；**生产默认拒**（`allow_production`+`confirm=主人已授权` 才放）；禁写路径拦；**凭据只收槽名、明文密钥拒收**；
- **双流对账**：recon × SAST 合并去重（类别+host+path+param 签名），双方证据合并、严重度取高、置信度取大、保留 file/line；
- **利用队列**：按五类 OWASP 分组派单（执行仍在既有授权手 `offense_ops`/`pentest`/`bounty`/`own_lab`）；
- **验证闸**：`reproduced=true` + 真实请求行 + 回读证据 + 复现步骤，缺一即 `dropped`；通过才 `exploited` 并记 `proof_sha256`（**No exploit, no report**）；
- **报告**：Markdown + JSON + **SARIF 2.1.0**；只收 exploited，dropped 只计数；
- **CI 闸**：只对 exploited 且 ≥ 阈值失败（代码假设不失败流水线）；
- **续跑**：`workspace/resume`（纯 dict，断点不重复）；
- **端到端**：`pipeline()` 一条龙 + 可复现 hash。

验收：**`tests/test_pentest_flow.py` · 64 项 ALL OK**（授权 fail-closed / 对账去重 / 验证闸 / SARIF 结构 / CI 闸 / 续跑 / 纯函数 AST 探针）。

## 四、边界（说死）

1. **不是攻击工具**：本件零网络、零进程、零 payload；真 exploit 由既有授权手在那道门里执行；
2. **只对授权目标**：无授权/越界/生产未确认/明文凭据一律拒（fail-closed）；
3. **AGPL-3.0 纪律**：只蒸设计、**零代码复制**，不引 Docker/Playwright/runtime 依赖，不搬商业版能力，不搬 96.15% XBOW 战绩；
4. 模型判断仍需人工复核（上游同款口径）；
5. **已于 2026-11-02 注册**：`pentest_flow` 进 `caps_registry` + api 分派（零作用域；policy 未改；
   run_task 万能插门）；真执行仍只在既有授权手。

## 五、下一步（P1/P2）

源码攻击面图（喂 SAST 流）· 五类专精代理运行时（结论必须过 `validate`）· 认证测试 DSL（槽名）· 接进 `bounty`/`own_lab` 出报告路径 · 一键 CI 脚本 + SARIF 落盘 · 扫描级隔离（复用 mirror/room）· PDF 报告（复用 genoffice）。

## 六、复跑

```bash
# ① 真吞 + ② 反思
py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap devour_github \
  '{"repo":"https://github.com/KeygraphHQ/shannon","name":"devoured_shannon"}'
py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap devour_reflect '{}'
# ③ 流水线内核验收（64 项）
py -3.14 -X utf8 tests/test_pentest_flow.py
```

> 本轮验收机无全局 py，实际用便携 Python 3.12（纯 stdlib）跑；命令按本仓标准口径写 `py -3.14`。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
