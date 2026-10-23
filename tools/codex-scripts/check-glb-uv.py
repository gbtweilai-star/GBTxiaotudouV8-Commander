# -*- coding: utf-8 -*-
"""查宝箱 GLB 每个材质组的 UV 落区：图集象限 = 左上木 / 右上铁 / 右下金 / 左下(未使用,暗)。"""
import json
import struct
import pathlib
import numpy as np

P = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8\assets\treasure-chest.glb")
raw = P.read_bytes()
jlen, = struct.unpack_from("<I", raw, 12)
j = json.loads(raw[20:20 + jlen].decode("utf-8"))
off = 20 + jlen + ((-jlen) % 4)
blen, = struct.unpack_from("<I", raw, off)
BIN = raw[off + 8: off + 8 + blen]


def acc(i):
    a = j["accessors"][i]
    bv = j["bufferViews"][a["bufferView"]]
    start = bv.get("byteOffset", 0)
    n = {"VEC3": 3, "VEC2": 2, "SCALAR": 1}[a["type"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(BIN, dt, a["count"] * n, start).reshape(a["count"], n)


QUAD = {(0, 0): "木(左上)", (0, 1): "铁(右上)", (1, 1): "金(右下)", (1, 0): "暗(左下,应无)"}
for i, pr in enumerate(j["meshes"][0]["primitives"]):
    name = j["materials"][pr["material"]]["name"]
    uv = acc(pr["attributes"]["TEXCOORD_0"])
    u0, v0 = uv.min(axis=0)
    u1, v1 = uv.max(axis=0)
    quads = set()
    for u, v in uv:
        quads.add((int(u > 0.5), int(v > 0.5)))
    print(f"[{name}] UV u:{u0:.3f}..{u1:.3f}  v:{v0:.3f}..{v1:.3f}  顶点 {len(uv)}")
    print("        跨象限: " + " · ".join(sorted(QUAD[q] for q in quads)))
print("\n图集实际内容（4 个象限的平均色）：")
im = j["images"][0]
bv = j["bufferViews"][im["bufferView"]]
png = BIN[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]  # noqa: E402
from PIL import Image  # noqa: E402
import io  # noqa: E402
a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
for (qx, qy), lbl in [((0, 0), "左上"), ((0, 1), "右上"), ((1, 1), "右下"), ((1, 0), "左下")]:
    blk = a[qy * 256:(qy + 1) * 256, qx * 256:(qx + 1) * 256]
    print(f"  {lbl}: 平均 RGB = {blk.reshape(-1, 3).mean(axis=0).round(0)}")
