# -*- coding: utf-8 -*-
"""面板档合成（分区 LOD）：**减面身体** + **高密度合格头** + 同一套 22 骨。
判据：文件 <10MB（面板路由此前 61MB 会 500）· 体重算权重(和=1) · 头沿用 Head/Neck/HeadTop · 引用合法。
从零重建 GLB：只带每件**自己的**贴图（避免把 4K 身体贴图也塞进头件）。"""
import json
import pathlib
import struct
import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
BODY = DH / "raw/phase7-body-low/tripo-out/gbt-body-low-convert-98605f3a/model.glb"
HEAD = DH / "raw/rig/part-head.glb"
OUT = DH / "raw/rig/model-panel-tier.glb"


def load(p):
    raw = p.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, bytes(raw[off + 8: off + 8 + bl])


def acc(J, BIN, i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(BIN, dt, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps)


def slots_and_images(J, BIN, prim):
    m = J["materials"][prim["material"]]
    pbr = m.get("pbrMetallicRoughness", {})
    out = {}
    for key, tex in (("base", pbr.get("baseColorTexture")), ("mr", pbr.get("metallicRoughnessTexture")),
                     ("norm", m.get("normalTexture"))):
        if not tex:
            continue
        si = J["textures"][tex["index"]]["source"]
        bv = J["bufferViews"][J["images"][si]["bufferView"]]
        data = BIN[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]
        out[key] = (data, J["images"][si].get("mimeType", "image/jpeg"))
    return out, m


def cluster_decimate(V, N, UV, IDX, J4, W4, cell):
    """顶点聚类减面：体素网格合并 + 属性取均值 + 丢退化面。返回 (V,N,UV,J4,W4,IDX)"""
    key = np.floor(V / cell).astype(np.int64)
    _, inv, counts = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    n = len(counts)

    def avg(A):
        out = np.zeros((n, A.shape[1]), np.float64)
        np.add.at(out, inv, A)
        return out / counts[:, None]
    V2, N2, UV2 = avg(V), avg(N), avg(UV)
    first = np.full(n, -1, np.int64)
    first[inv[::-1]] = np.arange(len(inv))[::-1]      # 每格第一个顶点（取它的骨索引）
    J42 = J4[first]
    W42 = avg(W4).astype(np.float32)
    W42 /= np.maximum(W42.sum(axis=1, keepdims=True), 1e-6)
    idx = inv[IDX]
    keep = (idx[:, 0] != idx[:, 1]) & (idx[:, 1] != idx[:, 2]) & (idx[:, 0] != idx[:, 2])
    return V2.astype(np.float32), N2.astype(np.float32), UV2.astype(np.float32), J42, W42, idx[keep].astype(np.uint32), len(counts)


def qem_decimate(V, N, UV, IDX3, J4, W4, target_faces):
    """QEM 边坍缩 + **面上最近点重心插值**回传 UV/权重（不跨 UV 缝）。"""
    import trimesh
    from trimesh.proximity import closest_point
    src = trimesh.Trimesh(vertices=V, faces=IDX3, process=False)
    dv = src.simplify_quadric_decimation(face_count=int(target_faces))
    V2 = np.asarray(dv.vertices, np.float64)
    F2 = np.asarray(dv.faces, np.int64)
    _, _, tri = closest_point(src, V2)                    # 每个新顶点落在原始哪个三角面上
    tri = np.asarray(tri, np.int64)
    A, B, C = IDX3[tri, 0], IDX3[tri, 1], IDX3[tri, 2]
    # 面内重心坐标（投影到面平面）

    def bary(p, a, b, c):
        v0, v1, v2 = b - a, c - a, p - a
        d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
        d20, d21 = v2 @ v0, v2 @ v1
        den = d00 * d11 - d01 * d01
        if abs(den) < 1e-12:
            return np.array([1.0, 0.0, 0.0])
        v = (d11 * d20 - d01 * d21) / den
        w = (d00 * d21 - d01 * d20) / den
        return np.array([1 - v - w, v, w])
    UV2 = np.zeros((len(V2), 2), np.float64)
    W42 = np.zeros((len(V2), 4), np.float32)
    J42 = np.zeros((len(V2), 4), np.uint16)
    for i in range(len(V2)):
        ia, ib, ic = A[i], B[i], C[i]
        w = bary(V2[i], V[ia], V[ib], V[ic])
        w = np.clip(w, 0, 1)
        w = w / max(w.sum(), 1e-9)
        _uv = w[0] * UV[ia] + w[1] * UV[ib] + w[2] * UV[ic]
        _lo = np.minimum(np.minimum(UV[ia], UV[ib]), UV[ic]) - 1e-4
        _hi = np.maximum(np.maximum(UV[ia], UV[ib]), UV[ic]) + 1e-4
        UV2[i] = np.clip(_uv, _lo, _hi)                 # ② 按面钳制，防越岛极值
        acc = {}
        for wi, vi in zip(w, (ia, ib, ic)):
            for j, ww in zip(J4[vi], W4[vi]):
                if ww > 0:
                    acc[int(j)] = acc.get(int(j), 0.0) + float(wi) * float(ww)
        top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
        s = sum(v for _, v in top) or 1.0
        for k, (j, ww) in enumerate(top):
            J42[i, k] = j
            W42[i, k] = ww / s
    # ① 法线也重心插值（取面首顶点法线会让 QEM 后的面出现明暗碎片）
    N2 = np.zeros((len(V2), 3), np.float64)
    for i in range(len(V2)):
        ia, ib, ic = A[i], B[i], C[i]
        w = bary(V2[i], V[ia], V[ib], V[ic])
        w = np.clip(w, 0, 1)
        w = w / max(w.sum(), 1e-9)
        nv = w[0] * N[ia] + w[1] * N[ib] + w[2] * N[ic]
        N2[i] = nv / max(np.linalg.norm(nv), 1e-9)
    return V2.astype(np.float32), N2.astype(np.float32), UV2.astype(np.float32), J42, W42, F2.astype(np.uint32), len(V2)


def smooth(V, IDX, iters=3, lam=0.5):
    """拉普拉斯平滑（消聚类阶梯感）；用边表做稀疏平均。"""
    e = np.concatenate([IDX[:, [0, 1]], IDX[:, [1, 2]], IDX[:, [2, 0]]])
    e = np.concatenate([e, e[:, ::-1]])
    for _ in range(iters):
        acc = np.zeros_like(V)
        cnt = np.zeros(len(V), np.float32)
        np.add.at(acc, e[:, 0], V[e[:, 1]])
        np.add.at(cnt, e[:, 0], 1.0)
        avg = acc / np.maximum(cnt[:, None], 1e-6)
        V = (1 - lam) * V + lam * avg
    return V


JB, BB = load(BODY)
JH, BH = load(HEAD)
pb, ph = JB["meshes"][0]["primitives"][0], JH["meshes"][0]["primitives"][0]
PB = acc(JB, BB, pb["attributes"]["POSITION"], 3).astype(np.float64)
NB = acc(JB, BB, pb["attributes"]["NORMAL"], 3)
UB = acc(JB, BB, pb["attributes"]["TEXCOORD_0"], 2)
IB = acc(JB, BB, pb["indices"], 1).astype(np.uint32)
PH = acc(JH, BH, ph["attributes"]["POSITION"], 3).astype(np.float64)
NH = acc(JH, BH, ph["attributes"]["NORMAL"], 3)
UH = acc(JH, BH, ph["attributes"]["TEXCOORD_0"], 2)
IH = acc(JH, BH, ph["indices"], 1).astype(np.uint32)
JH4 = acc(JH, BH, ph["attributes"]["JOINTS_0"], 4).astype(np.uint16)
WH4 = acc(JH, BH, ph["attributes"]["WEIGHTS_0"], 4).astype(np.float32)
# ── 头：本地聚类减面到目标面数（面板路由上限 12MB ⇒ 头必须先瘦）──
TARGET_TRIS = 75000
_V, _N, _UV, _J, _W, _I, _n = qem_decimate(PH, NH, UH, IH.reshape(-1, 3), JH4, WH4, TARGET_TRIS)
PH, NH, UH, JH4, WH4, IH = _V, _N, _UV, _J, _W, _I
print(f"头（QEM 减面）{len(PH)} 顶点/{len(IH)} 三角形（目标 {TARGET_TRIS} · UV/权重最近邻回传）")

print(f"身体 {len(PB)} 顶点/{len(IB)//3} 三角形 · 头 {len(PH)} 顶点/{len(IH)//3} 三角形")

# 骨（从 head 件取：同一套 22 骨）+ 世界坐标
nodes = JH["nodes"]
bone_idx = [i for i, n in enumerate(nodes) if (n.get("name") or "").startswith("mixamorig")]
names = [nodes[i]["name"] for i in bone_idx]
parent_of = {}
for k, n in enumerate(nodes):
    for c in n.get("children") or []:
        parent_of[c] = k
world = {}
for i in bone_idx:
    chain, cur, g = [], i, 0
    while cur is not None and cur not in world:
        chain.append(cur)
        cur = parent_of.get(cur)
        g += 1
        if g > 200:
            raise SystemExit("环")
    w = world[cur] if cur is not None else np.zeros(3)
    for nd in reversed(chain):
        w = w + np.array(nodes[nd].get("translation", [0, 0, 0]), np.float64)
        world[nd] = w
W3 = np.stack([world[i] for i in bone_idx])
# 骨段：head=自身，tail=子骨中点（叶给 +0.05 上）
kids = {names[k]: [names[j] for j in range(len(names)) if parent_of[bone_idx[j]] == bone_idx[k]] for k in range(len(names))}
tail = np.stack([np.mean([world[bone_idx[names.index(c)]] for c in kids[names[k]]], axis=0) if kids[names[k]]
                 else W3[k] + np.array([0, 0.05, 0]) for k in range(len(names))])


def seg_d(V, a, b):
    ab = b - a
    t = np.clip(((V - a) @ ab) / max(1e-12, ab @ ab), 0, 1)
    return np.linalg.norm(V - (a + t[:, None] * ab), axis=1)   # t 是 (N,)，必须 t[:,None]*ab


D = np.stack([seg_d(PB, W3[k], tail[k]) for k in range(len(names))], axis=1)
order = np.argsort(D, axis=1)[:, :4]
Wa = np.zeros_like(D)
rows = np.arange(len(PB))[:, None]
Wa[rows, order] = 1.0 / np.power(D[rows, order] + 1e-4, 3)
Wa /= Wa.sum(axis=1, keepdims=True)
JB4 = order.astype(np.uint16)
WB4 = Wa[rows, order].astype(np.float32)
WB4 /= WB4.sum(axis=1, keepdims=True)
print(f"体重算权重：和 {WB4.sum(axis=1).min():.4f}/{WB4.sum(axis=1).max():.4f}")

# ── 从零重建 ──
out_bin = bytearray()
views, accessors = [], []


def view(data, target=None):
    while len(out_bin) % 4:
        out_bin.append(0)
    o = len(out_bin)
    out_bin.extend(data)
    v = {"buffer": 0, "byteOffset": o, "byteLength": len(data)}
    if target:
        v["target"] = target
    views.append(v)
    return len(views) - 1


def add_acc(arr, ct, typ, target=None, mm=False):
    vi = view(arr.tobytes(), target)
    a = {"bufferView": vi, "componentType": ct, "count": len(arr), "type": typ}
    if mm:
        a.update({"min": [float(x) for x in arr.min(axis=0)], "max": [float(x) for x in arr.max(axis=0)]})
    accessors.append(a)
    return len(accessors) - 1


imgs = []


def recompress(data, mime, max_side=2048, q=88):
    """贴图压缩：超过 max_side 的缩到 max_side，统一 JPEG q88（面板档够用且省一半体积）"""
    try:
        from PIL import Image
        import io as _io
        im = Image.open(_io.BytesIO(data))
        if max(im.size) > max_side:
            r = max_side / max(im.size)
            im = im.resize((int(im.size[0] * r), int(im.size[1] * r)), Image.LANCZOS)
        buf = _io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=q)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return data, mime


