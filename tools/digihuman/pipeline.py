# -*- coding: utf-8 -*-
"""数字人 · 单一编排器（**模型无关**版）

    python tools/digihuman/pipeline.py status              # 全链机检门 + 写账本
    python tools/digihuman/pipeline.py providers           # 本机有哪些后端可用 / 每个能力位会落到谁
    python tools/digihuman/pipeline.py map                 # 阶段地图（含能力位/契约/回退）
    python tools/digihuman/pipeline.py run S3 --dry        # 只打印将由哪个后端执行什么命令
    python tools/digihuman/pipeline.py run S3 --provider blender
    python tools/digihuman/pipeline.py use mesh.decimate=blender   # 写进 .digihuman/config.json

口径（Owner 2026-09-22）：
- **契约与门固定**（阶段/输入输出/判据见技能 references/full-pipeline.md）；
- **"谁来做"可换**：阶段只声明**能力位**（geom.generate / mesh.decimate / rig.auto …），
  由 providers.py 的注册表解析后端；缺后端就**如实说缺**，绝不假装能跑。
"""
from __future__ import annotations

import json
import pathlib
import struct
import subprocess
import sys
import time

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import providers as P                                                    # noqa: E402

WS = pathlib.Path(__file__).resolve().parents[2]
DH = WS / "holo_pet/assets/digital-human"
RIG = DH / "raw/rig"
LEDGER = WS / ".digihuman/ledger.json"
DEEP = "--deep" in sys.argv          # --deep：跑重门（官方运行时验收，需本地服务 8788）

# 🔴 2026-10-09 补：**本仓既有绑骨件**（projects/digital-human/out/dh_rigged.glb，19 骨）用的是
#   Blender 风格命名（upper_arm_L / thigh_R…），不是 Mixamo 风格。原来只认 MIXAMO_TO_VRM ⇒
#   把一份**真的绑好骨、带 6 条动画**的成品判成"缺 VRM 必需骨"。这里把这一套也认下来（同等有效）。
BLENDER_TO_VRM = {
    "hips": "hips", "spine": "spine", "chest": "chest", "upper_chest": "upperChest",
    "neck": "neck", "head": "head",
    "shoulder_L": "leftShoulder", "upper_arm_L": "leftUpperArm",
    "forearm_L": "leftLowerArm", "hand_L": "leftHand",
    "shoulder_R": "rightShoulder", "upper_arm_R": "rightUpperArm",
    "forearm_R": "rightLowerArm", "hand_R": "rightHand",
    "thigh_L": "leftUpperLeg", "shin_L": "leftLowerLeg", "foot_L": "leftFoot",
    "toe_L": "leftToes",
    "thigh_R": "rightUpperLeg", "shin_R": "rightLowerLeg", "foot_R": "rightFoot",
    "toe_R": "rightToes",
}
VRM_REQUIRED = ["hips", "spine", "head", "leftUpperArm", "leftLowerArm", "leftHand",
                "rightUpperArm", "rightLowerArm", "rightHand",
                "leftUpperLeg", "leftLowerLeg", "leftFoot",
                "rightUpperLeg", "rightLowerLeg", "rightFoot"]
MIXAMO_TO_VRM = {
    "Hips": "hips", "Spine": "spine", "Spine1": "chest", "Spine2": "upperChest",
    "Neck": "neck", "Head": "head",
    "LeftShoulder": "leftShoulder", "LeftArm": "leftUpperArm", "LeftForeArm": "leftLowerArm",
    "LeftHand": "leftHand", "RightShoulder": "rightShoulder", "RightArm": "rightUpperArm",
    "RightForeArm": "rightLowerArm", "RightHand": "rightHand",
    "LeftUpLeg": "leftUpperLeg", "LeftLeg": "leftLowerLeg", "LeftFoot": "leftFoot",
    "LeftToeBase": "leftToes", "RightUpLeg": "rightUpperLeg", "RightLeg": "rightLowerLeg",
    "RightFoot": "rightFoot", "RightToeBase": "rightToes",
}


def read_glb(path: pathlib.Path):
    raw = path.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    return J, raw[off + 8: off + 8 + bl]


