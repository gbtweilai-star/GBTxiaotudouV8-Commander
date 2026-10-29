<p align="center">
  <a href="https://github.com/gbtweilai-star/GBTxiaotudouV8moxing">
    <img src="assets/brand/repo-banner.png" alt="GBT小土豆V8 · 独立数字人框架" width="100%">
  </a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-%E2%89%A5_3.10-7C4DFF">
  <img alt="核心依赖" src="https://img.shields.io/badge/Core-stdlib_only-22C55E">
  <img alt="能力位" src="https://img.shields.io/badge/Caps-295-F5B041">
  <img alt="职业域" src="https://img.shields.io/badge/Domains-30-00E5FF">
  <img alt="测试用例" src="https://img.shields.io/badge/Tests-2640-3F4759">
  <img alt="语言" src="https://img.shields.io/badge/Lang-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-9AA4C4">
</p>

<p align="center">
  <b>独立数字人框架</b>：统一入口 <code>run_task</code> · 全行为落审计账 · 能力位现读可核<br>
  <sub>开发者：自由的风 · 本署名不可删除、不可篡改归属</sub>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#结构">结构</a> ·
  <a href="#测试">测试</a> ·
  <a href="docs/">文档</a> ·
  <a href="#开发者署名（每一页，禁止删除）">署名</a>
</p>

---

# GBT小土豆V8 · 独立私人框架

> V8.0.0 · 独立私人框架，与任何企业公司无关。
> 融合 AutoClaw 桌面形态 + GBT小土豆 能力体系，统一接口 + 统一可审计数据后台。
> Python ≥ 3.10 · 核心仅标准库（桌面壳需 customtkinter + tkinter）。

## 为人处世三律（写在框架最前面）

1. **听从指令** — 用户指令第一，不揣测、不代答、不擅自扩大或缩小任务范围。
2. **给意见** — 完成后主动给出专业判断：风险在哪、更好的做法是什么、下一步建议什么。
3. **一起想办法** — 遇到阻塞不甩锅、不空手而归，带着方案回来让用户挑。

拒绝的永远只是具体行为的风险，不是这个人：说清楚为什么不行，再给出怎样才行。

## GBT 钢印

框架执行产出的结果默认携带 `gbt_stamp`（框架名 / 版本 / GBT 标记 / 独立归属声明）。
钢印不可伪造归属，不可移除出处；`run_task(kind, payload, stamp=False)` 可显式关闭。
所有钢印产物与任何企业公司无关。

## 结构

```
Autoclaw/
├── autoclaw.py           # CLI 入口
├── Autoclaw.bat          # Windows 快捷启动
├── src/
│   ├── core/
│   │   ├── scanner.py    # OSINT 扫描核心（DNS/WHOIS/子域名/端口/指纹/邮箱/IP/社交）
│   │   └── guard.py      # 目标安全校验（默认拒绝内网/环回，可显式放行）
│   └── ui/               # 桌面 GUI 层
└── gbt_allinone/         # V8 框架核心
    ├── __init__.py       # 导出 run_task / list_capabilities / SOUL / stamp_result
    ├── api.py            # 统一接口（全行为落审计 + 默认 GBT 钢印）
    ├── soul.py           # 为人处世理念 + 钢印机制
    ├── caps_registry.py  # 能力注册表（良性白名单 + 危险禁用名单）
    ├── store.py          # JSONL 审计后台
    ├── cli.py / app.py   # CLI 壳 / 桌面壳
    ├── ledger/ wallet/   # 内部账本 / HD 钱包 / 链上只读
    └── tests/            # 测试（52 项）
```

## 快速开始

```powershell
# CLI：列出能力 + 审计条数
python -c "import sys;sys.path.insert(0,'.');from gbt_allinone.cli import main;main(['list'])"

# OSINT 扫描（公网目标，全程落审计，结果带 GBT 钢印）
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as gbt, json;print(json.dumps(gbt.run_task('osint_scan',{'target':'example.com'}),ensure_ascii=False)[:500])"

# 桌面壳（在役壳：holo_pet_w3 的 Electron 壳 + 127.0.0.1:8765 网页面板）
#   2026-10-15 更正：旧文档指的 launch-gui.ps1 **不存在**（Test-Path=False），已换成真入口
cd holo_pet_w3 ^&^& npx --no-install electron shell/main.cjs
```

安装依赖：`pip install -r requirements.txt`（customtkinter / darkdetect / dnspython）

## 并发实测（≥20000 根触手 · 零失败）

<img src="assets/brand/concurrency-card.png" alt="并发容量实测读数卡：1024→20000 根，六级零失败" width="100%">

