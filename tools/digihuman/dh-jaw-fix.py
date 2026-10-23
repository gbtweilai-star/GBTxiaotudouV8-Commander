# -*- coding: utf-8 -*-
"""重绑下颌权重（修 2026-10-21 那个"张嘴把眼睛挤闭"的错）。

判据不是凭记忆写的下限，而是**从网格中线纵剖面读出来的**（tools/digihuman/dh-face-profile.py）：
    z≈1.470–1.520 下巴 · 1.520–1.556 唇 · 1.556–1.604 鼻 · 1.614–1.700 眼/眉
    ⇒ 下颌只能吃到 **z ≤ 1.556（唇线）**，往下到下巴满权重；鼻子/眼睛一律 0。
旧版权重落在 1.5584–1.6274（鼻子→眼睛下缘）、且平均权重只有 0.307 ⇒ 上脸被拽、眼睛被挤闭。

用法：
  blender -b --python dh-jaw-fix.py                 # 只测量 + 渲染对照图（不写盘）
  blender -b --python dh-jaw-fix.py -- --apply      # 写 state/hd/jaw-fix/dh-v4-jaw.glb
"""
import math
import os
import sys

import bpy
from mathutils import Euler

GLB = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets\dh-v3-jaw.glb"
OUTDIR = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\hd\jaw-fix"
OUTGLB = os.path.join(OUTDIR, "dh-v4-jaw.glb")

