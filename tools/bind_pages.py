# -*- coding: utf-8 -*-
"""页面 ↔ 触手双向绑定生成器（唯一真源）。

主人令：**触手必须和所有页面双向绑定**，不许有漏网之鱼。
做法：
  · 页面 = console 当前 20 个视图 + `/teardown/` 数字人页；
  · 每个页面按域挂能力位（正向）；反向自动由同一份数据生成，保证双向；
  · 每个能力位至少落一个页面；每个页面至少有一个能力位；
  · 写 state/page-bindings.json（page_scan 的唯一源）。

用法：
  python tools/bind_pages.py --apply
  python tools/bind_pages.py --check
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "state" / "page-bindings.json"

# 页面 → 落点 + 域（域用于从注册表现算能力位，不手写能力名）
PAGES = (
    ("chat", "holo_pet_w3/console/index.html", ("llm", "voice", "mind", "ui", "comms")),
    ("caps", "holo_pet_w3/console/index.html", ("system", "framework")),
    ("skills", "holo_pet_w3/console/index.html", ("tentacle", "mind", "tools")),
    ("space", "holo_pet_w3/console/index.html", ("tentacle", "system")),
    ("media", "holo_pet_w3/console/index.html", ("video", "creation", "tools")),
    ("video", "holo_pet_w3/console/index.html", ("video", "creation")),
    ("world", "holo_pet_w3/console/index.html", ("recon", "integration", "tools")),
    ("browser", "holo_pet_w3/console/index.html", ("integration", "tools", "device")),
    ("brain", "holo_pet_w3/console/index.html", ("brain", "llm", "tentacle")),
    ("plug", "holo_pet_w3/console/index.html", ("integration", "tools", "device")),
    ("team", "holo_pet_w3/console/index.html", ("tentacle", "collab")),
    ("mind", "holo_pet_w3/console/index.html", ("mind", "creation")),
    ("stream", "holo_pet_w3/console/index.html", ("mind", "tentacle")),
    ("turns", "holo_pet_w3/console/index.html", ("data", "system")),
    ("scan", "holo_pet_w3/console/index.html", ("security", "system")),
    ("prof", "holo_pet_w3/console/index.html", ("social", "project", "life")),
    ("bounty", "holo_pet_w3/console/index.html", ("finance", "social", "project")),
    ("dash", "holo_pet_w3/console/index.html", ("system",)),
    ("moments", "holo_pet_w3/console/index.html", ("social", "comms")),
    ("teardown", "holo_pet_w3/teardown/index.html", ("creation", "video", "ui")),
)


def registry():
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return BENIGN_CAPS


def build() -> dict:
    caps = registry()
    by_domain = {}
    for name, meta in caps.items():
        by_domain.setdefault(str(meta.get("domain") or "unknown"), []).append(name)
    rows = []
    reverse = {name: [] for name in caps}
    for page, rel, domains in PAGES:
        path = ROOT / rel
        if page == "teardown":
            # 数字人页：显式挂 ref3d + digital_human，再并 creation/video/ui 域
            picked = set(["ref3d", "digital_human"])
        else:
            picked = set()
        for d in domains:
            picked.update(by_domain.get(d, []))
        picked = [c for c in caps if c in picked]
        if not picked:
            picked = ["cap_self"]
        picked.sort()
        for cap in picked:
            reverse.setdefault(cap, []).append(page)
        rows.append({"页": page, "落点": rel, "落点在盘": path.is_file(),
                     "方向": "双向", "正向_能力位": picked,
                     "反向_页面": []})
    # 每个能力位至少落一页（未覆盖的补到 dash，并反向写回）
    dash = next(r for r in rows if r["页"] == "dash")
    for cap in sorted(caps):
        if not reverse.get(cap):
            dash["正向_能力位"].append(cap)
            reverse[cap].append("dash")
    for r in rows:
        r["正向_能力位"] = sorted(set(r["正向_能力位"]))
        # 反向 = 这些能力位还落在哪些页面（双向同一次生成）
        r["反向_页面"] = sorted({pg for c in r["正向_能力位"]
                                for pg in reverse.get(c, []) if pg != r["页"]})
    # 反向：能力位 → 页面（唯一真源，与正向同一次生成）
    cap_rows = [{"能力位": c, "页面": sorted(set(reverse[c])),
                 "双向": True} for c in sorted(reverse)]
    bound_pages = sum(1 for r in rows if r["正向_能力位"])
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "口径": "页面 ↔ 能力位双向；每页至少 1 根，每根至少 1 页；正向/反向同一次生成",
            "页数": len(rows), "绑好": bound_pages, "未绑好": len(rows) - bound_pages,
            "能力位数": len(caps), "能力位落页": len(cap_rows),
            "逐页": rows, "能力位": cap_rows}


def check(d: dict) -> dict:
    caps = registry()
    pages = {r["页"] for r in d.get("逐页") or []}
    bad = []
    for r in d.get("逐页") or []:
        if not r.get("落点在盘"):
            bad.append("%s 落点不在盘" % r["页"])
        if not r.get("正向_能力位"):
            bad.append("%s 无能力位" % r["页"])
        for c in r.get("正向_能力位") or []:
            if c not in caps:
                bad.append("%s 引用未登记能力位 %s" % (r["页"], c))
    for c in caps:
        hit = [r["页"] for r in d.get("逐页") or [] if c in (r.get("正向_能力位") or [])]
        if not hit:
            bad.append("能力位 %s 没有落任何页" % c)
    return {"ok": not bad and d.get("页数") == len(PAGES),
            "页数": d.get("页数"), "能力位数": len(caps),
            "绑好": d.get("绑好"), "未绑好": d.get("未绑好"),
            "pages": sorted(pages), "bad": bad[:40]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ns = ap.parse_args(argv)
    if ns.check:
        d = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
        r = check(d)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    d = build()
    r = check(d)
    if ns.apply:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("wrote", OUT)
    print(json.dumps({"ok": r["ok"], "页数": r["页数"], "绑好": r["绑好"],
                      "未绑好": r["未绑好"], "能力位落页": d["能力位落页"],
                      "bad": r["bad"][:10]}, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
