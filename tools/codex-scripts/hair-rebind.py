# -*- coding: utf-8 -*-
"""缝合后 · **把新头的头发挂到已有的头发弹簧骨上**

为什么必须补这一步：
  `avatar-grafted.glb` 继承了身体那条链的 26 个关节（含 4 根 Hair 弹簧骨），
  但**新缝上去的专用头那一片**是我用 head-graft-np.py 直接赋权给 Head/Neck 的 ——
  它的头发**不受弹簧骨驱动**，摆动时头和身子会"脱节"。
  Owner 要的是"**把所有部位都绑上**"，这一片不能漏。

做法（与 spring-hair.py 同一套判据，不写死坐标）：
  · 只在**头部 primitive** 上认头发：主导骨 = Head，且低于头关节；
  · 按**绕头竖轴的方位角**分到已有的 4 条 Hair 链（方位角从顶点质心算，不用写死标签）；
  · 权重 = 沿链深度（根 0 → 尖 1），乘 0.9，余量留给 Head（根部不撕）。

用法：python tools/codex-scripts/hair-rebind.py <缝合件.glb> <输出.glb>
退出码：0 = 写出且自检通过；1 = 自检不过；2 = 前置问题。
"""
import json
import pathlib
import struct
import sys

import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-grafted.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/avatar-final.glb"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), t, a["count"] * comps,
                         bv.get("byteOffset", 0)).reshape(a["count"], comps)


names = [n.get("name", "") for n in J["nodes"]]
joints = J["skins"][0]["joints"]
HAIR = {i: names[joints[i]] for i in range(len(joints)) if "Hair" in names[joints[i]]}
IDX_HEAD = next(i for i, nd in enumerate(joints) if names[nd] == "mixamorig:Head")
if not HAIR:
    print("🔴 该件里没有 Hair 弹簧骨（应该先跑过 spring-hair.py）⇒ 停止")
    raise SystemExit(2)
print(f"已有头发链 {len(HAIR)} 条：{sorted(HAIR.values())} · 关节总数 {len(joints)}")

# 头部 primitive = 顶点最多的那一个
prs = J["meshes"][0]["primitives"]
hi = max(range(len(prs)), key=lambda k: J["accessors"][prs[k]["attributes"]["POSITION"]]["count"])
pr = prs[hi]
P = acc(pr["attributes"]["POSITION"], 3).astype(np.float64)
JT = acc(pr["attributes"]["JOINTS_0"], 4).astype(np.int64)
WT = acc(pr["attributes"]["WEIGHTS_0"], 4).astype(np.float64)
print(f"头部 primitive #{hi}：顶点 {len(P)} · Hair 链 {len(HAIR)}")

ibm = acc(J["skins"][0]["inverseBindMatrices"], 16).reshape(-1, 4, 4).astype(np.float64)
head_pos = -ibm[IDX_HEAD][3, :3]                     # glTF 列主序：平移在 [3,:3]
y_head = head_pos[1]
y_top = P[:, 1].max()
# 头发链的根与尖：从 extras.springBone.tail 与节点 translation 取
chain_roots = {}
for i, nm in HAIR.items():
    node = joints[i]
    nd = J["nodes"][node]
    tail = nd.get("extras", {}).get("springBone", {}).get("tail")
    if tail is None:
        print(f"🔴 {nm} 缺 springBone.tail ⇒ 停止")
        raise SystemExit(2)
    chain_roots[i] = np.array(tail, np.float64)
print("链尖（世界坐标）：" + " · ".join(f"{HAIR[i]}={np.round(v, 3).tolist()}" for i, v in chain_roots.items()))

# 认头发：头部这片里，主导骨 = Head 且低于头关节（与 spring-hair.py 同判据）
slot = np.argmax(WT, axis=1)
dom = np.take_along_axis(JT, slot[:, None], axis=1).ravel()
hair = (dom == IDX_HEAD) & (P[:, 1] < y_head - 0.005)
print(f"新头的头发候选：{int(hair.sum())} / {len(P)}")
if hair.sum() < 50:
    print("🔴 头发候选太少 ⇒ 停止（宁缺不糊）")
    raise SystemExit(2)

# 方位角分链（不写死"前后左右"）：把每个顶点分给**方位角最近的链尖**
ang = np.arctan2(P[:, 0] - head_pos[0], P[:, 2] - head_pos[2])
tail_ang = {i: float(np.arctan2(t[0] - head_pos[0], t[2] - head_pos[2])) for i, t in chain_roots.items()}
y_low = float(np.percentile(P[hair][:, 1], 2))
span = max(1e-6, y_head - y_low)
JT2, WT2 = JT.copy(), WT.copy()
changed = 0
for vi in np.where(hair)[0]:
    a = float(ang[vi])
    best = min(HAIR, key=lambda i: abs((a - tail_ang[i] + np.pi) % (2 * np.pi) - np.pi))
    depth = float(np.clip((y_head - P[vi, 1]) / span, 0, 1))
    w = depth ** 1.5 * 0.9
    if w <= 0.02:
        continue
    JT2[vi] = [best, IDX_HEAD, 0, 0]
    WT2[vi] = [w, 1.0 - w, 0.0, 0.0]
    changed += 1
print(f"改权顶点：{changed}（分到 {len(HAIR)} 条链）")


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


jv = add_view(JT2.astype(np.uint16), 34962)
wv = add_view(WT2.astype(np.float32), 34962)
J["accessors"].append({"bufferView": jv, "componentType": 5123, "count": len(JT2), "type": "VEC4"})
J["accessors"].append({"bufferView": wv, "componentType": 5126, "count": len(WT2), "type": "VEC4"})
pr["attributes"]["JOINTS_0"] = len(J["accessors"]) - 2
pr["attributes"]["WEIGHTS_0"] = len(J["accessors"]) - 1
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

# 自检：读回 → 该 primitive 权重和 = 1 · Hair 骨确实进了 JOINTS · 关节数未变
raw2 = OUT.read_bytes()
jl2, = struct.unpack_from("<I", raw2, 12)
J2 = json.loads(raw2[20:20 + jl2].decode("utf-8"))
o2 = 20 + jl2 + ((-jl2) % 4)
bl2, = struct.unpack_from("<I", raw2, o2)
B2 = raw2[o2 + 8: o2 + 8 + bl2]


def acc2(i, c):
    a = J2["accessors"][i]
    bv = J2["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(B2, t, a["count"] * c, bv.get("byteOffset", 0)).reshape(a["count"], c)


bad = []
p2 = J2["meshes"][0]["primitives"][hi]
w2 = acc2(p2["attributes"]["WEIGHTS_0"], 4)
s = w2.sum(axis=1)
if abs(s.min() - 1) > 1e-4 or abs(s.max() - 1) > 1e-4:
    bad.append(f"权重和 {s.min():.4f}~{s.max():.4f}")
j2 = acc2(p2["attributes"]["JOINTS_0"], 4)
if not set(np.unique(j2)).intersection(set(HAIR)):
    bad.append("Hair 骨根本没进 JOINTS（改权没生效）")
if len(J2["skins"][0]["joints"]) != len(joints):
    bad.append("关节数变了（不应改）")
if len(BIN) % 4:
    bad.append("BIN 未对齐")
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB · 改权 {changed} 顶点")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print("✅ 自检通过（权重和=1 · Hair 骨已进 JOINTS · 关节数未变 · BIN 对齐）")
