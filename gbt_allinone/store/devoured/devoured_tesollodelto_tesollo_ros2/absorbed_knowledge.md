# tesollodelto/tesollo_ros2 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:54 | 来源: https://github.com/tesollodelto/tesollo_ros2
> Stars: 4 | 语言: None | 许可: BSD-3-Clause

## 项目概览
- 描述: ROS 2 drivers and control packages for Tesollo robotic hands and grippers, including ros2_control, MoveIt 2, Gazebo simulation, and SDK integration.
- 主题: dexterous-hand, gazebo, moveit2, robot-drivers, robotic-gripper, robotic-hand, robotics, ros2, ros2-control, tesollo
- 分支: main | 最近推送: 2026-10-15

## README 摘要
<div align="center">
  <img src="doc/source/_static/title.svg" alt="TESOLLO ROS 2" width="600" />
  <p>
    Official ROS 2 Packages for TESOLLO Robotic Hands and Grippers
  </p>
  <p>
    <a href="https://github.com/tesollodelto/tesollo_ros2">
      <img src="https://img.shields.io/badge/GitHub-tesollo__ros2-181717?logo=github" alt="GitHub" />
    </a>
    <img src="https://img.shields.io/badge/ROS_2-Humble-blue?logo=ros" alt="ROS 2 Humble" />
    <img src="https://img.shields.io/badge/ROS_2-Jazzy-blue?logo=ros" alt="ROS 2 Jazzy" />
    <img src="https://img.shields.io/badge/ROS_2-Lyrical-orange?logo=ros" alt="ROS 2 Lyrical (experimental)" />
    <img src="https://img.shields.io/badge/License-BSD--3--Clause-green" alt="License" />
  </p>
  <p>
    <a href="https://tesollodelto.github.io/tesollo_ros2/"><strong>Documentation</strong></a>
    ·
    <a href="https://www.tesollo.com/"><strong>TESOLLO Website</strong></a>
  </p>
</div>

Official ROS 2 integration repository for **TESOLLO DELTO robotic hands and grippers**.

This repository brings together model-specific ROS 2 packages and shared development resources for **robot description, ros2_control hardware integration, RViz visualization, Gazebo simulation, MoveIt 2, and TESOLLO SDK-to-ROS 2 integration**.

## CI Status

**Gripper Packages**

