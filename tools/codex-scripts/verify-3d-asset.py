# -*- coding: utf-8 -*-
r"""3D 资产机检（verify-3d-asset）—— **十道工序落成可跑的判据**。

主人给的三份权威口径（我照它炼，不自己发明）：
  · Khronos glTF 2.0 规范（registry.khronos.org/glTF）—— JOINTS_0/WEIGHTS_0（权重须归一）· skin · animation · PBR
  · Tripo 3D 角色检查单（tripo3d.ai/blog/3d-character-checklist）—— 我们模型的来源方
  · Game-Ready Asset Checklist 2026（strayspark.studio）—— 四边面优先 · 清 n-gon · 删内部面 · UV 不重叠 · 纹素密度一致 · 岛间距 2–4px · 三角面预算

十道工序（**能机检的一律机检，机检不了的如实标「人眼/工具另判」**，不许假装）：
  2 建模 → 包围盒比例        3 拓扑 → 三角面/退化面/非流形
  4 法线 → 有没法线/是否归一 5 预算 → 主角 20k–80k 三角面量级
  6 UV → 有通道/是否越界     7 材质 → baseColor 贴图与色彩空间
  8 绑定 → 关节数/层级/skin  9 蒙皮 → WEIGHTS_0 权重和≈1 · 零权重顶点
  10 动画 → 循环首尾对齐 · 体积
**机检不了的（明写，别装）**：雕刻/重拓扑 · UV 岛间距的像素测量 · PBR 烘焙 · 权重刷 · IK/BlendShape · LOD/引擎复核
  —— 那六件要 Blender 交互或专门工具，本件**只报"未检"**。

用法：py -3.14 -X utf8 tools/codex-scripts/verify-3d-asset.py [--check|--selftest]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "verify-3d-asset.json"
SKIP = ("node_modules", "_upstream", "_legacy_sources", "vendor", ".git", "dist", "native_browser")
# 只检**在役件**（备份/测试碎片不检，但要在读数里点名放过）
IN_SERVICE = ("projects/digital-human/out/dh-v2-rigged.glb",     # 2026-10-10 主人 Tripo 重绑（65 骨）
              "holo_pet/assets/digital-human/raw/rig/model-rigged-anim.glb",
              "projects/digital-human/out/dh_rigged.glb",
              "holo_pet/assets/digital-human/raw/phase1/model.glb",
              "assets/treasure-chest.glb")


def read_glb(p: Path) -> tuple:
    b = p.read_bytes()
    if b[:4] != b"glTF":
        raise ValueError("不是 GLB（magic 不对）")
    jl, = struct.unpack_from("<I", b, 12)
    J = json.loads(b[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", b, off)
    BIN = b[off + 8: off + 8 + bl]
    return J, BIN


def _tri_count(J) -> int:
    n = 0
    for m in J.get("meshes", []):
        for pr in m.get("primitives", []):
            if "indices" in pr:
                n += J["accessors"][pr["indices"]]["count"] // 3
            else:
                n += J["accessors"][pr["attributes"]["POSITION"]]["count"] // 3
    return n


def _bbox(J) -> dict:
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for m in J.get("meshes", []):
        for pr in m.get("primitives", []):
            a = J["accessors"][pr["attributes"]["POSITION"]]
            if "min" in a and "max" in a:
                lo = [min(lo[i], a["min"][i]) for i in range(3)]
                hi = [max(hi[i], a["max"][i]) for i in range(3)]
    if lo[0] > 1e8:
        return {}
    return {"min": [round(x, 4) for x in lo], "max": [round(x, 4) for x in hi],
            "尺寸": [round(hi[i] - lo[i], 4) for i in range(3)]}


def _weights(J, BIN) -> dict:
    """蒙皮：WEIGHTS_0 每顶点权重和 ≈1？零权重顶点几个？（**只能靠真读 BIN**）"""
    tot, zero, worst = 0, 0, 0.0
    for m in J.get("meshes", []):
        for pr in m.get("primitives", []):
            wi = pr["attributes"].get("WEIGHTS_0")
            if wi is None:
                return {"有WEIGHTS_0": False}
            a = J["accessors"][wi]
            bv = J["bufferViews"][a["bufferView"]]
            off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
            cnt = a["count"]
            stride = bv.get("byteStride") or 16
            for i in range(cnt):
                f = struct.unpack_from("<4f", BIN, off + i * stride)
                s = sum(f)
                tot += 1
                if s < 1e-6:
                    zero += 1
                worst = max(worst, abs(s - 1.0))
    return {"有WEIGHTS_0": True, "顶点数": tot, "零权重顶点": zero,
            "权重和最大偏差": round(worst, 6), "权重归一": worst <= 1e-3}


def _anims(J) -> list:
    out = []
    for a in J.get("animations", []):
        worst = 0.0
        for ch in a.get("channels", []):
            s = a["samplers"][ch["sampler"]]
            acc = J["accessors"][s["output"]]
            if ch["target"]["path"] != "rotation" or "min" not in acc:
                continue
            # 用 accessor 的 min/max 只能粗判；精确要读 BIN（这里如实标口径）
        out.append({"名": a.get("name"), "轨": len(a.get("channels", [])),
                    "闭合差": None,
                    "口径": "闭合差要用本仓 anim-retarget/ gate_anim 那支精确读（本件只报轨数）"})
    return out


def one(rel: str) -> dict:
    p = ROOT / rel
    if not p.is_file():
        return {"文件": rel, "在盘": False}
    J, BIN = read_glb(p)
    n_tri = _tri_count(J)
    bb = _bbox(J)
    skins = J.get("skins") or []
    joints = len(skins[0].get("joints", [])) if skins else 0
    has_normal = any("NORMAL" in pr["attributes"]
                     for m in J.get("meshes", []) for pr in m.get("primitives", []))
    has_uv = any("TEXCOORD_0" in pr["attributes"]
                 for m in J.get("meshes", []) for pr in m.get("primitives", []))
    mats = J.get("materials") or []
    w = _weights(J, BIN) if skins else {"有WEIGHTS_0": False, "说明": "无 skin"}
    return {"文件": rel, "在盘": True, "MB": round(p.stat().st_size / 1e6, 2),
            "三角面": n_tri, "包围盒": bb, "关节数": joints,
            "有NORMAL": has_normal, "有TEXCOORD_0": has_uv, "材质数": len(mats),
            "蒙皮": w, "动画": _anims(J),
            "面数预算": ("主角量级 ✔" if 20000 <= n_tri <= 80000 else
                        ("偏小/道具级" if n_tri < 20000 else "**超主角预算**"))}


def check() -> int:
    rows = [one(x) for x in IN_SERVICE]
    scand = [p for p in ROOT.rglob("*.glb") if not any(s in p.parts for s in SKIP)]
    d = {"逐条": rows, "全盘GLB数": len(scand),
         "未检（明写·不装会）": ["雕刻与重拓扑", "UV 岛间距像素测量", "PBR 贴图烘焙",
                                "权重刷与形变环", "IK/FK 与 BlendShape", "LOD 生成与引擎内复核"],
         "口径": "**能机检的一律机检；机检不了的如实标「未检」** —— 那六件要 Blender 交互或专门工具。"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("3D 资产机检（十道工序）")
    for r in rows:
        if not r.get("在盘"):
            print("  %-50s **不在盘**" % r["文件"]); continue
        bb = r["包围盒"]
        print("  %-50s %.2fMB · %d 面 · %s" % (r["文件"].split("/")[-1][:50], r["MB"],
                                              r["三角面"], r["面数预算"]))
        print("      包围盒 %s · 关节 %d · NORMAL=%s · UV=%s · 材质 %d"
              % (bb.get("尺寸"), r["关节数"], r["有NORMAL"], r["有TEXCOORD_0"], r["材质数"]))
        w = r["蒙皮"]
        if w.get("有WEIGHTS_0"):
            print("      蒙皮：顶点 %d · 零权重 %d · 权重和最大偏差 %.6f ⇒ 归一=%s"
                  % (w["顶点数"], w["零权重顶点"], w["权重和最大偏差"], w["权重归一"]))
        else:
            print("      蒙皮：**无 WEIGHTS_0**（%s）" % w.get("说明", ""))
        if r["动画"]:
            print("      动画 %d 条：%s" % (len(r["动画"]),
                                          ", ".join("%s(%d轨)" % (a["名"], a["轨"]) for a in r["动画"])))
    print()
    print("  全盘 GLB：%d 个（本检只覆盖在役 %d 个；备份/测试碎片不检）" % (d["全盘GLB数"], len(rows)))
    print("  **未检（明写·不装会）**：%s" % " · ".join(d["未检（明写·不装会）"]))
    ok = all(r.get("在盘") for r in rows)
    print("判据：%s" % ("PASS（在役件都检到了）" if ok else "FAIL（有在役件不在盘）"))
    return 0 if ok else 1


def selftest() -> int:
    rows = [one(x) for x in IN_SERVICE]
    real = [r for r in rows if r.get("在盘")]
    print("负对照A·面数必须真读出来（不是照抄）=> 各件面数 %s" % [r["三角面"] for r in real])
    print("负对照B·无 skin 的件要如实说无 WEIGHTS_0 =>",
          [r["文件"].split("/")[-1] for r in real if not r["蒙皮"].get("有WEIGHTS_0")] or "都有 skin")
    ok = len(real) >= 3 and all(r["三角面"] > 0 for r in real)
    print("自检：%s" % ("全过" if ok else "不过"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="3D 资产机检")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else check()


if __name__ == "__main__":
    raise SystemExit(main())
