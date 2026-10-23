# -*- coding: utf-8 -*-
"""资产级「去油光 + 金属度归零 + T 区/唇部反光差异」

为什么必须做（Owner 用本仓 AI 味禁令逐条对照后指出）：
  ❌「金属度非零的皮肤 —— 会发灰、失血色」
  ❌「全脸均匀油光 —— 真人只有 T 区/唇部反光」
  我此前只在**取景器材质**里设了 `metalness=0`、`specularIntensity` 等 —— 那是**渲染端**的事。
  **资产自带的 metallicRoughness 贴图**里，B 通道（金属度）均值仍是 **0.127**、G 通道（粗糙度）
  全脸一个值。换任何别的渲染器（VRM 运行时 / Unity / UE / 别的 viewer）就**原样露馅**。
  所以这一刀必须落在**贴图**上，不是在取景器里。

做法（判据全部从数据来，不写死脸的位置）：
  ① 逐顶点判「是不是皮肤」：按 UV 采样底色 —— 暖色且亮；
  ② 逐顶点判「是不是唇」：**红得多**（R 与 G 的差显著大于皮肤基线）且亮 —— 唇的反照率比率与皮肤不同；
  ③ 逐顶点判「是不是 T 区」：**近中轴 + 正面**（|x−中轴| 小、z 靠前），且高度在面部带内；
  ④ 粗糙度目标：唇 0.34（最亮）· T 区 0.44 · 一般皮肤 0.60 · 非皮肤（头发等）保留原值并夹到 [0.20,0.60]；
  ⑤ **金属度一律 0**（头模上没有金属件；头发也不该是金属）；
  ⑥ 逐顶点值**栅格化**到 UV（泼点 + 最近邻补洞 + 轻模糊），低频效果足够。

安全性：新图**追加到缓冲区末尾**、指向它的 bufferView 改到新位置，**其他偏移一律不动**
（这是本项目验证过最不易错的写法；"就地替换 + 平移偏移"我翻过两次车）。

用法：python tools/codex-scripts/skin-specular.py <件.glb> <输出.glb>
退出码：0 = 写出且自检通过；1 = 自检不过；2 = 前置问题。
"""
import io
import json
import pathlib
import struct
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-talk.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/avatar-specl.glb"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), t, a["count"] * comps,
                         bv.get("byteOffset", 0)).reshape(a["count"], comps)


def img_arr(idx):
    im = J["images"][idx]
    bv = J["bufferViews"][im["bufferView"]]
    o = bv.get("byteOffset", 0)
    return np.asarray(Image.open(io.BytesIO(bytes(BIN[o:o + bv["byteLength"]]))).convert("RGB")).astype(np.float64)


prs = J["meshes"][0]["primitives"]
_sel = None
for _a in sys.argv:
    if _a.startswith("--prim="):
        _sel = int(_a.split("=", 1)[1])
# 缝合件有 2 个 primitive：0=身体 1=头。不指定则取顶点最多的那个。
hi = _sel if _sel is not None else max(
    range(len(prs)), key=lambda k: J["accessors"][prs[k]["attributes"]["POSITION"]]["count"])
print(f"选择 primitive #{hi}（共 {len(prs)} 个）")
pr = prs[hi]
mat = J["materials"][pr["material"]]
pbr = mat["pbrMetallicRoughness"]
bci = J["textures"][pbr["baseColorTexture"]["index"]]["source"]
mri = None
if "metallicRoughnessTexture" in pbr:
    mri = J["textures"][pbr["metallicRoughnessTexture"]["index"]]["source"]
    print(f"该 primitive 已有 MR 贴图 image{mri}")
else:
    # 🔴 实测发现：**头的材质根本没有 MR 贴图** —— 缝合时我只搬了底色与法线。
    #    于是头是「金属度 0（好）+ **粗糙度全场均匀 0.55**（坏）」——
    #    这正是 Owner 指出的「**全脸均匀油光**」的直接来源。
    #    所以这里要**新建一张 MR**：G 放 T 区/唇部的粗糙度差异，B 恒 0。
    print("该 primitive **没有** MR 贴图 ⇒ 本步新建一张（G=粗糙度差异 · B=金属度 0）")
