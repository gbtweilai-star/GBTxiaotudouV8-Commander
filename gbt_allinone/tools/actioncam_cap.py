# gbt-capability: actioncam
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""actioncam · 动作镜头控制系统（拍子表制 · 触手可调）。

岗位：动作戏的**镜头语法层**——把"精确动作镜头设计 / 画质参数 / 机位角度 /
用户视角冲击 / 时机把控"做成**逐拍可操控**的执行器。

边界（与 `tools/actioncam.py` 的 CLI 同一套规矩）：
  * `plan` / `status` **只读直连**（不生成、不渲染、不落盘）；
  * 写 op（`gen` / `seg` / `build` / `add` / `rm`）过 **`filesystem_write`** 门
    （闸挂处理器层，不碰 `security/policy.py`）——它们会生图（出网）、起 ffmpeg、落盘；
  * 写 op 的人读输出被**捕获进 `log` 字段** —— JSON 契约不许被人读行污染。

拍子表（beat sheet）是唯一真相：每一拍 = `move`（10 种动作运镜）+ `angle`
（仰/俯/平/荷兰角）+ `dur`（时长=时机）+ `prompt`（英文，动作构图）+ `seed`（锁定）。
"""
from __future__ import annotations
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])

import contextlib
import importlib.util
import io
from pathlib import Path

ROOT = Path(_GBT_ROOT)
_AC_PATH = ROOT / "tools" / "actioncam.py"
READ_OPS = ("plan", "status", "qc")
WRITE_OPS = ("gen", "seg", "build", "add", "rm")
_MAX_LOG = 4000


def _ac():
    spec = importlib.util.spec_from_file_location("actioncam", _AC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifests() -> list[str]:
    d = ROOT / "projects" / "movie" / "产线"
    if not d.is_dir():
        return []
    return sorted(p.relative_to(ROOT).as_posix() for p in d.glob("manifest-actioncam*.json"))


def _gate(what: str) -> dict | None:
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    g = auth_gate.check_and_consume("filesystem_write", detail=f"actioncam:{what}"[:60])
    if g.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": g.get("error"), "how_to_grant": g.get("how_to_grant")}


def status(**_kw) -> dict:
    return {"ok": _AC_PATH.is_file(), "op": "status", "kind": "actioncam",
            "impl": str(_AC_PATH), "read_ops": list(READ_OPS),
            "write_ops": list(WRITE_OPS), "manifests": _manifests(),
            "moves": "pov_bob/whip_lr/whip_rl/crash_zoom/dolly_in/push_out/arc_lr/shake/impact_hold",
            "angles": "eye/low/high/dutch", "quality": "hd/fhd/cinema",
            "口径": "plan/status 只读免门；gen/seg/build/add/rm 过 filesystem_write 门（生图出网/ffmpeg/落盘）"}


def plan(manifest: str = "", verbose: bool = False) -> dict:
    """拍子表读数（**返回数据，不打印**）：每拍的运镜/角度/时长/就绪态。"""
    mfs = _manifests()
    if not manifest:
        if not mfs:
            return {"ok": False, "error": "产线目录下没有 manifest-actioncam*.json"}
        manifest = mfs[0]
    mp = ROOT / manifest
    if not mp.is_file():
        return {"ok": False, "error": f"拍子表不存在：{manifest}", "manifests": mfs}
    ac = _ac()
    m = ac.load(mp)
    rows = []
    for b in m["beats"]:
        img = ac.beat_img(m, b)
        seg = ac.beat_seg(m, b)
        rows.append({"id": b["id"], "move": b.get("move"), "angle": b.get("angle"),
                     "dur": b.get("dur"),
                     "image": bool(img.is_file() and img.stat().st_size > 8000),
                     "segment": bool(seg.is_file() and seg.stat().st_size > 0)})
    out = ROOT / m["out_dir"] / m.get("output", "actioncam.mp4")
    total = sum(float(r["dur"]) for r in rows)
    return {"ok": True, "manifest": manifest, "title": m.get("title", ""),
            "quality": m.get("quality", "hd"), "beats": rows,
            "beats_total": len(rows), "seconds": round(total, 2),
            "images_ready": sum(1 for r in rows if r["image"]),
            "segs_ready": sum(1 for r in rows if r["segment"]),
            "built": (f"{round(out.stat().st_size / 1048576, 1)}MB" if out.is_file() else None),
            "output": str(out),
            "口径": "只读读数（不生成/不渲染/不写盘）"}


def run(op: str = "plan", manifest: str = "", **kw) -> dict:
    op = (op or "plan").lower()
    if op == "status":
        return status(**kw)
    if op == "plan":
        return plan(manifest)
    if op == "qc":
        # 生产审计（总监令工作流第 1 步机械化）：黑帧/卡帧/亮度读数，只读成片 + 追加 QC 台账
        mfs = _manifests()
        mf = str(manifest or (mfs[0] if mfs else ""))
        mp = ROOT / mf if mf else None
        if mp is None or not mp.is_file():
            return {"ok": False, "error": "qc 需要 manifest（找不到拍子表）", "manifests": mfs}
        ac = _ac()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = ac.cmd_qc(mp, out_name=str(kw.get("film") or ""))
        return {"ok": code == 0, "op": "qc", "exit": code, "manifest": mf,
                "log": buf.getvalue()[-_MAX_LOG:], "verdict": "通过" if code == 0 else "不通过",
                "口径": "黑帧段=0 且 卡帧段=0 才算通过；QC 台账 state/actioncam_qc.jsonl"}
    if op not in WRITE_OPS:
        return {"ok": False, "error": f"未知 op:{op}（{'/'.join(READ_OPS + WRITE_OPS)}）",
                "fail_closed": True}
    deny = _gate(op)
    if deny:
        return deny
    mfs = _manifests()
    if not manifest:
        if not mfs:
            return {"ok": False, "error": "产线目录下没有 manifest-actioncam*.json"}
        manifest = mfs[0]
    mp = ROOT / manifest
    if not mp.is_file():
        return {"ok": False, "error": f"拍子表不存在：{manifest}", "manifests": mfs}
    ac = _ac()
    buf = io.StringIO()
    code = 1
    try:
        with contextlib.redirect_stdout(buf):
            if op == "gen":
                code = ac.cmd_gen(mp, only=str(kw.get("beat") or ""),
                                  force=bool(kw.get("force")))
            elif op == "seg":
                code = ac.cmd_seg(mp, only=str(kw.get("beat") or ""))
            elif op == "build":
                skip = kw.get("skip") or []
                only = kw.get("only") or []
                skip = [skip] if isinstance(skip, str) else list(skip)
                only = [only] if isinstance(only, str) else list(only)
                code = ac.cmd_build(mp, skip, only)
            elif op == "add":
                code = ac.cmd_add(mp, after=str(kw.get("after") or ""),
                                  bid=str(kw.get("id") or ""),
                                  move=str(kw.get("move") or "dolly_in"),
                                  angle=str(kw.get("angle") or "eye"),
                                  dur=float(kw.get("dur") or 0.8),
                                  prompt=str(kw.get("prompt") or ""))
            else:  # rm
                code = ac.cmd_rm(mp, bid=str(kw.get("beat") or ""))
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "op": op, "manifest": manifest,
                "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "log": buf.getvalue()[-_MAX_LOG:]}
    return {"ok": code == 0, "op": op, "exit": code, "manifest": manifest,
            "log": buf.getvalue()[-_MAX_LOG:],
            "口径": "写 op 已过 filesystem_write 门；人读输出在 log 字段"}
