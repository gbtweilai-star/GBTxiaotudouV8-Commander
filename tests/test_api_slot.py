# -*- coding: utf-8 -*-
"""api_slot（动态 API 槽定义口）契约/统一门/API/面板验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import api_slot as AS  # noqa: E402

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
    print("[1] 契约：只登记定义，call 永远 not_supported")
    r = AS.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 20", r["checks"] >= 20, r["checks"])
    good = {"name": "weather_api", "method": "GET",
            "url": "https://api.example.com/v1/weather", "timeout": 8,
            "secret_env": "GBT_WEATHER_KEY",
            "params": [{"name": "city", "type": "string", "required": True}]}
    s = AS.validate_slot(good)
    check("https 放行", s["url"].startswith("https://"))
    check("密钥只存 env 名", s["secret_env"] == "GBT_WEATHER_KEY")
    for bad in ({"name": "x", "url": "http://api.example.com"},
                {"name": "x", "url": "https://localhost/x"},
                {"name": "x", "url": "https://127.0.0.1/x"},
                {"name": "x", "url": "https://192.168.1.2/x"},
                {"name": "x", "url": "https://user:pass@api.example.com/x"},
                {"name": "Bad Name", "url": "https://api.example.com"},
                {"name": "x", "url": "https://api.example.com", "method": "DELETE"},
                {"name": "x", "url": "https://api.example.com", "timeout": 999},
                {"name": "x", "url": "https://api.example.com", "secret_env": "sk-live-xxx"}):
        try:
            AS.validate_slot(bad)
            check("坏槽拒 " + str(list(bad)[:2]), False, bad)
        except AS.SlotError:
            check("坏槽拒 " + str(list(bad)[:2]), True)
    reg = AS.SlotRegistry()
    check("注册", reg.register(good)["ok"] and reg.list()["count"] == 1)
    check("删除", reg.remove("weather_api")["ok"] and reg.list()["count"] == 0)
    check("不存在删除拒", reg.remove("nope")["ok"] is False)
    c = AS.call("weather_api")
    check("call 不执行", c["ok"] is False and c["status"] == "not_supported"
          and c["executed"] is False, c)
    check("call 写原因", "未接" in c["reason"])
    ck_reg = AS.SlotRegistry(max_slots=1)
    ck_reg.register(good)
    check("上限", ck_reg.register(dict(good, name="second", url="https://api2.example.com"))["ok"] is False)
    check("schema 有 executor", AS.run("schema")["executor"] == "not_wired")
    check("list 只读", AS.run("list")["executor"] == "not_wired")

    print("[2] 统一门 / API / 面板 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 api_slot", '"api_slot": {' in reg and '"handler": "api_slot"' in reg)
    check("api 分派 api_slot", 'kind == "api_slot"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/slots", '"/api/slots"' in srv and "api_slot" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("右栏 API 槽面板", 'id="api-list"' in idx and "api-slot-panel.js" in idx)
    js = (ROOT / "holo_pet_w3/console/api-slot-panel.js").read_text(encoding="utf-8")
    check("面板只读/标注 not_wired", "/api/slots" in js and "not_wired" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 api_slot",
              (payload / "gbt_allinone/tools/api_slot.py").is_file()
              and '"api_slot": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/169 存在", (ROOT / "docs/169-api-slot.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— api_slot（https-only/拒私网/密钥引用名/参数白名单/call not_supported）+ 统一门/API/UI/APP 全绿")
    return 0


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("api_slot", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
