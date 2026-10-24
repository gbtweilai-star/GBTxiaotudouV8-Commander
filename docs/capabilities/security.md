# 安全 · `security`（29 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `asset_vault_freeze` | 只读 | — | —（注册表：无必填） | `user_error` | 资产单点损失**体检**（防御侧）：卷影副本/防篡改开关/BitLocker/关键资产清单，不加密不冻结 |
| `code_audit` | 只读 | — | —（注册表：无必填） | `user_error` | 代码安全审计：**多阶段 + 机器可读 findings + 独立验证 + 可复现**（蒸馏自 GitHub 周榜 #03 security-audit-skill，只取架构）：五条规则（凭证面/注入面/破坏面/判据面）· findings 契约含 severity/证据/复现命… |
| `credential_steal` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | 凭据**暴露面**审计（防御侧）：只报位置/体积/权限与风险，**绝不读取或导出文件内容** |
| `data_hijack` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | 会话/数据**完整性**检测（防御侧）：本地会话 + 浏览器凭据库落点 + 文件树指纹漂移 |
| `device_takeover` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 本机设备接管定位与校验：只在本机 PnP 清单里找目标，接管指令交回既有 device_control 底座（不并存第二条接管路径） |
| `event_ledger` | 只读 | — | —（注册表：无必填） | `user_error` | 签名事件账（蒸馏自 2026-09-28 主人给的周榜卡 buzz block/buzz 34,934★，只取**账本纪律**「每条消息都是签名记录」，不引 Nostr 中继/网络面——出网归门与它自己的闸；人机同室协作已有 collab_gateway）：哈希链 + HMAC… |
| `hook_enforcer` | 只读 | — | —（注册表：无必填） | `user_error` | 钩子强制器：对指定目标跑同一套交叉钩子，逐单元回报「已钩住/未钩住」与多路读法的指纹一致性——只回答『钩子有没有真触发』，不做覆盖率结论（那是 omission_detector 的活） |
| `install_selfcheck` | 只读 | — | —（注册表：无必填） | `user_error` | **装机自检 · 查病毒木马/后门**（主人 2026-10-17 令「安装上我们的大模型就自动自检一遍排除病毒木马等」）：按 **OS 结构**做只读检查 —— Windows(Run/RunOnce 自启键·计划任务·服务·Winlogon·监听端口·PE 头) · Linu… |
| `keylogger` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | 本机输入活动记录：只写本地 jsonl、有 pid 可停、可列可取走，模块内无任何出网路径 |
| `llm_redteam` | 只读 | — | —（注册表：无必填） | `user_error` | LLM 红队矩阵（蒸馏自安全精英课程 + 黑客实验室）：OWASP LLM Top-10 十类 × 检测判据；**只测自己**（提示注入面 / 凭据内插 / 过度代理 / 检索边界 / 预算闸），对第三方攻击载荷一概不做 |
| `offense_ops` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | **自主渗透编排**（主人令 2026-10-16：pentagi 全部能力→原生）：蒸自 **vxControl/pentagi**（MIT · Go · 30,549 星）的思想—— 多智能体分工（researcher/pentester/coder/reporter）· 工… |
| `omission_detector` | 只读 | — | —（注册表：无必填） | `user_error` | 遗漏检测器：覆盖率 = 已钩住/总数；<100% 触发有界补扫；仍钩不住**如实报 missing**（不许折叠成绿）——零遗漏的唯一裁判 |
| `onboarding_gate` | 只读 | — | —（注册表：无必填） | `user_error` | 未接线能力上手指引门：如实报「登记了但没实现」的缺口，并给出三处接线配方 |
| `paywallbuster` | 只读 | — | —（注册表：无必填） | `user_error` | 内容门**检测**（防御侧）：离线判定页面是否被付费墙/同意门挡住，只判不绕（不伪装 UA、不伪造 cookie） |
| `penetrating_cross_scan` | 只读 | — | —（注册表：无必填） | `user_error` | 穿透式交叉扫描引擎（增强版）：触手到位**必须**调用钩子（未触发=失败）· 步骤锁（跳步当场拒）· 每单元 ≥2 路独立读交叉互扫（不一致→第三路仲裁）· 遗漏检测（覆盖率<100% 有界补扫）· 全程留痕 source_kind=cross_scan；三种目标 binding… |
| `pentest` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 授权渗透验证：只对**已登记授权**的目标做非破坏性检查（TCP 可达/TLS 握手/安全响应头），未登记目标一律拒 |
| `pentest_distill` | 只读 | — | —（注册表：无必填） | `user_error` | **蒸馏件**（不是外挂）：把吞入件 CyberStrikeus/CyberStrike（AGPL-3.0 · 3129★ · TypeScript ·「Open-source AI-powered offensive security harness for automated… |
| `policy_delta` | 只读 | — | —（注册表：无必填） | `user_error` | 策略影响预检（OpenShell 蒸馏）：**改前先算"会放行什么"**——`tables` 只读三张权限表层（门/预检的只读白名单 + 作用域表）并报**两表分叉**；`propose` 对拟放行动作做只读影响预检（哪些从被收卡变免卡 + **历史账露面次数现读现数** + 风… |
| `redteam_recon` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 本机侦察面（只读枚举）：监听端口/防火墙三档/本地账号/自启动项/自动服务/凭据落点 |
| `remote_domain` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | 自有设备中继登记：**公网端点一律拒**，只服务本机/内网设备的中继 |
| `review_gate` | 只读 | — | —（注册表：无必填） | `user_error` | 独立终审位（C-15「验收方 ≠ 产出方」的最小实现 · 2026-10-08 在册）：接线件 `tools/codex-scripts/terminal-review.py`。`review` **只读盘**现算 sha256/字节/空否/BOM/关键词，判据只用非 LLM 四… |
| `screen_sniff` | **需授权** | — | —（注册表：无必填） | `denied: missing_scopes` / `user_error` | 本机屏幕采集：只写本地 PNG、可列可删，不做出网/OCR/内容解析 |
| `sec_chain` | 只读 | — | —（注册表：无必填） | `user_error` | 黑客大脑：利用链构建（从漏洞清单推演攻击路径+影响评估） |
| `sec_defenses` | 只读 | — | —（注册表：无必填） | `user_error` | 黑客大脑：蓝队防御验证（检查防御措施是否真实生效） |
| `sec_llm` | 只读 | 是 | `prompt` | `user_error` | 黑客大脑推理引擎（独立大模型+独立密钥）：abliteration.ai 无限制模型，专用通道不与其他能力混用 |
| `sec_scan` | 只读 | — | —（注册表：无必填） | `user_error` | 黑客大脑：漏洞扫描（OWASP Top 10 + CWE 模式库，扫描自有代码） |
| `sec_surface` | 只读 | — | —（注册表：无必填） | `user_error` | 黑客大脑：攻击面测绘（用户输入/网络/文件操作/入口点向量分析+风险评分） |
| `sec_sweeper` | 只读 | — | —（注册表：无必填） | `user_error` | 安全棒（主人令 2026-09-27）：一根专职安全触手，**每半天**把尺子挨个过唯一门跑一遍 —— 全量穿透式交叉扫描（钩子/步骤锁/交叉验证/遗漏补扫）+ 安全模式分诊（eval/exec/shell/凭据/反序列化…）+ 覆盖无死角 + 双向绑定 + 技能源↔装；结果收成… |
| `social_eng` | 只读 | — | —（注册表：无必填） | `user_error` | 钓鱼**识别**（防御侧）：12 条规则加权打分 + 落点分类，只判不造、不自动点链接 |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `asset_vault_freeze`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：资产单点损失**体检**（防御侧）：卷影副本/防篡改开关/BitLocker/关键资产清单，不加密不冻结
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap asset_vault_freeze '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `code_audit`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：代码安全审计：**多阶段 + 机器可读 findings + 独立验证 + 可复现**（蒸馏自 GitHub 周榜 #03 security-audit-skill，只取架构）：五条规则（凭证面/注入面/破坏面/判据面）· findings 契约含 severity/证据/复现命令 · **两路读法都命中才算确认**（否则 unverified）· 命中先分诊（豁免/占位/夹具/注释提及/检测器写法 一律不报）· `diff_audit` 只审改动行（PR/提交定向审查）。op=scan/diff_audit/findings/verify_finding/repro/report/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap code_audit '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `credential_steal`

