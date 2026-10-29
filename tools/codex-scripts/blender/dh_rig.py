# -*- coding: utf-8 -*-
"""数字人 · 绑骨 + 全肢体动作 + 导出（Blender 4.2 headless）

用法（Windows）：
  "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.EXE" --background \
      --python tools/codex-scripts/blender/dh_rig.py -- [选项]
选项：
  --glb <路径>   --out <目录>   --target-faces <n>   --ratio <r>
  --stages rig,export,render    --reuse-blend    --render-frames <n>   --res WxH

🔴 纪律（对应主人令 2026-10-08）
 1) 输入是**静态网格**（Tripo 导出，skins/animations 皆 None）⇒ 骨架从零建。
 2) 空闲物理内存 < 2.5GB ⇒ **必须**在抽稀代理上建骨+做动作+验证；台账/文档写明
    "全精度蒙皮未跑（因为内存，不是因为做完了）"。
 3) 骨架**左右对称**：只实测一侧（自然下垂那条臂 / 腿），另一侧**镜像**得到，
    并把左右骨长/镜像夹角全部量出来供判据复算。
 4) "真在动"以**读数**为准：逐帧记关节世界角 + 四个末端骨 tail 世界坐标 +
    抽样顶点形变位移 → trace.json，供 dh-rig-check.py 独立复核。
 5) 不许假绿：失败原样写进报告，不吞异常。

📐 坐标口径（**实测**，不是猜的）
  glTF 导入后 Blender 把 Y-up 换成 Z-up（导入件 matrix_world = 单位阵，现读确认）：
      Blender X = glTF X   （横向）
      Blender Y = -glTF Z  （前后，角色面朝 Blender -Y）
      Blender Z = glTF Y   （身高轴）
  脚本内一切"身高比例"都作用在 **Z**，前后在 **Y**。
"""
import argparse
import ctypes
import json
import math
import os
import struct
import sys
import time
import traceback

WS = r"C:\Users\ADMIN\Desktop\GBT小土豆V8"
DEFAULT_GLB = os.path.join(os.path.expanduser("~"), "Downloads",
                           "futuristic cosplay outfit 3d model.glb")
DEFAULT_OUT = os.path.join(WS, "projects", "digital-human", "out")

AX_LAT, AX_DEP, AX_UP = 0, 1, 2          # Blender: X 横向 / Y 前后 / Z 身高
UP = (0.0, 0.0, 1.0)
FPS = 24

# 人形解剖比例（以模型自身身高 H 为单位；Tripo 任意尺度，不套 cm）
FR = {"hip": 0.5300, "knee": 0.2850, "ankle": 0.0390, "toe": 0.0180,
      "spine": 0.6000, "chest": 0.7200, "neck": 0.8550, "head0": 0.8950,
      "shoulder": 0.8200, "clav": 0.8420}
# 肢体分段（自称/自髋起算的弧长比例，用于沿实测测地路径放关节）
ARM_FRAC = {"elbow": 0.186 / 0.440, "wrist": (0.186 + 0.146) / 0.440}
LEG_FRAC = {"ankle": 0.152 / 0.643, "knee": (0.152 + 0.246) / 0.643,
            "hip": (0.152 + 0.246 + 0.245) / 0.643}

SPINE_BONES = ["hips", "spine", "chest", "neck", "head"]
ARM_BONES = ["shoulder", "upper_arm", "forearm", "hand"]
LEG_BONES = ["thigh", "shin", "foot"]
ALL_BONES = SPINE_BONES + [b + "_L" for b in ARM_BONES] + [b + "_R" for b in ARM_BONES] \
    + [b + "_L" for b in LEG_BONES] + [b + "_R" for b in LEG_BONES]
END_KEYS = ["hand_L", "hand_R", "foot_L", "foot_R"]
BONE_PARENT = {"hips": None, "spine": "hips", "chest": "spine", "neck": "chest", "head": "neck"}
for _lg in ("L", "R"):
    BONE_PARENT["shoulder_" + _lg] = "chest"
    BONE_PARENT["upper_arm_" + _lg] = "shoulder_" + _lg
    BONE_PARENT["forearm_" + _lg] = "upper_arm_" + _lg
    BONE_PARENT["hand_" + _lg] = "forearm_" + _lg
    BONE_PARENT["thigh_" + _lg] = "hips"
    BONE_PARENT["shin_" + _lg] = "thigh_" + _lg
    BONE_PARENT["foot_" + _lg] = "shin_" + _lg

ACTIONS = [
    ("01_呼吸",    48, "胸/肩微起伏 + 骨盆重心左右漂 + 双脚轮流提踵"),
    ("02_打招呼",  48, "抬**左**臂挥手（肩带-上臂-前臂-腕联动；右臂受壳层限制只给≤12°）+ 重心移右腿（右膝下沉、右脚碾转）+ 左脚离地"),
    ("03_走两步",  48, "髋-腿-脚迈步（双脚交替离地）+ 反向摆臂"),
    ("04_转身",    48, "髋/脊/头分级旋转（55°/18°/+9°/+12°）+ 双脚原地碾转"),
    ("05_蹲起",    56, "髋-膝-踝三关节联动下沉 + 提踵 + 起身"),
    ("06_伸懒腰",  56, "左臂上举（右臂受壳层限制←14°）+ 脊/胸/颈/头逐级后仰 + 双脚提踵"),
]
FRAME_STEP = 2          # 每 2 帧一个关键帧（更密 ⇒ 曲线更平、无抖动混叠）


# ------------------------------------------------------------------ 基础设施
def mem_mb():
    class MEMSTAT(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEMSTAT(); m.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return round(m.ullAvailPhys / 1048576.0, 1), round(m.ullTotalPhys / 1048576.0, 1)


def log(msg):
    print("[dh_rig] " + str(msg), flush=True)


class MemTrail(object):
    def __init__(self):
        self.rows = []

    def snap(self, stage):
        a, t = mem_mb()
        self.rows.append({"stage": stage, "avail_mb": a, "total_mb": t,
                          "t": time.strftime("%Y-%m-%d %H:%M:%S")})
        log("MEM %-24s avail=%.1f MB / total=%.1f MB" % (stage, a, t))
        return a


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default=DEFAULT_GLB)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--ratio", type=float, default=None)
    ap.add_argument("--target-faces", type=int, default=180000)
    ap.add_argument("--stages", default="rig,export,render")
    ap.add_argument("--reuse-blend", action="store_true")
    ap.add_argument("--render-frames", type=int, default=10)
    ap.add_argument("--res", default="640x800")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--hd", action="store_true", help="动作帧走高清档 1080x1350")
    ap.add_argument("--hero", action="store_true", help="另出英雄静帧(正面/3-4侧/面部特写)")
    ap.add_argument("--hero-res", default="1536x1920")
    ap.add_argument("--samples", type=int, default=0, help="0=按引擎取默认")
    ap.add_argument("--engine", default="", help="强制引擎：CYCLES / BLENDER_EEVEE_NEXT")
    ap.add_argument("--legacy-look", action="store_true", help="复刻旧档灯光/正交机位(用于同帧 before/after)")
    ap.add_argument("--diag", action="store_true", help="另出诊断帧：静置姿势/法线开关/髋部放大")
    a = ap.parse_args(argv)
    if a.no_render:
        a.stages = "rig,export"
    a.stages = [s.strip() for s in a.stages.split(",") if s.strip()]
    return a


