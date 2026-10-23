# -*- coding: utf-8 -*-
"""把**仓里既有的真成品**接进数字人流水线（它一直在 projects/digital-human/out/ 里）。

主人问「数字人你修复好了没有」——查下来：**成品早就有了**
（projects/digital-human/out/dh_rigged.glb：19 骨 · VRM 必需骨缺 0 · 权重和恒 1 · 6 条动画），
只是流水线只看 holo_pet/assets/digital-human/raw/，**没看见它** ⇒ 一直报 4/14。
本件做三件事（全部留读数，不编）：
  ① 核验既有成品（骨/skin/权重/动画，逐条现读）；
  ② 接到流水线期望路径（raw/phase1/model.glb · raw/rig/model-rigged-anim.glb）；
  ③ 从**真实骨名**生成 skeleton.json（附 VRM 映射，可复核）。
"""
from __future__ import annotations

import json
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P                                              # noqa: E402

# 2026-10-15 对齐：在役件已是 v2（主人 2026-10-10 Tripo 重绑）⇒ 同步指针
SRC = P.WS / "projects" / "digital-human" / "out" / "dh-v2-rigged.glb"
DST_ANIM = P.RIG / "model-rigged-anim.glb"
DST_BASE = P.DH / "raw" / "phase1" / "model.glb"


def read_glb(p: Path):
    b = p.read_bytes()
    ln = struct.unpack("<I", b[12:16])[0]
    return json.loads(b[20:20 + ln]), len(b)


def main() -> int:
    if not SRC.is_file():
        print("既有成品不在：%s" % SRC)
        return 2
    j, nbytes = read_glb(SRC)
    joints = [j["nodes"][x].get("name") for x in j["skins"][0]["joints"]]
    anims = [a.get("name") for a in (j.get("animations") or [])]
    print("① 既有成品 %s" % SRC.name)
    print("   字节 %d · 骨 %d · skin %d · 动画 %d %s"
          % (nbytes, len(joints), len(j.get("skins") or []), len(anims), anims))
    ok, why = P.gate_rig(SRC)
    print("   门的读数：", (ok, why))
    if not ok:
        print("成品没过 S6 门，不往上接（如实报）")
        return 1
    DST_ANIM.parent.mkdir(parents=True, exist_ok=True)
    DST_BASE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, DST_ANIM)
    shutil.copyfile(SRC, DST_BASE)
    print("② 已接：raw/rig/model-rigged-anim.glb · raw/phase1/model.glb")
    vrm = {n: (P.BLENDER_TO_VRM.get(n) or P.MIXAMO_TO_VRM.get(n)) for n in joints}
    missing = [b for b in P.VRM_REQUIRED if b not in set(vrm.values())]
    skel = {"bones": [{"name": n, "vrm": vrm.get(n)} for n in joints],
            "vrm_required": P.VRM_REQUIRED, "missing_required": missing,
            "source": "projects/digital-human/out/dh_rigged.glb（既有真成品 · 19 骨 · 6 条动画）",
            "name_map": "Blender 风格 upper_arm_L → VRM leftUpperArm（见 pipeline.BLENDER_TO_VRM）",
            "generator": "tools/digihuman/dh-wire-existing.py"}
    (P.RIG / "skeleton.json").write_text(json.dumps(skel, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print("③ skeleton.json：骨 %d · VRM 必需骨缺 %d" % (len(joints), len(missing)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
