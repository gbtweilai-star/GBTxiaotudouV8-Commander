# 文档总索引

> **想找能力？** 先看下面这一节，别从 30 份文档里翻。
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 一、找能力（三种方式，从快到慢）

| 方式 | 命令 / 文件 | 适合 |
|---|---|---|
| **按人话搜** | `python -m gbt_commander search "回滚到上一个版本"` | 只记得想干什么，不记得能力名 |
| **看某个域** | `python -m gbt_commander catalog --domain pipeline` | 知道大概属于哪个域（30 个域任选） |
| **一次看全部** | [能力总表.md](能力总表.md)（348 项 · 简版说明） | 通读、比对 |
| **要全文说明** | [capabilities-full.json](capabilities-full.json)（348 条 · 每条约 226 字） | 机器读、要完整触发词 |
| **要人读全文** | [capabilities/](capabilities/)（30 份，含「它做什么」段） | 人读、要上下文 |
| **按意图逛** | [18-native-cloud-catalog.md](18-native-cloud-catalog.md) | 「我要看/听/说/记事/省内存/稳定输出」 |

**⚠️ 总表的说明列是简版（约 70 字）。触发词（放大 / 洗图 / 高清 / 4K …）在**
**`capabilities-full.json` 和 `capabilities/<域>.md` 里** —— 搜能力请查那两处。

---

## 二、先读这三份（新人路线）

| 文档 | 一句话 |
|---|---|
| [01-model-card.md](01-model-card.md) | 模型卡：7.6B 中文「总指挥」· 348 位能力 · 一个门 |
| [02-architecture.md](02-architecture.md) | 架构：为什么它敢叫「总指挥」 |
| [18-native-cloud-catalog.md](18-native-cloud-catalog.md) | **能力总目录（按「我要干什么」查）** ← 最实用 |

---

## 三、能力：有哪些 / 怎么证 / 怎么搜

| 文档 | 一句话 + 关键词 |
|---|---|
| [03-capabilities.md](03-capabilities.md) | 能力总表入口 · **348 位 / 30 域** · 两套数口径 |
| [能力总表.md](能力总表.md) | **逐条证据**（348 项）· 绑定 / 载体 / 接线文件 / 实测状态 |
| [07-capability-proof.md](07-capability-proof.md) | **逐位真调**（341 位那一轮）· 340 ok / 1 needs-input · 零失败 |
| [16-capability-audit-341.md](16-capability-audit-341.md) | 全量核对（341 位）· 红黄清零 · 8 处修复 · 3 个教训 |
| [capabilities/](capabilities/) | 30 个域各一份，含「它做什么 / 怎么调」 |
| [capabilities-full.json](capabilities-full.json) | **机器可读全文** · name/domain/desc/bind/carrier/wired/proof |

---

## 四、稳定输出与无限上下文（用户最关心的两件事）

| 文档 / 能力位 | 一句话 + 关键词 |
|---|---|
| `fact_gate` | **机器事实直答门** —— 机器事实**不过语言模型**：现读 → 代码判定 → 原文引用 → 直答。三次重训治不住编事实，最后靠这块代码闸 |
| `llm_watch` | **输出后当场机检** —— 无证据的「已完成」/ 越权声明 / 数字对不上 ⇒ 进主脑队列；**判不了就如实写判不了** |
| `offload_distill` | **内存墙** —— 上游 Edge0 做到 35B 只吃 ~2.5 GB：权重离芯 + LRU 双缓冲 + prerouter + Recover-LoRA |
| `quant_plan` | **压缩与直达** —— 每档 bits/weight ⇒ 体积估算（PTQ1_0 1.75 b/w · 7.67 GB · 保留 98.2% FP16） |
| `energy_scheduler` | 并发上限 / 失败冷却（连败 3 次停 300s）/ least-load 不饿死 |
| [08-concurrency.md](08-concurrency.md) | **20,000 路同时调 · 零失败** · 墙钟 135s · 吞吐峰值在 1k–6k 档 |
| [11-five-dim.md](11-five-dim.md) | 五维合一：route → execute → verify → health 串链 |
| [12-multidomain-monitor.md](12-multidomain-monitor.md) | 多域监控 · 基线 + diff —— **「修一处坏一处」的解药** |

