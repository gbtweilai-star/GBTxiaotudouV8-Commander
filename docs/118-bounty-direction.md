# 118 · 方向转向：安全研究 / 赏金工作台（合规优先）

> 主人 2026-11-02：「这套设计如果拿来正规挖洞赚钱呢？」
> 答案：**天生合适，但必须先有授权范围闸**。这一轮把「正规挖洞」的合规底座与工作台落地。

## 一、为什么这套设计适合（不是硬蹭）

已有底座全部能复用：
- `penetrating_cross_scan`：无死角交叉扫描（coverage=1.0、dead_spots=0、疑点→反思→穿透）；
- `security` 30 能力位、`recon` 18、`code_audit`/`review_gate`、`vision` 全谱（截图/定位）；
- 审计账本 + 证据固化（截图/哈希）+ 职业（安全/穿透）+ 职业路由 + 派单闭环；
- 21 种触手职业里，"安全/穿透"与"编程/审查/测试"正好覆盖漏洞挖掘与复现。

## 二、合规红线（写死在代码里，bounty.py）

| 红线 | 实现 |
|---|---|
| 没有授权 = 不建项 | `add_program()` 缺 `authorization_ref` 直接拒绝 |
| scope 外 = 硬拒绝 | 域名后缀/`fnmatch` + IP/CIDR 判定；`out_of_scope` 优先否决 |
| 范围外发现 = 拒录 | `add_finding()` 先过 `check()`，不过就不允许记录 |
| 证据可核 | 报告里每个证据带 `sha256`，改过即对不上 |
| 赔付只记账 | `payout()` 只写账本，**不收钱不转账**（转账是主人的事） |
| 本模块不扫网络 | 只做范围/账本/报告；真扫描仍走安全能力位，且必须先过范围闸 |

## 三、工作台（`#bounty`）

- **项目**：授权项目列表（平台/scope/out_of_scope/授权依据/赏金范围）；
- **范围检查**：选项目 + 填目标 → 允许/拒绝当场显示（`data-scope-check`）；
- **发现**：标题/严重度/CWE/CVSS/步骤/影响/修复/证据（文件 sha256）；
- **报告**：一键生成 Markdown 报告到 `outputs/bounty/`（含授权依据与 sha256）；
- **赔付账本**：只记录金额与状态，不做收付款。

接口：`POST /api/bounty`，`op = summary | check | add_program | add_finding | report | payout`。

## 四、实测

```
无授权建项 → 拒绝（缺 authorization_ref）
自有靶场建项 own-lab（scope: 127.0.0.1/localhost）
  → 127.0.0.1 允许 · example.com 拒绝（不在 scope）
越界发现 → 拒录
范围内发现 + 证据 → 报告生成（输出目录 outputs/bounty/，证据 sha256 与文件一致）
赔付 0 USD → 账本 +1（notice: 仅账本记录）
页面 #bounty：data-bounty = ok:1项目:1发现；范围检查按钮在；外部域检查显示"拒绝"
tests/test_bounty.py ALL OK（授权闸/范围闸/发现/报告/赔付 全链路）
```

## 五、赚钱路径（合规）

1. **公开赏金平台**（HackerOne / Bugcrowd / YesWeHack / 各厂商 VDP）：只做平台声明的 in-scope 资产；
2. **授权渗透测试服务**：签 ROE（Rules of Engagement）→ 用本工作台建项目、跑 case、出报告；
3. **漏洞复现/报告代写**：帮团队把已发现的漏洞整理成可 triage 的报告；
4. **安全巡检订阅**：对自有资产做周期性无死角扫描 + 报告（可挂到认知界面看板）。

**禁止**：未授权扫描、越界测试、破坏性验证、拿别人数据。这三条不是建议，是 `bounty.py` 的硬拒绝条件。

## 六、路线图（下一步）

1. **自训靶场**：本机搭 DVWA/juice-shop 靶场，用工作台跑通 recon → finding → report 全流程（无外部目标）；
2. **平台 scope 导入**：把 HackerOne/Bugcrowd 项目 scope 结构化导入（仍人工确认授权）；
3. **报告模板升级**：CVSS 计算、CWE 映射、复现命令、修复补丁建议；
4. **提交追踪**：findings 状态机（draft→submitted→triaged→duplicate→paid）+ 赔付账本对账；
5. **只读侦察管线**：子域/指纹/端点发现全部走 safe 能力位，破坏性验证一律要票。

## 七、边界（如实）

- 本工作台**不是扫描器**：它管授权/范围/发现/报告/赔付；扫描靠既有安全能力位（且要过范围闸）；
- scope 匹配是域名/IP 层，不覆盖"逻辑漏洞"的授权判定，那要人工看 ROE；
- 报告质量取决于发现质量；真正的收入来自"能复现、影响说得清"的报告。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
