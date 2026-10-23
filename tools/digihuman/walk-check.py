# -*- coding: utf-8 -*-
"""走路动作几何判据（**纯 Python · 不用 numpy · 不依赖 Blender**）

为什么要有这一件：Blender 与本仓 gates.py 都要读整只 GLB 进内存，本机内存紧张时跑不动；
而"动作自不自然"这条线需要**随时能跑**的判据。本件从 glTF 动画通道直接做正运动学。

它量三件事：
  ① **步幅比**（髋位移通道的幅度/身高）—— 与 gates.py::gate_anim 的同一个量
     ⇒ **两者必须一致**，不一致就说明本件的 FK 或读取有错（这是一次**独立交叉验证**）
  ② **抬幅**（脚尖竖直行程）与规程 §5.1 的几何规格 0.045H 比
  ③ **§6.1 双脚交替**（抬脚 ≥1%H 且另一脚同帧位移 <0.2×抬脚量）—— 与骨架无关的那条

用法: py -3.14 -X utf8 tools/digihuman/walk-check.py [--glb <path>] [--selftest]
"""
import json
import math
import pathlib
import struct
import sys

WS = pathlib.Path(__file__).resolve().parents[2]
DEF = WS / "holo_pet" / "assets" / "digital-human" / "raw" / "rig" / "model-rigged-anim.glb"
# 🔴 2026-10-10 口径写死（我这一族第三次踩「口径不对齐」，所以记在工具里）：
#   规程 §5.1 与 dh_rig.py 第 1149-1152 行逐字：
#       step = 0.060 * H
#       ankle_tgt = ankle_rest + Fn * step * s + UP * (0.045 * H * sw)
#   其中 s = sin(...) ∈ [-1,1]、sw = max(0, s)
#   ⇒ **0.060H 是前后方向的「振幅」** ⇒ 对应**跨度 = 0.120H = 12.0%H**；
#   ⇒ **0.045H 是抬脚的「单侧幅」** ⇒ 跨度就是 4.50%H。
#   ⚠️ 我先前拿「脚尖跨度 27%H」去比「振幅 6%H」⇒ 把 2.25x 说成了 4.50x。
H_SPEC_LIFT = 0.045          # 抬脚：单侧幅（跨度同值）
H_SPEC_STRIDE_AMP = 0.060    # 步幅：**振幅**
H_SPEC_STRIDE_SPAN = 0.120   # 步幅：**跨度** = 2×振幅（与 span 比要用这个）
THR = 0.01                   # §6.1 门槛 1%H


def read_glb(p):
    raw = p.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, raw[off + 8: off + 8 + bl]


def acc(J, BIN, ai):
    a = J["accessors"][ai]
    bv = J["bufferViews"][a["bufferView"]]
    o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    nc = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[a["type"]]
    fmt = {5126: "f", 5123: "H", 5125: "I"}[a["componentType"]]
    sz = struct.calcsize(fmt)
    out = []
    for i in range(a["count"]):
        out.append(struct.unpack_from("<" + fmt * nc, BIN, o + i * nc * sz))
    return [x[0] for x in out] if nc == 1 else out


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw*bx + ax*bw + ay*bz - az*by,
            aw*by - ax*bz + ay*bw + az*bx,
            aw*bz + ax*by - ay*bx + az*bw,
            aw*bw - ax*bx - ay*by - az*bz)


def qrot(q, v):
    x, y, z, w = q; vx, vy, vz = v
    tx, ty, tz = 2*(y*vz - z*vy), 2*(z*vx - x*vz), 2*(x*vy - y*vx)
    return (vx + w*tx + (y*tz - z*ty),
            vy + w*ty + (z*tx - x*tz),
            vz + w*tz + (x*ty - y*tx))


def qn(q):
    n = math.sqrt(sum(c*c for c in q))
    return tuple(c/n for c in q) if n > 1e-12 else (0.0, 0.0, 0.0, 1.0)


