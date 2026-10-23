#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把骨轴原始读数打成「骨位标签表」（主人 2026-10-21 令：
「**你要对绑定好的触手标记好是控制什么的，才明白使用什么来操控数字人的动作**」）。

输入：state/hd/app-after/bone-raw.json（_bone-raw.py 现量：每根骨绕 X/Y/Z 转 0.35 rad 后子骨的世界位移）
输出：
  · state/dh-bone-map.json                 机器读
  · holo_pet_w3/digital-human/bone-map.js  页面读（window.GBT_BONE_MAP，经典脚本，file:// 直接可引）
  · state/dh-bone-map.md                   人读一页表

口径（写死，别猜）：
  · 世界 +X = **她自己的左边**（实测 RightHand x≈−0.24）· +Y 上 · +Z 朝镜头（身前）
  · 每个动作**不靠人猜轴**：由「这个动作要往世界的哪个方向走」反查实测数据 ——
    哪个轴的位移里"那个方向"最大，就用哪个轴；符号也直接取实测的正负。
    这样**标签不可能跟实测打架**（上一版手写 33 条里有 12 条打架，就是这条规则的由来）。
"""
import json
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

RAW = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\hd\app-after\bone-raw.json"
OUT_JSON = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\dh-bone-map.json"
OUT_JS = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\digital-human\bone-map.js"
OUT_MD = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\dh-bone-map.md"

FINGER_CN = {"Thumb": "拇指", "Index": "食指", "Middle": "中指", "Ring": "无名指", "Pinky": "小指"}
BASE_CN = {
    "Hips": "骨盆（根）", "Spine": "腰椎", "Spine1": "下胸椎", "Spine2": "上胸椎",
    "Neck": "脖子", "Head": "头", "HeadTop_End": "头顶（末端）",
    "LeftShoulder": "左肩", "LeftArm": "左大臂", "LeftForeArm": "左前臂", "LeftHand": "左手掌",
    "RightShoulder": "右肩", "RightArm": "右大臂", "RightForeArm": "右前臂", "RightHand": "右手掌",
    "LeftUpLeg": "左大腿", "LeftLeg": "左小腿", "LeftFoot": "左脚", "LeftToeBase": "左脚趾",
    "LeftToe_End": "左脚趾（末端）",
    "RightUpLeg": "右大腿", "RightLeg": "右小腿", "RightFoot": "右脚", "RightToeBase": "右脚趾",
    "RightToe_End": "右脚趾（末端）",
}
SEM = {
    "Hips": ("骨盆", "骨盆前倾 / 整体转向（根骨）"),
    "Spine": ("腰", "前倾后仰 · 侧倾 · 转体"),
    "Spine1": ("下胸椎", "前倾后仰 · 侧倾 · 转体"),
    "Spine2": ("上胸椎", "前倾后仰 · 侧倾 · 转体"),
    "Neck": ("脖子", "点头 · 转头 · 侧歪"),
    "Head": ("头", "点头 · 转头 · 侧歪"),
    "Shoulder": ("肩", "抬肩 / 耸肩"),
    "Arm": ("大臂", "外展（抬手）· 前后摆 · 内外旋"),
    "ForeArm": ("前臂", "屈肘"),
    "Hand": ("手掌", "腕屈伸 · 腕摆"),
    "UpLeg": ("大腿", "屈髋（抬腿向前）· 外展"),
    "Leg": ("小腿", "屈膝"),
    "Foot": ("脚", "踝：勾脚 / 绷脚 / 内外翻"),
    "ToeBase": ("脚趾", "脚趾屈伸"),
}

# 每根可驱动骨支持哪些「动作键」。动作键只声明**方向语义**，轴与符号由实测反查。
#   flex=前后屈伸(toward world Z) · abduct=外展(toward world X) · twist=转体(toward world Y)
#   bend=前倾(Z) · side=侧倾(X) · nod=点头(Z) · turn=转头(Y) · tilt=侧歪(X)
#   shrug=抬肩(Y) · bob=升降(Y) · point=绷脚(Z) · wave=腕摆(Z)
MOTION = {
    "Hips":   ["bend", "twist"],
    "Spine":  ["bend", "side", "twist"],
    "Spine1": ["bend", "side", "twist"],
    "Spine2": ["bend", "side", "twist"],
    "Neck":   ["nod", "turn", "tilt"],
    "Head":   ["nod", "turn", "tilt"],
    "LeftShoulder":  ["shrug"],
    "RightShoulder": ["shrug"],
    "LeftArm":  ["abduct", "flex"],
    "RightArm": ["abduct", "flex"],
    "LeftForeArm":  ["flex"],
    "RightForeArm": ["flex"],
    "LeftHand":  ["wave"],
    "RightHand": ["wave"],
    "LeftUpLeg":  ["flex", "abduct"],
    "RightUpLeg": ["flex", "abduct"],
    "LeftLeg":  ["flex"],
    "RightLeg": ["flex"],
    "LeftFoot":  ["flex", "point", "toeout"],
    "RightFoot": ["flex", "point", "toeout"],
    "LeftToeBase":  ["flex"],
    "RightToeBase": ["flex"],
}
WANT = {
    "flex": "z", "bend": "z", "nod": "z", "point": "z", "wave": "z",
    "abduct": "x", "side": "x", "tilt": "x", "toeout": "x",
    "twist": "y", "turn": "y", "shrug": "y", "bob": "y",
}
DIR_CN = {"z": "身前/身后", "y": "上/下", "x": "左/右"}
AXIS_IDX = {"x": 0, "y": 1, "z": 2}


def want_of(name, key):
    """这个动作要往世界的哪个方向走 —— **带符号**（正值朝那一边）。
    这里是一层语义翻译，不涉及具体骨轴；轴与符号由实测反查（见 pick_axis）。
      · abduct（外展）：往**她自己那一侧**走（左骨朝 +X，右骨朝 −X）
      · ForeArm 的 flex（屈肘）：要**把手抬起来** ⇒ 朝 +Y
      · 其余 flex/bend/nod/point/wave：朝身前 +Z；side/tilt 朝 +X；turn/twist/shrug/bob 朝 +Y
    """
    axis = WANT.get(key)
    if axis is None:
        return None
    sgn = 1
    if key in ("abduct", "toeout"):
        sgn = 1 if name.startswith("Left") else -1
    elif key == "flex" and "ForeArm" in name:
        axis, sgn = "y", 1
    return (AXIS_IDX[axis], sgn, axis)
USE = {
    "Hips": ["walk"], "Spine": ["idle"], "Spine1": ["idle", "walk", "wave"],
    "Neck": ["idle", "wave"], "Head": ["idle", "walk", "wave"],
    "LeftArm": ["idle", "walk"], "RightArm": ["idle", "walk", "wave"],
    "LeftForeArm": ["idle", "walk", "wave"], "RightForeArm": ["idle", "walk", "wave"],
    "LeftHand": ["wave"], "RightHand": ["wave"],
    "LeftUpLeg": ["walk"], "RightUpLeg": ["walk"],
    "LeftLeg": ["walk"], "RightLeg": ["walk"],
    "LeftFoot": ["walk"], "RightFoot": ["walk"],
}


def cn_name(n):
    if n in BASE_CN:
        return BASE_CN[n]
    for side, s in (("Left", "左"), ("Right", "右")):
        if n.startswith(side):
            rest = n[len(side):]
            for k, c in FINGER_CN.items():
                if rest.startswith(k):
                    idx = rest[len(k):]
                    return "%s%s%s" % (s, c, ("第 %s 节" % idx) if idx else "")
    return n


def seg_of(n):
    if n.startswith("LeftHand"):
        return "左手"
    if n.startswith("RightHand"):
        return "右手"
    if n.startswith("Left"):
        return "左臂" if n.startswith(("LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand")) else "左腿"
    if n.startswith("Right"):
        return "右臂" if n.startswith(("RightShoulder", "RightArm", "RightForeArm", "RightHand")) else "右腿"
    return "躯干"


def sem_of(n):
    base = n
    for side in ("Left", "Right"):
        if n.startswith(side):
            base = n[len(side):]
            break
    if base.startswith(("Thumb", "Index", "Middle", "Ring", "Pinky")):
        return ("手指", "指节屈伸 / 张开")
    for k, v in SEM.items():
        if base.startswith(k):
            return v
    return ("未分类", "未标（需人工确认）")


def axis_phrase(v):
    if not v:
        return "—"
    dx, dy, dz, L = v
    parts = []
    if abs(dz) >= 0.008:
        parts.append(("身前" if dz > 0 else "身后", abs(dz)))
    if abs(dy) >= 0.008:
        parts.append(("向上" if dy > 0 else "向下", abs(dy)))
    if abs(dx) >= 0.008:
        parts.append(("她左侧" if dx > 0 else "她右侧", abs(dx)))
    if not parts:
        return "几乎不动（L=%.3f）" % L
    parts.sort(key=lambda t: -t[1])
    return " / ".join("%s %.2fm" % (a, b) for a, b in parts[:2])


def pick_axis(ax, name, key):
    """在实测三轴里挑「往这个动作要去的那个世界方向走得最多」的轴，并给出**驱动符号**。

    符号口径（很重要，上一版就在这里翻过车）：`sign` 是「调用方给正数 amount 时，
    该轴要乘的正负」——即 sign 已经包含了 want 的方向。这样在页面上写
    `driveBy("RightArm","abduct", +1.3)` 一定是**往她自己那一侧抬**，不用再记镜像符号。
    """
    w = want_of(name, key)
    if w is None:
        return None
    idx, want_sign, axis_name = w
    best = None
    for a in ("x", "y", "z"):
        v = ax.get(a)
        if not v:
            continue
        amt = v[idx]
        if best is None or abs(amt) > abs(best[1]):
            best = (a, amt, v)
    if best is None:
        return None
    a, amt, v = best
    sign = (1 if amt > 0 else -1) * want_sign
    return {"axis": a, "sign": sign, "want": axis_name, "want_sign": want_sign,
            "amount": round(abs(amt), 4), "weak": abs(amt) < 0.01,
            "phrase": axis_phrase(v)}


def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    rows = raw["rows"]
    out, weak = [], []
    for r in rows:
        n = str(r["full"]).replace("mixamorig", "")
        cnk, what = sem_of(n)
        ax = r.get("ax") or {}
        order = sorted([k for k in ("x", "y", "z") if ax.get(k)],
                       key=lambda k: -(ax[k][3] if ax.get(k) else -1))
        phrases = {k: axis_phrase(ax.get(k)) for k in ("x", "y", "z")}
        drive = {}
        for key in MOTION.get(n, []):
            d = pick_axis(ax, n, key)
            if not d:
                continue
            d["dir"] = d["want"]
            d["dir_cn"] = DIR_CN[d["want"]]
            d["note"] = "正数 amount = 往%s走（量得 %.3fm）" % (
                {"z": "身前", "y": "上", "x": "她自己那一侧"}[d["want"]], d["amount"])
            drive[key] = d
            if d["weak"]:
                weak.append({"bone": n, "key": key, "axis": d["axis"], "amount": d["amount"]})
        out.append({
            "name": n, "cn": cn_name(n), "seg": seg_of(n), "kind": cnk, "what": what,
            "parent": (str(r.get("parent")).replace("mixamorig", "") if r.get("parent") else None),
            "tip": (str(r.get("tip")).replace("mixamorig", "") if r.get("tip") else None),
            "leaf": (r.get("tip") is None),
            "ax": ax, "ax_phrase": phrases,
            "main": (order[0] if order else None),
            "order": order,
            "main_phrase": ("%s 轴 → %s" % (order[0].upper(), phrases[order[0]])) if order else "—",
            "drive": drive, "used_by": USE.get(n, []),
        })

    doc = {
        "schema": "gbt-bone-map/v2",
        "at": "2026-10-21",
        "source": "state/hd/app-after/bone-raw.json（_bone-raw.py 现量：每轴 +0.35 rad，子骨世界位移）",
        "world": {"+X": "她自己的左边", "+Y": "上", "+Z": "朝镜头（身前）"},
        "rule": "动作 → 世界方向（WANT）→ 在实测三轴里挑该方向位移最大的轴，符号取实测",
        "bones": out,
        "summary": {
            "count": len(out),
            "leaf": sum(1 for b in out if b["leaf"]),
            "drivable": sorted(MOTION.keys()),
            "drive_keys": sum(len(b["drive"]) for b in out),
            "weak": weak,
        },
    }
    json.dump(doc, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    packed = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    with open(OUT_JS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* GBT小土豆V8 · 骨位标签表（生成件 · 写手 tools/codex-scripts/dh-bone-map.py）\n"
                 " * 每根骨「管什么 / 哪个轴 / 正负号朝哪」都由 bone-raw.json 的实测读数反查得出。\n"
                 " * 页面只读它；改了模型就重跑写手，别手改这里。 */\n")
        fh.write("window.GBT_BONE_MAP = %s;\n" % packed)

    lines = ["# 骨位标签表（65 根 · 现量）", "",
             "> 世界：**+X = 她自己的左边** · +Y 上 · +Z 朝镜头（身前）",
             "> 轴与符号**不是我猜的**：动作先声明「要往世界哪个方向走」，再在实测三轴里挑该方向位移最大的那根轴，符号取实测正负。",
             "> 所以这张表跟读数**不可能打架**（上一版手写 33 条，12 条打架，所以改成反查）。", "",
             "## 一、可驱动的关节（按这张表摆，不凭感觉）", "",
             "| 骨 | 中文 | 动作 | 轴 | 符号 | 方向语义 | 实测 |", "|---|---|---|---|---|---|---|"]
    for b in out:
        for key, d in b["drive"].items():
            lines.append("| `%s` | %s | %s | `%s` | %+d | %s | %s%s |" % (
                b["name"], b["cn"], key, d["axis"], d["sign"], d["dir_cn"], d["phrase"],
                "（⚠ 位移 <1cm，别当主驱动）" if d["weak"] else ""))
    lines += ["", "## 二、65 根逐根", "",
              "| 骨 | 中文 | 段 | 管什么 | 主轴实测 | 用在 |", "|---|---|---|---|---|---|"]
    for b in out:
        lines.append("| `%s` | %s | %s | %s | %s | %s |" % (
            b["name"], b["cn"], b["seg"], b["what"], b["main_phrase"],
            ("、".join(b["used_by"]) or "—")))
    lines += ["", "## 三、弱驱动（位移 <1cm，标出来免得当成「能大动」）", ""]
    if weak:
        for w in weak:
            lines.append("- `%s` 的 `%s`：`%s` 轴只有 %.3fm" % (w["bone"], w["key"], w["axis"], w["amount"]))
    else:
        lines.append("- 无")
    lines += ["", "叶子骨 %d 根（没有子骨可量）：%s" % (
        doc["summary"]["leaf"], "、".join(b["name"] for b in out if b["leaf"]))]
    open(OUT_MD, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    print(json.dumps({"ok": True, "bones": len(out), "leaf": doc["summary"]["leaf"],
                      "drive_keys": doc["summary"]["drive_keys"], "weak": len(weak),
                      "json": OUT_JSON, "js": OUT_JS, "md": OUT_MD}, ensure_ascii=False))


if __name__ == "__main__":
    main()
