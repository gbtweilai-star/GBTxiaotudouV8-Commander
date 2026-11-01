# alexandertianlin/hand-tracking-fusion-system 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:45 | 来源: https://github.com/alexandertianlin/hand-tracking-fusion-system
> Stars: 1 | 语言: C | 许可: MIT

## 项目概览
- 描述: Multi-modal hand tracking fusion system: HaMeR + ViTPose + IMU glove + depth camera, with per-finger confidence-gated switching and Slerp complementary filter. Consolidated from 6 repos with full fusion algorithm docs, evaluation report, MIT License, and CITATION.cff.
- 主题: dexterous-hand, hamer, hand-tracking, imu, multi-modal-fusion, realsense, tactile-sensing, vitpose
- 分支: main | 最近推送: 2026-09-17

## README 摘要
# Hand Tracking Fusion System

**Real-time, drift-free, occlusion-robust 3D hand pose estimation** — fusing camera-based vision (HaMeR / ViTPose) with a custom IMU + tactile glove (6x MPU6050 @ 100 Hz), streamed to Unity over UDP.

---

## Why this exists

Hand tracking has two imperfect options, and neither works alone in the real world:

| | Strength | Failure mode |
|---|---|---|
| **Camera vision** (HaMeR / ViTPose) | Absolute pose, no drift | Slow (~7 FPS), dies on occlusion and fast motion |
| **IMU glove** | 100 Hz, never occluded | Drifts within seconds, no global reference |

For teleoperation and dexterous-manipulation data collection, both failure modes are unacceptable: drift corrupts trajectories, and a 135 ms dropout loses contact events.

**This system fuses them per finger.** At every frame, each finger independently picks its best source — vision when it is confident, IMU when it is not — and blends with a Slerp complementary filter instead of hard switching.

---

## Measured results

| Metric | Value | Notes |
|---|---|---|
| End-to-end pipeline latency | **~135 ms** | → 7.4 FPS effective vision rate |
| IMU streaming rate | **100 Hz** | 6x MPU6050, UART or WiFi |
| Vision rate | ~7.4 FPS | ViTPose every 6 frames + HaMeR per frame |
| Fusion | **Slerp complementary** | `Q_fused = Slerp(Q_imu, Q_vis, alpha)` |
| Dynamic alpha | **0.85 → 1.0** | 0.85 when vision is reliable, →1.0 when occluded |
| Per-finger confidence gate | **0.3** | below → IMU fallback, above → vision anchor |
| Auto-calibration | **open-palm** | 15-frame offset, refreshed every 3 s |
| Transport | UDP JSON | ports 8080 + 5055 → Unity |
| Validated on | RTX 4060 Laptop 8 GB / RTX 4080 Laptop 12 GB | Windows 11, CUDA 12.x |

> Accuracy evaluation (MPJPE / PA-MPJPE) is **not finished yet** — see [`results/README.md`](results/README.md) for the plan. The numbers above are latency and throughput, measured; they are not accuracy claims.

---

## Architecture

```
   Intel RealSense (640x480 @15 FPS)
            |
            v
      ViTPose (hand detection)  -->  HaMeR (MANO 3D mesh)
            |                              |
            |                              | global_orient quaternion
            |                              | 21 keypoints + per-finger confidence
            |                              v
   IMU + tactile glove                 FusionEngine
   (STM32H523 / H70B)          +-------------------------------------------+
     6x MPU6050 @100Hz  -----> |  Slerp complementary filter                |
     UART or WiFi              |    alpha = 0.85 (vision reliable)          |
     quaternion + force        |    alpha -> 1.0 (vision occluded)          |
                               |                                           |
                               |  Per-finger confidence gating             |
                               |    c >= 0.3 -> vision anchor              |
                               |    c <  0.3 -> IMU fallback               |
                               |                                           |
                               |  Orientation gating                       |
                               |    palm -> full correction                |
                               |    back -> open/fist only                 |
                               |    side -> no intervention                |
                               |                                           |
                               |  Occlusion -> IMU propagation             |
                               |  Recovery  -> exponential alpha decay     |
                               +-------------------------------------------+
                                              |
                                              v
                                    UDP JSON (8080 + 5055)
                                              |
                                              v
                                 Unity FusionHandController
                                 per-finger 3D visualization
```

Full mathematical formulation: [`docs/fusion_algorithm.md`](docs/fusion_algorithm.md).

---

## Hardware and software

| Component | Specification |
|---|---|
| GPU | NVIDIA 8 GB+ VRAM (validated: RTX 4060 Laptop 8 GB, RTX 4080 Laptop 12 GB) |
| Camera | Intel RealSense depth camera (640x480 @15 FPS) |
| Glove | Custom STM32H523 (UART) / STM32H70B (WiFi) + 6x MPU6050 IMU + tactile/force sensors |
| Software | Windows 10/11, CUDA 12.x, Python 3.10, Unity 2022.x |

---

## Quick start

```bash
conda create -n hamer python=3.10 -y
conda activate hamer
pip install -r python/requirements.txt

# Model weights (see docs/PROJECT_REPRODUCTION.md)
#   HaMeR checkpoint (~300 MB):  https://huggingface.co/geopavlakos/hamer
#   ViTPose+ wholebody (~2.3 GB): https://github.com/ViTAE-Transformer/ViTPose/releases
#   MANO model: included in the HaMeR package
```

Connect the camera (USB) and the glove (COM port), then:

```bash
python python/fusion_pipeline.py      # full fusion (recommended)
python python/run_vitpose_v3.py       # vision-only (HaMeR + ViTPose)
python python/run_hamer_camera.py     # standalone HaMeR inference
python python/measure_latency.py      # reproduce the latency numbers
```

Then open the Unity scene and press Play — Unity receives fused data over UDP (8080 + 5055).

---

## Fusion method

**Per-finger confidence gating** — each finger independently selects its source, so a partially occluded hand still tracks correctly. No global single-modality lock.

**Slerp complementary filter** — smooth blend `Q_fused = Slerp(Q_imu, Q_visual, alpha)` where alpha moves from 0.85 (vision reliable, confidence >= 0.7) to 1.0 (pure IMU, occluded), with linear interpolation in between. Coordinate frames are aligned by a calibration offset quaternion.

Both include **orientation gating** (palm / back / side), **open-palm auto-drift refresh**, a **vision-hold watchdog** (5-frame hold), and *

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识