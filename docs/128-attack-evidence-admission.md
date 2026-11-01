# 128 · 受攻击举证与交代（没证据不许说被攻击）

> 主人 2026-11-03：「没证据被攻击你怎么给用户交代？」
> 结论：**攻击模式先举证**；没证据就如实说"未发现被攻击证据"，绝不凭感觉宣称被攻击。

## 一、证据类型与门槛（`gbt_allinone/attack_evidence.py`）

| 类型 | 来源 | 强度 |
|---|---|---|
| `auth_denied_burst` | audit.jsonl 中 denied 短时爆发（默认 60s ≥10 次） | **强** |
| `port_scan` | 连接表：同一远端 IP 高频/多端口 | **强** |
| `file_tamper` | 关键文件 hash 与基线不符 | **强** |
| `intrusion_alert` | 主人/外部告警给出的具体入侵描述 | **强** |
| `user_report` | **主人明确陈述"被攻击"**（记录时间戳，作为证据） | 弱（但可进攻击模式） |
| `policy_anomaly` | 策略审计异常 | 弱 |

判定：**强证据 ≥1 → 允许**；只有 user_report → 允许（标注等级）；**什么都没有 → 拒绝**。

## 二、举证记录长什么样

`state/attack-evidence.jsonl` 每条：
```json
{"at":"2026-11-02T03:25:30","kind":"auth_denied_burst","source":"audit.jsonl",
 "detail":"60s 内 denied 50 次","sha256":"63d43…","strong":true}
```
攻击模式记录里带 `evidence_level / evidence_count / evidence_ids(sha256)`，可回溯、可核对。

## 三、没证据时怎么给用户交代（固定话术）

`attack_evidence.explain()` / `respond()` 返回：

> **未发现被攻击证据**。没有日志/连接/hash/主人陈述等证据 → 不能进入攻击模式，
> 更不能对外宣称被攻击；只能继续监控并如实报告"未见攻击证据"。
> 如确有攻击：请用 `--user-report` 记录你的陈述，或先跑取证收集证据。

## 四、CLI

```
# 无证据：会被拒绝（并解释原因）
python tools/incident.py respond --reason "感觉被打"

# 主人陈述（作为证据）
python tools/incident.py respond --reason "被攻击" --evidence "03:30 异常登录" --user-report --apply

# 先取证再判断
python tools/incident.py collect --agents 32
```

## 五、实测

```
test_attack_evidence.py ALL OK：
  无证据 → 拒绝（not_admitted），明说"未发现被攻击证据"，拒绝也写 attack_refused 审计
  主人陈述 → 可进，等级 user_report
  强证据（auth_denied_burst）→ 可进，等级 strong，evidence_ids 带 sha256
  explain() → 结论/证据清单/规则齐全
  respond() 无证据 → 不进入攻击模式，返回交代文案
```

## 六、边界（如实）

- 自动检测目前覆盖 audit denied 爆发 + hash 基线；端口扫描/IP 画像需接真实 IDS/连接表阈值（接口已留）；
- `user_report` 是"主人陈述"证据，不等同技术取证，攻击记录里等级会标 `user_report`；
- 证据不足时**宁可不动**，也不制造"被攻击"叙事。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
