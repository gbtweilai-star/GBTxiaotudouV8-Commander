# -*- coding: utf-8 -*-
"""anim-audit.py —— 读 GLB 里的动画数据，量出"哪根骨头被动画扭坏了"。

为什么要有这一件（2026-10-19 实栽）：
  idle 动作把她的双腿折到了头顶上方/胯上，而我上一轮把已经量到的 1.665m
  当成"idle 的臂展"来判读 —— 那其实是 **bind pose（T-pose）** 的臂展。
  同一个量具量了另一个对象，于是"改轨道"改错了地方（P1_判据错尺_假绿）。
  这一件只做一件事：直接读 GLB 的 animation 通道，把每根骨头
  "首帧姿势 vs 静止姿势"的夹角按从大到小排出来。骨头名 + 角度 = 真读数。

口径：
  · 不猜、不靠引擎：直接解析 GLB 二进制（JSON chunk + BIN chunk + accessor）
  · 角度单位是度；阈值 --threshold（默认 30°）以上的才打印，--all 全打
  · 退出码 0 = 读成功（不管有没有超阈值）；1 = 文件读不了/不是 GLB
  · 只读：不写任何文件、不改 GLB

用法：
  py -3.14 tools/codex-scripts/anim-audit.py holo_pet_w3/voice-theater/assets/dh-v2-rigged.glb
  py -3.14 tools/codex-scripts/anim-audit.py <glb> --all --json
"""
import io
import json
import math
import struct
import sys

# 编码守门（本仓规矩：不带 -X utf8 调用时不许静默输出空；Windows 控制台默认 GBK）
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

COMP = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(path):
    with open(path, "rb") as f:
        blob = f.read()
    if len(blob) < 20:
        raise ValueError("不是 GLB：文件只有 %d 字节" % len(blob))
    magic, ver, total = struct.unpack_from("<4sII", blob, 0)
    if magic != b"glTF":
        raise ValueError("不是 GLB：magic=%r（应为 b'glTF'）" % magic)
    off = 12
    js = None
    bin_ = None
    while off + 8 <= len(blob):
        clen, ctype = struct.unpack_from("<II", blob, off)
        data = blob[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode("utf-8"))
        elif ctype == 0x004E4942:
            bin_ = data
        off += 8 + clen + ((4 - clen % 4) % 4 if clen % 4 else 0)
    if js is None:
        raise ValueError("GLB 里没有 JSON chunk")
    return js, bin_, len(blob)


def read_accessor(js, bin_, idx):
    acc = js["accessors"][idx]
    if acc.get("bufferView") is None:
        return [([0.0] * NCOMP[acc["type"]])] * acc.get("count", 0)
    bv = js["bufferViews"][acc["bufferView"]]
    n = NCOMP[acc["type"]]
    fmt, size = COMP[acc["componentType"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or (n * size)
    out = []
    for i in range(acc["count"]):
        off = base + i * stride
        out.append(list(struct.unpack_from("<" + fmt * n, bin_, off)))
    return out


def qnorm(q):
    d = math.sqrt(sum(x * x for x in q)) or 1.0
    return [x / d for x in q]


def qangle(a, b):
    """两个四元数之间的夹角（度），取最短弧。"""
    a = qnorm(a)
    b = qnorm(b)
    dot = abs(sum(x * y for x, y in zip(a, b)))
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


def node_rest_rot(node):
    if "rotation" in node:
        return list(node["rotation"])
    if "matrix" in node:
        m = node["matrix"]  # column-major
        # 从 3x3 提取四元数
        m00, m01, m02 = m[0], m[4], m[8]
        m10, m11, m12 = m[1], m[5], m[9]
        m20, m21, m22 = m[2], m[6], m[10]
        tr = m00 + m11 + m22
        if tr > 0:
            s = math.sqrt(tr + 1.0) * 2
            return [(m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s]
        if m00 > m11 and m00 > m22:
            s = math.sqrt(1.0 + m00 - m11 - m22) * 2
            return [0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s]
        if m11 > m22:
            s = math.sqrt(1.0 + m11 - m00 - m22) * 2
            return [(m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s]
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2
        return [(m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s]
    return [0.0, 0.0, 0.0, 1.0]


def main(argv):
    if len(argv) < 2:
        print("用法: anim-audit.py <glb> [--all] [--threshold N] [--json]")
        return 1
    path = argv[1]
    show_all = "--all" in argv
    as_json = "--json" in argv
    thr = 30.0
    if "--threshold" in argv:
        thr = float(argv[argv.index("--threshold") + 1])
    try:
        js, bin_, nbytes = read_glb(path)
    except Exception as e:
        print("读不了 GLB：%s" % e)
        return 1

    nodes = js.get("nodes", [])
    anims = js.get("animations", [])
    if not as_json:
        print("GLB    %s（%d 字节 · nodes=%d · animations=%d）" % (path, nbytes, len(nodes), len(anims)))
    report = {"file": path, "bytes": nbytes, "animations": []}
    bad_total = 0
    for ai, an in enumerate(anims):
        name = an.get("name") or ("anim%d" % ai)
        rows = []
        for ch in an.get("channels", []):
            tgt = ch.get("target", {})
            if tgt.get("path") != "rotation":
                continue
            ni = tgt.get("node")
            if ni is None or ni >= len(nodes):
                continue
            smp = an["samplers"][ch["sampler"]]
            vals = read_accessor(js, bin_, smp["output"])
            if not vals:
                continue
            rest = node_rest_rot(nodes[ni])
            q0 = vals[0]
            ang = qangle(q0, rest)
            # 整段动作里偏离静止姿势的最大角度（判"回不回得来"）
            worst = max(qangle(v, rest) for v in vals)
            rows.append({"node": ni, "bone": nodes[ni].get("name", "#%d" % ni),
                         "deg_first": round(ang, 1), "deg_max": round(worst, 1),
                         "samples": len(vals)})
        rows.sort(key=lambda r: -r["deg_first"])
        held = [r for r in rows if r["deg_first"] >= thr]
        bad_total += len(held)
        report["animations"].append({"name": name, "channels": len(rows),
                                     "over_threshold": len(held), "rows": rows})
        if as_json:
            continue
        print("")
        print("动作 %-6s 通道 %d 条 · 首帧偏离静止姿势 ≥%.0f° 的有 %d 根"
              % (name, len(rows), thr, len(held)))
        show = rows if show_all else held
        for r in show[:40]:
            flag = "  ← 扭坏了" if r["deg_first"] >= 90 else ""
            print("    %-28s 首帧 %7.1f°   整段最大 %7.1f°   采样 %d%s"
                  % (r["bone"], r["deg_first"], r["deg_max"], r["samples"], flag))
        if not show:
            print("    （没有骨头超过 %.0f°：这段动作是贴着绑定姿势的）" % thr)

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print("")
    print("判读：首帧就偏离静止姿势 ≥%.0f° 的骨头 = 动作一开始就把她摆成另一个姿势。" % thr)
    print("      其中 ≥90° 的几乎一定是自动绑骨跑坏的（腿折到胯上/手臂反折）。")
    print("      要修就修这些骨头，不要改别的（改多了会把好关节也带坏）。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
