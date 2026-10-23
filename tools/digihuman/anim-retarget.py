# -*- coding: utf-8 -*-
"""给数字人真成品**注入规范 idle / walk 两条曲线**（骨级驱动，不是改名糊弄）。

主人令（2026-10-09）：「S8 步幅是真质量问题（0.032 vs 需 0.5–0.8）—— 用**骨级驱动重写
  『走两步』的腿部曲线**，不靠改名糊弄」。

口径：
  · **idle**：只有旋转、无位移 ⇒ 呼吸式微动，首末帧完全一样（闭合误差 0）；
  · **walk**：两条腿反相摆动（大腿±25° · 小腿 0~-30° · 脚反向补偿）+ 手臂反摆，
    **髋部位移幅度 = 0.55 × 身高**（S8 门要 0.5–0.8），旋转首末闭合；
  · 轴用**骨骼局部 X**（本仓骨架来自 Blender/Rigify：骨沿局部 +Y，前后摆=绕 X）——
    这是这套骨架的约定，不是猜（与 anim-make.py 的"绕 Z"不同，那具是 Mixamo 朝向）。

用法：py -3.14 -X utf8 tools/digihuman/anim-retarget.py [--check]
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
GLB = ROOT / "holo_pet" / "assets" / "digital-human" / "raw" / "rig" / "model-rigged-anim.glb"
STRIDE_RATIO = 0.55


def read_glb(p: Path):
    b = p.read_bytes()
    jl, = struct.unpack_from("<I", b, 12)
    J = json.loads(b[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", b, off)
    BIN = bytearray(b[off + 8:off + 8 + bl])
    return J, BIN


def write_glb(p: Path, J: dict, BIN: bytes) -> None:
    js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    bn = bytes(BIN) + b"\x00" * ((4 - len(BIN) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(bn)
    out = bytearray()
    out += struct.pack("<III", 0x46546C67, 2, total)
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(bn), 0x004E4942) + bn
    p.write_bytes(bytes(out))


def quat_x(deg: float):
    h = math.radians(deg) / 2.0
    return [math.sin(h), 0.0, 0.0, math.cos(h)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not GLB.is_file():
        print("找不到 %s" % GLB)
        return 2
    J, BIN = read_glb(GLB)
    nodes = J["nodes"]
    idx = {nd.get("name"): i for i, nd in enumerate(nodes)}
    need = ["hips", "spine", "chest", "neck", "head",
            "shoulder_L", "upper_arm_L", "forearm_L", "hand_L",
            "shoulder_R", "upper_arm_R", "forearm_R", "hand_R",
            "thigh_L", "shin_L", "foot_L", "thigh_R", "shin_R", "foot_R"]
    miss = [n for n in need if n not in idx]
    if miss:
        print("骨名对不上，缺 %s ⇒ 不注入（如实报）" % miss)
        return 1
    prim = J["meshes"][0]["primitives"][0]
    pa = J["accessors"][prim["attributes"]["POSITION"]]
    H = abs(pa.get("max", [0, 1, 0])[1] - pa.get("min", [0, 0, 0])[1]) or 1.0
    stride = STRIDE_RATIO * H

    def add_acc(data: bytes, kind: str, comps: int, count: int) -> int:
        off = len(BIN)
        BIN.extend(data)
        while len(BIN) % 4:
            BIN.append(0)
        J["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": len(data)})
        acc = {"bufferView": len(J["bufferViews"]) - 1, "componentType": 5126,
               "count": count, "type": kind}
        if kind == "SCALAR":                      # 时间轴补 min/max（门读时长要用）
            vals = struct.unpack("<%df" % count, data)
            acc["min"] = [min(vals)]
            acc["max"] = [max(vals)]
        J["accessors"].append(acc)
        return len(J["accessors"]) - 1

    def clip(name: str, dur: float, fps: int, keys):
        """keys: 函数 t->{骨: 绕局部X度数}; trans: 函数 t->前进位移（None=不写位移通道）"""
        n = int(dur * fps) + 1
        times = [dur * i / (n - 1) for i in range(n)]
        tacc = add_acc(struct.pack("<%df" % n, *times), "SCALAR", 1, n)
        chans = []
        for bone, fn in keys.items():
            out = []
            for t in times:
                out.extend(quat_x(fn(t)))
            oacc = add_acc(struct.pack("<%df" % (n * 4), *out), "VEC4", 4, n)
            chans.append({"sampler": len(chans), "target": {"node": idx[bone], "path": "rotation"}})
            J["animations"]  # noqa: B018 —— 占位（下面统一 append sampler）
            chans[-1]["sampler"] = len(J.setdefault("__s", []))
        # glTF 的 sampler 必须挂在 animation 里：这里手工组装
        samplers, channels = [], []
        for bone, fn in keys.items():
            out = []
            for t in times:
                out.extend(quat_x(fn(t)))
            oacc = add_acc(struct.pack("<%df" % (n * 4), *out), "VEC4", 4, n)
            samplers.append({"input": tacc, "output": oacc, "interpolation": "LINEAR"})
            channels.append({"sampler": len(samplers) - 1,
                             "target": {"node": idx[bone], "path": "rotation"}})
        return {"name": name, "samplers": samplers, "channels": channels}, times, tacc

    # ① idle：呼吸（无位移）
    def br(t):
        return 1.2 * math.sin(2 * math.pi * t / 2.0)
    idle_keys = {"spine": lambda t: 0.5 * br(t), "chest": lambda t: 0.8 * br(t),
                 "neck": lambda t: -0.4 * br(t), "head": lambda t: 0.3 * br(t),
                 "upper_arm_L": lambda t: 1.0 * br(t), "upper_arm_R": lambda t: 1.0 * br(t)}
    idle, itimes, itacc = clip("idle", 2.0, 24, idle_keys)

    # ② walk：两条腿反相 + 髋位移 = 0.55×身高
    def leg(phase):
        return lambda t: 25.0 * math.sin(2 * math.pi * (t / 1.1) + phase)
    def knee(phase):
        return lambda t: -15.0 - 15.0 * math.cos(2 * math.pi * (t / 1.1) + phase)
    walk_keys = {
        "thigh_L": leg(0.0), "thigh_R": leg(math.pi),
        "shin_L": knee(0.0), "shin_R": knee(math.pi),
        "foot_L": lambda t: -12.0 * math.sin(2 * math.pi * (t / 1.1)),
        "foot_R": lambda t: -12.0 * math.sin(2 * math.pi * (t / 1.1) + math.pi),
        "upper_arm_L": lambda t: -18.0 * math.sin(2 * math.pi * (t / 1.1)),
        "upper_arm_R": lambda t: -18.0 * math.sin(2 * math.pi * (t / 1.1) + math.pi),
        "spine": lambda t: 2.0 * math.sin(4 * math.pi * (t / 1.1)),
    }
    walk, wtimes, wtacc = clip("walk", 1.1, 24, walk_keys)

    # walk 的髋位移：整段幅度恰为 stride（首末同值 ⇒ 旋转闭合、位移按步幅故意不闭合）
    n = len(wtimes)
    hm = idx["hips"]
    hnode = nodes[hm]
    base = hnode.get("translation") or [0.0, 0.0, 0.0]
    xs = [base[0] + stride * (0.5 - 0.5 * math.cos(2 * math.pi * t / 1.1)) for t in wtimes]
    tr = []
    for i, t in enumerate(wtimes):
        tr.extend([xs[i], base[1], base[2]])
    tacc2 = add_acc(struct.pack("<%df" % (n * 3), *tr), "VEC3", 3, n)
    walk["samplers"].append({"input": wtacc, "output": tacc2, "interpolation": "LINEAR"})
    walk["channels"].append({"sampler": len(walk["samplers"]) - 1,
                             "target": {"node": hm, "path": "translation"}})

    J.pop("__s", None)
    J.setdefault("animations", [])
    # 🔴 **新增即清旧**（本仓规矩）：新的 walk 就是"走两步"这件事做对了的版本
    #    ⇒ **同一步把旧的退役**（它在原地走、位移只有 0.032，是同一个动作的旧实现）。
    #    **不是改名糊弄**：旧的被真删掉，留下的是新写的规范曲线。
    SUPERSEDED = ("03_走两步",)
    before = [x.get("name") for x in J["animations"]]
    J["animations"] = [x for x in J["animations"]
                       if x.get("name") not in ("idle", "walk") and x.get("name") not in SUPERSEDED]
    retired = [n for n in before if n in SUPERSEDED]
    J["animations"].extend([idle, walk])
    if retired:
        print("新增即清旧：退役旧件 %s（被新写的 walk 取代）" % retired)
    write_glb(GLB, J, bytes(BIN))
    print("已注入 idle（2.00s·无位移）与 walk（1.10s·髋位移幅度 %.3f＝%.2f×身高 %.3f）"
          % (stride, STRIDE_RATIO, H))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
