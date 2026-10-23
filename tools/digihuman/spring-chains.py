# -*- coding: utf-8 -*-
"""把 7 根弹簧骨升级为 **2 关节链**（根 + 尖），并按高度把权重从"单骨"劈给根/尖。

为什么必须做（VRMC_springBone 规范，Round 2 抓取）：
- `springs[*].joints[n]` 必须是 `joints[n+1]` 的**祖先**；**链尾关节只当尾巴用**；
- ⇒ **单关节链在 VRM 运行时里不会动**（我们原先是单关节）。
附带修一个潜在缺陷：弹簧骨原先把**世界坐标**写进了 `translation`（子节点应相对父节点）——一并修正。

输入 raw/rig/model-springs-hair.glb → 输出 raw/rig/model-springs-chains.glb
"""
from __future__ import annotations

import json
import pathlib
import struct

WS = pathlib.Path(__file__).resolve().parents[2]
RIG = WS / "holo_pet/assets/digital-human/raw/rig"
SRC = RIG / "model-springs-hair.glb"
OUT = RIG / "model-springs-chains.glb"
SPRINGS = ("SkirtF", "SkirtB", "SkirtL", "SkirtR", "HairB", "HairL", "HairR")


def load(p):
    raw = p.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, bytearray(raw[off + 8: off + 8 + bl])


def write(p, J, BIN):
    body = bytearray(BIN)
    while len(body) % 4:
        body.append(0)
    J["buffers"][0]["byteLength"] = len(body)
    js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    p.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                  + struct.pack("<I", len(js)) + b"JSON" + js
                  + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))


