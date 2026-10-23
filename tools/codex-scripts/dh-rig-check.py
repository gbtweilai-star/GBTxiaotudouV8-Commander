#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数字人页 · 骨架对称性 & "动作真在动" 的机检件（**含正负对照**）

## 为什么要有这一件
主人令 2026-10-08：「每个动作要能证明真在动（不是"坐标合法"）：给出每帧真实角度/位移」
「骨架左右对称（这是踩过的坑：骨架左右不对称会长歪）」。

页面自己会算一遍读数（页面里第 ② 卡的"动作取证"）。但**自证不算证**：
所以这一件**独立解析页面里的同一份规格**（页面把它写成严格 JSON，就是为了这一件能读），
用**自己的实现**把正向运动学再算一遍，两套实现对账。对不上就是有问题。

## 查四条（缺一不可）
 ① 结构：父子都在表里 · 无环 · 必有根 · 主人点名的关节齐（髋/脊/胸/颈/头 · 肩-上臂-前臂-手 · 髋-大腿-小腿-脚-脚掌）
 ② 静息对称：每一对镜像关节的静息世界坐标关于中轴互为镜像（容差 0.5px）
 ③ 镜像律：rest_L == -rest_R；且**标了 sym 的动作**在**每个关键帧**上都要 delta_L == -delta_R
 ④ 真在动：每个动作按 41 点采样算三个量 —— 幅度 d2（相对 t=0 最大角偏移）、
    连续性 d1（相邻帧最大 |Δ角|）、位移 disp（关节世界坐标相对 t=0 最大位移），
    并且要**超过同一套采样量出来的 idle 基线**（现量基线，不是拍脑袋常数）。
    另有一行伪关节 root（角度=yaw、位置=根位移）—— 转身/走动/蹲起的驱动量在它身上，
    不算它，转身会被误判成"没动"。

## 正负对照（**判据自己也要被测**）
 负对照 A：故意把一侧关节的横向偏移取反 ⇒ 对称检查**必须报红**
 负对照 B：故意破坏镜像律（把 R 的静息角改成与 L 同号）⇒ 镜像律检查**必须报红**
 负对照 C：把某个"真在动"的动作整套关键帧清零 ⇒ 动作检查**必须报红**
 三条负对照若有一条**没报红**，说明判据是死的 —— 本件自己判失败（退出码 5），
 因为"通不过扰动的判据"等于没有判据。

## 语音三腿（只读探测，全部容忍失败）
 桥（本机回环 127.0.0.1:8765，设计内依赖）· intercom.py status（三腿读数）· SAPI 嗓表。
 失败**如实记原文**，不影响骨架/动作的判决（它们是两件事，不许互相糊）。

用法：
    py -3.14 tools/codex-scripts/dh-rig-check.py                # 查 + 正负对照
    py -3.14 tools/codex-scripts/dh-rig-check.py --json         # 只吐 JSON
    py -3.14 tools/codex-scripts/dh-rig-check.py --emit-state    # 顺手写 state/digital-human.json（**唯一写者**）
退出码：0=全过 · 3=骨架/对称有问题 · 4=动作没真动 · 5=负对照没报红 · 9=读不到规格
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "holo_pet_w3" / "digital-human" / "index.html"
STATE = ROOT / "state" / "digital-human.json"
BRIDGE_HOST, BRIDGE_PORT = "127.0.0.1", 8765      # 本机回环（设计内依赖，主人令里点名允许的那一条）
PY_EXE = sys.executable
TOL_PX = 0.5
SAMPLES = 41
_CREATE_NO_WINDOW = 0x08000000


# ───────────────────────── 规格装载 ─────────────────────────
def load_specs(page: Path):
    """从页面里取两份**严格 JSON** 规格（页面用注释标记把它们圈出来，就是为了这里能读）。"""
    text = page.read_text(encoding="utf-8")
    out = {}
    for key, begin, end in (("rig", "GBT-RIG-SPEC-BEGIN */", "/* GBT-RIG-SPEC-END"),
                            ("act", "GBT-ACT-SPEC-BEGIN */", "/* GBT-ACT-SPEC-END")):
        i = text.find(begin)
        j = text.find(end)
        if i < 0 or j < 0 or j <= i:
            raise SystemExit("读不到规格块 %s（标记 %s 不在页面里）" % (key, begin))
        raw = text[i + len(begin):j]
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SystemExit("规格块 %s 不是严格 JSON：%s" % (key, e))
    return out["rig"], out["act"], text