# ── 从纵剖面读出来的边界（单位 m，Blender Z-up）────────────────────────────────
Z_CHIN_BOTTOM = 1.470   # 再往下是脖子，不许动
Z_FULL = 1.505          # 这以下满权重（下巴本体）
Z_LIP = 1.556           # 唇线：这以上一律 0（鼻子/眼睛绝不吃到）
Y_FRONT = -0.040        # 只要脸前面
X_MAX = 0.055           # 半张脸的宽度上限
X_FADE = 0.045          # 到 X_MAX 之间淡出（别把腮帮子一起拽）

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
APPLY = "--apply" in argv
os.makedirs(OUTDIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
mesh = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
print("[mesh] %s verts=%d" % (mesh.name, len(mesh.data.vertices)))

def group_by_suffix(suffix):
    for g in mesh.vertex_groups:
        if g.name.lower().endswith(suffix):
            return g
    return None


g_head = group_by_suffix("head")
g_jaw = group_by_suffix("jaw")
if not g_head or not g_jaw:
    raise SystemExit("缺 Head/Jaw 顶点组：%s" % [g.name for g in mesh.vertex_groups])

head_idx, jaw_idx = g_head.index, g_jaw.index


def wof(v, gi):
    for ge in v.groups:
        if ge.group == gi:
            return ge.weight
    return 0.0


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ── 1. 清掉旧的 Jaw 权重（改回 Head，保持归一）─────────────────────────────────
old = []
mesh.vertex_groups.active_index = jaw_idx
for v in mesh.data.vertices:
    w = wof(v, jaw_idx)
    if w > 0.0005:
        old.append((v.index, round(v.co.z, 4), round(v.co.y, 4), round(w, 3)))
print("[旧权重] %d 个顶点，z %.4f..%.4f" % (
    len(old), min(r[1] for r in old) if old else 0, max(r[1] for r in old) if old else 0))

for v in mesh.data.vertices:
    w = wof(v, jaw_idx)
    if w > 0.0005:
        g_jaw.remove([v.index])
        hw = wof(v, head_idx)
        g_head.add([v.index], hw + w, "REPLACE")

# ── 2. 按剖面重新分配 ────────────────────────────────────────────────────────
picked = []
for v in mesh.data.vertices:
    x, y, z = v.co
    if not (Z_CHIN_BOTTOM <= z <= Z_LIP):
        continue
    if y > Y_FRONT or abs(x) > X_MAX:
        continue
    hw = wof(v, head_idx)
    if hw < 0.2:            # 不是头皮的顶点（脖子/衣服）不要
        continue
    # 高度方向：唇线处 0 → 下巴底处 1（整段平滑过渡，**不许有硬边界**：
    # 硬边界会在腮帮子上割出一道台阶，实测看图就是这么坏的）
    tz = smooth((Z_LIP - z) / max(1e-6, (Z_LIP - Z_CHIN_BOTTOM)))
    # 左右方向：X_FADE 内 1 → X_MAX 处 0
    ax = abs(x)
    tx = 1.0 if ax <= X_FADE else max(0.0, (X_MAX - ax) / max(1e-6, (X_MAX - X_FADE)))
    w = round(tz * tx, 4)
    if w <= 0.004:
        continue
    picked.append((v.index, round(x, 4), round(y, 4), round(z, 4), w))

for idx, x, y, z, w in picked:
    g_jaw.add([idx], w, "REPLACE")
    # 同步把 Head 权重降下来（总权重保持 1，否则会多出一份影响、脸被拉亮/拉薄）
    hw = wof(mesh.data.vertices[idx], head_idx)
    g_head.add([idx], max(0.0, hw * (1.0 - w)), "REPLACE")

zs = [p[3] for p in picked]
ws = [p[4] for p in picked]
print("[新权重] %d 个顶点  z %.4f..%.4f  w %.3f..%.3f 均值 %.3f" % (
    len(picked), min(zs), max(zs), min(ws), max(ws), sum(ws) / len(ws)))
bins = {}
for p in picked:
    bins.setdefault(round(p[3], 3), 0)
    bins[round(p[3], 3)] += 1
print("[新 z 分带] %s" % dict(sorted(bins.items())))
print("[自检] 落在眼睛区(z>=1.60)的顶点数 = %d（必须 0）" % sum(1 for p in picked if p[3] >= 1.60))

# ── 3. 渲染对照（闭口 vs 张口）───────────────────────────────────────────────
def setup_render():
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = 720
    sc.render.resolution_y = 720
    sc.render.film_transparent = False
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 85
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (0.01, -0.75, 1.60)     # 脸正前方（角色朝 -Y）
    cam.rotation_euler = Euler((math.radians(90), 0, 0), "XYZ")
    sc.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 4.0
    sun.rotation_euler = Euler((math.radians(50), 0, math.radians(20)), "XYZ")
    bpy.context.collection.objects.link(sun)
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "AREA"))
    fill.data.energy = 60
    fill.location = (-0.6, -0.6, 1.5)
    fill.rotation_euler = Euler((math.radians(75), 0, math.radians(-45)), "XYZ")
    bpy.context.collection.objects.link(fill)
    sc.world = bpy.data.worlds.new("w")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.02, 0.03, 1)


setup_render()
jaw_bone = None
for b in arm.data.bones:
    if b.name.lower().endswith("jaw"):
        jaw_bone = b
print("[骨] %s head=%s" % (jaw_bone.name, tuple(round(v, 4) for v in jaw_bone.head_local)))
pb = arm.pose.bones[jaw_bone.name]
pb.rotation_mode = "XYZ"

shots = []
for tag, ang in (("closed", 0.0), ("open8", -8.0), ("open16", -16.0)):
    pb.rotation_euler = Euler((0, math.radians(ang), 0), "XYZ")
    bpy.context.view_layer.update()
    p = os.path.join(OUTDIR, "blender-jaw-%s.png" % tag)
    bpy.context.scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    shots.append(p)
    print("[渲染] %s  角度 %.1f" % (p, ang))
pb.rotation_euler = Euler((0, 0, 0), "XYZ")

if APPLY:
    bpy.ops.export_scene.gltf(filepath=OUTGLB, export_format="GLB",
                              export_animations=True, export_skins=True, use_selection=False)
    print("[导出] %s  %d 字节" % (OUTGLB, os.path.getsize(OUTGLB)))
else:
    print("[导出] 跳过（没给 --apply）")
print("[图] %s" % shots)
