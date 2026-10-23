# -*- coding: utf-8 -*-
"""对比两个 GLB 的几何与贴图，判断能否**直接移植骨架**（顶点顺序一致才可）。
用法: python tools/codex-scripts/compare-mesh.py <A.glb> <B.glb>"""
import hashlib
import io
import json
import pathlib
import struct
import sys
from PIL import Image


def load(p):
    raw = pathlib.Path(p).read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, raw[off + 8: off + 8 + bl], len(raw)


def acc_bytes(J, BIN, i):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    o = bv.get("byteOffset", 0)
    return bytes(BIN[o:o + bv["byteLength"]])


def slots(J):
    m = J["materials"][0]
    pbr = m.get("pbrMetallicRoughness", {})
    out = {}
    if "baseColorTexture" in pbr:
        out["baseColor"] = J["textures"][pbr["baseColorTexture"]["index"]]["source"]
    if "normalTexture" in m:
        out["normal"] = J["textures"][m["normalTexture"]["index"]]["source"]
    if "metallicRoughnessTexture" in pbr:
        out["metalRough"] = J["textures"][pbr["metallicRoughnessTexture"]["index"]]["source"]
    return out


for p in sys.argv[1:]:
    J, BIN, size = load(p)
    pr = J["meshes"][0]["primitives"][0]
    a = J["accessors"]
    pos = acc_bytes(J, BIN, pr["attributes"]["POSITION"])
    uv = acc_bytes(J, BIN, pr["attributes"]["TEXCOORD_0"]) if "TEXCOORD_0" in pr["attributes"] else b""
    print(f"\n{p.split(chr(92))[-1]} · {size/1024/1024:.2f} MB")
    print(f"  顶点 {a[pr['attributes']['POSITION']]['count']} · 三角形 {a[pr['indices']]['count']//3 if 'indices' in pr else '?'}")
    print(f"  POSITION sha {hashlib.sha256(pos).hexdigest()[:16]} · TEXCOORD sha {hashlib.sha256(uv).hexdigest()[:16]}")
    print(f"  骨架: skins={len(J.get('skins') or [])} · JOINTS_0={'有' if 'JOINTS_0' in pr['attributes'] else '无'}")
    for slot, idx in slots(J).items():
        bv = J["bufferViews"][J["images"][idx]["bufferView"]]
        data = bytes(BIN[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]])
        try:
            im = Image.open(io.BytesIO(data))
            info = f"{im.size[0]}×{im.size[1]} {im.format}"
        except Exception:
            info = "?"
        print(f"  {slot:11s} image[{idx}] {info} · {len(data)/1024:.0f} KB")
