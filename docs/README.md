# 文档总索引

> **想找能力？** 先看下面这一节，别从 30 份文档里翻。
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 一、找能力（三种方式，从快到慢）

| 方式 | 命令 / 文件 | 适合 |
|---|---|---|
| **按人话搜** | `python -m gbt_commander search "回滚到上一个版本"` | 只记得想干什么，不记得能力名 |
| **看某个域** | `python -m gbt_commander catalog --domain pipeline` | 知道大概属于哪个域（30 个域任选） |
| **一次看全部** | [`03-capabilities.md`](03-capabilities.md)（**368 项 · 本表由注册表现生成**） | 通读、比对 |
| **要全文说明** | [`capabilities-full.json`](capabilities-full.json)（**快照 2026-10-25 · 349 条**；现读请用 `run_task("cap_self", {"op":"verify"})` 或 `caps_registry`） | 机器读、要完整触发词 |
| **要人读全文** | [`capabilities/`](capabilities/)（30 份，**本轮已按 368 位重生成**） | 人读、要上下文 |
| **按意图逛** | [`18-native-cloud-catalog.md`](18-native-cloud-catalog.md) | 「我要看/听/说/记事/省内存/稳定输出」 |

**⚠️ 总表的说明列是简版（约 70 字）。触发词（放大 / 洗图 / 高清 / 4K …）在**
**`capabilities-full.json` 和 `capabilities/<域>.md` 里** —— 搜能力请查那两处。

---

## 二、先读这三份（新人路线）

| 文档 | 一句话 |
|---|---|
| [`01-model-card.md`](01-model-card.md) | 模型卡：7.6B 中文「总指挥」· **368 位能力（现读）** · 一个门 |
| [`02-architecture.md`](02-architecture.md) | 架构：为什么它敢叫「总指挥」 |
| [`18-native-cloud-catalog.md`](18-native-cloud-catalog.md) | **能力总目录（按「我要干什么」查）** ← 最实用 |

---

## 三、能力：有哪些 / 怎么证 / 怎么搜

| 文档 | 一句话 + 关键词 |
|---|---|
| [`03-capabilities.md`](03-capabilities.md) | 能力总表入口 · **368 位 / 30 域（注册表现生成）** · 两套数口径 |
| [`03-capabilities.md`](03-capabilities.md) + [`capabilities/`](capabilities/) | **逐条清单**（368 项 · 本轮重生成）· 域 / 类型 / 需参数 / 常见错误 / 它做什么 |
| [`07-capability-proof.md`](07-capability-proof.md) | **逐位真调**（341 位那一轮）· 340 ok / 1 needs-input · 零失败 |
| [`16-capability-audit-341.md`](16-capability-audit-341.md) | 全量核对（341 位）· 红黄清零 · 8 处修复 · 3 个教训 |
| [`capabilities/`](capabilities/) | 30 个域各一份，含「它做什么 / 怎么调」 |
| [`capabilities-full.json`](capabilities-full.json) | **机器可读全文** · name/domain/desc/bind/carrier/wired/proof |

---

## 四、稳定输出与无限上下文（用户最关心的两件事）

| 文档 / 能力位 | 一句话 + 关键词 |
|---|---|
| `fact_gate` | **机器事实直答门** —— 机器事实**不过语言模型**：现读 → 代码判定 → 原文引用 → 直答。三次重训治不住编事实，最后靠这块代码闸 |
| `llm_watch` | **输出后当场机检** —— 无证据的「已完成」/ 越权声明 / 数字对不上 ⇒ 进主脑队列；**判不了就如实写判不了** |
| `offload_distill` | **内存墙** —— 上游 Edge0 做到 35B 只吃 ~2.5 GB：权重离芯 + LRU 双缓冲 + prerouter + Recover-LoRA |
| `quant_plan` | **压缩与直达** —— 每档 bits/weight ⇒ 体积估算（PTQ1_0 1.75 b/w · 7.67 GB · 保留 98.2% FP16） |
| `energy_scheduler` | 并发上限 / 失败冷却（连败 3 次停 300s）/ least-load 不饿死 |
| [`08-concurrency.md`](08-concurrency.md) | **20,000 路同时调 · 零失败** · 墙钟 135s · 吞吐峰值在 1k–6k 档 |
| [`11-five-dim.md`](11-five-dim.md) | 五维合一：route → execute → verify → health 串链 |
| [`12-multidomain-monitor.md`](12-multidomain-monitor.md) | 多域监控 · 基线 + diff —— **「修一处坏一处」的解药** |

---

## 五、反向调用云端算力

| 文档 | 一句话 |
|---|---|
| [`13-omni-plug.md`](13-omni-plug.md) | **万能插**：万能插座（现场判类）· 万物皆可控 · **反向调用云端算力**（12 个云源 / 五原语） |
| [`05-deployment.md`](05-deployment.md) | 从权重到一条能打的线上接口 |

**命令：** `run_task("cloud_plugin", {"op":"sources"})` · `{"op":"primitives"}`

---

## 六、本体与手机端

| 文档 | 一句话 + 关键词 |
|---|---|
| [`17-phone-a19-runtime.md`](17-phone-a19-runtime.md) | **手机端 A19 全链路** · Q5_0 5.24 GB · 8–11.7 tok/s · 三层接线 · Q4_0 撑不住的逐层爆炸表 |
| `身体-设备即本体.md` （本快照无此文件） | 身体 · 设备即本体 |
| `身体能力位与多轮.md` （本快照无此文件） | **七根感官 + 六根动作** · `body_*` 七位 · 多轮上下文 · 界面接线 |
| `本体-一体式设计.md` （本快照无此文件） | 模型 + APP 是一件事 |
| `APP-自有权重.md` （本快照无此文件） | 自有权重按需激活 |
| `GPU-车道实测与判决.md` （本快照无此文件） | GPU 车道实测与判决 |

