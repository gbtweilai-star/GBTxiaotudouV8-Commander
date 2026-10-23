# -*- coding: utf-8 -*-
"""rigify_bind.py —— 给 CC0 底模绑骨（Rigify 人形 metarig → generate → 自动权重）。

Owner 2026-10-19 定的顺序第 3 步：`清辅助几何 → 配皮肤材质 → Rigify 绑骨 → 八条闸 → 三档图`。

为什么用 Rigify：它随 Blender 自带（GPL，无需外部资产、无需联网、无需密钥），
生成的是**带 IK/FK 切换的人形骨架**，比手搭骨骼可靠；权重用 `ARMATURE_AUTO`（热扩散）自动绑。

用法：
    blender -b -P tools/digihuman/rigify_bind.py -- --glb <in.glb> --out <out.glb>
回执：<<<GBT-RIGIFY>>>{...}<<<END>>>
"""
from __future__ import annotations

import hashlib
import json
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
    dst = Path(arg("--out", "outputs/makehuman/body-rigged.glb"))
    if not src.is_file():
        print("读不到 glb：%s" % src)
        return 2

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src))
    mesh = next((o for o in bpy.context.scene.objects if o.type == "MESH"), None)
    if mesh is None:
        print("没有网格")
        return 3

    # 网格包围盒（世界坐标）——用来对齐 metarig
    bpy.context.view_layer.update()
    corners = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
    zs = [c.z for c in corners]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    h = max(zs) - min(zs)
    # 🔴 2026-10-19：本仓身高口径是 **1.720（文件空间）**，上一版量到 1.6909 会直接红在
    #    八条闸第③条。这里先把网格精确缩到 1.720，再让 metarig 跟着对齐（不是反过来）。
    if h > 1e-6 and abs(h - 1.72) > 0.005:
        s0 = 1.72 / h
        mesh.scale = (s0, s0, s0)
        bpy.ops.object.select_all(action="DESELECT")
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.context.view_layer.update()
        corners = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
        zs = [c.z for c in corners]
        xs = [c.x for c in corners]
        ys = [c.y for c in corners]
        h = max(zs) - min(zs)
    lo_z = min(zs)
    ctr_x = (max(xs) + min(xs)) / 2
    ctr_y = (max(ys) + min(ys)) / 2

    # 1) 加 Rigify 人形 metarig（插件随 Blender 自带，先启用）
    try:
        bpy.ops.preferences.addon_enable(module="rigify")
    except Exception as e:                                     # noqa: BLE001
        print("rigify 启用失败：%s" % type(e).__name__)
    bpy.ops.object.armature_human_metarig_add()
    rig = bpy.context.object
    # 2) 对齐：把 metarig 缩到与网格同高、脚底对齐、水平居中
    bpy.context.view_layer.update()
    rc = [rig.matrix_world @ Vector(c) for c in rig.bound_box]
    rz = [c.z for c in rc]
    rx = [c.x for c in rc]
    ry = [c.y for c in rc]
    rh = max(rz) - min(rz)
    s = h / rh if rh > 1e-6 else 1.0
    rig.scale = (s, s, s)
    bpy.context.view_layer.update()
    rc2 = [rig.matrix_world @ Vector(c) for c in rig.bound_box]
    rz2 = [c.z for c in rc2]
    rx2 = [c.x for c in rc2]
    ry2 = [c.y for c in rc2]
    rig.location.x += ctr_x - (max(rx2) + min(rx2)) / 2
    rig.location.y += ctr_y - (max(ry2) + min(ry2)) / 2
    rig.location.z += lo_z - min(rz2)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)

    # 3) 生成控制/变形骨架
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.rigify_generate()
    bpy.ops.object.mode_set(mode="OBJECT")
    new_rig = bpy.context.object
    n_bones = len(new_rig.data.bones)
    # 🔴 2026-10-19 修：rigify 生成的是**第二条骨架**，原来那条 metarig 还留在场景里 ⇒
    #    导出后 glb 里有 **2 个 skins**，八条闸第①条（单网格单蒙皮）当场红。
    #    这里把 metarig 删掉，只留「生成后的控制骨架 + 网格」。
    try:
        if rig is not None and rig.name != new_rig.name:
            bpy.data.objects.remove(rig, do_unlink=True)
    except ReferenceError:
        pass

    # 4) 自动权重（热扩散）：网格父级到骨架
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    new_rig.select_set(True)
    bpy.context.view_layer.objects.active = new_rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")

    # 4b) 补绑：热扩散对**不连通的小壳**（眼球/牙/舌这种独立岛）会算不出权重 ⇒ 实测剩 80 个
    #     未绑顶点（就是眼球）。这里按**最近已绑顶点**的权重把它补上（标准做法，不猜）。
    fixed = 0
    bound = [v for v in mesh.data.vertices if any(g.weight > 1e-6 for g in v.groups)]
    if bound:
        for v in mesh.data.vertices:
            if any(g.weight > 1e-6 for g in v.groups):
                continue
            best, bd = None, 1e18
            for b in bound:
                d = (b.co - v.co).length_squared
                if d < bd:
                    bd, best = d, b
            if best is None:
                continue
            for g in best.groups:
                mesh.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
            fixed += 1

    # 5) 统计未绑顶点（权重为 0 的）
    unbound = 0
    for v in mesh.data.vertices:
        if not any(g.weight > 1e-6 for g in v.groups):
            unbound += 1

    dst.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(dst), export_format="GLB", use_selection=True)
    data = dst.read_bytes()
    rec = {"ok": unbound == 0, "src": str(src), "out": str(dst),
           "bones": n_bones, "verts": len(mesh.data.vertices),
           "unbound_verts": unbound,
           "height_m": round(h, 4),
           "bytes": len(data), "sha16": hashlib.sha256(data).hexdigest()[:16]}
    print("<<<GBT-RIGIFY>>>%s<<<END>>>" % json.dumps(rec, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
