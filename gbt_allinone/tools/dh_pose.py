# gbt-capability: dh_pose
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""数字人动作控制（dh_pose）· 主人令 2026-10-13「触手化作骨架操控数字人的所有动作，都在你可控之内」+「连带手指脚趾都要绑骨」。

这一格管三件事，全部**现读、可机检**：
  · 轴系标定（`calibrate-axes.py`：用**旋转轴探针**量每根骨哪个轴是什么动作）
  · 语义表（`state/dh-pose/semantics.json`：意图 → 骨/轴/符号，**不是猜，是实测**）
  · 摆姿势 / 出动作（编译成骨角度 JSON 后交给 `blender` 位渲染）

🔴 两条实测铁律（都写进语义表的口径）：
  ① 脊柱链的**自转（转身/扭头/转腰）＝局部 Y**——v1 拿「骨末端位移」当探针时 Y 恒为 0，
     因为骨末端正好在自转轴上；**不是没驱动，是量错了地方**。换旋转轴探针才量出来。
  ② 手指脚趾**真绑上了**：65 骨 / 指骨 40 其中 30 有权重 / 趾骨 4 其中 2 有权重；
     无权的 13 根全是末端骨（`Toe_End` 与手指 `*4`），天生不带顶点。

门：`status` / `semantics` / `compile` 是**纯读**（不写盘、不起进程）；`pose` / `acts` 会写盘并起 Blender
     ⇒ 一律经 `blender` 位（那位的 `filesystem_write` 门挂在处理器层），本格不自己造第二道门。
