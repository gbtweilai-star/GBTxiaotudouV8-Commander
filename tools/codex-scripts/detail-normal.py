# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""专业技法 · 毛孔级细节法线（detail normal bake）：从 albedo 高频提细节，混入现有 normalMap。

原理（与商业材质的 detail-normal 同源）：
  ① 取 baseColor 的亮度 → 高斯高通（减去模糊）得到**微观起伏**
  ② 高通图求梯度 (dx,dy) → 作为切线空间法线的 xy 扰动
  ③ 与原法线混合：n' = normalize(n_xy + k·(dx,dy), n_z) → 归一化后编码回 RGB
读数：原/新法线图的高频能量、平均扰动量（可证伪：能量必须上升，且不爆饱和）。
"""
import io
import json
import pathlib
import struct
import numpy as np
import cv2
from PIL import Image

WS = pathlib.Path(_GBT_ROOT)
GLB = WS / "holo_pet/assets/digital-human/raw/rig/model-rigged-anim.glb"
STRENGTH = 1.0          # 细节强度（0.5=很轻 3=明显）

raw = GLB.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
del raw

mat = J["materials"][0]
pbr = mat.get("pbrMetallicRoughness", {})


def img_index_of(tex):
    return J["textures"][tex["index"]]["source"]


bc_i = img_index_of(pbr["baseColorTexture"])
nm_i = img_index_of(mat["normalTexture"])
print(f"槽位解析：baseColor=image[{bc_i}] · normal=image[{nm_i}]")


def read_img(i):
    bv = J["bufferViews"][J["images"][i]["bufferView"]]
    return bytes(BIN[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]])


base = Image.open(io.BytesIO(read_img(bc_i))).convert("RGB")
nrm = Image.open(io.BytesIO(read_img(nm_i))).convert("RGB")
print(f"baseColor {base.size} · normal {nrm.size}")

g = cv2.cvtColor(np.asarray(base), cv2.COLOR_RGB2GRAY).astype(np.float32)
# 对齐到**法线图的分辨率**再算高通（两张图尺寸不同，直接相加会因形状不符而失败 —— 实测踩到）
g = cv2.resize(g, (nrm.width, nrm.height), interpolation=cv2.INTER_AREA)
blur = cv2.GaussianBlur(g, (0, 0), 1.2)
hp = g - blur                                    # 微观起伏
dx = cv2.Sobel(hp, cv2.CV_32F, 1, 0, ksize=3) * (STRENGTH / 8.0)
dy = cv2.Sobel(hp, cv2.CV_32F, 0, 1, ksize=3) * (STRENGTH / 8.0)
print(f"高通能量(标准差) {hp.std():.2f} · 扰动 dx/dy 幅度 {np.abs(dx).mean():.3f}/{np.abs(dy).mean():.3f}")

n = np.asarray(nrm).astype(np.float32) / 127.5 - 1.0             # 解码到 [-1,1]
before = float(np.std(n[:, :, :2]))
n[:, :, 0] = n[:, :, 0] + dx
n[:, :, 1] = n[:, :, 1] + dy
ln = np.linalg.norm(n, axis=2, keepdims=True)
n = n / np.maximum(ln, 1e-6)
after = float(np.std(n[:, :, :2]))
out = (np.clip(n * 0.5 + 0.5, 0, 1) * 255).astype(np.uint8)
buf = io.BytesIO()
Image.fromarray(out).save(buf, format="JPEG", quality=95)
new_bytes = buf.getvalue()
print(f"法线 xy 能量 {before:.4f} → {after:.4f}（应上升）· 新图 {len(new_bytes)/1024:.0f} KB")

# 只替换法线图的 bufferView（其余原样搬移，保持 4 字节对齐）
views = J["bufferViews"]
nm_bv = J["images"][nm_i]["bufferView"]
new_bin = bytearray()
for i, v in enumerate(views):
    while len(new_bin) % 4:
        new_bin.append(0)
    if i == nm_bv:
        v["byteOffset"] = len(new_bin)
        v["byteLength"] = len(new_bytes)
        new_bin.extend(new_bytes)
    else:
        o = v.get("byteOffset", 0)
        v["byteOffset"] = len(new_bin)
        new_bin.extend(bytes(BIN[o:o + v["byteLength"]]))
J["images"][nm_i]["mimeType"] = "image/jpeg"
while len(new_bin) % 4:
    new_bin.append(0)
J["buffers"][0]["byteLength"] = len(new_bin)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
GLB.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(new_bin))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(new_bin)) + b"BIN\x00" + bytes(new_bin))
print(f"回写 {GLB.name} · {GLB.stat().st_size/1024/1024:.2f} MB（法线细节已烘进资产）")
