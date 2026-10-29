# -*- coding: utf-8 -*-
"""定案修法：pymeshlab **几何 QEM（不带纹理）** + UV 原样 → trimesh 导 GLB → 注入原贴图。
（Round 19 定案：`..._with_texture` 缺贴图会退化成乱塌缩；几何 QEM 本身正常。）"""
import json
import pathlib
import struct
import trimesh
import pymeshlab as ml

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
RIG = WS / "holo_pet/assets/digital-human/raw/rig"
SRC = RIG / "part-head.glb"
TMP = pathlib.Path(r"C:\gbt_pml")
TMP.mkdir(exist_ok=True)
OBJ = TMP / "geo_low.obj"
MID = RIG / "head-geo-low.glb"
OUT = RIG / "head-fixed-low.glb"
TARGET = 75000

# ① 几何 QEM（不带纹理）
ms = ml.MeshSet()
ms.load_new_mesh(str(SRC))
ms.meshing_decimation_quadric_edge_collapse(targetfacenum=TARGET, preserveboundary=True,
                                            preservenormal=True, planarquadric=False, selected=False)
m0 = ms.current_mesh()
print(f"几何 QEM：面 {m0.face_number()} 顶点 {m0.vertex_number()} · 有纹理坐标 {m0.has_wedge_tex_coord()}")
ms.save_current_mesh(str(OBJ), save_textures=False)
# ② trimesh 导 GLB（保 UV，不翻 V）
m = trimesh.load(str(OBJ), process=False)
m.export(str(MID))
print(f"中转 GLB：{MID.name} · 顶点 {len(m.vertices)} 面 {len(m.faces)} · 有 UV {getattr(m.visual, 'uv', None) is not None}")

# ③ 注入原贴图（baseColor + normal）
raw = MID.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode())
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
sraw = SRC.read_bytes()
sjl, = struct.unpack_from("<I", sraw, 12)
SJ = json.loads(sraw[20:sjl + 20].decode())
soff = 20 + sjl + ((-sjl) % 4)
sbl, = struct.unpack_from("<I", sraw, soff)
SBIN = sraw[soff + 8:soff + 8 + sbl]
smat = SJ["materials"][0]
spbr = smat.get("pbrMetallicRoughness", {})


def view(d):
    while len(BIN) % 4:
        BIN.append(0)
    o = len(BIN)
    BIN.extend(d)
    J["bufferViews"].append({"buffer": 0, "byteOffset": o, "byteLength": len(d)})
    return len(J["bufferViews"]) - 1


J.setdefault("images", [])
J.setdefault("textures", [])
J.setdefault("materials", [])
for t in (spbr.get("baseColorTexture"), smat.get("normalTexture")):
    if not t:
        continue
    si = SJ["textures"][t["index"]]["source"]
    bv = SJ["bufferViews"][SJ["images"][si]["bufferView"]]
    o = bv.get("byteOffset", 0)
    J["images"].append({"bufferView": view(SBIN[o:o + bv["byteLength"]]),
                        "mimeType": SJ["images"][si].get("mimeType", "image/jpeg")})
    J["textures"].append({"sampler": 0, "source": len(J["images"]) - 1})
J.setdefault("samplers", [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}])
mat = {"name": "head", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                                "metallicFactor": 0, "roughnessFactor": 0.7}}
if len(J["textures"]) > 1:
    mat["normalTexture"] = {"index": 1}
J["materials"].append(mat)
mi = len(J["materials"]) - 1
for mm in J["meshes"]:
    for pr in mm["primitives"]:
        pr["material"] = mi
body = bytearray(BIN)
while len(body) % 4:
    body.append(0)
J["buffers"][0]["byteLength"] = len(body)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode()
while len(js) % 4:
    js += b" "
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB")
