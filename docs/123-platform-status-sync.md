# 123 · 平台状态只读同步（提交后自动回填）

> 主人 2026-11-02：「下一步」——提交后平台会改状态（triaged/duplicate/paid），本地只读回填。

## 一、只读口径（写死）

- 只发 **GET**；mock 平台对 POST/PUT/DELETE 一律 **405**（测试验证）；
- 真平台必须显式 token（env），没 token 直接拒绝；
- 状态回填走**本地状态机**（`draft→submitted→triaged→paid→closed`），非法流转会被拒；
- 每次同步写 `state/bounty/platform-sync.jsonl` 审计；
- 404（平台没有该报告）归 `skipped`，不算失败。

## 二、实现

`gbt_allinone/platform_sync.py`：

| 能力 | 说明 |
|---|---|
| provider | `mock`（本地靶场，默认）；`hackerone` / `bugcrowd` 需填 token_env + base_url |
| 状态映射 | new/submitted/open→submitted；triaged/accepted/valid→triaged；duplicate→duplicate；resolved/fixed/paid→paid；closed/informative→closed |
| 状态机路径 | BFS 求最短合法路径（例 submitted→paid 会走 submitted→triaged→paid） |
| dry-run | 默认；只出计划不改状态 |
| 过滤 | 可只同步某个 program |

mock 平台：`tools/lab/mock_platform.py`（只读 GET、Bearer token、map 驱动状态）。

## 三、实测

```
mock 平台：/healthz 在线；triaged/duplicate/paid 三个状态映射正确
dry-run：3 条计划（triaged / duplicate / triaged→paid），状态未变
apply：3 条回填成功（triaged / duplicate / paid），审计日志写入
只读：POST/PUT/DELETE → 405
异常：未知 provider 拒绝；缺 token 拒绝（明说 env 名）
tests/test_platform_sync.py ALL OK
```

## 四、界面与接口

- `#bounty` 新增「**同步平台状态**」按钮（只读 mock 同步，带确认框）；
- 接口：`POST /api/bounty {"op":"platform_sync","provider":"mock","confirm":false|true}`；
- 巡检标记：`data-platform-sync = ok:<检查数>:<回填数>`。

## 五、边界（如实）

- mock 平台是本地模拟；真平台 API 字段/鉴权不同，接真平台要按它文档填 base_url/token；
- 同步只回填状态，不拉平台评论/附件（避免把平台数据带进本地）；
- 状态机不可达的组合会跳过并写原因，不硬塞。

## 六、下一步

1. 真平台字段适配（HackerOne/Bugcrowd API 文档）；
2. 拉平台评论/复核意见（只读）回填到报告；
3. 赔付与平台 reward 对账。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
