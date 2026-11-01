# Bobyue0118/BrainCo-Revo2-Dex-Retargeting 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:44 | 来源: https://github.com/Bobyue0118/BrainCo-Revo2-Dex-Retargeting
> Stars: 38 | 语言: Python | 许可: MIT

## 项目概览
- 描述: 支持BrainCo Revo2灵巧手（实时）重定向及手部动作生成  / Real-time Dex-retargeting & Hand Control
- 主题: dexterous-hand, retargeting-motion
- 分支: main | 最近推送: 2026-04-29

## README 摘要
# 📚 BrainCo Hand Retargeting System

**Version 2.1.0** - Complete hand motion retargeting from video/image to robotic hand control

---

## ✨ Key Features

- 🎥 **Video Processing** - Extract hand motion from any video
- 🖼️ **Image Support** - Process single images or image sequences
- 🔄 **Complete Pipeline** - Images → 6-DOF control + rendered hand poses
- 🤖 **Smart Retargeting** - Map human joints to 11-DOF robotic hand
- 🎮 **3D Visualization** - PyBullet (fast & interactive) & SAPIEN (realistic)
- ⚡ **Real-time Mode** - See webcam/video, detected hand landmarks, and 3D BrainCo hand together
- 🙌 **Both-Hand Realtime Mode** - Detect and retarget left and right hands together in a 3-panel webcam view
- 📊 **Data Analysis** - Visualize trajectories and statistics
- 🤖 **6-DOF Control** - Export controllable joint commands for robot

---

## 🖼️ Both-Hand Realtime Demo

![Both-hand realtime webcam visualization](demo.gif)

Realtime webcam mode now supports `--hand both`, with the scene on the left, left-hand retargeting in the middle, and right-hand retargeting on the right.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Core dependencies (mediapipe, opencv, etc.)
pip install -r requirements.txt

# PyBullet for 3D visualization:
# ⚠️ macOS Apple Silicon (M1/M2/M3/M4): pip install will fail, use conda
conda install -c conda-forge pybullet

# Linux / Windows
pip install pybullet

# Optional: SAPIEN for advanced visualization (Linux/Windows only)
# pip install sapien
```

### 2. Run

```bash
# Video retargeting (generates hand_trajectory.json)
python hand_retargeting.py \
    --video human_hand_video.mp4 \
    --urdf brainco_hand/brainco_right.urdf \
    --hand right

# Complete pipeline: images → 6-DOF control
python image_to_6dof_pipeline.py \
    --input image_frames/ \
    --hand right \
    --output result/

# 3D visualization with PyBullet
python visualize_revo2_hand.py \
    --urdf brainco_hand/brainco_right.urdf \
    --trajectory hand_trajectory.json \
    --loop

# Realtime webcam visualization
python realtime_visualize.py \
    --camera-index 0 \
    --urdf brainco_hand/brainco_right.urdf \
    --hand right

# Realtime webcam visualization for both hands
python realtime_visualize.py \
    --camera-index 0 \
    --hand both \
    --left-urdf brainco_hand/brainco_left.urdf \
    --right-urdf brainco_hand/brainco_right.urdf
```

---

## 🤖 Supported Hand Models

| Model | URDF Path | Status |
|---|---|---|
| BrainCo Hand ⭐ | `brainco_hand/brainco_right.urdf` | Recommended |
| Revo2 Original | `Revo2_URDF Description_ROS2/revo2_description/urdf/revo2_right_hand.urdf` | Legacy |

Both support left/right hand variants and the same 11-DOF joint structure.

---

## 🤖 BrainCo Hand Control (6-DOF)

The BrainCo hand has **11 DOF** total, but only **6 are controllable**:

### Controllable Joints (6 DOF):
- Thumb: metacarpal + proximal (2 DOF)
- Index, Middle, Ring, Pinky: proximal each (4 DOF)

### Mimic Joints (5 DOF - auto-computed):
All distal joints automatically follow their proximal joints via URDF mimic:
- `thumb_distal` = 1.0 × `thumb_proximal`
- `index_distal` = 1.155 × `index_proximal`
- `middle_distal` = 1.155 × `middle_proximal`
- `ring_distal` = 1.155 × `ring_proximal`
- `pinky_distal` = 1.155 × `pinky_proximal`

### Output Files:
- `hand_trajectory.json` - Full 11-DOF trajectory (all joints)
- `hand_trajectory_6dof.json` - 6-DOF controllable trajectory (for robot control) ⭐

Use `dof6_control.py` to export the 6-DOF trajectory to CSV/NumPy/text format for your robot control system!

---

## 📂 Project Structure

```
BrainCo-Revo2-Dex-Retargeting/
├── brainco_hand/                      # BrainCo hand URDF models
│   ├── brainco_right.urdf
│   ├── brainco_left.urdf
│   └── meshes/                        # STL mesh files
├── hand_retargeting.py                # Core: video → joint angles
├── image_retargeting.py               # Image / sequence retargeting
├── image_to_6dof_pipeline.py          # End-to-end pipeline
├── dof6_control.py                    # 6-DOF trajectory export
├── visualize_revo2_hand.py            # PyBullet 3D visualization
├── realtime_visualize.py              # Real-time video + 3D mode
├── visualize_trajectory.py            # 2D trajectory plot (11-DOF)
├── visualize_trajectory_6dof.py       # 2D trajectory plot (6-DOF)
├── render_hand_poses.py               # Headless batch image rendering
├── examples.py                        # API usage examples (6 examples)
├── requirements.txt                   # Python dependencies
└── Revo2_URDF Description_ROS2/       # Original Revo2 URDF
```

---

## 🎮 Visualization Options

| Script | Mode | macOS |
|---|---|---|
| `visualize_revo2_hand.py` | PyBullet 3D replay | ✅ |
| `realtime_visualize.py` | Video + 3D single-hand or both-hand view | ✅ |
| `visualize_trajectory_6dof.py` | 6-DOF curve plots | ✅ |
| `visualize_trajectory.py` | 11-DOF curve plots | ✅ |
| `visualize_sapien.py` | SAPIEN advanced render | ❌ |

### PyBullet 3D Replay
```bash
python visualize_revo2_hand.py \
    --urdf brainco_hand/brainco_right.urdf \
    --trajectory hand_trajectory.json \
    --speed 1.0 --loop
# Controls: Space = pause/resume, q = quit
```

### Real-time Video + 3D
```bash
# Single-hand mode
python realtime_visualize.py \
    --video human_hand_video.mp4 \
    --urdf brainco_hand/brainco_right.urdf \
    --hand right

# Both-hand mode
python realtime_visualize.py \
    --camera-index 0 \
    --hand both \
    --left-urdf brainco_hand/brainco_left.urdf \
    --right-urdf brainco_hand/brainco_right.urdf
```

In `--hand both` mode, the window shows the camera scene on the left, the left-hand BrainCo retargeting in the middle, and the right-hand BrainCo retargeting on the right.

### Trajectory Curve Plot
```bash
python visualize_trajectory_6dof.py \
    --input hand_trajectory_6dof.json \
    --combined
```

---

## 🎯 Complete Pipeline Example

```bash
# Step 1: Extract frames from video
mkdir frames
ffmpeg -i human_hand_v

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识