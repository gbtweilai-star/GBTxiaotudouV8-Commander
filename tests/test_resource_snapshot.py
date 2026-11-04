# -*- coding: utf-8 -*-
"""resource_snapshot（本机资源快照）契约/统一门/API/面板验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import resource_snapshot as RS  # noqa: E402

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
    print("[1] 契约（归一/范围/真采样）")
    r = RS.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 14", r["checks"] >= 14, r["checks"])
    fx = {"at": "t", "host": "h", "platform": "p", "cpu_percent": 12.5,
          "mem_total_mb": 16000, "mem_used_mb": 8000, "mem_percent": 50,
          "disk_total_gb": 500, "disk_used_gb": 250, "disk_percent": 50,
          "uptime_s": 3600, "process_count": 200}
    n = RS.normalize(fx)
    check("归一", n["cpu_percent"] == 12.5 and n["process_count"] == 200)
    check("CPU 越界拒", _raises(lambda: RS.normalize(dict(fx, cpu_percent=101))))
    check("内存负数拒", _raises(lambda: RS.normalize(dict(fx, mem_used_mb=-1))))
    check("非数字拒", _raises(lambda: RS.normalize(dict(fx, disk_total_gb="x"))))
    check("非对象拒", _raises(lambda: RS.normalize("x")))
    check("process_count 可空", RS.normalize(dict(fx, process_count=None))["process_count"] is None)
    s = RS.snapshot()
    check("真采样", s["ok"] is True, s.get("error"))
    check("CPU 在范围", 0 <= s["cpu_percent"] <= 100)
    check("内存有值", s["mem_total_mb"] > 0 and 0 <= s["mem_percent"] <= 100)
    check("磁盘有值", s["disk_total_gb"] > 0 and 0 <= s["disk_percent"] <= 100)
    check("uptime 非负", s["uptime_s"] >= 0)
    check("host/平台", bool(s.get("host")) and bool(s.get("platform")))
    check("schema 字段", set(RS.run("schema")["fields"]) == set(RS.FIELDS))
    check("未知 op 拒", _raises(lambda: RS.run("teleport")))

    print("[2] 统一门 / API / 面板 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 resource_snapshot", '"resource_snapshot": {' in reg
          and '"handler": "resource_snapshot"' in reg)
    check("api 分派 resource_snapshot", 'kind == "resource_snapshot"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/resources", '"/api/resources"' in srv and "resource_snapshot" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("右栏资源面板", 'id="res-cpu"' in idx and "resource-panel.js" in idx)
    js = (ROOT / "holo_pet_w3/console/resource-panel.js").read_text(encoding="utf-8")
    check("面板只读刷新", "/api/resources" in js and "setInterval" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 resource_snapshot",
              (payload / "gbt_allinone/tools/resource_snapshot.py").is_file()
              and '"resource_snapshot": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/171 存在", (ROOT / "docs/171-resource-snapshot.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— resource_snapshot（ctypes+shutil/范围/可空进程数）+ 统一门/API/面板/APP 全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except (RS.SnapshotError, ValueError):
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("resource_snapshot", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
