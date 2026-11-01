# Juxi-Technology/AmazingHand 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:57 | 来源: https://github.com/Juxi-Technology/AmazingHand
> Stars: 0 | 语言: JavaScript | 许可: unknown

## 项目概览
- 描述: Control software and CAD models for the AmazingHand 8-DOF bionic dexterous hand
- 主题: 3d-printing, amazinghand, arduino, dexterous-hand, feetech, juxi-technology, juxitechnology, open-source-hardware, pollen-robotics, python
- 分支: main | 最近推送: 2026-10-22

## README 摘要
English | [简体中文](README_CN.md)

# AmazingHand

![AmazingHand](AmazingHand-main/assets/AmazingHand_Couv.jpg)

AmazingHand is an open-source, 3D-printable humanoid robotic hand with **8 degrees of freedom across 4 fingers**. Every actuator sits inside the hand — no cables running to the forearm — for roughly 400 g and under €200 in parts.

This repository gathers the original mechanical design and firmware from the [Pollen Robotics](https://github.com/pollen-robotics/AmazingHand) project together with the control software, browser controller and servo tooling developed by Juxi Technology.

## 📦 Contents

| Folder | Description | README |
|--------|-------------|--------|
| **`AmazingHand-main/`** | Original design: STL/STEP CAD files, Arduino & Python examples, demos (control, simulation, hand tracking), assembly and 3D-printing guides, BOM | [English](AmazingHand-main/README.md) · [中文](AmazingHand-main/README_CN.md) |
| **`AmazingHandControl/`** | Python control tools: Tkinter GUI and CLI for calibration, pose presets, sequences and live servo control | [English](AmazingHandControl/README.md) · [中文](AmazingHandControl/README_CN.md) |
| **`SCS0009_ServoController/`** | SCS0009 servo debug tool: PySide6 GUI to scan the bus, read and write all 44 registers, change baud rate, factory reset, and back up parameters as `.xdat` | [English](SCS0009_ServoController/README.md) · [中文](SCS0009_ServoController/README_CN.md) |
| **`Amazinghand-web/`** | Browser control: 8 servo sliders, 19 preset poses, and camera teleop with MediaPipe running entirely in the page — left or right hand, bilingual UI, tutorials in 11 languages | [English](Amazinghand-web/README.md) · [中文](Amazinghand-web/tutorials/zh-hans/README.md) |

## 🚀 Getting started

| What you want to do | Where to go |
|---------------------|-------------|
| Control the hand from a browser — sliders, preset poses, camera teleop | [`Amazinghand-web/`](Amazinghand-web/README.md) — `pip install -r requirements.txt`, then `python server.py --no-connect` and open <http://localhost:8000> |
| Run the desktop demos — simulation, hand tracking, servo control | [`AmazingHand-main/Demo/`](AmazingHand-main/Demo/README.md) — one-click deployment scripts for [Windows](AmazingHand-main/Demo/Windows_Deploy_Scripts/), [Linux](AmazingHand-main/Demo/Linux_Deploy_Scripts/) and [macOS](AmazingHand-main/Demo/Mac_Deploy_Scripts/) |
| Calibrate servos or script poses offline | [`AmazingHandControl/`](AmazingHandControl/README.md) · [`SCS0009_ServoController/`](SCS0009_ServoController/README.md) |

Hardware needed: the assembled hand, an external 5 V / 2 A supply, and a USB serial bus adapter (see [Hardware](#-hardware) below).

## 🔧 Hardware

- 8 × Feetech **SCS0009** servos (potentiometer feedback, 10-bit resolution, 0–1023)
- External 5 V / 2 A power supply
- Serial bus adapter, or an Arduino with a Feetech TTL Linker
- 3D-printed parts — see the [BOM](AmazingHand-main/README.md#bom-bill-of-materials)

Each finger is driven by a parallel mechanism: two SCS0009 servos move it in flexion/extension and abduction/adduction.

## 📖 Documentation

- [Assembly guide](AmazingHand-main/docs/AmazingHand_Assembly.pdf)
- [3D printing tips](AmazingHand-main/docs/AmazingHand_3DprintingTips.pdf)
- [AmazingHand overview](AmazingHand-main/docs/AmazingHand_Overview.pdf)
- [Chinese BOM](https://docs.google.com/spreadsheets/d/1fHZiTky79vyZwICj5UGP2c_RiuLLm89K8HrB3vpb2h4/edit?gid=837395814#gid=837395814)

## 📄 License & attribution

- Software: [Apache License 2.0](AmazingHand-main/LICENSE)
- Mechanical design: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- `SCS0009_ServoController/`: [MIT](SCS0009_ServoController/LICENSE)
- Third-party components bundled with `Amazinghand-web/` (MediaPipe, …): see [its NOTICE](Amazinghand-web/NOTICE.md)

Based on [AmazingHand](https://github.com/pollen-robotics/AmazingHand) by Pollen Robotics.


## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识