| Package | Description | Build |
|---|---|---|
| [dg5f_ros2](https://github.com/tesollodelto/dg5f_ros2) | DG-5F-M 5-finger dexterous robotic hand | [![CI](https://github.com/tesollodelto/dg5f_ros2/actions/workflows/ci.yml/badge.svg)](https://github.com/tesollodelto/dg5f_ros2/actions/workflows/ci.yml) |
| [dg5f_s_ros2](https://github.com/tesollodelto/dg5f_s_ros2) | DG-5F-S compact 5-finger dexterous robotic hand | [![CI](https://github.com/tesollodelto/dg5f_s_ros2/actions/workflows/ci.yml/badge.svg)](https://github.com/tesollodelto/dg5f_s_ros2/actions/workflows/ci.yml) |
| [dg4f_ros2](https://github.com/tesollodelto/dg4f_ros2) | DG-4F 4-finger robotic gripper | [![CI](https://github.com/tesollodelto/dg4f_ros2/actions/workflows/ci.yml/badge.svg)](https://github.com/tesollodelto/dg4f_ros2/actions/workflows/ci.yml) |
| [dg3f_m_ros2](https://github.com/tesollodelto/dg3f_m_ros2) | DG-3F-M 3-finger robotic gripper | [![CI](https://github.com/tesollodelto/dg3f_m_ros2/actions/workflows/ci.yml/badge.svg)](https://github.com/tesollodelto/dg3f_m_ros2/actions/workflows/ci.yml) |
| [dg3f_b_ros2](https://github.com/tesollodelto/dg3f_b_ros2) | DG-3F-B 3-finger gripper (discontinued) | [![CI](https://github.com/tesollodelto/dg3f_b_ros2/actions/workflows/ci.yml/badge.svg)](https://github.com/tesollodelto/dg3f_b_ros2/actions/workflows/ci.yml) |
| [dg2f_ros2](https://github.com/tesollodelto/dg2f_ros2) | DG-2F 2-finger robotic gripper (6 DoF) | — |
| [dg1f_ros2](https://github.com/tesollodelto/dg1f_ros2) | DG-1F articulated vacuum gripper (3 DoF) | — |

**Common Packages**

| Package | Description | Build |
|---|---|---|
| [delto_hardware](https://github.com/tesollodelto/dg_hardware) | ros2_control hardware interface (repo: `dg_hardware`) | [![CI](https://github.com/tesollodelto/dg_hardware/actions/workflows/ci.yml/badge.svg)](https://github.com/tesollodelto/dg_hardware/actions/workflows/ci.yml) |
| [delto_tcp_comm](https://github.com/tesollodelto/dg_tcp_comm) | TCP communication library (repo: `dg_tcp_comm`) | [![CI](https://github.com/tesollodelto/dg_tcp_comm/actions/workflows/ci.yml/badge.svg)](https://github.com/tesollodelto/dg_tcp_comm/actions/workflows/ci.yml) |
| [dg_sdk_ros2_bridge](https://github.com/tesollodelto/dg_sdk_ros2_bridge) | TESOLLO DG SDK bridge + `dg_msgs` | [![CI](https://github.com/tesollodelto/dg_sdk_ros2_bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/tesollodelto/dg_sdk_ros2_bridge/actions/workflows/ci.yml) |

## Supported ROS 2 distributions

`main` is the single source tree for all distributions — there are no per-distro branches.

| Distribution | Status | Notes |
|---|---|---|
| Humble | Supported | Built in CI |
| Jazzy | Supported | Built in CI |
| Lyrical | **Experimental** | Built in CI, allowed to fail; not validated on hardware |

Distro differences are handled by feature detection, not by branching:
`ament_target_dependencies()` (removed in Lyrical's `ament_cmake`) is selected with
`if(COMMAND ...)`, and the `on_init()` hardware-interface signature (changed in
`hardware_interface` 4.x) with `__has_include`. The same sources build against
`hardware_interface` 2.x, 4.x and 6.x.

> The former `jazzy` and `lyrical` branches are superseded by `main` and are no
> longer updated. Use `main`.

## Architecture

This repository uses a **per-model submodule** structure with shared common packages:

- Each gripper or robotic hand model (`dg1f`, `dg2f`, `dg3f_b`, `dg3f_m`, `dg4f`, `dg5f`, `dg5f_s`) has its own independent repository, included here as a git submodule.
- `dg_common` contains shared packages: `dg_tcp_comm` and `dg_hardware` (managed as submodules).
- `dg_sdk_ros2_bridge` bridges the TESOLLO DG SDK with ROS 2, and includes `dg_msgs` (message/service definitions).

### Why this structure?

- **Individual product deployment** - Customers using only one model can clone this repo and initialize only the submodule they need.
- **Independent versioning** - Each model can be released and tagged independently.
- **Full integration** - This parent repo aggregates everything for development and CI.

## Repository Structure

```text
tesollo_ros2/
├── dg1f_ros2/            # [submodule] DG-1F articulated vacuum gripper
│   ├── dg1f_description/
│   └── dg1f_driver/
│
├── dg2f_ros2/            # [submodule] DG-2F 2-finger gripper
│   ├── dg2f_description/
│   └── dg2f_driver/
│
├── dg3f_b_ros2/          # [submodule] DG-3F-B 3-finger gripper (discontinued)
│   ├── dg3f_b_description/
│   └── dg3f_b_driver/
│
├── dg3f_m_ros2/          # [submodule] DG-3F-M 3-finger gripper
│   ├── dg3f_m_description/
│   ├── dg3f_m_driver/
│   └── dg3f_m_gz/
│
├── dg4f_ros2/            # [submodul

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识