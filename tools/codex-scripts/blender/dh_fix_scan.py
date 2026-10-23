# -*- coding: utf-8 -*-
"""数字人 · 大帆/撕裂/浮片 —— 逐动作**定位**工具（第二轮：网格修复）

目的：不猜"哪里撕了"，而是量出来：
  · 哪些**边**在动作中被拉长（比值 / 绝对拉伸量），它们静置时在哪、动起来到哪；
  · 这些边的两端顶点分别受哪根骨驱动 ⇒ **骨对**归因（谁和谁被硬拽在一起）；
  · 拉长边的静置位置分布（z 分桶 × 横向 u 分桶）⇒ 是"髋-臂桥"还是"髋-腿缝"。
  · 每帧一个"撕裂度"仪表：边长比 >4 / >10 / >50 的边数、最大比值、总超长量、面积比。

用法：
  "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe" --background \
     --python tools/codex-scripts/blender/dh_fix_scan.py -- \
     --blend projects/digital-human/out/dh_rigged.blend \
     --actions 02_打招呼,04_转身 --frames 11,21,32 --out .scratch/dh_scan.json

🔴 只读：本工具**不改** blend / 不写 blend，只输出 JSON + stdout。
"""
import argparse
import json
import math
import os
import sys
import time

WS = r"C:\Users\ADMIN\Desktop\GBT小土豆V8"


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(WS, "projects", "digital-human", "out",
                                                    "dh_rigged.blend"))
    ap.add_argument("--actions", default="02_打招呼,04_转身,05_蹲起,06_伸懒腰")
    ap.add_argument("--frames", default="11,21,32")
    ap.add_argument("--out", default=os.path.join(WS, ".scratch", "dh_scan.json"))
    ap.add_argument("--top", type=int, default=12, help="每组打印多少条最坏边")
    ap.add_argument("--radius-near", type=float, default=0.002, help="近邻半径(单位=模型单位)")
    return ap.parse_args(argv)


