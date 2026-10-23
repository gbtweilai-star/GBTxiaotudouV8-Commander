# -*- coding: utf-8 -*-
"""S7 · 表情（VRM Expressions）：给网格加 **morph targets** + 写 `VRMC_vrm.expressions`。

契约（Round 4 抓取）：
- 网格侧：`meshes[0].primitives[0].targets = [{POSITION: <delta accessor>}, ...]`
  + `meshes[0].extras.targetNames = ["blink","aa","happy", ...]`（规范推荐）
- 扩展侧：`VRMC_vrm.expressions.preset.<name>.morphTargetBinds = [{node, index, weight}]`
- 值域 [0,1]；`overrideBlink/overrideMouth` 控制与程序化表情（眨眼/口型）的叠加。

诚实说明：本资产的脸是**贴图皮肤（无眼睑/口部独立几何）**，所以：
- `blink` = 眼区整体下压（看起来是**眯眼**，不是真闭眼）
- `aa`   = 口区下压（下巴张开）
- `happy`= 嘴角上提 + 轻微眯眼
三个都做**余弦衰减**，避免硬边。

输入 raw/rig/model-springs-chains.glb → 输出 raw/rig/model-expressions.glb
"""
from __future__ import annotations

import array
import json
import math
import pathlib
import struct
import sys

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


WS = pathlib.Path(__file__).resolve().parents[2]
RIG = WS / "holo_pet/assets/digital-human/raw/rig"
SRC = RIG / "model-springs-chains.glb"
OUT = RIG / "model-expressions.glb"
NAMES = ["blink", "aa", "happy"]


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


def add_vec3(J, BIN, rows):
    a = array.array("f", [x for r in rows for x in r])
    while len(BIN) % 4:
        BIN.append(0)
    off = len(BIN)
    BIN.extend(a.tobytes())
    J["bufferViews"].append({"byte": 0} and {"buffer": 0, "byteOffset": off, "byteLength": a.itemsize * len(a)})
    J["accessors"].append({"bufferView": len(J["bufferViews"]) - 1, "componentType": 5126,
                           "count": len(rows), "type": "VEC3"})
    return len(J["accessors"]) - 1


def main():
    J, BIN = load(SRC)
    prim = J["meshes"][0]["primitives"][0]
    a_p = J["accessors"][prim["attributes"]["POSITION"]]
    bv = J["bufferViews"][a_p["bufferView"]]
    P = array.array("f")
    P.frombytes(bytes(BIN[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + a_p["count"] * 12]))
    n = a_p["count"]
    xs = [P[i * 3] for i in range(n)]
    ys = [P[i * 3 + 1] for i in range(n)]
    xmax = max(xs)
    # 前面（脸）区域：x 靠前 **且 y 在颈线以上**（否则会把胸/裙/腿当脸 —— 实测踩过）
    NECK_Y = 0.386
    front = [i for i in range(n) if xs[i] > 0.55 * xmax and ys[i] > NECK_Y]
    fy = sorted(ys[i] for i in front)
    y_hi, y_lo = fy[int(len(fy) * 0.95)], fy[int(len(fy) * 0.05)]
    eye_y, mouth_y = y_lo + (y_hi - y_lo) * 0.66, y_lo + (y_hi - y_lo) * 0.30
    print(f"脸区 {len(front)} 顶点 · y {y_lo:.3f}~{y_hi:.3f} · 眼线 {eye_y:.3f} · 口线 {mouth_y:.3f}")

    def band(cy, half, amp, sideways=0.0):
        out = []
        for i in range(n):
            if xs[i] <= 0.45 * xmax:
                out.append((0.0, 0.0, 0.0))
                continue
            d = abs(ys[i] - cy)
            f = math.cos(min(1.0, d / half) * math.pi / 2) ** 2 if d < half else 0.0
            dx = sideways * f * (1 if P[i * 3 + 2] > 0 else -1)
            out.append((dx, -amp * f, 0.0))
        return out

    def smile(amp, squint):
        out = []
        for i in range(n):
            f_m = 0.0
            if xs[i] > 0.45 * xmax:
                d = abs(ys[i] - mouth_y)
                if d < 0.020:
                    f_m = math.cos(min(1.0, d / 0.020) * math.pi / 2) ** 2
            f_e = 0.0
            if xs[i] > 0.55 * xmax:
                d = abs(ys[i] - eye_y)
                if d < 0.014:
                    f_e = math.cos(min(1.0, d / 0.014) * math.pi / 2) ** 2
            out.append((0.0, amp * f_m - squint * f_e, 0.0))
        return out

    targets = {
        "blink": band(eye_y, 0.014, 0.0075),
        "aa": band(mouth_y, 0.018, 0.0090),
        "happy": smile(0.0035, 0.0030),
    }
    idx_of = {}
    for k, nm in enumerate(NAMES):
        idx_of[nm] = add_vec3(J, BIN, targets[nm])
    prim["targets"] = [{"POSITION": idx_of[nm]} for nm in NAMES]
    J["meshes"][0].setdefault("extras", {})["targetNames"] = NAMES
    # 表达式块
    vrm = J.setdefault("extensions", {}).setdefault("VRMC_vrm", {"specVersion": "1.0"})
    vrm["expressions"] = {"preset": {
        nm: {"isBinary": False, "morphTargetBinds": [{"node": 0, "index": k, "weight": 1.0}],
             **({"overrideBlink": "blend"} if nm == "happy" else {})}
        for k, nm in enumerate(NAMES)}}
    write(OUT, J, BIN)
    # 自证门：形变必须真的落在**头区**（颈线以上），且非零顶点数合理
    bad = []
    for nm in NAMES:
        nz = [i for i in range(n) if any(abs(v) > 1e-6 for v in targets[nm][i])]
        below = [i for i in nz if ys[i] <= NECK_Y]
        if len(nz) < 50:
            bad.append(f"{nm} 形变顶点过少({len(nz)})")
        if below:
            bad.append(f"{nm} 有 {len(below)} 个形变顶点在颈线以下（打到身体上了）")
        print(f"  {nm}: 形变顶点 {len(nz)} · 其中颈线以下 {len(below)} · y 范围 "
              f"{min((ys[i] for i in nz), default=0):.3f}~{max((ys[i] for i in nz), default=0):.3f}")
    print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · morph {len(NAMES)} 个：{NAMES}")
    if bad:
        print("S7 门: ❌ " + "; ".join(bad))
        return 1
    print("S7 门: ✅ morph 已挂 + expressions.preset 已写 + **形变落在头区**（自证）")
    return 0