上面这张是**读数卡**（脚本渲染，不是终端截图）—— 数字全部来自 `state/concurrency-last.json`，
而那个 JSON 由测试脚本自己落盘：

```bash
py -3.14 -X utf8 tools/codex-scripts/concurrency-capacity-test.py \
    --levels 1024,4096,8192,10000,16384,20000 --json state/concurrency-last.json
py -3.14 -X utf8 tools/codex-scripts/render-concurrency-card.py     # 由读数渲染证据卡
```

口径（写死的三条）：① 单位动作是**真实过门的一次能力位调用**（`comfy_native` 的只读 `status`），
`probe=True` 只是**不写审计台账**，用来先量"纯调度上限"；② 线程池一次开满 N —— **"首次建线程"的成本
落在第一个大批量那一行**，所以看后面的行才是稳态；③ **失败就是失败**，列样例，不折叠成"波动"。

**当前读数**（宿主可用内存只有 **1.86 GB**）：`20000/20000 成功 · 墙钟 4,295 ms · 单发中位 0.2 ms ·
可用内存 1.91→1.78 GB` —— 20,000 根同发**零失败**，内存基本不动。
容量登记与历次读数见 [`docs/并发容量登记.md`](docs/并发容量登记.md)。

## 能力边界（现读口径 · 2026-10-12 更正）

**先纠正一句旧话**：本仓曾把这一节写成"禁止类能力"的口径 —— 那是**过期描述**，
现读事实与此不符，已按盘上真身改写（Owner 2026-09-23「把禁止全部解开」仍生效）。

- **没有"按名禁用"的能力**：`DISABLED_CAPS = 0`。历史上那 11 个名字只登记在
  `UNIMPLEMENTED_CAPS`，**只有名字、没有实现** —— 调用得到的是 `unknown capability`，
  **不是"被安全策略挡住"**（两者差别很大，别念错）。
- **真正把关的是"授权门"**：`gbt_allinone/security/policy.py` 的 15 个作用域
  （付款／隐私／生产写入／远控／发声／出网…）。授权**只能主人在终端发放**：
  `python -m gbt_allinone auth grant --scope <作用域> --ttl <秒>`；
  **AI 永远无权给自己发授权**，缺哪个就如实报哪个。
- **门是"主人的开关"，不是"技术限制"**：门开着，技术全在。
- 只读类（`mirror_scan` / `mirror_status` 等）不需要授权。
## 数据后台（可追踪）

- `gbt_allinone/store/audit.jsonl`：call / ok / error / denied 全程落盘。
- 查询：`gbt.query_log(event=None, limit=N)`；计数：`gbt.log_count()`。

## 测试

```powershell
python gbt_allinone\tests\test_framework.py   # 52 项：钢印/理念/引擎/管线/防复发/调度/巡检/长程/察言观色/体检层/触手
```

## 万能插执行引擎（替代子代理）

V8 立场：框架内不依赖子代理。脑子只有一份（SOUL + run_task），手有很多只（引擎线程池）。

- `wf_define`：定义 DAG 工作流（校验环/依赖/能力合法性）
- `wf_run`：分层并行执行，`{{node.path}}` 模板注入上游输出，fail-fast 如实报错
- `wf_status`：运行记录查询

## 生产管线（唯一交付通道）

所有产物必须走：镜像多维度空间 → 门禁审计（完整性/归属/审计/策略）→ 生产写入。

- `pipeline_submit`：三阶段一次跑完；过闸 → 原子写入生产区 + 护照 + GBT 钢印；不过 → 隔离区 + 如实报原因
- `pipeline_status`：发布/阻断全留痕
- `ghost_guard`：防复发检测——幽灵目录/备份散件/攻击残留/注册表冲突，任何一项回来立即报警

无人值守闭环：`wf_define`（编排）→ `sched_define`（定时）→ `sched_tick`/`run_forever`（自动执行）→ `pipeline_submit`（生产发布）→ `svc_inspect`（巡检留痕），整条链路零人工按钮。


## 触手金钥匙（连接大脑执行层的眼睛与双手）

- \	entacle\：统一调用触手的 66 项能力（see / read_text / click / type / list_windows / process_list / clipboard / chain / monitor…）
- \	entacle_manifest\：能力总纲 + 三通道感官 + 六铁律（先看再动/动后等稳定/找不到就滚/遇弹窗必关/每步亲眼验证/不确定就对比）
- \	entacle_status\：自诊断（依赖分层 ctypes/mss/uiautomation/dxcam + 10 邻域覆盖）
- 视觉 DXGI 硬采热路径 28-34ms/帧；硬件层原样迁移（SHA256 与原版一致），每次调用落审计 + GBT 钢印

