"""把 run_op 当门面跑一遍：profile / draft / parse 三条路都要通。"""
import json
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

import gbt_allinone as gbt  # noqa: E402

PATH = ".scratch/oldlinks/links.txt"


def brief(title, obj, keys=None):
    print(f"\n===== {title} =====")
    if keys:
        obj = {k: obj.get(k) for k in keys}
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str)[:900])


def main():
    for op, payload in (
        ("presets", {}),
        ("profile", {"path": PATH}),
        ("draft", {"path": PATH, "plan_name": "old_links_draft"}),
        ("parse", {"path": PATH, "plan_name": "link_index"}),
        ("verify", {"path": PATH, "plan_name": "link_index"}),
        ("vocab", {"values": ["intro", "nlp", "zzz"], "allowed": ["intro", "nlp"]}),
    ):
        env = gbt.run_task("record_grid", {"op": op, **payload}, stamp=False)
        body = env.get("gbt_result", env)
        result = body.get("result") or {}
        print(f"\n########## op={op} | ok={result.get('ok')} | status={body.get('status')}")
        if op == "presets":
            brief("presets", result, ["note"])
            print("preset keys:", sorted(result.get("presets", {})))
        elif op == "profile":
            brief("profile", result, ["ok", "source"])
            print("best:", result["profile"]["best"])
            print("columns:", [(c["index"], c["suggested_kind"], c.get("dotted_pair", False))
                               for c in result["profile"]["columns"]])
        elif op == "draft":
            brief("draft", result, ["ok", "plan"])
            print("warnings:", result["plan"]["warnings"])
        elif op == "parse":
            brief("parse", result, ["ok", "status", "stats", "fingerprint"])
        elif op == "verify":
            brief("verify", result, ["ok", "idempotent", "records", "fingerprint", "reparsed"])
        else:
            brief("vocab", result, ["ok", "checked", "vocab_size", "outside", "outside_ratio"])


if __name__ == "__main__":
    main()