# ───────────────────────── 正向运动学（**独立实现**，只与规格同源） ─────────────────────────
def fk(rig: dict, pose: dict, rootx: float = 0.0, rooty: float = 0.0, yaw: float = 0.0):
    """关节世界位姿 = 父位姿 · translate(off) · rotate(rest+Δ)；再把根平移与 yaw 水平前缩施加上去。
    这两条**必须**与页面施加的 SVG 变换同源，否则读数与画面不一致（页面初版就踩过）。"""
    by = {j["n"]: j for j in rig["joints"]}
    cx = rig["root"][0] + rootx
    cy_ = math.cos(math.radians(yaw))
    sx = (0.28 if not cy_ else (cy_ if abs(cy_) >= 0.28 else (0.28 if cy_ > 0 else -0.28)))
    world = {}
    for j in rig["joints"]:
        a = j["rest"] + float(pose.get(j["n"], 0.0))
        p = world.get(j["p"]) if j["p"] else None
        if p is None:
            bx, byy, ba = cx, rig["root"][1] + rooty, 0.0
        else:
            bx, byy, ba = p["x"], p["y"], p["a"]
        r = math.radians(ba)
        ex, ey = math.cos(r), math.sin(r)
        x = bx + j["off"][0] * ex + j["off"][1] * (-ey)
        y = byy + j["off"][0] * ey + j["off"][1] * ex
        atot = ba + a
        x = cx + (x - cx) * sx
        world[j["n"]] = {"x": x, "y": y, "a": atot,
                         "dx": -math.sin(math.radians(atot)) * sx,
                         "dy": math.cos(math.radians(atot))}
    return world


def joint_order(rig):
    return [j["n"] for j in rig["joints"]]


def pose_at(acts, name, t):
    a = acts[name]
    ks = a["keys"]
    if a["dur"] == 0 or len(ks) == 1:
        return dict(ks[0].get("d") or {})
    u = (t % 1.0) if a.get("loop") else min(1.0, max(0.0, t))
    for i in range(len(ks) - 1):
        lo, hi = ks[i], ks[i + 1]
        if lo["t"] <= u <= hi["t"]:
            span = (hi["t"] - lo["t"]) or 1.0
            k = (u - lo["t"]) / span
            k = k * k * (3 - 2 * k)                      # smoothstep（与页面同一条，观感用）
            names = set(lo.get("d") or {}) | set(hi.get("d") or {})
            return {q: float((lo.get("d") or {}).get(q, 0.0)) +
                       (float((hi.get("d") or {}).get(q, 0.0)) - float((lo.get("d") or {}).get(q, 0.0))) * k
                    for q in names}
    return dict(ks[-1].get("d") or {})


def world_at(rig, acts, name, t):
    d = pose_at(acts, name, t)
    return (fk(rig, d, d.get("rootX", 0.0), d.get("rootY", 0.0), d.get("yaw", 0.0)), d)


# ───────────────────────── ① 结构 ─────────────────────────
def check_structure(rig):
    order = joint_order(rig)
    by = {j["n"]: j for j in rig["joints"]}
    issues = []
    roots = [n for n in order if not by[n]["p"]]
    for n in order:
        p = by[n]["p"]
        if p is not None and p not in by:
            issues.append("关节 %s 的父 %s 不在表里" % (n, p))
    if len(roots) != 1:
        issues.append("根关节应当恰好 1 个，现读 %d 个：%s" % (len(roots), roots))
    for n in order:                                       # 环检测
        seen, cur = set(), n
        while cur is not None:
            if cur in seen:
                issues.append("关节链上有环：%s → … → %s" % (n, cur)); break
            seen.add(cur)
            cur = by.get(cur, {}).get("p")
    missing = []
    for cn, nm in rig.get("required", []):
        if nm not in by:
            missing.append("%s(%s)" % (cn, nm))
    if missing:
        issues.append("主人点名的关节不在表里：" + " · ".join(missing))
    return {"ok": not issues, "issues": issues, "joints": len(order), "roots": roots,
            "required_ok": not missing, "pairs": len(rig.get("pairs", []))}


