# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[3])
"""② 「大帆」区权重实况（**只读**，不改 blend）

回答四件事，全部给数字：
  1) 帆区顶点（02_打招呼 f21 上被拉长 >4× 的边端点）的权重实况：第一/第二影响骨、权重和、
     影响数、以及**跨区面片**（一个三角面两端挂在差异极大的两根骨上）有多少、在哪。
  2) 权重硬跳变：逐边算 ‖w_v0 − w_v1‖₁/2（总变差），给分布与最坏 20 条（静置位置+骨对）。
  3) 与"非帆区"基线对比（权重和 / 影响数 / 跳变），证明不是全局问题而是局部病灶。
  4) 边界处的衰减形状：hand_L 域 → thigh_L/hips 域过渡带上的代表性顶点逐点权重表。

用法： blender.exe --background --python tools/codex-scripts/blender/dh_sail_weights.py -- \
          --action 02_打招呼 --frame 21 --out .scratch/dh_sail_weights.json
"""
import argparse
import json
import math
import os
import sys

WS = _GBT_ROOT
LIMB_GROUP = {"hips": "torso", "spine": "torso", "chest": "torso", "neck": "torso", "head": "torso",
              "shoulder_L": "armL", "upper_arm_L": "armL", "forearm_L": "armL", "hand_L": "armL",
              "shoulder_R": "armR", "upper_arm_R": "armR", "forearm_R": "armR", "hand_R": "armR",
              "thigh_L": "legL", "shin_L": "legL", "foot_L": "legL",
              "thigh_R": "legR", "shin_R": "legR", "foot_R": "legR"}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(WS, "projects", "digital-human", "out",
                                                    "dh_rigged.blend"))
    ap.add_argument("--action", default="02_打招呼")
    ap.add_argument("--frame", type=int, default=21)
    ap.add_argument("--ratio", type=float, default=4.0)
    ap.add_argument("--out", default=os.path.join(WS, ".scratch", "dh_sail_weights.json"))
    return ap.parse_args(argv)


