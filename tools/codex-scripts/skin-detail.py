# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""面部/皮肤微细节：程序化生成**可平铺**的毛孔 + 细纹 detail normal，
只在**皮肤区**合成进原法线贴图（黑衣服上不该长毛孔）。

为什么必须做（REALISM.md §2 第 8 步）：
  真人皮肤放大后是**毛孔 + 细纹**。现在整身只有一张 1024² normal，
  放大即"塑料感"。detail normal 是把它从"光滑塑料"推向"有皮肤"的最低成本一刀。

口径：
  · 生成：随机高度场（wrap 模式高斯滤波 ⇒ **天然可平铺**）+ 毛孔凹点 + 细纹条带；
  · 合成：**whiteout blend**（detail normal 的标准做法）——
      n = normalize(vec3(n_base.xy + n_detail.xy, n_base.z * n_detail.z))
  · 只在皮肤区生效：按底色贴图判"暖色且够亮"（与 add-eyes.py 同一套判据），
    衣服/头发/鞋保持原样。
  · 法线贴图放大到与底色同尺寸后再合成，避免细节被插值糊掉。

用法：python tools/codex-scripts/skin-detail.py <in.glb> <out.glb> [强度=1.0]
退出码：0 = 写出且自检通过；1 = 自检不过；2 = 前置问题。
"""
import io
import json
import pathlib
import struct
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-springs.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/avatar-skin.glb"
STRENGTH = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
PREVIEW = WS / "render/皮肤微细节-detail.png"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])

# 可选：--mat=N 指定材质（缝合件里 0=身体 1=头）。不指定则取默认 0。
_mi = 0
for _a in sys.argv:
    if _a.startswith("--mat="):
        _mi = int(_a.split("=", 1)[1])
mat = J["materials"][_mi]
print(f"目标材质 #{_mi}: {mat.get(chr(34)+chr(110)+chr(97)+chr(109)+chr(101)+chr(34), chr(63))}")
pbr = mat.get("pbrMetallicRoughness", {})
if "normalTexture" not in mat:
    print("🔴 材质里没有 normalTexture ⇒ 无处合成，停止")
    raise SystemExit(2)


def img_bytes(idx):
    im = J["images"][idx]
    bv = J["bufferViews"][im["bufferView"]]
    o = bv.get("byteOffset", 0)
    return bytes(BIN[o:o + bv["byteLength"]])


bc_idx = J["textures"][pbr["baseColorTexture"]["index"]]["source"]
nm_idx = J["textures"][mat["normalTexture"]["index"]]["source"]
bc = Image.open(io.BytesIO(img_bytes(bc_idx))).convert("RGB")
nm0 = Image.open(io.BytesIO(img_bytes(nm_idx))).convert("RGB")
print(f"底色 {bc.width}² · 原法线 {nm0.width}² · 强度 {STRENGTH}")

# ── ① 程序化 detail normal（可平铺） ─────────────────────────────────────
S = 1024
rng = np.random.default_rng(20260925)
# 毛孔：随机凹点，用 wrap 高斯滤波聚成"坑"
pores = np.zeros((S, S), np.float64)
k = 9000
ys = rng.integers(0, S, k)
xs = rng.integers(0, S, k)
pores[ys, xs] = -1.0
pores = gaussian_filter(pores, 1.4, mode="wrap")
# 细纹：低频各向异性条带（皮肤细纹不是圆点）
grain = rng.normal(0, 1, (S, S))
fine = gaussian_filter(grain, (5.5, 1.4), mode="wrap")          # 横向拉长 => 细纹
fine = fine / (np.abs(fine).max() + 1e-9)
h = pores * 1.0 + fine * 0.55
h = h / (np.abs(h).max() + 1e-9)
# 高度场 → 法线（中心差分）
gy, gx = np.gradient(h)
nz = np.full_like(h, 1.0 / max(0.08, 0.35 * STRENGTH))
nrm = np.dstack([-gx * 2.4 * STRENGTH, -gy * 2.4 * STRENGTH, nz])
nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
detail = np.clip(nrm * 0.5 + 0.5, 0, 1)
print(f"detail normal 生成：{S}² · 毛孔 {k} 点（sigma 1.4）· 细纹 sigma(5.5,1.4)")

# 预览图（把 detail 存一份供人眼看）
PREVIEW.parent.mkdir(parents=True, exist_ok=True)
Image.fromarray((detail * 255).astype(np.uint8)).save(PREVIEW)

# ── ② 放大原法线到底色尺寸，按皮肤区合成 ─────────────────────────────────
W = bc.width
nm = np.asarray(nm0.resize((W, W), Image.LANCZOS)).astype(np.float64)
det = detail
if det.shape[0] != W:
    det = np.asarray(Image.fromarray((det * 255).astype(np.uint8)).resize((W, W), Image.LANCZOS)).astype(np.float64) / 255.0

bca = np.asarray(bc).astype(np.float64)
skin = (bca[:, :, 0] > bca[:, :, 1] + 6) & (bca[:, :, 1] > bca[:, :, 2]) & (bca[:, :, 0] > 120)
print(f"皮肤区：{skin.mean()*100:.1f}% 的纹素（只有这些会长毛孔）")

n1 = nm / 255.0 * 2.0 - 1.0                     # 原法线 [-1,1]
n2 = det * 2.0 - 1.0                            # 细节法线 [-1,1]
out = n1.copy()
blended = np.dstack([n1[:, :, 0] + n2[:, :, 0],
                     n1[:, :, 1] + n2[:, :, 1],
                     n1[:, :, 2] * n2[:, :, 2]])   # whiteout blend
blended /= np.linalg.norm(blended, axis=2, keepdims=True)
m = skin[:, :, None]
out = np.where(m, blended, n1)
out = np.clip(out * 0.5 + 0.5, 0, 1)
png = Image.fromarray((out * 255).astype(np.uint8))
buf = io.BytesIO()
png.save(buf, format="PNG", optimize=True)
newbytes = buf.getvalue()
print(f"合成后法线：{W}² · PNG {len(newbytes)/1024:.0f} KB（原 {len(img_bytes(nm_idx))/1024:.0f} KB）")

# ── ③ 写回 GLB（换掉那张法线图字节） ─────────────────────────────────────
nv = J["bufferViews"][J["images"][nm_idx]["bufferView"]]
o0 = nv.get("byteOffset", 0)
L0 = nv["byteLength"]
tail_off = o0 + L0
pad = (-len(newbytes)) % 4                     # bufferView 起点要 4 字节对齐
# 🔴 第一版只做了"新图接在原位置"，**没给后面的 bufferView 加偏移量** ⇒
#    image1 / image2 立刻读不回（自检抓到）。旧图换成新图后，后面所有 bufferView
#    的绝对偏移都要整体平移 `(len(newbytes)+pad) - L0`。
shift = (len(newbytes) + pad) - L0
nb = bytearray(BIN[:o0])
nb.extend(newbytes)
nb.extend(b"\x00" * pad)
nb.extend(BIN[tail_off:])
for i, bv in enumerate(J["bufferViews"]):
    if i == J["images"][nm_idx]["bufferView"]:
        bv["byteOffset"] = o0
        bv["byteLength"] = len(newbytes)
    elif bv.get("byteOffset", 0) > o0:
        bv["byteOffset"] = bv.get("byteOffset", 0) + shift
# 🔴 BIN 块长度必须 4 字节对齐 —— 漏了这一步 GLB 就是畸形文件。
#    实测：出厂闸 release-check.py 报 `BIN 长度 56976445 不是 4 的倍数`，
#    而本脚本自己的自检**没有查这一项** ⇒ 闸漏了、废品差点上线。现在补上。
while len(nb) % 4:
    nb.append(0)
J["buffers"][0]["byteLength"] = len(nb)
print(f"缓冲重写：原图 {L0/1024:.0f} KB → 新图 {len(newbytes)/1024:.0f} KB · 尾部整体平移 {shift:+d} 字节")
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(nb))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(nb)) + b"BIN\x00" + bytes(nb))
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB")

# ── ④ 自检：重新读回，确认法线图确实换了、其它图没坏 ─────────────────────
raw2 = OUT.read_bytes()
jl2, = struct.unpack_from("<I", raw2, 12)
J2 = json.loads(raw2[20:20 + jl2].decode("utf-8"))
o2 = 20 + jl2 + ((-jl2) % 4)
bl2, = struct.unpack_from("<I", raw2, o2)
B2 = raw2[o2 + 8: o2 + 8 + bl2]
bad = []
for i, im in enumerate(J2["images"]):
    bv = J2["bufferViews"][im["bufferView"]]
    oo = bv.get("byteOffset", 0)
    seg = B2[oo:oo + bv["byteLength"]]
    try:
        pic = Image.open(io.BytesIO(seg))
        pic.load()
        if i == nm_idx and pic.size[0] != W:
            bad.append(f"image{i} 尺寸未更新（{pic.size}）")
    except Exception as e:
        bad.append(f"image{i} 读不回（{type(e).__name__}）")
if not bad:
    pic = Image.open(io.BytesIO(B2[J2["bufferViews"][J2["images"][nm_idx]["bufferView"]].get("byteOffset", 0):
                                   J2["bufferViews"][J2["images"][nm_idx]["bufferView"]].get("byteOffset", 0) +
                                   J2["bufferViews"][J2["images"][nm_idx]["bufferView"]]["byteLength"]]))
    print(f"自检：{len(J2['images'])} 张图全部读回 OK · 法线现在 {pic.size[0]}²")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print("✅ 自检通过（法线已换 · 其余图未损坏）· 预览 → " + str(PREVIEW.name))
