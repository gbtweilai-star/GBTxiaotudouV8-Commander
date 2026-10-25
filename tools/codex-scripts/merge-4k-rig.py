# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""把骨架/蒙皮搬到 **4K 贴图版**高模上（顶点顺序与 UV 与旧件逐一相同 ⇒ 直接搬，不重算）。
来源：raw/rig/model-rigged-hi.glb（含 bones + skin + JOINTS_0/WEIGHTS_0）
底子：4K 重贴后的 model.glb（4096² PNG 贴图）
输出：raw/rig/model-rigged-4k.glb（4K 贴图 + 22 骨 + 蒙皮）"""
import json
import pathlib
import struct
import numpy as np

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
RIG = DH / "raw/rig/model-rigged-hi.glb"
BASE = DH / "raw/phase4-4k/tripo-out/gbt-4k-tex-convert-0d1f0aa6/model.glb"
OUT = DH / "raw/rig/model-rigged-4k.glb"


def load(p):
    raw = p.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, bytearray(raw[off + 8: off + 8 + bl])


JR, BR = load(RIG)
JB, BB = load(BASE)
pr_r = JR["meshes"][0]["primitives"][0]
pr_b = JB["meshes"][0]["primitives"][0]


def acc(J, BIN, i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), dt, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps)


# ① 先验证顶点一致（不同就拒绝，不硬干）
n_r = JR["accessors"][pr_r["attributes"]["POSITION"]]["count"]
n_b = JB["accessors"][pr_b["attributes"]["POSITION"]]["count"]
# 🔴 2026-09-25 清掉一句死表达式：原来第二个合取项末尾写着 `or True` ⇒ 那一项**恒真、等于没写**
#    （`dead_judgments` 审计器点出来的）。它显然是想再验一条"POSITION accessor 指向同一处"，
#    但**从来没实现**。这里如实收成"只看顶点数一致"，并把"那条没实现"写下来 ——
#    免得下一个人以为搬之前已经验过 accessor 归属。**行为逐字节不变**（原式恒等于 `n_r == n_b`）。
same = (n_r == n_b)   # NOTE: 原计划还有一条 accessor 归属校验，**未实现**；本行只判顶点数
print(f"顶点 {n_r} vs {n_b} ⇒ {'一致，可直搬' if n_r == n_b else '不一致，停'}")
if n_r != n_b:
    raise SystemExit(1)

# ② 把 JOINTS_0 / WEIGHTS_0 的数据搬进 4K 底子
JT = acc(JR, BR, pr_r["attributes"]["JOINTS_0"], 4).astype(np.uint16)
WT = acc(JR, BR, pr_r["attributes"]["WEIGHTS_0"], 4).astype(np.float32)


def add_view(BIN, arr, target=None):
    while len(BIN) % 4:
        BIN.append(0)
    o = len(BIN)
    BIN.extend(arr.tobytes())
    v = {"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes}
    if target:
        v["target"] = target
    JB["bufferViews"].append(v)
    return len(JB["bufferViews"]) - 1


jv = add_view(BB, JT, 34962)
wv = add_view(BB, WT, 34962)
JB["accessors"].append({"bufferView": jv, "componentType": 5123, "count": len(JT), "type": "VEC4"})
JB["accessors"].append({"bufferView": wv, "componentType": 5126, "count": len(WT), "type": "VEC4"})
pr_b["attributes"]["JOINTS_0"] = len(JB["accessors"]) - 2
pr_b["attributes"]["WEIGHTS_0"] = len(JB["accessors"]) - 1

# ③ 搬骨骼节点 + skin（层级按名字重建，避免索引错位）
bone_src = [i for i, n in enumerate(JR["nodes"]) if (n.get("name") or "").startswith("mixamorig")]
base = len(JB["nodes"])
name2new = {}
for i in bone_src:
    src = JR["nodes"][i]
    new = {"name": src["name"], "translation": src["translation"]}
    if "rotation" in src:
        new["rotation"] = src["rotation"]
    if "scale" in src:
        new["scale"] = src["scale"]
    JB["nodes"].append(new)
    name2new[src["name"]] = base + len(name2new)
for i in bone_src:
    src = JR["nodes"][i]
    kids = [name2new[JR["nodes"][c]["name"]] for c in (src.get("children") or []) if (JR["nodes"][c].get("name") or "").startswith("mixamorig")]
    if kids:
        JB["nodes"][name2new[src["name"]]]["children"] = kids

sk_r = JR["skins"][0]
a = JR["accessors"][sk_r["inverseBindMatrices"]]
bv = JR["bufferViews"][a["bufferView"]]
ibm = np.frombuffer(bytes(BR), np.float32, a["count"] * 16, bv.get("byteOffset", 0)).reshape(-1, 16)
iv = add_view(BB, ibm)
JB["accessors"].append({"bufferView": iv, "componentType": 5126, "count": len(ibm), "type": "MAT4"})
JB["skins"] = [{"name": "GBT_AutoRig", "joints": [name2new[JR["nodes"][i]["name"]] for i in sk_r["joints"]],
                "inverseBindMatrices": len(JB["accessors"]) - 1,
                "skeleton": name2new[JR["nodes"][sk_r["joints"][0]]["name"]]}]
JB["nodes"][0]["skin"] = 0
JB["nodes"].append({"name": "Armature", "children": [JB["skins"][0]["skeleton"]]})
JB["scenes"][0]["nodes"] = [0, len(JB["nodes"]) - 1]

# ④ 规范写出
body = bytearray(BB)
while len(body) % 4:
    body.append(0)
JB["buffers"][0]["byteLength"] = len(body)
js = json.dumps(JB, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · 关节 {len(bone_src)} · 贴图保持 4K 原件")
