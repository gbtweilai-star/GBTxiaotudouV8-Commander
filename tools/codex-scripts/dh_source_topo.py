# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""源 GLB 拓扑体检：手上的壳和髋上的壳在**原始网格**里就连着吗？

目的：判断"左臂下垂时手/前臂贴在髋上"这条**桥**是
  (a) 源网格本来就这样（Tripo 把两张面缝成一张），还是
  (b) 我方管线里 remove_doubles(0.0006) 焊接出来的。
读数口径全部写进 JSON，可复算。

用法： py -3.14 tools/codex-scripts/dh_source_topo.py
"""
import json
import math
import os
import struct
import sys

import numpy as np

WS = _GBT_ROOT
SRC = os.path.join(os.path.expanduser("~"), "Downloads", "futuristic cosplay outfit 3d model.glb")
REPORT = os.path.join(WS, "projects", "digital-human", "out", "rig_report.json")
OUT = os.path.join(WS, ".scratch", "dh_source_topo.json")

CT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def main():
    raw = open(SRC, "rb").read()
    jl = struct.unpack_from("<I", raw, 12)[0]
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl = struct.unpack_from("<I", raw, off)[0]
    BIN = raw[off + 8:off + 8 + bl]
    del raw
    pr = J["meshes"][0]["primitives"][0]

    def read_acc(i):
        a = J["accessors"][i]
        bv = J["bufferViews"][a["bufferView"]]
        fmt, sz = CT[a["componentType"]]
        n = NC[a["type"]]
        base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        arr = np.frombuffer(BIN, dtype=np.dtype("<" + fmt), count=a["count"] * n, offset=base)
        return arr.reshape(a["count"], n)

    P = read_acc(pr["attributes"]["POSITION"]).astype(np.float64)   # glTF Y-up
    I = read_acc(pr["indices"]).astype(np.int64).ravel()
    print("[topo] 源网格 verts=%d tris=%d" % (len(P), len(I) // 3))
    # glTF → Blender: X=x, Y=-z, Z=y
    co = np.stack([P[:, 0], -P[:, 2], P[:, 1]], axis=1)
    del P
    T = I.reshape(-1, 3)
    del I

    RP = json.load(open(REPORT, encoding="utf-8"))
    bones = {b["name"]: (np.array(b["head"], dtype=np.float64), np.array(b["tail"], dtype=np.float64))
             for b in RP["skeleton"]["bones"]}
    H = float(RP["landmarks"]["height_units"])
    cx = float(RP["landmarks"]["axis_lat"])
    cd = float(RP["landmarks"]["axis_dep"])
    R_ENV = {"hips": 0.068, "spine": 0.050, "chest": 0.055, "neck": 0.025, "head": 0.060,
             "shoulder": 0.025, "upper_arm": 0.030, "forearm": 0.024, "hand": 0.024,
             "thigh": 0.028, "shin": 0.029, "foot": 0.022}

    # ---- 逐顶点：按"归一化距离最小"的标准包络判定归属（与绑骨脚本同口径，不用权重） ----
    names, heads, tails, rads = [], [], [], []
    for n, (h, t) in bones.items():
        names.append(n); heads.append(h); tails.append(t)
        rads.append(R_ENV.get(n.split("_")[0], 0.03) * H)
    dom = np.full(len(co), -1, dtype=np.int32)
    dmin = np.full(len(co), 1e9)
    for j, n in enumerate(names):
        ab = tails[j] - heads[j]
        L2 = float(ab @ ab) or 1e-12
        wv = np.clip(((co - heads[j]) @ ab) / L2, 0.0, 1.0)
        d = np.linalg.norm(co - (heads[j] + wv[:, None] * ab), axis=1) / rads[j]
        uu = co[:, 0] - cx
        sgn = -1.0 if n.endswith("_R") else (1.0 if n.endswith("_L") else 0.0)
        if sgn != 0:
            wrong = (np.sign(uu) * sgn) < 0
            f = np.clip(0.30 + 0.70 * np.clip(np.abs(uu) / (0.09 * H), 0.0, 1.0), 0.30, 1.0)
            d = d / np.where(wrong, f, 1.0)
        upd = d < dmin
        dom[upd] = j
        dmin[upd] = d[upd]
    del dmin

    ARM_L = {"hand_L", "forearm_L"}
    ARM_R = {"hand_R", "forearm_R"}
    TORSO = {"hips", "spine", "chest", "neck", "head", "thigh_L", "thigh_R"}
    grp = {}
    for j, n in enumerate(names):
        grp[j] = ("armL" if n in ARM_L else "armR" if n in ARM_R else
                  "torso" if n in TORSO else "limb")
    glab = np.array([{"armL": 1, "armR": 2, "torso": 3, "limb": 4}[grp[int(j)]] for j in dom],
                    dtype=np.int8)

    # ---- 边的跨区统计（源网格；不 uniquify） ----
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]], axis=0)
    a0, a1 = glab[e[:, 0]], glab[e[:, 1]]
    length = np.linalg.norm(co[e[:, 0]] - co[e[:, 1]], axis=1)
    res = {"verts": int(len(co)), "tris": int(len(T)), "H": H,
           "region_vertex_counts": {}, "cross_edges": {}, "cross_edge_len": {}}
    for k, v in (("armL(hand/forearm_L)", 1), ("armR(hand/forearm_R)", 2),
                 ("torso(hips/spine/chest/head/thigh)", 3)):
        res["region_vertex_counts"][k] = int((glab == v).sum())
    pairs = [("armL", "torso", 1, 3), ("armR", "torso", 2, 3), ("armL", "armR", 1, 2)]
    for n0, n1, g0, g1 in pairs:
        m = ((a0 == g0) & (a1 == g1)) | ((a0 == g1) & (a1 == g0))
        n = int(m.sum())
        res["cross_edges"]["%s<->%s" % (n0, n1)] = n
        if n:
            L = length[m]
            res["cross_edge_len"]["%s<->%s" % (n0, n1)] = {
                "min": round(float(L.min()), 6), "median": round(float(np.median(L)), 6),
                "max": round(float(L.max()), 6),
                "n_lt_0.0008": int((L < 0.0008).sum()),
                "n_lt_0.002": int((L < 0.002).sum()),
                "n_ge_0.005": int((L >= 0.005).sum())}
        print("[topo] 跨区边 %-10s <-> %-10s : %d 条%s" % (n0, n1, n,
              ("  长度 min=%.6f 中位=%.6f max=%.6f (其中 <0.0008 的 %d 条)"
               % (res["cross_edge_len"]["%s<->%s" % (n0, n1)]["min"],
                  res["cross_edge_len"]["%s<->%s" % (n0, n1)]["median"],
                  res["cross_edge_len"]["%s<->%s" % (n0, n1)]["max"],
                  res["cross_edge_len"]["%s<->%s" % (n0, n1)]["n_lt_0.0008"])) if n else ""))

    # ---- 连通分量（在源网格上；分片汤会有很多块） ----
    try:
        import scipy.sparse as sp
        import scipy.sparse.csgraph as csg
        w = np.ones(len(e))
        A = sp.coo_matrix((w, (e[:, 0], e[:, 1])), shape=(len(co),) * 2).tocsr()
        ncomp, lab = csg.connected_components((A + A.T).tocsr(), directed=False)
        sizes = np.bincount(lab)
        top = sorted([int(x) for x in sizes], reverse=True)[:10]
        res["components"] = {"n": int(ncomp), "top10": top,
                             "largest_ratio": round(float(sizes.max()) / len(co), 5)}
        print("[topo] 连通分量=%d 最大块=%d (%.2f%%) top10=%s"
              % (ncomp, sizes.max(), 100.0 * sizes.max() / len(co), top))
        # 最大块里有多少 armL / torso 顶点（=手和髋是否在同一块里）
        big = int(np.argmax(sizes))
        inbig = lab == big
        res["largest_comp_regions"] = {
            "armL": int(((glab == 1) & inbig).sum()), "armR": int(((glab == 2) & inbig).sum()),
            "torso": int(((glab == 3) & inbig).sum())}
        print("[topo] 最大块内 armL=%d armR=%d torso=%d（源网格 %d 顶点里）"
              % (res["largest_comp_regions"]["armL"], res["largest_comp_regions"]["armR"],
                 res["largest_comp_regions"]["torso"], len(co)))
        del A, lab
    except Exception as ex:
        res["components"] = {"error": repr(ex)}
        print("[topo] 分量计算失败 %r" % (ex,))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[topo] 落盘 " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
