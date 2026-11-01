# yuzhench/inspire-hand-rh56-py 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:50 | 来源: https://github.com/yuzhench/inspire-hand-rh56-py
> Stars: 5 | 语言: Python | 许可: MIT

## 项目概览
- 描述: Pure-Python driver for the Inspire RH56DFTP dexterous hand — Modbus TCP, no ROS, with a browser debug UI.                                               
- 主题: dexterous-hand, dexterous-manipulation, dexterous-robotic-hand, hand-driver, inspire-robotics, modbus-tcp, python, rh56, rh56dftp, robot-control
- 分支: main | 最近推送: 2026-05-04

## README 摘要
# inspire_rh56dftp

Pure-Python Modbus TCP driver for the [Inspire Robots RH56DFTP dexterous hand](https://en.inspire-robots.com/product/rh56dfx).

The official software stack ships only as a ROS package, which is heavy if all
you want is to send 6 register values to a hand on the LAN. This package is
just the wire protocol — three files, stdlib-only — plus a browser debug UI
behind an optional dependency.

> **Manual:** All register addresses, frame layouts and tactile map come from
> the official Inspire Robots
> [RH56DFTP user manual PRJ-02-TS-U-010 V1.0.0 (Dec 2024)](https://en.inspire-robots.com/wp-content/uploads/2025/01/INSPIRE-ROBOTS-The-Dexterous-Hand-RH56DFTP-User-Manual-V1.0.0.pdf).
> Section numbers (`§2.6.20` etc.) in this codebase reference that document.

## Install

From PyPI (released versions):

```bash
pip install inspire_rh56dftp                # core driver only (no deps)
pip install inspire_rh56dftp[viz]           # + browser debug UI
```

From GitHub (latest `main`):

```bash
pip install git+https://github.com/yuzhench/inspire_rh56dftp.git
pip install "inspire_rh56dftp[viz] @ git+https://github.com/yuzhench/inspire_rh56dftp.git"
```

From source (for development — clone, then editable install):

```bash
git clone https://github.com/yuzhench/inspire_rh56dftp.git
cd inspire_rh56dftp
pip install -e ".[viz]"
```

## Quick start

```python
from inspire_rh56dftp import InspireHand

hand = InspireHand(ip="192.168.123.211")
hand.send_raw([0, 0, 0, 0, 0, 1000])       # close fist (thumb across palm)
hand.send_raw([1000, 1000, 1000, 1000, 1000, 0])   # open hand
hand.close()
```

Values are in DOF order: `[pinky, ring, middle, index, thumb_bend, thumb_rotation]`,
each `0..1000` (raw register units, 1000 = fully extended for the 4 fingers
and `thumb_bend`; for `thumb_rotation`, 0 = retracted, 1000 = across palm).

## Hardware setup

The RH56DFTP ships with factory-default IP `192.168.123.211` and exposes
Modbus TCP on port `6000`. It does **not** run a DHCP server, so the host
needs a static IP in the same subnet:

```bash
sudo ip addr add 192.168.123.50/24 dev <eth>     # one-shot
# or persist via NetworkManager:
sudo nmcli con add type ethernet ifname <eth> con-name inspire-hand \
    ipv4.addresses 192.168.123.50/24 ipv4.method manual ipv6.method disabled
```

Verify:

```bash
ping -c 3 192.168.123.211
```

## Two layers of API

```
InspireHand (client.py)         InspireHandSender (scheduler.py)
──────────────────────          ──────────────────────────────────
synchronous:                    background-thread wrapper around an
every call blocks until         InspireHand. Runs writes (control)
the hand acks                   and reads (tactile) on independent
                                clocks sharing one TCP socket.
use for: scripts,               use for: real-time control loops
one-shot moves,                 that also need continuous tactile
sequenced demos                 data
```

Both share the same lock on the underlying socket, so reads and writes never
race on the wire even when issued from multiple threads.

### Reading registers directly

The high-level API exposes `send_raw()` (writes ANGLE_SET) and the scheduler's
`latest_tactile`. For everything else (joint feedback, force, custom ranges):

```python
from inspire_rh56dftp import InspireHand, registers

hand = InspireHand(ip="192.168.123.211")
actual_angles = hand.read_holding(registers.ANGLE_ACT, 6)   # 6 ints
forces        = hand.read_holding(registers.FORCE_ACT, 6)
```

`registers.py` is a pure transcription of manual §2.6 — see the file or
import it for the full address map.

## Browser debug UI

```bash
pip install inspire_rh56dftp[viz]
python -m inspire_rh56dftp.viz 192.168.123.211      # IP defaults to factory
# open http://127.0.0.1:8765
```

The page has 6 horizontal sliders (one per DOF) and the live tactile heatmap
laid out anatomically over a right-hand silhouette. Drag a slider to set the
target; the orange "ack" number shows what the hand reports back. Useful for
verifying wiring, finding mechanical stops, and watching tactile cells light
up while you poke them.

The UI talks to the server over a single bidirectional WebSocket and works
with the hand absent — sliders just won't move anything until you click
**Reconnect**.

## Modbus protocol quirks (read this before writing your own client)

These cost real time to discover; documenting them here so the next person
doesn't repeat the work.

### 1. The hand mishandles transaction IDs

The RH56DFTP firmware has an off-by-one bug in the Modbus TX-ID echo back.
Strict clients (`pymodbus`, etc.) reject the bad IDs as "unexpected response"
and eventually close the connection. This package uses a raw socket and
deliberately does **not** validate the TX-ID — it just consumes the response
bytes and moves on.

### 2. Every write must be followed by a synchronous ACK read

The hand always sends a 12-byte ACK after a write. If you don't read it:

1. Bytes pile up in the hand's TCP send buffer.
2. Kernel flow control kicks in and blocks the hand's `send()`.
3. The hand's main loop blocks on that send.
4. **The hand stops responding to new commands**, even though your own
   `sendall()` keeps reporting success.

Symptom: control feels great for the first few seconds, then the hand
freezes — and your client has no idea anything is wrong because writes
look fine. Always drain the ACK. We don't need to validate it (see #1);
draining it is what matters.

### 3. Tactile data is big-endian, despite what the manual says

Manual §2.6.20 claims tactile cells are little-endian ("low byte first").
**Empirical test on real hardware shows it's big-endian.** Little-endian
interpretation gives values up to 23000+; big-endian gives the documented
0..4095 range. Likely a doc issue copied from the basic RH56 RS485 protocol
(where the data IS little-endian) — the Modbus TCP gateway converts to BE
on the wire but the docs weren't updated.

### 4. The hand needs a brief grac

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识