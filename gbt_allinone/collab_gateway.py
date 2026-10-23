"""Scoped external-AI collaboration gateway.

One HTTP endpoint multiplexes all external actions. Tokens are stored as
hashes, project paths are replaced by opaque material handles, and the mirror
space registry is never exposed. Peer control is limited to actions explicitly
registered by the remote framework.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ._paths import STORE_DIR
from .safe_io import FileLock, atomic_write_json, load_json, safe_relative_path
from .security import net_guard

_ROOT = Path(STORE_DIR) / "collab"
_SESSIONS = _ROOT / "sessions.json"
_PEERS = _ROOT / "peers.json"
_PROPOSALS = _ROOT / "inbox"
_LOCK = _ROOT / ".collab.lock"

_SESSION_SCOPES = {"visual", "materials", "proposal"}
_DELEGATE_ACTIONS = {"room_plan", "room_simulate", "room_parity"}
_MAX_HTTP_BODY = 4 * 1024 * 1024
_MAX_MATERIAL_BYTES = 5 * 1024 * 1024
_PEER_ACTION_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")

_SERVER = {
    "instance": None,
    "thread": None,
    "host": None,
    "port": None,
    "started_at": None,
}
_SERVER_LOCK = threading.Lock()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _audit(event: str, meta: dict) -> None:
    try:
        from .store import audit
        audit(event, meta)
    except Exception:
        pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _load_unlocked(path: Path, default):
    value = load_json(path, default)
    return value if isinstance(value, type(default)) else default


def _save_unlocked(path: Path, value) -> None:
    atomic_write_json(path, value)


def _public_session(record: dict, *, include_endpoint: bool = True) -> dict:
    out = {
        "session_id": record.get("session_id"),
        "label": record.get("label"),
        "project_alias": record.get("project_alias"),
        "created_at": record.get("created_at"),
        "expires_at": record.get("expires_at"),
        "revoked": bool(record.get("revoked")),
        "scopes": record.get("scopes") or [],
        "materials": [
            {
                "ref": row.get("ref"),
                "name": row.get("name"),
                "bytes": row.get("bytes"),
                "media_type": row.get("media_type"),
            }
            for row in record.get("materials") or []
        ],
        "allow_delegation": bool(record.get("allow_delegation")),
        "delegates": record.get("delegates") or [],
        "calls": int(record.get("calls") or 0),
        "max_calls": int(record.get("max_calls") or 0),
        "last_seen_at": record.get("last_seen_at"),
    }
    if include_endpoint:
        status = server_status()
        out["endpoint"] = status.get("endpoint")
    return out


def _room_dimension(room_id: str) -> Path:
    from . import room_space as RS
    root = RS._room_root(room_id)
    return RS._dirs(root)["dimension"]


def open_session(
    room_id: str,
    *,
    label: str = "",
    scopes=None,
    materials=None,
    allow_delegation: bool = False,
    delegates=None,
    ttl_s: int = 3600,
    max_calls: int = 1000,
) -> dict:
    """Create one scoped collaboration token for one room."""
    from . import room_space as RS

    room_id = RS._canonical_room_id(room_id)
    RS.status(room_id)
    requested = [str(x) for x in (scopes or ["visual", "materials", "proposal"])]
    scopes_clean = list(dict.fromkeys(x for x in requested if x in _SESSION_SCOPES))
    denied = sorted(set(requested) - _SESSION_SCOPES)
    if denied:
        raise ValueError(f"unsupported collaboration scopes: {denied}")
    if not scopes_clean:
        raise ValueError("at least one collaboration scope is required")

    dim = _room_dimension(room_id)
    token = "gbtc_" + secrets.token_urlsafe(32)
    session_id = "conn-" + secrets.token_hex(8)
    project_alias = "proj-" + hashlib.sha256(
        session_id.encode("utf-8")).hexdigest()[:12]
    material_rows = []
    for raw in materials or []:
        rel = str(raw or "").replace("\\", "/").strip()
        if not rel:
            continue
        path = safe_relative_path(dim, rel)
        if not path.is_file():
            raise ValueError(f"material is not a file: {rel}")
        size = path.stat().st_size
        if size > _MAX_MATERIAL_BYTES:
            raise ValueError(f"material exceeds {_MAX_MATERIAL_BYTES} bytes: {rel}")
        ref = "mat-" + hashlib.sha256(
            (session_id + "\0" + rel).encode("utf-8")).hexdigest()[:16]
        material_rows.append({
            "ref": ref,
            "name": Path(rel).name,
            "rel": rel,
            "bytes": size,
            "media_type": _media_type(path),
        })

    delegate_clean = []
    if allow_delegation:
        for action in delegates or []:
            action = str(action or "").strip()
            if action in _DELEGATE_ACTIONS and action not in delegate_clean:
                delegate_clean.append(action)
    record = {
        "session_id": session_id,
        "token_hash": _hash_token(token),
        "label": str(label or "")[:120],
        "project_alias": project_alias,
        "room_id": room_id,
        "created_at": _now(),
        "expires_at": round(time.time() + max(60, int(ttl_s)), 3),
        "revoked": False,
        "scopes": scopes_clean,
        "materials": material_rows,
        "allow_delegation": bool(delegate_clean),
        "delegates": delegate_clean,
        "issued_frames": {},
        "calls": 0,
        "max_calls": max(1, int(max_calls)),
        "last_seen_at": None,
    }
    with FileLock(_LOCK):
        sessions = _load_unlocked(_SESSIONS, {})
        sessions[session_id] = record
        _save_unlocked(_SESSIONS, sessions)

    result = _public_session(record)
    result.update({
        "ok": True,
        "token": token,
        "token_notice": "token is returned once; only its hash is stored",
        "visibility": {
            "room_id": False,
            "mirror_space": False,
            "registry": False,
            "audit": False,
            "filesystem_paths": False,
        },
    })
    _audit("collab_session_opened", {
        "session_id": session_id,
        "project_alias": project_alias,
        "scopes": scopes_clean,
        "materials": len(material_rows),
        "allow_delegation": bool(delegate_clean),
    })
    return result


def status(session_id: str | None = None) -> dict:
    """Owner-facing session status without token material."""
    with FileLock(_LOCK):
        sessions = _load_unlocked(_SESSIONS, {})
    if session_id:
        record = sessions.get(str(session_id))
        if not isinstance(record, dict):
            return {"ok": False, "error": "collaboration session not found"}
        return {
            "ok": True,
            "session": _public_session(record),
            "room_id": record.get("room_id"),
        }
    rows = []
    for record in sessions.values():
        if not isinstance(record, dict):
            continue
        row = _public_session(record)
        row["room_id"] = record.get("room_id")
        rows.append(row)
    return {"ok": True, "count": len(rows), "sessions": rows}


def close_session(session_id: str) -> dict:
    session_id = str(session_id or "").strip()
    if not session_id:
        raise ValueError("session_id is required")
    with FileLock(_LOCK):
        sessions = _load_unlocked(_SESSIONS, {})
        record = sessions.get(session_id)
        if not isinstance(record, dict):
            return {"ok": False, "error": "collaboration session not found"}
        record["revoked"] = True
        record["revoked_at"] = _now()
        _save_unlocked(_SESSIONS, sessions)
    _audit("collab_session_revoked", {"session_id": session_id})
    return {"ok": True, "session_id": session_id, "revoked": True}


def _authenticate(token: str) -> tuple[dict | None, dict]:
    raw = str(token or "").strip()
    if not raw:
        return None, {"ok": False, "error": "session token is required"}
    token_hash = _hash_token(raw)
    with FileLock(_LOCK):
        sessions = _load_unlocked(_SESSIONS, {})
        for record in sessions.values():
            if not isinstance(record, dict) or record.get("token_hash") != token_hash:
                continue
            if record.get("revoked"):
                return None, {"ok": False, "error": "session revoked"}
            if float(record.get("expires_at") or 0) <= time.time():
                return None, {"ok": False, "error": "session expired"}
            if int(record.get("calls") or 0) >= int(record.get("max_calls") or 0):
                return None, {"ok": False, "error": "session call limit reached"}
            record["calls"] = int(record.get("calls") or 0) + 1
            record["last_seen_at"] = _now()
            _save_unlocked(_SESSIONS, sessions)
            return dict(record), {"ok": True}
    return None, {"ok": False, "error": "invalid session token"}


def _manifest(record: dict) -> dict:
    return {
        "ok": True,
        "protocol": "gbt-collab/v1",
        "project": {
            "alias": record.get("project_alias"),
            "label": record.get("label"),
        },
        "actions": {
            "manifest": True,
            "frame": "visual" in (record.get("scopes") or []),
            "materials": "materials" in (record.get("scopes") or []),
            "propose": "proposal" in (record.get("scopes") or []),
            "task": bool(record.get("allow_delegation")),
            "close": True,
        },
        "materials": _public_session(record, include_endpoint=False)["materials"],
        "delegates": record.get("delegates") or [],
        "expires_at": record.get("expires_at"),
        "access": "scoped_project_only",
    }


def _latest_frame(record: dict) -> dict:
    from . import room_space as RS

    got = RS.frame(record["room_id"])
    if not got.get("ok"):
        return {"ok": False, "error": "project has no shared visual frame"}
    frame_id = got.get("frame_id")
    with FileLock(_LOCK):
        sessions = _load_unlocked(_SESSIONS, {})
        current = sessions.get(record["session_id"])
        if not isinstance(current, dict):
            return {"ok": False, "error": "session disappeared"}
        issued = current.setdefault("issued_frames", {})
        frame_ref = None
        for ref, known in issued.items():
            if known == frame_id:
                frame_ref = ref
                break
        if frame_ref is None:
            frame_ref = "fr-" + secrets.token_hex(8)
            issued[frame_ref] = frame_id
            _save_unlocked(_SESSIONS, sessions)
    return {
        "ok": True,
        "frame_ref": frame_ref,
        "frame_kb": got.get("frame_kb"),
        "image_base64": got.get("frame_b64"),
        "note": "visual content is scoped to this collaboration session",
    }


def _get_frame(record: dict, payload: dict) -> dict:
    from . import room_space as RS

    ref = str(payload.get("frame_ref") or "").strip()
    with FileLock(_LOCK):
        sessions = _load_unlocked(_SESSIONS, {})
        current = sessions.get(record["session_id"])
        if not isinstance(current, dict):
            return {"ok": False, "error": "session disappeared"}
        issued = current.get("issued_frames") or {}
        frame_id = issued.get(ref) if ref else None
    if ref and not frame_id:
        return {"ok": False, "error": "frame_ref is not authorized for this session"}
    if not frame_id:
        return _latest_frame(record)
    got = RS.frame(record["room_id"], frame_id)
    if not got.get("ok"):
        return {"ok": False, "error": "authorized frame is no longer available"}
    return {
        "ok": True,
        "frame_ref": ref,
        "frame_kb": got.get("frame_kb"),
        "image_base64": got.get("frame_b64"),
    }


def _materials(record: dict) -> dict:
    return {
        "ok": True,
        "project": record.get("project_alias"),
        "materials": _public_session(record, include_endpoint=False)["materials"],
    }


def _read_material(record: dict, payload: dict) -> dict:
    ref = str(payload.get("ref") or "").strip()
    row = next(
        (item for item in record.get("materials") or []
         if item.get("ref") == ref),
        None,
    )
    if not row:
        return {"ok": False, "error": "material_ref is not authorized"}
    path = safe_relative_path(_room_dimension(record["room_id"]), row["rel"])
    if not path.is_file():
        return {"ok": False, "error": "material is no longer available"}
    raw = path.read_bytes()
    if len(raw) > _MAX_MATERIAL_BYTES:
        return {"ok": False, "error": "material grew beyond the authorized size"}
    result = {
        "ok": True,
        "ref": ref,
        "name": row.get("name"),
        "bytes": len(raw),
        "media_type": row.get("media_type"),
    }
    if _is_text(row.get("media_type"), raw):
        result["content"] = raw.decode("utf-8", errors="replace")
    else:
        result["content_base64"] = base64.b64encode(raw).decode("ascii")
    return result


def _store_inbox(record: dict, payload: dict, *, kind: str) -> dict:
    requested_action = str(
        payload.get("task_action")
        or payload.get("delegate_action")
        or payload.get("op")
        or ""
    ).strip()
    if kind == "task":
        if not record.get("allow_delegation") or requested_action not in (
                record.get("delegates") or []):
            return {"ok": False, "error": "delegated action is not authorized"}
    item_id = kind + "-" + secrets.token_hex(8)
    item = {
        "id": item_id,
        "kind": kind,
        "project_alias": record.get("project_alias"),
        "session_id": record.get("session_id"),
        "created_at": _now(),
        "action": (requested_action if kind == "task" else "propose")[:80],
        "text": str(payload.get("text") or "")[:20000],
        "payload": payload.get("payload") if isinstance(
            payload.get("payload"), dict) else {},
    }
    target = _PROPOSALS / record["session_id"] / f"{item_id}.json"
    atomic_write_json(target, item)
    _audit("collab_inbox_item", {
        "session_id": record.get("session_id"),
        "project_alias": record.get("project_alias"),
        "kind": kind,
        "action": item["action"],
    })
    return {"ok": True, "id": item_id, "kind": kind, "queued": True}


def inbox(session_id: str | None = None, limit: int = 100) -> dict:
    """Owner-facing collaboration proposals and delegated task requests."""
    limit = max(1, min(int(limit), 500))
    roots = [_PROPOSALS / str(session_id)] if session_id else []
    if not roots:
        roots = [p for p in _PROPOSALS.iterdir() if p.is_dir()] if _PROPOSALS.exists() else []
    rows = []
    for root in roots:
        for path in root.glob("*.json"):
            item = load_json(path, None)
            if isinstance(item, dict):
                rows.append(item)
    rows.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    # 🔴 2026-09-22 第 42 轮修（错报治理 · 与 `pipeline.list_records` / `agency_tentacles.catalog`
    #    同一类，这是本仓第三处）：`count` 原来是 `min(len(rows), limit)` —— 那是**这一页**的条数
    #    （还被硬上限 500 压着），读的人问"一共收到多少条提案"会拿到页大小。
    #    ⇒ 补 `total`（真分母）+ `truncated` + `count_note`，形状照 `tentacle/omni_fs.py:162` 的样板。
    return {"ok": True, "count": min(len(rows), limit), "items": rows[:limit],
            "total": len(rows), "limit": limit, "truncated": len(rows) > limit,
            "count_note": ("count=本页条数；total=收到的总数；"
                           + ("**本次被 limit 截断**（还有 %d 条没列出）" % (len(rows) - limit)
                              if len(rows) > limit else "本次未截断（total 全部列出）"))}


def dispatch(envelope: dict, token: str = "") -> dict:
    """Dispatch one envelope over the single collaboration connection."""
    data = dict(envelope or {})
    action = str(data.get("action") or data.get("op") or "manifest").strip().lower()
    supplied = token or data.get("token") or data.get("session") or ""
    if action in ("join", "manifest"):
        action = "manifest"
    record, auth = _authenticate(supplied)
    if not auth.get("ok"):
        return {"ok": False, "protocol": "gbt-collab/v1", "error": auth.get("error")}
    try:
        if action == "manifest":
            return _manifest(record)
        if action == "frame":
            if "visual" not in (record.get("scopes") or []):
                return {"ok": False, "error": "visual scope is not authorized"}
            return _get_frame(record, data)
        if action == "materials":
            if "materials" not in (record.get("scopes") or []):
                return {"ok": False, "error": "materials scope is not authorized"}
            return _materials(record)
        if action == "material":
            if "materials" not in (record.get("scopes") or []):
                return {"ok": False, "error": "materials scope is not authorized"}
            return _read_material(record, data)
        if action in ("propose", "task"):
            if "proposal" not in (record.get("scopes") or []):
                return {"ok": False, "error": "proposal scope is not authorized"}
            return _store_inbox(record, data, kind=action)
        if action == "close":
            return close_session(record["session_id"])
        if action == "ping":
            return {"ok": True, "protocol": "gbt-collab/v1", "session_id": record["session_id"]}
        return {"ok": False, "error": f"unknown collaboration action: {action}"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


class _CollabHandler(BaseHTTPRequestHandler):
    server_version = "GBT-Collab/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002
        return

    def _send(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):  # noqa: N802
        if urllib.parse.urlsplit(self.path).path != "/gbt/collab":
            self._send(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > _MAX_HTTP_BODY:
            self._send(413, {"ok": False, "error": "invalid body size"})
            return
        try:
            envelope = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send(400, {"ok": False, "error": "invalid JSON"})
            return
        auth = self.headers.get("Authorization") or ""
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        result = dispatch(envelope, token=token)
        self._send(200 if result.get("ok") else 403, result)


def start_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    allow_public: bool = False,
) -> dict:
    """Start the single collaboration endpoint, reusing an existing listener."""
    host = str(host or "127.0.0.1").strip()
    port = int(port)
    with _SERVER_LOCK:
        server = _SERVER.get("instance")
        if server is not None:
            return {
                "ok": True,
                "reused": True,
                **_server_public_status_unlocked(),
            }
        if not allow_public and not _host_is_private(host):
            raise ValueError("public bind requires allow_public=true")
        server = ThreadingHTTPServer((host, port), _CollabHandler)
        server.daemon_threads = True
        thread = threading.Thread(
            target=server.serve_forever,
            name="gbt-collab-server",
            daemon=True,
        )
        thread.start()
        _SERVER.update({
            "instance": server,
            "thread": thread,
            "host": host,
            "port": server.server_address[1],
            "started_at": _now(),
        })
        status = _server_public_status_unlocked()
    _audit("collab_server_started", {
        "host": status["host"],
        "port": status["port"],
        "public": bool(allow_public),
    })
    return {"ok": True, "reused": False, **status}


def stop_server() -> dict:
    with _SERVER_LOCK:
        server = _SERVER.get("instance")
        if server is None:
            return {"ok": True, "running": False, "note": "server already stopped"}
        server.shutdown()
        server.server_close()
        _SERVER.update({
            "instance": None,
            "thread": None,
            "host": None,
            "port": None,
            "started_at": None,
        })
    _audit("collab_server_stopped", {})
    return {"ok": True, "running": False}


def server_status() -> dict:
    with _SERVER_LOCK:
        return _server_public_status_unlocked()


def _server_public_status_unlocked() -> dict:
    server = _SERVER.get("instance")
    host = _SERVER.get("host")
    port = _SERVER.get("port")
    running = bool(server is not None and _SERVER.get("thread")
                   and _SERVER["thread"].is_alive())
    endpoint = f"http://{host}:{port}/gbt/collab" if running else None
    return {
        "ok": True,
        "running": running,
        "host": host,
        "port": port,
        "endpoint": endpoint,
        "started_at": _SERVER.get("started_at"),
        "transport_security": "use TLS reverse proxy for non-loopback access",
    }


def register_peer(
    peer_id: str,
    endpoint: str,
    actions,
    *,
    auth_env: str = "",
    secret_env: str = "",
    allow_insecure: bool = False,
) -> dict:
    """Register an explicitly authorized remote framework endpoint."""
    peer_id = str(peer_id or "").strip()
    if not _PEER_ACTION_RE.fullmatch(peer_id):
        raise ValueError("peer_id contains unsupported characters")
    parsed = urllib.parse.urlsplit(str(endpoint or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("peer endpoint must be an http(s) URL")
    host = parsed.hostname or ""
    if parsed.scheme != "https" and not _host_is_private(host) and not allow_insecure:
        raise ValueError("non-loopback peer endpoint requires https or allow_insecure=true")
    if not auth_env and not secret_env:
        raise ValueError("peer authentication requires auth_env or secret_env")
    clean_actions = []
    for action in actions or []:
        action = str(action or "").strip()
        if not _PEER_ACTION_RE.fullmatch(action):
            raise ValueError(f"invalid peer action: {action}")
        if action not in clean_actions:
            clean_actions.append(action)
    if not clean_actions:
        raise ValueError("peer must expose at least one action")
    record = {
        "peer_id": peer_id,
        "endpoint": str(endpoint).strip(),
        "actions": clean_actions,
        "auth_env": str(auth_env or "")[:120],
        "secret_env": str(secret_env or "")[:120],
        "allow_insecure": bool(allow_insecure),
        "created_at": _now(),
        "updated_at": _now(),
    }
    with FileLock(_LOCK):
        peers = _load_unlocked(_PEERS, {})
        record["created_at"] = (peers.get(peer_id) or {}).get(
            "created_at") or record["created_at"]
        peers[peer_id] = record
        _save_unlocked(_PEERS, peers)
    _audit("collab_peer_registered", {
        "peer_id": peer_id,
        "actions": clean_actions,
        "endpoint_host": host,
    })
    return {"ok": True, "peer": _public_peer(record)}


def peer_status(peer_id: str | None = None) -> dict:
    with FileLock(_LOCK):
        peers = _load_unlocked(_PEERS, {})
    if peer_id:
        record = peers.get(str(peer_id))
        if not isinstance(record, dict):
            return {"ok": False, "error": "peer not registered"}
        return {"ok": True, "peer": _public_peer(record)}
    return {
        "ok": True,
        "count": len(peers),
        "peers": [_public_peer(row) for row in peers.values()
                  if isinstance(row, dict)],
    }


def _public_peer(record: dict) -> dict:
    return {
        "peer_id": record.get("peer_id"),
        "endpoint": record.get("endpoint"),
        "actions": record.get("actions") or [],
        "auth_configured": bool(record.get("auth_env")
                                and os.environ.get(record.get("auth_env"))),
        "signature_configured": bool(record.get("secret_env")
                                     and os.environ.get(record.get("secret_env"))),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }


def request_peer(
    peer_id: str,
    action: str,
    payload: dict | None = None,
    *,
    timeout_s: int = 15,
) -> dict:
    """Call one action that the remote peer explicitly registered."""
    peer_id = str(peer_id or "").strip()
    action = str(action or "").strip()
    with FileLock(_LOCK):
        peers = _load_unlocked(_PEERS, {})
        peer = peers.get(peer_id)
    if not isinstance(peer, dict):
        return {"ok": False, "error": "peer not registered"}
    if action not in (peer.get("actions") or []):
        return {"ok": False, "error": "peer action is not authorized"}

    endpoint = str(peer.get("endpoint") or "")
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "https" and not _host_is_private(parsed.hostname or ""):
        if not peer.get("allow_insecure"):
            return {"ok": False, "error": "insecure peer endpoint is blocked"}
    body_payload = payload if isinstance(payload, dict) else {}
    body = json.dumps({
        "protocol": "gbt-peer/v1",
        "peer_id": peer_id,
        "action": action,
        "payload": body_payload,
        "issued_at": round(time.time(), 3),
        "nonce": secrets.token_hex(16),
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "GBT-Xiaotudou-Collab/1.0",
    }
    auth_env = str(peer.get("auth_env") or "")
    auth_token = os.environ.get(auth_env, "") if auth_env else ""
    if auth_token:
        headers["Authorization"] = "Bearer " + auth_token
    secret_env = str(peer.get("secret_env") or "")
    secret = os.environ.get(secret_env, "") if secret_env else ""
    if not auth_token and not secret:
        return {"ok": False, "error": "peer credentials are not configured in the environment"}
    if secret:
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        canonical = (
            timestamp + "\n" + nonce + "\n"
            + body.decode("utf-8")
        ).encode("utf-8")
        signature = hmac.new(
            secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
        headers["X-GBT-Timestamp"] = timestamp
        headers["X-GBT-Nonce"] = nonce
        headers["X-GBT-Signature"] = signature

    try:
        response = net_guard.safe_request_json(
            endpoint,
            method="POST",
            headers=headers,
            body=body,
            timeout=max(1, int(timeout_s)),
            max_bytes=1024 * 1024,
            allow_private=True,
            max_redirects=0,
        )
        result = response.get("json")
        if result is None:
            result = {"text": response.get("text") or ""}
        status = int(response.get("status") or 0)
        return {
            "ok": 200 <= status < 300,
            "status": status,
            "response": result,
        }
    except net_guard.NetworkGuardError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:240]}"}


def _host_is_private(host: str) -> bool:
    host = str(host or "").strip().lower()
    if host in ("localhost", ""):
        return True
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(row[4][0])
                for row in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            ]
        except OSError:
            return False
    return all(
        address.is_loopback or address.is_private or address.is_link_local
        for address in addresses
    )


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".json": "application/json",
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ts": "text/typescript",
        ".html": "text/html",
        ".css": "text/css",
        ".csv": "text/csv",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
    }.get(suffix, "application/octet-stream")


def _is_text(media_type: str, raw: bytes) -> bool:
    if str(media_type or "").startswith("text/"):
        return True
    if str(media_type or "") in (
        "application/json", "text/markdown", "application/xml"):
        return True
    return b"\x00" not in raw[:1024]
