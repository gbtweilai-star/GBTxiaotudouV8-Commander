# -*- coding: utf-8 -*-
"""look.py — 只看不动：把 GLB 摆到镜头前拍全身 + 脸特写，回执 JSON。
用法:
  blender -b -P tools/digihuman/look.py -- --glb <abs.glb> --outdir <abs dir> [--tag x] [--pose]
"""
import bpy, sys, os, json, math
from mathutils import Vector

def argv_after():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []

def getarg(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default

args = argv_after()
glb = os.path.abspath(getarg(args, '--glb'))
outdir = os.path.abspath(getarg(args, '--outdir'))
tag = getarg(args, '--tag', 'look')
os.makedirs(outdir, exist_ok=True)
rec = {'ok': False, 'glb': glb, 'outdir': outdir, 'shots': []}

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=glb)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
rec['meshes'] = [o.name for o in meshes]
rec['armatures'] = [(o.name, len(o.data.bones)) for o in arms]
rec['actions'] = [a.name for a in bpy.data.actions]
tris = 0
verts = 0
for o in meshes:
    verts += len(o.data.vertices)
    tris += sum(max(1, len(p.vertices) - 2) for p in o.data.polygons)
rec['verts'] = verts
rec['tris'] = tris

# 世界包围盒
lo = Vector((1e9, 1e9, 1e9)); hi = Vector((-1e9, -1e9, -1e9))
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
size = hi - lo
ctr = (hi + lo) / 2
rec['bbox'] = {'min': [round(v, 4) for v in lo], 'max': [round(v, 4) for v in hi],
               'size': [round(v, 4) for v in size]}
H = size.z or 1.0

# 材质/贴图
rec['materials'] = []
for o in meshes:
    for m in o.data.materials:
        if not m:
            continue
        d = {'name': m.name, 'images': []}
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image:
                    d['images'].append({'node': n.name, 'image': n.image.name,
                                        'size': list(n.image.size),
                                        'linked_to': [l.to_socket.name for l in n.outputs[0].links]})
        rec['materials'].append(d)

# 环境
world = bpy.data.worlds.new('W')
sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs[0].default_value = (0.055, 0.058, 0.065, 1)
bg.inputs[1].default_value = 1.0

def add_area(name, loc, energy, size_, rot):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size_
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = rot
    sc.collection.objects.link(ob)
    return ob

Z = H * 0.62
add_area('key', (ctr.x - 1.6 * H, ctr.y - 2.4 * H, ctr.z + 1.0 * H), 900 * H * H, 2.2 * H, (math.radians(64), 0, math.radians(-34)))
add_area('fill', (ctr.x + 2.4 * H, ctr.y - 1.9 * H, ctr.z + 0.5 * H), 380 * H * H, 3.0 * H, (math.radians(78), 0, math.radians(52)))
add_area('rim', (ctr.x + 0.6 * H, ctr.y + 2.6 * H, ctr.z + 1.2 * H), 700 * H * H, 2.0 * H, (math.radians(108), 0, math.radians(168)))

cam_d = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam_d.type = 'ORTHO'

sc.render.engine = 'BLENDER_EEVEE_NEXT'
try:
    sc.eevee.taa_render_samples = 32
except Exception:
    pass
sc.render.film_transparent = False
for vt in ('AgX', 'Filmic', 'Standard'):
    try:
        sc.view_settings.view_transform = vt
        sc.view_settings.look = 'None'
        rec['view_transform'] = vt
        break
    except Exception:
        continue

def shoot(name, target, ortho_scale, res, rx=90.0, rz=0.0, dist=None):
    cam.location = Vector(target) + Vector((0, -3.0 * H, 0))
    cam.rotation_euler = (math.radians(rx), 0, math.radians(rz))
    cam_d.ortho_scale = ortho_scale
    sc.render.resolution_x = res[0]
    sc.render.resolution_y = res[1]
    sc.render.resolution_percentage = 100
    p = os.path.join(outdir, '%s-%s.png' % (tag, name))
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    sz = os.path.getsize(p) if os.path.exists(p) else -1
    rec['shots'].append({'shot': name, 'path': p, 'bytes': sz,
                         'res': list(res), 'ortho_scale': round(ortho_scale, 4)})
    return sz

# 全身正面
shoot('front', (ctr.x, ctr.y, ctr.z), max(size.x, size.z) * 1.06, (760, 1240))
# 脸特写：头 = 身高顶部 15%
head_c = Vector((ctr.x, ctr.y, hi.z - H * 0.078))
shoot('face', head_c, H * 0.145, (900, 900))
# 3/4 侧
cam.location = Vector((ctr.x, ctr.y, ctr.z)) + Vector((2.1 * H, -2.1 * H, 0.25 * H))
cam.rotation_euler = (math.radians(84), 0, math.radians(45))
cam_d.ortho_scale = max(size.x, size.z) * 1.06
sc.render.resolution_x, sc.render.resolution_y = 760, 1240
p = os.path.join(outdir, '%s-side.png' % tag)
sc.render.filepath = p
bpy.ops.render.render(write_still=True)
rec['shots'].append({'shot': 'side', 'path': p, 'bytes': os.path.getsize(p) if os.path.exists(p) else -1})

rec['ok'] = all(s['bytes'] > 2000 for s in rec['shots'])
print('<<<GBT-LOOK>>>')
print(json.dumps(rec, ensure_ascii=False, indent=1))
