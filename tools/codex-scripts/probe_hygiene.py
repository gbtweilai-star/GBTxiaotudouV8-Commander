import json
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

import gbt_allinone as gbt  # noqa: E402

for kind, payload in (("file_hygiene", {}), ("ghost_guard", {})):
    r = gbt.run_task(kind, payload, stamp=False)
    b = r.get("gbt_result", r)["result"]
    print(f"\n===== {kind} =====")
    print(json.dumps({k: v for k, v in b.items() if k != "findings"},
                     ensure_ascii=False, default=str)[:700])
    print("findings:", json.dumps(b.get("findings"), ensure_ascii=False, default=str)[:700])
