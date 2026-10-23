#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""D3 落地后的记账（原子替换）：
   · `not_done` 的 N2（规程缺口 5 处）改写为「已做：149→1」；
   · `owner_decisions` 的 D3 标 `已落地`（不是"待你拍板"了）；
   · 新增一条 `owner_decisions` D15：仅剩的 image_video 整域无规程件怎么处置（建规程 / 并入 creation）。
"""
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
L = os.path.join(ROOT, "state", "排查台账.json")
j = json.load(open(L, encoding="utf-8"))
now = time.strftime("%Y-%m-%dT%H:%M:%S%z")

for x in (j.get("not_done") or []):
    if x.get("id") == "N2":
        x["state"] = "已做（2026-10-22）"
        x["what"] = ("（**已做**）规程缺口：`spec-gap-scan.py` 量出 **149 位**（341 位/30 域，旧账的“5 处”作废），"
                     "`spec-gap-patch.py` 由生成器给 **17 个域**的 `SKILL.md` 写入 `caps-auto` 位清单段（共 148 位，"
                     "**17 份备份**在 `state/skill-backup/`）⇒ 复量 **149 → 1**。"
                     "仅剩 `image_video` **整域无规程件**（1 位），已单列 D15。")
        x["evidence"] = ("py -3.14 tools/codex-scripts/spec-gap-patch.py --apply => 17 个 SKILL.md 已写（148 位）｜ "
                         "spec-gap-scan.py 复量 => 缺口 149 → 1（仅 image_video）｜ omni.py build => 图鉴 341 位 / 406 技能未受影响")
        x["annotated_at"] = now

for d in (j.get("owner_decisions") or []):
    if str(d.get("id")) == "D3":
        d["landed_at"] = now
        d["landed_how"] = ("按设计走甲：生成器写「域内位清单」段（幂等、可回滚），149 → 1；"
                           "不是手抄 149 条（P9：手抄必烂）")
        d["evidence"] = ("state/spec-gap-patch.json（17 份文件前后 sha256 + 备份路径）· state/skill-backup/ 17 份 .bak · "
                         "spec-gap-scan.py 复量缺口 1")

od = j.setdefault("owner_decisions", [])
if not any(str(d.get("id")) == "D15" for d in od):
    od.append({
        "id": "D15",
        "ask": ("`image_video` 域**整域没有规程件**（该域 1 位能力位，其余 148 位已由自动清单补齐）。"
                "选一个：甲=新建 `gbt-image_video/SKILL.md`（按本仓规矩要过六腿：登记/分派/图鉴/触手/绑定/记忆页）· "
                "乙=把该位并入 `creation` 域（改注册表 domain）· 丙=挂账不补（spec-gap 判据会一直报 1）"),
        "why": "这是 D3 落地后**唯一剩下的规程缺口**。它不是「没写」，是「这个域从来没有规程件」——"
                "补它等于新建一份技能，牵涉六腿绑定，所以不自己动。",
        "created_at": now,
    })

fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(L))
with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(j, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
os.replace(tmp, L)
print("已记账：N2→已做 · D3→已落地 · 新增 D15（image_video 整域无规程件）")
print("open_faults %d · not_done %d · owner_decisions %d"
      % (len(j.get("open_faults") or []), len(j.get("not_done") or []), len(od)))
