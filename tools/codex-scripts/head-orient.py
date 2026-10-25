# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""专用头模 · 定向归一（用**鼻尖**定前后，不是脚趾）

为什么不能直接用 avatar-orient.py：
  那件靠"**脚掌相对踝部的水平偏移**"判正面（脚趾朝前）。头模是**头+胸像**，
  底部是锁骨/胸，**没有脚** ⇒ 它的前后判据在头模上必然失效（会判出个随机方向）。
  头的正前方向在**鼻尖**：上半脸的皮肤里，沿深度轴凸出最远的那个点。

判据（全部是读数）：
  · 肩轴：肩高带的水平跨度大者（与 avatar-orient.py 同口径）；
  · 正面：**鼻尖**——在面部高度带上，沿候选深度轴取皮肤顶点，凸出最远者为鼻；
    正前 = 从头部中轴指向鼻尖的水平方向；
  · 自检：旋转后要求「肩轴 = X」且「鼻尖沿 +Z」。

用法：python tools/codex-scripts/head-orient.py <in.glb> <out.glb>
退出码：0 = 归一且自检过；1 = 自检不过；2 = 前置问题。
"""
import io
import json
import pathlib
import struct
import sys

import numpy as np
from PIL import Image

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
    DH / "raw/head-hi/tripo-out/owner-脸-特写-png-convert-81c54599/model.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/head-hi/head-facing.glb"
if not SRC.is_file():
    print(f"🔴 输入不在盘上：{SRC}")
    raise SystemExit(2)

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
pr = J["meshes"][0]["primitives"][0]


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), t, a["count"] * comps,
                         bv.get("byteOffset", 0)).reshape(a["count"], comps)


P = acc(pr["attributes"]["POSITION"], 3).astype(np.float64)
UV = acc(pr["attributes"]["TEXCOORD_0"], 2).astype(np.float64)
# 认皮肤：底色图**按材质索引取**（不能按尺寸猜 —— 这个模型三张图都是 4096²）
mat = J["materials"][0]
bci = J["textures"][mat["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]
bv = J["bufferViews"][J["images"][bci]["bufferView"]]
o = bv.get("byteOffset", 0)
bc = np.asarray(Image.open(io.BytesIO(bytes(BIN[o:o + bv["byteLength"]]))).convert("RGB")).astype(np.float64)
uu = np.clip((UV[:, 0] % 1.0) * (bc.shape[1] - 1), 0, bc.shape[1] - 1).astype(int)
vv = np.clip((UV[:, 1] % 1.0) * (bc.shape[0] - 1), 0, bc.shape[0] - 1).astype(int)
C = bc[vv, uu]
# 🔴 皮肤掩码收紧到 R>150：上一版用 R>110，**棕发也满足**「暖色且够亮」⇒
#    判据把**后脑的头发**当成了鼻尖，整个头转了 180°（渲出来是后脑勺）。
#    这是本项目第二次栽在"皮肤/头发颜色判据"上（第一次在 add-eyes.py 量脸宽），
#    所以这次不是调阈值，而是**换判据**（见下面的脊宽法）。
skin = (C[:, 0] > C[:, 1] + 8) & (C[:, 1] >= C[:, 2]) & (C[:, 0] > 150)
print(f"顶点 {len(P)} · 皮肤 {int(skin.sum())}（{skin.mean()*100:.1f}%，判据 R>150 且 R>G+8）")

y0, y1 = P[:, 1].min(), P[:, 1].max()
H = y1 - y0
ext = P.max(axis=0) - P.min(axis=0)
axis_arm = 0 if ext[0] >= ext[2] else 2
axis_dep = 2 if axis_arm == 0 else 0
# 肩带（头模的"肩"在很下面：胸像底部）
sh_band = P[np.abs(P[:, 1] - (y0 + 0.10 * H)) < 0.03 * H]
print(f"肩带 x跨 {sh_band[:, 0].max()-sh_band[:, 0].min():.4f} · "
      f"z跨 {sh_band[:, 2].max()-sh_band[:, 2].min():.4f} ⇒ 肩轴 {'X' if axis_arm == 0 else 'Z'}")


def nose_dir(PP, tag):
    """鼻尖方向 —— 用**脊宽**判，不用"谁凸得更远"。

    🔴 为什么要换判据（上一版失败的直接原因）：
      上一版取"面部带里沿深度轴最凸出的点"当鼻尖。**后脑的头发比鼻尖凸得更远**，
      于是判反了 180°。而且当时正反两向读数只差 0.0008，**判据本来就是险胜**。
      换判据：在极端薄片（沿候选方向最外 3% 高度）里量**沿肩轴的宽度** ——
        · 鼻尖是**窄脊**（宽约 0.02–0.05 H）
        · 后脑是一**大片**（宽约 0.3+ H）
      两者差一个量级，比"谁更远"稳得多。
    并且加**不确定闸**：两个候选方向的脊宽若相差不到 20%，判『不确定』并停，不硬选。
    """
    band = skin & (PP[:, 1] > y1 - 0.45 * H) & (PP[:, 1] < y1 - 0.18 * H)
    if band.sum() < 200:
        return None, None, None
    P_ = PP[band]
    cands = []
    for d in (0, 2):
        for s in (1.0, -1.0):
            proj = P_[:, d] * s
            e = float(np.percentile(proj, 99.5))
            slab = P_[proj > e - 0.03 * H]
            if len(slab) < 5:
                continue
            width = float(slab[:, axis_arm].max() - slab[:, axis_arm].min())
            cands.append((d, s, width, e))
    cands.sort(key=lambda t: t[2])
    for d, s, w, e in cands:
        print(f"[{tag}] 候选 轴={'XZ'[d//2]} 向={'+' if s > 0 else '-'} · 脊宽 {w:.4f} · 外沿 {e:+.4f}")
    if not cands:
        return None, None, None
    # 🔴 选法修正：**不能取"全局最窄"** —— 那样会选到与深度无关的那根轴
    #    （实测 Z 轴两侧都"窄"：0.0359 / 0.0388，但它不是前后轴）。
    #    正确口径：**同一根轴上比正反**。后脑是一大片、鼻尖是窄脊 ⇒ 比值大的那根轴
    #    才是深度轴；该轴上**较窄的那一向**就是正面。
    #    实测 X 轴 0.0540 / 0.2721 = 比值 5.0（深度轴）；Z 轴 0.0359 / 0.0388 = 1.08。
    per_axis = {}
    for d, s, w, e in cands:
        per_axis.setdefault(d, []).append((s, w, e))
    scored = []
    for d, lst in per_axis.items():
        if len(lst) < 2:
            continue
        lst.sort(key=lambda t: t[1])
        ratio = lst[1][1] / max(lst[0][1], 1e-9)
        scored.append((ratio, d, lst))
    if not scored:
        return None, None, None
    scored.sort(reverse=True)
    ratio, d, lst = scored[0]
    s, w, e = lst[0]                      # 较窄的一向 = 正面
    print(f"[{tag}] 深度轴判定：{'XZ'[d//2]} 轴 正反脊宽 "
          f"{lst[0][1]:.4f}(向{'+' if lst[0][0] > 0 else '-'}) / "
          f"{lst[1][1]:.4f}(向{'+' if lst[1][0] > 0 else '-'}) · 比值 {ratio:.2f}"
          f"（次选轴比值 {scored[1][0]:.2f}）" if len(scored) > 1 else "")
    vec = np.zeros(3)
    vec[d] = s
    return d, vec, (w, lst[1][1], ratio)


dep_before, vec_before, widths = nose_dir(P, "归一前")
if vec_before is None:
    print("🔴 定不出鼻尖方向")
    raise SystemExit(2)
# 不确定闸：深度轴的比值必须显著高于次选轴，否则判「不确定」停手
if widths[1] is not None and widths[2] < 2.0:
    print(f"🔴 **判据不确定**：深度轴比值仅 {widths[2]:.2f}（要求 ≥2.0）"
          f" ⇒ 按上一轮教训**停下来**，不硬选一边")
    raise SystemExit(1)
print(f"[归一前] 鼻尖朝 {'+' if vec_before[dep_before] > 0 else '-'}{'XZ'[dep_before//2]}"
      f" · 深度轴比值 {widths[2]:.2f}")
axis_dep = dep_before


def rot_y(v, deg):
    t = np.radians(deg)
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])
    return v @ R.T


# 目标：肩轴 = X、鼻尖 = +Z。先把"鼻尖所在轴"转到 Z；若它本来就是 Z，只需把符号摆正。
deg = 0.0
if axis_dep == 0:
    deg = -90.0 * float(vec_before[0])      # +X → +Z 用 −90；−X → +Z 用 +90
deg = deg % 360.0
if deg > 180:
    deg -= 360
print(f"[规划] 绕 Y 旋转 {deg:+.0f}°")
P1 = rot_y(P, deg)

# 自检（用旋转后的点重算）
sh1 = P1[np.abs(P1[:, 1] - (y0 + 0.10 * H)) < 0.03 * H]
ok_axis = (sh1[:, 0].max() - sh1[:, 0].min()) > (sh1[:, 2].max() - sh1[:, 2].min())
band1 = P1[skin & (P1[:, 1] > y1 - 0.45 * H) & (P1[:, 1] < y1 - 0.18 * H)]
hi_z = float(np.percentile(band1[:, 2], 99.9))
lo_z = float(np.percentile(band1[:, 2], 0.1))
ok_nose = abs(hi_z) > abs(lo_z)
print(f"[自检] 肩轴=X : {'✅' if ok_axis else '🔴'} · 鼻尖沿+Z : "
      f"{'✅' if ok_nose else '🔴'}（z hi={hi_z:+.4f} lo={lo_z:+.4f}）")
if not (ok_axis and ok_nose):
    print("🔴 两条自检未同时通过 ⇒ 不写盘")
    raise SystemExit(1)

Pf = rot_y(P, deg).astype(np.float32)
Nf = rot_y(acc(pr["attributes"]["NORMAL"], 3).astype(np.float64), deg).astype(np.float32)


def add_view(arr, target=None):
    while len(BIN) % 4:
        BIN.append(0)
    oo = len(BIN)
    BIN.extend(arr.tobytes())
    v = {"buffer": 0, "byteOffset": oo, "byteLength": arr.nbytes}
    if target:
        v["target"] = target
    J["bufferViews"].append(v)
    return len(J["bufferViews"]) - 1


pv = add_view(Pf, 34962)
J["accessors"].append({"bufferView": pv, "componentType": 5126, "count": len(Pf), "type": "VEC3",
                       "min": [float(x) for x in Pf.min(axis=0)],
                       "max": [float(x) for x in Pf.max(axis=0)]})
pr["attributes"]["POSITION"] = len(J["accessors"]) - 1
nv = add_view(Nf, 34962)
J["accessors"].append({"bufferView": nv, "componentType": 5126, "count": len(Nf), "type": "VEC3"})
pr["attributes"]["NORMAL"] = len(J["accessors"]) - 1

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
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB · 旋转 {deg:+.0f}°")
