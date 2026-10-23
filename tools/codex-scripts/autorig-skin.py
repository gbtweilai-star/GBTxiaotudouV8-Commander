# -*- coding: utf-8 -*-
"""本地自动绑骨 · 第 3 步：蒙皮权重 + 导出绑骨 GLB + 姿态测试（全部本地，零积分）

方法：
  权重 = 逐顶点到各骨段的距离 → 取最近 4 段 → w=(1/d)^3 归一 → 再按三角邻接做 3 次拉普拉斯平滑
  裙摆/下摆：额外按"布料归髋"处理（避免裙摆被两条腿撕开）
  绑定姿势 = 当前 T-pose（骨骼静止变换=平移，无旋转 ⇒ IBM = 逆平移，干净且可验）
  姿态测试 = 对 LeftArm 及其子树施加绕深度轴 45° 旋转，用权重在 CPU 上直接形变顶点 → 另存静态 GLB 供渲染验收
"""
import json
import math
import pathlib
import struct
import sys
import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
# 可传参：autorig-skin.py <低模.glb> <骨架.json> <绑骨输出.glb> <姿态测试.glb>
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/avatarmesh/avatar-lowpoly.glb"
SKEL = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/skeleton.json"
OUT_RIG = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else DH / "raw/rig/avatar-rigged.glb"
OUT_POSE = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else DH / "raw/rig/avatar-pose-test.glb"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), dt, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps).astype(np.float64)


pr = J["meshes"][0]["primitives"][0]
P = acc(pr["attributes"]["POSITION"], 3)
N = acc(pr["attributes"]["NORMAL"], 3)
UV = acc(pr["attributes"]["TEXCOORD_0"], 2)
IDX = acc(pr["indices"], 1).astype(np.int64).reshape(-1, 3)
SK = json.loads(SKEL.read_text(encoding="utf-8"))
JOINTS, PARENT = SK["joints"], SK["parent"]
names = list(PARENT.keys())
pos = {n: np.array(JOINTS[n], np.float64) for n in names}
print(f"网格 {len(P)} 顶点 · {len(IDX)} 三角形 · 骨架 {len(names)} 关节")
y_top, y_bot = P[:, 1].max(), P[:, 1].min()
H = y_top - y_bot

# ① 骨段（head→tail）：tail 取子关节中点；叶节点给一个短尾巴
children = {n: [m for m in names if PARENT[m] == n] for n in names}


def tail_of(n):
    ch = children[n]
    if ch:
        return np.mean([pos[c] for c in ch], axis=0)
    p = pos[n]
    up = 1 if "Head" in n or "Spine" in n or "Neck" in n else -1
    return p + np.array([0, 0.03 * H * up, 0])


SEG = {n: (pos[n], tail_of(n)) for n in names}

# ② 权重（距离 + 平滑 + 布料归髋）


def seg_dist(v, a, b):
    ab = b - a
    t = np.clip(((v - a) @ ab) / max(1e-12, ab @ ab), 0, 1)
    return np.linalg.norm(v - (a + t * ab))


D = np.zeros((len(P), len(names)))
for i, n in enumerate(names):
    a, b = SEG[n]
    D[:, i] = [seg_dist(v, a, b) for v in P]
order = np.argsort(D, axis=1)[:, :4]
W = np.zeros_like(D)
rows = np.arange(len(P))[:, None]
W[rows, order] = 1.0 / np.power(D[rows, order] + 1e-4, 3)
W /= W.sum(axis=1, keepdims=True)

# 平滑：三角邻接上的拉普拉斯（3 次）
nb = [[] for _ in range(len(P))]
for a, b, c in IDX:
    nb[a] += [b, c]
    nb[b] += [a, c]
    nb[c] += [a, b]
nb = [np.array(sorted(set(x))) for x in nb]
for _ in range(3):
    W2 = W.copy()
    for i in range(len(P)):
        if len(nb[i]):
            W2[i] = 0.5 * W[i] + 0.5 * W[nb[i]].mean(axis=0)
    W = W2 / W2.sum(axis=1, keepdims=True)

