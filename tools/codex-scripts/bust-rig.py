# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""胸像（头肩）简化骨架 + 微动：SpineBase→Spine1→Neck→Head→HeadTop
要点（全部沿用已验证口径）：
  · 颈位**由几何实测**（沿臂轴横截宽度最小处），不猜比例
  · 权重：到骨段距离取最近 4 段 → (1/d)^3 归一 → 三角邻接平滑 3 次
  · 骨骼平移**相对父节点**（绝对坐标会累加成错姿势 —— 踩过）
  · 微动 clip：呼吸(脊柱)+头部摆动/点头，周期整除时长 ⇒ 循环闭合
输出：raw/portrait-bust-rigged.glb（含 idle 微动）"""
import json
import math
import pathlib
import struct
import numpy as np

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
import sys  # noqa: E402
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/portrait-bust.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/portrait-bust-rigged.glb"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
del raw


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), dt, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps).astype(np.float64)


pr = J["meshes"][0]["primitives"][0]
P = acc(pr["attributes"]["POSITION"], 3)
IDX = acc(pr["indices"], 1).astype(np.int64).reshape(-1, 3)
ext = P.max(axis=0) - P.min(axis=0)
arm = 0 if ext[0] >= ext[2] else 2
y_top, y_bot = P[:, 1].max(), P[:, 1].min()
H = y_top - y_bot
print(f"胸像 {len(P)} 顶点 · 高 {H:.3f} · 臂轴 {'XYZ'[arm]}")

# ① 颈位：沿高度扫横截宽度，取最小处（在 0.30–0.62 区间内）
best = None
for f in np.arange(0.30, 0.63, 0.01):
    y = y_top - f * H
    band = P[np.abs(P[:, 1] - y) < 0.012 * H]
    if len(band) < 20:
        continue
    w = float(band[:, arm].max() - band[:, arm].min())
    if best is None or w < best[0]:
        best = (w, f, y)
neck_f = best[1] if best else 0.45


def cen_at(f, tol=0.02):
    y = y_top - f * H
    band = P[np.abs(P[:, 1] - y) < tol * H]
    return band.mean(axis=0) if len(band) else P.mean(axis=0)


J3 = {
    "SpineBase": cen_at(0.94), "Spine1": cen_at(min(0.92, neck_f + 0.22)),
    "Neck": cen_at(neck_f), "Head": cen_at(max(0.06, neck_f - 0.16)),
    "HeadTop": np.array([P[:, 0].mean(), y_top, P[:, 2].mean()]),
}
PARENT = {"SpineBase": None, "Spine1": "SpineBase", "Neck": "Spine1", "Head": "Neck", "HeadTop": "Head"}
names = list(PARENT)
print(f"颈位实测 f={neck_f:.2f}（横截最窄 {best[0]:.3f}）· 关节 {len(names)}")

# ② 权重


def seg_d(v, a, b):
    ab = b - a
    t = np.clip(((v - a) @ ab) / max(1e-12, ab @ ab), 0, 1)
    return np.linalg.norm(v - (a + t * ab))


tail = {n: (np.mean([J3[c] for c in names if PARENT[c] == n], axis=0) if any(PARENT[c] == n for c in names)
            else J3[n] + np.array([0, 0.05 * H, 0])) for n in names}
D = np.stack([[seg_d(v, J3[n], tail[n]) for v in P] for n in names], axis=1)
order = np.argsort(D, axis=1)[:, :4]
W = np.zeros_like(D)
rows = np.arange(len(P))[:, None]
W[rows, order] = 1.0 / np.power(D[rows, order] + 1e-4, 3)
W /= W.sum(axis=1, keepdims=True)
nb = [[] for _ in range(len(P))]
for a, b, c in IDX:
    nb[a] += [b, c]
    nb[b] += [a, c]
    nb[c] += [a, b]
nb = [np.array(sorted(set(x))) for x in nb]
for _ in range(3):
    W2 = W.copy()
    for i in range(len(P)):
        if len(nb[i]):
            W2[i] = 0.5 * W[i] + 0.5 * W[nb[i]].mean(axis=0)
    W = W2 / W2.sum(axis=1, keepdims=True)
top4 = np.argsort(W, axis=1)[:, ::-1][:, :4]
w4 = np.take_along_axis(W, top4, axis=1)
w4 /= w4.sum(axis=1, keepdims=True)
print(f"权重：和 {w4.sum(axis=1).min():.4f}/{w4.sum(axis=1).max():.4f} · 活跃骨 {(w4 > 0.01).sum(axis=1).mean():.2f}")


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


jv = add_view(top4.astype(np.uint16), 34962)
wv = add_view(w4.astype(np.float32), 34962)
J["accessors"].append({"bufferView": jv, "componentType": 5123, "count": len(top4), "type": "VEC4"})
J["accessors"].append({"bufferView": wv, "componentType": 5126, "count": len(w4), "type": "VEC4"})
pr["attributes"]["JOINTS_0"] = len(J["accessors"]) - 2
pr["attributes"]["WEIGHTS_0"] = len(J["accessors"]) - 1

# ③ 骨骼节点（相对父节点）+ skin
base = len(J["nodes"])
idx = {}
for n in names:
    par = PARENT[n]
    rel = J3[n] - (J3[par] if par else 0.0)
    J["nodes"].append({"name": "mixamorig:" + n, "translation": [float(x) for x in rel]})
    idx[n] = base + len(idx)
for n in names:
    kids = [idx[c] for c in names if PARENT[c] == n]
    if kids:
        J["nodes"][idx[n]]["children"] = kids
ibm = np.array([np.linalg.inv(np.eye(4)) for _ in names], np.float32)   # 占位，下面按世界坐标重算
world = {}


def wpos(n):
    w = np.array(J["nodes"][idx[n]]["translation"], np.float64)
    return w if PARENT[n] is None else wpos(PARENT[n]) + w


for n in names:
    world[n] = wpos(n)
ibm = []
for n in names:
    m = np.eye(4, dtype=np.float32)
    m[:3, 3] = -world[n]
    ibm.append(m.T.flatten())
ibm = np.array(ibm, np.float32)
iv = add_view(ibm)
J["accessors"].append({"bufferView": iv, "componentType": 5126, "count": len(ibm), "type": "MAT4"})
J["skins"] = [{"name": "GBT_BustRig", "joints": [idx[n] for n in names],
               "inverseBindMatrices": len(J["accessors"]) - 1, "skeleton": idx["SpineBase"]}]
J["nodes"][0]["skin"] = 0
J["nodes"].append({"name": "Armature", "children": [idx["SpineBase"]]})
J["scenes"][0]["nodes"] = [0, len(J["nodes"]) - 1]

# ④ idle 微动（呼吸 + 头部摆动/点头；周期整除时长 ⇒ 循环闭合）


def quat(rx, ry, rz):
    hx, hy, hz = map(math.radians, (rx / 2, ry / 2, rz / 2))
    cx, sx = math.cos(hx), math.sin(hx)
    cy, sy = math.cos(hy), math.sin(hy)
    cz, sz = math.cos(hz), math.sin(hz)
    return np.array([sx*cy*cz + cx*sy*sz, cx*sy*cz - sx*cy*sz, cx*cy*sz + sx*sy*cz, cx*cy*cz - sx*sy*sz], np.float32)


LEN, FPS = 8.0, 12
times = np.arange(0, LEN + 1e-6, 1 / FPS, dtype=np.float32)
per = {n: [] for n in names}
for t in times:
    br = math.sin(2 * math.pi * t / 4.0)
    sw = math.sin(2 * math.pi * t / 8.0)
    per["SpineBase"].append(quat(0, 0.8 * sw, 0))
    per["Spine1"].append(quat(-1.0 * br, 0, 0.5 * br))
    per["Neck"].append(quat(0.6 * br, -0.5 * sw, 0))
    per["Head"].append(quat(1.0 * br, 3.0 * sw, 0.5 * math.sin(2 * math.pi * t / 4.0)))
    per["HeadTop"].append(quat(0, 0, 0))
samplers, channels = [], []
while len(BIN) % 4:
    BIN.append(0)
o = len(BIN)
BIN.extend(times.tobytes())
J["bufferViews"].append({"buffer": 0, "byteOffset": o, "byteLength": times.nbytes})
J["accessors"].append({"bufferView": len(J["bufferViews"]) - 1, "componentType": 5126, "count": len(times),
                       "type": "SCALAR", "min": [float(times.min())], "max": [float(times.max())]})
tin = len(J["accessors"]) - 1
for n in names:
    arr = np.array(per[n], np.float32)
    while len(BIN) % 4:
        BIN.append(0)
    o = len(BIN)
    BIN.extend(arr.tobytes())
    J["bufferViews"].append({"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes})
    J["accessors"].append({"bufferView": len(J["bufferViews"]) - 1, "componentType": 5126, "count": len(arr), "type": "VEC4"})
    samplers.append({"input": tin, "output": len(J["accessors"]) - 1, "interpolation": "LINEAR"})
    channels.append({"sampler": len(samplers) - 1, "target": {"node": idx[n], "path": "rotation"}})
J["animations"] = [{"name": "idle", "channels": channels, "samplers": samplers}]
closes = [float(np.abs(np.array(v[0]) - np.array(v[-1])).max()) for v in per.values()]
print(f"idle: {LEN:.1f}s · 通道 {len(channels)} · 循环闭合误差 {max(closes):.5f}（应≈0）")

body = bytearray(BIN)
while len(body) % 4:
    body.append(0)
J["buffers"][0]["byteLength"] = len(body)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · 关节 {len(names)} · 动画 1 段")
