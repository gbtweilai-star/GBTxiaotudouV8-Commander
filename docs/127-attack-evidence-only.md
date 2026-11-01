# 127 · 受攻击只采集证据（极限并发取证，不黑客反击）

> 主人 2026-11-02：「我们只是采集证据。」
> 这条定死：受攻击时进入极限并发模式，**只做本机取证与合法防御**，不做任何反入侵。

## 一、只采集证据（`gbt_allinone/attack_forensics.py`）

| 采集器 | 内容 | 用途 |
|---|---|---|
| system | 主机名/平台/CPU/PID/时间/用户 | 环境基线 |
| processes | 全量进程快照（PID/名称/命令行/创建时间） | 找可疑进程/植入 |
| connections | TCP 连接 + **外连 IP 摘要**（排除环回） | 攻击者 IP 画像 |
| audit | audit.jsonl / orchestration-ledger / security-policy-audit / omni-plug | 时间线 |
| recent-files | 近 24h 被改动文件（500 条） | 找篡改/植入 |
| policy | 当前安全策略/攻击模式状态 | 处置依据 |

- **极限并发**：多采集器线程池并行（agents 2–64，默认 32），一次出全部证据；
- **证据链**：`manifest.json` 记录每个文件 sha256 + 采集者 + 保管说明；
- **证据包**：`outputs/forensics/<incident>/` + `<incident>-evidence.zip`（zip 也有 sha256）；
- 只读本机；不改攻击者任何系统。

## 二、极限并发的资源回收

`reclaim_own_workers(apply=False)`：
- 只找**本框架自己的**非必需进程（omni-run / mock_platform / vuln_lab / electron…）；
- 白名单保留 `console-server.py / llama-server / model-bridge / engine`；
- **系统进程、用户进程一律不碰**；`--apply` 才真关；
- 返回候选清单 + 保留数，界面/CLI 可审计。

## 三、受攻击响应（一键）

```
python tools/incident.py respond --reason "被扫描攻击" --evidence "edge log: 500 conn/s" --apply
  → 进入攻击模式（最高决策=GBT小土豆V8，10 分钟 TTL）
  → 回收本框架非必需进程（--apply）
  → 极限并发取证（默认 32 采集器并行）
  → 产出证据目录 + manifest(sha256) + ZIP
```

## 四、明确拒绝（写死）

`counterstrike(op)` 对以下动作一律 `blocked_illegal` 并给法律依据：
接管攻击者电源 / 接管控制台 / 切断键鼠 / 反入侵对方主机 / 销毁对方数据。

> 依据：未经授权访问他人计算机系统违反《网络安全法》第 27 条、《刑法》第 285/286 条。
> 黑客反击（hack-back）会把受害者变成被告，本框架永不实施。

**合法替代**：本机取证、封禁攻击者 IP（本机/安全组）、限速/关端口、诱捕(tarpit)拖住、把证据包交平台/警方/CNCERT。

## 五、实测

```
test_attack_forensics.py ALL OK：
  6 采集器并发 → 证据目录 + manifest（10 个文件 sha256）+ ZIP
  进程快照 24 条 · 连接 71 条 · 近 24h 文件 500 条
  资源回收候选只来自本框架（保留 console-server 等关键进程）
  respond → 攻击模式生效 · 转账仍 blocked_transfer · 黑客能力 attack_self_decision
  power_off/console_takeover/kbm_cut/hack_back → 全部 blocked_illegal + 合法替代清单
  审计含 attack_on
```

## 六、边界（如实）

- 自动攻击检测仍是接口预留（`enter_attack_mode` 可由监控调用），未接真实 IDS；
- 取证是**本机快照**：内存转储/磁盘镜像等深度取证需额外工具与授权（未做）；
- 证据包只在本机 `outputs/forensics/`，提交平台/警方前不要再改动（manifest 会失效）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
