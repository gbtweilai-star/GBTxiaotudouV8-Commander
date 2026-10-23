# -*- coding: utf-8 -*-
"""用 Blender 4.2 无头模式**先看清**这个绑骨件：骨位/朝向/嘴部顶点在哪。

为什么先量：脚要"并"要知道脚骨现在的静止朝向；嘴要"能张"要知道嘴在哪、哪些顶点属于下唇。
凭感觉写（把骨随便转 8°、按高度切一半顶点）会得到歪脚和漏嘴的形变。
用法：blender -b --python dh-blender-inspect.py
"""
import bpy
import json
import os
import sys

SRC = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets\dh-v2-rigged.glb"
OUT = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\hd\app-after\blender-inspect.json"

# 清场
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)

rep = {"src": SRC, "objects": [], "bones": [], "mesh": {}, "head": {}}

for ob in bpy.data.objects:
    rep["objects"].append({"name": ob.name, "type": ob.type})

arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
rep["all_meshes"] = [{"name": o.name, "verts": len(o.data.vertices), "vgroups": len(o.vertex_groups)} for o in meshes]
# 选**顶点最多**的那件：GLB 里可能还有代理/辅助网格（第一版就选错了个 42 顶点的空壳）
mesh = max(meshes, key=lambda o: len(o.data.vertices)) if meshes else None
if arm is None or mesh is None:
    print(json.dumps({"ok": False, "why": "no armature/mesh"}))
    sys.exit(1)

rep["armature"] = arm.name
rep["armature_scale"] = list(arm.scale)

# 骨：名字 / 父 / 头尾（世界坐标）/ 静止欧拉
for b in arm.data.bones:
    h = arm.matrix_world @ b.head_local
    t = arm.matrix_world @ b.tail_local
    rep["bones"].append({
        "name": b.name,
        "parent": b.parent.name if b.parent else None,
        "head": [round(v, 4) for v in h],
        "tail": [round(v, 4) for v in t],
        "len": round((t - h).length, 4),
        "euler": [round(v, 4) for v in b.matrix_local.to_euler()],
    })

# 网格：包围盒、分组、形态键
rep["mesh"] = {
    "name": mesh.name,
    "verts": len(mesh.data.vertices),
    "polys": len(mesh.data.polygons),
    "shape_keys": ([k.name for k in mesh.data.shape_keys.key_blocks] if mesh.data.shape_keys else []),
    "vgroups": [g.name for g in mesh.vertex_groups],
    "dim": [round(v, 4) for v in mesh.dimensions],
}

# 嘴部：以 Head 骨为参照，找"头骨以下 / 前方"的顶点带（下唇/下颌区域）
head = next((b for b in arm.data.bones if b.name.lower().endswith("head")), None)
if head:
    hh = arm.matrix_world @ head.head_local  # Blender 是 Z-up：**高度是 z**（第一版按 y 量，结果 0 个顶点）
    ht = arm.matrix_world @ head.tail_local
    rep["head"] = {"head": [round(v, 4) for v in hh], "tail": [round(v, 4) for v in ht]}
    mw = mesh.matrix_world
    ys = []
    for v in mesh.data.vertices:
        w = mw @ v.co
        ys.append((v.index, [round(x, 4) for x in w]))
    # 头骨范围内的顶点：高度在 head 与 headTop 之间
    top = next((b for b in arm.data.bones if "HeadTop" in b.name), None)
    topy = (arm.matrix_world @ top.tail_local).z if top else ht.z
    band = [p for _, p in ys if hh.z - 0.02 <= p[2] <= topy]
    rep["head"]["verts_in_head_band"] = len(band)
    if band:
        rep["head"]["bbox"] = {
            "x": [round(min(p[0] for p in band), 4), round(max(p[0] for p in band), 4)],
            "z": [round(min(p[2] for p in band), 4), round(max(p[2] for p in band), 4)],
            "y": [round(min(p[1] for p in band), 4), round(max(p[1] for p in band), 4)],
        }

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(rep, fh, ensure_ascii=False, indent=1)
print(json.dumps({"ok": True, "out": OUT, "bones": len(rep["bones"]),
                  "verts": rep["mesh"]["verts"], "shape_keys": rep["mesh"]["shape_keys"],
                  "vgroups": len(rep["mesh"]["vgroups"])}, ensure_ascii=False))
