# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""把低模骨架的蒙皮权重**迁移到高模**（同一次生成、同一坐标系 ⇒ 精确迁移，不是投影猜）
理由：低模用来做实时/网页（能动能省），高模用来出图/主控台形象（好看）。两边共用同一套 22 骨骨架。

方法：对低模顶点建空间网格 → 每个高模顶点取邻近低模顶点的 k=3 最近 → 反距离加权平均权重 → 归一
输出：raw/rig/model-rigged-hi.glb（高模 + 骨架 + skin）
"""
import json
import pathlib
import struct
import numpy as np

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
LOW = DH / "raw/rig/model-rigged.glb"               # 已绑骨（含 JOINTS_0/WEIGHTS_0）—— 注意不是绑骨前的转换件
HIGH = DH / "raw/phase2a/model.glb"                  # 高保真 T-pose（762k）
OUT = DH / "raw/rig/model-rigged-hi.glb"
SKEL = DH / "raw/rig/skeleton.json"


def load(path):
    raw = path.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, bytearray(raw[off + 8: off + 8 + bl])


def acc(J, BIN, i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), dt, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps).astype(np.float64)


JL, BL = load(LOW)
JH, BH = load(HIGH)
pl = JL["meshes"][0]["primitives"][0]
ph = JH["meshes"][0]["primitives"][0]
Pl = acc(JL, BL, pl["attributes"]["POSITION"], 3)
Jl = acc(JL, BL, pl["attributes"]["JOINTS_0"], 4).astype(int)
Wl = acc(JL, BL, pl["attributes"]["WEIGHTS_0"], 4)
Ph = acc(JH, BH, ph["attributes"]["POSITION"], 3)
print(f"低模 {len(Pl)} 顶点（已绑骨）· 高模 {len(Ph)} 顶点（待迁移）")
print(f"  bbox 低模 x[{Pl[:, 0].min():.3f},{Pl[:, 0].max():.3f}] y[{Pl[:, 1].min():.3f},{Pl[:, 1].max():.3f}] z[{Pl[:, 2].min():.3f},{Pl[:, 2].max():.3f}]")
print(f"  bbox 高模 x[{Ph[:, 0].min():.3f},{Ph[:, 0].max():.3f}] y[{Ph[:, 1].min():.3f},{Ph[:, 1].max():.3f}] z[{Ph[:, 2].min():.3f},{Ph[:, 2].max():.3f}]")
span = np.linalg.norm([Ph[:, i].max() - Ph[:, i].min() for i in range(3)]) / np.linalg.norm([Pl[:, i].max() - Pl[:, i].min() for i in range(3)])
print(f"  尺度比 高/低 = {span:.4f}（≈1 说明同一坐标系，可直接迁移）")

# 空间网格：低模顶点分桶
cell = 0.02
lo = Pl.min(axis=0)
grid = {}
for i, v in enumerate(Pl):
    key = tuple(((v - lo) / cell).astype(int))
    grid.setdefault(key, []).append(i)
print(f"  低模分桶: cell={cell} · 桶数 {len(grid)}")

JH4 = np.zeros((len(Ph), 4), np.int64)
WH4 = np.zeros((len(Ph), 4), np.float64)
miss = 0
for i, v in enumerate(Ph):
    base = ((v - lo) / cell).astype(int)
    cand = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                cand += grid.get((base[0] + dx, base[1] + dy, base[2] + dz), [])
    if not cand:
        miss += 1
        continue
    cand = np.array(cand)
    d = np.linalg.norm(Pl[cand] - v, axis=1)
    k = cand[np.argsort(d)[:3]]
    w = 1.0 / np.power(np.linalg.norm(Pl[k] - v, axis=1) + 1e-5, 2)
    w /= w.sum()
    acc_w = {}
    for j, wj in zip(k, w):
        for b, wb in zip(Jl[j], Wl[j]):
            if wb > 0:
                acc_w[int(b)] = acc_w.get(int(b), 0.0) + wj * wb
    items = sorted(acc_w.items(), key=lambda kv: -kv[1])[:4]
    s = sum(x[1] for x in items)
    for t, (b, wb) in enumerate(items):
        JH4[i, t] = b
        WH4[i, t] = wb / s
print(f"  迁移完成：未命中 {miss} 顶点 · 权重和 min/max = {WH4.sum(axis=1).min():.4f}/{WH4.sum(axis=1).max():.4f} · 平均活跃骨 {(WH4 > 0.01).sum(axis=1).mean():.2f}")

# 注入 skin 到高模


def add_view(BIN, arr, target=None):
    while len(BIN) % 4:
        BIN.append(0)
    o = len(BIN)
    BIN.extend(arr.tobytes())
    v = {"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes}
    if target:
        v["target"] = target
    JH["bufferViews"].append(v)
    return len(JH["bufferViews"]) - 1


jv = add_view(BH, JH4.astype(np.uint16), 34962)
wv = add_view(BH, WH4.astype(np.float32), 34962)
JH["accessors"].append({"bufferView": jv, "componentType": 5123, "count": len(JH4), "type": "VEC4"})
JH["accessors"].append({"bufferView": wv, "componentType": 5126, "count": len(WH4), "type": "VEC4"})
ph["attributes"]["JOINTS_0"] = len(JH["accessors"]) - 2
ph["attributes"]["WEIGHTS_0"] = len(JH["accessors"]) - 1

# 复用低模的骨骼节点/skin（两点同坐标系 ⇒ 骨骼与 IBM 可直接复用）
bone_ids = [i for i, n in enumerate(JL["nodes"]) if (n.get("name") or "").startswith("mixamorig:")]
low_base = min(bone_ids)                      # 真实基准索引：不能用 len 差算（骨骼后面还跟着 Armature 节点）
base = len(JH["nodes"])
for i in bone_ids:
    n = JL["nodes"][i]
    nn = {"name": n["name"], "translation": n["translation"]}
    if "children" in n:
        nn["children"] = [c - low_base + base for c in n["children"]]
    JH["nodes"].append(nn)
print(f"  骨骼节点: 低模 {len(bone_ids)} 个（基准索引 {low_base}）→ 高模基准 {base}")
sk = JL["skins"][0]
ibm_acc = sk["inverseBindMatrices"]
# 复制 IBM 数据到高模 BIN
a = JL["accessors"][ibm_acc]
bv = JL["bufferViews"][a["bufferView"]]
ibm = np.frombuffer(bytes(BL), np.float32, a["count"] * 16, bv.get("byteOffset", 0)).reshape(-1, 16)
iv = add_view(BH, ibm)
JH["accessors"].append({"bufferView": iv, "componentType": 5126, "count": len(ibm), "type": "MAT4"})
JH["skins"] = [{"name": "GBT_AutoRig", "joints": [base + i for i in range(len(bone_ids))], "inverseBindMatrices": len(JH["accessors"]) - 1, "skeleton": base + 0}]
JH["nodes"][0]["skin"] = 0
JH["nodes"].append({"name": "Armature", "children": [base + 0]})
JH["scenes"][0]["nodes"] = [0, len(JH["nodes"]) - 1]


# ── 收尾：按 PARENT 表重建骨骼层级（不信任复制来的 children 索引），并断言无自环 ──
SK = json.loads(SKEL.read_text(encoding="utf-8"))
PAR = SK["parent"]
n2i = {n.get("name"): i for i, n in enumerate(JH["nodes"]) if (n.get("name") or "").startswith("mixamorig:")}
assert len(n2i) == len(PAR), f"骨骼节点数不符：{len(n2i)} vs {len(PAR)}"
for name in PAR:
    node = n2i["mixamorig:" + name]
    kids = [n2i["mixamorig:" + c] for c, par in PAR.items() if par == name]
    if kids:
        JH["nodes"][node]["children"] = kids
    else:
        JH["nodes"][node].pop("children", None)
# 断言：无自环、父链可终止
parent_of = {}
for k, nd in enumerate(JH["nodes"]):
    for c in nd.get("children") or []:
        assert c != k, f"节点 {k} 自环"
        parent_of[c] = k
for j in JH["skins"][0]["joints"]:
    seen, cur = set(), j
    while cur is not None:
        assert cur not in seen, f"关节 {j} 父链成环于 {cur}"
        seen.add(cur)
        cur = parent_of.get(cur)
roots = [n2i["mixamorig:Hips"]]
assert JH["nodes"][-1]["children"] == roots, "Armature 未正确指向 Hips"
print(f"  层级重建完成：{len(n2i)} 骨骼 · 无自环 · 无环 ✓ · 根 = Hips({roots[0]})")


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


write_glb(OUT, JH, BH)
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · 关节 {len(bone_ids)} · skin {'有' if JH.get('skins') else '无'}")
