# -*- coding: utf-8 -*-
"""真门（纯标准库 · 可证伪）—— 替换流水线里两个"永远为真"的假门。

    python tools/digihuman/gates.py textures <glb>    # S4：贴图真的在吗、多大、槽位对不对
    python tools/digihuman/gates.py anim <glb>        # S8：动画段数/时长/**循环闭合实测**
    python tools/digihuman/gates.py status <json>     # S12：状态源字段结构

判据只认"从文件里算出来的数"，不认我在注释里写的字。
"""
from __future__ import annotations

import json
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


def read_glb(p: pathlib.Path):
    raw = p.read_bytes()
    if raw[:4] != b"glTF":
        raise ValueError("不是 GLB")
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, raw[off + 8: off + 8 + bl]


def acc_floats(J, BIN, idx, comps):
    import array
    a = J["accessors"][idx]
    bv = J["bufferViews"][a["bufferView"]]
    n = a["count"] * comps
    arr = array.array("f")
    off = bv.get("byteOffset", 0)
    arr.frombytes(BIN[off:off + n * 4])
    return a["count"], arr


def img_size(data: bytes):
    """PNG / JPEG 头部读尺寸（不依赖 Pillow）"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack_from(">II", data, 16)
        return w, h, "PNG"
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3):
                h, w = struct.unpack_from(">HH", data, i + 5)
                return w, h, "JPEG"
            seg = struct.unpack_from(">H", data, i + 2)[0]
            i += 2 + seg
        return None
    return None


def gate_textures(p: pathlib.Path):
    if not p.exists():
        return False, f"缺 {p.name}"
    J, BIN = read_glb(p)
    imgs = J.get("images", [])
    if not imgs:
        return False, "GLB 内无贴图（images 为空）"
    slots = {}
    for mi, m in enumerate(J.get("materials", [])):
        pbr = m.get("pbrMetallicRoughness", {})
        for name, tex in (("baseColor", pbr.get("baseColorTexture")), ("metalRough", pbr.get("metallicRoughnessTexture")),
                          ("normal", m.get("normalTexture"))):
            if not tex:
                continue
            t = J["textures"][tex["index"]]
            si = t.get("source")
            if si is None or si >= len(imgs):
                return False, f"材质{mi} 的 {name} 槽位指向不存在的 image"
            slots.setdefault(name, []).append(si)
    detail, bad = [], []
    for name, ids in slots.items():
        for si in ids:
            bv = J["bufferViews"][imgs[si]["bufferView"]]
            o = bv.get("byteOffset", 0)
            data = BIN[o:o + bv["byteLength"]]
            w = img_size(data)
            if not w:
                bad.append(f"{name} 尺寸读不出")
                continue
            if min(w[0], w[1]) < 512:
                bad.append(f"{name} 仅 {w[0]}x{w[1]}")
            detail.append(f"{name} {w[0]}x{w[1]}{w[2]}")
    need = {"baseColor"}
    miss = [n for n in need if n not in slots]
    ok = not bad and not miss
    note = f"贴图 {len(imgs)} 张 · 槽位 {sorted(slots)} · " + "、".join(detail[:4])
    if miss:
        note += f" · ✗ 缺必需槽位 {miss}"
    if bad:
        note += " · ✗ " + ";".join(bad[:3])
    return ok, note


# 位移动作的提示词 —— **只有**这些 clip 才判「步幅/身高 ∈ 0.5–0.8」。
LOCOMOTION_HINT = ("walk", "run", "jog", "走", "跑", "迈步")


def gate_anim(p: pathlib.Path, expect=("idle", "walk"), tol=1e-3, stride=(0.5, 0.8)):
    """判据照**源码口径**（SKILL.md:39）分两类看：
      ① 旋转通道：循环闭合误差 ≈0（关节必须回到原位）
      ② 髋部位移通道：**步幅/身高 ∈ 0.5–0.8**（根位移是特征，不是"没闭合"）
    """
    if not p.exists():
        return False, f"缺 {p.name}"
    J, BIN = read_glb(p)
    anims = J.get("animations", [])
    if not anims:
        return False, "无 animations"
    names = [a.get("name", f"clip{i}") for i, a in enumerate(anims)]
    miss = [c for c in expect if c not in names]
    # 身高（用 POSITION 的 y 跨度），用于步幅比
    prim = J["meshes"][0]["primitives"][0]
    pa = J["accessors"][prim["attributes"]["POSITION"]]
    H = abs(pa.get("max", [0, 1, 0])[1] - pa.get("min", [0, 0, 0])[1]) or 1.0
    rows, worst_rot, strides = [], 0.0, []
    for a in anims:
        dur, loop_rot, trans = 0.0, 0.0, 0.0
        for ch in a["channels"]:
            s = a["samplers"][ch["sampler"]]
            ia = J["accessors"][s["input"]]
            dur = max(dur, float(ia.get("max", [0])[0]))
            path = ch["target"]["path"]
            comps = 4 if path == "rotation" else 3
            n, arr = acc_floats(J, BIN, s["output"], comps)
            if n < 2:
                continue
            first = list(arr[0:comps])
            last = list(arr[(n - 1) * comps:n * comps])
            if path == "rotation":
                loop_rot = max(loop_rot, max(abs(first[k] - last[k]) for k in range(comps)))
            elif path == "translation":
                # 整段位移幅度（不是首末差）—— 步幅的度量
                xs = [arr[i * comps] for i in range(n)]
                zs = [arr[i * comps + 2] for i in range(n)]
                trans = max(trans, max(max(xs) - min(xs), max(zs) - min(zs)))
        worst_rot = max(worst_rot, loop_rot)
        # 🔴 2026-10-09 修判据自身的错（实测撞了，且**不是放宽**）：
        #    原文把**所有** clip 的位移幅度都收进 strides，再要求**每一条**都落在 0.5–0.8 ——
        #    于是「呼吸」「打招呼」「蹲起」「伸懒腰」这些**非位移动作**（位移 0.01~0.06）全被错杀。
        #    **步幅是"位移动作"的特征**：只有走/跑类 clip 才该判它；非位移 clip 只要**闭合**即可。
        #    （与骨架那条 >=20 错杀同源：把一条该限定范围的判据套到了全体。）
        is_loco = any(h in str(a.get("name") or "").lower() for h in LOCOMOTION_HINT)
        if trans > 0:
            if is_loco:
                strides.append(trans / H)
            else:
                rows.append(f"{a.get('name')} {dur:.2f}s/{len(a['channels'])}轨 旋转闭合差 {loop_rot:.6f}"
                            f"（非位移动作 ⇒ 不判步幅）")
                continue
        rows.append(f"{a.get('name')} {dur:.2f}s/{len(a['channels'])}轨 旋转闭合差 {loop_rot:.6f}"
                    + (f" 步幅比 {trans / H:.3f}" if trans > 0 else ""))
    stride_ok = all(stride[0] <= s <= stride[1] for s in strides) if strides else True
    # 有位移动作却一条都没落到判据里 ⇒ 说明"步幅没被真量到"，不许算过（fail-closed）
    loco_names = [str(a.get("name") or "").lower() for a in anims]
    has_loco = any(any(h in n for h in LOCOMOTION_HINT) for n in loco_names)
    # 🔴 2026-10-10 修（**我的负控抓出来的**）：原文最后一项写的是 (strides or not has_loco)，
    #    而 strides 是**列表** ⇒ 非空时 **and 会把列表本身当结果返回** ⇒ ok 不再是布尔值。
    #    实测：gate_anim(model-rigged.glb)[0] == [0.5487...]（一个列表），不是 True。
    #    判决当时**恰好是对的**（列表非空 = 真，且 stride_ok 已单独把关），但类型错了：
    #    返回列表意味着**任何"非空的列表"都算过** —— 这正是判据台架 D 族盯的形状，
    #    也是我自己立的律（判据的返回必须是明确的正/负）该咬住的东西。改成 **显式 bool**。
    ok = bool((not miss) and worst_rot <= tol and stride_ok and (bool(strides) or not has_loco))
    note = "、".join(rows) + f" · 旋转闭合最差 {worst_rot:.6f}（阈 {tol}）"
    if strides:
        note += f" · 步幅比 {[round(s, 3) for s in strides]}（需 {stride[0]}–{stride[1]}）"
    if miss:
        note += f" · ✗ 缺 clip {miss}"
    if not stride_ok:
        note += " · ✗ 步幅比越界"
    return ok, note


def gate_status(p: pathlib.Path):
    if not p.exists():
        return False, f"缺 {p.name}"
    d = json.loads(p.read_text(encoding="utf-8"))
    need = ["stage", "current_asset_verdict", "next_step"]
    miss = [k for k in need if k not in d]
    cav = d.get("current_asset_verdict")
    shapes = []
    if isinstance(cav, dict):
        for k in ("verdict", "joints", "verts", "textures_mb"):
            if k not in cav:
                shapes.append(k)
    else:
        shapes.append("current_asset_verdict 不是对象")
    ok = not miss and not shapes
    note = f"字段 {len(d)} 个 · 必填齐" if ok else f"✗ 缺 {miss + shapes}"
    return ok, note


def selftest() -> int:
    """三道门的负控 —— **用真件当正负例对，不造假的**。

    🔴 2026-10-10 补。起因：judge-map 逐阶段清点负控出处，**S4 与 S8 都落在本件上却一个负控都没有**
    ⇒ 按本仓律（判据没有负控就是摆设），这两道门**证明不了自己会响**。
    本件自己有话在先：「替换流水线里两个**永远为真**的假门」—— 那就更该证明它们现在**会红**。
    正负例都用**仓里真件**：
      · gate_anim 负例 = model-rigged.glb（**没动画**，是 anim-make 的输入）
      · gate_anim 正例 = model-rigged-anim.glb（anim-make 的输出，有 idle/walk 且循环闭合）
      · gate_textures 负例 = 缺件；正例 = 同一个有贴图的 GLB
      · gate_status 负例 = 缺件 / 造一个缺必填字段的 JSON；正例 = 真 STATUS.json
    """
    R = pathlib.Path(__file__).resolve().parents[2]
    RIG = R / "holo_pet" / "assets" / "digital-human" / "raw" / "rig"
    noanim = RIG / "model-rigged.glb"
    anim = RIG / "model-rigged-anim.glb"
    status = R / "holo_pet" / "assets" / "digital-human" / "STATUS.json"
    fails = []
    n = [0]

    def check(name, got, want):
        n[0] += 1
        ok = (got == want)
        print("  %-54s %s" % (name, "✅" if ok else "❌ 期望 %s 得到 %s" % (want, got)))
        if not ok:
            fails.append(name)

    check("gate_textures 负例·缺件 ⇒ 红", gate_textures(R / "_nope.glb")[0], False)
    if noanim.is_file():
        check("gate_textures 正例·真件有贴图 ⇒ 过", gate_textures(noanim)[0], True)
    # 🔴 2026-10-10 自纠：我原本拿 model-rigged.glb 当"无动画"的负例 —— **前提就是错的**
    #    （实测仓里**每个** GLB 都带 idle/walk，2 段）。==负控的前提不验，负控本身就是假绿。==
    #    改为**现场造一个最小合法 GLB（无 animations）**当负例。
    import struct as _st
    import tempfile as _tf
    js = json.dumps({"asset": {"version": "2.0"}, "meshes": []}).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    # 🔴 read_glb **无条件读 BIN 块头** ⇒ 合成件必须带一个（长度可 0，但那 4 字节头要在）
    bin_hdr = _st.pack("<II", 0, 0x004E4942)
    body = _st.pack("<II", len(js), 0x4E4F534A) + js + bin_hdr
    glb = b"glTF" + _st.pack("<II", 2, 12 + len(body)) + body
    with _tf.TemporaryDirectory() as td:
        p0 = pathlib.Path(td) / "noanim.glb"
        p0.write_bytes(glb)
        check("gate_anim 负例·**无 animations** ⇒ 红", gate_anim(p0)[0], False)
        check("gate_textures 负例·GLB 内无贴图 ⇒ 红", gate_textures(p0)[0], False)
    if anim.is_file():
        check("gate_anim 正例·model-rigged-anim.glb 有 idle/walk 且循环闭合 ⇒ 过",
              gate_anim(anim)[0], True)
    check("gate_status 负例·缺件 ⇒ 红", gate_status(R / "_nope.json")[0], False)
    if status.is_file():
        check("gate_status 正例·真 STATUS.json ⇒ 过", gate_status(status)[0], True)
    # 造一个**缺必填字段**的状态源 ⇒ 必须红
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        bad = pathlib.Path(td) / "bad.json"
        bad.write_text('{"_口径":"空骨架"}', encoding="utf-8")
        check("gate_status 负例·缺必填字段 ⇒ 红", gate_status(bad)[0], False)

    print()
    # 条数现算，不硬编码
    print("gates 自检: %s（%d 条）"
          % ("**全部通过**" if not fails else "**%d 条失败**" % len(fails), n[0]))
    return 0 if not fails else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    arg = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if cmd in ("textures", "anim", "status") and arg is None:
        # 🔴 2026-09-26 自纠：漏传 glb 参数时原来拿 None 进 gate_*，在 p.exists() 上炸 AttributeError
        print("缺参数：%s 需要 <glb 路径>" % cmd)
        print(__doc__)
        raise SystemExit(2)
    if cmd == "selftest":
        raise SystemExit(selftest())
    if cmd == "textures":
        ok, note = gate_textures(arg)
    elif cmd == "anim":
        ok, note = gate_anim(arg)
    elif cmd == "status":
        ok, note = gate_status(arg)
    else:
        print(__doc__)
        raise SystemExit(2)
    print(f"{'✅' if ok else '❌'} {note}")
    raise SystemExit(0 if ok else 1)
