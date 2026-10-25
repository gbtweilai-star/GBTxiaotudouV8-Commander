# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
import json
import os
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ws = _GBT_ROOT


def rows(p):
    p = os.path.join(ws, p)
    out = []
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


panel = rows(r".scratch\codex_v2_panel_ledger.jsonl")
mock = rows(r".scratch\codex_v2_panel_probe.mock.jsonl")
print("panel ledger rows:", len(panel))
for r in panel:
    print("  ", json.dumps({k: r.get(k) for k in ("event", "origin", "route_from", "route_to", "received", "raw_value", "type", "method", "frame_bytes", "frame_bytes_hash", "schema_verdict", "kind", "params_keys")}, ensure_ascii=False))
print()
print("mock ledger rows:", len(mock))
for r in mock:
    print("  ", json.dumps(r, ensure_ascii=False)[:260])
print()
print("=== hash cross-check (panel.emit out  vs  mock in) ===")
pe = [r for r in panel if r.get("event") == "panel.emit" and r.get("frame_bytes_hash")]
mi = [r for r in mock if r.get("event") == "mock.in"]
print("panel out frames:", len(pe), "| mock in frames:", len(mi))
for r in pe:
    hit = [m for m in mi if m.get("frame_bytes_hash") == r.get("frame_bytes_hash")]
    print("   %-22s %s  -> mock match %d  method=%s" % (r.get("method"), r.get("frame_bytes_hash"), len(hit), (hit[0].get("method") if hit else "-")))
