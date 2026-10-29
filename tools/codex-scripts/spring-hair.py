# -*- coding: utf-8 -*-
"""次级动力学 · **头发弹簧链**（不写死坐标版）

为什么要重写（2026-09-25 实测）：
  仓里既有 `spring-bones.py` 的裙摆坐标是**写死给上一代模型**的 ——
  `Y_ROOT/Y_TIP = -0.030/-0.230`、`LEG_Z = 0.041`、方向表还是"前=+X"。
  本代网格做过定向归一（**正面 → +Z、肩轴 → X**），拿旧表跑必然整片错位；
  而且本角色是长头发、没有裙摆，次级动力学真正该绑的是**头发**。
  所以这里改成**从数据里认**：谁是头发，由**蒙皮权重**说了算（主导骨 = Head 且低于头关节），
  链的朝向往哪偏，由**顶点质心**说了算 —— 全程不写一个坐标常数。

用法：
  python tools/codex-scripts/spring-hair.py <绑骨.glb> <输出.glb> [链数=4]
退出码：0 = 写出且自检通过；1 = 自检不过。
"""
import json
import pathlib
import struct
import sys

import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-rigged.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/avatar-springs.glb"
CHAINS = int(sys.argv[3]) if len(sys.argv) > 3 else 4

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
pr = J["meshes"][0]["primitives"][0]


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), t, a["count"] * comps,
                         bv.get("byteOffset", 0)).reshape(a["count"], comps)


P = acc(pr["attributes"]["POSITION"], 3).astype(np.float64)
JT = acc(pr["attributes"]["JOINTS_0"], 4).astype(np.int64)
WT = acc(pr["attributes"]["WEIGHTS_0"], 4).astype(np.float64)
names = [n.get("name", "") for n in J["nodes"]]
skin = J["skins"][0]
joints = skin["joints"]
jid2name = {i: names[node] for i, node in enumerate(joints)}
print(f"网格 {len(P)} 顶点 · 关节 {len(joints)}")


def node_of(name):
    for i, node in enumerate(joints):
        if names[node] == name:
            return i
    raise SystemExit(f"🔴 找不到关节 {name}")


HIPS, HEAD = node_of("mixamorig:Hips"), node_of("mixamorig:Head")
# 关节世界位置：从 IBM 取逆平移（rig 写出时 IBM = 逆平移，干净可验）
a = J["accessors"][skin["inverseBindMatrices"]]
bv = J["bufferViews"][a["bufferView"]]
ibm = np.frombuffer(bytes(BIN), np.float32, a["count"] * 16,
                    bv.get("byteOffset", 0)).reshape(-1, 4, 4)
# glTF 的矩阵访问器是**列主序**：rig 写出时把 row-major 的 m.T 直接铺开，
#    所以按 (4,4) 读回来得到的是 m.T，平移落在 **[3, :3]**（实测读 [:3,3] 会得到全 0，
#    于是头关节 y 读成 0.000、头发候选 0 个 —— 这个坑先踩为敬）。
jpos = {i: -ibm[i][3, :3].astype(np.float64) for i in range(len(joints))}
head_pos = jpos[HEAD]
y_head = head_pos[1]
y_bot = P[:, 1].min()
H = P[:, 1].max() - y_bot
print(f"头关节 y={y_head:+.3f} · 身高 {H:.3f}")

# ① 认头发
# 判据演进（实测）：只按"主导骨 == Head"认，只能捞到**颅底薄薄一带 213 个顶点** ——
#    因为长发垂在后背/肩上时，离 Neck/Spine1 的骨段更近，主导骨根本不在 Head。
#    现实口径：**主导骨 ∈ {Head, Neck, Spine1}**（头颈胸这一段）＋ 低于头关节
#    ＋ **离脊柱竖轴够远**（把脖子/后颈自身的表面排除，否则脖子会被拉成面条）。
slot = np.argmax(WT, axis=1)
dom = np.take_along_axis(JT, slot[:, None], axis=1).ravel()
IDX_TRUNK = [i for i, nd in enumerate(joints)
             if names[nd] in ("mixamorig:Head", "mixamorig:Neck", "mixamorig:Spine1")]
rad = np.hypot(P[:, 0] - head_pos[0], P[:, 2] - head_pos[2])
RAD_MIN = 0.045
hair = np.isin(dom, IDX_TRUNK) & (P[:, 1] < y_head - 0.01 * H) & (rad > RAD_MIN)
print(f"头发候选：{int(hair.sum())} / {len(P)} 顶点（主导骨=Head 且 y < 头关节）")
if hair.sum() < 50:
    print("🔴 头发候选太少 ⇒ 停止（宁缺不糊）")
    raise SystemExit(1)
Hp = P[hair]
y_low = np.percentile(Hp[:, 1], 2)
print(f"  头发 y 范围 {Hp[:, 1].min():+.3f} .. {Hp[:, 1].max():+.3f}（2 分位 {y_low:+.3f}）")