---

## 五、反向调用云端算力

| 文档 | 一句话 |
|---|---|
| [13-omni-plug.md](13-omni-plug.md) | **万能插**：六类插座 · 万物皆可控 · **反向调用云端算力**（12 个云源 / 五原语） |
| [05-deployment.md](05-deployment.md) | 从权重到一条能打的线上接口 |

**命令：** `run_task("cloud_plugin", {"op":"sources"})` · `{"op":"primitives"}`

---

## 六、本体与手机端

| 文档 | 一句话 + 关键词 |
|---|---|
| [17-phone-a19-runtime.md](17-phone-a19-runtime.md) | **手机端 A19 全链路** · Q5_0 5.24 GB · 8–11.7 tok/s · 三层接线 · Q4_0 撑不住的逐层爆炸表 |
| [身体-设备即本体.md](身体-设备即本体.md) | 身体 · 设备即本体 |
| [身体能力位与多轮.md](身体能力位与多轮.md) | **七根感官 + 六根动作** · `body_*` 七位 · 多轮上下文 · 界面接线 |
| [本体-一体式设计.md](本体-一体式设计.md) | 模型 + APP 是一件事 |
| [APP-自有权重.md](APP-自有权重.md) | 自有权重按需激活 |
| [GPU-车道实测与判决.md](GPU-车道实测与判决.md) | GPU 车道实测与判决 |

---

## 七、安全与边界

| 文档 | 一句话 + 关键词 |
|---|---|
| [14-security-and-control.md](14-security-and-control.md) | **防 AI 攻击 与 方向控制** · 14 个作用域 · AI 无权自授 · 三威胁模型（注入/幻觉/越权） |
| [15-tentacle-counter.md](15-tentacle-counter.md) | 极限触手与反控 · 极限压测 + 反向遥控 |
| [SECURITY.md](../SECURITY.md) | 安全策略与报告渠道 |

---

## 八、权重与部署

| 文档 | 一句话 + 关键词 |
|---|---|
| [05-deployment.md](05-deployment.md) | 部署全链路 |
| [权重操作纪律.md](权重操作纪律.md) | **权重操作纪律**（事故后立）· 禁止事项 |
| [WEIGHTS.md](../WEIGHTS.md) | 四种权重的分片清单 + 一键安装 |
| [PROOF-weights.md](../PROOF-weights.md) | **权重实证** · 12 项排除表 · Q4_0 vs Q8_0 逐层对照 |

---

## 九、验收与审计

| 文档 | 一句话 |
|---|---|
| [04-evaluation.md](04-evaluation.md) | 评测：不看感觉，看读数 |
| [06-showcase.md](06-showcase.md) | 真实回执（未经编辑） |
| [架构验收-五柱.md](架构验收-五柱.md) | 五根柱子：双向绑定 / 名册可取 / 门 / 账 / 复现 |
| [验收-10问.md](验收-10问.md) · [验收-10问-v2.md](验收-10问-v2.md) | Q5_0 十问验收（含事故后复验） |
| [09-mirror-space.md](09-mirror-space.md) | 镜像空间：先在模拟世界跑绿，再晋升到现实 |
| [10-gbt-tianzhen.md](10-gbt-tianzhen.md) | **GBT天真**：不装 ComfyUI，也跑得动 ComfyUI 的节点契约（27 个原生算子） |

---

## 十、发布物料

[launch/](launch/) —— 3 份对外文案（中英标题、要点、常见问答）。

---

## 十一、搜不到怎么办

   1) python -m gbt_commander search "<人话>"        # 意图 → 能力位（带分数）
   2) grep -i "<关键词>" docs/capabilities-full.json # 全文搜
   3) python -m gbt_commander catalog --domain <域>  # 按域列

**能力位名字在 `gbt_allinone/caps_registry.py` 里注册；本目录只是它的读本，不是第二份源。**

---

**开发者：自由的风 · 护着：公主土豆**
**本署名不可删除、不可篡改归属。**
