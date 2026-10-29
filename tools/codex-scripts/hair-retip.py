# -*- coding: utf-8 -*-
"""按**新头发的实际范围**重算 4 条头发弹簧链的链尖

为什么必须做（`STATUS.json` 的 `hair_rebind_pass.known_mismatch`）：
  那 4 条链的链尖在 y≈0.22 —— 是 **spring-hair.py 给"身体那片头发"算的**。
  缝合后**新头的头发只到 y≈0.33** ⇒ 权重分对了，但**驱动它的骨长度对不上**，
  摆动幅度会偏大（骨头比肉长）。链尖必须按新头发重算。

安全性：本步**只改 JSON 里的 `extras.springBone.tail`**，不碰 BIN 缓冲区
（IBM 由链**根**决定，根没变）。所以不存在本仓反复踩过的"偏移平移"风险。

判据（不写死坐标）：
  · 头发顶点 = 头部 primitive 里主导骨为 Head、且低于头关节的顶点；
  · 每条链认领**方位角最近**的那批顶点（方位角从链尖方向算，不用"前后左右"标签）；
  · 链尖 = 该扇区**最低 3%** 顶点的质心。

用法：python tools/codex-scripts/hair-retip.py <件.glb> <输出.glb>
退出码：0 = 写出且自检通过；1 = 自检不过；2 = 前置问题。
"""
import json
import pathlib
import struct
import sys

import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-final.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/avatar-final2.glb"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = raw[off + 8: off + 8 + bl]


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(BIN, t, a["count"] * comps,
                         bv.get("byteOffset", 0)).reshape(a["count"], comps)


names = [n.get("name", "") for n in J["nodes"]]
joints = J["skins"][0]["joints"]
HAIR = [i for i in range(len(joints)) if "Hair" in names[joints[i]]]
IDX_HEAD = next(i for i, nd in enumerate(joints) if names[nd] == "mixamorig:Head")
if not HAIR:
    print("🔴 没有 Hair 链 ⇒ 停止")
    raise SystemExit(2)

prs = J["meshes"][0]["primitives"]
hi = max(range(len(prs)), key=lambda k: J["accessors"][prs[k]["attributes"]["POSITION"]]["count"])
pr = prs[hi]
P = acc(pr["attributes"]["POSITION"], 3).astype(np.float64)
JT = acc(pr["attributes"]["JOINTS_0"], 4).astype(np.int64)
WT = acc(pr["attributes"]["WEIGHTS_0"], 4).astype(np.float64)
ibm = acc(J["skins"][0]["inverseBindMatrices"], 16).reshape(-1, 4, 4).astype(np.float64)
head_pos = -ibm[IDX_HEAD][3, :3]
y_head = float(head_pos[1])
slot = np.argmax(WT, axis=1)
dom = np.take_along_axis(JT, slot[:, None], axis=1).ravel()
hair = (dom == IDX_HEAD) & (P[:, 1] < y_head - 0.005)
Hp = P[hair]
print(f"头部 primitive #{hi} · 头发顶点 {len(Hp)} · 头发 y 范围 "
      f"{Hp[:, 1].min():+.4f} .. {Hp[:, 1].max():+.4f}")
if len(Hp) < 50:
    print("🔴 头发顶点太少 ⇒ 停止")
    raise SystemExit(2)

# 每条链认领方位角最近的顶点，链尖 = 该扇区最低 3% 的质心
old_tips, new_tips = {}, {}
for i in HAIR:
    nd = J["nodes"][joints[i]]
    sb = nd.get("extras", {}).get("springBone", {})
    t0 = np.array(sb.get("tail", [0, 0, 0]), np.float64)
    old_tips[i] = t0.copy()
    a_t = float(np.arctan2(t0[0] - head_pos[0], t0[2] - head_pos[2]))
    ang = np.arctan2(Hp[:, 0] - head_pos[0], Hp[:, 2] - head_pos[2])
    d = np.abs((ang - a_t + np.pi) % (2 * np.pi) - np.pi)
    sel = Hp[d < np.pi / 4]                       # 45° 扇区
    if len(sel) < 10:
        sel = Hp[np.argsort(d)[:max(10, len(Hp) // 8)]]
    cut = np.percentile(sel[:, 1], 3)
    low = sel[sel[:, 1] <= cut]
    tip = low.mean(axis=0)
    # 链尖不得低于**头发实际最低点**（否则骨又比肉长）
    tip[1] = max(tip[1], float(Hp[:, 1].min()))
    new_tips[i] = tip
    nd.setdefault("extras", {}).setdefault("springBone", {})["tail"] = [float(x) for x in tip]
    print(f"  {names[joints[i]]:22s} 扇区 n={len(sel):6d} · 链尖 y {t0[1]:+.4f} → {tip[1]:+.4f}"
          f"（新头发最低 {Hp[:, 1].min():+.4f}）")

# 只改 JSON ⇒ 直接重打包（JSON 长度会变，必须重算 chunk 长度并补齐）
body = bytearray(BIN)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))

# 自检：读回 → 4 条链尖确实更新 · 且都不低于头发最低点 · BIN 长度未变（纯 JSON 改动）
raw2 = OUT.read_bytes()
jl2, = struct.unpack_from("<I", raw2, 12)
J2 = json.loads(raw2[20:20 + jl2].decode("utf-8"))
o2 = 20 + jl2 + ((-jl2) % 4)
bl2, = struct.unpack_from("<I", raw2, o2)
B2 = raw2[o2 + 8: o2 + 8 + bl2]
bad = []
for i in HAIR:
    t2 = np.array(J2["nodes"][J2["skins"][0]["joints"][i]]["extras"]["springBone"]["tail"], np.float64)
    if np.allclose(t2, old_tips[i]):
        bad.append(f"{names[joints[i]]} 链尖未更新")
    if t2[1] < Hp[:, 1].min() - 1e-6:
        bad.append(f"{names[joints[i]]} 链尖仍低于头发最低点")
if len(B2) != len(BIN):
    bad.append("BIN 长度变了（本步不应改缓冲区）")
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB · BIN {len(BIN)} → {len(B2)} 字节")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print("✅ 自检通过（4 条链尖已更新 · 均不低于头发最低点 · BIN 未动）")
