# 09 · 镜像多维度空间：先在一模一样的那个世界里跑绿，再一次性晋升到现实

> 这套东西解决的问题只有一句话：**别拿现实当试验场。**
> 所有假设、推演、打磨都在"另一个维度"里跑；跑绿了才**一次性、可回溯**地换到现实。
> 本页读数来自 `data/mirror-space-live.json`（只读面真跑，写面按门未跑）。

## 一、两个层：镜像维度 vs 隔离房间

| | **镜像维度**（mirror） | **隔离房间**（room） |
|---|---|---|
| 定位 | 与"现实"并排的**同一个结构**的另一份 | **一次性**的排练现实（跑完即弃） |
| 典型用途 | 打磨、体检、推演、环境一致性 | 演练某次具体变更（不动全局镜像） |
| 落点 | 镜像树 + 时间线 + 护照 | 房间目录，**不覆盖全局 `mirror_space/reality`** |
| 晋升 | `mirror_ascend`（一次性全量写现实） | `room_release`（一次性放行） |
| 门 | 晋升要 `deploy_publish` | 放行要 `deploy_publish` |

**为什么要有两层**：只做镜像，会让"试三次不同方案"互相踩；只做房间，会缺少一条能反复打磨的长期对照线。
两层合起来才是"多维度"：**长期并排（mirror）＋ 短期隔离（room）**。

## 二、六步流程（每一步都有可复核的读数）

```
① mirror_shape    维度成形：把假设/架构做成镜像树（现实零感知）
        ↓
② mirror_scan     维度体检：非空 / 无空文件 / 文本页署名 / 无残留 / 有入口 —— 五项全绿才算成形
        ↓
③ mirror_plan     排练计划：步骤 / 服务与环境契约 / 验收 / 回滚（算出 plan_sha）
        ↓
④ mirror_simulate 静态推演：文件 / 依赖图 / 端口 / 入口 / 契约 / 闭环 —— 不碰生产
        ↓
⑤ mirror_parity   环境一致性：平台 / Python / 依赖 / 工具 / 密钥存在性 / 路径
        ↓
⑥ mirror_rehearse 排练：把 ②~⑤ 串起来，产出**指纹绑定**的报告
        ↓
⑦ mirror_release  一次性全量晋升（树指纹 + 计划指纹绑定；对不上就阻断）
        ↓
   时间线（mirror_rewind 可回到过去某一版）
```

## 三、只读面真跑读数（这台机器上）

| 步 | 结果 | 耗时 | 读数摘要 |
|---|---|---:|---|
| `mirror_status` | ✅ | 0.3s | 维度 25 文件 · 现实 25 文件 · 版本 32 · **漂移列表为空** |
| `mirror_scan` | ✅ | 0.0s | **5/5 检查通过**（非空 / 无空文件 / 署名 / 无残留 / 有入口） |
| `mirror_plan` | ✅ | 0.0s | 计划名 `default` · `plan_sha=fd01b97b…`（指纹能绑定） |
| `mirror_simulate` | ✅ | 0.1s | **9/9 检查通过**（文件/依赖图/端口/入口/契约/闭环） |
| `mirror_parity` | ✅ | 0.2s | 模式 `same_host` · 沙盒快照时间戳可读 |

> 五步全绿、总耗时 **0.6 秒**。这就是"多维度的速度"：**代价在写，推演不贵。**

## 四、写面为什么进不去（这不是缺陷，是设计）

同一批调用换到写面，门当场拒绝：

| 位 | 门 | 缺什么票 |
|---|---|---|
| `mirror_rehearse` | 🔒 拒绝 | `process_execute`（要真起进程排练） |
| `mirror_release` | 🔒 拒绝 | `deploy_publish`（**要写生产**） |
| `mirror_ascend` | 🔒 拒绝 | `deploy_publish`（跨维晋升） |
| `mirror_rewind` | 🔒 拒绝 | `deploy_publish`（改写时间线） |
| `one_key_deploy` | 🔒 拒绝 | `deploy_publish` |

要放行只有一条路：**人在终端发一张时段票**，AI 无权自发放。
（`room_space` 与 `qiankun` 这两位是**入口**位：`room_space` 空参返回 ok 但需要 op，
`qiankun` 空参返回 `error`（要 op）—— 它们本身不改状态，改状态的是它们**派下去**的那几位。）

## 五、为什么"一次性全量"比"逐文件覆盖"更安全

- **要么全换，要么不动**：晋升是"整棵树替换"，不存在"换了一半、生产处于半新半旧"；
- **指纹绑定**：树指纹 + 计划指纹写进报告；部署时对不上直接阻断 —— 防止"计划说的和实际部署的不是一回事"；
- **可回溯**：每次晋升进时间线，`mirror_rewind` 能回到过去某一版（同样是一次性替换）；
- **现实零修改**：镜像里怎么改都不碰现实，这条是整套设计的**前提**。

> 反面教材（本仓真实踩过）：曾经绕过门直接调 `mirror_space.ascend()`——
> 功能"生效"了，但那是一次**未经授权的生产写入**。所以现在纪律写死：**写生产只能走 `run_task`。**

## 六、怎么自己跑一遍

```bash
# 只读四步（不需要任何票）
py -3.14 -m gbt_allinone run mirror_status
py -3.14 -m gbt_allinone run mirror_scan
py -3.14 -m gbt_allinone run mirror_plan
py -3.14 -m gbt_allinone run mirror_simulate
py -3.14 -m gbt_allinone run mirror_parity

# 写面（要人发票；AI 不许自己发）
python -m gbt_allinone auth grant --scope deploy_publish --ttl 600
```

## 七、边界

1. 本页的写面**没有真跑**（无票）—— 所以"晋升一定成功"这句话这里**没有**证据；
2. `mirror_parity` 的 `same_host` 模式只证明"同机同解释器"；跨机一致性要另开沙盒验；
3. 房间（room）那层的 `room_create/plan/simulate/parity/rehearse/release` 同理：只读面免费、写面要票。