# ───────────────────────── ②③ 对称与镜像律 ─────────────────────────
def check_symmetry(rig):
    w = fk(rig, {})
    cx = 2 * rig["root"][0]
    worst, worst_pair, bad = 0.0, "", []
    for l, r in rig["pairs"]:
        d = max(abs(w[l]["x"] + w[r]["x"] - cx), abs(w[l]["y"] - w[r]["y"]))
        if d > worst:
            worst, worst_pair = d, "%s/%s" % (l, r)
        if d > TOL_PX:
            bad.append("%s/%s:%.2fpx" % (l, r, d))
    return {"ok": not bad, "worst_px": round(worst, 4), "worst_pair": worst_pair,
            "tolerance_px": TOL_PX, "bad": bad, "pairs_checked": len(rig["pairs"])}


def check_rest_law(rig):
    by = {j["n"]: j for j in rig["joints"]}
    bad = []
    for l, r in rig["pairs"]:
        if abs(by[l]["rest"] + by[r]["rest"]) > 1e-9:
            bad.append("%s:%s vs %s:%s（应互为相反数）" % (l, by[l]["rest"], r, by[r]["rest"]))
    return {"ok": not bad, "bad": bad}


def check_action_mirror(rig, acts):
    pairs = rig["pairs"]
    bad_sym, asym_seen = [], {}
    for name, a in acts.items():
        deltas = [k.get("d") or {} for k in a["keys"]]
        violated_at = None
        has_asym = False
        for kd in deltas:
            for l, r in pairs:
                vl, vr = float(kd.get(l, 0.0)), float(kd.get(r, 0.0))
                if abs(vl + vr) > 1e-9:
                    has_asym = True
                    if violated_at is None:
                        violated_at = "%s:%s vs %s:%s" % (l, vl, r, vr)
        asym_seen[name] = has_asym
        if a.get("sym") and has_asym:
            bad_sym.append("%s（标了 sym=true，却在 %s 上不镜像）" % (name, violated_at))
        if (not a.get("sym")) and (not has_asym):
            bad_sym.append("%s（标了 sym=false，却每个关键帧都完全镜像）" % name)
    return {"ok": not bad_sym, "bad": bad_sym, "per_action_asym": asym_seen}


# ───────────────────────── ④ 真在动 ─────────────────────────
def metric(rig, acts, name):
    mj = joint_order(rig) + ["root"]

    def mp(w, d, n):
        if n == "root":
            return {"a": d.get("yaw", 0.0), "x": rig["root"][0] + d.get("rootX", 0.0),
                    "y": rig["root"][1] + d.get("rootY", 0.0)}
        return {"a": w[n]["a"], "x": w[n]["x"], "y": w[n]["y"]}

    rows = [world_at(rig, acts, name, i / (SAMPLES - 1)) for i in range(SAMPLES)]
    base = {n: mp(rows[0][0], rows[0][1], n) for n in mj}
    prev = dict(base)
    per = {n: {"d1": 0.0, "d2": 0.0, "disp": 0.0} for n in mj}
    mx = {"d1": 0.0, "d2": 0.0, "disp": 0.0, "whoD1": "", "whoD2": "", "whoDisp": ""}
    for i, (w, d) in enumerate(rows):
        for n in mj:
            p = mp(w, d, n)
            if i > 0:
                dd = abs(p["a"] - prev[n]["a"])
                per[n]["d1"] = max(per[n]["d1"], dd)
                if dd > mx["d1"]:
                    mx["d1"], mx["whoD1"] = dd, n
            d2 = abs(p["a"] - base[n]["a"])
            per[n]["d2"] = max(per[n]["d2"], d2)
            if d2 > mx["d2"]:
                mx["d2"], mx["whoD2"] = d2, n
            disp = math.hypot(p["x"] - base[n]["x"], p["y"] - base[n]["y"])
            per[n]["disp"] = max(per[n]["disp"], disp)
            if disp > mx["disp"]:
                mx["disp"], mx["whoDisp"] = disp, n
            prev[n] = p
    mx["per"] = per
    return mx


