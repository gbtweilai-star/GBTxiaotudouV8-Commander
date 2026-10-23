#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""规程缺口量具（D3 的尺子）—— 只读，回答「哪些能力位在册但规程没写」。

为什么要它：台账里那句「规程缺口 5 处（data 缺1 · llm 缺2 · security 缺11 · video 缺6）」**没有可复跑的产出物**
（P9：账没有写手必烂）。本件把这句话变成可复跑读数：
  ① 从注册表取每一位的域（`caps_registry.BENIGN_CAPS`，现 341 位 / 30 域）；
  ② 每个域的规程 = `gbt-<域>/SKILL.md`（我方四个技能容器里找第一个存在的）；
  ③ 规程正文里**没点到名字**的位 = 缺口；整域没有规程件 = 域级缺口；
  ④ `UNIMPLEMENTED_CAPS`（幽灵域）单列，不算进「缺口」——它们本来就"只有名字"。

输出：`state/spec-gap-scan.json`（机读）+ `outputs/spec-gap/规程缺口清单.md`（人读）
用法：py -3.14 tools/codex-scripts/spec-gap-scan.py [--json]
"""
import argparse
import json
import os
import re
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = os.path.expanduser("~")
OUT_JSON = os.path.join(ROOT, "state", "spec-gap-scan.json")
OUT_MD = os.path.join(ROOT, "outputs", "spec-gap", "规程缺口清单.md")
CONTAINERS = [
    os.path.join(HOME, ".openclaw-autoclaw", "skills"),
    os.path.join(ROOT, ".dsh", "skills"),
    os.path.join(HOME, ".agents", "skills"),
    os.path.join(ROOT, "skills"),
]


def find_spec(domain):
    for base in CONTAINERS:
        p = os.path.join(base, "gbt-%s" % domain, "SKILL.md")
        if os.path.isfile(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, ROOT)
    from gbt_allinone import caps_registry as CR

    caps = CR.BENIGN_CAPS
    unimplemented = set(getattr(CR, "UNIMPLEMENTED_CAPS", {}) or {})
    by_dom = {}
    for name, v in caps.items():
        dom = str((v or {}).get("domain") or "(无域)")
        by_dom.setdefault(dom, []).append(name)
    for dom in by_dom:
        by_dom[dom].sort()

    rows, total_missing, no_spec = [], 0, []
    for dom in sorted(by_dom):
        spec = find_spec(dom)
        names = by_dom[dom]
        if not spec:
            no_spec.append(dom)
            rows.append({"domain": dom, "caps": len(names), "spec": None,
                         "missing": names, "missing_count": len(names)})
            total_missing += len(names)
            continue
        txt = open(spec, encoding="utf-8", errors="replace").read()
        missing = [n for n in names if not re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(n), txt)]
        total_missing += len(missing)
        rows.append({"domain": dom, "caps": len(names), "spec": os.path.relpath(spec, ROOT)
                     if spec.startswith(ROOT) else spec,
                     "missing": missing, "missing_count": len(missing),
                     "spec_bytes": len(txt)})

    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "registry_caps": len(caps),
        "domains": len(by_dom),
        "specs_found": len(by_dom) - len(no_spec),
        "domains_without_spec": no_spec,
        "missing_total": total_missing,
        "rows": rows,
        "unimplemented_caps": sorted(unimplemented),
        "note": "缺口=「位在册、该域规程 SKILL.md 里没点到名字」；幽灵域单列不计",
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT_JSON)

    if a.json:
        print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False, indent=2))
        return 0

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# 规程缺口清单（D3 的尺子 · 机检）", "",
             "> 生成：`py -3.14 tools/codex-scripts/spec-gap-scan.py` · %s" % out["at"],
             "> 口径：**缺口 = 能力位在注册表里，但它所在域的 `gbt-<域>/SKILL.md` 正文没点到这个名字**。",
             "> 幽灵域（`UNIMPLEMENTED_CAPS`，只有名字没有实现）**单列**，不算缺口。",
             "",
             "## 汇总", "",
             "| 项 | 读数 |", "|---|---|",
             "| 注册表能力位 | %d |" % out["registry_caps"],
             "| 域 | %d |" % out["domains"],
             "| 有规程件的域 | %d |" % out["specs_found"],
             "| **缺口总数（位）** | **%d** |" % out["missing_total"],
             "| 整域没有规程件 | %s |" % ("、".join(no_spec) or "无"),
             "", "## 逐域", "", "| 域 | 位数 | 规程件 | 缺口 |", "|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %d | %s | **%d** |"
                     % (r["domain"], r["caps"], "有" if r.get("spec") else "❌无",
                        r["missing_count"]))
    for r in rows:
        if r["missing_count"]:
            lines += ["", "### `%s` 缺 %d 位" % (r["domain"], r["missing_count"]), ""]
            lines.append("、".join("`%s`" % n for n in r["missing"]))
    if unimplemented:
        lines += ["", "## 幽灵域（单列，不计缺口）", "",
                  "、".join("`%s`" % n for n in sorted(unimplemented))]
    tmp_md = OUT_MD + ".tmp"
    with open(tmp_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp_md, OUT_MD)

    print("规程缺口：注册表 %d 位 / %d 域 · 有规程件 %d 域 · **缺口 %d 位**"
          % (out["registry_caps"], out["domains"], out["specs_found"], out["missing_total"]))
    for r in sorted(rows, key=lambda x: -x["missing_count"])[:8]:
        print("  %-16s 缺 %2d / %2d 位%s" % (r["domain"], r["missing_count"], r["caps"],
                                             "" if r.get("spec") else "（整域无规程件）"))
    print("  人读：%s" % OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
