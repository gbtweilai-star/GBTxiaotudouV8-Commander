# -*- coding: utf-8 -*-
"""技能「发现层」检查器（2026-09-23 立，源自外部设计对照）。

## 由来

读了 `secondsky/claude-skills` 的 `frontend-design`（见
`memory/2026-09-23-外部插件设计对照-frontend-design.md`），它比本仓清楚的地方是
**两层文档分工**：`README.md` 是**发现层**（人怎么找到并放心用），`SKILL.md` 是**执行层**（模型照着做）。
本仓的 `gbt-*` 技能**普遍只有 SKILL.md** ⇒ 缺了一层：**没有"什么时候别用"、没有反模式触发词、
没有预期结果、没有相邻技能导航、没有成熟度时标。**

## 查五条（每一条都能机检）

    ① README.md 在不在
    ② README 里有没有「什么时候别用」（人最需要的那句边界）
    ③ 触发表里有没有**反模式词**（让人说"别给我假绿"能命中纪律件）
    ④ 有没有相邻技能导航（"相关技能"/链接到别的技能）
    ⑤ SKILL.md 头部有没有**成熟度/时标**（Status / Last Updated / 成熟度 / 最后更新）

## 退出码（**为什么默认不判红**）

    默认            只报不判 ⇒ 退出码 0。**理由**：现在是采纳期，全仓几十个技能不可能一夜补完；
                   一上来就全红，等于把一条真判据变成"长期红、没人看"（本仓最恨的那种）。
    `--strict`      有任何一条缺失就退出码 1 —— 补齐期结束后把默认翻成它。
    `--only <名>`   只查一个（补一个验一个时用）。
    `--selftest`    负对照：喂一个"只有 SKILL.md"的假技能，**必须逐条报缺** ⇒ 证明它真能红。

## 为什么不查 SKILL.md 内容质量

那是 `verify-distill.py` / `audit-regulations.py` 的活（覆盖/同哈希/点名位/零编造/结构四面）。
本件**只管发现层**，两件不重叠 —— **不造第三套口径**。
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS = ROOT / "skills"

# 反模式词：**症状词**，不是抽象词。人说"别给我假绿"，得能命中纪律件。
ANTI_PATTERNS = ("假绿", "假故障", "假红", "只读半身", "只登记", "没反应", "静默",
                 "跳过", "绕门", "误报", "错报", "过期", "冲突", "未接线", "说反",
                 "报得出名字", "门说拒了", "不可证伪", "占位", "桩")

WHEN_NOT_RE = re.compile(r"(什么时候别用|什么时候不要用|别用|不要用|不适用|Don'?t\s+Use|When\s+NOT)", re.I)
RELATED_RE = re.compile(r"(相关技能|相邻技能|参见|另见|Related\s+skills|边界|与\s*`?gbt-)", re.I)
MATURITY_RE = re.compile(r"(Status\s*[:：]|Last\s+Updated|成熟度|最后更新|版本\s*[:：])", re.I)


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""


def lint_one(d: Path) -> dict:
    name = d.name
    skill = d / "SKILL.md"
    readme = d / "README.md"
    out = {"skill": name, "missing": [], "have": []}

    if not skill.is_file():
        out["missing"].append("SKILL.md")
        return out
    stext = skill.read_text(encoding="utf-8", errors="replace")

    if readme.is_file():
        out["have"].append("README")
        rtext = readme.read_text(encoding="utf-8", errors="replace")
    else:
        out["missing"].append("README（发现层）")
        rtext = ""

    hay = rtext + "\n" + _frontmatter(stext) + "\n" + stext

    if rtext and WHEN_NOT_RE.search(rtext):
        out["have"].append("什么时候别用")
    else:
        out["missing"].append("什么时候别用")

    anti = [w for w in ANTI_PATTERNS if w in hay]
    if len(anti) >= 3:
        out["have"].append("反模式词×%d" % len(anti))
    else:
        out["missing"].append("反模式触发词（现读 %d 个：%s）" % (len(anti), ",".join(anti) or "无"))

    if rtext and RELATED_RE.search(rtext):
        out["have"].append("相邻技能导航")
    else:
        out["missing"].append("相邻技能导航")

    head = stext
    m = re.match(r"^---\n.*?\n---\n", stext, re.S)
    if m:
        head = stext[m.end():]          # 先剥 frontmatter
    # 🔴 本轮实测踩到：第一版查 `stext[:600]` —— 而 frontmatter 一长（加了触发词注释），
    #    正文里的成熟度头就被挤出前 600 字 ⇒ **明明写了却报"缺"**（假红）。
    #    修法：**先剥 frontmatter 再看正文**，别假设固定偏移。
    if MATURITY_RE.search(head[:800]):
        out["have"].append("成熟度/时标头")
    else:
        out["missing"].append("成熟度/时标头")

    out["score"] = "%d/5" % len(out["have"])
    return out


def _selftest() -> int:
    """负对照：假技能树里放一个"只有 SKILL.md"的，五条必须**逐条**报缺。"""
    import tempfile
    bad = []
    print("=" * 78)
    print("负对照 · 假技能树（只有一个裸 SKILL.md）")
    print("=" * 78)
    with tempfile.TemporaryDirectory(prefix="skill_lint_") as td:
        d = Path(td) / "gbt-fake"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: gbt-fake\n---\n\n啥也没有。\n", encoding="utf-8")
        r = lint_one(d)
    print("  取得：have=%s" % r["have"])
    print("        缺=%s" % r["missing"])
    if len(r["missing"]) != 5:
        bad.append("期望五条全缺，实得 %d 条" % len(r["missing"]))
    for need in ("README（发现层）", "什么时候别用", "相邻技能导航", "成熟度/时标头"):
        if need not in r["missing"]:
            bad.append("没报出：%s" % need)
    if not any(x.startswith("反模式触发词") for x in r["missing"]):
        bad.append("没报出：反模式触发词")
    print("-" * 78)
    if bad:
        print("  🔴 负对照不过：%s" % bad)
        return 1
    print("  ✅ 负对照全过：五条逐条报缺 ⇒ 这个检查器**能红**")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="技能发现层检查（外部设计对照的采纳项）")
    ap.add_argument("--only", default="")
    ap.add_argument("--strict", action="store_true", help="任何一条缺失即退出码 1")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    dirs = [d for d in sorted(SKILLS.iterdir())
            if d.is_dir() and (d / "SKILL.md").is_file()] if SKILLS.is_dir() else []
    if a.only:
        dirs = [d for d in dirs if d.name == a.only]
    if not dirs:
        print("🔴 没找到技能目录（%s）" % SKILLS)
        return 3

    rows = [lint_one(d) for d in dirs]
    full = [r for r in rows if not r["missing"]]
    print("=" * 78)
    print("技能发现层检查（对照 secondsky/claude-skills 的 frontend-design）")
    print("=" * 78)
    print("  技能根 %s · 查到 %d 个技能" % (SKILLS, len(rows)))
    print("  五条要件：README · 什么时候别用 · 反模式触发词 · 相邻技能导航 · 成熟度时标")
    print("-" * 78)
    for r in rows:
        mark = "✅" if not r["missing"] else "⏳"
        print("  %s %-34s %-4s %s" % (mark, r["skill"], r["score"],
                                      ("缺：" + "、".join(r["missing"])) if r["missing"] else "五条齐"))
    print("-" * 78)
    need = {"README（发现层）": 0, "什么时候别用": 0, "相邻技能导航": 0, "成熟度/时标头": 0}
    anti_missing = 0
    for r in rows:
        for m in r["missing"]:
            if m.startswith("反模式触发词"):
                anti_missing += 1
            elif m in need:
                need[m] += 1
    print("  补齐率：五条齐 %d/%d（%.0f%%）" % (len(full), len(rows), 100.0 * len(full) / len(rows)))
    print("  各要件缺多少：%s ｜ 反模式触发词 %d"
          % (" · ".join("%s %d" % (k, v) for k, v in need.items()), anti_missing))
    print("  说明：**默认只报不判**（采纳期，一夜补不完全仓）；`--strict` 才是门。")
    if a.json:
        Path(a.json).write_text(json.dumps(
            {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
             "rows": rows, "full": len(full), "total": len(rows)},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print("  产物: %s" % a.json)
    if a.strict and (len(full) != len(rows)):
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