def add_accessor(J, BIN, arr, ctype, typ, target=None):
    import array
    a = array.array({5126: "f", 5123: "H", 5125: "I"}[ctype], arr)
    while len(BIN) % 4:
        BIN.append(0)
    off = len(BIN)
    BIN.extend(a.tobytes())
    J["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": a.itemsize * len(a),
                             **({"target": target} if target else {})})
    J["accessors"].append({"bufferView": len(J["bufferViews"]) - 1, "componentType": ctype,
                           "count": len(arr) // {"VEC4": 4, "MAT4": 16, "SCALAR": 1}[typ], "type": typ})
    return len(J["accessors"]) - 1


def main():
    J, BIN = load(SRC)
    nodes = J["nodes"]
    names = [n.get("name", "") for n in nodes]
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children") or []:
            parent[c] = i
    # 世界坐标 + 父节点世界坐标
    world = {}

    def wpos(i):
        if i in world:
            return world[i]
        t = nodes[i].get("translation", [0, 0, 0])
        p = parent.get(i)
        w = [t[0], t[1], t[2]] if p is None else [t[k] + wpos(p)[k] for k in range(3)]
        world[i] = w
        return w

    prim = J["meshes"][0]["primitives"][0]
    a_j = J["accessors"][prim["attributes"]["JOINTS_0"]]
    a_w = J["accessors"][prim["attributes"]["WEIGHTS_0"]]
    a_p = J["accessors"][prim["attributes"]["POSITION"]]
    nv = a_p["count"]
    bv = {k: J["bufferViews"][acc["bufferView"]] for k, acc in (("j", a_j), ("w", a_w), ("p", a_p))}
    import array
    JT = array.array("H"); JT.frombytes(bytes(BIN[bv["j"].get("byteOffset", 0): bv["j"].get("byteOffset", 0) + nv * 8]))
    WT = array.array("f"); WT.frombytes(bytes(BIN[bv["w"].get("byteOffset", 0): bv["w"].get("byteOffset", 0) + nv * 16]))
    P = array.array("f"); P.frombytes(bytes(BIN[bv["p"].get("byteOffset", 0): bv["p"].get("byteOffset", 0) + nv * 12]))
    JMAP = {n: i for i, n in enumerate(J["skins"][0]["joints"])}     # 节点号 → joints 下标
    N_OLD = len(J["skins"][0]["joints"])
    base = len(nodes)
    made = []
    for k, sn in enumerate(SPRINGS):
        idx = next((i for i, nm in enumerate(names) if nm.split(":")[-1] == sn), None)
        if idx is None:
            continue
        ex = (nodes[idx].get("extras") or {}).get("springBone") or {}
        head = wpos(idx)                                      # 原 translation 世界值
        tail = ex.get("tail") or [head[0], head[1] - 0.07, head[2]]
        pid = parent.get(idx, 0)
        pw = wpos(pid)
        # 根节点：translation 改为**相对父节点**
        nodes[idx]["translation"] = [head[c] - pw[c] for c in range(3)]
        nodes[idx].setdefault("extras", {})["springBone"] = {**ex, "role": "root"}
        # 尖节点：child of root，local = tail - head
        nodes.append({"name": f"mixamorig:{sn}_Tip",
                      "translation": [tail[c] - head[c] for c in range(3)],
                      "extras": {"springBone": {"role": "tip", "stiffness": ex.get("stiffness", 0.2),
                                                "dragForce": ex.get("dragForce", 0.3),
                                                "gravityPower": ex.get("gravityPower", 0.3),
                                                "hitRadius": ex.get("hitRadius", 0.01),
                                                "tail": tail}}})
        nodes[idx].setdefault("children", []).append(base + k)
        made.append({"name": sn, "root": idx, "tip": base + k, "jid_root": JMAP[idx], "jid_tip": N_OLD + k,
                     "head": head, "tail": tail, "ex": ex})
    # 权重按高度劈给根/尖
    changed = 0
    for v in range(nv):
        for s in made:
            jt, wt = s["jid_root"], s["jid_tip"]
            for c in range(4):
                if JT[v * 4 + c] == jt and WT[v * 4 + c] > 0:
                    y = P[v * 3 + 1]
                    span = max(1e-6, s["head"][1] - s["tail"][1])
                    t = min(1.0, max(0.0, (s["head"][1] - y) / span))
                    w = WT[v * 4 + c]
                    # 上段(t<0.5)→根，下段→尖（按 t 线性劈）
                    WT[v * 4 + c] = w * (1 - t)
                    # 找一个空槽放尖
                    for c2 in range(4):
                        if WT[v * 4 + c2] == 0 and JT[v * 4 + c2] == JT[v * 4 + (c2)] and c2 != c:
                            JT[v * 4 + c2] = jt      # 复用空槽（先放尖的 joints）
                            WT[v * 4 + c2] = w * t
                            break
                    changed += 1
                    break
    jacc = add_accessor(J, BIN, list(JT), 5123, "VEC4", 34962)
    wacc = add_accessor(J, BIN, list(WT), 5126, "VEC4", 34962)
    prim["attributes"]["JOINTS_0"] = jacc
    prim["attributes"]["WEIGHTS_0"] = wacc
    J["skins"][0]["joints"] += [s["tip"] for s in made]
    # IBM：尖 = head=tail 的逆平移
    import numpy as np
    a = J["accessors"][J["skins"][0]["inverseBindMatrices"]]
    b = J["bufferViews"][a["bufferView"]]
    ibm = np.frombuffer(bytes(BIN), np.float32, a["count"] * 16, b.get("byteOffset", 0)).reshape(-1, 16).tolist()
    for s in made:
        m = np.eye(4, dtype=np.float32); m[:3, 3] = [-c for c in s["tail"]]
        ibm.append([float(x) for x in m.T.flatten()])
    iv = add_accessor(J, BIN, [x for row in ibm for x in row], 5126, "MAT4")
    J["accessors"][iv]["count"] = len(ibm)
    J["skins"][0]["inverseBindMatrices"] = iv
    write(OUT, J, BIN)
    print(f"升级 {len(made)} 根 → 2 关节链 · 改动顶点影响 {changed} 处")
    print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · 关节 {len(J['skins'][0]['joints'])}")


if __name__ == "__main__":
    main()
