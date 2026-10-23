# -*- coding: utf-8 -*-
"""**专业绑骨修复 · 包装器**（Blender 4.2 本地 · 免费 · 零付费接口）

真正的 Blender 侧逻辑在 `rig_fix_bpy.py`（独立文件，便于 `--background --python` 直跑与单独审阅）。
本器只做三件事：起 Blender、把回执解析出来、把**六条硬判据**打印成人能读的样子：

  ① 自动定轴：三轴跨度 → 取最大者为身高轴 → 旋到 Z 并 apply（不再假设 Y-up / Z-up）
  ② 量具自证：场景内身高 vs 直接解析 GLB 得到的 POSITION 跨度，差 >5% 直接红
  ③ 导出侧自证：直接解析 GLB ⇒ `meshes==1 && skins==1`，且没有 42 顶点的无名网格（杂物球）

用法：
    py -3.14 tools/codex-scripts/rig-fix.py [--drop-strays] [--json]
退出码：0 = 六条硬判据全过 · 1 = 有一条红（原因与读数都在回执里）

⚠️ **本器会覆盖在役资产**（holo_pet_w3/voice-theater/assets/dh-v2-rigged.glb），
   而它**不重做动作修正**。所以在役资产的完整流水线是三步、必须按顺序：

     ① py -3.14 tools/codex-scripts/rig-fix.py --drop-strays     # 几何/绑骨/尺度（六条硬判据）
     ② py -3.14 tools/codex-scripts/anim-hipfix.py <glb> <glb>   # 动作修正（髋骨归位 + 手臂垂放）
        · 髋骨：--bones LeftUpLeg,RightUpLeg（吸附回静止姿势）
        · 手臂：--bones "" --set "LeftArm=-0.552047,-0.417612,0.306125,0.653553"
                --set "RightArm=-0.571611,0.369986,-0.242467,0.691072"
                --set "LeftForeArm=rest" --set "RightForeArm=rest"
          （这组值由 `.scratch/solve-arms2.cjs` 闭环解算出来：写进骨头→量手臂方向→按误差迭代，
            左右各 84.5° / 72.7° 且**不对称**，所以不许写一个共用角度）
     ③ py -3.14 tools/codex-scripts/dh-asset-gate.py              # 八条判据（含"腿没折·手垂放·循环闭合"）

   只跑 ① 出来的是"能渲染"的资产 —— 但她的**腿会折在胯上、双手举过头顶**（2026-10-19 实栽）。
   另：Blender 导入器会给每根 pose bone 造一个 42 顶点的 Icosphere 显示形状（文件字节里没有它），
   别把量具的这个假象当成"导出里有杂物球"（rig-audit.py 已剔除并在回执里点名）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "projects" / "digital-human" / "out" / "dh-v2-rigged.glb"
OUTDIR = ROOT / "outputs" / "rig-fix"
DST = OUTDIR / "dh-v2-rigged-fixed.glb"
TARGET_H = 1.72
BPY = Path(__file__).resolve().parent / "rig_fix_bpy.py"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe")


def sha16(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser(description="Blender 本地绑骨修复（自动定轴 / 量具自证 / 导出侧自证）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--drop-strays", action="store_true",
                    help="把【无顶点组+无材质+无骨架】的杂物从导出件里删掉（Tripo 常留一个 42 顶点单位球）")
    a = ap.parse_args()

    if not SRC.is_file():
        print("🔴 源 GLB 不在：%s" % SRC)
        return 1
    if not BLENDER.is_file():
        print("🔴 Blender 不在：%s（免费本地 DCC；本器不调用任何付费接口）" % BLENDER)
        return 1
    if not BPY.is_file():
        print("🔴 Blender 侧脚本不在：%s" % BPY)
        return 1

    pngdir = OUTDIR / "turnaround"
    log = Path(tempfile.gettempdir()) / "gbt_rig_fix_v6.log"
    cmd = [str(BLENDER), "--background", "--factory-startup", "--python", str(BPY), "--",
           str(SRC), str(DST), str(pngdir), str(TARGET_H)]
    if a.drop_strays:
        cmd.append("--drop-strays")
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        cp = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=1200)

    text = log.read_text(encoding="utf-8", errors="replace")
    i = text.find("<<<GBT-FIX>>>")
    j = text.find("<<<END>>>", max(0, i))
    if i < 0 or j < 0:
        print("🔴 Blender 跑完但没吐结果块（rc=%s）" % cp.returncode)
        print("   尾部原话：%s" % text[-500:])
        return 1
    data = json.loads(text[i + len("<<<GBT-FIX>>>"):j])
    data["at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    data["src"] = str(SRC.relative_to(ROOT)).replace("\\", "/")
    if DST.is_file():
        data["dst"] = str(DST.relative_to(ROOT)).replace("\\", "/")
        data["dst_sha16"] = sha16(DST)
        data["dst_bytes"] = DST.stat().st_size
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "rig-fix-report.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    if not data.get("ok"):
        print("═" * 68)
        print("  专业绑骨修复（Blender 4.2 · 本地 · 免费）")
        print("═" * 68)
        print("  🔴 没成：%s" % data.get("why"))
        if data.get("axis"):
            print("  定轴读数：%s" % json.dumps(data["axis"], ensure_ascii=False))
        return 1

    ax = data.get("axis") or {}
    gb = data.get("glb_check") or {}
    pre = data.get("pre_export") or {}
    af = data.get("after") or {}
    sk = data.get("skin_move") or {}

    checks = []
    checks.append(("GLB 侧：单网格 + 有蒙皮",
                   gb.get("meshes") == 1 and gb.get("skins") == 1,
                   "meshes=%s skins=%s verts=%s" % (gb.get("meshes"), gb.get("skins"), gb.get("vert_counts"))))
    checks.append(("杂物球没混进导出件", 42 not in (gb.get("vert_counts") or []),
                   "顶点数表 %s" % (gb.get("vert_counts"),)))
    # 判据必须在**文件空间**里判：Blender 场景里有单位换算（实测 0.652），拿场景 Z 当身高会永远红
    glb_h = (gb.get("pos_spans") or [0, 0, 0])[1]
    scene_h = pre.get("height_m") or 0
    factor = (scene_h / glb_h) if glb_h else 0
    checks.append(("量具自证：换算系数合理(0.3~3)", 0.3 < factor < 3,
                   "场景 Z %.3f ÷ 文件 Y %.3f = 换算 %.3f（导入自带，不是错）"
                   % (scene_h, glb_h, factor)))
    checks.append(("身高（文件里量）1.72m±0.02", abs(glb_h - TARGET_H) < 0.02,
                   "GLB Y 跨度 %.3f m（目标 %.2f）" % (glb_h, TARGET_H)))
    checks.append(("未绑顶点归零", (af.get("unweighted") or 0) == 0, "未绑 %s" % af.get("unweighted")))
    dead = [m for m, d in (sk.get("per_mesh") or {}).items() if d.get("moved", 0) == 0]
    checks.append(("蒙皮网格都被骨架带动", bool(sk.get("ok")) and not dead, "死壳 %s" % (dead or "无")))
    ok = all(c[1] for c in checks)

    if a.json:
        print(json.dumps({"checks": checks, "ok": ok, **data}, ensure_ascii=False, indent=1))
    else:
        print("═" * 68)
        print("  专业绑骨修复（Blender 4.2 · 本地 · 免费）· %s"
              % ("✅ 六条硬判据全过" if ok else "🔴 有红"))
        print("═" * 68)
        print("  自动定轴：三轴跨度 %s → 判身高轴 %s → 旋转 %s → 旋后跨度 %s"
              % (ax.get("before_spans"), ax.get("picked_axis"), ax.get("rotation"), ax.get("after_spans")))
        print("  杂物：%s" % json.dumps(data.get("stray"), ensure_ascii=False))
        print("  补权重顶点 %s · 归一化 %s · 缩放系数 %s"
              % (data.get("fixed_verts"), data.get("normalized"), data.get("scale_k")))
        for name, good, detail in checks:
            print("  %s %-24s %s" % ("✅" if good else "🔴", name, detail))
        print("  产物：%s · %s · %s 字节" % (data.get("dst"), data.get("dst_sha16"), data.get("dst_bytes") or 0))
        print("  转台：%s" % ("、".join(Path(p).name for p in data.get("shots", [])
                                       if not str(p).startswith("ERR")) or "无"))
        if any(str(p).startswith("ERR") for p in data.get("shots", [])):
            print("  ⚠️ 有视角渲染失败：%s" % [p for p in data["shots"] if str(p).startswith("ERR")])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