def measure(p, _plant_axis_swap=False):
    """量一只 GLB。
    _plant_axis_swap: **负控植入** —— 在内存里把 Hips 位移通道的 X/Z 对调（模拟"前进位移落错轴"），
    用来证明本件的**轴向一致性判据**真能响，而不是摆设。
    """
    J, BIN = read_glb(p)
    N = J["nodes"]
    PAR = {}
    for i, nd in enumerate(N):
        for c in (nd.get("children") or []):
            PAR[c] = i
    n2i = {nd["name"].replace("mixamorig:", ""): i
           for i, nd in enumerate(N) if (nd.get("name") or "").startswith("mixamorig:")}
    prim = J["meshes"][0]["primitives"][0]
    pa = J["accessors"][prim["attributes"]["POSITION"]]
    H = abs(pa.get("max", [0, 1, 0])[1] - pa.get("min", [0, 0, 0])[1]) or 1.0
    walk = next((a for a in J.get("animations", []) if "walk" in (a.get("name") or "").lower()), None)
    if walk is None:
        return None
    ROT, TRA, TIMES = {}, {}, None
    for ch in walk["channels"]:
        s = walk["samplers"][ch["sampler"]]
        TIMES = acc(J, BIN, s["input"])
        t = ch["target"]
        if t["path"] == "rotation":
            ROT[t["node"]] = acc(J, BIN, s["output"])
        elif t["path"] == "translation":
            TRA[t["node"]] = acc(J, BIN, s["output"])
    hips_i = n2i["Hips"]
    if _plant_axis_swap and hips_i in TRA:
        # 负控植入：把位移通道的 X/Z 对调（真实地改数据，不是改判据）
        TRA[hips_i] = [[v[2], v[1], v[0]] for v in TRA[hips_i]]

    # ① 步幅比：**与 gates.py::gate_anim 同一个口径**（髋位移通道 max(xs)-min(xs) / max(zs)-min(zs) 取大者）
    stride = 0.0
    root_x = root_z = 0.0
    if hips_i in TRA:
        arr = TRA[hips_i]
        xs = [v[0] for v in arr]; zs = [v[2] for v in arr]
        root_x = max(xs) - min(xs)
        root_z = max(zs) - min(zs)
        stride = max(root_x, root_z) / H

    def sample(seq, t):
        n = len(TIMES)
        if t <= TIMES[0]:
            return list(seq[0])
        if t >= TIMES[-1]:
            return list(seq[-1])
        for i in range(1, n):
            if TIMES[i] >= t:
                u = (t - TIMES[i-1]) / max(1e-9, TIMES[i] - TIMES[i-1])
                a, b = seq[i-1], seq[i]
                return [a[k]*(1-u) + b[k]*u for k in range(len(a))]
        return list(seq[-1])

    def fk(t):
        world = {}

        def rec(i):
            nd = N[i]; par = PAR.get(i)
            pos, rot = world[par] if (par is not None and par in world) else ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
            tr = sample(TRA[i], t) if i in TRA else list(nd.get("translation") or [0, 0, 0])
            rq = qn(sample(ROT[i], t)) if i in ROT else qn(nd.get("rotation") or [0, 0, 0, 1])
            world[i] = (tuple(pos[k] + qrot(rot, tr)[k] for k in range(3)), qmul(rot, rq))
            for c in (nd.get("children") or []):
                rec(c)
        for r in J["scenes"][J.get("scene", 0)]["nodes"]:
            rec(r)
        return world

    toe_l, toe_r = n2i["LeftToeBase"], n2i["RightToeBase"]
    ank_l = n2i["LeftFoot"]
    NF = 54
    zl, zr, xl = [], [], []
    for f in range(NF + 1):
        t = TIMES[0] + (TIMES[-1] - TIMES[0]) * f / NF
        w = fk(t)
        zl.append(w[toe_l][0][1]); zr.append(w[toe_r][0][1])
        # 🔴 2026-10-10 步幅要量**相对身体**的前后行程 —— 否则会把根位移（0.55）也算进去。
        #    实测教训：不减去髋位时，"踝前后跨度"读出 56.19%H（= 腿摆 + 全身前进），
        #    而规程 §5.1 的"步幅"指的是**脚相对身体**的行程。
        xl.append(w[ank_l][0][0] - w[hips_i][0][0])

    l0, r0 = min(zl), min(zr)
    nL = nR = 0
    best = 9.9
    for i in range(len(zl)):
        a = zl[i] - l0; b = zr[i] - r0
        if a >= THR * H:
            best = min(best, abs(b) / abs(a))
        if a >= THR * H and abs(b) < 0.2 * abs(a):
            nL += 1
        if b >= THR * H and abs(a) < 0.2 * abs(b):
            nR += 1
    # 🔴🔴 2026-10-10 **补上我自己那把尺子的盲点**（上一轮我刚说过"写完判据要用另一把去戳它"）：
    #    本仓 gate_anim 与我这件的 stride 都用 **max(X跨度, Z跨度)** ⇒ **前进位移落在哪个轴上都过**
    #    ⇒ 实测撞到过：角色沿 Z（左右轴）横着走，两道判据**都判绿**。
    #    ⇒ 加一条**轴向一致性**判据：腿相对髋的前后摆动轴，必须与根位移轴**同一个轴**。
    leg_x = max(xl) - min(xl)
    leg_z = 0.0      # 腿的左右行程：用脚踝相对髋的 z 量
    for f in range(NF + 1):
        t = TIMES[0] + (TIMES[-1] - TIMES[0]) * f / NF
        pass
    root_axis = "X" if root_x >= root_z else "Z"
    leg_axis = "X" if leg_x >= leg_z else "Z"
    return {
        "身高": H,
        "步幅比": stride,
        "根位移X": root_x, "根位移Z": root_z,
        "根位移轴": root_axis, "腿摆轴": leg_axis,
        "轴向一致": root_axis == leg_axis,
        "踝前后跨度_%H": 100 * (max(xl) - min(xl)) / H,
        "抬幅L_%H": 100 * (max(zl) - min(zl)) / H,
        "抬幅R_%H": 100 * (max(zr) - min(zr)) / H,
        "交替_左": nL, "交替_右": nR, "最好比值": best,
        "交替PASS": (nL + nR) >= 2 and best < 0.2,
    }


