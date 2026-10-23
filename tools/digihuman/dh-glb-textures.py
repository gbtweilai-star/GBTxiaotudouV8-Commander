# -*- coding: utf-8 -*-
"""读 GLB 里的贴图清单与像素尺寸（不解码整图，只读 PNG/JPEG 头 + GLB 结构）。"""
import io
import json
import struct
import sys

GLB = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets\dh-v5-color.glb"

raw = open(GLB, "rb").read()
magic, ver, length = struct.unpack_from("<III", raw, 0)
off = 12
json_chunk = None
bin_chunk = None
while off < len(raw):
    clen, ctype = struct.unpack_from("<II", raw, off)
    body = raw[off + 8: off + 8 + clen]
    if ctype == 0x4E4F534A:
        json_chunk = body
    elif ctype == 0x004E4942:
        bin_chunk = body
    off += 8 + clen + ((4 - clen % 4) % 4 if clen % 4 else 0)

g = json.loads(json_chunk.decode("utf-8"))


def png_size(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", b[16:24])
        return w, h, "png"
    if b[:2] == b"\xff\xd8":
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            m = b[i + 1]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5: i + 9])
                return w, h, "jpeg"
            seg = struct.unpack(">H", b[i + 2: i + 4])[0]
            i += 2 + seg
        return None
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return None
    return None


print("GLB %d 字节 · 版本 %d · 节点 %d · 网格 %d · 材质 %d · 贴图 %d · 动画 %d" % (
    length, ver, len(g.get("nodes", [])), len(g.get("meshes", [])),
    len(g.get("materials", [])), len(g.get("images", [])), len(g.get("animations", []))))
for a in g.get("animations", []):
    print("  动画: %-10s 通道 %d" % (a.get("name"), len(a.get("channels", []))))

bv = g.get("bufferViews", [])
for i, im in enumerate(g.get("images", [])):
    name = im.get("name") or im.get("uri") or ("bufferView#%d" % im.get("bufferView", -1))
    b = None
    if "bufferView" in im and bin_chunk is not None:
        v = bv[im["bufferView"]]
        b = bin_chunk[v.get("byteOffset", 0): v.get("byteOffset", 0) + v["byteLength"]]
    sz = png_size(b) if b else None
    mime = im.get("mimeType", "?")
    extra = ""
    if sz:
        w, h, fmt = sz
        extra = "%dx%d (%s)" % (w, h, fmt)
        if w != h and w > 0:
            extra += " · %s" % ("非方形" if abs(w / h - 1) > 0.01 else "方形")
    print("贴图 %d: %-28s %-12s %8d 字节  %s" % (
        i, str(name)[:28], mime.replace("image/", ""), len(b) if b else 0, extra))

for j, m in enumerate(g.get("materials", [])):
    pbr = m.get("pbrMetallicRoughness", {})
    print("材质 %d: %-16s baseTex=%s mrTex=%s normalTex=%s" % (
        j, str(m.get("name"))[:16],
        pbr.get("baseColorTexture", {}).get("index"),
        pbr.get("metallicRoughnessTexture", {}).get("index"),
        m.get("normalTexture", {}).get("index")))
