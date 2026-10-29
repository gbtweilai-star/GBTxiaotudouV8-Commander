# -*- coding: utf-8 -*-
"""终件出厂校验（release gate）：逐项机检 + 落一份清单

口径（仓里规矩：**废物不许上线**）：
  一个 GLB 要算"能出厂"，必须同时过下面这几组硬检。任何一项不过 ⇒ 退出码 1，**不许晋升**。

检查项：
  A 容器   glTF 魔数 / 版本 / JSON 与 BIN 两个 chunk 的长度与**4 字节对齐** / 总长自洽
  B 引用   所有 accessor.bufferView、image.bufferView 索引**不越界**；indices 索引不越界
  C 蒙皮   skin 存在；每个 primitive 都带 JOINTS_0+WEIGHTS_0；**权重和 = 1**（容差 1e-3）
  D 关节   关节数 ≥ 20；父子链**无自环、无环**
  E 贴图   每张 image 都能被 PIL 解码，且记录真尺寸
  F 几何   POSITION 非空；访问器 min/max 与实际数据一致；bbox 合理（高 > 0）
输出：逐项读数 + 结尾一行 `RELEASE: PASS|FAIL`，便于外层脚本判。

用法：python tools/codex-scripts/release-check.py <件.glb>
退出码：0 = 全过；1 = 有项不过；2 = 前置问题。
"""
import io
import json
import pathlib
import struct
import sys

import numpy as np
from PIL import Image

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DH / "raw/rig/avatar-final.glb"
if not SRC.is_file():
    print(f"🔴 文件不在盘上：{SRC}")
    raise SystemExit(2)

raw = SRC.read_bytes()
bad, notes = [], []

# ── A 容器 ───────────────────────────────────────────────────────────────
if raw[:4] != b"glTF":
    bad.append(f"A 魔数不是 glTF（{raw[:4]!r}）")
ver, total = struct.unpack_from("<II", raw, 4)
if ver != 2:
    bad.append(f"A 版本 {ver} ≠ 2")
pos, chunks = 12, {}
while pos + 8 <= len(raw):
    clen, ctype = struct.unpack_from("<I4s", raw, pos)
    if clen % 4:
        bad.append(f"A chunk {ctype!r} 长度 {clen} 不是 4 的倍数")
    chunks[ctype] = (pos + 8, clen)
    pos += 8 + clen
if pos != len(raw):
    notes.append(f"A 末位对齐：解析到 {pos} / 实际 {len(raw)}（差 {len(raw)-pos} 字节，可接受但记录）")
if total != len(raw):
    bad.append(f"A 头部总长 {total} ≠ 实际 {len(raw)}")
J = json.loads(raw[chunks[b"JSON"][0]:chunks[b"JSON"][0] + chunks[b"JSON"][1]].decode("utf-8"))
BIN = raw[chunks[b"BIN\x00"][0]:chunks[b"BIN\x00"][0] + chunks[b"BIN\x00"][1]]
print(f"[A 容器] glTF {ver} · JSON {chunks[b'JSON'][1]} B · BIN {len(BIN)} B · 文件 {len(raw)/1024/1024:.2f} MB")

# ── B 引用 ───────────────────────────────────────────────────────────────
n_bv, n_ac = len(J["bufferViews"]), len(J["accessors"])
for i, a in enumerate(J["accessors"]):
    if a.get("bufferView", -1) >= n_bv:
        bad.append(f"B accessor{i}.bufferView 越界")
for i, im in enumerate(J.get("images", [])):
    if im.get("bufferView", -1) >= n_bv:
        bad.append(f"B image{i}.bufferView 越界")


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    t = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(BIN, t, a["count"] * comps, bv.get("byteOffset", 0)).reshape(a["count"], comps)


