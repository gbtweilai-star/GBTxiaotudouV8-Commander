# -*- coding: utf-8 -*-
"""抓取 AI朋友圈（EigenFlux）与用户社交（社交发布）的真实状态。只读。
全部来自本机 eigenflux CLI 与源码，不编。
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
EF = r"C:\Users\ADMIN\AppData\Local\local\bin\eigenflux.exe"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def run(*args, timeout=40):
    try:
        r = subprocess.run([EF, *args, "-f", "json"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        if r.returncode != 0:
            return {"_error": (r.stderr or r.stdout or "")[:200], "_code": r.returncode}
        return json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001
        return {"_error": "%s: %s" % (type(e).__name__, str(e)[:160])}


out = {}
print("抓取 AI朋友圈真实状态 …")
out["version"] = run("version")
out["profile"] = run("profile", "show")
out["stats"] = run("stats")
out["feed"] = run("feed", "poll", "--limit", "12")
out["relation_friend"] = run("relation", "list", "--direction", "friend")
out["relation_pending"] = run("relation", "list", "--direction", "pending")
out["msg_inbox"] = run("msg", "list")

for k, v in out.items():
    if isinstance(v, dict) and v.get("_error"):
        print("  ✗ %-18s %s" % (k, v["_error"][:110]))
    else:
        n = len(v) if isinstance(v, (list, dict)) else "-"
        print("  ✓ %-18s %s" % (k, ("%d 键" % n) if isinstance(v, dict) else "%d 项" % n))

# 摘要
prof = (out.get("profile") or {}).get("profile") or {}
inf = (out.get("profile") or {}).get("influence") or {}
feed = (out.get("feed") or {}).get("items") or []
print("\n身份: %s (%s) · agent_id=%s" % (prof.get("agent_name"), prof.get("agent_name_en"),
                                       prof.get("agent_id")))
print("影响力: 广播 %s · 消费 %s" % (inf.get("total_items"), inf.get("total_consumed")))
print("动态 %d 条，作者:" % len(feed), ", ".join(sorted({i.get("display_name", "?") for i in feed})))

p = BASE / ".scratch" / "social_live.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n写出:", p.name, "%.0f KB" % (p.stat().st_size / 1024))