def main():
    a = parse_args()
    import bpy
    import numpy as np
    from mathutils import Vector

    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    scn = bpy.context.scene
    mesh_obj = bpy.data.objects["DH_Body"]
    arm_obj = bpy.data.objects["DH_Armature"]
    me = mesh_obj.data
    nv = len(me.vertices)
    co = np.empty(nv * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    H = float(co[:, 2].max() - co[:, 2].min())
    cx = 0.00835   # 由 rig_core 读，见下
    cd = 0.002849
    core_p = os.path.join(os.path.dirname(a.blend), "rig_core.json")
    if os.path.exists(core_p):
        core = json.load(open(core_p, encoding="utf-8"))
        H = float(core["H"]); cx = float(core["cx"]); cd = float(core["cd"])
        all_bones = list(core["bones"])
    else:
        all_bones = [g.name for g in mesh_obj.vertex_groups]
    z0 = float(co[:, 2].min())
    bi = {n: i for i, n in enumerate(all_bones)}
    NB = len(all_bones)

    # ---- 权重（稠密，85977×19 = 1.6M float，可承受） ----
    W = np.zeros((nv, NB), dtype=np.float64)
    gidx = {g.index: i for i, g in enumerate(mesh_obj.vertex_groups)}
    for v in me.vertices:
        for g in v.groups:
            j = gidx.get(g.group)
            if j is not None:
                W[v.index, j] = g.weight
    rs = W.sum(axis=1)
    dom = np.argmax(W, axis=1)
    domw = W[np.arange(nv), dom]

    # ---- 边 ----
    ne = len(me.edges)
    ev = np.empty(ne * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(ne, 2)
    L0 = np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1)

    def samp():
        dg = bpy.context.evaluated_depsgraph_get()
        mev = mesh_obj.evaluated_get(dg).to_mesh()
        arr = np.empty(len(mev.vertices) * 3, dtype=np.float64)
        mev.vertices.foreach_get("co", arr)
        out = arr.reshape(-1, 3).copy()
        mesh_obj.evaluated_get(dg).to_mesh_clear()
        return out

    def face_area(P):
        """三角面面积和（mesh 是 collapse 三角化 ⇒ 全三角）"""
        lp = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", lp)
        lp = lp.reshape(-1, 3)
        v0, v1, v2 = P[lp[:, 0]], P[lp[:, 1]], P[lp[:, 2]]
        return 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)

    me.calc_loop_triangles()
    A0 = face_area(co)
    A0_tot = float(A0.sum())

    out = {"blend": a.blend, "H": H, "cx": cx, "cd": cd, "verts": nv, "edges": ne,
           "faces": int(len(me.loop_triangles)),
           "aabb_z0": z0, "bone_list": all_bones,
           "rest": {"edge_len_mean": float(L0.mean()), "edge_len_median": float(np.median(L0)),
                    "edge_len_min": float(L0.min()), "edge_len_max": float(L0.max()),
                    "edges_lt_0.0008": int((L0 < 0.0008).sum()),
                    "edges_lt_0.002": int((L0 < 0.002).sum()),
                    "area_total": A0_tot},
           "frames": {}}

    frames = [int(x) for x in a.frames.split(",") if x.strip()]
    acts = [x.strip() for x in a.actions.split(",") if x.strip()]
    for aname in acts:
        act = bpy.data.actions.get(aname)
        if act is None:
            print("[scan] 缺动作 " + aname)
            continue
        arm_obj.animation_data.action = act
        for f in frames:
            scn.frame_set(f)
            P = samp()
            dl = np.linalg.norm(P[ev[:, 0]] - P[ev[:, 1]], axis=1)
            ratio = dl / np.maximum(L0, 1e-12)
            excess = np.maximum(0.0, dl - 2.0 * L0)
            disp = np.linalg.norm(P - co, axis=1)
            A1 = face_area(P)

            m4 = ratio > 4.0
            m10 = ratio > 10.0
            m50 = ratio > 50.0
            # ---- 骨对归因：对 ratio>4 的边，把"超长量"记到两端主导骨对上 ----
            pair = {}
            near = {}
            if m4.any():
                idx = np.where(m4)[0]
                v0 = ev[idx, 0]; v1 = ev[idx, 1]
                ex = excess[idx]
                for k in range(len(idx)):
                    d0 = all_bones[int(dom[v0[k]])]
                    d1 = all_bones[int(dom[v1[k]])]
                    key = "|".join(sorted([d0, d1]))
                    r = pair.setdefault(key, {"n": 0, "excess": 0.0, "max_ratio": 0.0,
                                              "rest_len_mean": 0.0})
                    r["n"] += 1
                    r["excess"] += float(ex[k])
                    r["max_ratio"] = max(r["max_ratio"], float(ratio[idx[k]]))
                    r["rest_len_mean"] += float(L0[idx[k]])
                for k in pair:
                    if pair[k]["n"]:
                        pair[k]["rest_len_mean"] = round(pair[k]["rest_len_mean"] / pair[k]["n"], 6)
                        pair[k]["excess"] = round(pair[k]["excess"], 5)
                        pair[k]["max_ratio"] = round(pair[k]["max_ratio"], 2)

            # ---- 静置位置分布（z 桶 0.05H × u 桶 0.025H），只统计 m10 ----
            buckets = {}
            if m10.any():
                idx = np.where(m10)[0]
                vv = np.unique(np.concatenate([ev[idx, 0], ev[idx, 1]]))
                for vi in vv:
                    zb = int(math.floor((co[vi, 2] - z0) / (0.05 * H)))
                    ub = int(math.floor((co[vi, 0] - cx) / (0.025 * H)))
                    key = "z%02d_u%+03d" % (zb, ub)
                    r = buckets.setdefault(key, {"n": 0, "disp_max": 0.0, "bone_hist": {}})
                    r["n"] += 1
                    r["disp_max"] = max(r["disp_max"], float(disp[vi]))
                    bn = all_bones[int(dom[vi])]
                    r["bone_hist"][bn] = r["bone_hist"].get(bn, 0) + 1
                for k in buckets:
                    buckets[k]["disp_max"] = round(buckets[k]["disp_max"], 5)

            # ---- 最坏边明细 ----
            top = []
            if m4.any():
                idx = np.where(m4)[0]
                order = idx[np.argsort(-excess[idx])][:a.top]
                for e in order:
                    i0, i1 = int(ev[e, 0]), int(ev[e, 1])
                    top.append({
                        "edge": int(e), "v0": i0, "v1": i1,
                        "rest_len": round(float(L0[e]), 8),
                        "def_len": round(float(dl[e]), 6),
                        "ratio": round(float(ratio[e]), 2),
                        "rest_p0": [round(float(x), 5) for x in co[i0]],
                        "rest_p1": [round(float(x), 5) for x in co[i1]],
                        "def_p0": [round(float(x), 5) for x in P[i0]],
                        "def_p1": [round(float(x), 5) for x in P[i1]],
                        "w0": [[all_bones[j], round(float(W[i0, j]), 4)] for j in np.argsort(-W[i0])[:3]
                               if W[i0, j] > 1e-4],
                        "w1": [[all_bones[j], round(float(W[i1, j]), 4)] for j in np.argsort(-W[i1])[:3]
                               if W[i1, j] > 1e-4]})

            n_chain = 0
            if m4.any():
                # 被拉长的边里有几条是"静置时几乎重合"(<0.0008=焊接门) ⇒ 焊接桥
                n_chain = int((L0[np.where(m4)[0]] < 0.0008).sum())
            out["frames"]["%s@%d" % (aname, f)] = {
                "action": aname, "frame": f,
                "edge_ratio_gt4": int(m4.sum()), "edge_ratio_gt10": int(m10.sum()),
                "edge_ratio_gt50": int(m50.sum()),
                "max_ratio": round(float(ratio.max()), 2),
                "max_def_len": round(float(dl.max()), 5),
                "excess_total": round(float(excess.sum()), 5),
                "edges_gt4_from_weld_bridge": n_chain,
                "area_def_over_rest": round(float(A1.sum()) / max(1e-12, A0_tot), 5),
                "verts_disp_gt_0_1H": int((disp > 0.1 * H).sum()),
                "disp_max": round(float(disp.max()), 5),
                "bone_pairs": dict(sorted(pair.items(), key=lambda kv: -kv[1]["excess"])[:8]),
                "rest_buckets": dict(sorted(buckets.items(), key=lambda kv: -kv[1]["n"])[:10]),
                "worst_edges": top}
            # log
            print("[scan] %-10s f%-3d  >4:%6d >10:%5d >50:%5d  max=%.0fx (%.4f)  "
                  "超长合计=%.4f  面积比=%.4f  位移>0.1H 顶点=%d"
                  % (aname, f, m4.sum(), m10.sum(), m50.sum(), ratio.max(), dl.max(),
                     excess.sum(), A1.sum() / A0_tot, int((disp > 0.1 * H).sum())))
            for k, v in list(out["frames"]["%s@%d" % (aname, f)]["bone_pairs"].items())[:5]:
                print("       骨对 %-28s 边数=%-6d 超长=%.4f 最大比值=%.1fx 静置边长均值=%.6f"
                      % (k, v["n"], v["excess"], v["max_ratio"], v["rest_len_mean"]))
            print("       静置热点: " + "  ".join(
                ["%s n=%d disp=%.3f top=%s" % (k, v["n"], v["disp_max"],
                                               sorted(v["bone_hist"].items(), key=lambda kv: -kv[1])[:3])
                 for k, v in list(out["frames"]["%s@%d" % (aname, f)]["rest_buckets"].items())[:4]]))
            for te in top[:3]:
                print("       边#%d 静置长=%.6f → 形变长=%.4f (%.0fx)  %s→%s | %s→%s | w0=%s w1=%s"
                      % (te["edge"], te["rest_len"], te["def_len"], te["ratio"],
                         te["rest_p0"], te["rest_p1"], te["def_p0"], te["def_p1"], te["w0"], te["w1"]))

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[scan] 落盘 %s (%d 字节, %.1fs)" % (a.out, os.path.getsize(a.out), time.time() - t0))
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 1
    sys.exit(rc)
