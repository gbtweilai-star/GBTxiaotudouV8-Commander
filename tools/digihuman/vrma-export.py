# -*- coding: utf-8 -*-
"""补齐缺口：`anim.retarget` ⇒ 导出 **VRM Animation 1.0（`.vrma`）**。

    python tools/digihuman/vrma-export.py <绑骨含动画.glb> <输出.vrma> [clip名]
    python tools/digihuman/vrma-export.py --check <某.vrma>      # 门：结构合规性

契约（VRMC_vrm_animation-1.0 原文，Round 8 抓取）：
- 根级 `extensions.VRMC_vrm_animation = {specVersion:"1.0", humanoid:{humanBones:{<名>:{node}}}, expressions?, lookAt?}`
  `extensionsUsed` 含 `VRMC_vrm_animation`；
- 动画用 **glTF 原生 `animations`**；**首个 animation 被加载**；
- humanoid 骨节点须处于 **T-pose 静止姿**（我们的骨架正是从 T-pose 建 ⇒ 天然满足）；
- **动画不得含 scale**；**除 Hips 外不得含 translation**；leftEye/rightEye 不可有动画；
- 它**不放进 VRM 模型文件**，是单独一份"只有动画"的 glTF（扩展名 `.vrma`）。
"""
from __future__ import annotations

import json
import pathlib
import struct
import sys

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


WS = pathlib.Path(__file__).resolve().parents[2]
MIXAMO_TO_VRM = {
    "Hips": "hips", "Spine": "spine", "Spine1": "chest", "Spine2": "upperChest",
    "Neck": "neck", "Head": "head",
    "LeftShoulder": "leftShoulder", "LeftArm": "leftUpperArm", "LeftForeArm": "leftLowerArm",
    "LeftHand": "leftHand", "RightShoulder": "rightShoulder", "RightArm": "rightUpperArm",
    "RightForeArm": "rightLowerArm", "RightHand": "rightHand",
    "LeftUpLeg": "leftUpperLeg", "LeftLeg": "leftLowerLeg", "LeftFoot": "leftFoot",
    "LeftToeBase": "leftToes", "RightUpLeg": "rightUpperLeg", "RightLeg": "rightLowerLeg",
    "RightFoot": "rightFoot", "RightToeBase": "rightToes",
}
VRM_REQUIRED = ["hips", "spine", "head", "leftUpperArm", "leftLowerArm", "leftHand",
                "rightUpperArm", "rightLowerArm", "rightHand", "leftUpperLeg", "leftLowerLeg",
                "leftFoot", "rightUpperLeg", "rightLowerLeg", "rightFoot"]


def load(p: pathlib.Path):
    raw = p.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, raw[off + 8: off + 8 + bl]


def write(p: pathlib.Path, J, BIN: bytes):
    js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    body = bytearray(BIN)
    while len(body) % 4:
        body.append(0)
    J["buffers"] = [{"byteLength": len(body)}]
    js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    p.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                  + struct.pack("<I", len(js)) + b"JSON" + js
                  + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))


