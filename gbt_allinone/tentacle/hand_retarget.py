# gbt-capability: hand_retarget
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""hand_retarget — 手部姿态重定向（原生位 · 2026-11-01 蒸馏自 dexterous-hand 知识胶囊）。

## 它是什么（以及不是什么）
把**手部跟踪输入**（MediaPipe 风格 21 个 3D 关键点，Vision Pro / Quest3 / 摄像头 /
IMU 手套都能先转成这个形状）映射成**目标灵巧手的关节角**（15-DoF / 20-DoF 两种内置模型，
也接受任意 JSON 手模型），供遥操作/URDF 驱动使用。

- **是**：几何向量法重定向 —— 用相邻骨段夹角算屈曲、用掌平面基底算外展；带关节限位、
  标定偏移、左右手符号。可离线、零依赖、可复现。
- **不是**：不是 IK 优化、不是接触力/触觉估计、不是厂商寄存器协议（那是 `hand_bridge`）。
  几何法对"手指侧摆/对掌"是近似；要更高精度，需换逆运动学求解器（本仓暂无，如实写）。

## 吸收来源
`AnyDexRetarget`（92★, MIT）· `PCHands`（7★, BSD-3）· `BrainCo-Revo2-Dex-Retargeting`（38★, MIT）·
`hand-tracking-fusion-system`（1★, MIT）四份知识胶囊（2026-11-01 吞噬）。
本实现是**按几何原理自写**，未复制任何仓库代码；许可边界见 `整理报告/吞噬记录-dexterous-hand.md`。

## 契约
op（默认 status）：
  · `status`   只读：能力/模型/输入形状
  · `models`   只读：内置手模型清单（名 / DoF / 关节名）
  · `retarget` **纯计算**：landmarks 或 joints → 关节角
  · `where`    只读：入口与调用例
payload：
  · `landmarks`: 21×[x,y,z]（米或归一化都行，比例自洽即可）
  · 或 `joints`: {关节名: 值}（直通模式：只做限位/单位换算）
  · `model`: "generic_15dof"（默认）| "generic_20dof" | 自定义 dict
  · `hand`: "right"（默认）| "left"（影响外展符号）
  · `unit`: "rad"（默认）| "deg"
  · `calibration`: {"offsets": {关节名: 弧度}}（中性位标定）
  · `clamp`: 默认 True（越界夹到限位并如实报）
