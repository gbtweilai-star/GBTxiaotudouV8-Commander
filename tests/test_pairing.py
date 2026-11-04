# -*- coding: utf-8 -*-
"""pairing（局域网配对/证书安全原语）契约/门/API/面板验收。"""
from __future__ import annotations

import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import pairing as PG  # noqa: E402

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
    print("[1] 契约（配对码/一次性/设备/证书指纹）")
    r = PG.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 14", r["checks"] >= 14, r["checks"])
    d = pathlib.Path(tempfile.mkdtemp(prefix="gbt-pair-test-"))
    now = [1000.0]
    b = PG.PairingBoard(path=d / "dev.json", gate_fn=lambda _x: None, clock=lambda: now[0])
    c = b.new_code()
    check("6 位码", len(c["code"]) == 6 and c["code"].isdigit())
    claim = b.claim(c["code"], "主人手机")
    check("claim 设备", claim["ok"] and claim["device"]["token"], claim)
    check("码一次性", b.claim(c["code"], "第二个")["ok"] is False)
    check("落盘", (d / "dev.json").is_file())
    check("列表脱敏", "token" not in str(b.devices()), b.devices())
    c2 = b.new_code()
    now[0] += PG.CODE_TTL + 1
    check("过期拒", b.claim(c2["code"], "设备")["ok"] is False)
    c3 = b.new_code()
    check("坏设备名", b.claim(c3["code"], "a")["ok"] is False)
    dev = claim["device"]["id"]
    check("撤销", b.revoke(dev)["device"]["status"] == "revoked")
    check("重复撤销", b.revoke(dev)["ok"] is False)
    denied = PG.PairingBoard(path=d / "deny.json",
                             gate_fn=lambda _x: {"ok": False, "denied": True})
    cd = denied.new_code()
    check("写面门拒", denied.claim(cd["code"], "设备")["ok"] is False)
    check("门拒不落盘", not (d / "deny.json").exists())
    fixture = ROOT / "tests" / "fixtures" / "test-cert.pem"
    pem = fixture.read_text(encoding="utf-8")
    fp = PG.cert_fingerprint(pem)
    check("证书指纹", fp["ok"] and ":" in fp["fingerprint"], fp)
    check("指纹匹配", PG.verify_cert(pem, fp["fingerprint_plain"])["ok"])
    check("指纹不匹配", PG.verify_cert(pem, "00" * 32)["ok"] is False)
    check("坏 PEM 拒", PG.cert_fingerprint("nope")["ok"] is False)

    print("[2] 统一门 / API / 面板 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 pairing", '"pairing": {' in reg and '"handler": "pairing"' in reg)
    check("api 分派 pairing", 'kind == "pairing"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/pairing", '"/api/pairing"' in srv and "pairing" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("右栏配对面板", 'id="pair-code-btn"' in idx and "pairing-panel.js" in idx)
    js = (ROOT / "holo_pet_w3/console/pairing-panel.js").read_text(encoding="utf-8")
    check("UI 生成/claim/撤销", "/api/pairing" in js and "op: \"claim\"" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 pairing",
              (payload / "gbt_allinone/tools/pairing.py").is_file()
              and '"pairing": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/174 存在", (ROOT / "docs/174-pairing-cert.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— pairing（一次性码/尝试上限/设备白名单/撤销/证书指纹）+ 统一门/API/面板/APP 全绿")
    return 0


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("pairing", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
