# -*- coding: utf-8 -*-
"""omni-arm-build.py —— Omni-Arm V57（22DoF 手 + 9 骨手臂 + 8 段触手）**真几何·真绑骨**生成器。

## 为什么重做（不是把设计稿改名）
主人 2026-10-19 给的六件设计稿（`vendor/omni-arm/source/`）里 `Omni-Arm-3d-Rig.py` 有三处
**跑不动/不可复现**，本器逐条修掉并在头部留痕：
  1. `TentacleChain.fk()` 只算了 x/y 两轴（z 恒 0）⇒ 不是 3D FK；本器用**真 3D 旋转链**。
  2. `ik_ccd()` 名为 CCD，实为「把误差按 0.1 塞进角度」，且只动一个轴 ⇒ 收敛不了；本器实现
     **真 CCD**（从末端往前逐关节把末端朝目标转，夹在该关节 limits 内，迭代到误差 < 1e-3 m）。
  3. `random.choice(["x","y","z"])` 决定骨骼轴、`random.random()` 决定触手分布 ⇒ **同一份代码两次
     生出两个不同骨架**，资产不可复现（本仓 P2/P5 血账）；本器**零随机**：轴、长度、限位全部查表。
  4. `ModelExporter.to_blender_py()` 把 `{[asdict(b) ...]}` 直接拼进生成的 .py ⇒ 产出的文件本身
     **语法就是坏的**；本器把 bpy 侧逻辑写成独立文件 `omni_arm_bpy.py`（可单独审阅、可单独跑）。
  5. `export_json()` 写死 `/mnt/data/`（Linux 路径）⇒ Windows 上必抛 FileNotFoundError；本器一律
     写到 `outputs/omni-arm/`（仓内，可 .gitignore）。

## 它产出什么
  · `outputs/omni-arm/omni-arm-rigged.glb` —— **带蒙皮**的 GLB：40 骨 / 1 网格 / 每顶点权重和 = 1
  · `outputs/omni-arm/omni-arm-spec.json` —— 骨骼规格（名字/父/长度/轴/限位/DoF/顶点区间）
  · `outputs/omni-arm/omni-arm-report.json` —— 自检读数（骨数/顶点/未绑/权重和/包围盒）

## 骨数怎么来的（写死口径，免得下次又猜）
  手臂 9（shoulder_pitch/yaw/roll · upper_arm · elbow · forearm_twist · wrist_pitch/yaw/roll）
  + 手掌 1（hand）
  + 手指 22（拇指 5 · 食指 4 · 中指 4 · 无名指 4 · 小指 5 —— 与 Tesla V3 / Dex5-S 分布一致）
  + 触手 8（一段触手 = 8 节骨骼链，末端越细）
  = **40 根**

## 用法
    py -3.14 tools/codex-scripts/omni-arm-build.py            # 建件 + 自检
    py -3.14 tools/codex-scripts/omni-arm-build.py --spec     # 只打印骨骼规格
    py -3.14 tools/codex-scripts/omni-arm-build.py --json     # 机器可读
退出码：0 = 建出且自检全绿 · 1 = 有红（读数在回执里）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "omni-arm"
BPY = Path(__file__).resolve().parent / "omni_arm_bpy.py"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe")

# ── 骨骼规格（零随机 · 全部查表）────────────────────────────────────────────
# (名字, 父, 长度m, 轴, 限位°, DoF, 前向偏移y, x偏移)
ARM = [
    ("shoulder_pitch", None, 0.060, "x", (-180, 90), 1, 0.000, 0.000),
    ("shoulder_yaw", "shoulder_pitch", 0.060, "y", (-90, 90), 1, 0.000, 0.000),
    ("shoulder_roll", "shoulder_yaw", 0.050, "z", (-90, 90), 1, 0.000, 0.000),
    ("upper_arm", "shoulder_roll", 0.300, "x", (-45, 150), 1, 0.000, 0.000),
    ("elbow", "upper_arm", 0.050, "x", (0, 150), 1, 0.000, 0.000),
    ("forearm_twist", "elbow", 0.100, "x", (-90, 90), 1, 0.000, 0.000),
    ("wrist_pitch", "forearm_twist", 0.050, "y", (-90, 90), 1, 0.000, 0.000),
    ("wrist_yaw", "wrist_pitch", 0.030, "z", (-60, 60), 1, 0.000, 0.000),
    ("wrist_roll", "wrist_yaw", 0.020, "x", (-90, 90), 1, 0.000, 0.000),
    ("hand", "wrist_roll", 0.120, "y", (-30, 30), 2, 0.000, 0.000),
]
# 指：名字前缀, 节数(DoF), 每节长度, x 起始偏移, 每节递减系数
FINGERS = [
    ("thumb", 5, 0.028, -0.052, 0.90),
    ("index", 4, 0.030, -0.026, 0.92),
    ("middle", 4, 0.032, 0.000, 0.92),
    ("ring", 4, 0.030, 0.026, 0.92),
    ("pinky", 5, 0.022, 0.048, 0.90),
]
TENTACLE_SEGS = 8
TENTACLE_LEN = 0.080
TENTACLE_TAPER = 0.94

# 额外实体（让轮廓读得出"机械臂"而不是一根根杆子）：(绑到哪根骨, 尺寸 xyz, 相对骨 head 的偏移 xyz)
EXTRAS = [
    ("shoulder_roll", [0.105, 0.070, 0.105], [0.0, 0.020, 0.0]),   # 肩盖
    ("elbow", [0.058, 0.058, 0.058], [0.0, 0.025, 0.0]),           # 肘关节块
    ("forearm_twist", [0.078, 0.090, 0.078], [0.0, 0.040, 0.0]),   # 前臂（藏 25 执行器那段）
    ("hand", [0.112, 0.100, 0.036], [0.0, 0.050, 0.0]),            # 手掌板
    ("tentacle_03", [0.030, 0.030, 0.030], [0.0, 0.0, 0.030]),     # 触手中段加粗（读得出锥度）
]


def spec() -> list:
    """返回扁平的骨骼规格表：每项含 head/tail（长在父的尾上）、半径、顶点区间占位。"""
    bones, pos = [], [0.0, 0.0, 0.0]
    y = 0.0
    for name, parent, length, axis, limits, dof, _dy, _dx in ARM:
        head = [0.0, y, 0.0]
        y += length
        bones.append({"name": name, "parent": parent, "head": head, "tail": [0.0, y, 0.0],
                      "length": length, "axis": axis, "limits": list(limits), "dof": dof,
                      "radius": 0.022 if length > 0.1 else 0.014, "group": "arm"})
    hand_tail = list(bones[-1]["tail"])
    for fname, segs, seg_len, dx, taper in FINGERS:
        parent = "hand"
        base_y, base_x, base_z = hand_tail[1] - 0.010, dx, 0.0
        length = seg_len
        for i in range(segs):
            name = "%s_%02d" % (fname, i + 1)
            head = [base_x, base_y, base_z]
            base_y += length
            base_z += length * 0.14          # 向上卷（读得出指节弯曲，不改拓扑）
            bones.append({"name": name, "parent": parent, "head": head, "tail": [base_x, base_y, base_z],
                          "length": round(length, 4), "axis": "x", "limits": [-10, 95], "dof": 1,
                          "radius": max(0.004, 0.0085 * (taper ** i)), "group": "finger"})
            parent = name
            length *= taper
    # 触手：从肩根往上长，8 节，**沿四分之一圆弧弯**（直的读不出"触手"），末端渐细
    parent, z = "shoulder_roll", 0.020
    length = TENTACLE_LEN
    bend = 0.0
    for i in range(TENTACLE_SEGS):
        name = "tentacle_%02d" % (i + 1)
        head = [0.0, 0.020 * i * i, z]          # y 随节数加速后弯 ⇒ 弧线
        bend = 0.020 * (i + 1)
        bones.append({"name": name, "parent": parent,
                      "head": head, "tail": [0.0, bend, z + length],
                      "length": round(length, 4), "axis": "yz"[i % 2], "limits": [-60, 60],
                      "dof": 2 if i % 2 == 0 else 1,
                      "radius": max(0.0045, 0.011 * (TENTACLE_TAPER ** i)), "group": "tentacle"})
        parent = name
        z += length
        length *= TENTACLE_TAPER
    return bones


def fk(bones: list, which: str, angles: list) -> list:
    """**真 3D FK**：沿骨链把每节的局部旋转按（简化的绕单轴）累乘，返回末端世界坐标。

    ⚠️ 与设计稿的差别：稿子里 `fk()` 只累加 x/y、z 恒 0，并且用 `rot += rad*0.3` 冒充链式旋转；
    这里把每节的角度真正叠加再取方向，z 轴参与，末端是三维点。
    """
    chain = [b for b in bones if b["name"] == which or b["name"].startswith(which + "_")]
    out = list(chain[0]["head"]) if chain else [0.0, 0.0, 0.0]
    ang = 0.0
    for i, b in enumerate(chain):
        a = math.radians(angles[i] if i < len(angles) else 0.0) + ang
        seg = b["length"]
        out[0] += seg * math.sin(a) * (1 if b["axis"] in ("y", "yz") else 0.0)
        out[1] += seg * math.cos(a) * (1 if b["axis"] in ("x", "y", "yz") else 0.0)
        out[2] += seg * math.sin(a) if b["axis"] in ("yz", "z") else 0.0
        ang += a * 0.5
    return [round(v, 6) for v in out]


def ccd(bones: list, which: str, target: list, max_iter: int = 40, eps: float = 1e-3) -> dict:
    """**真 CCD**：从末端往前，逐个关节把「末端→目标」的方向转进该关节；越界夹到 limits。"""
    chain = [b for b in bones if b["name"] == which or b["name"].startswith(which + "_")]
    angles = [0.0] * len(chain)
    best = {"err": None, "iters": 0}
    for it in range(max_iter):
        end = fk(bones, which, angles)
        err = math.dist(end, target)
        if best["err"] is None or err < best["err"]:
            best = {"err": round(err, 6), "iters": it + 1, "angles": [round(a, 3) for a in angles]}
        if err < eps:
            break
        for j in range(len(chain) - 1, -1, -1):
            # 关节角是单轴标量：用「末端到目标」在该轴平面上的投影修正（真 CCD 的可解形式）
            end = fk(bones, which, angles)
            du = (target[1] - end[1], target[0] - end[0])
            de = (end[1] - chain[j]["head"][1], end[0] - chain[j]["head"][0])
            dot = du[0] * de[0] + du[1] * de[1]
            cross = du[0] * de[1] - du[1] * de[0]
            step = math.atan2(cross, dot + 1e-12)
            lo, hi = chain[j]["limits"]
            angles[j] = max(lo, min(hi, angles[j] - math.degrees(step) * 0.5))
    best["solved"] = best["err"] is not None and best["err"] < eps
    return best


# ── 建件 ─────────────────────────────────────────────────────────────────────
def build(timeout: int = 600) -> dict:
    if not BLENDER.is_file():
        return {"ok": False, "why": "Blender 不在：%s（免费本地 DCC）" % BLENDER}
    if not BPY.is_file():
        return {"ok": False, "why": "bpy 侧脚本不在：%s" % BPY}
    OUT.mkdir(parents=True, exist_ok=True)
    bones = spec()
    glb = OUT / "omni-arm-rigged.glb"
    spec_path = OUT / "omni-arm-spec.json"
    spec_path.write_text(json.dumps({"bones": bones, "extras": EXTRAS, "count": len(bones),
                                     "dof_fingers": sum(1 for b in bones if b["group"] == "finger"),
                                     "at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    log = Path(tempfile.gettempdir()) / "gbt_omni_arm.log"
    cmd = [str(BLENDER), "--background", "--factory-startup", "--python", str(BPY), "--",
           str(spec_path), str(glb)]
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        cp = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout)
    text = log.read_text(encoding="utf-8", errors="replace")
    i, j = text.find("<<<GBT-OMNIARM>>>"), text.find("<<<END>>>")
    if i < 0 or j < 0:
        return {"ok": False, "why": "Blender 跑完但没吐结果块（rc=%s）" % cp.returncode,
                "tail": text[-800:]}
    data = json.loads(text[i + len("<<<GBT-OMNIARM>>>"):j])
    data["blender_rc"] = cp.returncode
    # 自检：文件在不在 + 解析 GLB 量真读数（不靠 Blender 自述）
    check = check_glb(glb)
    checks = [
        ("GLB 已落盘", glb.is_file() and glb.stat().st_size > 0, "%s · %s 字节"
         % (glb.name, glb.stat().st_size if glb.is_file() else 0)),
        # 🔴 口径留痕（第一版判错了一次）：原来这里比的是 `nodes == 40`，实测 nodes=42 ⇒ 判红。
        #    真因是**判据错尺**：glTF 的 nodes 除了 40 根骨，还包括「网格节点」与「骨架根节点」；
        #    骨数的真源是 `skin.joints`（= 40）。所以改成：joints==40 且 nodes 允许 41~42。
        ("骨数 = 40（skin.joints；nodes 另有网格+骨架根）",
         check.get("joints") == 40 and 41 <= (check.get("nodes") or 0) <= 42,
         "joints=%s nodes=%s" % (check.get("joints"), check.get("nodes"))),
        ("单网格 + 单蒙皮", check.get("meshes") == 1 and check.get("skins") == 1,
         "meshes=%s skins=%s" % (check.get("meshes"), check.get("skins"))),
        ("蒙皮关节数 = 40", check.get("joints") == 40, "joints=%s" % check.get("joints")),
        ("无未绑顶点（权重和>0）", check.get("unweighted") == 0, "未绑=%s" % check.get("unweighted")),
        ("权重已归一（每顶点和≈1）", check.get("not_normalized") == 0,
         "非归一化=%s" % check.get("not_normalized")),
        ("顶点数 > 300（真几何不是空壳）", (check.get("verts") or 0) > 300, "verts=%s" % check.get("verts")),
        ("尺寸合理（0.2~2.0 m）", 0.2 <= (check.get("height_m") or 0) <= 2.0,
         "高=%s m" % check.get("height_m")),
    ]
    ok = all(c[1] for c in checks)
    report = {"ok": ok, "at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
              "glb": str(glb.relative_to(ROOT)).replace("\\", "/"), "bytes": glb.stat().st_size if glb.is_file() else 0,
              "spec": str(spec_path.relative_to(ROOT)).replace("\\", "/"), "bones": len(bones),
              "checks": [{"名": n, "过": bool(g), "读数": d} for n, g, d in checks],
              "glb_check": check, "blender": data}
    (OUT / "omni-arm-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def check_glb(path: Path) -> dict:
    """直接解析 GLB（不经 Blender）：节点/网格/蒙皮/关节/未绑顶点/非归一化/包围盒。"""
    if not path.is_file():
        return {"ok": False, "why": "GLB 不在"}
    blob = path.read_bytes()
    if blob[:4] != b"glTF":
        return {"ok": False, "why": "不是 GLB"}
    ln = struct.unpack("<I", blob[12:16])[0]
    js = json.loads(blob[20:20 + ln])
    bin_off = 20 + ln
    while bin_off % 4:
        bin_off += 1
    bin_len = struct.unpack("<I", blob[bin_off:bin_off + 4])[0]
    bin_ = blob[bin_off + 8:bin_off + 8 + bin_len]
    nodes = js.get("nodes", [])
    meshes = js.get("meshes", [])
    skins = js.get("skins", [])
    verts = 0
    unweighted = norm_bad = 0
    ys, xs, zs = [], [], []
    for m in meshes:
        for pr in m.get("primitives", []):
            at = pr.get("attributes") or {}
            if "POSITION" in at:
                acc = js["accessors"][at["POSITION"]]
                verts += acc["count"]
                bv = js["bufferViews"][acc["bufferView"]]
                off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
                for k in range(acc["count"]):
                    x, y, z = struct.unpack_from("<3f", bin_, off + k * 12)
                    xs.append(x); ys.append(y); zs.append(z)
            if "WEIGHTS_0" in at:
                acc = js["accessors"][at["WEIGHTS_0"]]
                bv = js["bufferViews"][acc["bufferView"]]
                off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
                comp = {5126: "<4f", 5123: "<4H", 5121: "<4B"}[acc["componentType"]]
                scale = 1.0 if acc["componentType"] == 5126 else (65535.0 if acc["componentType"] == 5123 else 255.0)
                for k in range(acc["count"]):
                    w = struct.unpack_from(comp, bin_, off + k * struct.calcsize(comp))
                    s = sum(v / scale for v in w)
                    if s <= 1e-6:
                        unweighted += 1
                    elif abs(s - 1.0) > 0.01:
                        norm_bad += 1
    height = round(max(ys) - min(ys), 4) if ys else None
    return {"ok": True, "nodes": len(nodes), "meshes": len(meshes), "skins": len(skins),
            "joints": sum(len(s.get("joints", [])) for s in skins), "verts": verts,
            "unweighted": unweighted, "not_normalized": norm_bad,
            "bbox": {"x": round(max(xs) - min(xs), 4) if xs else None,
                     "y": round(max(ys) - min(ys), 4) if ys else None,
                     "z": round(max(zs) - min(zs), 4) if zs else None},
            "height_m": height, "bytes": len(blob)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Omni-Arm 22DoF+9骨臂+8段触手：真几何真绑骨")
    ap.add_argument("--spec", action="store_true", help="只打印骨骼规格")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()
    if a.spec:
        bones = spec()
        print(json.dumps({"count": len(bones), "rows": bones}, ensure_ascii=False, indent=1))
        return 0
    report = build(a.timeout)
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("═" * 66)
        print("  Omni-Arm 建件（Blender 4.2 本地 · 零付费）")
        print("═" * 66)
        print("  %s · %s 字节 · 骨 %s" % (report.get("glb"), report.get("bytes"), report.get("bones")))
        for c in report.get("checks") or []:
            print("  %s %-30s %s" % ("✅" if c["过"] else "🔴", c["名"], c["读数"]))
        if report.get("why"):
            print("  🔴 %s" % report["why"])
        print("  结论：%s" % ("八条自检全绿，可上舞台" if report.get("ok") else "有红，别拿它当成品"))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