# ② 按**绕头竖轴的方位角**分链（方位角从数据算，不用"前后左右"这种写死标签）
ang = np.arctan2(Hp[:, 0] - head_pos[0], Hp[:, 2] - head_pos[2])
sector = ((ang + np.pi) / (2 * np.pi) * CHAINS).astype(int) % CHAINS
base_node = len(J["nodes"])
N_OLD = len(joints)
new = []
for s in range(CHAINS):
    sel = Hp[sector == s]
    if len(sel) < 20:
        print(f"  扇区 {s}: 顶点 {len(sel)} 太少，跳过")
        continue
    tip = np.array([sel[:, 0].mean(), np.percentile(sel[:, 1], 2), sel[:, 2].mean()])
    root = np.array([head_pos[0], y_head, head_pos[2]], np.float64)
    nm = f"Hair{s}"
 # translation 必须**相对父节点（Head）**：写成绝对坐标会被父级再累加一次，
    #    骨子跑到头顶上方（实测包围盒高度 1.000 → 1.086、中心上移 0.043）。
    #    IBM 仍用**绝对** root 的逆平移 —— 两者口径不同，别混。
    rel = root - head_pos
    J["nodes"].append({"name": "mixamorig:" + nm,
                       "translation": [float(x) for x in rel],
                       "extras": {"springBone": {"stiffness": 0.14, "dragForce": 0.35,
                                                 "gravityPower": 0.30, "hitRadius": 0.012,
                                                 "tail": [float(x) for x in tip]}}})
    J["nodes"][joints[HEAD]].setdefault("children", []).append(base_node + len(new))
    new.append({"name": nm, "node": base_node + len(new), "jid": N_OLD + len(new),
                "sector": s, "root": root, "tip": tip, "n": len(sel)})
    print(f"  {nm}: {len(sel)} 顶点 · 根 y={root[1]:+.3f} → 尖 y={tip[1]:+.3f} · "
          f"水平落点 ({tip[0]:+.3f},{tip[2]:+.3f})")
if not new:
    print("🔴 一条链都没建起来")
    raise SystemExit(1)

# ③ 重权：弹簧权重 = 沿链的深度（根 0 → 尖 1），其余留给 Head ⇒ 根部不撕
JMAP = {node: i for i, node in enumerate(joints)}
JT2, WT2 = JT.copy(), WT.copy()
span = max(1e-6, y_head - y_low)
changed = 0
for i in np.where(hair)[0]:
    depth = float(np.clip((y_head - P[i, 1]) / span, 0.0, 1.0))
    w = depth ** 1.5 * 0.9                      # 根附近几乎不动，尖端跟着飘
    if w <= 0.02:
        continue
    # 归到"方位角最近"的那条链
    a_i = np.arctan2(P[i, 0] - head_pos[0], P[i, 2] - head_pos[2])
    s_i = int(((a_i + np.pi) / (2 * np.pi) * CHAINS) % CHAINS)
    ch = next((c for c in new if c["sector"] == s_i), new[0])
    JT2[i] = [ch["jid"], JMAP[HEAD], 0, 0]
    WT2[i] = [w, 1.0 - w, 0.0, 0.0]
    changed += 1
print(f"改权顶点：{changed}")


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


jv = add_view(JT2.astype(np.uint16), 34962)
wv = add_view(WT2.astype(np.float32), 34962)
J["accessors"].append({"bufferView": jv, "componentType": 5123, "count": len(JT2), "type": "VEC4"})
J["accessors"].append({"bufferView": wv, "componentType": 5126, "count": len(WT2), "type": "VEC4"})
pr["attributes"]["JOINTS_0"] = len(J["accessors"]) - 2
pr["attributes"]["WEIGHTS_0"] = len(J["accessors"]) - 1
skin["joints"] = joints + [c["node"] for c in new]
ibm2 = np.vstack([ibm.reshape(-1, 16),
                  np.zeros((len(new), 16), np.float32)])   # 新骨的 IBM 逐条填，注意是 16 列
for k, c in enumerate(new):
    m = np.eye(4, dtype=np.float32)
    m[:3, 3] = -c["root"]
    ibm2[len(ibm) + k] = m.T.flatten()
iv = add_view(ibm2.astype(np.float32))
J["accessors"].append({"bufferView": iv, "componentType": 5126, "count": len(ibm2), "type": "MAT4"})
skin["inverseBindMatrices"] = len(J["accessors"]) - 1

body = bytearray(BIN)
while len(body) % 4:
    body.append(0)
J["buffers"][0]["byteLength"] = len(body)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))

# 自检：关节数 = 旧+新 · 权重和 = 1 · 新骨确实进了 joints 且 IBM 数对得上
ws = WT2.sum(axis=1)
bad = []
if len(skin["joints"]) != N_OLD + len(new):
    bad.append(f"关节数不符 {len(skin['joints'])} vs {N_OLD + len(new)}")
if abs(ws.min() - 1) > 1e-3 or abs(ws.max() - 1) > 1e-3:
    bad.append(f"权重和 {ws.min():.4f}~{ws.max():.4f}")
if len(ibm2) != len(skin["joints"]):
    bad.append("IBM 条数与关节数不符")
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB · 关节 {len(skin['joints'])}"
      f"（新增 {len(new)} 根弹簧骨）· 权重和 {ws.min():.4f}~{ws.max():.4f}")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print("✅ 自检通过（关节/权重/IBM 三项一致）")
