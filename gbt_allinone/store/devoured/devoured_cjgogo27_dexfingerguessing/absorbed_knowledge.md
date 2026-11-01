# cjgogo27/DexFingerGuessing 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:47 | 来源: https://github.com/cjgogo27/DexFingerGuessing
> Stars: 1 | 语言: Python | 许可: MIT

## 项目概览
- 描述: DexFinger Guessing: a PaXini DexH13 dexterous hand plays rock-paper-scissors with you and mirrors your fingers. Python + Modbus, no vendor SDK.
- 主题: dexh13, dexterous-hand, hand-tracking, mediapipe, modbus, paxini, python, robotics, rock-paper-scissors
- 分支: main | 最近推送: 2026-10-31

## README 摘要
# DexFingerGuessing

**灵巧手的「猜拳」与「模仿」。** 抛个手势，让它接住。

<p align="center">
  <a href="http://10.16.10.28:8000">
    <img alt="打开网页控制台" src="https://img.shields.io/badge/%E2%96%B6%20%E6%89%93%E5%BC%80%E7%BD%91%E9%A1%B5%E6%8E%A7%E5%88%B6%E5%8F%B0-10.16.10.28%3A8000-1f6feb?style=for-the-badge">
  </a>
</p>

> **▶ 打开网页控制台** 指向实验室内网 `http://10.16.10.28:8000`，外网打不开。
> 自己部署时改成 `http://<你的IP>:8000` 即可。

帕西尼 **DexH13** 灵巧手的 Python 驱动层 + 两个互动玩法 + 网页控制台。
不依赖官方 SDK（官方仅 Linux 且要求固件 2.0+），**本机固件 1.4.4 可直接跑**。

<p align="center"><img src="docs/img/hand-tracking.jpg" width="620" alt="实时手部关键点"></p>

## 硬件

| 部件 | 规格 |
|---|---|
| 灵巧手 | PaXini DexH13 右手，固件 `V1.4.4_D`，从站 `0x79` |
| 供电 | 24–48 V DC，3 A Max |
| 通信 | RS485 / Modbus RTU，**460800** 8N1 |
| USB-485 | Prolific **PL2303GR**（CH340 不行，上限 3 Mbps） |
| 摄像头 | 任意 UVC，720p 即可 |

接线：`绿→A  白→B  黑→GND  屏蔽→悬空`。
接线图、供电安全、排障见 [docs/HARDWARE.md](docs/HARDWARE.md)。

## 快速开始

```bash
pip install -r requirements.txt
bash scripts/fetch_model.sh      # 下载 7.8 MB 手部关键点模型
python3 scripts/check_env.py     # 自检：依赖 / 模型 / 串口 / 摄像头
python3 web/app.py               # 打开 http://<本机IP>:8000
```

`check_env.py` 会逐项打勾，缺什么一目了然。没有硬件也能玩摄像头部分。

## 玩法

**网页控制台**（推荐）：实时画面 + 骨架，手摆好再点开始。

| 模式 | 说明 |
|---|---|
| 预览 | 只看不动 |
| 跟随模仿 | 你的手指怎么弯，手就怎么弯 |
| 猜拳 | 识别石头/剪刀/布，手跟你对局 |

页面里还带一个**手势挑战**小游戏：30 秒内按提示比出手势，纯前端，不需要灵巧手。

控制面板另有 **复位到零位**：停掉当前玩法、13 个关节回零、并保持使能，
随时可以一键把手收回初始姿态。

**命令行**：

```bash
python3 games/rps.py --rounds 5        # 猜拳
python3 games/mimic.py --seconds 30    # 跟随模仿
python3 lessons/l1_probe.py            # 从这开始：先把手的身份扫出来
```

六节课 `lessons/l1..l6` 从扫描、读数、使能一路到采数据，建议按顺序读一遍。

## 目录

```
dexh13/     驱动（crc / protocol / transport / hand / gestures）
games/      rps.py 猜拳 · mimic.py 跟随模仿
web/        app.py + templates/index.html（Flask + MJPEG）
lessons/    l1_probe → l6_record
docs/       PROTOCOL.md（协议逆向）· HARDWARE.md（接线/供电/排障）
scripts/    fetch_model.sh · check_env.py
```

## 协议要点

标准 Modbus RTU（FC03 / FC16，CRC 低字节在前），寄存器表与实测帧样例见
[docs/PROTOCOL.md](docs/PROTOCOL.md)。三个容易踩的坑：

1. 位置和电流是 **int16 有符号**，按无符号读会把 `-17` 读成 `65519`
2. `0x2010` / `0x2020` 是只写寄存器，读回来恒为 `0xFFFF`
3. 使能必须五步时序，少一步关节不动

## 已知限制

- **触觉读不到**：460800 仅约 46 KB/s，全量触觉需 547 KB/s，要升固件到 2.0+ 或走 EtherCAT
- **只有 4 指**：拇指 + 食/中/无名，模仿时小指不参与
- **没有力控**：力控在官方 SDK 里（需固件 2.0+）
- **单目**：无深度、无标定，换机位需重新标定

## 免责声明

非官方项目。协议由逆向 `pxdex-h13` 上位机得到，仅用于互操作与研究；
相关商标与著作权归帕西尼（PaXini）所有。

## License

MIT（仅本项目代码）。依赖：MediaPipe / OpenCV（Apache-2.0）、pyserial（BSD）、Flask（BSD）。

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识