## 触手金钥匙（连接大脑执行层的眼睛与双手）

- `tentacle`：统一调用触手的 66 项能力（see / read_text / click / type / list_windows / process_list / clipboard / chain / monitor…）
- `tentacle_manifest`：能力总纲 + 三通道感官（视觉 DXGI 直读显卡帧缓冲 / 听觉 WASAPI 回环 / 操作 UIA 穿透）+ 六铁律（先看再动/动后等稳定/找不到就滚/遇弹窗必关/每步亲眼验证/不确定就对比前后截图）
- `tentacle_status`：自诊断（依赖分层 ctypes/mss/uiautomation/dxcam + 10 邻域覆盖映射）
- 视觉 DXGI 硬采热路径 28-34ms/帧；硬件层原样迁移（SHA256 与原版一致）；每次调用落审计 + GBT 钢印

## 吞天（自我进化：吞噬 GitHub 仓库 → 知识胶囊 → 反思重组）

- \devour_github\：吞噬任意 GitHub 仓库（README+代码 → 6222 字知识胶囊，实测吞了 2702 stars 的 slugify）
- \devour_scan\：能力缺口扫描（77 能力域覆盖对照，进化方向自检）
- \devour_reflect\：反思（回顾吞噬历史，发现弱能力与重组机会）
- \devour_pulse\：完整认知循环（吞噬→反思→消化→重组→进化）
- 吞噬产物走镜像管线发布（门禁+版本化+审计），知识注入触手已知问题库
- 复活工程：旧 brain 依赖全部 V8 化（gatekeeper→pipeline、脑委会→llm 桥、神经触手→触手桥、nexus→selfscan）

## 推演环（think_loop：完整心智循环）

下达任务 → 她自己走完七步（每步真实执行、留痕）：

| 步 | 名称 | 做什么 |
|---|---|---|
| 1 | 理解 | LLM 复述任务+约束（防理解偏差，只出理解不出代码） |
| 2 | 推演 | 方案在镜像维度 dry-run（假设/模拟不碰现实） |
| 3 | 执行 | 万能插真跑（调用工具） |
| 4 | 纠错 | 失败自动诊断根因（LLM 提案）→ 带诊断重试 |
| 5 | 反向延伸 | 结果反推：下一步工作 + 最脆弱一环 |
| 6 | 反思进取 | 领悟提炼落盘（polish_insights 永久资产） |
| 7 | 整理 | 结构化结果 + 审计留痕 |

调用：`g.run_task('think_loop', {'goal': '...任务描述...'})`

## 一指定江山乾坤换位 + AI 接管部署队列

所有假设/架构试验/反复修改全部关在镜像部署区；生产只接受验证通过后的一次性全量晋升——零修改、零污染、一步到位。

- `one_key_deploy`：抓取(GitHub/本地) → 镜像 → 署名注入 → 验证矩阵 → 一次性晋升，**一条命令 3 秒上线**（实测 todomvc 28957★ 14 文件）
- `mirror_shape/scan/ascend/status/rewind`：镜像空间五维操作（维度成形随便改 / 维度体检 5 项矩阵 / 跨维晋升+护照+时间线 / 现实漂移检测 / 时间线回滚）
- `deploy_queue`：AI 接管队列——submit 入队 / tick 部署下一个（**完一个自动下一个**）/ status 全景
- 生产零修改纪律：晋升后生产区任何变动 = 漂移（对照护照逐文件指纹），ghost_guard 级报警

## 原生视觉传输总线（眼睛也上传输层）

视觉不是孤立快照——眼睛的每一帧都可缓存、可定位、可回放、可进流水线：

- `vision_snapshot`：感知指纹（aHash）快照缓存，同画面零成本复用（JPEG 编码噪声免疫）
- `vision_diff`：变化区域定位——网格块哈希给出**变化矩形**（归一化坐标），非只说"变了"
- `vision_stream_record`：视觉流帧时间线落 store（指纹+变化标记），可统计
- `vision_stream_replay`：流回放 + 变化段提取
- 断头路修复：`brain.gatekeeper` 垫片补齐，截图显式落盘走 V8 镜像管线（channel=mirror_pipeline）
- 增量修复：视觉总线强制全屏帧（omni_core 的 delta 局部图会破坏对比语义——这也是 tentacle_see 偶发失败的根因）

调用：`g.run_task('tentacle', {'action': 'vision_diff'})`

## 万能插：核心传输工具（传输层进化）

万能插不只是"能跑 DAG 的执行器"，而是框架的核心传输工具——能力之间的数据流动有形状、有复用、有路由、有层级。

