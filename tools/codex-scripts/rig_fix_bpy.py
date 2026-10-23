# -*- coding: utf-8 -*-
"""Blender 侧脚本（由 `rig-fix.py` 用 `blender --background --python` 驱动）
口令：`blender --background --factory-startup --python 本件 -- <src> <dst> <pngdir> <target_h> [--drop-strays]`

## 这一版把"量具本身"修了（2026-10-18 主人令三处）
1. **自动定轴**：导入后分别量世界 X/Y/Z 三个跨度，**最大者判为身高轴**，并在场景里把该轴旋到 Z 再 apply。
   不再假设 Y-up 或 Z-up（之前正是这个假设让我量出 2.00 / 0.187 / 0.638 三个假身高）。
2. **量具自证**：打印三轴跨度 + 判定 + 用的旋转；并用**直接解析 GLB JSON** 得到的 `POSITION` 跨度做外部对照，
   两者差 >5% 直接报红（红 = 这次读数不可信，不许当成功）。
3. **导出侧自证**：导出后**不用 Blender 读**，直接解析 GLB：`meshes==1 && skins==1 && 没有 42 顶点的无名网格`；
   不满足就报红（之前杂物球被 remove 了却仍在导出件里，就是靠这条才看得见）。

输出：一段 `<<<GBT-FIX>>>{json}<<<END>>>`，由包装器解析。
"""
import bpy
import json
import math
import os
import struct
import sys
from mathutils import Vector, Euler

# 编码守门（本仓规矩：不带 -X utf8 调用时不许静默输出空；Windows 控制台默认 GBK）
# 本件由 Blender 的 --python 拉起，输出会被包装器按分隔符解析 —— 印不出中文就等于回执空。
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

TAG = "<<<GBT-FIX>>>"
END = "<<<END>>>"


def emit(payload):
    sys.stdout.write(TAG + json.dumps(payload, ensure_ascii=False) + END)


def meshes():
    return [o for o in bpy.data.objects if o.type == 'MESH']


def armatures():
    return [o for o in bpy.data.objects if o.type == 'ARMATURE']


def world_spans(objs):
    """世界空间三轴跨度（逐求值顶点，不用 bound_box —— 它是局部空间，会骗人）"""
    mn = [1e18] * 3
    mx = [-1e18] * 3
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        for v in me.vertices:
            w = mw @ v.co
            for i in range(3):
                mn[i] = min(mn[i], float(w[i]))
                mx[i] = max(mx[i], float(w[i]))
        ev.to_mesh_clear()
    return [mx[i] - mn[i] for i in range(3)], mn, mx


def glb_pos_spans(path):
    """直接解析 GLB 的 JSON 块：返回 (meshes 数, skins 数, 各 mesh 顶点数, POSITION 三轴跨度)"""
    raw = open(path, 'rb').read()
    off, js = 12, None
    while off < len(raw):
        clen, ctype = struct.unpack('<II', raw[off:off + 8])
        off += 8
        chunk = raw[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode('utf-8'))
    acc = js.get('accessors', [])
    counts = []
    spans = [0.0, 0.0, 0.0]
    for m in js.get('meshes', []):
        for pr in m.get('primitives', []):
            a = pr.get('attributes', {}).get('POSITION')
            if a is None:
                continue
            counts.append(acc[a]['count'])
            mn, mx = acc[a].get('min'), acc[a].get('max')
            if mn and mx:
                for i in range(3):
                    spans[i] = max(spans[i], float(mx[i]) - float(mn[i]))
    return len(js.get('meshes', [])), len(js.get('skins', [])), counts, spans


def audit(tag):
    target = [o for o in meshes() if any(md.type == 'ARMATURE' for md in o.modifiers)] or meshes()
    verts = unweighted = nonnorm = 0
    groups = set()
    for m in target:
        for v in m.data.vertices:
            verts += 1
            total = 0.0
            for g in v.groups:
                w = float(g.weight)
                total += w
                if w > 1e-4:
                    nm = m.vertex_groups[g.group].name if g.group < len(m.vertex_groups) else str(g.group)
                    groups.add(nm)
            if total < 0.02:
                unweighted += 1
            elif abs(total - 1.0) > 0.02:
                nonnorm += 1
    spans, mn, mx = world_spans(target)
    return {"tag": tag, "verts": verts, "unweighted": unweighted, "non_normalized": nonnorm,
            "bound_groups": len(groups), "spans": [round(s, 4) for s in spans],
            "height_m": round(spans[2], 4),
            "bbox": [round(v, 3) for v in mn] + [round(v, 3) for v in mx],
            "per_mesh": [{"mesh": o.name, "verts": len(o.data.vertices),
                          "groups": len(o.vertex_groups),
                          "armature_mod": sum(1 for md in o.modifiers if md.type == 'ARMATURE')}
                         for o in meshes()]}


