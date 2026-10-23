# -*- coding: utf-8 -*-
"""皮肤「去蜡感」重制：把源素材的**烘焙高光**压掉、按真人血色**重新上色**、把粗糙度**夹到真人区间**。

为什么必须动这一步（本轮才看清的真问题）：
  Owner 那张源图**本身就是"光泽人偶"审美** —— 皮肤是蜡的、高光是塑料的。
  PBR 只会**忠实**渲染它：参数再对，得到的也只是一张清晰的蜡像照片。
  要靠近"真人"，必须**重新诠释**皮肤，而不是照抄源图：
    · 底色贴图里**不该有镜面高光**（那是光照结果，不是反照率）—— 现在被烘进去了；
    · 真人皮肤有**血色分布**（颊/鼻/耳偏红，额头偏黄），不是均匀的灰白；
    · 真人皮肤粗糙度落在 **0.45–0.62** 的中窄带；源图实测均值 0.67、p10 0.41（偏光）。

做法（全部可机检）：
  ① 认皮肤：按材质 baseColorTexture 取底色图（**不能按尺寸猜**），判「暖且亮」；
  ② 压高光：L := L - k·max(0, L − p90)，把烘焙进去的镜面压平；
  ③ 上血色：向真人皮肤的 R:G:B 比例混合 + 低频斑驳（wrap 高斯 ⇒ 可平铺）；
  ④ 夹粗糙度：皮肤纹素夹到 [0.45, 0.62]；
  ⑤ 回写 GLB（安全的 bufferView 整体平移）+ 硬自检（所有图读回 + 尺寸核对）。

用法：python tools/codex-scripts/skin-tone.py <in.glb> <out.glb> [强度=1.0]
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

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-skin.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/avatar-real.glb"
K = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
PREVIEW = WS / "render/皮肤重制-对照.png"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])

mat = J["materials"][0]
pbr = mat.get("pbrMetallicRoughness", {})
if "baseColorTexture" not in pbr:
    print("🔴 材质没有 baseColorTexture ⇒ 停止")
    raise SystemExit(2)


def img_idx(tex_key):
    return J["textures"][mat[tex_key]["index"]]["source"] if tex_key in mat else \
        (J["textures"][pbr[tex_key]["index"]]["source"] if tex_key in pbr else None)


def img_rgb(idx):
    bv = J["bufferViews"][J["images"][idx]["bufferView"]]
    o = bv.get("byteOffset", 0)
    return Image.open(io.BytesIO(bytes(BIN[o:o + bv["byteLength"]]))).convert("RGB")


def img_bytes(idx):
    bv = J["bufferViews"][J["images"][idx]["bufferView"]]
    o = bv.get("byteOffset", 0)
    return bytes(BIN[o:o + bv["byteLength"]])


bc_i = img_idx("baseColorTexture")
mr_i = img_idx("metallicRoughnessTexture")
bc_im = img_rgb(bc_i)
mr_im = img_rgb(mr_i) if mr_i is not None else None
print(f"底色 image{bc_i} {bc_im.size} · 金属粗糙 image{mr_i} {mr_im.size if mr_im else '-'}")

bc = np.asarray(bc_im).astype(np.float64)
L = bc[:, :, 0] * 0.299 + bc[:, :, 1] * 0.587 + bc[:, :, 2] * 0.114
skin = (bc[:, :, 0] > bc[:, :, 1] + 6) & (bc[:, :, 1] >= bc[:, :, 2]) & (bc[:, :, 0] > 110)
print(f"皮肤区：{skin.mean()*100:.1f}% 纹素 · 皮肤平均色 "
      f"({bc[skin][:, 0].mean():.0f},{bc[skin][:, 1].mean():.0f},{bc[skin][:, 2].mean():.0f})"
      f" · 平均亮度 {L[skin].mean():.0f}")

# ── ② 压高光：把烘进底色的镜面压平 ────────────────────────────────────────
p90 = np.percentile(L[skin], 90)
excess = np.maximum(0.0, L - p90)
L2 = L - K * 0.85 * excess
ratio = np.where(L > 1e-6, L2 / np.maximum(L, 1e-6), 1.0)
bc2 = np.clip(bc * ratio[:, :, None], 0, 255)
print(f"压高光：p90={p90:.0f} · 压掉的最大亮度 {K*0.85*excess.max():.0f}")

# ── ③ 上血色：向真人皮肤的 R:G:B 比例混合 + 低频斑驳 ──────────────────────
# 真人浅肤色反照率大致比例 R:G:B ≈ 1.00 : 0.80 : 0.70（相对亮度），比"灰白"红得多
Lh = (bc2[:, :, 0] * 0.299 + bc2[:, :, 1] * 0.587 + bc2[:, :, 2] * 0.114)
target = np.dstack([Lh * 1.055, Lh * 0.815, Lh * 0.700])
out = bc2.copy()
m = skin[:, :, None]
out = np.where(m, bc2 * 0.42 + target * 0.58, bc2)
# 斑驳：真人皮肤不是均匀的（血管/色素低频起伏）
S = 512
rng = np.random.default_rng(20260925)
mot = gaussian_filter(rng.normal(0, 1, (S, S)), 22, mode="wrap")
mot = mot / (np.abs(mot).max() + 1e-9)
motf = np.asarray(Image.fromarray(((mot * 0.5 + 0.5) * 255).astype(np.uint8)).resize(
    (out.shape[1], out.shape[0]), Image.BICUBIC)).astype(np.float64) / 127.5 - 1.0
blush = np.dstack([motf * 7.0, motf * 2.5, motf * 1.0])          # 偏红的斑驳
out = np.where(m, out + blush * K, out)
out = np.clip(out, 0, 255)
print("上血色：向 (1.00:0.80:0.70) 混合 58% + 低频斑驳 ±7（σ=22 可平铺）")
print(f"  → 皮肤平均色 ({out[skin][:, 0].mean():.0f},{out[skin][:, 1].mean():.0f},{out[skin][:, 2].mean():.0f})")

bc_new = io.BytesIO()
Image.fromarray(out.astype(np.uint8)).save(bc_new, format="JPEG", quality=94)
bc_bytes = bc_new.getvalue()

# ── ④ 夹粗糙度到真人区间 ─────────────────────────────────────────────────
mr_bytes = None
if mr_im is not None:
    mr = np.asarray(mr_im).astype(np.float64)
    # 🔴 底色 2048²、金属粗糙 1024² —— **分辨率不同**：掩码必须跟着缩到 MR 的网格上，
    #    否则 `np.where` 的结果塞不进 mr2（实测直接广播报错）。别假设两张图同尺寸。
    if mr.shape[:2] != skin.shape[:2]:
        skin_mr = np.asarray(Image.fromarray((skin * 255).astype(np.uint8)).resize(
            (mr.shape[1], mr.shape[0]), Image.BILINEAR)).astype(np.float64) / 255.0 > 0.5
        print(f"  掩码缩放：{skin.shape[1]}² → {mr.shape[1]}²（皮肤占比 "
              f"{skin_mr.mean()*100:.1f}%）")
    else:
        skin_mr = skin
    r = mr[:, :, 1]
    r2 = np.clip(r, 0.45 * 255, 0.62 * 255)
    mr2 = mr.copy()
    mr2[:, :, 1] = np.where(skin_mr, r2, r)
    m = io.BytesIO()
    Image.fromarray(mr2.astype(np.uint8)).save(m, format="PNG", optimize=True)
    mr_bytes = m.getvalue()
    print(f"粗糙度：皮肤从均值 {r[skin_mr].mean()/255:.3f} 夹到 "
          f"{r2[skin_mr].mean()/255:.3f}（目标带 0.45–0.62）")

# 对照图
sheet = Image.new("RGB", (1024, 512), (18, 22, 34))
sheet.paste(bc_im.resize((512, 512)), (0, 0))
sheet.paste(Image.fromarray(out.astype(np.uint8)).resize((512, 512)), (512, 0))
PREVIEW.parent.mkdir(parents=True, exist_ok=True)
sheet.save(PREVIEW)

# ── ⑤ 回写 GLB ───────────────────────────────────────────────────────────
REPL = []
REPL.append((bc_i, bc_bytes))
if mr_bytes is not None:
    REPL.append((mr_i, mr_bytes))
# 从 BIN 里按 offset 从后往前替换，避免位移互相干扰
views = sorted([(J["images"][i]["bufferView"], i, data) for i, data in REPL],
               key=lambda t: J["bufferViews"][t[0]].get("byteOffset", 0))
# 🔴 前两版都在"把新图放回旧位置 + 平移后续偏移"上翻车（image1/image2 轮流读不回）。
#    这里改成**最不可能错的写法**：新图**追加到缓冲区末尾**，指向它们的两个 bufferView
#    改到新位置，**其他 bufferView 的偏移一律不动**。
#    代价：旧图字节变成冗余（文件大 ~2 MB）；收益：偏移正确性**不依赖任何累加推导**。
nb = bytearray(BIN)
for vi, ii, data in views:
    while len(nb) % 4:
        nb.append(0)
    newoff = len(nb)
    nb.extend(data)
    bv = J["bufferViews"][vi]
    print(f"  image{ii}: 旧偏移 {bv.get('byteOffset', 0)} → 新偏移 {newoff} · "
          f"{bv['byteLength']} → {len(data)} 字节")
    bv["byteOffset"] = newoff
    bv["byteLength"] = len(data)
while len(nb) % 4:                      # 🔴 BIN 块长度必须 4 字节对齐，否则 GLB 畸形
    nb.append(0)
J["buffers"][0]["byteLength"] = len(nb)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(nb))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(nb)) + b"BIN\x00" + bytes(nb))
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB · 缓冲区 {len(BIN)} → {len(nb)} 字节")

# 硬自检：所有图读回 + 尺寸不变
# 🔴 第一次写这段时，"参照图"是从**已被改过偏移的 J/BIN** 里读的 ⇒ 参照本身是垃圾，
#    于是自检报"image1/image2 读不回"，而真正读不回的其实是参照 —— **闸自己错了**。
#    正确做法：参照一律从**原始文件重新读**，不复用内存里被改过的对象。
raw0 = SRC.read_bytes()
jl0, = struct.unpack_from("<I", raw0, 12)
J0 = json.loads(raw0[20:20 + jl0].decode("utf-8"))
o0 = 20 + jl0 + ((-jl0) % 4)
bl0, = struct.unpack_from("<I", raw0, o0)
B0 = raw0[o0 + 8: o0 + 8 + bl0]


def ref_size(i):
    bv = J0["bufferViews"][J0["images"][i]["bufferView"]]
    oo = bv.get("byteOffset", 0)
    return Image.open(io.BytesIO(B0[oo:oo + bv["byteLength"]])).size


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
    try:
        pic = Image.open(io.BytesIO(B2[oo:oo + bv["byteLength"]]))
        pic.load()
    except Exception as e:
        bad.append(f"image{i} 读不回（{type(e).__name__}）")
        continue
    try:
        rs = ref_size(i)
        if pic.size != rs:
            bad.append(f"image{i} 尺寸变了 {rs}→{pic.size}")
    except Exception as e:
        bad.append(f"image{i} 参照读不回（{type(e).__name__}）")
# BIN 块长度必须 4 字节对齐（不对齐的 GLB 是畸形文件）
if len(nb) % 4:
    bad.append(f"BIN 块长度 {len(nb)} 不是 4 的倍数（GLB 畸形）")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print(f"✅ 自检通过（{len(J2['images'])} 张图读回 OK · 尺寸未变 · BIN {len(nb)} 字节 4 对齐）"
      f" · 对照 → {PREVIEW.name}")
