# gbt-capability: remote_controller
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""remote_controller — 远程接管的**授权内核**：没有远端用户同意，一个字节都不动。

主人 2026-11-01 的硬规矩（原话转述）：
  · 是“接管电脑控制器”的远程协助，不是拿动作 API 假装远控；
  · **必须远端用户点击同意授权**，万能插才能接管。

本件先把“同意”做成硬门（传输/屏幕/输入是下一步，不在本件假装）：
  request  —— 发起请求，生成一次性 code + agent_secret（只交给远端 agent）
  approve  —— **只能由远端 agent 持有 secret + 用户确认**才能批准（HMAC 校验 code/request/host）
  session  —— 只有 approved 且未过期/未撤销，才发 session；否则 denied
  revoke   —— 远端/本地随时撤销，撤销即失效
  audit/status/where

硬门：
  · 请求方不能自己 approve；
  · 没有 remote_user.confirmed=true / 没有正确 secret / code 错 / 过期 ⇒ 一律拒；
  · session 未批准 ⇒ denied；本件不提供屏幕/输入/语音通道（避免把“授权”冒充成“远控已通”）。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE = ROOT / "state" / "remote_controller" / "sessions.json"

STATUS = {
    "cap": "remote_controller", "tier": "native", "domain": "tentacle",
    "ops": ["status", "request", "approve", "deny", "session", "revoke", "audit", "where"],
    "consent_required": True,
    "rule": "远端用户显式同意 + 一次性 secret 校验 → 才发 session；请求方不能自批",
    "not_implemented": ["媒体通道（屏幕帧/输入注入/语音）", "公网隧道/relay", "远程 agent GUI"],
    "next": "授权内核已硬；下一步接远端 agent（同意 UI）+ 加密会话 + 屏幕/输入/语音通道",
}


def _store(payload=None) -> Path:
    payload = payload or {}
    return Path(payload.get("store") or os.environ.get("GBT_REMOTE_STORE") or DEFAULT_STORE).expanduser().resolve()


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"sessions": {}, "audit": []}


def _save(p: Path, d: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _sig(secret: str, request_id: str, host: str, user: str) -> str:
    msg = "%s|%s|%s" % (request_id, host, user)
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


def _request(payload):
    p = _store(payload)
    d = _load(p)
    rid = "rc-" + secrets.token_hex(6)
    code = "%06d" % secrets.randbelow(1000000)
    secret = secrets.token_urlsafe(24)
    row = {"id": rid, "code": code, "secret": secret, "scope": payload.get("scope") or ["screen", "input", "voice"],
           "requester": payload.get("requester") or "local",
           "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "expires_in": int(payload.get("expires_in") or 300),
           "status": "pending", "approved_at": None, "remote_user": None, "session": None}
    d["sessions"][rid] = row
    d.setdefault("audit", []).append({"at": row["created_at"], "event": "request", "id": rid,
                                      "scope": row["scope"], "requester": row["requester"]})
    _save(p, d)
    return {"ok": True, "status": "pending", "request_id": rid, "code": code, "agent_secret": secret,
            "scope": row["scope"], "expires_in": row["expires_in"], "store": str(p),
            "how_to": "把 code+agent_secret 交给远端 agent；远端用户确认后 agent 调 approve；请求方不能自批"}


def _approve(payload):
    p = _store(payload)
    d = _load(p)
    rid = str(payload.get("request_id") or payload.get("id") or "")
    row = d["sessions"].get(rid)
    if not row:
        return {"ok": False, "status": "not_found"}
    if row.get("status") != "pending":
        return {"ok": False, "status": row.get("status"), "error": "不是 pending，不能重复批准"}
    if row.get("approved_at"):
        return {"ok": False, "status": "already_approved"}
    if time.time() > time.mktime(time.strptime(row["created_at"], "%Y-%m-%dT%H:%M:%S")) + row["expires_in"]:
        row["status"] = "expired"; _save(p, d)
        return {"ok": False, "status": "expired", "error": "请求过期；重新 request"}
    if str(payload.get("code") or "") != row["code"]:
        return {"ok": False, "status": "bad_code", "error": "一次性 code 不对"}
    ru = payload.get("remote_user") if isinstance(payload.get("remote_user"), dict) else {}
    if ru.get("confirmed") is not True:
        return {"ok": False, "status": "needs_remote_consent",
                "error": "必须由远端用户 confirmed=true（点击同意），请求方不能自批"}
    host = str(ru.get("host") or payload.get("host") or "")
    user = str(ru.get("user") or payload.get("user") or "")
    want = _sig(row["secret"], rid, host, user)
    got = str(payload.get("agent_signature") or "")
    if not got or not hmac.compare_digest(want, got):
        return {"ok": False, "status": "bad_signature",
                "error": "缺少远端 agent secret 的 HMAC 签名（证明是远端 agent 批的，不是请求方自批）"}
    row.update({"status": "approved", "approved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "remote_user": {"host": host, "user": user, "confirmed": True},
                "agent_signature": got})
    d.setdefault("audit", []).append({"at": row["approved_at"], "event": "approve", "id": rid,
                                      "remote_user": row["remote_user"]})
    _save(p, d)
    return {"ok": True, "status": "approved", "request_id": rid, "scope": row["scope"],
            "remote_user": row["remote_user"], "note": "远端已同意；可申请 session（媒体通道仍未接）"}


def _deny(payload):
    p = _store(payload); d = _load(p)
    rid = str(payload.get("request_id") or payload.get("id") or "")
    row = d["sessions"].get(rid)
    if not row:
        return {"ok": False, "status": "not_found"}
    row["status"] = "denied"; _save(p, d)
    d.setdefault("audit", []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "deny", "id": rid})
    _save(p, d)
    return {"ok": True, "status": "denied", "request_id": rid}


