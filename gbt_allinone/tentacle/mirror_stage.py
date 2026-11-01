# gbt-capability: mirror_stage
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""mirror_stage — 镜像工作空间：**生产永不被试验污染；跑通后整页原子替换**。

主人 2026-11-01 的口径（原话转述）：
  · 没跑通的代码严禁进入生产面板；
  · 生产面板要改，就在**镜像多维度空间**里各种假设/猜想/多维度试，直到跑通；
  · 跑通后用**原子替换法**整页替换生产代码，而不是一直污染生产；
  · 镜像空间同时是远程协助/千里语音的通道（远程部分另位，不在本件假装）。

本件只做前三条，且**每一步都能验**：
  create  —— 把生产目标文件复制进 state/mirror/stage/<id>/（生产只读）
  write   —— 只在镜像里写候选（多候选就是多个 stage id）
  verify  —— 在镜像里跑外部验证器（cmd + exit_code + evidence），失败绝不 promote
  promote —— 只有 verify 通过且 confirm=true 才做**整文件 os.replace 原子替换**（先备份）
  rollback—— 从备份原子还原
  status/list/where

诚实边界：
  · 本件不做远程桌面/隧道/语音；那是独立能力，不能混在这里假装已通；
  · verify 在镜像目录里跑命令（有副作用也只在镜像）；promote 只替换 create 时登记的目标；
  · 没有验证证据、没有 confirm、目标越界（repo 外）一律拒。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE = ROOT / "state" / "mirror" / "stage"
DEFAULT_BACKUP = ROOT / "state" / "mirror" / "backups"

STATUS = {
    "cap": "mirror_stage", "tier": "native", "domain": "system",
    "ops": ["status", "create", "list", "write", "verify", "promote", "rollback", "where"],
    "default_stage": str(DEFAULT_STAGE), "default_backup": str(DEFAULT_BACKUP),
    "rule": "生产只读 → 镜像多候选 → 外部验证 → 原子整页替换；没验过不进生产",
    "not_implemented": ["远程桌面/隧道/语音（另位能力，不在本件）", "自动多候选评分（需人/模型选）"],
}


def _repo(payload) -> Path:
    return Path(payload.get("repo") or ROOT).expanduser().resolve()


def _stage_root(payload, repo: Path) -> Path:
    return Path(payload.get("stage_root") or (repo / "state" / "mirror" / "stage")).resolve()


def _backup_root(payload, repo: Path) -> Path:
    return Path(payload.get("backup_root") or (repo / "state" / "mirror" / "backups")).resolve()


