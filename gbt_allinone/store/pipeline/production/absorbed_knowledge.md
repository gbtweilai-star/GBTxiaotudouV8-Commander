# 杂交: devoured_12-twelve-12_robolings x devoured_bobyue0118_brainco-revo2-dex-retargeting

# 12-Twelve-12/robolings 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:39 | 来源: https://github.com/12-Twelve-12/robolings
> Stars: 13 | 语言: Python | 许可: MIT

## 项目概览
- 描述: Small exercises for robot learning, rustlings style: kinematics, dexterous hands, control, diffusion policy, flow matching. NumPy only.
- 主题: dexterous-hand, diffusion-policy, embodied-ai, exercises, flow-matching, imitation-learning, kalman-filter, kinematics, learning-by-doing, lerobot
- 分支: main | 最近推送: 2026-10-08

## README 摘要
# robolings

Exercises for robot learning, in the style of [rustlings](https://github.com/rust-lang/rustlings).

55 small functions to implement, from Rodrigues' formula to the sampler of a flow-matching policy, with the perception and state estimation that feed it. NumPy only, no GPU, no simulator. The tests run in under a second.

[中文说明](README.zh-CN.md) (the problem statements are available in Chinese too)

![A watch session: a wrong slerp fails three tests, the hint names the fix, the corrected one passes](docs/demo.svg)

## Usage

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/12-Twelve-12/robolings?quickstart=1)

To try it without installing anything, open a Codespace on this repo: it comes with Python, NumPy and the editor set up, and `python robolings.py` runs in the terminal that appears. To keep your answers, fork the repo and clone your fork, then:

```bash
pip install -r requirements.txt
python robolings.py           # progress, and what to do next
python robolings.py watch     # rerun an exercise every time you save it
python robolings.py run slerp # test a single exercise
python robolings.py show slerp # print the problem statement
python robolings.py hint slerp # a nudge if you are stuck
python robolings.py list
```

The stubs are in `exercises/`, one file per exercise. Replace the `raise NotImplementedError` and run the exercise again. Python 3.10+.

```text
robolings  [###...........................]  6/55

  01_rotations
   [x]  1  rodrigues              Rodrigues' rotation formula
   [x]  2  quat_mul               Quaternion product
   ...
  02_kinematics
   [x]  7  transform_inverse      Inverse of a homogeneous transform
   [ ]  8  forward_kinematics     Forward kinematics of a serial chain

Next: forward_kinematics
  edit   exercises/02_kinematics/forward_kinematics.py
  check  python robolings.py run forward_kinematics
  read   python robolings.py show forward_kinematics
  stuck  python robolings.py hint forward_kinematics
```

`watch` is the comfortable way to work: leave it running in one terminal, edit in another, and every save reruns the exercise you just touched.

Stuck? `hint` gives you a nudge, and the answers are in `solutions/`. `python robolings.py reset slerp` throws your attempt away and starts that exercise over.

### Progress on GitHub

![progress](../../raw/progress/progress.svg)

Each push to your fork runs the tests, puts a progress table in the summary of the workflow run, and updates this badge. The badge belongs to the repository you are looking at: here it shows how many exercises there are, in your fork it shows your own count.

Forks have Actions disabled by default, so enable them once in the Actions tab. The badge appears after the first run.

### Getting new exercises

Use **Sync fork** on GitHub, or merge `upstream/main`. New exercises arrive as new files, so your own answers are not touched.

## Exercises

| Track | Exercises | Content |
|---|---|---|
| Rotations | 7 | Rodrigues, quaternion product, quaternion ↔ matrix, slerp, Kabsch, log and exp |
| Kinematics | 7 | transform inverse, FK, analytic two-link IK, geometric Jacobian, damped least squares, null-space projection, manipulability |
| Dexterous hands | 6 | mimic joints, coupled Jacobian, retargeting cost, fingertip IK with joint limits, friction cone, force closure |
| Control | 9 | min-jerk, trapezoidal profile, low-pass filter, MIT-mode impedance control, rate limiter, angle wrapping, PID with anti-windup, gravity compensation, admittance control |
| Imitation learning | 7 | normalisation, action chunking, DCT tokenisation, relative actions, temporal ensembling, obs history, weight EMA |
| Diffusion policy | 5 | cosine schedule, forward process, DDPM step, DDIM step, classifier-free guidance |
| Flow matching | 3 | training target, Euler sampler, midpoint sampler |
| Perception | 6 | pinhole projection, depth back-projection, lens distortion and its inverse, voxel downsampling, plane fit, one ICP step |
| State estimation | 5 | complementary filter, gyro attitude integration, EKF prediction, EKF update in Joseph form, innovation gating |

### Where the exercises come from

Each track is the piece of a paper or a textbook that you would otherwise read past. If you are working through one of these, the matching exercises are the ones to do first.

| Track | Reads well with |
|---|---|
| Rotations, kinematics | Lynch and Park, [Modern Robotics](https://modernrobotics.org) (free), chapters 3, 4, 5 and 6 |
| Dexterous hands | Murray, Li and Sastry, [A Mathematical Introduction to Robotic Manipulation](https://www.cds.caltech.edu/~murray/mlswiki/) (free), chapter 5 on grasping |
| Imitation learning | [ACT](https://arxiv.org/abs/2304.13705) for action chunking and temporal ensembling, [FAST](https://arxiv.org/abs/2501.09747) for DCT action tokens |
| Diffusion policy | [Diffusion Policy](https://arxiv.org/abs/2303.04137), with [DDPM](https://arxiv.org/abs/2006.11239), [DDIM](https://arxiv.org/abs/2010.02502), the [cosine schedule](https://arxiv.org/abs/2102.09672) and [classifier-free guidance](https://arxiv.org/abs/2207.12598) it is built from |
| Flow matching | [Flow Matching for Generative Modeling](https://arxiv.org/abs/2210.02747), and [π0](https://arxiv.org/abs/2410.24164), whose action head is the sampler in track 07 |
| Perception, state estimation | Any computer vision or estimation textbook covers these. The exercises pin the conventions (OpenCV camera axes, Joseph form) that the textbooks leave to the reader |

## Roadmap

The tracks are not meant to stay the size they are now. The gaps, roughly in the order they matter:

- **Flow matching** (3) is the thinnest track, and the hardest to grow without repeating the diffusion one.
- **Control** (9) treats every joint on its own. Nothing couples joints through a model, and nothing plans around a joint limit.
- **Imitation learning** (7) stops at the data pipeline. Nothing in i

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识
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

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
