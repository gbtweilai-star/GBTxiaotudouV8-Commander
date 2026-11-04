# -*- coding: utf-8 -*-
"""补跑 page_scan 两个超时分片里的 20 个能力位（逐个、长超时）。"""
import concurrent.futures as cf
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
HELPER = ROOT / "tools" / "run_payload_one.py"
OUT = ROOT / "state" / "page-scan-tail"
CAPS = ['scan_cap', 'scene_anchor', 'sched_define', 'sched_status', 'sched_tick',
        'scrapling', 'screen_sniff', 'sec_chain', 'sec_defenses', 'sec_llm',
        'sec_scan', 'sec_surface', 'sec_sweeper', 'self_intake', 'selfscan',
        'shared_resources', 'shot_director', 'showcase_ops', 'signature_guard', 'skill_finder']
TIMEOUT = float(sys.argv[1]) if len(sys.argv) > 1 else 420.0


def one(cap):
    t0 = time.time()
    try:
        p = subprocess.run([PY, "-X", "utf8", str(HELPER), str(ROOT), "page_scan",
                            json.dumps({"op": "scan", "caps": [cap], "workers": 1})],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT)
        lines = (p.stdout or "").strip().splitlines()
        data = json.loads(lines[-1]) if lines else {}
        res = data.get("result") or {}
        return {"cap": cap, "ok": bool(data.get("envelope_ok")), "绿": res.get("绿"),
                "黄": res.get("黄"), "红": res.get("红"), "红名单": res.get("红名单") or [],
                "wall_s": round(time.time() - t0, 1), "error": data.get("error")}
    except subprocess.TimeoutExpired:
        return {"cap": cap, "timeout": True, "wall_s": round(time.time() - t0, 1)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(one, CAPS):
            rows.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
    agg = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "count": len(rows),
           "ok": sum(1 for r in rows if r.get("ok")),
           "timeout": sum(1 for r in rows if r.get("timeout")),
           "绿": sum(int(r.get("绿") or 0) for r in rows),
           "黄": sum(int(r.get("黄") or 0) for r in rows),
           "红": sum(int(r.get("红") or 0) for r in rows),
           "rows": rows}
    (OUT / "report.json").write_text(json.dumps(agg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: agg[k] for k in ("ok", "timeout", "绿", "黄", "红")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    raise SystemExit(main())
