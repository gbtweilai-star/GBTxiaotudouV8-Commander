#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""往台账 open_faults 里**追加**本轮新登记的两条（只追加，不动既有条目；原子替换落盘）。"""
import json
import os
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

LEDGER = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\排查台账.json"

NEW = [
    {
        "id": "F22",
        "what": "框架自改门 verify 红：自 2026-10-19 基线以来累计 **294 件**被监视文件变动，其中 **232 件没有自改护照**"
                "（另有 44 件护照已过期、18 件新鲜）⇒ 这些改动没有『原因/证据/独立复核/回滚』四件套",
        "severity": "中",
        "evidence": "py -3.14 -X utf8 -m gbt_allinone.tools.framework_gate verify => verdict=red · changed_files=294 · "
                    "未认领=232 · 认领但已过期=44 · 已认领且新鲜=18（本轮已为自改的 13 件开护照 fc-20261022T043628-748g 并关闭，把 243 降到 232）",
        "state": "待认领（**不许批量造账**：每一批变动要能被一条真实理由覆盖；按模块分批补，一批一张护照）",
    },
    {
        "id": "F23",
        "what": "「镜像多维度排练跑通」这条交付声明（delivery-claims D7）**卡在缺票**：`mirror_rehearse` 要 `process_execute` 时段授权",
        "severity": "中",
        "evidence": "py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap mirror_rehearse --full => "
                    "missing_scopes=[process_execute] · reason=需要人工授权（process_execute）· rc=1",
        "state": "等主人发一张票（终端：python -m gbt_allinone auth grant --scope process_execute --ttl 600）；AI 无权自发票",
    },
]

# 2026-10-22 先例：`open(目标,'w')` 在这份文件上会 EINVAL（宿主持有），必须原子替换。
fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(LEDGER))
with open(LEDGER, encoding="utf-8") as fh:
    led = json.load(fh)
have = {x.get("id") for x in (led.get("open_faults") or []) if isinstance(x, dict)}
added = []
for item in NEW:
    if item["id"] in have:
        continue
    led.setdefault("open_faults", []).append(item)
    added.append(item["id"])
if not added:
    os.unlink(tmp)
    print("两条都已在册，未改")
    sys.exit(0)
with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(led, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
os.replace(tmp, LEDGER)
print("已追加：%s ｜ open_faults 现 %d 条 ｜ 文件 %d 字节"
      % (",".join(added), len(led["open_faults"]), os.path.getsize(LEDGER)))