---

## 七、安全与边界

| 文档 | 一句话 + 关键词 |
|---|---|
| [`14-security-and-control.md`](14-security-and-control.md) | **防 AI 攻击 与 方向控制** · 14 个作用域 · AI 无权自授 · 三威胁模型（注入/幻觉/越权） |
| [`15-tentacle-counter.md`](15-tentacle-counter.md) | 极限触手与反控 · 极限压测 + 反向遥控 |
| `SECURITY.md` | 安全策略与报告渠道 |

---

## 八、权重与部署

| 文档 | 一句话 + 关键词 |
|---|---|
| [`05-deployment.md`](05-deployment.md) | 部署全链路 |
| `权重操作纪律.md` （本快照无此文件） | **权重操作纪律**（事故后立）· 禁止事项 |
| [`WEIGHTS.md`](../WEIGHTS.md) | 四种权重的分片清单 + 一键安装 |
| [`PROOF-weights.md`](../PROOF-weights.md) | **权重实证** · 12 项排除表 · Q4_0 vs Q8_0 逐层对照 |

---

## 九、验收与审计

| 文档 | 一句话 |
|---|---|
| [`04-evaluation.md`](04-evaluation.md) | 评测：不看感觉，看读数 |
| [`06-showcase.md`](06-showcase.md) | 真实回执（未经编辑） |
| `架构验收-五柱.md` （本快照无此文件） | 五根柱子：双向绑定 / 名册可取 / 门 / 账 / 复现 |
| `验收-10问.md` （本快照无此文件） · `验收-10问-v2.md` （本快照无此文件） | Q5_0 十问验收（含事故后复验） |
| [`09-mirror-space.md`](09-mirror-space.md) | 镜像空间：先在模拟世界跑绿，再晋升到现实 |
| [`10-gbt-tianzhen.md`](10-gbt-tianzhen.md) | **GBT天真**：不装 ComfyUI，也跑得动 ComfyUI 的节点契约（27 个原生算子） |
| [`21-tianzhen-usage.md`](21-tianzhen-usage.md) | **GBT天真 使用手册** · 三种调用方式 · 27 算子契约表 · 本机实跑读数 · 出图流水线 · 两条硬约束 · 踩过的坑 |

---

## 十、发布物料

| 文件 | 是什么 |
|---|---|
| [`gallery/`](gallery/) | **实拍证据图**：开源海报 · A19 自检 · 天真放大 2048×2729 前后对比 · 三帧拼条 · 能力文档对齐复盘 |
| [00-poster.jpg](gallery/00-poster.jpg) | 开源海报（341 位 / 20000 路并发 / 4.88 GB 手机能跑）|
| [02-tianzhen-upscale-2048x2729.png](gallery/02-tianzhen-upscale-2048x2729.png) | **665×886 → 2048×2729**，本地 LANCZOS+USM 放大实拍 |
| [05-tianzhen-3frame-strip.png](gallery/05-tianzhen-3frame-strip.png) | 三帧拼条 1080×540：蓄势→甩击→撞击，验动效连贯性 |


[`launch/`](launch/) —— 3 份对外文案（中英标题、要点、常见问答）。

---

## 十一、搜不到怎么办

```
1) python -m gbt_commander search "<人话>"        # 意图 → 能力位（带分数）
2) grep -i "<关键词>" docs/capabilities-full.json # 全文搜
3) python -m gbt_commander catalog --domain <域>  # 按域列
```

**能力位名字在 `gbt_allinone/caps_registry.py` 里注册；本目录只是它的读本，不是第二份源。**

---

## 十二、主干自有权重（2026-11-01 新增，10 份）

> 这一组回答的是「她到底用谁的脑子、怎么保证不丢」。**条数一律现算，不写死**：
> 现读 `run_task("cap_self", {"op": "brief"})` 或 `{"op":"verify"}`。

| 文档 | 一句话 |
|---|---|
| [`39-commander-trunk.md`](39-commander-trunk.md) | **权重融合进主干**：自有权重 → llama-server → `semantic_route` 第一顺位；降级链三档；实测读数 |
| [`40-page-binding-audit.md`](40-page-binding-audit.md) | **全仓页级双向绑定**：1706 页 100% 有绑定、反向 354/354、1 个连通分量、任意两页 ≤ 2 跳 |
| [`41-pulse-core-native.md`](41-pulse-core-native.md) | **四合一原生位**：脉冲 / 量化压缩 2.71× / 按需激活 / 精准直达，`verify` 四判据 |
| [`42-cap-self.md`](42-cap-self.md) | **能力自知**：三源对账（注册表↔快照↔分派），漂移即红；`has` 三种"没有"分开说 |
| [`43-omni-open-auto.md`](43-omni-open-auto.md) | **万能插自动打开**：插口是扫出来的（不是固定六类），增量对比拔掉/断线会进声带 |
| [`44-diagnostic-round.md`](44-diagnostic-round.md) | **按源码推荐跑诊断**：真缺陷 1 个（缺 `store/wf_runs`）；布局类异物属形态非缺陷；D/E/F 源码明令不实现 |
| [`45-code-graph.md`](45-code-graph.md) | **补齐断链**：`code_graph` 模块此前不存在；顺带挖出 BOM 会让 `ast.parse` 静默失败 |
| [`46-coverage-sample.md`](46-coverage-sample.md) | **判决层抽样**：56/60 = 93.3%；7 个 miss 全是模型辨别力，不是召回 |
| [`47-deploy-install-supervisor.md`](47-deploy-install-supervisor.md) | **落地**：一键安装六步幂等 + 引擎守护（kill 后 7 秒自愈）；自启因权限未注册（如实记） |
| [`48-signature-scope-gap.md`](48-signature-scope-gap.md) | **署名覆盖补漏**：docs/ 69 页从未被检查；新增 `scope=all`，现 100/100 |

