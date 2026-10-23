# gbt-capability: rig_audit / rig_fix / anim_audit / anim_fix / dh_asset_gate
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""数字人**建模绑骨**能力位群（五位一套）—— 把已经在役、真跑通过的五件判据工具接上唯一门。

## 为什么是"包装"而不是"重写"
这五件不是新写的：`tools/codex-scripts/` 里那五支脚本是 2026-10-19 那一轮**真栽了三次**之后
才磨出来的量具（腿折在胯上 → 髋骨归位 → 手举过头顶 → 闭环解算按下来 → 八条闸全绿）。
它们的判据、阈值、自检全部写在脚本里、有实测留痕。**本文件一个字都不重写这些逻辑**，
只做三件事：① 起进程调那支脚本；② 把它的 JSON 回执原样带出来；③ 写面挂票。

## 五位各自管什么（分工不许混）
  · `dh_asset_gate` —— **一条命令验完**：单网格单蒙皮 / 无杂物球 / 身高 1.720±0.02（文件空间）/
    无死顶点 / 髋骨没被扭 / 手臂垂放 / 循环闭合 / 派生件对账。**纯读、免费**。
  · `anim_audit` —— 读 GLB 的 animation 通道，把每根骨"首帧 vs 静止姿势"的夹角排出来
    （当初就是它量出髋骨 177° 被扭）。**纯读、免费**。
  · `rig_audit` —— 拿本机 Blender 做 **DCC 级**体检（骨架层级/权重和/未绑顶点/非归一化/零长骨/
    左右镜像/包围盒/缩放是否已应用）。**纯体检，但会写一份派生的 `.js` 给页吃 ⇒ 要票**。
  · `rig_fix` —— 自动定轴 + 补权重 + 归一化 + 去杂物 + 转台照，出**六条硬判据**。写 `outputs/rig-fix/` ⇒ 要票。
  · `anim_fix` —— GLB 层面动手术：把点名的骨头轨道**归位/写成量出来的姿势**（髋骨、手臂），
    带**六条自检**（命中通道 / 采样形状 / 四元数模长 / 写回复查 / 只改这些字节 / 网格蒙皮没动），
    任一条不过就**不写盘**。写 dst ⇒ 要票；`dry=true` 免票（只自检不落盘）。

## 门（处理器层挂闸，不碰 policy.py）
  读面免门：任一 op=status；`anim_audit run`；`dh_asset_gate run`；`anim_fix dry=true`
  写面要票：`rig_audit run`（写 .js）· `rig_fix run` · `anim_fix dry=false`

## 在役资产与三段流水线（照 `rig-fix.py` 的文档口径，顺序不许换）
  ① rig_fix → ② anim_fix（髋骨归位 + 手臂垂放）→ ③ dh_asset_gate 八条全绿
  在役件：`holo_pet_w3/voice-theater/assets/dh-v2-rigged.glb`

ops：`status` / `run`（rig_audit 另有 `check`；anim_fix 另有 `plan`）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

WS = Path(__file__).resolve().parents[2]
SCRIPTS = WS / "tools" / "codex-scripts"
IN_USE = WS / "holo_pet_w3" / "voice-theater" / "assets" / "dh-v2-rigged.glb"
RIG_FIX_OUT = WS / "outputs" / "rig-fix"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe")
_MAX_OUT = 6000

ART = {
    "rig_audit": {"script": "rig-audit.py", "needs_blender": True,
                  "what": "Blender DCC 级绑骨体检（骨架层级/权重/未绑/镜像/包围盒）",
                  "writes": "派生 .js（页面用 <script> 吃）"},
    "rig_fix": {"script": "rig-fix.py", "needs_blender": True,
                "what": "自动定轴 + 补权重 + 归一化 + 去杂物 + 转台照，六条硬判据",
                "writes": "outputs/rig-fix/*.glb + 转台 PNG + report.json"},
    "anim_audit": {"script": "anim-audit.py", "needs_blender": False,
                   "what": "逐骨量「首帧 vs 静止姿势」夹角（找出被动画扭坏的骨头）",
                   "writes": "无（纯读）"},
    "anim_fix": {"script": "anim-hipfix.py", "needs_blender": False,
                 "what": "GLB 层面把点名骨头的旋转轨道归位/写成量出来的姿势（六条自检）",
                 "writes": "dst .glb（dry=true 时不写）"},
    "dh_asset_gate": {"script": "dh-asset-gate.py", "needs_blender": False,
                      "what": "八条资产闸（单网格单蒙皮/无杂物/身高/死顶点/髋/臂/循环/派生件对账）",
                      "writes": "无（纯读）"},
}
READ_OPS = {"status"}
KINDS = tuple(ART)


