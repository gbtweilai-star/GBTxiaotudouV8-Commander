# -*- coding: utf-8 -*-
"""头身缝合 · **重叠壳法**（纯 numpy，不需要 DCC）

为什么用"重叠"而不是"焊接"（这一轮想通的）：
  焊接要求两件在接缝处**拓扑一致**（顶点一一对应）——头是高模 737k、身是低模 28k，
  拓扑根本不同，硬焊必出破面。但**两件都是不透明实体** ⇒ 只要让"新的头+一截颈"
  **盖住**身体原有的脖子，接缝就被遮挡，视觉上完全连续。这是实时角色常用的做法。

几何账（上一轮量出来的）：
  · 两件同约定：身高归一 1.0、y ∈ [-0.5, +0.5]、居中；
  · 身体 Neck 关节 y=+0.3631 · 专用头最窄带(颈) y=+0.1000；
  · 缩放比 = 0.1369/0.4000 = **0.342**，头顶点对齐到 y=+0.5；
  · 缩放后头模 y ∈ [0.158, 0.5] ⇒ **在 y=0.33 处切**，留一截颈做重叠。

蒙皮：切下来的头+颈**全绑 Head 骨**，根部按高度渐变混入 Neck（避免根部僵死）。

用法：python tools/codex-scripts/head-graft-np.py <身体.glb> <专用头.glb> <输出.glb>
退出码：0 = 写出且自检通过；1 = 自检不过；2 = 前置问题。
"""
import json
import pathlib
import struct
import sys

import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
BODY = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-real.glb"
HEAD = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/head-hi/head-facing.glb"
OUT = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else DH / "raw/rig/avatar-grafted.glb"
Y_CUT = 0.33
SCALE = 0.342


def load(p):
    raw = p.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    o = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, o)
    return J, bytearray(raw[o + 8: o + 8 + bl])


def acc(J, B, i, c):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(B), t, a["count"] * c, bv.get("byteOffset", 0)).reshape(a["count"], c)


JB, BB = load(BODY)
JH, BH = load(HEAD)
pb = JB["meshes"][0]["primitives"][0]
ph = JH["meshes"][0]["primitives"][0]
names = [n.get("name", "") for n in JB["nodes"]]
joints = JB["skins"][0]["joints"]
IDX_HEAD = next(i for i, nd in enumerate(joints) if names[nd] == "mixamorig:Head")
IDX_NECK = next(i for i, nd in enumerate(joints) if names[nd] == "mixamorig:Neck")
print(f"身体 primitive {len(JB['meshes'][0]['primitives'])} 个 · 关节 {len(joints)} · "
      f"Head 槽 {IDX_HEAD} / Neck 槽 {IDX_NECK}")

Pb = acc(JB, BB, pb["attributes"]["POSITION"], 3).astype(np.float64)
Ph = acc(JH, BH, ph["attributes"]["POSITION"], 3).astype(np.float64)
UVh = acc(JH, BH, ph["attributes"]["TEXCOORD_0"], 2).astype(np.float64)
Nh = acc(JH, BH, ph["attributes"]["NORMAL"], 3).astype(np.float64)
Ih = acc(JH, BH, ph["indices"], 1).astype(np.int64).reshape(-1, 3)
print(f"身体顶点 {len(Pb)} · 专用头顶点 {len(Ph)} / 三角 {len(Ih)}")