def add_img(data, mime):
    vi = view(data)
    imgs.append({"bufferView": vi, "mimeType": mime})
    return len(imgs) - 1


body_tex, body_mat = slots_and_images(JB, BB, pb)
head_tex, head_mat = slots_and_images(JH, BH, ph)
bi = {k: add_img(*v) for k, v in body_tex.items()}
hi = {k: add_img(*v) for k, v in head_tex.items()}
textures = [{"sampler": 0, "source": bi[k]} for k in ("base", "norm") if k in bi] + \
           [{"sampler": 0, "source": hi[k]} for k in ("base", "norm") if k in hi]
mat_body = {"name": "body", "pbrMetallicRoughness": {
    "baseColorTexture": {"index": 0}, "metallicFactor": 0, "roughnessFactor": 0.75},
    "normalTexture": {"index": 1}}
mat_head = {"name": "head", "pbrMetallicRoughness": {
    "baseColorTexture": {"index": 2}, "metallicFactor": 0, "roughnessFactor": 0.7},
    "normalTexture": {"index": 3}}

a_pb = add_acc(PB.astype(np.float32), 5126, "VEC3", 34962, True)
a_nb = add_acc(NB.astype(np.float32), 5126, "VEC3", 34962)
a_ub = add_acc(UB.astype(np.float32), 5126, "VEC2", 34962)
a_jb = add_acc(JB4, 5123, "VEC4", 34962)
a_wb = add_acc(WB4, 5126, "VEC4", 34962)
a_ib = add_acc(IB, 5125, "SCALAR", 34963)
a_ph = add_acc(PH.astype(np.float32), 5126, "VEC3", 34962, True)
a_nh = add_acc(NH.astype(np.float32), 5126, "VEC3", 34962)
a_uh = add_acc(UH.astype(np.float32), 5126, "VEC2", 34962)
a_jh = add_acc(JH4, 5123, "VEC4", 34962)
a_wh = add_acc(WH4, 5126, "VEC4", 34962)
a_ih = add_acc(IH.reshape(-1), 5125, "SCALAR", 34963)

