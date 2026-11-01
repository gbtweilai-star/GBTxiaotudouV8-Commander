# 126 · 最高安全策略：黑客能力要终端确认 / 受攻击自我决策 / 转账永远确认

> 主人 2026-11-02 定的三条最高规则：
> 1. **AI 要使用黑客全能力 → 必须主人终端确认才放行**；
> 2. **例外：遭受攻击时 → 极限并发（边防御边找反击机会），最高决策 = GBT小土豆V8 自我判断**；
> 3. **转账 → 任何模式、任何时候都必须主人确认**。

## 一、策略引擎（`gbt_allinone/security_policy.py`）

| 规则 | 判定 | 放行条件 |
|---|---|---|
| **黑客全能力**（security 域 + pentest/redteam/exploit/cross_scan/sec_scan/osint…） | `need_terminal_confirm` | 主人终端 `approve <token>` 后**一次性**放行（绑定能力位、5 分钟 TTL、用一次即失效） |
| **受攻击模式** | `attack_self_decision` | 攻击模式 active 期间，黑客动作由 **V8 自我决策**放行（写 `decider=GBT小土豆V8` 审计） |
| **转账**（transfer/wallet/pay/withdraw…） | `blocked_transfer` | **永远拦**；攻击模式也不放行；必须主人单独确认 |
| 普通/守卫能力 | `allow` | 正常 |

黑客类不含守卫（selfscan/inventory/signature_guard/legacy_guard… 照常跑）。

## 二、终端确认流程（AI 不能自己批准）

```
AI: python tools/confirm-security.py request pentest --reason "授权范围内测试"
  → 输出 token + 终端命令
主人（终端）: python tools/confirm-security.py approve <token>
  → 一次性放行该能力位（5 分钟内有效，用一次即失效）
```

攻击模式（受攻击时由 V8/监控触发，或主人手动）：

```
python tools/confirm-security.py attack-on --reason "被扫描" --evidence "edge 500 conn/s" --ttl 600
python tools/confirm-security.py status
python tools/confirm-security.py attack-off
```

## 三、强制点

- `omni_all` 全开同步执行：逐位先过策略 → `blocked_transfer` / `blocked_by_terminal_confirm` 单列，不算失败；
  攻击模式下放行的位结果带 `self_decision="GBT小土豆V8（攻击模式）"`；
- `profession_dispatch` 派单：候选能力位先过滤，被策略拦下的进 `blocked_by_policy`；
- `console-server`：`POST /api/security/policy`（status/check/request/attack-on/attack-off）；
- UI `#plug`：显示「策略：黑客全能力需终端确认 · 转账永远需确认」，攻击模式红字「攻击模式（V8 自我决策）」。

## 四、实测

```
test_security_policy.py ALL OK：
  黑客默认 need_terminal_confirm · 终端 approve 后 allow 一次 · 第二次又拦
  攻击模式 → attack_self_decision（放行） · 攻击模式转账仍 blocked_transfer
  TTL 到期自动失效 · 审计含 request/approve/consume/attack_on/attack_off/allow_attack
```

## 五、边界（如实）

- 终端确认 token 由 CLI 生成/批准，AI 侧只能 request；**AI 不能 approve**；
- 攻击模式的"最高决策"是 V8 自我判断，但**转账不在此例外内**（硬拦）；
- 攻击模式默认 10 分钟 TTL，防"一直开着"；进入/退出/每次放行都写审计；
- 自动攻击检测（端口扫描/大量 401/异常流量）目前是**接口预留**（enter_attack_mode 可由监控调用），尚未接真实 IDS。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