# ── 公共件 ───────────────────────────────────────────────────────────────────
def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(WS)).replace("\\", "/")
    except ValueError:
        return str(p)


def _glb(raw=None) -> tuple[Path | None, str]:
    """GLB 路径只许指到仓内（防 ../ 逃逸）；默认在役件。"""
    p = Path(str(raw).strip()) if raw and str(raw).strip() else IN_USE
    if not p.is_absolute():
        p = (WS / p)
    try:
        p = p.resolve()
        p.relative_to(WS)
    except ValueError:
        return None, "GLB 必须在仓内（拒绝仓外路径）：%s" % p
    if not p.is_file():
        return None, "GLB 不在：%s" % p
    return p, ""


def _run(argv: list, timeout: int) -> dict:
    """起脚本、原话透传（P19：失败路径不许只剩 ok=False）。

    🔴 全量 stdout 单独留一份 `full`：**解析 JSON 一律用 full**，展示才用截断的 out/err。
       为什么（2026-10-19 实栽一次）：先写成 `stdout[-6000:]` 再解析 ⇒ 长 JSON 被从**末尾**截掉，
       `json.loads` 必失败 ⇒ 回执变成 `ok:false, animations:[]`，看着像"量具没数据"，
       其实是**我自己的包装器把 JSON 切了**（P1 判据错尺的变种：拿截断件当读数）。
    """
    try:
        p = subprocess.run([sys.executable] + [str(a) for a in argv], cwd=str(WS),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=int(timeout))
        full = p.stdout or ""
        return {"ok": p.returncode == 0, "exit": p.returncode, "full": full,
                "out": full[-_MAX_OUT:], "err": (p.stderr or "")[-_MAX_OUT:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit": None, "fail_closed": True, "full": "",
                "error": "超时（>%ss）：%s" % (timeout, " ".join(str(a) for a in argv))}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "exit": None, "fail_closed": True, "full": "",
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


def _json_tail(text: str):
    """人读行后面跟 JSON 的老写法（dh-asset-gate）：从**最后一个行首 `{`** 起解析。"""
    if not text:
        return None
    idx = text.rfind("\n{\n")
    blob = text[idx + 1:] if idx >= 0 else text
    try:
        return json.loads(blob)
    except Exception:                                          # noqa: BLE001
        return None


def _gate(what: str) -> dict | None:
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    got = auth_gate.check_and_consume("filesystem_write", detail=str(what)[:60])
    if got.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": got.get("error"), "how_to_grant": got.get("how_to_grant"),
            "note": "这一位会写盘（派生件/glb/转台照）—— 写面必须人工授权"}


def _script(kind: str) -> tuple[Path | None, str]:
    p = SCRIPTS / ART[kind]["script"]
    if not p.is_file():
        return None, "脚本不在：%s" % p
    return p, ""


def status(kind: str = "", **_kw) -> dict:
    kinds = [kind] if kind in ART else list(KINDS)
    rows = []
    for k in kinds:
        s = SCRIPTS / ART[k]["script"]
        rows.append({"kind": k, "脚本": _rel(s), "在位": s.is_file(),
                     "需要 Blender": ART[k]["needs_blender"],
                     "blender": str(BLENDER) if BLENDER.is_file() else "未找到",
                     "写什么": ART[k]["writes"], "管什么": ART[k]["what"]})
    glb_ok = IN_USE.is_file()
    return {"ok": all(r["在位"] for r in rows), "op": "status",
            "在役资产": {"path": _rel(IN_USE), "bytes": IN_USE.stat().st_size if glb_ok else 0,
                         "在位": glb_ok},
            "rows": rows,
            "三段流水线": "① rig_fix → ② anim_fix（髋骨归位+手臂垂放）→ ③ dh_asset_gate 八条全绿",
            "口径": "读面免门；写字那三位过 filesystem_write（处理器层）"}


