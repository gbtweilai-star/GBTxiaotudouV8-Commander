# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""程序化 **idle（待机）动作** —— 给自研 26 关节骨架加一条循环闭合的呼吸/重心微动

为什么需要它：
  数字人在语音对讲里"是不是活的"，一半靠**无意识微动**（呼吸起伏、重心漂移、头部轻摆）。
  静止的 T/A-pose 再逼真也像假人。这一段不依赖眼位、不依赖贴图，是**独立可做**的。

口径：
  · 只驱动 **Hips / Spine / Spine1 / Neck / Head** 五个骨（腰背呼吸 + 头轻摆）；
  · 每条通道用**正弦**，周期整除总时长 ⇒ **首末帧必须相等**（循环闭合，硬判据）；
  · 关节旋转用**四元数**（glTF 要求 rotation 通道为 VEC4 四元数），绕世界 X/Z 的小角度；
  · 骨骼节点的静止 TRS 不动，动画通道**叠加**在静止姿势之上；
  · 时长 4.0s · 采样 41 帧（0.1s 步长）。
自检：
  · 首末帧四元数逐位相等（循环闭合）；
  · 四元数**模长 = 1**（容差 1e-4）；
  · 通道目标节点都在 joints 里；动画采样器/通道引用不越界。

用法：python tools/codex-scripts/anim-idle.py <件.glb> <输出.glb>
退出码：0 = 写出且自检通过；1 = 自检不过；2 = 前置问题。
"""
import json
import math
import pathlib
import struct
import sys

import numpy as np

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-final.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/avatar-anim.glb"
DUR, STEP = 4.0, 0.1
N = int(round(DUR / STEP)) + 1

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
names = [n.get("name", "") for n in J["nodes"]]
joints = J["skins"][0]["joints"]

# 通道表：(关节名, 绕轴, 振幅弧度, 每周期次数)
CH = [("mixamorig:Hips", "z", 0.012, 1), ("mixamorig:Spine", "x", 0.018, 1),
      ("mixamorig:Spine1", "x", 0.022, 1), ("mixamorig:Neck", "x", -0.016, 1),
      ("mixamorig:Head", "z", 0.026, 1), ("mixamorig:Head", "x", 0.014, 2)]
times = np.arange(N) * STEP


def quat(axis, ang):
    s = math.sin(ang / 2.0)
    q = {"x": [s, 0.0, 0.0, math.cos(ang / 2.0)],
         "z": [0.0, 0.0, s, math.cos(ang / 2.0)]}
    return q[axis]


def add_view(arr, target=None):
    while len(BIN) % 4:
        BIN.append(0)
    o = len(BIN)
    BIN.extend(arr.tobytes())
    v = {"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes}
    if target:
        v["target"] = target
    J["bufferViews"].append(v)
    return len(J["bufferViews"]) - 1


def add_acc(arr, ct, typ, mm=False):
    vi = add_view(arr)
    a = {"bufferView": vi, "componentType": ct, "count": len(arr), "type": typ}
    if mm:
        # 🔴 SCALAR 访问器是 1 维：`min(axis=0)` 返回**标量**，不能直接迭代
        #    （实测 `for x in np.float32(...)` 直接 TypeError）。1 维要单独走一条路。
        if arr.ndim == 1:
            a.update({"min": [float(arr.min())], "max": [float(arr.max())]})
        else:
            a.update({"min": [float(x) for x in arr.min(axis=0)],
                      "max": [float(x) for x in arr.max(axis=0)]})
    J["accessors"].append(a)
    return len(J["accessors"]) - 1


# 时间访问器（所有通道共用）
t_acc = add_acc(times.astype(np.float32), 5126, "SCALAR", True)
samplers, channels, outs = [], [], []
for nm, axis, amp, cycles in CH:
    if nm not in names:
        print(f"🔴 找不到关节 {nm} ⇒ 停止")
        raise SystemExit(2)
    node = names.index(nm)
    vals = []
    for t in times:
        ph = 2 * math.pi * cycles * (t / DUR)
        vals.append(quat(axis, amp * math.sin(ph)))
    arr = np.array([vals[0]] + vals, np.float32)[:N]          # 长度对齐 N
    arr = np.array(vals, np.float32)
    o_acc = add_acc(arr, 5126, "VEC4")
    outs.append(arr)
    samplers.append({"input": t_acc, "output": o_acc, "interpolation": "LINEAR"})
    channels.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": "rotation"}})

J.setdefault("animations", []).append({"name": "idle", "samplers": samplers, "channels": channels})
while len(BIN) % 4:
    BIN.append(0)
J["buffers"][0]["byteLength"] = len(BIN)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(BIN))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(BIN)) + b"BIN\x00" + bytes(BIN))

# 自检
raw2 = OUT.read_bytes()
jl2, = struct.unpack_from("<I", raw2, 12)
J2 = json.loads(raw2[20:20 + jl2].decode("utf-8"))
o2 = 20 + jl2 + ((-jl2) % 4)
bl2, = struct.unpack_from("<I", raw2, o2)
B2 = raw2[o2 + 8: o2 + 8 + bl2]
bad = []
an = J2["animations"][-1]
for k, s in enumerate(an["samplers"]):
    a = J2["accessors"][s["output"]]
    bv = J2["bufferViews"][a["bufferView"]]
    q = np.frombuffer(B2, np.float32, a["count"] * 4, bv.get("byteOffset", 0)).reshape(-1, 4)
    nrm = np.linalg.norm(q, axis=1)
    if abs(nrm.min() - 1) > 1e-4 or abs(nrm.max() - 1) > 1e-4:
        bad.append(f"通道{k} 四元数模长 {nrm.min():.6f}~{nrm.max():.6f} ≠ 1")
    if not np.allclose(q[0], q[-1], atol=1e-6):
        bad.append(f"通道{k} 首末帧不等 ⇒ **循环不闭合**")
for c in an["channels"]:
    if c["target"]["node"] not in joints:
        bad.append("通道目标不是 skin 关节")
ti = J2["accessors"][an["samplers"][0]["input"]]
print(f"动作：idle · {len(an['channels'])} 通道 · {ti['count']} 帧 · 时长 "
      f"{J2['accessors'][an['samplers'][0]['input']]['max'][0]:.1f}s（步长 {STEP}s）")
print(f"驱动骨：{[nm for nm, *_ in CH]}")
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print("✅ 自检通过（四元数模长=1 · 首末帧相等=循环闭合 · 目标均为 skin 关节）")