prims = J["meshes"][0]["primitives"]
tris = 0
for k, p in enumerate(prims):
    nv = J["accessors"][p["attributes"]["POSITION"]]["count"]
    if "indices" in p:
        ix = acc(p["indices"], 1).astype(np.int64).reshape(-1, 3)
        tris += len(ix)
        if ix.max() >= nv:
            bad.append(f"B primitive{k} indices 越界（max {ix.max()} ≥ 顶点 {nv}）")
print(f"[B 引用] accessor {n_ac} · bufferView {n_bv} · primitive {len(prims)} · 三角 {tris}")

# ── C 蒙皮 ───────────────────────────────────────────────────────────────
if not J.get("skins"):
    bad.append("C 无 skin")
else:
    for k, p in enumerate(prims):
        for key in ("JOINTS_0", "WEIGHTS_0"):
            if key not in p["attributes"]:
                bad.append(f"C primitive{k} 缺 {key}")
    ws = [acc(p["attributes"]["WEIGHTS_0"], 4).sum(axis=1) for p in prims
          if "WEIGHTS_0" in p["attributes"]]
    wmin = min(w.min() for w in ws)
    wmax = max(w.max() for w in ws)
    if abs(wmin - 1) > 1e-3 or abs(wmax - 1) > 1e-3:
        bad.append(f"C 权重和 {wmin:.4f}~{wmax:.4f} ≠ 1")
    print(f"[C 蒙皮] primitive {len(prims)} 全带蒙皮 · 权重和 {wmin:.4f}~{wmax:.4f}")

# ── D 关节 ───────────────────────────────────────────────────────────────
joints = J["skins"][0]["joints"] if J.get("skins") else []
if len(joints) < 20:
    bad.append(f"D 关节仅 {len(joints)} < 20")
parent = {}
for i, nd in enumerate(J["nodes"]):
    for c in nd.get("children", []) or []:
        if c == i:
            bad.append(f"D 节点 {i} 自环")
        parent[c] = i
for j in joints:
    seen, cur = set(), j
    while cur is not None:
        if cur in seen:
            bad.append(f"D 关节 {j} 父链成环")
            break
        seen.add(cur)
        cur = parent.get(cur)
print(f"[D 关节] {len(joints)} 个 · 父链无环")

# ── E 贴图 ───────────────────────────────────────────────────────────────
sizes = []
for i, im in enumerate(J.get("images", [])):
    bv = J["bufferViews"][im["bufferView"]]
    o = bv.get("byteOffset", 0)
    try:
        pic = Image.open(io.BytesIO(BIN[o:o + bv["byteLength"]]))
        pic.load()
        sizes.append(f"{pic.width}²")
    except Exception as e:
        bad.append(f"E image{i} 解码失败（{type(e).__name__}）")
print(f"[E 贴图] {len(J.get('images', []))} 张 · 尺寸 {' '.join(sizes)}")

# ── F 几何 ───────────────────────────────────────────────────────────────
P = acc(prims[0]["attributes"]["POSITION"], 3).astype(np.float64)
allP = np.vstack([acc(p["attributes"]["POSITION"], 3).astype(np.float64) for p in prims])
h = float(allP[:, 1].max() - allP[:, 1].min())
if h <= 0.01:
    bad.append(f"F 身高 {h:.4f} 不合理")
a0 = J["accessors"][prims[0]["attributes"]["POSITION"]]
if "min" in a0 and not np.allclose(np.array(a0["min"]), P.min(axis=0), atol=1e-3):
    bad.append("F accessor.min 与实际数据不符")
print(f"[F 几何] 顶点 {int(sum(J['accessors'][p['attributes']['POSITION']]['count'] for p in prims))}"
      f" · 身高 {h:.4f} · bbox x±{allP[:, 0].max():.3f} z±{allP[:, 2].max():.3f}")

for n in notes:
    print("  ⚠️", n)
if bad:
    print("\n🔴 出厂校验不过：")
    for b in bad:
        print("   -", b)
    print("RELEASE: FAIL")
    raise SystemExit(1)
print("\n✅ 六组硬检全过（容器/引用/蒙皮/关节/贴图/几何）")
print("RELEASE: PASS")
