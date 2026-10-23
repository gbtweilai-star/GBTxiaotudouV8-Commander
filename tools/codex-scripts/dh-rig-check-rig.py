#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数字人 · 绑骨/蒙皮/全肢体动作 判据（含 **3 条负对照**）

⚠️ 文件路径说明（如实报偏离）：
  主人令里点名的是 `tools/codex-scripts/dh-rig-check.py`，但该路径**已被并行任务的产物占用**
  （2026-10-08 08:12 写入，内容是**页面侧** `GBT-RIG-SPEC` 的机检件，检查的是
  `holo_pet_w3/digital-human/index.html` 里内嵌的骨架规格，**不是** Blender 侧这套骨架）。
  为“不破坏真环境/不动别人的产物”，本件改落 `dh-rig-check-rig.py`，并在文档与台账写明这一条偏离。

用法：
  py -3.14 tools/codex-scripts/dh-rig-check-rig.py --check
  py -3.14 tools/codex-scripts/dh-rig-check-rig.py --check --write-ledger
  py -3.14 tools/codex-scripts/dh-rig-check-rig.py --probe bone-len      # 负对照① 改一侧骨长
  py -3.14 tools/codex-scripts/dh-rig-check-rig.py --probe frozen-frames # 负对照② 冻结整段动作
  py -3.14 tools/codex-scripts/dh-rig-check-rig.py --probe lock-ends     # 负对照③ 锁死四末端

口径（与 docs/数字人-绑骨与全肢体动作.md 一致）：
  · 一切阈值用**身高百分比**；身高 = 输入 GLB 的 AABB 高度（实测 0.98004 单位）
  · 四末端 = hand_L / hand_R / foot_L / foot_R 四根**末端骨的尾点(tail)**世界坐标
  · "真在动" = 相邻帧读数有非零变化 且 ≥3 个关节参与（世界角变化范围 > 0.5°）
  · "全肢体" = 四末端 tail **累计位移(路径积分)** ≥ 3% 身高
  · "独立复核" = 不读 trace，直接从导出的 GLB 里解节点层级+采样器，自己算一遍末端轨迹

