# -*- coding: utf-8 -*-
"""数字人 · 诊断视图：把"骨权域"和"被拉长的边"**画出来**（不是感觉，是着色）

模式：
  dom        按"第一影响骨"给顶点上色（19 色 + 分组色），看骨权域到底在哪
  blade@动作@帧  把该帧被拉长的边（形变/静置 > 阈值）端点染红→黄（按比值），其余灰
  disp@动作@帧   按该帧顶点位移量染色（蓝→红）

渲染用 EEVEE（无灯光，自发光 = 颜色即读数），720×900，快。
用法：
  blender.exe --background --python tools/codex-scripts/blender/dh_fix_view.py -- \
     --mode dom --out .scratch/view_dom.png
  blender.exe --background --python tools/codex-scripts/blender/dh_fix_view.py -- \
     --mode blade --action 02_打招呼 --frame 21 --out .scratch/view_blade_02f21.png
"""
import argparse
import json
import math
import os
import sys

WS = r"C:\Users\ADMIN\Desktop\GBT小土豆V8"

PALETTE = {
    "hips": (0.90, 0.20, 0.20), "spine": (0.95, 0.55, 0.10), "chest": (0.95, 0.90, 0.15),
    "neck": (0.35, 0.85, 0.25), "head": (0.10, 0.55, 0.95),
    "shoulder_L": (0.35, 0.95, 0.95), "upper_arm_L": (0.10, 0.80, 0.60),
    "forearm_L": (0.55, 1.00, 0.55), "hand_L": (0.95, 0.45, 0.95),
    "shoulder_R": (0.60, 0.30, 0.95), "upper_arm_R": (0.30, 0.15, 0.95),
    "forearm_R": (0.10, 0.10, 0.65), "hand_R": (0.55, 0.35, 0.75),
    "thigh_L": (0.95, 0.65, 0.55), "shin_L": (0.75, 0.45, 0.35), "foot_L": (0.55, 0.30, 0.20),
    "thigh_R": (0.60, 0.75, 0.90), "shin_R": (0.35, 0.50, 0.70), "foot_R": (0.20, 0.30, 0.50),
}
ARM_L = ["shoulder_L", "upper_arm_L", "forearm_L", "hand_L"]
ARM_R = ["shoulder_R", "upper_arm_R", "forearm_R", "hand_R"]


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(WS, "projects", "digital-human", "out",
                                                    "dh_rigged.blend"))
    ap.add_argument("--mode", default="dom")
    ap.add_argument("--action", default="")
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--ratio", type=float, default=4.0)
    ap.add_argument("--out", default=os.path.join(WS, ".scratch", "view.png"))
    ap.add_argument("--res", default="720x900")
    ap.add_argument("--spp", type=int, default=32)
    ap.add_argument("--yaw", type=float, default=0.0, help="相机绕竖轴额外偏转（度）")
    ap.add_argument("--lens", type=float, default=70.0)
    ap.add_argument("--zoom", default="", help="正交特写：cx,cy,cz,scale(=scale×H)")
    ap.add_argument("--pitch", type=float, default=0.0, help="相机抬高角（度，绕横向轴）")
    return ap.parse_args(argv)


