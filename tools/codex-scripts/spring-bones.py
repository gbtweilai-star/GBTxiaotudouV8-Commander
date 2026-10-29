# -*- coding: utf-8 -*-
"""次级动力学 ①加骨 ②区域重权：给低模全身件加 **4 根裙摆弹簧骨**（前/后/左/右），
根部与 Hips **混权**（0→1 渐变，防根部撕裂）—— 口径来自 VRMC_springBone-1.0（见技能 pitfalls §11）。
区域判据（实测）：y ∈ [髋 −0.03, 裙摆底 −0.23]，且**距腿轴 > 腿半径**（剔腿）。
输出：raw/rig/model-springs.glb（新增 4 骨 · 原 22 骨与动画保持不变）"""
import json
import pathlib
import struct
import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
import sys  # noqa: E402
MODE = sys.argv[1] if len(sys.argv) > 1 else "both"
SRC = DH / "raw/rig/model-rigged-anim.glb"
OUT = DH / f"raw/rig/model-springs-{MODE}.glb"
Y_ROOT, Y_TIP = -0.030, -0.230          # 裙摆区（实测 Hips −0.024 / 膝 −0.260）
LEG_Z = 0.041                            # 左右腿轴（实测）
LEG_R = 0.055                            # 腿半径（剔腿阈值）

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
pr = J["meshes"][0]["primitives"][0]


def acc(i, comps, dt=np.float64):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), t, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps).astype(dt)


P = acc(pr["attributes"]["POSITION"], 3)
JT = acc(pr["attributes"]["JOINTS_0"], 4).astype(np.int64)
WT = acc(pr["attributes"]["WEIGHTS_0"], 4)
names = [n.get("name", "") for n in J["nodes"]]
hips_i = names.index("mixamorig:Hips")
base = len(J["nodes"])
# 4 个方向：前(+X) 后(-X) 左(+Z) 右(-Z)
DIRS = {"SkirtF": np.array([1, 0, 0.0]), "SkirtB": np.array([-1, 0, 0.0]),
        "SkirtL": np.array([0, 0, 1.0]), "SkirtR": np.array([0, 0, -1.0])}
new_bones = []
N_OLD = len(J["skins"][0]["joints"])          # joints 数组原长度（新增骨在其中的下标从它开始）
for k, (nm, d) in enumerate(DIRS.items()):
    head = d * 0.085 + np.array([0, Y_ROOT, 0])
    tail = d * 0.10 + np.array([0, Y_TIP, 0])
    if MODE == "weights":
        new_bones.append({"name": nm, "idx": hips_i, "dir": d, "head": head, "tail": tail})
        continue
    J["nodes"].append({"name": "mixamorig:" + nm, "translation": [float(x) for x in head],
                       "extras": {"springBone": {"stiffness": 0.18, "dragForce": 0.30,
                                                 "gravityPower": 0.30, "hitRadius": 0.01,
                                                 "tail": [float(x) for x in tail]}}})
    J["nodes"][hips_i].setdefault("children", []).append(base + k)
    new_bones.append({"name": nm, "idx": base + k, "jid": N_OLD + k, "dir": d, "head": head, "tail": tail})
print(f"新增 {len(new_bones)} 根弹簧骨：{[b['name'] for b in new_bones]}")

# ② 区域重权：裙摆顶点 = y 带内 且 距腿轴 > 腿半径
leg_axis = np.stack([P[:, 2] - LEG_Z, P[:, 2] + LEG_Z], axis=1)          # 到左右腿轴（z 方向）的距离
d_leg = np.abs(leg_axis).min(axis=1)
in_band = (P[:, 1] <= Y_ROOT) & (P[:, 1] >= Y_TIP) & (d_leg > LEG_R)
print(f"裙摆区顶点：{int(in_band.sum())} / {len(P)}（y∈[{Y_TIP},{Y_ROOT}] 且距腿>{LEG_R}）")
t = np.clip((Y_ROOT - P[:, 1]) / (Y_ROOT - Y_TIP), 0, 1)                # 根 0 → 摆 1
# 选方向：投影到 4 个方向里最接近的
proj = np.stack([P[:, 0] * d[0] + P[:, 2] * d[2] for d in DIRS.values()], axis=1)
pick = np.argmax(proj, axis=1)
JMAP = {node: pos for pos, node in enumerate(J["skins"][0]["joints"])}   # 节点号 → joints 下标
JT2, WT2 = JT.copy(), WT.copy()
changed = 0
for i in np.where(in_band)[0]:
    w = float(t[i])
    if w <= 0.02:
        continue
    b = new_bones[int(pick[i])]["jid"]        # joints 下标（不是节点号）
    # 新权重 = [弹簧骨 w, Hips 1-w]，其余清空（区域小，够用且不撕裂）
    if MODE == "bones":
        continue
    JT2[i] = [b, JMAP[hips_i], 0, 0]
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
J["skins"][0]["joints"] = J["skins"][0]["joints"] + [b["idx"] for b in new_bones]
# IBM：弹簧骨静止位 = 其 head 的逆平移（骨骼写的是 head 的世界平移）
a = J["accessors"][J["skins"][0]["inverseBindMatrices"]]
bv = J["bufferViews"][a["bufferView"]]
ibm = np.frombuffer(bytes(BIN), np.float32, a["count"] * 16, bv.get("byteOffset", 0)).reshape(-1, 16).copy()
for b in new_bones:
    m = np.eye(4, dtype=np.float32)
    m[:3, 3] = -b["head"]
    ibm = np.vstack([ibm, m.T.flatten()])
iv = add_view(ibm, None)
J["accessors"].append({"bufferView": iv, "componentType": 5126, "count": len(ibm), "type": "MAT4"})
J["skins"][0]["inverseBindMatrices"] = len(J["accessors"]) - 1

body = bytearray(BIN)
while len(body) % 4:
    body.append(0)
J["buffers"][0]["byteLength"] = len(body)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · 关节 {len(J['skins'][0]['joints'])}")
