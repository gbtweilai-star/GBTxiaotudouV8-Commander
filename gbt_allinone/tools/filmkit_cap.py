# gbt-capability: filmkit
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""filmkit 柔性影片产线能力（清单制装配 · 任意段加减重制）。

岗位：短片/短剧/AI 电影线的**装配层**——一切以 `manifest.json` 为唯一真相，
场（音频+3 镜 prompt）与镜（图+运镜）都可单独重生成、跳过、插入、摘除，重装配随时可跑。

边界（与 `tools/filmkit.py` 的 CLI 同一套规矩）：
  * `status` / `plan` **只读直连**（不生成、不渲染、不写盘）；
  * 写 op（`gen` / `seg` / `build` / `add` / `rm`）过 **`filesystem_write`** 门
    （闸挂处理器层，不碰 `security/policy.py`）——它们会生图（出网）、起 ffmpeg、落盘；
  * 写 op 的人读输出被**捕获进 `log` 字段** —— `run_task` 的返回是 JSON 契约，
    人读行不许混进 stdout（`tentacle_bind` 就是这么被打挂过一次，2026-09-26 修）。
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
_FK_PATH = ROOT / "tools" / "filmkit.py"
READ_OPS = ("status", "plan")
WRITE_OPS = ("gen", "seg", "build", "add", "rm")
_MAX_LOG = 4000


def _fk():
    spec = importlib.util.spec_from_file_location("filmkit", _FK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifests() -> list[str]:
    d = ROOT / "projects" / "movie" / "产线"
    if not d.is_dir():
        return []
    return sorted(p.relative_to(ROOT).as_posix() for p in d.glob("manifest*.json"))


def _gate(what: str) -> dict | None:
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    g = auth_gate.check_and_consume("filesystem_write", detail=f"filmkit:{what}"[:60])
    if g.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": g.get("error"), "how_to_grant": g.get("how_to_grant")}


def plan(manifest: str = "") -> dict:
    """只读状态表（**返回数据，不打印**）：场/镜进度 + 成片形态。"""
    mfs = _manifests()
    if not manifest:
        if not mfs:
            return {"ok": False, "error": "产线目录下没有 manifest*.json"}
        manifest = mfs[0]
    mp = ROOT / manifest
    if not mp.is_file():
        return {"ok": False, "error": f"清单不存在：{manifest}", "manifests": mfs}
    fk = _fk()
    m = fk.load(mp)
    rows = []
    for sc in m["scenes"]:
        imgs = sum(1 for s in sc["shots"]
                   if (p := fk.img_path(m, sc, s)).is_file() and p.stat().st_size > 8000)
        segs = sum(1 for s in sc["shots"] if fk.seg_path(m, s["id"]).is_file())
        aud = fk.scene_audio(m, sc)
        rows.append({"id": sc["id"], "title": sc.get("title", ""),
                     "shots": len(sc["shots"]), "images": imgs, "segs": segs,
                     "audio": (f"{fk.dur(aud):.1f}s" if aud else None),
                     "ready": bool(imgs == len(sc["shots"]) and segs == len(sc["shots"]) and aud)})
    out = ROOT / m["out_dir"] / m.get("output", "film.mp4")
    return {"ok": True, "manifest": manifest, "title": m.get("title", ""),
            "scenes_total": len(rows), "ready_scenes": sum(1 for r in rows if r["ready"]),
            "scenes": rows,
            "built": (f"{round(out.stat().st_size / 1048576, 1)}MB" if out.is_file() else None),
            "output": str(out),
            "口径": "只读读数（不生成/不渲染/不写盘）"}


def run(op: str = "status", manifest: str = "", **kw) -> dict:
    op = (op or "status").lower()
    if op == "status":
        return {"ok": _FK_PATH.is_file(), "op": "status", "kind": "filmkit",
                "impl": str(_FK_PATH), "read_ops": list(READ_OPS),
                "write_ops": list(WRITE_OPS), "manifests": _manifests(),
                "口径": "status/plan 只读免门；gen/seg/build/add/rm 过 filesystem_write 门（生图/渲染/落盘）"}
    if op == "plan":
        return plan(manifest)
    if op not in WRITE_OPS:
        return {"ok": False, "error": f"未知 op:{op}（{'/'.join(READ_OPS + WRITE_OPS)}）",
                "fail_closed": True}
    deny = _gate(op)
    if deny:
        return deny
    mfs = _manifests()
    if not manifest:
        if not mfs:
            return {"ok": False, "error": "产线目录下没有 manifest*.json"}
        manifest = mfs[0]
    mp = ROOT / manifest
    if not mp.is_file():
        return {"ok": False, "error": f"清单不存在：{manifest}", "manifests": mfs}
    fk = _fk()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            if op == "gen":
                code = fk.cmd_gen(mp, only_scene=str(kw.get("scene") or ""),
                                  force=bool(kw.get("force")))
            elif op == "seg":
                code = fk.cmd_seg(mp, only_scene=str(kw.get("scene") or ""))
            elif op == "build":
                skip = kw.get("skip") or []
                only = kw.get("only") or []
                skip = [skip] if isinstance(skip, str) else list(skip)
                only = [only] if isinstance(only, str) else list(only)
                code = fk.cmd_build(mp, skip, only, audio_only=bool(kw.get("audio_only")))
            elif op == "add":
                code = fk.cmd_add(mp, after=str(kw.get("after") or ""),
                                  sid=str(kw.get("id") or ""), title=str(kw.get("title") or ""),
                                  prompt=str(kw.get("prompt") or ""),
                                  audio=str(kw.get("audio") or ""),
                                  move=str(kw.get("move") or ""))
            else:  # rm
                code = fk.cmd_rm(mp, sid=str(kw.get("scene") or kw.get("id") or ""))
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "op": op, "manifest": manifest,
                "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "log": buf.getvalue()[-_MAX_LOG:]}
    return {"ok": code == 0, "op": op, "exit": code, "manifest": manifest,
            "log": buf.getvalue()[-_MAX_LOG:],
            "口径": "写 op 已过 filesystem_write 门；人读输出在 log 字段"}
