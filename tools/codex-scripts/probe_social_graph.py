# -*- coding: utf-8 -*-
"""抓可视化所需的真实数据：好友名单 / 好友请求 / 我的资料 / 动态全量。只读。"""
import json
import subprocess
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
EF = r"C:\Users\ADMIN\AppData\Local\local\bin\eigenflux.exe"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run(*a, timeout=45):
    try:
        r = subprocess.run([EF, *a, "-f", "json"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return json.loads(r.stdout) if r.returncode == 0 else {"_error": (r.stderr or r.stdout)[:180]}
    except Exception as e:  # noqa: BLE001
        return {"_error": "%s: %s" % (type(e).__name__, str(e)[:140])}


out = {}
for key, args in (("friends", ("relation", "friends", "--limit", "80")),
                  ("incoming", ("relation", "list", "--direction", "incoming", "--limit", "30")),
                  ("outgoing", ("relation", "list", "--direction", "outgoing", "--limit", "30")),
                  ("profile", ("profile", "show")),
                  ("stats", ("stats",)),
                  ("feed", ("feed", "poll", "--limit", "30")),
                  ("server", ("server", "list"))):
    out[key] = run(*args)
    v = out[key]
    if isinstance(v, dict) and v.get("_error"):
        print("  ✗ %-10s %s" % (key, v["_error"][:110]))
    else:
        n = len(v) if isinstance(v, (list, dict)) else "?"
        print("  ✓ %-10s %s" % (key, ("%d 键" % n) if isinstance(v, dict) else "%d 项" % n))

fr = out.get("friends") or {}
lst = fr.get("friends") or fr.get("items") or fr.get("list") or []
print("\n好友数:", len(lst))
if lst:
    print("首个好友字段:", sorted(lst[0].keys()))
    for f in lst[:8]:
        print("   ", json.dumps(f, ensure_ascii=False)[:170])

p = BASE / ".scratch" / "social_graph.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n写出:", p.name, "%.0f KB" % (p.stat().st_size / 1024))
