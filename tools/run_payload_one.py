# -*- coding: utf-8 -*-
import json
import sys

ROOT = sys.argv[1]
CAP = sys.argv[2]
PAYLOAD = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
sys.path.insert(0, ROOT)
try:
    import gbt_allinone as G
    env = G.run_task(CAP, PAYLOAD, safe=True, probe=True)
    out = {"cap": CAP, "envelope_ok": bool(env.get("ok")),
           "result": (env.get("gbt_result") or {}).get("result") or env.get("result"),
           "error": env.get("error")}
    print(json.dumps(out, ensure_ascii=False, default=str))
except Exception as e:  # noqa: BLE001
    print(json.dumps({"cap": CAP, "envelope_ok": False,
                      "error": "%s: %s" % (type(e).__name__, str(e)[:200])},
                     ensure_ascii=False))
