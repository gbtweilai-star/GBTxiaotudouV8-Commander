# -*- coding: utf-8 -*-
"""数字人基础件构建（全免费 · 全本地 · Blender 无头）—— 用**绑骨架的免费工具**自己干。

主人令（2026-10-09）：「直接使用触手操控这些绑骨架的免费工具啊，我都服了你了，一个AI学不会这些！」

口径（先说清楚，不吹）：
  · 本脚本产出的是**比例正确、骨架标准、蒙皮可见的躯体基底**（procedural base），
    **不是**从参考图还原的逼真脸/服装 —— 那一步（S1 图生 3D）要么走 Tripo（花钱），
    要么等基础件立住之后再换后端。**这一步的价值是：把 S5/S6 的骨架与蒙皮先真立起来**。
  · 技法：Rigify 人形 metarig（159 骨）→ 由骨骼头尾生成顶点的**躯体网格**（Skin 修改器 + 细分）
    → Rigify 生成变形骨架 → **自动权重**蒙皮 → 按 **VRM Humanoid** 改名 → 导出 GLB + skeleton.json。

用法：blender -b -P dh-basebuild.py -- <out_dir>
"""
import json
import os
import sys

import bpy

OUT = sys.argv[-1] if "--" in sys.argv else r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet\assets\digital-human\raw"
RIG_DIR = os.path.join(OUT, "rig")
PHASE1 = os.path.join(OUT, "phase1")
os.makedirs(RIG_DIR, exist_ok=True)
os.makedirs(PHASE1, exist_ok=True)

# Rigify 变形骨名 → VRM Humanoid 标准名（15 必需 + 常用）
DEF2VRM = {
    "DEF-spine": "hips", "DEF-spine.001": "spine", "DEF-spine.002": "chest",
    "DEF-spine.003": "upperChest", "DEF-spine.004": "neck", "DEF-spine.006": "head",
    "DEF-shoulder.L": "leftShoulder", "DEF-upper_arm.L": "leftUpperArm",
    "DEF-forearm.L": "leftLowerArm", "DEF-hand.L": "leftHand",
    "DEF-shoulder.R": "rightShoulder", "DEF-upper_arm.R": "rightUpperArm",
    "DEF-forearm.R": "rightLowerArm", "DEF-hand.R": "rightHand",
    "DEF-thigh.L": "leftUpperLeg", "DEF-shin.L": "leftLowerLeg", "DEF-foot.L": "leftFoot",
    "DEF-toe.L": "leftToes",
    "DEF-thigh.R": "rightUpperLeg", "DEF-shin.R": "rightLowerLeg", "DEF-foot.R": "rightFoot",
    "DEF-toe.R": "rightToes",
}
VRM_REQUIRED = ["hips", "spine", "head", "leftUpperArm", "leftLowerArm", "leftHand",
                "rightUpperArm", "rightLowerArm", "rightHand",
                "leftUpperLeg", "leftLowerLeg", "leftFoot",
                "rightUpperLeg", "rightLowerLeg", "rightFoot"]


def log(*a):
    print("[dh-basebuild]", *a, flush=True)


# ① 干净场景 + 启用 Rigify（必须**先** read_factory_settings 再 enable —— 踩过）
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="rigify")
bpy.ops.object.armature_human_metarig_add()
meta = bpy.context.object
meta.name = "GBTMetaRig"
bones = meta.data.bones
log("metarig 骨数 =", len(bones))

# ② 由骨骼头尾造躯体网格（顶点=骨头/尾，边=父子链）——Skin 修改器把它撑成实体
verts, edges, idx = [], [], {}
for i, b in enumerate(bones):
    idx[b.name] = len(verts)
    verts.append(tuple(b.head_local))
    vid_tail = len(verts)
    verts.append(tuple(b.tail_local))
    edges.append((idx[b.name], vid_tail))
    idx.setdefault("__tail__" + b.name, vid_tail)
for b in bones:
    if b.parent:
        edges.append((idx[b.name], idx[b.parent.name]))

me = bpy.data.meshes.new("GBTBody")
me.from_pydata(verts, edges, [])
me.update()
body = bpy.data.objects.new("GBTBody", me)
bpy.context.collection.objects.link(body)

skin = body.modifiers.new("Skin", "SKIN")
sub = body.modifiers.new("Sub", "SUBSURF")
sub.levels = 2
# 半径：按骨长给一个基础体型（躯干粗、四肢细），不追求像，只求**实体成立**
# Blender 4.x：皮肤半径不在 MeshVertex 上（没有 .radius），在 **skin_vertices 层**里。
#    第一版写成 v.radius ⇒ AttributeError: 'MeshVertex' object has no attribute 'radius'。
sv = me.skin_vertices[0].data
for i, b in enumerate(bones):
    sv[idx[b.name]].radius = (0.07, 0.07)
    sv[idx["__tail__" + b.name]].radius = (0.05, 0.05)
bpy.context.view_layer.objects.active = body
for m in ("Skin", "Sub"):
    bpy.ops.object.modifier_apply(modifier=m)
log("躯体网格 顶点 =", len(body.data.vertices), "面 =", len(body.data.polygons))

# ③ Rigify 生成变形骨架
bpy.context.view_layer.objects.active = meta
bpy.ops.object.mode_set(mode="POSE")
bpy.ops.pose.rigify_generate()
rig = bpy.context.object
log("变形骨架 =", rig.name, "骨数 =", len(rig.data.bones))

