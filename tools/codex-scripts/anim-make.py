# -*- coding: utf-8 -*-
"""Phase 3 · 动画烘焙器：在**我们自己的 22 骨骨架**上写关键帧 → 烘成 glTF 动画（本地、零积分）

坐标口径（由数据实测得出，不是猜）：
  模型高度 = Y · 臂轴 = Z（双臂沿 Z 展开）· 正面 = +X
  ⇒ 腿/躯干前摆 = 绕 Z 正角 · 手臂前后摆 = 绕 Y · 扭转/头部左右 = 绕 Y · 侧倾 = 绕 X
每条 clip 都要**首末帧闭合**（循环无跳变），并输出读数：时长 / 通道数 / 闭合误差 / 根位移。

用法: python tools/codex-scripts/anim-make.py
"""
import json
import math
import os
import pathlib
import struct
import numpy as np

# 复合模式（可扫；见 build_clip 里的说明）：W_BD / W_DB / L_B
MODE = os.environ.get("GBT_ANIM_MODE", "W_BD")
# 幅度系数（可扫）：臂 / 腿 的**增量**各乘一个系数（BASE 不动）
ARM_K = float(os.environ.get("GBT_ANIM_ARM", "1.0"))
LEG_K = float(os.environ.get("GBT_ANIM_LEG", "1.0"))
_ARM = ("LeftShoulder", "RightShoulder", "LeftArm", "RightArm",
        "LeftForeArm", "RightForeArm", "LeftHand", "RightHand")
_LEG = ("LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg",
        "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase")

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SRC = DH / "raw/rig/model-rigged.glb"                 # 低模绑骨件（动画挂它：小、快、随时可换高模）
OUT = DH / "raw/rig/model-rigged-anim.glb"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytearray(raw[off + 8: off + 8 + bl])
del raw

bone_node = {nd["name"].replace("mixamorig:", ""): i for i, nd in enumerate(J["nodes"]) if (nd.get("name") or "").startswith("mixamorig:")}
print(f"骨架节点 {len(bone_node)} 个")


# ── 世界轴 → 骨局部 的共轭换算（**采用 dh_rig.py 的同一条数学**，不另发明）──────
# 🔴 2026-10-10 修：本件原来把 walk/idle 的**世界轴增量**直接**逐轴加进骨局部欧拉角**
#    （add_pose 的"角度相加"）。这只有在"骨局部轴 ≈ 世界轴"时才近似成立：
#      · Mixamo **上臂**的局部轴与世界差得远 ⇒ 摆幅被压到 **44%**（实测）
#      · **腿**差得近 ⇒ 摆幅反被放到 **2 倍**（实测 1.59 / 2.11）
#      · 左右还严重不对称（独立离地 2 帧 vs 12 帧；规程正解 18 / 14）
#    本仓规程（docs/数字人-绑骨与全肢体动作.md 第 241 行）写着正解：
#      「方向一律用**世界轴/世界目标方向**驱动，通过对 bone.matrix_local 求逆换算到骨局部，
#        **不猜骨局部轴**」—— 而且它记着第一版踩坑（常数方向 ⇒ 末帧 141.6° 臂旋转 ⇒ 壳拉成刀片）。
#    glTF 层的等价式（节点旋转是**父相对**的）：
#      new_local = conj(P_world, q_world) @ q_base_local        conj(P,q) = P⁻¹·q·P
#    P_world = 该骨**父节点**在静止姿势下的世界朝向（自根向下累乘静止旋转）。
def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz], np.float32)


def _qconj_by(p, q):
    """把世界旋转 q 按 p 共轭到 p 的局部系（p 须为单位四元数）。"""
    pinv = np.array([-p[0], -p[1], -p[2], p[3]], np.float32)
    return _qmul(_qmul(pinv, q), p)


IDENT = np.array([0.0, 0.0, 0.0, 1.0], np.float32)
_PARENT = {}
for _i, _nd in enumerate(J["nodes"]):
    for _c in (_nd.get("children") or []):
        _PARENT[_c] = _i


def _node_rest(i):
    """该骨**自己**的静止局部旋转（节点 rotation 现读；无则单位阵）。"""
    q = J["nodes"][i].get("rotation")
    return np.array(q, np.float32) if q else IDENT.copy()


def _node_rest_by_name(name):
    i = bone_node.get(name)
    return _node_rest(i) if i is not None else IDENT.copy()


_PW = {}