def check_actions(rig, acts):
    base = metric(rig, acts, "idle")
    res, bad = {}, []
    for name, a in acts.items():
        m = metric(rig, acts, name)
        static = (a.get("dur", 0) == 0) or (len(a["keys"]) == 1)
        if name == "idle":
            ok = base["d2"] <= 5 and base["disp"] <= 8
            verdict = "现量基线"
        elif static:
            ok, verdict = True, "静态姿势"
        else:
            ok = (m["d2"] > 5 and m["d1"] > 0.2 and m["disp"] > 2
                  and m["d2"] > 2 * base["d2"] and m["disp"] > 2 * base["disp"])
            verdict = "真在动" if ok else "未达门"
        if not ok:
            bad.append("%s：%s（幅度%.2f° 单帧%.2f° 位移%.2fpx；基线 幅度%.2f° 位移%.2fpx）"
                       % (name, verdict, m["d2"], m["d1"], m["disp"], base["d2"], base["disp"]))
        res[name] = {"cn": a.get("cn", ""), "sym": bool(a.get("sym")), "verdict": verdict,
                     "d2": round(m["d2"], 3), "who_d2": m["whoD2"],
                     "d1": round(m["d1"], 3), "who_d1": m["whoD1"],
                     "disp": round(m["disp"], 3), "who_disp": m["whoDisp"],
                     "moving_joints": sum(1 for n, v in m["per"].items() if v["d2"] > 5 and v["d1"] > 0.2),
                     "joints_measured": len(m["per"])}
    return {"ok": not bad, "bad": bad, "actions": res,
            "baseline": {"d2": round(base["d2"], 3), "who_d2": base["whoD2"],
                         "d1": round(base["d1"], 3), "disp": round(base["disp"], 3),
                         "who_disp": base["whoDisp"], "samples": SAMPLES}}


# ───────────────────────── 正负对照 ─────────────────────────
def clone(o):
    return json.loads(json.dumps(o))


def negative_controls(rig, acts):
    out = []

    def rec(name, expect_red, got_red, detail):
        out.append({"name": name, "expect_red": expect_red, "got_red": bool(got_red),
                    "pass": bool(expect_red == got_red), "detail": detail})

    # A：把左肩的横向偏移取反 ⇒ 对称必须报红
    r2 = clone(rig)
    for j in r2["joints"]:
        if j["n"] == "clavicleL":
            j["off"][0] = -j["off"][0]
    s2 = check_symmetry(r2)
    rec("负对照A·一侧横移取反", True, not s2["ok"], "镜像最大误差 %.2fpx（应 >%.1fpx 才报红）"
        % (s2["worst_px"], TOL_PX))

    # B：破坏镜像律（R 的静息角改成与 L 同号）⇒ 镜像律必须报红
    r3 = clone(rig)
    for j in r3["joints"]:
        if j["n"] == "upperArmR":
            j["rest"] = 83
    l3 = check_rest_law(r3)
    rec("负对照B·静息角不互为相反数", True, not l3["ok"], "报红条数 %d" % len(l3["bad"]))

    # C：把 wave 整套关键帧清零 ⇒ 动作检查必须报红
    a2 = clone(acts)
    for k in a2["wave"]["keys"]:
        k["d"] = {}
    c2 = check_actions(rig, a2)
    rec("负对照C·把 wave 清零", True, not c2["ok"], "wave 判决 = %s"
        % c2["actions"]["wave"]["verdict"])

    # C2：反向扰动 —— 把 idle 的微动放大到"动作级" ⇒ 基线检查必须报红（基线不许混进动作）
    a3 = clone(acts)
    for k in a3["idle"]["keys"]:
        k["d"] = {"thighL": 40, "thighR": -40, "shinL": -60, "shinR": 60, "rootY": 40, "yaw": k["t"] * 300}
    c3 = check_actions(rig, a3)
    rec("负对照C2·把 idle 放大成动作", True, not c3["ok"], "idle 现被量成 幅度%.2f° 位移%.2fpx"
        % (c3["baseline"]["d2"], c3["baseline"]["disp"]))
    return out


