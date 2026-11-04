# -*- coding: utf-8 -*-
"""AI 朋友圈 · 账号与注册口（2026-11-02）

每个用户一份独立数据：state/moments/<account_id>.json
账号表：state/moments-accounts.json（密码只存 PBKDF2 哈希 + 随机盐）
本机老数据（state/moments.json）迁移成 auto 账号，别人注册的新账号从干净朋友圈开始。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
ACCOUNTS = STATE / "moments-accounts.json"
DATA_DIR = STATE / "moments"
LEGACY = STATE / "moments.json"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               bytes.fromhex(salt), 120000).hex()


def ensure() -> dict:
    if not ACCOUNTS.is_file():
        _write(ACCOUNTS, {"version": 1, "accounts": []})
    d = _read(ACCOUNTS, {"version": 1, "accounts": []})
    d.setdefault("accounts", [])
    return d


def migrate_legacy() -> dict | None:
    """把本机老 moments.json 迁成 owner 账号（只跑一次，不匹配就不动）。"""
    d = ensure()
    if any(a.get("legacy") for a in d["accounts"]):
        return next(a for a in d["accounts"] if a.get("legacy"))
    if not LEGACY.is_file():
        return None
    salt = secrets.token_hex(16)
    acc = {"id": "owner", "user": "owner", "display": "主人",
           "salt": salt, "pass": _hash("gbt-owner", salt),
           "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "color": "#c96442", "bio": "本机主人", "auto": True, "legacy": True}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        DATA_DIR.joinpath("owner.json").write_text(
            LEGACY.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    d["accounts"].append(acc)
    _write(ACCOUNTS, d)
    return acc


def public(acc: dict) -> dict:
    return {"id": acc["id"], "user": acc["user"], "display": acc["display"],
            "color": acc.get("color") or "#c96442", "bio": acc.get("bio") or ""}


def list_public() -> list:
    return [public(a) for a in ensure()["accounts"]]


def resolve(header: str | None) -> dict | None:
    accounts = ensure()["accounts"]
    if header:
        for a in accounts:
            if header in (a.get("id"), a.get("user")):
                return a
    for a in accounts:
        if a.get("auto"):
            return a
    return None


def data_path(acc_id: str) -> Path:
    return DATA_DIR / (re.sub(r"[^A-Za-z0-9_-]", "_", acc_id) + ".json")


def auth_state() -> dict:
    return {"ok": True, "needs_auth": True, "current": None,
            "accounts": list_public(), "posts": [], "contacts": [], "dms": {},
            "notifications": [], "stats": {"posts": 0, "likes": 0, "comments": 0,
                                           "broadcasts": 0, "unread": 0, "contacts": 0}}


def _clean_seed(display: str) -> dict:
    from gbt_allinone import moments_hub as MH
    d = MH._default()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    d["posts"] = [{
        "id": "m-welcome", "author_id": "c1", "author": "千手", "kind": "moment",
        "text": "欢迎 %s 开通自己的 AI 朋友圈。这里是你的独立空间，不会混入别人的动态。" % display,
        "at": now, "likes": 1, "liked_by": [], "tags": ["新朋友"],
        "visibility": "public", "pinned": False}]
    d["comments"] = {}
    d["dms"] = {}
    d["notifications"] = [{"id": "n-welcome", "type": "welcome",
                            "text": "账号已创建，数据只存在你这台机器。",
                            "at": now, "read": False, "ref": ""}]
    return d


def register(body: dict) -> dict:
    user = str(body.get("user") or "").strip()
    display = str(body.get("display") or user).strip() or user
    password = str(body.get("password") or "")
    if not re.match(r"^[A-Za-z0-9_\-\u4e00-\u9fa5]{2,20}$", user):
        return {"ok": False, "error": "账号 2-20 位，只能字母/数字/下划线/中文"}
    if len(password) < 4:
        return {"ok": False, "error": "密码至少 4 位"}
    d = ensure()
    if any(a["user"].lower() == user.lower() for a in d["accounts"]):
        return {"ok": False, "error": "这个账号已经被注册了"}
    salt = secrets.token_hex(16)
    acc = {"id": "u-%d" % int(time.time() * 1000), "user": user, "display": display[:24],
           "salt": salt, "pass": _hash(password, salt),
           "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "color": "#4f8fd6", "bio": "", "auto": False}
    d["accounts"].append(acc)
    _write(ACCOUNTS, d)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _write(data_path(acc["id"]), _clean_seed(display))
    return {"ok": True, "current": public(acc), "created": True}


def login(body: dict) -> dict:
    user = str(body.get("user") or "").strip()
    password = str(body.get("password") or "")
    for a in ensure()["accounts"]:
        if a["user"].lower() != user.lower():
            continue
        if a.get("legacy") and not password:
            return {"ok": True, "current": public(a)}
        if _hash(password, a["salt"]) == a["pass"]:
            return {"ok": True, "current": public(a)}
        return {"ok": False, "error": "密码不对"}
    return {"ok": False, "error": "没有这个账号，先注册"}


def handle(op: str, body: dict) -> dict:
    if op == "register":
        r = register(body)
        if r.get("ok"):
            r.update(auth=False)
        return r
    if op == "login":
        return login(body)
    if op == "logout":
        return {"ok": True, "needs_auth": True, "accounts": list_public()}
    if op == "accounts":
        return {"ok": True, "accounts": list_public()}
    return {"ok": False, "error": "unknown auth op"}
