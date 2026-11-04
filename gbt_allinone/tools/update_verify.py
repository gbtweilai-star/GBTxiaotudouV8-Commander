# -*- coding: utf-8 -*-
# gbt-capability: update_verify  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""更新清单 / 签名校验（P2-13 的可做安全面）。

**只做离线校验，不下载、不安装、不推送**：
  · 清单 schema：app_id/version(semver)/channel/artifact_url(https, 拒私网)/sha256/size/notes；
  · 签名：Ed25519 over canonical JSON（去掉 signature 字段）；没公钥/没签名 = 不可安装；
  · 产物 URL 只校验 https/非私网，**不发请求**；`install_supported=false`；
  · 要真正自动更新，还要主人给签名身份/发布通道/安装器 —— 本件不假装。
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import re
import urllib.parse

SCHEMA = 1
APP_ID = "gbt-xiaotudou-v8"
CHANNELS = ("stable", "beta")
SEMVER_RX = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
SHA_RX = re.compile(r"^[0-9a-f]{64}$")
MAX_SIZE = 2 * 1024 * 1024 * 1024


class UpdateError(ValueError):
    pass


def parse_version(v) -> tuple:
    s = str(v or "").strip()
    m = SEMVER_RX.match(s)
    if not m:
        raise UpdateError("version 必须是 semver（例 8.0.1）")
    return tuple(int(x) for x in m.groups())


def compare_versions(a, b) -> int:
    pa, pb = parse_version(a), parse_version(b)
    return (pa > pb) - (pa < pb)


def _host_ok(url) -> tuple[bool, str]:
    try:
        u = urllib.parse.urlparse(str(url or ""))
    except ValueError:
        return False, "url 解析失败"
    if u.scheme != "https":
        return False, "只许 https 产物地址"
    if u.username or u.password:
        return False, "url 不许内嵌凭据"
    h = (u.hostname or "").strip().lower()
    if not h or h in ("localhost",):
        return False, "host 为空/本机"
    try:
        ip = ipaddress.ip_address(h)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, "拒私网/回环/保留地址"
    except ValueError:
        pass
    return True, ""


