# -*- coding: utf-8 -*-
"""高模姿态测试（**分块 float32**，峰值内存约 13MB —— 这台机内存紧，必须分块）
抬 LeftArm 子树 45°，验证迁移来的权重在高模上形变正确；导出静态 GLB 供渲染验收。"""
import json
import math
import pathlib
import struct
import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = DH / "raw/rig/model-rigged-hi.glb"
OUT = DH / "raw/rig/model-rigged-hi-pose.glb"
CHUNK = 50000

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
del raw


def acc(i, comps, dt=np.float32):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), t, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps).astype(dt)


pr = J["meshes"][0]["primitives"][0]
P = acc(pr["attributes"]["POSITION"], 3)
JT = acc(pr["attributes"]["JOINTS_0"], 4, np.int32)
WT = acc(pr["attributes"]["WEIGHTS_0"], 4)
n = len(P)
print(f"高模 {n} 顶点 · 权重和 min/max {WT.sum(axis=1).min():.4f}/{WT.sum(axis=1).max():.4f}", flush=True)

# 世界坐标（迭代式 + 环保护；骨骼节点平移是相对父节点的，需逐级累加）
parent_of = {}
for k, nd in enumerate(J["nodes"]):
    for c in nd.get("children") or []:
        parent_of[c] = k
world = {}


def wpos(i):
    chain, cur, g = [], i, 0
    while cur is not None and cur not in world:
        chain.append(cur)
        cur = parent_of.get(cur)
        g += 1
        if g > 200:
            raise SystemExit("✗ 父链成环")
    w = world[cur] if cur is not None else np.zeros(3, np.float32)
    for node in reversed(chain):
        w = w + np.array(J["nodes"][node].get("translation", [0, 0, 0]), np.float32)
        world[node] = w
    return world[i]


idx = {nd.get("name"): i for i, nd in enumerate(J["nodes"])}
for nd in J["nodes"]:
    if (nd.get("name") or "").startswith("mixamorig:"):
        wpos(idx[nd["name"]])
arm = idx["mixamorig:LeftArm"]
head = world[arm].astype(np.float32)
sub = set()


def walk(i):
    sub.add(i)
    for c in J["nodes"][i].get("children") or []:
        walk(c)


walk(arm)
th = math.radians(45)
c_, s_ = math.cos(th), math.sin(th)
M = np.eye(4, dtype=np.float32)
M[:3, :3] = np.array([[1, 0, 0], [0, c_, -s_], [0, s_, c_]], np.float32)
Mi = np.eye(4, dtype=np.float32)
Mi[:3, 3] = -head
X = (M @ Mi).astype(np.float32)
X[:3, 3] += head
I4 = np.eye(4, dtype=np.float32)
Mv = np.stack([X if i in sub else I4 for i in range(len(J["nodes"]))]).astype(np.float32)   # (节点,4,4) 极小

Pp = np.empty_like(P)
maxd = 0.0
moved = 0
for s in range(0, n, CHUNK):
    e = min(n, s + CHUNK)
    M4 = Mv[JT[s:e]]                                              # (块,4,4,4) float32 ≈ 12.8MB
    v4 = np.concatenate([P[s:e], np.ones((e - s, 1), np.float32)], axis=1)
    d4 = np.einsum("vkij,vj->vki", M4, v4)
    res = np.einsum("vk,vki->vi", WT[s:e], d4)[:, :3]
    Pp[s:e] = res
    d = np.linalg.norm(res - P[s:e], axis=1)
    maxd = max(maxd, float(d.max()))
    moved += int((d > 1e-4).sum())
    del M4, v4, d4, res, d
print(f"抬左臂 45°：受影响顶点 {moved} · 最大位移 {maxd:.3f}", flush=True)

J2 = json.loads(json.dumps(J))
J2.pop("skins", None)
J2["nodes"][0].pop("skin", None)
pa = Pp.astype(np.float32)
while len(BIN) % 4:
    BIN.append(0)
_o = len(BIN)
BIN.extend(pa.tobytes())
J2["bufferViews"].append({"buffer": 0, "byteOffset": _o, "byteLength": pa.nbytes, "target": 34962})
J2["accessors"].append({"bufferView": len(J2["bufferViews"]) - 1, "componentType": 5126, "count": len(pa), "type": "VEC3",
                        "min": [float(x) for x in pa.min(axis=0)], "max": [float(x) for x in pa.max(axis=0)]})
p2 = J2["meshes"][0]["primitives"][0]
p2["attributes"]["POSITION"] = len(J2["accessors"]) - 1
p2["attributes"].pop("JOINTS_0", None)
p2["attributes"].pop("WEIGHTS_0", None)


def write_glb(path, jj, bb):
    body = bytearray(bb)
    while len(body) % 4:
        body.append(0)
    jj["buffers"][0]["byteLength"] = len(body)
    js = json.dumps(jj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                     + struct.pack("<I", len(js)) + b"JSON" + js
                     + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))


write_glb(OUT, J2, BIN)
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB", flush=True)
