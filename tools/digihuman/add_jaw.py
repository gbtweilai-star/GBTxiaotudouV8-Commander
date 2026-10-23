# -*- coding: utf-8 -*-
"""add_jaw.py —— 给底模加**下颚骨**并渲三档张口（语音嘴对齐的前置：嘴得先能动）。

为什么必须自己加（2026-10-19 实测）：在役 `dh-v2-rigged.glb` 的 67 个节点里
**没有任何 jaw/mouth/chin/lip 骨**，`morph targets = 0`（无 blendshape）——
也就是说**在那个资产上"语音嘴对齐"物理上做不到**：没有可驱动的嘴。
所以嘴对齐必须落在新底模上：加一根 jaw 骨 + 把下颌区域的顶点按权重绑上去。

判据（打印机读回执）：下颌顶点数 / jaw 骨名 / 三个角度 / 每张图字节。

用法：
    blender -b -P tools/digihuman/add_jaw.py -- --glb <in.glb> --out-dir <dir>
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name: str, default: str = "") -> str:
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS):
            return ARGS[i + 1]
    return default


def main() -> int:
    src = Path(arg("--glb"))
    out_dir = Path(arg("--out-dir", "outputs/makehuman/jaw"))
    out_dir.mkdir(parents=True, exist_ok=True)
    if not src.is_file():
        print("读不到 glb：%s" % src)
        return 2

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src))
    mesh = next((o for o in bpy.context.scene.objects if o.type == "MESH"), None)
    rig = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
    if mesh is None or rig is None:
        print("缺网格或骨架")
        return 3

    # ── 下颌区域怎么算（可指回）：取「头部骨」的 DEF 骨位置作锚点，
    #    下颌 = z 低于嘴线、且在脸前方的顶点。嘴线取 head 骨 head/tail 的中点。
    head_bone = None
    for name in ("DEF-head", "DEF-head.001", "head", "Head"):
        head_bone = rig.data.bones.get(name)
        if head_bone:
            break
    if head_bone is None:
        cands = [b for b in rig.data.bones if "head" in b.name.lower()]
        head_bone = cands[0] if cands else None
    if head_bone is None:
        print("找不到 head 骨，无法定位下颌")
        return 4
    hb_head = rig.matrix_world @ head_bone.head_local
    hb_tail = rig.matrix_world @ head_bone.tail_local
    mouth_z = (hb_head.z + hb_tail.z) / 2.0

    # ── 加 jaw 骨（子骨挂在 head 下，沿 -Y 前方伸）
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones
    if "gbt-jaw" not in eb:
        jb = eb.new("gbt-jaw")
        jb.head = (hb_head.x, hb_head.y, mouth_z - (hb_tail.z - hb_head.z) * 0.25)
        jb.tail = (hb_head.x, hb_head.y - abs(hb_tail.y - hb_head.y) * 0.6,
                   jb.head.z - 0.02)
        jb.parent = eb.get(head_bone.name)
        jb.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # ── 权重：下颌顶点 = **只取脸下部这一小块**（第一版取到 4,355 个，把脖子和肩也圈进去了
    #    ⇒ 转 20° 直接把肩颈撕出黑洞，图上一眼可见）。收紧三条：离头心近、z 在嘴线附近、
    #    y 在头心前方。
    vg = mesh.vertex_groups.get("gbt-jaw") or mesh.vertex_groups.new(name="gbt-jaw")
    jaw_ids = []
    mw = mesh.matrix_world
    head_ctr = (hb_head + hb_tail) / 2.0
    for v in mesh.data.vertices:
        w = mw @ v.co
        d = (w - head_ctr).length
        if d > 0.135:
            continue
        if not (mouth_z - 0.085 <= w.z <= mouth_z + 0.015):
            continue
        if w.y > head_ctr.y - 0.02:      # 只在头心前方（脸这一侧）
            continue
        if abs(w.x - head_ctr.x) > 0.062:
            continue
        jaw_ids.append(v.index)
    if jaw_ids:
        vg.add(jaw_ids, 1.0, "REPLACE")

    # ── 渲三档张口（自带的极简三点光 + 正面相机，只为证明"嘴能开"）
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if hasattr(bpy.types, "RenderEngine") else "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 720, 1080
    scene.render.film_transparent = False
    scene.world = scene.world or bpy.data.worlds.new("W")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.02, 0.03, 1)

    cam_data = bpy.data.cameras.new("c")
    cam = bpy.data.objects.new("c", cam_data)
    scene.collection.objects.link(cam)
    cam_data.lens = 85
    cam.location = (hb_head.x, hb_head.y - 1.3, mouth_z + 0.06)
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = cam
    for i, (loc, energy) in enumerate((((0.8, -1.2, 1.6), 900), ((-1.0, -0.9, 0.9), 420),
                                       ((0.2, 0.9, 1.2), 260))):
        ld = bpy.data.lights.new("L%d" % i, "POINT")
        ld.energy = energy
        lo = bpy.data.objects.new("L%d" % i, ld)
        lo.location = loc
        scene.collection.objects.link(lo)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    pb = rig.pose.bones.get("gbt-jaw")
    shots = []
    for deg in (0, 10, 20):
        if pb:
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (math.radians(deg), 0, 0)
        bpy.context.view_layer.update()
        p = out_dir / ("jaw-%02d.png" % deg)
        scene.render.filepath = str(p)
        bpy.ops.render.render(write_still=True)
        shots.append({"deg": deg, "png": str(p),
                      "bytes": p.stat().st_size if p.is_file() else 0})
    bpy.ops.object.mode_set(mode="OBJECT")

    rec = {"ok": all(s["bytes"] > 0 for s in shots),
           "src": str(src), "jaw_bone": "gbt-jaw", "mouth_z": round(mouth_z, 4),
           "jaw_verts": len(jaw_ids), "shots": shots}
    print("<<<GBT-JAW>>>%s<<<END>>>" % json.dumps(rec, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
