# -*- coding: utf-8 -*-
"""用 Blender 4.2 给她的头加一根 **Jaw（下颌）骨** 并把嘴部顶点绑上去 —— 真口型的地基。

主人两条待办里的第②条。为什么必须在 DCC 里做：three.js 只能驱动**已存在的骨**，
网格上没有 jaw 骨、也没有形态键，页面写多少行都张不开嘴（之前页面就照实写了"做不到"）。

做法（每一步都留读数，不猜）：
 1. 选**顶点最多**的网格（GLB 里有个 42 顶点的辅助 Icosphere，第一版就选错过）；
 2. 以 Head 骨为参照定嘴的位置：Blender 是 Z-up、角色朝 −Y；
    嘴带 = z 在唇线下 2.5cm 内、y 向前、|x| 窄 —— 参数写在下面，可改；
 3. 建 Jaw 骨：父级 Head，起点在颞颌关节高度、尾端朝下巴，长度按头部尺寸给；
 4. 嘴部顶点按"离唇线越近权重越大"绑到 Jaw（1.0 → 0 平滑衰减），其余骨权重不动；
 5. 导出 GLB（原文件先备份到 state/_backup/，再原子替换）。

用法：
  blender -b --python tools/digihuman/dh-add-jaw.py -- --dry       只量不做
  blender -b --python tools/digihuman/dh-add-jaw.py -- --apply     真写并导出
"""
import bpy
import json
import math
import os
import shutil
import sys
from mathutils import Vector

SRC = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets\dh-v2-rigged.glb"
DST = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets\dh-v3-jaw.glb"
BAK = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\_backup\dh-v2-rigged.glb"

# 嘴带参数（Blender 世界坐标；Z 是高度，−Y 是她的正前方）
MOUTH_Z = (1.545, 1.640)     # 唇线上下各 ~2.5cm
MOUTH_Y_MAX = -0.045         # 只要脸前面那一片
MOUTH_ABSX = 0.060           # 半宽（嘴角）
FALLOFF_Z = 0.035            # 离唇线 3.5cm 外权重降到 0

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
APPLY = "--apply" in argv

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
mesh = max(meshes, key=lambda o: len(o.data.vertices))
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
head = next(b for b in arm.data.bones if b.name.lower().endswith("head"))

mw = mesh.matrix_world
report = {"src": SRC, "dst": DST, "apply": APPLY,
          "mesh": mesh.name, "verts": len(mesh.data.vertices),
          "armature": arm.name, "bones_before": len(arm.data.bones)}

# ── 1) 找嘴带顶点 ────────────────────────────────────────────────────────────
mouth_verts = []
for v in mesh.data.vertices:
    w = mw @ v.co
    if MOUTH_Z[0] <= w.z <= MOUTH_Z[1] and w.y <= MOUTH_Y_MAX and abs(w.x) <= MOUTH_ABSX:
        mouth_verts.append((v.index, w))

report["mouth_candidates"] = len(mouth_verts)
if mouth_verts:
    zs = [w.z for _, w in mouth_verts]
    report["mouth_bbox"] = {
        "z": [round(min(zs), 4), round(max(zs), 4)],
        "y": [round(min(w.y for _, w in mouth_verts), 4), round(max(w.y for _, w in mouth_verts), 4)],
        "x": [round(min(w.x for _, w in mouth_verts), 4), round(max(w.x for _, w in mouth_verts), 4)],
    }
    # 唇线 = 嘴带的中点高度（权重从这里向两侧衰减）
    lip_z = (min(zs) + max(zs)) / 2.0
    report["lip_z"] = round(lip_z, 4)

if not APPLY:
    print(json.dumps({"ok": True, "dry": report}, ensure_ascii=False))
    sys.exit(0)

if len(mouth_verts) < 20:
    print(json.dumps({"ok": False, "why": "嘴带顶点太少，拒绝动模型", "report": report}, ensure_ascii=False))
    sys.exit(1)

# ── 2) 建 Jaw 骨（父级 Head）─────────────────────────────────────────────────
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones
jaw_name = "mixamorig:Jaw" if head.name.startswith("mixamorig:") else "Jaw"
if jaw_name in eb:
    eb.remove(eb[jaw_name])
jaw = eb.new(jaw_name)
jaw.parent = eb[head.name]
jaw.use_connect = False
# 颞颌关节：在 Head 骨起点略下方、略靠后；尾巴指向下巴前下方
hj = Vector((head.head_local.x, head.head_local.y + 0.01, head.head_local.z - 0.012))
jaw.head = hj
jaw.tail = hj + Vector((0.0, -0.055, -0.055))
bpy.ops.object.mode_set(mode="OBJECT")

# ── 3) 权重：嘴带顶点按到唇线的距离衰减绑到 Jaw ──────────────────────────────
if jaw_name not in mesh.vertex_groups:
    vg = mesh.vertex_groups.new(name=jaw_name)
else:
    vg = mesh.vertex_groups[jaw_name]
for idx, w in mouth_verts:
    d = abs(w.z - report["lip_z"])
    wt = max(0.0, 1.0 - d / FALLOFF_Z)
    if wt > 0.01:
        vg.add([idx], min(1.0, wt), "REPLACE")
report["weighted"] = sum(1 for _, w in mouth_verts if abs(w.z - report["lip_z"]) < FALLOFF_Z)

# ── 4) 导出（原文件先备份）───────────────────────────────────────────────────
os.makedirs(os.path.dirname(BAK), exist_ok=True)
if os.path.isfile(SRC) and not os.path.isfile(BAK):
    shutil.copy2(SRC, BAK)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(
    filepath=DST, export_format="GLB", use_selection=False,
    export_animations=True, export_apply=False, export_yup=True,
)
report["bones_after"] = len(arm.data.bones)
report["exported"] = DST
report["bytes"] = os.path.getsize(DST) if os.path.isfile(DST) else 0
report["backup"] = BAK if os.path.isfile(BAK) else None
print(json.dumps({"ok": True, "report": report}, ensure_ascii=False))