---


**开发者：自由的风 · 护着：公主土豆**
**本署名不可删除、不可篡改归属。**

| 51 | [51-twin-caps-experiment.md](51-twin-caps-experiment.md) | 孪生位实验：加了区分词，2/5 命中 —— 结论是尺子本身有歧义 |
| 52 | [52-human-intent-baseline.md](52-human-intent-baseline.md) | 人写意图基准：召回 100%，命中 1/6 |
| 53 | [53-lexicon-scoped-routing.md](53-lexicon-scoped-routing.md) | 短意图修复：用人工词表收窄候选，1/6 → 5/5 |
| 54 | [54-human-bench-final.md](54-human-bench-final.md) | 人写意图 24 条终值：16/24 = 66.7%（召回 100%） |
| 55 | [55-tonight-ledger.md](55-tonight-ledger.md) | 今晚补齐清单与闭环固化 |
| 57 | [57-alias-forge.md](57-alias-forge.md) | 别名锻造：新能力位自动获得直达入口 |
| 58 | [58-pulse-first-route.md](58-pulse-first-route.md) | 脉冲优先路由：主干真的省掉 40s 级调用 |
| 59 | [59-comfy-parity.md](59-comfy-parity.md) | GBT天真 ↔ 秋叶版一比一：传统面 100%、模型面如实不接 |
| 60 | [60-comfy-engine.md](60-comfy-engine.md) | GBT天真 执行引擎加固：旁路/循环/失败回滚/未接线明说 |
| 61 | [61-comfy-harvest.md](61-comfy-harvest.md) | 秋叶版取食器：只取缺的、用得上的，权重一个不下 |
| 62 | [62-comfy-node-scaffold.md](62-comfy-node-scaffold.md) | 补节点脚手架：三族模板 + 独立 extras 模块 + 判据 |
| 63 | [63-comfy-ref-rebuild.md](63-comfy-ref-rebuild.md) | 参照重建（127→1000）+ 分类升级 + 批次 A 12 节点 |
| 64 | [64-native-workflow-import.md](64-native-workflow-import.md) | 原生 ComfyUI 图导入：转换 + 校验 + 未接线原因 |
| 65 | [65-comfy-import-dir.md](65-comfy-import-dir.md) | 批量导入目录：可跑/要GPU/未知/坏文件四分类 |
| 66 | [66-comfy-run-snapshots.md](66-comfy-run-snapshots.md) | 可复跑快照：每图留指纹 + replay 验 sha256 |
| 67 | [67-autonomy-contract.md](67-autonomy-contract.md) | 自主契约：架构给完后除危险能力/转账不许打扰主人 |
| 68 | [68-blueprint-chain.md](68-blueprint-chain.md) | 蓝图主链：架构→蓝图→过目→思维导图→派遣→落地 |
| 69 | [69-run-to-landing.md](69-run-to-landing.md) | 跑到落地：中途不停，只有落地/需票/轮尽才停 |
| 70 | [70-research-on-blocker.md](70-research-on-blocker.md) | 卡点研究环：查资料→落知识→重排任务，不问人 |
| 71 | [71-stuck-task-protection.md](71-stuck-task-protection.md) | 死循环保护：两轮失败标 stuck 并剔除，不装落地 |
| 72 | [72-blueprint-templates.md](72-blueprint-templates.md) | 蓝图模板库：落地即沉淀，相似架构 ≥2 关键词才复用 |
| 73 | [73-one-line-entry.md](73-one-line-entry.md) | 一句话入口：说一句 走完整链，未确认则停在蓝图 |
| 74 | [74-two-way-sync.md](74-two-way-sync.md) | 一键双向同步：交付树 ↔ live 工作仓（计划/执行/校验三层） |
| 75 | [75-sync-guard.md](75-sync-guard.md) | 双仓同步巡检位：status/verify/patrol + notify 推送 |
| 76 | [76-viral-forge.md](76-viral-forge.md) | 爆款拆解·克隆配方：吸收 hypit 设计，词锚配方 + 变体钩子 |
| 77 | [77-drama-forge.md](77-drama-forge.md) | 短剧产线：剧本→分镜→SAPI 旁白/字幕→竖屏成片，分镜卡/自有图两模式 |
| 78 | [78-sync-clobber-fix.md](78-sync-clobber-fix.md) | 双向同步回滚修复：newer-wins + 测试自清，防"刚改就被旧副本打回" |
| 79 | [79-legacy-guard.md](79-legacy-guard.md) | 旧物守卫：六类旧/重复检查，自注册插件 |
| 80 | [80-taste-guard.md](80-taste-guard.md) | 反-slop 设计闸：蒸馏 taste-skill 18 条 house rules，HTML 静态审计 |
| 81 | [81-single-source-of-truth.md](81-single-source-of-truth.md) | 唯一真相：旧副本制造歧义，newer-wins + 单一真相 |
| 86 | [86-repo-cleanup-plan.md](legacy/86-repo-cleanup-plan.md) | 原始仓库整理：删 2323 文件/154MB 运行态，补 .gitignore |
| 87 | [87-repo-cleanup-done.md](legacy/87-repo-cleanup-done.md) | 原始仓库整理完成：5108→2708 文件，删 2323 个/154MB |
| 82 | [82-experience-forge.md](82-experience-forge.md) | 成长闭环：外部验证通过才准固化，存记忆/工具/规则不写权重 |
| 83 | [83-mirror-stage.md](83-mirror-stage.md) | 镜像工作空间：生产只读→多候选→验证→整页原子替换，失败不进生产 |
| 84 | [84-remote-controller.md](84-remote-controller.md) | 远程接管授权内核：远端用户点同意 + agent 签名才发 session |
| 85 | [85-local-only-audit.md](85-local-only-audit.md) | 本地算力审计：云 TTS/云取图点名，本地优先 fail-closed |
| 89 | [89-history-rewrite.md](legacy/89-history-rewrite.md) | 方案A：历史重写（362→351 提交，193.1→177.2MB，HEAD 不变） |
| 90 | [90-what-she-can-do.md](90-what-she-can-do.md) | 她能干嘛：30 域 375 位（从注册表实时生成） |
| 91 | [91-visual-pages.md](legacy/91-visual-pages.md) | 所有可视化页面：28 面板 + 落地页 + 图集 |
| 92 | [92-absorb-superpowers.md](legacy/92-absorb-superpowers.md) | 吞噬 superpowers-zh：20 个方法论 skill → skills_hub（第 376 位） |
| 93 | [93-gbtv5-full-review.md](legacy/93-gbtv5-full-review.md) | GBT-Framework v5 全量核对（897 文件/192 cap）+ chain_kernel 七步纪律 |
| 94 | [94-distill-not-dump.md](legacy/94-distill-not-dump.md) | 蒸馏不搬运：熔断加强 energy_core + root_cause + 拒收清单 |
| 95 | [95-cap-pack.md](legacy/95-cap-pack.md) | 能力包 cap_pack：清单发现+动态装载（第380位） |
| 96 | [96-mcp-and-dual-gate.md](legacy/96-mcp-and-dual-gate.md) | MCP 注册表闭环 + 双脑确认（接进 chain_kernel 派工） |
| 97 | [97-commander-engine-online.md](legacy/97-commander-engine-online.md) | 本机指挥官模型接入：引擎起、框架用、P0 假绿修掉 |
| 98 | [98-cap-count-truth.md](legacy/98-cap-count-truth.md) | 能力位到底几位：341/348/368/375/385 来龙去脉 + 计数守卫 |
| 99 | [99-agent-skills-spec.md](legacy/99-agent-skills-spec.md) | 吞噬 Agent Skills 规范：校验/打包/安装/渐进读取 |
| 100 | [100-gsap-skill.md](legacy/100-gsap-skill.md) | 实战：把 GSAP 8 个技能蒸馏成 1 个（validate/pack/match 闭环） |
| 101 | [101-panel-anim.md](legacy/101-panel-anim.md) | 面板动效真落地：GSAP 接三页 + 截图对比（5.75%/15.81% 像素变化） |
| 102 | [102-cognitive-console.md](legacy/102-cognitive-console.md) | 认知界面：拆 28 面板 + 照参考布局 1:1 三栏 + 土豆 Logo + 无限上下文 |
| 103 | [103-console-views-3d.md](legacy/103-console-views-3d.md) | 控制台四视图：功能表 385 / 技能栏 23 / 仪表盘 / 3D 触手星图（15,400 根） |
| 104 | [104-bloom-and-live-tentacles.md](legacy/104-bloom-and-live-tentacles.md) | 3D Bloom 辉光 + 按真实审计点亮触手（ok:385+30+15400+4） |
| 105 | [105-live-tentacles-sse.md](legacy/105-live-tentacles-sse.md) | 实时触手：SSE 推审计事件，3D 当场点亮（实测 inventory 事件） |
| 106 | [106-mouse-rotate-and-avatar.md](legacy/106-mouse-rotate-and-avatar.md) | 鼠标转动（自检 ok:14.491）+ 中心她的头像 + 修 /icons 404 |
| 107 | [107-brain-execution-layer.md](legacy/107-brain-execution-layer.md) | 大脑执行层：中心脑核 + 七步闭环管道 + 橙色证据节点 + 审计同心环 |
| 108 | [108-universal-plug-visualization.md](legacy/108-universal-plug-visualization.md) | 万能插：数字流动的结 + 8 能力域插口 + 自动插合触手 |
| 109 | [109-native-autostart-console-service.md](legacy/109-native-autostart-console-service.md) | 原生 APP 自启 :8766（Electron/Python 壳/启动器 + 登录自启一键装） |
| 110 | [110-team-collab-and-mindmap.md](legacy/110-team-collab-and-mindmap.md) | 触手协作（8角色×16协作链）+ 思维导图任务指引（6支×18叶） |
| 111 | [111-team-pulse-effect.md](legacy/111-team-pulse-effect.md) | 触手协作脉冲特效：冲击波环/拖尾/核心闪光 + 真实事件映射 |
| 112 | [112-penetrating-cross-scan.md](legacy/112-penetrating-cross-scan.md) | 穿透式交叉扫描：385 节点/85 疑点 + 五感过程 + 视觉全谱（不止 OCR） |
| 113 | [113-real-scan-data.md](legacy/113-real-scan-data.md) | 穿透扫描接真跑结果：unit_details 驱动（agree/arbitrated/unhooked）+ 三目标切换 |
| 114 | [114-no-blind-spot-scan.md](legacy/114-no-blind-spot-scan.md) | 无死角扫描：coverage=1.0 + full_coverage + dead_spots + 现场重扫补扫（最多3轮） |
| 115 | [115-tentacle-professions.md](legacy/115-tentacle-professions.md) | 触手职业表：12 职业（编程首席）·真实能力位映射·#prof 视图 |
| 116 | [116-profession-routing.md](legacy/116-profession-routing.md) | 职业路由：任务→职业→候选能力位（safe/gated 分栏，代码动词优先） |
| 117 | [117-landing-closed-loop.md](legacy/117-landing-closed-loop.md) | 落地闭环：路由→派单→账本 + 全景清单（11 视图/385 位/21 职业/无死角/自启） |
| 118 | [118-bounty-direction.md](legacy/118-bounty-direction.md) | 方向转向：安全研究/赏金工作台（授权闸/scope闸/报告/赔付账本 #bounty） |
| 119 | [119-own-lab-end-to-end.md](legacy/119-own-lab-end-to-end.md) | 自训靶场 + 端到端：6 类漏洞真跑 → 录单 → 报告(sha256) → 账本 |
| 86 | [86-comfyui-local.md](86-comfyui-local.md) | ComfyUI 本地运行时落地：8188 CPU + Realistic Vision + GBT `comfyui.t2i` |
| 87 | [87-pro-film-pipeline.md](87-pro-film-pipeline.md) | 专业成片步骤：项目制设计、镜头/声音/色彩/QC |
| 88 | [88-realtime-eye-hand.md](88-realtime-eye-hand.md) | 眼手脑同拍：采集线程+闭环微步，实测 18fps 感知 / 3.2fps 负载下 |
| 89 | [89-hand-realtime.md](89-hand-realtime.md) | 眼手脑同拍 · 灵巧手 loopback：60 tick/58Hz/0.31ms 跑通 |
| 90 | [90-hand-ik.md](legacy/90-hand-ik.md) | 手指数值 IK：每指平面 3-link、限位、残差、同拍 58Hz |
| 91 | [91-hand-global-ik.md](91-hand-global-ik.md) | 全手 IK 关节向量 + 限位 + 时序平滑（非真 21-DoF QP） |
| 92 | [92-hand-vision.md](92-hand-vision.md) | 手部视觉入口：MediaPipe 本地；摄像头需隐私/后端，图片/视频可用 |
| 93 | [93-hand-image-chain.md](93-hand-image-chain.md) | 图片→MediaPipe 21 点→IK→loopback 手：已跑通 |
| 94 | [94-hand-force-contact.md](94-hand-force-contact.md) | 力/接触/柔顺接口：loopback 仿真；真机 fail-closed |
| 95 | [95-hand-force-loop.md](95-hand-force-loop.md) | 力限幅+导纳同拍：60 tick/58Hz/力峰值=limit |
| 96 | [96-hand-video-chain.md](96-hand-video-chain.md) | 手部视频→21点→IK→loopback：30/30 帧跑通 |
| 97 | [97-hand-video-smoothing.md](97-hand-video-smoothing.md) | 视频视觉链：抖动度量 + EMA 平滑 |
| 98 | [98-hand-video-timing.md](98-hand-video-timing.md) | 视频时序：时间戳/丢帧/处理延迟，实测 176.95ms mean |
| 99 | [99-hand-roi-experiment.md](99-hand-roi-experiment.md) | ROI/降分辨率实测：未达实时，瓶颈在推理不是分辨率 |
| 100 | [100-hand-pipeline-verdict.md](100-hand-pipeline-verdict.md) | 常驻 worker+三线程：仍 1.44fps，判本机 CPU 不适合实时手势 |
| 101 | [101-hand-onnx-realtime.md](101-hand-onnx-realtime.md) | 换本地 ONNX：23.69fps / frame p95 91.7ms，达到实时判据 |
| 102 | [102-hand-onnx-threaded.md](102-hand-onnx-threaded.md) | ONNX 三线程：26fps 但 e2e p95 255ms；串行仍是实时最佳 |
| 103 | [103-hand-latest-frame.md](103-hand-latest-frame.md) | latest-frame：延迟降但 coverage 0.1，判不达标 |
| 104 | [104-hand-adaptive-queue.md](104-hand-adaptive-queue.md) | 自适应队列：30帧短片冷启动拖累，coverage 0.3；串行仍最佳 |
| 105 | [105-hand-longrun-degradation.md](105-hand-longrun-degradation.md) | 长视频稳态：150帧崩到0.22fps，短片段23fps不能外推 |
| 106 | [106-hand-longrun-profile.md](106-hand-longrun-profile.md) | 60帧稳态25.3fps/p95 37.5ms；150帧仍异常，需chunk回收 |
| 108 | [108-hand-process-recycle.md](108-hand-process-recycle.md) | 真进程回收：150帧21fps/p95 39ms，长跑稳定 |
| 109 | [109-hand-chunked-chain.md](109-hand-chunked-chain.md) | 长视频闭环：进程回收+IK/HAL，150帧28fps |
| 110 | [110-hand-chunked-force.md](110-hand-chunked-force.md) | 长视频链+力限幅：150帧40fps，力峰值=limit |
| 111 | [111-hand-adaptive-force.md](111-hand-adaptive-force.md) | 自适应刚度+接触事件：力峰值=limit；fps 14.8 |
| 112 | [112-hand-compliance-optimized.md](112-hand-compliance-optimized.md) | compliance降频+防抖：42.3fps，力峰值=limit |
| 113 | [113-hand-dense-compliance.md](113-hand-dense-compliance.md) | 接触后密调/稳态降频：40.36fps，compliance_calls=8 |
| 114 | [114-hand-force-feedforward.md](114-hand-force-feedforward.md) | 力变化率前馈：已实现；静态接触 ff_hits=0 不吹 |
| 115 | [115-hand-feedforward-dynamic.md](115-hand-feedforward-dynamic.md) | 动态外力：pre-clamp保底；裸奔峰值20.5，前馈不能替代 |
| 116 | [116-hand-feedforward-unsafe.md](116-hand-feedforward-unsafe.md) | 位置前馈在动态外力下峰值6.68：前馈不能替代pre-clamp |
| 117 | [117-hand-safety-guard.md](117-hand-safety-guard.md) | 安全闸：force_limit>0 时禁止 pre_clamp=false 裸奔 |
| 118 | [118-hand-safety-api-fix.md](118-hand-safety-api-fix.md) | API 安全闸：裸奔配置结构化拒绝，不再 payload 崩溃 |
| 119 | [119-camera-winrt.md](119-camera-winrt.md) | 摄像头突破：WinRT能抓帧；Python子进程不行，需PowerShell帧桥 |
| 120 | [120-camera-bridge-chain.md](legacy/120-camera-bridge-chain.md) | WinRT帧桥→ONNX：真实相机帧可读；手图帧3/3/35fps |
| 121 | [121-camera-winrt-video.md](legacy/121-camera-winrt-video.md) | WinRT连续录像：3s/720p/46帧，ONNX 29.32fps；手未入镜 |
| 122 | [122-camera-chunks-real.md](legacy/122-camera-chunks-real.md) | WinRT连续chunk：真实相机33帧/5 detected/5 moved；coverage不足 |
| 123 | [123-hand-regression-matrix.md](legacy/123-hand-regression-matrix.md) | 手部回归 15/15 PASS；修 flaky 平滑断言 |
| 124 | [124-mediaframe-reader-fail.md](legacy/124-mediaframe-reader-fail.md) | MediaFrameReader初始化失败；连续相机仍用1s chunk |
| 125 | [125-framesources-null.md](legacy/125-framesources-null.md) | FrameSources枚举为null；MediaFrameReader仍未通 |
| 126 | [126-fast-camera-chunks.md](legacy/126-fast-camera-chunks.md) | 0.3s chunk相机：12帧/32fps处理；仍无手 detected=0 |
| 127 | [127-csharp-windowsdk-missing.md](legacy/127-csharp-windowsdk-missing.md) | C#/WinRT helper编译失败：缺Windows SDK UnionMetadata |
| 128 | [128-delivery-cleanup.md](legacy/128-delivery-cleanup.md) | 交付树清理：25.7k/7.6GB→3.3k/245MB；剩engine/llama锁定 |
| 129 | [129-desktop-hand-package.md](legacy/129-desktop-hand-package.md) | 桌面版打包手部ONNX：API onnx_image 21点/20关节/moved |
| 130 | [130-desktop-hand-chunked-api.md](legacy/130-desktop-hand-chunked-api.md) | 桌面API onnx_chunked：30帧/27.82fps/moved30 |
| 131 | [131-desktop-camera-chunks-api.md](legacy/131-desktop-camera-chunks-api.md) | 桌面API camera_chunks：300帧/moved300/11.47fps |
| 132 | [132-desktop-hand-ui.md](legacy/132-desktop-hand-ui.md) | 桌面UI注入手部按钮：图片/长视频走API |
| 133 | [133-desktop-native-picker.md](133-desktop-native-picker.md) | 桌面UI：原生文件选择+结果面板；API 200 |
| 134 | [134-desktop-camera-dir-ui.md](legacy/134-desktop-camera-dir-ui.md) | 桌面UI：相机chunk目录选择+可关闭结果面板 |
| 135 | [135-desktop-camera-watch.md](135-desktop-camera-watch.md) | camera_watch目录监视：150帧/45.29fps/moved150 |
| 136 | [136-desktop-watch-ui.md](legacy/136-desktop-watch-ui.md) | 桌面UI第4按钮：监视相机目录→camera_watch |
| 137 | [137-desktop-record-ui.md](137-desktop-record-ui.md) | 桌面UI录相机5s+自动camera_watch；接线已验证，点击未测 |
| 138 | [138-desktop-record-verified.md](legacy/138-desktop-record-verified.md) | UI录相机5s端到端：5 chunk，record ok；无手 detected=0 |
| 139 | [139-hand-buttons-sidebar.md](139-hand-buttons-sidebar.md) | 手部按钮移入左栏，居中模态结果 |
| 140 | [140-tianzhen-addnoise-and-ui-confirm.md](140-tianzhen-addnoise-and-ui-confirm.md) | 手部UI无孤儿确认；天真补ImageAddNoise，119节点/覆盖10.2% |
| 141 | [141-tianzhen-purecpu-batch2.md](141-tianzhen-purecpu-batch2.md) | 天真第二批20个纯CPU节点：139节点/覆盖122=12.2% |
| 142 | [142-tianzhen-purecpu-batch3.md](142-tianzhen-purecpu-batch3.md) | 天真第三批9节点：148节点/覆盖131=13.1% |
| 143 | [143-tianzhen-purecpu-tests.md](143-tianzhen-purecpu-tests.md) | 天真纯CPU节点真调用测试 ALL PASS（非只注册） |
| 144 | [144-tianzhen-purecpu-batch4.md](144-tianzhen-purecpu-batch4.md) | 天真第四批9节点：157节点/覆盖140=14.0% |
| 145 | [145-tianzhen-purecpu-batch5.md](145-tianzhen-purecpu-batch5.md) | 天真第五批7节点：164节点/覆盖147=14.7% |
| 146 | [146-tianzhen-canny.md](146-tianzhen-canny.md) | 天真Canny边缘：165节点/覆盖148=14.8% |
| 147 | [147-tianzhen-workflow-integration.md](147-tianzhen-workflow-integration.md) | 天真纯CPU节点走完整workflow：5节点/68×68/gate pass |
| 148 | [148-desktop-tianzhen-api.md](148-desktop-tianzhen-api.md) | 桌面版接天真只读API：status/coverage 200，PIL13/165节点 |
| 149 | [149-desktop-tianzhen-run.md](149-desktop-tianzhen-run.md) | 桌面天真API可跑workflow：5节点/200/sha一致 |
| 150 | [150-tianzhen-coverage-fix.md](150-tianzhen-coverage-fix.md) | coverage口径对齐：traditional 0，不再虚报177 |
| 151 | [151-desktop-tianzhen-ui.md](151-desktop-tianzhen-ui.md) | 桌面天真UI：状态/覆盖按钮，CDP实测可用 |
| 152 | [152-capability-router.md](152-capability-router.md) | capability_router：看屏幕/开网页/读写文件/看图四类接进 /api/chat，自动调用万能插（56项验收 ALL OK，含两轮独立验收回归） |
| 153 | [153-tianzhen-api-negative.md](153-tianzhen-api-negative.md) | 天真API负例：未知节点fail-closed，非白名单400 |
| 154 | [154-tianzhen-boundary-audit.md](154-tianzhen-boundary-audit.md) | 天真边界审计：unknown85全模型/3D，无纯CPU可补 |
| 155 | [155-living-world-devour.md](155-living-world-devour.md) | 吞噬 AEON/WorldX/Temporal God：逐仓拔缺失 + world_forge 世界内核（46项验收 ALL OK） |
| 156 | [156-shannon-devour.md](156-shannon-devour.md) | 吞噬 Shannon：把「No exploit, no report」蒸成授权渗透流水线（64项验收 ALL OK） |
| 157 | [157-p1-registration-app.md](157-p1-registration-app.md) | world_forge/pentest_flow 注册能力位 + P1（世界规格/存档/3D、源码攻击面/五类代理）+ APP 真机接线（76项验收 ALL OK） |
| 155 | [155-comfyui-local-objectinfo.md](legacy/155-comfyui-local-objectinfo.md) | 本地ComfyUI真快照1033节点；补SaveImageWebsocket，traditional0 |
| 156 | [156-local-only-coverage.md](legacy/156-local-only-coverage.md) | 本地口径：cloud 368 不计入，本地覆盖146/665=21.95% |
| 157 | [157-native-sdturbo.md](legacy/157-native-sdturbo.md) | 删ComfyUI后本地SD-Turbo原生出图：256/24.24s/121KB |
| 158 | [158-desktop-native-t2i-512.md](158-desktop-native-t2i-512.md) | 桌面API接SD-Turbo：256/512，缓存load4.68s，512生成27.13s |
| 159 | [159-native-shortfilm-nightlight.md](159-native-shortfilm-nightlight.md) |
| 160 | [160-voice-intercom.md](legacy/160-bailongma-voice-intercom.md) | 数字人语音对讲：MIC/空格 PTT + 对话面板 + 本机 Whisper 识别 + 中文女声（内核 27 项 + 验收 29 项） |
| 161 | [161-bailongma-gap-matrix.md](161-bailongma-gap-matrix.md) | 上游参考项目 → GBT 全能力对照 / 吞噬台账（20 组：已吞/部分/缺/不吞 + P0–P2 排期） | 原生SD-Turbo竖屏成片《夜灯》：15.84s/1080×1920/本地Hanhan |
| 162 | [162-native-browser-embed.md](legacy/162-native-browser-embed.md) | 我们自己的原生浏览器：Electron WebContentsView 宿主（标签/地址栏/下载/权限/边界）+ 契约与真机读数 |
| 163 | [163-ui-card-acui.md](legacy/163-ui-card-acui.md) | ACUI 卡片协议 ui_card：schema/白名单/纯文本/TTL/动作只回事件 + 能力位/统一门/console 卡片栈（P0 完成） |
| 164 | [164-voice-settings.md](legacy/164-voice-settings.md) | 语音设置页：TTS 音色/语速/音高/音量 + ASR 后端 auto/whisper/windows + 自动朗读（能力位/统一门/数字人弹窗） |
| 166 | [166-body-control.md](legacy/166-body-control.md) | body_control（身体控制/触手/全息投影）：如实 not_supported，缺感觉/执行器报缺，动作 executed=false |
| 167 | [167-context-inject.md](legacy/167-context-inject.md) | 上下文注入 context_inject：过期/去重/相关度/来源配额/字符预算 + 能力位/统一门/右栏预览 |
| 168 | [168-thought-stream.md](legacy/168-thought-stream.md) | 思考流/行动流：真实编排账归一化五类（thought/action/result/guard/system）+ 能力位/统一门/console 视图 |
| 169 | [169-api-slot.md](legacy/169-api-slot.md) | 动态 API 槽：https-only/拒私网/密钥只存 env 引用名/参数白名单；只登记定义，call 永远 not_supported |
| 170 | [170-reminder.md](170-reminder.md) | 提醒能力位：创建/列出/取消/到点查询；写面过 filesystem_write 门；不做网络通知 |
| 171 | [171-resource-snapshot.md](legacy/171-resource-snapshot.md) | 本机资源快照：ctypes+shutil 只读 CPU/内存/磁盘/uptime；能力位/统一门/右栏面板 |
| 172 | [172-media-stage.md](legacy/172-media-stage.md) | 媒体舞台/音乐库/历史：既有产物索引/分类/Range 文件服务；console 视图；APP 打包副本 |
| 173 | [173-turn-trace.md](173-turn-trace.md) | 轮次追踪 Turn Trace：session+间隔归并步骤/结果/证据/耗时；不伪造输入；能力位/统一门/console 视图 |
| 174 | [174-pairing-cert.md](174-pairing-cert.md) | 局域网配对/证书安全原语：一次性码/设备白名单/证书指纹；无监听、无签发 |
| 175 | [175-lan-pairing.md](175-lan-pairing.md) | 局域网配对监听/自签证书：只绑私有 LAN/回环 + TLS + 一次性码→Bearer；无远程命令；证书放 state/ |
| 176 | [176-update-verify.md](176-update-verify.md) | 更新清单/签名校验：Ed25519 验签/篡改拒/https URL 校验；只校验，不下载/安装 |
| 177 | [177-voice-stream.md](177-voice-stream.md) | 流式语音：PCM16 16k 分片 + 局部/最终 Whisper + sherpa-onnx 声学 KWS（小土豆）；能力位/统一门/右栏面板 |
| 178 | [178-update-chain-local.md](178-update-chain-local.md) | 本地更新测试链：无密钥 hash-only→stage→confirm→backup→replace→rollback；只 state/updates-test，不碰正式 APP |
| 180 | [180-video-hub.md](180-video-hub.md) | 视频舱：33 件视频生态能力按六段融合编目；只读/不执行；能力位 `/api/video` |
| 179 | [179-kws.md](179-kws.md) | 声学唤醒 KWS：sherpa-onnx 中文 3.3M 模型 + 拼音关键词「小土豆」；本机/无密钥；API/流式接线 |
| 181 | [181-page-mesh.md](181-page-mesh.md) | 页面触手网格：21 页每页脉冲、双向链 420、BroadcastChannel 互通、共享缓存提速 |
| 182 | [182-ref3d.md](182-ref3d.md) | ref3d：参考图 → 可拆解 3D 交互页（我们的数字人 DH-V7，1 mesh/66 bones，旧 Salticus 已清） |
| 183 | [183-email-cap.md](183-email-cap.md) | email_cap 审计别名 → 真实 coze_mail；闸门/配额在；transport 未接线如实报 needs_dependency |
| 184 | [184-page-bindings.md](184-page-bindings.md) | 页面 ↔ 触手双向绑定：20 页 ↔ 410 能力位；page_scan 唯一真源；无漏网 |
| 185 | [185-native-scan.md](185-native-scan.md) | 原生扫描深度体检：BOM 25 文件已清、wf_runs 补建、page_scan 20/20；capability_net 410/410 入口已修；page_scan 分片 355 绿/54 黄/0 红 |
| 186 | [186-git-advanced.md](186-git-advanced.md) | git_write 高级写面：push/force_push/rebase/reset 真跑；confirm/network/destructive 标记；Windows git 路径兜底 |
| 187 | [187-console-layout.md](187-console-layout.md) | PAGE MESH HUD 进入布局槽，不再压右栏；APP payload selfscan/signature/inventory 复扫 clean |
| 188 | [188-cap-verification.md](188-cap-verification.md) | 能力核实台账：verified 267/410、has_test 300/410（真实探针/测试引用）；66 组重复文档归档；legacy clean |
| 165 | [165-focus-stack-memory-audit.md](legacy/165-focus-stack-memory-audit.md) | 焦点栈 + 记忆审计：上限12/提分/排序/pop + 只读审计（重复/缺时/secret_like）；能力位/统一门/右栏面板 |
| 160 | [160-weight-fusion-rv-tiny.md](160-weight-fusion-rv-tiny.md) | 公共权重真融合：RV5.1×Tiny-SD，共同148键，出图正常 |
| 161 | [161-t2i-fused-node.md](legacy/161-t2i-fused-node.md) | t2i_fused 节点：本地融合权重 64/1 与 256/8 实测出图 |
| 162 | [162-desktop-api-t2i-fused.md](162-desktop-api-t2i-fused.md) | 桌面 API 接入 t2i_fused：64/1 实测 11.04s |
| 163 | [163-svd-i2v-cpu-fp32.md](163-svd-i2v-cpu-fp32.md) | SVD CPU fp32 真图生视频：4帧/352s，2s循环成片 |
| 164 | [164-svd-8frame-cpu.md](164-svd-8frame-cpu.md) | SVD 8帧 CPU 实测：675.76s，4s循环成片 |
| 165 | [165-svd-vertical-1080.md](165-svd-vertical-1080.md) | SVD 真运动竖屏 1080×1920/8s |
| 166 | [166-svd-narrated-shot.md](166-svd-narrated-shot.md) | 真运动旁白短镜头 1080×1920/11.62s |
| 167 | [167-two-shot-motion.md](167-two-shot-motion.md) | 双镜头真运动短片 1080×1920/19.63s |
| 168 | [168-three-shot-motion.md](168-three-shot-motion.md) | 三镜头真运动短片 1080×1920/19.88s |
| 169 | [169-three-shot-polished.md](169-three-shot-polished.md) | 三镜成片级收尾：雨声/片头尾/淡入淡出 |
| 170 | [170-red-eye-character-film.md](legacy/170-red-eye-character-film.md) | 《红瞳》中式僵尸竖屏短片 1080×1920/24.2s |
| 171 | [171-red-eye-all-motion.md](171-red-eye-all-motion.md) | 《红瞳》全SVD真运动版 1080×1920/22.52s |
| 172 | [172-gbt-i2v-svd-node-api.md](172-gbt-i2v-svd-node-api.md) | GBT天真 i2v_svd 节点/API 实测 |
| 189 | [189-shuohao-skills-absorbed.md](189-shuohao-skills-absorbed.md) | 吞噬 shuohao-skills：7技能+GBT节点+AI漫剧成片 |
| 190 | [190-e01-detail-rework.md](190-e01-detail-rework.md) | E01-01细节返工：cut3主角4帧+台词字幕混音 |
| 191 | [191-e01-v5.md](191-e01-v5.md) | 渡口 E01-01 v5：cut1/cut4返工+字幕修正 |
| 192 | [192-e01-v6.md](192-e01-v6.md) | E01-01 v6：cut2 重做 + 离线男声 + 字幕尾端达标 |
| 193 | [193-e01-v7.md](193-e01-v7.md) | E01-01 v7：cut1 素色/皮箱/泥路修正 |

