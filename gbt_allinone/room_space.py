# gbt-capability: filesystem, process_execute
"""GBT小土豆V8 · 内置沙盒会议室（room_space）。

定位：
  会议室不是一个外挂服务，也不是第二套视觉总线。它是镜像多维度空间里的
  一个隔离房间：每个房间都有自己的 dimension / reality / timelines /
  passports，复用原有原子写、树指纹、排练命令与视觉帧库。

核心闭环：
  room_create   创建房间（不触碰全局镜像维度）
  room_enter    人和 AI 加入同一房间
  room_shape    在房间维度里写文件、方案和产物
  room_observe  把当前共享视觉帧绑定到房间事件
  room_snapshot 冻结房间时间线
  room_replay   回放房间快照和帧 ID
  room_plan     固化假设 / 架构 / 步骤 / 验收 / 回滚
  room_simulate 静态推演
  room_parity   沙盒与目标环境契约核对
  room_rehearse 在房间维度内跑闭环命令
  room_release  全绿后一次性写入房间现实区 + 护照

边界：
  - 不删除原有能力，不覆盖全局 mirror_space/reality；
  - 不另起 vision_bus，帧仍走现有 vision_watch / vision_bus；
  - 房间现实区是隔离排练现实，生产晋升仍必须显式走全局门禁。
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import sys
import time
from pathlib import Path

from ._paths import STORE_DIR
from . import dimension_naming as DN
from .safe_io import (
    FileLock,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    load_json,
    locked_append_text,
    safe_relative_path,
)

_ROOT = Path(STORE_DIR) / "mirror_space" / "rooms"
_ROOM_ID_RE = re.compile(r"^[^/\\\x00]{1,64}$")

# 入口名**只此一份**（2026-10-21 修：此前 `scan` / `simulate` / `qiankun` 三处各写一遍
# 同样四个字面量，改一处必然漏两处 —— 属本仓根因表 P8「修复件没接上驱动」同族）。
# 判据仍是「必须有入口」，这里只是把「哪些算入口」收敛成一个可被引用的定义。
ENTRY_NAMES = ("index.html", "main.py", "app.py", "start.ps1")
_ROOM_CAPABILITIES = (
    "room_create", "room_enter", "room_shape", "room_scan",
    "room_observe", "room_frame", "room_snapshot", "room_replay",
    "room_plan", "room_simulate", "room_parity", "room_rehearse",
    "room_gate", "room_release", "room_sync", "room_status",
    "room_namespace", "room_registry", "room_resolve",
)


def _namespace_contract(room_id: str) -> dict:
    return DN.namespace(room_id, _ROOM_CAPABILITIES)


def _register_namespace(room_id: str, *, extra_resources=()) -> dict:
    return DN.register(
        room_id,
        capabilities=_ROOM_CAPABILITIES,
        extra_resources=extra_resources,
    )


def _frame_fqn(room_id: str, frame_id) -> str:
    return DN.fqn(room_id, "frame", str(frame_id or ""))


def _resolve_local_ref(room_id: str, value: str, kind: str = "") -> dict:
    """Accept a legacy local id or validate a room-qualified FQN."""
    ref = str(value or "").strip()
    parsed = DN.parse_fqn(ref)
    if not parsed.get("ok"):
        return {"ok": True, "local_name": ref, "fqn": "", "legacy": True}
    expected_dim = DN.dimension_id(room_id)
    if parsed.get("dimension_id") != expected_dim:
        return {
            "ok": False,
            "error": "FQN belongs to another room dimension",
            "expected_dimension_id": expected_dim,
            "actual_dimension_id": parsed.get("dimension_id"),
        }
    if kind and parsed.get("kind") != kind:
        return {
            "ok": False,
            "error": f"FQN kind mismatch: expected {kind}",
            "actual_kind": parsed.get("kind"),
        }
    resolved = DN.resolve(ref)
    if not resolved.get("ok"):
        return {"ok": False, "error": resolved.get("error")}
    return {
        "ok": True,
        "local_name": parsed.get("local_name"),
        "fqn": ref,
        "legacy": False,
        "resolved": resolved,
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _audit(event: str, meta: dict) -> None:
    try:
        from .store import audit
        audit(event, meta)
    except Exception:
        pass


def _canonical_room_id(value) -> str:
    room_id = str(value or "").strip()
    if (not room_id or room_id in (".", "..")
            or not _ROOM_ID_RE.fullmatch(room_id)):
        raise ValueError("room_id 必须是非空文件名，不能包含路径分隔符")
    return room_id


def _room_root(room_id: str) -> Path:
    return safe_relative_path(_ROOT, _canonical_room_id(room_id))


def _room_lock(room_id: str) -> Path:
    return _ROOT / f".{_canonical_room_id(room_id)}.lock"


def _dirs(root: Path) -> dict[str, Path]:
    return {
        "dimension": root / "dimension",
        "reality": root / "reality",
        "timelines": root / "timelines",
        "passports": root / "passports",
        "snapshots": root / "snapshots",
        "plans": root / "plans",
        "reports": root / "reports",
        "rehearsals": root / "rehearsals",
        "runtimes": root / "runtimes",
        "frames": root / "frames",
    }


def _ensure_dirs(root: Path) -> dict[str, Path]:
    dirs = _dirs(root)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def _meta_path(root: Path) -> Path:
    return root / "room.json"


def _room_meta(room_id: str, required: bool = True) -> tuple[Path, dict]:
    root = _room_root(room_id)
    meta = load_json(_meta_path(root), None)
    if not isinstance(meta, dict):
        if required:
            raise ValueError(f"房间不存在: {room_id}")
        return root, {}
    return root, meta


def _json_sha(value) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _tree(root: Path) -> dict:
    from . import mirror_space as MS
    return MS._tree_fingerprint(root)


def _tree_sha(root: Path) -> str:
    return _json_sha(_tree(root))


def _append_event(root: Path, event: str, data: dict | None = None) -> dict:
    row = {
        "ts": _now(),
        "event": event,
        "data": data or {},
    }
    locked_append_text(
        root / "events.jsonl",
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n",
    )
    return row


def _latest_visual() -> dict:
    """读取现有视觉通道的最新摘要；此处不采集、不复制总线。"""
    for modpath in (
        "gbt_allinone.tentacle.brain.tentacle_transmission",
        "brain.tentacle_transmission",
        "tentacle_transmission",
    ):
        try:
            mod = importlib.import_module(modpath)
            entry = mod.latest("visual")
            if not isinstance(entry, dict):
                continue
            summary = entry.get("summary") or {}
            return {
                "found": True,
                "source": entry.get("source"),
                "ts": entry.get("ts") or entry.get("epoch_ms"),
                "type": summary.get("type"),
                "frame_id": summary.get("frame_id"),
                "fingerprint": summary.get("fingerprint"),
                "frame_kb": summary.get("frame_kb"),
                "size": summary.get("size"),
            }
        except Exception:
            continue
    return {"found": False}


def _room_latest_frame(meta: dict) -> dict:
    """优先使用房间自己绑定的帧，避免多房间之间读到彼此的最新帧。"""
    frame = meta.get("last_frame")
    if isinstance(frame, dict) and frame.get("frame_id"):
        return {"found": True, **frame}
    return {"found": False}


def _frame_store():
    for modpath in (
        "gbt_allinone.tentacle.vision_bus",
        "tentacle.vision_bus",
        "vision_bus",
    ):
        try:
            return importlib.import_module(modpath)
        except Exception:
            continue
    return None


def _vision_watch():
    for modpath in (
        "gbt_allinone.tentacle.vision_watch",
        "tentacle.vision_watch",
        "vision_watch",
    ):
        try:
            return importlib.import_module(modpath)
        except Exception:
            continue
    return None


def _persist_shared_frame(frame_b64: str, source: str = "room_space") -> dict:
    store = _frame_store()
    if store is None:
        return {"ok": False, "error": "vision_bus 不可用"}
    result = store.persist_frame(frame_b64)
    if result.get("ok"):
        try:
            from .tentacle.brain import tentacle_transmission as TT
            TT.transmit(
                {
                    "type": "room_frame",
                    "ok": True,
                    "frame_id": result.get("frame_id"),
                    "frame_kb": result.get("frame_kb"),
                    "source": source,
                },
                source=source,
                channel="visual",
                priority="high",
            )
        except Exception:
            pass
    return result


def _public_room(room_id: str, meta: dict, *, include_events: bool = False) -> dict:
    root = _room_root(room_id)
    dirs = _dirs(root)
    tree = _tree(dirs["dimension"])
    namespace = meta.get("namespace") or _namespace_contract(room_id)
    latest_frame = _room_latest_frame(meta)
    if latest_frame.get("frame_id"):
        latest_frame["frame_fqn"] = _frame_fqn(
            room_id, latest_frame.get("frame_id"))
    snapshot_files = sorted(dirs["snapshots"].glob("*.json")) if dirs["snapshots"].exists() else []
    passport_files = sorted(dirs["passports"].glob("v*.json")) if dirs["passports"].exists() else []
    timeline_dirs = [p for p in dirs["timelines"].iterdir() if p.is_dir()] if dirs["timelines"].exists() else []
    events = []
    lines = []                    # 先初始化：下面只在"有 events.jsonl"时才赋值，
                                  # 少了这一行，include_events=True 但文件不存在时会 NameError
    if include_events and (root / "events.jsonl").exists():
        try:
            lines = (root / "events.jsonl").read_text(
                encoding="utf-8", errors="replace").splitlines()
            for line in lines[-20:]:
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue
        except OSError:
            pass
    return {
        "ok": True,
        "room_id": room_id,
        "path": str(root),
        "purpose": meta.get("purpose", ""),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "state": meta.get("state", "open"),
        "members": meta.get("members") or {},
        "display": meta.get("display") or {},
        "namespace": namespace,
        "dimension": {"files": len(tree), "sha": _json_sha(tree)},
        "reality": {"files": len(_tree(dirs["reality"])),
                    "version": len(passport_files)},
        "timelines": len(timeline_dirs),
        "snapshots": [p.stem for p in snapshot_files[-10:]],
        "passports": [p.stem for p in passport_files[-10:]],
        # 🔴 2026-09-22 第 43 轮修（错报治理 · **清单被截、分母不见**）：
        #    上面两个清单只给**最后 10 个**（`[-10:]`），而返回值里没有"一共多少个"。
        #    读的人会把 10 当成"这个房间只有 10 个快照/护照"。实测形状同
        #    `agency_tentacles.catalog` / `pipeline.list_records` / `collab_gateway.inbox`
        #    （本仓同一类病的第 4、5 处）。⇒ 每个被截的清单都配一个真分母 + 截断旗。
        "snapshots_total": len(snapshot_files),
        "snapshots_truncated": len(snapshot_files) > 10,
        "passports_total": len(passport_files),
        "passports_truncated": len(passport_files) > 10,
        "events_total": len(events) if include_events else None,
        "events_truncated": (len(lines) > 20) if include_events else None,
        "lists_note": ("snapshots / passports 只列**最后 10 个**；events 只取**最后 20 行**。"
                       "要看全量请读 snapshots_total / passports_total / events_total；"
                       "**只列了一部分 ≠ 只有那么多**。"),
        "latest_frame": latest_frame,
        "events": events if include_events else None,
        "law": meta.get("law", ""),
    }


def create(room_id: str, purpose: str = "", *, display: dict | None = None) -> dict:
    """创建一个隔离房间；同名房间只复用，不重复初始化、不覆盖现场。"""
    room_id = _canonical_room_id(room_id)
    root = _room_root(room_id)
    with FileLock(_room_lock(room_id)):
        old = load_json(_meta_path(root), None)
        if isinstance(old, dict):
            result = _public_room(room_id, old)
            result.update({"created": False, "reused": True})
            return result
        dirs = _ensure_dirs(root)
        safe_display = {}
        if isinstance(display, dict):
            for key in ("provider", "mode", "target", "width", "height", "note"):
                if display.get(key) not in (None, ""):
                    safe_display[key] = display.get(key)
        meta = {
            "schema": "gbt-room/v1",
            "naming_schema": DN.NAMESPACE_SCHEMA,
            "room_id": room_id,
            "namespace": _namespace_contract(room_id),
            "purpose": str(purpose or "")[:240],
            "created_at": _now(),
            "updated_at": _now(),
            "state": "open",
            "display": safe_display,
            "members": {},
            "law": (
                "房间维度可反复试错；房间现实只由全绿排练一次性替换；"
                "视觉帧只引用现有 vision_bus 帧库，不另建总线"
            ),
        }
        atomic_write_json(_meta_path(root), meta)
        namespace_result = _register_namespace(room_id)
        _append_event(root, "room_created", {
            "purpose": meta["purpose"],
            "display": safe_display,
            "dimension": str(dirs["dimension"]),
            "dimension_id": meta["namespace"]["dimension_id"],
        })
        result = _public_room(room_id, meta)
        result.update({
            "created": True,
            "reused": False,
            "namespace_registered": namespace_result.get("ok", False),
        })
        _audit("room_created", {"room_id": room_id})
        return result


def enter(room_id: str, actor: str = "owner", role: str = "member") -> dict:
    """加入房间并留下参与者记录；重复进入只更新状态，不重复建房间。"""
    room_id = _canonical_room_id(room_id)
    root, meta = _room_meta(room_id)
    actor = str(actor or "owner").strip()[:80] or "owner"
    role = str(role or "member").strip()[:40] or "member"
    member_fqn = DN.fqn(room_id, "member", actor)
    with FileLock(_room_lock(room_id)):
        meta = load_json(_meta_path(root), {}) or meta
        members = meta.setdefault("members", {})
        members[actor] = {
            "actor": actor,
            "role": role,
            "fqn": member_fqn,
            "joined_at": members.get(actor, {}).get("joined_at") or _now(),
            "last_seen_at": _now(),
        }
        meta["updated_at"] = _now()
        atomic_write_json(_meta_path(root), meta)
        _append_event(root, "room_join", {
            "actor": actor,
            "role": role,
            "fqn": member_fqn,
        })
    _register_namespace(
        room_id,
        extra_resources=[DN.resource(room_id, "member", actor)],
    )
    result = _public_room(room_id, meta, include_events=True)
    result["member_fqn"] = member_fqn
    return result


def shape(room_id: str, path: str, content: str, note: str = "") -> dict:
    """写房间维度；只能写在当前房间的 dimension 根内。"""
    room_id = _canonical_room_id(room_id)
    root, meta = _room_meta(room_id)
    dirs = _ensure_dirs(root)
    target = safe_relative_path(dirs["dimension"], path)
    raw = str(content)
    relative_path = target.relative_to(dirs["dimension"].resolve()).as_posix()
    artifact_fqn = DN.fqn(room_id, "artifact", relative_path)
    with FileLock(_room_lock(room_id)):
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, raw)
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        _append_event(root, "room_shape", {
            "path": path,
            "sha": sha,
            "bytes": len(raw.encode("utf-8")),
            "note": str(note or "")[:160],
            "fqn": artifact_fqn,
        })
        meta["updated_at"] = _now()
        atomic_write_json(_meta_path(root), meta)
    _register_namespace(
        room_id,
        extra_resources=[DN.resource(room_id, "artifact", relative_path)],
    )
    return {
        "ok": True,
        "room_id": room_id,
        "path": relative_path,
        "fqn": artifact_fqn,
        "dimension_fqn": DN.fqn(room_id, "dimension"),
        "sha": sha,
        "dimension_sha": _tree_sha(dirs["dimension"]),
        "dimension": True,
    }


def shape_bytes(room_id: str, path: str, data: bytes, note: str = "") -> dict:
    """写房间维度（**二进制安全**）——图片/模型/字体不许当文本读。

    与 `shape()` 同一套边界（只能写在当前房间 dimension 根内、同锁同审计同命名空间），
    区别只在**逐字节**落盘。由来（2026-09-19）：把项目搬进房间时若一律走文本路，
    PNG/GLB 会被替换字符污染 ⇒ 房间里的产物当场变废，排练再绿也是假绿。
    """
    room_id = _canonical_room_id(room_id)
    root, meta = _room_meta(room_id)
    dirs = _ensure_dirs(root)
    target = safe_relative_path(dirs["dimension"], path)
    raw = bytes(data)
    relative_path = target.relative_to(dirs["dimension"].resolve()).as_posix()
    artifact_fqn = DN.fqn(room_id, "artifact", relative_path)
    with FileLock(_room_lock(room_id)):
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(target, raw)
        sha = hashlib.sha256(raw).hexdigest()[:16]
        _append_event(root, "room_shape", {
            "path": path,
            "sha": sha,
            "bytes": len(raw),
            "binary": True,
            "note": str(note or "")[:160],
            "fqn": artifact_fqn,
        })
        meta["updated_at"] = _now()
        atomic_write_json(_meta_path(root), meta)
    _register_namespace(
        room_id,
        extra_resources=[DN.resource(room_id, "artifact", relative_path)],
    )
    return {
        "ok": True,
        "room_id": room_id,
        "path": relative_path,
        "fqn": artifact_fqn,
        "dimension_fqn": DN.fqn(room_id, "dimension"),
        "sha": sha,
        "dimension_sha": _tree_sha(dirs["dimension"]),
        "dimension": True,
        "binary": True,
    }


def scan(room_id: str, *, require_entry: bool = False) -> dict:
    """房间体检：不碰现实区，只验证当前房间维度的可排练程度。"""
    room_id = _canonical_room_id(room_id)
    root, meta = _room_meta(room_id)
    dim = _dirs(root)["dimension"]
    tree = _tree(dim)
    checks = {
        "room_exists": {"ok": bool(meta), "detail": str(root)},
        "no_empty_files": {
            "ok": not any(v.get("size") == 0 for v in tree.values()),
            "detail": len([k for k, v in tree.items() if v.get("size") == 0]),
        },
        "discipline": {
            "ok": not any(
                rel.endswith(".tmp") or "__pycache__" in rel
                or (Path(rel).name.startswith("_") and rel.endswith(".py") and Path(rel).name != "__init__.py")
                for rel in tree
            ),
            "detail": "无临时残留",
        },
    }
    if require_entry:
        entries = [
            rel for rel in tree
            if Path(rel).name in ENTRY_NAMES
        ]
        checks["entry_point"] = {
            "ok": bool(entries),
            "detail": entries[:5] if entries else "缺入口文件",
        }
    passed = sum(1 for item in checks.values() if item["ok"])
    report_fqn = DN.fqn(room_id, "report", "simulate-latest")
    result = {
        "ok": passed == len(checks),
        "room_id": room_id,
        "report_fqn": report_fqn,
        "passed": passed,
        "total": len(checks),
        "checks": checks,
        "files": len(tree),
        "dimension_fqn": DN.fqn(room_id, "dimension"),
        "dimension_sha": _json_sha(tree),
        "scanned_at": _now(),
    }
    _audit("room_scanned", {
        "room_id": room_id,
        "ok": result["ok"],
        "files": len(tree),
    })
    return result


def observe(room_id: str, frame_b64: str | None = None) -> dict:
    """把当前共享帧绑定到房间；帧本体仍由现有 vision_bus 内容寻址存储。"""
    room_id = _canonical_room_id(room_id)
    root, meta = _room_meta(room_id)
    frame = {}
    if frame_b64:
        frame = _persist_shared_frame(str(frame_b64), source="room_space.explicit")
    else:
        watch = _vision_watch()
        if watch is not None:
            try:
                captured = watch.frame()
                if captured.get("ok"):
                    focus = captured.get("frame") or {}
                    if focus.get("image_base64"):
                        frame = _persist_shared_frame(
                            focus["image_base64"], source="room_space.vision_watch")
            except Exception:
                pass
        if not frame.get("ok"):
            latest = _latest_visual()
            if latest.get("frame_id"):
                frame = {
                    "ok": True,
                    "frame_id": latest.get("frame_id"),
                    "frame_kb": latest.get("frame_kb"),
                    "fingerprint": latest.get("fingerprint"),
                    "source": latest.get("source"),
                }
    if not frame.get("ok"):
        return {
            "ok": False,
            "room_id": room_id,
            "error": "没有可共享帧；先启动 vision_watch 或传入 frame_b64",
        }
    data = {
        "frame_id": frame.get("frame_id"),
        "frame_fqn": _frame_fqn(room_id, frame.get("frame_id")),
        "frame_kb": frame.get("frame_kb"),
        "fingerprint": frame.get("fingerprint"),
        "source": frame.get("source"),
        "observed_at": _now(),
    }
    with FileLock(_room_lock(room_id)):
        _append_event(root, "room_observe", data)
        meta["last_frame"] = data
        meta["updated_at"] = _now()
        atomic_write_json(_meta_path(root), meta)
    _register_namespace(
        room_id,
        extra_resources=[
            DN.resource(room_id, "frame", frame.get("frame_id")),
        ],
    )
    return {
        "ok": True,
        "room_id": room_id,
        "frame": data,
        "frame_fqn": data["frame_fqn"],
        "shared": True,
        "note": "人和 AI 通过现有视觉总线看到同一帧，并由房间 FQN 固定绑定",
    }


def frame(room_id: str, frame_id: str | None = None) -> dict:
    """按本地 frame_id 或房间 FQN 取回共享画面。"""
    room_id = _canonical_room_id(room_id)
    _root, meta = _room_meta(room_id)
    store = _frame_store()
    if store is None:
        return {"ok": False, "error": "vision_bus 不可用"}
    ref = str(frame_id or "").strip()
    if not ref:
        ref = str(_room_latest_frame(meta).get("frame_id") or "")
    if not ref:
        return {"ok": False, "room_id": room_id, "error": "房间没有共享帧"}
    local = _resolve_local_ref(room_id, ref, "frame")
    if not local.get("ok"):
        return {"ok": False, "room_id": room_id, **local}
    frame_id_value = local.get("local_name")
    result = store.get_frame(frame_id_value)
    return {
        **result,
        "room_id": room_id,
        "frame_id": frame_id_value,
        "frame_fqn": _frame_fqn(room_id, frame_id_value),
        "requested_fqn": local.get("fqn") or None,
    }


def snapshot(room_id: str, label: str = "") -> dict:
    """冻结房间维度为全量时间线，并绑定当前共享帧。"""
    room_id = _canonical_room_id(room_id)
    root, meta = _room_meta(room_id)
    dirs = _ensure_dirs(root)
    with FileLock(_room_lock(room_id)):
        snap_id = time.strftime("%Y%m%dT%H%M%S") + f"-{time.time_ns()}"
        snap_dir = dirs["timelines"] / snap_id
        from . import mirror_space as MS
        MS._replace_tree(dirs["dimension"], snap_dir)
        tree = _tree(snap_dir)
        latest_frame = _room_latest_frame(meta)
        if latest_frame.get("frame_id"):
            latest_frame["frame_fqn"] = _frame_fqn(
                room_id, latest_frame.get("frame_id"))
        snapshot_fqn = DN.fqn(room_id, "snapshot", snap_id)
        record = {
            "room_id": room_id,
            "namespace": meta.get("namespace") or _namespace_contract(room_id),
            "snapshot_id": snap_id,
            "snapshot_fqn": snapshot_fqn,
            "label": str(label or "")[:160],
            "created_at": _now(),
            "dimension_sha": _json_sha(tree),
            "manifest": tree,
            "latest_frame": latest_frame,
        }
        atomic_write_json(dirs["snapshots"] / f"{snap_id}.json", record)
        _append_event(root, "room_snapshot", {
            "snapshot_id": snap_id,
            "files": len(tree),
            "dimension_sha": record["dimension_sha"],
            "frame_id": (record["latest_frame"] or {}).get("frame_id"),
            "fqn": snapshot_fqn,
        })
        meta["updated_at"] = _now()
        atomic_write_json(_meta_path(root), meta)
    _register_namespace(
        room_id,
        extra_resources=[DN.resource(room_id, "snapshot", snap_id)],
    )
    return {
        "ok": True,
        "room_id": room_id,
        "snapshot_id": snap_id,
        "snapshot_fqn": snapshot_fqn,
        "files": len(tree),
        "dimension_sha": record["dimension_sha"],
        "latest_frame": record["latest_frame"],
        "frame_fqn": (record["latest_frame"] or {}).get("frame_fqn"),
    }


def replay(room_id: str, snapshot_id: str | None = None,
           include_frames: bool = True) -> dict:
    """回放房间时间线；帧仍按 frame_id 从现有视觉帧库取回。"""
    room_id = _canonical_room_id(room_id)
    root, _meta = _room_meta(room_id)
    dirs = _ensure_dirs(root)
    files = sorted(dirs["snapshots"].glob("*.json"))
    if snapshot_id:
        manifest_path = safe_relative_path(dirs["snapshots"], f"{snapshot_id}.json")
    else:
        manifest_path = files[-1] if files else None
    if manifest_path is None or not manifest_path.exists():
        return {"ok": False, "room_id": room_id, "error": "房间没有可回放快照"}
    record = load_json(manifest_path, {})
    if not isinstance(record, dict):
        return {"ok": False, "room_id": room_id, "error": "快照记录损坏"}
    snap_dir = safe_relative_path(dirs["timelines"], str(record.get("snapshot_id") or ""))
    timeline = _tree(snap_dir)
    frame_info = record.get("latest_frame") or {}
    result = {
        "ok": True,
        "room_id": room_id,
        "snapshot_id": record.get("snapshot_id"),
        "snapshot_fqn": record.get("snapshot_fqn") or DN.fqn(
            room_id, "snapshot", str(record.get("snapshot_id") or "")),
        "created_at": record.get("created_at"),
        "label": record.get("label"),
        "files": len(timeline),
        "dimension_sha": record.get("dimension_sha"),
        "manifest": timeline,
        "frame_id": frame_info.get("frame_id"),
        "frame_fqn": frame_info.get("frame_fqn") or (
            _frame_fqn(room_id, frame_info.get("frame_id"))
            if frame_info.get("frame_id") else ""),
        "frame_available": bool(frame_info.get("frame_id")),
    }
    if include_frames and frame_info.get("frame_id"):
        got = frame(room_id, frame_info.get("frame_id"))
        result["frame"] = got
        result["frame_available"] = bool(got.get("ok"))
    return result


def _capture_profile(plan: dict) -> dict:
    """房间自己的环境契约快照；只记录存在性，不记录密钥值。"""
    from . import deployment_rehearsal as DR
    environment = plan.get("environment") or {}
    dependencies = {}
    for dep in environment.get("dependencies") or []:
        try:
            dependencies[dep] = importlib.metadata.version(dep)
        except Exception:
            dependencies[dep] = None
    tools = set(environment.get("tools") or [])
    for spec in ((plan.get("rehearsal") or {}).get("commands") or []):
        argv = spec.get("argv") or []
        if argv:
            tools.add(DR._tool_name(argv[0]))
    profile = {
        "captured_at": _now(),
        "platform": sys.platform,
        "os": platform.system().lower(),
        "machine": platform.machine().lower(),
        "python": DR._python_version(),
        "python_implementation": platform.python_implementation().lower(),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_bits": 64 if sys.maxsize > 2**32 else 32,
        "path_style": "windows" if os.name == "nt" else "posix",
        "shell": DR._shell_name(),
        "tools": {tool: DR._tool_present(tool) for tool in sorted(tools)},
        "dependencies": dependencies,
        "env_present": {
            key: bool(os.environ.get(key))
            for key in environment.get("required") or []
        },
        "paths": {
            key: Path(os.path.expanduser(os.path.expandvars(key))).exists()
            for key in environment.get("required_files") or []
        },
        "services": {
            str(svc.get("name")): {
                "port": int(svc.get("port") or 0),
                "signal": bool(
                    svc.get("health_url") or svc.get("heartbeat_file")
                    or str(svc.get("kind") or "").lower() == "windows_service"
                ),
            }
            for svc in plan.get("services") or []
        },
    }
    return {
        "profile": profile,
        "profile_sha": _json_sha(profile),
        "note": "只含契约与存在性，不含密钥值",
    }


def define_plan(room_id: str, plan: dict) -> dict:
    """定义房间排练计划，复用全局排练层的严格规范化。"""
    room_id = _canonical_room_id(room_id)
    root, _meta = _room_meta(room_id)
    dirs = _ensure_dirs(root)
    from . import deployment_rehearsal as DR
    normalized = DR._normalize_plan(plan)
    plan_fqn = DN.fqn(room_id, "plan", "active")
    record = {
        "room_id": room_id,
        "namespace": _namespace_contract(room_id),
        "plan_fqn": plan_fqn,
        "defined_at": _now(),
        "plan_sha": DR._json_sha(normalized),
        "plan": normalized,
    }
    with FileLock(_room_lock(room_id)):
        atomic_write_json(dirs["plans"] / "active.json", record)
    _register_namespace(
        room_id,
        extra_resources=[DN.resource(room_id, "plan", "active")],
    )
    _audit("room_plan_defined", {
        "room_id": room_id,
        "plan_sha": record["plan_sha"][:12],
    })
    return {"ok": True, **record}


def get_plan(room_id: str) -> dict:
    room_id = _canonical_room_id(room_id)
    root, _meta = _room_meta(room_id)
    record = load_json(_dirs(root)["plans"] / "active.json", None)
    if not isinstance(record, dict) or not isinstance(record.get("plan"), dict):
        raise ValueError(f"房间排练计划不存在: {room_id}")
    return {"ok": True, "room_id": room_id, **record}


def simulate(room_id: str, plan: dict | None = None) -> dict:
    """房间静态推演：文件、入口、假设、依赖图、闭环和回滚。"""
    room_id = _canonical_room_id(room_id)
    if plan is not None:
        define_plan(room_id, plan)
    plan_record = get_plan(room_id)
    normalized = plan_record["plan"]
    root, _meta = _room_meta(room_id)
    dirs = _ensure_dirs(root)
    tree = _tree(dirs["dimension"])
    dimension_sha = _json_sha(tree)
    from . import deployment_rehearsal as DR

    checks = {}
    checks["room_exists"] = {"ok": True, "detail": room_id}

    assumptions = DR._assumption_rows(normalized, tree)
    contradicted = [
        row for row in assumptions if row.get("status") == "contradicted"
    ]
    unverified = [
        row for row in assumptions if row.get("status") == "unverified"
    ]
    strict = bool(normalized.get("strict_assumptions"))
    checks["assumptions_verified"] = {
        "ok": not contradicted and not (strict and unverified),
        "detail": (
            f"verified={len(assumptions) - len(contradicted) - len(unverified)}, "
            f"contradicted={len(contradicted)}, unverified={len(unverified)}"
        ),
        "assumptions": assumptions,
    }

    missing_files = []
    for rel in normalized.get("files") or []:
        try:
            if not safe_relative_path(dirs["dimension"], rel).exists():
                missing_files.append(rel)
        except ValueError:
            missing_files.append(f"{rel} (路径越界)")
    checks["files_present"] = {
        "ok": not missing_files,
        "detail": missing_files[:8] if missing_files else "全部存在",
    }

    entrypoints = normalized.get("architecture", {}).get("entrypoints") or []
    declared_entries = bool(entrypoints)
    if not declared_entries:
        # 计划没声明入口 ≠ 树里没有入口。此前这里直接判“未声明入口”失败，于是任何
        # 没填 architecture.entrypoints 的计划**永远过不了静态推演**（而且读数不说怎么办）。
        # 现在按 ENTRY_NAMES 在维度树里真找一遍：找到就放行并标明“未声明·按树识别”，
        # 找不到才失败，且把可识别的名字报出来。
        entrypoints = sorted(
            rel for rel in tree if Path(rel).name in ENTRY_NAMES
        )[:8]
    missing_entries = [rel for rel in entrypoints if rel not in tree]
    if entrypoints and not missing_entries:
        entry_detail = (
            "入口契约完整" if declared_entries
            else "入口未声明，按树内识别：" + ", ".join(entrypoints)
        )
    elif entrypoints:
        entry_detail = f"入口缺失: {missing_entries}"
    else:
        entry_detail = (
            "树内没有任何入口（可识别名："
            + " / ".join(ENTRY_NAMES)
            + "）；文档型产物请补一个 index.html"
        )
    checks["entrypoints"] = {
        "ok": bool(entrypoints) and not missing_entries,
        "detail": entry_detail,
    }

    try:
        DR._waves(normalized.get("steps") or [], "部署步骤")
        DR._waves(
            normalized.get("architecture", {}).get("components") or [],
            "架构组件",
        )
        graph_ok, graph_detail = True, "依赖图无环"
    except Exception as exc:
        graph_ok, graph_detail = False, str(exc)[:200]
    checks["dependency_graph"] = {"ok": graph_ok, "detail": graph_detail}

    rehearsal = normalized.get("rehearsal") or {}
    static_only = bool(rehearsal.get("static_only"))
    acceptance = rehearsal.get("acceptance") or []
    checks["closed_loop_defined"] = {
        "ok": bool(acceptance) or static_only,
        "detail": f"acceptance={acceptance}" if acceptance else "static_only",
    }
    checks["rollback_defined"] = {
        "ok": bool(normalized.get("rollback")),
        "detail": normalized.get("rollback") or {},
    }

    passed = sum(1 for item in checks.values() if item["ok"])
    result = {
        "ok": passed == len(checks),
        "room_id": room_id,
        "passed": passed,
        "total": len(checks),
        "checks": checks,
        "plan_sha": plan_record["plan_sha"],
        "dimension_sha": dimension_sha,
        "files": len(tree),
        "simulated_at": _now(),
    }
    with FileLock(_room_lock(room_id)):
        atomic_write_json(dirs["reports"] / "simulate-latest.json", result)
    _register_namespace(
        room_id,
        extra_resources=[DN.resource(room_id, "report", "simulate-latest")],
    )
    return result


def parity(room_id: str, plan: dict | None = None,
           production: dict | None = None) -> dict:
    """核对房间沙盒与目标环境契约，复用全局排练层比较器。"""
    room_id = _canonical_room_id(room_id)
    if plan is not None:
        define_plan(room_id, plan)
    plan_record = get_plan(room_id)
    normalized = plan_record["plan"]
    root, _meta = _room_meta(room_id)
    dirs = _ensure_dirs(root)
    sandbox = _capture_profile(normalized)["profile"]
    production_spec = production or normalized.get("environment", {}).get("production") or {}
    mode = str(production_spec.get("mode") or "").strip().lower()
    from . import deployment_rehearsal as DR

    if mode == "same_host":
        declared = {
            key: value for key, value in production_spec.items()
            if key not in ("mode", "profile", "note", "notes", "detail")
        }
        production_profile = dict(sandbox)
        if declared:
            production_profile.update(declared)
            comparison = DR.compare_profiles(sandbox, declared)
        else:
            comparison = {
                "ok": True,
                "blockers": [],
                "warnings": [{
                    "field": "production.mode",
                    "detail": "显式同机同环境；晋升时再次检查环境漂移",
                }],
            }
    else:
        production_profile = production_spec.get("profile") or production_spec
        if not isinstance(production_profile, dict):
            raise ValueError("生产 profile 必须是对象")
        comparison = DR.compare_profiles(sandbox, production_profile)

    report_fqn = DN.fqn(room_id, "report", "parity-latest")
    result = {
        "ok": comparison["ok"],
        "room_id": room_id,
        "report_fqn": report_fqn,
        "mode": mode or "explicit_profile",
        "sandbox": sandbox,
        "production": production_profile,
        "blockers": comparison["blockers"],
        "warnings": comparison["warnings"],
        "plan_sha": plan_record["plan_sha"],
        "dimension_sha": _tree_sha(dirs["dimension"]),
        "checked_at": _now(),
    }
    with FileLock(_room_lock(room_id)):
        atomic_write_json(dirs["reports"] / "parity-latest.json", result)
    _register_namespace(
        room_id,
        extra_resources=[DN.resource(room_id, "report", "parity-latest")],
    )
    return result


def rehearse(room_id: str, plan: dict | None = None,
             execute: bool = True) -> dict:
    """在房间维度内跑生产前排练；不触碰房间现实区，不触碰全局生产。"""
    room_id = _canonical_room_id(room_id)
    if plan is not None:
        define_plan(room_id, plan)
    plan_record = get_plan(room_id)
    normalized = plan_record["plan"]
    root, _meta = _room_meta(room_id)
    dirs = _ensure_dirs(root)
    simulation = simulate(room_id)
    parity_result = parity(room_id)
    blockers = []
    if not simulation.get("ok"):
        blockers.append("静态推演未全绿")
    if not parity_result.get("ok"):
        blockers.append("沙盒与目标环境契约不一致")

    before_tree = _tree(dirs["dimension"])
    before_sha = _json_sha(before_tree)
    report_id = time.strftime("%Y%m%dT%H%M%S") + f"-{time.time_ns()}"
    runtime_root = dirs["runtimes"] / report_id
    runtime_root.mkdir(parents=True, exist_ok=True)
    command_results = []
    # 2026-10-21 修（假账）：此前「前置未过 ⇒ 命令不跑」与「命令跑了但失败」在回执里长得
    # 一模一样，都落成 `未通过验收命令`。第一次真跑 one_key_deploy 时，因静态推演第 4 关
    # 未过，验收命令**一次都没执行**，回执却写「未通过验收命令: ['py-syntax-sweep']」——
    # 那是「没跑到」，不是「跑失败」。现在两者分开报，并留下 skip 原因。
    commands_skipped = (not execute) or bool(blockers)
    skip_reason = ""
    if commands_skipped:
        skip_reason = "execute=False" if not execute else "前置未过：" + "、".join(blockers)
    if not commands_skipped:
        from . import deployment_rehearsal as DR
        for spec in normalized.get("rehearsal", {}).get("commands") or []:
            try:
                command_results.append(DR._run_command(
                    spec,
                    dirs["dimension"],
                    runtime_root,
                    before_sha,
                    inherited_env_keys=normalized.get("environment", {}).get("required"),
                ))
            except Exception as exc:
                command_results.append({
                    "id": str(spec.get("id") or "command"),
                    "ok": False,
                    "error": str(exc)[:300],
                })

    after_tree = _tree(dirs["dimension"])
    after_sha = _json_sha(after_tree)
    acceptance = normalized.get("rehearsal", {}).get("acceptance") or []
    passed_commands = {row.get("id") for row in command_results if row.get("ok")}
    missing_acceptance = [item for item in acceptance if item not in passed_commands]
    if missing_acceptance:
        if commands_skipped:
            blockers.append(
                f"验收命令未执行（{skip_reason}）: {missing_acceptance} —— "
                "这是「没跑到」，不是「跑失败」")
        else:
            blockers.append(f"未通过验收命令: {missing_acceptance}")
    if after_sha != before_sha and not normalized.get("allow_rehearsal_artifacts"):
        blockers.append("排练改变了房间维度树，报告失效")

    rehearsal_fqn = DN.fqn(room_id, "rehearsal", report_id)
    result = {
        "ok": not blockers,
        "room_id": room_id,
        "report_id": report_id,
        "rehearsal_fqn": rehearsal_fqn,
        "plan_sha": plan_record["plan_sha"],
        "dimension_sha": after_sha,
        "dimension_files": len(after_tree),
        "simulation": simulation,
        "parity": parity_result,
        "commands": command_results,
        "commands_skipped": commands_skipped,
        "commands_skip_reason": skip_reason or None,
        "acceptance": acceptance,
        "blockers": blockers,
        "rehearsed_at": _now(),
        "law": "房间排练全绿 + 树/计划指纹绑定；变更即失效",
    }
    with FileLock(_room_lock(room_id)):
        atomic_write_json(dirs["rehearsals"] / f"{report_id}.json", result)
        atomic_write_json(dirs["rehearsals"] / "latest.json", result)
    _register_namespace(
        room_id,
        extra_resources=[
            DN.resource(room_id, "rehearsal", report_id),
            DN.resource(room_id, "rehearsal", "latest"),
        ],
    )
    _audit("room_rehearsed", {
        "room_id": room_id,
        "ok": result["ok"],
        "report_id": report_id,
        "blockers": len(blockers),
    })
    return result


def gate(room_id: str) -> dict:
    """检查房间晋升门：报告、计划、维度树和环境漂移必须一致。"""
    room_id = _canonical_room_id(room_id)
    root, _meta = _room_meta(room_id)
    dirs = _ensure_dirs(root)
    latest = load_json(dirs["rehearsals"] / "latest.json", None)
    blockers = []
    environment = {"ok": True, "checked": False, "drift": []}
    plan_record = {}
    if not isinstance(latest, dict):
        blockers.append("没有房间排练报告")
    else:
        if not latest.get("ok"):
            blockers.append("最新房间排练未通过")
        try:
            plan_record = get_plan(room_id)
        except Exception as exc:
            blockers.append(str(exc)[:160])
        if latest.get("dimension_sha") != _tree_sha(dirs["dimension"]):
            blockers.append("房间维度在排练后发生变化，报告已失效")
        if (plan_record.get("plan_sha")
                and latest.get("plan_sha") != plan_record.get("plan_sha")):
            blockers.append("房间计划在排练后发生变化，报告已失效")
        rehearsed = (latest.get("parity") or {}).get("sandbox")
        if isinstance(rehearsed, dict) and plan_record:
            current = _capture_profile(plan_record["plan"])["profile"]
            from . import deployment_rehearsal as DR
            drift = DR._profile_drift(rehearsed, current)
            environment = {"ok": not drift, "checked": True, "drift": drift[:10]}
            if drift:
                blockers.append(
                    "目标环境在排练后发生变化: "
                    + ", ".join(str(row.get("field")) for row in drift[:6])
                )
    result = {
        "ok": not blockers,
        "room_id": room_id,
        "report_fqn": DN.fqn(room_id, "report", "gate-latest"),
        "blockers": blockers,
        "environment": environment,
        "report": latest,
        "gate_at": _now(),
    }
    with FileLock(_room_lock(room_id)):
        atomic_write_json(dirs["reports"] / "gate-latest.json", result)
    _register_namespace(
        room_id,
        extra_resources=[DN.resource(room_id, "report", "gate-latest")],
    )
    return result


def _next_version(dirs: dict[str, Path]) -> int:
    nums = []
    for item in dirs["timelines"].glob("v*"):
        if item.name[1:].isdigit():
            nums.append(int(item.name[1:]))
    return max(nums, default=0) + 1


def release(room_id: str, purpose: str = "",
            plan: dict | None = None,
            owner_override: bool = False, override_reason: str = "") -> dict:
    """房间内一次性晋升：全绿后写房间现实区，保留时间线和护照。

    🔴 2026-10-13（主人令：「**技术层面不能给她有限制只保留人工授权护栏即可**」·
       「**直接改成终端YES才能使用就好了有时候我需要用到的啊**」）：
      「排练未全绿」/「晋升门未通过」两关**都不是死路**了。默认照旧卡住；
      主人在终端发**专用一次性钥匙** `deploy_force`（提示符 YES）+ 调用方显式
      `owner_override=true` ⇒ 放行并**大声落审计**。
      钥匙由**门外那道门**认 ⇒ 旗标不带授权，模型无法自我解锁。
    """
    room_id = _canonical_room_id(room_id)
    root, meta = _room_meta(room_id)
    if plan is not None:
        define_plan(room_id, plan)
    rehearsal = rehearse(room_id)
    if not rehearsal.get("ok"):
        if not owner_override:
            _audit("room_release_blocked",
                   {"room_id": room_id, "blockers": rehearsal.get("blockers")})
            return {
                "ok": False,
                "blocked": True,
                "room_id": room_id,
                "reason": "房间排练未全绿，禁止写入房间现实区",
                "rehearsal": rehearsal,
                "如何放行": ("这不是技术层死限：主人在终端发**专用一次性钥匙** `deploy_force`"
                          "（python -m gbt_allinone auth grant --scope deploy_force --ttl 600，"
                          "提示符敲 YES），再带 owner_override=true 重调即可放行；"
                          "放行会写审计 room_release_overridden。"),
            }
        _audit("room_release_overridden",
               {"room_id": room_id, "blocked_by": "rehearsal",
                "blockers": rehearsal.get("blockers"),
                "reason": str(override_reason or purpose or "(未写理由)")[:200]})
    gate_result = gate(room_id)
    if not gate_result.get("ok"):
        if not owner_override:
            return {
                "ok": False,
                "blocked": True,
                "room_id": room_id,
                "reason": "房间晋升门未通过",
                "gate": gate_result,
                "如何放行": ("同上：主人终端发**专用一次性钥匙** `deploy_force`（YES），"
                          "再带 owner_override=true 重调。"),
            }
        _audit("room_release_overridden",
               {"room_id": room_id, "blocked_by": "gate",
                "blockers": gate_result.get("blockers"),
                "reason": str(override_reason or purpose or "(未写理由)")[:200]})
    dirs = _ensure_dirs(root)
    with FileLock(_room_lock(room_id)):
        from . import mirror_space as MS
        current_sha = _tree_sha(dirs["dimension"])
        if current_sha != rehearsal.get("dimension_sha"):
            return {
                "ok": False,
                "blocked": True,
                "room_id": room_id,
                "reason": "房间维度在门禁后发生变化，禁止晋升",
                "current_dimension_sha": current_sha,
                "rehearsal_dimension_sha": rehearsal.get("dimension_sha"),
            }
        version = _next_version(dirs)
        timeline = dirs["timelines"] / f"v{version}"
        MS._replace_tree(dirs["dimension"], timeline)
        MS._replace_tree(dirs["dimension"], dirs["reality"])
        manifest = _tree(dirs["reality"])
        namespace = meta.get("namespace") or _namespace_contract(room_id)
        timeline_fqn = DN.fqn(room_id, "timeline", f"v{version}")
        passport_fqn = DN.fqn(room_id, "passport", f"v{version}")
        reality_fqn = DN.fqn(room_id, "reality")
        passport = {
            "schema": "gbt-room-passport/v1",
            "room_id": room_id,
            "namespace": namespace,
            "resource_fqns": {
                "reality": reality_fqn,
                "timeline": timeline_fqn,
                "passport": passport_fqn,
            },
            "version": version,
            "promoted_at": _now(),
            "purpose": str(purpose or meta.get("purpose") or "")[:240],
            "files": len(manifest),
            "manifest": manifest,
            "plan_sha": rehearsal.get("plan_sha"),
            "rehearsal_id": rehearsal.get("report_id"),
            "dimension_sha": rehearsal.get("dimension_sha"),
            "latest_frame": _room_latest_frame(meta),
            "law": "房间现实只由全绿排练一次性替换；全局生产仍需显式全局晋升",
        }
        atomic_write_json(dirs["passports"] / f"v{version}.json", passport)
        _append_event(root, "room_released", {
            "version": version,
            "purpose": passport["purpose"],
            "files": len(manifest),
            "rehearsal_id": passport["rehearsal_id"],
        })
        meta["updated_at"] = _now()
        meta["last_release"] = {
            "version": version,
            "released_at": passport["promoted_at"],
        }
        atomic_write_json(_meta_path(root), meta)
    _register_namespace(
        room_id,
        extra_resources=[
            DN.resource(room_id, "timeline", f"v{version}"),
            DN.resource(room_id, "passport", f"v{version}"),
        ],
    )
    _audit("room_released", {
        "room_id": room_id,
        "version": version,
        "passport_fqn": passport_fqn,
        "timeline_fqn": timeline_fqn,
        "reality_fqn": reality_fqn,
        "files": len(manifest),
    })
    return {
        "ok": True,
        "room_id": room_id,
        "version": version,
        "passport_fqn": passport_fqn,
        "timeline_fqn": timeline_fqn,
        "reality_fqn": reality_fqn,
        "files": len(manifest),
        "released_at": passport["promoted_at"],
        "passport": str(dirs["passports"] / f"v{version}.json"),
        "scope": "room_reality",
    }


def sync(room_id: str) -> dict:
    """把房间状态、最新快照和共享帧合并成双方同步契约。"""
    room_id = _canonical_room_id(room_id)
    root, meta = _room_meta(room_id)
    status = _public_room(room_id, meta, include_events=True)
    try:
        status["plan"] = get_plan(room_id)
    except Exception:
        status["plan"] = None
    try:
        status["gate"] = load_json(
            _dirs(root)["reports"] / "gate-latest.json", None)
    except Exception:
        status["gate"] = None
    namespace = status.get("namespace") or _namespace_contract(room_id)
    status["namespace"] = namespace
    status["shared_contract"] = {
        "dimension_sha": status["dimension"]["sha"],
        "dimension_id": namespace["dimension_id"],
        "dimension_fqn": namespace["resources"]["dimension"]["fqn"],
        "frame_id": (status.get("latest_frame") or {}).get("frame_id"),
        "frame_fqn": (status.get("latest_frame") or {}).get("frame_fqn"),
        "same_source": "existing_vision_bus",
        "vision_bus_fqn": namespace["resources"]["vision_bus"]["fqn"],
        "capability_fqns": {
            name: row["fqn"] for name, row in namespace["capabilities"].items()
        },
        "room_scope": "mirror_space/rooms",
    }
    return status


def status(room_id: str, include_events: bool = False) -> dict:
    room_id = _canonical_room_id(room_id)
    root, meta = _room_meta(room_id)
    return _public_room(room_id, meta, include_events=include_events)


def namespace(room_id: str) -> dict:
    """Register and return the room's complete FQN contract."""
    room_id = _canonical_room_id(room_id)
    _room_meta(room_id)
    result = _register_namespace(room_id)
    return {
        "ok": True,
        "room_id": room_id,
        **result,
    }


def registry(room_id: str | None = None) -> dict:
    """Read the global dimension registry, optionally for one room."""
    if room_id:
        room_id = _canonical_room_id(room_id)
    return DN.registry(room_id)


def resolve(value: str) -> dict:
    """Resolve a room-qualified resource or capability FQN."""
    return DN.resolve(value)


__all__ = [
    "create", "enter", "shape", "scan", "observe", "frame",
    "snapshot", "replay", "define_plan", "get_plan", "simulate",
    "parity", "rehearse", "gate", "release", "sync", "status",
    "namespace", "registry", "resolve",
]

