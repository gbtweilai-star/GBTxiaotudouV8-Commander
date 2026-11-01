# 120 · 赏金报告升级 + 提交追踪（可直接投）

> 主人 2026-11-02：「下一步」——先把报告打磨到能直接提交，再接外部平台。

## 一、报告升级能力

| 能力 | 实现 |
|---|---|
| **CVSS 3.1 评分** | `bounty_core.cvss3(vector)`：按 3.1 base 公式算分（含 Scope Changed），自动给严重度；无向量时按严重度给默认向量并算分 |
| **CWE 映射** | 10 个常见 CWE（79/89/22/200/306/639/693/78/352/918）带中文名与修复建议；未收录如实标"未收录" |
| **复现命令** | 报告含 ```bash``` 段（finding.repro，未填则给占位并提醒补） |
| **修复建议** | finding.remediation，未填则自动用 CWE 的标准修复建议 |
| **证据可核** | 每个证据文件 sha256；报告另存侧车 JSON（finding+program+报告 sha256） |
| **提交建议** | 报告末段写平台、提交前检查项（scope/证据/复现） |

报告路径：`outputs/bounty/<finding>.md` + `<finding>.json`。

## 二、提交追踪状态机

```
draft → submitted → triaged → paid → closed
        ↘ duplicate → closed
        ↘ closed
```
- 非法流转**硬拒绝**（例：`draft → paid` 会被拒并列出允许的下一状态）；
- 状态事件追加写 `state/bounty/status.jsonl`（可回放）；
- `submit()` = 转 submitted 并记平台/链接；
- summary 统计 `by_status`、`avg_cvss`、`payout_total`。

## 三、实测

```
CVSS 3.1：9.8 / 8.8 / 6.1 / 0.0 四组标准向量全对上
CWE-79 → 跨站脚本（XSS）+ 标准修复建议
报告：CVSS 段/CWE 段/复现命令/修复建议/证据 sha256/提交建议/侧车 JSON 全在
状态机：draft→paid 拒绝（提示允许 submitted/closed）；submit→triaged→paid 通过
summary：by_status 计数 + avg_cvss + payout_total
tests/test_bounty.py ALL OK（含 CVSS/CWE/报告段/状态机 断言）
```

## 四、界面（`#bounty`）

发现卡显示：目标 · CWE/名称 · **CVSS 分数** · **状态** · 证据数；按钮：**生成报告**、**提交**（弹平台名，转 submitted）。
顶部 KPI：项目数 / 发现数 / 各严重度 / **各状态** / **平均 CVSS** / 赔付账本。

## 五、边界（如实）

- CVSS 只算 **base**（不碰 temporal/environmental）；平台若要求环境分需补；
- CWE 表是常见 10 类，未收录走通用建议；
- 状态机是本地账本，平台真实状态仍需人工同步（下一步可接平台 API）。

## 六、下一步

1. **平台 scope 导入**（HackerOne/Bugcrowd 项目 JSON → 建项目，人工确认授权）；
2. 报告模板再升级：CVSS 环境分、修复补丁 diff、复现视频/截图附件；
3. 提交追踪接平台 API（可选，需 token 且只读）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