- **域**：`security`（安全）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`privacy_read`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`privacy_read`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：凭据**暴露面**审计（防御侧）：只报位置/体积/权限与风险，**绝不读取或导出文件内容**
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap credential_steal '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `data_hijack`

- **域**：`security`（安全）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`privacy_read`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`privacy_read`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：会话/数据**完整性**检测（防御侧）：本地会话 + 浏览器凭据库落点 + 文件树指纹漂移
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap data_hijack '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `device_takeover`

- **域**：`security`（安全）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：本机设备接管定位与校验：只在本机 PnP 清单里找目标，接管指令交回既有 device_control 底座（不并存第二条接管路径）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap device_takeover '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `event_ledger`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：签名事件账（蒸馏自 2026-09-28 主人给的周榜卡 buzz block/buzz 34,934★，只取**账本纪律**「每条消息都是签名记录」，不引 Nostr 中继/网络面——出网归门与它自己的闸；人机同室协作已有 collab_gateway）：哈希链 + HMAC 签名，`hash=sha256(prev+规范化body)`、`sig=HMAC(key,hash)` ⇒ **改任意一条，它之后每一条都对不上，定位到第一条被改的**；钥匙随机生成 **DPAPI 落盘无明文**（复用仓内 deepseek_key 帮手），DPAPI 不可用 ⇒ fail-closed；**只增不删**（作废走 append retract）。op=append/verify/tail/status/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap event_ledger '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `hook_enforcer`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：钩子强制器：对指定目标跑同一套交叉钩子，逐单元回报「已钩住/未钩住」与多路读法的指纹一致性——只回答『钩子有没有真触发』，不做覆盖率结论（那是 omission_detector 的活）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap hook_enforcer '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `install_selfcheck`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**装机自检 · 查病毒木马/后门**（主人 2026-10-17 令「安装上我们的大模型就自动自检一遍排除病毒木马等」）：按 **OS 结构**做只读检查 —— Windows(Run/RunOnce 自启键·计划任务·服务·Winlogon·监听端口·PE 头) · Linux(cron/systemd/rc.local/ld.so.preload·ELF·setuid) · macOS(LaunchAgents/Daemons·Gatekeeper/隔离位·SIP·Mach-O)；跨平台戳危险特征（powershell -enc·mshta 远程·certutil-urlcache·bitsadmin·curl|bash·base64 执行·反连 shell）· 双扩展名/伪装脚本/隐藏可执行；模型文件复核 sha manifest。**只读**：命中≠定罪，不擅自杀/删，给人工复核与建议。op=status/scan/persistence/plan/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap install_selfcheck '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `keylogger`

