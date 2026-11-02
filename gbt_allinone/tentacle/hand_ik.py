# -*- coding: utf-8 -*-
"""hand_ik — 手指三连杆 box-constrained 数值 IK（无第三方依赖）。

为什么需要：
  hand_retarget 的几何法直接从骨段夹角读屈曲，快，但它是"量角器"，不是"追目标"。
  这里给每根手指一个平面 3-link FK，用坐标下降最小化 MCP/PIP/DIP/TIP 四个目标点的
  位置误差，并在关节限位内求解；输出关节角 + IK 残差 + 限位命中记录。

边界：
  - 每根手指用**手指平面**近似 3D；不是整手 21-DoF 全局 IK；
  - 不建模接触/力；不替代硬件闭环；
  - 无 scipy/numpy 依赖，纯 Python，可在 3.12 生产环境跑。
"""
from __future__ import annotations

import math

PI = math.pi


def _vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(v):
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _plane_basis(p, palm_forward=None):
    """手指平面：x=掌前向(腕→中指MCP，所有手指共用)，n=x×(TIP-MCP)，y=n×x。"""
    x = palm_forward or _norm(_vsub(p[9], p[0]))
    n = _norm(_cross(x, _vsub(p[4], p[1])))
    if abs(_dot(n, n)) < 1e-9:
        n = (0.0, 0.0, 1.0)
    y = _norm(_cross(n, x))
    return x, y


def _fk(a1, a2, a3, l1, l2, l3):
    """三连杆平面 FK，返回 (q2,q3,q4)，相对 MCP 原点；伸直时沿 +x。"""
    x2 = l1 * math.cos(a1); y2 = l1 * math.sin(a1)
    x3 = x2 + l2 * math.cos(a1 + a2); y3 = y2 + l2 * math.sin(a1 + a2)
    x4 = x3 + l3 * math.cos(a1 + a2 + a3); y4 = y3 + l3 * math.sin(a1 + a2 + a3)
    return (x2, y2), (x3, y3), (x4, y4)


def _loss(a, l1, l2, l3, t2, t3, t4):
    q2, q3, q4 = _fk(a[0], a[1], a[2], l1, l2, l3)
    return ((q2[0] - t2[0]) ** 2 + (q2[1] - t2[1]) ** 2 +
            (q3[0] - t3[0]) ** 2 + (q3[1] - t3[1]) ** 2 +
            (q4[0] - t4[0]) ** 2 + (q4[1] - t4[1]) ** 2)


def _solve_finger(p, limits, palm_forward=None, prior=None, smooth=0.0, sweeps=12, grid=25):
    """p=[wrist,MCP,PIP,DIP,TIP] 3D; limits=[(lo,hi)]*3；prior/smooth 为全手时序约束。"""
    x, y = _plane_basis(p, palm_forward)
    base = p[1]
    def proj(q):
        v = _vsub(q, base)
        return (_dot(v, x), _dot(v, y))
    t2, t3, t4 = proj(p[2]), proj(p[3]), proj(p[4])
    l1 = math.dist(p[1], p[2]); l2 = math.dist(p[2], p[3]); l3 = math.dist(p[3], p[4])
    if min(l1, l2, l3) < 1e-9:
        return None
    def score(a):
        s = _loss(a, l1, l2, l3, t2, t3, t4)
        if prior is not None and smooth:
            s += float(smooth) * sum((a[k] - prior[k]) ** 2 for k in range(3))
        return s
    # 初值：有时序先验则从先验起，否则由目标方向反解
    if prior is not None:
        a = [_clamp(prior[k], *limits[k]) for k in range(3)]
    else:
        a1 = math.atan2(t2[1], t2[0]) if (abs(t2[0]) + abs(t2[1])) > 1e-9 else 0.0
        d2 = (t3[0] - t2[0], t3[1] - t2[1])
        d3 = (t4[0] - t3[0], t4[1] - t3[1])
        a2 = math.atan2(d2[1], d2[0]) - a1
        a3 = math.atan2(d3[1], d3[0]) - (a1 + a2)
        a = [_clamp(a1, *limits[0]), _clamp(a2, *limits[1]), _clamp(a3, *limits[2])]
    best = score(a)
    hits = []
    for _ in range(sweeps):
        for k in range(3):
            lo, hi = limits[k]
            cand = [lo + (hi - lo) * j / (grid - 1) for j in range(grid)]
            local_best, local_val = a[k], best
            for c in cand:
                trial = a[:]
                trial[k] = c
                v = score(trial)
                if v < local_val:
                    local_best, local_val = c, v
            a[k] = local_best
            best = local_val
            if abs(a[k] - limits[k][0]) < 1e-9 or abs(a[k] - limits[k][1]) < 1e-9:
                hits.append(k)
    q2, q3, q4 = _fk(a[0], a[1], a[2], l1, l2, l3)
    rms = math.sqrt(_loss(a, l1, l2, l3, t2, t3, t4) / 6.0)
    return {"angles": a, "rms_m": rms, "limit_hits": sorted(set(hits)),
            "targets": [t2, t3, t4], "fk": [q2, q3, q4]}


def solve(landmarks, model, hand="right", prev=None, smooth=0.0):
    """对模型内每根手指做 IK；prev/smooth 为全手时序约束；返回 {joints, ik, warnings}。"""
    if not isinstance(landmarks, (list, tuple)) or len(landmarks) != 21:
        return {"ok": False, "status": "user_error", "error": "需要 21 个 landmarks"}
    p = [tuple(float(x) for x in pt[:3]) for pt in landmarks]
    joints, per, warnings = {}, {}, []
    sign = 1.0 if str(hand).lower() != "left" else -1.0
    palm_forward = _norm(_vsub(p[9], p[0]))
    for finger in model.get("fingers") or []:
        fname = finger.get("name", "?")
        chain = finger.get("chain") or []
        if len(chain) < 5:
            warnings.append("%s 链不足 5 点，跳过 IK" % fname)
            continue
        pts = [p[i] for i in chain[:5]]
        # 关节名/限位：按模型 joints 顺序取 mcp/pip/dip
        jl = [j for j in (finger.get("joints") or []) if j.get("kind") == "flex"]
        limits = []
        for j in jl[:3]:
            lim = j.get("limit") or [0.0, PI]
            limits.append((float(lim[0]), float(lim[1])))
        while len(limits) < 3:
            limits.append((0.0, PI))
        prior = None
        if isinstance(prev, dict) and all(j.get("name") in prev for j in jl[:3]):
            prior = [float(prev[j.get("name")]) for j in jl[:3]]
        r = _solve_finger(pts, limits, palm_forward, prior=prior, smooth=smooth)
        if not r:
            warnings.append("%s 骨段≈0，跳过 IK" % fname)
            continue
        for j, ang in zip(jl[:3], r["angles"]):
            joints[j.get("name")] = round(ang * float(j.get("sign", 1.0)) + float(j.get("offset", 0.0)), 6)
        per[fname] = {"rms_m": round(r["rms_m"], 6), "limit_hits": r["limit_hits"],
                      "smooth": bool(prior and smooth)}
    # 外展沿用 hand_retarget 的几何解
    from . import hand_retarget as HR
    geo = HR.run("retarget", landmarks=landmarks, model=model, hand=hand, unit="rad")
    for k, v in (geo.get("joints") or {}).items():
        if k.endswith("_abd"):
            joints[k] = v
    return {"ok": bool(joints), "joints": joints, "ik": per,
            "warnings": warnings, "hand": hand, "smooth": float(smooth),
            "source": "planar-box-constrained-ik" + ("+temporal" if smooth else "")}

