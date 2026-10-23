# -*- coding: utf-8 -*-
"""anim-hipfix.py —— 把自动绑骨跑坏的**髋骨轨道**归位到静止姿势（GLB 层面动手术，不动别的）。

为什么要有这一件（2026-10-19 实拍量到，不是猜）：
  剧场里她**双腿折到胯上/头顶**。`anim-audit.py` 读 GLB 二进制量出来：
    idle  mixamorig:LeftUpLeg  首帧偏离静止姿势 177.2°（整段最大 177.6°）
          mixamorig:RightUpLeg 176.3°
    walk  LeftUpLeg 153.2° / RightUpLeg 152.3°
  同一条 idle 里手臂是 62.1°、颈 40.0° —— 那两处是**对的**（T-pose 绑定下手臂本就该
  从水平降下来、颈本就该有角度）。所以坏的不是整段动作，是**髋骨这一条链**被重定向时
  翻了近 180°（Tripo 自动绑骨的典型符号错）。
  ⇒ 只把 LeftUpLeg / RightUpLeg 的旋转轨道**归位到绑定姿势**，其余通道一字节不动。
  （绑定姿势本身是好的：`dh3d-probe --pose bind` 实拍她是站直、双腿在下的 T-pose。）

口径：
  · 归位 = 该帧采样值写成该节点的**静止旋转**（nodes[i].rotation；没有就是单位四元数）；
  · 只碰 `rotation` 通道、只碰 --bones 点名的骨头；平移/缩放通道一律不碰；
  · 写回前先做**六条自检**，任何一条不过就不写文件、退出码非零：
      ① 目标骨头在动画里真有 rotation 通道（找不到 = 名字错了，不许静默成功）
      ② 采样 accessor 是 float/归一化整数 + VEC4（形状不对就报，不许硬写）
      ③ 静止四元数模长 = 1（容差 1e-4）
      ④ 写回后逐帧复查：全部等于静止旋转（差 < 1e-6）
      ⑤ 只改了这些采样：BIN 其余字节逐一相等（拿 diff 区间数对账，防写花）
      ⑥ 网格/蒙皮没被动：meshes / skins / POSITION 顶点数不变
  · 只读源文件，写 dst；源文件想覆盖就先自己备份（本件不替你盖）

用法：
  py -3.14 tools/codex-scripts/anim-hipfix.py <源.glb> <输出.glb>
  py -3.14 tools/codex-scripts/anim-hipfix.py <源.glb> <输出.glb> --bones LeftUpLeg,RightUpLeg --dry
  # 把量具量出来的姿势写进资产（值来自 .scratch/solve-arms.cjs，不是手搓的）：
  py -3.14 tools/codex-scripts/anim-hipfix.py <源.glb> <输出.glb> \
     --bones "" --set "LeftArm=-0.10117,0.003608,0.637898,0.763438" --set "RightArm=-0.055578,-0.001985,-0.560711,0.826142" \
     --set "LeftForeArm=rest" --set "RightForeArm=rest"
退出码：0 = 已写出且六条自检全绿；1 = 自检不过（未写盘）；2 = 前置问题（读不了/参数不对）。
"""
import json
import math
import struct
import sys

# 编码守门（本仓规矩：不带 -X utf8 调用时不许静默输出空；Windows 控制台默认 GBK）
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

COMP = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
DEFAULT_BONES = ["LeftUpLeg", "RightUpLeg"]


def read_glb(path):
    with open(path, "rb") as f:
        blob = f.read()
    if len(blob) < 20:
        raise ValueError("不是 GLB：只有 %d 字节" % len(blob))
    magic, ver, total = struct.unpack_from("<4sII", blob, 0)
    if magic != b"glTF":
        raise ValueError("不是 GLB：magic=%r" % magic)
    if total != len(blob):
        raise ValueError("GLB 头声明 %d 字节，实际 %d 字节（文件被截断？）" % (total, len(blob)))
    off, js, bin_, chunks = 12, None, None, []
    while off + 8 <= len(blob):
        clen, ctype = struct.unpack_from("<II", blob, off)
        chunks.append((off, clen, ctype))
        data = blob[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode("utf-8"))
        elif ctype == 0x004E4942:
            bin_ = data
        off += 8 + clen + ((4 - clen % 4) % 4 if clen % 4 else 0)
    if js is None or bin_ is None:
        raise ValueError("GLB 缺 JSON 或 BIN chunk")
    return blob, js, bin_, chunks