def canonical(raw) -> bytes:
    body = {k: v for k, v in raw.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def clean_manifest(raw) -> dict:
    if not isinstance(raw, dict):
        raise UpdateError("manifest 必须是对象")
    if int(raw.get("schema") or 0) != SCHEMA:
        raise UpdateError("schema 只支持 %d" % SCHEMA)
    if str(raw.get("app_id") or "") != APP_ID:
        raise UpdateError("app_id 不匹配（%s）" % APP_ID)
    version = str(raw.get("version") or "").strip()
    parse_version(version)
    channel = str(raw.get("channel") or "stable").lower()
    if channel not in CHANNELS:
        raise UpdateError("channel 只许 %s" % ",".join(CHANNELS))
    ok, why = _host_ok(raw.get("artifact_url"))
    if not ok:
        raise UpdateError("artifact_url: " + why)
    sha = str(raw.get("sha256") or "").lower()
    if not SHA_RX.match(sha):
        raise UpdateError("sha256 必须是 64 位小写 hex")
    try:
        size = int(raw.get("size") or 0)
    except (TypeError, ValueError):
        raise UpdateError("size 必须是整数")
    if not (1 <= size <= MAX_SIZE):
        raise UpdateError("size 范围 1..2GB")
    notes = str(raw.get("notes") or "")[:2000]
    sig = str(raw.get("signature") or "").strip()
    if sig:
        try:
            base64.b64decode(sig, validate=True)
        except Exception:  # noqa: BLE001
            raise UpdateError("signature 不是合法 base64")
    return {"schema": SCHEMA, "app_id": APP_ID, "version": version, "channel": channel,
            "artifact_url": str(raw.get("artifact_url")), "sha256": sha, "size": size,
            "notes": notes, "signature": sig}


def _public_key(pem):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    if not pem:
        raise UpdateError("未配置发布公钥")
    try:
        key = serialization.load_pem_public_key(str(pem).encode("utf-8"))
    except Exception:  # noqa: BLE001
        raise UpdateError("发布公钥 PEM 解析失败")
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise UpdateError("发布公钥必须是 Ed25519")
    return key


def verify_manifest(raw, public_key_pem="", current_version="0.0.0") -> dict:
    m = clean_manifest(raw)
    result = {"ok": True, "manifest": m, "signed": False, "signature_ok": False,
              "verified": False, "newer": False, "install_supported": False,
              "action": "manual_review",
              "note": "只做离线校验；不下载/不安装/不推送"}
    try:
        cur = str(current_version or "0.0.0")
        result["newer"] = compare_versions(m["version"], cur) > 0
    except UpdateError:
        result["newer"] = False
    if not m["signature"]:
        result["reason"] = "unsigned：没有签名，不能作为更新安装"
        return result
    result["signed"] = True
    if not public_key_pem:
        result["reason"] = "未配置发布公钥；只能看到清单，不能验签/不能安装"
        return result
    try:
        key = _public_key(public_key_pem)
        key.verify(base64.b64decode(m["signature"]), canonical(m))
        result["signature_ok"] = True
        result["verified"] = True
        result["action"] = "manual_review"
        result["reason"] = "签名通过；安装器/发布通道仍未接（本件不安装）"
    except UpdateError as e:
        result["reason"] = "验签失败: %s" % e
    except Exception as e:  # noqa: BLE001
        result["reason"] = "验签失败: %s" % type(e).__name__
    return result


def sign_manifest(raw, private_key_pem) -> dict:
    m = clean_manifest(raw)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    try:
        key = serialization.load_pem_private_key(str(private_key_pem).encode("utf-8"), password=None)
    except Exception:  # noqa: BLE001
        raise UpdateError("私钥 PEM 解析失败")
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise UpdateError("私钥必须是 Ed25519")
    m["signature"] = base64.b64encode(key.sign(canonical(m))).decode("ascii")
    return {"ok": True, "manifest": m}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    key = ed25519.Ed25519PrivateKey.generate()
    priv = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()
    pub = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    base = {"schema": 1, "app_id": APP_ID, "version": "8.0.2", "channel": "stable",
            "artifact_url": "https://updates.example.com/gbt/app.zip",
            "sha256": hashlib.sha256(b"x").hexdigest(), "size": 12345,
            "notes": "test"}
    signed = sign_manifest(base, priv)["manifest"]
    r = verify_manifest(signed, pub, "8.0.1")
    ck("验签通过", r["verified"] is True and r["signature_ok"] is True, r)
    ck("版本更新", r["newer"] is True)
    ck("不自动安装", r["install_supported"] is False and r["action"] == "manual_review")
    unsigned = verify_manifest(base, pub, "8.0.1")
    ck("未签名不可安装", unsigned["install_supported"] is False and unsigned["verified"] is False)
    tampered = dict(signed, version="8.0.3")
    ck("篡改验签失败", verify_manifest(tampered, pub, "8.0.1")["verified"] is False)
    ck("无公钥不验签", verify_manifest(signed, "", "8.0.1")["signature_ok"] is False)
    ck("旧版本不更新", verify_manifest(signed, pub, "8.0.3")["newer"] is False)
    ck("http 拒", _raises(lambda: clean_manifest(dict(base, artifact_url="http://x/app.zip"))))
    ck("私网拒", _raises(lambda: clean_manifest(dict(base, artifact_url="https://127.0.0.1/app.zip"))))
    ck("app_id 拒", _raises(lambda: clean_manifest(dict(base, app_id="evil"))))
    ck("sha 形态拒", _raises(lambda: clean_manifest(dict(base, sha256="bad"))))
    ck("semver 拒", _raises(lambda: clean_manifest(dict(base, version="8.0"))))
    ck("schema 拒", _raises(lambda: clean_manifest(dict(base, schema=2))))
    ck("compare", compare_versions("8.0.10", "8.0.2") > 0)
    ck("schema 可达", "app_id" in run("schema") and "install_supported" in run("schema"))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (UpdateError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "app_id": APP_ID, "schema": SCHEMA,
                "channels": list(CHANNELS), "install_supported": False,
                "download": False, "note": "只做离线清单/签名校验；安装器未接"}
    if op == "verify":
        try:
            return verify_manifest(params.get("manifest") or {},
                                   params.get("public_key") or "",
                                   params.get("current_version") or "0.0.0")
        except UpdateError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "sign":
        try:
            return sign_manifest(params.get("manifest") or {},
                                 params.get("private_key") or "")
        except UpdateError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "verify_self":
        return verify()
    raise ValueError("未知 op: %s（schema/verify/sign/verify_self）" % op)
