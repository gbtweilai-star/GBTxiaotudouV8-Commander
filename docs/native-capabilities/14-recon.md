# 14 · 侦察域 (`recon`)

> 5+ 能力位 · OSINT扫描 · 自适应抓取 · 知识图谱 · 技能蒸馏
>
> 只对授权与公开面侦察，隐私脱敏，采集物不外发。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单

| 能力位 | 说明 |
|---|---|
| `osint_scan` | OSINT扫描（DNS/WHOIS/子域名/端口/指纹/邮箱/IP归属/社交） |
| `spider_ops` | 自适应抓取编排（多候选路径+结构指纹+相似度回找） |
| `know_map` | 理解任何事（仓/库/文档→分层知识图） |
| `skill_forge` | 技能蒸馏五式（女娃/雷达/同事/前任/反蒸馏） |
| `tentacle_learn` | 触手扫描·采集·学习（scan→collect→extract→learn） |
| `recon_distill` | 侦察知识蒸馏 |
| `arxiv` | ArXiv论文检索 |

## OSINT扫描

### 七维扫描

| 维度 | 内容 |
|---|---|
| DNS | A/AAAA/MX/TXT/NS/CNAME记录 |
| WHOIS | 注册人/注册商/到期时间 |
| 子域名 | 字典爆破+证书透明日志 |
| 端口 | 常见端口扫描（21/22/80/443/3306/6379...） |
| 指纹 | 服务器类型/框架/CMS识别 |
| 邮箱 | 页面邮箱提取+格式推断 |
| IP归属 | ASN/地理位置/反查域名 |

### API参考

```python
import gbt_allinone as gbt

result = gbt.run_task("osint_scan", {"target": "example.com"})
# 返回: {
#   ok, target: "example.com",
#   dns: {A: ["93.184.216.34"], MX: [...], TXT: [...]},
#   whois: {registrar: "...", created: "...", expires: "..."},
#   subdomains: ["www.example.com", "mail.example.com"],
#   ports: [{port: 80, state: "open"}, {port: 443, state: "open"}],
#   fingerprint: {server: "nginx", framework: "..."},
#   emails: [],
#   ip_owner: {asn: "AS15133", geo: "US"}
# }
```

### 安全护栏

**默认拒内网**：目标为内网/环回/保留地址时直接拒绝。

```python
# 内网目标 → 拒绝
gbt.run_task("osint_scan", {"target": "192.168.1.1"})
# 返回: {ok: false, status: "denied", reason: "内网目标需人工授权"}

# 授权后可扫
# 终端执行: python -m gbt_allinone auth grant --scope osint_private --ttl 600
gbt.run_task("osint_scan", {"target": "192.168.1.1", "allow_private": True})
```

## 自适应抓取（spider_ops）

**核心是adaptive**：页面结构一变选择器就废 ⇒ 多候选路径 + 结构指纹 + 相似度回找。

```python
# 计划
gbt.run_task("spider_ops", {"op": "plan", "url": "https://example.com/list"})
# 返回: {ok, selectors: [...], structure_fingerprint: "..."}

# 抓取
gbt.run_task("spider_ops", {"op": "fetch", "url": "...", "selectors": [...]})

# 自适应解析（结构变了也能找回）
gbt.run_task("spider_ops", {"op": "adaptive", "html": "...", "fingerprint": "..."})
```

### 边界

- 只抓授权/公开目标
- 遵守robots与条款
- 不绕验证码
- 不撞库
- 不抓个人隐私
- 每条数据可指回URL与时间

## 知识图谱（know_map）

把任何仓/库/文档变成一张**可点、可搜、可问的分层知识图**。

```python
# 扫描
gbt.run_task("know_map", {"op": "scan", "path": "."})
# 返回: {ok, files: 598, entry_points: [...]}

# 建图（每条边带evidence = path:line）
gbt.run_task("know_map", {"op": "build", "path": "."})
# 返回: {ok, nodes: 6301, edges: 9120, layers: 3}

# 导览
gbt.run_task("know_map", {"op": "tour"})

# 检索
gbt.run_task("know_map", {"op": "ask", "q": "鉴权在哪里"})

# 变更影响
gbt.run_task("know_map", {"op": "impact", "file": "gbt_allinone/api.py"})
```

## 技能蒸馏五式（skill_forge）

| 式 | 来源 | 说明 |
|---|---|---|
| **女娃** | nuwa-skill | 不是复制人、是提炼思维框架（心智模型/决策启发式/表达DNA/边界） |
| **雷达** | last30days | agent主导搜索、按投票与真实金额计分（非编辑评分） |
| **同事** | distilly | 经验/对话→可复用技能 |
| **前任** | ex-skill | 原材料→说话方式DNA |
| **反蒸馏** | anti-distill | 交出版消毒+私有备份留核心 |

### 边界

- MIT只蒸思想
- **隐私**：原材料不外发、第三方脱敏、不做人脸声纹建模
- **不冒充真人**

## 触手学习（tentacle_learn）

四步闭环：**scan → collect → extract → learn**，末尾**复验**"真的进了语料/可被现读"。

| 面 | 内容 |
|---|---|
| 能力面 | 本机能力位 |
| 页面面 | 网页结构 |
| 文件面 | 本地文件 |
| 设备面 | 硬件设备 |
| 网面 | 只对授权域 |

**红线**：只扫/只采授权与公开面 · 隐私脱敏 · 采集物与语料不外发 · 每步留痕 · 拿不准的不进learn

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
