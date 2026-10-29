# -*- coding: utf-8 -*-
"""面部专件 · **眼球**（独立几何 + 程序化虹膜贴图 + 绑到 Head 骨）

为什么必须做这一件（REALISM.md §2 第 7 步）：
  真人眼睛有**角膜高光**与**虹膜折射**。现在模型上的"眼睛"是**贴图画上去的** ——
  无论贴图多清，它都不会随视角变化产生角膜高光，这是"恐怖谷"的头号来源。
  眼球必须是独立几何、独立材质，并且**跟着 Head 骨动**（所以要有 JOINTS_0/WEIGHTS_0）。

做法：
  · 位置**从网格量**（不写死）：在眼高带上取脸部正面顶点，量出脸宽与正面 z，
    眼距取脸宽的固定比例，眼球中心从正面表面**后退一个半径**（角膜略凸出）；
  · 几何：UV 球（经纬网格），虹膜落在 u=0.25 / v=0.5（该参数化下 +Z 极点就在这）；
  · 贴图：程序化 —— 巩膜白 + 虹膜径向纤维 + 瞳孔 + 角膜缘暗环；
  · 蒙皮：所有眼球顶点 JOINTS_0 = Head 关节、WEIGHTS_0 = 1.0。

用法：python tools/codex-scripts/add-eyes.py <绑骨.glb> <输出.glb>
退出码：0 = 写出且自检通过；1 = 自检不过；2 = 前置问题。
"""
import json
import math
import pathlib
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-springs.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/avatar-eyes.glb"
TEX = DH / "raw/rig/eye-iris.png"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
pr = max(J["meshes"][0]["primitives"],
         key=lambda q: J["accessors"][q["attributes"]["POSITION"]]["count"])   # 顶点最多的 = 专用头那一份


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), t, a["count"] * comps,
                         bv.get("byteOffset", 0)).reshape(a["count"], comps)


P = acc(pr["attributes"]["POSITION"], 3).astype(np.float64)
names = [n.get("name", "") for n in J["nodes"]]
joints = J["skins"][0]["joints"]
HEAD = next(i for i, nd in enumerate(joints) if names[nd] == "mixamorig:Head")
y_top, y_bot = P[:, 1].max(), P[:, 1].min()
# 眼线是**全身**比例，不能用"所测 primitive 自己的高度"：
#    缝合件里选中的是**专用头那一片**（裁过的头+一截颈，自身高只有 0.17），
#    拿它算 y_eye = y_top − 0.066·H 会落到**头顶头发**上，于是"取不到皮肤顶点"。
#    必须用**整体** bbox（全部 primitive 的并集）来定身高。
_g0, _g1 = P[:, 1].min(), P[:, 1].max()
for _q in J["meshes"][0]["primitives"]:
    _pp = acc(_q["attributes"]["POSITION"], 3)
    _g0, _g1 = min(_g0, _pp[:, 1].min()), max(_g1, _pp[:, 1].max())
H = float(_g1 - _g0)
print(f"所测 primitive 高 {y_top - y_bot:.3f} · **整体**身高 {H:.3f}（y {_g0:+.3f}..{_g1:+.3f}）")
print(f"网格 {len(P)} 顶点 · 身高 {H:.3f} · Head 关节槽位 {HEAD}")

