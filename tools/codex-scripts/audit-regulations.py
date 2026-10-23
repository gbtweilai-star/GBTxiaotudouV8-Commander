# -*- coding: utf-8 -*-
"""规程体检器：对已交付的每一份深蒸件做**结构 + 诚实面**审计（不是内容对错，那个看 verify-distill）。

为什么要有它：`verify-distill.py` 判的是"两份同哈希 / frontmatter 齐 / 点名能力位真存在 / 该域零遗漏"，
**它不判这份规程有没有"报告层红线"和"未验账"** —— 而这两样正是 Owner 反复要求的东西
（"读数先问这是事实还是我读错了地方"、"不许把没验过的命令写进规程"）。
本器把它们变成可数的读数：**哪几件没有红线节、哪几件没列未验**，一眼看得见。

刻意**不做成硬门**（默认 exit 0）：结构是写法，硬门会把好件判红；
但它把"缺哪一节"逐件列出来，让"补齐"这件事有据可依。

用法：
    py -3.14 tools/codex-scripts/audit-regulations.py            # 全量体检（域 + 簇）
    py -3.14 tools/codex-scripts/audit-regulations.py --strict   # 缺节就非零退出（用于把关）
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"
MANAGED = Path.home() / ".openclaw-autoclaw" / "skills"

# 每份规程"应当有"的四个面（对齐 Objective 与 Owner 的硬要求）
# ⚠️ 判据是**关键词**，所以必须把自然变体都收进来 —— 第一版只认字面"未验"，
# 于是 `gbt-vision`（写的是"没有验过"）、`gbt-tentacle`（写的是"诚实账"）被误判成"缺账"。
# **本器只能证明"有痕迹"，不能证明"账写得对"**；误判要往"收词"这边修，不许放宽成不查。
FACETS = {
    "报告层红线": r"红线|读错|事实|不撒|不假",
    "未验账": r"未验|没验|没有验|未实测|未核实|待验|没跑过|未跑",
    "门/授权": r"授权|作用域|missing_scopes|门",
    "出处/固化": r"出处|固化|图鉴|atlas",
}


def load_map(name: str) -> dict:
    src = OMNI.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return dict(ast.literal_eval(node.value))
    return {}


def audit(skill: str) -> dict:
    path = ROOT / "skills" / skill / "SKILL.md"
    managed = MANAGED / skill / "SKILL.md"
    row: dict = {"skill": skill, "bytes": 0, "lines": 0, "caps": 0, "unverified": 0, "missing": []}
    if not path.exists():
        row["missing"] = ["文件不在"]
        return row
    body = path.read_text(encoding="utf-8")
    row["bytes"] = len(body.encode("utf-8"))
    row["lines"] = body.count("\n") + 1
    row["caps"] = len(set(re.findall(r"five-dim\.py\s+cap\s+([A-Za-z0-9_\-]+)", body)))
    row["unverified"] = len(re.findall(r"未验", body))
    for label, pat in FACETS.items():
        if not re.search(pat, body):
            row["missing"].append(label)
    row["managed"] = managed.exists()
    if row["managed"]:
        row["identical"] = path.read_bytes() == managed.read_bytes()
    else:
        row["identical"] = False
        row["missing"].append("managed 副本不在")
    return row


def main(argv: list[str]) -> int:
    doms = load_map("DISTILLED_DOMAINS")
    clusters = load_map("DISTILLED_CLUSTERS")
    targets: list[tuple[str, str]] = []
    for d, s in sorted(doms.items()):
        targets.append((f"域 {d}", s))
    for c, s in sorted(clusters.items()):
        targets.append((f"簇 {c}", s))
    uniq = sorted({s for _k, s in targets})
    # 🔴 2026-09-22 补：**元/框架件**——既不是职业域、也不是技能簇，但确实交付在盘上。
    # 旧版只按两张登记表枚举 ⇒ `gbt-aesthetic` / `gbt-omni` / `gbt-potato` / `gbt-brain-vault` /
    # `gbt-design-mastery` 这五件**交付了却没有任何一关看它**（"没查"被读成了"没问题"，就是假绿）。
    # 现在按 `skills/` 现读补进来，单独一组，四节照样判。
    registered = set(uniq)
    meta = [d.name for d in sorted((ROOT / "skills").iterdir())
            if d.is_dir() and d.name.startswith("gbt-") and d.name not in registered
            and (d / "SKILL.md").exists()]
    rows = [audit(s) for s in uniq] + [audit(s) for s in meta]

    bad = [r for r in rows if r["missing"]]
    print("=" * 96)
    print("深蒸件体检 · 共 %d 件（域 %d 条映射 / 簇 %d 条映射，去重 %d 件；另加元/框架件 %d 件）"
          % (len(rows), len(doms), len(clusters), len(uniq), len(meta)))
    print("=" * 96)
    print("%-22s %8s %6s %5s %5s  %s" % ("skill", "bytes", "lines", "cap", "未验", "缺什么"))
    for r in rows:
        print("%-22s %8d %6d %5d %5d  %s"
              % (r["skill"], r["bytes"], r["lines"], r["caps"], r["unverified"],
                 "、".join(r["missing"]) if r["missing"] else "—"))
    print("-" * 96)
    print("元/框架件（不在域/簇登记表里，按盘上现读补入）：%s" % ("、".join(meta) if meta else "（无）"))
    tot_u = sum(r["unverified"] for r in rows)
    tot_c = sum(r["caps"] for r in rows)
    print("小计：%d 件 · 合计 %d 行 · 点名过的能力位（去重前）%d 处 · 「未验」标记 %d 处"
          % (len(rows), sum(r["lines"] for r in rows), tot_c, tot_u))
    print("缺节的件：%d / %d%s" % (len(bad), len(rows), "" if bad else " —— 四节齐"))
    for r in bad:
        print("   ✗ %-22s 缺：%s" % (r["skill"], "、".join(r["missing"])))
    print("读法：本器**不判内容对错**（那个看 verify-distill 的覆盖/同哈希/无编造），"
          "只把「红线 / 未验 / 门 / 出处」四个面缺没缺变成可数读数。")
    return 1 if (bad and "--strict" in argv) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