# ── ① 对齐：缩放 0.342 + 头顶点对齐到 y=+0.5 + 中轴对齐 ──────────────────
# 用"皮肤区"的几何中心对齐中轴（避免被头发带偏）
top_h = Ph[:, 1].max()
cx_h = float(np.median(Ph[Ph[:, 1] > top_h - 0.02][:, 0]))
cz_h = float(np.median(Ph[Ph[:, 1] > top_h - 0.02][:, 2]))
top_b = Pb[:, 1].max()
_ibm = acc(JB, BB, JB["skins"][0]["inverseBindMatrices"], 16).reshape(-1, 4, 4).astype(np.float64)
head_j_y = float(-_ibm[IDX_HEAD][3, 1])       # glTF 列主序：平移在 [3,:3]
cx_b = float(np.median(Pb[Pb[:, 1] > 0.42][:, 0]))
cz_b = float(np.median(Pb[Pb[:, 1] > 0.42][:, 2]))
P1 = Ph.copy()
P1[:, 1] = (P1[:, 1] - top_h) * SCALE + top_b
P1[:, 0] = (P1[:, 0] - cx_h) * SCALE + cx_b
P1[:, 2] = (P1[:, 2] - cz_h) * SCALE + cz_b
print(f"对齐：头顶点 {top_h:+.4f}→{top_b:+.4f} · 缩放 {SCALE} · 中轴 x {cx_h:+.4f}→{cx_b:+.4f} · "
      f"z {cz_h:+.4f}→{cz_b:+.4f}")
print(f"  缩放后头模 y 范围 {P1[:, 1].min():+.4f} .. {P1[:, 1].max():+.4f}（身体 Neck 在 y={head_j_y:+.4f}）")

# ── ② 切：只留 y > Y_CUT（三个角都在面上方） ─────────────────────────────
keep = (P1[Ih[:, 0], 1] > Y_CUT) & (P1[Ih[:, 1], 1] > Y_CUT) & (P1[Ih[:, 2], 1] > Y_CUT)
Ih2 = Ih[keep]
used = np.unique(Ih2)
remap = -np.ones(len(P1), np.int64)
remap[used] = np.arange(len(used))
Ph2 = P1[used]
UVh2 = UVh[used]
Nh2 = Nh[used]
Ih3 = remap[Ih2].astype(np.uint32)
print(f"切面 y>{Y_CUT}：保留三角 {len(Ih3)} / {len(Ih)}（{len(Ih3)/len(Ih)*100:.1f}%）· "
      f"顶点 {len(Ph2)} · 保留部分 y 范围 {Ph2[:, 1].min():+.4f}..{Ph2[:, 1].max():+.4f}")

# ── ③ 蒙皮：Head 为主，根部按高度渐变混入 Neck ───────────────────────────
t = np.clip((Ph2[:, 1] - Y_CUT) / (top_b - Y_CUT), 0, 1)
w_head = 0.35 + 0.65 * t                      # 切面处 0.35（混 65% Neck），头顶 1.0
WH = np.stack([w_head, 1.0 - w_head, np.zeros_like(w_head), np.zeros_like(w_head)], axis=1)
JH4 = np.zeros((len(Ph2), 4), np.uint16)
JH4[:, 0] = IDX_HEAD
JH4[:, 1] = IDX_NECK
print(f"蒙皮：Head 权重 {w_head.min():.2f}..{w_head.max():.2f}（根部混 Neck 防僵）· 权重和 "
      f"{WH.sum(axis=1).min():.4f}~{WH.sum(axis=1).max():.4f}")


