# -*- coding: utf-8 -*-
"""修剪 GLB：删掉**没有被任何材质引用**的 texture / image 及其 bufferView（孤儿贴图常见于手工组装）。
用法: python tools/codex-scripts/prune-glb.py <file.glb>"""
import json
import pathlib
import struct
import sys

p = pathlib.Path(sys.argv[1])
raw = p.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = raw[off + 8: off + 8 + bl]

# 1) 材质引用到的 texture
used_tex = set()
for m in J.get("materials", []):
    pbr = m.get("pbrMetallicRoughness", {})
    for slot in ("baseColorTexture", "metallicRoughnessTexture"):
        if slot in pbr:
            used_tex.add(pbr[slot]["index"])
    for slot in ("normalTexture", "occlusionTexture", "emissiveTexture"):
        if slot in m:
            used_tex.add(m[slot]["index"])
used_img = {J["textures"][t]["source"] for t in used_tex if "source" in J["textures"][t]}
print(f"引用：texture {sorted(used_tex)} · image {sorted(used_img)}（原有 {len(J.get('textures', []))} / {len(J.get('images', []))}）")

tex_map = {old: new for new, old in enumerate(sorted(used_tex))}
img_map = {old: new for new, old in enumerate(sorted(used_img))}
J["textures"] = [J["textures"][i] for i in sorted(used_tex)]
J["images"] = [J["images"][i] for i in sorted(used_img)]
for m in J.get("materials", []):
    pbr = m.get("pbrMetallicRoughness", {})
    for slot in ("baseColorTexture", "metallicRoughnessTexture"):
        if slot in pbr:
            pbr[slot]["index"] = tex_map[pbr[slot]["index"]]
    for slot in ("normalTexture", "occlusionTexture", "emissiveTexture"):
        if slot in m:
            m[slot]["index"] = tex_map[m[slot]["index"]]
for t in J["textures"]:
    t["source"] = img_map[t["source"]]

# 2) 重建 bufferView：保留被 accessor / 保留图片引用的
keep_bv = set()
for a in J.get("accessors", []):
    if "bufferView" in a:
        keep_bv.add(a["bufferView"])
for im in J["images"]:
    keep_bv.add(im["bufferView"])
new_bin = bytearray()
bv_map = {}
for i, bv in enumerate(J["bufferViews"]):
    if i not in keep_bv:
        continue
    while len(new_bin) % 4:
        new_bin.append(0)
    o = bv.get("byteOffset", 0)
    bv_map[i] = len(J["bufferViews"]) if False else None
    bv["byteOffset"] = len(new_bin)
    new_bin.extend(BIN[o:o + bv["byteLength"]])
kept_old = sorted(keep_bv)
old2new = {o: n for n, o in enumerate(kept_old)}
J["bufferViews"] = [J["bufferViews"][i] for i in kept_old]
for a in J.get("accessors", []):
    if "bufferView" in a:
        a["bufferView"] = old2new[a["bufferView"]]
for im in J["images"]:
    im["bufferView"] = old2new[im["bufferView"]]
while len(new_bin) % 4:
    new_bin.append(0)
J["buffers"][0]["byteLength"] = len(new_bin)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
p.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(new_bin))
              + struct.pack("<I", len(js)) + b"JSON" + js
              + struct.pack("<I", len(new_bin)) + b"BIN\x00" + bytes(new_bin))
print(f"修剪后 {p.stat().st_size/1024/1024:.2f} MB")