def split_skin_material(mesh_obj, report):
    """皮肤单开一份材质：basecolor 缩到 512² 后按面 UV 中心采样分类。
    （4096² 全读要 ~268MB，内存不允许；512² 副本只占 4MB）
    幂等：已经有 DH_Skin 就跳过。"""
    import bpy
    import numpy as np
    for m in bpy.data.materials:
        if m.name.startswith("DH_Skin"):
            report.setdefault("skin_material", {})["already"] = True
            return 0
    src = None
    for m in bpy.data.materials:
        if not m.use_nodes or m.name.startswith("DH_"):
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and n.image.colorspace_settings.name == "sRGB":
                src = m
                break
        if src:
            break
    if src is None:
        return 0
    me = mesh_obj.data
    if not len(me.materials) or me.uv_layers.active is None:
        return 0
    nface = len(me.polygons)
    img = None
    for n in src.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and n.image.colorspace_settings.name == "sRGB":
            img = n.image
            break
    # 🔴 内存纪律：4096² 的 float 缓冲是 268MB，`img.copy()` 会再吃一份 ⇒ 在空闲
    #    仅 ~0.3GB 的机器上直接把渲染卡死（实测：链跑 10 分钟没动静）。
    #    改成"就地把贴图缩到 512² 采样，读完立即 reload() 从打包数据恢复原分辨率"，
    #    峰值只多 4MB。
    orig_size = tuple(img.size)
    img.scale(512, 512)
    buf = np.empty(512 * 512 * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    px = buf.reshape(512, 512, 4)
    try:
        img.reload()
    except Exception as _e:
        log("贴图 reload 失败: %r" % (_e,))
    if tuple(img.size) != orig_size:
        log("🔴 贴图未能恢复原分辨率（%s → %s），放弃材质分离以免降质"
            % (orig_size, tuple(img.size)))
        del buf, px
        return 0
    uvd = me.uv_layers.active.data
    skin_mask = np.zeros(nface, dtype=bool)
    for i, poly in enumerate(me.polygons):
        us = vs = 0.0
        for li in poly.loop_indices:
            us += uvd[li].uv[0]
            vs += uvd[li].uv[1]
        us /= poly.loop_total
        vs /= poly.loop_total
        xi = int(min(511, max(0, (us % 1.0) * 512)))
        yi = int(min(511, max(0, (vs % 1.0) * 512)))
        r, g, b = float(px[yi, xi, 0]), float(px[yi, xi, 1]), float(px[yi, xi, 2])
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        skin_mask[i] = (lum > 0.52) and (0.05 < (r - b) < 0.30) and ((g - b) < 0.10)
    skinmat = src.copy()
    skinmat.name = "DH_Skin"
    sb = None
    for n in skinmat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            sb = n
    SK = {"Roughness": 0.62, "Specular IOR Level": 0.22, "Coat Weight": 0.0, "Subsurface Weight": 0.14}
    if sb is not None:
        for k, v in SK.items():
            if k in sb.inputs:
                sb.inputs[k].default_value = v
        if "Subsurface Radius" in sb.inputs:
            sb.inputs["Subsurface Radius"].default_value = (0.008, 0.004, 0.002)
    me.materials.append(skinmat)
    sidx = len(me.materials) - 1
    nsk = 0
    for i, poly in enumerate(me.polygons):
        if skin_mask[i]:
            poly.material_index = sidx
            nsk += 1
    me.update()
    report["skin_material"] = {
        "method": "basecolor 缩到 512² 后按面 UV 中心采样分类（亮>0.52 且 R-B∈(0.05,0.30) 且 G-B<0.10）",
        "texture": img.name, "full_res": list(img.size), "sample_res": [512, 512],
        "faces_total": nface, "faces_skin": int(nsk), "skin_ratio": round(nsk / float(nface), 5),
        "skin_params": dict(SK, **{"Subsurface Radius": [0.008, 0.004, 0.002],
                                   "note": "皮肤：降高光/去清漆/加次表面 ⇒ 治「抹了油」"}),
        "leather_params": {"Roughness": 0.42, "Specular IOR Level": 0.50, "Coat Weight": 0.12,
                           "Coat Roughness": 0.25, "note": "皮革/头发：缎面而非湿塑料，清漆 0.30→0.12"}}
    log("材质分离：皮肤面 %d/%d (%.2f%%) → DH_Skin %s" % (nsk, nface, 100.0 * nsk / nface, SK))
    return nsk


def write_report(out_root, report):
    """**合并不覆盖**：只跑渲染的阶段不要把绑骨/导出段擦成空。"""
    os.makedirs(out_root, exist_ok=True)
    p = os.path.join(out_root, "rig_report.json")
    if os.path.exists(p):
        try:
            old = json.load(open(p, encoding="utf-8"))
            for k, v in old.items():
                def _ne(x):
                    if isinstance(x, dict):
                        return any(_ne(y) for y in x.values())
                    if isinstance(x, (list, tuple)):
                        return len(x) > 0
                    return bool(x)
                if k == "render" and isinstance(v, dict) and isinstance(report.get("render"), dict):
                    for kk, vv in v.items():
                        if _ne(vv) and not _ne(report["render"].get(kk)):
                            report["render"][kk] = vv
                elif v and not report.get(k):
                    report[k] = v
        except Exception as ex:
            print("[dh_rig] 合并旧 report 失败(忽略): %r" % (ex,), flush=True)
    json.dump(report, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[dh_rig] rig_report.json → %s (%d 字节)" % (p, os.path.getsize(p)), flush=True)


# ------------------------------------------------------------------ 主流程
def main():
    args = parse_args()
    mem = MemTrail()
    report = {"ok": False, "script": "tools/codex-scripts/blender/dh_rig.py",
              "blender": None, "input": {}, "proxy": {}, "landmarks": {}, "skeleton": {},
              "skinning": {}, "actions": {}, "export": {}, "render": {}, "memory": [],
              "notes": [], "errors": [], "t": time.strftime("%Y-%m-%d %H:%M:%S")}
    mem.snap("start")
    out_root = args.out
    frames_root = os.path.join(out_root, "frames")
    os.makedirs(out_root, exist_ok=True)

    # ---- 现读输入头（不信手抄） --------------------------------------
    raw = open(args.glb, "rb").read(32)
    size = os.path.getsize(args.glb)
    ver, declared = struct.unpack_from("<II", raw, 4)
    jl, jt = struct.unpack_from("<II", raw, 12)
    report["input"] = {"path": args.glb, "bytes": size, "header": {
        "magic": raw[:4].decode("ascii", "replace"), "version": ver,
        "declared_length": declared, "length_matches": declared == size,
        "json_chunk_len": jl, "json_chunk_type": raw[16:20].decode("ascii", "replace")}}
    log("输入 %s (%d 字节) magic=%s v%d len匹配=%s" % (os.path.basename(args.glb), size,
        raw[:4].decode("ascii", "replace"), ver, declared == size))
    if raw[:4] != b"glTF" or declared != size:
        report["errors"].append("输入不是合法 GLB（头/长度不符）")
        write_report(out_root, report); return 2

    jraw = open(args.glb, "rb").read()
    J = json.loads(jraw[20:20 + jl].decode("utf-8"))
    pr0 = J["meshes"][0]["primitives"][0]
    report["input"]["gltf_json"] = {
        "generator": (J.get("asset") or {}).get("generator"),
        "nodes": len(J.get("nodes", [])), "meshes": len(J.get("meshes", [])),
        "skins": None if J.get("skins") is None else len(J["skins"]),
        "animations": None if J.get("animations") is None else len(J["animations"]),
        "materials": len(J.get("materials", [])), "textures": len(J.get("textures", [])),
        "accessors": len(J.get("accessors", [])),
        "source_vertices": J["accessors"][pr0["attributes"]["POSITION"]]["count"],
        "source_triangles": J["accessors"][pr0["indices"]]["count"] // 3,
        "source_aabb_min": J["accessors"][pr0["attributes"]["POSITION"]]["min"],
        "source_aabb_max": J["accessors"][pr0["attributes"]["POSITION"]]["max"]}
    g = report["input"]["gltf_json"]
    log("输入解剖: generator=%s nodes=%s meshes=%s skins=%s animations=%s verts=%d tris=%d"
        % (g["generator"], g["nodes"], g["meshes"], g["skins"], g["animations"],
           g["source_vertices"], g["source_triangles"]))
    del jraw

    import bpy
    import numpy as np
    from mathutils import Vector, Matrix, Quaternion
    report["blender"] = bpy.app.version_string

    blend_path = os.path.join(out_root, "dh_rigged.blend")
    core_path = os.path.join(out_root, "rig_core.json")
    rig_ready = False
    rig = {}
    if args.reuse_blend and os.path.exists(blend_path) and os.path.exists(core_path):
        log("载入既有 rig blend: " + blend_path)
        bpy.ops.wm.open_mainfile(filepath=blend_path)
        mesh_obj = bpy.data.objects["DH_Body"]
        arm_obj = bpy.data.objects["DH_Armature"]
        rig = json.load(open(core_path, encoding="utf-8"))
        rig_ready = True
        mem.snap("reuse_blend")

    # ============================================================ 阶段 1：建骨
    if "rig" in args.stages and not rig_ready:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scn = bpy.context.scene
        scn.render.fps = FPS
        mem.snap("after_factory_reset")

        # ---- 1.1 导入全精度 GLB ---------------------------------------
        t0 = time.time()
        bpy.ops.import_scene.gltf(filepath=args.glb)
        mem.snap("after_import_full")
        mesh_obj = [o for o in scn.objects if o.type == "MESH"][0]
        v_full, p_full = len(mesh_obj.data.vertices), len(mesh_obj.data.polygons)
        log("全精度导入: verts=%d polys=%d (%.1fs)" % (v_full, p_full, time.time() - t0))
        report["proxy"].update({"full_verts": v_full, "full_polys": p_full})

        # ---- 1.2 抽稀代理 --------------------------------------------
        ratio = args.ratio if args.ratio is not None else min(1.0, float(args.target_faces) / max(1, p_full))
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        mod = mesh_obj.modifiers.new("DH_Decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        t0 = time.time()
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mem.snap("after_decimate")
        v_px, p_px = len(mesh_obj.data.vertices), len(mesh_obj.data.polygons)
        dt = round(time.time() - t0, 2)
        report["proxy"].update({"decimated": True, "ratio": round(ratio, 6),
                                "target_faces": args.target_faces, "proxy_verts": v_px,
                                "proxy_polys": p_px, "decimate_seconds": dt,
                                "reason": "空闲物理内存 < 2.5GB ⇒ 按纪律先在抽稀代理上建骨/做动作/验证"})
        log("抽稀: ratio=%.4f → verts=%d polys=%d (%.1fs)" % (ratio, v_px, p_px, dt))
        mesh_obj.name = "DH_Body"; mesh_obj.data.name = "DH_BodyMesh"
        # 抽稀后**焊接重合点**：Tripo 网格在 UV 缝/壳边界上有大量重合但未共享的顶点，
        # 不焊接会导致 (a) 连通分量上千、(b) Bone Heat 无解、(c) 权重被撕开。
        def comp_count():
            e2 = np.empty(len(mesh_obj.data.edges) * 2, dtype=np.int64)
            mesh_obj.data.edges.foreach_get("vertices", e2)
            e2 = e2.reshape(-1, 2)
            ww = np.ones(len(e2))
            a2 = sp.coo_matrix((ww, (e2[:, 0], e2[:, 1])), shape=(len(mesh_obj.data.vertices),) * 2).tocsr()
            n2, _l2 = csg.connected_components((a2 + a2.T).tocsr(), directed=False)
            sz = np.bincount(_l2)
            return int(n2), int(sz.max())

        import scipy.sparse as sp
        import scipy.sparse.csgraph as csg
        pre = comp_count()
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=0.0006)
        bpy.ops.object.mode_set(mode="OBJECT")
        v_px, p_px = len(mesh_obj.data.vertices), len(mesh_obj.data.polygons)
        post = comp_count()
        report["proxy"]["weld"] = {"threshold": 0.0006, "components_before": pre[0],
                                   "largest_before": pre[1], "components_after": post[0],
                                   "largest_after": post[1], "verts_after": v_px, "polys_after": p_px,
                                   "note": "抽稀后按 0.0006 焊接重合点，降低碎片度"}
        log("焊接重合点(0.0006): 分量 %d→%d，最大块 %d→%d，verts=%d polys=%d"
            % (pre[0], post[0], pre[1], post[1], v_px, p_px))
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        bpy.ops.object.shade_smooth()

        # ---- 1.3 实测 landmark ---------------------------------------
        cbuf = np.empty(v_px * 3, dtype=np.float64)
        mesh_obj.data.vertices.foreach_get("co", cbuf)
        co = cbuf.reshape(v_px, 3)
        mn, mx = co.min(0), co.max(0)
        H = float(mx[AX_UP] - mn[AX_UP])
        report["landmarks"]["aabb"] = {"min": [round(float(v), 6) for v in mn],
                                       "max": [round(float(v), 6) for v in mx],
                                       "axes": "Blender X横向 / Y前后 / Z身高"}
        report["landmarks"]["height_units"] = round(H, 6)
        log("代理 AABB min=(%.4f,%.4f,%.4f) max=(%.4f,%.4f,%.4f) H=%.5f"
            % (mn[0], mn[1], mn[2], mx[0], mx[1], mx[2], H))

        def leg_slab_centers(side):
            """该侧腿中轴采样：下半身 0~45%H，每 5% 一层，按 X 最大间隙切左右"""
            out = []
            for pct in range(0, 45, 5):
                lo = mn[AX_UP] + H * pct / 100.0
                hi = mn[AX_UP] + H * (pct + 5) / 100.0
                m = (co[:, AX_UP] >= lo) & (co[:, AX_UP] < hi)
                if m.sum() < 50:
                    continue
                idx = np.where(m)[0]
                xs = np.sort(co[idx, AX_LAT])
                gap = np.diff(xs); gi = int(np.argmax(gap))
                if gap[gi] > 0.010 * H and 0 < gi < len(xs) - 1:
                    sub = idx[gi + 1:] if side > 0 else idx[:gi + 1]
                else:
                    sub = idx
                if len(sub) < 20:
                    continue
                out.append(((lo + hi) * .5, float(co[sub, AX_LAT].mean()),
                            float(co[sub, AX_DEP].mean()), int(len(sub)), round(float(gap[gi]), 5)))
            return out

        legP, legN = leg_slab_centers(+1), leg_slab_centers(-1)
        report["landmarks"]["leg_axis_plusX"] = [[round(v, 5) for v in r] for r in legP]
        report["landmarks"]["leg_axis_minusX"] = [[round(v, 5) for v in r] for r in legN]
        pairs = [((legP[i][1] + legN[i][1]) * .5, (legP[i][2] + legN[i][2]) * .5,
                  (legP[i][0] + legN[i][0]) * .5)
                 for i in range(min(len(legP), len(legN)))]
        cx = float(np.mean([p[0] for p in pairs])) if pairs else float((mn[0] + mx[0]) * .5)
        cd = float(np.mean([p[1] for p in pairs])) if pairs else float((mn[1] + mx[1]) * .5)
        report["landmarks"]["axis_lat"] = round(cx, 6)
        report["landmarks"]["axis_dep"] = round(cd, 6)
        log("实测身体中轴 X=%.5f Y=%.5f（%d 层双腿簇中点平均）" % (cx, cd, len(pairs)))

        def leg_axis(side, u):
            tab = legP if side > 0 else legN
            if len(tab) < 2:
                return (cx + side * 0.05 * H, cd, u)
            us = np.array([r[0] for r in tab])
            kx = np.polyfit(us, np.array([r[1] for r in tab]), 1)
            kd = np.polyfit(us, np.array([r[2] for r in tab]), 1)
            return (float(np.polyval(kx, u)), float(np.polyval(kd, u)), u)

        def arm_axis_tab(side):
            """该侧手臂中轴：0.44H~0.84H 每 4% 一层，取该层最外侧 18% 点的均值"""
            out = []
            for pct in range(44, 84, 4):
                lo = mn[AX_UP] + H * pct / 100.0
                hi = mn[AX_UP] + H * (pct + 4) / 100.0
                m = (co[:, AX_UP] >= lo) & (co[:, AX_UP] < hi)
                if side > 0:
                    m &= (co[:, AX_LAT] > cx + 0.055 * H)
                else:
                    m &= (co[:, AX_LAT] < cx - 0.055 * H)
                if m.sum() < 30:
                    continue
                idx = np.where(m)[0]
                ext = co[idx, AX_LAT] if side > 0 else -co[idx, AX_LAT]
                k = max(1, int(len(idx) * 0.18))
                sel = idx[np.argsort(-ext)[:k]]
                out.append(((lo + hi) * .5, float(co[sel, AX_LAT].mean()),
                            float(co[sel, AX_DEP].mean()), int(len(idx))))
            return out

        armP, armN = arm_axis_tab(+1), arm_axis_tab(-1)
        report["landmarks"]["arm_axis_plusX"] = [[round(v, 5) for v in r] for r in armP]
        report["landmarks"]["arm_axis_minusX"] = [[round(v, 5) for v in r] for r in armN]

        def arm_axis(side, u):
            """该侧手臂中轴在线性拟合下、高度 u 处的 (x, y, u)"""
            tab = armP if side > 0 else armN
            if len(tab) < 2:
                return (cx + side * 0.098 * H, cd, u)
            us = np.array([r[0] for r in tab])
            kx = np.polyfit(us, np.array([r[1] for r in tab]), 1)
            kd = np.polyfit(us, np.array([r[2] for r in tab]), 1)
            return (float(np.polyval(kx, u)), float(np.polyval(kd, u)), u)

        # ---- 1.4 连通分量 + 测地线追四肢末端（真测，不猜） --------------
        # ⚠️ 实测教训：Tripo 网格是**多壳**的（欧拉特征数 34755 ⇒ 上千个壳），
        #    种子若落在小壳上，测地可达域只有 0.16 单位（=误差）。所以必须先取
        #    **最大连通块**再放种子，且末端点也必须落在最大块里。
        ev = np.empty(len(mesh_obj.data.edges) * 2, dtype=np.int64)
        mesh_obj.data.edges.foreach_get("vertices", ev)
        ev = ev.reshape(-1, 2)
        w = np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1)
        w = np.maximum(w, 1e-9)
        adj = sp.coo_matrix((w, (ev[:, 0], ev[:, 1])), shape=(v_px, v_px)).tocsr()
        adj = (adj + adj.T).tocsr()
        ncomp, labels = csg.connected_components(adj, directed=False)
        sizes = np.bincount(labels)
        main_lab = int(np.argmax(sizes))
        inmain = labels == main_lab
        top = sorted([int(x) for x in sizes], reverse=True)[:6]
        report["landmarks"]["connectivity"] = {
            "components": int(ncomp), "largest_vertices": int(sizes[main_lab]),
            "largest_ratio": round(float(sizes[main_lab]) / float(v_px), 5),
            "top6_sizes": top,
            "note": "多壳网格：自动权重(Bone Heat)对分离壳会漏块 ⇒ 必须有兜底权重"}
        log("连通分量 = %d 个；最大块 %d 顶点（占 %.2f%%），top6=%s"
            % (ncomp, sizes[main_lab], 100.0 * sizes[main_lab] / v_px, top))

        cand = np.where(inmain)[0]
        seed = int(cand[int(np.argmin((co[cand, AX_LAT] - cx) ** 2
                                    + (co[cand, AX_UP] - (mn[AX_UP] + 0.55 * H)) ** 2
                                    + (co[cand, AX_DEP] - cd) ** 2))])
        t0 = time.time()
        _dg = csg.dijkstra(adj, indices=seed, return_predecessors=True, min_only=True)
        dvec, pred = np.asarray(_dg[0], dtype=np.float64), _dg[1]
        mem.snap("after_dijkstra")
        reach = np.isfinite(dvec)
        dmax = float(dvec[reach].max()) if reach.any() else -1.0
        log("测地线(种子 %d, 最大块内) 完成 %.1fs 可达顶点=%d 最远=%.4f 单位（H=%.4f）"
            % (seed, time.time() - t0, int(reach.sum()), dmax, H))
        report["landmarks"]["geodesic_reach"] = {
            "seed_vertex": seed, "reachable": int(reach.sum()),
            "reachable_ratio": round(float(reach.sum()) / float(v_px), 5), "max_dist": round(dmax, 5)}

        def back_path(target):
            """返回**自远端(手/脚) → 近端(种子)** 的顶点路径"""
            path, v, seen = [], int(target), set()
            while v >= 0 and v != seed and int(v) not in seen:
                path.append(int(v)); seen.add(int(v)); v = int(pred[v])
            path.append(seed)
            return path                       # [target, ..., seed]，s=0 在远端

        def distal(mask, side):
            m = mask & inmain & ((co[:, AX_LAT] > cx) if side > 0 else (co[:, AX_LAT] <= cx))
            m &= reach
            idx = np.where(m)[0]
            if len(idx) == 0:
                return None
            return int(idx[int(np.argmax(dvec[idx]))])

        z0 = mn[AX_UP]
        lowm = co[:, AX_UP] < z0 + 0.05 * H
        # 手候选必须**排除头部/肩带**（实测踩过：不排除时测地最远点落在头发上）
        hand_band = (co[:, AX_UP] > z0 + 0.22 * H) & (co[:, AX_UP] < z0 + 0.78 * H)
        toe = {k: distal(lowm, s) for s, k in ((+1, "P"), (-1, "N"))}
        hand = {k: distal(hand_band, s) for s, k in ((+1, "P"), (-1, "N"))}
        geo_len = {}
        for k in ("P", "N"):
            geo_len["leg_" + k] = (round(float(dvec[toe[k]]), 5) if toe.get(k) is not None else None)
            geo_len["arm_" + k] = (round(float(dvec[hand[k]]), 5) if hand.get(k) is not None else None)
        report["landmarks"]["geodesic"] = {
            "toe_vertex": dict(toe), "hand_vertex": dict(hand), "surface_arclen": geo_len,
            "need_arclen": {"leg": round(0.643 * H, 5), "arm": round(0.440 * H, 5)},
            "note": "沿**表面**测地弧长；壳体包裹使其略大于解剖直线长度，只作量级/可达性证据"}
        log("测地表面弧长 = %s ；解剖需求 腿=%.4f 臂=%.4f（H=%.5f）"
            % (geo_len, 0.643 * H, 0.440 * H, H))

        # ---- 1.5 哪条臂自然下垂（**实测**：0.42~0.52H 高度带的外侧外伸量） --
        band = (co[:, AX_UP] > z0 + 0.42 * H) & (co[:, AX_UP] < z0 + 0.52 * H)
        ext = {}
        for side, k in ((+1, "P"), (-1, "N")):
            m = band & ((co[:, AX_LAT] > cx) if side > 0 else (co[:, AX_LAT] < cx))
            ext[k] = float(abs(co[m, AX_LAT] - cx).max()) if m.sum() else 0.0
        ref_key = "P" if ext["P"] >= ext["N"] else "N"
        report["landmarks"]["arm_lateral_extent_in_band_42_52H"] = {k: round(v, 5) for k, v in ext.items()}
        log("下垂臂判定：0.42~0.52H 外侧外伸 +X=%.4f / -X=%.4f ⇒ 静置参考侧=%s（外伸大=有手垂在那侧）"
            % (ext["P"], ext["N"], ref_key))

        # ---- 1.6 关节落位（口径写在下面，可复算） ----------------------
        #   · 关节**高度** = 人体解剖比例 × 模型实测身高 H（可靠、可复算、不含表面包裹误差）
        #   · 关节**横向/前后** = **实测肢轴**（按身高分层取该侧簇中心/最外侧点，线性拟合后取值）
        #   · 脚**尖** = 实测：该侧底部离踝最远的水平点（真正测出来的朝向）
        #   · 只实测一侧（下垂臂那侧 / 任一条腿），另一侧**镜像** ⇒ 左右对称由构造保证
        def place_leg(side):
            an = leg_axis(side, z0 + FR["ankle"] * H)
            kn = leg_axis(side, z0 + FR["knee"] * H)
            hp = leg_axis(side, z0 + FR["hip"] * H)
            m = lowm & inmain & ((co[:, AX_LAT] > cx) if side > 0 else (co[:, AX_LAT] <= cx))
            idx = np.where(m)[0]
            if len(idx):
                dv = np.linalg.norm(co[idx][:, [AX_LAT, AX_DEP]] - np.array([an[0], an[1]]), axis=1)
                tj = int(idx[int(np.argmax(dv))])
                to = (float(co[tj, AX_LAT]), float(co[tj, AX_DEP]), float(z0 + FR["toe"] * H))
            else:
                to = (an[0], an[1] - 0.10 * H, z0 + FR["toe"] * H)
            return {"hip": hp, "knee": kn, "ankle": an, "toe": to}

        def place_arm(side):
            return {"shoulder": arm_axis(side, z0 + FR["shoulder"] * H),
                    "elbow": arm_axis(side, z0 + (FR["shoulder"] - 0.186) * H),
                    "wrist": arm_axis(side, z0 + (FR["shoulder"] - 0.332) * H),
                    "hand": arm_axis(side, z0 + (FR["shoulder"] - 0.440) * H)}

        placed = {"leg_P": place_leg(+1), "leg_N": place_leg(-1),
                  "arm_P": place_arm(+1), "arm_N": place_arm(-1)}
        report["landmarks"]["placed_chains"] = {k: {kk: [round(c, 6) for c in vv]
                                                   for kk, vv in v.items()} for k, v in placed.items()}
        for k in sorted(placed):
            log("落位链 %-7s %s" % (k, {kk: [round(c, 4) for c in vv] for kk, vv in placed[k].items()}))

        # ---- 1.7 朝向 / 左右映射（由实测脚尖-踝） ----------------------
        fwd = (0.0, -1.0, 0.0)
        try:
            f1 = np.array(placed["leg_P"]["toe"]) - np.array(placed["leg_P"]["ankle"])
            f2 = np.array(placed["leg_N"]["toe"]) - np.array(placed["leg_N"]["ankle"])
            f = f1 + f2
            f[AX_UP] = 0.0
            if np.linalg.norm(f) > 1e-9 and float(np.dot(f1, f2)) > 0:
                fwd = tuple((f / np.linalg.norm(f)).tolist())
        except Exception as ex:
            report["notes"].append("朝向前方测量失败，退回 Blender -Y: %r" % (ex,))
        up = Vector(UP)
        rt = Vector(fwd).cross(up)          # 人右手方向 = 前 × 上
        report["landmarks"]["facing_forward"] = [round(v, 6) for v in fwd]
        report["landmarks"]["character_right_dir"] = [round(v, 6) for v in rt]
        right_is_minus = rt[AX_LAT] < 0
        key_of = {}
        for side, k in ((+1, "P"), (-1, "N")):
            is_right = (side < 0) if right_is_minus else (side > 0)
            key_of["R" if is_right else "L"] = k
        report["landmarks"]["key_of"] = key_of
        report["landmarks"]["side_map"] = {
            "_R": ("-X（Blender x<0）" if right_is_minus else "+X（Blender x>0）"),
            "_L": ("+X（Blender x>0）" if right_is_minus else "-X（Blender x<0）")}
        log("前方 F=(%.3f,%.3f,%.3f) 角色右手方向=(%.3f,%.3f,%.3f) key_of=%s"
            % (fwd[0], fwd[1], fwd[2], rt[0], rt[1], rt[2], key_of))

        # ---- 1.8 关节落位汇总：参考侧实测 → 另一侧镜像 ----------------
        report["landmarks"]["arm_rest_ref_side"] = ref_key
        ref_sign = +1 if ref_key == "P" else -1
        ref_logical = "R" if ((ref_sign < 0) == right_is_minus) else "L"
        other_logical = "L" if ref_logical == "R" else "R"
        arm_r, leg_r = placed["arm_" + ref_key], placed["leg_" + ref_key]

        def mirror(p):
            return (2 * cx - p[0], p[1], p[2])

        J = {"pelvis": (cx, cd, z0 + FR["hip"] * H), "spine": (cx, cd, z0 + FR["spine"] * H),
             "chest": (cx, cd, z0 + FR["chest"] * H), "neck": (cx, cd, z0 + FR["neck"] * H),
             "head": (cx, cd, z0 + FR["head0"] * H), "head_tip": (cx, cd, z0 + H),
             "clav": (cx, cd, z0 + FR["clav"] * H)}
        for nm in ("hip", "knee", "ankle", "toe"):
            J[nm + "_" + ref_logical] = tuple(leg_r[nm])
            J[nm + "_" + other_logical] = mirror(tuple(leg_r[nm]))
        for nm in ("shoulder", "elbow", "wrist", "hand"):
            J[nm + "_" + ref_logical] = tuple(arm_r[nm])
            J[nm + "_" + other_logical] = mirror(tuple(arm_r[nm]))
        for lg in ("L", "R"):
            sh = J["shoulder_" + lg]
            J["clav_" + lg] = (cx, cd, z0 + FR["clav"] * H)
            J["clav_end_" + lg] = (cx + (sh[0] - cx) * 0.45, cd + (sh[1] - cd) * 0.45,
                                   sh[2] + (J["clav_" + lg][2] - sh[2]) * 0.55)
        report["landmarks"]["joints"] = {k: [round(float(x), 6) for x in v] for k, v in J.items()}
        log("关节落位: " + json.dumps({k: [round(x, 4) for x in v] for k, v in J.items()}, ensure_ascii=False))

        # ---- 1.7 建 armature -----------------------------------------
        arm_data = bpy.data.armatures.new("DH_ArmatureData")
        arm_obj = bpy.data.objects.new("DH_Armature", arm_data)
        scn.collection.objects.link(arm_obj)
        bpy.context.view_layer.objects.active = arm_obj
        arm_obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        ebs = arm_data.edit_bones
        spec = [("hips", J["pelvis"], J["spine"], None), ("spine", J["spine"], J["chest"], "hips"),
                ("chest", J["chest"], J["neck"], "spine"), ("neck", J["neck"], J["head"], "chest"),
                ("head", J["head"], J["head_tip"], "neck")]
        for lg in ("L", "R"):
            spec += [("shoulder_" + lg, J["clav_" + lg], J["clav_end_" + lg], "chest"),
                     ("upper_arm_" + lg, J["clav_end_" + lg], J["elbow_" + lg], "shoulder_" + lg),
                     ("forearm_" + lg, J["elbow_" + lg], J["wrist_" + lg], "upper_arm_" + lg),
                     ("hand_" + lg, J["wrist_" + lg], J["hand_" + lg], "forearm_" + lg),
                     ("thigh_" + lg, J["hip_" + lg], J["knee_" + lg], "hips"),
                     ("shin_" + lg, J["knee_" + lg], J["ankle_" + lg], "thigh_" + lg),
                     ("foot_" + lg, J["ankle_" + lg], J["toe_" + lg], "shin_" + lg)]
        for name, h, t, par in spec:
            b = ebs.new(name); b.head = h; b.tail = t
            if par:
                b.parent = ebs[par]
        bpy.ops.object.mode_set(mode="OBJECT")
        log("骨架建成: %d 根骨" % len(arm_data.bones))

        # ---- 1.8 对称性量化 -------------------------------------------
        sym = []
        for base in ARM_BONES + LEG_BONES:
            bl, br = arm_data.bones[base + "_L"], arm_data.bones[base + "_R"]
            vl = (bl.tail_local - bl.head_local); vr = (br.tail_local - br.head_local)
            dl = vl.normalized() if vl.length > 1e-12 else vl
            dr = vr.normalized() if vr.length > 1e-12 else vr
            dmi = Vector((-dr[0], dr[1], dr[2]))
            ang = math.degrees(dl.angle(dmi)) if dmi.length > 1e-12 else 0.0
            sym.append({"bone": base, "len_L": round(vl.length, 9), "len_R": round(vr.length, 9),
                        "len_diff": round(abs(vl.length - vr.length), 12),
                        "mirror_angle_deg": round(ang, 12)})
        report["skeleton"]["symmetry"] = sym
        report["skeleton"]["max_len_diff"] = max(s["len_diff"] for s in sym)
        report["skeleton"]["max_mirror_angle_deg"] = max(s["mirror_angle_deg"] for s in sym)
        log("对称量化: max_len_diff=%.3e  max_mirror_angle=%.3e°"
            % (report["skeleton"]["max_len_diff"], report["skeleton"]["max_mirror_angle_deg"]))
        bones_rec = [{"name": b.name, "parent": (b.parent.name if b.parent else None),
                      "head": [round(float(c), 6) for c in b.head_local],
                      "tail": [round(float(c), 6) for c in b.tail_local],
                      "length": round(float((b.tail_local - b.head_local).length), 6)}
                     for b in arm_data.bones]
        report["skeleton"]["bones"] = bones_rec
        report["skeleton"]["bone_count"] = len(bones_rec)
        report["skeleton"]["hierarchy"] = {b["name"]: b["parent"] for b in bones_rec}

        # ---- 1.9 蒙皮 -------------------------------------------------
        skin = {}
        bpy.ops.object.select_all(action="DESELECT")
        mesh_obj.select_set(True); arm_obj.select_set(True)
        bpy.context.view_layer.objects.active = arm_obj
        method = None
        try:
            t0 = time.time()
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
            method = "自动权重（Bone Heat）"
            skin["auto_seconds"] = round(time.time() - t0, 2)
            log("自动权重完成 %.1fs" % skin["auto_seconds"])
        except Exception as ex:
            skin["auto_error"] = repr(ex)
            log("自动权重失败: %r" % (ex,))
        mem.snap("after_autoweight")

        def coverage():
            vg = mesh_obj.vertex_groups
            names = [g.name for g in vg]
            cnt_un = n_ev = 0
            tot_w = 0.0
            per = {n: 0 for n in names}
            for v in mesh_obj.data.vertices:
                s = 0.0
                for gg in v.groups:
                    s += gg.weight
                    if gg.weight > 1e-6:
                        per[vg[gg.group].name] += 1
                if s < 1e-6:
                    cnt_un += 1
                else:
                    tot_w += s; n_ev += 1
            return names, cnt_un, (tot_w / max(1, n_ev)), per

        names, cnt_un, avg_w, per_bone = coverage()
        need_manual = (len(names) == 0) or (cnt_un > 0.02 * v_px) or \
                      any(per_bone.get(n, 0) == 0 for n in ALL_BONES if n in names)
        log("蒙皮覆盖: 组=%d 无权重顶点=%d/%d 平均权重和=%.4f" % (len(names), cnt_un, v_px, avg_w))
        if need_manual:
            log("⇒ 自动权重不足，改用**自写加权就近权重**（claim 半径 + 骨架跳距门 + 跨侧压制 + 图平滑）")
            for gg in list(mesh_obj.vertex_groups):
                mesh_obj.vertex_groups.remove(gg)
            if not any(m.type == "ARMATURE" for m in mesh_obj.modifiers):
                md = mesh_obj.modifiers.new("Armature", "ARMATURE"); md.object = arm_obj
            else:
                for m in mesh_obj.modifiers:
                    if m.type == "ARMATURE":
                        m.object = arm_obj
            mesh_obj.parent = arm_obj
            segs = [(n, np.array(arm_data.bones[n].head_local), np.array(arm_data.bones[n].tail_local))
                    for n in ALL_BONES]
            NB = len(segs)
            bi = {n: i for i, (n, _h, _t) in enumerate(segs)}
            # ---- claim 半径：>1 表示这根骨"抢得更多"，<1 表示让它少抢 ----
            # 🔴 实测教训：手臂自然下垂时 hand/forearm 骨线段紧贴髋部
            #    （髋线到 hand 段距离 ≈0.047，到 thigh 段 ≈0.030）⇒ 最近骨会把
            #    髋部顶点判给 hand；一旦抬臂，髋部被拽走形成"拉丝/刀片"撕裂。
            #    所以远端手骨 claim 压到 0.45，并加下面的"跳距门"。
            # 包络半径（单位 H）：'哪根骨的**归一化**距离最近就归谁' = 标准包络蒙皮。
            # 🔴 为什么要用半径而不是纯最近骨：纯最近骨下，髋/臀顶点天然离**大腿骨**
            #    更近（髋线到 thigh 段 ≈0.030，到 hips 竖线 ≈0.037~0.094）⇒ 髋部整片
            #    判给大腿，一抬腿就被拽走。给 hips 一个大包络(0.060H)后，髋腔归 hips。
            R_ENV = {"hips": 0.068, "spine": 0.050, "chest": 0.055, "neck": 0.025, "head": 0.060,
                     "shoulder": 0.025, "upper_arm": 0.030, "forearm": 0.024, "hand": 0.024,
                     "thigh": 0.028, "shin": 0.029, "foot": 0.022}
            rad = np.array([max(1e-4, R_ENV.get(n.split("_")[0], 0.03) * H) for n, _h, _t in segs])
            side_of = np.array([(-1 if n.endswith("_R") else (1 if n.endswith("_L") else 0))
                                for n, _h, _t in segs])
            # ---- 骨架跳距：只有"近亲"骨之间才允许共享权重 ----
            hop = np.full((NB, NB), 99, dtype=np.int32)
            for i, n in enumerate([s[0] for s in segs]):
                hop[i, i] = 0
                p = BONE_PARENT.get(n)
                d = 0
                while p is not None:
                    d += 1
                    hop[i, bi[p]] = hop[bi[p], i] = d
                    p = BONE_PARENT.get(p)
            # ---- 沿网格邻接的平滑矩阵（CSR 行归一） ----
            A = adj.tocsr().astype(np.float32)
            deg = np.asarray(A.sum(axis=1)).ravel()
            deg[deg == 0] = 1.0
            S = sp.diags(1.0 / deg).dot(A).tocsr()
            hd = [np.array(arm_data.bones[n].head_local, dtype=np.float64) for n in ALL_BONES]
            tl = [np.array(arm_data.bones[n].tail_local, dtype=np.float64) for n in ALL_BONES]
            W = np.zeros((v_px, NB), dtype=np.float64)
            CH = 25000
            t0 = time.time()
            for s0 in range(0, v_px, CH):
                e0 = min(v_px, s0 + CH)
                blk = co[s0:e0]
                nb_ = blk.shape[0]
                D = np.empty((nb_, NB), dtype=np.float64)
                for j in range(NB):
                    ab = tl[j] - hd[j]
                    L2 = float(ab @ ab) or 1e-12
                    wv = np.clip(((blk - hd[j]) @ ab) / L2, 0.0, 1.0)
                    D[:, j] = np.linalg.norm(blk - (hd[j] + wv[:, None] * ab), axis=1)
                Dw = D / rad[None, :]                     # 归一化距离：越小越该归这根骨
                uu = blk[:, AX_LAT] - cx
                for j in range(NB):
                    if side_of[j] != 0:
                        wrong = (np.sign(uu) * side_of[j]) < 0
                        f = np.clip(0.30 + 0.70 * np.clip(np.abs(uu) / (0.09 * H), 0.0, 1.0), 0.30, 1.0)
                        Dw[:, j] /= np.where(wrong, f, 1.0)
                order = np.argsort(Dw, axis=1)
                idx = np.arange(nb_)
                j0 = order[:, 0]
                j1 = order[:, 1]
                assert j0.shape == (nb_,) and j1.shape == (nb_,), "坏形状"
                d0 = Dw[idx, j0]; d1 = Dw[idx, j1]
                gate = (hop[j0, j1] <= 2).astype(np.float64)
                blend = np.clip((d1 - d0) / (d0 + d1 + 1e-9), 0.0, 1.0) * gate
                w0 = 1.0 / (d0 + 1e-6)
                w1 = (1.0 / (d1 + 1e-6)) * (0.45 * blend)
                tot = w0 + w1
                W[s0 + idx, j0] = w0 / tot
                W[s0 + idx, j1] += w1 / tot
            _rs = W.sum(axis=1)
            _nz = np.count_nonzero(W > 1e-9, axis=1)
            log("权重初值自检：行和 min=%.9f max=%.9f ；每顶点非零骨数 max=%d（期望 ≤2）"
                % (_rs.min(), _rs.max(), int(_nz.max())))
            # 统计"改前"的跨侧/远端手骨污染（用未经平滑的 W）
            def opp_stats(Wm):
                opp = np.zeros(v_px, dtype=np.float32)
                for j in range(NB):
                    if side_of[j] != 0:
                        m = (np.sign(co[:, AX_LAT] - cx) * side_of[j]) < 0
                        opp[m] += Wm[m, j]
                hipm = hip_band
                first = np.argmax(Wm, axis=1)
                first_is_hips = int((first[hipm] == bi["hips"]).sum())
                first_is_thigh = int(((first[hipm] == bi["thigh_L"]) |
                                      (first[hipm] == bi["thigh_R"])).sum())
                first_is_hand = int(((first[hipm] == bi["hand_L"]) |
                                     (first[hipm] == bi["hand_R"])).sum())
                fb = first[hipm]
                hist = {}
                for j, (nm2, _h2, _t2) in enumerate(segs):
                    c = int((fb == j).sum())
                    if c:
                        hist[nm2] = c
                return {"opp_mean": float(opp.mean()), "opp_max": float(opp.max()),
                        "hip_band_first_hips": first_is_hips, "hip_band_first_thigh": first_is_thigh,
                        "hip_band_first_hand": first_is_hand, "hip_band_n": int(hipm.sum()),
                        "hip_band_first_hist_top": dict(sorted(hist.items(), key=lambda kv: -kv[1])[:7])}
            # 髋带口径：0.44~0.58H、0.03H<|u|<0.09H（上界排除垂在体侧的手/前臂）
            _uu = np.abs(co[:, AX_LAT] - cx)
            hip_band = ((co[:, AX_UP] > z0 + 0.44 * H) & (co[:, AX_UP] < z0 + 0.58 * H)
                        & (_uu > 0.03 * H) & (_uu < 0.09 * H))
            before_stats = opp_stats(W)
            # ---- 髋缝软化：髋关节高度 ±0.035H、|u|<=0.10H 的一圈，把大腿权重
            #      分一半给 hips（否则壳体在高开衩处被大腿整片带走 ⇒ 拉丝/翻边） ----
            zh = z0 + FR["hip"] * H
            seam = (np.abs(co[:, AX_UP] - zh) <= 0.060 * H) & (np.abs(co[:, AX_LAT] - cx) <= 0.15 * H)
            jh = bi["hips"]; jt = [bi["thigh_L"], bi["thigh_R"]]
            if seam.any():
                take = 0.6 * (W[np.ix_(np.where(seam)[0], jt)].sum(axis=1))
                W[np.ix_(np.where(seam)[0], jt)] *= 0.4
                W[np.where(seam)[0], jh] += take
                W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
            # 调试：直接看几个髋带顶点的 top-3 骨名+权重（不用 hist 转述，防列序误读）
            try:
                _ids = np.where(hip_band)[0]
                if len(_ids):
                    _pick = _ids[::max(1, len(_ids) // 5)][:6]
                    for _vi in _pick:
                        _row = W[_vi]
                        _top = np.argsort(-_row)[:3]
                        log("  顶点%d (x=%.4f y=%.4f z=%.4f u=%+.4f) 非零=%d 行和=%.6f top3 = %s"
                            % (_vi, co[_vi, 0], co[_vi, 1], co[_vi, 2], co[_vi, 0] - cx,
                               int((_row > 1e-9).sum()), float(_row.sum()),
                               [(segs[_k][0], round(float(_row[_k]), 4)) for _k in _top]))
            except Exception as _e:
                log("  调试打印失败 %r" % (_e,))
            # ---- 沿网格邻接平滑 K 次（λ=0.40）让权重在壳体上连续 ----
            K, lam = 4, 0.35
            for _ in range(K):
                W = (1.0 - lam) * W + lam * (S.dot(W))
                W = np.maximum(W, 0.0)
                W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
            after_stats = opp_stats(W)
            # ---- 裁到每顶点最多 4 个影响（glTF 默认 4）并归一 ----
            if NB > 4:
                keep = np.argsort(-W, axis=1)[:, :4]
                Wn = np.zeros_like(W)
                rows = np.repeat(np.arange(v_px), 4)
                Wn[rows, keep.ravel()] = W[rows, keep.ravel()]
                W = Wn
            # ---- 兜底：保证每根骨都**至少**管到一些顶点（死骨=该肢体完全不形变） --
            forced = {}
            for j, (n, _h, _t) in enumerate(segs):
                col = W[:, j]
                if int((col > 1e-4).sum()) < 20:
                    hh = np.array(arm_data.bones[n].head_local); tt = np.array(arm_data.bones[n].tail_local)
                    ab = tt - hh; L2 = float(ab @ ab) or 1e-12
                    ttv = np.clip(((co - hh) @ ab) / L2, 0.0, 1.0)
                    dd = np.linalg.norm(co - (hh[None, :] + ttv[:, None] * ab[None, :]), axis=1)
                    near = np.argsort(dd)[:40]
                    W[near, j] = np.maximum(W[near, j], 0.45)
                    forced[n] = int(len(near))
            W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
            if NB > 4:
                keep = np.argsort(-W, axis=1)[:, :4]
                Wn = np.zeros_like(W)
                rows = np.repeat(np.arange(v_px), 4)
                Wn[rows, keep.ravel()] = W[rows, keep.ravel()]
                W = Wn
                W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
            # ---- 诊断：每根骨管到的顶点在哪（证明"右臂骨管的是躯干，不是手臂"）----
            own = {}
            for j, (n, _h, _t) in enumerate(segs):
                m = W[:, j] > 0.5
                if int(m.sum()) == 0:
                    own[n] = {"n_verts": 0}
                    continue
                cen = co[m].mean(axis=0)
                hh2 = np.array(arm_data.bones[n].head_local); tt2 = np.array(arm_data.bones[n].tail_local)
                ab2 = tt2 - hh2; L22 = float(ab2 @ ab2) or 1e-12
                t2 = np.clip(((cen - hh2) @ ab2) / L22, 0.0, 1.0)
                own[n] = {"n_verts": int(m.sum()),
                          "centroid": [round(float(v), 4) for v in cen],
                          "centroid_off_from_bone": round(float(np.linalg.norm(cen - (hh2 + t2 * ab2))), 4),
                          "centroid_lateral_u": round(float(cen[AX_LAT] - cx), 4)}
            skin["bone_ownership"] = own
            for n in ("upper_arm_L", "forearm_L", "hand_L", "upper_arm_R", "forearm_R", "hand_R",
                      "hips", "chest", "thigh_L", "thigh_R"):
                o = own.get(n) or {}
                log("骨权域 %-12s n=%-6s 质心=%s 偏离骨轴=%-7s 横向u=%s"
                    % (n, o.get("n_verts"), o.get("centroid"), o.get("centroid_off_from_bone"),
                       o.get("centroid_lateral_u")))
            skin["bones_force_seeded"] = forced
            gs = {n: mesh_obj.vertex_groups.new(name=n) for n in ALL_BONES}
            for j, (n, _h, _t) in enumerate(segs):
                col = W[:, j]
                idx = np.where(col > 1e-4)[0]
                g = gs[n]
                for vv in idx:
                    g.add([int(vv)], float(col[vv]), "REPLACE")
            method = "自写包络蒙皮（包络半径/骨架跳距门≤2跳/跨侧压制/髋缝软化/沿网格平滑2×λ0.30/死骨兜底/每顶点≤4影响）"
            skin["manual_seconds"] = round(time.time() - t0, 2)
            skin["weight_params"] = {"envelope_radius_H": R_ENV, "hop_gate": 2, "smooth_iter": K,
                                     "smooth_lambda": lam, "max_influences": 4,
                                     "cross_side_gate": "1/(0.30+0.70*clip(|u|/(0.09H),0,1))"}
            skin["weight_stats_before_smooth"] = before_stats
            skin["weight_stats_after_smooth"] = after_stats
            names, cnt_un, avg_w, per_bone = coverage()
            log("自写权重完成 %.1fs；复测 组=%d 无权重=%d 平均权重和=%.4f"
                % (skin["manual_seconds"], len(names), cnt_un, avg_w))
            log("权重自检 髋带(%.2f~%.2fH, |x|>%.2fH) 顶点 %d 个："
                "第一影响骨 = hips %d / thigh %d / hand %d ；跨侧权重均值 %.4f→%.4f 峰值 %.4f→%.4f"
                % (0.44, 0.56, 0.03, before_stats["hip_band_n"],
                   before_stats["hip_band_first_hips"], before_stats["hip_band_first_thigh"],
                   before_stats["hip_band_first_hand"], before_stats["opp_mean"], after_stats["opp_mean"],
                   before_stats["opp_max"], after_stats["opp_max"]))
            log("髋带第一影响骨分布 改前: %s" % before_stats["hip_band_first_hist_top"])
            log("髋带第一影响骨分布 改后: %s" % after_stats["hip_band_first_hist_top"])
            log("包络半径(×H): %s" % R_ENV)
        skin.update({"method": method, "vertex_groups": sorted(names), "group_count": len(names),
                     "unweighted_verts": int(cnt_un), "unweighted_ratio": round(cnt_un / float(v_px), 6),
                     "avg_weight_sum": round(float(avg_w), 5),
                     "verts_per_bone": {k: int(v) for k, v in sorted(per_bone.items())},
                     "zero_cover_bones": sorted([n for n in ALL_BONES if per_bone.get(n, 0) == 0])})
        report["skinning"] = skin
        log("蒙皮方法=%s 组=%d 无权重=%d 零覆盖=%s" % (method, len(names), cnt_un, skin["zero_cover_bones"]))

        # ---- 1.9b 材质分离（皮肤单开一份） ------------------------------
        try:
            split_skin_material(mesh_obj, report)
        except Exception as ex:
            report["notes"].append("材质分离失败: %r" % (ex,))
            log("材质分离失败: %r" % (ex,))

        # ---- 1.10 六个全肢体动作（世界轴解析 FK/IK，不猜局部轴） --------
        mem.snap("before_actions")

        # 关节驱动 helper：给"世界轴 + 角度"或"世界目标方向"，算出姿态骨 basis
        class Poser(object):
            def __init__(self, ao, ad):
                self.ao, self.ad = ao, ad
                self.rel = {}
                for b in ad.bones:
                    if b.parent is not None:
                        self.rel[b.name] = b.parent.matrix_local.inverted() @ b.matrix_local
                    else:
                        self.rel[b.name] = b.matrix_local.copy()

            def base(self, name, parent_pose):
                r = self.rel[name]
                return (parent_pose @ r) if parent_pose is not None else r

            def rest_dir(self, name, parent_pose=None):
                b = self.base(name, parent_pose)
                return (b.to_3x3() @ Vector((0, 1, 0))).normalized()

            def by_axis(self, name, parent_pose, axis, deg):
                b = self.base(name, parent_pose)
                q = Quaternion(Vector(axis).normalized(), math.radians(deg))
                new3 = q.to_matrix() @ b.to_3x3()
                basis = b.to_3x3().inverted() @ new3
                return basis.to_quaternion(), Matrix.Translation(b.translation) @ new3.to_4x4()

            def by_dir(self, name, parent_pose, target_dir):
                b = self.base(name, parent_pose)
                d0 = (b.to_3x3() @ Vector((0, 1, 0))).normalized()
                q = d0.rotation_difference(Vector(target_dir).normalized())
                new3 = q.to_matrix() @ b.to_3x3()
                basis = b.to_3x3().inverted() @ new3
                return basis.to_quaternion(), Matrix.Translation(b.translation) @ new3.to_4x4()

            def by_dirb(self, name, parent_pose, target_dir, t):
                """从**静置方向**按 t∈[0,1] 混到目标方向 ⇒ 动作首尾能回到静置，
                避免"常数方向"导致最后一帧仍有 141° 大旋转（实测踩过：拉丝/刀片撕裂）"""
                b = self.base(name, parent_pose)
                d0 = (b.to_3x3() @ Vector((0, 1, 0))).normalized()
                tgt = Vector(target_dir).normalized()
                d = (1.0 - float(t)) * d0 + float(t) * tgt
                if d.length < 1e-6:
                    d = tgt
                return self.by_dir(name, parent_pose, d.normalized())

            def with_trans(self, name, parent_pose, loc):
                b = self.base(name, parent_pose)
                return Matrix.Translation(loc) @ b

        P = Poser(arm_obj, arm_data)
        bone_len = {n: (arm_data.bones[n].tail_local - arm_data.bones[n].head_local).length
                    for n in ALL_BONES}
        lat_axis = (1.0, 0.0, 0.0)      # 横向轴：绕它转 = 前后俯仰
        dep_axis = (0.0, 1.0, 0.0)      # 前后轴：绕它转 = 左右侧倾
        up_axis = (0.0, 0.0, 1.0)       # 竖直轴：绕它转 = 转身
        Fn = np.array(Vector(fwd).normalized()[:], dtype=np.float64)   # numpy 版（与数组运算）
        F = Vector(fwd).normalized()                                   # mathutils 版（与 Vector 运算）
        # 角色右手在 -X ⇒ 右侧单位向量 = (-1,0,0)；左侧反之
        sgn_r = -1.0 if right_is_minus else 1.0
        SIDE = {"R": Vector((sgn_r, 0.0, 0.0)), "L": Vector((-sgn_r, 0.0, 0.0))}
        # hips 位移：世界(装备空间)向量 → 骨局部向量（basis.location 走的是骨局部轴）
        HIPS_M0 = arm_data.bones["hips"].matrix_local.to_3x3()
        # 腿的静置脚踝/脚尖（用于 IK 目标）
        ankle_rest = {lg: np.array(J["ankle_" + lg]) for lg in ("L", "R")}
        toe_rest = {lg: np.array(J["toe_" + lg]) for lg in ("L", "R")}
        hip_rest = {lg: np.array(J["hip_" + lg]) for lg in ("L", "R")}
        knee_rest = {lg: np.array(J["knee_" + lg]) for lg in ("L", "R")}
        L1 = float(np.linalg.norm(knee_rest["L"] - hip_rest["L"]))
        L2 = float(np.linalg.norm(ankle_rest["L"] - knee_rest["L"]))
        log("腿长 L1(大腿)=%.5f L2(小腿)=%.5f  (H=%.5f)" % (L1, L2, H))

        def leg_ik(lg, hip_pos, ankle_target):
            """2 连杆 IK：给定髋位与脚踝目标，返回 (大腿方向, 小腿方向, 膝位)"""
            Pv = np.array(ankle_target) - np.array(hip_pos)
            d = float(np.linalg.norm(Pv))
            d = max(abs(L1 - L2) + 1e-4, min(L1 + L2 - 1e-4, d))
            dirv = Pv / max(1e-9, float(np.linalg.norm(Pv)))
            ca = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
            al = math.acos(max(-1.0, min(1.0, ca)))
            bend = Fn.copy()                      # 膝盖朝前
            ax = np.cross(dirv, bend)
            if np.linalg.norm(ax) < 1e-6:
                ax = np.cross(dirv, np.array(UP))
            ax = ax / np.linalg.norm(ax)
            best = None
            for sgn in (+1.0, -1.0):
                q = Quaternion(Vector(list(ax)), sgn * al)
                td = q.to_matrix() @ Vector(list(dirv))
                kn = np.array(hip_pos) + L1 * np.array(td[:], dtype=np.float64)
                score = float(np.dot((kn - np.array(hip_pos)) / max(1e-9, L1), bend))
                if best is None or score > best[0]:
                    best = (score, np.array(td[:], dtype=np.float64), kn)
            _, thigh_d, knee_p = best
            shin_d = np.array(ankle_target) - knee_p
            return tuple(thigh_d), tuple(shin_d), knee_p

        arm_obj.animation_data_create()
        pb = arm_obj.pose.bones
        for b in pb:
            b.rotation_mode = "QUATERNION"

        def apply_frame(aname, ph, f):
            """算好这一帧所有骨的 basis 并打关键帧"""
            w = 2 * math.pi * ph
            s1, c1 = math.sin(w), math.cos(w)
            s2 = math.sin(2 * w)
            hips_loc = Vector((0.0, 0.0, 0.0)); hips_q = Quaternion((1, 0, 0, 0))
            spines = {}          # name -> (axis, deg)
            arms = {}            # name -> ('axis'|'dir', ...)
            ankle_tgt = {lg: ankle_rest[lg].copy() for lg in ("L", "R")}
            toe_lift = {lg: 0.0 for lg in ("L", "R")}

            if aname == "01_呼吸":
                hips_loc = Vector((0.030 * H * s1, 0.0, -0.010 * H * (0.5 - 0.5 * c1)))
                hips_q = Quaternion(Vector(up_axis), math.radians(1.4 * s1))
                spines = {"spine": (lat_axis, 1.6 * s1), "chest": (lat_axis, -2.4 * s1),
                          "neck": (lat_axis, 0.9 * s1), "head": (dep_axis, 1.2 * c1)}
                for lg in ("L", "R"):
                    arms["shoulder_" + lg] = ("axis", up_axis, -1.6 * s1 * (1 if lg == "L" else -1))
                    arms["upper_arm_" + lg] = ("axis", dep_axis, 2.2 * (1 if lg == "L" else -1) * (0.5 + 0.5 * s1))
                    arms["forearm_" + lg] = ("axis", lat_axis, -3.0 * s1)
                # 轮流提踵：L 在 sin>0 时抬，R 在 sin<0 时抬（各 ~16° ⇒ 脚尖位移 ≈4.2%H）
                toe_lift = {"L": math.radians(16.0) * max(0.0, s1),
                            "R": math.radians(16.0) * max(0.0, -s1)}

            elif aname == "02_打招呼":
                # 🔴 实测偏离（写进文档）：网格的**右臂已被烘焙成"手扶头发"姿势**，
                #    而左右对称骨架的右臂骨在静置（下垂）位 ⇒ 右臂骨管到的是**躯干**顶点
                #    （见 bone_ownership：右臂骨质心 |u| 偏小、偏离骨轴大）。旋转右臂 >~40°
                #    会把躯干壳拉成拉丝。为不假绿：**挥手改由左臂执行**（左上肢是本网格上
                #    唯一"几何与骨骼一致"的臂），右臂只给 ≤12° 的安全小角（读数仍记骨级位移）。
                prog = math.sin(math.pi * ph)
                wob = math.sin(2 * math.pi * ph * 2.0)
                hips_loc = Vector((0.020 * H * prog, 0.0, -0.008 * H * prog))
                hips_q = Quaternion(Vector(up_axis), math.radians(3.0 * prog))
                spines = {"spine": (dep_axis, -3.5 * prog), "chest": (dep_axis, -5.0 * prog),
                          "neck": (lat_axis, -5.0 * prog), "head": (up_axis, -6.0 * prog)}
                Sl = SIDE["L"]
                arms["shoulder_L"] = ("axis", dep_axis, 20.0 * prog * (-sgn_r) * (-1.0))
                arms["upper_arm_L"] = ("dirb", Sl * 0.42 + Vector(UP) * 0.88 + F * (0.10 + 0.10 * wob), prog)
                arms["forearm_L"] = ("dirb", Sl * 0.30 + Vector(UP) * 0.90 + F * (0.20 + 0.25 * wob), prog)
                arms["hand_L"] = ("dirb", Sl * (0.25 + 0.35 * wob) + Vector(UP) * 0.92, prog)
                # 右臂：安全小角（≤12°），只作陪衬
                arms["shoulder_R"] = ("axis", dep_axis, -6.0 * prog * (-sgn_r))
                arms["upper_arm_R"] = ("axis", lat_axis, -12.0 * prog)
                arms["forearm_R"] = ("axis", lat_axis, -12.0 * prog)
                # 重心移到右腿：左腿承重下沉 + 左脚原地碾转；右脚整体离地
                toe_lift["L"] = math.radians(19.0) * prog
                toe_lift["R"] = math.radians(18.0) * prog
                ankle_tgt["L"] = (ankle_rest["L"] + Fn * 0.014 * H * prog
                                  + np.array([0.0, 0.0, 0.016 * H * prog]))
                ankle_tgt["R"] = (ankle_rest["R"] + Fn * 0.015 * H * prog
                                  + np.array([-sgn_r * 0.008 * H * prog, 0.0, 0.0]))

            elif aname == "03_走两步":
                g = 2 * math.pi * ph * 2.0            # 两个完整步态周期
                hips_loc = Vector((0.016 * H * math.sin(g), 0.0, -0.012 * H * abs(math.sin(g))))
                hips_q = Quaternion(Vector(up_axis), math.radians(7.0 * math.sin(g)))
                spines = {"spine": (up_axis, -3.5 * math.sin(g)), "chest": (up_axis, -2.5 * math.sin(g + math.pi)),
                          "neck": (dep_axis, 2.0 * math.sin(g)), "head": (dep_axis, 2.5 * math.sin(g + math.pi))}
                for lg, phase in (("L", 0.0), ("R", math.pi)):
                    s = math.sin(g + phase)
                    sw = max(0.0, s)                  # 摆动相
                    # 🟠 关节限位（实测结论：该服装壳在大角度髋屈曲+大摆臂下会被拉出拉丝）
                    #    步幅 0.085H→0.072H、抬脚 22°→18°、摆臂 30°→24°、前臂去掉常数偏移
                    step = 0.060 * H
                    ankle_tgt[lg] = (ankle_rest[lg]
                                     + Fn * step * s
                                     + np.array(UP) * (0.045 * H * sw))
                    toe_lift[lg] = math.radians(15.0) * sw
                    arms["shoulder_" + lg] = ("axis", up_axis, -3.0 * (-s) * (1 if lg == "L" else -1))
                    arms["upper_arm_" + lg] = ("axis", lat_axis, -24.0 * (-s))
                    arms["forearm_" + lg] = ("axis", lat_axis, -20.0 * sw)
                    arms["hand_" + lg] = ("axis", dep_axis, 6.0 * (-s))

            elif aname == "04_转身":
                turn = math.sin(math.pi * ph)          # 0→1→0
                base = math.radians(55.0 * turn)
                hips_loc = Vector((0.0, -0.010 * H * turn, -0.006 * H * turn))
                hips_q = Quaternion(Vector(up_axis), base)
                spines = {"spine": (up_axis, 18.0 * turn), "chest": (up_axis, 9.0 * turn),
                          "neck": (up_axis, 7.0 * turn), "head": (up_axis, 12.0 * turn)}
                for lg in ("L", "R"):
                    v = ankle_rest[lg] - np.array([cx, cd, ankle_rest[lg][2]])
                    q = Quaternion(Vector(up_axis), base)
                    nv = q.to_matrix() @ Vector(list(v))
                    ankle_tgt[lg] = np.array([cx, cd, ankle_rest[lg][2]]) + np.array(nv[:], dtype=np.float64)
                    arms["shoulder_" + lg] = ("axis", up_axis, -6.0 * turn * (1 if lg == "L" else -1))
                    arms["upper_arm_" + lg] = ("axis", lat_axis, -12.0 * turn)
                    arms["forearm_" + lg] = ("axis", lat_axis, -16.0 * turn)
                    toe_lift[lg] = math.radians(10.0) * turn

            elif aname == "05_蹲起":
                cyc = 0.5 - 0.5 * math.cos(2 * math.pi * ph)            # 0→1→0
                depth = cyc
                hips_loc = Vector((0.0, -0.055 * H * depth, -0.235 * H * depth))
                hips_q = Quaternion(Vector(lat_axis), math.radians(-9.0 * depth))
                spines = {"spine": (lat_axis, 16.0 * depth), "chest": (lat_axis, 7.0 * depth),
                          "neck": (lat_axis, -9.0 * depth), "head": (lat_axis, -7.0 * depth)}
                for lg in ("L", "R"):
                    arms["shoulder_" + lg] = ("axis", up_axis, -4.0 * depth * (1 if lg == "L" else -1))
                    arms["upper_arm_" + lg] = ("axis", lat_axis, -34.0 * depth)
                    arms["forearm_" + lg] = ("axis", lat_axis, -30.0 * depth)
                    arms["hand_" + lg] = ("axis", lat_axis, -14.0 * depth)
                    toe_lift[lg] = math.radians(20.0) * depth

            elif aname == "06_伸懒腰":
                upp = math.sin(math.pi * ph)
                hips_loc = Vector((0.0, 0.012 * H * upp, 0.010 * H * upp))
                hips_q = Quaternion(Vector(lat_axis), math.radians(-6.0 * upp))
                spines = {"spine": (lat_axis, -17.0 * upp), "chest": (lat_axis, -20.0 * upp),
                          "neck": (lat_axis, -14.0 * upp), "head": (lat_axis, -12.0 * upp)}
                # 左上肢：几何与骨骼一致 ⇒ 可全举；右上肢：烘焙姿势 ⇒ 限幅到小目标
                Sl, Sr = SIDE["L"], SIDE["R"]
                arms["shoulder_L"] = ("dirb", Vector(UP) * 0.86 + Sl * 0.32, upp)
                arms["upper_arm_L"] = ("dirb", Vector(UP) * 0.90 + Sl * 0.34 + F * 0.16, upp)
                arms["forearm_L"] = ("dirb", Vector(UP) * 0.95 + Sl * 0.20 + F * 0.10, upp)
                arms["hand_L"] = ("dirb", Vector(UP) * 0.97 + Sl * 0.12, upp)
                arms["shoulder_R"] = ("axis", dep_axis, -7.0 * upp * (-sgn_r))
                arms["upper_arm_R"] = ("axis", lat_axis, -14.0 * upp)
                arms["forearm_R"] = ("axis", lat_axis, -14.0 * upp)
                for lg in ("L", "R"):
                    toe_lift[lg] = math.radians(24.0) * upp

            # ---- 写关键帧 ----
            for b in pb:
                b.rotation_quaternion = (1, 0, 0, 0)
                b.location = (0, 0, 0)
            # hips：hips_loc 上面写的是**世界(装备空间)位移**，这里换成骨局部位移
            loc_local = HIPS_M0.inverted() @ Vector(hips_loc[:])
            hb = pb["hips"]; hb.rotation_quaternion = hips_q; hb.location = loc_local
            hb.keyframe_insert("rotation_quaternion", frame=f)
            hb.keyframe_insert("location", frame=f)
            pose_hips = P.base("hips", None) @ Matrix.Translation(loc_local) @ hips_q.to_matrix().to_4x4()
            poses = {"hips": pose_hips}
            # 脊柱链
            for nm in ("spine", "chest", "neck", "head"):
                ax, dg = spines.get(nm, (lat_axis, 0.0))
                q, pm = P.by_axis(nm, poses[BONE_PARENT[nm]], ax, dg)
                pb[nm].rotation_quaternion = q
                pb[nm].keyframe_insert("rotation_quaternion", frame=f)
                poses[nm] = pm
            # 腿（IK：髋位由 hips 姿态决定，脚踝目标给定）
            for lg in ("L", "R"):
                base_t = P.base("thigh_" + lg, poses["hips"])
                hip_pos = np.array(base_t.translation[:], dtype=np.float64)
                tgt = ankle_tgt[lg].copy()
                td, sd, kp = leg_ik(lg, hip_pos, tgt)
                q, pm = P.by_dir("thigh_" + lg, poses["hips"], td)
                pb["thigh_" + lg].rotation_quaternion = q
                pb["thigh_" + lg].keyframe_insert("rotation_quaternion", frame=f)
                poses["thigh_" + lg] = pm
                q, pm2 = P.by_dir("shin_" + lg, pm, sd)
                pb["shin_" + lg].rotation_quaternion = q
                pb["shin_" + lg].keyframe_insert("rotation_quaternion", frame=f)
                poses["shin_" + lg] = pm2
                # 脚：绕踝按 toe_lift 抬（绕横向轴）
                q, pm3 = P.by_axis("foot_" + lg, pm2, lat_axis, -math.degrees(toe_lift[lg]))
                pb["foot_" + lg].rotation_quaternion = q
                pb["foot_" + lg].keyframe_insert("rotation_quaternion", frame=f)
                poses["foot_" + lg] = pm3
            # 臂
            for lg in ("L", "R"):
                for nm in ("shoulder", "upper_arm", "forearm", "hand"):
                    full = nm + "_" + lg
                    spec_a = arms.get(full)
                    par = poses[BONE_PARENT[full]]
                    if spec_a is None:
                        q = Quaternion((1, 0, 0, 0)); pm = P.base(full, par)
                    elif spec_a[0] == "axis":
                        q, pm = P.by_axis(full, par, spec_a[1], spec_a[2])
                    elif spec_a[0] == "dirb":
                        q, pm = P.by_dirb(full, par, spec_a[1], spec_a[2])
                    else:
                        q, pm = P.by_dir(full, par, spec_a[1])
                    pb[full].rotation_quaternion = q
                    pb[full].keyframe_insert("rotation_quaternion", frame=f)
                    poses[full] = pm

        for aname, nframes, adesc in ACTIONS:
            act = bpy.data.actions.new(aname)
            act.use_fake_user = True
            arm_obj.animation_data.action = act
            t0 = time.time()
            for f in range(0, nframes + 1, FRAME_STEP):
                apply_frame(aname, f / float(nframes), f)
            report["actions"][aname] = {"desc": adesc, "frames": nframes,
                                        "keyframes": list(range(0, nframes + 1, FRAME_STEP)),
                                        "fcurves": len(act.fcurves),
                                        "build_seconds": round(time.time() - t0, 2)}
            log("动作 %-8s 帧0..%-3d 关键帧=%d fcurve=%d (%.1fs)"
                % (aname, nframes, len(report["actions"][aname]["keyframes"]), len(act.fcurves),
                   report["actions"][aname]["build_seconds"]))

        # ---- 1.11 落盘 blend + rig_core --------------------------------
        try:
            bpy.ops.wm.save_as_mainfile(filepath=blend_path)
            log("已存 blend %s (%d 字节)" % (blend_path, os.path.getsize(blend_path)))
            report["proxy"]["blend_bytes"] = os.path.getsize(blend_path)
        except Exception as ex:
            report["errors"].append("存 blend 失败: %r" % (ex,))
        rig = {"H": H, "aabb_min": [float(v) for v in mn], "aabb_max": [float(v) for v in mx],
               "cx": cx, "cd": cd, "key_of": key_of, "right_is_minus": right_is_minus,
               "forward": [float(v) for v in fwd],
               "proxy_verts": v_px, "proxy_polys": p_px, "full_verts": v_full, "full_polys": p_full,
               "bones": [b.name for b in arm_data.bones], "end_bones": END_KEYS, "fps": FPS,
               "bone_lengths": {k: round(float(v), 6) for k, v in bone_len.items()},
               "stage_ratio": {"end_effector_min": 0.03, "squat_hip_min": 0.05, "foot_lift_min": 0.01},
               "L1": L1, "L2": L2}
        json.dump(rig, open(core_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        mem.snap("after_actions")

    # ============================================================ 阶段 2：逐帧读数
    if not rig:
        rig = json.load(open(core_path, encoding="utf-8"))
    from mathutils import Vector
    scn = bpy.context.scene
    arm_obj = bpy.data.objects["DH_Armature"]
    mesh_obj = bpy.data.objects["DH_Body"]
    H = float(rig["H"])
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    trace_ok = False
    if any(s in args.stages for s in ("export", "render")) or "rig" in args.stages:
        nv = len(mesh_obj.data.vertices)
        rng = np.random.default_rng(20261008)
        sample_idx = np.sort(rng.choice(nv, size=min(240, nv), replace=False))

        def wmat(name):
            return arm_obj.matrix_world @ arm_obj.pose.bones[name].matrix

        def jang(name):
            b = arm_obj.data.bones[name]
            R = (b.matrix_local.to_3x3().inverted() @ arm_obj.pose.bones[name].matrix.to_3x3())
            q = R.to_quaternion()
            return 2.0 * math.degrees(math.acos(max(-1.0, min(1.0, abs(q.w)))))

        def samp():
            dg = bpy.context.evaluated_depsgraph_get()
            mev = mesh_obj.evaluated_get(dg).to_mesh()
            arr = np.empty(len(mev.vertices) * 3, dtype=np.float64)
            mev.vertices.foreach_get("co", arr)
            out = arr.reshape(-1, 3)[sample_idx].copy()
            mesh_obj.evaluated_get(dg).to_mesh_clear()
            return out

        trace = {"fps": FPS, "height_units": H, "unit_note": "位移单位 = 模型自身单位；阈值按身高百分比",
                 "stage_ratio": rig["stage_ratio"], "end_bones": END_KEYS,
                 "all_bones": ALL_BONES,
                 "sample_vertex_count": int(len(sample_idx)),
                 "sample_vertex_index": [int(v) for v in sample_idx[:16]], "actions": {}}
        for aname, nframes, adesc in ACTIONS:
            act = bpy.data.actions.get(aname)
            if act is None:
                report["errors"].append("找不到动作 " + aname); continue
            arm_obj.animation_data.action = act
            nf = int(round(act.frame_range[1]))
            rows, base = [], None
            for f in range(0, nf + 1):
                scn.frame_set(f)
                row = {"f": f}
                for nm in ALL_BONES:
                    row["A_" + nm] = round(jang(nm), 4)
                    row["H_" + nm] = [round(c, 6) for c in (arm_obj.matrix_world @ arm_obj.pose.bones[nm].head)]
                    row["T_" + nm] = [round(c, 6) for c in (arm_obj.matrix_world @ arm_obj.pose.bones[nm].tail)]
                sd = samp()
                if base is None:
                    base = sd.copy()
                dv = np.linalg.norm(sd - base, axis=1)
                row["vmax"] = round(float(dv.max()), 6)
                row["vmean"] = round(float(dv.mean()), 6)
                rows.append(row)
            ee = {}
            for k in END_KEYS:
                cum = sum(math.dist(rows[i + 1]["T_" + k], rows[i]["T_" + k]) for i in range(len(rows) - 1))
                cum_h = sum(math.dist(rows[i + 1]["H_" + k], rows[i]["H_" + k]) for i in range(len(rows) - 1))
                ee[k] = {"tail_cum_disp": round(cum, 6), "head_cum_disp": round(cum_h, 6),
                         "tail_cum_ratio_of_H": round(cum / H, 6), "head_cum_ratio_of_H": round(cum_h / H, 6),
                         "tail_max_from_first": round(max(math.dist(r["T_" + k], rows[0]["T_" + k]) for r in rows), 6),
                         "tail_z_series": [round(r["T_" + k][2], 6) for r in rows],
                         "tail_rest": rows[0]["T_" + k]}
            trace["actions"][aname] = {"frames": nf, "desc": adesc, "rows": rows, "end_effectors": ee,
                                       "hip_head_z": [round(r["H_hips"][2], 6) for r in rows]}
            log("读数 %-8s 末端 tail 累计位移(单位 / %%H): %s" % (aname, "  ".join(
                ["%s=%.4f(%.2f%%)" % (k, ee[k]["tail_cum_disp"], ee[k]["tail_cum_ratio_of_H"] * 100)
                 for k in END_KEYS])))
        tp = os.path.join(out_root, "trace.json")
        json.dump(trace, open(tp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        report["trace"] = {"path": tp, "bytes": os.path.getsize(tp)}
        log("trace.json 落盘 %d 字节" % os.path.getsize(tp))
        mem.snap("after_trace")
        trace_ok = True

    # ============================================================ 阶段 3：导出 GLB
    if "export" in args.stages:
        bpy.ops.object.select_all(action="DESELECT")
        arm_obj.select_set(True); mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = arm_obj
        glb_out = os.path.join(out_root, "dh_rigged.glb")
        base_kw = dict(filepath=glb_out, export_format="GLB", use_selection=True,
                       export_animations=True, export_animation_mode="ACTIONS",
                       export_skins=True, export_yup=True)
        try:
            bpy.ops.export_scene.gltf(**base_kw, export_force_sampling=True,
                                      export_optimize_animation_size=False,
                                      export_bake_animation=True)
        except TypeError as ex:
            log("导出参数退化（%s）" % ex)
            bpy.ops.export_scene.gltf(**base_kw)
        mem.snap("after_export")
        rb = open(glb_out, "rb").read()
        jl2 = struct.unpack_from("<I", rb, 12)[0]
        J2 = json.loads(rb[20:20 + jl2].decode("utf-8"))
        anims = J2.get("animations") or []
        report["export"] = {
            "path": glb_out, "bytes": len(rb), "magic": rb[:4].decode("ascii", "replace"),
            "version": struct.unpack_from("<I", rb, 4)[0],
            "declared_length": struct.unpack_from("<I", rb, 8)[0],
            "length_matches": struct.unpack_from("<I", rb, 8)[0] == len(rb),
            "animation_count": len(anims),
            "animation_names": [a.get("name") for a in anims],
            "channel_count": sum(len(a.get("channels", [])) for a in anims),
            "sampler_count": sum(len(a.get("samplers", [])) for a in anims),
            "channels_per_anim": {a.get("name"): len(a.get("channels", [])) for a in anims},
            "skin_count": len(J2.get("skins") or []),
            "skins_joints": [len(s.get("joints", [])) for s in (J2.get("skins") or [])],
            "nodes": len(J2.get("nodes", [])), "meshes": len(J2.get("meshes", [])),
            "accessors": len(J2.get("accessors", []))}
        e = report["export"]
        log("导出 %s %d 字节 anims=%d channels=%d samplers=%d skins=%s"
            % (glb_out, e["bytes"], e["animation_count"], e["channel_count"], e["sampler_count"],
               e["skins_joints"]))
        del rb, J2

    # ============================================================ 阶段 4：渲染帧
    if "render" in args.stages:
        W, Hh = [int(v) for v in args.res.lower().split("x")]
        if args.hd and not args.legacy_look:
            W, Hh = 1080, 1350
        cx = float(rig["cx"]); cd = float(rig["cd"]); zmin = float(rig["aabb_min"][2])
        fwdv = Vector(rig.get("forward", [0.0, -1.0, 0.0])).normalized()
        ctr = Vector((cx, cd, zmin + H * 0.52))
        scn.render.resolution_x, scn.render.resolution_y = W, Hh
        scn.render.resolution_percentage = 100
        scn.render.image_settings.file_format = "PNG"
        look = {"legacy": bool(args.legacy_look), "resolution": [W, Hh]}

        # ---- 4.1 灯光 / 背景 / 地面（旧档过曝是"发灰发白 + 乳白斑"的主因之一） --
        if args.legacy_look:
            energies = (700.0, 300.0, 300.0); lsize = 2.4
            world_col, world_str = (0.28, 0.30, 0.34, 1.0), 1.0
            cam_type, cam_lens, cam_dist, cam_up = "ORTHO", 0.0, 3.0 * H, 0.0
        else:
            energies = (120.0, 40.0, 65.0); lsize = 1.5
            world_col, world_str = (0.22, 0.24, 0.28, 1.0), 0.10
            cam_type, cam_lens, cam_dist, cam_up = "PERSP", 70.0, 2.55 * H, 0.24 * H
        cam_data = bpy.data.cameras.new("DH_Cam")
        cam = bpy.data.objects.new("DH_Cam", cam_data)
        scn.collection.objects.link(cam)
        cam_data.type = cam_type
        if cam_type == "ORTHO":
            cam_data.ortho_scale = H * 1.30
            cam.location = ctr + fwdv * cam_dist
        else:
            cam_data.lens = cam_lens
            cam.location = ctr + fwdv * cam_dist + Vector((0.0, 0.0, cam_up))
        cam.rotation_mode = "XYZ"
        cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
        scn.camera = cam
        look["camera"] = {"type": cam_type, "lens": cam_data.lens, "dist": round(cam_dist, 4),
                          "height_offset": round(cam_up, 4)}
        lights = [("DH_Key", (1.7, -2.0, 1.75)), ("DH_Fill", (-2.0, -1.3, 1.05)),
                  ("DH_Rim", (0.35, 2.1, 1.55))]
        for (nm, loc), en in zip(lights, energies):
            ld = bpy.data.lights.new(nm, "AREA"); ld.energy = en; ld.size = lsize
            try:
                ld.shadow_soft_size = 0.06
            except Exception:
                pass
            lo = bpy.data.objects.new(nm, ld); scn.collection.objects.link(lo)
            lo.location = Vector(loc) + Vector((cx, cd, zmin))
            lo.rotation_euler = (ctr - lo.location).to_track_quat("-Z", "Y").to_euler()
        look["lights_W"] = {"DH_Key": energies[0], "DH_Fill": energies[1], "DH_Rim": energies[2],
                            "size_m": lsize}
        if not args.legacy_look:
            try:
                bpy.ops.mesh.primitive_plane_add(size=8.0, location=(cx, cd, zmin - 0.0005))
                fl = bpy.context.active_object; fl.name = "DH_Floor"
                fm = bpy.data.materials.new("DH_FloorMat"); fm.use_nodes = True
                fb = fm.node_tree.nodes.get("Principled BSDF")
                if fb:
                    fb.inputs["Base Color"].default_value = (0.34, 0.34, 0.36, 1.0)
                    fb.inputs["Roughness"].default_value = 0.85
                fl.data.materials.append(fm)
                look["floor"] = {"size": 8.0, "base_color": [0.34, 0.34, 0.36], "roughness": 0.85,
                                 "z": round(zmin - 0.0005, 5), "purpose": "接触阴影/落地感"}
            except Exception as ex:
                report["notes"].append("地面创建失败: %r" % (ex,))
        wd = bpy.data.worlds.new("DH_W"); wd.use_nodes = True
        try:
            bg = wd.node_tree.nodes["Background"]
            bg.inputs[0].default_value = world_col
            bg.inputs[1].default_value = world_str
        except Exception:
            pass
        scn.world = wd
        look["world"] = {"color": list(world_col[:3]), "strength": world_str}

        # ---- 4.2 色彩管理（旧档 AgX + look None ⇒ 发灰） --------------------
        cm = {}
        try:
            scn.view_settings.view_transform = "AgX"
            scn.view_settings.look = "None" if args.legacy_look else "AgX - Punchy"
            scn.view_settings.exposure = 0.0 if args.legacy_look else 0.25
        except Exception as ex:
            cm["error"] = repr(ex)
        cm.update({"view_transform": scn.view_settings.view_transform,
                   "look": scn.view_settings.look, "exposure": scn.view_settings.exposure,
                   "gamma": scn.view_settings.gamma})
        look["color_management"] = cm

        # ---- 4.3 材质：确认法线真接上 + 皮革清漆 + 皮肤单开一份 --------------
        if not args.legacy_look:
            try:
                split_skin_material(mesh_obj, report)
            except Exception as ex:
                report["notes"].append("渲染阶段材质分离失败: %r" % (ex,))
        mats = []
        for mat in bpy.data.materials:
            if not mat.use_nodes or mat.name.startswith("DH_") or mat.name.endswith("_Skin_"):
                continue
            nodes = {n.type: n for n in mat.node_tree.nodes}
            bs = nodes.get("BSDF_PRINCIPLED")
            nmn = nodes.get("NORMAL_MAP")
            rec = {"material": mat.name, "normal_map_node": bool(nmn),
                   "normal_map_wired": bool(nmn and any(o.is_linked for o in nmn.outputs)),
                   "normal_strength": (float(nmn.inputs["Strength"].default_value) if nmn else None),
                   "normal_space": (nmn.space if nmn else None)}
            if bs is not None and not args.legacy_look:
                bs.inputs["Roughness"].default_value = 0.42
                for k, v in (("Coat Weight", 0.12), ("Coat Roughness", 0.25),
                             ("Subsurface Weight", 0.0), ("Specular IOR Level", 0.50)):
                    if k in bs.inputs:
                        try:
                            bs.inputs[k].default_value = v
                        except Exception:
                            pass
                if "Subsurface Radius" in bs.inputs:
                    try:
                        bs.inputs["Subsurface Radius"].default_value = (0.006, 0.003, 0.0015)
                    except Exception:
                        pass
                rec["applied"] = {"Roughness": 0.42, "Coat Weight": 0.12, "Coat Roughness": 0.25,
                                  "Subsurface Weight": 0.0, "Specular IOR Level": 0.50,
                                  "Subsurface Radius": [0.006, 0.003, 0.0015],
                                  "note": "单材质网格：皮革/皮肤无法按部位分离 ⇒ 同一 BSDF 统一上清漆+轻微次表面"}
            mats.append(rec)
        look["materials"] = mats

        # ---- 4.4 引擎：Cycles 优先（HIP kernel 实测载入失败 ⇒ 退 CPU） --------
        eng_req = args.engine or ("CYCLES" if (args.hero or args.diag) else "BLENDER_EEVEE_NEXT")
        eng_used = None
        for eng in ([eng_req] if eng_req else []) + ["BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"]:
            try:
                scn.render.engine = eng; eng_used = eng; break
            except Exception:
                continue
        nsamp = args.samples or (128 if eng_used == "CYCLES" else 256)
        if eng_used == "CYCLES":
            try:
                scn.cycles.device = "CPU"; scn.cycles.samples = nsamp
                scn.cycles.use_denoising = True; scn.cycles.max_bounces = 8
                scn.cycles.use_adaptive_sampling = True
            except Exception as ex:
                report["notes"].append("Cycles setup: %r" % (ex,))
        elif eng_used == "BLENDER_EEVEE_NEXT":
            try:
                scn.eevee.taa_render_samples = nsamp
            except Exception:
                pass
        look.update({"engine_requested": eng_req, "engine_used": eng_used, "samples": nsamp,
                     "frames_per_action": args.render_frames})
        report["render"] = look
        log("渲染档: 引擎=%s 采样=%d 分辨率=%dx%d 色彩=%s/%s 主灯=%sW 地面=%s"
            % (eng_used, nsamp, W, Hh, cm.get("view_transform"), cm.get("look"), energies[0],
               ("有" if "floor" in look else "无")))

        def render_to(fp):
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            scn.render.filepath = fp
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            return {"path": fp, "bytes": (os.path.getsize(fp) if os.path.exists(fp) else 0),
                    "sec": round(time.time() - t0, 2)}

        # ---- 4.5 六段动作帧 ------------------------------------------------
        sfx = "hd_" if (args.hd and not args.legacy_look) else ("after_" if not args.legacy_look else "")
        frames = {}
        t_all = time.time()
        for aname, nframes, _d in ACTIONS:
            act = bpy.data.actions.get(aname)
            if act is None:
                continue
            arm_obj.animation_data.action = act
            nf = int(round(act.frame_range[1]))
            sel = [int(round(v)) for v in np.linspace(0, nf, args.render_frames)]
            d = os.path.join(frames_root, aname); os.makedirs(d, exist_ok=True)
            got = []
            for f in sel:
                scn.frame_set(f)
                got.append(dict({"f": f}, **render_to(os.path.join(d, "%sf%03d.png" % (sfx, f)))))
            frames[aname] = got
            log("渲染 %-8s %d 张 (%.1fs) 首张=%d 字节" % (aname, len(got),
                sum(g["sec"] for g in got), got[0]["bytes"] if got else 0))
            mem.snap("after_render_" + aname)
        report["render"]["frames"] = frames
        report["render"]["total_files"] = sum(len(v) for v in frames.values())
        report["render"]["total_seconds"] = round(time.time() - t_all, 1)

        # ---- 4.6 诊断帧：静置姿势 / 法线开关 / 髋部放大 ---------------------
        if args.diag:
            dg = os.path.join(frames_root, "_诊断"); os.makedirs(dg, exist_ok=True)
            diag = {}
            act_w = bpy.data.actions.get("03_走两步")
            arm_obj.animation_data.action = None
            for b in arm_obj.pose.bones:
                b.rotation_quaternion = (1, 0, 0, 0); b.location = (0, 0, 0)
            bpy.context.view_layer.update()
            diag["rest_pose"] = render_to(os.path.join(dg, "rest_pose.png"))
            if act_w is not None:
                arm_obj.animation_data.action = act_w
                scn.frame_set(21)
                diag["normal_on_f21"] = render_to(os.path.join(dg, "normal_on_f21.png"))
                nmn = None
                for mat in bpy.data.materials:
                    if mat.use_nodes:
                        for n in mat.node_tree.nodes:
                            if n.type == "NORMAL_MAP":
                                nmn = n
                if nmn is not None:
                    old_s = float(nmn.inputs["Strength"].default_value)
                    nmn.inputs["Strength"].default_value = 0.0
                    diag["normal_off_f21"] = render_to(os.path.join(dg, "normal_off_f21.png"))
                    nmn.inputs["Strength"].default_value = old_s
                    diag["normal_strength_restored"] = old_s
            cam2d = bpy.data.cameras.new("DH_Zoom"); cam2 = bpy.data.objects.new("DH_Zoom", cam2d)
            scn.collection.objects.link(cam2)
            cam2d.type = "ORTHO"; cam2d.ortho_scale = H * 0.40
            zc = Vector((cx, cd, zmin + H * 0.50))
            cam2.location = zc + fwdv * (2.0 * H)
            cam2.rotation_euler = (zc - cam2.location).to_track_quat("-Z", "Y").to_euler()
            old_cam = scn.camera; old_res = (scn.render.resolution_x, scn.render.resolution_y)
            scn.camera = cam2
            scn.render.resolution_x, scn.render.resolution_y = 900, 900
            if act_w is not None:
                arm_obj.animation_data.action = act_w; scn.frame_set(21)
                diag["hip_zoom_f21"] = render_to(os.path.join(dg, "hip_zoom_f21.png"))
            arm_obj.animation_data.action = None
            for b in arm_obj.pose.bones:
                b.rotation_quaternion = (1, 0, 0, 0); b.location = (0, 0, 0)
            bpy.context.view_layer.update()
            diag["hip_zoom_rest"] = render_to(os.path.join(dg, "hip_zoom_rest.png"))
            scn.camera = old_cam
            scn.render.resolution_x, scn.render.resolution_y = old_res
            report["render"]["diag"] = diag
            log("诊断帧完成: %s" % sorted(diag.keys()))

        # ---- 4.7 英雄静帧（正面全身 / 3-4 侧 / 面部特写） -------------------
        if args.hero:
            hW, hH = [int(v) for v in args.hero_res.lower().split("x")]
            hdir = os.path.join(frames_root, "_英雄静帧"); os.makedirs(hdir, exist_ok=True)
            arm_obj.animation_data.action = bpy.data.actions.get("01_呼吸")
            scn.frame_set(24)
            hero = {}
            up = Vector((0.0, 0.0, 1.0))
            side = Vector(fwdv).cross(up).normalized()
            shots = [
                ("hero_front_full", ctr + fwdv * (2.35 * H) + up * (0.16 * H), ctr, 80.0, hW, hH),
                ("hero_3q_full", ctr + (fwdv * 0.80 + side * 0.62).normalized() * (2.35 * H)
                 + up * (0.16 * H), ctr, 80.0, hW, hH),
                ("hero_face_closeup", Vector((cx, cd, zmin + 0.885 * H))
                 + (fwdv * 0.62 + side * 0.22).normalized() * (0.85 * H) + up * (0.02 * H),
                 Vector((cx, cd, zmin + 0.885 * H)), 135.0, hW, int(round(hW * 1.25))),
            ]
            for nm, loc, tgt, lens, rw, rh in shots:
                cam_data.type = "PERSP"; cam_data.lens = lens
                cam.location = loc
                cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
                scn.render.resolution_x, scn.render.resolution_y = rw, rh
                hero[nm] = dict({"lens": lens, "res": [rw, rh]},
                                **render_to(os.path.join(hdir, nm + ".png")))
                log("英雄静帧 %-18s %dx%d %.1fs %d 字节" % (nm, rw, rh, hero[nm]["sec"], hero[nm]["bytes"]))
                mem.snap("after_" + nm)
            report["render"]["hero"] = hero
            scn.render.resolution_x, scn.render.resolution_y = W, Hh

    report["ok"] = len(report["errors"]) == 0
    report["memory"] = mem.rows
    write_report(out_root, report)
    log("完成 ok=%s 错误=%d" % (report["ok"], len(report["errors"])))
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        print("[dh_rig] 🔴 异常终止:", flush=True)
        traceback.print_exc()
        try:
            sys.stdout.flush()
        except Exception:
            pass
        rc = 1
    sys.exit(rc)