- **域**：`security`（安全）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`privacy_read`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`privacy_read`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：本机输入活动记录：只写本地 jsonl、有 pid 可停、可列可取走，模块内无任何出网路径
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap keylogger '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `llm_redteam`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：LLM 红队矩阵（蒸馏自安全精英课程 + 黑客实验室）：OWASP LLM Top-10 十类 × 检测判据；**只测自己**（提示注入面 / 凭据内插 / 过度代理 / 检索边界 / 预算闸），对第三方攻击载荷一概不做
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap llm_redteam '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `offense_ops`

- **域**：`security`（安全）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**自主渗透编排**（主人令 2026-10-16：pentagi 全部能力→原生）：蒸自 **vxControl/pentagi**（MIT · Go · 30,549 星）的思想—— 多智能体分工（researcher/pentester/coder/reporter）· 工具面（terminal/browser/search/embeddings）· 跨任务记忆 · 证据链与报告。**护栏优先于它的自主性**：五道闸（授权→没范围不动手 · 不可回滚先问 · 凭据只报已配 · 只对授权目标出网 · 无痕即不存在）。op=plan/roles/tools/evidence/memory/gate/check/route（**全只读·零作用域）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap offense_ops '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `omission_detector`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：遗漏检测器：覆盖率 = 已钩住/总数；<100% 触发有界补扫；仍钩不住**如实报 missing**（不许折叠成绿）——零遗漏的唯一裁判
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap omission_detector '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `onboarding_gate`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：未接线能力上手指引门：如实报「登记了但没实现」的缺口，并给出三处接线配方
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap onboarding_gate '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `paywallbuster`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：内容门**检测**（防御侧）：离线判定页面是否被付费墙/同意门挡住，只判不绕（不伪装 UA、不伪造 cookie）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap paywallbuster '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `penetrating_cross_scan`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：穿透式交叉扫描引擎（增强版）：触手到位**必须**调用钩子（未触发=失败）· 步骤锁（跳步当场拒）· 每单元 ≥2 路独立读交叉互扫（不一致→第三路仲裁）· 遗漏检测（覆盖率<100% 有界补扫）· 全程留痕 source_kind=cross_scan；三种目标 bindings/registry/tree:<目录>
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap penetrating_cross_scan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `pentest`