def _session(payload):
    p = _store(payload); d = _load(p)
    rid = str(payload.get("request_id") or payload.get("id") or "")
    row = d["sessions"].get(rid)
    if not row:
        return {"ok": False, "status": "not_found"}
    if row.get("status") != "approved":
        return {"ok": False, "status": "denied", "error": "远端未同意/已撤销 ⇒ 不发 session",
                "current": row.get("status")}
    sid = "sess-" + secrets.token_hex(6)
    row["status"] = "session"; row["session"] = {"id": sid, "opened_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                  "scope": row["scope"]}
    d.setdefault("audit", []).append({"at": row["session"]["opened_at"], "event": "session", "id": rid, "session": sid})
    _save(p, d)
    return {"ok": True, "status": "session", "request_id": rid, "session": row["session"],
            "note": "授权会话已开；屏幕/输入/语音通道尚未接入（不冒充已远控）"}


def _revoke(payload):
    p = _store(payload); d = _load(p)
    rid = str(payload.get("request_id") or payload.get("id") or "")
    row = d["sessions"].get(rid)
    if not row:
        return {"ok": False, "status": "not_found"}
    row["status"] = "revoked"
    d.setdefault("audit", []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "revoke", "id": rid})
    _save(p, d)
    return {"ok": True, "status": "revoked", "request_id": rid,
            "note": "撤销后 session 不再有效；下一次 session 也必须重新同意"}


def _audit(payload):
    p = _store(payload); d = _load(p)
    return {"ok": True, "events": d.get("audit") or [], "sessions": len(d.get("sessions") or {}), "store": str(p)}


def run(op="status", **kw):
    op = str(op or "status").strip().lower()
    if op == "status":
        p = _store(kw); d = _load(p)
        return {"ok": True, "op": "status", **STATUS, "sessions": len(d.get("sessions") or {}),
                "store": str(p)}
    if op == "where":
        return {"ok": True, "op": "where", **STATUS, "module": "gbt_allinone/tentacle/remote_controller.py",
                "example": "request -> 远端 agent(用户点同意) approve -> session"}
    if op == "request":
        return _request(kw)
    if op == "approve":
        return _approve(kw)
    if op == "deny":
        return _deny(kw)
    if op == "session":
        return _session(kw)
    if op == "revoke":
        return _revoke(kw)
    if op == "audit":
        return _audit(kw)
    return {"ok": False, "op": op, "status": "unknown_op", "error": "未知 op：%s" % op,
            "available": STATUS["ops"], "fail_closed": True}