# 骨骼节点 + IBM
base_node = 1
bone_new = {}
jnode = []
for k, i in enumerate(bone_idx):
    par = parent_of.get(i)
    if par in bone_idx:
        rel = np.array(nodes[i].get("translation", [0, 0, 0]))
    else:
        rel = np.array(nodes[i].get("translation", [0, 0, 0]))
    jnode.append({"name": names[k], "translation": [float(x) for x in rel], "children": []})
    bone_new[i] = base_node + k
for k, i in enumerate(bone_idx):
    par = parent_of.get(i)
    if par in bone_new:
        jnode[bone_new[par] - base_node]["children"].append(bone_new[i])

ibm = []
for k, i in enumerate(bone_idx):
    m = np.eye(4, dtype=np.float32)
    m[:3, 3] = -world[i]
    ibm.append(m.T.flatten())
ibm = np.array(ibm, np.float32)
a_ibm = add_acc(ibm, 5126, "MAT4")

G = {
    "asset": {"version": "2.0", "generator": "GBT小土豆V8 · 面板档（分区 LOD）"},
    "scene": 0, "scenes": [{"nodes": [0, base_node + len(bone_idx)]}],
    "nodes": [{"mesh": 0, "name": "panel_tier", "skin": 0}] + jnode +
    [{"name": "Armature", "children": [base_node]}],
    "meshes": [{"name": "panel_tier", "primitives": [
        {"attributes": {"POSITION": a_pb, "NORMAL": a_nb, "TEXCOORD_0": a_ub, "JOINTS_0": a_jb, "WEIGHTS_0": a_wb},
         "indices": a_ib, "material": 0},
        {"attributes": {"POSITION": a_ph, "NORMAL": a_nh, "TEXCOORD_0": a_uh, "JOINTS_0": a_jh, "WEIGHTS_0": a_wh},
         "indices": a_ih, "material": 1}]}],
    "skins": [{"name": "GBT_AutoRig", "joints": [base_node + k for k in range(len(bone_idx))],
               "inverseBindMatrices": a_ibm, "skeleton": base_node}],
    "materials": [mat_body, mat_head], "textures": textures, "images": imgs,
    "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
    "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(out_bin)}],
}
while len(out_bin) % 4:
    out_bin.append(0)
G["buffers"][0]["byteLength"] = len(out_bin)
js = json.dumps(G, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(out_bin))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(out_bin)) + b"BIN\x00" + bytes(out_bin))
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · 关节 {len(bone_idx)} · 2 primitive")
