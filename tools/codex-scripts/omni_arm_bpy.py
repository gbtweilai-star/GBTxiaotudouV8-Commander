# -*- coding: utf-8 -*-
"""omni_arm_bpy.py —— Omni-Arm 的 **bpy 侧**：按 spec 建骨架 + 真几何 + 刚体权重，导出 GLB。

⚠️ 与主人设计稿 `ModelExporter.to_blender_py()` 的差别（那件把 `{[asdict(b)...]}` 直接拼进源码，
   产出的 .py 本身语法是坏的）：这里 bpy 逻辑是**独立可跑文件**，输入只用 JSON spec，
   不拼代码、不 eval，跑完在 stdout 吐 `<<<GBT-OMNIARM>>>{...}<<<END>>>` 结果块。

用法（由 omni-arm-build.py 调起）：
    blender --background --factory-startup --python omni_arm_bpy.py -- <spec.json> <out.glb>
"""
import json
import math
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

import bpy
import mathutils


def _args():
    argv = sys.argv
    if "--" in argv:
        rest = argv[argv.index("--") + 1:]
        if len(rest) >= 2:
            return rest[0], rest[1]
    raise SystemExit("用法: ... --python omni_arm_bpy.py -- <spec.json> <out.glb>")


def _clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def _basis(head, tail):
    """给一段骨算局部基（沿骨方向 d + 两个正交轴）。"""
    d = mathutils.Vector(tail) - mathutils.Vector(head)
    if d.length < 1e-9:
        d = mathutils.Vector((0.0, 1.0, 0.0))
    d.normalize()
    ref = mathutils.Vector((0.0, 0.0, 1.0)) if abs(d.z) < 0.9 else mathutils.Vector((1.0, 0.0, 0.0))
    u = d.cross(ref)
    if u.length < 1e-9:
        u = mathutils.Vector((1.0, 0.0, 0.0))
    u.normalize()
    v = d.cross(u)
    v.normalize()
    return d, u, v


def main():
    spec_path, out_path = _args()
    spec = json.loads(open(spec_path, encoding="utf-8").read())
    bones = spec["bones"]
    _clear()

    # ── 1 骨架 ──────────────────────────────────────────────────────────────
    arm_data = bpy.data.armatures.new("OmniArm_22DoF")
    arm_obj = bpy.data.objects.new("OmniArm", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    made = {}
    for b in bones:
        eb = arm_data.edit_bones.new(b["name"])
        eb.head = mathutils.Vector(b["head"])
        eb.tail = mathutils.Vector(b["tail"])
        eb.use_connect = False
        made[b["name"]] = eb
    for b in bones:
        if b.get("parent") and b["parent"] in made:
            made[b["name"]].parent = made[b["parent"]]
            made[b["name"]].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # ── 2 几何：每根骨一个盒子（真体积，不是空壳）──────────────────────────
    verts, faces, groups = [], [], {}
    for b in bones:
        head, tail, r = b["head"], b["tail"], max(0.0035, float(b.get("radius") or 0.01))
        d, u, v = _basis(head, tail)
        h = mathutils.Vector(head)
        t = mathutils.Vector(tail)
        ring0 = [h + u * r + v * r, h + u * r - v * r, h - u * r - v * r, h - u * r + v * r]
        ring1 = [t + u * r + v * r, t + u * r - v * r, t - u * r - v * r, t - u * r + v * r]
        base = len(verts)
        verts.extend([tuple(p) for p in ring0] + [tuple(p) for p in ring1])
        f = [(base + 0, base + 1, base + 2, base + 3),          # 底
             (base + 7, base + 6, base + 5, base + 4),          # 顶
             (base + 0, base + 4, base + 5, base + 1),
             (base + 1, base + 5, base + 6, base + 2),
             (base + 2, base + 6, base + 7, base + 3),
             (base + 3, base + 7, base + 4, base + 0)]
        faces.extend(f)
        groups[b["name"]] = list(range(base, base + 8))

    # ── 2b 额外实体：肩盖/肘块/前臂/手掌板/触手中段（让轮廓读得出"机械臂"）──
    by_name = {b["name"]: b for b in bones}
    for entry in spec.get("extras") or []:
        bone_name, size, off = entry[0], entry[1], entry[2]
        host = by_name.get(bone_name)
        if not host:
            continue
        c = mathutils.Vector(host["head"]) + mathutils.Vector(off)
        hx, hy, hz = (float(s) / 2.0 for s in size)
        base = len(verts)
        for sx, sy, sz in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                           (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)):
            verts.append((c.x + sx * hx, c.y + sy * hy, c.z + sz * hz))
        faces.extend([
            (base + 0, base + 3, base + 2, base + 1), (base + 4, base + 5, base + 6, base + 7),
            (base + 0, base + 1, base + 5, base + 4), (base + 1, base + 2, base + 6, base + 5),
            (base + 2, base + 3, base + 7, base + 6), (base + 3, base + 0, base + 4, base + 7),
        ])
        groups.setdefault(bone_name, []).extend(range(base, base + 8))

    mesh = bpy.data.meshes.new("OmniArmMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("OmniArmBody", mesh)
    bpy.context.collection.objects.link(obj)

    # ── 3 权重：刚体绑定（每盒 → 该骨权重 1.0，权重和恒 = 1）────────────────
    for name, idxs in groups.items():
        vg = obj.vertex_groups.new(name=name)
        vg.add(idxs, 1.0, "REPLACE")

    # ── 4 父级 + 骨架修改器（这是"真蒙皮"的关键，不是只建骨）─────────────────
    obj.parent = arm_obj
    mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = arm_obj
    mod.use_vertex_groups = True

    # ── 5 材质（铝合金观感；Dex5-S 就是铝合金）─────────────────────────────
    mat = bpy.data.materials.new("OmniArmAluminium")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.72, 0.74, 0.78, 1.0)
        bsdf.inputs["Metallic"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 0.34
    mesh.materials.append(mat)

    # ── 6 导出 GLB ─────────────────────────────────────────────────────────
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=out_path, export_format="GLB", use_selection=True,
        export_skins=True, export_animations=False, export_apply=False,
        export_yup=True,
    )

    payload = {
        "ok": True,
        "blender": bpy.app.version_string,
        "bones": len(arm_obj.data.bones),
        "verts": len(mesh.vertices),
        "polys": len(mesh.polygons),
        "vertex_groups": len(obj.vertex_groups),
        "modifier": mod.type,
        "glb": out_path,
    }
    print("<<<GBT-OMNIARM>>>" + json.dumps(payload, ensure_ascii=False) + "<<<END>>>")


main()