def export(src: pathlib.Path, out: pathlib.Path, clip: str | None = None):
    J, BIN = load(src)
    names = [n.get("name", "") for n in J["nodes"]]
    # 1) 人形骨：节点 → VRM 语义名
    bone = {}
    for i, nm in enumerate(names):
        v = MIXAMO_TO_VRM.get(nm.split(":")[-1])
        if v:
            bone[i] = v
    # 2) 只保留人形骨节点（丢掉弹簧骨/裙/发/tip），并重建父子（相对平移沿用源件 = T-pose 静止姿）
    keep = sorted(bone)
    newidx = {old: k for k, old in enumerate(keep)}
    parent = {}
    for i, n in enumerate(J["nodes"]):
        for c in n.get("children") or []:
            parent[c] = i
    # VRM T-pose 约定：脚在 y=0。本仓模型归一化后原点在身体中心 ⇒ 整体上移半身高
    ys = [P[1] for P in (J["nodes"][i].get("translation", [0, 0, 0]) for i in keep)]
    T_POSE_SHIFT = 0.5
    nodes = []
    for old in keep:
        _t = [float(x) for x in J["nodes"][old].get("translation", [0, 0, 0])]
        if parent.get(old) not in newidx:      # 人形骨最外层根（父不是人形骨）才挪 ⇒ 脚落 y=0
            _t = [_t[0], _t[1] + T_POSE_SHIFT, _t[2]]
        nodes.append({"name": bone[old], "translation": _t})
    for old in keep:
        p = parent.get(old)
        while p is not None and p not in newidx:      # 找最近的人形祖先
            p = parent.get(p)
        if p is not None:
            nodes[newidx[p]].setdefault("children", []).append(newidx[old])
    # 3) 动画：只留人形骨通道，**丢 scale**，**除 hips 外丢 translation**（VRMA 硬约束）
    anims = []
    for a in J.get("animations", []):
        if clip and a.get("name") != clip:
            continue
        chans, samplers, smap = [], [], {}
        for ch in a.get("channels", []):
            tgt = ch["target"]
            node = tgt.get("node")
            if node not in newidx:
                continue
            path = tgt.get("path")
            if path == "scale":
                continue
            if path == "translation" and bone[node] != "hips":
                continue
            s = ch["sampler"]
            if s not in smap:
                samplers.append(a["samplers"][s])
                smap[s] = len(samplers) - 1
            chans.append({"sampler": smap[s], "target": {"node": newidx[node], "path": path}})
        if chans:
            anims.append({"name": a.get("name", "clip"), "channels": chans, "samplers": samplers})
    V = {
        "asset": {"version": "2.0", "generator": "GBT小土豆V8 · VRMA 导出（VRMC_vrm_animation 1.0）"},
        "extensionsUsed": ["VRMC_vrm_animation"],
        "extensions": {"VRMC_vrm_animation": {
            "specVersion": "1.0",
            "humanoid": {"humanBones": {bone[old]: {"node": newidx[old]} for old in keep}},
        }},
        "nodes": nodes, "scenes": [{"nodes": [newidx[i] for i in keep if parent.get(i) not in newidx]}],
        "scene": 0,
        "animations": anims,
        "accessors": J["accessors"], "bufferViews": J["bufferViews"],
        "buffers": [{"byteLength": len(BIN)}],
    }
    write(out, V, BIN)
    ok, note = check(out)
    print(f"输出 {out.name} · {out.stat().st_size/1024/1024:.2f} MB · 动画 {[a['name'] for a in anims]}")
    print(f"VRMA 门: {'✅' if ok else '❌'} {note}")
    return 0 if ok else 1


def check(p: pathlib.Path):
    if not p.exists():
        return False, f"缺 {p.name}"
    J, _ = load(p)
    ext = (J.get("extensions") or {}).get("VRMC_vrm_animation")
    if not ext:
        return False, "缺 VRMC_vrm_animation 扩展"
    if ext.get("specVersion") != "1.0":
        return False, "specVersion≠1.0"
    if "VRMC_vrm_animation" not in (J.get("extensionsUsed") or []):
        return False, "extensionsUsed 未声明"
    hb = (ext.get("humanoid") or {}).get("humanBones") or {}
    miss = [b for b in VRM_REQUIRED if b not in hb]
    if miss:
        return False, f"humanBones 缺必需骨 {len(miss)}: {','.join(miss[:4])}"
    if not J.get("animations"):
        return False, "无 animations"
    bad = []
    for a in J["animations"]:
        for ch in a["channels"]:
            path = ch["target"]["path"]
            node = ch["target"]["node"]
            if path == "scale":
                bad.append("含 scale 通道")
            if path == "translation" and J["nodes"][node].get("name") != "hips":
                bad.append(f"非 hips 含 translation（{J['nodes'][node].get('name')}）")
    if bad:
        return False, "；".join(sorted(set(bad))[:3])
    return True, (f"humanBones {len(hb)} 个（必需骨齐）· 动画 {len(J['animations'])} 段 · "
                  f"通道 {sum(len(a['channels']) for a in J['animations'])} 条 · 无 scale / 仅 hips 有 translation")


if __name__ == "__main__":
    if "--check" in sys.argv:
        i = sys.argv.index("--check")
        target = pathlib.Path(sys.argv[i + 1])
        ok, note = check(target)
        print(f"VRMA 门: {'✅' if ok else '❌'} {note}")
        raise SystemExit(0 if ok else 1)
    src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
        WS / "holo_pet/assets/digital-human/raw/rig/model-rigged-anim.glb"
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else \
        WS / "holo_pet/assets/digital-human/raw/rig/avatar-motion.vrma"
    clip = sys.argv[3] if len(sys.argv) > 3 else None
    raise SystemExit(export(src, out, clip))
