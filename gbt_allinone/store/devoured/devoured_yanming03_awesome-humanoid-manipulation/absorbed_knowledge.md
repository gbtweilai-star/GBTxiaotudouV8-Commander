# yanming03/awesome-humanoid-manipulation 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:30 | 来源: https://github.com/yanming03/awesome-humanoid-manipulation
> Stars: 164 | 语言: None | 许可: unknown

## 项目概览
- 描述: A curated list of awesome papers and resources on humanoid manipulation, dexterous manipulation, bimanual dexterous manipulation, in-hand manipulation, and humanlike manipulation.
- 主题: awesome, awesome-list, bimanual-manipulation, dexterous-grasping, dexterous-hand, dexterous-manipulation, humanlike-manipulation, humanoid-manipulation, humanoid-robot, imitation-learning
- 分支: main | 最近推送: 2026-06-11

## README 摘要
# Awesome Humanoid & Dexterous Manipulation
[![Awesome](https://awesome.re/badge.svg)](https://awesome.re)
[![Made With Love](https://img.shields.io/badge/Made%20With-Love-red.svg)](https://github.com/chetanraj/awesome-github-badges)

A curated list of awesome papers and resources on **humanoid manipulation**, **dexterous manipulation**, **bimanual dexterous manipulation**, and **humanlike manipulation**. This repo covers upper-body humanoid robot learning, multi-fingered hand manipulation, in-hand object reorientation, and related topics. Inspired by [awesome-humanoid-learning](https://github.com/jonyzhang2023/awesome-humanoid-learning).

**Keywords**: awesome humanoid manipulation, awesome dexterous manipulation, awesome bimanual manipulation, awesome dexterous hand, awesome humanoid robot, awesome robot hand manipulation, in-hand manipulation, dexterous grasping

_Scope_: This list covers the following topics:

1. Humanoid robot manipulation and loco-manipulation
2. Dexterous hand manipulation (single-hand, in-hand reorientation, dexterous grasping)
3. Bimanual dexterous multi-fingered manipulation
4. Dual-arm manipulation with other end effectors
5. Teleoperation and human-to-robot retargeting for dexterous tasks
6. Physically simulated humanoid animations and digital human-object interaction

**Contributions are welcome!** Please feel free to submit a pull request or open an issue.

---

## Contents
- [Awesome Humanoid \& Dexterous Manipulation](#awesome-humanoid--dexterous-manipulation)
  - [Contents](#contents)
  - [Robot Models](#robot-models)
    - [Humanoids](#humanoids)
    - [Dexterous Hands](#dexterous-hands)
    - [Dual-Arm Robots](#dual-arm-robots)
  - [Simulation Environments \& Benchmarks](#simulation-environments--benchmarks)
  - [Workshops](#workshops)
  - [Projects](#projects)
  - [Packages](#packages)
  - [Related Awesome Lists](#related-awesome-lists)
  - [Papers](#papers)
    - [Surveys](#surveys)
    - [Humanoid Robot Manipulation](#humanoid-robot-manipulation)
    - [Dexterous Hand Manipulation](#dexterous-hand-manipulation)
    - [Bimanual Dexterous Multi-Fingered Manipulation](#bimanual-dexterous-multi-fingered-manipulation)
    - [Teleoperation \& Human-to-Robot Retargeting](#teleoperation--human-to-robot-retargeting)
    - [Dual-Arm Manipulation with Other End Effectors](#dual-arm-manipulation-with-other-end-effectors)
    - [Physically Simulated Humanoid Animations and Digital Human-Object Interaction](#physically-simulated-humanoid-animations-and-digital-human-object-interaction)
  - [Close Reading](#close-reading)


<a name="Models" />

## Robot Models

<a name="Humanoids" />

### Humanoids

| Name | Maker | Formats | License | Meshes | Inertias | Collisions |
|------|-------|---------|---------|--------|----------|------------|
| H1 | Unitree | [URDF & MJCF](https://github.com/unitreerobotics/unitree_ros/tree/master/robots/h1_description), [USD](https://github.com/unitreerobotics/unitree_model/tree/main/H1/usd) | BSD-3-Clause | ✔️ | ✔️ | ✔️ |
| H1-2 (preview) | Unitree | [URDF & MJCF](https://github.com/unitreerobotics/unitree_rl_gym/tree/main/resources/robots/h1_2), [Simplified URDF](https://github.com/unitreerobotics/unitree_rl_gym/tree/main/resources/robots/h1_2) | BSD-3-Clause | ✔️ | ✔️ | ✔️ |
| G1 | Unitree | [URDF & MJCF](https://github.com/unitreerobotics/unitree_ros/tree/master/robots/g1_description) | BSD-3-Clause | ✔️ | ✔️ | ✔️ |
| GR-1 | FFTAI (Fourier) | [URDF](https://github.com/FFTAI/Wiki-GRx-Models/tree/master/GRX/GR1), [MJCF](https://github.com/FFTAI/wiki-mjcf/) | GPL-3.0 | ✔️ | ✔️ | ✔️ |
| GR-2 | FFTAI (Fourier) | [URDF](https://github.com/FFTAI/Wiki-GRx-Models) | GPL-3.0 | ✔️ | ✔️ | ✔️ |
| AgiBot X1 | AgiBot | [URDF & MJCF](https://github.com/AgibotTech/agibot_x1_train) | Apache-2.0 | ✔️ | ✔️ | ✔️ |
| Atlas v4 | Boston Dynamics | [URDF](https://github.com/openai/roboschool/tree/1.0.49/roboschool/models_robot/atlas_description) | MIT | ✔️ | ✔️ | ✔️ |
| Digit | Agility Robotics | [URDF](https://github.com/adubredu/DigitRobot.jl/tree/main/urdf) | ✖️ | ✔️ | ✔️ | ✔️ |
| Magicbot Z1 | Magiclab | [URDF](https://github.com/MagiclabRobotics/magicbot-z1_description) | ✖️ | ✔️ | ✔️ | ✔️ |
| Deep Robotics | Deep Robotics | [URDF](https://github.com/DeepRoboticsLab/URDF_model) | ✖️ | ✔️ | ✔️ | ✔️ |
| Berkeley Humanoid Lite | UC Berkeley | [URDF, MJCF, USD](https://github.com/HybridRobotics/Berkeley-Humanoid-Lite) | Open Source | ✔️ | ✔️ | ✔️ |
| Berkeley Humanoid | UC Berkeley | [URDF](https://github.com/HybridRobotics/berkeley_humanoid_description) | Open Source | ✔️ | ✔️ | ✔️ |

Also see: [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) for high-quality MJCF models, [awesome-robot-descriptions](https://github.com/robot-descriptions/awesome-robot-descriptions) for a comprehensive list.

<a name="DexterousHands" />

### Dexterous Hands

| Name | Maker | Formats | License | Meshes | Inertias | Collisions |
|------|-------|---------|---------|--------|----------|------------|
| Ability Hand | PSYONIC, Inc. | [MJCF](https://github.com/psyonicinc/ability-hand-api/tree/master/URDF/mujoco), [URDF](https://github.com/psyonicinc/ability-hand-api/tree/master/URDF) | ✖️ | ✔️ | ✔️ | ✖️ |
| Allegro Hand | Wonik Robotics | [URDF](https://github.com/RobotLocomotion/models/tree/master/allegro_hand_description/urdf), [MJCF](https://github.com/google-deepmind/mujoco_menagerie/tree/main/wonik_allegro) | BSD | ✔️ | ✔️ | ✔️ |
| Shadow Hand | Shadow Robot | [URDF](https://github.com/shadow-robot/sr_common/tree/noetic-devel/sr_description/mujoco_models/urdfs), [MJCF](https://github.com/google-deepmind/mujoco_menagerie/tree/main/shadow_hand) | BSD | ✔️ | ✔️ | ✔️ |
| LEAP Hand | Carnegie Mellon | [URDF](https://github.com/leap-hand/LEAP_Hand_Sim/tree/main/assets) | MIT | ✔️ | ✔️ | ✔️ |
| Inspire Hand | Inspire-Robots | [URDF](https://github.com/dexsuite/dex-urdf) | ✖️ | ✔️ | ✔️ | ✔️ |
| ORCA Hand | ORCA Robotics | [URDF & MJCF](https://github.com/orca

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识