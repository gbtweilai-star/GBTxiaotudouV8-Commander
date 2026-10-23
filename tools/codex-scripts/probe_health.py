import json
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

import gbt_allinone as gbt  # noqa: E402

r = gbt.run_task("selfscan", {}, stamp=False)
b = r.get("gbt_result", r)["result"]
print("verdict:", b.get("verdict"))
print("routing:", json.dumps(b["sections"]["routing"], ensure_ascii=False))
mods = b["sections"]["modules"]
print("modules:", json.dumps({k: v for k, v in mods.items() if k != "bad"}, ensure_ascii=False))
print("bad modules:", mods.get("bad"))
print("findings:", json.dumps(b.get("findings"), ensure_ascii=False)[:800])
