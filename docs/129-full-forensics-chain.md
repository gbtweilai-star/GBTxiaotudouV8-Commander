# 129 · 全量采集 + 证据链

> 主人 2026-11-03：受攻击时要**采集足够证据**、极限并发、全量采集；
> 只做证据链，把攻击者送进大牢。

## 一、采集能力（16 个采集器，极限并发 agents 2–64）

| 采集器 | 文件 | 抓什么 |
|---|---|---|
| system | system.json | 主机/平台/CPU/用户/时间基线 |
| processes | processes.json | 全量进程（PID/命令行/创建时间） |
| connections | connections.json + remote-summary.json | TCP 连接 + 外连 IP 画像 |
| eventlog | eventlog-security.json | Windows 安全事件（登录/失败/权限） |
| services | services.json | 服务状态（可疑服务） |
| scheduled-tasks | scheduled-tasks.json | 计划任务（持久化点） |
| startup | startup.json | 开机自启（持久化点） |
| users | users.json | 本地账户（异常账户） |
| network | netconfig.json + arp.json + dns-cache.json | 网卡/ARP/DNS（横向移动痕迹） |
| firewall | firewall-profiles.json + firewall-rules.json | 防火墙状态（封堵/被改） |
| software | installed-software.json | 已安装软件（后门/可疑软件） |
| memory | memory.dmp 或 memory-unavailable.json | 内存转储（没工具/权限就如实标 unavailable，不伪造） |
| audit | audit-*.jsonl | 审计/账本/策略日志 |
| recent-files | recent-files.json | 近 24h 被改文件（篡改/植入） |
| timeline | timeline.json + timeline.md | 合成事件时间线（给警方看顺序） |
| policy | policy-state.json | 当前安全策略/攻击模式 |

## 二、证据链规格（可校验、可交法庭）

```
每个文件: sha256
哈希链:  chain_i = sha256(chain_{i-1} + sha256(file_i))   ← 改一个文件，链就断
根哈希:  chain_root（manifest.json）
证据索引: evidence-index.md（文件清单 + 根哈希 + 法律声明）
保管链:  chain_of_custody（采集者/机器/时间/哈希）
打包:    <incident>-evidence.zip（zip 也有 sha256）
```

实测：**16 采集器 / 26 个文件 / 24 链环 / chain_root 3a9db466… / 4.9 秒**。

## 三、极限并发的资源腾挪

- `reclaim_own_workers(apply=False)`：只关**本框架自己的**非必需进程
  （omni-run / mock_platform / vuln_lab / electron…），白名单保留 console-server/llama-server/engine；
- 返回**内存预算**：`free_mb_before / free_mb_after / freed_mb`；
- **系统进程、用户进程一律不碰**（要关需主人确认，不擅自动别人的进程）；
- 采集线程池 agents 可到 64，采集器并行跑。

## 四、处置范围

`counterstrike(power_off / console_takeover / kbm_cut / hack_back)` → **blocked_illegal**（超出处置范围）。
**证据链才是定罪材料**。

**合法动作**：证据包 + 时间线 + 哈希链 → 报警/CNCERT/平台安全团队；
封禁攻击者 IP（本机防火墙/安全组）；限速/关端口；诱捕拖住继续取证。

## 五、实测

```
test_attack_forensics.py ALL OK：
  16 采集器 / 26 文件 / 哈希链 24 环 / evidence-index.md / timeline.md+json
  内存预算 free_mb_before>0 · 回收候选只来自本框架 · 关键进程保留
  respond → 攻击模式（强证据级）+ 取证包
  power_off/console_takeover/kbm_cut/hack_back → 全部 blocked_illegal
test_attack_evidence / test_security_policy 全过
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