负对照必须**报红**才算判据有效：报绿 ⇒ 判据是假的，返工。
"""
import argparse
import json
import math
import os
import struct
import sys
import time

WS = r"C:\Users\ADMIN\Desktop\GBT小土豆V8"
OUT = os.path.join(WS, "projects", "digital-human", "out")
GLB = os.path.join(OUT, "dh_rigged.glb")
TRACE = os.path.join(OUT, "trace.json")
REPORT = os.path.join(OUT, "rig_report.json")
CORE = os.path.join(OUT, "rig_core.json")
FRAMES = os.path.join(OUT, "frames")
LEDGER = os.path.join(WS, "state", "digital-human-rig.json")
SELF = os.path.join(WS, "tools", "codex-scripts", "dh-rig-check-rig.py")

END_BONES = ["hand_L", "hand_R", "foot_L", "foot_R"]
REQUIRED_BONES = (["hips", "spine", "chest", "neck", "head"]
                  + [b + "_" + s for b in ("shoulder", "upper_arm", "forearm", "hand")
                     for s in ("L", "R")]
                  + [b + "_" + s for b in ("thigh", "shin", "foot") for s in ("L", "R")])
BONE_LEAVES = ("shoulder", "upper_arm", "forearm", "hand", "thigh", "shin", "foot")

R = []


def ok(cid, name, passed, detail="", neg=False):
    R.append({"id": cid, "name": name, "pass": bool(passed), "detail": detail, "negative": neg})
    if neg:
        tag = "🟢 报红(符合预期)" if not passed else "🔴 报绿(判据失效!)"
    else:
        tag = "🟢 绿" if passed else "🔴 红"
    print("%-4s %-16s %s" % (cid, tag, name))
    if detail:
        print("        " + detail)
    return bool(passed)


# ------------------------------------------------------------------ GLB 读取
def glb_read(path):
    raw = open(path, "rb").read()
    magic = raw[:4]
    ver, total = struct.unpack_from("<II", raw, 4)
    jl, jt = struct.unpack_from("<II", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, bt = struct.unpack_from("<II", raw, off)
    BIN = raw[off + 8:off + 8 + bl]
    return raw, J, BIN, {"magic": magic.decode("ascii", "replace"), "version": ver,
                         "declared": total, "bytes": len(raw), "len_ok": total == len(raw)}


_CT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def acc(J, BIN, i):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    fmt, sz = _CT[a["componentType"]]
    n = _NC[a["type"]]
    base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or (sz * n)
    return [struct.unpack_from("<" + fmt * n, BIN, base + k * stride) for k in range(a["count"])]


# ------------------------------------------------------------------ 4x4 数学
def m4_mul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def m4_trs(t, r, s):
    x, y, z, w = r
    Rm = [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
          [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
          [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]]
    return [[Rm[i][j] * s[j] for j in range(3)] + [t[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def slerp(a, b, t):
    d = sum(a[i] * b[i] for i in range(4))
    if d < 0:
        b = tuple(-v for v in b); d = -d
    if d > 0.9995:
        q = tuple(a[i] + t * (b[i] - a[i]) for i in range(4))
    else:
        th0 = math.acos(max(-1.0, min(1.0, d)))
        th = th0 * t
        s0, s1 = math.sin(th0 - th) / math.sin(th0), math.sin(th) / math.sin(th0)
        q = tuple(a[i] * s0 + b[i] * s1 for i in range(4))
    n = math.sqrt(sum(v * v for v in q)) or 1.0
    return tuple(v / n for v in q)


def sample_acc(vals, times, t, is_quat):
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    lo, hi = 0, len(times) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if times[mid] <= t:
            lo = mid
        else:
            hi = mid
    span = (times[hi] - times[lo]) or 1.0
    u = (t - times[lo]) / span
    if is_quat:
        return slerp(vals[lo], vals[hi], u)
    a, b = vals[lo], vals[hi]
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(len(a)))


def glb_end_effector_paths(J, BIN, target_names=END_BONES):
    """**独立于 trace**：从导出的 GLB 自己解节点层级 + 动画采样器，算末端世界坐标轨迹"""
    import struct as _s
    raw = None
    nodes = J.get("nodes", [])
    name2idx = {n["name"]: i for i, n in enumerate(nodes) if n.get("name")}
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[c] = i
    parent.setdefault("__roots__", None)

    def static_local(i, over=None):
        """glTF 语义：动画通道**替换**该节点的 t/r/s 分量（不是叠乘）。over = 被替换后的分量。"""
        n = nodes[i]
        if "matrix" in n and not over:
            m = n["matrix"]
            return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
        tr = over.get("translation", n.get("translation", [0, 0, 0])) if over else n.get("translation", [0, 0, 0])
        ro = over.get("rotation", n.get("rotation", [0, 0, 0, 1])) if over else n.get("rotation", [0, 0, 0, 1])
        sc = over.get("scale", n.get("scale", [1, 1, 1])) if over else n.get("scale", [1, 1, 1])
        return m4_trs(tr, ro, sc)

    out = {}
    for a in J.get("animations", []):
        chans, maxt = {}, 0.0
        for ch in a.get("channels", []):
            tgt = ch["target"]
            if "node" not in tgt:
                continue
            smp = a["samplers"][ch["sampler"]]
            times = [v[0] for v in acc(J, BIN, smp["input"])]
            vals = acc(J, BIN, smp["output"])
            chans.setdefault(tgt["node"], {})[tgt["path"]] = (times, vals)
            if times:
                maxt = max(maxt, times[-1])
        ts = sorted({round(t, 4) for v in chans.values() for (ti, _) in v.values() for t in ti})
        if maxt and (not ts or ts[-1] < maxt - 1e-6):
            ts.append(round(maxt, 4))
        if len(ts) > 300:
            step = max(1, len(ts) // 300)
            ts = ts[::step]
        series = {n: [] for n in target_names if n in name2idx}
        for t in ts:
            memo = {}

            def wm(i):
                if i in memo:
                    return memo[i]
                over = {}
                for path, (times, vals) in chans.get(i, {}).items():
                    if times:
                        over[path] = sample_acc(vals, times, t, path == "rotation")
                L = static_local(i, over or None)
                p = parent.get(i)
                memo[i] = L if p is None else m4_mul(wm(p), L)
                return memo[i]

            for n in series:
                M = wm(name2idx[n])
                series[n].append(M[:3][0][3:4] + M[:3][1][3:4] + M[:3][2][3:4])
        out[a.get("name")] = series
    return out


def path_len(pts):
    return sum(math.dist(pts[i + 1], pts[i]) for i in range(len(pts) - 1))


def bbox_of(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
    return [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]


# ------------------------------------------------------------------ 主判据
def run_check(mut=None):
    mut = mut or {}
    del R[:]
    print("=" * 80)
    print("数字人 · 绑骨/蒙皮/全肢体动作 判据   %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 80)
    for p in (TRACE, REPORT, CORE, GLB):
        if not os.path.exists(p):
            ok("C0", "产物齐全", False, "缺 " + p)
            return False, R
    T = json.load(open(TRACE, encoding="utf-8"))
    RP = json.load(open(REPORT, encoding="utf-8"))
    CO = json.load(open(CORE, encoding="utf-8"))
    H = float(T["height_units"])
    SR = T["stage_ratio"]
    TH_END, TH_HIP, TH_LIFT = SR["end_effector_min"], SR["squat_hip_min"], SR["foot_lift_min"]
    print("身高 H = %.6f 单位（=输入 GLB AABB 高度）\n阈值：末端累计位移≥%.4f(3%%H) · 髋竖移≥%.4f(5%%H) "
          "· 抬脚≥%.4f(1%%H)\n" % (H, TH_END * H, TH_HIP * H, TH_LIFT * H))

    # C1 输入件
    hdr, gj = RP["input"]["header"], RP["input"]["gltf_json"]
    ok("C1", "输入件是真 GLB，且本来没有骨架/动画（⇒ 绑骨确实是零基础建的）",
       hdr["magic"] == "glTF" and hdr["length_matches"] and gj.get("skins") is None
       and gj.get("animations") is None,
       "magic=%s v%s 长度自洽=%s · skins=%s animations=%s · 源 %d 顶点 / %d 三角面"
       % (hdr["magic"], hdr["version"], hdr["length_matches"], gj.get("skins"),
          gj.get("animations"), gj.get("source_vertices"), gj.get("source_triangles")))

    # C2 内存纪律
    px, mem = RP["proxy"], RP["memory"]
    avail_min = min(m["avail_mb"] for m in mem) if mem else 9e9
    ok("C2", "内存纪律留痕：有实测空闲内存读数，且因 <2.5GB 而抽稀（全精度蒙皮未跑）",
       bool(mem) and px.get("decimated") is True and avail_min < 2560,
       "采样 %d 条，最低空闲 %.1f MB；全精度 %d 面 → 代理 %d 面（焊接后 %d 顶点，ratio=%.4f）"
       % (len(mem), avail_min, px["full_polys"], (px.get("weld") or {}).get("polys_after"), (px.get("weld") or {}).get("verts_after"), px["ratio"]))

    # C3 骨架齐全
    hier = RP["skeleton"]["hierarchy"]
    missing = [b for b in REQUIRED_BONES if b not in hier]
    ok("C3", "骨架齐全：全肢体（髋/脊/胸/颈/头 + 左右 肩-上臂-前臂-手 + 左右 髋-大腿-小腿-脚）",
       not missing and len(hier) == 19, "骨数=%d；缺=%s" % (len(hier), missing or "无"))

    # C4 左右对称
    sym = [dict(s) for s in RP["skeleton"]["symmetry"]]
    if mut.get("bone_len"):
        b0, side0 = mut["bone_len"]
        for s in sym:
            if s["bone"] == b0:
                key = "len_L" if side0 == "L" else "len_R"
                s[key] = round(s[key] * 1.30, 9)
                s["len_diff"] = abs(s["len_L"] - s["len_R"])
    max_len = max(s["len_diff"] for s in sym)
    for s in sym:
        s.setdefault("mirror_angle_deg", s.get("ang_vs_mirror_deg", 0.0))
    max_ang = max(s["mirror_angle_deg"] for s in sym)
    TOL_LEN, TOL_ANG = 1e-4, 0.5
    ok("C4", "骨架**左右对称**：对应骨长差 ≤1e-4 且镜像后指向夹角 ≤0.5°",
       max_len <= TOL_LEN and max_ang <= TOL_ANG,
       "最大骨长差=%.3e 单位（%s）· 最大镜像夹角=%.3e° ；逐对：%s"
       % (max_len, ", ".join("%s %.2e" % (s["bone"], s["len_diff"]) for s in sym),
          max_ang, len(sym) and "%d 对" % len(sym)),
       neg=bool(mut.get("bone_len")))

    # C5 蒙皮
    sk = RP["skinning"]
    ok("C5", "蒙皮存在且干净：顶点组=骨数 · 无权重顶点=0 · 权重和=1 · 零覆盖骨为空",
       sk["group_count"] == 19 and sk["unweighted_verts"] == 0
       and abs(sk["avg_weight_sum"] - 1.0) < 1e-3 and not sk["zero_cover_bones"],
       "方法=%s\n        组=%d 无权重顶点=%d(%.4f%%) 平均权重和=%.5f 零覆盖骨=%s"
       % (sk["method"], sk["group_count"], sk["unweighted_verts"], sk["unweighted_ratio"] * 100,
          sk["avg_weight_sum"], sk["zero_cover_bones"] or "无"))

    # C6 权重自检数字
    st, stb = sk.get("weight_stats_after_smooth", {}), sk.get("weight_stats_before_smooth", {})
    hb = st.get("hip_band_n", 0)
    ratio = (st.get("hip_band_first_hips", 0) / hb) if hb else 0.0
    r0 = (stb.get("hip_band_first_hips", 0) / hb) if hb else 0.0
    ok("C6", "权重自检（数字口径）：髋带第一影响骨 hips 占比 ≥60% 且跨侧权重峰值 ≤0.5",
       ratio >= 0.60 and st.get("opp_max", 9) <= 0.5,
       "髋带顶点 n=%d：第一影响骨 hips %d→%d (%.1f%%→%.1f%%)；跨侧权重 均值 %.4f→%.4f 峰值 %.4f→%.4f"
       % (hb, stb.get("hip_band_first_hips", -1), st.get("hip_band_first_hips", -1),
          r0 * 100, ratio * 100, stb.get("opp_mean", -1), st.get("opp_mean", -1),
          stb.get("opp_max", -1), st.get("opp_max", -1)))

    # ---- 动作：注入负对照扰动 ----
    acts = {a: dict(v) for a, v in T["actions"].items()}
    all_bones = T["all_bones"]
    touched = set()
    if mut.get("frozen"):
        af = mut["frozen"]
        rows = acts[af]["rows"]
        acts[af]["rows"] = [dict(rows[0], f=r["f"]) for r in rows]
        touched.add(af)
    if mut.get("lock_ends"):
        af = mut["lock_ends"]
        rows = acts[af]["rows"]
        new = []
        for r in rows:
            r2 = dict(r)
            for b in END_BONES:
                r2["T_" + b] = list(rows[0]["T_" + b])
                r2["H_" + b] = list(rows[0]["H_" + b])
            new.append(r2)
        acts[af]["rows"] = new
        touched.add(af)

    table, motion = [], []
    for a in acts:
        rows = acts[a]["rows"]
        nz = 0
        for i in range(len(rows) - 1):
            da = max(abs(rows[i + 1]["A_" + b] - rows[i]["A_" + b]) for b in all_bones)
            dt = max(math.dist(rows[i + 1]["T_" + b], rows[i]["T_" + b]) for b in END_BONES)
            dv = abs(rows[i + 1].get("vmax", 0.0) - rows[i].get("vmax", 0.0))
            if max(da, dt, dv) > 1e-6:
                nz += 1
        jm = sum(1 for b in all_bones
                 if max(r["A_" + b] for r in rows) - min(r["A_" + b] for r in rows) > 0.5)
        vmx = max(r.get("vmax", 0.0) for r in rows) / H
        ee = {b: path_len([r["T_" + b] for r in rows]) / H for b in END_BONES}
        table.append((a, ee))
        motion.append({"action": a, "nonzero_steps": nz, "steps": len(rows) - 1,
                       "joints_moved": jm, "ee": ee, "vmax_ratio": vmx})

    worst_nz = min(m["nonzero_steps"] / max(1, m["steps"]) for m in motion)
    worst_j = min(m["joints_moved"] for m in motion)
    ok("C7", "六段动作**真在动**（逐帧读数为准）：每个相邻帧都有非零变化 且 每段 ≥3 个关节参与",
       worst_nz >= 0.999 and worst_j >= 3,
       "最低相邻帧非零比例=%.4f；最少参与关节=%d/19" % (worst_nz, worst_j),
       neg=bool(mut.get("frozen")))
    for m in motion:
        print("        %-10s 相邻帧非零 %3d/%-3d · 参与关节 %2d/19 · 顶点最大位移 %.1f%%H"
              % (m["action"], m["nonzero_steps"], m["steps"], m["joints_moved"], m["vmax_ratio"] * 100))

    print("\n        【四末端累计位移表】单位=身高%%（路径积分；阈值 3%%）")
    print("        %-10s %-16s %-16s %-16s %-16s" % ("动作", *END_BONES))
    bad = []
    for a, ee in table:
        print("        %-10s %-16s %-16s %-16s %-16s" % (a, *["%.2f%%" % (ee[b] * 100)
                                                            for b in END_BONES]))
        bad += ["%s/%s=%.2f%%" % (a, b, ee[b] * 100) for b in END_BONES if ee[b] < TH_END]
    mn = min(min(ee.values()) for _a, ee in table) * 100
    ok("C8", "六段动作**全肢体**：四末端 tail 累计位移 全部 ≥3% 身高（24/24 达标）",
       not bad, ("24/24 达标，最小 %.2f%%（%s）" % (mn, min(table, key=lambda t: min(t[1].values()))[0]))
       if not bad else "不达标：%s" % ", ".join(bad), neg=bool(mut.get("lock_ends")))

    # C9 走两步交替
    w = acts.get("03_走两步")
    det, alt_ok = "缺动作", False
    if w:
        rows = w["rows"]
        g = {b: min(r["T_" + b][2] for r in rows) for b in ("foot_L", "foot_R")}
        lo = ro = 0
        ex = []
        for i in range(len(rows) - 1):
            zl, zr = rows[i]["T_foot_L"][2], rows[i]["T_foot_R"][2]
            dl, dr = abs(zl - g["foot_L"]), abs(zr - g["foot_R"])
            mvl = math.dist(rows[i + 1]["T_foot_L"], rows[i]["T_foot_L"])
            mvr = math.dist(rows[i + 1]["T_foot_R"], rows[i]["T_foot_R"])
            if dl >= TH_LIFT * H and dr < 0.2 * dl:
                lo += 1; ex.append((rows[i]["f"], "左", round(dl / H * 100, 2), round(mvr, 5)))
            elif dr >= TH_LIFT * H and dl < 0.2 * dr:
                ro += 1; ex.append((rows[i]["f"], "右", round(dr / H * 100, 2), round(mvl, 5)))
        alt_ok = lo >= 2 and ro >= 2
        det = ("左独立离地 %d 帧 / 右独立离地 %d 帧（判据：抬脚≥%.2f%%H 且另一脚同帧位移<0.2×抬脚量=%.4f 单位）\n"
               "        交替样例 (帧, 抬脚, 离地量%%, 另一脚同帧位移)：%s"
               % (lo, ro, TH_LIFT * 100, 0.2 * TH_LIFT * H, ex[:3] + ex[-2:]))
    ok("C9", "走两步专属：**双脚交替**（各 ≥2 帧独立离地，另一脚同帧基本不动）", alt_ok, det)

    # C10 蹲起
    q = acts.get("05_蹲起")
    hipdrop, dl, qv = 0.0, {}, "缺动作"
    if q:
        rows = q["rows"]
        hz = [r["H_hips"][2] for r in rows]
        hipdrop = (max(hz) - min(hz)) / H
        dl = {b: max(r["A_" + b] for r in rows) - min(r["A_" + b] for r in rows)
              for b in ("thigh_L", "shin_L", "foot_L")}
        qv = ("髋竖直位移 %.4f 单位 = %.2f%%H（阈值 ≥%.2f%%H）；三关节角度变化 髋 %.2f° / 膝 %.2f° / 踝 %.2f°"
              % (max(hz) - min(hz), hipdrop * 100, TH_HIP * 100, dl["thigh_L"], dl["shin_L"], dl["foot_L"]))
    ok("C10", "蹲起专属：髋/膝/踝**三关节同时变化**（各 >5°）且 髋部竖直位移 ≥5% 身高",
       bool(q) and hipdrop >= TH_HIP and all(v > 5.0 for v in dl.values()), qv)

    # C11 导出 GLB 动画通道
    raw, J, BIN, gh = glb_read(GLB)
    anims = J.get("animations") or []
    ch_total = sum(len(a.get("channels", [])) for a in anims)
    per = {a.get("name"): len(a.get("channels", [])) for a in anims}
    skins = J.get("skins") or []
    nj = len(skins[0].get("joints", [])) if skins else 0
    ok("C11", "导出的 GLB **真有 animation 通道**（真读文件字节，不看脚本日志）",
       gh["len_ok"] and len(anims) >= 6 and ch_total > 0 and all(v > 0 for v in per.values())
       and len(skins) == 1 and nj == 19,
       "%s %d 字节 · magic=%s v%s 长度自洽=%s · animations=%d 通道合计=%d · skin=1×%d 关节\n"
       "        逐段通道数=%s" % (os.path.basename(GLB), gh["bytes"], gh["magic"], gh["version"],
                                gh["len_ok"], len(anims), ch_total, nj, per))

    # C12 独立复核（从 GLB 自己解）
    lines, ind_ok = [], True
    try:
        ind = glb_end_effector_paths(J, BIN)
    except Exception as ex:
        ind, ind_ok = {}, False
        lines.append("解算失败 %r" % (ex,))
    for a in anims:
        nm = a.get("name")
        got = ind.get(nm, {})
        for b in END_BONES:
            pts = got.get(b) or []
            if len(pts) < 2:
                ind_ok = False; lines.append("%s/%s 解不出" % (nm, b)); continue
            gl = path_len(pts) / H
            # glTF 的骨骼节点**原点 = 骨头(head)**；trace 里对应的是 H_ 系列（不是 tail）
            tl = path_len([r["H_" + b] for r in acts[nm]["rows"]]) / H
            lines.append("%s/%s GLB节点头=%.1f%%H trace骨头=%.1f%%H" % (nm, b, gl * 100, tl * 100))
            if abs(gl - tl) > 0.35 * max(1e-9, tl):
                ind_ok = False
    ok("C12", "独立复核：**从导出的 GLB 自己解节点层级+采样器**算末端骨头位移，与 trace 的 H_ 系列差 ≤35%",
       ind_ok, "； ".join(lines[:4]) + (" … 共 %d 项" % len(lines)))

    # C13 渲染帧
    cnt = 0; minsz = (0, 0); hero = []
    for root, _d, files in os.walk(FRAMES):
        for f in files:
            if not f.lower().endswith(".png"):
                continue
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                hd = fh.read(33)
            if hd[:8] != b"\x89PNG\r\n\x1a\n":
                continue
            w_, h_ = struct.unpack(">II", hd[16:24])
            cnt += 1
            if minsz == (0, 0) or w_ * h_ < minsz[0] * minsz[1]:
                minsz = (w_, h_)
            if "_英雄静帧" in root:
                hero.append((f, w_, h_))
    hero_h = max([h for _f, _w, h in hero], default=0)
    ok("C13", "渲染帧真的落盘且是合法 PNG；含 ≥1920 高的英雄静帧",
       cnt >= 60 and minsz[0] >= 640 and hero_h >= 1920,
       "PNG 共 %d 张；动作帧最小 %dx%d；英雄静帧 %d 张（最大高 %d，要求 ≥1920）"
       % (cnt, minsz[0], minsz[1], len(hero), hero_h))

    # C14 台账/读数一致性
    ok("C14", "台账口径对齐：骨数/动作数/代理顶点数 与 rig_core 一致（可被外部复算）",
       len(CO["bones"]) == 19 and len(T["actions"]) == 6
       and CO["proxy_verts"] == px.get("weld", {}).get("verts_after"),
       "rig_core: 骨=%d 动作=%d 代理顶点=%d（报告焊接后=%d）trace 抽样顶点=%d"
       % (len(CO["bones"]), len(T["actions"]), CO["proxy_verts"],
          px.get("weld", {}).get("verts_after"), T["sample_vertex_count"]))
    return all(r["pass"] for r in R), R


def write_ledger(passed, rows, negs):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    RP = json.load(open(REPORT, encoding="utf-8"))
    T = json.load(open(TRACE, encoding="utf-8"))
    CO = json.load(open(CORE, encoding="utf-8"))
    H = T["height_units"]
    table = {a: {b: round(v["end_effectors"][b]["tail_cum_disp"] / H, 6) for b in END_BONES}
             for a, v in T["actions"].items()}
    avail_min = min(m["avail_mb"] for m in RP["memory"])
    led = {
        "schema": "digital-human-rig/1",
        "updated_at": now,
        "height_units": H,
        "height_basis": "身高 = 输入 GLB 的 AABB 高度（glTF Y 轴）= 0.98004 单位；Tripo 任意尺度，不套 cm；"
                        "一切阈值按身高百分比",
        "input": {"path": RP["input"]["path"], "bytes": RP["input"]["bytes"],
                  "header": RP["input"]["header"], "gltf_json": RP["input"]["gltf_json"],
                  "verdict": "静态网格：skins=None animations=None ⇒ 骨架/蒙皮/动画全部从零建"},
        "proxy": RP["proxy"],
        "memory": {"min_avail_mb": avail_min,
                   "min_avail_mb_across_session": 93.1,
                   "min_avail_mb_note": "本任务全程（多次 Blender 进程，含并行任务占用）实测最低空闲 93.1 MB；"
                                        "绑骨脚本自身采样器在本轮记录到的最低值见 min_avail_mb。"
                                        "两者都远低于 2.5GB 门限 ⇒ 全程走抽稀代理。",
                   "samples": RP["memory"], "decimated": True,
                   "full_precision_skin_run": False,
                   "full_precision_not_run_reason": "空闲物理内存最低实测 %.1f MB，不足跑全精度"
                                                    "(1956491 面)蒙皮+渲染；这是**因内存未跑**，不是做完了"
                                                    % avail_min},
        "skeleton": {"ready": True, "bone_count": RP["skeleton"]["bone_count"],
                     "hierarchy": RP["skeleton"]["hierarchy"], "bones": RP["skeleton"]["bones"],
                     "symmetry": {"pairs": RP["skeleton"]["symmetry"],
                                  "max_len_diff": RP["skeleton"]["max_len_diff"],
                                  "max_mirror_angle_deg": RP["skeleton"]["max_mirror_angle_deg"],
                                  "method": "只实测一侧（自然下垂那条臂 + 一侧腿）→ 镜像 ⇒ 对称由构造保证"}},
        "skinning": {"ready": True, "method": RP["skinning"]["method"],
                     "group_count": RP["skinning"]["group_count"],
                     "unweighted_verts": RP["skinning"]["unweighted_verts"],
                     "zero_cover_bones": RP["skinning"]["zero_cover_bones"],
                     "weight_params": RP["skinning"].get("weight_params"),
                     "weight_stats_before": RP["skinning"].get("weight_stats_before_smooth"),
                     "weight_stats_after": RP["skinning"].get("weight_stats_after_smooth"),
                     "bone_ownership": RP["skinning"].get("bone_ownership")},
        "actions": {"ready": True, "count": len(T["actions"]),
                    "defs": {a: {"frames": v["frames"], "desc": v["desc"]}
                             for a, v in T["actions"].items()},
                    "end_effector_cum_disp_ratio_of_H": table,
                    "thresholds": {"end_effector": 0.03, "squat_hip": 0.05, "foot_lift": 0.01},
                    "unit": "单位=身高(H)；数值为**路径积分累计位移 / H**"},
        "export": dict(RP["export"], ready=RP["export"]["animation_count"] >= 6),
        "render": {"ready": True, "engine_used": RP["render"].get("engine_used"),
                   "samples": RP["render"].get("samples"),
                   "resolution": RP["render"].get("resolution"),
                   "hero_resolution": RP["render"].get("hero"),
                   "color_management": RP["render"].get("color_management"),
                   "materials": RP["render"].get("materials"),
                   "lights_W": RP["render"].get("lights_W"),
                   "floor": RP["render"].get("floor"),
                   "total_files": RP["render"].get("total_files"),
                   "engine_note": "Cycles GPU(HIP) 实测不可用：Failed to load HIP kernel from kernel_gfx90c.fatbin.zst (Shared object initialization failed) ⇒ Cycles 只能 CPU"
                   "(实测 34.6 s/帧@1080x1350/128spp+降噪)；六段动作帧按主人「够看动作」口径走 "
                   "EEVEE_NEXT 256spp(5.9 s/帧)，英雄静帧走 Cycles CPU"},
        "criteria": {"all_green": bool(passed), "items": rows},
        "negative_controls": negs,
        "deviations": [
            "判据件路径：主人令点名 tools/codex-scripts/dh-rig-check.py，但该路径已被**并行任务**"
            "（页面侧 GBT-RIG-SPEC 机检）在 08:12 占用 ⇒ 本件改落 dh-rig-check-rig.py，不覆盖他人产物。",
            "打招呼：规格要求「抬右臂」，实测右臂几何被烘焙成「手扶头发」抬起姿势、与对称骨架的右臂骨不重合"
            "（bone_ownership 证据）⇒ 挥手改由**左臂**执行，右臂只给 ≤12° 安全小角。",
            "伸懒腰：右臂限幅 ≤14°（同上原因），左臂全举。",
        ],
        "known_limits": [
            "全精度蒙皮未跑（内存原因，见 memory 段）",
            "右臂：网格烘焙姿势与对称骨架不重合 ⇒ 该侧网格几何几乎不跟随右臂骨；右臂读数为**骨级**位移",
            "单材质网格 ⇒ 清漆/次表面只能在同一 BSDF 统一施加，无法按皮革/皮肤分部位",
            "旋转/位移读数在 Blender 空间（mesh 局部=世界）；glTF 导出经 Y-up 转换，轴向不同但距离不变",
        ],
        "artifacts": {
            "rigged_glb": {"path": GLB, "bytes": os.path.getsize(GLB)},
            "blend": {"path": os.path.join(OUT, "dh_rigged.blend"),
                      "bytes": os.path.getsize(os.path.join(OUT, "dh_rigged.blend"))
                      if os.path.exists(os.path.join(OUT, "dh_rigged.blend")) else 0},
            "trace": {"path": TRACE, "bytes": os.path.getsize(TRACE)},
            "report": {"path": REPORT, "bytes": os.path.getsize(REPORT)},
            "frames_dir": FRAMES,
            "rig_script": os.path.join(WS, "tools", "codex-scripts", "blender", "dh_rig.py"),
            "checker": SELF,
            "doc": os.path.join(WS, "docs", "数字人-绑骨与全肢体动作.md"),
        },
    }
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump(led, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n台账已写：%s (%d 字节)" % (LEDGER, os.path.getsize(LEDGER)))
    return led


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--probe", default="", choices=["", "bone-len", "frozen-frames", "lock-ends"])
    ap.add_argument("--write-ledger", action="store_true")
    a = ap.parse_args()
    if not a.check and not a.probe:
        a.check = True

    MUT = {"bone-len": {"bone_len": ("forearm", "L")},
           "frozen-frames": {"frozen": "03_走两步"},
           "lock-ends": {"lock_ends": "01_呼吸"}}
    if a.probe:
        print("\n########## 负对照：%s ##########" % a.probe)
        passed, rows = run_check(mut=MUT[a.probe])
        reds = [r["id"] + " " + r["name"] for r in rows if not r["pass"]]
        print("\n负对照 %s ⇒ %s" % (a.probe, "**已报红 ✓ 判据有效**" if not passed
                                    else "竟然报绿 ✗ 判据失效，返工"))
        print("报红条目：%s" % (reds or "无"))
        neg = {"probe": a.probe, "mutation": {k: str(v) for k, v in MUT[a.probe].items()},
               "expected_red": True, "observed_red": (not passed), "red_items": reds,
               "verdict": "判据有效" if not passed else "判据失效，需返工",
               "t": time.strftime("%Y-%m-%d %H:%M:%S")}
        p = os.path.join(OUT, "negctl_%s.json" % a.probe)
        json.dump(neg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("负对照记录：%s" % p)
        return 0 if not passed else 1

    passed, rows = run_check()
    print("\n" + "=" * 80)
    print("判据结果：%d/%d 通过 ⇒ %s" % (sum(1 for r in rows if r["pass"]), len(rows),
                                       "✅ 全绿" if passed else "❌ 有报红"))
    for r in rows:
        if not r["pass"]:
            print("   🔴 %s %s" % (r["id"], r["name"]))
    print("=" * 80)
    if a.write_ledger:
        negs = []
        for k in MUT:
            p = os.path.join(OUT, "negctl_%s.json" % k)
            if os.path.exists(p):
                negs.append(json.load(open(p, encoding="utf-8")))
        write_ledger(passed, rows, negs)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
