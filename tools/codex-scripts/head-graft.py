# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""把头接进全身（head graft）：拿**审美合格的头**（胸像）替换身体模型的头部。
做法（游戏里常用的"分离头部"法，不做焊接）：
  ① 身体：删掉"颈线以上"的三角形（顶点保留，无害）⇒ 身体不再有旧头
  ② 胸像：只取"其颈线以上"的三角形，重编号成独立网格
  ③ 对齐：按**头部包围盒**求统一缩放 + 平移（两个模型同轴：高度 Y、正面 +X、臂轴 Z）
  ④ 共用**身体那一套 22 骨**：新头按到骨段距离权重（只用 Head/Neck/HeadTop）
  ⑤ 头用胸像自己的 3 张贴图（新材质），身体保持 4K 材质
输出：raw/rig/model-rigged-4k-graft.glb"""
import json
import pathlib
import struct
import numpy as np

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
BODY = DH / "raw/rig/model-rigged-4k.glb"
HEAD = DH / "raw/portrait-bust.glb"
OUT = DH / "raw/rig/model-rigged-4k-graft.glb"


def load(p):
    raw = p.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, bytearray(raw[off + 8: off + 8 + bl])


def acc(J, BIN, i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), dt, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps)


JB, BB = load(BODY)
pr_b = JB["meshes"][0]["primitives"][0]
PB = acc(JB, BB, pr_b["attributes"]["POSITION"], 3)
IB = acc(JB, BB, pr_b["indices"], 1).astype(np.int64).reshape(-1, 3)
yb_top = PB[:, 1].max()
# 颈线（口径 v3 · 确定性）：T-pose 下横向宽度会量到**双臂**（实测"最宽"=0.983=臂展），
# 宽度启发式一律不可用 ⇒ 用解剖比例：颈线 ≈ 头顶下 0.125×身高（成人头高约 1/7.5~1/8）
H_body = PB[:, 1].max() - PB[:, 1].min()
neck_b = yb_top - 0.125 * H_body
_band_b = PB[np.abs(PB[:, 1] - neck_b) < 0.006 * H_body]
neck_c_b = _band_b.mean(axis=0) if len(_band_b) else PB[PB[:, 1] > neck_b].mean(axis=0)
print(f"身体：颈线 y={neck_b:.3f}（头顶下 12.5%×{H_body:.3f}）· 颈截面中心 {np.round(neck_c_b, 3)}")

keep_tri = ~(PB[IB[:, 0], 1] > neck_b) | ~(PB[IB[:, 1], 1] > neck_b) | ~(PB[IB[:, 2], 1] > neck_b)
IB2 = IB[keep_tri]
print(f"身体：颈线 y={neck_b:.3f} · 三角形 {len(IB)} → {len(IB2)}（删掉旧头 {len(IB)-len(IB2)}）")

JH, BH = load(HEAD)
pr_h = JH["meshes"][0]["primitives"][0]
PH = acc(JH, BH, pr_h["attributes"]["POSITION"], 3).astype(np.float64)
NH = acc(JH, BH, pr_h["attributes"]["NORMAL"], 3)
UH = acc(JH, BH, pr_h["attributes"]["TEXCOORD_0"], 2)
IH = acc(JH, BH, pr_h["indices"], 1).astype(np.int64).reshape(-1, 3)
yh_top, yh_bot = PH[:, 1].max(), PH[:, 1].min()
# 胸像下巴线（v5 · 确定性）：头肩胸像里**头约占上方 40%**（启发式在此失效：
# 头发+衣领会让"颈部横截"反而比头顶宽 —— 实测 v4 把头顶当成了颈）
Hh = yh_top - yh_bot
neck_h = yh_top - 0.40 * Hh
neck_h_f = 0.40
print(f"胸像：下巴线 y={neck_h:.3f}（头顶下 40%×{Hh:.3f}）")
keep_h = (PH[IH[:, 0], 1] > neck_h) & (PH[IH[:, 1], 1] > neck_h) & (PH[IH[:, 2], 1] > neck_h)
IH2 = IH[keep_h]
used = np.unique(IH2)
print(f"胸像：颈线 f={neck_h_f:.2f} y={neck_h:.3f} · 头部三角形 {len(IH2)} · 用顶点 {len(used)}")

# 对齐（v8 · 定稿）：缩放按**头高**（切口解剖位置不同 ⇒ 半径不可比，v7 教训）；
# 水平按颈截面中心；底部**下沉 0.02 进领口**把接缝藏起来
_bb = PB[np.abs(PB[:, 1] - neck_b) < 0.006 * H_body]
neck_c_b = _bb.mean(axis=0) if len(_bb) else PB[PB[:, 1] > neck_b].mean(axis=0)
_hb = PH[np.abs(PH[:, 1] - neck_h) < 0.012 * (yh_top - yh_bot)]
neck_c_h = _hb.mean(axis=0) if len(_hb) else PH[PH[:, 1] > neck_h].mean(axis=0)
head_h_b = yb_top - neck_b
head_h_h = yh_top - neck_h
s = (head_h_b / max(1e-9, head_h_h)) * 0.965         # ×0.965：人像标准 1/7.5~1/8 头身；v8 的 0.93 偏小 7%
PH2 = (PH[used] - neck_c_h) * s + neck_c_b
PH2[:, 1] += (neck_b - PH2[:, 1].min()) - 0.007      # 下沉仅 0.007：领口上方露短颈（核心口径：可见颈段≈0.02-0.03×H；颈几何仍伸进领口内遮缝）
print(f"对齐 v8：头高 身体 {head_h_b:.3f}/胸像 {head_h_h:.3f} ⇒ 缩放 {s:.4f} · "
      f"头 y {PH2[:, 1].min():.3f}~{PH2[:, 1].max():.3f}（身体顶 {yb_top:.3f}）· 底沉 0.02")

# 新头权重（只用 Head/Neck/HeadTop；骨骼世界坐标取自身体 rig）
names = [JB["nodes"][j].get("name", "") for j in JB["skins"][0]["joints"]]
idx_of = {n: i for i, n in enumerate(names)}
world = {}
parent_of = {}
for k, n in enumerate(JB["nodes"]):
    for c in n.get("children") or []:
        parent_of[c] = k
for j in JB["skins"][0]["joints"]:
    chain, cur, g = [], j, 0
    while cur is not None and cur not in world:
        chain.append(cur)
        cur = parent_of.get(cur)
        g += 1
        if g > 200:
            raise SystemExit("父链成环")
    w = world[cur] if cur is not None else np.zeros(3, np.float64)
    for node in reversed(chain):
        w = w + np.array(JB["nodes"][node].get("translation", [0, 0, 0]), np.float64)
        world[node] = w
jid = {n: JB["skins"][0]["joints"][idx_of[n]] for n in names if n.startswith("mixamorig:")}
head_names = [n for n in ("mixamorig:HeadTop", "mixamorig:Head", "mixamorig:Neck") if n in jid]
hp = {n: world[jid[n]] for n in head_names}


def seg_d(v, a, b):
    ab = b - a
    t = np.clip(((v - a) @ ab) / max(1e-12, ab @ ab), 0, 1)
    return np.linalg.norm(v - (a + t * ab))


D = np.stack([[seg_d(v, hp[n], hp[n] + np.array([0, 0.05, 0])) for v in PH2] for n in head_names], axis=1)
order = np.argsort(D, axis=1)
W = np.zeros_like(D)
rows = np.arange(len(PH2))[:, None]
W[rows, order] = 1.0 / np.power(D[rows, order] + 1e-4, 3)
W /= W.sum(axis=1, keepdims=True)
J4 = np.zeros((len(PH2), 4), np.uint16)
W4 = np.zeros((len(PH2), 4), np.float32)
for k in range(min(4, len(head_names))):
    J4[:, k] = [idx_of[head_names[i]] for i in order[:, k]]
    W4[:, k] = W[rows[:, 0], order[:, k]]
W4 /= W4.sum(axis=1, keepdims=True)
print(f"新头权重：和 {W4.sum(axis=1).min():.4f}/{W4.sum(axis=1).max():.4f} · 骨 {head_names}")

# 组装：改身体索引 + 追加头的 primitive（含胸像 3 张贴图作为新材质）


def add_view(BIN, arr, target=None):
    while len(BIN) % 4:
        BIN.append(0)
    o = len(BIN)
    BIN.extend(arr.tobytes())
    v = {"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes}
    if target:
        v["target"] = target
    JB["bufferViews"].append(v)
    return len(JB["bufferViews"]) - 1


nv = add_view(BB, IB2.astype(np.uint32).reshape(-1), 34963)
JB["accessors"].append({"bufferView": nv, "componentType": 5125, "count": IB2.size, "type": "SCALAR"})
pr_b["indices"] = len(JB["accessors"]) - 1

# 头贴图（胸像的 3 张）搬进来


def head_img(slot):
    m = JH["materials"][0]
    pbr = m.get("pbrMetallicRoughness", {})
    if slot == "base":
        return JH["textures"][pbr["baseColorTexture"]["index"]]["source"]
    if slot == "norm":
        return JH["textures"][m["normalTexture"]["index"]]["source"]
    return JH["textures"][pbr["metallicRoughnessTexture"]["index"]]["source"]


img_new = {}
for slot in ("base", "norm", "mr"):
    si = head_img(slot)
    bv = JH["bufferViews"][JH["images"][si]["bufferView"]]
    data = bytes(BH[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]])
    while len(BB) % 4:
        BB.append(0)
    o = len(BB)
    BB.extend(data)
    JB["bufferViews"].append({"buffer": 0, "byteOffset": o, "byteLength": len(data)})
    JB["images"].append({"bufferView": len(JB["bufferViews"]) - 1, "mimeType": JH["images"][si].get("mimeType", "image/jpeg")})
    JB["textures"].append({"sampler": 0, "source": len(JB["images"]) - 1})
    img_new[slot] = len(JB["textures"]) - 1
JB["materials"].append({"name": "head_graft", "doubleSided": False,
                        "pbrMetallicRoughness": {"baseColorTexture": {"index": img_new["base"]},
                                                 "metallicRoughnessTexture": {"index": img_new["mr"]},
                                                 "metallicFactor": 0, "roughnessFactor": 0.7},
                        "normalTexture": {"index": img_new["norm"]}})
mat_head = len(JB["materials"]) - 1

ap = add_view(BB, PH2.astype(np.float32), 34962)
an = add_view(BB, NH[used].astype(np.float32), 34962)
au = add_view(BB, UH[used].astype(np.float32), 34962)
aj = add_view(BB, J4, 34962)
aw = add_view(BB, W4, 34962)


def push_acc(bv_, ctype, cnt, typ, mm=None):
    a = {"bufferView": bv_, "componentType": ctype, "count": cnt, "type": typ}
    if mm:
        a.update(mm)
    JB["accessors"].append(a)
    return len(JB["accessors"]) - 1


a_p = push_acc(ap, 5126, len(PH2), "VEC3", {"min": [float(x) for x in PH2.min(axis=0)], "max": [float(x) for x in PH2.max(axis=0)]})
a_n = push_acc(an, 5126, len(PH2), "VEC3")
a_u = push_acc(au, 5126, len(PH2), "VEC2")
a_j = push_acc(aj, 5123, len(J4), "VEC4")
a_w = push_acc(aw, 5126, len(W4), "VEC4")
remap = -np.ones(len(PH), np.int64)
remap[used] = np.arange(len(used))
IH3 = remap[IH2].astype(np.uint32).reshape(-1)
ai = add_view(BB, IH3, 34963)
a_i = push_acc(ai, 5125, IH3.size, "SCALAR")
JB["meshes"][0]["primitives"].append({"attributes": {"POSITION": a_p, "NORMAL": a_n, "TEXCOORD_0": a_u,
                                                     "JOINTS_0": a_j, "WEIGHTS_0": a_w},
                                      "indices": a_i, "material": mat_head})

body = bytearray(BB)
while len(body) % 4:
    body.append(0)
JB["buffers"][0]["byteLength"] = len(body)
js = json.dumps(JB, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · primitive {len(JB['meshes'][0]['primitives'])} 个（身体 + 新头）")
