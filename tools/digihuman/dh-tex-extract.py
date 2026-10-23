# -*- coding: utf-8 -*-
"""把 GLB 里的贴图抠出来落盘（二进制原样），并裁一张 1:1 特写看压缩痕迹。"""
import io
import json
import os
import struct

from PIL import Image

GLB = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets\dh-v5-color.glb"
OUT = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\hd\tex"
os.makedirs(OUT, exist_ok=True)

raw = open(GLB, "rb").read()
off = 12
js = bn = None
while off < len(raw):
    clen, ctype = struct.unpack_from("<II", raw, off)
    body = raw[off + 8: off + 8 + clen]
    if ctype == 0x4E4F534A:
        js = body
    elif ctype == 0x004E4942:
        bn = body
    off += 8 + clen + ((4 - clen % 4) % 4 if clen % 4 else 0)
g = json.loads(js.decode("utf-8"))

for i, im in enumerate(g.get("images", [])):
    v = g["bufferViews"][im["bufferView"]]
    b = bn[v.get("byteOffset", 0): v.get("byteOffset", 0) + v["byteLength"]]
    ext = "jpg" if b[:2] == b"\xff\xd8" else "png"
    name = (im.get("name") or "img%d" % i).replace(" ", "_")
    p = os.path.join(OUT, "%02d-%s.%s" % (i, name, ext))
    open(p, "wb").write(b)
    print("[抠出] %s %d 字节" % (p, len(b)))

# 彩色贴图 1:1 特写（脸/胸前那块，坐标按 4096 比例取）
col = Image.open(os.path.join(OUT, "01-Color.jpg")).convert("RGB")
print("彩色贴图 %s mode=%s" % (col.size, col.mode))
crop = col.crop((1400, 300, 2000, 900)).resize((1200, 1200), Image.NEAREST)
crop.save(os.path.join(OUT, "color-1to1-zoom.png"))
print("[特写] %s" % os.path.join(OUT, "color-1to1-zoom.png"))

# 顺便量一下像素级“块效应”指标：8×8 块边界与其他位置的梯度差
import numpy as np
arr = np.asarray(col.convert("L"), dtype=np.float32)
h, w = arr.shape
dx = np.abs(np.diff(arr, axis=1))
block_cols = dx[:, 7::8]
other_cols = np.delete(dx, np.arange(7, dx.shape[1], 8), axis=1)
ratio = float(block_cols.mean() / max(1e-6, other_cols.mean()))
print("[块效应] 8px 边界的水平梯度均值 %.3f vs 其他 %.3f ⇒ 比值 %.3f（>1.1 说明 JPEG 块效应明显）"
      % (block_cols.mean(), other_cols.mean(), ratio))
