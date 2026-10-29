import json
import os
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ws = r"C:\Users\ADMIN\Desktop\GBT小土豆V8"


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