"""
import json
import os
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
SPEC = WS / "state" / "dh-pose" / "semantics.json"
PREFIX = "mixamorig:"
FING = ("Index", "Middle", "Pinky", "Ring", "Thumb")
GLB = "holo_pet/assets/digital-human/raw/rig/model-rigged-anim.glb"
RENDER = "tools/digihuman/render-shot.py"


def _spec() -> dict:
    if not SPEC.is_file():
        return {}
    return json.loads(SPEC.read_text(encoding="utf-8"))


def _norm_side(side):
    """侧别归一化成 "L" / "R" / ""（不带左右）。认不出返回 None（调用方按 fail-closed 拒）。

    🔴 2026-10-19 修（主人问「能不能完美操控绑骨」时当场量出来的真故障）：
    原来 `_side()` 判的是 `str(side).upper().startswith("L")` —— 而**主人口令传进来的是中文
    「左/右」**。"左".upper() 还是 "左"，不以 L 开头 ⇒ 一律走 else 分支出 **Right**。
    实测：`抬臂/左/45`、`抬臂/右/45`、`抬臂/-/45` 三种写法**全出 mixamorig:RightArm**
    —— 侧别参数整个是死的。这种"参数接了但没接上"比报错更坏：绿着、结果是错的。
    """
    s = str(side if side is not None else "").strip()
    if s in ("", "-", "无", "中", "中间"):
        return ""
    k = s.lower()
    if k in ("l", "left", "左", "左侧"):
        return "L"
    if k in ("r", "right", "右", "右侧"):
        return "R"
    if s.startswith("左"):
        return "L"
    if s.startswith("右"):
        return "R"
    return None


def _side(side: str) -> str:
    n = _norm_side(side)
    return "Left" if n == "L" else ("Right" if n == "R" else "")


def compile_intent(intent: str, side: str, deg: float):
    """意图 × 侧 × 角度 → {骨名: [rx,ry,rz]}（度）。认不出就如实报，不瞎编。"""
    sp = _spec().get(intent)
    if not sp:
        return {}, "语义表里没有「%s」（现读 state/dh-pose/semantics.json，共 %d 条）" % (
            intent, len([k for k in _spec() if not k.startswith("_")]))
    ns = _norm_side(side)
    if ns is None:
        return {}, "认不出侧别「%s」—— 只认 左/右/L/R/Left/Right/-（- = 不带左右）" % (side,)
    has_finger = any(str(b).startswith("Hand") for b in sp["bones"])
    if has_finger and not ns:
        return {}, "「%s」是指/掌类动作，必须指定侧（左 或 右）——不能给 -" % intent
    ai = "XYZ".index(sp["axis"])
    sgn = float(sp.get("sign", 1)) * float((sp.get("side_sign") or {}).get(ns or "-", 1))
    out = {}
    scale = sp.get("scale") or [1.0]
    for idx, b in enumerate(sp["bones"]):
        sc = scale[idx] if idx < len(scale) else 1.0
        if b.startswith("Hand"):
            for j in (sp.get("joints") or [1]):
                for f in FING:
                    v = [0.0, 0.0, 0.0]
                    v[ai] = sgn * float(deg) * (sc if b.startswith("Hand") else 1.0)
                    out[PREFIX + _side(ns) + "Hand" + f + str(j)] = v
        else:
            v = [0.0, 0.0, 0.0]
            v[ai] = sgn * float(deg) * sc
            limb = b in ("Arm", "ForeArm", "Hand", "UpLeg", "Leg", "Foot", "ToeBase",
                         "Shoulder")
            out[PREFIX + (_side(ns) if limb else "") + b] = v
    return out, None


def build_pose(cmd: list):
    """cmd = [意图, 侧, 角度, 意图, 侧, 角度…]（角度可为负；侧给 `-` 表示不带左右）。"""
    if not cmd or len(cmd) % 3:
        return None, "命令必须是 3 的倍数：[意图 侧 角度] × N"
    pose, errs = {}, []
    for i in range(0, len(cmd), 3):
        intent, side, deg = cmd[i], cmd[i + 1], cmd[i + 2]
        try:
            d = float(deg)
        except (TypeError, ValueError):
            errs.append("角度不是数：「%s」" % deg)
            continue
        part, err = compile_intent(intent, side, d)
        if err:
            errs.append(err)
            continue
        for k, v in part.items():
            cur = pose.get(k, [0.0, 0.0, 0.0])
            pose[k] = [cur[j] + v[j] for j in range(3)]
    if errs:
        return None, " / ".join(errs)
    return pose, None


def _render(pose: dict, out: str, half: bool = False, w: int = 0, h: int = 0,
            engine: str = "", margin: float = 0.0, glb: str = "") -> dict:
    """写临时 pose.json 并交给 blender 位渲染（写盘与起进程的门在那里）。

    `glb` 可指定源件（2026-10-19 加）：原来源件写死在 `GLB`，换资产就得改代码 ——
    "换更高模的资产来补逼真"这件事必须先做到**资产无关**，否则每换一次都是改代码。
    """
    from . import blender_cap as _bl
    tmp = WS / ".scratch" / "dh_pose" / "_cap_pose.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(pose, ensure_ascii=False), encoding="utf-8")
    src = str(glb or GLB)
    if not Path(src).is_absolute():
        src = str(WS / src)
    args = ["-b", "-P", RENDER, "--", "--glb", src, "--pose", str(tmp), "--out", out]
    if half:
        args.append("--half")
    # 2026-10-19 加（主人令「画面清晰」）：分辨率与引擎要能从能力位传下去，
    # 不然"清晰"永远只能停在脚本的默认 1080×1920。
    if w and h:
        args += ["--w", str(int(w)), "--h", str(int(h))]
    if engine:
        args += ["--engine", str(engine)]
    if margin:
        args += ["--margin", str(float(margin))]
    return _bl.run(args=args)


def status(**_kw) -> dict:
    sp = _spec()
    return {"ok": True, "op": "status", "kind": "dh_pose",
            "语义表": str(SPEC.relative_to(WS)), "条数":
                len([k for k in sp if not k.startswith("_")]),
            "骨架来源": GLB,
            "口径": "自转=局部Y（旋转轴探针实测）；指/趾骨已绑（30/40 与 2/4 有权重，其余为末端骨）",
            "不写盘": True}


def semantics(**_kw) -> dict:
    sp = _spec()
    return {"ok": True, "op": "semantics", "kind": "dh_pose", "表": sp}


def compile(cmd=None, **_kw) -> dict:
    pose, err = build_pose(cmd or [])
    if err:
        return {"ok": False, "op": "compile", "error": err, "fail_closed": True}
    return {"ok": True, "op": "compile", "kind": "dh_pose",
            "骨数": len(pose), "pose": pose}


def pose(cmd=None, out="", half=False, w=0, h=0, engine="", margin=0.0, glb="", **_kw) -> dict:
    bones, err = build_pose(cmd or [])
    if err:
        return {"ok": False, "op": "pose", "error": err, "fail_closed": True}
    dst = out or str(WS / "outputs" / "cloud" / "digital_human_selfintro" / "dh_pose_cap.png")
    # 🔴 2026-10-19 修（主人发 filesystem_write 票后第一次真跑当场栽的）：
    #    ① `out` 的父目录不存在时，渲染脚本落**边车 .json**（图+源哈希回执）会
    #       FileNotFoundError —— 而 **Blender 会吞掉 Python 异常、exit code 仍是 0**，
    #       于是外层拿到 exit=0 就报了 ok:true，其实一张图都没有（典型 P1：判据看错对象）。
    #    ② 现在两头都补：先建父目录；跑完**以"图在不在、多大"为判据**，不看 exit code。
    dst_p = Path(dst)
    if not dst_p.is_absolute():
        dst_p = WS / dst_p
    try:
        dst_p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"ok": False, "op": "pose", "kind": "dh_pose", "骨数": len(bones),
                "出图": str(dst_p), "error": "mkdir_failed", "why": str(e)}
    r = _render(bones, str(dst_p), bool(half), int(w or 0), int(h or 0), str(engine or ""),
                float(margin or 0), str(glb or ""))
    produced = dst_p.is_file() and dst_p.stat().st_size > 0
    return {"ok": bool(produced), "op": "pose", "kind": "dh_pose",
            "骨数": len(bones), "出图": str(dst_p),
            "图在不在": produced,
            "图字节": dst_p.stat().st_size if dst_p.is_file() else 0,
            "判据": "**以图在不在为准，不看 Blender 的 exit code**（它会吞 Python 异常仍退 0）",
            "blender": {"exit": r.get("exit"), "denied": r.get("denied", False)},
            "尾巴": (r.get("out") or "")[-600:]}


ACTS = WS / "state" / "dh-pose" / "actions.json"

# 自然站姿基底（主人令「动作自然」）：这个 rig 的绑定静止姿势是**双臂外展**，
# 只驱动动作骨 ⇒ 没被点名的骨笔直伸着，像机器人。每帧先铺这层再叠动作。
BASE_STANCE = (
    # 实测：这个 rig 的静止姿势双臂**外展水平**，`垂臂 12°` 只挪一点点（图上看不出来）。
    # 要真把手臂放下来，得用 `抬臂` 的**负角**（-58° 实测到位，见 outputs/dh-pose/natural-fill-4k.png）。
    ("抬臂", "L", -58), ("抬臂", "R", -58),
    ("屈肘", "L", 15), ("屈肘", "R", 15),
)


def _acts_spec() -> dict:
    if not ACTS.is_file():
        return {}
    return json.loads(ACTS.read_text(encoding="utf-8")).get("动作", {})


def _lerp_frames(defn: dict):
    """动作定义（语义关键帧）→ 逐帧骨角度：**在语义层插值**，再编译（这样每帧都仍是可读的意图）。"""
    n = int(defn["帧"])
    kfs = sorted(defn["关键帧"], key=lambda k: float(k["相位"]))
    out = []
    for i in range(n):
        p = i / max(1, n - 1)
        lo = kfs[0]
        hi = kfs[-1]
        for j in range(len(kfs) - 1):
            if float(kfs[j]["相位"]) <= p <= float(kfs[j + 1]["相位"]):
                lo, hi = kfs[j], kfs[j + 1]
                break
        span = float(hi["相位"]) - float(lo["相位"])
        t = 0.0 if span <= 1e-9 else (p - float(lo["相位"])) / span
        # 🔴 2026-10-13 主人令「所有的细节都要做到位」：原来 t 是**线性**的 ⇒ 动起来匀速机械。
        #   真人动作起停都有加减速 ⇒ 过一层 smoothstep（首尾导数为 0，中段最快）。
        t = t * t * (3.0 - 2.0 * t)
        vals = {}
        for kf, w in ((lo, 1.0 - t), (hi, t)):
            for it, side, deg in kf.get("语义", []):
                vals[(it, side)] = vals.get((it, side), 0.0) + float(deg) * w
        frame, errs = {}, []
        for (it, side), deg in vals.items():
            if abs(deg) < 1e-6:
                continue
            part, err = compile_intent(it, side, deg)
            if err:
                errs.append(err)
                continue
            for k, v in part.items():
                cur = frame.get(k, [0.0, 0.0, 0.0])
                frame[k] = [cur[q] + v[q] for q in range(3)]
        out.append((frame, errs))
    return out


def acts(action="", out_dir="", list_only=False, glb="", **_kw) -> dict:
    """把「动作定义（语义关键帧）」编译成逐帧姿势并渲染成 PNG 序列。

    这是「所有肢体动作都能实现」的正解：动作不是硬编码函数，而是 76 块语义积木的任意组合。
    """
    spec = _acts_spec()
    if not spec:
        return {"ok": False, "op": "acts", "error": "缺 %s" % ACTS, "fail_closed": True}
    if list_only or not action:
        return {"ok": True, "op": "acts", "kind": "dh_pose",
                "动作数": len(spec), "名单": sorted(spec.keys()),
                "定义": str(ACTS.relative_to(WS))}
    if action not in spec:
        return {"ok": False, "op": "acts", "fail_closed": True,
                "error": "动作定义里没有「%s」（现读 %s，共 %d 条）"
                         % (action, ACTS.name, len(spec)), "名单": sorted(spec.keys())}
    frames = _lerp_frames(spec[action])
    errs = sorted({e for _f, es in frames for e in es})
    if errs:
        return {"ok": False, "op": "acts", "fail_closed": True,
                "error": "编译有红：" + " / ".join(errs[:3])}
    # 🔴 2026-10-19 加（主人令「动作自然」）：动作只驱动它点名的骨，**没点名的骨停在绑定
    #    静止姿势（这个 rig 的静止姿势是双臂外展的 A/T-pose）** ⇒ 挥手时另一只手笔直伸着，
    #    看着像机器人。所以先铺一层**自然站姿**（双臂下垂+微屈肘+髋微倾），动作再叠上去。
    base, base_err = build_pose([x for t in BASE_STANCE for x in t])
    if base_err:
        return {"ok": False, "op": "acts", "error": "基底站姿编译失败：" + base_err,
                "fail_closed": True}
    merged = []
    for f, _e in frames:
        m = {k: list(v) for k, v in base.items()}
        for k, v in f.items():
            m[k] = [base.get(k, [0.0, 0.0, 0.0])[i] + v[i] if k in base else v[i]
                    for i in range(3)]
        merged.append(m)
    frames = [(m, []) for m in merged]
    # 🔴 同上一轮 `pose` 那个假绿：`out` 用相对路径时，Blender 按**它自己的 cwd** 解析
    #    （实测落到 `C:\outputs\...`），而回执还报 ok。⇒ 这里必须先解析成绝对路径。
    dst = out_dir or str(WS / "outputs" / "cloud" / "digital_human_selfintro" / "acts_cap" / action)
    dst_p = Path(dst)
    if not dst_p.is_absolute():
        dst_p = WS / dst_p
    dst_p.mkdir(parents=True, exist_ok=True)
    tmp = WS / ".scratch" / "dh_pose" / ("_seq_%s.json" % action)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps([f for f, _e in frames], ensure_ascii=False), encoding="utf-8")
    from . import blender_cap as _bl
    r = _bl.run(args=["-b", "-P", RENDER, "--", "--glb", (str(glb) if glb else GLB),
                      "--pose-seq", str(tmp),
                      "--out", str(dst_p)])
    # 判据：**数盘上真帧**，不看 exit code（Blender 会吞异常仍退 0）
    got = sorted(p for p in dst_p.glob("f*.png") if p.stat().st_size > 1024)
    short = [p.name for p in dst_p.glob("f*.png") if p.stat().st_size <= 1024]
    return {"ok": len(got) >= 1 and not short, "op": "acts", "kind": "dh_pose", "动作": action,
            "帧数": len(frames), "出帧目录": str(dst_p),
            "盘上有效帧": len(got), "残帧": short[:5],
            "基底站姿": "已叠加（垂臂+微屈肘+髋微倾）",
            "判据": "**数盘上有效帧（>1KB）**，不看 Blender 的 exit code",
            "blender": {"exit": r.get("exit"), "denied": r.get("denied", False)},
            "尾巴": (r.get("out") or "")[-400:]}


def run(op="status", **params) -> dict:
    fn = {"status": status, "semantics": semantics, "compile": compile, "pose": pose,
          "acts": acts}.get(op)
    if not fn:
        return {"ok": False, "error": "未知 op：%s" % op, "fail_closed": True,
                "ops": ["status", "semantics", "compile", "pose", "acts"]}
    return fn(**params)
