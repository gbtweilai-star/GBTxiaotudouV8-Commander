# 121 · 平台 scope 导入（离线，必须人工确认）

> 主人 2026-11-02：「下一步」——把 HackerOne / Bugcrowd 项目 scope 结构化导入，接真实平台前的最后一环。

## 一、导入器（`gbt_allinone/scope_import.py`）

支持两种平台格式 + 一种已归一化格式：

| 来源 | 结构 | 归一化 |
|---|---|---|
| **HackerOne** | `{program, scopes:[{asset_identifier, asset_type, eligible_for_bounty}]}` | URL 去协议/路径；`*.host` 去通配；IP 保留；`eligible_for_bounty=false` → **out（保守）** |
| **Bugcrowd** | `{program, targets:{in_scope:[], out_of_scope:[]}}` | website/api 归一化为域名；network 转 CIDR；out 支持对象或纯字符串 |
| 归一化 | `{name, scope[], out_of_scope[]}` | 直接校验 |

示例文件（**虚构，仅供演示**）：`data/scope-samples/hackerone-sample.json`、`bugcrowd-sample.json`。

## 二、合规口径（写死）

1. **默认 dry-run**：只给预览（name/scope/out/authorization_ref），**不落库**；
2. **confirm=True 才建项目**，`authorization_ref` 自动写 `imported from <platform> program <handle> — 需人工核对授权`；
3. **空 scope 拒绝**（不造空项目）；
4. 只能读**仓库内** JSON 文件（路径校验），不联网、不访问平台 API。

## 三、实测

```
HackerOne 示例归一化：www.example.com / api.example.com（去 *）/ 203.0.113.10
                      intranet.example.com（bounty=false）→ out；mail.example.com（显式 out）保留
Bugcrowd 示例：shop.example.net / api.example.net / 198.51.100.0/24；out: pay.example.net / status.example.net
dry-run 不落库 ✓   confirm 建项 ✓（id=acme-vdp，授权依据含 hackerone + 需人工核对授权）
范围闸：in-scope 允许、通配域允许、IP 允许；out-of-scope/bounty=false/外部域 全拒绝
空 scope 拒绝 ✓
tests/test_scope_import.py ALL OK
```

## 四、界面

`#bounty` 新增「导入示例 scope」按钮：先 dry-run 出预览 → 浏览器确认后才落库 → 刷新项目列表。
接口：`POST /api/bounty {"op":"scope_import","file":"...","confirm":false|true}`。

## 五、边界（如实）

- 示例是虚构项目，**不能拿去测真实资产**；真实项目要替换 JSON 并人工核对授权；
- 平台导出字段会变，解析器认不出时**拒绝**而不是猜（宁可漏，不越界）；
- `eligible_for_bounty=false` 一律按 out（保守），即便平台语义是"仅 VDP"。

## 六、下一步

1. 接真实平台导出（用户提供 JSON）→ dry-run 核对 → confirm 建项；
2. 报告模板加 CVSS 环境分 + 修复 diff；
3. 提交状态接平台 API（可选、只读）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
