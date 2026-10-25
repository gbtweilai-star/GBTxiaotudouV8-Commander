# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""源 GLB 拓扑体检 · 第二轮：**手贴髋**那一处到底是"同一张面"还是"两张面贴在一起"。

在 v1 代理网格上量到的最坏"帆边"静置端点（去重后的重灾区，见 dh_scan_*.json）：
   A = (0.12676, -0.01322, 0.38034)  权重 hand_L 0.795 / thigh_L 0.205
   B = (0.12675, -0.01284, 0.36968)  权重 thigh_L 0.817 / hand_L 0.183
   C = (0.12615, -0.01786, 0.36544)  权重 thigh_L 0.849 / hand_L 0.151
本脚本回到**源网格**看这三处：
   · 附近有哪些顶点（阈值内），它们属于哪个连通分量；
   · 这些分量各自覆盖哪些身体区域（细标签）；
   · 若 A/B/C 附近只有**一个**分量 ⇒ 源网格本来就是一张连续面（手与腿焊在一起）；
     若有两个分量分别来自手臂侧与腿侧 ⇒ 是"两张面贴在一起"，帆是焊接/抽稀造成的。

用法： py -3.14 tools/codex-scripts/dh_source_probe.py
"""
import json
import os
import struct
import sys

import numpy as np

WS = _GBT_ROOT
SRC = os.path.join(os.path.expanduser("~"), "Downloads", "futuristic cosplay outfit 3d model.glb")
REPORT = os.path.join(WS, "projects", "digital-human", "out", "rig_report.json")
OUT = os.path.join(WS, ".scratch", "dh_source_probe.json")

CT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
# v1 代理上量到的最坏"帆边"静置端点（3 处，来自 02/05/06 三条动作）
PROBES = [(0.12676, -0.01322, 0.38034), (0.12675, -0.01284, 0.36968), (0.12615, -0.01786, 0.36544),
          (-0.09059, 0.00424, 0.52968), (-0.08998, 0.00423, 0.52953)]   # 右侧"腰带浮片"两处
R_ENV = {"hips": 0.068, "spine": 0.050, "chest": 0.055, "neck": 0.025, "head": 0.060,
         "shoulder": 0.025, "upper_arm": 0.030, "forearm": 0.024, "hand": 0.024,
         "thigh": 0.028, "shin": 0.029, "foot": 0.022}


def main():
    raw = open(SRC, "rb").read()
    jl = struct.unpack_from("<I", raw, 12)[0]
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    BIN = raw[off + 8:off + 8 + struct.unpack_from("<I", raw, off)[0]]
    del raw
    pr = J["meshes"][0]["primitives"][0]

    def read_acc(i):
        a = J["accessors"][i]
        bv = J["bufferViews"][a["bufferView"]]
        fmt, sz = CT[a["componentType"]]
        n = NC[a["type"]]
        base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        return np.frombuffer(BIN, dtype=np.dtype("<" + fmt), count=a["count"] * n,
                             offset=base).reshape(a["count"], n)

    P = read_acc(pr["attributes"]["POSITION"]).astype(np.float64)
    I = read_acc(pr["indices"]).astype(np.int64).ravel()
    co = np.stack([P[:, 0], -P[:, 2], P[:, 1]], axis=1)
    del P
    T = I.reshape(-1, 3)
    del I, BIN

    RP = json.load(open(REPORT, encoding="utf-8"))
    bones = {b["name"]: (np.array(b["head"], dtype=np.float64), np.array(b["tail"], dtype=np.float64))
             for b in RP["skeleton"]["bones"]}
    H = float(RP["landmarks"]["height_units"])
    cx = float(RP["landmarks"]["axis_lat"])

    names = list(bones.keys())
    # 细标签：每根骨单独一个标签
    dom = np.full(len(co), -1, dtype=np.int32)
    dmin = np.full(len(co), 1e9)
    for j, n in enumerate(names):
        h, t = bones[n]
        ab = t - h
        L2 = float(ab @ ab) or 1e-12
        wv = np.clip(((co - h) @ ab) / L2, 0.0, 1.0)
        d = np.linalg.norm(co - (h + wv[:, None] * ab), axis=1) / (R_ENV.get(n.split("_")[0], 0.03) * H)
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

    # 连通分量
    import scipy.sparse as sp
    import scipy.sparse.csgraph as csg
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]], axis=0)
    A = sp.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(co),) * 2).tocsr()
    ncomp, lab = csg.connected_components((A + A.T).tocsr(), directed=False)
    sizes = np.bincount(lab)
    del A, e
    print("[probe] 源网格分量=%d 最大=%d" % (ncomp, sizes.max()))

    res = {"source_components": int(ncomp), "probes": []}
    for p in PROBES:
        pv = np.array(p, dtype=np.float64)
        d = np.linalg.norm(co - pv, axis=1)
        near = np.where(d < 0.004)[0]
        rec = {"probe": [round(float(x), 5) for x in pv], "n_within_4mm": int(len(near)),
               "components": {}}
        for vi in near:
            L = lab[vi]
            r = rec["components"].setdefault(str(int(L)), {"n": 0, "label_hist": {},
                                                           "z_range": [9, -9], "u_range": [9, -9]})
            r["n"] += 1
            nm = names[int(dom[vi])]
            r["label_hist"][nm] = r["label_hist"].get(nm, 0) + 1
            r["z_range"][0] = min(r["z_range"][0], float(co[vi, 2]))
            r["z_range"][1] = max(r["z_range"][1], float(co[vi, 2]))
            r["u_range"][0] = min(r["u_range"][0], float(co[vi, 0] - cx))
            r["u_range"][1] = max(r["u_range"][1], float(co[vi, 0] - cx))
        for k in rec["components"]:
            rec["components"][k]["z_range"] = [round(v, 4) for v in rec["components"][k]["z_range"]]
            rec["components"][k]["u_range"] = [round(v, 4) for v in rec["components"][k]["u_range"]]
        res["probes"].append(rec)
        print("[probe] 探针 %s 附近 4mm 内 %d 个源顶点，落在 %d 个分量："
              % (rec["probe"], rec["n_within_4mm"], len(rec["components"])))
        for k, v in sorted(rec["components"].items(), key=lambda kv: -kv[1]["n"]):
            print("        分量#%-6s n=%-5d 标签=%s z=%s u=%s"
                  % (k, v["n"], sorted(v["label_hist"].items(), key=lambda kv: -kv[1])[:4],
                     v["z_range"], v["u_range"]))

    # 分量级别的"跨区"总结：哪些分量同时含 hand_L/forearm_L 与 hips/thigh_L 标签
    armidx = [i for i, n in enumerate(names) if n in ("hand_L", "forearm_L")]
    toxidx = [i for i, n in enumerate(names) if n in ("hips", "thigh_L", "spine", "chest")]
    isa = np.isin(dom, armidx)
    ist = np.isin(dom, toxidx)
    cross_comp = []
    for L in np.unique(lab):
        m = lab == L
        a = int((m & isa).sum()); t = int((m & ist).sum())
        if a > 0 and t > 0:
            zs = co[m, 2]
            cross_comp.append({"comp": int(L), "n": int(m.sum()), "armL": a, "torso": t,
                               "z": [round(float(zs.min()), 3), round(float(zs.max()), 3)]})
    cross_comp.sort(key=lambda r: -r["n"])
    res["components_spanning_armL_and_torso"] = cross_comp[:15]
    print("[probe] 同时含 hand/forearm_L 与 hips/thigh_L/spine/chest 的分量 = %d 个（前 15 见 JSON）"
          % len(cross_comp))
    for r in cross_comp[:5]:
        print("        分量#%-6d 顶点=%-6d armL=%-5d torso=%-5d z范围=%s"
              % (r["comp"], r["n"], r["armL"], r["torso"], r["z"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[probe] 落盘 " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