# ── 解析 2 连杆 IK（**移植自 dh_rig.py 第 1055 行 leg_ik，逐行同数学**）──────────
# 🔴 2026-10-10 移植的三前提（都已现读确认）：
#   ① 几何量：L1(大腿)=0.2335 · L2(小腿)=0.2315 · 髋/膝/踝静止位置（从节点层级现算）
#   ② 沿骨轴在**该骨自己的局部系**里 = **+Y**（LeftUpLeg/LeftLeg/LeftFoot 都是）
#   ③ 左右互为镜像（右腿 Y/Z 取反）—— 已在 walk 里修
#   而"支撑脚踩住地面"这条判据（同帧位移 <0.2×抬脚量）**摆角度做不到**：髋一摆支撑脚就动 31%。
#   ⇒ 按目标①「不手搓平行实现」：**搬本仓既有那段解析 IK**，不另发明。
def _qrot(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return np.array([vx + w * tx + (y * tz - z * ty),
                     vy + w * ty + (z * tx - x * tz),
                     vz + w * tz + (x * ty - y * tx)], np.float64)


def _rot_diff(a, b):
    """把单位向量 a 转到 b 的四元数（q·a = b）。"""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    a = a / max(1e-12, float(np.linalg.norm(a)))
    b = b / max(1e-12, float(np.linalg.norm(b)))
    d = float(np.dot(a, b))
    if d > 1.0 - 1e-9:
        return IDENT.copy()
    if d < -1.0 + 1e-9:
        ax = np.cross(a, np.array([1.0, 0.0, 0.0]))
        if float(np.linalg.norm(ax)) < 1e-6:
            ax = np.cross(a, np.array([0.0, 1.0, 0.0]))
        ax = ax / max(1e-12, float(np.linalg.norm(ax)))
        return np.array([ax[0], ax[1], ax[2], 0.0], np.float32)
    c = np.cross(a, b)
    q = np.array([c[0], c[1], c[2], 1.0 + d], np.float64)
    return (q / max(1e-12, float(np.linalg.norm(q)))).astype(np.float32)


def _rest_world_rt(name):
    """沿父链累乘 (t, r) ⇒ (该骨的世界静止位置, 世界静止朝向)。"""
    i = bone_node.get(name)
    if i is None:
        return np.zeros(3), IDENT.copy()
    chain = []
    while i is not None:
        chain.append(i)
        i = _PARENT.get(i)
    pos = np.zeros(3)
    rot = IDENT.copy()
    for k in reversed(chain):
        t = np.array(J["nodes"][k].get("translation") or [0, 0, 0], np.float64)
        pos = pos + _qrot(rot, t)
        rot = _qmul(rot, _node_rest(k))
    return pos, rot


_HIPS_REST_POS, _HIPS_REST_ROT = _rest_world_rt("Hips")
# Hips 节点在**父空间**的静止 translation（位移通道必须写成"它 + 增量"，不能覆盖它）
_HIPS_REST_T = [float(v) for v in (J["nodes"][bone_node["Hips"]].get("translation") or [0.0, 0.0, 0.0])]
_LEGS = {}
for _s, _trio in (("L", ("LeftUpLeg", "LeftLeg", "LeftFoot")),
                  ("R", ("RightUpLeg", "RightLeg", "RightFoot"))):
    _hp, _ = _rest_world_rt(_trio[0])
    _kp, _ = _rest_world_rt(_trio[1])
    _ap, _ = _rest_world_rt(_trio[2])
    _LEGS[_s] = {"up": _trio[0], "lo": _trio[1], "ft": _trio[2],
                 "hip": _hp, "knee": _kp, "ankle": _ap,
                 "L1": float(np.linalg.norm(_kp - _hp)), "L2": float(np.linalg.norm(_ap - _kp))}


def _leg_ik(hip_pos, ankle_target, L1, L2, bend):
    """**移植自 dh_rig.py 的 leg_ik**：给定髋位与脚踝目标 ⇒ (大腿方向, 小腿方向, 膝位)。"""
    hp = np.asarray(hip_pos, np.float64)
    tgt = np.asarray(ankle_target, np.float64)
    Pv = tgt - hp
    n = float(np.linalg.norm(Pv))
    d = max(abs(L1 - L2) + 1e-4, min(L1 + L2 - 1e-4, n))
    dirv = Pv / max(1e-9, n) if n > 1e-9 else np.array([0.0, -1.0, 0.0])
    ca = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
    al = math.acos(max(-1.0, min(1.0, ca)))
    bend = np.asarray(bend, np.float64)
    bend = bend / max(1e-12, float(np.linalg.norm(bend)))
    ax = np.cross(dirv, bend)
    if float(np.linalg.norm(ax)) < 1e-6:
        ax = np.cross(dirv, np.array([0.0, 0.0, 1.0]))
    ax = ax / max(1e-12, float(np.linalg.norm(ax)))
    best = None
    for sgn in (1.0, -1.0):
        ang = sgn * al
        h = ang / 2.0
        q = np.array([ax[0] * math.sin(h), ax[1] * math.sin(h), ax[2] * math.sin(h), math.cos(h)], np.float64)
        td = _qrot(q, dirv)
        kn = hp + L1 * td
        score = float(np.dot((kn - hp) / max(1e-9, L1), bend))
        if best is None or score > best[0]:
            best = (score, td, kn)
    _, thigh_d, knee_p = best
    return thigh_d, (tgt - knee_p), knee_p


def _by_dir_anim(name, parent_world, target_dir):
    """把该骨指向世界方向 target_dir（**移植 dh_rig 的 by_dir**）⇒ (局部四元数, 该骨世界朝向)。"""
    R = _node_rest(bone_node[name])
    base = _qmul(parent_world, R)
    d0 = _qrot(base, np.array([0.0, 1.0, 0.0]))       # 沿骨方向（局部 +Y，已验）
    q = _rot_diff(d0, target_dir)
    local = _qmul(_qconj_by(parent_world, q), R)
    return local, _qmul(parent_world, local)


def _leg_walk_ik(side, phase, hips_world, pelvis_y):
    """一条腿走 IK：踝目标按**规格**给（步幅 0.060H · 抬脚 0.045H）⇒ 大腿/小腿局部四元数。"""
    L = _LEGS[side]
    off = np.array([0.0, pelvis_y, 0.0], np.float64)       # 骨盆整体升降
    hip_pos = L["hip"] + off
    u = phase if side == "L" else phase + 0.5
    ph = 2 * math.pi * u
    swing = max(0.0, -math.sin(ph))                        # 摆动相
    fwd = np.array([1.0, 0.0, 0.0])                        # 正面 = +X（头注已实测）
    up = np.array([0.0, 1.0, 0.0])
    # 🔴 2026-10-10 关键：踝目标**不加骨盆偏移** —— 目标地点是**地面**。
    #    我第一版写成 L["ankle"] + off + …，于是**支撑脚跟着骨盆一起抬**（实测两脚都 1.5%H
    #    ⇒ 谁都不"独立" ⇒ 交替恒 0）。而 IK 存在的意义正是"骨盆怎么动，脚踝都钉在目标上"。
    tgt = (L["ankle"]
           + fwd * (IK_STRIDE * math.sin(ph))
           + up * (IK_LIFT * swing))
    thigh_d, shin_d, _ = _leg_ik(hip_pos, tgt, L["L1"], L["L2"], fwd)
    up_local, up_world = _by_dir_anim(L["up"], hips_world, thigh_d)
    lo_local, _ = _by_dir_anim(L["lo"], up_world, shin_d)
    return {L["up"]: up_local, L["lo"]: lo_local}


def _parent_world(name):
    """该骨的**父节点**在静止姿势下的世界朝向（自根向下累乘静止旋转）。"""
    if name in _PW:
        return _PW[name]
    i = bone_node.get(name)
    if i is None:
        _PW[name] = IDENT.copy()
        return _PW[name]
    chain, p = [], _PARENT.get(i)
    while p is not None:
        chain.append(p)
        p = _PARENT.get(p)
    acc = IDENT.copy()
    for p in reversed(chain):          # 从根往下乘
        acc = _qmul(acc, _node_rest(p))
    _PW[name] = acc
    return acc


def quat(rx, ry, rz):
    """XYZ 顺序的欧拉角（度）→ 四元数 (x,y,z,w)。"""
    hx, hy, hz = map(math.radians, (rx / 2, ry / 2, rz / 2))
    cx, sx = math.cos(hx), math.sin(hx)
    cy, sy = math.cos(hy), math.sin(hy)
    cz, sz = math.cos(hz), math.sin(hz)
    return np.array([
        sx * cy * cz + cx * sy * sz,
        cx * sy * cz - sx * cy * sz,
        cx * cy * sz + sx * sy * cz,
        cx * cy * cz - sx * sy * sz,
    ], np.float32)


# ── 基准姿势基底：T-pose 绑定下，手臂必须放下才自然（绕 X 轴放下，左右镜像）──
BASE = {
    "LeftShoulder": (0, 0, -4), "RightShoulder": (0, 0, 4),
    "LeftArm": (82, 0, 0), "RightArm": (-82, 0, 0),          # 上臂下垂 ≈82°（更贴身自然）
    "LeftForeArm": (8, -12, 0), "RightForeArm": (-8, -12, 0),  # 肘部微屈 + 略内收
    "LeftHand": (4, 0, 0), "RightHand": (-4, 0, 0),
    "Spine": (2, 0, 0), "Spine1": (1, 0, 0), "Neck": (-2, 0, 0),
    # 🔴 2026-10-10 修镜像：左右大腿骨的静止旋转**x 分量符号相反**（LeftUpLeg -0.9996 vs
    #    RightUpLeg +0.9994，现读）⇒ **左右互为镜像** ⇒ 同一个"绕 Z"在左右会转到**相反方向**。
    #    所以左右腿的角度**必须反号**，不能同号（同号就是这里和 walk 里那个 58% 差异的真因）。
    "LeftLeg": (0, 0, -3), "RightLeg": (0, 0, 3),              # 膝盖微屈（镜像：右腿反号）
}


def add_pose(pose):
    """把动作增量叠到基准姿势上（角度相加，逐轴）。"""
    out = {}
    keys = set(BASE) | {k for k in pose if not k.endswith("X") and not k.endswith("Y") and not k.startswith("_")}
    for k in keys:
        b = BASE.get(k, (0, 0, 0))
        d = pose.get(k, (0, 0, 0)) if not k.endswith("X") and not k.endswith("Y") else (0, 0, 0)
        out[k] = (b[0] + d[0], b[1] + d[1], b[2] + d[2])
    for k, v in pose.items():          # HipsX/HipsY/_stride 等标量原样带回
        if k.endswith("X") or k.endswith("Y") or k.startswith("_"):
            out[k] = v
    return out


def ease(t, p):
    """平滑插值曲线（呼吸/重心用 cos 更自然；四关键帧走路用 smoothstep）。"""
    if p == "smooth":
        return t * t * (3 - 2 * t)
    if p == "cos":
        return 0.5 - 0.5 * math.cos(math.pi * t)
    return t


# ── ① 走路：标准四关键帧 + 镜像（1.10s / 一个完整步幅 = 左右各一步）────────
# ── 走路：**一条腿的自身相位函数**（左右共用同一函数 ⇒ 对称由结构保证）──────────
# 🔴 2026-10-10 重写动机（几何基线量出来的真账）：
#   旧版是"四关键帧 + 手写左右两份"，实测 **左右极不对称**（抬幅 11.14%H vs 21.50%、
#   步幅 37.20%H vs 43.36%），源头是同一相位下左右膝的**常数偏置差 5 倍**（-6 vs -30）。
#   而规程 §5.1 给的是**与骨架无关的几何规格**：**抬脚 0.045H · 步幅 0.060H · 脚尖抬 15°**。
#   ⇒ 改成：一条腿按**自身相位** u 求值，右腿传 u+0.5 ⇒ 左右**必然**对称；
#     髋摆/膝弯/踝勾做成**可扫旋钮**，用几何规格当验收线（不再跨骨架比数）。
HIP_SWING = float(os.environ.get("GBT_WALK_HIP", "14.0"))    # 髋前后摆幅（度）—— 管步幅
KNEE_SWING = float(os.environ.get("GBT_WALK_KSW", "16.0"))   # 摆动相膝弯（度）—— 管抬脚
KNEE_STANCE = float(os.environ.get("GBT_WALK_KST", "6.0"))   # 支撑相膝微屈（度）
ANKLE_LIFT = float(os.environ.get("GBT_WALK_ANK", "8.0"))    # 摆动相踝勾（度）—— 管脚尖抬
ARM_SWING = float(os.environ.get("GBT_WALK_ARM", "18.0"))
# 🔴 2026-10-10 **骨盆起伏就是"支撑脚残动的地板"**（实测，且旋钮接上后才看见）：
#    它是**共模**（两只脚一起抬），且**不随腿幅缩放** ⇒ 比值 = 残动/抬幅 永远过不了 0.2。
#    实测 BOB 0.011→0.001：比值 0.230→**0.002**，交替 0→**36 帧**；抬幅几乎不变。
#    ⚠️ 我先前"证伪骨盆起伏"那次是在**旋钮还没接上**（HipsY 行仍用硬编码）时测的 ⇒ **那次证伪无效**。
WALK_BOB = float(os.environ.get("GBT_WALK_BOB", "0.001"))     # 骨盆起伏幅度（米/模型单位）
# 🔴 2026-10-10 新增：**支撑相髋摆系数**。实测（BOB 0.011→0.003 数字一模一样 ⇒ 骨盆起伏对幅度免疫）
#    证明支撑脚的残动**来自关节角本身**：hip = HIP_SWING*sin(2πu) 在 u=0.25（正支撑中期）取最大
#    ⇒ **把支撑脚拖着走**。真实步态里支撑相髋也摆，但那正是 IK 用来"把脚钉住"的一段；
#    没有 IK 时只能把支撑相的髋摆压下去（代价：步态略不如真实，但换来支撑脚站得住）。
STANCE_K = float(os.environ.get("GBT_WALK_STANCEK", "0.60"))
# 🔴 2026-10-10 再定位一处**共模**驱动：骨盆扭转 "Hips": (0, 5*s, -2*s) 的两条腿根**一起动**。
#    估算：骨盆中心到腿根 ~0.1 · 扭 5° ⇒ 0.1*sin(5°) = 0.0087 = **0.89%H** —— 与实测支撑脚残动 0.94%H 吻合。
#    （逐帧：zL 升到 3.47% 时 zR 仍 0.94% ⇒ 比值 0.27 > 判据的 0.2 ⇒ 交替判 0。）
PELVIS_YAW = float(os.environ.get("GBT_WALK_YAW", "5.0"))     # 骨盆绕竖轴扭转幅（度）
PELVIS_ROL = float(os.environ.get("GBT_WALK_ROL", "2.0"))     # 骨盆侧倾幅（度）
# IK 路（GBT_WALK_IK=1 开）：踝目标按**规格**给 —— 步幅 0.060H（峰谷跨度 ⇒ 振幅一半）· 抬脚 0.045H
WALK_IK = os.environ.get("GBT_WALK_IK", "0") == "1"
_HH = 0.97878                                              # 网格 AABB 身高（与规程同口径）
IK_STRIDE = float(os.environ.get("GBT_IK_STRIDE", str(0.030 * _HH)))   # 前后振幅 = 0.060H/2
IK_LIFT = float(os.environ.get("GBT_IK_LIFT", str(0.045 * _HH)))       # 抬脚规格 0.045H    # 摆臂幅（度）


def _leg(u):
    """u = 该腿**自身**相位 ∈[0,1)：0 触地(前) · 0.25 支撑过顶 · 0.5 触地(后) · 0.75 摆动过顶。
    左右**共用**这一个函数（右腿传 u+0.5）⇒ **对称是结构保证的，不靠手写两份**。"""
    ph = 2 * math.pi * u
    sw_raw = math.sin(ph)
    swing = max(0.0, -sw_raw)                      # 摆动相（u∈0.5~1.0）为正
    hip = HIP_SWING * sw_raw * (STANCE_K + (1.0 - STANCE_K) * swing)
    # ↑ 摆动相用满幅、支撑相按 STANCE_K 压（见 STANCE_K 处的说明）
    knee = -(KNEE_STANCE + KNEE_SWING * swing)
    ankle = ANKLE_LIFT * swing
    return hip, knee, ankle


def walk_pose(phase):
    """phase ∈[0,1)：0=左脚触地 … 0.5=右脚触地（左右对称由 _leg 保证）。"""
    hL, kL, aL = _leg(phase)
    hR, kR, aR = _leg(phase + 0.5)
    ph = 2 * math.pi * phase
    s = math.sin(ph)
    pelvis_y = -0.36 * WALK_BOB + WALK_BOB * abs(s)
    out = {
        # 🔴 2026-10-10 骨盆起伏压到交替门槛以下：原为 -0.012 + 0.024*|s|（峰值 0.012 = **1.2%H**），
        #    而 §6.1 的"独立离地"门槛是 **1%H = 0.00979** ⇒ **骨盆一抬，支撑脚也被算成离地**
        #    ⇒ 两脚永远"同起同落" ⇒ 交替恒 0。压到峰值 ~0.7%H（0.007）就不越门槛。
        # 🔴 2026-10-10 **我自己的账目错误**：上一版我算了 pelvis_y、还加了 GBT_WALK_BOB 旋钮，
        #    但这一行**仍在用硬编码的 -0.004 + 0.011*abs(s)** ⇒ 旋钮根本没接上（那两组"一模一样"的
        #    读数不是"骨盆无效"，是**我改的那一行没被用**）。同时把骨盆扭转/侧倾也接成旋钮。
        "Hips": (0, PELVIS_YAW * s, -PELVIS_ROL * s), "HipsY": pelvis_y, "HipsX": None,
        "Spine": (0, -2 * s, 1.0), "Spine1": (0, -1.5 * s, 0.6),
        "Neck": (0, 1 * s, 0), "Head": (0, 1 * s, 0),
        # 🔴 右腿的 Y/Z 分量**取反**（镜像修正，见 BASE 处的说明）：
        #    左右大腿骨静止旋转 x 分量符号相反 ⇒ 同一角度在右侧会转到相反方向。
        #    不加这一步，左右必然不对称（实测抬幅 4.69% vs 7.48%、步幅 15.38% vs 21.18%）。
        "LeftUpLeg": (0, 0, hL), "LeftLeg": (0, 0, kL), "LeftFoot": (0, 0, aL),
        "RightUpLeg": (0, -0.0, -hR), "RightLeg": (0, -0.0, -kR), "RightFoot": (0, -0.0, -aR),
        # 反向摆臂：与**同侧腿**反相 ⇒ 左腿前摆时右臂前摆
        "LeftArm": (0, ARM_SWING * math.sin(2 * math.pi * (phase + 0.5)), 0),
        "RightArm": (0, -ARM_SWING * math.sin(2 * math.pi * (phase + 0.5)), 0),
        "LeftForeArm": (0, -10, 0), "RightForeArm": (0, -10, 0),
    }
    if WALK_IK:
        # IK 路：腿不再给角度，而是 **髋位 + 踝目标 → leg_ik → by_dir**（局部四元数）
        hips_world = _qmul(quat(0, PELVIS_YAW * s, -PELVIS_ROL * s), _HIPS_REST_ROT)
        out.update(_leg_walk_ik("L", phase, hips_world, pelvis_y))
        out.update(_leg_walk_ik("R", phase, hips_world, pelvis_y))
    return out


def _walk_pose_OLD(phase):
    """旧版留档（四关键帧 + 手写左右）—— 已被上面取代，留着对比用。"""
    fwd, _ = 24.0, -20.0
    if phase in (0.0, 0.5):
        s = 1 if phase == 0.0 else -1
        return {
            "Hips": (0, 9 * s, -4 * s), "HipsY": -0.028, "HipsX": None,
            "Spine": (0, -4 * s, 2.5), "Spine1": (0, -3 * s, 1.5), "Neck": (0, 2 * s, 0),
            "Head": (0, 2 * s, -1),
            "LeftUpLeg": (0, 0, fwd * s), "LeftLeg": (0, 0, -6 - 6 * (1 - s) / 2),
            "RightUpLeg": (0, 0, -fwd * s), "RightLeg": (0, 0, -30 - 8 * (1 + s) / 2),
            "LeftFoot": (0, 0, -8 * s), "RightFoot": (0, 0, 6 * s),
            "LeftArm": (0, -20 * s, 0), "RightArm": (0, 20 * s, 0),
            "LeftForeArm": (0, -14, 0), "RightForeArm": (0, -14, 0),
        }
    s = 1 if phase == 0.25 else -1
    return {
        "Hips": (0, 4 * s, -2 * s), "HipsY": 0.018, "HipsX": None,
        "Spine": (0, -1 * s, 1.0), "Spine1": (0, -1 * s, 0.5), "Neck": (0, 0.5 * s, 0), "Head": (0, 1 * s, 0),
        "LeftUpLeg": (0, 0, 3 * s), "LeftLeg": (0, 0, -46 if s < 0 else -10),
        "RightUpLeg": (0, 0, -3 * s), "RightLeg": (0, 0, -10 if s < 0 else -46),
        "LeftFoot": (0, 0, 4), "RightFoot": (0, 0, 4),
        "LeftArm": (0, -9 * s, 0), "RightArm": (0, 9 * s, 0),
        "LeftForeArm": (0, -12, 0), "RightForeArm": (0, -12, 0),
    }


# ── ② idle：三层叠加（呼吸 4s · 重心漂移 8s · 头部扫视）─────────────────
IDLE_LEN, IDLE_FPS = 8.0, 12


def idle_at(t):
    br = math.sin(2 * math.pi * t / 4.0)                 # 呼吸
    ws = math.sin(2 * math.pi * t / 8.0)                 # 重心漂移
    sacc = [1.5, 3.8, 6.2]                               # 扫视时刻
    hy = sum(3.0 * math.exp(-((t - s) ** 2) / 0.06) for s in sacc)
    hn = 1.2 * math.sin(2 * math.pi * t / 4.0)   # 周期必须整除 8s，否则循环不闭合
    return {
        "Hips": (1.2 * ws, 1.0 * ws, -0.8 * ws), "HipsY": -0.004 * abs(ws), "HipsX": 0.010 * ws,
        "Spine": (0, -0.6 * ws, 0.5 * ws), "Spine1": (-0.9 * br, 0, 0.6 * br),
        "Neck": (0, -0.5 * ws, 0), "Head": (0, hy, hn),
        "LeftShoulder": (0, 0, -0.6 * br), "RightShoulder": (0, 0, -0.6 * br),
        "LeftArm": (0, -1.0 * ws, -1.2 * br), "RightArm": (0, -1.0 * ws, -1.2 * br),
        "LeftForeArm": (0, -1.5, 0.8 * br), "RightForeArm": (0, -1.5, 0.8 * br),
        "LeftUpLeg": (0, 0, 0.5 * ws), "RightUpLeg": (0, 0, -0.5 * ws),
        "LeftLeg": (0, 0, -1.0), "RightLeg": (0, 0, -1.0),
        "LeftFoot": (0, 0, 0.5), "RightFoot": (0, 0, 0.5),
    }


def walk_at(t, T=1.10):
    # 🔴 改成**直接求值**（不再四关键帧插值）：连续 ⇒ 更平滑，且 u 走满一圈天然回到起点
    #    ⇒ 闭合误差仍是 0，而不会因插值端点引入拐点。
    p = (t % T) / T
    out = dict(walk_pose(p))
    out["_stride"] = (t / T) * 0.55
    return out
    keys = [(0.0, walk_pose(0.0)), (0.25, walk_pose(0.25)), (0.5, walk_pose(0.5)), (0.75, walk_pose(0.75)), (1.0, walk_pose(0.0))]
    for i in range(len(keys) - 1):
        a, pa = keys[i]
        b, pb = keys[i + 1]
        if a <= p <= b:
            u = ease((p - a) / (b - a), "smooth")
            out = {}
            for k in pa:
                if k.endswith("X") or k.endswith("Y"):
                    out[k] = (pa[k] or 0) * (1 - u) + (pb[k] or 0) * u
                else:
                    out[k] = tuple(pa[k][c] * (1 - u) + pb[k][c] * u for c in range(3))
            out["_stride"] = (t / T) * 0.55                 # 根位移：每步幅 0.55（模型高=1.0 时的自然步长）
            return out
    return keys[0][1]


# ── ③ 采样 + 建通道 ─────────────────────────────────────────────────────
def build_clip(name, length, fps, fn, root_motion):
    times = np.arange(0, length + 1e-6, 1.0 / fps, np.float32)
    if times[-1] < length:
        times = np.append(times, np.float32(length))
    per_bone = {}
    hips_pos = []
    for t in times:
        raw = fn(float(t))
        pose = add_pose(raw)                       # 仍供 HipsX/HipsY/_stride 这些**标量**用
        for b in bone_node:
            # 🔴 2026-10-10 第二版（第一版回退过，见下面的失败记录）：**正确式子**
            #     new_local = conj(P_world, q_world) · R_rest
            #   ① R_rest = 该骨**自己**的静止局部旋转（从节点 rotation 现读，不再拿 BASE 顶替）
            #   ② q_world = BASE 的角度 **复合** 增量角度 —— 两者本来就是按**世界轴**量的
            #      （BASE 的 LeftArm (82,0,0) 就是"绕世界 X 把手臂放下"）
            #   ③ P_world = 该骨**父节点**的静止世界朝向（自根向下累乘静止旋转）
            #   ④ conj(P,q)=P⁻¹qP 把世界旋转换算到父节点的局部系，再右乘 R_rest 得到该骨的局部旋转
            # 🔴 2026-10-10 第三版：**把复合顺序做成可扫的参数**，让数字选（不再我猜一版量一版）。
            #    动机：我推了一遍数学 ⇒ "把增量绕 BASE 转过的轴" 恰好 = BASE·delta，
            #    而那正是第二版在跑的 —— 所以甲1 不是没试的路，是已经在跑。
            #    剩下真正没试的是：复合顺序(谁先谁后) / BASE 归世界还是归局部。
            #      W_BD = BASE·delta（世界复合，BASE 先）   ← 第二版
            #      W_DB = delta·BASE（世界复合，delta 先）
            #      L_B  = 增量走世界共轭、BASE 并回**局部**（乘在 R_rest 之后）
            qb = quat(*BASE.get(b, (0, 0, 0)))
            d = raw.get(b)
            if isinstance(d, tuple) and len(d) == 4:
                # 🔴 IK 路直接给的**该骨局部四元数**（leg_ik → by_dir 已算好）⇒ 原样落通道
                per_bone.setdefault(b, []).append(np.array(d, np.float32))
                continue
            if isinstance(d, tuple) and any(d):
                _k = ARM_K if b in _ARM else (LEG_K if b in _LEG else 1.0)
                d = (d[0] * _k, d[1] * _k, d[2] * _k)
            qd = quat(*d) if (isinstance(d, tuple) and any(d)) else IDENT
            _M = globals().get("MODE", "W_BD")
            if _M == "W_BD":
                q_world = _qmul(qb, qd)
                local = _qmul(_qconj_by(_parent_world(b), q_world), _node_rest(bone_node[b]))
            elif _M == "W_DB":
                q_world = _qmul(qd, qb)
                local = _qmul(_qconj_by(_parent_world(b), q_world), _node_rest(bone_node[b]))
            else:  # L_B：BASE 归局部（它是"T-pose→手臂放下"的局部贴合），只让增量走世界轴
                local = _qmul(_qmul(_qconj_by(_parent_world(b), qd), _node_rest(bone_node[b])), qb)
            per_bone.setdefault(b, []).append(local)
        # 🔴 2026-10-10 **这一版共轭换算我试了、又回退了**（真账，不许当成没试过）：
        #    我按 new_local = conj(P_world, q_world) · q_base 改了一版，重跑产物、用规程 §5.1 复量
        #    ⇒ **数字几乎没动**（hand_L 54.09→57.45 · hand_R 53.61→52.43 · foot_L 98.82→95.54
        #      · foot_R 125.15→108.97 · 独立离地 2/12→2/10；规程正解 123.92 / 119.11 / 62.21 / 59.27
        #      · 18/14）⇒ **没改对**。
        #    查为什么：这个 GLB 的节点静止旋转**不是单位阵**（Hips 90.00°、LeftUpLeg 177.18°、
        #    65 骨平均 32.76°、>10° 的有 22 根）⇒ 共轭本该有影响，说明**公式用错了项**：
        #    正解里乘的是该骨**自己的静止旋转 R_rest**，我乘的却是人手写的 BASE 局部调整。
        #    ⇒ 回退（不把"没变好、还换了产物"的状态留给 S8），把正确式子留在下面的注释里：
        #        new_local = conj(P_world, q_world) · R_rest
        #      其中 P_world = 该骨**父节点**的静止世界朝向，R_rest = 该骨**自己**的静止局部旋转。
        #    ⇒ 下一轮按这个式子重做，**验收就是 §5.1 那四个数字要回到正解量级**（否则就是没改对）。
        # 🔴🔴🔴 2026-10-10 **整整十三轮没看见的根因，就在这里**（45→57 轮）：
        #    glTF 里节点的 translation 是**父空间绝对位移**，不是增量。而这里原来写的是
        #        [HipsX, HipsY, _stride]
        #    ⇒ **把 Hips 的静止 translation 整个替换掉了**（原始件是 y = **0.5678**）
        #    ⇒ 髋部从 y=0.568 掉到 y≈0 ⇒ **整个人下沉 0.568 单位 = 58% 身高**。
        #    这解释了：第 40-41 轮胶片里"人物塌在画面下半、上面 55% 空" · 踝在 z=-0.50 ·
        #    §5.1 累计位移全部离谱 · 而**闭合误差永远 0.00000**（首末帧是同一个错值）。
        #    也解释了为什么从第 45 轮起怎么调都不对：**腿的动作一直被"整个人下沉 58%"盖住**。
        #    这是同一族病的**第五副副本**：把"增量"当成了"绝对值"
        #    （前四副：清动画≠回绑定姿势 · 注释说不用三点光 · JS 按当前姿势量缩放 · 取景基准没冻结）。
        #    ⇒ 修：**静止位移 + 增量**。
        # 🔴🔴 2026-10-10 又一副（**同族第六副：轴混淆**）——**两道判据都抓不到**：
        #    _stride（前进位移）原来落在 **index 2 = Z**，而头注写着「**臂轴 = Z**（双臂沿 Z 展开）·
        #    **正面 = +X**」⇒ **Z 是左右轴** ⇒ 角色**横着走**（实测：X 幅度 0.0000、Z 幅度 0.5500）。
        #    而**腿是在 X 轴前后摆的**（IK 用 fwd=(+1,0,0)）⇒ 两者内部不一致。
        #    为什么两道判据都抓不到：
        #      本仓 gate_anim: trans = max(max(xs)-min(xs), max(zs)-min(zs))  ← **取较大者 ⇒ 落哪个轴都过**
        #      我的 walk-check: 步幅比 = max(...)                             ← **同样的盲点**
        #    ⇒ 修：前进位移落 **index 0 = X**（正面）。
        hips_pos.append([_HIPS_REST_T[0] + (pose.get("HipsX", 0.0) or 0.0) + (pose.get("_stride", 0.0) if root_motion else 0.0),
                         _HIPS_REST_T[1] + (pose.get("HipsY", 0.0) or 0.0),
                         _HIPS_REST_T[2]])
    samplers, channels = [], []

    def add(inp, out, node, path):
        samplers.append({"input": inp, "output": out, "interpolation": "LINEAR"})
        channels.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path}})
    while len(BIN) % 4:
        BIN.append(0)
    ti = len(BIN)
    BIN.extend(times.tobytes())
    J["bufferViews"].append({"buffer": 0, "byteOffset": ti, "byteLength": times.nbytes})
    J["accessors"].append({"bufferView": len(J["bufferViews"]) - 1, "componentType": 5126, "count": len(times), "type": "SCALAR",
                           "min": [float(times.min())], "max": [float(times.max())]})
    tin = len(J["accessors"]) - 1
    for b, quats in per_bone.items():
        arr = np.array(quats, np.float32)
        while len(BIN) % 4:
            BIN.append(0)
        o = len(BIN)
        BIN.extend(arr.tobytes())
        J["bufferViews"].append({"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes})
        J["accessors"].append({"bufferView": len(J["bufferViews"]) - 1, "componentType": 5126, "count": len(arr), "type": "VEC4"})
        add(tin, len(J["accessors"]) - 1, bone_node[b], "rotation")
    if root_motion:
        arr = np.array(hips_pos, np.float32)
        while len(BIN) % 4:
            BIN.append(0)
        o = len(BIN)
        BIN.extend(arr.tobytes())
        J["bufferViews"].append({"buffer": 0, "byteOffset": o, "byteLength": arr.nbytes})
        J["accessors"].append({"bufferView": len(J["bufferViews"]) - 1, "componentType": 5126, "count": len(arr), "type": "VEC3"})
        add(tin, len(J["accessors"]) - 1, bone_node["Hips"], "translation")
    # 闭合误差：首末关键帧四元数最大差（旋转须闭合，位移按 stride 故意不闭合）
    closes = [float(np.abs(np.array(v[0]) - np.array(v[-1])).max()) for v in per_bone.values()]
    # 🔴 2026-10-10 同一盲点的**第二处**：这里原来读 hips_pos[-1][2]（Z 轴末值）报"根位移/步幅"，
    #    而前进位移修到 X 轴之后它会读出 ~0。改成**跨距**（轴无关），与本仓 gate_anim 的口径一致。
    _st = (max(p[0] for p in hips_pos) - min(p[0] for p in hips_pos)) if root_motion else 0.0
    return {"name": name, "channels": channels, "samplers": samplers}, float(max(closes)), float(times[-1]), float(_st)


clips = []
c1, close1, len1, stride = build_clip("idle", IDLE_LEN, IDLE_FPS, idle_at, root_motion=False)
clips.append(c1)
c2, close2, len2, stride2 = build_clip("walk", 1.10, 24, lambda t: walk_at(t), root_motion=True)
clips.append(c2)
J["animations"] = clips
J["buffers"][0]["byteLength"] = len(BIN)


def write_glb(path, jj, bb):
    body = bytearray(bb)
    while len(body) % 4:
        body.append(0)
    jj["buffers"][0]["byteLength"] = len(body)
    js = json.dumps(jj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(body))
                     + struct.pack("<I", len(js)) + b"JSON" + js
                     + struct.pack("<I", len(body)) + b"BIN\x00" + bytes(body))


write_glb(OUT, J, BIN)
print(f"idle: {len1:.1f}s · 通道 {len(c1['channels'])} · 循环闭合误差 {close1:.5f}（应≈0）")
print(f"walk: {len2:.2f}s · 通道 {len(c2['channels'])} · 循环闭合误差 {close2:.5f} · 根位移/步幅 {stride2:.3f}（模型高=1.0）")
print(f"输出 {OUT.name} · {OUT.stat().st_size/1024/1024:.2f} MB · 动画 {len(J['animations'])} 段")
