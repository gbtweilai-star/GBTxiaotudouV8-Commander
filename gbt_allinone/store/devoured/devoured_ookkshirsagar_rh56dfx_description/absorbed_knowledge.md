# ookkshirsagar/rh56dfx_description 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:48 | 来源: https://github.com/ookkshirsagar/rh56dfx_description
> Stars: 16 | 语言: Python | 许可: MIT

## 项目概览
- 描述: ROS 2 URDF description package for the Inspire Robotics RH56DFX 6-DOF dexterous hand. Supports left and right variants with mesh geometry, joint limits, RViz visualisation, and ros2_control integration.
- 主题: ai, dexterous-hand, grasp-planning, imitation-learning, inspire-robotics, isaac-sim, manipulation, moveit2, reinforcement-learning, rh56dfx
- 分支: main | 最近推送: 2026-02-25

## README 摘要
# rh56dfx_description

A ROS 2 URDF/xacro description package for the **Inspire Robotics RH56DFX** 6-DOF dexterous robotic hand. Supports both **left** and **right** hand variants with full mesh geometry, joint limits, and ros2_control integration.

> **Credits:** The RH56DFX hand hardware is designed and manufactured by [Inspire Robotics](http://www.inspire-robots.com). This ROS 2 description package provides URDF/xacro models and ros2_control configuration for simulation and integration purposes.

---

## Overview

The RH56DFX is a high-performance dexterous hand with 6 degrees of freedom featuring:
- **4 fingers** (index, middle, ring, little) each with 2 links + rubber pads + fingertip
- **1 thumb** with 4 links + rubber pads + fingertip
- **Wrist** with yaw and base rotation joints
- **Mimic joints** for realistic multi-link finger curling from a single actuator command
- **Palm** link with soft contact geometry
- Compact aluminium construction designed for mounting on industrial robot arms


This package provides everything needed to:
- Visualise the hand in RViz
- Integrate it into a larger robot URDF via xacro macros
- Control it with ros2_control JointTrajectoryController

---

## Package Contents

```
rh56dfx_description/
├── config/
│   ├── left/
│   │   ├── joint_limits.yaml       # Left hand joint position/velocity limits
│   │   ├── joint_names.yaml        # Left hand joint name definitions
│   │   └── ros2_controllers.yaml   # Left hand ros2_control config
│   └── right/
│       ├── joint_limits.yaml       # Right hand joint position/velocity limits
│       ├── joint_names.yaml        # Right hand joint name definitions
│       └── ros2_controllers.yaml   # Right hand ros2_control config
├── launch/
│   └── display.launch.py           # Visualisation launch with RViz + joint sliders
├── meshes/
│   ├── left/
│   │   ├── collision/              # Simplified collision STL meshes (left)
│   │   └── visual/                 # High-resolution visual STL meshes (left)
│   └── right/
│       ├── collision/              # Simplified collision STL meshes (right)
│       └── visual/                 # High-resolution visual STL meshes (right)
├── rviz/
│   ├── rh56dfx_left.rviz           # Pre-configured RViz layout for left hand
│   └── rh56dfx_right.rviz          # Pre-configured RViz layout for right hand
├── tutorials/
│   ├── 01_visualise_the_hand.md         # Launch, RViz navigation, joint sliders, hand poses
│   ├── 02_embed_in_your_robot.md        # Integrate the hand into your own robot URDF
│   ├── 03_understanding_mimic_joints.md # What mimic joints are and how to command correctly
│   └── 04_xacro_vs_macro.md             # When to use rh56dfx.xacro vs rh56dfx_macro.xacro
└── urdf/
    ├── rh56dfx.xacro               # Top-level hand URDF (standalone visualisation only)
    ├── rh56dfx_macro.xacro         # Reusable xacro macro for embedding in larger robots
    ├── rh56dfx_left.csv            # Left hand joint parameter data
    └── rh56dfx_right.csv           # Right hand joint parameter data
```

---

## Requirements

| Dependency | Version |
|---|---|
| ROS 2 | Jazzy (Ubuntu 24.04) |
| robot_state_publisher | — |
| joint_state_publisher_gui | — |
| rviz2 | — |
| ros2_control | — |
| xacro | — |

```bash
sudo apt install \
  ros-jazzy-robot-state-publisher \
  ros-jazzy-joint-state-publisher-gui \
  ros-jazzy-rviz2 \
  ros-jazzy-ros2-control \
  ros-jazzy-xacro
```

---

## Installation

```bash
# Clone into your ROS 2 workspace
cd ~/ros2_ws/src
git clone https://github.com/ookkshirsagar/rh56dfx_description.git

# Build
cd ~/ros2_ws
colcon build --packages-select rh56dfx_description --symlink-install
source install/setup.bash
```

---

## Usage

### Visualise in RViz

Launch the hand in RViz with an interactive joint slider GUI:

```bash
# Left hand (default)
ros2 launch rh56dfx_description display.launch.py

# Right hand
ros2 launch rh56dfx_description display.launch.py side:=right
```

**Launch arguments:**

| Argument | Default | Description |
|---|---|---|
| `side` | `left` | Hand variant — `left` or `right` |
| `prefix` | `""` | Prefix added to all link and joint names |
| `use_world` | `false` | Attach a fixed `world` link as root for standalone use |

This opens RViz with the hand model and a Joint State Publisher GUI for manually moving all finger joints.

> RViz configs are pre-saved in `rviz/rh56dfx_left.rviz` and `rviz/rh56dfx_right.rviz` and loaded automatically by the launch file.

---

### Embed in Your Robot URDF

Use the provided xacro macro to attach the RH56DFX hand to any humanoid/robot arm:

```xml
<!-- In your robot's xacro file -->
<xacro:include filename="$(find rh56dfx_description)/urdf/rh56dfx_macro.xacro"/>

<!-- Attach left hand to your robot's tool flange -->
<xacro:rh56dfx_hand
    side="left"
    prefix="left_"/>

<!-- Then connect left_hand_root to your robot's flange with a fixed joint -->
<joint name="flange_to_hand" type="fixed">
  <parent link="tool0"/>
  <child link="left_hand_root"/>
</joint>

<!-- Attach right hand to your robot's tool flange -->
<xacro:rh56dfx_hand
    side="right"
    prefix="right_"/>

<!-- Then connect right_hand_root to your robot's flange with a fixed joint -->
<joint name="flange_to_hand" type="fixed">
  <parent link="tool0"/>
  <child link="right_hand_root"/>
</joint>
```

**Macro parameters:**

| Parameter | Description |
|---|---|
| `side` | Hand variant — `left` or `right` |
| `prefix` | Prepended to all link/joint names. Use e.g. `left_` or `right_` to avoid name collisions |

> **Note:** The macro creates a `{prefix}hand_root` link as the kinematic anchor. Connect your robot's flange to this link with a fixed joint.

---

## Kinematic Structure

```
{prefix}hand_root
└── {prefix}wrist_base_link       (fixed)
    └── {prefix}wrist_yaw          (revolute — wrist_yaw_joint)
        └── {prefix}hand_base      (revolute — hand_base_joint)
            ├── {prefix}thumb_1    (revolute — thumb_1_joint)
         

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识