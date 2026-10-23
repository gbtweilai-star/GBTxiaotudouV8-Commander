# -*- coding: utf-8 -*-
"""plate_render — 用本机 Blender(EEVEE) 给三方向作品出**真 3D 镜头底片**（逐镜一张）。

为什么有这件：主人要「高质量成品」。此前成片画面是 ffmpeg 渐变字卡（平面）；
Blender 就装在本机，能出**真几何 + 真灯光 + 真材质**的镜头。零出网、零钥匙。

用法：
  blender -b -P tools/plate_render.py -- --scene xinglai --out <dir> --w 1080 --h 1920 --shots 8
  blender -b -P tools/plate_render.py -- --scene tangwu  --out <dir> --w 1920 --h 1080 --shots 8
"""
import math
import os
import sys
import time

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=""):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


SCENE = arg("--scene", "xinglai")
OUT = arg("--out", "")
W = int(arg("--w", "1080"))
H = int(arg("--h", "1920"))
SHOTS = int(arg("--shots", "8"))
SAMPLES = int(arg("--samples", "32"))


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = W
    sc.render.resolution_y = H
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.eevee.taa_render_samples = SAMPLES
        sc.eevee.use_raytracing = True
    except Exception:
        pass
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    sc.render.film_transparent = False
    return sc