def where(kind: str) -> dict:
    return {"ok": True, "op": "where", "kind": kind,
            "entry": "py -3.14 tools/codex-scripts/five-dim.py cap %s '{\"op\":\"run\"}'" % kind,
            "脚本": _rel(SCRIPTS / ART[kind]["script"]), "写什么": ART[kind]["writes"],
            "在役资产": _rel(IN_USE)}


# ── rig_audit ────────────────────────────────────────────────────────────────
def rig_audit(op: str = "run", glb=None, out=None, timeout: int = 600, **_kw) -> dict:
    op = str(op or "run").strip().lower()
    if op == "status":
        return status("rig_audit")
    if op == "where":
        return where("rig_audit")
    if op not in ("run", "check"):
        return {"ok": False, "op": op, "error": "未知 op", "available": ["status", "run", "check", "where"]}
    path, why = _glb(glb)
    if not path:
        return {"ok": False, "op": op, "error": why, "fail_closed": True}
    script, why2 = _script("rig_audit")
    if not script:
        return {"ok": False, "op": op, "error": why2}
    if not BLENDER.is_file():
        return {"ok": False, "op": op,
                "error": "Blender 不在：%s（免费本地 DCC；本器不调付费接口）" % BLENDER}
    if op == "run":
        denied = _gate("rig_audit:run")
        if denied:
            return {"op": "run", **denied}
    argv = [script, "--glb", path]
    if op == "check":
        argv.append("--check")
    else:
        argv.append("--json")
        if out:
            argv += ["--out", str(WS / str(out))]
    got = _run(argv, timeout)
    data = _json_tail(got.get("full") or "")
    mirror = None
    if data and isinstance(data.get("mirror_off"), list):
        offs = data["mirror_off"]
        if offs:
            dxs = [abs(float(r.get("dx") or 0)) for r in offs]
            dys = [abs(float(r.get("dy") or 0)) for r in offs]
            dzs = [abs(float(r.get("dz") or 0)) for r in offs]
            mirror = {"对": "%s/%s 严格对称（容差 1e-4）" % (data.get("mirror_ok"), data.get("mirror_pairs")),
                      "最大偏差_场景单位": round(max(dxs + dys + dzs), 5),
                      "分量_max": {"dx": round(max(dxs), 5), "dy": round(max(dys), 5),
                                   "dz": round(max(dzs), 5)},
                      "口径": ("**这是参考值，不是红绿**：该判据要的是「作者按对称手工绑的骨」，"
                               "而 Tripo 这类自动绑骨天然有毫米~厘米级左右抖动（实测在役件 dx≈0.013 场景单位）。"
                               "「有没有绑坏」看 dh_asset_gate 的 ⑤⑥ 与 rig_fix 的六条硬判据，不看这一条。"
                               "改这条阈值必须留痕，不许静默翻。")}
    return {"ok": bool(got.get("ok")) and (data is None or data.get("ok", True)), "op": op,
            "glb": _rel(path), "argv_exit": got.get("exit"), "error": got.get("error"),
            "reads": data, "镜像偏差": mirror,
            "tail": (got.get("err") or "")[-600:] if not got.get("ok") else "",
            "口径": "Blender 导入器会造 42 顶点 Icosphere 显示形状（文件里没有它）—— 量具已剔除并点名"}