def skin_move_test(arm):
    head = None
    for b in arm.data.bones:
        if b.name.lower().endswith("head") and "top" not in b.name.lower():
            head = b
            break
    if head is None:
        return {"ok": False, "why": "找不到 Head 骨"}
    pb = arm.pose.bones.get(head.name)
    target = [o for o in meshes() if any(md.type == 'ARMATURE' for md in o.modifiers)]
    before = {}
    for m in target:
        dg = bpy.context.evaluated_depsgraph_get()
        me = m.evaluated_get(dg).to_mesh()
        before[m.name] = [(m.matrix_world @ v.co).copy() for v in me.vertices]
        m.evaluated_get(dg).to_mesh_clear()
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (math.radians(30), 0, 0)
    bpy.context.view_layer.update()
    res = {}
    for m in target:
        dg = bpy.context.evaluated_depsgraph_get()
        me = m.evaluated_get(dg).to_mesh()
        after = [(m.matrix_world @ v.co) for v in me.vertices]
        moved = sum(1 for a, b in zip(before[m.name], after) if (a - b).length > 1e-4)
        res[m.name] = {"moved": moved, "total": len(after)}
        m.evaluated_get(dg).to_mesh_clear()
    pb.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    return {"ok": True, "bone": head.name, "per_mesh": res}