# ── 门（纯标准库 · 与后端无关）─────────────────────────────────────────────
def gate_glb_refs(path: pathlib.Path):
    J, _ = read_glb(path)
    bv, acc = len(J.get("bufferViews", [])), len(J.get("accessors", []))
    bad = []
    for i, a in enumerate(J.get("accessors", [])):
        if a.get("bufferView", -1) >= bv:
            bad.append(f"accessor{i}")
    for i, im in enumerate(J.get("images", [])):
        if im.get("bufferView", -1) >= bv:
            bad.append(f"image{i}")
    for m in J.get("meshes", []):
        for p in m.get("primitives", []):
            if p.get("indices", 0) >= acc:
                bad.append("indices")
            for tg in p.get("targets", []):
                for v in tg.values():
                    if v >= acc:
                        bad.append("target")
    return (not bad), ("全部合法" if not bad else "越界:" + ",".join(bad[:4]))


def gate_rig(path: pathlib.Path):
    J, BIN = read_glb(path)
    skins = J.get("skins") or []
    if not skins:
        return False, "无 skin"
    joints = skins[0]["joints"]
    def _vrm(nm):
        nm = (nm or "").split(":")[-1]
        return MIXAMO_TO_VRM.get(nm) or BLENDER_TO_VRM.get(nm)
    mapped = {_vrm(J["nodes"][j].get("name", "")) for j in joints}
    miss = [b for b in VRM_REQUIRED if b not in mapped]
    prim = J["meshes"][0]["primitives"][0]
    has_jw = "JOINTS_0" in prim["attributes"] and "WEIGHTS_0" in prim["attributes"]
    import array
    a = J["accessors"][prim["attributes"]["WEIGHTS_0"]]
    b = J["bufferViews"][a["bufferView"]]
    arr = array.array("f"); arr.frombytes(BIN[b.get("byteOffset", 0): b.get("byteOffset", 0) + a["count"] * 16])
    s = [sum(arr[i * 4:i * 4 + 4]) for i in range(a["count"])]
    # 🔴 2026-10-09 修（实测撞了，且**不是放宽**）：
    #    原文写死 len(joints) >= 20 —— 而本仓既有成品 dh_rigged.glb 是 **19 骨**：
    #    15 根 VRM 必需骨**一条不缺** + chest + shoulder_L/R + 权重和恒 1.0000。
    #    VRM Humanoid 必需表本身不含 chest/shoulder/toes ⇒ **19 骨就是完整合法的人形**。
    #    「20」是个拍脑袋的"富余"阈值，把一份真绑好的件错杀（S6 永远过不了）。
    #    ⇒ 判据改成**真正该判的三条**：① 必需骨一条不缺 ② JOINTS/WEIGHTS 齐
    #      ③ 权重和恒 1；骨数下限收到 = 必需骨条数（15），**不是取消下限**。
    ok = (len(joints) >= len(VRM_REQUIRED) and has_jw and not miss
          and abs(min(s) - 1) < 1e-3 and abs(max(s) - 1) < 1e-3)
    return ok, (f"关节 {len(joints)} · VRM 必需骨缺 {len(miss)} · 权重和 {min(s):.4f}~{max(s):.4f}")


def gate_size(path: pathlib.Path, max_mb: float):
    """体积门。🔴 2026-10-09 修：原来**对不存在的产物直接 .stat()** ⇒ 抛 FileNotFoundError，
    在 status/map 里显示成「门异常」—— 那是**门自己崩了**，不是"这一阶段没过"。
    根因：门必须能对"产物还没有"给出**诚实读数**（缺 X），而不是崩。
    同类门（gate_glb_refs / gate_rig）本来就有 exists 检查，只有这一个是漏的。"""
    path = pathlib.Path(path)
    if not path.exists():
        return False, f"缺: {path.name}"
    if path.is_file() and path.stat().st_size == 0:
        return False, f"空文件: {path.name}"
    mb = path.stat().st_size / 1024 / 1024
    return mb <= max_mb, f"{mb:.2f} MB（上限 {max_mb}）"