# ④ 按 VRM 改名（**保留原名到 custom prop**，可回溯）
renamed = {}
for b in rig.data.bones:
    if b.name in DEF2VRM:
        vrm = DEF2VRM[b.name]
        b["gbt_orig"] = b.name
        renamed[b.name] = vrm
for old, new in renamed.items():
    try:
        rig.data.bones[old].name = new
    except Exception as exc:                                  # noqa: BLE001
        log("改名失败", old, "→", new, exc)
log("VRM 改名 =", len(renamed))

# ⑤ 自动权重蒙皮
body.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type="ARMATURE_AUTO")
# 2026-10-09 修（实测撞了，导出器原话「GBTBody has no skin, skipping adding neutral bone data」）：
#    ARMATURE_AUTO 建好了顶点组与修改器，但**父子类型落在 OBJECT** ⇒
#    glTF 导出器的 find_armature() 认不出这网格有蒙皮 ⇒ **skins=0**（JOINTS_0/WEIGHTS_0 都白导）。
#    显式把父子类型钉成 **ARMATURE**（Armature Deform），导出器才写得进 skin 数组。
body.parent_type = "ARMATURE"
mods = [m.type for m in body.modifiers]
log("蒙皮修改器 =", mods)
groups = len(body.vertex_groups)
log("顶点组（受骨影响的组数）=", groups)

# ⑥ 写 skeleton.json（15 必需骨 + 父子关系）
have = {b.name: b for b in rig.data.bones}
missing = [v for v in VRM_REQUIRED if v not in have]
skel = {"bones": [{"name": b.name, "parent": (b.parent.name if b.parent else None)}
                  for b in rig.data.bones if b.name in set(DEF2VRM.values())],
        "vrm_required": VRM_REQUIRED,
        "missing_required": missing,
        "source": "Rigify human metarig（159 骨）→ 变形骨架 → VRM 改名",
        "generator": "tools/codex-scripts/dh-basebuild.py（Blender 无头，全免费本地）"}
with open(os.path.join(RIG_DIR, "skeleton.json"), "w", encoding="utf-8") as f:
    json.dump(skel, f, ensure_ascii=False, indent=1)
log("skeleton.json 缺必需骨 =", missing)

# ⑦ 一段 idle 循环动画（S8 要的是**循环闭合**）
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="POSE")
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 24
for pb in rig.pose.bones:
    if pb.name in ("hips", "chest", "head"):
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)
        pb.keyframe_insert("rotation_euler", frame=1)
        pb.rotation_euler = (0.02, 0, 0.01)
        pb.keyframe_insert("rotation_euler", frame=13)
        pb.rotation_euler = (0, 0, 0)
        pb.keyframe_insert("rotation_euler", frame=24)
bpy.ops.object.mode_set(mode="OBJECT")

# ⑧ 导出：基底网格（S1）+ 绑骨动画件（S6/S8）
# 2026-10-09 修（实测撞了）：第一版 use_selection=True ⇒ 导出的 GLB **skins=0**
#    （JOINTS_0/WEIGHTS_0 都在，但没有 skin 数组）⇒ S6 门直接判「无 skin」。
#    根因：use_selection 下场景图里没有「骨架是网格父节点」这条关系（而且 metarig 还在场）。
#    修法：**先删掉临时 metarig**，再**整场景导出**。
# 2026-10-09 清场（根因修复）：Rigify 生成了一大堆 WGT-* 控件件（本次导出 **928 个节点**），
#    导出器在这一堆里**认不出蒙皮**（原话「GBTBody has no skin」），skins 恒为 0。
#    修法：导出前**只留 body + rig**，并按最规范的三步重建蒙皮关系（父子 + 修改器 + 逆矩阵），
#    而不是靠 parent_set 的副产物。
for _o in list(bpy.data.objects):
    if _o.name not in (body.name, rig.name):
        bpy.data.objects.remove(_o, do_unlink=True)
log("清场后剩余对象 =", [o.name for o in bpy.data.objects])
for _m in list(body.modifiers):
    if _m.type == "ARMATURE":
        body.modifiers.remove(_m)
body.parent = rig
body.parent_type = "OBJECT"
body.matrix_parent_inverse = rig.matrix_world.inverted()
_mod = body.modifiers.new("Armature", "ARMATURE")
_mod.object = rig
log("蒙皮三步已重建：parent=", body.parent.name, "| mod=", _mod.object.name)
_fa = body.find_armature()
log("导出前 find_armature =", (_fa.name if _fa else None),
    "| parent =", (body.parent.name if body.parent else None), "| parent_type =", body.parent_type,
    "| 修改器 =", [(m.type, getattr(getattr(m, "object", None), "name", None))
                   for m in body.modifiers])
if "GBTMetaRig" in bpy.data.objects:
    bpy.data.objects.remove(bpy.data.objects["GBTMetaRig"], do_unlink=True)
    log("已删除临时 metarig（避免导出里多一具空骨架）")
_sel = [o for o in (body, rig) if o.name in bpy.data.objects]
for o in _sel:
    o.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(filepath=os.path.join(PHASE1, "model.glb"),
                          export_format="GLB", export_skins=True)
bpy.ops.export_scene.gltf(filepath=os.path.join(RIG_DIR, "model-rigged-anim.glb"),
                          export_format="GLB", export_skins=True)
log("导出 model.glb / model-rigged-anim.glb 完成")
print("DONE verts=%d bones=%d vgroups=%d missing=%d"
      % (len(body.data.vertices), len(rig.data.bones), groups, len(missing)), flush=True)
