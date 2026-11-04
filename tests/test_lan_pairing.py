# -*- coding: utf-8 -*-
"""lan_pairing（局域网监听/自签证书）契约/门/API/APP 验收。"""
from __future__ import annotations

import json
import pathlib
import ssl
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import lan_pairing as LP  # noqa: E402

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
    print("[1] 契约（绑定白名单/证书/端口）")
    r = LP.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 14", r["checks"] >= 14, r["checks"])
    check("loopback 解析", LP.resolve_bind("loopback") == ("127.0.0.1", "loopback"))
    check("拒公网", _raises(lambda: LP.resolve_bind("8.8.8.8")))
    check("拒通配", _raises(lambda: LP.resolve_bind("0.0.0.0")))
    check("拒域名", _raises(lambda: LP.resolve_bind("evil.example.com")))
    d = pathlib.Path(tempfile.mkdtemp(prefix="gbt-lan-test-"))
    cert = LP.ensure_cert(d / "c.pem", d / "k.pem")
    check("生成自签证书", cert.get("ok") and cert.get("created"), cert)
    check("指纹格式", ":" in cert.get("fingerprint", ""))
    check("私钥文件存在", (d / "k.pem").is_file())
    check("不覆盖证书", LP.ensure_cert(d / "c.pem", d / "k.pem").get("created") is False)
    check("停服务幂等", LP.LanServer(port=8767).stop()["ok"])

    print("[2] 真 TLS 监听（loopback 临时端口）")
    seen = {}

    def pair(code, name):
        seen["code"] = code
        if code == "123456":
            return {"ok": True, "device": {"id": "dev-test", "name": name, "token": "tok-test"}}
        return {"ok": False, "error": "bad_code"}

    srv = LP.LanServer(host="loopback", port=8769, cert_path=d / "c.pem", key_path=d / "k.pem",
                       pair_fn=pair, token_ok=lambda t: {"ok": t == "tok-test",
                                                          "device": {"id": "dev-test", "name": "测试"}})
    started = srv.start()
    check("启动监听", started.get("ok") and started.get("running"), started)
    check("只绑回环", started.get("bind") == "127.0.0.1", started.get("bind"))
    check("TLS=true", started.get("tls") is True and started.get("commands") is False)
    url = started.get("url") or ""
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(url + "/api/lan/health", context=ctx, timeout=10) as resp:
            health = json.loads(resp.read().decode())
        check("health", health.get("ok") is True and health.get("fingerprint") == started.get("fingerprint"))
        req = urllib.request.Request(url + "/api/lan/pair",
                                     data=json.dumps({"code": "123456", "name": "x"}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            pair_res = json.loads(resp.read().decode())
        check("LAN pair", pair_res.get("ok") is True and pair_res["device"]["token"] == "tok-test", pair_res)
        req2 = urllib.request.Request(url + "/api/lan/status",
                                      headers={"Authorization": "Bearer tok-test"})
        with urllib.request.urlopen(req2, context=ctx, timeout=10) as resp:
            st = json.loads(resp.read().decode())
        check("带 token status", st.get("ok") is True and st.get("commands") is False)
        try:
            urllib.request.urlopen(url + "/api/lan/status", context=ctx, timeout=10)
            check("无 token 401", False)
        except urllib.error.HTTPError as e:
            check("无 token 401", e.code == 401, e.code)
        req3 = urllib.request.Request(url + "/api/lan/status",
                                      headers={"Authorization": "Bearer bad"})
        try:
            urllib.request.urlopen(req3, context=ctx, timeout=10)
            check("坏 token 401", False)
        except urllib.error.HTTPError as e:
            check("坏 token 401", e.code == 401, e.code)
    finally:
        stopped = srv.stop()
    check("停止监听", stopped.get("ok") and stopped.get("running") is False, stopped)

    print("[3] 统一门 / API / UI / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 lan_pairing", '"lan_pairing": {' in reg and '"handler": "lan_pairing"' in reg)
    check("api 分派 lan_pairing", 'kind == "lan_pairing"' in api)
    check("run_task 可达", _gate_ok())
    srvpy = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/lan", '"/api/lan"' in srvpy and "lan_pairing" in srvpy)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("配对面板启停按钮", 'id="pair-lan-start"' in idx and 'id="pair-lan-stop"' in idx)
    js = (ROOT / "holo_pet_w3/console/pairing-panel.js").read_text(encoding="utf-8")
    check("UI 启停/状态", "/api/lan" in js and "pair-lan-state" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 lan_pairing",
              (payload / "gbt_allinone/tools/lan_pairing.py").is_file()
              and '"lan_pairing": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/175 存在", (ROOT / "docs/175-lan-pairing.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— lan_pairing（只绑私有/回环 + TLS + 一次性码/Bearer + 无命令接口）全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except (LP.LanError, ValueError):
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("lan_pairing", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