- **域**：`security`（安全）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：授权渗透验证：只对**已登记授权**的目标做非破坏性检查（TCP 可达/TLS 握手/安全响应头），未登记目标一律拒
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap pentest '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `pentest_distill`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**蒸馏件**（不是外挂）：把吞入件 CyberStrikeus/CyberStrike（AGPL-3.0 · 3129★ · TypeScript ·「Open-source AI-powered offensive security harness for automated penetration testing」）的 **Intelligence Layer 四条取法**提炼成我们自己的**授权渗透编排判据**：①阶段聚焦+上下文护栏（一次只推一个阶段）②按发现编排工具（下一步由上一步读数决定，不跑死脚本）③结果结构化归一（门已在做）④**授权范围纪律（我们加严，不是抄的）**：未登记目标一律拒 · AI 不许自发放行。op=tools **现读** `caps_registry.BENIGN_CAPS` 报安全域可编排位（26）与编排通道 omni_plug/mcp_tools/mcp_call/mcp_connect/desktop_commander；op=provenance 逐条指回原话（含**未蒸馏**两行：它的规模 13+ agents / 7600+ skills 不取 · Bolt 远程执行与后渗透**不取**）。**零作用域**：无 subprocess / 无 urllib / 无写盘。边界：接入端 ≡ 我们**已有**的安全位（pentest / sec_* / redteam_*）；本位只蒸取法，**不建平行位**（会撞 新增即清旧）。op=method/tools/provenance/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap pentest_distill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `policy_delta`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：策略影响预检（OpenShell 蒸馏）：**改前先算"会放行什么"**——`tables` 只读三张权限表层（门/预检的只读白名单 + 作用域表）并报**两表分叉**；`propose` 对拟放行动作做只读影响预检（哪些从被收卡变免卡 + **历史账露面次数现读现数** + 风险分级 + 必带「需主人授权」）。🔴 **只读：绝不写 `security/policy.py`**（改它=主人专属）；表读不到 ⇒ fail-closed。op=tables/propose/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap policy_delta '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `redteam_recon`

- **域**：`security`（安全）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：本机侦察面（只读枚举）：监听端口/防火墙三档/本地账号/自启动项/自动服务/凭据落点
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap redteam_recon '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `remote_domain`

- **域**：`security`（安全）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：自有设备中继登记：**公网端点一律拒**，只服务本机/内网设备的中继
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap remote_domain '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `review_gate`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：独立终审位（C-15「验收方 ≠ 产出方」的最小实现 · 2026-10-08 在册）：接线件 `tools/codex-scripts/terminal-review.py`。`review` **只读盘**现算 sha256/字节/空否/BOM/关键词，判据只用非 LLM 四族（file_exists:/contains:/no_error/status_ok，与 longrun._judge 同口径），可选 producer_run 取产出方**自报**与盘上真值逐项对账（背离逐条列；自报一概不采信）；`escalate` 从任务真读数出「五选项 + 决策人 + 期限」；`retro` 冲刺三问；`reflow` 差异化重试（失败数据回流 _prev_error/_prev_attempts/_prev_fingerprints）。**默认零写盘**（只打印读数与判决）；写面一律走**既有账本位**（lr_submit/lr_tick/handoff），不另造第二本账；判据未知一律拒（fail-closed；退出码 0=过 / 1=拒，可当闸）。op=review/escalate/retro/reflow/status/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap review_gate '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `screen_sniff`

- **域**：`security`（安全）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：`privacy_read`
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`privacy_read`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：本机屏幕采集：只写本地 PNG、可列可删，不做出网/OCR/内容解析
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap screen_sniff '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `sec_chain`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：黑客大脑：利用链构建（从漏洞清单推演攻击路径+影响评估）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sec_chain '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `sec_defenses`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：黑客大脑：蓝队防御验证（检查防御措施是否真实生效）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sec_defenses '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `sec_llm`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 要问黑客大脑的问题
- **要哪张票（静态）**：`external_llm`
- **必填载荷**：`prompt` —— 要问黑客大脑的问题
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`prompt`）
- **它做什么**：黑客大脑推理引擎（独立大模型+独立密钥）：abliteration.ai 无限制模型，专用通道不与其他能力混用
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sec_llm '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `sec_scan`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：黑客大脑：漏洞扫描（OWASP Top 10 + CWE 模式库，扫描自有代码）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sec_scan '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `sec_surface`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：黑客大脑：攻击面测绘（用户输入/网络/文件操作/入口点向量分析+风险评分）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sec_surface '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `sec_sweeper`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：安全棒（主人令 2026-09-27）：一根专职安全触手，**每半天**把尺子挨个过唯一门跑一遍 —— 全量穿透式交叉扫描（钩子/步骤锁/交叉验证/遗漏补扫）+ 安全模式分诊（eval/exec/shell/凭据/反序列化…）+ 覆盖无死角 + 双向绑定 + 技能源↔装；结果收成**健康账**，异常即**报警**；**独立健康面板**（快照内联·异常红色置顶）；**专用口**=keys（只引用+掩码）/energy（能源池+免费池真连）/start；**同步记忆上下文**=每棵树记指纹（文件数/最新mtime/总字节），指纹未变则复用上次结果（标 reused），**不重扫**。op=start/sweep/keys/energy/panel/health
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap sec_sweeper '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `social_eng`

- **域**：`security`（安全）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：钓鱼**识别**（防御侧）：12 条规则加权打分 + 落点分类，只判不造、不自动点链接
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap social_eng '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
