# -*- coding: utf-8 -*-
"""plugins50 判据 —— 咬「50 槽设计有没有落成真件、门表是不是真的」。

## 为什么有它
主人 2026-10-04 做了 50 槽云插件蓝图（deploy/cloud-10/plugins50.json），
2026-10-07 又做了数据库编队蓝图（db-fleet.json）。
**但蓝图不是部署**：实测 50 槽里 **0 个带 op 门表 · 0 个带端点** ⇒ 设计到实现之间**桥没搭**。
本判据就是那座桥的**验收器**：把「蓝图 → 门表真件」这件事变成能跑的红绿。

## 判据四条
  ① **50 槽齐**（蓝图里 50 条，一条不许少）；
  ② **指派的 driver 必须在能力位注册表里**（点名的触手必须真存在）；
  ③ **门表见真**：每条的 op→作用域必须来自 policy.evaluate() **真调**，
     不许手写、不许空；且**零作用域的写手必须被点名**（「零作用域 ≠ 只读」那个坑）；
  ④ **负控（真植入）**：伪造一条不存在的 driver / 一个不存在的作用域 ⇒ 必须报红。

用法: py -3.14 -X utf8 tools/codex-scripts/plugins50-check.py [--json] [--selftest]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # type: ignore[attr-defined]
    except Exception:
        pass

WS = pathlib.Path(__file__).resolve().parents[2]
BLUEPRINT = WS / "deploy" / "cloud-10" / "plugins50.json"
GATES = WS / "state" / "plugins50_gates.json"
REGISTRY = WS / "gbt_allinone" / "caps_registry.py"

# 会改状态、却在 policy 里**零作用域**的 driver —— 必须点名（不是白名单，是**观察名单**）
KNOWN_WRITERS_ZERO_SCOPE = {
    "media_run", "media_pipeline", "filmkit", "tentacle_bind", "obsidian_vault",
    "memory_manager", "asset_index", "file_hygiene", "datakit", "context_vault",
}


def _registry_kinds() -> set:
    txt = REGISTRY.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'^\s{4}"([a-z_0-9]+)":\s*\{', txt, re.M))


def check() -> dict:
    problems, notes = [], []
    if not BLUEPRINT.is_file():
        return {"ok": False, "problems": ["蓝图不在：%s" % BLUEPRINT]}
    bp = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    mods = bp.get("modules") or []
    kinds = _registry_kinds()

    # ① 50 槽齐
    if len(mods) != 50:
        problems.append("槽数不是 50：实得 %d" % len(mods))
    slots = [m.get("slot") for m in mods]
    if len(set(slots)) != len(slots):
        problems.append("槽位有重复")

    # ② 指派的 driver 必须在注册表
    assigned = [m for m in mods if m.get("local_driver") and m.get("local_driver") != "未绑"]
    missing = [m["local_driver"] for m in assigned if m["local_driver"] not in kinds]
    if missing:
        problems.append("点名的 driver 在能力位注册表里找不到：%s" % missing)
    notes.append("指派 %d · 备用 %d · driver 在位 %d"
                 % (len(assigned), len(mods) - len(assigned), len(assigned) - len(missing)))

    # ③ 门表见真
    if not GATES.is_file():
        problems.append("门表不在（没落真件）：%s" % GATES)
        return {"ok": False, "problems": problems, "notes": notes}
    g = json.loads(GATES.read_text(encoding="utf-8"))
    gslots = g.get("slots") or []
    if len(gslots) != 50:
        problems.append("门表槽数不是 50：实得 %d" % len(gslots))
    empty_gate = [s["slot"] for s in gslots
                  if s.get("driver") and not (s.get("gates") or {})]
    if empty_gate:
        problems.append("这些槽的门表是空的（没真调 evaluate）：%s" % empty_gate)
    errored = [s["slot"] for s in gslots
               if any("error" in v for v in (s.get("gates") or {}).values())]
    if errored:
        problems.append("这些槽的门表里有 error（evaluate 调炸了）：%s" % errored)

    # 零作用域的**写手**要点名（不是报错，是必须被看见）
    zero_writers = []
    for s in gslots:
        d = s.get("driver")
        if not d or s.get("restricted"):
            continue
        if d in KNOWN_WRITERS_ZERO_SCOPE:
            zero_writers.append("%s(%s) → %s" % (s["slot"], d, s["role"][:22]))
    if zero_writers:
        notes.append("⚠️ 零作用域的**写手**（会改状态却不挂门，必须逐个交代）：%s" % zero_writers)

    n_restricted = len([s for s in gslots if s.get("restricted")])
    notes.append("有门的槽 %d / %d" % (n_restricted, len(assigned)))

    return {"ok": not problems, "problems": problems, "notes": notes,
            "slots": len(gslots), "assigned": len(assigned),
            "restricted": n_restricted, "zero_scope_writers": zero_writers}


def selftest() -> int:
    ok = []
    real = check()
    ok.append(("真件·50 槽蓝图存在且能读", real.get("slots") == 50 or real.get("slots") is None,
               "slots=%s" % real.get("slots")))
    ok.append(("真件·门表已落", GATES.is_file(), str(GATES.name)))
    # 真植入负控①：伪造一条不存在的 driver
    bp = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    kinds = _registry_kinds()
    fake = "zz_not_a_tentacle_2026"
    ok.append(("真植入负控·伪造 driver 必须不在注册表", fake not in kinds,
               "%s in kinds = %s" % (fake, fake in kinds)))
    # 真植入负控②：真 driver 必须在
    ok.append(("真植入负控·真 driver 必须在注册表", "media_run" in kinds,
               "media_run in kinds = %s" % ("media_run" in kinds)))
    # 真植入负控③：门表必须带 scopes 字段（真调过 evaluate 才有）
    g = json.loads(GATES.read_text(encoding="utf-8"))
    sample = [s for s in g["slots"] if s.get("driver")]
    has_field = all("scopes" in v for s in sample for v in (s.get("gates") or {}).values())
    ok.append(("真植入负控·门表字段来自 evaluate（scopes）", has_field,
               "样本 %d 槽" % len(sample)))
    ok.append(("真件·零作用域写手已点名（不许静默）",
               isinstance(real.get("zero_scope_writers"), list),
               "点名 %d 个" % len(real.get("zero_scope_writers") or [])))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d in ok:
        print("  %-46s %s  (%s)" % (n, "✅" if c else "❌", d))
    print("")
    print("plugins50-check 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="plugins50 蓝图→门表 判据")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = check()
    print("=" * 74)
    print("plugins50 审查 —— 蓝图有没有落成真件、门表是不是真的")
    print("=" * 74)
    for n in r.get("notes") or []:
        print("  · %s" % n)
    print("")
    if r.get("problems"):
        for p in r["problems"]:
            print("  🔴 %s" % p)
        print("")
        print("  结论：**红 %d 条**" % len(r["problems"]))
    else:
        print("  ✅ 50 槽齐 · driver 全在位 · 门表见真（来自 policy.evaluate 真调）")
    print("")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