返回：{ok, op, model, hand, unit, joints, clamped, warnings, checks}
"""
from __future__ import annotations

import math

__all__ = ["run", "STATUS", "MODELS", "retarget_landmarks", "apply_limits"]

PI = math.pi

# ── 内置手模型 ────────────────────────────────────────────────────────────
# chain: [腕(0), MCP, PIP, DIP, TIP]（拇指用 0,1,2,3,4）
# joints: 沿 chain 取"关节位置"下标，kind=flex（屈曲）；spread 可选（外展）
_FINGERS = [
    ("thumb", [0, 1, 2, 3, 4], [1, 2, 3]),
    ("index", [0, 5, 6, 7, 8], [5, 6, 7]),
    ("middle", [0, 9, 10, 11, 12], [9, 10, 11]),
    ("ring", [0, 13, 14, 15, 16], [13, 14, 15]),
    ("pinky", [0, 17, 18, 19, 20], [17, 18, 19]),
]


def _flex_limit(finger: str, joint_ix: int):
    """关节限位（弧度）。拇指对掌范围大；近端>远端，符合人手生理范围。"""
    if finger == "thumb":
        return [(0.0, 1.20), (0.0, 1.40), (0.0, 1.60)][joint_ix]
    return [(0.0, 1.57), (0.0, 1.75), (0.0, 1.40)][joint_ix]


def _build_model(name: str, dof: int):
    fingers = []
    for fname, chain, points in _FINGERS:
        joints = []
        for ji, point in enumerate(points):
            lo, hi = _flex_limit(fname, ji)
            suffix = ("mcp", "pip", "dip")[ji] if ji < 3 else "j%d" % ji
            joints.append({"name": "%s_%s" % (fname, suffix), "kind": "flex",
                           "point": point, "limit": [lo, hi], "scale": 1.0,
                           "offset": 0.0, "sign": 1.0})
        finger = {"name": fname, "chain": chain, "joints": joints}
        if dof >= 20:
            finger["spread"] = {"name": "%s_abd" % fname, "limit": [-0.6, 0.6],
                                 "scale": 1.0, "offset": 0.0}
        fingers.append(finger)
    return {"name": name, "dof": dof, "fingers": fingers,
            "calibration": {"offsets": {}},
            "notes": ["几何向量法重定向（非 IK）；外展为掌平面夹角近似"]}


MODELS = {
    "generic_15dof": _build_model("generic_15dof", 15),
    "generic_20dof": _build_model("generic_20dof", 20),
}

STATUS = {
    "cap": "hand_retarget",
    "tier": "native",
    "ops": ["status", "models", "retarget", "ik", "ik_global", "where"],
    "inputs": ["landmarks(21x3)", "joints(dict)"],
    "models": sorted(MODELS),
    "dof": {"generic_15dof": 15, "generic_20dof": 20},
    "not_implemented": ["全手 21-DoF 全局 IK（当前每指平面 3-link）", "接触/触觉估计", "厂商寄存器协议（见 hand_bridge）"],
}


# ── 向量工具 ──────────────────────────────────────────────────────────────
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(v):
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _flex_at(p, prev_ix, joint_ix, next_ix, forward=None):
    """屈曲角：伸直=0，弯曲增大（弧度）。

    MCP（prev=腕）不能用「腕→MCP 与 MCP→PIP 的夹角」—— 那会把掌骨的自然宽度算成屈曲
    （实测：直手小指 MCP 会假报 33.7°）。改用**掌平面前向轴**（腕→中指 MCP）作参考：
    手指方向与前向轴重合=0；PIP/DIP 仍按相邻骨段夹角（伸直=0）。
    """
    v = _sub(p[next_ix], p[joint_ix])
    nv = math.sqrt(_dot(v, v))
    if nv < 1e-9:
        return None
    if prev_ix == 0 and forward is not None:
        c = _clamp(_dot(forward, v) / nv, -1.0, 1.0)
        return math.acos(c)                     # 与前向轴夹角：伸直=0
    u = _sub(p[prev_ix], p[joint_ix])
    nu = math.sqrt(_dot(u, u))
    if nu < 1e-9:
        return None
    c = _clamp(_dot(u, v) / (nu * nv), -1.0, 1.0)
    return PI - math.acos(c)                    # 骨段反向：伸直=0


def _palm_basis(p):
    """掌平面基底：x 轴=腕→中指 MCP；法线=食指MCP×小指MCP；y=法线×x。"""
    x = _norm(_sub(p[9], p[0]))
    n = _norm(_cross(_sub(p[5], p[0]), _sub(p[17], p[0])))
    y = _norm(_cross(n, x))
    return x, y, n


def _spread_of(p, chain, hand_sign):
    """外展：手指方向在掌平面内相对中指的角度（弧度）。"""
    x, y, _ = _palm_basis(p)
    mcp, nxt = chain[1], chain[2]
    d = _norm(_sub(p[nxt], p[mcp]))
    ang = math.atan2(_dot(d, y), _dot(d, x))
    return ang * hand_sign


def _out_of_plane(p, chain):
    """手指方向与掌平面法线的夹角余弦（用于提示"手掌侧翻/外展不纯"）。"""
    _, _, n = _palm_basis(p)
    d = _norm(_sub(p[chain[2]], p[chain[1]]))
    return abs(_dot(d, n))


def _joints_from_landmarks(landmarks, model, hand="right", clamp=True, calibration=None):
    p = [tuple(float(x) for x in pt[:3]) for pt in landmarks]
    sign = 1.0 if str(hand).lower() != "left" else -1.0
    cal = ((calibration or {}).get("offsets") or {})
    forward, _, _ = _palm_basis(p)
    out, clamped, warnings = {}, [], []
    for finger in model.get("fingers") or []:
        fname = finger.get("name", "?")
        chain = finger.get("chain") or []
        for j in finger.get("joints") or []:
            if j.get("kind") != "flex":
                continue
            point = int(j.get("point"))
            try:
                pos = chain.index(point)
                prev_ix, next_ix = chain[pos - 1], chain[pos + 1]
            except (ValueError, IndexError):
                warnings.append("%s.%s 关节下标不在链上，跳过" % (fname, j.get("name")))
                continue
            flex = _flex_at(p, prev_ix, point, next_ix, forward)
            if flex is None:
                warnings.append("%s.%s 骨段长度≈0，跳过" % (fname, j.get("name")))
                continue
            val = (flex * float(j.get("scale", 1.0)) * float(j.get("sign", 1.0))
                   + float(j.get("offset", 0.0)) + float(cal.get(j.get("name"), 0.0)))
            lo, hi = (j.get("limit") or [0.0, PI])[:2]
            if clamp and not (lo <= val <= hi):
                clamped.append(j.get("name"))
                val = _clamp(val, lo, hi)
            out[j.get("name")] = round(val, 6)
        sp = finger.get("spread")
        if sp:
            ang = _spread_of(p, chain, sign)
            val = ang * float(sp.get("scale", 1.0)) + float(sp.get("offset", 0.0)) \
                + float(cal.get(sp.get("name"), 0.0))
            lo, hi = (sp.get("limit") or [-PI / 2, PI / 2])[:2]
            if clamp and not (lo <= val <= hi):
                clamped.append(sp.get("name"))
                val = _clamp(val, lo, hi)
            out[sp.get("name")] = round(val, 6)
    return out, clamped, warnings


def _apply_direct(joints, model, clamp=True):
    out, clamped, warnings = {}, [], []
    known = {}
    for finger in model.get("fingers") or []:
        for j in finger.get("joints") or []:
            known[j.get("name")] = j
        if finger.get("spread"):
            known[finger["spread"].get("name")] = finger["spread"]
    for name, raw in (joints or {}).items():
        if name not in known:
            warnings.append("未知关节 %s（按模型清单拒收）" % name)
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            warnings.append("%s 的值不是数字，跳过" % name)
            continue
        lo, hi = (known[name].get("limit") or [0.0, PI])[:2]
        if clamp and not (lo <= val <= hi):
            clamped.append(name)
            val = _clamp(val, lo, hi)
        out[name] = round(val, 6)
    return out, clamped, warnings


def retarget_landmarks(landmarks, model=None, hand="right", clamp=True, calibration=None):
    """公开的纯函数入口：landmarks → (joints, clamped, warnings)。"""
    model = model or MODELS["generic_15dof"]
    if not isinstance(landmarks, (list, tuple)) or len(landmarks) != 21:
        raise ValueError("landmarks 需要 21 个点，收到 %r" % (len(landmarks) if hasattr(landmarks, "__len__") else type(landmarks)))
    for i, pt in enumerate(landmarks):
        if not isinstance(pt, (list, tuple)) or len(pt) < 3:
            raise ValueError("第 %d 个关键点不是 [x,y,z]" % i)
    return _joints_from_landmarks(landmarks, model, hand, clamp, calibration)


def apply_limits(joints, model=None, clamp=True):
    """公开的纯函数入口：joints 直通 + 限位。"""
    return _apply_direct(joints, model or MODELS["generic_15dof"], clamp)


def _model_or_none(model):
    if model is None:
        return MODELS["generic_15dof"]
    if isinstance(model, str):
        return MODELS.get(model)
    if isinstance(model, dict):
        return model
    return None


def _as_unit(joints, unit):
    if str(unit).lower().startswith("deg"):
        return {k: round(v * 180.0 / PI, 3) for k, v in joints.items()}
    return joints


def run(op="status", **kw):
    op = str(op or "status").strip().lower()
    if op == "status":
        return {"ok": True, "op": "status", **STATUS}
    if op in ("models", "list"):
        return {"ok": True, "op": "models", "models": [
            {"name": m["name"], "dof": m["dof"],
             "joints": [j["name"] for f in m["fingers"] for j in f["joints"]]
                       + [f["spread"]["name"] for f in m["fingers"] if f.get("spread")]}
            for m in MODELS.values()]}
    if op == "where":
        return {"ok": True, "op": "where", "cap": "hand_retarget",
                "entry": "py -3.14 tools/codex-scripts/five-dim.py cap hand_retarget '{\"op\":\"status\"}'",
                "module": "gbt_allinone/tentacle/hand_retarget.py",
                "retarget_example": "{\"op\":\"retarget\",\"landmarks\":[[0,0,0],...21],\"model\":\"generic_15dof\",\"hand\":\"right\",\"unit\":\"deg\"}",
                "模型": "内置 generic_15dof / generic_20dof；也可传 model dict（chain/joints/limit 同名契约）"}
    if op == "retarget":
        model = _model_or_none(kw.get("model"))
        if model is None:
            return {"ok": False, "op": op, "status": "needs_input",
                    "error": "未知 model（可用：%s，或传 dict）" % ", ".join(MODELS)}
        hand = str(kw.get("hand") or "right").lower()
        if hand not in ("right", "left"):
            return {"ok": False, "op": op, "status": "needs_input",
                    "error": "hand 只认 right/left"}
        unit = str(kw.get("unit") or "rad")
        clamp = kw.get("clamp", True) is not False
        calibration = kw.get("calibration")
        warnings, clamped = [], []
        if kw.get("joints"):
            joints, clamped, warnings = apply_limits(kw["joints"], model, clamp)
        elif kw.get("landmarks"):
            try:
                joints, clamped, warnings = retarget_landmarks(
                    kw["landmarks"], model, hand, clamp, calibration)
            except ValueError as e:
                return {"ok": False, "op": op, "status": "user_error", "error": str(e)}
        else:
            return {"ok": False, "op": op, "status": "needs_input",
                    "error": "需要 landmarks（21×[x,y,z]）或 joints（dict）",
                    "how_to_fix": "先给手部跟踪点：MediaPipe/Vision Pro/Quest3/IMU 手套都可先转 21 点"}
        if kw.get("landmarks"):
            try:
                side = abs(_out_of_plane([tuple(float(x) for x in pt[:3]) for pt in kw["landmarks"]],
                                         (model.get("fingers") or [{}])[0].get("chain") or [0, 1, 2]))
            except Exception:  # noqa: BLE001
                side = None
            if side is not None and side > 0.75:
                warnings.append("手掌侧翻明显（|cos|=%.2f）：几何外展可能失真，建议先摆正手掌" % side)
        return {"ok": True, "op": op, "cap": "hand_retarget",
                "model": model.get("name"), "hand": hand, "unit": unit,
                "joints": _as_unit(joints, unit),
                "joint_count": len(joints), "clamped": clamped, "warnings": warnings,
                "checks": {"input": "landmarks" if kw.get("landmarks") else "joints",
                           "landmarks": len(kw["landmarks"]) if kw.get("landmarks") else None},
                "honesty": "几何向量法（非 IK）；外展/对掌为近似；无接触/触觉建模"}
    if op in ("ik", "ik_global"):
        model = _model_or_none(kw.get("model"))
        if model is None:
            return {"ok": False, "op": op, "status": "needs_input",
                    "error": "未知 model（可用：%s，或传 dict）" % ", ".join(MODELS)}
        hand = str(kw.get("hand") or "right").lower()
        if hand not in ("right", "left"):
            return {"ok": False, "op": op, "status": "needs_input", "error": "hand 只认 right/left"}
        if not kw.get("landmarks"):
            return {"ok": False, "op": op, "status": "needs_input",
                    "error": "ik 需要 landmarks（21×[x,y,z]）"}
        from . import hand_ik
        smooth = float(kw.get("smooth") or (0.15 if op == "ik_global" else 0.0))
        r = hand_ik.solve(kw["landmarks"], model, hand, prev=kw.get("prev"), smooth=smooth)
        if not r.get("ok"):
            return {"ok": False, "op": op, "status": "user_error", "error": r.get("error"),
                    "warnings": r.get("warnings")}
        unit = str(kw.get("unit") or "rad")
        return {"ok": True, "op": op, "cap": "hand_retarget", "model": model.get("name"),
                "hand": hand, "unit": unit, "joints": _as_unit(r["joints"], unit),
                "joint_count": len(r["joints"]), "ik": r.get("ik"),
                "warnings": r.get("warnings") or [], "smooth": smooth,
                "checks": {"input": "landmarks", "landmarks": len(kw["landmarks"]),
                           "solver": "planar-box-constrained-ik"},
                "honesty": "每指平面 3-link IK，非全手 21-DoF 全局 IK；无接触/触觉建模"}
    return {"ok": False, "op": op, "status": "unknown_op",
            "error": "未知 op：%s" % op, "available": STATUS["ops"], "fail_closed": True}

