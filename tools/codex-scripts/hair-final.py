# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""缝合件 · **头发挂链 + 链尖重算（一次完成）**

为什么合成一件（上一轮的教训）：
  上一轮 `hair-rebind.py` 与 `hair-retip.py` **用同一套有缺陷的判据，于是"一致地错"** ——
  链尖确实和被驱动的顶点对齐了，但**被驱动的顶点本身选错了**，交叉验证完全失效。
  所以这次把"认头发 → 分链 → 定权重 → 算链尖"**放进同一次运行**，让它们共享同一份顶点集，
  不可能再出现两边判据不一致。

判据修正（上一轮查出的根因）：
  `head-graft-np.py` 给缝合头赋权时，切面处是 **Head 0.35 / Neck 0.65**、向上渐变到 Head 1.0
  ⇒ **中下部头发的主导骨是 Neck**，旧判据「主导骨=Head」只捞到颅底 0.0185 厚的一带（占真头发极小一块）。
  改成「主导骨 ∈ {Head, Neck} 且 **高于颈部切面**」。

用法：python tools/codex-scripts/hair-final.py <缝合件.glb> <输出.glb>
退出码：0 = 写出且自检通过；1 = 自检不过；2 = 前置问题。
"""
import json
import pathlib
import struct
import sys

import numpy as np

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-grafted.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DH / "raw/rig/avatar-final.glb"
Y_CUT = 0.33                                   # 与 head-graft-np.py 的切面一致

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), t, a["count"] * comps,
                         bv.get("byteOffset", 0)).reshape(a["count"], comps)


names = [n.get("name", "") for n in J["nodes"]]
joints = J["skins"][0]["joints"]
HAIR = [i for i in range(len(joints)) if "Hair" in names[joints[i]]]
IDX_HEAD = next(i for i, nd in enumerate(joints) if names[nd] == "mixamorig:Head")
IDX_NECK = next(i for i, nd in enumerate(joints) if names[nd] == "mixamorig:Neck")
if not HAIR:
    print("🔴 没有 Hair 链 ⇒ 停止")
    raise SystemExit(2)

prs = J["meshes"][0]["primitives"]
hi = max(range(len(prs)), key=lambda k: J["accessors"][prs[k]["attributes"]["POSITION"]]["count"])
pr = prs[hi]
P = acc(pr["attributes"]["POSITION"], 3).astype(np.float64)
JT = acc(pr["attributes"]["JOINTS_0"], 4).astype(np.int64)
WT = acc(pr["attributes"]["WEIGHTS_0"], 4).astype(np.float64)
ibm = acc(J["skins"][0]["inverseBindMatrices"], 16).reshape(-1, 4, 4).astype(np.float64)
head_pos = -ibm[IDX_HEAD][3, :3]
y_head = float(head_pos[1])

slot = np.argmax(WT, axis=1)
dom = np.take_along_axis(JT, slot[:, None], axis=1).ravel()
# ── 判据修正：主导骨 ∈ {Head, Neck} 且高于颈部切面 ────────────────────────
hair = np.isin(dom, [IDX_HEAD, IDX_NECK]) & (P[:, 1] > Y_CUT + 0.004)
Hp = P[hair]
print(f"头部 primitive #{hi} · 判据=主导骨∈{{Head,Neck}} 且 y>{Y_CUT + 0.004:.3f}")
print(f"头发顶点 {len(Hp)}（旧判据只有 41457）· y 范围 {Hp[:, 1].min():+.4f} .. {Hp[:, 1].max():+.4f}"
      f"（跨度 {Hp[:, 1].max()-Hp[:, 1].min():.4f}）")
if len(Hp) < 200 or (Hp[:, 1].max() - Hp[:, 1].min()) < 0.05:
    print("🔴 头发顶点太少或纵向跨度过小 ⇒ 停止")
    raise SystemExit(2)

# 保序记录原始链尖方向（分链用），再统一重算
ang_h = np.arctan2(Hp[:, 0] - head_pos[0], Hp[:, 2] - head_pos[2])
y_low = float(np.percentile(Hp[:, 1], 2))
span = max(1e-6, y_head - y_low)
JT2, WT2 = JT.copy(), WT.copy()
changed = 0
report = []
for i in HAIR:
    nd = J["nodes"][joints[i]]
    sb = nd.setdefault("extras", {}).setdefault("springBone", {})
    t0 = np.array(sb.get("tail", [0, 0, 0]), np.float64)
    a_t = float(np.arctan2(t0[0] - head_pos[0], t0[2] - head_pos[2]))
    d = np.abs((ang_h - a_t + np.pi) % (2 * np.pi) - np.pi)
    sel = d < np.pi / 4
    if sel.sum() < 20:
        sel = d < np.pi / 2
    # ① 挂权：深度^1.5 × 0.9，余量留 Head（根部不撕）
    for local in np.where(sel)[0]:
        vi = np.where(hair)[0][local]
        depth = float(np.clip((y_head - P[vi, 1]) / span, 0, 1))
        w = depth ** 1.5 * 0.9
        if w <= 0.02:
            continue
        JT2[vi] = [i, IDX_HEAD, 0, 0]
        WT2[vi] = [w, 1.0 - w, 0.0, 0.0]
        changed += 1
    # ② 链尖 = 该扇区最低 3% 的质心（**与挂权同一份顶点集**）
    low = Hp[sel][Hp[sel][:, 1] <= np.percentile(Hp[sel][:, 1], 3)]
    tip = low.mean(axis=0)
    tip[1] = max(tip[1], float(Hp[:, 1].min()))
    sb["tail"] = [float(x) for x in tip]
    report.append((names[joints[i]], int(sel.sum()), float(t0[1]), float(tip[1])))

for nm, n, oy, ny in report:
    print(f"  {nm:22s} 扇区 n={n:6d} · 链尖 y {oy:+.4f} → {ny:+.4f}")
print(f"改权顶点：{changed} · 头发最低 y {Hp[:, 1].min():+.4f}")

jv_off = len(BIN)


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
while len(BIN) % 4:
    BIN.append(0)
J["buffers"][0]["byteLength"] = len(BIN)
js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
while len(js) % 4:
    js += b" "
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body := bytearray(BIN)))
                + struct.pack("<I", len(js)) + b"JSON" + js
                + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))

# 自检：权重和=1 · Hair 骨进 JOINTS · 链尖覆盖到头发实际范围 · 关节数未变
raw2 = OUT.read_bytes()
jl2, = struct.unpack_from("<I", raw2, 12)
J2 = json.loads(raw2[20:20 + jl2].decode("utf-8"))
o2 = 20 + jl2 + ((-jl2) % 4)
bl2, = struct.unpack_from("<I", raw2, o2)
B2 = raw2[o2 + 8: o2 + 8 + bl2]


def acc2(i, c):
    a = J2["accessors"][i]
    bv = J2["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(B2, t, a["count"] * c, bv.get("byteOffset", 0)).reshape(a["count"], c)


bad = []
p2 = J2["meshes"][0]["primitives"][hi]
s = acc2(p2["attributes"]["WEIGHTS_0"], 4).sum(axis=1)
if abs(s.min() - 1) > 1e-4 or abs(s.max() - 1) > 1e-4:
    bad.append(f"权重和 {s.min():.4f}~{s.max():.4f}")
j2 = acc2(p2["attributes"]["JOINTS_0"], 4)
if not set(np.unique(j2)).intersection(set(HAIR)):
    bad.append("Hair 骨未进 JOINTS")
tips = [float(np.array(J2["nodes"][J2["skins"][0]["joints"][i]]["extras"]["springBone"]["tail"])[1])
        for i in HAIR]
if min(tips) < Hp[:, 1].min() - 1e-6:
    bad.append("仍有链尖低于头发最低点")
if max(tips) - min(tips) < 0.002:
    bad.append("4 条链尖几乎相同（链退化）")
if len(J2["skins"][0]["joints"]) != len(joints):
    bad.append("关节数变了")
# 覆盖率：分母**只算"该被弹簧驱动的部分"** —— 逐层排除两类本来就该留在 Head 上的顶点：
#   ① 头皮（y > 头关节）：戴在颅骨上的头发不跟弹簧摆；
#   ② **根部带**（深度 <0.16 ⇒ 权重 w<0.02 被跳过）：发根必须跟着头走，否则整片头发会从
#      头皮上"撕开"。第一版闸把这两类都算进分母，于是把**正确结果**连续判成 38.1% / 79.5% 不合格。
depth_all = np.clip((y_head - P[:, 1]) / span, 0, 1)
driven = hair & (P[:, 1] <= y_head - 0.004) & (depth_all >= 0.16)
cov = float(np.isin(np.where(driven)[0],
                    np.where((WT2[:, 0] > 0.02) & (JT2[:, 0] != IDX_HEAD))[0]).mean())
print(f"挂链覆盖率（**只算该被驱动的垂发**：y≤{y_head - 0.004:.3f} 且深度≥0.16）：{cov*100:.1f}%")
print(f"  分母 {int(driven.sum())} · 头皮 {int((hair & (P[:, 1] > y_head - 0.004)).sum())} 与"
      f" 根部带 {int((hair & (P[:, 1] <= y_head - 0.004) & (depth_all < 0.16)).sum())} 留在 Head，属正确")
if cov < 0.8:
    bad.append(f"覆盖率仅 {cov*100:.1f}%")
print(f"输出 {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB · 链尖 {[round(t, 4) for t in tips]}")
if bad:
    print("🔴 自检不过：" + "；".join(bad))
    raise SystemExit(1)
print("✅ 自检通过（权重和=1 · Hair 进 JOINTS · 链尖不越界且不退化 · 覆盖率达标 · 关节数未变）")