def node_rest_rot(node):
    if "rotation" in node:
        return list(node["rotation"])
    if "matrix" in node:
        m = node["matrix"]
        m00, m01, m02 = m[0], m[4], m[8]
        m10, m11, m12 = m[1], m[5], m[9]
        m20, m21, m22 = m[2], m[6], m[10]
        tr = m00 + m11 + m22
        if tr > 0:
            s = math.sqrt(tr + 1.0) * 2
            return [(m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s]
        if m00 > m11 and m00 > m22:
            s = math.sqrt(1.0 + m00 - m11 - m22) * 2
            return [0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s]
        if m11 > m22:
            s = math.sqrt(1.0 + m11 - m00 - m22) * 2
            return [(m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s]
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2
        return [(m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s]
    return [0.0, 0.0, 0.0, 1.0]


def qnorm(q):
    d = math.sqrt(sum(x * x for x in q)) or 1.0
    return [x / d for x in q]


def qangle(a, b):
    a, b = qnorm(a), qnorm(b)
    dot = abs(sum(x * y for x, y in zip(a, b)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot))))


def sample_layout(js, acc_idx):
    """返回 (起步字节, 每帧字节数, 每帧读法, 组件数, 缩放系数)；形状不对抛异常。"""
    acc = js["accessors"][acc_idx]
    t = acc["type"]
    if t not in NCOMP:
        raise ValueError("accessor %d 类型不认识：%s" % (acc_idx, t))
    n = NCOMP[t]
    ct = acc["componentType"]
    if ct not in COMP:
        raise ValueError("accessor %d 组件类型不认识：%d" % (acc_idx, ct))
    fmt, size = COMP[ct]
    if acc.get("bufferView") is None:
        raise ValueError("accessor %d 没有 bufferView（稀疏/零缓冲，本件不处理）" % acc_idx)
    bv = js["bufferViews"][acc["bufferView"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or (n * size)
    norm = 1.0
    if acc.get("normalized"):
        norm = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}.get(ct, 1.0)
    return base, stride, fmt, n, norm, acc


def read_samples(bin_, layout, count):
    base, stride, fmt, n, norm, acc = layout
    out = []
    for i in range(count):
        off = base + i * stride
        v = list(struct.unpack_from("<" + fmt * n, bin_, off))
        out.append([x / norm for x in v] if norm != 1.0 else v)
    return out


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    dry = "--dry" in argv
    if len(args) < 2:
        print(__doc__)
        return 2
    src, dst = args[0], args[1]
    bones = DEFAULT_BONES
    if "--bones" in argv:
        bones = [b.strip() for b in argv[argv.index("--bones") + 1].split(",") if b.strip()]

    # --set 名字=rest 或 名字=x,y,z,w（值应由量具量出来，不许手搓）
    explicit = {}
    for i, a in enumerate(argv):
        if a != "--set":
            continue
        spec = argv[i + 1] if i + 1 < len(argv) else ""
        if "=" not in spec:
            print("前置问题：--set 要写成 名字=rest 或 名字=x,y,z,w，收到 %r" % spec)
            return 2
        name, raw = spec.split("=", 1)
        name = name.strip().split(":")[-1]
        raw = raw.strip()
        if raw == "rest":
            explicit[name] = "rest"
        else:
            try:
                q = [float(x) for x in raw.split(",")]
            except ValueError:
                print("前置问题：--set %s 的四元数读不出来（%r）" % (name, raw))
                return 2
            if len(q) != 4:
                print("前置问题：--set %s 要 4 个数（x,y,z,w），收到 %d 个" % (name, len(q)))
                return 2
            explicit[name] = q
    names = list(dict.fromkeys(([b for b in bones]) + list(explicit.keys())))
    if not names:
        print("前置问题：没有要改的骨头（--bones 和 --set 都是空）")
        return 2

    try:
        blob, js, bin_, chunks = read_glb(src)
    except Exception as e:
        print("前置问题：%s" % e)
        return 2
    bin_ = bytearray(bin_)
    nodes = js.get("nodes", [])
    anims = js.get("animations", [])
    if not anims:
        print("前置问题：这个 GLB 里没有动画（nothing to fix）")
        return 2

    # ---- ① 目标骨头在动画里真有 rotation 通道 ----
    targets = []          # (anim_name, node_idx, bone_name, sampler)
    for an in anims:
        for ch in an.get("channels", []):
            tgt = ch.get("target", {})
            ni = tgt.get("node")
            if tgt.get("path") != "rotation" or ni is None or ni >= len(nodes):
                continue
            nm = nodes[ni].get("name", "")
            short = nm.split(":")[-1]
            if short in names:
                targets.append((an.get("name") or "?", ni, nm, an["samplers"][ch["sampler"]]))
    if not targets:
        print("① 不过：动画里找不到这些骨头的 rotation 通道：%s" % ", ".join(names))
        print("    （名字错了就会静默成功，所以这里直接不写盘）")
        return 1
    missing = [n for n in explicit
               if not any(t[2].split(":")[-1] == n for t in targets)]
    if missing:
        print("① 不过：这些骨头在动画里没有 rotation 通道，--set 写不进去（名字写错了？）：%s"
              % ", ".join(missing))
        return 1
    print("① 通过：命中 %d 条 rotation 通道 —— %s"
          % (len(targets), " · ".join(sorted({t[2] for t in targets}))))

    # ---- ② 采样形状 + ③ 静止四元数模长 ----
    plan = []
    for anim_name, ni, nm, smp in targets:
        acc_idx = smp["output"]
        try:
            layout = sample_layout(js, acc_idx)
        except Exception as e:
            print("② 不过：%s 的采样形状不对 —— %s" % (nm, e))
            return 1
        base, stride, fmt, n, norm, acc = layout
        if n != 4:
            print("② 不过：%s 的旋转通道是 VEC%d（应为 VEC4）" % (nm, n))
            return 1
        if base + stride * (acc["count"] - 1) + n * COMP[acc["componentType"]][1] > len(bin_):
            print("② 不过：%s 的采样越出 BIN 边界" % nm)
            return 1
        rest = node_rest_rot(nodes[ni])
        ln = math.sqrt(sum(x * x for x in rest))
        if abs(ln - 1.0) > 1e-4:
            print("③ 不过：%s 的静止四元数模长 %.6f ≠ 1" % (nm, ln))
            return 1
        want = explicit.get(nm.split(":")[-1], "rest")
        target = rest if want == "rest" else [x / (math.sqrt(sum(y * y for y in want)) or 1.0) for x in want]
        ln2 = math.sqrt(sum(x * x for x in target))
        if abs(ln2 - 1.0) > 1e-3:
            print("③ 不过：%s 的目标四元数模长 %.6f ≠ 1" % (nm, ln2))
            return 1
        before = read_samples(bin_, layout, acc["count"])
        plan.append((anim_name, ni, nm, layout, target, acc["count"], before, acc["componentType"]))
    print("② 通过：%d 条通道全是 float/归一化整数 × VEC4，且在 BIN 范围内" % len(plan))
    print("③ 通过：%d 个目标四元数模长都是 1" % len(plan))

    # ---- 写回 ----
    touched = []          # (起步, 结束) 字节区间，用于 ⑤ 对账
    for anim_name, ni, nm, layout, rest, count, before, ct in plan:
        base, stride, fmt, n, norm, acc = layout
        size = n * COMP[ct][1]
        vals = [int(round(x * norm)) for x in rest] if norm != 1.0 else rest
        for i in range(count):
            off = base + i * stride
            struct.pack_into("<" + fmt * n, bin_, off, *vals)
            touched.append((off, off + size))
        print("   归位 %-28s %-5s %d 帧：首帧 %.1f° → %.1f°"
              % (nm, anim_name, count,
                 qangle(before[0], rest), qangle(read_samples(bin_, layout, 1)[0], rest)))

    # ---- ④ 写回后逐帧复查 ----
    bad = 0
    for anim_name, ni, nm, layout, rest, count, before, ct in plan:
        for q in read_samples(bin_, layout, count):
            if qangle(q, rest) > 1e-3:
                bad += 1
    if bad:
        print("④ 不过：写回后还有 %d 帧没归位" % bad)
        return 1
    print("④ 通过：写回后每一帧都等于目标姿势（差 < 1e-3°）")

    # ---- ⑤ 只改了这些采样：BIN 其余字节逐一相等 ----
    orig = read_glb(src)[2]
    idx = set()
    for a, b in touched:
        idx.update(range(a, b))
    diff = [i for i in range(len(orig)) if i not in idx and orig[i] != bin_[i]]
    if diff:
        print("⑤ 不过：区间外有 %d 个字节被改了（首个偏移 %d）" % (len(diff), diff[0]))
        return 1
    print("⑤ 通过：改动只落在 %d 个采样字节区间内（%d 字节），其余 %d 字节逐一相等"
          % (len(touched), len(idx), len(orig) - len(idx)))

    # ---- ⑥ 网格/蒙皮未动 ----
    js2 = json.loads(json.dumps(js))
    print("⑥ 通过：meshes=%d · skins=%d · POSITION 顶点数=%s（本次不碰网格）"
          % (len(js2.get("meshes", [])), len(js2.get("skins", [])),
             [js2["accessors"][p["attributes"]["POSITION"]]["count"]
              for m in js2.get("meshes", []) for p in m.get("primitives", []) if "POSITION" in p.get("attributes", {})]))

    if dry:
        print("")
        print("--dry：六条自检全绿，但没写盘（要求写盘就去掉 --dry）")
        return 0

    # ---- 重新封装 GLB（JSON 长度可能变，所以要重算 chunk 头）----
    js_bytes = json.dumps(js, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    js_bytes += b" " * ((4 - len(js_bytes) % 4) % 4)
    bin_bytes = bytes(bin_)
    bin_bytes += b"\x00" * ((4 - len(bin_bytes) % 4) % 4)
    total = 12 + 8 + len(js_bytes) + 8 + len(bin_bytes)
    out = bytearray()
    out += struct.pack("<4sII", b"glTF", 2, total)
    out += struct.pack("<II", len(js_bytes), 0x4E4F534A) + js_bytes
    out += struct.pack("<II", len(bin_bytes), 0x004E4942) + bin_bytes
    with open(dst, "wb") as f:
        f.write(out)

    print("")
    print("写出 %s（%d 字节 · 源 %d 字节）" % (dst, total, len(blob)))
    # 写完用**新文件**再读一次，防"以为写对了"（P5）；比对的是**目标值**（--set 时可指定），不是静止姿势
    want_by = {(a, ni): tgt for (a, ni, nm, lay, tgt, cnt, bef, ct) in plan}
    blob3, js3, bin3, _ = read_glb(dst)
    ok = 0
    for an in js3.get("animations", []):
        for ch in an.get("channels", []):
            tgt = ch.get("target", {})
            ni = tgt.get("node")
            if tgt.get("path") != "rotation" or ni is None:
                continue
            if nodes[ni].get("name", "").split(":")[-1] not in names:
                continue
            smp = an["samplers"][ch["sampler"]]
            lay = sample_layout(js3, smp["output"])
            cnt = js3["accessors"][smp["output"]]["count"]
            want = want_by.get((an.get("name"), ni))
            if want is None:
                continue
            worst = max(qangle(q, want) for q in read_samples(bin3, lay, cnt))
            print("   复读 %-5s %-28s 最大偏离目标 %.2f°"
                  % (an.get("name"), nodes[ni].get("name"), worst))
            ok += 1 if worst < 0.5 else 0
    print("   复读通过 %d / %d 条通道（< 0.5° 才算写对）" % (ok, len(plan)))
    return 0 if ok == len(plan) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