def gate_render() -> tuple:
    """**S12 的渲染面**：图在不在 + **它是不是当前这个 rig 渲的**。

    🔴 2026-10-10 补：S12 声明的能力位是 render.shot，但门原来**只查 STATUS.json 的字段结构**，
    从来没有渲染过任何东西（现读 render/ 与 shot/ 都是 0 个）。
    照 S2 那条假绿的教训，装真判据 + **绑源哈希**：
      · 图不在 / 边车不在                        ⇒ 红（说清怎么渲）
      · 边车里的「源sha256」≠ 当前 rig 的 sha256  ⇒ 红（**这张图是旧 rig 渲的**，复核已失效）
      · 两者一致                                  ⇒ 绿（附图哈希与时间）
    """
    import hashlib
    img = DH / "render" / "latest.png"
    sc = DH / "render" / "latest.json"
    rig = RIG / "model-rigged-anim.glb"
    if not img.is_file():
        return False, "缺渲染图 holo_pet/assets/digital-human/render/latest.png（跑 tools/digihuman/render-shot.py）"
    if not sc.is_file():
        return False, "缺渲染回执 latest.json（**没有回执就分不清这张图是哪个 rig 渲的**）"
    try:
        rec = json.loads(sc.read_text(encoding="utf-8"))
    except Exception as e:                                            # noqa: BLE001
        return False, f"回执读不了: {type(e).__name__}"
    was, now = rec.get("源sha256") or "", ""
    if rig.is_file():
        now = hashlib.sha256(rig.read_bytes()).hexdigest()
    if not now:
        return False, "缺 rig（model-rigged-anim.glb）—— 没法比对"
    if not was:
        return False, "回执**没有绑定源哈希**（旧格式，无法证明是当前 rig 渲的）"
    if was != now:
        return False, f"**渲染已失效** —— rig 换过了（回执 {was[:12]}… ≠ 现在 {now[:12]}…）⇒ 重渲"
    # 🔴 2026-10-10 同一条理再咬一格：**观色参数也是"源"**。
    #    改 state/digihuman/render-preset.json（取景/光照/色调映射）而没重渲 ⇒ 这张图不再代表当前观色。
    pre = WS / "state" / "digihuman" / "render-preset.json"   # 本件里根是 WS，不是 ROOT
    was_p = rec.get("预设sha256") or ""
    now_p = hashlib.sha256(pre.read_bytes()).hexdigest() if pre.is_file() else ""
    if now_p and was_p and was_p != now_p:
        return False, (f"**渲染已失效** —— 观色预设改过了"
                       f"（回执 {was_p[:12]}… ≠ 现在 {now_p[:12]}…）⇒ 按新预设重渲")
    if now_p and not was_p:
        return False, "回执**没有记录观色预设哈希**（旧格式）⇒ 重渲一次"
    return True, (f"渲染 {img.name} {rec.get('字节', 0)/1024:.0f}KB · 源哈希吻合 {now[:12]}… · "
                  f"预设吻合 {now_p[:12] if now_p else 'n/a'}… · {rec.get('at')} · {rec.get('取景', '')}")


