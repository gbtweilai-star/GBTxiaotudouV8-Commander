# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""低模宝箱（带贴图 · 自包含 GLB）—— 零依赖程序化生成，不联网、不需要任何 API Key。

产物：assets/treasure-chest.glb（贴图以 PNG 嵌在 GLB 内，单文件自包含）
构成：箱体(木) + 半圆盖(木) + 三条铁箍 + 金锁扣 + 四只铁脚 ≈ 150–250 三角形
贴图：512×512 程序化图集 —— 木纹(左上) / 铁(右上) / 金(右下)，采样器 CLAMP 防串色
自证：写完立刻回读 GLB（JSON 块 + 访问器计数 + 图片字节），不合格就报错退出。
"""
import json
import math
import pathlib
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

WS = pathlib.Path(_GBT_ROOT)
OUT = WS / "assets/treasure-chest.glb"
ATLAS = WS / "assets/treasure-chest-atlas.png"

# ── ① 贴图图集（程序化）──────────────────────────────────────────────────
W = H = 512
img = Image.new("RGB", (W, H), (30, 30, 30))
px = np.asarray(img).copy()


def noise(shape, seed, lo=0.0, hi=1.0):
    rng = np.random.default_rng(seed)
    return rng.random(shape) * (hi - lo) + lo


# 木纹：左上 256²（3 条横板 + 木纹条纹）
wood = np.zeros((256, 256, 3), np.float32)
base = np.array([124, 78, 40], np.float32)
for y in range(256):
    plank = (y // 51)                       # 5 条板：用密度代替平铺，避免 UV 越区
    shade = 0.86 + 0.14 * ((plank * 37) % 7) / 7
    grain = 0.10 * np.sin(y * 0.9 + plank * 2.1) + 0.05 * np.sin(y * 0.23)
    wood[y, :, :] = base * shade * (1 + grain)[:, None] if hasattr(grain, "__len__") else base * shade
wood += (noise((256, 256, 1), 7, -12, 12))
for y in range(0, 256, 51):                 # 板缝
    wood[max(0, y - 2):y + 2, :, :] *= 0.45
wood = np.clip(wood, 0, 255).astype(np.uint8)
px[0:256, 0:256] = wood

# 铁：右上 256²（暗灰 + 麻点 + 铆钉）
iron = np.zeros((256, 256, 3), np.float32)
iron[:, :, :] = np.array([86, 90, 96], np.float32)
iron += noise((256, 256, 1), 11, -16, 16)
iron = np.clip(iron, 0, 255).astype(np.uint8)
px[0:256, 256:512] = iron

# 金：右下 256²（暖黄 + 竖条高光）
gold = np.zeros((256, 256, 3), np.float32)
gold[:, :, :] = np.array([196, 152, 62], np.float32)
gold += (28 * np.sin(np.arange(256) * 0.35))[None, :, None]
gold += noise((256, 256, 1), 13, -10, 10)
px[256:512, 256:512] = np.clip(gold, 0, 255).astype(np.uint8)

img = Image.fromarray(px, "RGB")
d = ImageDraw.Draw(img)
for cx, cy in [(286, 138), (400, 60)]:       # 铆钉（铁区）
    d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(148, 152, 158), outline=(54, 56, 60))
d.rectangle([8, 8, 248, 248], outline=(60, 38, 20))          # 木区框
d.rectangle([264, 8, 504, 248], outline=(40, 42, 46))
d.rectangle([264, 264, 504, 504], outline=(120, 92, 30))
img = img.filter(ImageFilter.GaussianBlur(0.4))
img.save(ATLAS)
png_bytes = ATLAS.read_bytes()

# 图集分区（UV 落点，带 2px 内缩防串色）
R_WOOD = (0.004, 0.004, 0.496, 0.496)        # (u0,v0,u1,v1) 注意 v 轴向下
R_IRON = (0.504, 0.004, 0.996, 0.496)
R_GOLD = (0.504, 0.504, 0.996, 0.996)


def uv_in(region, u, v):
    u0, v0, u1, v1 = region
    return (u0 + (u1 - u0) * u, v0 + (v1 - v0) * v)


# ── ② 几何（每个材质一组：位置/法线/UV/索引）─────────────────────────────
groups = {"wood": [], "iron": [], "gold": []}


def box(grp, x0, y0, z0, x1, y1, z1, region, tile=(1, 1)):
    """轴对齐盒子，6 面各 2 三角形，每面独立顶点（平面着色）。"""
    P, N, U, ii = [], [], [], []
    faces = [
        ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1)),    # +Z
        ((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (0, 0, -1)),   # -Z
        ((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (1, 0, 0)),    # +X
        ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (-1, 0, 0)),   # -X
        ((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (0, 1, 0)),    # +Y
        ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0)),   # -Y
    ]
    for a, b, c, dd, n in faces:
        base = len(P)
        uvs = [uv_in(region, 0, 0), uv_in(region, tile[0], 0), uv_in(region, tile[0], tile[1]), uv_in(region, 0, tile[1])]
        for pt, uv in zip((a, b, c, dd), uvs):
            P.append(pt)
            N.append(n)
            U.append(uv)
        ii += [base, base + 1, base + 2, base, base + 2, base + 3]
    groups[grp].append((P, N, U, ii))


def arc_band(grp, x0, x1, radius, y_center, segs, thick, region, vspan=0.5):
    """半圆盖上的弧形铁箍（单面 ribbon，材质双面渲染）。"""
    P, N, U, ii = [], [], [], []
    for s in range(segs):
        t0, t1 = math.pi * s / segs, math.pi * (s + 1) / segs
        y0, z0 = y_center + radius * math.sin(t0), radius * math.cos(t0)
        y1, z1 = y_center + radius * math.sin(t1), radius * math.cos(t1)
        base = len(P)
        for pt in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)):
            P.append(pt)
            n = (0, math.sin((t0 + t1) / 2), math.cos((t0 + t1) / 2))
            N.append(n)
            U.append(uv_in(region, 0 if len(P) % 2 else 0.5, 0))
        U[base + 0] = uv_in(region, 0, vspan * t0 / math.pi)
        U[base + 1] = uv_in(region, 1, vspan * t0 / math.pi)
        U[base + 2] = uv_in(region, 1, vspan * t1 / math.pi)
        U[base + 3] = uv_in(region, 0, vspan * t1 / math.pi)
        ii += [base, base + 1, base + 2, base, base + 2, base + 3]
    groups[grp].append((P, N, U, ii))


def half_cylinder(grp, x0, x1, radius, y_center, segs, region):
    """低模半圆盖：弧面 5 段 + 两端扇形封口。"""
    P, N, U, ii = [], [], [], []
    for s in range(segs):
        t0, t1 = math.pi * s / segs, math.pi * (s + 1) / segs
        y0, z0 = y_center + radius * math.sin(t0), radius * math.cos(t0)
        y1, z1 = y_center + radius * math.sin(t1), radius * math.cos(t1)
        base = len(P)
        P += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)]
        N += [(0, math.sin(t0), math.cos(t0))] * 2 + [(0, math.sin(t1), math.cos(t1))] * 2
        U += [uv_in(region, 0, vspan) for vspan in (t0 / math.pi, t0 / math.pi, t1 / math.pi, t1 / math.pi)]
        ii += [base, base + 1, base + 2, base, base + 2, base + 3]
    for x in (x0, x1):                                   # 两端扇形封口
        base = len(P)
        ctr = (x, y_center, 0.0)
        P.append(ctr)
        N.append((-1 if x == x0 else 1, 0, 0))
        U.append(uv_in(region, 0.5, 0.5))
        for s in range(segs):
            t0, t1 = math.pi * s / segs, math.pi * (s + 1) / segs
            P.append((x, y_center + radius * math.sin(t0), radius * math.cos(t0)))
            P.append((x, y_center + radius * math.sin(t1), radius * math.cos(t1)))
            N += [(-1 if x == x0 else 1, 0, 0)] * 2
            # 端面 UV 必须收在本区之内：用 0.35 半径 ⇒ 区内 0.15..0.85，绝不越过 u/v=0.5 的分界
            U += [uv_in(region, 0.5 + 0.35 * math.cos(t0), 0.5 - 0.35 * math.sin(t0)),
                  uv_in(region, 0.5 + 0.35 * math.cos(t1), 0.5 - 0.35 * math.sin(t1))]
            i0 = base + 1 + s * 2
            if x == x0:
                ii += [base, i0, i0 + 1]
            else:
                ii += [base, i0 + 1, i0]
    groups[grp].append((P, N, U, ii))


X0, X1 = -0.50, 0.50
Z0, Z1 = -0.33, 0.33
FY0, FY1 = 0.06, 0.62
box("wood", X0, FY0, Z0, X1, FY1, Z1, R_WOOD)                       # 箱体（不平铺：平铺会越区采到铁）
half_cylinder("wood", X0, X1, 0.34, FY1, 6, R_WOOD)                   # 半圆盖
for xc in (-0.32, 0.0, 0.32):                                          # 三条铁箍
    box("iron", xc - 0.035, FY0 - 0.01, Z0 - 0.012, xc + 0.035, FY1, Z1 + 0.012, R_IRON, tile=(1, 1))
    arc_band("iron", xc - 0.035, xc + 0.035, 0.352, FY1, 6, 0.02, R_IRON)
for fx in (X0 + 0.09, X1 - 0.09):                                      # 四只铁脚
    for fz in (Z0 + 0.075, Z1 - 0.075):
        box("iron", fx - 0.055, 0.0, fz - 0.055, fx + 0.055, FY0 + 0.002, fz + 0.055, R_IRON)
box("gold", -0.115, FY1 - 0.10, Z1 + 0.004, 0.115, FY1 + 0.045, Z1 + 0.034, R_GOLD)   # 锁扣
box("gold", -0.028, FY1 - 0.075, Z1 + 0.030, 0.028, FY1 - 0.020, Z1 + 0.052, R_GOLD)  # 锁扣凸起

# ── ③ 打包 GLB ───────────────────────────────────────────────────────────
buf = bytearray()
views, accessors, prims = [], [], []


def add_view(data: bytes, target=None):
    while len(buf) % 4:
        buf.append(0)
    off = len(buf)
    buf.extend(data)
    v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
    if target:
        v["target"] = target
    views.append(v)
    return len(views) - 1


def add_acc(arr, comp_type, type_str, target=None, minmax=False):
    b = arr.tobytes()
    vi = add_view(b, target)
    acc = {"bufferView": vi, "componentType": comp_type, "count": len(arr), "type": type_str}
    if minmax:
        acc["min"] = [float(x) for x in arr.min(axis=0)]
        acc["max"] = [float(x) for x in arr.max(axis=0)]
    accessors.append(acc)
    return len(accessors) - 1


MATS = [("wood", 0.0, 0.85), ("iron", 0.55, 0.50), ("gold", 0.60, 0.35)]   # (组名, 金属度, 粗糙度)
# 注：metallic 不能给 1.0 —— 没有环境贴图时全金属会渲染成黑色（金锁扣就栽在这）
for gi, (grp, metal, rough) in enumerate(MATS):
    P, N, U, ii = [], [], [], []
    for gp, gn, gu, gind in groups[grp]:
        off = len(P)
        P += gp
        N += gn
        U += gu
        ii += [i + off for i in gind]
    p = np.array(P, np.float32)
    n = np.array(N, np.float32)
    u = np.array(U, np.float32)
    idx = np.array(ii, np.uint32)
    ap = add_acc(p, 5126, "VEC3", 34962, True)
    an = add_acc(n, 5126, "VEC3", 34962)
    au = add_acc(u, 5126, "VEC2", 34962)
    ai = add_acc(idx, 5125, "SCALAR", 34963)
    prims.append({"attributes": {"POSITION": ap, "NORMAL": an, "TEXCOORD_0": au},
                  "indices": ai, "material": gi})

img_view = add_view(png_bytes)
gltf = {
    "asset": {"version": "2.0", "generator": "GBT小土豆V8 · 程序化低模宝箱"},
    "scene": 0,
    "scenes": [{"nodes": [0]}],
    "nodes": [{"mesh": 0, "name": "treasure_chest"}],
    "meshes": [{"name": "treasure_chest", "primitives": prims}],
    "materials": [{"name": m[0], "doubleSided": True,
                   "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                            "metallicFactor": m[1],
                                            "roughnessFactor": m[2]}} for m in MATS],
    "textures": [{"sampler": 0, "source": 0}],
    "images": [{"bufferView": img_view, "mimeType": "image/png", "name": "atlas"}],
    "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
    "accessors": accessors, "bufferViews": views,
    "buffers": [{"byteLength": len(buf)}],
}
js = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
while len(buf) % 4:
    buf.append(0)
glb = (b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(buf))
       + struct.pack("<I", len(js)) + b"JSON" + js
       + struct.pack("<I", len(buf)) + b"BIN\x00" + bytes(buf))
OUT.write_bytes(glb)

# ── ④ 自证：回读刚写的 GLB ───────────────────────────────────────────────
raw = OUT.read_bytes()
magic, ver, total = struct.unpack_from("<4sII", raw, 0)
jlen, jtype = struct.unpack_from("<I4s", raw, 12)
back = json.loads(raw[20:20 + jlen].decode("utf-8"))
tris = sum(len(back["accessors"][pr["indices"]]["count"] * [0]) // 3 for pr in back["meshes"][0]["primitives"])
verts = sum(back["accessors"][pr["attributes"]["POSITION"]]["count"] for pr in back["meshes"][0]["primitives"])
print(f"写出 {OUT} · {len(raw)/1024:.1f} KB · magic={magic.decode()} v{ver}")
print(f"  网格: {len(back['meshes'][0]['primitives'])} 个材质组 · 顶点 {verts} · 三角形 {tris}")
print(f"  贴图: {len(back['images'])} 张（bufferView 内嵌 · {len(png_bytes)/1024:.1f} KB）· 采样器 CLAMP")
print(f"  抽屉自证: accessors={len(back['accessors'])} · bufferViews={len(back['bufferViews'])} · materials={[m['name'] for m in back['materials']]}")
assert magic == b"glTF" and back["asset"]["version"] == "2.0" and tris < 500, "自证不通过"
print("  自证通过 ✓")