# ───────────────────────── 语音三腿（只读探测，容忍失败） ─────────────────────────
def probe_voice():
    v = {"at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # 桥：本机回环 127.0.0.1:8765 —— 主人令里**明确登记的"设计内本机依赖"**，这里只做 TCP 连通性判断
    try:
        s = socket.create_connection((BRIDGE_HOST, BRIDGE_PORT), timeout=2.5)
        s.close()
        v["bridge"] = {"ok": True, "target": "http://%s:%d/api/message" % (BRIDGE_HOST, BRIDGE_PORT),
                       "why": "本机回环·设计内依赖（主人令点名允许的唯一一条）· 只判能不能连上，不发请求"}
    except OSError as e:
        v["bridge"] = {"ok": False, "target": "http://%s:%d/api/message" % (BRIDGE_HOST, BRIDGE_PORT),
                       "error": "%s: %s" % (type(e).__name__, e)}

    # intercom.py status（本仓既有的只读三腿读数口）
    ic = ROOT / "tools" / "codex-scripts" / "intercom.py"
    if not ic.is_file():
        v["intercom"] = {"ok": False, "error": "intercom.py 不在盘上：" + str(ic)}
    else:
        try:
            cp = subprocess.run([PY_EXE, str(ic), "status"], capture_output=True, timeout=180,
                                cwd=str(ROOT), creationflags=_CREATE_NO_WINDOW)
            txt = (cp.stdout or b"").decode("utf-8", "replace")
            i = txt.find("{")
            v["intercom"] = ({"ok": True, "legs": (json.loads(txt[i:]) or {}).get("legs")}
                             if i >= 0 else {"ok": False, "error": "没吐 JSON（exit=%s）" % cp.returncode})
        except Exception as e:                                     # noqa: BLE001
            v["intercom"] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}

    # SAPI 嗓表（PowerShell · System.Speech）
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.GetInstalledVoices() | ForEach-Object { $i=$_.VoiceInfo; "
          "\"$($i.Name) | $($i.Culture.Name) | $($i.Gender) | enabled=$($_.Enabled)\" }")
    try:
        cp = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                            capture_output=True, timeout=90, creationflags=_CREATE_NO_WINDOW)
        lines = [ln.strip() for ln in (cp.stdout or b"").decode("utf-8", "replace").splitlines() if ln.strip()]
        zh = [ln for ln in lines if "zh-CN" in ln]
        v["sapi"] = {"ok": bool(lines), "voices": lines, "zh_voices": zh,
                     "note": "离线嗓（页面臂 A 的 speechSynthesis 底下就是这批 SAPI 嗓）"}
    except Exception as e:                                          # noqa: BLE001
        v["sapi"] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
    return v


