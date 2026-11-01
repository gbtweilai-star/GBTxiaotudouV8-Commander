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
| 86 | [86-repo-cleanup-plan.md](86-repo-cleanup-plan.md) | 原始仓库整理：删 2323 文件/154MB 运行态，补 .gitignore |
| 87 | [87-repo-cleanup-done.md](87-repo-cleanup-done.md) | 原始仓库整理完成：5108→2708 文件，删 2323 个/154MB |
| 82 | [82-experience-forge.md](82-experience-forge.md) | 成长闭环：外部验证通过才准固化，存记忆/工具/规则不写权重 |
| 83 | [83-mirror-stage.md](83-mirror-stage.md) | 镜像工作空间：生产只读→多候选→验证→整页原子替换，失败不进生产 |
| 84 | [84-remote-controller.md](84-remote-controller.md) | 远程接管授权内核：远端用户点同意 + agent 签名才发 session |
| 85 | [85-local-only-audit.md](85-local-only-audit.md) | 本地算力审计：云 TTS/云取图点名，本地优先 fail-closed |
| 89 | [89-history-rewrite.md](89-history-rewrite.md) | 方案A：历史重写（362→351 提交，193.1→177.2MB，HEAD 不变） |
| 90 | [90-what-she-can-do.md](90-what-she-can-do.md) | 她能干嘛：30 域 375 位（从注册表实时生成） |
| 91 | [91-visual-pages.md](91-visual-pages.md) | 所有可视化页面：28 面板 + 落地页 + 图集 |
| 92 | [92-absorb-superpowers.md](92-absorb-superpowers.md) | 吞噬 superpowers-zh：20 个方法论 skill → skills_hub（第 376 位） |
| 93 | [93-gbtv5-full-review.md](93-gbtv5-full-review.md) | GBT-Framework v5 全量核对（897 文件/192 cap）+ chain_kernel 七步纪律 |
| 94 | [94-distill-not-dump.md](94-distill-not-dump.md) | 蒸馏不搬运：熔断加强 energy_core + root_cause + 拒收清单 |
| 95 | [95-cap-pack.md](95-cap-pack.md) | 能力包 cap_pack：清单发现+动态装载（第380位） |
| 96 | [96-mcp-and-dual-gate.md](96-mcp-and-dual-gate.md) | MCP 注册表闭环 + 双脑确认（接进 chain_kernel 派工） |
| 97 | [97-commander-engine-online.md](97-commander-engine-online.md) | 本机指挥官模型接入：引擎起、框架用、P0 假绿修掉 |
| 98 | [98-cap-count-truth.md](98-cap-count-truth.md) | 能力位到底几位：341/348/368/375/385 来龙去脉 + 计数守卫 |
| 99 | [99-agent-skills-spec.md](99-agent-skills-spec.md) | 吞噬 Agent Skills 规范：校验/打包/安装/渐进读取 |
| 100 | [100-gsap-skill.md](100-gsap-skill.md) | 实战：把 GSAP 8 个技能蒸馏成 1 个（validate/pack/match 闭环） |
| 101 | [101-panel-anim.md](101-panel-anim.md) | 面板动效真落地：GSAP 接三页 + 截图对比（5.75%/15.81% 像素变化） |
| 102 | [102-cognitive-console.md](102-cognitive-console.md) | 认知界面：拆 28 面板 + 照白龙马 1:1 三栏 + 土豆 Logo + 无限上下文 |
| 103 | [103-console-views-3d.md](103-console-views-3d.md) | 控制台四视图：功能表 385 / 技能栏 23 / 仪表盘 / 3D 触手星图（15,400 根） |
| 104 | [104-bloom-and-live-tentacles.md](104-bloom-and-live-tentacles.md) | 3D Bloom 辉光 + 按真实审计点亮触手（ok:385+30+15400+4） |
| 105 | [105-live-tentacles-sse.md](105-live-tentacles-sse.md) | 实时触手：SSE 推审计事件，3D 当场点亮（实测 inventory 事件） |
| 106 | [106-mouse-rotate-and-avatar.md](106-mouse-rotate-and-avatar.md) | 鼠标转动（自检 ok:14.491）+ 中心她的头像 + 修 /icons 404 |
| 107 | [107-brain-execution-layer.md](107-brain-execution-layer.md) | 大脑执行层：中心脑核 + 七步闭环管道 + 橙色证据节点 + 审计同心环 |
| 108 | [108-universal-plug-visualization.md](108-universal-plug-visualization.md) | 万能插：数字流动的结 + 8 能力域插口 + 自动插合触手 |
| 109 | [109-native-autostart-console-service.md](109-native-autostart-console-service.md) | 原生 APP 自启 :8766（Electron/Python 壳/启动器 + 登录自启一键装） |
| 110 | [110-team-collab-and-mindmap.md](110-team-collab-and-mindmap.md) | 触手协作（8角色×16协作链）+ 思维导图任务指引（6支×18叶） |
| 111 | [111-team-pulse-effect.md](111-team-pulse-effect.md) | 触手协作脉冲特效：冲击波环/拖尾/核心闪光 + 真实事件映射 |
| 112 | [112-penetrating-cross-scan.md](112-penetrating-cross-scan.md) | 穿透式交叉扫描：385 节点/85 疑点 + 五感过程 + 视觉全谱（不止 OCR） |
| 113 | [113-real-scan-data.md](113-real-scan-data.md) | 穿透扫描接真跑结果：unit_details 驱动（agree/arbitrated/unhooked）+ 三目标切换 |
| 114 | [114-no-blind-spot-scan.md](114-no-blind-spot-scan.md) | 无死角扫描：coverage=1.0 + full_coverage + dead_spots + 现场重扫补扫（最多3轮） |
| 115 | [115-tentacle-professions.md](115-tentacle-professions.md) | 触手职业表：12 职业（编程首席）·真实能力位映射·#prof 视图 |
| 116 | [116-profession-routing.md](116-profession-routing.md) | 职业路由：任务→职业→候选能力位（safe/gated 分栏，代码动词优先） |
| 117 | [117-landing-closed-loop.md](117-landing-closed-loop.md) | 落地闭环：路由→派单→账本 + 全景清单（11 视图/385 位/21 职业/无死角/自启） |
| 118 | [118-bounty-direction.md](118-bounty-direction.md) | 方向转向：安全研究/赏金工作台（授权闸/scope闸/报告/赔付账本 #bounty） |
| 119 | [119-own-lab-end-to-end.md](119-own-lab-end-to-end.md) | 自训靶场 + 端到端：6 类漏洞真跑 → 录单 → 报告(sha256) → 账本 |
| 120 | [120-bounty-report-and-tracker.md](120-bounty-report-and-tracker.md) | 赏金报告升级（CVSS 3.1/CWE/复现/修复/侧车 JSON）+ 提交状态机 |
| 121 | [121-platform-scope-import.md](121-platform-scope-import.md) | 平台 scope 导入（HackerOne/Bugcrowd 离线归一化，dry-run + 人工确认才落库） |
| 122 | [122-submit-bundle.md](122-submit-bundle.md) | 可提交包：CVSS 时间/环境分 + 修复 diff + 附件 + manifest + ZIP |
| 123 | [123-platform-status-sync.md](123-platform-status-sync.md) | 平台状态只读同步：mock 平台端到端、状态机回填、审计、只读 405 |
| 124 | [124-omni-all-sync.md](124-omni-all-sync.md) | 万能插全开同步执行：385 位逐个同步、票挡需授权位、进度落盘、API/UI |
| 125 | [125-alarm-rootcause-fixes.md](125-alarm-rootcause-fixes.md) | 报警必追根因：全开 63 失败归因（policy/超时/kwargs/硬编码路径/缺参/缺件）与修复 |
| 126 | [126-security-policy-three-rules.md](126-security-policy-three-rules.md) | 最高安全策略：黑客能力终端确认 / 受攻击V8自我决策 / 转账永远确认 |
| 127 | [127-attack-evidence-only.md](127-attack-evidence-only.md) | 受攻击只采集证据：极限并发取证/资源回收/证据包；明确拒绝黑客反击 |