def mat(name, color, emit=None, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = (emit[0], emit[1], emit[2], 1)
        bsdf.inputs["Emission Strength"].default_value = emit[3]
    return m


def box(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(material)
    return o


def cyl(name, loc, radius, depth, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    return o


def plane(name, loc, scale, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(material)
    return o


def light(kind, loc, energy, color=(1, 1, 1), size=2.0, rot=(0, 0, 0)):
    bpy.ops.object.light_add(type=kind, location=loc, rotation=rot)
    o = bpy.context.object
    o.data.energy = energy
    o.data.color = color
    if kind == "AREA":
        o.data.size = size
    return o


def camera(loc, look_at=(0, 0, 1), lens=35):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    cam.data.lens = lens
    bpy.context.scene.camera = cam
    import mathutils
    d = mathutils.Vector(look_at) - mathutils.Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return cam


SHOT_CAMS = {
    "xinglai": [
        ((0.10, -3.9, 0.50), (0.0, 0.15, 0.34), 34),
        ((0.95, -2.05, 0.62), (0.10, 0.10, 0.38), 35),
        ((0.0, -3.55, 1.95), (0.0, 0.25, 0.95), 28),
        ((0.42, -1.65, 0.70), (0.10, 0.05, 0.66), 60),
        ((-0.30, -1.35, 0.78), (0.12, 0.06, 0.62), 75),
        ((0.0, -6.2, 3.4), (0.0, 0.5, 0.7), 24),
        ((0.85, -2.9, 1.15), (0.0, 0.2, 0.55), 40),
        ((0.0, -1.35, 1.02), (0.0, 0.55, 0.85), 32),
    ],
    "tangwu": [
        ((0.0, -6.4, 1.62), (0.0, 0.6, 1.05), 30),
        ((0.55, -3.5, 1.55), (0.0, 0.9, 1.35), 45),
        ((0.15, -1.85, 1.42), (0.0, 0.95, 1.30), 60),
        ((-0.35, -4.6, 1.50), (0.15, 0.5, 1.10), 32),
        ((0.42, -1.35, 1.35), (0.0, 0.75, 1.12), 55),
        ((0.0, -2.15, 1.46), (0.0, 0.85, 1.22), 50),
        ((-1.35, -5.2, 1.68), (0.25, 0.3, 1.05), 28),
        ((0.0, -7.6, 1.72), (0.0, 0.9, 1.05), 26),
    ],
}
SHOT_LIGHT = {
    "xinglai": [(0.20, 0.45, 0.95), (0.55, 0.25, 0.95), (0.30, 0.60, 1.00), (0.95, 0.35, 0.60),
                (0.45, 0.85, 0.95), (0.95, 0.70, 0.35), (0.30, 0.75, 1.00), (0.95, 0.85, 0.65)],
    "tangwu": [(1.00, 0.93, 0.80), (0.95, 0.86, 0.72), (1.00, 0.90, 0.76), (0.90, 0.84, 0.74),
               (0.88, 0.82, 0.72), (0.92, 0.86, 0.76), (1.00, 0.94, 0.82), (0.96, 0.90, 0.78)],
}


def build_xinglai():
    """服务器机房 / 冷却液池 / 霓虹管道 ——《醒来》。

    第一版三处不行（真看图后改）：① 屏幕 emission 3.2 爆成一块白板 ② 主角是低模球、
    分段坐标肉眼可见 ③ 机柜只一个光杆、没细节。现：屏幕降亮 + 加黑边框 + 加 LED 点阵；
    球提高分段并平滑着色；机柜成排带插槽灯。
    """
    m_floor = mat("floor", (0.035, 0.045, 0.06), rough=0.35, metal=0.2)
    m_wall = mat("wall", (0.05, 0.06, 0.08), rough=0.7)
    m_pool = mat("pool", (0.02, 0.06, 0.10), emit=(0.05, 0.35, 0.55, 1.2), rough=0.08, metal=0.6)
    m_pipe_p = mat("pipe_p", (0.10, 0.03, 0.14), emit=(0.45, 0.10, 0.75, 2.4), rough=0.35)
    m_pipe_c = mat("pipe_c", (0.02, 0.09, 0.12), emit=(0.10, 0.65, 0.85, 2.4), rough=0.35)
    m_metal = mat("metal", (0.11, 0.12, 0.13), rough=0.42, metal=0.85)
    m_screen = mat("screen", (0.02, 0.03, 0.05), emit=(0.30, 0.62, 0.95, 0.9), rough=0.2)
    m_bezel = mat("bezel", (0.03, 0.035, 0.04), rough=0.45, metal=0.6)
    m_led = mat("led", (0.02, 0.05, 0.06), emit=(0.25, 0.85, 1.00, 2.2), rough=0.3)
    m_tato = mat("tato", (0.32, 0.16, 0.07), rough=0.72)
    m_neon = mat("neon", (0.05, 0.02, 0.02), emit=(1.00, 0.25, 0.35, 3.6), rough=0.3)
    plane("floor", (0, 1.2, 0), (16, 16, 1), m_floor)
    box("wall_back", (0, 5.6, 2.2), (16, 0.2, 4.4), m_wall)
    box("wall_l", (-6.0, 1.2, 2.2), (0.2, 9.0, 4.4), m_wall)
    box("wall_r", (6.0, 1.2, 2.2), (0.2, 9.0, 4.4), m_wall)
    box("ceil", (0, 1.2, 4.4), (16, 9.0, 0.15), m_wall)
    plane("pool", (0, -0.7, 0.012), (3.6, 2.6, 1), m_pool)
    for i, x in enumerate((-3.7, -2.55, 2.55, 3.7)):
        m = m_pipe_p if i % 2 == 0 else m_pipe_c
        cyl("pipe%d" % i, (x, 0.6, 1.9), 0.16, 9.2, m, rot=(math.radians(90), 0, 0))
    box("console", (0.1, 2.35, 0.62), (2.0, 0.55, 1.15), m_metal)
    box("console_bezel", (0.1, 2.05, 1.02), (1.66, 0.05, 0.76), m_bezel)
    box("console_screen", (0.1, 2.00, 1.02), (1.52, 0.03, 0.62), m_screen)
    for r in range(3):
        for c in range(6):
            box("led_%d_%d" % (r, c), (-0.55 + c * 0.22, 1.97, 0.80 + r * 0.20),
                (0.09, 0.02, 0.05), m_led)
    for side in (-1, 1):
        for k in range(3):
            x = side * (4.4 + k * 0.16)
            box("rack%d_%d" % (side, k), (x, 0.9 + k * 1.9, 1.15), (0.75, 3.4, 2.3), m_metal)
            for s in range(5):
                box("slot%d_%d_%d" % (side, k, s), (x - side * 0.39, 0.9 + k * 1.9, 0.35 + s * 0.42),
                    (0.02, 2.6, 0.06), m_led)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=0.30,
                                         location=(0.05, -0.55, 0.22))
    t = bpy.context.object
    t.name = "tato"
    t.scale = (1.0, 0.86, 0.92)
    t.data.materials.append(m_tato)
    bpy.ops.object.shade_smooth()
    plane("neon", (0.0, 5.42, 2.55), (4.2, 1.0, 1), m_neon)
    light("AREA", (0, -1.2, 3.6), 320, (0.55, 0.75, 1.0), size=6)
    light("POINT", (-4.6, 2.6, 1.9), 220, (0.45, 0.65, 1.0))
    light("POINT", (4.6, 2.6, 1.9), 220, (0.75, 0.35, 1.0))
    light("POINT", (0.1, 2.1, 1.35), 160, (0.35, 0.8, 1.0))


def build_tangwu():
    """乡下老屋堂屋 / 八仙桌 / 相框 / 门外光 ——《堂屋》。"""
    m_floor = mat("floor", (0.22, 0.16, 0.10), rough=0.55)
    m_wall = mat("wall", (0.42, 0.38, 0.32), rough=0.85)
    m_wood = mat("wood", (0.26, 0.15, 0.07), rough=0.5)
    m_frame = mat("frame", (0.45, 0.32, 0.16), rough=0.45, metal=0.3)
    m_photo = mat("photo", (0.10, 0.09, 0.08), emit=(0.28, 0.24, 0.20, 0.35), rough=0.25)
    plane("floor", (0, 1.0, 0), (12, 14, 1), m_floor)
    box("wall_back", (0, 5.2, 1.9), (12, 0.2, 3.8), m_wall)
    box("wall_l", (-4.2, 1.0, 1.9), (0.2, 9.0, 3.8), m_wall)
    box("wall_r", (4.2, 1.0, 1.9), (0.2, 9.0, 3.8), m_wall)
    box("ceil", (0, 1.0, 3.75), (12, 9.0, 0.15), m_wall)
    box("table_top", (0, 1.15, 0.80), (2.5, 1.55, 0.10), m_wood)
    for sx in (-1.05, 1.05):
        for sy in (0.55, 1.75):
            box("leg", (sx, sy, 0.40), (0.11, 0.11, 0.80), m_wood)
    box("frame", (0.0, 5.05, 1.95), (0.95, 0.07, 0.72), m_frame)
    plane("photo", (0.0, 4.99, 1.95), (0.78, 0.55, 1), m_photo, rot=(math.radians(90), 0, 0))
    box("door_jamb_l", (-1.5, 4.99, 1.45), (0.16, 0.22, 2.9), m_wood)
    box("door_jamb_r", (-0.15, 4.99, 1.45), (0.16, 0.22, 2.9), m_wood)
    light("AREA", (-0.82, 6.6, 1.55), 900, (1.0, 0.90, 0.72), size=3.2, rot=(math.radians(90), 0, 0))
    light("POINT", (0.4, 2.4, 2.9), 60, (0.95, 0.90, 0.80))
    light("POINT", (-2.4, 0.2, 1.0), 25, (0.85, 0.82, 0.78))


def main():
    sc = _reset()
    if SCENE == "xinglai":
        build_xinglai()
    else:
        build_tangwu()
    cams = SHOT_CAMS[SCENE]
    cols = SHOT_LIGHT[SCENE]
    # ⚠️ 必须绝对路径：Blender 对**相对**渲染路径不按 CWD 解析（实测输出「已保存」而盘上无件）。
    #    另：非 ASCII 路径（如中文目录）也会静默失败 ⇒ 输出一律走 ASCII 中转目录。
    outdir = os.path.abspath(OUT or os.getcwd())
    os.makedirs(outdir, exist_ok=True)
    print("OUTDIR %s" % outdir)
    for i in range(SHOTS):
        loc, look, lens = cams[i % len(cams)]
        cam = camera(loc, look, lens)
        key = light("AREA", (loc[0] * 0.6, loc[1] - 1.6, loc[2] + 2.6), 110,
                    cols[i % len(cols)], size=4.0)
        t0 = time.time()
        sc.render.filepath = os.path.join(outdir, "shot%02d.png" % (i + 1))
        bpy.ops.render.render(write_still=True)
        print("SHOT %02d %.1fs -> %s" % (i + 1, time.time() - t0, sc.render.filepath))
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.objects.remove(key, do_unlink=True)
    print("PLATES_DONE %s %d" % (SCENE, SHOTS))


main()