| 传输能力 | 说明 |
|---|---|
| 扇入聚合 | `{{*}}` 收集全部上游；`{{*.gbt_result.result.words}}` 收集多路上游字段成列表 |
| 数据算子 | `transfer` 能力：map/filter/merge/unique/sort/limit/pluck/collect/flatten/split/join/rename/wrap/stats（14 个纯变换） |
| 传输缓存 | 节点 `cache: true` —— 同 (kind, 参数指纹) 命中即复用，`cache_ttl` 秒 |
| 条件分流 | 节点 `routes: [{when, kind, params}]` —— switch 语义取首个命中分支 |
| 层级传输 | 工作流当节点嵌套（`kind: wf_run`），深度保护 5 层 |
| 快速值 | 模板支持列表下标：`{{node.result.items.0.name}}` |

## 黑客大脑 · 融合强化（吞天消化开源智慧）

- 吞噬三大平台诊断项目：bandit(8257★)/semgrep(16583★)/gitleaks(29223★)
- 检测模式库 10 → **25 条**（+15 类高价值检测）：
  - 密钥泄露（gitleaks 智慧）：AWS Key / GitHub Token / LLM API Key / 私钥块 / Slack Token
  - 危险调用（bandit 智慧）：subprocess shell=True(B602) / tempfile.mktemp(B108) / assert 安全校验(B101) / 弱哈希 md5/sha1(B324) / requests verify=False(B501) / Flask debug(B201) / Jinja2 无转义(B701)
  - 逻辑缺陷（semgrep 智慧）：str.format 拼接 SQL / chmod 777
- 实测：融合样本 13/13 全命中；框架自扫抓到 3 处真病灶（B602）并当场修复
- 误报治理：占位符豁免 + 模式库自引用豁免

## 开发者署名（每一页，禁止删除）

- 开发者：**自由的风** —— 框架每一页（文档/网页/产物）自动携带署名，禁止删除、禁止篡改归属
- `signature_guard` 能力：扫描全框架页面署名完整性，缺失即报，restore=true 自动补回
- 管线发布时文本/网页产物自动注入署名；file_hygiene 铁律 9 顺带管署名
- 日常：`g.run_task('signature_guard', {'restore': True})`

## 万能插执行引擎（延伸：四把节点级武器）

- `timeout`：节点超时秒数，超时如实报错，不拖垮整个工作流
- `when`：条件执行表达式（AST 白名单求值，安全），不满足则跳过、不算失败
- `fallback`：降级回退，主能力最终失败时改走备选能力（带 gbt_fallback 标记）
- `retry_backoff`：重试退避秒数（配合 max_node_retries）

## 文件家规与自愈

- \LAYOUT.md\：文件组织宪法（每样东西有唯一的位置，八条铁律）
- \
ile_hygiene\ 能力：按家规自检乱放 + 自动归位 + 审计留痕——她自己收拾自己的家
- 日常：\g.run_task('file_hygiene', {'fix': True})
## 万能插极限操控（六轮阶梯压测）

- 5 路域专攻并行 → 10 路暴露审计无锁缺陷（已修复）→ 20/40/80/160 路 ALL_OK
- 160 路并发：加速比 39.77x，审计 1694 行零损坏，运行记录零碰撞
- 领悟集落盘 store/polish_insights.json（极限测试方法论 + 已知边界登记）

## 触手契约层（MCP：抓住契约协议=接入整个工具生态）

- `mcp_connect`：连接任意 MCP 工具服务器（stdio JSON-RPC，实测 everything/filesystem 双服务器）
- `mcp_tools`：契约清单（名称+参数 schema——工具的"合同文本"）
- `mcp_call`：按契约调用任意工具，带钢印落审计
- 生态红利：官方 filesystem（14 工具）/ everything（13 工具）/ GitHub / 数据库……成百上千 MCP 服务器，一行连接全变成她的能力
- 已验证：连接→握手→契约→调用全链 1.5 秒；Windows .CMD 解析自动处理

## 黑客大脑（红蓝双模安全评估）

- \sec_surface\：攻击面测绘（输入/网络/文件/入口四维向量分析+风险评分，实测 V8 仓库 4117 向量）
- \sec_scan\：漏洞扫描（OWASP Top 10 + CWE 模式库，只扫自有代码，6 秒全仓）
- \sec_chain\：利用链构建（漏洞→攻击路径→影响评估）
- \sec_defenses\：蓝队防御验证（V8 真实防御矩阵 5 项：危险门禁/内网护栏/管线门禁/注册表完整性/写保护，实测 5/5）
- \sec_llm\：黑客大脑推理引擎（**独立大模型+独立密钥**：abliteration.ai 无限制模型，专用 ABLITERATION_API_KEY 通道，与通用 LLM 并行不混用；OpenAI 兼容 + 推理模型 reasoning 特性处理。三模型实测：abliterated-model(157tk)/large(67tk)/large-v2(54tk，默认——最快最省，都是 reasoning 模型)

