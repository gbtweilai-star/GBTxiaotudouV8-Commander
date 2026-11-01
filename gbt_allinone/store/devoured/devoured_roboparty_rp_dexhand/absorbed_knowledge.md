# Roboparty/rp_dexhand 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:51 | 来源: https://github.com/Roboparty/rp_dexhand
> Stars: 10 | 语言: Python | 许可: unknown

## 项目概览
- 描述: RP Hand dexterous hand: product documentation, hardware, companion software, CAD/URDF/MJCF and SDK guides.
- 主题: can-fd, dexterous-hand, humanoid-robot, robotics
- 分支: main | 最近推送: 2026-10-19

## README 摘要
<a id="top"></a>

<p align="center">
  <a href="https://github.com/Roboparty/RP1">RP1 Humanoid</a> &nbsp; / &nbsp; <strong>RP Hand</strong> &nbsp; / &nbsp; <a href="https://github.com/Roboparty/roboparty_dexhand">SDK</a>
</p>

<h1 align="center">RP Hand</h1>

<p align="center">
  A compact five-finger dexterous hand for humanoid robots.<br>
  Six active axes. CAN-FD connectivity. Product and development resources in one place.
</p>

<p align="center">
  <a href="README.md">English</a> &nbsp; | &nbsp; <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="assets/rp-hand.gif" alt="RP Hand quick-change installation on the RP1 humanoid robot" width="760">
</p>

<p align="center"><sub>RP Hand quick-change installation on RP1.</sub></p>

<p align="center">
  <a href="docs/en/quickstart.md"><strong>Get started</strong></a> &nbsp; · &nbsp;
  <a href="docs/en/downloads.md"><strong>Software &amp; models</strong></a> &nbsp; · &nbsp;
  <a href="https://github.com/Roboparty/roboparty_dexhand"><strong>SDK source</strong></a>
</p>

## Overview

RP Hand provides five-finger manipulation for small and medium humanoid robots. It has **11 mechanical degrees of freedom, including 6 actively controlled axes**, in a compact worm-gear mechanism. On RP1, the matching CAN-FD connection supports internal cable routing.

- **Robot integration** — dimensions, connector pinout and left/right CAD for mechanical and electrical integration.
- **Device setup** — a Windows configuration application for debugging and parameter setup.
- **Visual hand control** — gesture-recognition demo packages for Windows and Linux.
- **Application development** — a Linux CAN-FD SDK with C++, Python and bundled ROS 2 interfaces, plus URDF and MJCF models.

## Specifications

| Property | Value |
| --- | --- |
| Fingers | 5 |
| Mechanical DoF | 11: 6 active axes and 5 passive / coupled DoF |
| Dimensions | 147.54 × 73.53 × 26.35 mm |
| Mass | 379 ± 10 g |
| Transmission | Worm gear |
| RP1 communication | CAN-FD |

[Hardware guide: dimensions, power and pinout →](docs/en/hardware.md)

## Start with your task

| Set up the hand | Develop an application | Integrate the hardware |
| --- | --- | --- |
| Configure the device and try the gesture demo. | Build a C++, Python or ROS 2 application over CAN-FD. | Check the installation space and use the left/right robot models. |
| [Companion software](docs/en/software.md) · [Downloads](docs/en/downloads.md) | [Quick start](docs/en/quickstart.md) · [SDK repository](https://github.com/Roboparty/roboparty_dexhand) | [Hardware](docs/en/hardware.md) · [CAD / URDF / MJCF](docs/en/models.md) |

For a first robot integration, check the [wiring](docs/en/hardware.md), bring up one hand with the [quick start](docs/en/quickstart.md), then add [ROS 2](docs/en/ros2.md) if needed. The ROS 2 package is included in the SDK repository at `ros2/rphand_ros`.

## Documentation

| Guide | Contents |
| --- | --- |
| [Quick start](docs/en/quickstart.md) | Linux environment, SDK build, CAN-FD setup and first connection |
| [C++ / Python SDK](docs/en/sdk.md) | Control flow, axis order, units and state feedback |
| [ROS 2 integration](docs/en/ros2.md) | Jazzy setup, dual-hand launch, commands and recording |
| [Hardware](docs/en/hardware.md) | Dimensions, power, connectors and wiring |
| [Companion software](docs/en/software.md) | Configuration application and gesture-recognition demos |
| [Models](docs/en/models.md) | Left/right CAD, URDF, MJCF and joint mapping |
| [Downloads](docs/en/downloads.md) | Applications, models and protocol files |
| [Troubleshooting](docs/en/troubleshooting.md) | Build, communication and motion checks |

## Support and contributions

Use [rp_dexhand Issues](https://github.com/Roboparty/rp_dexhand/issues) for product documentation and resources, and [SDK Issues](https://github.com/Roboparty/roboparty_dexhand/issues) for C++, Python and ROS 2 code.

[Contributing](CONTRIBUTING.md) · [Licensing](LICENSES.md) · [Source attribution](NOTICE.md) · [Back to top](#top)


## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识