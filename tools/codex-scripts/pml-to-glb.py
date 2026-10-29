# -*- coding: utf-8 -*-
"""pymeshlab 缝保护 QEM → OBJ → 自建 GLB（贴图沿用 part-head.glb 的原件）。
用 python 3.12 跑（pymeshlab 在那边）。"""
import json
import pathlib
import struct
import numpy as np
import pymeshlab as ml

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
RIG = WS / "holo_pet/assets/digital-human/raw/rig"
SRC = RIG / "part-head.glb"
OBJ = pathlib.Path(r"C:\gbt_pml\head_low.obj")
OUT = RIG / "head-pml-low.glb"
TARGET = 75000

ms = ml.MeshSet()
ms.load_new_mesh(r"C:\gbt_pml\head.glb")
ms.meshing_decimation_quadric_edge_collapse_with_texture(
    targetfacenum=TARGET, preserveboundary=True, preservenormal=True, planarquadric=True, selected=False)
print("简化：面", ms.current_mesh().face_number(), "顶点", ms.current_mesh().vertex_number())
ms.save_current_mesh(str(OBJ), save_textures=False)   # 本构建存贴图会崩 ⇒ 只存网格
print("已存 OBJ")

# 解析 OBJ（v / vt / f 的 v/vt 形式）
V, VT, F = [], [], []
for line in OBJ.read_text(errors="ignore").splitlines():
    p = line.split()
    if not p:
        continue
    if p[0] == "v":
        V.append([float(x) for x in p[1:4]])
    elif p[0] == "vt":
        VT.append([float(x) for x in p[1:3]])
    elif p[0] == "f":
        tri = []
        for tok in p[1:4]:
            a = tok.split("/")
            tri.append((int(a[0]) - 1, int(a[1]) - 1 if len(a) > 1 and a[1] else 0))
        F.append(tri)
V = np.array(V, np.float64)
VT = np.array(VT, np.float64)
F = np.array(F, np.int64)
print(f"OBJ：顶点 {len(V)} · UV {len(VT)} · 面 {len(F)}")

# 按 (顶点, UV) 重编号（OBJ 的 v/vt 是分开索引；glTF 需要每顶点一套属性）
key = np.stack([F[:, :, 0], F[:, :, 1]], axis=-1).reshape(-1, 2)
uniq, inv = np.unique(key, axis=0, return_inverse=True)
vi, ti = uniq[:, 0], uniq[:, 1]
NV, NUV, NF = V[vi], VT[ti].copy(), inv.reshape(-1, 3)
NUV[:, 1] = 1.0 - NUV[:, 1]     # 🔴 OBJ 的 vt 原点在左下、glTF 在左上 ⇒ 必须翻 V
# 法线：按面积加权平均
N = np.zeros_like(NV)
tris = NV[NF]
fn = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
for k in range(3):
    np.add.at(N, NF[:, k], fn)
N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
print(f"重编号：顶点 {len(NV)} · 面 {len(NF)}")

# 取原始贴图（baseColor + normal）
raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = raw[off + 8: off + 8 + bl]
mat = J["materials"][0]
pbr = mat.get("pbrMetallicRoughness", {})
buf = bytearray()
views = []
accs = []
imgs = []
texs = []


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


a_p = add(NV.astype(np.float32), 5126, "VEC3", 34962, True)
a_n = add(N.astype(np.float32), 5126, "VEC3", 34962)
a_u = add(NUV.astype(np.float32), 5126, "VEC2", 34962)
a_i = add(NF.astype(np.uint32).reshape(-1), 5125, "SCALAR", 34963)
for tex_obj in (pbr.get("baseColorTexture"), mat.get("normalTexture")):
    if not tex_obj:
        continue
    si = J["textures"][tex_obj["index"]]["source"]
    bv = J["bufferViews"][J["images"][si]["bufferView"]]
    o = bv.get("byteOffset", 0)
    imgs.append({"bufferView": view(BIN[o:o + bv["byteLength"]]), "mimeType": J["images"][si].get("mimeType", "image/jpeg")})
    texs.append({"sampler": 0, "source": len(imgs) - 1})
G = {"asset": {"version": "2.0", "generator": "GBT · pymeshlab 缝保护 QEM"},
     "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "head_pml"}],
     "meshes": [{"name": "head_pml", "primitives": [{"attributes": {"POSITION": a_p, "NORMAL": a_n, "TEXCOORD_0": a_u},
                                                     "indices": a_i, "material": 0}]}],
     "materials": [{"name": "head", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                                             "metallicFactor": 0, "roughnessFactor": 0.7}}],
     "textures": texs, "images": imgs,
     "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
     "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(buf)}]}
if len(texs) > 1:
    G["materials"][0]["normalTexture"] = {"index": 1}
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
