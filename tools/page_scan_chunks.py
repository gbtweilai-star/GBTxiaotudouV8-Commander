# -*- coding: utf-8 -*-
"""page_scan 分片跑（按能力位 20/片，并行 6）；避免整轮超时。"""
import concurrent.futures as cf
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
HELPER = ROOT / "tools" / "run_payload_one.py"
OUT = ROOT / "state" / "page-scan-chunks"
TIMEOUT = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
SIZE = 10


def one(chunk):
    t0 = time.time()
    try:
        p = subprocess.run([PY, "-X", "utf8", str(HELPER), str(ROOT), "page_scan",
                            json.dumps({"op": "scan", "caps": chunk, "workers": 32})],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT)
        lines = (p.stdout or "").strip().splitlines()
        data = json.loads(lines[-1]) if lines else {}
        res = data.get("result") or {}
        return {"ok": bool(data.get("envelope_ok")), "caps": len(chunk),
                "绿": res.get("绿"), "黄": res.get("黄"), "红": res.get("红"),
                "红名单": (res.get("红名单") or [])[:8],
                "黄名单": (res.get("黄名单") or [])[:30],
                "wall_s": round(time.time() - t0, 1), "error": data.get("error")}
    except subprocess.TimeoutExpired:
        return {"ok": False, "timeout": True, "caps": len(chunk),
                "wall_s": round(time.time() - t0, 1)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pb = json.loads((ROOT / "state/page-bindings.json").read_text(encoding="utf-8"))
    caps = sorted({c for p in pb.get("逐页") or [] for c in (p.get("正向_能力位") or [])
                   if c != "page_scan"})
    chunks = [caps[i:i + SIZE] for i in range(0, len(caps), SIZE)]
    rows = []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(one, chunks):
            rows.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
    agg = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "chunks": len(rows),
           "ok_chunks": sum(1 for r in rows if r.get("ok")),
           "timeout_chunks": sum(1 for r in rows if r.get("timeout")),
           "绿": sum(int(r.get("绿") or 0) for r in rows),
           "黄": sum(int(r.get("黄") or 0) for r in rows),
           "红": sum(int(r.get("红") or 0) for r in rows),
           "red": [x for r in rows for x in (r.get("红名单") or [])],
           "yellow": [x for r in rows for x in (r.get("黄名单") or [])],
           "rows": rows}
    (OUT / "report.json").write_text(json.dumps(agg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: agg[k] for k in ("chunks", "ok_chunks", "timeout_chunks", "绿", "黄", "红")},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
