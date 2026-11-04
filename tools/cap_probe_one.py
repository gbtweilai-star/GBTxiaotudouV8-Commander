# -*- coding: utf-8 -*-
"""单个能力的安全探针子进程：父进程用超时隔离，防某个能力卡死整轮。"""
import json
import sys

ROOT = sys.argv[1]
CAP = sys.argv[2]
OP = sys.argv[3]
sys.path.insert(0, ROOT)

try:
    import gbt_allinone as G
    env = G.run_task(CAP, {"op": OP}, safe=True, probe=True)
    out = {"cap": CAP, "op": OP, "envelope_ok": bool(env.get("ok")),
           "status": env.get("status"), "kind": env.get("kind"),
           "result": (env.get("gbt_result") or {}).get("result") or env.get("result"),
           "error": env.get("error")}
    print(json.dumps(out, ensure_ascii=False, default=str))
except Exception as e:  # noqa: BLE001
    print(json.dumps({"cap": CAP, "op": OP, "envelope_ok": False,
                      "error": "%s: %s" % (type(e).__name__, str(e)[:200])},
                     ensure_ascii=False))
