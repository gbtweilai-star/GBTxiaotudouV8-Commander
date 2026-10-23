# -*- coding: utf-8 -*-
r"""数字人棚拍渲染（render-shot）—— **观色统一入口**（一套设置，反复复核同一件事）。

主人令（2026-10-10）：「继续给我打磨一下**观色和动作自然**」

## 上一版渲出来我看到的三个"观色"毛病（自查，不遮掩）
1. **平**：只有三点光打在纯黑上 ⇒ 像产品图，人物和背景没有分离，脸缺立体。
2. **灰**：没有环境光/环境色 ⇒ 暗部死黑、亮部发白（高光溢出），皮肤没有血色。
3. **飘**：没有地面/接触阴影 ⇒ 人像贴在空气里。

## 这一版观色七条（每条都可指认）
① **世界环境**：竖向渐变（天光偏冷、地面反光偏暖）—— 给暗部填色，不再死黑。
② **主光暖 / 辅光冷**：主光 5000K 暖、辅光 7500K 冷，冷暖对冲才有立体。
③ **轮廓光（rim）**：背后强光勾边，把人与背景分开。
④ **色调映射 AgX + 曝光**：高光不再溢出成白块（上一版脸就是过曝发白的）。
⑤ **接触阴影**：脚下加一张阴影承接面，人不"飘"。
⑥ **取景按本体顶点算**（上一版被杂件撑坏包围盒，取景拍歪过）。
⑦ **渲染帧可取动画某一时刻** ⇒ 能看"动作自然不自然"，不只渲 T-pose。

用法：py -3.14 -X utf8 tools/digihuman/render-shot.py [--anim walk --t 0.3 --out state/x.png]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
GLB = ROOT / "projects" / "digital-human" / "out" / "dh-v2-rigged.glb"


PRESET = ROOT / "state" / "digihuman" / "render-preset.json"


def preset() -> dict:
    """**观色单一真源**：取景/光照/色调映射从 state/digihuman/render-preset.json 读。

    🔴 2026-10-10 补：原来这些参数**散在脚本里**（lens=85、MarginV、三点光能量…），
    没人能复核"这一版观色和上一版差在哪"，也 diff 不出来。抽成配置后可 diff、可复核，
    并由渲染回执记下**预设哈希** ⇒ 门能咬住"观色换了没有"。
    """
    import json
    if PRESET.is_file():
        return json.loads(PRESET.read_text(encoding="utf-8"))
    return {}


def _cam_at(cam, loc, look):
    """把相机摆到 loc 并看向 look —— **显式构造基向量，不用 to_track_quat**。

    🔴🔴 2026-10-10 **这是整整两轮排查的定案结论**（我连查 13 步才逼出来）：
      · 原来用 (look - loc).to_track_quat("-Z", "Y").to_matrix() —— 它给出的解**上方向是反的**，
        渲出来**人是倒的**（腿在上、头在中）。
      · 显式按「右 = 前 × 世界上 / 上 = 右 × 前」构造，**保证画面上方向 = 世界 +Z**，
        最小复现实测**人是正的**。
      · 为什么难查：这毛病**两种渲染器（EEVEE/Cycles）、两套机位、清不清动画都一模一样**
        —— 看上去像「模型歪了/取景错了/渲染器坏了」，其实一直是**相机的上方向**。
        **而且我先前拿一张同样倒的图当「好图」做参照，把自己带偏了两轮。**
    """
    from mathutils import Matrix
    fwd = (look - loc).normalized()
    right = fwd.cross(Vector((0.0, 0.0, 1.0))).normalized()
    up = right.cross(fwd).normalized()                 # ← 保证 = 世界 +Z 方向（画面上）
    cam.matrix_world = Matrix(((right.x, up.x, -fwd.x, loc.x),
                               (right.y, up.y, -fwd.y, loc.y),
                               (right.z, up.z, -fwd.z, loc.z),
                               (0.0, 0.0, 0.0, 1.0)))
    return up


def setup_world(cool=(0.05, 0.08, 0.16), warm=(0.16, 0.12, 0.09)):
    """① 竖向渐变世界 —— 上冷下暖，给暗部填色。"""
    w = bpy.data.worlds.new("gbt_world")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.35
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*warm, 1.0)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (*cool, 1.0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    tex = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tex.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def add_light(name, loc, target, energy, size, temp, kind="AREA"):
    L = bpy.data.lights.new(name, type=kind)
    L.energy = energy
    L.size = size
    if hasattr(L, "color"):
        k = temp
        # 简易色温近似（5000K 暖白 / 7500K 冷白）
        if k <= 5200:
            L.color = (1.0, 0.92, 0.82)
        elif k >= 7200:
            L.color = (0.78, 0.86, 1.0)
        else:
            L.color = (1.0, 1.0, 1.0)
    ob = bpy.data.objects.new(name, L)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


def _has_pose(a) -> bool:
    """是否带了姿势（单帧 --pose 或序列 --pose-seq）。

    🔴 2026-10-13 踩过两次：REST/ POSE 的分支只判断了 --pose，
    于是 --pose-seq 摆好的逐帧姿势被 `pose_position = "REST"` 整批抹掉
    （现象＝编译出的帧明明有 108°，渲出来还是 T-pose）。凡新增姿势入口，
    必须同时进这个判断。
    """
    return bool(getattr(a, "pose", "") or getattr(a, "pose_seq", ""))


_NM_SHORT = {"hips": "mixamorig:Hips", "spine": "mixamorig:Spine",
             "chest": "mixamorig:Spine2", "neck": "mixamorig:Neck",
             "head": "mixamorig:Head"}


def _apply_pose(arm, pose) -> int:
    """把 {骨名: [rx,ry,rz]} 施加到骨架上，返回真应用到的骨数。

    骨名解析顺序：原名 → 短名映射（skeleton.json 那套）→ 加 mixamorig: 前缀。
    实测：GLB 里是 65 根 mixamo 命名骨，而语义表用短名 ⇒ 不解析就会"应用 0 根"。
    """
    if arm is None:
        return 0
    n = 0
    for bn, v in pose.items():
        pb = None
        for cand in (bn, _NM_SHORT.get(bn, ""), "mixamorig:" + str(bn)):
            if cand and arm.pose.bones.get(cand):
                pb = arm.pose.bones.get(cand)
                break
        if pb is None:
            continue
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (math.radians(float(v[0])), math.radians(float(v[1])),
                             math.radians(float(v[2])))
        n += 1
    bpy.context.view_layer.update()
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="数字人棚拍渲染（观色统一入口）")
    ap.add_argument("--glb", default=str(GLB))
    ap.add_argument("--anim", default="", help="动画名（留空=不播动画，渲绑定姿势）")
    ap.add_argument("--t", type=float, default=0.0, help="取动画第几秒")
    ap.add_argument("--out", default=str(ROOT / "state" / "dh-v2-preview.png"))
    ap.add_argument("--w", type=int, default=1080)
    ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("--half", action="store_true", help="半身取景（看脸/纹理细节）")
    # 2026-10-19 加（主人令「画面清晰动作自然」）：取景余量可调，默认 1.18 保旧行为；
    # 1.02~1.06 = 人物占满画幅（同样的像素数，人物分辨率更高 ⇒ 更清楚）。
    ap.add_argument("--margin", type=float, default=1.18,
                    help="取景留白余量（1.18=默认；1.02=人物占满画幅）")
    ap.add_argument("--face", action="store_true",
                    help="脸部近景：按 **颈+头** 的骨顶点组取包围盒（看脸用，不猜倍数）")
    ap.add_argument("--engine", default="", help="渲染引擎（留空=EEVEE_NEXT；可给 CYCLES）")
    ap.add_argument("--tpose-ref", action="store_true",
                    help="**规范化 T-pose 参考图**：正面 + 白底 + 全身（补 S0/S2 的入口件）")
    ap.add_argument("--pose", default="",
                    help="关节姿势 JSON：{\"骨名\": [rx,ry,rz](度)} 或 {\"骨名\": {\"rot\": [..], \"loc\": [..]}}")
    ap.add_argument("--pose-seq", default="",
                    help="姿势**序列** JSON（list[pose]）：逐帧施加并渲染到 --out 目录")
    # 🔴 2026-10-10 踩过：**Blender 会把 --background/--python 一起塞进 sys.argv**，
    #    直接 parse_args() 会报 "blender.exe: error: unrecognized arguments: --background --python ..."
    #    （看着像 Blender 报错，其实是**我自己脚本的 argparse** 在报）。标准解法：只取 -- 之后的。
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    a = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a.glb)
    # 🔴🔴 2026-10-10 **这一条是我整整两轮排查的答案**：
    #   Blender 的 glTF 导入器会为**骨架**建一个**骨形代理球**（Icosphere · 42 顶点 · 尺寸 2×2×2），
    #   放进名为 **glTF_not_exported** 的集合里 —— 那个集合**不参与导出，但默认可见、可渲染**。
    #   ⇒ 每张渲染图里都有个 2 米大的球把角色罩住（"人像躺着 / 半截 / 细节少一半"全是它）。
    #   证据：导入后 users_collection=['glTF_not_exported'] · hide_render=False。
    #   为什么两种渲染器、两套机位、清不清动画**都一模一样** —— 因为它是**几何**，不是渲染/相机问题。
    #   ⇒ 导入后**一律清掉这个集合**（连同它的对象）。
    _helpers = [c for c in bpy.data.collections if c.name.startswith("glTF_not_exported")]
    _dropped = []
    for _c in _helpers:
        for _o in list(_c.objects):
            _dropped.append(_o.name)
            bpy.data.objects.remove(_o, do_unlink=True)
        bpy.data.collections.remove(_c)
    if _dropped:
        print("  清掉导入器辅助件（glTF_not_exported）:", _dropped)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    body = max(meshes, key=lambda o: len(o.data.vertices))
    print("本体 %s · 顶点 %d" % (body.name[:30], len(body.data.vertices)))

    # ⑥ 材质基色打磨（2026-10-13 主人令「自然逼真人类」）
    #   现读：全身**只有一张贴图**（皮肤与衣服同一图集）⇒ 只能做整体偏色。
    #   必须用**乘法**（暖度=乘 (1+w, 1, 1-w)）：加法会把纯黑的衣服也提亮。
    _mg = (preset().get("材质打磨") or {})
    _warm = float(_mg.get("暖度", 0.0))
    _msat = float(_mg.get("饱和度", 1.0))
    if _warm or abs(_msat - 1.0) > 1e-6:
        _n = 0
        for _m in bpy.data.materials:
            if not _m.use_nodes:
                continue
            _pr = next((x for x in _m.node_tree.nodes if x.type == "BSDF_PRINCIPLED"), None)
            if not _pr:
                continue
            _bc = _pr.inputs["Base Color"]
            if not _bc.is_linked:
                continue
            _src = _bc.links[0].from_socket
            _nt2 = _m.node_tree
            _nt2.links.remove(_bc.links[0])
            _hs2 = _nt2.nodes.new("ShaderNodeHueSaturation")
            _hs2.inputs["Saturation"].default_value = _msat
            _mul = _nt2.nodes.new("ShaderNodeMixRGB")
            _mul.blend_type = "MULTIPLY"
            _mul.inputs["Fac"].default_value = 1.0
            _mul.inputs["Color2"].default_value = (1.0 + _warm, 1.0, max(0.0, 1.0 - _warm), 1.0)
            _nt2.links.new(_src, _hs2.inputs["Color"])
            _nt2.links.new(_hs2.outputs["Color"], _mul.inputs["Color1"])
            _nt2.links.new(_mul.outputs["Color"], _bc)
            _n += 1
        print("  材质打磨(预设)：暖度 %+.3f · 饱和度 %.2f · 改了 %d 个材质" % (_warm, _msat, _n))

    # ── 触手控制动作的口（2026-10-13 主人令「触手化作骨架操控数字人的所有动作」）──
    #   传一份「骨名 → 角度」的 JSON，就能任意摆姿势；并且**当场打印关键骨的世界坐标**，
    #   让"控制有没有真生效"变成读数，而不是"看起来好像动了"。
    if getattr(a, "pose", ""):
        import json as _json
        spec = _json.loads(Path(a.pose).read_text(encoding="utf-8"))
        _arm = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
        if _arm is None:
            print("  ⛔ 场景里没有骨架，--pose 无从施加")
        else:
            _NAMEMAP = {
                "hips": "mixamorig:Hips", "spine": "mixamorig:Spine",
                "chest": "mixamorig:Spine2", "neck": "mixamorig:Neck",
                "head": "mixamorig:Head",
                "shoulder_L": "mixamorig:LeftShoulder", "upper_arm_L": "mixamorig:LeftArm",
                "forearm_L": "mixamorig:LeftForeArm", "hand_L": "mixamorig:LeftHand",
                "shoulder_R": "mixamorig:RightShoulder", "upper_arm_R": "mixamorig:RightArm",
                "forearm_R": "mixamorig:RightForeArm", "hand_R": "mixamorig:RightHand",
                "thigh_L": "mixamorig:LeftUpLeg", "shin_L": "mixamorig:LeftLeg",
                "foot_L": "mixamorig:LeftFoot",
                "thigh_R": "mixamorig:RightUpLeg", "shin_R": "mixamorig:RightLeg",
                "foot_R": "mixamorig:RightFoot",
            }

            def _bone(name):
                for cand in (name, _NAMEMAP.get(name, ""), "mixamorig:" + name):
                    if cand and _arm.pose.bones.get(cand):
                        return _arm.pose.bones[cand]
                return None

            _ok, _miss = [], []
            # 🔴 2026-10-13：model-rigged-anim.glb 自带动作；**动作会每帧覆盖静态姿势**
            #    （实测：设了 7 根骨、世界坐标确实变了，但出图字节与没摆之前一模一样）。
            #    ⇒ 施姿势前先清动作、并把姿势模式钉成 POSE。
            for _ob in bpy.context.scene.objects:
                if _ob.type == "ARMATURE":
                    if getattr(_ob, "animation_data", None) and _ob.animation_data.action:
                        _ob.animation_data.action = None
                    _ob.data.pose_position = "POSE"
            print("  已清掉骨架动作并把姿势模式钉为 POSE（否则动画会盖住静态姿势）")
            for _bn, _v in spec.items():
                if str(_bn).startswith("_"):
                    continue          # 跳过 "_口径" 这类注释键
                _pb = _bone(_bn)
                if _pb is None:
                    _miss.append(_bn)
                    continue
                _rot = _v.get("rot", [0, 0, 0]) if isinstance(_v, dict) else _v
                _pb.rotation_mode = "XYZ"
                _pb.rotation_euler = (math.radians(float(_rot[0])),
                                      math.radians(float(_rot[1])),
                                      math.radians(float(_rot[2])))
                if isinstance(_v, dict) and _v.get("loc"):
                    _pb.location = tuple(float(x) for x in _v["loc"])
                _ok.append(_pb.name)
            bpy.context.view_layer.update()
            print("  姿势控制：应用 %d 根 · 未找到骨名 %s" % (len(_ok), _miss or "无"))
            for _bn in ("mixamorig:Hips", "mixamorig:Head", "mixamorig:LeftHand",
                        "mixamorig:RightHand", "mixamorig:LeftFoot", "mixamorig:RightFoot"):
                _pb = _bone(_bn)
                if _pb:
                    _w = _arm.matrix_world @ _pb.head
                    print("    %-8s 世界坐标 (%.3f, %.3f, %.3f)" % (_bn, _w.x, _w.y, _w.z))

    # 🔴 2026-10-10 **重大自纠**：先前我只在 --tpose-ref 模式里清动画，**普通模式没清** ⇒
    #    glTF 导入会自己把第一段动作挂上去 ⇒ 渲出来是 **idle/walk 姿势**、人倒着还被裁掉大半。
    #    而流水线**照样报 ✅**（我的三层门只看状态源/哈希/量规，**没一条看画面对不对**）。
    #    ==量规其实早就给了信号：废图的梯度方差 28.9，而全身图 50.6 —— 我看不懂而已。==
    #    ⇒ 渲染前**一律先清动画**（除非调用方显式 --anim 指定要播某段）。
    # 🔴🔴🔴 2026-10-10 **第二个根因，而且它推翻了这一条原来的写法**（实测数据在下面）：
    #    原来以为"清动画 = 回到绑定姿势" —— **不对**。实测：
    #      ① 导入后原样(带动画)          z 0.499 ~ 1.119  高 0.621
    #      ② 清动画后(本条原来的做法)      z 0.499 ~ 1.119  高 0.621   ← **与①一模一样**
    #      ③ 再设 pose_position = REST   z 0.000 ~ 0.979  高 **0.979**  ← 这才是绑定姿势
    #      残留旋转的 pose bone 数 = **42**（清了 action，骨头上的姿势值还在）
    #    ⇒ **清动画 ≠ 回绑定姿势**；必须显式把骨架切到 REST。
    #    而 REST 的高度 0.979 与**原始顶点**包围盒一致 ⇒ 我最初量的是对的，
    #    错在**渲染用了带姿势的网格**。上一轮我改用"求值后网格"只是让取景去迁就错的几何
    #    （治了裁切、没治姿势）——**这一条才是真修**。
    if not a.anim:
        _arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
        for _o in bpy.context.scene.objects:
            if _o.animation_data:
                _o.animation_data_clear()
        for _act in list(bpy.data.actions):
            bpy.data.actions.remove(_act)
        for _arm in _arms:
            # 🔴 2026-10-13：--pose 在场时**不许回 REST** —— REST 渲染的是绑定姿势，
            #    会把 --pose 摆好的静态姿势整批抹掉（实测：出图字节与 T-pose 版一模一样）。
            _arm.data.pose_position = "POSE" if _has_pose(a) else "REST"
        print("  姿势模式 %s（--pose %s）；清掉 action 数 = %d · 骨架 %d 根"
              % ("POSE" if _has_pose(a) else "REST",
                 "在场" if _has_pose(a) else "不在", len(bpy.data.actions), len(_arms)))

    if a.anim:
        arm = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
        if arm and arm.animation_data is None:
            arm.animation_data_create()
        acts = [x.name for x in bpy.data.actions]
        hit = next((n for n in acts if a.anim.lower() in n.lower()), None)
        if hit and arm:
            arm.animation_data.action = bpy.data.actions[hit]
            print("播放动画动作 %s @ %.2fs" % (hit, a.t))
        bpy.context.scene.frame_set(int(a.t * bpy.context.scene.render.fps))

    # 🔴🔴🔴 2026-10-10 **整整两轮排查的根因，就在这里**（20+ 步才逼出来）：
    #    原来用 **原始顶点**（body.data.vertices）算包围盒 —— 而**真正渲出来的是
    #    经过 Armature 修改器形变后的网格**。这两者可以**差到离谱**：
    #      原始:     z  0.000 ~ 0.979 （高 0.979）
    #      求值后:   z  0.499 ~ 1.119 （高 **0.621**）  ← 渲的就是这个
    #    ⇒ 取景按 0.979 算、画面上却只有 0.621 且**整体高了 0.499** ⇒
    #      相机瞄到的 z=0.489 **正好是它的脚底** ⇒ 人被顶出画外、顶部被切、只占 ~49%。
    #    为什么难查：① 现象像"相机坏了/模型歪了/渲染器坏了"，其实**几何被形变改过**；
    #      ② 我先前拿一张**同样被切的图**当"好图"做参照，把自己带偏两轮；
    #      ③ 量角器本身没错（标定证明相机对），错的是**我量错了对象**。
    #    ⇒ 一律用 **depsgraph 求值后的网格**算包围盒（那才是渲染真正用的那份）。
    # 🔴🔴 2026-10-10 **同一族的第四副副本**（前几副：清动画当回绑定姿势 · 注释说不用三点光 ·
    #    JS 按当前姿势量缩放）。这次是**取景基准没冻结**：
    #    上面那段按"**当前帧的求值网格**"算包围盒 —— 播动画时每帧姿势都不同
    #    ⇒ **相机跟着动作跑**：胶片里人一会儿大一会儿小、东倒西歪。
    #    实测证据：渲 6 帧 walk 拼胶片，帧间差 36.60，但**画面在跳**（不是动作在走）。
    #    ⇒ **取景基准必须先切 REST 量一遍、再切回去播动画**（基准是"人多大"，不是"这一帧多大多小"）。
    _arms0 = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    _saved_pp = [_a.data.pose_position for _a in _arms0]
    for _a in _arms0:
        _a.data.pose_position = "REST"          # 量基准时一律用绑定姿势
    bpy.context.view_layer.update()
    _dg = bpy.context.evaluated_depsgraph_get()
    _ev = body.evaluated_get(_dg)
    _me = _ev.to_mesh()
    ws = [_ev.matrix_world @ v.co for v in _me.vertices]
    _ev.to_mesh_clear()
    for _a, _s in zip(_arms0, _saved_pp):
        _a.data.pose_position = _s            # 量完立刻切回去（动画照播）
    bpy.context.view_layer.update()
    print("  取景基准：**冻结在绑定姿势**上量（顶点 %d / 原始 %d）· 当前姿势模式 %s"
          % (len(ws), len(body.data.vertices), _saved_pp[0] if _saved_pp else "无骨架"))
    # 🔴 2026-10-13 细节（主人令「所有的细节都要做到位」）：绑定姿势基准**盖不住大动作** ——
    #    实测把「举手过头」渲出来，手被裁到画外。⇒ 动作序列要按**整段姿势的包围盒并集**取景。
    #    实测对照（挥手，旧取景 = 只按绑定姿势）：顶边切掉举手、右边切掉平伸手；
    #    并集取景后两只手都进画（见 outputs/cloud/digital_human_selfintro/acts_cap/）。
    _frame_n = 1
    if getattr(a, "pose_seq", ""):
        _poses_p = json.loads(Path(a.pose_seq).read_text(encoding="utf-8"))
        _arm_p = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
        _pp_saved = _arm_p.data.pose_position if _arm_p else None
        if _arm_p:
            _arm_p.data.pose_position = "POSE"
        _pts = []
        for _p in _poses_p:
            _apply_pose(_arm_p, _p)
            _dg_p = bpy.context.evaluated_depsgraph_get()
            _ev_p = body.evaluated_get(_dg_p)
            _me_p = _ev_p.to_mesh()
            _pts.extend([_ev_p.matrix_world @ v.co for v in _me_p.vertices])
            _ev_p.to_mesh_clear()
        if _pts:
            _lo2 = Vector((min(p[i] for p in _pts) for i in range(3)))
            _hi2 = Vector((max(p[i] for p in _pts) for i in range(3)))
            print("  取景基准（动作序列并集 %d 帧）：z %.3f~%.3f · x %.3f~%.3f · y %.3f~%.3f"
                  % (len(_poses_p), _lo2.z, _hi2.z, _lo2.x, _hi2.x, _lo2.y, _hi2.y))
            ws = _pts
            _frame_n = len(_poses_p)
        if _arm_p:
            _arm_p.data.pose_position = _pp_saved or "POSE"
        bpy.context.view_layer.update()
    lo = Vector((min(p[i] for p in ws) for i in range(3)))
    hi = Vector((max(p[i] for p in ws) for i in range(3)))
    ctr = (lo + hi) / 2
    size = hi - lo
    H = size.z
    top = hi.z if not a.half else lo.z + H * 0.88
    # 🔴 2026-10-13 细节（主人问「清晰度你不会调嘛？」）：**近景要按"要看的部位"取景，不是抬底边**。
    #    原来 --half 只把底边抬 12%，而**宽度项（T-pose 臂展 0.95）**把相机顶到 4.69
    #    ⇒ 半身取景形同没裁：脸在全景里只占 ~100px，放大必糊（这不是渲染器的问题）。
    #    ⇒ 改成**骨顶点组定区域**：--half = 脊柱链+颈+头 · --face = 颈+头。
    #    （灯与地面的落点仍按全身 lo/H，不受影响——只改相机取景。）
    _reg = (("mixamorig:Head", "mixamorig:Neck") if getattr(a, "face", False) else
            (("mixamorig:Head", "mixamorig:Neck", "mixamorig:Spine2",
              "mixamorig:Spine1", "mixamorig:Spine") if a.half else None))
    if _reg:
        _grp = {body.vertex_groups[n].index for n in _reg if body.vertex_groups.get(n)}
        _rpts = [body.matrix_world @ v.co for v in body.data.vertices
                 if any(g.group in _grp and g.weight > 0.5 for g in v.groups)]
        if _rpts:
            lo = Vector((min(p[i] for p in _rpts) for i in range(3)))
            hi = Vector((max(p[i] for p in _rpts) for i in range(3)))
            ctr = (lo + hi) / 2
            size = hi - lo
            H = size.z
            top = hi.z
            print("  取景区域（%s · %d 顶点 · 骨顶点组）：z %.3f~%.3f · 宽 %.3f · 深 %.3f"
                  % ("face" if getattr(a, "face", False) else "half",
                     len(_rpts), lo.z, hi.z, hi.x - lo.x, hi.y - lo.y))

    # 🔴 2026-10-10 补：**规范化 T-pose 参考图**模式（S2 门五条：双臂水平/双腿直立/正面全身/无遮挡/白底）。
    #    为什么需要它：流水线 S0 的判据要 raw/phase2a-tpose/T-pose参考-规范化.png，
    #    而主人的新绑骨是从 Tripo 直接下来的、没走旧 S0 流程 ⇒ 那个入口件缺。
    #    正解不是"跳过 S0"，而是**从新绑骨自己渲一张合五条的参考图**（我这件本来就会渲）。
    if a.tpose_ref:
        # 🔴 2026-10-10 **我第一次渲出来是废的，而且流水线还报 14/14**（S2 判据只查文件在不在）。
        #    根因：我喂的是**带动画**的件（model-rigged-anim.glb），Blender 自动把第一段动作挂上去了，
        #    渲出来是 idle 姿势、不是 T-pose ⇒ 关键帧/取景全错，图像扭曲。
        #    ⇒ T-pose 参考图必须**先把动画清干净**，回到绑定姿势。
        # 🔴🔴 2026-10-10 **同一把刀，第二次落下**：我先前在这里只写了"清动画（回到绑定姿势）"——
        #    而**清动画根本回不到绑定姿势**（S12 那边实测：清完仍是 0.621 高的弯姿势，
        #    42 根 pose bone 上的姿势值还在；只有 pose_position=REST 才回到 0.979 的绑定姿势）。
        #    ⇒ 这条分支跟我刚修的 S12 那条是**同一个病**，一起治。
        #    （本分支上面的注释还写着"我第一次渲出来是废的，而流水线报 14/14" ——
        #      那次我只治到"清动画"就以为好了，其实没回绑定姿势。）
        for _o in bpy.context.scene.objects:
            if _o.animation_data:
                _o.animation_data_clear()
        for _act in list(bpy.data.actions):
            bpy.data.actions.remove(_act)
        for _arm in [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]:
            # 🔴 2026-10-13：这一句原来是无条件 REST，**会把 --pose 摆好的静态姿势抹掉**
            #    （REST 模式渲染绑定姿势，不理会 pose bone 的角度）⇒ 实测出图字节纹丝不动。
            if _has_pose(a):
                _arm.data.pose_position = "POSE"
                print("  --pose/--pose-seq 在场 ⇒ **保留 POSE 模式**（否则姿势被 REST 抹掉）")
            else:
                _arm.data.pose_position = "REST"   # ← 关键：显式回绑定姿势
            print("  姿势模式 %s；残留 action 数 = %d"
                  % (_arm.data.pose_position, len(bpy.data.actions)))
        # 正面正交 + 白底：不用三点光，用均匀环境光（无遮挡、无阴影、无色偏）
        w = bpy.data.worlds.new("white")
        bpy.context.scene.world = w
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
        # 🔴🔴 2026-10-10 **又一处"注释说一套、代码做一套"**：
        #    上面那行注释写的是「**不用三点光**，用均匀环境光（无遮挡、无阴影、无色偏）」，
        #    而代码紧接着就**加了三盏 220/160/120 的 AREA 灯** ⇒ 脸直接爆掉。
        #    实测：脸部高光占比 **66.041%**（旧值 66.741% —— **几乎没变**）
        #    ⇒ 说明「白脸」跟姿态无关，是**光照过曝**；我上一轮把姿态修好了，这张脸照样是白的。
        #    ⇒ 按它自己写的口径办：**只留白色世界，不加任何灯**（参考图本就该均匀无影无色偏）。
        w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.85
        cam_data2 = bpy.data.cameras.new("c2"); cam2 = bpy.data.objects.new("c2", cam_data2)
        bpy.context.scene.collection.objects.link(cam2)
        cam_data2.type = "ORTHO"
        cam_data2.ortho_scale = max(size.x, size.z) * 1.15
        look2 = Vector((ctr.x, ctr.y, ctr.z))
        cam2.location = (ctr.x, ctr.y - 3.0 * H, ctr.z)          # **正面**（不偏）
        _cam_at(cam2, Vector(cam2.location), look2)      # 同上：显式基向量，别用 to_track_quat
        bpy.context.scene.camera = cam2
        sc2 = bpy.context.scene
        sc2.render.engine = "BLENDER_EEVEE_NEXT"
        sc2.view_settings.view_transform = "Standard"           # 白底参考图不做胶片调色
        sc2.view_settings.exposure = 0.0
        sc2.render.film_transparent = False
        sc2.render.resolution_x, sc2.render.resolution_y = 1024, 1536
        sc2.render.filepath = a.out
        bpy.ops.render.render(write_still=True)
        print("T-pose 参考图 => %s (%d 字节) · 正交 scale %.3f"
              % (Path(a.out).name, Path(a.out).stat().st_size if Path(a.out).is_file() else 0,
                 cam_data2.ortho_scale))
        return 0

    setup_world()
    # ② 主光暖 5000K · ③ 辅光冷 7500K · ④ 轮廓光
    # 🔴 2026-10-13 修「假单一真源」：三点光原来**写死在脚本里**，改预设不改画面
    #    （实测改完 −2EV，像素统计一模一样），而 S12 的门却在哈希那个不生效的文件。
    _lp = (preset().get("三点光") or {})

    def _L(key, m0, e0, s0, k0):
        b = _lp.get(key) or {}
        return (list(b.get("位置倍数") or m0), float(b.get("能量", e0)),
                float(b.get("尺寸", s0)), float(b.get("色温K", k0)))

    mk, ek, sk, kk = _L("主光_key", (1.3, -1.5, 1.0), 900, 1.8, 5000)
    mf, ef, sf, kf = _L("辅光_fill", (-1.6, -1.0, 0.4), 320, 2.4, 7500)
    mr, er, sr, kr = _L("轮廓_rim", (-0.3, 1.7, 1.1), 700, 1.4, 6000)
    print("  三点光(预设)：key %.0fW/%.0fK · fill %.0fW/%.0fK · rim %.0fW/%.0fK"
          % (ek, kk, ef, kf, er, kr))
    add_light("key", (ctr.x + mk[0] * H, ctr.y + mk[1] * H, ctr.z + mk[2] * H), tuple(ctr), ek, sk, kk)
    add_light("fill", (ctr.x + mf[0] * H, ctr.y + mf[1] * H, ctr.z + mf[2] * H), tuple(ctr), ef, sf, kf)
    add_light("rim", (ctr.x + mr[0] * H, ctr.y + mr[1] * H, ctr.z + mr[2] * H), tuple(ctr), er, sr, kr)

    # ⑤ 接触阴影：脚下承接面
    bpy.ops.mesh.primitive_plane_add(size=H * 6, location=(ctr.x, ctr.y, lo.z - 0.005))
    floor = bpy.context.active_object
    fl = bpy.data.materials.new("floor")
    fl.use_nodes = True
    fl.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.055, 0.07, 1)
    fl.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
    floor.data.materials.append(fl)

    # 🔴 2026-10-10 第七刀（**我自己看出来的**：第一版渲出来人是倒的、还被裁到腰胯）。
    #    根因：我用**绝对单位**猜相机距离（ctr.y - H*1.9），而镜头是 **85mm 长焦**、视场很窄
    #    ⇒ 按 1.9H 摆根本框不下全身。正路是**从视场角反算距离**：
    #        d = (主体高度 / 2) / tan(垂直视场 / 2) × 余量
    #    这样无论镜头多长、人多大，取景都是稳的。
    subject_h = (top - lo.z) if a.half else (hi.z - lo.z)
    # 🔴 2026-10-13 细节：竖屏 9:16 的**可见宽度**装不下她的臂展（几何事实）⇒ 只按高度取景
    #   会把张开的手臂裁在画外（实测：T-pose 与举手动作的手都被切）。⇒ 高度与宽度**都算一遍取远的那个**。
    subject_w = max(abs(hi.x - lo.x), abs(hi.y - lo.y))
    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam_data.lens = 85
    cam_data.sensor_width = 36.0
    # 传感器：竖幅 1080x1920 ⇒ 垂直视场由 sensor_fit 决定
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_height = 36.0
    fov_v = 2.0 * math.atan(cam_data.sensor_height / (2.0 * cam_data.lens))
    _asp = float(a.w) / float(a.h)
    fov_h = 2.0 * math.atan((cam_data.sensor_height * _asp) / (2.0 * cam_data.lens))
    # 2026-10-19 加（主人令「画面清晰」）：留白余量原来写死 1.18 ⇒ 人物在 4K 里也偏小。
    # 改成可传参（默认仍 1.18 保旧行为）；要"人物占满画幅"就给 1.02~1.06。
    _margin = float(getattr(a, "margin", 0) or 1.18)
    dist = max((subject_h / 2.0) / math.tan(fov_v / 2.0),
               (subject_w / 2.0) / math.tan(fov_h / 2.0)) * _margin
    print("  取景距离：高 %.3f ⇒ %.2f · 宽 %.3f ⇒ %.2f · 取远 %.2f（宽高都算）"
          % (subject_h, (subject_h / 2.0) / math.tan(fov_v / 2.0) * _margin,
             subject_w, (subject_w / 2.0) / math.tan(fov_h / 2.0) * _margin, dist))
    look = Vector((ctr.x, ctr.y, lo.z + subject_h / 2.0))
    # 🔴 2026-10-13 细节：取景口径**落进回执**（原来只在 stdout 打一行，图换没换、按什么基准
    #    取景，事后无从复核）。回执里带基准/帧数/包围盒/宽高/距离 ⇒ 门与人都能对账。
    a._framing = {
        "基准": "动作序列并集" if getattr(a, "pose_seq", "") else "绑定姿势(REST)",
        "帧数": _frame_n, "余量": round(_margin, 3),
        "包围盒": {"x": [round(lo.x, 4), round(hi.x, 4)],
                   "y": [round(lo.y, 4), round(hi.y, 4)],
                   "z": [round(lo.z, 4), round(hi.z, 4)]},
        "subject_h": round(subject_h, 4), "subject_w": round(subject_w, 4),
        "距离": round(dist, 4), "看向": [round(v, 4) for v in tuple(look)],
        "垂直视场度": round(math.degrees(fov_v), 3), "水平视场度": round(math.degrees(fov_h), 3),
    }
    # 3/4 视角：绕竖轴偏 ~18°，不是正对
    # 🔴 2026-10-10 A/B 实测：3/4 偏移（x += sin(18°)*dist*0.55 ≈ +0.46）在**近景人像**上
    #    会把主体推成侧向透视，看起来像"躺着"（远处正交那种偏移没问题，近景不行）。
    #    早期那张好图（dh-v2-preview）用的就是**正对**。⇒ 偏角改为可由预设控，默认**正对**。
    ang = math.radians(float((preset().get("取景") or {}).get("3/4偏角_度", 0.0)))
    cam.location = (look.x + math.sin(ang) * dist * 0.55,
                    look.y - math.cos(ang) * dist,
                    look.z + subject_h * 0.04)
    # 🔴 2026-10-10 **这一条是我这一整轮的真凶**：
    #    原来写 cam.rotation_euler = (look - cam.location).to_track_quat("-Z","Y").to_euler()
    #    ⇒ 渲出来人**躺着**（相机朝正下方看地面），而**相机朝向矩阵读出来是单位阵**。
    #    ⇒ 改成**一次设定完整 matrix_world**（平移 × 旋转），不走 euler 往返；
    #      并在读 matrix_world 前先 view_layer.update()（否则读到的是没求值的旧值）。
    from mathutils import Matrix
    _cam_at(cam, Vector(cam.location), look)
    bpy.context.view_layer.update()
    bpy.context.scene.camera = cam
    print("取景：主体高 %.3f · 垂直视场 %.1f° · 相机距离 %.3f · 看向 %s"
          % (subject_h, math.degrees(fov_v), dist, tuple(round(x, 3) for x in look)))
    # 🔴 2026-10-10 加**相机自证**：光报"看向哪儿"不够 —— 渲出来是废图时，
    #    我看不出是位置错、朝向错、还是模型本身就歪。把真实位置与朝向矩阵打出来。
    _m = cam.matrix_world
    print("  相机位置 %s" % (tuple(round(v, 3) for v in cam.location),))
    print("  相机朝向矩阵行: %s" % " | ".join(
        str(tuple(round(v, 3) for v in _m[i][:3])) for i in range(3)))
    print("  模型包围盒: x %.3f~%.3f · y %.3f~%.3f · z %.3f~%.3f"
          % (lo.x, hi.x, lo.y, hi.y, lo.z, hi.z))

    sc = bpy.context.scene
    # 🔴 2026-10-10 顺手打两个**我从没验过的量**：相机真实垂直视场角 + 渲染引擎。
    #    我前面一直在算"取景应该对"，却从没问过**渲染器实际拿到的是不是那支镜头**。
    print("  相机 angle_y %.2f° · sensor_fit %s · sensor_height %.1f · lens %.1f"
          % (math.degrees(cam_data.angle_y), cam_data.sensor_fit,
             cam_data.sensor_height, cam_data.lens))
    sc.render.engine = a.engine or "BLENDER_EEVEE_NEXT"      # 可给 BLENDER_WORKBENCH 做诊断（不需灯）
    if a.engine == "CYCLES":
        sc.cycles.samples = 24
        sc.cycles.device = "CPU"
    print("  引擎 %s" % sc.render.engine)
    # ④ 色调映射（同样改接预设：观色单一真源）
    _tm = (preset().get("色调映射") or {})
    sc.view_settings.view_transform = str(_tm.get("view_transform", "AgX"))
    sc.view_settings.look = str(_tm.get("look", "AgX - Medium High Contrast"))
    sc.view_settings.exposure = float(_tm.get("exposure", 0.0))
    print("  色调映射(预设)：%s · %s · exposure %+.2f"
          % (sc.view_settings.view_transform, sc.view_settings.look,
             sc.view_settings.exposure))
    # ⑤ 饱和度（2026-10-13 加）：AgX 天生褪色，实测与原图还差约 30% 饱和度
    #    （脸 0.164 vs 0.267 · 胸甲 0.213 vs 0.319）⇒ 用合成器的 Hue/Sat 在**渲染内**补，
    #    不是事后 P 图。旋钮进预设＝仍是观色单一真源。
    _sat = float(_tm.get("饱和度", 1.0))
    if abs(_sat - 1.0) > 1e-6:
        sc.use_nodes = True
        _nt = sc.node_tree
        for _n in list(_nt.nodes):
            _nt.nodes.remove(_n)
        _rl = _nt.nodes.new("CompositorNodeRLayers")
        _hs = _nt.nodes.new("CompositorNodeHueSat")
        _hs.inputs["Saturation"].default_value = _sat
        _cp = _nt.nodes.new("CompositorNodeComposite")
        _nt.links.new(_rl.outputs["Image"], _hs.inputs["Image"])
        _nt.links.new(_hs.outputs["Image"], _cp.inputs["Image"])
        print("  饱和度(预设)：%.2f（合成器 Hue/Sat）" % _sat)
    sc.render.resolution_x, sc.render.resolution_y = a.w, a.h
    sc.render.film_transparent = False
    _seq = getattr(a, "pose_seq", "")
    if _seq:
        # 姿势序列：逐帧施加 → 逐帧渲染（动作库走这条路）
        import json as _j2
        _poses = _j2.loads(Path(_seq).read_text(encoding="utf-8"))
        _dir = Path(a.out)
        _dir.mkdir(parents=True, exist_ok=True)
        _arm2 = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
        _arm2.data.pose_position = "POSE"
        for _i, _p in enumerate(_poses):
            _applied = _apply_pose(_arm2, _p)
            sc.render.filepath = str(_dir / ("f%04d.png" % _i))
            bpy.ops.render.render(write_still=True)
        print("  姿势序列：渲了 %d 帧 -> %s（末帧应用 %d 根）"
              % (len(_poses), _dir, _applied))
    else:
        sc.render.filepath = a.out
        bpy.ops.render.render(write_still=True)
    out_p = Path(a.out)
    print("渲染 => %s (%d 字节)" % (out_p.name, out_p.stat().st_size if out_p.is_file() else 0))
    _sidecar(out_p, a)
    return 0


def _sidecar(out_p: Path, a) -> None:
    """**渲染回执**（绑到源 GLB 的哈希）—— 照 S2 那条假绿的教训：

    2026-10-10 在数字人 S2 上抓到的病是「复核记录没绑到图上 ⇒ 图换了照样放行」。
    渲染这条同理：**不记源哈希，就分不清这张图是哪个 rig 渲的**。
    ⇒ 每渲一次落一条边车（图 + 源 GLB 的 sha256 + 时间 + 参数），供 S12 的门比对。
    """
    import hashlib
    import json
    import time
    glb = Path(a.glb)
    sc = out_p.with_suffix(".json")
    rec = {"图": str(out_p), "源GLB": str(glb),
           "源sha256": hashlib.sha256(glb.read_bytes()).hexdigest() if glb.is_file() else "",
           "图sha256": hashlib.sha256(out_p.read_bytes()).hexdigest() if out_p.is_file() else "",
           "at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "取景": "正交正面白底（T-pose 参考）" if getattr(a, "tpose_ref", False) else "三点光 3/4 视角",
           "字节": out_p.stat().st_size if out_p.is_file() else 0}
    _fr = getattr(a, "_framing", None)
    if isinstance(_fr, dict):
        rec["取景读数"] = _fr
    if PRESET.is_file():
        rec["预设sha256"] = hashlib.sha256(PRESET.read_bytes()).hexdigest()
        rec["预设"] = str(PRESET.relative_to(ROOT)) if PRESET.is_relative_to(ROOT) else str(PRESET)
    sc.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("     回执 => %s（源 %s… · 图 %s…）"
          % (sc.name, rec["源sha256"][:12], rec["图sha256"][:12]))


if __name__ == "__main__":
    raise SystemExit(main())