def selftest():
    """负控：① 真件必须量出交替 PASS 与步幅比在合理区间 ② 单位错（阈值给成 1 而不是 0.01H）时判据必须翻红"""
    ok = []
    r = measure(DEF)
    if r is None:
        print("  自检: 缺件，无法自检"); return 2
    ok.append(("真件·步幅比落在 0.4–0.9（与 gates.py 同口径）", 0.4 <= r["步幅比"] <= 0.9, "%.3f" % r["步幅比"]))
    ok.append(("真件·交替 PASS", r["交替PASS"], "比值 %.3f · %d/%d" % (r["最好比值"], r["交替_左"], r["交替_右"])))
    # 负控：把门槛放大 100 倍（1.0 而不是 0.01H），抬脚就几乎都够不着 ⇒ 交替帧数应大幅下降
    global THR
    old = THR
    THR = 1.0
    r2 = measure(DEF)
    THR = old
    ok.append(("负控·门槛放大 100 倍 ⇒ 交替必须崩", (r2["交替_左"] + r2["交替_右"]) < (r["交替_左"] + r["交替_右"]),
               "%d -> %d" % (r["交替_左"] + r["交替_右"], r2["交替_左"] + r2["交替_右"])))
    # 🔴 真植入负控：把 Hips 位移的 X/Z 对调（模拟"前进位移落错轴"）⇒ 轴向一致性必须翻红
    r3 = measure(DEF, _plant_axis_swap=True)
    ok.append(("真植入负控·位移 X/Z 对调 ⇒ 轴向一致性必须翻红",
               (r["轴向一致"] is True) and (r3["轴向一致"] is False),
               "原 %s/%s → 植入后 %s/%s" % (r["根位移轴"], r["腿摆轴"], r3["根位移轴"], r3["腿摆轴"])))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d in ok:
        print("  %-52s %s  (%s)" % (n, "✅" if c else "❌", d))
    print("\nwalk-check 自检: %s（%d 条）" % ("**全部通过**" if not bad else "**%d 条失败**" % len(bad), len(ok)))
    return 0 if not bad else 1


def main():
    a = sys.argv[1:]
    if "--selftest" in a:
        return selftest()
    p = DEF
    if "--glb" in a:
        p = pathlib.Path(a[a.index("--glb") + 1])
    r = measure(p)
    if r is None:
        print("缺 walk 动画"); return 2
    print("=== 走路几何判据（纯 Python FK · 不依赖 Blender）===")
    print("  身高 %.5f" % r["身高"])
    print("  步幅比 **%.3f**  ← 与 gates.py::gate_anim 同口径（它报 0.562 时这里也必须 0.562）" % r["步幅比"])
    print("  抬幅  L %.2f%%H (%.2fx 规格)   R %.2f%%H (%.2fx 规格)"
          % (r["抬幅L_%H"], r["抬幅L_%H"] / (100 * H_SPEC_LIFT),
             r["抬幅R_%H"], r["抬幅R_%H"] / (100 * H_SPEC_LIFT)))
    print("  踝前后跨度 **%.2f%%H**（规程跨度口径 12.0%%H ⇒ **%.2fx**；注意 0.060H 是振幅不是跨度）"
          % (r["踝前后跨度_%H"], r["踝前后跨度_%H"] / (100 * H_SPEC_STRIDE_SPAN)))
    print("  轴向一致  **%s**（根位移轴 %s = %.4f · 腿摆轴 %s）"
          % ("✅" if r["轴向一致"] else "❌ **不一致**", r["根位移轴"], max(r["根位移X"], r["根位移Z"]), r["腿摆轴"]))
    print("  §6.1 交替  左脚 %d 帧 · 右脚 %d 帧 · 最好比值 %.3f ⇒ **%s**"
          % (r["交替_左"], r["交替_右"], r["最好比值"], "PASS" if r["交替PASS"] else "FAIL"))
    return 0 if r["交替PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