def check_contract(p) -> tuple:
    """S7 契约门：GLB 里**真的**挂上了 morph targets + targetNames + expressions.preset。

    🔴 2026-10-10 补。起因：judge-map 逐阶段清点负控出处，S7 那格是空的。
    看清了一件重要的事：S7 原来的"门"**只是生成器 main() 的退出码** —— 它跑成功就算过，
    **并不检查产物里到底有没有那些东西**。本函数把"契约真的落在产物里"单独做成可判的读数，
    这样它才有正负例可言（而不是"生成脚本没报错"）。
    判据（逐条都从文件里**算出来**，不看注释）：
      · meshes[0].primitives[0].targets 个数 == extras.targetNames 个数 且 > 0
      · VRMC_vrm.expressions.preset 的键集覆盖 targetNames
      · 每个 target 的 POSITION 增量 accessor 存在、count == 顶点数
    """
    if not p.exists():
        return False, "缺 %s" % p.name
    J, _ = load(p)
    prim = J["meshes"][0]["primitives"][0]
    tg = prim.get("targets") or []
    names = ((J["meshes"][0].get("extras") or {}).get("targetNames")) or []
    nvert = J["accessors"][prim["attributes"]["POSITION"]]["count"]
    preset = (((J.get("extensions") or {}).get("VRMC_vrm") or {})
              .get("expressions") or {}).get("preset") or {}
    bad = []
    if not tg:
        bad.append("primitives[0].targets 空（没挂 morph）")
    if len(names) != len(tg):
        bad.append("targetNames(%d) 与 targets(%d) 数量不符" % (len(names), len(tg)))
    if not names:
        bad.append("extras.targetNames 空")
    miss = [n for n in names if n not in preset]
    if miss:
        bad.append("expressions.preset 缺 %s" % miss)
    for k, t in enumerate(tg):
        ai = (t or {}).get("POSITION")
        if ai is None:
            bad.append("targets[%d] 没有 POSITION" % k); continue
        if J["accessors"][ai].get("count") != nvert:
            bad.append("targets[%d] count %s ≠ 顶点数 %d"
                       % (k, J["accessors"][ai].get("count"), nvert))
    ok = not bad
    return ok, ("morph %d 个 %s · preset %d 个 · 顶点 %d"
                % (len(tg), names[:4], len(preset), nvert)
                + ("" if ok else " · ✗ " + "; ".join(bad)))


def selftest() -> int:
    """S7 契约门的负控：**真件配对**（有 morph 的 vs 没 morph 的）。

    正例 = model-expressions.glb（本脚本的产物，已挂 morph）
    负例 = model-rigged.glb（上一步产物，**没有** morph targets）
    ==两边都是仓里真件，我不造假的来凑数。==
    """
    fails, n = [], [0]

    def c(name, got, want):
        n[0] += 1
        ok = (got == want)
        print("  %-56s %s" % (name, "✅" if ok else "❌ 期望 %s 得到 %s" % (want, got)))
        if not ok:
            fails.append(name)

    c("check_contract 负例·缺件 ⇒ 红", check_contract(RIG / "_nope.glb")[0], False)
    noexpr = RIG / "model-rigged.glb"
    if noexpr.is_file():
        c("check_contract 负例·model-rigged.glb **没挂 morph** ⇒ 红",
          check_contract(noexpr)[0], False)
    if OUT.is_file():
        c("check_contract 正例·model-expressions.glb 挂了 morph ⇒ 过",
          check_contract(OUT)[0], True)
    print()
    print("expr-make 自检: %s（%d 条）"
          % ("**全部通过**" if not fails else "**%d 条失败**" % len(fails), n[0]))
    return 0 if not fails else 1


if __name__ == "__main__":
    if "selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main())