# 布料归髋：裙摆高度区间（髋以下到膝以上）且明显离腿轴之外的顶点，权重压向 Hips
hip_i = names.index("Hips")
skirt = (P[:, 1] < pos["Hips"][1]) & (P[:, 1] > pos["LeftLeg"][1]) & (np.abs(P[:, 2]) < 0.14 * H)
if skirt.any():
    W[skirt] = 0.85 * W[skirt] + 0.15  # 抬 Hips 分量后再归一
    W[skirt, hip_i] += 0.35
    W[skirt] /= W[skirt].sum(axis=1, keepdims=True)
print(f"权重：写入全部 {len(P)} 顶点 · 平均活跃骨数 {(W > 0.01).sum(axis=1).mean():.2f} · 权重和 min/max = {W.sum(axis=1).min():.4f}/{W.sum(axis=1).max():.4f} · 布料归髋顶点 {int(skirt.sum())}")

# ③ 组 JOINTS_0(u16) / WEIGHTS_0(f32)，并追加 bufferView
top4 = np.argsort(W, axis=1)[:, ::-1][:, :4]
w4 = np.take_along_axis(W, top4, axis=1)
w4 /= w4.sum(axis=1, keepdims=True)
J4 = top4.astype(np.uint16)
W4 = w4.astype(np.float32)