# ── rig_fix ──────────────────────────────────────────────────────────────────
def rig_fix(op: str = "run", drop_strays: bool = False, timeout: int = 1300, **_kw) -> dict:
    op = str(op or "run").strip().lower()
    if op == "status":
        return status("rig_fix")
    if op == "where":
        return where("rig_fix")
    if op == "plan":
        src = WS / "projects" / "digital-human" / "out" / "dh-v2-rigged.glb"
        return {"ok": True, "op": "plan", "src": _rel(src), "src_在位": src.is_file(),
                "dst": _rel(RIG_FIX_OUT / "dh-v2-rigged-fixed.glb"),
                "会跑": ["自动定轴（三轴跨度取最大为身高轴）", "补权重", "归一化", "去杂物(可选)",
                         "转台照", "六条硬判据"],
                "六条判据": ["单网格+有蒙皮", "无 42 顶点杂物球", "量具自证换算 0.3~3",
                             "身高 1.720±0.02（文件空间）", "未绑顶点归零", "蒙皮网格被骨架带动"],
                "注意": "本器**不重做动作修正**：出件后必须再跑 anim_fix，否则腿会折、手会举过头顶（2026-10-19 实栽）"}
    if op != "run":
        return {"ok": False, "op": op, "error": "未知 op", "available": ["status", "plan", "run", "where"]}
    script, why = _script("rig_fix")
    if not script:
        return {"ok": False, "op": op, "error": why}
    if not BLENDER.is_file():
        return {"ok": False, "op": op, "error": "Blender 不在：%s" % BLENDER}
    denied = _gate("rig_fix:run")
    if denied:
        return {"op": "run", **denied}
    argv = [script, "--json"] + (["--drop-strays"] if drop_strays else [])
    got = _run(argv, timeout)
    data = _json_tail(got.get("full") or "")
    return {"ok": bool(got.get("ok")) and bool(data and data.get("ok")), "op": "run",
            "argv_exit": got.get("exit"), "error": got.get("error"),
            "checks": (data or {}).get("checks"), "dst": (data or {}).get("dst"),
            "dst_sha16": (data or {}).get("dst_sha16"), "dst_bytes": (data or {}).get("dst_bytes"),
            "why": (data or {}).get("why"), "tail": (got.get("err") or "")[-600:] if not got.get("ok") else "",
            "下一步": "出件后跑 anim_fix（髋骨归位+手臂垂放），再跑 dh_asset_gate 验八条"}


# ── anim_audit ───────────────────────────────────────────────────────────────
def anim_audit(op: str = "run", glb=None, all: bool = False, threshold: float = 30.0,
               timeout: int = 300, **_kw) -> dict:
    op = str(op or "run").strip().lower()
    if op == "status":
        return status("anim_audit")
    if op == "where":
        return where("anim_audit")
    if op != "run":
        return {"ok": False, "op": op, "error": "未知 op", "available": ["status", "run", "where"]}
    path, why = _glb(glb)
    if not path:
        return {"ok": False, "op": op, "error": why, "fail_closed": True}
    script, why2 = _script("anim_audit")
    if not script:
        return {"ok": False, "op": op, "error": why2}
    argv = [script, path, "--json", "--threshold", str(threshold)] + (["--all"] if all else [])
    got = _run(argv, timeout)
    data = _json_tail(got.get("full") or "")
    rows = []
    for anim in ((data or {}).get("animations") or []):
        rows.append({"anim": anim.get("name"), "channels": anim.get("channels"),
                     "over_threshold": anim.get("over_threshold"),
                     "top": [(r.get("bone"), r.get("deg_first")) for r in (anim.get("rows") or [])[:5]]})
    return {"ok": bool(got.get("ok")) and data is not None, "op": "run", "glb": _rel(path),
            "threshold": threshold, "animations": rows, "error": got.get("error"),
            "tail": (got.get("err") or "")[-600:] if not got.get("ok") else ""}


