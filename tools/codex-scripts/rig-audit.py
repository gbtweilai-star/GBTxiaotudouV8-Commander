# -*- coding: utf-8 -*-
"""**专业绑骨体检**：用本机的 Blender 4.2（免费 · 本地 · 零付费接口）对 GLB 做 DCC 级审计。

## 为什么不用网页里那套"自己算"
网页里能数顶点、能量包围盒，但**算不出**：骨骼父子层级、每根骨的真实权重和、左右镜像是否对称、
非归一化权重、零长度骨、缩放是否已应用 —— 这些是 Blender 里才有的事实。
本器把 Blender 当**量具**用（`--background` 无界面跑），只读、不写生产件。

## 它做什么（一次跑完，输出可被页面直接吃）
1. `blender --background --python <本器的 bpy 段>` 导入 GLB；
2. 逐项量：骨架/骨数/层级深度/每骨权重顶点数与权重和/未绑顶点/非归一化权重/
   零长骨/左右镜像（按 `Left`↔`Right` 配对比较头部坐标）/包围盒/缩放与旋转是否已应用；
3. 把结果写成 `window.GBT_RIG_AUDIT = {...}` 的 **.js**（页面用 <script> 直接吃，
   `file://` 下 fetch 被拦，所以走脚本注入这条与 glb-inline 同型的路）；
4. 同时打印一份人读摘要。

## 用法
    py -3.14 tools/codex-scripts/rig-audit.py                 # 默认 GLB + 写 .js
    py -3.14 tools/codex-scripts/rig-audit.py --json          # 机器可读
    py -3.14 tools/codex-scripts/rig-audit.py --check         # 只对账：.js 与 GLB 的 sha 是否一致

退出码：0 审计完成 · 1 Blender/GLB 不在或解析失败（**不假装成功**）

## 纪律
- **只读**：不给 GLB 写任何东西；产物只有那个 .js 与 stdout。
- **原话透传**：Blender 起不来/报错，把它最后 400 字原样带出来（P19）。
- **派生件带指纹**：.js 里写死源 GLB 的 sha256 + 字节数，`--check` 对不上就红（P9）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
GLB = ROOT / "holo_pet_w3" / "voice-theater" / "assets" / "dh-v5-color.glb"   # 量**在役件**（v5），不去量构建树里的旧副本
OUT_JS = ROOT / "holo_pet_w3" / "digital-human" / "rig-audit.js"
BLENDER_CANDIDATES = [
    Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe"),
]

BPY = r'''
import bpy, json, math, sys
from mathutils import Vector

def out(payload):
    sys.stdout.write("<<<GBT-RIG-AUDIT>>>" + json.dumps(payload, ensure_ascii=False) + "<<<END>>>")

def main():
    path = sys.argv[-1]   # 调用形如 ... --python script.py -- <glb>：最后一个才是路径
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        bpy.ops.import_scene.gltf(filepath=path)
    except Exception as e:
        out({"ok": False, "why": "glTF 导入失败：" + str(e)[:300]})
        return

    objs = list(bpy.data.objects)
    arms = [o for o in objs if o.type == 'ARMATURE']
    # ⚠️ 2026-10-19 修（量具自己错了尺，不是资产的问题）：
    #   Blender 的 glTF 导入器会给**每一根 pose bone** 造一个显示形状（一个 42 顶点的 Icosphere，
    #   实测 custom_shape_users=65），它出现在场景里、却没有顶点组 ⇒ 被当成"第二个网格 + 42 个未绑顶点"。
    #   文件字节里根本没有 "Icosphere" 这个词（grep 整份 GLB 得到 -1），glTF 侧也只有 1 个网格。
    #   ⇒ 先把骨骼显示形状剔掉，再谈网格/权重/包围盒。
    widgets = set()
    for a in arms:
        for pb in a.pose.bones:
            cs = pb.custom_shape
            if cs:
                widgets.add(cs.name)
    meshes = [o for o in objs if o.type == 'MESH' and o.name not in widgets]
    res = {"ok": True, "armatures": len(arms), "meshes": len(meshes),
           "excluded_widgets": sorted(widgets)}

    # ── 骨架 ────────────────────────────────────────────────────────────────
    bones = []
    for a in arms:
        for b in a.data.bones:
            bones.append({
                "name": b.name,
                "parent": b.parent.name if b.parent else None,
                "len": round(float(b.length), 5),
                "head": [round(float(v), 5) for v in b.head_local],
                "tail": [round(float(v), 5) for v in b.tail_local],
            })
    res["bones"] = len(bones)
    res["roots"] = [b["name"] for b in bones if not b["parent"]]
    res["zero_len"] = [b["name"] for b in bones if b["len"] <= 1e-6]

    depth = {}
    def d(n):
        if n in depth: return depth[n]
        bb = next((x for x in bones if x["name"] == n), None)
        depth[n] = 1 if not bb or not bb["parent"] else 1 + d(bb["parent"])
        return depth[n]
    res["max_depth"] = max([d(b["name"]) for b in bones], default=0)

    # ── 权重（按顶点组真算） ────────────────────────────────────────────────
    vg_weight = {}
    unweighted = 0
    non_normalized = 0
    verts_total = 0
    for m in meshes:
        for v in m.data.vertices:
            verts_total += 1
            total = 0.0
            for g in v.groups:
                w = float(g.weight)
                total += w
                if w > 1e-4:
                    nm = m.vertex_groups[g.group].name if g.group < len(m.vertex_groups) else str(g.group)
                    vg_weight[nm] = vg_weight.get(nm, 0.0) + w
            if total < 0.02:
                unweighted += 1
            elif abs(total - 1.0) > 0.02:
                non_normalized += 1
    res["verts"] = verts_total
    res["unweighted"] = unweighted
    res["unweighted_pct"] = round(100.0 * unweighted / max(1, verts_total), 2)
    res["non_normalized"] = non_normalized
    res["bound_groups"] = len([k for k, w in vg_weight.items() if w > 0])
    top = sorted(vg_weight.items(), key=lambda kv: -kv[1])[:8]
    res["top_groups"] = [[k, round(w, 1)] for k, w in top]

    # ── 左右镜像（同名前缀配对，比较头部 X 是否反号、其余轴是否相近） ─────────
    by_name = {b["name"]: b for b in bones}
    pairs, mirrored, off = 0, 0, []
    for nm, b in by_name.items():
        if "Left" not in nm:
            continue
        rn = nm.replace("Left", "Right")
        if rn not in by_name:
            continue
        pairs += 1
        l, r = b["head"], by_name[rn]["head"]
        if abs(l[0] + r[0]) < 1e-4 and abs(l[1] - r[1]) < 1e-4 and abs(l[2] - r[2]) < 1e-4:
            mirrored += 1
        else:
            off.append({"pair": [nm, rn], "dx": round(l[0] + r[0], 5),
                        "dy": round(l[1] - r[1], 5), "dz": round(l[2] - r[2], 5)})
    res["mirror_pairs"] = pairs
    res["mirror_ok"] = mirrored
    res["mirror_off"] = off[:8]

    # ── 变换是否已应用 / 包围盒 ──────────────────────────────────────────────
    unapplied = []
    for o in meshes + arms:
        s = o.scale
        if abs(s[0] - 1) > 1e-4 or abs(s[1] - 1) > 1e-4 or abs(s[2] - 1) > 1e-4:
            unapplied.append({"obj": o.name, "scale": [round(float(v), 4) for v in s]})
    res["unapplied_scale"] = unapplied

    mn = [1e9, 1e9, 1e9]; mx = [-1e9, -1e9, -1e9]
    for m in meshes:
        for c in m.bound_box:
            w = m.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], float(w[i])); mx[i] = max(mx[i], float(w[i]))
    res["bbox_min"] = [round(v, 3) for v in mn]
    res["bbox_max"] = [round(v, 3) for v in mx]
    # ⚠️ 2026-10-19 修：Blender 是 **Z-up**，身高在 **Z**（第 3 个数），原来是 mx[1]-mn[1] 量的 Y —— 
    #   拿横向尺寸当身高（同一个错尺病，这已经是这一件的第 3 次）。三个轴都报出来，谁也别猜。
    res["height_m"] = round(mx[2] - mn[2], 3)            # 场景 Z 跨度 = 身高（Blender 口径）
    res["span_axes"] = {"x": round(mx[0] - mn[0], 3),
                        "y": round(mx[1] - mn[1], 3),
                        "z": round(mx[2] - mn[2], 3)}
    res["height_note"] = ("场景 Z 跨度（Blender Z-up）。glTF 导入会按实测系数缩放，"
                          "文件空间身高要拿 glTF 的 POSITION Y 跨度看（本仓 dh-asset-gate.py 第③条）")

    out(res)

main()
'''


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_blender() -> Path | None:
    for p in BLENDER_CANDIDATES:
        if p.is_file():
            return p
    for base in (Path(r"C:\Program Files\Blender Foundation"), Path(r"C:\Program Files (x86)\Blender Foundation")):
        if base.is_dir():
            for p in sorted(base.glob("Blender */blender.exe"), reverse=True):
                return p
    return None


def run_audit(glb: Path, blender: Path) -> dict:
    script = Path(tempfile.gettempdir()) / "gbt_rig_audit_bpy.py"
    script.write_text(BPY, encoding="utf-8")
    log = Path(tempfile.gettempdir()) / "gbt_rig_audit.log"
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        cp = subprocess.run([str(blender), "--background", "--factory-startup",
                             "--python", str(script), "--", str(glb)],
                            stdout=fh, stderr=subprocess.STDOUT, timeout=600)
    text = log.read_text(encoding="utf-8", errors="replace")
    i = text.find("<<<GBT-RIG-AUDIT>>>")
    j = text.find("<<<END>>>", i if i >= 0 else 0)
    if i < 0 or j < 0:
        return {"ok": False, "why": "Blender 跑完但没吐审计块（rc=%s）" % cp.returncode,
                "tail": text[-400:]}
    try:
        return json.loads(text[i + len("<<<GBT-RIG-AUDIT>>>"):j])
    except Exception as e:                              # noqa: BLE001
        return {"ok": False, "why": "审计块不是合法 JSON：%s" % e, "tail": text[-400:]}


def main() -> int:
    ap = argparse.ArgumentParser(description="用本机 Blender 做专业绑骨审计（只读）")
    ap.add_argument("--json", action="store_true", help="打印机器可读 JSON")
    ap.add_argument("--check", action="store_true", help="只对账：rig-audit.js 与 GLB 的 sha")
    ap.add_argument("--glb", default=None,
                    help="换一份 GLB 来审（默认审 projects/... 的原始件；"
                         "审在役件就传 holo_pet_w3/voice-theater/assets/dh-v2-rigged.glb）")
    ap.add_argument("--out", default=None, help="派生件输出路径（默认 holo_pet_w3/digital-human/rig-audit.js）")
    a = ap.parse_args()

    global GLB, OUT_JS
    if a.glb:
        GLB = Path(a.glb) if Path(a.glb).is_absolute() else (ROOT / a.glb)
    if a.out:
        OUT_JS = Path(a.out) if Path(a.out).is_absolute() else (ROOT / a.out)

    if not GLB.is_file():
        print("🔴 GLB 不在：%s" % GLB)
        return 1
    src_sha, src_bytes = sha256(GLB), GLB.stat().st_size

    if a.check:
        if not OUT_JS.is_file():
            print("🔴 派生件不在：%s（先跑一次 py -3.14 tools/codex-scripts/rig-audit.py）" % OUT_JS.name)
            return 1
        t = OUT_JS.read_text(encoding="utf-8", errors="replace")
        if src_sha not in t:
            print("🔴 rig-audit.js 与源 GLB 对不上（源 sha256=%s…）⇒ 重跑本器" % src_sha[:16])
            return 1
        print("✅ 对账一致 · %s · 源 %d 字节" % (OUT_JS.name, src_bytes))
        return 0

    blender = find_blender()
    if not blender:
        print("🔴 找不到 Blender（免费本地 DCC）。路径候选：%s" % ", ".join(str(p) for p in BLENDER_CANDIDATES))
        print("   ⇒ 装 Blender 4.x（免费）后重跑；本器不调用任何付费接口。")
        return 1

    data = run_audit(GLB, blender)
    data["source"] = {"glb": str(GLB.relative_to(ROOT)).replace("\\", "/"),
                      "sha256": src_sha, "bytes": src_bytes}
    data["measured_by"] = {"tool": "Blender", "exe": str(blender), "mode": "--background"}
    data["at"] = __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")

    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text("/* 自动生成，别手改 —— py -3.14 tools/codex-scripts/rig-audit.py\n"
                      "   量具：本机 Blender（--background）· 源 %s sha256=%s */\n"
                      "window.GBT_RIG_AUDIT = %s;\n"
                      % (data["source"]["glb"], src_sha[:16], json.dumps(data, ensure_ascii=False, indent=1)),
                      encoding="utf-8")

    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        print("═" * 66)
        print("  专业绑骨体检（Blender %s · 只读）" % str(blender).split("Blender ")[-1].split("\\")[0])
        print("═" * 66)
        if not data.get("ok"):
            print("  🔴 没成：%s" % data.get("why"))
            print("  尾部原话：%s" % str(data.get("tail", ""))[-300:])
        else:
            print("  骨架 %d · 网格 %d · 顶点 %d" % (data["armatures"], data["meshes"], data["verts"]))
            if data.get("excluded_widgets"):
                print("  已剔除骨骼显示形状 %s（Blender 导入器自动生成，不是资产网格）"
                      % ", ".join(data["excluded_widgets"]))
            print("  骨骼 %d · 根骨 %s · 最大层级 %d · 零长骨 %s"
                  % (data["bones"], ",".join(data["roots"][:3]), data["max_depth"],
                     data["zero_len"] or "无"))
            print("  未绑顶点 %d（%.2f%%）· 非归一化 %d · 真绑到的顶点组 %d"
                  % (data["unweighted"], data["unweighted_pct"], data["non_normalized"], data["bound_groups"]))
            print("  镜像 %d/%d 对 · 偏差 %s" % (data["mirror_ok"], data["mirror_pairs"],
                                              ("%d 对" % len(data["mirror_off"])) if data["mirror_off"] else "0"))
            print("  包围盒 高 %.2f m · 未应用缩放 %s" % (data["height_m"], data["unapplied_scale"] or "无"))
            print("  权重前八：%s" % ", ".join("%s=%.1f" % (k, w) for k, w in data["top_groups"]))
        print("─" * 66)
        print("  产物：%s（页面用 <script> 直接吃，file:// 下不走 fetch）" % OUT_JS.relative_to(ROOT))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