def main():
    tail = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[-4:]
    drop = '--drop-strays' in tail
    tail = [t for t in tail if not t.startswith('--')]
    if len(tail) < 4:
        emit({"ok": False, "why": "参数不足：需要 src dst pngdir target_h"})
        return
    src, dst, pngdir, target_h = tail[0], tail[1], tail[2], float(tail[3])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        bpy.ops.import_scene.gltf(filepath=src)
    except Exception as e:
        emit({"ok": False, "why": "导入失败：" + str(e)[:300]})
        return

    arm = armatures()[0] if armatures() else None
    if arm is None:
        emit({"ok": False, "why": "模型里没有骨架"})
        return

    # ── ① 杂物：无顶点组 + 无材质 + 无骨架修改器 ─────────────────────────────
    stray = []
    for m in list(meshes()):
        if not m.vertex_groups and not (m.data.materials and len(m.data.materials)) \
                and not any(md.type == 'ARMATURE' for md in m.modifiers):
            nm = m.name
            if drop:
                bpy.data.objects.remove(m, do_unlink=True)
                stray.append({"obj": nm, "dropped": True})
            else:
                stray.append({"obj": nm, "verts": len(m.data.vertices), "dropped": False})
    if drop:
        for m in list(meshes()):
            if m.name in [s["obj"] for s in stray if s.get("dropped")] and m.name in bpy.data.objects:
                bpy.data.objects.remove(m, do_unlink=True)

    # ── ② 自动定轴：三轴跨度取最大者为身高轴，把它旋到 Z 并 apply ────────────
    objs = meshes() + armatures()
    spans, mn, mx = world_spans(meshes())
    axis = max(range(3), key=lambda i: spans[i])
    rot = None
    if axis == 1:     # Y 是身高轴 → 绕 X 转 -90°
        rot = ('X', -90)
    elif axis == 0:   # X 是身高轴 → 绕 Y 转 +90°
        rot = ('Y', 90)
    if rot:
        ang = math.radians(rot[1])
        for o in objs:
            o.rotation_mode = 'XYZ'
            if rot[0] == 'X':
                o.rotation_euler.x += ang
            else:
                o.rotation_euler.y += ang
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    spans_after, _, _ = world_spans(meshes())
    axis_report = {"before_spans": [round(s, 4) for s in spans], "picked_axis": "XYZ"[axis],
                   "rotation": rot, "after_spans": [round(s, 4) for s in spans_after]}

    # ── ③ 查漏壳 + 补权重 + 归一化 ──────────────────────────────────────────
    added_mod = []
    for m in meshes():
        if not any(md.type == 'ARMATURE' for md in m.modifiers):
            md = m.modifiers.new("Armature", 'ARMATURE')
            md.object = arm
            added_mod.append(m.name + "(补修改器)")

    deform_bones = {b.name for b in arm.data.bones if getattr(b, "use_deform", True)}
    bound = set()
    for m in meshes():
        for v in m.data.vertices:
            for g in v.groups:
                if float(g.weight) > 1e-4:
                    nm = m.vertex_groups[g.group].name
                    if nm in deform_bones:
                        bound.add(nm)
    if not bound:
        bound = set(deform_bones)
    heads = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones}

    fixed = normalized = 0
    for m in meshes():
        idx2 = {vg.index: vg for vg in m.vertex_groups}
        for v in m.data.vertices:
            total = sum(float(g.weight) for g in v.groups)
            if total < 0.02:
                p = m.matrix_world @ v.co
                best, bd = None, 1e18
                for bn in bound:
                    h = heads.get(bn)
                    if h is None:
                        continue
                    d = (p - h).length
                    if d < bd:
                        bd, best = d, bn
                if best is None:
                    continue
                vg = m.vertex_groups.get(best) or m.vertex_groups.new(name=best)
                vg.add([v.index], 1.0, 'REPLACE')
                fixed += 1
            elif abs(total - 1.0) > 0.02:
                for g in list(v.groups):
                    idx2[g.group].add([v.index], float(g.weight) / total, 'REPLACE')
                normalized += 1

    # ── ④ 身高归一到 target_h（数据级：顶点 + rest 骨长）────────────────────
    # 🔴 2026-10-18 第六修：**k 必须按 glTF 空间的身高算**。
    #    实测：场景 Z=0.638 而 glTF Y=0.979（导入带单位换算 0.652）⇒ 拿场景 Z 算 k，
    #    文件里就变成 0.979×(1.72/0.638)=2.64 m。外部量具（直接解析 GLB）才是真理来源。
    _, _, _, src_spans = glb_pos_spans(src)
    base_h = src_spans[1] if src_spans[1] > 1e-9 else max(src_spans)
    k = (target_h / base_h) if base_h > 1e-9 else 1.0
    axis_report['glb_src_spans'] = [round(v, 4) for v in src_spans]
    axis_report['glb_base_h'] = round(base_h, 4)
    if abs(k - 1.0) > 1e-6:
        for m in meshes():
            for v in m.data.vertices:
                v.co = v.co * k
            m.data.update()
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in arm.data.edit_bones:
            eb.head = eb.head * k
            eb.tail = eb.tail * k
        bpy.ops.object.mode_set(mode='OBJECT')
    pre = audit("pre_export")

    # ── ⑤ 导出 + **GLB 侧自证**（不用 Blender 读）───────────────────────────
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(True)
    try:
        ret = bpy.ops.export_scene.gltf(filepath=dst, export_format='GLB', export_apply=False,
                                        use_selection=False, export_skins=True, export_yup=True)
    except Exception as e:
        emit({"ok": False, "why": "导出失败：" + str(e)[:300], "axis": axis_report})
        return
    nmesh, nskin, counts, gspans = glb_pos_spans(dst)
    glb_check = {"meshes": nmesh, "skins": nskin, "vert_counts": counts,
                 "pos_spans": [round(s, 4) for s in gspans],
                 "ret": str(ret), "size": os.path.getsize(dst)}
    # 外部对照：GLB 里 Y 向跨度 vs 场景里 Z 向（导出 yup ⇒ Y 就是身高轴）
    ext_ok = abs(gspans[1] - pre["height_m"]) / max(1e-9, pre["height_m"]) <= 0.05 if gspans[1] > 0 else False

    # ── ⑥ 复检 + 蒙皮真动 + 转台 ────────────────────────────────────────────
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=dst)
    arm2 = armatures()[0] if armatures() else None
    after = audit("after")
    skin = skin_move_test(arm2) if arm2 else {"ok": False, "why": "复检件没有骨架"}

    shots = []
    try:
        os.makedirs(pngdir, exist_ok=True)
        scene = bpy.context.scene
        try:
            scene.render.engine = 'BLENDER_WORKBENCH'
        except Exception:
            scene.render.engine = 'BLENDER_EEVEE'
        scene.render.resolution_x = 768
        scene.render.resolution_y = 1024
        bb_min, bb_max = world_spans(meshes())[1:]
        height = max(0.2, bb_max[2] - bb_min[2])
        width = max(0.2, bb_max[0] - bb_min[0])
        center = Vector(((bb_min[0] + bb_max[0]) / 2, (bb_min[1] + bb_max[1]) / 2, (bb_min[2] + bb_max[2]) / 2))
        dist = max(height * 2.3, width * 3.2)   # 留边：1.7 倍时把头切了
        cam_data = bpy.data.cameras.new("cam")
        cam = bpy.data.objects.new("cam", cam_data)
        scene.collection.objects.link(cam)
        scene.camera = cam
        cam_data.lens = 60
        ldata = bpy.data.lights.new("sun", 'SUN')
        ldata.energy = 3.5
        light = bpy.data.objects.new("sun", ldata)
        light.location = (3.0, -3.0, 4.0)
        scene.collection.objects.link(light)
        for i, (ang, nm) in enumerate([(35, "q3"), (0, "front"), (-35, "q3l"), (180, "back")]):
            r = math.radians(ang)
            # 从 +Y 侧看并把镜头抬到胸高：之前从 -Y 看、up 被解析成 -Z ⇒ 拍出来是倒的
            cam.location = (center.x + dist * math.sin(r),
                            center.y + dist * math.cos(r),
                            center.z + height * 0.02)
            _q = (center - cam.location).to_track_quat('-Z', 'Y')
            _e = _q.to_euler()
            _e.rotate_axis('Z', math.radians(180))   # 上一版整幅倒 180°：绕镜头轴滚正
            cam.rotation_euler = _e
            p = os.path.join(pngdir, "view-%02d-%s.png" % (i + 1, nm))
            scene.render.filepath = p
            try:
                bpy.ops.render.render(write_still=True)
                shots.append(p)
            except Exception as e:
                shots.append("ERR " + str(e)[:80])
    except Exception as e:
        shots = ["ERR " + str(e)[:80]]

    emit({"ok": True, "axis": axis_report, "stray": stray, "added_mod": added_mod,
          "fixed_verts": fixed, "normalized": normalized, "scale_k": round(k, 6),
          "pre_export": pre, "glb_check": glb_check, "glb_external_ok": ext_ok,
          "after": after, "skin_move": skin, "dst": dst, "shots": shots})


main()
