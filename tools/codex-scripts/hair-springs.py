# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""头发弹簧骨 3 根（后/左/右），父骨=Head；区域**剔除面部**（脸在 +X）。
口径沿用已验证结论：① joins 下标（joints 下标≠节点号）② 根部与父骨混权 ③ 参数写进 extras。
输入 raw/rig/model-springs-both.glb（已有 4 根裙摆弹簧骨）→ 输出 raw/rig/model-springs-hair.glb"""
import json
import pathlib
import struct
import numpy as np

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
SRC = DH / "raw/rig/model-springs-both.glb"
OUT = DH / "raw/rig/model-springs-hair.glb"

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
parent_of = {}
for k, n in enumerate(J["nodes"]):
    for c in n.get("children") or []:
        parent_of[c] = k
world = {}
for i, n in enumerate(J["nodes"]):
    if not (n.get("name") or "").startswith("mixamorig"):
        continue
    chain, cur, g = [], i, 0
    while cur is not None and cur not in world:
        chain.append(cur)
        cur = parent_of.get(cur)
        g += 1
        if g > 200:
            raise SystemExit("环")
    w = world[cur] if cur is not None else np.zeros(3)
    for nd in reversed(chain):
        w = w + np.array(J["nodes"][nd].get("translation", [0, 0, 0]), np.float64)
        world[nd] = w
head_i = names.index("mixamorig:Head")
neck_y = world[names.index("mixamorig:Neck")][1]
hc = world[head_i]
print(f"Head 世界位 {np.round(hc, 3)} · 颈 y={neck_y:.3f}")

HAIR = {  # 方向 → (head 偏移, tail 偏移)
    "HairB": (np.array([-0.045, 0.030, 0.0]), np.array([-0.080, -0.055, 0.0])),
    "HairL": (np.array([0.005, 0.030, 0.055]), np.array([0.005, -0.045, 0.080])),
    "HairR": (np.array([0.005, 0.030, -0.055]), np.array([0.005, -0.045, -0.080])),
}
N_OLD = len(J["skins"][0]["joints"])
JMAP = {n: i for i, n in enumerate(J["skins"][0]["joints"])}
new = []
base = len(J["nodes"])
for k, (nm, (ho, to)) in enumerate(HAIR.items()):
    head = hc + ho
    tail = hc + to
    J["nodes"].append({"name": "mixamorig:" + nm, "translation": [float(x) for x in head],
                       "extras": {"springBone": {"stiffness": 0.25, "dragForce": 0.45,
                                                 "gravityPower": 0.35, "hitRadius": 0.01,
                                                 "tail": [float(x) for x in tail]}}})
    J["nodes"][head_i].setdefault("children", []).append(base + k)
    new.append({"name": nm, "idx": base + k, "jid": N_OLD + k, "head": head, "tail": tail})


def seg_d(V, a, b):
    ab = b - a
    t = np.clip(((V - a) @ ab) / max(1e-12, ab @ ab), 0, 1)
    return np.linalg.norm(V - (a + t[:, None] * ab), axis=1)


# 区域：颈线以上，且**剔面部**（脸在 +X）
in_hair = (P[:, 1] > neck_y + 0.03) & ((P[:, 0] < 0.02) | (np.abs(P[:, 2]) > 0.05))
D = np.stack([seg_d(P, b["head"], b["tail"]) for b in new], axis=1)
pick = np.argmin(D, axis=1)
print(f"头发区顶点 {int(in_hair.sum())} / {len(P)}")
JT2, WT2 = JT.copy(), WT.copy()
hi_j = JMAP[head_i]
changed = 0
for i in np.where(in_hair)[0]:
    y_root = hc[1] + 0.030
    t = float(np.clip((y_root - P[i, 1]) / max(1e-6, (y_root - (hc[1] - 0.055))), 0, 1))
    if t <= 0.05:
        continue
    JT2[i] = [new[int(pick[i])]["jid"], hi_j, 0, 0]
    WT2[i] = [t, 1.0 - t, 0.0, 0.0]
    changed += 1
print(f"改权顶点 {changed}")


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
J["skins"][0]["joints"] = J["skins"][0]["joints"] + [b["idx"] for b in new]
a = J["accessors"][J["skins"][0]["inverseBindMatrices"]]
bv = J["bufferViews"][a["bufferView"]]
ibm = np.frombuffer(bytes(BIN), np.float32, a["count"] * 16, bv.get("byteOffset", 0)).reshape(-1, 16).copy()
for b in new:
    m = np.eye(4, dtype=np.float32)
    m[:3, 3] = -b["head"]
    ibm = np.vstack([ibm, m.T.flatten()])
iv = add_view(ibm)
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
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · 关节 {len(J['skins'][0]['joints'])}（+{len(new)} 发骨）")