## 镜像多维度空间 v2（pipeline：生产最后防线 + AI 自主完成工作）

三阶段深化（v2，2026-09-11 第十一批）：

- **Stage 1 镜像精修**：efine_rounds=N\ 开启 LLM 精修循环——审查→修改→快照→复审，每轮快照带血缘链（refined_from），最多 N 轮防失控
- **Stage 2 分级门禁**：P0 机械维度（完整/归属/审计/策略，恒开毫秒级）+ P1 质量维度（eview=True\ 开启 LLM 评分，阈值 60；分数与判定分歧时以量化分数为准并如实标注；截断恢复；JSON 平衡扫描+净化重试+双引擎容灾）
- **Stage 3 版本化生产**：原子写入（os.replace）+ 护照（版本号+血缘）+ \.versions/\ 历史链 + \pipeline_rollback\ 回滚（回滚也走审计）

新能力：\pipeline_versions\（版本历史+当前指纹）、\pipeline_rollback\（回滚到历史版本）。
向后兼容：\submit(name, content, meta)\ 与 v1 行为完全一致。

## 自主编排环（Autopilot）—— 从执行者到操盘手

- \utopilot\：给一个目标 → LLM 拆解工作流 → 本地校验（LLM 只是提案人无权限）→ 执行 → 自检 → 修复循环
- 纪律：轮数上限防失控（超限如实报 stopped）；LLM 方案必须落在已注册能力上（未注册一律拒绝）；全程审计 + 产出走管线带钢印
- 操控 AI 的严格实现：DeepSeek/Kimi/OpenAI 密钥链自动路由 + 空回复重试 + JSON 截断容错

## 框架体检层（眼睛 + 声带）

- \selfscan\：五维扫描——路由完整性（注册↔路由双向对账）/ 模块健康 / 存储健康 / 审计异常（四级信号分级：runtime 要追的病 / guard 护栏正常 / trace 测试足迹 / recovered 历史掉线已恢复）/ 桩缺口如实清点。P0 断连第一时间报警，autofix 可安全修复缺目录与损坏 JSON。
- \lerts\：声带——近期异常按能力聚合的根源线索，runtime 故障永远不静默。
- \CODING_DISCIPLINE.md\：编程纪律手册（32 条），她必须清楚的一切红线与习惯。


## 性能基线（丝滑如飞机）

- 冷启动 run_task(health)：~160ms（含解释器+框架加载）
- 热路径：health/echo <1ms · selfscan 175ms（进程内缓存后）· ghost_guard 31ms（定点扫描）· 触手 see 15-20ms（DXGI）
- 服务巡检并发化（线程池），预留端口不等超时；历史记录 JSON 分层采样检查
- 性能纪律：进程内缓存（模块检查）、定点扫描（不做全仓 rglob）、optional 服务快速跳过

---

>  · GBT小土豆V8 ·

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

## 桌面指挥官触手（Desktop Commander MCP）

把「终端 + 文件系统」接进框架（26 个工具：读写文件含 Excel/PDF/DOCX、执行命令、进程管理、搜索、会话交互）。

**本地形态（stdio，开箱可用）**

```python
import gbt_allinone as gbt
gbt.run_task("desktop_commander", {"op": "connect"})                     # 一键连接
gbt.run_task("desktop_commander", {"op": "tools"})                        # 26 工具清单（按用途归类）
gbt.run_task("desktop_commander", {"op": "call", "tool": "list_directory", "arguments": {"path": "."}})
```

**远程形态（remote 设备）**

```python
gbt.run_task("desktop_commander", {"op": "remote_start"})                 # 挂到云端中继，供远程 AI 驱动
gbt.run_task("desktop_commander", {"op": "remote_status"})                # 在线状态 + 日志尾部
gbt.run_task("desktop_commander", {"op": "remote_stop"})                  # 随时停止
```

remote 设备只在你启动时运行，命令在本机以你的用户权限执行。默认 `op=status` 为只读探测安全形态。

**品牌标识**：remote 设备通过 preload 注入（`gbt_allinone/tentacle/dc_brand_preload.js`）覆写 `os.hostname()`，以「GBT小土豆V8」的品牌身份上报云端设备列表（不改源码、不改系统 hostname）；品牌名可用环境变量 `GBT_DEVICE_NAME` 覆盖。
