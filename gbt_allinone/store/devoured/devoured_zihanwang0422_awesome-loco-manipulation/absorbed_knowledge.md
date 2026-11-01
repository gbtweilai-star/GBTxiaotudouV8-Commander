# zihanwang0422/awesome-loco-manipulation 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:32 | 来源: https://github.com/zihanwang0422/awesome-loco-manipulation
> Stars: 9 | 语言: None | 许可: unknown

## 项目概览
- 描述: Paper and Github repos about locomotion, manipulation and loco-manipulation.
- 主题: dexterous-hand, dexterous-manipulation, loco-manipulation, whole-body-control
- 分支: main | 最近推送: 2026-09-07

## README 摘要
# Awesome-Loco-Manipulation

## Table of Contents

1. [Manipulation](manipulation.md)
2. [Dexterous Hand Manipulation](dexterous_manipulation.md)
3. [Locomotion](locomotion.md)
4. [Mobile Manipulation](#4-mobile-manipulation)
5. [Legged Loco-Manipulation](#5-legged-loco-manipulation)
6. [Whole-Body Control & Loco-Manipulation](#6-whole-body-control--loco-manipulation)
   - [6.1 Motion Tracking](#61-motion-tracking)
   - [6.2 Loco-Manipulation](#62-loco-manipulation)
     - [6.2.1 TeleOp](#621-teleop)
     - [6.2.2 Contact-Rich Loco-Manipulation](#622-contact-rich-loco-manipulation)
     - [6.2.3 VLA](#623-vlavision-language-action)
     - [6.2.4 WAM](#624-wamworld-action-models)
   - [6.3 Real2Sim & Parkour](#63-real2sim--parkour)
   - [6.4 Behavior Foundation Models (BFM)](#64-behavior-foundation-models-bfm)
   - [6.5 VisionMimic / Sports](#65-visionmimic--sports)
7. [Animation / Motion Synthesis](#7-animation--motion-synthesis)
   - [7.1 Mimic](#71-mimic)
   - [7.2 InterMimic](#72-intermimic)
   - [7.3 MeshMimic](#73-meshmimic)
   - [7.4 MimicGen](#74-mimicgen)
     - [7.4.1 Kinematic Motion Generation](#741-kinematic-motion-generation)
     - [7.4.2 Latent Motion Generation](#742-latent-motion-generation)
     - [7.4.3 Physics-Based Latent Skill / Generative Controller](#743-physics-based-latent-skill--generative-controller)
     - [7.4.4 Physics-Based Tracking / Planning / Control](#744-physics-based-tracking--planning--control)
     - [7.4.5 Supporting Motion Models](#745-supporting-motion-models)

## 4. Mobile Manipulation

| Year | Title | Paper | GitHub |
|:----:|-------|-------|--------|
| 2026 | **WHOLE-MoMa** | [arXiv 2026.04](https://www.alphaxiv.org/abs/2604.12509) | — |
| 2025 | **SAGA: Open-World Mobile Manipulation via Structured Affordance Grounding** | [arXiv 2025.12](https://www.alphaxiv.org/abs/2512.12842) | — |
| 2025 | **CuriousBot: Interactive Mobile Exploration via Actionable 3D Relational Object Graph** | [arXiv 2025.01](https://www.alphaxiv.org/abs/2501.13338) | — |
| 2025 | **Dynamic Object Goal Pushing with Mobile Manipulators through Model-Free Constrained Reinforcement Learning** | [arXiv 2025.02](https://www.alphaxiv.org/abs/2502.01546) | — |
| 2025 | **VidBot: Learning Generalizable 3D Actions from In-the-Wild 2D Human Videos for Zero-Shot Robotic Manipulation** | [arXiv 2025.03](https://www.alphaxiv.org/abs/2503.07135) | [GitHub](https://github.com/ethz-mrl/VidBot) |
| 2025– | **BEHAVIOR Robot Suite** | [arXiv 2025](https://www.alphaxiv.org/search?q=BEHAVIOR+Robot+Suite) | [GitHub](https://github.com/behavior-robot-suite/brs-algo) |
| 2025 | **BiGym** | [arXiv 2025](https://www.alphaxiv.org/search?q=BiGym) | [GitHub](https://github.com/chernyadev/bigym) |
| 2025 | **Open-World Mobile Manipulation** | [arXiv 2025](https://www.alphaxiv.org/search?q=Open-World+Mobile+Manipulation) | — |
| 2025 | **EMMA** | [arXiv 2025](https://www.alphaxiv.org/search?q=EMMA) | — |
| 2024 | **Mobile ALOHA** | [arXiv 2024](https://www.alphaxiv.org/search?q=Mobile+ALOHA) | [GitHub](https://github.com/MarkFzp/mobile-aloha) |
| 2024 | **OK-Robot: What Really Matters in Integrating Open-Knowledge Models for Robotics** | [arXiv 2024](https://www.alphaxiv.org/search?q=OK-Robot%3A+What+Really+Matters+in+Integrating+Open-Knowledge+Models+for+Robotics) | [GitHub](https://github.com/ok-robot/ok-robot) |
| 2024 | **MoMa-LLM: Language-Grounded Dynamic Scene Graphs for Interactive Object Search** | [arXiv 2024](https://www.alphaxiv.org/search?q=MoMa-LLM%3A+Language-Grounded+Dynamic+Scene+Graphs+for+Interactive+Object+Search) | [GitHub](https://github.com/robot-learning-freiburg/MoMa-LLM) |
| 2024 | **TidyBot++** | [arXiv 2024](https://www.alphaxiv.org/search?q=TidyBot%2B%2B) | [GitHub](https://github.com/jimmyyhwu/tidybot2) |
| 2024 | **SPIN: Simultaneous Perception, Interaction and Navigation** | [arXiv 2024](https://www.alphaxiv.org/search?q=SPIN%3A+Simultaneous+Perception%2C+Interaction+and+Navigation) | — |
| 2024 | **Learning Generalizable Feature Fields for Mobile Manipulation** | [arXiv 2024.03](https://www.alphaxiv.org/abs/2403.07563) | — |
| 2024 | **Catch It! Learning to Catch in Flight with Mobile Dexterous Hands** | [arXiv 2024.09](https://www.alphaxiv.org/abs/2409.10319) | [GitHub](https://github.com/hang0610/Catch_It) |
| 2024 | **Continuously Improving Mobile Manipulation with Autonomous Real-World RL** | [arXiv 2024.09](https://www.alphaxiv.org/abs/2409.20568) | — |
| 2024 | **Adaptive Language-Guided Abstraction from Contrastive Explanations** | [arXiv 2024.09](https://www.alphaxiv.org/abs/2409.08212) | [GitHub](https://github.com/rai-opensource/predicators) |
| 2023 | **HomeRobot: Open-Vocabulary Mobile Manipulation** | [arXiv 2023](https://www.alphaxiv.org/search?q=HomeRobot%3A+Open-Vocabulary+Mobile+Manipulation) | [GitHub](https://github.com/facebookresearch/home-robot) |
|   |   |   | [Back to top ↑](#table-of-contents) |

## 5. Legged Loco-Manipulation

| Year | Title | Paper | GitHub |
|:----:|-------|-------|--------|
| 2026 | **TAC-LOCO: Unified Whole-Body Control for Quadrupedal TACtile-Informed LOCO-Manipulation** | [arXiv 2026.07](https://www.alphaxiv.org/abs/2607.10132) | — |
| 2026 | **FT-WBC: Learning Fault-Tolerant Whole-Body Control for Legged Loco-Manipulation** | [arXiv 2026.06](https://www.alphaxiv.org/abs/2606.24466) | — |
| 2026 | **Learning Terrain-Aware Whole-Body Control for Perceptive Legged Loco-Manipulation** | [arXiv 2026.05](https://www.alphaxiv.org/abs/2605.31343) | — |
| 2026 | **Learning Tactile-Aware Quadrupedal Loco-Manipulation Policies** | [arXiv 2026.04](https://www.alphaxiv.org/abs/2604.27224) | — |
| 2026 | 🌟️ **Sumo: Dynamic and Generalizable Whole-Body Loco-Manipulation** | [arXiv 2026.04](https://www.alphaxiv.org/abs/2604.08508) | [GitHub](https://github.com/rai-opensource/sumo) |
| 2026 | 🌟️ **BinWalker: Development and Field Evaluation of a Quadruped Manipulator Platform for Sustainable Litter Collection** | [arXiv 2026.03](http

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识