def add_view(arr, target=None):
    while len(BIN) % 4:
        BIN.append(0)
    o = len(BIN)
    BIN.extend(arr.tobytes())
    v = {"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes}
    if target:
        v["target"] = target
    J["bufferViews"].append(v)
    return len(J["bufferViews"]) - 1


jv = add_view(J4, 34962)
wv = add_view(W4, 34962)
J["accessors"].append({"bufferView": jv, "componentType": 5123, "count": len(J4), "type": "VEC4"})
J["accessors"].append({"bufferView": wv, "componentType": 5126, "count": len(W4), "type": "VEC4"})
aj, aw = len(J["accessors"]) - 2, len(J["accessors"]) - 1
pr["attributes"]["JOINTS_0"] = aj
pr["attributes"]["WEIGHTS_0"] = aw

# ④ 骨骼节点 + skin（IBM = 逆平移）
base_nodes = len(J["nodes"])
bone_idx = {}
for n in names:
    # glTF 层级里子节点平移必须**相对父节点**；写绝对坐标会被逐级累加 ⇒ 绑定姿势全错
    par = PARENT[n]
    rel = pos[n] - (pos[par] if par else 0.0)
    J["nodes"].append({"name": "mixamorig:" + n, "translation": [float(x) for x in rel]})
    bone_idx[n] = base_nodes + len(bone_idx)
for n in names:
    ch = children[n]
    if ch:
        J["nodes"][bone_idx[n]]["children"] = [bone_idx[c] for c in ch]
ibms = []
for n in names:
    m = np.eye(4)
    m[:3, 3] = -pos[n]
    ibms.append(m.T.flatten().astype(np.float32))
ibm = np.array(ibms, np.float32)
iv = add_view(ibm)
J["accessors"].append({"bufferView": iv, "componentType": 5126, "count": len(ibm), "type": "MAT4"})
ai = len(J["accessors"]) - 1
J["skins"] = [{"name": "GBT_AutoRig", "joints": [bone_idx[n] for n in names], "inverseBindMatrices": ai, "skeleton": bone_idx["Hips"]}]
mesh_node = 0
J["nodes"][mesh_node]["skin"] = 0
J["nodes"].append({"name": "Armature", "children": [bone_idx["Hips"]]})
J["scenes"][0]["nodes"] = [mesh_node, len(J["nodes"]) - 1]
J["buffers"][0]["byteLength"] = len(BIN)


def write_glb(path, jj, bb):
    """规范 GLB 写出：JSON 块用空格补齐、BIN 块用零补齐到 4 字节 —— 不对齐会让加载器解析崩。"""
    js = json.dumps(jj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    body = bytearray(bb)
    while len(body) % 4:
        body.append(0)
    jj["buffers"][0]["byteLength"] = len(body)
    js = json.dumps(jj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                     + struct.pack("<I", len(js)) + b"JSON" + js
                     + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))


write_glb(OUT_RIG, J, BIN)
print(f"绑骨 GLB: {OUT_RIG.name} · {OUT_RIG.stat().st_size/1024/1024:.2f} MB · 关节 {len(names)} · skin {'有' if J.get('skins') else '无'}")

# ⑤ 姿态测试：LeftArm 子树绕深度轴(0)转 45°，CPU 形变


def subtree(n):
    out = [n]
    for c in children[n]:
        out += subtree(c)
    return out


pose = {}
h = pos["LeftArm"]
R = np.eye(4)
# 🔴 旋转轴必须是**深度轴**，且深度轴是**量出来的**（skeleton.json 的 axes.dep），不能写死 X：
#    本代网格做过定向归一（肩轴→X、正面→+Z），深度轴变成了 Z；写死 X 等于绕肩轴转，
#    手臂只会前后甩、不会抬起 —— 实测就是这么把"抬左臂"测成了看不出变化。
DEP = int(SK.get("axes", {}).get("dep", 0))
th = math.radians(45)
c_, s_ = math.cos(th), math.sin(th)
R[:3, :3] = np.eye(3)
if DEP == 0:
    R[:3, :3] = np.array([[1, 0, 0], [0, c_, -s_], [0, s_, c_]])
elif DEP == 1:
    R[:3, :3] = np.array([[c_, 0, s_], [0, 1, 0], [-s_, 0, c_]])
else:
    R[:3, :3] = np.array([[c_, -s_, 0], [s_, c_, 0], [0, 0, 1]])
M = np.eye(4)
M[:3, 3] = h
M[:3, :3] = R[:3, :3]
Mi = np.eye(4)
Mi[:3, 3] = -h
X = M @ Mi
affected = subtree("LeftArm")
Mv = np.zeros((len(names), 4, 4))
for n in names:
    Mv[names.index(n)] = X if n in affected else np.eye(4)
Pp = np.zeros_like(P)
for i in range(len(P)):
    v = np.append(P[i], 1.0)
    acc4 = np.zeros(4)
    for k in range(4):
        acc4 += w4[i, k] * (Mv[top4[i, k]] @ v)
    Pp[i] = acc4[:3]
J2 = json.loads(json.dumps(J))
# 注意：J2 是深拷贝，bufferView 必须写进 J2 自己（用全局 add_view 会导致 accessor 指向不存在的索引）
while len(BIN) % 4:
    BIN.append(0)
_po = len(BIN)
_pb = Pp.astype(np.float32).tobytes()
BIN.extend(_pb)
J2["bufferViews"].append({"buffer": 0, "byteOffset": _po, "byteLength": len(_pb), "target": 34962})
pa = len(J2["bufferViews"]) - 1
J2["accessors"].append({"bufferView": pa, "componentType": 5126, "count": len(Pp), "type": "VEC3"})
J2["meshes"][0]["primitives"][0]["attributes"]["POSITION"] = len(J2["accessors"]) - 1
J2["meshes"][0]["primitives"][0]["attributes"].pop("JOINTS_0", None)
J2["meshes"][0]["primitives"][0]["attributes"].pop("WEIGHTS_0", None)
J2.pop("skins", None)                      # 静态测试件不是蒙皮网格：skin 引用必须一起去掉，否则加载器拒绝
J2["nodes"][0].pop("skin", None)
write_glb(OUT_POSE, J2, BIN)
d = np.linalg.norm(Pp - P, axis=1)
print(f"姿态测试（抬左臂 45°）：受影响顶点 {int((d > 1e-4).sum())} · 最大位移 {d.max():.3f} · 输出 {OUT_POSE.name}")
