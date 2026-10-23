# -*- coding: utf-8 -*-
"""贴图级调色（只动皮肤彩度，不动别的东西）+ 重新封装 GLB。

为什么必须动贴图：灯光扫描（state/_color-sweep.py）实测——
  现状皮肤 HSV = (24°, 0.149, 0.732)；把冷光收掉、暖光提上来，最好的那档只有 (25.4°, 0.167, 0.698)，
  而真人暖肤色在标准光下常见 (18–30°, 0.20–0.30, 0.60–0.72)。
  ⇒ **饱和度不是灯能给的**，是 albedo（color 贴图）本身太灰。

做法：
  ① 在 HSV 空间**只对"皮肤色相带"的像素**提彩度（默认 ×1.35），色相/明度不动；
  ② 掩膜做 5×5 羽化，避免边界出现硬圈；
  ③ 重新编码 JPEG(q=95) 换回 GLB 的对应 bufferView，其它 bufferView 原样搬、只改偏移。

用法：
  python tools/digihuman/dh-grade-texture.py                 # 只报（不写盘）
  python tools/digihuman/dh-grade-texture.py --apply         # 写 state/hd/tex/dh-v5-color.glb
"""
import argparse
import io
import json
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageFilter

SRC = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\hd\jaw-fix\dh-v4-jaw.glb"   # 流水线上游：v3 →(dh-jaw-fix)→ v4 →(本件)→ v5
OUTDIR = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\hd\tex"          # 只放证据（贴图 / 对比图）
ASSET_DIR = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets"
OUT = os.path.join(ASSET_DIR, "dh-v6-skin.glb")   # 在役件只有一份：不在仓里留第二份副本
# 命名口径：v5 = 只调了颜色；v6 = 颜色 + **粗糙度基线抬升**（去"抛光塑料"高光）⇒ 换名字，不叫 v5 了

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true")
ap.add_argument("--sat", type=float, default=1.35, help="皮肤彩度倍数")
ap.add_argument("--hue-lo", type=float, default=0.0)
ap.add_argument("--hue-hi", type=float, default=40.0)
ap.add_argument("--quality", type=int, default=95)
ap.add_argument("--rough-lift", type=float, default=0.0,
                help="粗糙度基线抬升 0..1（g' = lift + (1-lift)*g）；0 = 不动")
a = ap.parse_args()
os.makedirs(OUTDIR, exist_ok=True)


