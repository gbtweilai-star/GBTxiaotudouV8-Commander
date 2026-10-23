# -*- coding: utf-8 -*-
"""wire-gate -- 接线门：每个「未接线/未读到/缺依赖」项必须有一条**处置**，否则红。
处置四选一（写死，没有第五种）：
  wired      已接线（给证据：文件:行）
  owner_key  待主人发钥匙（给 scope + 命令）
  channel    待通道（写明缺哪条通道 + 谁能开）
  recipe     配方已写（写清改哪个文件、加什么、谁执行）
任何项**没有处置** ⇒ 报红（不许无人认领）。
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
GAPS = [ROOT / "state" / "open-gaps.json", ROOT / "state" / "capbinding-gaps.json"]
DISP = ROOT / "state" / "wire-dispositions.json"
OUT = ROOT / "state" / "wire-gate.json"

SELF_OUT = ("wire-gate.json", "open-gaps.json", "decorations.json", "selfcheck-all.json",
            "capbinding-gaps.json", "tool-paths.json", "wire-dispositions.json", "gap-resolutions.json")

def load():
    items = []
    for f in GAPS:
        if not f.is_file():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for it in (d.get("items") or []):
            if any(s in str(it.get("file") or it.get("cap") or "") for s in SELF_OUT):
                continue
            items.append({"src": f.name, "name": str(it.get("cap") or it.get("file") or "?"),
                          "class": it.get("class", "?"), "text": (it.get("text") or it.get("desc") or "")[:120]})
    return items

def main():
    disp = json.loads(DISP.read_text(encoding="utf-8")) if DISP.is_file() else {}
    table = disp.get("table", {})
    items = load()
    unowned, owned = [], []
    for it in items:
        key = it["name"]
        d = table.get(key)
        if d and d.get("how") in ("wired", "owner_key", "channel", "recipe"):
            owned.append((key, d))
        else:
            unowned.append(it)
    OUT.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "total": len(items),
                               "有处置": len(owned), "无处置": len(unowned),
                               "无处置清单": unowned[:80]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("接线门：共 %d 项 · **有处置 %d** · **无处置 %d**" % (len(items), len(owned), len(unowned)))
    seen = set()
    for it in unowned:
        if it["name"] in seen:
            continue
        seen.add(it["name"])
        print("   RED 无处置: [%s] %s" % (it["class"], it["name"][:60]))
    return 0 if not unowned else 1

if __name__ == "__main__":
    raise SystemExit(main())
