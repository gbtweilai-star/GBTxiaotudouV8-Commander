# -*- coding: utf-8 -*-
"""报 Jaw 那 148 个顶点的真实空间分布（Blender 无头），判断它到底选到了哪一片。
用法： blender -b --python dh-jaw-report.py
"""
import json
import sys

import bpy

GLB = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets\dh-v3-jaw.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
mesh = max(meshes, key=lambda o: len(o.data.vertices))
print("[mesh] %s verts=%d" % (mesh.name, len(mesh.data.vertices)))

arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
print("[armature] %s bones=%d" % (arm.name, len(arm.data.bones)))
for bn in ("Head", "Jaw", "Neck"):
    b = None
    for x in arm.data.bones:
        if x.name.lower().endswith(bn.lower()):
            b = x
            break
    if b:
        print("[bone] %-18s head=%s tail=%s parent=%s" % (
            b.name, tuple(round(v, 4) for v in b.head_local), tuple(round(v, 4) for v in b.tail_local),
            b.parent.name if b.parent else None))

vg_by_name = {g.name: g for g in mesh.vertex_groups}
print("[groups] %s" % ", ".join(sorted(vg_by_name))[:400])

jw = None
for n, g in vg_by_name.items():
    if n.lower().endswith("jaw"):
        jw = g
if jw is None:
    print("没有 Jaw 顶点组")
    sys.exit(2)
print("[jaw group] %s index=%d" % (jw.name, jw.index))

jaw_idx = jw.index
rows = []
for v in mesh.data.vertices:
    w = 0.0
    for ge in v.groups:
        if ge.group == jaw_idx:
            w = ge.weight
            break
    if w > 0.001:
        rows.append((v.index, round(v.co.x, 4), round(v.co.y, 4), round(v.co.z, 4), round(w, 3)))

print("[jaw verts] %d" % len(rows))
if rows:
    zs = [r[3] for r in rows]
    ys = [r[2] for r in rows]
    xs = [abs(r[1]) for r in rows]
    ws = [r[4] for r in rows]
    print("[bbox] x|%.4f..%.4f| y|%.4f..%.4f| z|%.4f..%.4f| w %.3f..%.3f 均值%.3f" % (
        min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), min(ws), max(ws), sum(ws) / len(ws)))
    # z 分带（1cm）：看它有没有爬到眼睛高度
    bands = {}
    for _, x, y, z, w in rows:
        k = round(z, 2)
        bands.setdefault(k, 0)
        bands[k] += 1
    print("[z 分带] " + json.dumps({str(k): bands[k] for k in sorted(bands)}, ensure_ascii=False))
    # 头部整体（Head 组）的 z 范围，作对照
    hg = None
    for n, g in vg_by_name.items():
        if n.lower().endswith("head"):
            hg = g
    if hg is not None:
        hz = []
        for v in mesh.data.vertices:
            for ge in v.groups:
                if ge.group == hg.index and ge.weight > 0.2:
                    hz.append(v.co.z)
                    break
        if hz:
            print("[head 组 z] %.4f .. %.4f（n=%d）" % (min(hz), max(hz), len(hz)))
    print("[最大权重那 10 个] " + json.dumps(sorted(rows, key=lambda r: -r[4])[:10]))
