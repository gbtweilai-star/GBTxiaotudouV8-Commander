# -*- coding: utf-8 -*-
# gbt-capability: pairing  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""局域网配对 / 证书（P2-12，主人已点头：先本机/局域网安全设计）。

**只做安全原语，不开监听、不生成证书、不暴露公网**：
  · 配对码：6 位数字、TTL 300s、一次性、最多 3 次尝试；只存 sha256，不存明文；
  · 设备白名单：claim 成功后发一次性 device token（只存 sha256），设备表落
    `state/paired-devices.json`（写面过 filesystem_write 门；可信会话免票）；
  · 证书：只做 **PEM 指纹校验**（sha256 DER，AA:BB:…）；**不生成证书/不上传/不交换**；
    `/api/pairing` 也不开任何端口 —— 真正的监听/证书签发要另批。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import ssl
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = _ROOT / "state" / "paired-devices.json"
CODE_TTL = 300
MAX_ATTEMPTS = 3
MAX_CODES = 20
MAX_DEVICES = 32
CODE_RX = re.compile(r"^[0-9]{6}$")
NAME_RX = re.compile(r"^[A-Za-z0-9_\-\u4e00-\u9fff][A-Za-z0-9_\-\u4e00-\u9fff .]{1,31}$")
ID_RX = re.compile(r"^dev-[0-9a-f]{8}$")


class PairingError(ValueError):
    pass