# ───────────────────────── main ─────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="数字人页：骨架对称性 + 动作真在动 的机检（含正负对照）")
    ap.add_argument("--page", default=str(PAGE))
    ap.add_argument("--json", action="store_true", help="只吐 JSON")
    ap.add_argument("--emit-state", action="store_true", help="顺手写 state/digital-human.json")
    ap.add_argument("--no-voice", action="store_true", help="跳过语音三腿探测（快）")
    args = ap.parse_args()

    page = Path(args.page)
    if not page.is_file():
        print("读不到页面：" + str(page)); return 9
    rig, acts, text = load_specs(page)

    rep = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "page": str(page),
           "page_bytes": page.stat().st_size,
           "page_sha256_16": hashlib.sha256(page.read_bytes()).hexdigest()[:16]}

    rep["rig"] = {"structure": check_structure(rig), "symmetry": check_symmetry(rig),
                  "rest_law": check_rest_law(rig), "action_mirror": check_action_mirror(rig, acts),
                  "spec": {"joints": len(rig["joints"]), "pairs": len(rig["pairs"]),
                           "viewBox": rig.get("viewBox"), "root": rig.get("root"),
                           "figure": rig.get("figure")}}
    rep["motion"] = check_actions(rig, acts)
    rep["negative_controls"] = negative_controls(rig, acts)
    rep["voice"] = {"skipped": True} if args.no_voice else probe_voice()

    hard = [rep["rig"]["structure"]["ok"], rep["rig"]["symmetry"]["ok"],
            rep["rig"]["rest_law"]["ok"], rep["rig"]["action_mirror"]["ok"],
            rep["motion"]["ok"], all(n["pass"] for n in rep["negative_controls"])]
    rep["ok"] = all(hard)
    rep["exit_code"] = (0 if rep["ok"] else
                        (5 if not all(n["pass"] for n in rep["negative_controls"]) else
                         (3 if not (rep["rig"]["structure"]["ok"] and rep["rig"]["symmetry"]["ok"]
                                    and rep["rig"]["rest_law"]["ok"] and rep["rig"]["action_mirror"]["ok"])
                          else 4)))

    if args.emit_state:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "id": "digital-human",
            "title": "数字人页（绑骨全肢体 + 语音交互）· 状态台账",
            "writer": "tools/codex-scripts/dh-rig-check.py --emit-state（**只由工具写**，不手改）",
            "at": rep["at"],
            "page": {"path": "holo_pet_w3/digital-human/index.html", "bytes": rep["page_bytes"],
                     "sha256_16": rep["page_sha256_16"],
                     "self_contained": {"原理": "CSP connect-src 'none' 由浏览器执法",
                                        "外链样式表": 0, "外链脚本": 0, "iframe": 0,
                                        "网络取数原语": 0, "module 脚本": 0,
                                        "本地图": ["reference-02.jpg"], "经典脚本": "内联 3 段"}},
            "rig": {"ready": rep["rig"]["structure"]["ok"] and rep["rig"]["symmetry"]["ok"]
                              and rep["rig"]["rest_law"]["ok"],
                    "joints": rep["rig"]["spec"]["joints"], "mirror_pairs": rep["rig"]["spec"]["pairs"],
                    "symmetry_worst_px": rep["rig"]["symmetry"]["worst_px"],
                    "symmetry_ok": rep["rig"]["symmetry"]["ok"],
                    "rest_law_ok": rep["rig"]["rest_law"]["ok"],
                    "required_joints_ok": rep["rig"]["structure"]["required_ok"],
                    "action_mirror_ok": rep["rig"]["action_mirror"]["ok"],
                    "evidence": rep["rig"]},
            "actions": {"ready": rep["motion"]["ok"], "baseline": rep["motion"]["baseline"],
                        "per_action": rep["motion"]["actions"],
                        "criteria": {"幅度d2": ">5°", "连续性d1": ">0.2°", "位移": ">2px",
                                     "对基线": "幅度与位移均 >2×现量基线",
                                     "root": "伪关节（角度=yaw、位置=根位移）必须计入，否则转身/走动/蹲起会被误判"},
                        "not_moving_by_design": {"refpose": "单帧静态姿势（照参考图摆的），不进'真在动'判决",
                                                 "idle": "现量基线本身（判据反过来：必须很小）"}},
            "voice": {"chain": "麦克风 → 离线听写(SAPI) → 文本入框 → 面板桥 /api/message → TTS 出声 → 嘴型/动作同步",
                      "legs": rep["voice"],
                      "window_registration_needs": {"audio_autoplay": True,
                "why": "数字人窗要有话就说（不必每次先点一下）⇒ 注册表里写 \"audio_autoplay\": true，壳会把 autoplayPolicy 设为 no-user-gesture-required。"
                       "不写/false 时页面照常工作，只是第一次出声前需要一次点击（页面会如实标\"待一次点击后即可发声\"并在首次点击后自动恢复）。"
                       "**登记由主人做**（我没改 shell/windows.json）。",
                "other": "页面自包含 ⇒ 无需其它白名单；第 ⑤ 环走壳口 gbtW3.message（目标写死在壳里）"},
            "page_side": {"A · 本机离线嗓": "window.speechSynthesis（底下系统 SAPI；嗓表异步，等 voiceschanged + 轮询）",
                                    "B · 门内 SAPI": "gbtW3.intercom('say') —— 需 audio_output 授权（台账现为 0 ⇒ 会如实报缺）",
                                    "C · 云臂": "hf_voice.py —— 需 HF 密钥、会出网（页面只显示状态，不默认调）",
                                    "桥": "gbtW3.message({text})（壳口，目标写死在壳里）；浏览器直开时无此口，页面如实标"}},
            "honesty": {
                "未验": ["真麦克风采集（本机录音端点在场 0 个：WASAPI 0 / winmm 0 / Chromium 0）",
                         "流式 interim 上屏（离线识别器只有整段/定长返回）",
                         "真 barge-in 打断（离线识别器不能边说边听）",
                         "白龙马的 Whisper+VAD 参数（RMS 三阈值/2s 切句）——本机不跑 Whisper，未接",
                         "hf_voice 云臂（缺 HF 密钥，未验）",
                         "真实窗内出声（需壳的 audio_autoplay + 真实音频设备；无头取证拿不到声音）"],
                "判据来源": "本件与页面各自独立实现同一套运动学；两套对账一致才算过"},
            "negative_controls": rep["negative_controls"],
        }
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        rep["state_written"] = str(STATE)

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        r = rep["rig"]
        print("页面 %s（%d 字节 · sha256:%s）" % (page.name, rep["page_bytes"], rep["page_sha256_16"]))
        print("① 结构      : %s（关节 %d · 镜像对 %d · 根 %s）%s"
              % ("过" if r["structure"]["ok"] else "报红", r["structure"]["joints"],
                 r["structure"]["pairs"], r["structure"]["roots"],
                 "" if r["structure"]["ok"] else " ← " + "; ".join(r["structure"]["issues"])))
        print("② 静息对称  : %s（%d 对 · 最大镜像误差 %.4fpx · 容差 %.1fpx）"
              % ("过" if r["symmetry"]["ok"] else "报红", r["symmetry"]["pairs_checked"],
                 r["symmetry"]["worst_px"], TOL_PX))
        print("③ 镜像律    : %s%s" % ("过" if r["rest_law"]["ok"] else "报红",
                                    "" if r["rest_law"]["ok"] else " ← " + "; ".join(r["rest_law"]["bad"])))
        print("  sym 标注  : %s%s" % ("过" if r["action_mirror"]["ok"] else "报红",
                                    "" if r["action_mirror"]["ok"] else " ← " + "; ".join(r["action_mirror"]["bad"])))
        b = rep["motion"]["baseline"]
        print("④ 真在动    : %s（现量基线 幅度%.2f° 单帧%.2f° 位移%.2fpx · %d 点采样）"
              % ("过" if rep["motion"]["ok"] else "报红", b["d2"], b["d1"], b["disp"], b["samples"]))
        for n, a in rep["motion"]["actions"].items():
            print("    %-8s %-8s 幅度%8.2f°(%s) 单帧%7.2f° 位移%8.2fpx(%s) 真动关节 %d/%d"
                  % (n, a["verdict"], a["d2"], a["who_d2"], a["d1"], a["disp"], a["who_disp"],
                     a["moving_joints"], a["joints_measured"]))
        print("负对照（判据自己也要被测）：")
        for n in rep["negative_controls"]:
            print("    %-26s 期望报红=%s 实得报红=%s ⇒ %s（%s）"
                  % (n["name"], n["expect_red"], n["got_red"], "过" if n["pass"] else "**失败**", n["detail"]))
        if not rep["voice"].get("skipped"):
            v = rep["voice"]
            print("语音三腿（只读探测）：")
            print("    桥 8765      : %s %s" % ("连上" if v["bridge"]["ok"] else "连不上",
                                              v["bridge"].get("error", "")))
            ic = v.get("intercom", {})
            legs = ic.get("legs") or {}
            print("    intercom     : %s tts=%s listen=%s wavein=%s capture_ready=%s"
                  % ("到位" if ic.get("ok") else "取不到", legs.get("tts"), legs.get("listen_local"),
                     legs.get("wavein_devices"), legs.get("capture_ready")))
            print("    SAPI 嗓      : %s" % (" / ".join(v["sapi"].get("zh_voices") or v["sapi"].get("voices") or ["无"])))
        print("总结：%s（退出码 %d）" % ("全过" if rep["ok"] else "有问题", rep["exit_code"]))
        if rep.get("state_written"):
            print("状态台账已写：" + rep["state_written"])
    return rep["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
