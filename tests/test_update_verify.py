# -*- coding: utf-8 -*-
"""update_verify（更新清单/签名校验）契约/门/API/面板验收。"""
from __future__ import annotations

import base64
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import update_verify as UV  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:200])


def main() -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    print("[1] 契约（清单/Ed25519/不安装）")
    r = UV.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 14", r["checks"] >= 14, r["checks"])
    key = ed25519.Ed25519PrivateKey.generate()
    priv = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()
    pub = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    base = {"schema": 1, "app_id": UV.APP_ID, "version": "8.0.2", "channel": "stable",
            "artifact_url": "https://updates.example.com/app.zip",
            "sha256": hashlib.sha256(b"x").hexdigest(), "size": 1000, "notes": "test"}
    signed = UV.sign_manifest(base, priv)["manifest"]
    v = UV.verify_manifest(signed, pub, "8.0.1")
    check("签名通过", v["ok"] and v["signature_ok"] and v["verified"], v)
    check("版本更新", v["newer"] is True)
    check("不安装", v["install_supported"] is False and v["action"] == "manual_review")
    check("未签名不可安装", UV.verify_manifest(base, pub, "8.0.1")["install_supported"] is False)
    check("篡改拒", UV.verify_manifest(dict(signed, version="8.0.3"), pub, "8.0.1")["verified"] is False)
    check("无公钥不验签", UV.verify_manifest(signed, "", "8.0.1")["signature_ok"] is False)
    check("旧版不更新", UV.verify_manifest(signed, pub, "8.0.3")["newer"] is False)
    check("http 拒", _raises(lambda: UV.clean_manifest(dict(base, artifact_url="http://x/a.zip"))))
    check("私网拒", _raises(lambda: UV.clean_manifest(dict(base, artifact_url="https://127.0.0.1/a.zip"))))
    check("app_id 拒", _raises(lambda: UV.clean_manifest(dict(base, app_id="evil"))))
    check("sha 形态拒", _raises(lambda: UV.clean_manifest(dict(base, sha256="bad"))))
    check("semver 拒", _raises(lambda: UV.clean_manifest(dict(base, version="8.0"))))
    check("schema 拒", _raises(lambda: UV.clean_manifest(dict(base, schema=2))))
    check("版本比较", UV.compare_versions("8.0.10", "8.0.2") > 0)

    print("[2] 统一门 / API / 面板 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 update_verify", '"update_verify": {' in reg and '"handler": "update_verify"' in reg)
    check("api 分派", 'kind == "update_verify"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/update", '"/api/update"' in srv and "update_verify" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("右栏更新校验面板", 'id="up-manifest"' in idx and "update-panel.js" in idx)
    js = (ROOT / "holo_pet_w3/console/update-panel.js").read_text(encoding="utf-8")
    check("UI 只校验不安装", "/api/update" in js and "install_supported" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 update_verify",
              (payload / "gbt_allinone/tools/update_verify.py").is_file()
              and '"update_verify": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/176 存在", (ROOT / "docs/176-update-verify.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— update_verify（清单/Ed25519/篡改拒/不安装）+ 统一门/API/面板/APP 全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except (UV.UpdateError, ValueError):
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("update_verify", {"op": "verify_self"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
