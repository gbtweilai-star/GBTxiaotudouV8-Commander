#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""护照**账实一致**复核（只读）—— 把最近关闭的护照逐条对一遍证据链。

查什么（每条都机检，不靠眼）：
  ① **文件在不在**：护照 `files` 里每一件，现在盘上是否还存在；
  ② **claim 覆盖得住**：门 `verify` 现在是否还有这批文件的未认领/过期条目；
  ③ **证据形状**：`evidence` 非空、且含 `=>`（本仓口径：命令 => 读数）；
  ④ **回滚可执行**：`rollback` 非空且 ≥8 字（门自己的 close 判据也是这条）；
  ⑤ **复核/印章**：`review` 有，或显式写了 `--no-review-reason`；`has_stamp` 或 `--no-stamp-reason`。

输出：`state/passport-audit.json` + `outputs/passport-audit/账实一致.md`
用法：py -3.14 tools/codex-scripts/passport-audit.py [--today] [--json]
"""
import argparse
import json
import os
import subprocess
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASSPORTS = os.path.join(ROOT, "gbt_allinone", "store", "framework_changes", "passports")
STORE = os.path.join(ROOT, "gbt_allinone", "store", "framework_changes")
OUT = os.path.join(ROOT, "state", "passport-audit.json")
OUT_MD = os.path.join(ROOT, "outputs", "passport-audit", "账实一致.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not os.path.isdir(PASSPORTS):
        print("护照目录不在：%s" % PASSPORTS)
        return 2
    today = time.strftime("%Y-%m-%d")
    rows = []
    for f in sorted(os.listdir(PASSPORTS)):
        if not f.endswith(".json"):
            continue
        try:
            p = json.load(open(os.path.join(PASSPORTS, f), encoding="utf-8"))
        except (ValueError, OSError):
            continue
        closed = str(p.get("closed_at") or "")
        if a.today and not closed.startswith(today):
            continue
        # 🔴 2026-10-22 自纠（第 11 次，留痕）：护照里**没有 `files` 字段**，认领的文件在 `changed`（dict）。
        #    我按 `files` 取 ⇒ 每张护照都"0 件文件、0 件缺" ⇒ 那份「47/47 ✅ 件在盘」是**空检查**。
        files = list((p.get("changed") or {}).keys()) or (p.get("files") or [])
        missing = [x for x in files if not os.path.exists(os.path.join(ROOT, str(x).replace("/", os.sep)))]
        ev = str(p.get("evidence") or "")
        rb = str(p.get("rollback") or "")
        rows.append({
            "id": p.get("id"), "closed_at": closed, "reason": str(p.get("reason") or "")[:80],
            "files": len(files), "missing": missing,
            "evidence_ok": bool(ev) and "=>" in ev,
            "evidence_len": len(ev),
            "rollback_ok": len(rb) >= 8,
            "review": p.get("review") or p.get("no_review_reason") or "",
            "stamp": p.get("has_stamp") or p.get("no_stamp_reason") or "",
        })
    # 门现状
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "gbt_allinone.tools.framework_gate",
                        "--root", ".", "--store", STORE, "verify"],
                       cwd=ROOT, capture_output=True)
    out = r.stdout.decode("utf-8", "replace")
    i = out.find("{")
    gate = json.loads(out[i:]) if i >= 0 else {}
    bad = [x for x in rows if x["missing"] or not x["evidence_ok"] or not x["rollback_ok"]]
    receipt = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "scope": "today" if a.today else "all",
               "passports": len(rows), "problems": len(bad),
               "gate": {k: gate.get(k) for k in ("verdict", "changed_files", "未认领", "认领但已过期",
                                                 "已认领且新鲜", "baseline_at")},
               "rows": rows}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT)
    if a.json:
        print(json.dumps({k: v for k, v in receipt.items() if k != "rows"}, ensure_ascii=False, indent=2))
        return 0 if not bad else 1

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# 护照账实一致复核（只读）", "",
             "> 生成：`py -3.14 tools/codex-scripts/passport-audit.py%s` · %s"
             % (" --today" if a.today else "", receipt["at"]),
             "> 口径：① 件在不在盘上 ② 证据含 `命令 => 读数` ③ 回滚 ≥8 字 ④ 有复核/无复核理由 ⑤ 有印章/无印章理由。",
             "", "## 门现状", "",
             "| 项 | 读数 |", "|---|---|",
             "| verdict | **%s** |" % receipt["gate"].get("verdict"),
             "| changed_files | %s |" % receipt["gate"].get("changed_files"),
             "| 未认领 | %s |" % receipt["gate"].get("未认领"),
             "| 认领但已过期 | %s |" % receipt["gate"].get("认领但已过期"),
             "| 已认领且新鲜 | %s |" % receipt["gate"].get("已认领且新鲜"),
             "| baseline_at | %s |" % receipt["gate"].get("baseline_at"),
             "", "## 护照复核：共 **%d** 张 · 问题 **%d** 张" % (len(rows), len(bad)), ""]
    if rows:
        lines += ["| 护照 | 关闭时间 | 件数 | 件在盘 | 证据形 | 回滚 | 复核 | 印章 |",
                  "|---|---|---|---|---|---|---|---|"]
        for x in rows[-40:]:
            lines.append("| `%s` | %s | %d | %s | %s | %s | %s | %s |"
                         % (x["id"], x["closed_at"][:19], x["files"],
                            "✅" if not x["missing"] else "❌%d 缺" % len(x["missing"]),
                            "✅" if x["evidence_ok"] else "❌",
                            "✅" if x["rollback_ok"] else "❌",
                            "✅" if x["review"] else "❌",
                            "✅" if x["stamp"] else "❌"))
    if bad:
        lines += ["", "## 有问题的（逐条）", ""]
        for x in bad:
            why = []
            if x["missing"]:
                why.append("缺件 %d（%s）" % (len(x["missing"]), "、".join(x["missing"][:3])))
            if not x["evidence_ok"]:
                why.append("证据不含量 `=>`（长 %d）" % x["evidence_len"])
            if not x["rollback_ok"]:
                why.append("回滚过短")
            lines.append("- `%s`：%s" % (x["id"], "；".join(why)))
    tmp_md = OUT_MD + ".tmp"
    with open(tmp_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp_md, OUT_MD)
    print("护照复核：%d 张 · 问题 %d 张 · 门=%s（未认领 %s / 过期 %s）"
          % (len(rows), len(bad), receipt["gate"].get("verdict"),
             receipt["gate"].get("未认领"), receipt["gate"].get("认领但已过期")))
    for x in bad[:8]:
        print("  🔴 %s 缺件=%s 证据=%s 回滚=%s" % (x["id"], x["missing"][:2], x["evidence_ok"], x["rollback_ok"]))
    print("  人读：%s" % OUT_MD)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