def add_view(B, arr, target=None):
    while len(B) % 4:
        B.append(0)
    o = len(B)
    B.extend(arr.tobytes())
    v = {"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes}
    if target:
        v["target"] = target
    JB["bufferViews"].append(v)
    return len(JB["bufferViews"]) - 1


def add_acc(B, arr, ct, typ, target=None, mm=False):
    vi = add_view(B, arr, target)
    a = {"bufferView": vi, "componentType": ct, "count": len(arr), "type": typ}
    if mm:
        a.update({"min": [float(x) for x in arr.min(axis=0)], "max": [float(x) for x in arr.max(axis=0)]})
    JB["accessors"].append(a)
    return len(JB["accessors"]) - 1


# ── ④ 把专用头的贴图与材质搬进身体 GLB ───────────────────────────────────
img_base = len(JB["images"])
tex_base = len(JB["textures"])
mat_base = len(JB["materials"])
for im in JH["images"]:
    bv = JH["bufferViews"][im["bufferView"]]
    o = bv.get("byteOffset", 0)
    vi = add_view(BB, np.frombuffer(bytes(BH[o:o + bv["byteLength"]]), np.uint8))
    JB["images"].append({"bufferView": vi, "mimeType": im.get("mimeType", "image/jpeg")})
for tx in JH["textures"]:
    JB["textures"].append({"sampler": 0, "source": img_base + tx["source"]})
hm = JH["materials"][0]
hp = hm.get("pbrMetallicRoughness", {})
nm = {"name": "head_hi", "doubleSided": hm.get("doubleSided", False),
      "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 0.55}}
if hp.get("baseColorTexture"):
    nm["pbrMetallicRoughness"]["baseColorTexture"] = {"index": tex_base + hp["baseColorTexture"]["index"]}
if hm.get("normalTexture"):
    nm["normalTexture"] = {"index": tex_base + hm["normalTexture"]["index"]}
JB["materials"].append(nm)
print(f"搬运贴图 {len(JH['images'])} 张 · 材质 → index {mat_base}")

a_p = add_acc(BB, Ph2.astype(np.float32), 5126, "VEC3", 34962, True)
a_n = add_acc(BB, Nh2.astype(np.float32), 5126, "VEC3", 34962)
a_u = add_acc(BB, UVh2.astype(np.float32), 5126, "VEC2", 34962)
a_i = add_acc(BB, Ih3.reshape(-1), 5125, "SCALAR", 34963)
a_j = add_acc(BB, JH4, 5123, "VEC4", 34962)
a_w = add_acc(BB, WH.astype(np.float32), 5126, "VEC4", 34962)
JB["meshes"][0]["primitives"].append({
    "attributes": {"POSITION": a_p, "NORMAL": a_n, "TEXCOORD_0": a_u,
                   "JOINTS_0": a_j, "WEIGHTS_0": a_w},
    "indices": a_i, "material": mat_base})

while len(BB) % 4:
    BB.append(0)
JB["buffers"][0]["byteLength"] = len(BB)
js = json.dumps(JB, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(BB))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(BB)) + b"BIN\x00" + bytes(BB))

# ── ⑤ 自检 ───────────────────────────────────────────────────────────────
raw2 = OUT.read_bytes()
jl2, = struct.unpack_from("<I", raw2, 12)
J2 = json.loads(raw2[20:20 + jl2].decode("utf-8"))
o2 = 20 + jl2 + ((-jl2) % 4)
bl2, = struct.unpack_from("<I", raw2, o2)
B2 = raw2[o2 + 8: o2 + 8 + bl2]
bad = []
prim2 = J2["meshes"][0]["primitives"]
if len(prim2) != 2:
    bad.append(f"primitive 数 {len(prim2)} ≠ 2")
for k, p in enumerate(prim2):
    for key in ("POSITION", "NORMAL", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"):
        if key not in p["attributes"]:
            bad.append(f"primitive{k} 缺 {key}")
w = np.frombuffer(B2[J2["bufferViews"][J2["accessors"][prim2[1]["attributes"]["WEIGHTS_0"]]["bufferView"]]
                     .get("byteOffset", 0):][:J2["accessors"][prim2[1]["attributes"]["WEIGHTS_0"]]["count"] * 16],
                  np.float32).reshape(-1, 4)
if abs(w.sum(axis=1).min() - 1) > 1e-4 or abs(w.sum(axis=1).max() - 1) > 1e-4:
    bad.append(f"头部权重和 {w.sum(axis=1).min():.4f}~{w.sum(axis=1).max():.4f}")
if len(BB) % 4:
    bad.append("BIN 未 4 字节对齐")
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB · primitive {len(prim2)}")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print("✅ 自检通过（2 primitive 全属性齐 · 头部权重和=1 · BIN 对齐）")