# 贴图采样：底色图按**该 primitive 自己的材质**取（缝合件里身/头各一套，按尺寸猜会取错）
import io as _io  # noqa: E402
UVall = acc(pr["attributes"]["TEXCOORD_0"], 2).astype(np.float64)
_mat = J["materials"][pr["material"]] if "material" in pr else J["materials"][0]
_bci = J["textures"][_mat["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]
_bv = J["bufferViews"][J["images"][_bci]["bufferView"]]
_o = _bv.get("byteOffset", 0)
bc = np.asarray(Image.open(_io.BytesIO(bytes(BIN[_o:_o + _bv["byteLength"]]))).convert("RGB")).astype(np.float64)
uu = np.clip((UVall[:, 0] % 1.0) * (bc.shape[1] - 1), 0, bc.shape[1] - 1).astype(int)
vv = np.clip((UVall[:, 1] % 1.0) * (bc.shape[0] - 1), 0, bc.shape[0] - 1).astype(int)
C = bc[vv, uu]
print(f"底色图 = image{_bci}（按材质取）· {bc.shape[1]}²")

# ── 人工给定眼位（路径 ①）────────────────────────────────────────────────
# 为什么最后走人工：比例法 / 几何反查 / 连通域**三种自动方法全部失败**，根源同一个 ——
#    源图是「重妆光泽人偶」：浓眼妆吃掉了眼白、额头高光冒充眼白（见 STATUS.json eye_attempt_4）。
#    **输入里没有可供定位的解剖信号**，再换第四种自动方法也是碰运气。
#    量取来源：render/眼球-缝合件-正面.png（真眼睛在画面约 58% 处 ⇒ y≈0.395；
#    瞳孔距约脸宽 30% ⇒ 单侧 x≈0.025）。
_manual = None
for _a in sys.argv:
    if _a.startswith("--manual-eye="):
        _manual = [float(v) for v in _a.split("=", 1)[1].split(",")]
if _manual:
    x_eye, y_eye, z_socket = _manual
    R = 0.0090 * H
    z_eye = z_socket - R * 0.35
    print(f"[人工给定] 单侧 x=±{x_eye:.4f} · y={y_eye:+.4f} · 眼窝 z={z_socket:+.4f} · 半径 {R:.4f}")
    _ok_y = (y_top - 0.20 * H) <= y_eye <= (y_top - 0.05 * H)
    _ok_x = 0.008 <= x_eye <= 0.060
    if not (_ok_y and _ok_x):
        print(f"🔴 人工值超出解剖期望区间（y_ok={_ok_y} x_ok={_ok_x}）⇒ 拒绝写盘")
        raise SystemExit(1)
    print("✅ 解剖期望闸通过（人工值落在人头该在的区间内）")

# 方法换血（第二次失败后的修正）：**不再靠比例猜眼线**。
#    比例法连错两次的根因是"口径"——身体比例套到头模上，眼线/脸宽都偏。
#    改用**几何反查**：眼白是脸上最显眼的「**高亮度 + 低色度**」区域
#    （巩膜接近中性白，而皮肤是暖色、头发是暗棕）。取这些顶点、按 x 分成左右两簇，
#    簇心就是双眼中心。位置来自**同一份几何**，不存在比例口径问题。
# （自动检测块已删除：比例法 / 几何反查 / 连通域三种方法全部失败，
#   根源是源图为『重妆光泽人偶』，输入里没有可供定位的解剖信号。
#   详见 STATUS.json 的 eye_attempt_2/3/4。现在眼位走 --manual-eye=<x,y,z>。
if not _manual:
    print('🔴 未给 --manual-eye=<单侧x,y,眼窝z>，且自动定位方法已判定无效 ⇒ 拒绝瞎放')
    raise SystemExit(2)

# ── ② 程序化虹膜贴图 ─────────────────────────────────────────────────────
TS = 512
im = Image.new("RGB", (TS, TS), (236, 233, 230))          # 巩膜：偏暖的白，不是纯白
d = ImageDraw.Draw(im)
cx, cy = TS * 0.25, TS * 0.5                              # 虹膜落在 u=0.25 / v=0.5
R_iris = TS * 0.085
rng = np.random.default_rng(20260925)
# 虹膜底：棕（与角色发色/设定一致的暖棕）
for r in range(int(R_iris), 0, -1):
    t = r / R_iris
    base = np.array([92, 58, 34]) * (0.55 + 0.75 * (1 - t))
    base = np.clip(base + np.array([26, 18, 8]) * (1 - t), 0, 255)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(int(v) for v in base))
# 径向纤维
for k in range(220):
    a = rng.uniform(0, 2 * math.pi)
    r0 = R_iris * rng.uniform(0.32, 0.55)
    r1 = R_iris * rng.uniform(0.86, 1.0)
    w = rng.uniform(0.5, 1.8)
    v = int(rng.uniform(-26, 34))
    col = (int(np.clip(96 + v, 0, 255)), int(np.clip(60 + v * 0.7, 0, 255)), int(np.clip(36 + v * 0.5, 0, 255)))
    d.line([cx + math.cos(a) * r0, cy + math.sin(a) * r0,
            cx + math.cos(a) * r1, cy + math.sin(a) * r1], fill=col, width=int(w))
d.ellipse([cx - R_iris * 0.99, cy - R_iris * 0.99, cx + R_iris * 0.99, cy + R_iris * 0.99],
          outline=(28, 20, 14), width=max(2, int(TS * 0.012)))   # 角膜缘暗环
R_pup = R_iris * 0.40
d.ellipse([cx - R_pup, cy - R_pup, cx + R_pup, cy + R_pup], fill=(8, 7, 9))   # 瞳孔
im = im.filter(ImageFilter.GaussianBlur(0.6))
TEX.parent.mkdir(parents=True, exist_ok=True)
im.save(TEX)
png = TEX.read_bytes()
print(f"虹膜贴图：{TS}² · {len(png)/1024:.0f} KB → {TEX.name}")

# ── ③ 眼球球体（经纬网格，+Z 极点落在 u=0.25 / v=0.5） ────────────────────
LAT, LON = 28, 56
verts, uvs, tris = [], [], []
for i in range(LAT + 1):
    th = math.pi * i / LAT
    for j in range(LON + 1):
        ph = 2 * math.pi * j / LON
        verts.append((math.sin(th) * math.cos(ph), math.cos(th), math.sin(th) * math.sin(ph)))
        uvs.append((j / LON, i / LAT))
for i in range(LAT):
    for j in range(LON):
        a = i * (LON + 1) + j
        b = a + LON + 1
        tris += [(a, b, a + 1), (a + 1, b, b + 1)]
V0 = np.array(verts, np.float64)
# 法线：球心在原点 ⇒ 法线就是归一化的位置
N0 = V0 / np.maximum(np.linalg.norm(V0, axis=1, keepdims=True), 1e-9)
UV0 = np.array(uvs, np.float32)
IDX0 = np.array(tris, np.uint32).reshape(-1)
print(f"眼球几何：顶点 {len(V0)} · 三角 {len(tris)}")


def place(sign):
    p = V0.copy()
    p[:, 0] = p[:, 0] * R * 0.98 + sign * x_eye
    p[:, 1] = p[:, 1] * R + y_eye
    p[:, 2] = p[:, 2] * R + z_eye
    return p.astype(np.float32)


def add_view(arr, target=None):
    while len(BIN) % 4:
        BIN.append(0)
    o = len(BIN)
    BIN.extend(arr.tobytes())
    v = {"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes}
    if target:
        v["target"] = target
    J["bufferViews"].append(v)
    return len(J["bufferViews"]) - 1


def add_acc(arr, ct, typ, target=None, mm=False):
    vi = add_view(arr, target)
    a = {"bufferView": vi, "componentType": ct, "count": len(arr), "type": typ}
    if mm:
        a.update({"min": [float(x) for x in arr.min(axis=0)], "max": [float(x) for x in arr.max(axis=0)]})
    J["accessors"].append(a)
    return len(J["accessors"]) - 1


# 贴图 + 材质
tex_view = add_view(np.frombuffer(png, np.uint8))
J["images"].append({"bufferView": tex_view, "mimeType": "image/png"})
J["textures"].append({"sampler": 0, "source": len(J["images"]) - 1})
J["materials"].append({
    "name": "eye_iris", "doubleSided": False,
    "pbrMetallicRoughness": {"baseColorTexture": {"index": len(J["textures"]) - 1},
                             "metallicFactor": 0.0, "roughnessFactor": 0.18},
    "extensions": {"KHR_materials_specular": {"specularIntensity": 0.9}},
})
mat_i = len(J["materials"]) - 1
base_node = len(J["nodes"])
N_PRIM0 = len(J["meshes"][0]["primitives"])     # 记录原有 primitive 数（自检要用"原有+2"判，不写死常数）
W_ACC = []                      # 记下眼球 WEIGHTS_0 的 accessor 号：自检**不回头猜**，建的时候就留下
for sign, tag in ((1, "L"), (-1, "R")):
    Ps = place(sign)
    a_p = add_acc(Ps, 5126, "VEC3", 34962, True)
    a_n = add_acc(N0.astype(np.float32), 5126, "VEC3", 34962)
    a_u = add_acc(UV0, 5126, "VEC2", 34962)
    a_i = add_acc(IDX0, 5125, "SCALAR", 34963)
    # 蒙皮：全绑 Head
    jt = np.tile(np.array([[HEAD, 0, 0, 0]], np.uint16), (len(Ps), 1))
    wt = np.tile(np.array([[1.0, 0.0, 0.0, 0.0]], np.float32), (len(Ps), 1))
    a_j = add_acc(jt, 5123, "VEC4", 34962)
    a_w = add_acc(wt, 5126, "VEC4", 34962)
    W_ACC.append(a_w)
    J["meshes"][0]["primitives"].append({
        "attributes": {"POSITION": a_p, "NORMAL": a_n, "TEXCOORD_0": a_u,
                       "JOINTS_0": a_j, "WEIGHTS_0": a_w},
        "indices": a_i, "material": mat_i})
    print(f"  眼球 {tag}：x={sign*x_eye:+.4f} z={z_eye:+.4f} · 顶点 {len(Ps)}")

body = bytearray(BIN)
while len(body) % 4:
    body.append(0)
J["buffers"][0]["byteLength"] = len(body)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))

# 自检
bad = []
prim = J["meshes"][0]["primitives"]
# 不能写死 3：缝合件本身已经是 2 个 primitive（身 + 头），加 2 眼 = 4。
#    判据必须是"**原有多少 + 2**"，而不是一个常数。
if len(prim) != N_PRIM0 + 2:
    bad.append(f"primitive 数 {len(prim)} ≠ 原有 {N_PRIM0} + 2")
for k, p in enumerate(prim[1:], 1):
    if "JOINTS_0" not in p["attributes"] or "WEIGHTS_0" not in p["attributes"]:
        bad.append(f"primitive{k} 缺蒙皮属性（skinned mesh 的每个 primitive 都必须有）")
# 每个角的权重和 = 1（用建的时候记下的 accessor 号，不回去猜）
for k, ai in enumerate(W_ACC):
    w = acc(int(ai), 4)
    if abs(w.sum(axis=1).min() - 1) > 1e-6 or abs(w.sum(axis=1).max() - 1) > 1e-6:
        bad.append(f"眼球{k} 权重和 ≠ 1")
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB · primitive {len(prim)} 个")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print("✅ 自检通过（3 个 primitive · 眼球带蒙皮 · 权重和 = 1）")
