# -*- coding: utf-8 -*-
"""page_scan 分片跑：每页一个子进程 + 超时，避免整轮 180s 超时。

用法：python tools/page_scan_shards.py [per_page_timeout]
输出：state/page-scan-shards/report.json
"""
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
HELPER = ROOT / "tools" / "run_payload_one.py"
OUT = ROOT / "state" / "page-scan-shards"
TIMEOUT = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pb = json.loads((ROOT / "state/page-bindings.json").read_text(encoding="utf-8"))
    pages = [str(p.get("页")) for p in pb.get("逐页") or []]
    rows = []
    for page in pages:
        t0 = time.time()
        try:
            p = subprocess.run([PY, "-X", "utf8", str(HELPER), str(ROOT), "page_scan",
                                json.dumps({"op": "scan", "page": page, "workers": 64})],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=TIMEOUT)
            lines = (p.stdout or "").strip().splitlines()
            data = json.loads(lines[-1]) if lines else {}
            res = data.get("result") or {}
            rows.append({"page": page, "ok": bool(data.get("envelope_ok")),
                         "绿": res.get("绿"), "黄": res.get("黄"), "红": res.get("红"),
                         "实探": res.get("实探能力位"), "用时": res.get("用时秒"),
                         "红名单": (res.get("红名单") or [])[:5],
                         "error": data.get("error"), "wall_s": round(time.time() - t0, 1)})
        except subprocess.TimeoutExpired:
            rows.append({"page": page, "ok": False, "timeout": True,
                         "wall_s": round(time.time() - t0, 1)})
        except Exception as e:  # noqa: BLE001
            rows.append({"page": page, "ok": False,
                         "error": "%s: %s" % (type(e).__name__, str(e)[:120]),
                         "wall_s": round(time.time() - t0, 1)})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    ok = sum(1 for r in rows if r.get("ok"))
    red = sum(int(r.get("红") or 0) for r in rows)
    agg = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "pages": len(rows),
           "ok_pages": ok, "timeout_pages": sum(1 for r in rows if r.get("timeout")),
           "red_total": red, "rows": rows}
    (OUT / "report.json").write_text(json.dumps(agg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: agg[k] for k in ("pages", "ok_pages", "timeout_pages", "red_total")},
                     ensure_ascii=False, indent=1))
    return 0 if ok == len(rows) and red == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