P = acc(pr["attributes"]["POSITION"], 3).astype(np.float64)
UV = acc(pr["attributes"]["TEXCOORD_0"], 2).astype(np.float64)
bc = img_arr(bci)
if mri is not None:
    bvm = J["bufferViews"][J["images"][mri]["bufferView"]]
    om = bvm.get("byteOffset", 0)
    mr_im = Image.open(io.BytesIO(bytes(BIN[om:om + bvm["byteLength"]]))).convert("RGB")
else:
    mr_im = Image.new("RGB", (2048, 2048), (255, 140, 0))     # 占位：稍后整张重写
print(f"头部 primitive #{hi} · 顶点 {len(P)} · 底色 image{bci} {bc.shape[1]}² · "
      f"MR {'image%d %s' % (mri, mr_im.size) if mri is not None else '（缺 ⇒ 新建）'}")

uu = np.clip((UV[:, 0] % 1.0) * (bc.shape[1] - 1), 0, bc.shape[1] - 1).astype(int)
vv = np.clip((UV[:, 1] % 1.0) * (bc.shape[0] - 1), 0, bc.shape[0] - 1).astype(int)
C = bc[vv, uu]
lum = C[:, 0] * 0.299 + C[:, 1] * 0.587 + C[:, 2] * 0.114
rg = C[:, 0] - C[:, 1]                                   # 红-绿差：唇显著更大
skin = (C[:, 0] > C[:, 1] + 8) & (C[:, 1] >= C[:, 2]) & (C[:, 0] > 150)
print(f"皮肤顶点 {int(skin.sum())}（{skin.mean()*100:.1f}%）· 红-绿差 中位 {np.median(rg[skin]):.1f}")

# ② 唇：红-绿差显著高于皮肤基线，且够亮（唇有血色、不是暗影）
base_rg = float(np.median(rg[skin])) if skin.any() else 20.0
lips = skin & (rg > base_rg + 14) & (lum > 100)
# ③ T 区：近中轴 + 正面（用"皮肤顶点沿 x 的分位"当脸宽基线，不写死坐标）
face_x = P[skin & (P[:, 2] > 0)]
half = float(np.percentile(np.abs(face_x[:, 0]), 90)) if len(face_x) > 50 else 0.05
cx = float(np.median(face_x[:, 0])) if len(face_x) > 50 else 0.0
tz = skin & (np.abs(P[:, 0] - cx) < 0.35 * half) & (P[:, 2] > np.percentile(P[:, 2], 55))
print(f"唇顶点 {int(lips.sum())} · T 区顶点 {int(tz.sum())}（脸半宽基线 {half:.4f} · 中轴 {cx:+.4f}）")

# ④ 粗糙度目标
R = np.full(len(P), np.nan)
R[skin] = 0.60
R[tz & skin] = 0.44
R[lips] = 0.34
# 非皮肤（头发等）：保留原 MR 的粗糙度，夹到 [0.20,0.60]
mr0 = np.asarray(mr_im).astype(np.float64)
mru = np.clip((UV[:, 0] % 1.0) * (mr0.shape[1] - 1), 0, mr0.shape[1] - 1).astype(int)
mrv = np.clip((UV[:, 1] % 1.0) * (mr0.shape[0] - 1), 0, mr0.shape[0] - 1).astype(int)
orig_r = mr0[mrv, mru, 1] / 255.0
R[np.isnan(R)] = np.clip(orig_r[np.isnan(R)], 0.20, 0.60)
print(f"粗糙度目标：唇 0.34 / T 区 0.44 / 一般皮肤 0.60 · 均值 {R.mean():.3f}"
      f"（原贴图均值 {orig_r.mean():.3f}）")

# ⑤ 栅格化到 UV：泼点 → 最近邻补洞 → 轻模糊
S = mr0.shape[0]
gu = np.clip((UV[:, 0] % 1.0) * (S - 1), 0, S - 1).astype(int)
gv = np.clip((UV[:, 1] % 1.0) * (S - 1), 0, S - 1).astype(int)
splat = np.full((S, S), np.nan)
splat[gv, gu] = R
mask = np.isnan(splat)
if mask.all():
    print("🔴 栅格化全空 ⇒ 停止")
    raise SystemExit(2)
