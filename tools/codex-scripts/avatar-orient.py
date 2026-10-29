# -*- coding: utf-8 -*-
"""数字人 · 网格定向归一：把任意朝向的 GLB 转成**本仓口径**（上 +Y / 正面 +Z / 肩宽轴 = X）

为什么需要它（2026-09-25 实测）：
  本机三视图重建出来的网格，**肩宽轴落在了 Z、正面朝 +X** —— 也就是整个模型相对仓里
  既有资产（形象页/主控台/骨架 viewer 都按「正面 +Z」取景）**转了 90°**。
  在这种朝向上取景，`?view=front` 出来的其实是一张侧面图；再往前一步做绑骨，
  髋/肩的左右也会跟着错位。所以定向必须先归一，且**归一要能被量出来**，不能靠眼看。

判据（全部是读数，不是感觉）：
  · 归一前：量肩部高度带的 x/z 跨度，**宽的那条就是肩宽轴**；
  · 前后：量脚掌（最低 4% 高度）相对踝部（12% 高度）的质心偏移，**偏移指向就是脚尖=正面**；
  · 归一后：复查「肩轴 = X」（x 跨 > z 跨）且「脚尖沿 +Z」，两条都过才写盘。

用法：
  python tools/codex-scripts/avatar-orient.py <in.glb> <out.glb> [--target front+z|keep]
退出码：0 = 归一完成且两条自检全过；1 = 自检不过；2 = 前置/参数问题。
"""
import json
import pathlib
import struct
import sys

import numpy as np

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WS / "holo_pet/assets/digital-human/raw/phase1-owner/model.glb"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else WS / "holo_pet/assets/digital-human/raw/avatarmesh/model-facing.glb"


def read_glb(path):
    raw = path.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, bytearray(raw[off + 8: off + 8 + bl])


def acc(J, BIN, i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(bytes(BIN), dt, a["count"] * comps,
                         bv.get("byteOffset", 0)).reshape(a["count"], comps)


def add_view(J, BIN, arr, target=None):
    while len(BIN) % 4:
        BIN.append(0)
    o = len(BIN)
    BIN.extend(arr.tobytes())
    v = {"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes}
    if target:
        v["target"] = target
    J["bufferViews"].append(v)
    return len(J["bufferViews"]) - 1


def write_glb(path, J, BIN):
    body = bytearray(BIN)
    while len(body) % 4:
        body.append(0)
    J["buffers"][0]["byteLength"] = len(body)
    js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                     + struct.pack("<I", len(js)) + b"JSON" + js
                     + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))


def rot_y(v, deg):
    """绕 +Y 右手旋转 deg 度。"""
    t = np.radians(deg)
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]], np.float64)
    return v @ R.T


def rng(a):
    return float(a.max() - a.min())


def measure(P, tag):
    """量「肩轴」与「脚尖朝向」。返回 (肩轴是X?, 脚尖单位向量, 读数dict)。"""
    y0, y1 = P[:, 1].min(), P[:, 1].max()
    H = max(1e-9, y1 - y0)
    sh = P[np.abs(P[:, 1] - (y1 - 0.15 * H)) < 0.02 * H]
    xsp, zsp = rng(sh[:, 0]), rng(sh[:, 2])
    foot = P[P[:, 1] < y0 + 0.04 * H]
    ankle = P[np.abs(P[:, 1] - (y0 + 0.12 * H)) < 0.02 * H]
    d = np.array([foot[:, 0].mean() - ankle[:, 0].mean(),
                  foot[:, 1].mean() - ankle[:, 1].mean(),
                  foot[:, 2].mean() - ankle[:, 2].mean()]) if len(foot) and len(ankle) else np.zeros(3)
    horiz = np.array([d[0], 0.0, d[2]])
    n = np.linalg.norm(horiz)
    if n > 1e-9:
        horiz = horiz / n
    return {"tag": tag, "height": H, "shoulder_x_span": xsp, "shoulder_z_span": zsp,
            "shoulder_axis": "X" if xsp > zsp else "Z",
            "toe_offset": (float(d[0]), float(d[1]), float(d[2])),
            "toe_dir_xz": (float(horiz[0]), float(horiz[2]))}


