# -*- coding: utf-8 -*-
"""obj2glb.py —— 外部 OBJ 资产 → GLB（给 render-shot / dh_pose 复用同一条渲染链）。

用途（2026-10-19 · Owner 选 B 路线「接入 CC0/CC-BY 专业成品」）：
CC0 底模（MakeHuman base.obj，19,158 顶点 / 18,486 四边面 / 带 UV）落地后，
先转成 GLB 才能走我们已有的渲染与判据链（render-shot 只吃 glb）。

用法：
    blender -b -P tools/digihuman/obj2glb.py -- --obj <in.obj> --out <out.glb>

判据（打印成一行机读回执）：
    <<<GBT-OBJ2GLB>>>{...}<<<END>>>
    含：顶点数 / 面数 / 是否带 UV / 尺寸 / 输出字节 / sha16
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name: str, default: str = "") -> str:
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS):
            return ARGS[i + 1]
    return default


def _keep_groups(ob, keep: set) -> int:
    """**清辅助几何**（MakeHuman base.obj 里除了 body，还塞了 helper-tights/skirt/hair/genital
    + 一堆 joint-* 小方块）：按 obj 的 `g <name>` 分组过滤，只留 keep 名单里的组。

    实测（2026-10-19）：139 组里 body 13,378 面，tights 2,650、skirt 684、hair 198、
    genital 182、眼球/牙/睫若干、joint-* 每个 6 面 —— 之前渲染出来的"长裙"就是 helper-skirt，
    头上那道"横带"是 helper-hair/tights。不清掉就绑骨 = 给衣服和辅助块绑骨。
    """
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    # obj 导入后，分组名在 vertex groups 里（bpy 以 group 为单位建了顶点组）
    names = {g.name for g in ob.vertex_groups}
    drop = [g for g in ob.vertex_groups if g.name not in keep]
    if not names:
        bm.free()
        return 0
    bm.free()
    for g in drop:
        ob.vertex_groups.remove(g)
    # 删掉不属于任何保留组的面
    keep_idx = {ob.vertex_groups[g].index for g in keep if g in ob.vertex_groups}
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    doomed = []
    for f in bm.faces:
        ks = set()
        for v in f.verts:
            for ge in v.link_edges:
                pass
        # 用顶点的 group 归属判断
        in_keep = False
        for v in f.verts:
            for g in v.groups if hasattr(v, "groups") else []:
                if g.group in keep_idx:
                    in_keep = True
                    break
            if in_keep:
                break
        if not in_keep:
            doomed.append(f)
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    return len(doomed)


def _skin_material(ob) -> str:
    """配皮肤材质（**说明**：MakeHuman 官方仓库的 data/textures 里只有 texture_notfound.png，
    **没有 CC0 皮肤贴图**；它的皮肤是"材质参数"不是贴图。所以这里用 Principled + 次表面散射
    现做一套 —— 全部由我们生成，不引入任何来源可疑的图片，也不会有 UV 接缝。
    """
    me = ob.data
    mat = bpy.data.materials.get("GBT_Skin") or bpy.data.materials.new("GBT_Skin")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.72, 0.55, 0.45, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.42
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.28
        bsdf.inputs["Subsurface Radius"].default_value = (0.12, 0.05, 0.03)
        bsdf.inputs["Subsurface Scale"].default_value = 0.06
    elif "Subsurface" in bsdf.inputs:
        bsdf.inputs["Subsurface"].default_value = 0.28
    # 一点噪声当毛孔/起伏（不引外部贴图）
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 380.0
    tex.inputs["Detail"].default_value = 2.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    me.materials.clear()
    me.materials.append(mat)
    return mat.name


def _eye_material(ob) -> str:
    """眼球材质：白巩膜 + 深色虹膜（用球形渐变近似，不引外部图）。"""
    me = ob.data
    mat = bpy.data.materials.get("GBT_Eye") or bpy.data.materials.new("GBT_Eye")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.92, 0.90, 0.88, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.15
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    # 🔴 2026-10-19 修：这里原来是 `me.materials.clear()` —— 把上一步挂好的**皮肤材质槽清掉了**，
    #    只剩这张近白的眼球材质 ⇒ 整个人渲染出来是灰的（我盯着图看了三遍才发现是槽被清）。
    #    现在改成**追加**：槽 0 = 皮肤，槽 1 = 眼球。
    if mat.name not in [m.name for m in me.materials]:
        me.materials.append(mat)
    return mat.name


def _filter_obj(src: Path, keep: set, out_obj: Path) -> dict:
    """**按 obj 的 g/o 分组裁件**（自己解析，不赌导入器认不认 `g`）。

    留痕（2026-10-19 实测）：Blender 的 `wm.obj_import` 对 `g` 行**不建顶点组**
    （实测 `groups_before: 0`），所以我第一版"按顶点组过滤"是空转、`dropped_faces: 0`，
    渲染出来那条"长裙"（helper-skirt 684 面）和头上的"横带"（helper-hair/tights）还在。
    这里改成：先按分组把 obj 拆干净（只留 keep 里的组），重新编号 v/vt 再写临时 obj。
    """
    v, vt, vn, faces = [], [], [], []
    cur, dropped = None, 0
    kept_faces = 0
    for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            v.append(line)
        elif line.startswith("vt "):
            vt.append(line)
        elif line.startswith("vn "):
            vn.append(line)
        elif line.startswith(("g ", "o ")):
            cur = line[2:].strip()
        elif line.startswith("f "):
            if keep and cur not in keep:
                dropped += 1
                continue
            kept_faces += 1
            faces.append(line)
    # 统计真正用到的顶点/UV 索引 → 重编号
    used_v, used_vt = {}, {}
    new_faces = []
    for line in faces:
        parts = line.split()[1:]
        out = []
        for tok in parts:
            comps = tok.split("/")
            vi = int(comps[0])
            if vi < 0:
                vi = len(v) + vi + 1
            used_v.setdefault(vi, len(used_v) + 1)
            s = str(used_v[vi])
            if len(comps) > 1 and comps[1]:
                ti = int(comps[1])
                if ti < 0:
                    ti = len(vt) + ti + 1
                used_vt.setdefault(ti, len(used_vt) + 1)
                s += "/" + str(used_vt[ti])
            out.append(s)
        new_faces.append("f " + " ".join(out))
    out_obj.parent.mkdir(parents=True, exist_ok=True)
    with out_obj.open("w", encoding="utf-8") as fh:
        for i in sorted(used_v):
            fh.write(v[i - 1] + "\n")
        for i in sorted(used_vt):
            fh.write(vt[i - 1] + "\n")
        fh.write("g %s\n" % ",".join(sorted(keep)) if keep else "")
        fh.write("\n".join(new_faces) + "\n")
    return {"kept_faces": kept_faces, "dropped_faces": dropped,
            "kept_verts": len(used_v), "kept_uvs": len(used_vt),
            "keep": sorted(keep), "tmp_obj": str(out_obj)}


def _face_keep_ranges(src: Path, keep: set) -> tuple:
    """按 obj 的 g/o 分组算出**要保留的面序号区间**（不改 obj，不重编号）。

    留痕（2026-10-19 踩的两次）：
      ① 第一版按"顶点组"过滤 —— Blender 的 `wm.obj_import` **不建** `g` 顶点组（groups_before: 0）
         ⇒ 空转，长裙/横带都还在；
      ② 第二版自己重写 obj 并重编号 v/vt —— 出来的是一团尖锥（重编号写错），
         宁可放弃这条路也不赌手写解析。
    现在这版：**导入整份 obj（导入器本身是对的），再按面序号区间删**。区间从 g/o 分组数出来。
    """
    idx = 0
    cur = None
    keep_idx = []
    all_groups = {}
    for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(("g ", "o ")):
            cur = line[2:].strip()
        elif line.startswith("f "):
            all_groups[cur] = all_groups.get(cur, 0) + 1
            if cur in keep:
                keep_idx.append(idx)
            idx += 1
    return keep_idx, all_groups


def _delete_faces_except(ob, keep_idx: list) -> int:
    """按面序号保留 keep_idx 里的面，其余删掉（顶点/边由 bmesh 自行清理）。"""
    import bmesh
    keep = set(keep_idx)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    doomed = [f for f in bm.faces if f.index not in keep]
    n = len(doomed)
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return n


def main() -> int:
    src = Path(arg("--obj"))
    dst = Path(arg("--out", "outputs/makehuman/base.glb"))
    if not src.is_file():
        print("读不到 obj：%s" % src)
        return 2

    bpy.ops.wm.read_factory_settings(use_empty=True)
    # 分组区间（只用于"导完之后按面序号删"，导入本身不碰原文件）
    keep_arg0 = arg("--keep", "body,helper-l-eye,helper-r-eye")
    keep0 = {x.strip() for x in keep_arg0.split(",") if x.strip()}
    clean_stats = {}
    import_src = src
    bpy.ops.wm.obj_import(filepath=str(import_src), forward_axis="NEGATIVE_Z", up_axis="Y")

    mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not mesh_objs:
        print("导入后没有 MESH 对象")
        return 3
    # 多个对象就合并成一个（GLB 里单网格更好绑骨/更好判）
    if len(mesh_objs) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for o in mesh_objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = mesh_objs[0]
        bpy.ops.object.join()
    ob = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]

    me = ob.data
    dims = [round(v, 4) for v in ob.dimensions]
    has_uv = bool(me.uv_layers)
    # 平滑着色（底模本来是光滑面，别让渲染看起来像多面体）
    bpy.ops.object.shade_smooth()
    # 统一缩放到 1.72 m 身高（本仓口径：身高 1.720±0.02，**在文件空间量**）
    target_h = 1.72
    cur_h = max(dims)
    if cur_h > 0:
        s = target_h / cur_h
        ob.scale = (s, s, s)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    dims2 = [round(v, 4) for v in ob.dimensions]

    # ── 清辅助几何 + 配材质（2026-10-19 · Owner 定的顺序：先清、再配皮）──
    keep_arg = arg("--keep", "body,helper-l-eye,helper-r-eye")
    keep = {x.strip() for x in keep_arg.split(",") if x.strip()}
    faces_before = len(me.polygons)
    keep_idx, all_groups = _face_keep_ranges(src, keep) if keep else ([], {})
    dropped = _delete_faces_except(ob, keep_idx) if keep_idx else 0
    me = ob.data
    # 清完再按"合身"重算尺寸（原来 dims2 是清之前量的）
    dims_clean = [round(v, 4) for v in ob.dimensions]
    mat_skin = _skin_material(ob)
    mat_eye = _eye_material(ob)
    # 眼球面用第二个材质槽（按顶点组归属判断）
    eye_idx = {ob.vertex_groups[g].index for g in ("helper-l-eye", "helper-r-eye")
               if g in ob.vertex_groups}
    if eye_idx:
        for poly in me.polygons:
            if any(any(g.group in eye_idx for g in me.vertices[vi].groups)
                   for vi in poly.vertices):
                poly.material_index = 1

    dst.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=str(dst), export_format="GLB",
                              use_selection=True, export_apply=True)

    data = dst.read_bytes()
    rec = {"ok": True, "src": str(src), "out": str(dst),
           "verts": len(me.vertices), "faces": len(me.polygons),
           "quads": sum(1 for p in me.polygons if len(p.vertices) == 4),
           "has_uv": has_uv, "uv_layers": [l.name for l in me.uv_layers],
           "dims_before": dims, "dims_after": dims_clean,
           "keep": sorted(keep), "keep_faces": len(keep_idx),
           "groups_in_obj": len(all_groups),
           "faces_before": faces_before, "dropped_faces": dropped,
           "materials": [mat_skin, mat_eye],
           "bytes": len(data), "sha16": hashlib.sha256(data).hexdigest()[:16]}
    print("<<<GBT-OBJ2GLB>>>%s<<<END>>>" % json.dumps(rec, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