idx = distance_transform_edt(mask, return_distances=False, return_indices=True)
filled = splat[tuple(idx)]
filled = gaussian_filter(filled, 2.0, mode="wrap")
print(f"栅格化：{S}² · 补洞 {int(mask.sum())} 纹素（{mask.mean()*100:.1f}%）· σ=2.0 模糊")

mr_new = mr0.copy()
mr_new[:, :, 1] = np.clip(filled * 255.0, 0, 255)     # G = 粗糙度
mr_new[:, :, 2] = 0.0                                 # B = 金属度 **一律 0**
buf = io.BytesIO()
Image.fromarray(mr_new.astype(np.uint8)).save(buf, format="PNG", optimize=True)
newbytes = buf.getvalue()
print(f"新 MR 贴图：{len(newbytes)/1024:.0f} KB · 金属度 → 0（原均值 {mr0[:, :, 2].mean()/255:.3f}）"
      f" · 粗糙度均值 {filled.mean():.3f}")

# ⑥ 追加到缓冲区末尾（其他偏移一律不动）
while len(BIN) % 4:
    BIN.append(0)
newoff = len(BIN)
BIN.extend(newbytes)
if mri is not None:
    bv = J["bufferViews"][J["images"][mri]["bufferView"]]
    print(f"  image{mri} bufferView：偏移 {bv.get('byteOffset', 0)} → {newoff} · "
          f"{bv['byteLength']} → {len(newbytes)} 字节")
    bv["byteOffset"] = newoff
    bv["byteLength"] = len(newbytes)
    J["images"][mri]["mimeType"] = "image/png"
    mri_final = mri
else:
    J["bufferViews"].append({"buffer": 0, "byteOffset": newoff, "byteLength": len(newbytes)})
    J["images"].append({"bufferView": len(J["bufferViews"]) - 1, "mimeType": "image/png"})
    mri_final = len(J["images"]) - 1
    J["textures"].append({"sampler": 0, "source": mri_final})
    # 有贴图后：metalness = metallicFactor × B(=0) ⇒ 设 1.0；roughness = roughnessFactor × G ⇒ 设 1.0
    pbr["metallicRoughnessTexture"] = {"index": len(J["textures"]) - 1}
    pbr["metallicFactor"] = 1.0
    pbr["roughnessFactor"] = 1.0
    print(f"  新建 image{mri_final}（偏移 {newoff} · {len(newbytes)} 字节）并挂到材质，"
          f"metallicFactor/roughnessFactor 设为 1.0（由贴图接管）")
while len(BIN) % 4:
    BIN.append(0)
J["buffers"][0]["byteLength"] = len(BIN)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(BIN))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(BIN)) + b"BIN\x00" + bytes(BIN))

# 自检：读回，实测 MR 贴图的金属度均值与粗糙度分布
raw2 = OUT.read_bytes()
jl2, = struct.unpack_from("<I", raw2, 12)
J2 = json.loads(raw2[20:20 + jl2].decode("utf-8"))
o2 = 20 + jl2 + ((-jl2) % 4)
bl2, = struct.unpack_from("<I", raw2, o2)
B2 = raw2[o2 + 8: o2 + 8 + bl2]
bad = []
bv2 = J2["bufferViews"][J2["images"][mri_final]["bufferView"]]
m2 = np.asarray(Image.open(io.BytesIO(B2[bv2.get("byteOffset", 0):bv2.get("byteOffset", 0) + bv2["byteLength"]])).convert("RGB")).astype(np.float64)
met = m2[:, :, 2].mean() / 255.0
rough = m2[:, :, 1] / 255.0
print(f"自检读数：金属度均值 **{met:.4f}**（要求 ≈0）· 粗糙度 {rough.min():.3f}~{rough.max():.3f} 均值 {rough.mean():.3f}")
if met > 0.02:
    bad.append(f"金属度仍 {met:.4f} > 0.02")
if len(BIN) % 4:
    bad.append("BIN 未 4 字节对齐")
for i, im in enumerate(J2["images"]):
    bv3 = J2["bufferViews"][im["bufferView"]]
    try:
        Image.open(io.BytesIO(B2[bv3.get("byteOffset", 0):bv3.get("byteOffset", 0) + bv3["byteLength"]])).load()
    except Exception as e:
        bad.append(f"image{i} 读不回（{type(e).__name__}）")
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print("✅ 自检通过（金属度归零 · 全部贴图可读 · BIN 对齐）")
