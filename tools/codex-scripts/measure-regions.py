# -*- coding: utf-8 -*-
"""量出低模全身件的**裙摆区域**与**头发区域**（弹簧骨要按区域加权，不能猜）。
输出：y 范围、每层横截半径分布、候选骨位（裙：4 向；发：后+两侧）。"""
import json
import pathlib
import struct
import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = DH / "raw/rig/model-rigged-anim.glb"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = raw[off + 8: off + 8 + bl]
pr = J["meshes"][0]["primitives"][0]
a = J["accessors"][pr["attributes"]["POSITION"]]
bv = J["bufferViews"][a["bufferView"]]
P = np.frombuffer(BIN, np.float32, a["count"] * 3, bv.get("byteOffset", 0)).reshape(-1, 3).astype(np.float64)
b = J["accessors"][pr["attributes"]["JOINTS_0"]]
bv2 = J["bufferViews"][b["bufferView"]]
JT = np.frombuffer(BIN, np.uint16, b["count"] * 4, bv2.get("byteOffset", 0)).reshape(-1, 4)
c = J["accessors"][pr["attributes"]["WEIGHTS_0"]]
bv3 = J["bufferViews"][c["bufferView"]]
WT = np.frombuffer(BIN, np.float32, c["count"] * 4, bv3.get("byteOffset", 0)).reshape(-1, 4)

names = [n.get("name", "") for n in J["nodes"]]
parent_of = {}
for k, n in enumerate(J["nodes"]):
    for ch in n.get("children") or []:
        parent_of[ch] = k
world = {}
for i, n in enumerate(J["nodes"]):
    if not (n.get("name") or "").startswith("mixamorig"):
        continue
    chain, cur, g = [], i, 0
    while cur is not None and cur not in world:
        chain.append(cur)
        cur = parent_of.get(cur)
        g += 1
        if g > 200:
            raise SystemExit("环")
    w = world[cur] if cur is not None else np.zeros(3)
    for nd in reversed(chain):
        w = w + np.array(J["nodes"][nd].get("translation", [0, 0, 0]), np.float64)
        world[nd] = w
bi = {n.get("name"): i for i, n in enumerate(J["nodes"])}
yhip = world[bi["mixamorig:Hips"]][1]
ykle = world[bi["mixamorig:LeftLeg"]][1]
print(f"骨骼：Hips y={yhip:.3f} · 膝 y={ykle:.3f}")
print("身高范围 y:", round(P[:, 1].min(), 3), "~", round(P[:, 1].max(), 3))

print("\n=== 裙摆候选区（Hips→膝 之间）分层半径 ===")
for f in np.arange(0.0, 1.01, 0.1):
    y = yhip + (ykle - yhip) * f
    band = P[np.abs(P[:, 1] - y) < 0.012]
    if len(band) < 10:
        print(f"  f={f:.1f} y={y:.3f} 顶点 {len(band)}")
        continue
    rx = float(band[:, 0].max() - band[:, 0].min()) / 2
    rz = float(band[:, 2].max() - band[:, 2].min()) / 2
    print(f"  f={f:.1f} y={y:.3f} 顶点 {len(band):4d} · 半宽 x={rx:.3f} z={rz:.3f}")

print("\n=== 头发候选区（颈线以上）分层半径 ===")
yneck = world[bi["mixamorig:Neck"]][1]
for f in np.arange(0.0, 1.01, 0.15):
    y = yneck + (P[:, 1].max() - yneck) * f
    band = P[np.abs(P[:, 1] - y) < 0.01]
    if len(band) < 10:
        continue
    rx = float(band[:, 0].max() - band[:, 0].min()) / 2
    rz = float(band[:, 2].max() - band[:, 2].min()) / 2
    print(f"  f={f:.2f} y={y:.3f} 顶点 {len(band):4d} · 半宽 x={rx:.3f} z={rz:.3f}")
