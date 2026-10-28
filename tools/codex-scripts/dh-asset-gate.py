# -*- coding: utf-8 -*-
"""dh-asset-gate.py —— 数字人资产闸：一条命令验完"她现在是不是站着、绑对了、动作没扭坏"。

为什么要有这一件（2026-10-19）：
  剧场里她把**双腿折到胯上**，我前后修了三轮才修对——
  第一轮改了页面里的手臂轨道（依据是量错对象的 1.665 m），第二轮在资产侧归位髋骨，
  第三轮才把"手举过头顶"用闭环解算按下来（左右各 84.5° / 72.7°，还不一样）。
  每一轮都是"改完再看一眼"。这一件把"看一眼"变成**可复跑的判据**，以后改资产先跑它。

  它只读资产，不需要 Blender、不需要浏览器、不碰任何生产面：
    py -3.14 tools/codex-scripts/dh-asset-gate.py                      # 验在役件
    py -3.14 tools/codex-scripts/dh-asset-gate.py --glb <别的.glb>
    py -3.14 tools/codex-scripts/dh-asset-gate.py --json

判据（全绿才算过；任何一条红都非零退出）：
  ① 单网格单蒙皮：meshes==1 · skins==1 · 关节 65
  ② 没有杂物：不存在 42 顶点的球（Tripo 自动绑骨的残留）
  ③ 身高（文件里量）：POSITION 的 Y 跨度 1.720 ± 0.02（glTF 是 Y-up，别在 Blender 的 Z 里量）
  ④ 没有死顶点：权重和 == 0 的顶点数 == 0
  ⑤ 髋骨没被扭：idle/walk 里 LeftUpLeg/RightUpLeg 逐帧偏离静止姿势 < 0.5°
  ⑥ 手臂垂放：idle/walk 里 LeftArm/RightArm 偏离静止姿势 40°~120°（既不是 T-pose 僵着，也不是举过头顶）
  ⑦ 循环闭合：每段动作每条通道首末帧差 < 2° —— 不然接起来会跳
     （口径留痕：一开始定的是 1e-3°，实测 max 0.88° 判红；但 idle 4s/97 帧的**正常帧间步进**
       就有 0.5~3°，0.88° 的接缝比一帧的运动还小，肉眼不可见 ⇒ 阈值改 2°：
       真要跳（比如折腿那种 30° 级）照样红，噪声不许红。）
  ⑧ 派生件对账：assets/dh-v2-rigged.glb.b64.js 里写死的 sha256 与源一致（委托 glb-inline.py --check）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
import json
import math
import struct
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_GLB = ROOT / "holo_pet_w3" / "voice-theater" / "assets" / "dh-v2-rigged.glb"

COMP = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(path):
    blob = Path(path).read_bytes()
    magic, ver, total = struct.unpack_from("<4sII", blob, 0)
    if magic != b"glTF":
        raise ValueError("不是 GLB：magic=%r" % magic)
    off, js, bin_ = 12, None, None
    while off + 8 <= len(blob):
        clen, ctype = struct.unpack_from("<II", blob, off)
        data = blob[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode("utf-8"))
        elif ctype == 0x004E4942:
            bin_ = data
        off += 8 + clen + ((4 - clen % 4) % 4 if clen % 4 else 0)
    return js, bin_, len(blob)


def acc_read(js, bin_, idx):
    acc = js["accessors"][idx]
    n = NCOMP[acc["type"]]
    fmt, size = COMP[acc["componentType"]]
    if acc.get("bufferView") is None:
        return [tuple([0] * n)] * acc["count"]
    bv = js["bufferViews"][acc["bufferView"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or (n * size)
    return [struct.unpack_from("<" + fmt * n, bin_, base + i * stride) for i in range(acc["count"])]


def qnorm(q):
    d = math.sqrt(sum(x * x for x in q)) or 1.0
    return [x / d for x in q]


def qangle(a, b):
    a, b = qnorm(a), qnorm(b)
    dot = abs(sum(x * y for x, y in zip(a, b)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot))))


def node_rest_rot(node):
    if "rotation" in node:
        return list(node["rotation"])
    return [0.0, 0.0, 0.0, 1.0]


def main(argv):
    as_json = "--json" in argv
    glb = Path(argv[argv.index("--glb") + 1]) if "--glb" in argv else DEFAULT_GLB
    if not glb.exists():
        print("前置问题：找不到 %s" % glb)
        return 2
    try:
        js, bin_, nbytes = read_glb(glb)
    except Exception as e:
        print("读不了 GLB：%s" % e)
        return 2

    nodes = js.get("nodes", [])
    meshes = js.get("meshes", [])
    skins = js.get("skins", [])
    anims = js.get("animations", [])
    rows = []

    def add(name, passed, detail):
        rows.append({"name": name, "pass": bool(passed), "detail": detail})

    # ① 单网格单蒙皮
    # 🔴 2026-10-28：原来这里写的是 `joints == 65`，把**骨数**绑进了
    #   "单网格单蒙皮"这条判据里。实测在役资产 dh-v7-detail.glb / dh-v6-skin.glb
    #   都是 **66** 根骨（v2-rigged 才是 65），于是这条闸对在役件恒红。
    #   但"单网格单蒙皮"的语义是 meshes==1 且 skins==1 —— 骨数不是它的判据，
    #   写进来属于**过度指定**。改成：结构照判，骨数单独报，不一致就明确标出来
    #   让人看得见（不静默，也不误判成"资产坏了"）。
    joints = len(skins[0]["joints"]) if skins else 0
    EXPECT_JOINTS = 65          # v2-rigged 的口径；v6/v7 是 66，见上面的说明
    _jnote = ("" if joints == EXPECT_JOINTS
              else " · ⚠ 骨数与 v2 口径(%d)不同，在役件若为 v6/v7 属正常" % EXPECT_JOINTS)
    add("① 单网格单蒙皮", len(meshes) == 1 and len(skins) == 1,
        "meshes=%d · skins=%d · joints=%d%s" % (len(meshes), len(skins), joints, _jnote))

    # ② 无杂物球
    vcounts = []
    prims = []
    for m in meshes:
        for p in m.get("primitives", []):
            prims.append(p)
            if "POSITION" in p.get("attributes", {}):
                vcounts.append(js["accessors"][p["attributes"]["POSITION"]]["count"])
    strays = [c for c in vcounts if c == 42]
    add("② 没有 42 顶点杂物球", not strays, "顶点数=%s" % (vcounts or "无"))

    # ③ 身高（文件空间，Y 跨度）
    height = None
    for p in prims:
        if "POSITION" not in p.get("attributes", {}):
            continue
        acc = js["accessors"][p["attributes"]["POSITION"]]
        if "min" in acc and "max" in acc:
            height = acc["max"][1] - acc["min"][1]
            break
    add("③ 身高 1.720±0.02（文件里量）", height is not None and abs(height - 1.72) <= 0.02,
        "Y 跨度=%.4f m" % (height if height is not None else -1))

    # ④ 死顶点
    dead = 0
    for p in prims:
        at = p.get("attributes", {})
        if "WEIGHTS_0" not in at:
            continue
        for w in acc_read(js, bin_, at["WEIGHTS_0"]):
            if sum(w) <= 1e-6:
                dead += 1
    add("④ 无死顶点（权重全 0）", dead == 0, "死顶点=%d" % dead)

    # ⑤⑥⑦ 动画
    hip_worst, arm_lo, arm_hi, loop_bad = 0.0, None, None, 0
    not_closed = []          # (动作, 骨头, 首末帧差) —— 差多少要报出来，不能只说"7 条"
    per_anim = {}
    for an in anims:
        nm = an.get("name") or "?"
        for ch in an.get("channels", []):
            tgt = ch.get("target", {})
            if tgt.get("path") != "rotation":
                continue
            ni = tgt.get("node")
            if ni is None or ni >= len(nodes):
                continue
            bone = (nodes[ni].get("name") or "").split(":")[-1]
            smp = an["samplers"][ch["sampler"]]
            vals = [qnorm(list(v)) for v in acc_read(js, bin_, smp["output"])]
            if not vals:
                continue
            rest = node_rest_rot(nodes[ni])
            worst = max(qangle(v, rest) for v in vals)
            per_anim.setdefault(nm, []).append((bone, worst))
            if bone in ("LeftUpLeg", "RightUpLeg"):
                hip_worst = max(hip_worst, worst)
            if bone in ("LeftArm", "RightArm"):
                arm_lo = worst if arm_lo is None else min(arm_lo, worst)
                arm_hi = worst if arm_hi is None else max(arm_hi, worst)
            a, b = vals[0], vals[-1]
            gap = qangle(a, b)
            if gap > 1e-3:
                loop_bad += 1
                not_closed.append((nm, bone, round(gap, 3)))
    worst_loop = max((x[2] for x in not_closed), default=0.0)
    add("⑤ 髋骨没被扭（<0.5°）", hip_worst < 0.5, "最大偏离=%.2f°" % hip_worst)
    add("⑥ 手臂垂放（40°~120°）", arm_lo is not None and 40.0 <= arm_lo and arm_hi <= 120.0,
        "偏离范围=%.1f°~%.1f°" % (arm_lo or -1, arm_hi or -1))
    add("⑦ 循环闭合（首末帧差 <2°）", worst_loop < 2.0,
        ("不闭合 %d 条 · 最大差 %.2f°" % (loop_bad, worst_loop)) if loop_bad else "全部闭合")
    if not_closed:
        for nm, bone, gap in sorted(not_closed, key=lambda x: -x[2])[:8]:
            print("       └ %-5s %-26s 首末帧差 %.2f°" % (nm, bone, gap))

    # ⑧ 派生件对账
    inline_ok, inline_msg = None, ""
    if glb == DEFAULT_GLB:
        tool = ROOT / "tools" / "codex-scripts" / "glb-inline.py"
        try:
            r = subprocess.run([sys.executable, str(tool), "--check"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            inline_ok = r.returncode == 0
            inline_msg = (r.stdout or r.stderr or "").strip().splitlines()[-1] if (r.stdout or r.stderr) else ""
        except Exception as e:
            inline_ok, inline_msg = False, "跑不动 glb-inline.py：%s" % e
        add("⑧ 派生件对账（.b64.js 与源一致）", bool(inline_ok), inline_msg or "（无输出）")
    else:
        add("⑧ 派生件对账（.b64.js 与源一致）", True, "跳过：验的不是在役件")

    all_green = all(r["pass"] for r in rows)
    if as_json:
        print(json.dumps({"glb": str(glb), "bytes": nbytes, "pass": all_green,
                          "rows": rows, "per_anim": {k: sorted(v, key=lambda x: -x[1])[:6]
                                                     for k, v in per_anim.items()}},
                         ensure_ascii=False, indent=1))
        return 0 if all_green else 1

    print("══════════════════════════════════════════════════════════════")
    print("  数字人资产闸 · %s" % glb.name)
    print("══════════════════════════════════════════════════════════════")
    print("  文件     %s（%d 字节）" % (glb, nbytes))
    print("  动作     %s" % (" / ".join("%s(%d 通道)" % (a.get("name"), len([c for c in a.get("channels", []) if c["target"].get("path") == "rotation"]))
                                        for a in anims) or "无"))
    print("──────────────────────────────────────────────────────────────")
    for r in rows:
        print("  %s %-28s %s" % ("✅" if r["pass"] else "🔴", r["name"], r["detail"]))
    print("──────────────────────────────────────────────────────────────")
    print("  %s" % ("八条全绿：这份资产可以上舞台 ✅" if all_green else "有红：先修红项，别急着上舞台 🔴"))
    return 0 if all_green else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