def main():
    a = parse_args()
    import bpy
    import numpy as np
    from mathutils import Vector

    bpy.ops.wm.open_mainfile(filepath=a.blend)
    scn = bpy.context.scene
    mesh_obj = bpy.data.objects["DH_Body"]
    arm_obj = bpy.data.objects["DH_Armature"]
    me = mesh_obj.data
    nv = len(me.vertices)
    co = np.empty(nv * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    core = json.load(open(os.path.join(os.path.dirname(a.blend), "rig_core.json"), encoding="utf-8"))
    H = float(core["H"]); cx = float(core["cx"]); cd = float(core["cd"])
    z0 = float(core["aabb_min"][2])
    bones = list(core["bones"])
    bi = {n: i for i, n in enumerate(bones)}

    # ---- 权重 ----
    W = np.zeros((nv, len(bones)))
    gidx = {g.index: i for i, g in enumerate(mesh_obj.vertex_groups)}
    for v in me.vertices:
        for g in v.groups:
            j = gidx.get(g.group)
            if j is not None:
                W[v.index, j] = g.weight
    dom = np.argmax(W, axis=1)

    frames = []
    blade_lvl = None
    dispv = None
    if a.mode == "blade" or a.mode == "disp":
        act = bpy.data.actions.get(a.action)
        if act is None:
            print("[view] 缺动作 " + a.action); return 2
        arm_obj.animation_data.action = act
        scn.frame_set(a.frame)
        dg = bpy.context.evaluated_depsgraph_get()
        mev = mesh_obj.evaluated_get(dg).to_mesh()
        arr = np.empty(len(mev.vertices) * 3, dtype=np.float64)
        mev.vertices.foreach_get("co", arr)
        P = arr.reshape(-1, 3).copy()
        mesh_obj.evaluated_get(dg).to_mesh_clear()
        ev = np.empty(len(me.edges) * 2, dtype=np.int64)
        me.edges.foreach_get("vertices", ev)
        ev = ev.reshape(-1, 2)
        L0 = np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1)
        dl = np.linalg.norm(P[ev[:, 0]] - P[ev[:, 1]], axis=1)
        ratio = dl / np.maximum(L0, 1e-12)
        blade_lvl = np.zeros(nv)
        m = ratio > a.ratio
        for e0, e1, r in zip(ev[m, 0], ev[m, 1], ratio[m]):
            blade_lvl[e0] = max(blade_lvl[e0], min(1.0, (r - a.ratio) / 40.0))
            blade_lvl[e1] = max(blade_lvl[e1], min(1.0, (r - a.ratio) / 40.0))
        dispv = np.linalg.norm(P - co, axis=1)
        print("[view] %s@%d 被拉长边(>%.1fx)=%d 条，涉及顶点=%d，最大比值=%.0f，位移最大=%.4f"
              % (a.action, a.frame, a.ratio, int(m.sum()), int((blade_lvl > 0).sum()),
                 ratio.max(), dispv.max()))

    # ---- 顶点色 ----
    if me.color_attributes:
        for ca in list(me.color_attributes):
            me.color_attributes.remove(ca)
    col = me.color_attributes.new(name="DH_Diag", type="FLOAT_COLOR", domain="POINT")
    C = np.zeros((nv, 4))
    C[:, 3] = 1.0
    if a.mode == "dom":
        for n, c in PALETTE.items():
            if n in bi:
                C[dom == bi[n], :3] = c
        n_armL = int(np.isin(dom, [bi[n] for n in ARM_L if n in bi]).sum())
        n_armR = int(np.isin(dom, [bi[n] for n in ARM_R if n in bi]).sum())
        print("[view] 第一影响骨属左臂骨=%d 顶点；属右臂骨=%d 顶点（总 %d）" % (n_armL, n_armR, nv))
    elif a.mode == "blade":
        C[:, :3] = (0.55, 0.55, 0.55)
        hot = blade_lvl > 0
        C[hot, 0] = 1.0
        C[hot, 1] = 1.0 - blade_lvl[hot] * 0.95
        C[hot, 2] = 0.05
    elif a.mode == "disp":
        dmax = max(1e-9, dispv.max())
        t = np.clip(dispv / dmax, 0, 1)
        C[:, 0] = t
        C[:, 1] = 0.25 + 0.25 * (1 - t)
        C[:, 2] = 1 - t
    C[dom == -1] = (0, 0, 0, 1)
    col.data.foreach_set("color", C.ravel())

    # ---- 自发光材质（纯色 = 读数）----
    for m in list(mesh_obj.data.materials):
        pass
    mat = bpy.data.materials.new("DH_DiagMat")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    at = nt.nodes.new("ShaderNodeVertexColor")
    at.layer_name = "DH_Diag"
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)

    # ---- 相机/渲染 ----
    W, Hh = [int(v) for v in a.res.lower().split("x")]
    scn.render.resolution_x, scn.render.resolution_y = W, Hh
    scn.render.resolution_percentage = 100
    scn.render.image_settings.file_format = "PNG"
    scn.render.engine = "BLENDER_EEVEE_NEXT"
    try:
        scn.eevee.taa_render_samples = a.spp
    except Exception:
        pass
    fwd = Vector(core.get("forward", [0, -1, 0])).normalized()
    if abs(a.yaw) > 1e-6:
        from mathutils import Quaternion
        fwd = (Quaternion(Vector((0, 0, 1)), math.radians(a.yaw)).to_matrix() @ fwd).normalized()
    ctr = Vector((cx, cd, z0 + H * 0.52))
    camd = bpy.data.cameras.new("DH_DiagCam")
    cam = bpy.data.objects.new("DH_DiagCam", camd)
    scn.collection.objects.link(cam)
    if a.zoom:
        zx, zy, zz, zs = [float(v) for v in a.zoom.split(",")]
        camd.type = "ORTHO"
        camd.ortho_scale = zs * H
        ctr = Vector((zx, zy, zz))
        cam.location = ctr + fwd * (2.0 * H) + Vector((0, 0, math.tan(math.radians(a.pitch)) * 2.0 * H))
    else:
        camd.type = "PERSP"; camd.lens = a.lens
        cam.location = ctr + fwd * (2.55 * H) + Vector((0, 0, 0.24 * H))
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    scn.camera = cam
    scn.view_settings.view_transform = "Standard"
    wd = bpy.data.worlds.new("DH_DiagW"); wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs[1].default_value = 0.0
    scn.world = wd
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    scn.render.filepath = os.path.abspath(a.out)
    scn.render.image_settings.color_mode = "RGB"
    bpy.ops.render.render(write_still=True)
    print("[view] 落盘 %s (%d 字节)" % (a.out, os.path.getsize(a.out)))
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 1
    sys.exit(rc)