def parse_glb(raw):
    magic, ver, length = struct.unpack_from("<III", raw, 0)
    off, js, bn = 12, None, None
    while off < len(raw):
        clen, ctype = struct.unpack_from("<II", raw, off)
        body = raw[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = body
        elif ctype == 0x004E4942:
            bn = body
        off += 8 + clen + ((4 - clen % 4) % 4 if clen % 4 else 0)
    return json.loads(js.decode("utf-8")), bn


g, binchunk = parse_glb(open(SRC, "rb").read())
bvs = g["bufferViews"]
print("[GLB] bufferViews=%d images=%d" % (len(bvs), len(g.get("images", []))))

# 找到 color 贴图（material.pbrMetallicRoughness.baseColorTexture → texture → source）
mi = g["materials"][0]
cimg = g["textures"][mi["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]
im = g["images"][cimg]
bv = bvs[im["bufferView"]]
off, ln = bv.get("byteOffset", 0), bv["byteLength"]
print("[color 贴图] image #%d bufferView #%d  %d 字节" % (cimg, im["bufferView"], ln))
raw_img = binchunk[off: off + ln]
img = Image.open(io.BytesIO(raw_img)).convert("RGB")
print("[尺寸] %s" % (img.size,))

arr = np.asarray(img).astype(np.float32) / 255.0
r, gg, b = arr[..., 0], arr[..., 1], arr[..., 2]
mx = arr.max(axis=2)
mn = arr.min(axis=2)
v = mx
s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
# 色相（0..360）
h = np.zeros_like(mx)
d = np.maximum(mx - mn, 1e-6)
m = (mx == r)
h[m] = (60 * ((gg - b) / d) % 360)[m]
m = (mx == gg) & (mx != r)
h[m] = (60 * ((b - r) / d) + 120)[m]
m = (mx == b) & (mx != r) & (mx != gg)
h[m] = (60 * ((r - gg) / d) + 240)[m]

# 皮肤掩膜：色相带 + 有彩度 + 不太暗不太亮
# （收紧到 0–40°：金色饰边在 45–50°，别跟着一起加彩，那是衣服不是皮肤）
z = np.zeros_like(h)
mask = ((h >= a.hue_lo) & (h <= a.hue_hi) & (s > 0.08) & (s < 0.55) & (v > 0.25) & (v < 0.96))
print("[掩膜] 皮肤候选像素 %.2f%%（%d px）" % (100 * mask.mean(), int(mask.sum())))
# 羽化掩膜（用 Pillow 做模糊，避免边界硬圈）
mk = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
feather = np.asarray(mk).astype(np.float32) / 255.0

s2 = np.clip(s * (1.0 + (a.sat - 1.0) * feather), 0.0, 1.0)
# 从 HSV 反算回 RGB（用 np.select 分段，逐像素无循环）
cc = v * s2
xx = cc * (1 - np.abs((h / 60.0) % 2 - 1))
m0 = v - cc
seg = np.floor(h / 60.0).astype(np.int32) % 6
cond = [(seg == k) for k in range(6)]
r2 = np.select(cond, [cc, xx, z, z, xx, cc], 0.0)
g2 = np.select(cond, [xx, cc, cc, xx, z, z], 0.0)
b2 = np.select(cond, [z, z, xx, cc, cc, xx], 0.0)
out = np.stack([r2, g2, b2], axis=-1) + m0[..., None]
res = (np.clip(out, 0, 1) * 255).round().astype(np.uint8)

before = res.copy()
im2 = Image.fromarray(res)
buf = io.BytesIO()
im2.save(buf, format="JPEG", quality=a.quality, subsampling=0)
new_img = buf.getvalue()
print("[重编码] JPEG q=%d %d → %d 字节" % (a.quality, ln, len(new_img)))

# 视觉差（只在掩膜内算，避免被黑衣服稀释）
a1 = np.asarray(img).astype(np.float32)
d_skin = np.abs(a1[mask] - res[mask]).mean()
print("[掩膜内平均色差] %.2f/255（0 表示没动）" % d_skin)

if not a.apply:
    print("[写盘] 跳过（没给 --apply）")
    sys.exit(0)

# ── 粗糙度抬升（2026-10-21 夜加）：皮肤看着"抛光塑料"，一个硬指标是 roughness 中位数只有 0.369
#    （G 通道现量 均值 0.527 / 中位 0.369 / p10 0.290）。真实皮肤在标准光下 0.45–0.65。
#    不改几何、不加贴图：把 G 通道按 g' = lift + (1-lift)*g 整体抬（保住原有的高低起伏，只上移基线）。
repl = {im["bufferView"]: new_img}
if a.rough_lift > 0:
    mr = g["materials"][0]["pbrMetallicRoughness"].get("metallicRoughnessTexture")
    if mr:
        mi2 = g["textures"][mr["index"]]["source"]
        im3 = g["images"][mi2]
        bv3 = g["bufferViews"][im3["bufferView"]]
        o3, l3 = bv3.get("byteOffset", 0), bv3["byteLength"]
        imr = Image.open(io.BytesIO(binchunk[o3: o3 + l3])).convert("RGB")
        ar = np.asarray(imr).astype(np.float32) / 255.0
        g_old = ar[..., 1].copy()
        ar[..., 1] = a.rough_lift + (1.0 - a.rough_lift) * ar[..., 1]
        ar = np.clip(ar, 0, 1)
        buf3 = io.BytesIO()
        Image.fromarray((ar * 255).round().astype(np.uint8)).save(buf3, format="PNG", optimize=True)
        new_mr = buf3.getvalue()
        repl[im3["bufferView"]] = new_mr
        print("[粗糙度] G 中位 %.3f → %.3f（抬升系数 %.2f）· PNG %d → %d 字节" % (
            float(np.median(g_old)), float(np.median(ar[..., 1])), a.rough_lift, l3, len(new_mr)))
    else:
        print("[粗糙度] 没找到 metallicRoughnessTexture，跳过")

# ── 重建 BIN：按原 byteOffset 顺序搬，替换掉被改的那几块 ────────────────────────
order = sorted(range(len(bvs)), key=lambda i: bvs[i].get("byteOffset", 0))
new_bin = bytearray()
for i in order:
    blk = bvs[i]
    data = repl.get(i)
    if data is None:
        o0 = blk.get("byteOffset", 0)
        data = binchunk[o0: o0 + blk["byteLength"]]
    while len(new_bin) % 4:
        new_bin.append(0)
    blk["byteOffset"] = len(new_bin)
    blk["byteLength"] = len(data)
    new_bin.extend(data)
while len(new_bin) % 4:
    new_bin.append(0)
g["buffers"][0]["byteLength"] = len(new_bin)

js = json.dumps(g, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
out = bytearray()
out.extend(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(new_bin)))
out.extend(struct.pack("<II", len(js), 0x4E4F534A))
out.extend(js)
out.extend(struct.pack("<II", len(new_bin), 0x004E4942))
out.extend(new_bin)
open(OUT, "wb").write(out)
print("[导出] %s  %d 字节" % (OUT, len(out)))