# ── anim_fix ─────────────────────────────────────────────────────────────────
def anim_fix(op: str = "run", src=None, dst=None, bones: str = "LeftUpLeg,RightUpLeg",
             sets=None, dry: bool = False, timeout: int = 300, **_kw) -> dict:
    op = str(op or "run").strip().lower()
    if op == "status":
        return status("anim_fix")
    if op == "where":
        return where("anim_fix")
    if op == "plan":
        return {"ok": True, "op": "plan",
                "用法": "src→dst 改名：两条 positional；--bones 点名骨头；--set NAME=rest 或 NAME=x,y,z,w",
                "默认": {"bones": bones, "dry": dry},
                "髋骨组": "LeftUpLeg,RightUpLeg（归位到静止姿势）",
                "手臂组（量出来的值，不许手搓）": {
                    "LeftArm": "-0.552047,-0.417612,0.306125,0.653553",
                    "RightArm": "-0.571611,0.369986,-0.242467,0.691072",
                    "LeftForeArm": "rest", "RightForeArm": "rest"},
                "六条自检": ["命中 rotation 通道", "采样形状对（float/归一化+VEC4）",
                             "静止四元数模长=1", "写回逐帧复查", "只改这些字节（其余逐一相等）",
                             "网格/蒙皮没被动"]}
    if op != "run":
        return {"ok": False, "op": op, "error": "未知 op", "available": ["status", "plan", "run", "where"]}
    s, why = _glb(src)
    if not s:
        return {"ok": False, "op": op, "error": "src " + why, "fail_closed": True}
    if dst:
        d = Path(str(dst))
        d = d if d.is_absolute() else (WS / d)
        try:
            d = d.resolve()
            d.relative_to(WS)
        except ValueError:
            return {"ok": False, "op": op, "error": "dst 必须在仓内（拒绝仓外路径）：%s" % d}
    else:
        d = RIG_FIX_OUT / (s.stem + "-animfix.glb")
    script, why2 = _script("anim_fix")
    if not script:
        return {"ok": False, "op": op, "error": why2}
    if not dry:
        denied = _gate("anim_fix:run")
        if denied:
            return {"op": "run", "src": _rel(s), "dst": _rel(d), **denied}
    argv = [script, s, d] + (["--bones", str(bones)] if str(bones or "") else ["--bones", ""])
    for spec in (sets or []):
        argv += ["--set", str(spec)]
    if dry:
        argv.append("--dry")
    got = _run(argv, timeout)
    return {"ok": bool(got.get("ok")), "op": "run", "src": _rel(s), "dst": _rel(d), "dry": bool(dry),
            "argv_exit": got.get("exit"), "error": got.get("error"),
            "out": (got.get("out") or "")[-1200:],
            "dst_bytes": d.stat().st_size if (d.is_file() and not dry) else None,
            "下一步": "dry=false 写过盘后，跑 dh_asset_gate 验八条"}


# ── dh_asset_gate ────────────────────────────────────────────────────────────
def dh_asset_gate(op: str = "run", glb=None, timeout: int = 300, **_kw) -> dict:
    op = str(op or "run").strip().lower()
    if op == "status":
        return status("dh_asset_gate")
    if op == "where":
        return where("dh_asset_gate")
    if op != "run":
        return {"ok": False, "op": op, "error": "未知 op", "available": ["status", "run", "where"]}
    path, why = _glb(glb)
    if not path:
        return {"ok": False, "op": op, "error": why, "fail_closed": True}
    script, why2 = _script("dh_asset_gate")
    if not script:
        return {"ok": False, "op": op, "error": why2}
    got = _run([script, "--json", "--glb", path], timeout)
    data = _json_tail(got.get("full") or "")
    rows = (data or {}).get("rows") or []
    return {"ok": bool(got.get("ok")) and bool(data and data.get("pass")), "op": "run",
            "glb": _rel(path), "字节": (data or {}).get("bytes"),
            "八条": [{"名": r.get("name"), "过": r.get("pass"), "读数": r.get("detail")} for r in rows],
            "全绿数": sum(1 for r in rows if r.get("pass")), "总数": len(rows),
            "error": got.get("error"),
            "tail": (got.get("out") or "")[-600:] if not got.get("ok") else ""}


TABLE = {"rig_audit": rig_audit, "rig_fix": rig_fix, "anim_audit": anim_audit,
         "anim_fix": anim_fix, "dh_asset_gate": dh_asset_gate}


def run_op(kind: str, op: str = "status", **kw) -> dict:
    fn = TABLE.get(str(kind))
    if fn is None:
        return {"ok": False, "error": "未知 kind", "available": sorted(TABLE), "fail_closed": True}
    return fn(op, **kw)


if __name__ == "__main__":
    k = sys.argv[1] if len(sys.argv) > 1 else "dh_asset_gate"
    print(json.dumps(run_op(k, sys.argv[2] if len(sys.argv) > 2 else "status"),
                     ensure_ascii=False, indent=1))

