# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""网格减面（**保 UV / 保纹理缝**）→ 直接写 GLB。用 python 3.12 跑（pymeshlab 只在那边）。

为什么要自己写这一件：
  · pymeshlab **存不了 glb**（`Unknown format for save: glb`），仓里既有做法是绕 PLY/OBJ 文件，
    而 OBJ 是文本、会把顶点精度与 v/vt 拆分搞坏（`pml-to-glb.py` 自己也把这句话写在注释里）。
  · 所以这里**不走文件**：直接取 pymeshlab 内存里的 顶点/面/法线/**wedge 纹理坐标**，
    再自建 GLB、贴图从源 GLB 原样搬过来 —— 少一道中转就少一处失真。

关键口径：
  · **wedge（每面角）UV 必须展开重编号**：同一个顶点在 UV 缝两侧是**两个不同的点**，
    按顶点合并会把整张贴图拉花。这里按 (顶点, UV) 二元组唯一化。
  · **V 轴要翻**：pymeshlab 内部是 OBJ/OpenGL 口径（原点左下），glTF 是左上 ⇒ 写盘前 v := 1-v。
    默认翻；`--no-flip-v` 可关（用来现场对照，验证这条判断本身对不对）。
  · 平滑法线：pymeshlab 给了就用它；缺就按面积加权现算。

用法（3.12）：
  python tools/codex-scripts/mesh-decimate.py <in.glb> <out.glb> <target_faces>
退出码：0 = 写出且自检通过；1 = 自检不过；2 = 前置问题。
"""
import json
import pathlib
import struct
import sys

import numpy as np
import pymeshlab as ml

WS = pathlib.Path(_GBT_ROOT)
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WS / "holo_pet/assets/digital-human/raw/avatarmesh/model-facing.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else WS / "holo_pet/assets/digital-human/raw/avatarmesh/model-lowpoly.glb"
TARGET = int(sys.argv[3]) if len(sys.argv) > 3 else 40000
FLIP_V = "--no-flip-v" not in sys.argv


def read_glb(path):
    raw = path.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, raw[off + 8: off + 8 + bl]


def closest_bary(p, a, b, c):
    """点 p 到三角形 abc 的最近点，返回 (重心坐标, 距离平方)。（Ericson, Real-Time Collision Detection）"""
    ab = b - a
    ac = c - a
    ap = p - a
    d1 = ab @ ap
    d2 = ac @ ap
    if d1 <= 0.0 and d2 <= 0.0:
        return (1.0, 0.0, 0.0), float(ap @ ap)
    bp = p - b
    d3 = ab @ bp
    d4 = ac @ bp
    if d3 >= 0.0 and d4 <= d3:
        return (0.0, 1.0, 0.0), float(bp @ bp)
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        q = p - (a + v * ab)
        return (1.0 - v, v, 0.0), float(q @ q)
    cp = p - c
    d5 = ab @ cp
    d6 = ac @ cp
    if d6 >= 0.0 and d5 <= d6:
        return (0.0, 0.0, 1.0), float(cp @ cp)
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        q = p - (a + w * ac)
        return (1.0 - w, 0.0, w), float(q @ q)
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        q = p - (b + w * (c - b))
        return (0.0, 1.0 - w, w), float(q @ q)
    den = 1.0 / (va + vb + vc)
    v = vb * den
    w = vc * den
    q = p - (a + ab * v + ac * w)
    return (1.0 - v - w, v, w), float(q @ q)


def _bary_scalar(px, py, pz, ax, ay, az, bx, by, bz, cx, cy, cz):
    """点 p 到三角形 abc 的最近点重心坐标 + 距离平方（纯标量版，比逐次 numpy 快得多）。"""
    abx, aby, abz = bx - ax, by - ay, bz - az
    acx, acy, acz = cx - ax, cy - ay, cz - az
    apx, apy, apz = px - ax, py - ay, pz - az
    d1 = abx * apx + aby * apy + abz * apz
    d2 = acx * apx + acy * apy + acz * apz
    if d1 <= 0.0 and d2 <= 0.0:
        return (1.0, 0.0, 0.0), apx * apx + apy * apy + apz * apz
    bpx, bpy, bpz = px - bx, py - by, pz - bz
    d3 = abx * bpx + aby * bpy + abz * bpz
    d4 = acx * bpx + acy * bpy + acz * bpz
    if d3 >= 0.0 and d4 <= d3:
        return (0.0, 1.0, 0.0), bpx * bpx + bpy * bpy + bpz * bpz
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        qx, qy, qz = px - (ax + v * abx), py - (ay + v * aby), pz - (az + v * abz)
        return (1.0 - v, v, 0.0), qx * qx + qy * qy + qz * qz
    cpx, cpy, cpz = px - cx, py - cy, pz - cz
    d5 = abx * cpx + aby * cpy + abz * cpz
    d6 = acx * cpx + acy * cpy + acz * cpz
    if d6 >= 0.0 and d5 <= d6:
        return (0.0, 0.0, 1.0), cpx * cpx + cpy * cpy + cpz * cpz
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        qx, qy, qz = px - (ax + w * acx), py - (ay + w * acy), pz - (az + w * acz)
        return (1.0 - w, 0.0, w), qx * qx + qy * qy + qz * qz
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        qx, qy, qz = px - (bx + w * (cx - bx)), py - (by + w * (cy - by)), pz - (bz + w * (cz - bz))
        return (0.0, 1.0 - w, w), qx * qx + qy * qy + qz * qz
    den = 1.0 / (va + vb + vc)
    v = vb * den
    w = vc * den
    qx = px - (ax + abx * v + acx * w)
    qy = py - (ay + aby * v + acy * w)
    qz = pz - (az + abz * v + acz * w)
    return (1.0 - v - w, v, w), qx * qx + qy * qy + qz * qz


def project_uv_perface(V0, F0, UV0, VN, FN, ktri=4):
    """**逐面**把源网格 UV 迁到减面后的网格上。

    🔴 为什么必须"逐面"而不是"逐顶点"（2026-09-25 实测，这是本次最贵的一课）：
      网格存在 **UV 缝**：同一个三维位置上有一对**重复顶点、UV 不同**。
      逐顶点投影时，"最近三角"在缝上会挑到**另一侧**那片 ⇒ 该顶点 UV 跳到贴图别处。
      自投影对照（拿源顶点投影回源网格）量到 **107/3000 = 3.6% 的顶点 UV 错到 0.96**，
      渲染出来就是"整张皮碎成放射状碎块"（而法线探针、素色探针都干净 —— 所以不是几何/法线问题）。
      改成逐面：**一个面只认一个源三角**（对三个角的距离和最小的那个），三个角都用它插值，
      面内 UV 必然自洽；跨缝时相邻面各自挑到自己那侧，纹理在缝上正确断开。
    """
    from scipy.spatial import cKDTree

    print(f"[3a] 逐面 UV 投影：源 {len(F0)} 面 → 目标 {len(FN)} 面（每面 {ktri} 个质心候选）")
    C0 = V0[F0].mean(axis=1)
    tri_tree = cKDTree(C0)
    CN = VN[FN].mean(axis=1)
    _, nb = tri_tree.query(CN, k=ktri)
    nb = np.atleast_2d(nb)

    V0l = V0.tolist()
    F0l = F0.tolist()
    UV0l = UV0.tolist()
    # 🔴 UV 必须存成**逐面角**，不能存进逐顶点数组：
    #    一个顶点被最多 6 个面共用，而每个面各自挑源三角（跨 UV 缝时挑到的是不同侧），
    #    写进逐顶点数组就是"后写的覆盖先写的" ⇒ 渲染出来正好是放射状碎块。
    #    2026-09-25 实测教训：自投影对照测不出这个错（那时每个面挑的都是自己那个源三角、值相同）。
    #    存逐面角、再按 (顶点,UV) 唯一化拆点，才是对的。
    UVc = np.zeros((len(FN) * 3, 2), np.float64)
    for fi in range(len(FN)):
        ia0, ib0, ic0 = FN[fi]
        p = (VN[ia0], VN[ib0], VN[ic0])
        best = None
        for t in nb[fi]:
            ta, tb, tc = F0l[int(t)]
            ax, ay, az = V0l[ta]
            bx, by, bz = V0l[tb]
            cx, cy, cz = V0l[tc]
            tot = 0.0
            barys = []
            for q in p:
                b, d = _bary_scalar(q[0], q[1], q[2], ax, ay, az, bx, by, bz, cx, cy, cz)
                tot += d
                barys.append(b)
            if best is None or tot < best[0]:
                best = (tot, int(t), barys)
        _, t, barys = best
        ta, tb, tc = F0l[t]
        ua, va = UV0l[ta]
        ub, vb = UV0l[tb]
        uc, vc = UV0l[tc]
        for k, b in enumerate(barys):
            UVc[fi * 3 + k] = (b[0] * ua + b[1] * ub + b[2] * uc,
                               b[0] * va + b[1] * vb + b[2] * vc)
    print(f"[3a] 逐面投影完成：{len(FN)} 面 × 3 面角 UV 已算（逐面角，不写逐顶点）")
    return UVc


def project_uv(V0, F0, UV0, VN, k=10):
    """把源网格的 UV **投影**到减面后的顶点上。

    为什么不用减面滤镜自带的 UV（2026-09-25 实测）：
      同一份输入，`_with_texture` 与普通 QEM **两条路都把 UV 弄坏**——
      不减面时贴图完全正常；一减面，大腿冒出白三角、脸糊成一片，
      普通 QEM 更把 24715 个顶点炸成 83261 个唯一 (顶点,UV) 对（= 逐面角乱拆）。
      所以 UV 不指望滤镜保，改成**几何投影**：新顶点 → 源表面最近点 → 重心插值 UV。
      源网格是**逐顶点 UV**，插值不会跨缝，因此这一步不会拉花。
    """
    from scipy.spatial import cKDTree

    print(f"[3a] UV 投影：源 {len(V0)} 顶点 / {len(F0)} 面 → 目标 {len(VN)} 顶点（k={k} 近邻候选）")
    tri_of_corner = np.repeat(np.arange(len(F0)), 3)
    vert_of_corner = F0.reshape(-1)
    order = np.argsort(vert_of_corner, kind="stable")
    vs = vert_of_corner[order]
    ts = tri_of_corner[order]
    counts = np.bincount(vs, minlength=len(V0))
    starts = np.concatenate([[0], np.cumsum(counts)])

    tree = cKDTree(V0)
    _, nb = tree.query(VN, k=k)
    if nb.ndim == 1:
        nb = nb[:, None]

    UVN = np.zeros((len(VN), 2), np.float64)
    miss = 0
    for i, p in enumerate(VN):
        cand = np.unique(np.concatenate([ts[starts[v]:starts[v + 1]] for v in nb[i]])) if len(nb[i]) else np.array([], int)
        if len(cand) == 0:
            miss += 1
            continue
        best_d, best_b, best_t = np.inf, None, -1
        for t in cand:
            ia, ib, ic = F0[t]
            b, d = closest_bary(p, V0[ia], V0[ib], V0[ic])
            if d < best_d:
                best_d, best_b, best_t = d, b, t
        ia, ib, ic = F0[best_t]
        UVN[i] = best_b[0] * UV0[ia] + best_b[1] * UV0[ib] + best_b[2] * UV0[ic]
    d = np.linalg.norm(VN - V0[tree.query(VN, k=1)[1]], axis=1)
    print(f"[3a] UV 投影完成：未命中 {miss} 顶点 · 顶点到源表面最近距离 "
          f"中位 {np.median(d):.5f} / 最大 {d.max():.5f}（相对身高 {np.median(d)/1.0:.4%}）")
    return UVN


def load_source_uv(path):
    """直接从源 GLB 读 POSITION / TEXCOORD_0 / indices —— **不经 pymeshlab**。

    理由：pymeshlab 载入 glTF 时会把 V 轴转成它内部的 OBJ 口径，再经它取 UV 就要重新翻回来；
    既然这里只是要"一份正确的 UV 真值"，直接读盘上的原始字节最不容易出错。
    """
    J, BIN = read_glb(path)
    pr = J["meshes"][0]["primitives"][0]

    def acc(i, comps):
        a = J["accessors"][i]
        bv = J["bufferViews"][a["bufferView"]]
        dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
        return np.frombuffer(bytes(BIN), dt, a["count"] * comps,
                             bv.get("byteOffset", 0)).reshape(a["count"], comps)
    V0 = acc(pr["attributes"]["POSITION"], 3).astype(np.float64)
    UV0 = acc(pr["attributes"]["TEXCOORD_0"], 2).astype(np.float64)
    F0 = acc(pr["indices"], 1).astype(np.int64).reshape(-1, 3)
    print(f"[3a] 源真值：顶点 {len(V0)} · UV {len(UV0)} · 面 {len(F0)}")
    if len(UV0) != len(V0):
        raise SystemExit(f"🔴 源网格不是逐顶点 UV（顶点 {len(V0)} vs UV {len(UV0)}）⇒ 投影法不适用")
    return V0, F0, UV0


def main():
    if not SRC.is_file():
        print(f"🔴 输入不在盘上：{SRC}")
        return 2

    ms = ml.MeshSet()
    ms.load_new_mesh(str(SRC))
    m = ms.current_mesh()
    f0, v0 = m.face_number(), m.vertex_number()
    print(f"[1] 载入 {SRC.name}：面 {f0} · 顶点 {v0} · wedge UV {m.has_wedge_tex_coord()}")

    if "--no-decimate" in sys.argv:
        print("[2] 跳过减面（--no-decimate：用来单独验『抽取+重编号』这条路径本身）")
    elif "--plain" in sys.argv:
        # 源网格是**逐顶点 UV**（实测：749175 顶点 ↔ 749175 个唯一 (顶点,UV) 对），
        # 所以普通 QEM 也可能把顶点 UV 一起插值过去；而 _with_texture 那支实测**会把 wedge UV 弄坏**
        # （同一份输入：不減面干净、减面后大腿出现白三角、脸糊成一片）。
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=TARGET, preserveboundary=True, preservenormal=True,
            planarquadric=True, selected=False)
        m = ms.current_mesh()
    else:
        ms.meshing_decimation_quadric_edge_collapse_with_texture(
            targetfacenum=TARGET, preserveboundary=True, preservenormal=True,
            planarquadric=True, selected=False)
        m = ms.current_mesh()
    V = np.asarray(m.vertex_matrix(), np.float64)
    F = np.asarray(m.face_matrix(), np.int64)
    try:
        N = np.asarray(m.vertex_normal_matrix(), np.float64)
    except Exception:
        N = None
    W = np.asarray(m.wedge_tex_coord_matrix(), np.float64) if m.has_wedge_tex_coord() else None
    print(f"[2] 减面：面 {m.face_number()} · 顶点 {m.vertex_number()} · "
          f"目标 {TARGET}（缝保护 QEM，不保证恰好命中）· 法线 {'有' if N is not None else '无'} · "
          f"wedge UV {'有' if W is not None else '无'}")
    if len(F) == 0 or len(V) == 0:
        print("🔴 减面后为空")
        return 1

    # ── UV 来源：默认**几何投影**（滤镜自带 UV 实测会坏，见 project_uv 的说明） ──
    if "--wedge-uv" in sys.argv:
        if W is not None and len(W) == len(F) * 3:
            uv = np.round(W.reshape(-1, 2), 6)
        else:
            print("🔴 wedge UV 缺失或长度不符 ⇒ 不能保住贴图，停止（宁缺不糊）")
            return 1
        if FLIP_V:
            uv = np.stack([uv[:, 0], 1.0 - uv[:, 1]], axis=1)
        pair = np.concatenate([F.reshape(-1)[:, None].astype(np.float64), uv], axis=1)
        uniq, inv = np.unique(pair, axis=0, return_inverse=True)
        src_v = uniq[:, 0].astype(np.int64)
        NV = V[src_v]
        NUV = uniq[:, 1:3]
        NF = inv.reshape(-1, 3).astype(np.uint32)
        NN = N[src_v] if (N is not None and len(N) == len(V)) else None
        print(f"[3] wedge 路径（对照用）：顶点 {len(NV)} · 面 {len(NF)} · V 轴翻转 {FLIP_V}")
        if NN is None:
            NN = np.zeros_like(NV)
            tri = NV[NF]
            fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            for k in range(3):
                np.add.at(NN, NF[:, k], fn)
            NN /= np.maximum(np.linalg.norm(NN, axis=1, keepdims=True), 1e-9)
    else:
        NV = V
        NF = F.astype(np.uint32)
        NN = N if (N is not None and len(N) == len(V)) else None
        if NN is None:
            NN = np.zeros_like(NV)
            tri = NV[NF]
            fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            for k in range(3):
                np.add.at(NN, NF[:, k], fn)
            NN /= np.maximum(np.linalg.norm(NN, axis=1, keepdims=True), 1e-9)
            print("    （法线缺失，已按面积加权现算）")
        V0, F0, UV0 = load_source_uv(SRC)
        # 🔴 这里**不翻 V**：UV 是直接从源 GLB 的 TEXCOORD_0 读的（glTF 口径，原点左上），
        #    本来就对。之前翻 V 是为了抵消 pymeshlab 内部的 OBJ 口径 —— 那条只在 wedge 路径成立。
        UVc = project_uv_perface(V0, F0, UV0, NV, NF)
        # 按 (顶点, UV) 唯一化拆点：UV 缝上的顶点必须一分为二，否则两侧争同一个 UV
        pair = np.concatenate([NF.reshape(-1)[:, None].astype(np.float64), UVc], axis=1)
        uniq, inv = np.unique(pair, axis=0, return_inverse=True)
        src_v = uniq[:, 0].astype(np.int64)
        NV, NUV, NF = NV[src_v], uniq[:, 1:3], inv.reshape(-1, 3).astype(np.uint32)
        NN = NN[src_v]                    # 法线跟着拆点一起重排，否则与顶点错位
        print(f"[3] 逐面投影路径：顶点 {len(NV)}（拆点后）· 面 {len(NF)} · UV 来自源 GLB（不翻 V）")

    # ── 贴图/材质：从源 GLB 原样搬 ───────────────────────────────────────────
    J, BIN = read_glb(SRC)
    src_mat = (J.get("materials") or [{}])[0]
    src_pbr = src_mat.get("pbrMetallicRoughness", {})
    buf = bytearray()
    views = []
    accs = []
    imgs = []
    texs = []

    def view(data, target=None):
        while len(buf) % 4:
            buf.append(0)
        o = len(buf)
        buf.extend(data)
        v = {"buffer": 0, "byteOffset": o, "byteLength": len(data)}
        if target:
            v["target"] = target
        views.append(v)
        return len(views) - 1

    def add(arr, ct, typ, target=None, mm=False):
        vi = view(arr.tobytes(), target)
        a = {"bufferView": vi, "componentType": ct, "count": len(arr), "type": typ}
        if mm:
            a.update({"min": [float(x) for x in arr.min(axis=0)],
                      "max": [float(x) for x in arr.max(axis=0)]})
        accs.append(a)
        return len(accs) - 1

    a_p = add(NV.astype(np.float32), 5126, "VEC3", 34962, True)
    a_n = add(NN.astype(np.float32), 5126, "VEC3", 34962)
    a_u = add(NUV.astype(np.float32), 5126, "VEC2", 34962)
    a_i = add(NF.reshape(-1), 5125, "SCALAR", 34963)

    def copy_tex(tex_obj):
        si = J["textures"][tex_obj["index"]]["source"]
        im = J["images"][si]
        bv = J["bufferViews"][im["bufferView"]]
        o = bv.get("byteOffset", 0)
        imgs.append({"bufferView": view(BIN[o:o + bv["byteLength"]]),
                     "mimeType": im.get("mimeType", "image/png")})
        texs.append({"sampler": 0, "source": len(imgs) - 1})
        return len(texs) - 1

    mat_out = {"name": src_mat.get("name", "avatar"), "pbrMetallicRoughness": {
        "metallicFactor": src_pbr.get("metallicFactor", 0.0),
        "roughnessFactor": src_pbr.get("roughnessFactor", 0.7)}}
    if src_pbr.get("baseColorTexture"):
        mat_out["pbrMetallicRoughness"]["baseColorTexture"] = {"index": copy_tex(src_pbr["baseColorTexture"])}
    BASECOLOR_ONLY = "--basecolor-only" in sys.argv
    if BASECOLOR_ONLY:
        print("[4a] --basecolor-only：只搬底色贴图（用来把『UV 坏』与『法线贴图坏』分开）")
    if src_pbr.get("metallicRoughnessTexture") and not BASECOLOR_ONLY:
        mat_out["pbrMetallicRoughness"]["metallicRoughnessTexture"] = {
            "index": copy_tex(src_pbr["metallicRoughnessTexture"])}
    if src_mat.get("normalTexture") and not BASECOLOR_ONLY:
        mat_out["normalTexture"] = {"index": copy_tex(src_mat["normalTexture"])}
    if src_mat.get("occlusionTexture") and not BASECOLOR_ONLY:
        mat_out["occlusionTexture"] = {"index": copy_tex(src_mat["occlusionTexture"])}
    if src_mat.get("emissiveTexture"):
        mat_out["emissiveTexture"] = {"index": copy_tex(src_mat["emissiveTexture"])}
    print(f"[4] 贴图搬运：{len(imgs)} 张（{', '.join(im['mimeType'] for im in imgs) or '无'}）")

    G = {"asset": {"version": "2.0", "generator": "GBT · pymeshlab 缝保护 QEM（内存直转 GLB）"},
         "scene": 0, "scenes": [{"nodes": [0]}],
         "nodes": [{"mesh": 0, "name": "avatar_lowpoly"}],
         "meshes": [{"name": "avatar_lowpoly", "primitives": [
             {"attributes": {"POSITION": a_p, "NORMAL": a_n, "TEXCOORD_0": a_u},
              "indices": a_i, "material": 0}]}],
         "materials": [mat_out], "textures": texs, "images": imgs,
         "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
         "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(buf)}]}

    body = bytearray(buf)
    while len(body) % 4:
        body.append(0)
    G["buffers"][0]["byteLength"] = len(body)
    js = json.dumps(G, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                    + struct.pack("<I", len(js)) + b"JSON" + js
                    + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))

    # ── 自检：引用合法 / UV 在 [0,1] / 顶点面数正常 ──────────────────────────
    bad = []
    if a_p >= len(views) or a_i >= len(views):
        bad.append("bufferView 越界")
    if NUV.min() < -0.01 or NUV.max() > 1.01:
        bad.append(f"UV 越界 [{NUV.min():.3f},{NUV.max():.3f}]")
    if len(NF) == 0 or len(NV) == 0:
        bad.append("空网格")
    sz = OUT.stat().st_size / 1024 / 1024
    print(f"[5] 输出 {OUT} · {sz:.2f} MB · 顶点 {len(NV)} · 面 {len(NF)} · 贴图 {len(imgs)}")
    if bad:
        print("🔴 自检不过：" + "；".join(bad))
        return 1
    print("✅ 自检通过（引用合法 · UV 在域内 · 网格非空）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
