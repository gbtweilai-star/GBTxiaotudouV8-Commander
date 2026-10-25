# -*- coding: utf-8 -*-
"""轻量级门限检查（只看节点/层级，不遍历顶点，秒级）——大网格（76 万顶点）用这个。
含**环保护**：层级坏掉时报错而不是死循环。"""
import json
import math
import pathlib
import struct
import sys
import numpy as np

p = pathlib.Path(sys.argv[1])
raw = p.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
print(f"{p.name} · {p.stat().st_size/1024/1024:.2f} MB")
sk = (J.get("skins") or [None])[0]
if not sk:
    print("  ✗ 没有 skin")
    raise SystemExit(1)
joints = sk["joints"]
names = [J["nodes"][j].get("name", "") for j in joints]
print(f"  [1] 关节 {len(joints)} 个（门限 ≥20 ⇒ {'✅' if len(joints) >= 20 else '❌'}）")

parent_of = {}
for k, n in enumerate(J["nodes"]):
    for c in n.get("children") or []:
        if c == k:
            raise SystemExit(f"  ✗ 节点 {k} 自环 —— 层级坏了")
        parent_of[c] = k

world = {}


def wpos(i):
    chain, cur, guard = [], i, 0
    while cur is not None and cur not in world:
        chain.append(cur)
        cur = parent_of.get(cur)
        guard += 1
        if guard > 200:
            raise SystemExit(f"  ✗ 骨骼父链成环（起点 {i}）—— 层级坏了")
    w = world[cur] if cur is not None else np.zeros(3)
    for node in reversed(chain):
        w = w + np.array(J["nodes"][node].get("translation", [0, 0, 0]), np.float64)
        world[node] = w
    return world[i]


idx = {n: j for n, j in zip(names, joints)}
for n in names:
    wpos(idx[n])
print(f"  [1b] 父链无环 ✓ · 根 = {names[0]}")


def angle(a, b):
    va, vb = world[idx[a]], world[idx[b]]
    d = vb - va
    return math.degrees(math.atan2(abs(d[1]), math.hypot(d[0], d[2])))


sem = ["Shoulder", "Arm", "ForeArm", "Hand", "UpLeg", "Leg", "Foot", "ToeBase", "Hips", "Spine", "Neck", "Head"]
hit = sum(1 for s in sem if any(s in n for n in names))
print(f"  [2] 骨名可映射：命中语义关键词 {hit}/{len(sem)} ⇒ {'✅' if hit >= 8 else '❌'}（例：{names[1]} · {names[-1]}）")
try:
    a1 = angle("mixamorig:LeftShoulder", "mixamorig:LeftHand")
    a2 = angle("mixamorig:LeftArm", "mixamorig:LeftForeArm")
    print(f"  [3] 绑定姿势：Shoulder→Hand {a1:.1f}° · Arm→ForeArm {a2:.1f}° ⇒ {'标准 T-pose ✅' if a1 < 12 else 'A-pose/其他 ⚠'}")
except KeyError as e:
    print(f"  [3] 绑定姿势：缺骨名 {e}")
pr = J["meshes"][0]["primitives"][0]
have = all(k in pr["attributes"] for k in ("JOINTS_0", "WEIGHTS_0"))
print(f"  [4] 蒙皮：JOINTS_0/WEIGHTS_0 {'齐 ✅' if have else '缺 ❌'} · 材质 {len(J.get('materials') or [])} · 贴图 {len(J.get('images') or [])}")