def main():
    if not SRC.is_file():
        print(f"🔴 输入不在盘上：{SRC}")
        return 2
    J, BIN = read_glb(SRC)
    m = J["meshes"][0]["primitives"][0]
    Pi = m["attributes"]["POSITION"]
    Ni = m["attributes"].get("NORMAL")
    P0 = acc(J, BIN, Pi, 3).astype(np.float64)
    N0 = acc(J, BIN, Ni, 3).astype(np.float64) if Ni is not None else None
    print(f"输入 {SRC.name} · 顶点 {len(P0)} · 有法线 {N0 is not None}")

    before = measure(P0, "归一前")
    print(f"[归一前] 高 {before['height']:.4f} · 肩带 x跨 {before['shoulder_x_span']:.4f} / "
          f"z跨 {before['shoulder_z_span']:.4f} ⇒ 肩轴 = {before['shoulder_axis']}")
    print(f"[归一前] 脚尖水平偏移 = ({before['toe_dir_xz'][0]:+.3f}, {before['toe_dir_xz'][1]:+.3f}) "
          f"（原始 dx={before['toe_offset'][0]:+.4f} dz={before['toe_offset'][2]:+.4f}）")

    # 目标：肩轴 = X，脚尖沿 +Z。四种情形各对应一个 Y 旋转角（右手系）。
    axis, (tx, tz) = before["shoulder_axis"], before["toe_dir_xz"]
    deg = 0.0
    if axis == "Z":
        # 原肩轴为 Z ⇒ 需把 Z 转到 X。±90° 二选一，用脚尖方向定符号。
        deg = -90.0 if tx > 0 else 90.0
    else:
        # 肩轴已是 X ⇒ 只需把脚尖摆到 +Z。
        deg = 180.0 if tz < 0 else 0.0
    print(f"[规划] 绕 Y 旋转 {deg:+.0f}°（肩轴 {axis}、脚尖主导轴 "
          f"{'X' if abs(tx) >= abs(tz) else 'Z'} ⇒ 目标：肩轴 X、脚尖 +Z）")

    P1 = rot_y(P0, deg)
    N1 = rot_y(N0, deg) if N0 is not None else None

    after = measure(P1, "归一后")
    print(f"[归一后] 肩带 x跨 {after['shoulder_x_span']:.4f} / z跨 {after['shoulder_z_span']:.4f} "
          f"⇒ 肩轴 = {after['shoulder_axis']}")
    print(f"[归一后] 脚尖水平偏移 = ({after['toe_dir_xz'][0]:+.3f}, {after['toe_dir_xz'][1]:+.3f})")

    ok_axis = after["shoulder_axis"] == "X"
    ok_toe = after["toe_dir_xz"][1] > 0.5 and abs(after["toe_dir_xz"][0]) < 0.5
    if deg == 0.0 and ok_axis and ok_toe:
        print("[结论] 本来就已经是本仓口径 ⇒ 仍照写（幂等），不做多余旋转")
    print(f"[自检] 肩轴=X : {'✅' if ok_axis else '🔴'} · 脚尖沿+Z : {'✅' if ok_toe else '🔴'}")
    if not (ok_axis and ok_toe):
        print("🔴 归一后两条自检未同时通过 ⇒ 不写盘（宁可卡住，不产歪资产）")
        return 1

    # 写回：新增 bufferView/accessor，重指 POSITION/NORMAL（不动 images/UV/indices）
    Pf = P1.astype(np.float32)
    pv = add_view(J, BIN, Pf, 34962)
    J["accessors"].append({"bufferView": pv, "componentType": 5126, "count": len(Pf),
                           "type": "VEC3", "min": [float(x) for x in Pf.min(axis=0)],
                           "max": [float(x) for x in Pf.max(axis=0)]})
    m["attributes"]["POSITION"] = len(J["accessors"]) - 1
    if N1 is not None:
        Nf = N1.astype(np.float32)
        nv = add_view(J, BIN, Nf, 34962)
        J["accessors"].append({"bufferView": nv, "componentType": 5126, "count": len(Nf), "type": "VEC3"})
        m["attributes"]["NORMAL"] = len(J["accessors"]) - 1
    write_glb(OUT, J, BIN)
    print(f"[输出] {OUT} · {OUT.stat().st_size/1024/1024:.2f} MB · 旋转 {deg:+.0f}°")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