def gate_clarity() -> tuple:
    """S12 的**清晰度面**：跑**规程自己的量规** tools/codex-scripts/measure-clarity.py。

    🔴 2026-10-10 补（照视频那条链刚学到的做法：**把"它自己的判据"叠上去，不是只留我的**）：
    数字人规程（skills/digihuman-pipeline）第 9 阶段写明了要 measure-clarity.py 出**客观读数**，
    而我一次没用过 —— S12 原来只看"状态源结构 + 渲染源哈希"。
    量规给三件我肉眼**看不出量级**的读数：轮廓锯齿度 / 脸部高光占比 / 梯度方差。
    现读三件（正是它教会我的一课）：
      · render/latest.png（S12 产物）   锯齿 0.312 · 脸部高光 4.10% · 梯度方差 28.9
      · 早期观色版 dh-v2-preview.png    锯齿 **0.236** · 脸部高光 **10.11%** · 梯度方差 **50.6**
      · T-pose 参考图                   脸部高光 **66.74%** ⇒ **脸几乎全白**
        —— 我先前肉眼只说得出"脸偏白、贴图没带上"，量规把它变成了 66.74% 这个数。
    本门**只报读数、不设阈值**：清晰度好不好是审美，按本仓口径归人看；机检只保证"量过、数是真读的"。
    """
    p = WS / "tools" / "codex-scripts" / "measure-clarity.py"
    img = DH / "render" / "latest.png"
    if not p.is_file():
        return False, "缺 measure-clarity.py（规程自己的量规没得跑）"
    if not img.is_file():
        return False, "缺渲染图（先跑 render-shot.py）"
    r = subprocess.run([sys.executable, "-X", "utf8", str(p), str(img)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    line = (r.stdout or "").strip().splitlines()
    if not line:
        return False, "量规没出读数：%s" % ((r.stderr or "")[:80])
    return True, "规程量规: " + line[-1].strip()


def gate_frame(min_h=0.55, min_w=0.20) -> tuple:
    """⚠️ **本条我实测过：它抓不住那张坏图**（坏图也报"主体占高 71%" —— 它把**地面**算进去了）。

    ⇒ 按本仓律（**判据没有负控就是摆设**），我**不把它当判过用**：本函数**只出读数**，
      真正的判过权交给下面 gate_review()（**没人看过的图不许自动判过**）。
      留在这里是因为"主体占高/占宽"仍是**有用的读数** —— 但它**不够格单独判**。
    """
    """S12 的**取景面**：主体在画面里占得够不够（全身像该占满多数画高）。

    🔴 2026-10-10 加这一条的真原因（**我自己栽的**）：
      S12 的三层门（状态源结构 / 渲染绑哈希 / 规程量规）**没有一条看"这画面对不对"**，
      而渲出来的图**主体只占画幅上半、下半整片是地面**，流水线**照样报 ✅**。
      我连着排查了 8 轮（清动画、验相机矩阵、换正对机位）**都没找到根因** ——
      ⇒ 那就先**把门装上**：**没人看过的图，不许自动判过。**
    量法（剪影，不依赖白底）：取非背景像素的包围盒，核**占高**与**占宽**。
      全身像：占高应 ≥ min_h（默认 0.55）；主体太窄说明只框到一条腿/一只胳膊。
    **这是"有没有框住全身"的下限判据，不是审美判据** —— 好不好看归人看。
    """
    img = DH / "render" / "latest.png"
    if not img.is_file():
        return False, "缺渲染图（先跑 render-shot.py）"
    try:
        import numpy as np
        from PIL import Image
    except Exception:                                                  # noqa: BLE001
        return False, "PIL/numpy 不在，取景判不了"
    a = np.asarray(Image.open(img).convert("RGB"), np.float32)
    corners = np.concatenate([a[:8, :8].reshape(-1, 3), a[:8, -8:].reshape(-1, 3),
                              a[-8:, :8].reshape(-1, 3), a[-8:, -8:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    mask = np.linalg.norm(a - bg, axis=2) > 40
    H, W = mask.shape[:2]
    # 背景是渐变/地面时"非背景"会占满 ⇒ 改用**每行的变化量**找主体带：
    # 主体行 = 该行像素标准差明显高于全图背景行
    row_std = mask.std(axis=1)
    body_rows = np.where(row_std > max(0.02, float(np.percentile(row_std, 60))))[0]
    if len(body_rows) < 20:
        return False, "**找不到主体**（整幅近乎均匀 ⇒ 没框住人或图是空的）"
    h_ratio = (body_rows.max() - body_rows.min() + 1) / H
    ys, xs = np.where(mask)
    w_ratio = ((xs.max() - xs.min() + 1) / W) if len(xs) else 0.0
    ok = h_ratio >= min_h and w_ratio >= min_w
    return ok, ("主体占高 %.0f%%（应≥%.0f%%）· 占宽 %.0f%%（应≥%.0f%%）%s"
                % (100 * h_ratio, 100 * min_h, 100 * w_ratio, 100 * min_w,
                   "" if ok else " ⇒ **没框住全身**（下半截空着/只框到一段）"))


def gate_review() -> tuple:
    """S12 的**复核面**：渲染图必须**被看过**，且复核记录**绑到这张图的哈希**。

    🔴 2026-10-10 这一条是我这轮最实在的产出。
    经过：S12 三层门（状态源结构 / 渲染绑哈希 / 规程量规）**没有一条看"这画面对不对"**，
    而 render/latest.png **主体只占画幅上半、下半整片是地面**，流水线**照样报 ✅**。
    我连查 8 轮（清动画 / 验相机矩阵 / 换正对机位 / 试取景判据）**都没找到根因**，
    而且我自己写的取景判据**被测出抓不住它**。
    ⇒ 那就别再假装机检能兜住：**用 S2 那套已经验证过的做法** ——
      **复核记录 + 图片哈希**；哈希不符或没记录 ⇒ **红（"没人看过"）**。
    **这不是"又多一条判据"，而是承认机检的边界**：有些东西只能人看，那就要人看过的凭据。
    """
    import hashlib
    img = DH / "render" / "latest.png"
    rec_p = WS / "state" / "digihuman" / "render-review.json"
    if not img.is_file():
        return False, "缺渲染图（先跑 render-shot.py）"
    now = hashlib.sha256(img.read_bytes()).hexdigest()
    if not rec_p.is_file():
        return False, ("**这张图还没人看过** —— 复核记录 %s 不在；看过之后跑 "
                       "py -3.14 tools/digihuman/review-render.py --by <复核人> [--fail 说明]"
                       % rec_p.name)
    try:
        rec = json.loads(rec_p.read_text(encoding="utf-8"))
    except Exception as e:                                             # noqa: BLE001
        return False, "复核记录读不了: %s" % type(e).__name__
    was = rec.get("图sha256") or ""
    if not was:
        return False, "复核记录**没绑图片哈希**（旧格式，无法证明它看的是现在这张图）"
    if was != now:
        return False, ("**复核已失效** —— 图换过了（记录 %s… ≠ 现在 %s…）⇒ 重看"
                       % (was[:12], now[:12]))
    if rec.get("结论") != "通过":
        return False, "复核结论**不是通过**：%s" % (rec.get("说明") or "（未写说明）")
    return True, ("已复核（%s @ %s）· 图哈希吻合 %s…"
                  % (rec.get("复核人"), rec.get("at"), now[:12]))


def gate_exists(paths):
    paths = [pathlib.Path(x) for x in paths]
    # 目录也算存在（Windows 上目录 st_size 常为 0 —— 踩过两次）
    miss = [p for p in paths if not p.exists() or (p.is_file() and p.stat().st_size == 0)]
    return (not miss), ("齐全" if not miss else "缺: " + ", ".join(p.name for p in miss))


def gate_sub(script: str, args=()):
    r = subprocess.run([sys.executable, str(WS / script), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    lines = (r.stdout or r.stderr or "").strip().splitlines()
    return r.returncode == 0, (lines[-1].replace("S10 门: ", "").replace("S7 门: ", "") if lines else "无输出")


S = lambda **kw: kw                                                     # noqa: E731
STAGES = [
    S(id="S0", name="素材与合规", cap=None, ins=[], outs=[DH / "raw/S0/ref.png"],
      gate=lambda: gate_exists([DH / "raw/phase2a-tpose/T-pose参考-规范化.png"]),
      note="参考图（本仓现有：phase2a-tpose/T-pose参考-规范化.png）", fallback="换更清晰正面全身图"),
    S(id="S1", name="几何生成", cap="geom.generate", ins=[], outs=[DH / "raw/phase1/model.glb"],
      gate=lambda: gate_exists([DH / "raw/phase1/tripo-out"]),
      note="任一图生 3D 后端；产出带贴图的网格", fallback="多视图 / 换模型 / 本地 GPU 模型"),
    S(id="S2", name="姿态规范(T-pose)", cap=None, ins=[], outs=[],
      gate=lambda: gate_sub("tools/digihuman/tpose-check.py"),
      note="机检 4 项（双臂水平/双腿直立/直立/白底）+ 人眼 1 项（无遮挡）", fallback="重生成或手摆"),
    S(id="S3", name="重拓扑/分部位LOD", cap="mesh.decimate", ins=[], outs=[RIG / "model-springs-chains.glb"],
      gate=lambda: gate_size(RIG / "model-springs-chains.glb", 12),
      note="分部位 LOD：脸保密度、身体狠削；保 UV 需 blender/pymeshlab(PLY)", fallback="本地 QEM(PLY) → Blender"),
    S(id="S4", name="UV + PBR 贴图", cap="geom.texture", ins=[], outs=[],
      gate=lambda: gate_sub("tools/digihuman/gates.py",
                            ("textures", str(RIG / "avatar.vrm"))), note="材质槽解析（真读 images 尺寸）", fallback="4K 重烘 / 本地重采样"),
    S(id="S5", name="标准骨架(VRM Humanoid)", cap="rig.auto", ins=[], outs=[RIG / "skeleton.json"],
      gate=lambda: gate_exists([RIG / "skeleton.json"]), note="15 必需骨 + 父子固定关系", fallback="Mixamo / SkinTokens(需 Blender)"),
    S(id="S6", name="蒙皮权重", cap="skin.auto", ins=[], outs=[RIG / "model-rigged-anim.glb"],
      gate=lambda: gate_rig(RIG / "model-rigged-anim.glb") if (RIG / "model-rigged-anim.glb").exists() else (False, "缺"),
      note="权重和=1 · 布料归髋", fallback="区域规则手改"),
    S(id="S7", name="表情/BlendShape", cap="expr.make", ins=[], outs=[RIG / "model-expressions.glb"],
      gate=lambda: gate_sub("tools/digihuman/expr-make.py") if (RIG / "model-expressions.glb").exists() else (False, "缺"),
      note="morph targets + VRMC_vrm.expressions（blink/aa/happy）", fallback="材质驱动表情"),
    S(id="S8", name="动画/重定向", cap="anim.make", ins=[], outs=[RIG / "model-rigged-anim.glb"],
      gate=lambda: gate_sub("tools/digihuman/gates.py",
                            ("anim", str(RIG / "model-rigged-anim.glb"))),
      note="循环类必须闭合（**实测**首末帧差，不写死在注释里）", fallback="Mixamo/动捕重定向（同骨架可换库）"),
    S(id="S9", name="次级动力学", cap="mesh.spring", ins=[], outs=[RIG / "model-springs-chains.glb"],
      gate=lambda: gate_exists([RIG / "model-springs-chains.glb"]), note="链 ≥2 关节（VRM 硬要求）", fallback="先修父骨激励"),
    S(id="S10", name="标准格式封装(VRM)", cap="pack.vrm", ins=[], outs=[RIG / "avatar.vrm"],
      gate=lambda: gate_sub("tools/digihuman/vrm-pack.py", ("--check",)),
      note="VRMC_vrm.humanoid/expressions + VRMC_springBone + meta", fallback="纯 GLB + 自定义扩展"),
    S(id="S11", name="Web 运行时", cap=None, ins=[], outs=[DH / "web/avatar.html"],
      gate=lambda: (gate_exists([DH / "web/avatar.html"]) if not DEEP else
                    (gate_sub("tools/digihuman/vrm-runtime-check.py",
                              ("/gbt-master/fs/holo_pet/assets/digital-human/raw/rig/avatar-vrm-check.glb",))
                     if gate_exists([DH / "web/avatar.html"]) else (False, "缺 avatar.html"))),
      note="three.js / three-vrm · --deep 时用**官方运行时**亲自读 avatar.vrm", fallback="自写 springBone（本仓已实现）"),
    S(id="S12", name="验收(客观+人眼)", cap="render.shot", ins=[], outs=[DH / "STATUS.json"],
      # 🔴 2026-10-10 修：原来**只查 STATUS.json 字段结构**，而 render.shot 这个声明能力位
      #    **从来没有渲染过任何东西**（现读 render/ 与 shot/ 都是 0 个）。
      #    现在两条一起判：① 状态源结构（既有）② **渲染图 + 回执且绑到当前 rig 哈希**（新）。
      # 三层一起判：① 状态源结构 ② 渲染图与源哈希吻合 ③ **规程自己的量规出过读数**
      # 四层：① 状态源结构 ② 渲染绑哈希 ③ 规程量规 ④ **复核（没人看过不许自动判过）**
      #   注：gate_frame 只出读数、**不参与判过**（我实测它抓不住坏图，见其 docstring）
      gate=lambda: (lambda a, b, c, d, e: ((a[0] and b[0] and c[0] and d[0]),
                                           " · ".join(x[1] for x in (a, b, c, d, e) if x[1])))(
          gate_sub("tools/digihuman/gates.py", ("status", str(DH / "STATUS.json"))),
          gate_render(), gate_clarity(), gate_review(), gate_frame()),
      note="状态源字段结构 + 渲染与源哈希吻合 + **规程量规客观读数**（锯齿/脸部高光/梯度方差）",
      fallback="人眼看图"),
    S(id="S13", name="发布与账本", cap=None, ins=[], outs=[LEDGER],
      gate=lambda: gate_exists([DH / "STATUS.json"]), note="哈希/来源/许可；废物不上线", fallback="—"),
]


def run_gates(verbose=True):
    rows = []
    for st in STAGES:
        try:
            ok, note = st["gate"]()
        except Exception as e:
            ok, note = False, f"门异常: {type(e).__name__}: {str(e)[:60]}"
        rows.append((st["id"], st["name"], ok, note))
        if verbose:
            print(f"  {'✅' if ok else '❌'} {st['id']:>3} {st['name']:<22} {note}")
    return rows


def ledger_write(rows):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    data = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stages": [{"id": i, "name": n, "ok": ok, "note": note} for i, n, ok, note in rows],
            "pass": sum(1 for r in rows if r[2]), "total": len(rows),
            "providers": {k: v for k, v in P.availability().items()}}
    LEDGER.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def cmd_providers():
    print("后端可用性（本机实测）")
    av = P.availability()
    for k, v in av.items():
        flag = "✅" if v["ok"] is True else ("⚠️" if v["ok"] is None else "❌")
        print(f"  {flag} {k:<10} {v['note']}")
    print("\n能力位 → 当前会落到谁（模型无关解析：显式 → 配置 → 可用顺序）")
    for cap in P.CAPS:
        who, why = P.resolve(cap)
        print(f"  {'✅' if who else '❌'} {cap:<16} → {who or ('无可用：' + (why or ''))}")


def cmd_map():
    print("阶段地图（能力位驱动 · 模型无关）")
    for st in STAGES:
        print(f"\n{st['id']} · {st['name']}   能力位: {st['cap'] or '（人工/本仓固定）'}")
        print(f"  判据  : {st['gate']()[1]}")
        print(f"  说明  : {st['note']}")
        print(f"  回退  : {st['fallback']}")


def selftest() -> int:
    """给 pipeline **自己的**那些门配负控（正例必过 · 负例必红）。

    🔴 2026-10-10 补。起因：judge-map 逐阶段清点负控出处，14 个阶段里**只有 S2 一个**能找到
    selftest（在 tpose-check.py 里），其余 8 个阶段的门都落在 pipeline.py 自己身上却**一个负控都没有**
    ⇒ 按本仓律（判据没有负控就是摆设），那些门**证明不了自己会响**。
    本函数补上：每一条都**先造负例（必须红）再造正例（必须过）**，全过才算通过。
    **用的是临时文件，不碰任何真产物。**
    """
    import tempfile
    fails = []

    total = [0]

    def check(name, got, want):
        total[0] += 1
        ok = (got == want)
        print("  %-52s %s" % (name, "✅" if ok else "❌ 期望 %s 得到 %s" % (want, got)))
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)

        # ── gate_size：**注意单位是 MB**（我第一版按字节写，判据当场就错了 —— 靠这条自检抓到）
        small = t / "small.bin"; small.write_bytes(b"x" * 512)          # 0.000488 MB
        check("gate_size 负例·超体量（512B > 上限 0.0001MB ⇒ 红）", gate_size(small, 0.0001)[0], False)
        big = t / "big.bin"; big.write_bytes(b"x" * 4096)               # 0.0039 MB
        check("gate_size 正例（4KB ≤ 上限 0.01MB ⇒ 过）", gate_size(big, 0.01)[0], True)
        check("gate_size 负例·缺件 ⇒ 红", gate_size(t / "nope.bin", 1)[0], False)
        empty = t / "empty.bin"; empty.write_bytes(b"")
        check("gate_size 负例·空文件 ⇒ 红", gate_size(empty, 1)[0], False)

        # ── gate_exists：缺件必须红
        check("gate_exists 负例（缺件 ⇒ 红）", gate_exists([t / "nope.bin"])[0], False)
        check("gate_exists 正例（在 ⇒ 过）", gate_exists([big])[0], True)

        # ── gate_sub：判据件说红时必须红（用 python -c 造一个恒定红/恒定绿的子判据）
        redp = t / "always_red.py"; redp.write_text("import sys;print('红');sys.exit(1)", encoding="utf-8")
        grnp = t / "always_green.py"; grnp.write_text("import sys;print('绿');sys.exit(0)", encoding="utf-8")
        check("gate_sub 负例（子判据 rc=1 ⇒ 红）", gate_sub(str(redp), ())[0], False)
        check("gate_sub 正例（子判据 rc=0 ⇒ 过）", gate_sub(str(grnp), ())[0], True)

        # ── gate_review：没记录必须红（**真产物不碰**：只核"记录不存在时会不会红"）
        rec = WS / "state" / "digihuman" / "render-review.json"
        if not rec.is_file():
            check("gate_review 负例（无复核记录 ⇒ 红）", gate_review()[0], False)
        else:
            print("  %-52s ⏭ 跳过（已有真复核记录，不去动它）" % "gate_review 负例")

    print()
    # 条数**现算**，不硬编码（我第一版写死 8，而实际跑了 9 条 —— 读数不能自己编）
    print("pipeline 门自检: %s（%d 条）"
          % ("**全部通过**" if not fails else "**%d 条失败**" % len(fails), total[0]))
    return 0 if not fails else 1


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else "status"
    if cmd == "selftest":
        return selftest()
    if cmd == "providers":
        cmd_providers(); return
    if cmd == "map":
        cmd_map(); return
    if cmd in ("status", "verify"):
        print("数字人流水线 · 全链门检（机检项 · 与后端无关）")
        d = ledger_write(run_gates())
        print(f"\n  通过 {d['pass']}/{d['total']} · 账本 → {LEDGER.relative_to(WS)}")
        return
    if cmd == "use":
        if len(a) < 2 or "=" not in a[1]:
            print("用法: use <能力位>=<后端>   例: use mesh.decimate=blender"); return
        cap, prov = a[1].split("=", 1)
        if cap not in P.CAPS:
            print(f"未知能力位 {cap}；可选：{', '.join(P.CAPS)}"); return
        if prov not in P.PROVIDERS:
            print(f"未知后端 {prov}；可选：{', '.join(P.PROVIDERS)}"); return
        cfg = P.load_config(); cfg[cap] = prov; P.save_config(cfg)
        print(f"已写入配置：{cap} → {prov}（.digihuman/config.json）"); return
    if cmd == "run":
        if len(a) < 2:
            print("用法: run <S0..S13> [--dry] [--provider <后端>]"); return
        st = next((s for s in STAGES if s["id"].lower() == a[1].lower()), None)
        if not st:
            print(f"没有这个阶段: {a[1]}"); return
        # 🔴 2026-09-26 自纠：--provider 恰为末参时 a[i+1] 会 IndexError
        _pi = a.index("--provider") if "--provider" in a else -1
        prefer = a[_pi + 1] if _pi != -1 and _pi + 1 < len(a) else None
        dry = "--dry" in a
        if not st["cap"]:
            print(f"[{st['id']}] {st['name']}：人工/本仓固定环节\n  {st['note']}\n  回退: {st['fallback']}")
            if not dry:
                ok, note = st["gate"]()
                print(f"  门: {'✅' if ok else '❌'} {note}")
            return
        who, why = P.resolve(st["cap"], prefer=prefer)
        if not who:
            print(f"❌ {st['id']} 需要能力位 {st['cap']}，但本机没有可用后端：{why}")
            print(f"   → 装/登录任一支持该能力的后端，或 `use {st['cap']}=<后端>` 指定"); return
        if prefer and who != prefer:
            print(f"ℹ️ 指定后端 {prefer} 不可用 ⇒ 按可用顺序回退到 **{who}**")
        tmpl = (P.PROVIDERS[who]["cmds"] or {}).get(st["cap"], "")
        print(f"[{st['id']}] {st['name']} · 能力位 {st['cap']} → 后端 **{who}**")
        print(f"  成本: {P.PROVIDERS[who]['cost']}\n  坑: {P.PROVIDERS[who]['notes']}\n  命令: {tmpl or '（该后端未声明模板）'}")
        if dry:
            return
        if not tmpl:
            print("  该后端未声明可执行模板 ⇒ 按它的 notes 人工执行"); return
        r = subprocess.run(tmpl, shell=True, cwd=str(WS))
        ok, note = st["gate"]()
        print(f"  退出码 {r.returncode} · 门: {'✅' if ok else '❌'} {note}")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
