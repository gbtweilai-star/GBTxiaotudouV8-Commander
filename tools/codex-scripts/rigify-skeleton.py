# -*- coding: utf-8 -*-
"""rigify-skeleton —— 用 Blender **Rigify**（自带专业绑骨件）生成标准人形骨架，落成唯一真相源。

主人令（2026-10-09）：「安装专业化多功能骨架绑定工具，别自己手搓的跟什么是的」。
本件就是那条：骨架**不再手写数字**，改由 Rigify 的 human metarig 现算，导出 rig.json：
  · 来源可复跑（命令写在文件头）· VRM Humanoid 标准骨名 · 世界坐标 + 正视投影 + 比例
用法： blender -b --factory-startup -P tools/codex-scripts/rigify-skeleton.py -- --out <rig.json>
"""
import json
import math
import sys
from pathlib import Path

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path("rig.json")

# Rigify 链名 → VRM Humanoid 标准骨名（映射表是**对照标准**，不是我编的坐标）
# 注：Rigify human metarig **没有**叫 hips 的骨 —— 它的骨盆就是 spine。
#    故 hips→spine / spine→spine.001 / chest→spine.002，逐段上移（**对照标准**，不是手写坐标）。
VRM_MAP = {
    "spine": "hips", "spine.001": "spine", "spine.002": "chest", "spine.003": "upperChest",
    "spine.004": "neck", "spine.006": "head",
    "shoulder.L": "leftShoulder", "upper_arm.L": "leftUpperArm", "forearm.L": "leftLowerArm",
    "hand.L": "leftHand",
    "shoulder.R": "rightShoulder", "upper_arm.R": "rightUpperArm", "forearm.R": "rightLowerArm",
    "hand.R": "rightHand",
    "thigh.L": "leftUpperLeg", "shin.L": "leftLowerLeg", "foot.L": "leftFoot", "toe.L": "leftToes",
    "thigh.R": "rightUpperLeg", "shin.R": "rightLowerLeg", "foot.R": "rightFoot", "toe.R": "rightToes",
}


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.preferences.addon_enable(module="rigify")
    bpy.ops.object.armature_human_metarig_add()
    ob = bpy.context.object
    bones = {}
    for b in ob.data.bones:
        h = ob.matrix_world @ b.head_local
        t = ob.matrix_world @ b.tail_local
        bones[b.name] = {"head": [round(h.x, 5), round(h.y, 5), round(h.z, 5)],
                         "tail": [round(t.x, 5), round(t.y, 5), round(t.z, 5)],
                         "parent": (b.parent.name if b.parent else None)}
    # 关键骨（VRM 映射到的那些）
    key = {rig: bones[r] for r, rig in VRM_MAP.items() if r in bones}
    miss = [rig for r, rig in VRM_MAP.items() if r not in bones]
    # 量比例：以**足底到头顶**为全高（专业口径：用脚尖最低点与 head.tail 最高点）
    zs = [v for b in bones.values() for v in (b["head"][2], b["tail"][2])]
    zmin, zmax = min(zs), max(zs)
    height = zmax - zmin
    # 正视投影：X 右为 +，Z 上为 + ⇒ 2D (x, -z)；再归一化到「全高 = 1」
    def proj(p):
        return [round(p[0] / height, 5), round((zmax - p[2]) / height, 5)]
    k2d = {rig: {"head": proj(v["head"]), "tail": proj(v["tail"]), "parent": v["parent"]}
           for rig, v in key.items()}
    head_top = bones.get("spine.006", {}).get("tail") or [0, 0, zmax]
    data = {
        "_来源": "Blender Rigify human metarig（专业绑骨件，非手搓）",
        "_可复跑": "blender -b --factory-startup -P tools/codex-scripts/rigify-skeleton.py -- --out <rig.json>",
        "_blender": bpy.app.version_string,
        "骨总数": len(bones),
        "VRM映射": VRM_MAP, "未映射": miss,
        "全高": round(height, 5), "足底z": round(zmin, 5), "头顶z": round(zmax, 5),
        "头高比例": round((zmax - (bones.get("spine.006", {}).get("head") or [0, 0, zmax])[2]) / height, 5),
        "关键骨_世界": key, "关键骨_正视归一": k2d,
        "全部骨名": sorted(bones),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    # ── 产出面板用的 rig-data.js：**按页面既有 schema 反算**（骨名不换，免得打断动画）────
    #    页面渲染口径（读源码 index.html:1131/1158 得到，不是我猜的）：
    #      每个关节 transform = translate(off) · rotate(rest+Δ)；骨头画在**局部 +Y** 上、长 len
    #      局部 +Y 经 rotate(a) 后指向世界 (-sin a, cos a) ⇒ rest=0 且 len>0 = 朝下，len<0 = 朝上
    #      off 在**父骨的局部系**里 ⇒ 必须用 M(-A_parent) 把世界位移转回父系。
    PAGE = [
        ("pelvis", "spine", "髋", 40, None), ("spine", "spine.001", "脊", 34, "pelvis"),
        ("chest", "spine.002", "胸", 44, "spine"), ("neck", "spine.004", "颈", 16, "chest"),
        ("head", "spine.006", "头", 44, "neck"),
        ("clavicleL", "shoulder.L", "肩(锁骨)", 14, "chest"),
        ("upperArmL", "upper_arm.L", "上臂", 13, "clavicleL"),
        ("foreArmL", "forearm.L", "前臂", 11, "upperArmL"),
        ("handL", "hand.L", "手", 10, "foreArmL"),
        ("clavicleR", "shoulder.R", "肩(锁骨)", 14, "chest"),
        ("upperArmR", "upper_arm.R", "上臂", 13, "clavicleR"),
        ("foreArmR", "forearm.R", "前臂", 11, "upperArmR"),
        ("handR", "hand.R", "手", 10, "foreArmR"),
        ("thighL", "thigh.L", "大腿", 22, "pelvis"), ("shinL", "shin.L", "小腿", 18, "thighL"),
        ("footL", "foot.L", "脚", 14, "shinL"), ("toeL", "toe.L", "脚趾", 10, "footL"),
        ("thighR", "thigh.R", "大腿", 22, "pelvis"), ("shinR", "shin.R", "小腿", 18, "thighR"),
        ("footR", "foot.R", "脚", 14, "shinR"), ("toeR", "toe.R", "脚趾", 10, "footR"),
    ]
    RIG_OF = {nm: rg for nm, rg, _, _, _ in PAGE}
    view_h = 491.4
    # 世界 2D（y 自上而下），单位 = view_h
    W2 = {r: [[k2d[VRM_MAP[r]]["head"][0] * view_h, k2d[VRM_MAP[r]]["head"][1] * view_h],
              [k2d[VRM_MAP[r]]["tail"][0] * view_h, k2d[VRM_MAP[r]]["tail"][1] * view_h]]
          for _, r, _, _, _ in PAGE if VRM_MAP.get(r) in k2d}
    # 每根骨的绝对静息角（度）：局部 +Y 指向世界 (-sin a, cos a)
    ABS = {}
    for _, r, _, _, _ in PAGE:
        if r in W2:
            (hx, hy), (tx, ty) = W2[r]
            ABS[r] = math.degrees(math.atan2(-(tx - hx), (ty - hy)))
    rows = []
    CUM = {}          # 沿链累加的**有效**静息角（页面就是这么合成的：child = parent 的 rotate · 自己的 rest）
    for name, rig, cn, w, par in PAGE:
        if rig not in W2:
            continue
        (hx, hy), (tx, ty) = W2[rig]
        a_abs = ABS[rig]
        a_par = CUM.get(par, 0.0) if par else 0.0      # ⚠️ 用**累加角**，不是单骨绝对角
        rel = a_abs - a_par
        while rel > 180:
            rel -= 360
        while rel <= -180:
            rel += 360
        ln = math.hypot(tx - hx, ty - hy)
        # 页面口径偏好：|rest| 控制在 ±90 内，超出就把 len 取负（等价方向，子骨局部系不翻）
        if abs(rel) > 90:
            rel -= 180 if rel > 0 else -180
            ln = -ln
        if par:
            ph = W2[RIG_OF[par]][0]
            dxw, dyw = hx - ph[0], hy - ph[1]
            ca, sa = math.cos(math.radians(a_par)), math.sin(math.radians(a_par))
            off = [round(ca * dxw + sa * dyw, 2), round(-sa * dxw + ca * dyw, 2)]
        else:
            off = [0.0, 0.0]
        CUM[name] = a_par + rel
        rows.append({"n": name, "p": (par or "root"), "off": off, "len": round(ln, 2), "w": w,
                     "rest": round(rel, 2),
                     "side": ("L" if name.endswith("L") else "R" if name.endswith("R") else "C"),
                     "cn": cn, "head2d": [round(hx, 2), round(hy, 2)], "rigify": rig})
    js = OUT.parent / "rig-data.js"
    js.write_text("/* 由 tools/codex-scripts/rigify-skeleton.py 生成 —— Blender Rigify 标准人形骨架\n"
                  "   手改无效（重生成即覆盖）；来源：Blender rigify human metarig */\n"
                  "window.GBT_RIG = " + json.dumps(
                      {"来源": data["_来源"], "_blender": data["_blender"], "全高": data["全高"],
                       "视图全高": view_h, "骨总数": data["骨总数"],
                       "比例": {"髋到足底占全高": round(1.0 - k2d.get("leftUpperLeg", {}).get("head", [0, 0])[1], 4),
                                "膝占全高": k2d.get("leftLowerLeg", {}).get("head", [0, 0])[1],
                                "踝占全高": k2d.get("leftFoot", {}).get("head", [0, 0])[1],
                                "肩占全高": k2d.get("leftUpperArm", {}).get("head", [0, 0])[1]},
                       "骨": rows}, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print("RIG_DATA_JS", js, "| 骨条数", len(rows))
    print("RIG_JSON", OUT)
    print("骨总数", len(bones), "| 关键骨", len(key), "| 未映射", miss)
    print("全高", round(height, 4), "| 足底z", round(zmin, 4), "| 头顶z", round(zmax, 4))
    for k in ("hips", "head", "leftUpperLeg", "leftLowerLeg", "leftFoot", "leftToes", "leftUpperArm"):
        if k in k2d:
            print("  %-14s 正视归一 head=%s" % (k, k2d[k]["head"]))


main()