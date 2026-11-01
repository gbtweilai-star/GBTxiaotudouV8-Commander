# Janebek/AdaDexTrack 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:36 | 来源: https://github.com/Janebek/AdaDexTrack
> Stars: 5 | 语言: Python | 许可: BSD-3-Clause

## 项目概览
- 描述: [CVPR 2026] "AdaDexTrack: Dynamic Modulation for Adaptive and Generalizable Dexterous Manipulation Tracking"
- 主题: dexterous-hand, reinforcement-learning, robotics
- 分支: main | 最近推送: 2026-10-27

## README 摘要
<h1 align="center">AdaDexTrack: Dynamic Modulation for Adaptive and Generalizable Dexterous Manipulation Tracking</h1>

<h3 align="center">CVPR 2026</h3>

<p align="center">
  <a href="https://janebek.github.io/AdaDexTrack/">Project website</a> ·
  <a href="https://openaccess.thecvf.com/content/CVPR2026/papers/Adalibieke_AdaDexTrack_Dynamic_Modulation_for_Adaptive_and_Generalizable_Dexterous_Manipulation_Tracking_CVPR_2026_paper.pdf">Paper</a> ·
  <a href="https://www.youtube.com/watch?v=eziNDfpwego">Video</a> ·
  <a href="https://huggingface.co/datasets/Janebek/AdaDexTrack">Dataset</a>
</p>

<p align="center">
  <a href="https://www.sqz.ac.cn/en"><img src="static/institutions/shanghai-qi-zhi-institute.svg" height="40" alt="Shanghai Qi Zhi Institute"></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://www.tsinghua.edu.cn/en/"><img src="static/institutions/tsinghua-university.jpg" height="60" alt="Tsinghua University"></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://www.ucsd.edu/"><img src="static/institutions/uc-san-diego.png" height="44" alt="UC San Diego"></a>
</p>

<p align="center">
  <a href="https://janebek.github.io/AdaDexTrack/videos/teaserv2.mp4" title="Watch the original 1080p video"><img src="static/teaser.webp" width="560" alt="Full AdaDexTrack real-world dexterous manipulation demo"></a>
</p>

This repository provides the AdaDexTrack pipeline: reference replay, semantic specialist training, demonstration collection, generalist BC training, and modulator training and inference. It includes **2,765 reference motions, 50 objects and 444 semantic groups**, with pretrained specialists, BC trackers, modulators and an object autoencoder.

## Table of Contents

### [1. Preparation and data visualization](#preparation-and-data-visualization)

- [Step 1: Installation](#step-1-installation)
- [Step 2: Download resources and inspect the dataset](#step-2-download-resources-and-inspect-the-dataset)
- [Step 3: Replay reference motions](#step-3-replay-reference-motions)

### [2. Specialist training and inference](#specialist-training-and-inference)

- [Step 1: Train semantic specialists](#step-1-train-semantic-specialists)
- [Step 2: Run specialist inference and evaluation](#step-2-run-specialist-inference-and-evaluation)

### [3. Generalist training and inference](#generalist-training-and-inference)

- [Step 1: Collect specialist demonstrations](#step-1-collect-specialist-demonstrations)
- [Step 2: Train the generalist BC tracker](#step-2-train-the-generalist-bc-tracker)
- [Step 3: Run BC inference and evaluation](#step-3-run-bc-inference-and-evaluation)

### [4. Modulator training and inference](#modulator-training-and-inference)

- [Step 1: Train the modulator](#step-1-train-the-modulator)
- [Step 2: Run modulator inference and evaluation](#step-2-run-modulator-inference-and-evaluation)

### [5. Sim2real deployment](#sim2real-deployment)

- [Step 1: Set up hardware and APIs](#step-1-set-up-hardware-and-apis)
- [Step 2: Calibrate coordinate frames and estimate object poses](#step-2-calibrate-coordinate-frames-and-estimate-object-poses)
- [Step 3: Assemble observations and run policy inference](#step-3-assemble-observations-and-run-policy-inference)
- [Step 4: Connect policy outputs to robot control](#step-4-connect-policy-outputs-to-robot-control)

[License and credits](#license-and-credits) · [Citation](#citation)

<a name="preparation-and-data-visualization"></a>

# 1. Preparation and data visualization

### Step 1: Installation

**For Ubuntu 20.04, follow the [complete installation guide](docs/install_ubuntu20.md).** It covers Ubuntu packages, NVIDIA drivers, Conda, the SDK download, environment setup, resource installation, first runs and troubleshooting.

This release targets **Ubuntu 20.04.6 with NVIDIA driver 535.161.07**. The project uses **Python 3.8.18, PyTorch 2.4.1 with CUDA 12.1, NumPy 1.23.5 and standalone Isaac Gym Preview 4**.

If Conda and a suitable NVIDIA driver are already installed:

```bash
git clone https://github.com/Janebek/AdaDexTrack.git
cd AdaDexTrack
conda env create -f environment.yml
conda activate adadextrack
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
export MAX_JOBS=2
```

Download the Isaac Gym Preview 4 release from the [NVIDIA website](https://developer.nvidia.com/isaac-gym).

```bash
cd isaacgym/python
pip install -e .
```

Continue from the cloned `AdaDexTrack/` repository root in the activated environment.

### Step 2: Download resources and inspect the dataset

Runtime resources are available from [Hugging Face](https://huggingface.co/datasets/Janebek/AdaDexTrack): `assets.tar.gz` includes object meshes, robot models, textures and latents; `references.tar.gz` contains the full corpus; `bc_tracker_unseen_ref.pth` is the unseen-reference (unseen-trajectory) tracker and `bc_tracker_unseen_obj.pth` is the unseen-object tracker. The two pretrained modulators are `modulator_unseen_ref.pth` and `modulator_unseen_obj.pth`, paired with their corresponding BC trackers. Publication status and the pinned Hub revision are recorded in `configs/artifact_release.json`.

After completing the environment and SDK setup, run from the repository root:

```bash
python scripts/download_resources.py
# Only object/robot assets, textures and latents:
python scripts/download_resources.py --components assets
```

The public resources need no Hugging Face login. The downloader automatically verifies archive and per-file SHA256 checksums, restores the runtime directories and rejects conflicting local files. Use `--revision <full Hub commit hash>` to pin a version. Third-party resources retain their source terms; the code license does not replace them. See [resource distribution](docs/resource_distribution.md) and [resource terms](docs/resource_licenses.md).

#### Dataset

We use [DiffH2O](https://github.com/facebookresearch/diffh2o) to generate
hand–object interaction motions from textual descriptions, then retarget them
to the xArm6–LEAP Hand robot to obta

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识