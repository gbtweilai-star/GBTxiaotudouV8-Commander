#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 spec 改台账（只支持两种安全动作）：改在册故障正文 / 追加一条待拍板。

为什么要有它：这段文字里有 `**`、反引号、中文引号，内联 python 在 PowerShell 里
反复被吃引号（同一个坑踩过三次）。把 spec 写成 JSON 文件，一次就对。

spec 形如：
{
  "fault_updates": {"F9": {"what": "...", "evidence": "...", "state": "..."}},
  "owner_decisions_add": [{"id": "D7", "ask": "...", "why": "..."}]
}

用法：py -3.14 tools/codex-scripts/ledger-apply-spec.py --spec state/ledger-spec.json
"""
import argparse
import json
import os
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "state", "排查台账.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    a = ap.parse_args()
    spec = json.load(open(os.path.join(ROOT, a.spec), encoding="utf-8"))
    led = json.load(open(LEDGER, encoding="utf-8"))
    changed = []

    for fid, patch in (spec.get("fault_updates") or {}).items():
        hit = [f for f in (led.get("open_faults") or []) if str(f.get("id")) == fid]
        if not hit:
            print("跳过 %s：未清故障里没有这条" % fid)
            continue
        for k, v in patch.items():
            hit[0][k] = v
        changed.append("fault:" + fid)

    for item in (spec.get("open_faults_add") or []):
        of = led.setdefault("open_faults", [])
        if any(str(x.get("id")) == str(item.get("id")) for x in of if isinstance(x, dict)):
            print("跳过 %s：已在未清故障里" % item.get("id"))
            continue
        of.append(item)
        changed.append("open_fault:" + str(item.get("id")))

    for item in (spec.get("owner_decisions_add") or []):
        od = led.setdefault("owner_decisions", [])
        if any(str(x.get("id")) == str(item.get("id")) for x in od if isinstance(x, dict)):
            print("跳过 %s：已在待拍板里" % item.get("id"))
            continue
        od.append(item)
        changed.append("decision:" + str(item.get("id")))

    if not changed:
        print("没有可应用的动作")
        return 0

    led.setdefault("log", []).append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "what": "台账按 spec 更新：" + "、".join(changed),
        "text": "spec=%s ｜ 动作：%s" % (a.spec, "、".join(changed)),
        "note": "由 tools/codex-scripts/ledger-apply-spec.py 应用（原子替换）",
    })
    fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(LEDGER))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(led, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, LEDGER)
    print("已应用：%s ｜ open_faults %d · owner_decisions %d"
          % ("、".join(changed), len(led.get("open_faults") or []), len(led.get("owner_decisions") or [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
