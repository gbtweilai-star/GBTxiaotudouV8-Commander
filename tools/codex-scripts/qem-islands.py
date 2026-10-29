# -*- coding: utf-8 -*-
"""缝锁定 QEM（**按 UV 拆焊 + 逐岛坍缩**）—— 不需 DCC，纯 numpy/scipy/fast_simplification。
输入：raw/rig/part-head.glb（高密度头）→ 输出：raw/rig/head-islands-low.glb（保 UV 缝的低模头）
用法：python tools/codex-scripts/qem-islands.py <in.glb> <out.glb> <target_faces>  （用 python 3.12 跑）"""
import json
import pathlib
import struct
import sys
import numpy as np
import fast_simplification
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WS / "holo_pet/assets/digital-human/raw/rig/part-head.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else WS / "holo_pet/assets/digital-human/raw/rig/head-islands-low.glb"
TARGET = int(sys.argv[3]) if len(sys.argv) > 3 else 75000

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = raw[off + 8: off + 8 + bl]
pr = J["meshes"][0]["primitives"][0]


def acc(i, comps, dt=np.float64):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(BIN, t, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps).astype(dt)


P = acc(pr["attributes"]["POSITION"], 3)
N = acc(pr["attributes"]["NORMAL"], 3)
UV = acc(pr["attributes"]["TEXCOORD_0"], 2)
F = acc(pr["indices"], 1).astype(np.int64).reshape(-1, 3)
print(f"输入 {len(P)} 顶点 / {len(F)} 三角形")

# ① 按 (位置, UV) 拆焊
KEY = np.concatenate([np.round(P, 5), np.round(UV, 5)], axis=1)
_, first, inv = np.unique(KEY, axis=0, return_index=True, return_inverse=True)
P2, UV2, N2 = P[first], UV[first], N[first]
F2 = inv[F]
print(f"拆焊后 {len(P2)} 顶点（UV 岛被物理分开）")

# ② 连通块 = UV 岛
e = np.concatenate([F2[:, [0, 1]], F2[:, [1, 2]], F2[:, [2, 0]]])
g = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(P2), len(P2)))
ncomp, lab = connected_components(g, directed=False)
print(f"UV 岛数 {ncomp}")

# ③ 逐岛 QEM（面数按占比）
out_V, out_UV, out_N, out_F = [], [], [], []
voff = 0
for c in range(ncomp):
    fmask = lab[F2[:, 0]] == c
    fc = F2[fmask]
    if len(fc) < 8:
        vids = np.unique(fc)
        remap = {v: i for i, v in enumerate(vids)}
        out_V.append(P2[vids])
        out_UV.append(UV2[vids])
        out_N.append(N2[vids])
        out_F.append(np.vectorize(remap.get)(fc) + voff)
        voff += len(vids)
        continue
    vids = np.unique(fc)
    remap = -np.ones(len(P2), np.int64)
    remap[vids] = np.arange(len(vids))
    vc, fc2 = P2[vids], remap[fc]
    tgt = max(4, int(round(TARGET * len(fc) / len(F2))))
    if len(fc2) > tgt:
        vc2, fc3 = fast_simplification.simplify(vc, fc2, target_count=tgt)
    else:
        vc2, fc3 = vc, fc2
    # ③b 边界吸回（缝锁定）：岛边界顶点吸到本岛**原始边界**的最近点

    def edge_counts(f):
        e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
        e = np.sort(e, axis=1)
        uniq, cnt = np.unique(e, axis=0, return_counts=True)
        return uniq, cnt
    ue_o, co = edge_counts(fc2)
    b_o = np.unique(ue_o[co == 1])
    if len(b_o) > 2:
        obtree = cKDTree(vc[b_o])
        ue_n, cn = edge_counts(fc3)
        b_n = np.unique(ue_n[cn == 1])
        if len(b_n):
            _, nb = obtree.query(vc2[b_n], k=1)
            vc2[b_n] = vc[b_o][nb]                      # 吸回原始边界 ⇒ 缝闭合
    # ④ 岛内最近邻回传 UV/法线（同岛内连续 ⇒ 不会错缝）
    tree = cKDTree(P2[vids])
    _, idx = tree.query(vc2, k=1)
    out_V.append(vc2.astype(np.float64))
    out_UV.append(UV2[vids][idx])
    out_N.append(N2[vids][idx])
    out_F.append(fc3.astype(np.int64) + voff)
    voff += len(vc2)

V3 = np.concatenate(out_V)
UV3 = np.concatenate(out_UV)
N3 = np.concatenate(out_N)
F3 = np.concatenate(out_F)
print(f"输出 {len(V3)} 顶点 / {len(F3)} 三角形（目标 {TARGET}）")

# ⑤ 写出（仅几何/UV/法线；权重随后由面板档脚本按骨段距离算）
buf = bytearray()
views = []
accs = []


def view(data, target=None):
    while len(buf) % 4:
        buf.append(0)
    o = len(buf)
    buf.extend(data)
    v = {"buffer": 0, "byteOffset": o, "byteLength": len(data)}
    if target:
        v["target"] = target
    views.append(v)
    return len(views) - 1


def add(arr, ct, typ, target=None, mm=False):
    vi = view(arr.tobytes(), target)
    a = {"bufferView": vi, "componentType": ct, "count": len(arr), "type": typ}
    if mm:
        a.update({"min": [float(x) for x in arr.min(axis=0)], "max": [float(x) for x in arr.max(axis=0)]})
    accs.append(a)
    return len(accs) - 1


a_p = add(V3.astype(np.float32), 5126, "VEC3", 34962, True)
a_n = add(N3.astype(np.float32), 5126, "VEC3", 34962)
a_u = add(UV3.astype(np.float32), 5126, "VEC2", 34962)
a_i = add(F3.astype(np.uint32).reshape(-1), 5125, "SCALAR", 34963)
# 贴图原样搬运（baseColor + normal）
mat = J["materials"][0]
pbr = mat.get("pbrMetallicRoughness", {})
imgs, texs = [], []
for key, tex_obj in (("base", pbr.get("baseColorTexture")), ("norm", mat.get("normalTexture"))):
    if not tex_obj:
        continue
    si = J["textures"][tex_obj["index"]]["source"]
    bv = J["bufferViews"][J["images"][si]["bufferView"]]
    o = bv.get("byteOffset", 0)
    vi = view(BIN[o:o + bv["byteLength"]])
    imgs.append({"bufferView": vi, "mimeType": J["images"][si].get("mimeType", "image/jpeg")})
    texs.append({"sampler": 0, "source": len(imgs) - 1})
G = {"asset": {"version": "2.0", "generator": "GBT · 缝锁定 QEM（逐 UV 岛）"},
     "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "head_islands"}],
     "meshes": [{"name": "head_islands", "primitives": [{"attributes": {"POSITION": a_p, "NORMAL": a_n, "TEXCOORD_0": a_u},
                                                         "indices": a_i, "material": 0}]}],
     "materials": [{"name": "head", "normalTexture": {"index": 1} if len(texs) > 1 else {},
                    "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0, "roughnessFactor": 0.7}}],
     "textures": texs, "images": imgs,
     "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
     "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(buf)}]}
if len(texs) < 2:
    G["materials"][0].pop("normalTexture", None)
body = bytearray(buf)
while len(body) % 4:
    body.append(0)
G["buffers"][0]["byteLength"] = len(body)
js = json.dumps(G, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB")
