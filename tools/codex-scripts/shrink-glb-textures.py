# -*- coding: utf-8 -*-
"""把 GLB 里**作为 metalRough 使用**的大图替换成 4×4 中性灰 JPEG（面板档省体积）。
依据：材质已设 metallicFactor=0 / roughnessFactor=0.75 ⇒ 该贴图接近中性，缩成 4×4 等价可接受。"""
import io
import json
import pathlib
import struct
import sys
from PIL import Image

p = pathlib.Path(sys.argv[1])
raw = p.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = raw[off + 8: off + 8 + bl]

targets = set()
for m in J.get("materials", []):
    pbr = m.get("pbrMetallicRoughness", {})
    if "metallicRoughnessTexture" in pbr:
        targets.add(J["textures"][pbr["metallicRoughnessTexture"]["index"]]["source"])
if not targets:
    print("没有 metalRough 贴图，跳过")
    raise SystemExit(0)

tiny = io.BytesIO()
Image.new("RGB", (4, 4), (0, 200, 0)).save(tiny, format="JPEG", quality=80)   # glTF: G=roughness B=metallic
tiny = tiny.getvalue()

new_bin = bytearray()
for i, im in enumerate(J["images"]):
    bv = J["bufferViews"][im["bufferView"]]
    while len(new_bin) % 4:
        new_bin.append(0)
    o = bv.get("byteOffset", 0)
    data = tiny if i in targets else BIN[o:o + bv["byteLength"]]
    bv["byteOffset"] = len(new_bin)
    bv["byteLength"] = len(data)
    new_bin.extend(data)
    if i in targets:
        im["mimeType"] = "image/jpeg"
while len(new_bin) % 4:
    new_bin.append(0)
J["buffers"][0]["byteLength"] = len(new_bin)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
p.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(new_bin))
              + struct.pack("<I", len(js)) + b"JSON" + js
              + struct.pack("<I", len(new_bin)) + b"BIN\x00" + bytes(new_bin))
print(f"已缩 {len(targets)} 张 metalRough → 4×4 JPEG · 新体积 {p.stat().st_size/1024/1024:.2f} MB")
