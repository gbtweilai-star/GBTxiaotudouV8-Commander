# qqsq12321/AnyDexRetarget 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:42 | 来源: https://github.com/qqsq12321/AnyDexRetarget
> Stars: 92 | 语言: Python | 许可: MIT

## 项目概览
- 描述: High-precision hand pose retargeting for multiple dexterous hands. Supports Vision Pro, Quest 3, camera, and more.
- 主题: dexterous-hand, hand-tracking, mujoco, quest3, retargeting, robotics, teleoperation, vision-pro
- 分支: master | 最近推送: 2026-10-29

## README 摘要
[中文](README.zh.md) | English

# AnyDexRetarget

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

High-precision hand pose retargeting system. Supports three optimizers, multiple dexterous hands, and multiple hand-tracking input sources for simulation and reality.

## Demo

### Simulation Retargeting

https://github.com/user-attachments/assets/0950b2b0-ecd4-4270-abf6-5729dc05c6cb

### Quest 3 Hand-Arm Teleoperation

https://github.com/user-attachments/assets/4bcac46b-a603-4c0c-9d70-83d4351c9811

### Apple Vision Pro Teleoperation

https://github.com/user-attachments/assets/dccdb649-4a20-422a-979c-2b1301e8836b

### Pico 4 + Linker L20 Teleoperation

https://github.com/user-attachments/assets/f6d87bf8-281f-4665-9023-111c90308ce2

### Pico 4 + Gaia Hand20 Teleoperation

https://github.com/user-attachments/assets/e3a2432a-129f-4b76-98c7-a4834b7240ba

## Related Projects

- [vr_teleop](https://github.com/qqsq12321/vr_teleop) - VR hand-tracking teleoperation for **robot arms**. Covers Kinova Gen3, Realman RM65 (single and dual arm), Piper, DexForce, and Aloha in simulation and/or on real hardware, and pulls in AnyDexRetarget as a submodule for the dexterous-hand part. Use it when you need arm motion as well as finger retargeting.

## Features

- **13 Robot Hands**: Shadow, Wuji, Allegro, Inspire, Ability, Leap, SVH, LinkerHand L21, Linker L20, ROHand, Unitree Dex5, Sharpa, and Gaia Hand20
- **Three Optimizers**: `adaptive` (pinch-aware, default), `vector` (key-vector matching), and `dexpilot` (adaptive distance projection for grasping)
- **High-Precision Pinch**: Adaptive optimization for accurate finger-to-thumb contact
- **Real-time Performance**: Analytical gradients + NLopt SLSQP (~2ms per frame)
- **Multiple Input Sources**: Apple Vision Pro, Meta Quest 3, Noitom PNS-G gloves, laptop camera (MediaPipe), recorded data replay

## Table of Contents

- [Related Projects](#related-projects)
- [Supported Robots](#supported-robots)
- [Repository Structure](#repository-structure)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Citation](#citation)
- [Acknowledgement](#acknowledgement)
- [Contact](#contact)

## Supported Robots

Config files are organized by **optimizer type** and **input source**:

```
example/config/
├── adaptive/          # AdaptiveOptimizerAnalytical (default)
│   ├── mediapipe/     # camera / video / replay input
│   ├── avp/           # Apple Vision Pro input
│   ├── quest3/        # Meta Quest 3 input
│   ├── pico4/         # Pico 4 input
│   └── noitom/        # Noitom PNS-G gloves
└── vector/            # KeyVectorOptimizer
    ├── mediapipe/
    ├── avp/
    ├── quest3/
    ├── pico4/
    └── noitom/
```

| Robot | `--robot` value | Config suffix | Description |
|-------|------------------|---------------|-------------|
| **Shadow Hand** | `shadow` | `shadow_hand` | Shadow Hand with MuJoCo Menagerie meshes (default sim target) |
| **Wuji Hand** | `wuji` | `wuji_hand` | Wuji Hand, 5 fingers / 20 DOF |
| **Allegro Hand** | `allegro` | `allegro_hand` | Allegro Hand, 4 fingers / 16 DOF |
| **Inspire Hand** | `inspire` | `inspire_hand` | Inspire Hand with mimic joints |
| **Ability Hand** | `ability` | `ability_hand` | Ability Hand with mimic joints |
| **Leap Hand** | `leap` | `leap_hand` | Leap Hand, 4 fingers / 16 DOF |
| **SVH Hand** | `svh` | `svh_hand` | Schunk SVH Hand with mimic joints |
| **LinkerHand L21** | `linkerhand_l21` | `linkerhand_l21` | LinkerHand L21 |
| **Linker L20** | `linker_l20` | `linker_l20` | DexForce Linker L20, 5 fingers / 21 revolute joints with mimic joints |
| **ROHand** | `rohand` | `rohand` | ROHand |
| **Unitree Dex5** | `unitree_dex5` | `unitree_dex5_hand` | Unitree Dex5 |
| **Sharpa Hand** | `sharpa` | `sharpa_hand` | Sharpa Wave Hand, 5 fingers / 22 DOF |
| **Gaia Hand20** | `gaia` | `gaia_hand20` | Gaia Hand20, 5 fingers |

> **Note on Noitom configs:** Only `shadow_hand`, `wuji_hand`, and `inspire_hand` have been roughly calibrated for Noitom input. If you need to fine-tune the mapping accuracy between your hand and the robot hand, run `debug_skeleton.py` to visualize four skeletons side-by-side: **Blue** = raw input, **Yellow** = uniformly scaled by `pinch_scaling`, **Green** = after segment scaling, **Red** = retargeted FK result. Compare the skeleton sizes and adjust the corresponding YAML config parameters (`scaling`, `segment_scaling`, `key_vectors[].scale`, etc.) accordingly.
>
> ```bash
> cd example
> python test/debug_skeleton.py --robot inspire --input noitom --noitom-local-ip 192.168.5.25
> ```

## Repository Structure

```text
├── anydexretarget/
│   ├── retarget.py                        # High-level unified interface
│   ├── robot.py                           # Pinocchio robot wrapper
│   ├── mediapipe.py                       # MediaPipe coordinate transforms
│   └── optimizer/                         # Optimizer implementations
│       ├── base_optimizer.py              # Base optimizer with FK/Jacobian
│       ├── analytical_optimizer.py        # AdaptiveOptimizerAnalytical
│       ├── key_vector_optimizer.py        # KeyVectorOptimizer
│       ├── dexpilot_optimizer.py          # DexPilotOptimizer
│       ├── robot_configs.py               # Robot link/URDF configurations
│       └── utils.py                       # TimingStats, LPFilter, Huber loss
├── example/
│   ├── teleop_sim.py                      # MuJoCo simulation demo
│   ├── teleop_real.py                     # Real hardware control
│   ├── input/                             # Input device modules
│   │   ├── cli.py                         # Shared --input / per-device options
│   │   ├── landmark_utils.py              # Shared MediaPipe landmark processing
│   │   ├── camera.py / video.py / ...     # Input devices
│   │   └── noitom.py                      # Noitom PNS-G glove input
│   ├── output/                            # Retarget-output post-processing, one script per h

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识