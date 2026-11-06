# 吞噬记录 · dexterous-hand（2026-11-01）

> 主人令：「有用就吞噬了吧」——承接上一轮对 `github.com/topics/dexterous-hand` 的排查，把其中对 GBT 有用的仓库用万能插吞掉。
> 执行方式：万能插能力位 **`devour_github`**（`run_task("devour_github", {"repo": <url>})`），不是手写脚本抄 README。
> 结果：**21 个知识胶囊**（20 个本轮选吞 + 1 个试点 `Awesome-Dexterous-Hands`），全部落地并注入神经触手；胶囊总 **172.1 KB**，知识正文 **121,585 字符**。
> 证据：`.scratch\lead\devour-dexterous-result.json`（逐个原始回执）、`devour-post.json`（吞后 scan/reflect/fusion 读数）。

---

## 一、吞了什么（按星数排序）

| # | 仓库 | ★ | 语言 | 许可（胶囊现读） | 选它的理由 | 知识字符 |
|---|---|---:|---|---|---|---:|
| 1 | [lightning-grasp](https://github.com/zhaohengyin/lightning-grasp) | 226 | Python | NOASSERTION（README 自述 **CC BY-NC 4.0**） | GPU 接触场程序化抓取合成，秒级数千抓取；Allegro/Shadow/YCB | 6,397 |
| 2 | [awesome-humanoid-manipulation](https://github.com/yanming03/awesome-humanoid-manipulation) | 164 | — | unknown | 人形/灵巧操作论文与资源总索引 | 6,689 |
| 3 | [AnyDexRetarget](https://github.com/qqsq12321/AnyDexRetarget) | 92 | Python | MIT | Vision Pro / Quest3 / 相机 → 多款灵巧手高精度重定向 | 6,501 |
| 4 | [Awesome-Dexterous-Hands](https://github.com/CyanHaze/Awesome-Dexterous-Hands) | 50 | — | **CC-BY-4.0** | 灵巧手论文/数据集/仿真器/硬件/开源资源大全（试点先吞） | 6,650 |
| 5 | [BrainCo-Revo2-Dex-Retargeting](https://github.com/Bobyue0118/BrainCo-Revo2-Dex-Retargeting) | 38 | Python | MIT | BrainCo Revo2 实时重定向与手部动作生成 | 6,432 |
| 6 | [rh56dfx_description](https://github.com/ookkshirsagar/rh56dfx_description) | 16 | Python | MIT | Inspire RH56DFX 6-DoF 手 ROS2 URDF/RViz/MoveIt2 | 6,649 |
| 7 | [TransDex](https://github.com/LFGfg/TransDex) | 14 | Python | unknown | 视触觉融合点云操作策略 | 6,429 |
| 8 | [robolings](https://github.com/12-Twelve-12/robolings) | 13 | Python | MIT | Rustlings 式机器人学习练习（运动学/灵巧手/扩散策略/流匹配） | 6,567 |
| 9 | [rp_dexhand](https://github.com/Roboparty/rp_dexhand) | 10 | Python | unknown | RP Hand 文档/硬件/CAD/URDF/MJCF/SDK 总包 | 4,484 |
| 10 | [awesome-loco-manipulation](https://github.com/zihanwang0422/awesome-loco-manipulation) | 9 | — | unknown | 移动-操作（loco-manipulation）论文/仓库索引 | 6,474 |
| 11 | [PCHands](https://github.com/hsp-iit/PCHands) | 7 | Python | BSD-3-Clause | N-DoF 机械手 PCA 手部姿态重定向（论文官方实现） | 6,489 |
| 12 | [AdaDexTrack](https://github.com/Janebek/AdaDexTrack) | 5 | Python | BSD-3-Clause | CVPR2026 自适应灵巧操作跟踪 | 6,444 |
| 13 | [inspire-hand-rh56-py](https://github.com/yuzhench/inspire-hand-rh56-py) | 5 | Python | MIT | Inspire RH56DFTP 纯 Python Modbus TCP 驱动（无 ROS） | 6,595 |
| 14 | [dexterous_hand_ros2](https://github.com/TOHgoto/dexterous_hand_ros2) | 4 | C++ | MIT | 通用 ROS2 灵巧手 HAL（CAN/串口 + 本地 mock 驱动） | 6,520 |
| 15 | [tesollo_ros2](https://github.com/tesollodelto/tesollo_ros2) | 4 | — | BSD-3-Clause | Tesollo 手 ROS2 驱动/ros2_control/MoveIt2/Gazebo | 6,562 |
| 16 | [DexFingerGuessing](https://github.com/cjgogo27/DexFingerGuessing) | 1 | Python | MIT | PaXini DexH13 灵巧手猜拳/手指镜像（Python+Modbus 交互 demo） | 3,000 |
| 17 | [hand-tracking-fusion-system](https://github.com/alexandertianlin/hand-tracking-fusion-system) | 1 | C | MIT | HaMeR+ViTPose+IMU 手套+深度相机多模态手部跟踪融合 | 6,690 |
| 18 | [Dexterous-Soft-Hand](https://github.com/Dengfeng-Yan/Dexterous-Soft-Hand) | 1 | — | unknown | MuJoCo 软体灵巧手任务库（仓库极小，README 仅 21 字符） | 466 |
| 19 | [artly-dex-hand](https://github.com/Blue-Hill-Tech/artly-dex-hand) | 0 | Python | unknown | Artly D21 灵巧手 SDK/CAD/URDF/MuJoCo 文档 | 4,605 |
| 20 | [AmazingHand](https://github.com/Juxi-Technology/AmazingHand) | 0 | JavaScript | unknown | AmazingHand 8-DoF 开源仿生灵巧手（3D 打印+控制软件） | 4,431 |
| 21 | [Mood-Gesture](https://github.com/cbbtoagi/Mood-Gesture) | 0 | Python | NOASSERTION | 中文情绪感知→LLM 祝福→灵巧手手势→明信片（情感陪伴应用） | 6,511 |

## 二、许可与边界（这是重点，不是附注）

- **吞噬只取**：GitHub API 元数据（stars/语言/许可/描述/topics/分支/pushed_at）+ **README 前 6,000 字符**；**没有**下载/复制任何仓库源码。
- 许可分布：**MIT 8** · **BSD-3-Clause 3** · **CC-BY-4.0 1** · **NOASSERTION 2** · **unknown 7**。
  - `lightning-grasp`：README 明写 **CC BY-NC 4.0（仅学术/研究，商用需单独授权）** ⇒ 只作知识参考，**算法思路可借鉴、代码不可商用搬运**。
  - `unknown`/`NOASSERTION`（awesome 清单、TransDex、rp_dexhand、Dexterous-Soft-Hand、artly、AmazingHand、Mood-Gesture）⇒ 按「来源未声明」处理：**内部知识参考，不商用、不复用代码**；真要吸收代码前先补七步法第 2 步（许可核验）。
- 胶囊是**知识层**（`tier: knowledge`，`auto_exec: false`），不是原生能力位，不会被自动执行。

## 三、吞后读数（万能插自检）

| 能力 | 读数 |
|---|---|
| `devour_github` × 21 | **21/21 ok**；`knowledge_chars` 合计 **121,585**；每个胶囊都三件齐（`absorbed_knowledge.md` + `knowledge.json` + `run.py`） |
| `devour_reflect` | 胶囊 **21** 个 · 平均质量分 **80** · strong 21 / weak 0 · 给出若干可重组对（如 robolings ↔ hand-tracking-fusion-system） |
| `devour_scan` | `total_caps` 现读 **365**（工作仓注册表已由并行会话继续加到 365；交付快照是 354）· 缺口仅 `ledger`/`wallet` 两个未启用域 |
| `devour_fusion audit` | count 0 / not_fused 0（知识胶囊不进"原生位融合"台账，符合口径） |

**胶囊落点**（工作仓，运行数据；源码交付树按口径不含 `state/store`）：

```
…\GBTxiaotudouV8-Commander-main\gbt_allinone\store\devoured\<cap_name>\
    absorbed_knowledge.md   # 吞噬记录 + README 摘要（给人读）
    knowledge.json          # 胶囊元数据（tier=knowledge）
    run.py                  # 读取本胶囊知识的入口
```

读法：`python gbt_allinone/store/devoured/<cap_name>/run.py knowledge` 或直接打开 `absorbed_knowledge.md`。

## 四、对 GBT 最有用的三条吸收路线（建议下一步）

1. **手部重定向管线**：`AnyDexRetarget` + `BrainCo-Revo2` + `PCHands` + `hand-tracking-fusion-system`
   ⇒ 可蒸馏成原生位 `hand_retarget`（输入：Vision Pro / Quest3 / 摄像头 / IMU 手套；输出：多手 URDF 关节角），直接接触手遥操作。
2. **手部硬件 ROS2 桥**：`rh56dfx_description` + `inspire-hand-rh56-py` + `rp_dexhand` + `dexterous_hand_ros2` + `tesollo_ros2`
   ⇒ 可蒸馏成 `hand_bridge`（HAL：CAN/CAN-FD/Modbus TCP/串口；URDF/MJCF 描述；ros2_control 适配），补上"真手"驱动层。
3. **抓取合成/操作策略**：`lightning-grasp` + `TransDex` + `AdaDexTrack`
   ⇒ 仅知识/算法参考（非商用许可 + 触觉数据依赖），可用于抓取质量评估与合成思路，不抄代码。

另：两份 awesome 清单（humanoid / loco-manipulation）可当后续自动扫描源；`Mood-Gesture`/`DexFingerGuessing` 可做数字人/触手交互 demo 灵感。

## 五、没吞的 17 个（有意跳过，不是漏）

| 类别 | 数量 | 例子 |
|---|---:|---|
| 自己的仓库（不吞自己） | 1 | `gbtweilai-star/GBTxiaotudouV8-Commander` |
| 同厂/同方向重复，只吞代表件 | 7 | Tesollo 另外 3 变体（dg5f、dg5f_s、sensor_lab）· Roboparty SDK 变体 · rokoko/revo2-d435i（BrainCo 家族）· so-arm101（AmazingHand 生态） |
| 硬件/集成小件（信息量小） | 4 | `realhand_l6_ros2` · `dexterous-hand-md20` · `Linker_Hand-Pressure_sensor` · `omnihand-o10-development` |
| 遥操作小仿真 | 3 | `fairino-fr5-teleop-sim` · `aero-hand-grasp-teleop` · `robotics-internship-integration` |
| 无独立内容/资产 QA | 2 | `physical-ai-toolbox` · `sharpa-wave-asset-qa` |

## 六、复现

```powershell
# 单个仓库（走万能插能力位，受 policy/授权门约束）
py -3.14 -c "import sys;sys.path.insert(0,'.');from gbt_allinone import api;print(api.run_task('devour_github',{'repo':'https://github.com/qqsq12321/AnyDexRetarget'}))"

# 吞后自检
py -3.14 -c "import sys;sys.path.insert(0,'.');from gbt_allinone import api;print(api.run_task('devour_reflect'))"
py -3.14 -c "import sys;sys.path.insert(0,'.');from gbt_allinone import api;print(api.run_task('devour_scan'))"
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
