# -*- coding: utf-8 -*-
"""脸部中线纵剖面：每 2mm 高度带上「最靠前（最小 y）」的表面点，用来**读**出嘴唇/下巴在哪。
Blender 无头运行。目的：不再凭记忆写 lip_z（上次凭记忆写 1.5928 ⇒ 把鼻子以上都算进下颌）。
"""
import bpy

GLB = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets\dh-v3-jaw.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
mesh = max([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))

CENTER = 0.015      # |x| 取中线附近 ±1.5cm
FRONT = -0.02       # 只要脸前面的点
lo, hi, step = 1.470, 1.680, 0.002

bands = {}
for v in mesh.data.vertices:
    x, y, z = v.co
    if abs(x) > CENTER or y > FRONT:
        continue
    k = round((z - lo) / step)
    zk = round(lo + k * step, 3)
    cur = bands.get(zk)
    if cur is None or y < cur[0]:
        bands[zk] = (y, x, z)

print("[中线纵剖面] z → 最靠前的 y（越小越凸出）")
prev = None
for z in sorted(bands):
    y, x, zz = bands[z]
    mark = ""
    if prev is not None:
        d = y - prev            # >0 表示往里收（凹），<0 表示往外凸
        if d > 0.004:
            mark = "  ← 往内收(凹)"
        elif d < -0.004:
            mark = "  ← 往外凸"
    print("  z=%.3f  y=%.4f  %s" % (z, y, mark))
    prev = y