def main():
    a = parse_args()
    import bpy
    import numpy as np

    bpy.ops.wm.open_mainfile(filepath=a.blend)
    scn = bpy.context.scene
    mesh_obj = bpy.data.objects["DH_Body"]
    arm_obj = bpy.data.objects["DH_Armature"]
    me = mesh_obj.data
    nv = len(me.vertices)
    co = np.empty(nv * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    core = json.load(open(os.path.join(os.path.dirname(a.blend), "rig_core.json"), encoding="utf-8"))
    H = float(core["H"]); cx = float(core["cx"]); z0 = float(core["aabb_min"][2])
    bones = list(core["bones"]); bi = {n: i for i, n in enumerate(bones)}
    NB = len(bones)

    W = np.zeros((nv, NB))
    gidx = {g.index: i for i, g in enumerate(mesh_obj.vertex_groups)}
    for v in me.vertices:
        for g in v.groups:
            j = gidx.get(g.group)
            if j is not None:
                W[v.index, j] = g.weight
    wsum = W.sum(axis=1)
    ninf = (W > 1e-6).sum(axis=1)
    order = np.argsort(-W, axis=1)
    dom = order[:, 0]
    dom2 = order[:, 1]
    domw = W[np.arange(nv), dom]
    gdom = np.array([{"torso": 0, "armL": 1, "armR": 2, "legL": 3, "legR": 4}[LIMB_GROUP[n]]
                     for n in bones])

    ev = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    L0 = np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1)
    jump = 0.5 * np.abs(W[ev[:, 0]] - W[ev[:, 1]]).sum(axis=1)     # 总变差 ∈[0,1]

    # ---- 帆区顶点：该帧被拉长 >ratio 的边端点 ----
    arm_obj.animation_data.action = bpy.data.actions.get(a.action)
    scn.frame_set(a.frame)
    dg = bpy.context.evaluated_depsgraph_get()
    mev = mesh_obj.evaluated_get(dg).to_mesh()
    arr = np.empty(len(mev.vertices) * 3, dtype=np.float64)
    mev.vertices.foreach_get("co", arr)
    P = arr.reshape(-1, 3).copy()
    mesh_obj.evaluated_get(dg).to_mesh_clear()
    dl = np.linalg.norm(P[ev[:, 0]] - P[ev[:, 1]], axis=1)
    ratio = dl / np.maximum(L0, 1e-12)
    m = ratio > a.ratio
    sail_v = np.unique(np.concatenate([ev[m, 0], ev[m, 1]])) if m.any() else np.array([], dtype=int)
    sail_mask = np.zeros(nv, dtype=bool); sail_mask[sail_v] = True
    disp = np.linalg.norm(P - co, axis=1)

    def stats(mask, tag):
        if not mask.any():
            return {}
        return {"n": int(mask.sum()),
                "wsum_min": round(float(wsum[mask].min()), 6),
                "wsum_median": round(float(np.median(wsum[mask])), 6),
                "wsum_max": round(float(wsum[mask].max()), 6),
                "n_wsum_below_0.999": int((wsum[mask] < 0.999).sum()),
                "influences_max": int(ninf[mask].max()),
                "influences_mean": round(float(ninf[mask].mean()), 3),
                "dom_hist": {bones[j]: int((dom[mask] == j).sum()) for j in np.argsort(
                    [-int((dom[mask] == j).sum()) for j in range(NB)])[:8]
                    if (dom[mask] == j).any()},
                "domw_mean": round(float(domw[mask].mean()), 4),
                "disp_mean": round(float(disp[mask].mean()), 5)}

    res = {"blend": a.blend, "action": a.action, "frame": a.frame, "ratio_threshold": a.ratio,
           "H": H, "verts": nv,
           "sail": stats(sail_mask, "sail"), "baseline_all": stats(np.ones(nv, dtype=bool), "all"),
           "baseline_nonsail": stats(~sail_mask, "rest")}

    # ---- 跨区面片（三角面两端挂差异极大的骨）----
    me.calc_loop_triangles()
    lt = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", lt)
    lt = lt.reshape(-1, 3)
    g0, g1, g2 = gdom[dom[lt[:, 0]]], gdom[dom[lt[:, 1]]], gdom[dom[lt[:, 2]]]
    span = (g0 != g1) | (g1 != g2) | (g0 != g2)
    armL_vs_torso = (((g0 == 1) | (g1 == 1) | (g2 == 1)) & ((g0 == 0) | (g1 == 0) | (g2 == 0)))
    armR_vs_torso = (((g0 == 2) | (g1 == 2) | (g2 == 2)) & ((g0 == 0) | (g1 == 0) | (g2 == 0)))
    lowm = (co[lt].mean(axis=1)[:, 2] < z0 + 0.62 * H)
    res["cross_region_faces"] = {
        "faces_total": int(len(lt)),
        "faces_span_two_limb_groups": int(span.sum()),
        "armL<->torso_ALL": int(armL_vs_torso.sum()),
        "armL<->torso_below_0.62H": int((armL_vs_torso & lowm).sum()),
        "armR<->torso_ALL": int(armR_vs_torso.sum()),
        "armR<->torso_below_0.62H": int((armR_vs_torso & lowm).sum())}
    print("[w] 跨区面片（一个三角面两端分属不同肢体组）：")
    for k, v in res["cross_region_faces"].items():
        print("      %-28s %d" % (k, v))

    # ---- 权重硬跳变分布 ----
    qs = [50, 90, 99, 99.9, 100]
    res["weight_jump"] = {"edges": int(len(ev)),
                          "percentiles": {("p%s" % q): round(float(np.percentile(jump, q)), 4) for q in qs},
                          "n_gt_0.5": int((jump > 0.5).sum()), "n_gt_0.9": int((jump > 0.9).sum())}
    print("[w] 逐边权重总变差(0=两端同骨权, 1=完全不同的骨)：%s  >0.5 的边=%d  >0.9 的边=%d"
          % (res["weight_jump"]["percentiles"], res["weight_jump"]["n_gt_0.5"],
             res["weight_jump"]["n_gt_0.9"]))

    # ---- 最坏跳变边明细（只挑静置在 z<0.62H 的）----
    idx = np.where((jump > 0.5) & (co[ev].mean(axis=1)[:, 2] < z0 + 0.62 * H))[0]
    idx = idx[np.argsort(-jump[idx])][:20]
    worst = []
    for e in idx:
        i0, i1 = int(ev[e, 0]), int(ev[e, 1])
        worst.append({"edge": int(e), "jump": round(float(jump[e]), 4),
                      "rest_len": round(float(L0[e]), 6),
                      "p0": [round(float(x), 5) for x in co[i0]],
                      "p1": [round(float(x), 5) for x in co[i1]],
                      "dom0": bones[int(dom[i0])], "dom1": bones[int(dom[i1])],
                      "w0": [[bones[j], round(float(W[i0, j]), 4)] for j in order[i0][:3]
                             if W[i0, j] > 1e-4],
                      "w1": [[bones[j], round(float(W[i1, j]), 4)] for j in order[i1][:3]
                             if W[i1, j] > 1e-4]})
    res["worst_jump_edges_below_0.62H"] = worst
    print("[w] 静置 z<0.62H 上跳变最坏的边（前 8）：")
    for r in worst[:8]:
        print("      jump=%.3f 静置长=%.5f %s w=%s | %s w=%s"
              % (r["jump"], r["rest_len"], r["dom0"], r["w0"], r["dom1"], r["w1"]))

    # ---- 边界衰减形状：hand_L 与 thigh_L/hips 交界带逐点权重 ----
    band = ((co[:, 0] - cx > 0.100) & (co[:, 0] - cx < 0.135) & (co[:, 2] > z0 + 0.33 * H)
            & (co[:, 2] < z0 + 0.45 * H))
    ids = np.where(band)[0]
    ids = ids[np.argsort(co[ids, 2])]
    tbl = []
    for vi in ids[::max(1, len(ids) // 14)][:14]:
        tbl.append({"v": int(vi), "z": round(float(co[vi, 2]), 5), "u": round(float(co[vi, 0] - cx), 5),
                    "y": round(float(co[vi, 1]), 5),
                    "dom": bones[int(dom[vi])], "dom2": bones[int(dom2[vi])],
                    "domw": round(float(domw[vi]), 4), "dom2w": round(float(W[vi, dom2[vi]]), 4),
                    "ninf": int(ninf[vi]), "wsum": round(float(wsum[vi]), 5),
                    "jump_max_incident": round(float(jump[(ev[:, 0] == vi) | (ev[:, 1] == vi)].max())
                                               if ((ev[:, 0] == vi) | (ev[:, 1] == vi)).any() else 0.0, 4)})
    res["handhip_band_profile"] = tbl
    print("[w] 手↔髋交界带（u=0.100~0.135H, z=0.33~0.45H）逐点权重（按高度序，抽样 14 点）：")
    for r in tbl:
        print("      v%-6d z=%.4f u=%+.4f y=%+.4f  dom=%-11s %.3f / %-11s %.3f  影响=%d 和=%.4f 该点最大跳变=%.3f"
              % (r["v"], r["z"], r["u"], r["y"], r["dom"], r["domw"], r["dom2"], r["dom2w"],
                 r["ninf"], r["wsum"], r["jump_max_incident"]))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[w] 落盘 " + a.out)
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 1
    sys.exit(rc)