def _safe_rel(rel: str) -> str:
    rel = str(rel or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in Path(rel).parts:
        raise ValueError("非法相对路径：%s" % rel)
    return rel


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _meta(stage: Path) -> dict:
    try:
        return json.loads((stage / "stage.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save(stage: Path, meta: dict):
    (stage / "stage.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def _create(payload):
    repo = _repo(payload)
    targets = payload.get("targets") or []
    if not targets:
        return {"ok": False, "status": "needs_input", "error": "targets 必填：要镜像的生产文件列表"}
    sid = str(payload.get("id") or ("stage-" + time.strftime("%m%d-%H%M%S") + "-" + hashlib.sha1(str(targets).encode()).hexdigest()[:4]))
    stage = _stage_root(payload, repo) / sid
    if stage.exists() and not payload.get("force"):
        return {"ok": False, "status": "exists", "error": "stage 已存在；换 id 或 force=true", "stage": str(stage)}
    copied = []
    try:
        for rel in targets:
            r = _safe_rel(rel)
            src = (repo / r).resolve()
            if not src.is_file():
                return {"ok": False, "status": "missing_target", "error": "生产目标不存在：%s" % r}
            dst = stage / "work" / r
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append({"path": r, "src_sha256": _sha(src), "staged_sha256": _sha(dst)})
        meta = {"id": sid, "repo": str(repo), "targets": [c["path"] for c in copied],
                "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "status": "staged",
                "verify": None, "promoted": []}
        _save(stage, meta)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "failed", "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    return {"ok": True, "status": "staged", "id": sid, "stage": str(stage), "targets": copied,
            "note": "生产文件只被复制，未被改动；候选只写 stage/work/"}


def _write(payload):
    repo = _repo(payload)
    sid = str(payload.get("id") or payload.get("stage") or "")
    stage = _stage_root(payload, repo) / sid
    meta = _meta(stage)
    if not meta:
        return {"ok": False, "status": "not_found", "error": "stage 不存在或无 stage.json"}
    rel = _safe_rel(payload.get("path") or "")
    if rel not in meta.get("targets", []):
        return {"ok": False, "status": "not_declared", "error": "只能写 create 时登记的 target：%s" % rel}
    dst = stage / "work" / rel
    try:
        if payload.get("content") is not None:
            dst.write_text(str(payload["content"]), encoding="utf-8")
        elif payload.get("src"):
            src = Path(payload["src"]).resolve()
            dst.write_bytes(src.read_bytes())
        else:
            return {"ok": False, "status": "needs_input", "error": "给 content 或 src"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "failed", "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    meta["status"] = "edited"
    _save(stage, meta)
    return {"ok": True, "status": "written", "id": sid, "path": rel, "sha256": _sha(dst),
            "note": "只写镜像；生产未动"}


def _verify(payload):
    repo = _repo(payload)
    sid = str(payload.get("id") or payload.get("stage") or "")
    stage = _stage_root(payload, repo) / sid
    meta = _meta(stage)
    if not meta:
        return {"ok": False, "status": "not_found", "error": "stage 不存在"}
    cmd = str(payload.get("cmd") or "").strip()
    if not cmd:
        return {"ok": False, "status": "needs_input", "error": "给 cmd（在镜像 work/ 目录里跑的外部验证器）"}
    work = stage / "work"
    timeout = int(payload.get("timeout") or 600)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, shell=True, cwd=str(work), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "id": sid, "cmd": cmd}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "failed", "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    ev = {"cmd": cmd, "exit_code": r.returncode, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
          "stdout_tail": (r.stdout or "")[-600:], "stderr_tail": (r.stderr or "")[-600:],
          "elapsed_s": round(time.time() - t0, 2)}
    meta["verify"] = ev
    meta["status"] = "verified" if r.returncode == 0 else "verify_failed"
    _save(stage, meta)
    return {"ok": r.returncode == 0, "status": meta["status"], "id": sid, "verify": ev,
            "note": "验证在镜像 work/ 里跑；失败绝不 promote"}


def _promote(payload):
    if payload.get("confirm") is not True:
        return {"ok": False, "status": "needs_confirm", "error": "promote 必须 confirm=true（生产原子替换）"}
    repo = _repo(payload)
    sid = str(payload.get("id") or payload.get("stage") or "")
    stage = _stage_root(payload, repo) / sid
    meta = _meta(stage)
    if not meta:
        return {"ok": False, "status": "not_found", "error": "stage 不存在"}
    v = meta.get("verify") or {}
    if not v or int(v.get("exit_code", 1)) != 0:
        return {"ok": False, "status": "not_verified", "error": "镜像没跑通（verify.exit_code≠0/无证据）⇒ 严禁进生产",
                "verify": v}
    targets = meta.get("targets") or []
    if payload.get("only") is not None:
        only = set(str(x) for x in payload["only"])
        targets = [t for t in targets if t in only]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = _backup_root(payload, repo) / (stamp + "-" + sid)
    replaced = []
    try:
        for rel in targets:
            src = stage / "work" / rel
            dst = (repo / rel).resolve()
            if not src.is_file():
                return {"ok": False, "status": "missing_staged", "error": "镜像缺文件：%s" % rel}
            if not str(dst).startswith(str(repo)):
                return {"ok": False, "status": "out_of_repo", "error": "目标越界：%s" % dst}
            bdst = backup / rel
            bdst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_file():
                shutil.copy2(dst, bdst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".mirror-tmp-%s" % stamp)
            shutil.copy2(src, tmp)
            os.replace(str(tmp), str(dst))  # 同卷原子替换
            replaced.append({"path": rel, "backup": str(bdst), "sha256": _sha(dst)})
        meta["status"] = "promoted"
        meta["promoted"] = replaced
        meta["backup"] = str(backup)
        _save(stage, meta)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "failed", "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                "replaced": replaced, "backup": str(backup)}
    return {"ok": True, "status": "promoted", "id": sid, "replaced": replaced, "backup": str(backup),
            "note": "整文件原子替换；生产旧版已备份，可 rollback"}


def _rollback(payload):
    repo = _repo(payload)
    sid = str(payload.get("id") or payload.get("stage") or "")
    stage = _stage_root(payload, repo) / sid
    meta = _meta(stage)
    if not meta:
        return {"ok": False, "status": "not_found"}
    backup = Path(meta.get("backup") or payload.get("backup") or "")
    if not backup or not backup.is_dir():
        return {"ok": False, "status": "no_backup", "error": "没有备份目录"}
    restored = []
    for item in meta.get("promoted") or []:
        rel = item.get("path")
        b = backup / rel
        dst = (repo / rel).resolve()
        if b.is_file():
            tmp = dst.with_name(dst.name + ".mirror-rb-%s" % time.strftime("%H%M%S"))
            shutil.copy2(b, tmp)
            os.replace(str(tmp), str(dst))
            restored.append({"path": rel, "sha256": _sha(dst)})
    meta["status"] = "rolled_back"
    _save(stage, meta)
    return {"ok": True, "status": "rolled_back", "restored": restored, "backup": str(backup)}


def _list(payload):
    repo = _repo(payload)
    root = _stage_root(payload, repo)
    out = []
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if d.is_dir() and (d / "stage.json").is_file():
                m = _meta(d)
                out.append({"id": m.get("id", d.name), "status": m.get("status"),
                            "targets": m.get("targets"), "verify": (m.get("verify") or {}).get("exit_code")})
    return {"ok": True, "stages": out, "count": len(out), "root": str(root)}


def run(op="status", **kw):
    op = str(op or "status").strip().lower()
    if op == "status":
        repo = _repo(kw)
        root = _stage_root(kw, repo)
        n = len(_list(kw)["stages"])
        return {"ok": True, "op": "status", **STATUS, "repo": str(repo), "stages": n}
    if op == "where":
        return {"ok": True, "op": "where", **STATUS, "module": "gbt_allinone/tentacle/mirror_stage.py",
                "example": "create -> write -> verify(cmd) -> promote(confirm=true)"}
    if op == "create":
        return _create(kw)
    if op == "write":
        return _write(kw)
    if op == "verify":
        return _verify(kw)
    if op == "promote":
        return _promote(kw)
    if op == "rollback":
        return _rollback(kw)
    if op == "list":
        return _list(kw)
    return {"ok": False, "op": op, "status": "unknown_op", "error": "未知 op：%s" % op,
            "available": STATUS["ops"], "fail_closed": True}
