#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""交付清单（只读）：把今天关闭的护照摊成一张「谁驱动 · 谁复核 · 怎么回滚」的画勾表。

为什么要它：护照是**过程账**（我改了什么、凭什么、怎么退），验收时人要的是**一屏能画勾的表**。
本件只读三处：护照 JSON、`boot-selfcheck.py` 的计划表、`monitor-loop.py` 的驱动表。

口径：
  · `驱动` = 这件改动**有没有东西会去跑/去查它**：
      - `常设判据`：文件被 `boot-selfcheck.py` 的计划或判据引用；
      - `常驻驱动`：被 `monitor-loop.py` 引用；
      - `一次性`：都不引用（工具/记账/一次性动作）。
  · `复核` = 护照里的 review 或 `--no-review-reason`；
  · `回滚` = 护照里的 rollback（原样截断）。
输出：`outputs/交付清单/<日期>-变更清单.md` + `state/delivery-checklist.json`
用法：py -3.14 tools/codex-scripts/delivery-checklist.py [--date 2026-10-22]
"""
import argparse
import json
import os
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASSPORTS = os.path.join(ROOT, "gbt_allinone", "store", "framework_changes", "passports")
BOOT = os.path.join(ROOT, "tools", "codex-scripts", "boot-selfcheck.py")
MON = os.path.join(ROOT, "tools", "codex-scripts", "monitor-loop.py")
OUT_JSON = os.path.join(ROOT, "state", "delivery-checklist.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    a = ap.parse_args()
    boot_src = open(BOOT, encoding="utf-8", errors="replace").read() if os.path.isfile(BOOT) else ""
    mon_src = open(MON, encoding="utf-8", errors="replace").read() if os.path.isfile(MON) else ""
    rows = []
    if os.path.isdir(PASSPORTS):
        for f in sorted(os.listdir(PASSPORTS)):
            if not f.endswith(".json"):
                continue
            try:
                p = json.load(open(os.path.join(PASSPORTS, f), encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if not str(p.get("closed_at") or "").startswith(a.date):
                continue
            # 同 passport-audit 的更正：认领文件在 `changed`（dict），不是 `files`
            files = [str(x) for x in (list((p.get("changed") or {}).keys()) or (p.get("files") or []))]
            driven = "一次性"
            for x in files:
                base = os.path.basename(x)
                if base in boot_src:
                    driven = "常设判据"
                    break
                if base in mon_src:
                    driven = "常驻驱动"
            ev = str(p.get("evidence") or "")
            rows.append({
                "id": p.get("id"), "closed_at": str(p.get("closed_at") or "")[:19],
                "driven_by": driven, "files": files,
                "reason": str(p.get("reason") or "")[:90],
                "evidence_head": ev[:70],
                "evidence_ok": "=>" in ev,
                "review": str(p.get("review") or p.get("no_review_reason") or "")[:40],
                "rollback": str(p.get("rollback") or "")[:70],
            })
    # 每件文件只保留一次（同一文件可能被多张护照认领）
    by_file = {}
    for r in rows:
        for f in r["files"]:
            by_file.setdefault(f, []).append(r["id"])
    receipt = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "date": a.date,
               "passports": len(rows), "files": len(by_file),
               "by_driven": {k: sum(1 for r in rows if r["driven_by"] == k)
                             for k in ("常设判据", "常驻驱动", "一次性")},
               "rows": rows}
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT_JSON)

    outdir = os.path.join(ROOT, "outputs", "交付清单")
    os.makedirs(outdir, exist_ok=True)
    md = os.path.join(outdir, "%s-变更清单.md" % a.date)
    lines = ["# %s · 变更清单（验收画勾用）" % a.date, "",
             "> 生成：`py -3.14 tools/codex-scripts/delivery-checklist.py` · %s" % receipt["at"],
             "> 口径：**驱动** = 有没有东西会去跑/去查它（常设判据 / 常驻驱动 / 一次性）；"
             "**复核** = 独立复核人或显式无复核理由；**回滚** = 护照原文。",
             "", "## 汇总", "",
             "| 项 | 读数 |", "|---|---|",
             "| 今日关闭护照 | **%d** 张 |" % len(rows),
             "| 涉及文件（去重） | **%d** 件 |" % len(by_file),
             "| 其中 常设判据 | %d 张 |" % receipt["by_driven"]["常设判据"],
             "| 其中 常驻驱动 | %d 张 |" % receipt["by_driven"]["常驻驱动"],
             "| 其中 一次性（工具/记账） | %d 张 |" % receipt["by_driven"]["一次性"],
             "", "## 逐张（☐ 画勾）", "",
             "| ☐ | 护照 | 驱动 | 件数 | 改了什么（理由） | 证据 | 回滚 |",
             "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: (x["driven_by"], x["closed_at"])):
        lines.append("| ☐ | `%s` | %s | %d | %s | %s | %s |"
                     % (r["id"], r["driven_by"], len(r["files"]), r["reason"],
                        "✅" if r["evidence_ok"] else "❌", r["rollback"]))
    lines += ["", "## 验收怎么用这张表", "",
              "1. 每条一行：**理由**看是不是真事、**证据**看有没有 `命令 => 读数`、**回滚**看能不能照着退；",
              "2. `驱动=一次性` 的（工具/记账）**不会自动跑**——它们只在你手动调时生效，属于「库存」不是「在役」；",
              "3. `驱动=常设判据/常驻驱动` 的才会自己跑；它们坏了要等下一次开机自检/下一轮心跳才暴露。"]
    tmp = md + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, md)
    print("交付清单：%s · 护照 %d 张 · 文件 %d 件（常设判据 %d / 常驻驱动 %d / 一次性 %d）"
          % (a.date, len(rows), len(by_file), receipt["by_driven"]["常设判据"],
             receipt["by_driven"]["常驻驱动"], receipt["by_driven"]["一次性"]))
    print("  人读：%s" % md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