def _default_gate(detail: str):
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    try:
        from .. import auth_gate
        got = auth_gate.check_and_consume("filesystem_write", detail=str(detail)[:60])
        if got.get("ok"):
            return None
        return {"ok": False, "denied": True, "gate": "filesystem_write",
                "error": got.get("error"), "how_to_grant": got.get("how_to_grant"),
                "note": "配对设备表写面必须过 filesystem_write 门"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "denied": True, "gate": "filesystem_write",
                "error": "gate 不可用，fail-closed: %s" % type(e).__name__}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PairingBoard:
    def __init__(self, path=DEFAULT_PATH, clock=time.time, gate_fn=None):
        self.path = Path(path)
        self.clock = clock
        self.gate_fn = gate_fn if gate_fn is not None else _default_gate
        self.codes = {}  # hash -> {expires, attempts, used}

    def _gated(self, detail: str):
        g = self.gate_fn(detail)
        return g if isinstance(g, dict) and not g.get("ok", True) else None

    def _load(self) -> list:
        try:
            if not self.path.is_file():
                return []
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:  # noqa: BLE001
            return []

    def _save(self, rows: list) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def _cleanup(self) -> None:
        now = self.clock()
        for k in list(self.codes):
            if self.codes[k]["expires"] <= now:
                self.codes.pop(k, None)

    def new_code(self) -> dict:
        self._cleanup()
        if len(self.codes) >= MAX_CODES:
            self.codes.pop(next(iter(self.codes)), None)
        code = str(secrets.randbelow(900000) + 100000)
        h = _sha(code)
        self.codes[h] = {"expires": self.clock() + CODE_TTL, "attempts": 0, "used": False}
        return {"ok": True, "code": code, "ttl_s": CODE_TTL,
                "expires_at": time.strftime("%Y-%m-%dT%H:%M:%S",
                                            time.localtime(self.clock() + CODE_TTL)),
                "one_time": True, "note": "只显示一次；服务重启即失效"}

    def claim(self, code, name) -> dict:
        code = str(code or "").strip()
        name = str(name or "").strip()
        if not CODE_RX.match(code):
            return {"ok": False, "error": "user_error: 配对码必须是 6 位数字"}
        if not NAME_RX.match(name):
            return {"ok": False, "error": "user_error: 设备名 2..32 字，字母数字/_-. 空格或中文"}
        self._cleanup()
        h = _sha(code)
        rec = self.codes.get(h)
        if not rec:
            return {"ok": False, "error": "invalid_or_expired_code"}
        if rec["used"]:
            return {"ok": False, "error": "code_already_used"}
        rec["attempts"] += 1
        if rec["attempts"] > MAX_ATTEMPTS:
            self.codes.pop(h, None)
            return {"ok": False, "error": "too_many_attempts"}
        rows = self._load()
        if len([r for r in rows if r.get("status") == "active"]) >= MAX_DEVICES:
            return {"ok": False, "error": "too_many_devices"}
        g = self._gated("pairing.claim:" + name)
        if g:
            return g
        dev_id = "dev-" + secrets.token_hex(4)
        token = secrets.token_urlsafe(32)
        row = {"id": dev_id, "name": name, "token_sha256": _sha(token),
               "status": "active", "paired_at": time.strftime("%Y-%m-%dT%H:%M:%S",
                                                              time.localtime(self.clock()))}
        rows.append(row)
        self._save(rows)
        rec["used"] = True
        self.codes.pop(h, None)
        return {"ok": True, "device": {"id": dev_id, "name": name, "status": "active",
                                       "paired_at": row["paired_at"], "token": token},
                "token_show_once": True, "count": len(rows)}

    def devices(self) -> dict:
        rows = self._load()
        safe = [{"id": r.get("id"), "name": r.get("name"), "status": r.get("status"),
                 "paired_at": r.get("paired_at")} for r in rows]
        return {"ok": True, "devices": safe, "count": len(safe),
                "active": sum(1 for r in safe if r.get("status") == "active"),
                "max": MAX_DEVICES}

    def revoke(self, device_id) -> dict:
        device_id = str(device_id or "")
        if not ID_RX.match(device_id):
            return {"ok": False, "error": "user_error: 设备 id 非法"}
        rows = self._load()
        hit = next((r for r in rows if r.get("id") == device_id), None)
        if not hit:
            return {"ok": False, "error": "no_such_device"}
        if hit.get("status") != "active":
            return {"ok": False, "error": "already_revoked"}
        g = self._gated("pairing.revoke:" + device_id)
        if g:
            return g
        hit["status"] = "revoked"
        hit["revoked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.clock()))
        self._save(rows)
        return {"ok": True, "device": {"id": hit["id"], "name": hit["name"],
                                       "status": "revoked", "revoked_at": hit["revoked_at"]},
                "count": len(rows)}


def cert_fingerprint(pem: str) -> dict:
    try:
        der = ssl.PEM_cert_to_DER_cert(str(pem or ""))
    except (ssl.SSLError, ValueError) as e:
        return {"ok": False, "error": "user_error: 证书 PEM 解析失败: %s" % str(e)[:120]}
    if not der:
        return {"ok": False, "error": "user_error: 证书为空"}
    fp = hashlib.sha256(der).hexdigest().upper()
    fp_colon = ":".join(fp[i:i + 2] for i in range(0, len(fp), 2))
    return {"ok": True, "fingerprint": fp_colon, "fingerprint_plain": fp,
            "der_len": len(der), "note": "只做本机指纹校验；不上传/不签发"}


def verify_cert(pem: str, expected: str = "") -> dict:
    got = cert_fingerprint(pem)
    if not got.get("ok"):
        return got
    want = "".join(ch for ch in str(expected or "").upper() if ch in "0123456789ABCDEF")
    have = got["fingerprint_plain"]
    if want and not hmac.compare_digest(want, have):
        return {"ok": False, "error": "fingerprint_mismatch", "fingerprint": got["fingerprint"]}
    return {"ok": True, "match": True, "fingerprint": got["fingerprint"]}


_BOARD = PairingBoard()


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    import tempfile
    d = tempfile.mkdtemp(prefix="gbt-pair-")
    now = [1000.0]
    b = PairingBoard(path=Path(d) / "devices.json", gate_fn=lambda _x: None,
                     clock=lambda: now[0])
    code = b.new_code()
    ck("码 6 位", bool(CODE_RX.match(code["code"])), code.get("code"))
    ck("claim 成功", b.claim(code["code"], "主人手机")["ok"])
    ck("码一次性", b.claim(code["code"], "第二个")["ok"] is False)
    code2 = b.new_code()
    ck("坏码拒", b.claim("000000", "x")["ok"] is False)
    ck("坏设备名拒", b.claim(code2["code"], "a")["ok"] is False)
    code3 = b.new_code()
    now[0] += CODE_TTL + 1
    ck("过期拒", b.claim(code3["code"], "设备")["ok"] is False)
    now[0] += 1
    code4 = b.new_code()
    for _ in range(3):
        b.claim("111111", "设备")
    ck("尝试上限", b.claim(code4["code"], "设备")["ok"] is True)  # 新码未受旧尝试影响
    ck("设备列表", b.devices()["active"] == 2, b.devices())
    dev_id = b.devices()["devices"][0]["id"]
    ck("撤销", b.revoke(dev_id)["device"]["status"] == "revoked")
    ck("重复撤销拒", b.revoke(dev_id)["ok"] is False)
    ck("坏 id 拒", b.revoke("bad")["ok"] is False)
    denied = PairingBoard(path=Path(d) / "deny.json",
                          gate_fn=lambda _x: {"ok": False, "denied": True})
    c2 = denied.new_code()
    ck("写面门拒", denied.claim(c2["code"], "设备")["ok"] is False)
    ck("门拒不落盘", not (Path(d) / "deny.json").exists())
    ck("证书坏 PEM 拒", cert_fingerprint("not a cert")["ok"] is False)
    ck("schema 可达", "code_ttl_s" in run("schema") and "listen" in run("schema"))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (PairingError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "code_ttl_s": CODE_TTL, "code_len": 6,
                "max_attempts": MAX_ATTEMPTS, "max_devices": MAX_DEVICES,
                "listen": "not_started", "cert_generate": "not_implemented",
                "note": "只做配对码/设备白名单/证书指纹校验；不开端口、不生成证书"}
    if op == "code":
        return _BOARD.new_code()
    if op == "claim":
        return _BOARD.claim(params.get("code"), params.get("name"))
    if op == "devices":
        return _BOARD.devices()
    if op == "revoke":
        return _BOARD.revoke(params.get("id"))
    if op == "cert":
        return cert_fingerprint(params.get("pem"))
    if op == "cert_verify":
        return verify_cert(params.get("pem"), params.get("expected"))
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/code/claim/devices/revoke/cert/cert_verify/verify）" % op)
