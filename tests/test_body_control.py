# -*- coding: utf-8 -*-
"""body_control（身体控制/触手/全息投影）如实报缺验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import body_control as BC  # noqa: E402

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
    print("[1] 契约：如实 not_supported，不假装能动")
    r = BC.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 15", r["checks"] >= 15, r["checks"])
    st = BC.status({})
    check("默认 not_supported", st["status"] == "not_supported", st["status"])
    check("wired=false", st["wired"] is False)
    check("缺感觉清单", "camera" in st["missing"]["sensors"] and "screen" in st["missing"]["sensors"])
    check("缺执行器清单", "tentacle_bus" in st["missing"]["actuators"]
          and "holographic_projection" in st["missing"]["actuators"])
    m = BC.move("wave")
    check("动作不执行", m["ok"] is False and m["executed"] is False and m["status"] == "not_supported", m)
    check("拒绝写原因", "未接线" in m["reason"])
    s1 = BC.status({"sensors": {"camera": True}})
    check("只有感觉仍 not_supported", s1["status"] == "not_supported")
    s2 = BC.status({"sensors": {k: True for k in BC.SENSORS},
                    "actuators": {k: True for k in BC.ACTUATORS}})
    check("全绑定也只 partial 且 wired=false",
          s2["status"] == "partial" and s2["wired"] is False, s2["status"])
    check("全绑定动作仍不执行", BC.move("walk")["executed"] is False)
    check("schema 域名为 body_control", BC.run("schema")["domain"] == "body_control")
    check("清单有全部传感器", set(BC.inventory({})["sensors"]) == set(BC.SENSORS))
    check("清单有全部执行器", set(BC.inventory({})["actuators"]) == set(BC.ACTUATORS))

    print("[2] 统一门 / API / 右栏 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 body_control", '"body_control": {' in reg
          and '"handler": "body_control"' in reg)
    check("api 分派 body_control", 'kind == "body_control"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/body", '"/api/body"' in srv and "body_control" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("右栏 body_control 状态块", 'id="body-state"' in idx and "body-panel.js" in idx)
    js = (ROOT / "holo_pet_w3/console/body-panel.js").read_text(encoding="utf-8")
    check("UI 只读状态", "/api/body" in js and "not_supported" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 body_control",
              (payload / "gbt_allinone/tools/body_control.py").is_file()
              and '"body_control": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/166 存在", (ROOT / "docs/166-body-control.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— body_control（not_supported/缺感觉/缺执行器/动作 execute=false）+ 统一门/UI/APP 全绿")
    return 0


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("body_control", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
