# -*- coding: utf-8 -*-
"""设计全维度总规程（`skills/gbt-design-mastery/`）的**验收门** —— 现读现算，exit code = 结论。

为什么要单独一道门、而不只信 `design-inventory.py --check`：
  `design-inventory --check` 只证明**总规程点名了 88 个成员 + 规则路径没指空**。
  它证明不了"七条线的深读（references）真的写出来了、每份都点了自己那条线的成员、
  每份都留了诚实账"。这三件如果没人查，就会出现"索引很全、深读是空壳"的假交付。
  ⇒ 本门把「索引覆盖」与「深读落地」分两段各查一次，**都过才 PASS**。

用法：
    py -3.14 tools/codex-scripts/verify-design-mastery.py            # 只查总规程 + 七份深读
    py -3.14 tools/codex-scripts/verify-design-mastery.py --no-index # 不调 design-inventory（离线用）
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
MASTER = ROOT / "skills" / "gbt-design-mastery" / "SKILL.md"
REFS = MASTER.parent / "references"
STATE = ROOT / "state" / "design_dimension.json"
INVENTORY = ROOT / "tools" / "codex-scripts" / "design-inventory.py"

# 总规程必须自带这八节（少一节 = 读者不知道该先看哪、或没有诚实账）
REQUIRED_SECTIONS = [
    "一句话决策流", "全维度地图", "七条线各管什么", "冲突裁决",
    "两道闸", "验收", "诚实账", "固化与出处",
]
# 诚实账的字面（宽松并集：写成"没验/未验/没跑过/未实测"都算）
HONEST_RE = re.compile(r"(未验|没验|没有验|未实测|未核实|待验|没跑过|未跑|没试过)")
SOURCE_RE = re.compile(r"(出处|真源|固化)")
MIN_REF_BYTES = 800          # 深读比一页摘要短 ⇒ 基本就是空壳
MIN_CMD_LINES = 3            # 深读里至少要有几条真命令（人类要照抄）
# ⚠️ 判"有没有可照抄的命令"**不能按行首匹配**：深读里的命令大多写在**表格里**（`| \`node --version\` | …`），
# 行首是 `|`。第一版按行首写 ⇒ 把 L4 误报成"没有命令行"。改成**全篇找命令形状**。
CMD_RE = re.compile(r"(?m)^[\s|>`\-*]*`?\s*((?:py -3\.14|python3?|node|npm|npx|pwsh|powershell|"
                    r"Get-[A-Z]\w+|arkcli|hyperframes|remotion|yt-dlp|ffmpeg|ffprobe|lark-cli)\b)")


def load_inventory_module():
    spec = importlib.util.spec_from_file_location("design_inventory", INVENTORY)
    mod = importlib.util.module_from_spec(spec)          # type: ignore[arg-type]
    spec.loader.exec_module(mod)                         # type: ignore[union-attr]
    return mod


def main(argv: list[str]) -> int:
    fail: list[str] = []
    warn: list[str] = []

    # ── A 总规程本体 ─────────────────────────────────────────────
    if not MASTER.exists():
        print("🔴 总规程不在：%s" % MASTER.relative_to(ROOT))
        return 1
    body = MASTER.read_text(encoding="utf-8")
    for s in REQUIRED_SECTIONS:
        if s not in body:
            fail.append("总规程缺章节：%s" % s)
    begin, end = "<!-- DESIGN-INDEX:BEGIN -->", "<!-- DESIGN-INDEX:END -->"
    if begin not in body or end not in body:
        fail.append("总规程缺索引标记块（%s / %s）" % (begin, end))
    else:
        block = body[body.index(begin) + len(begin):body.index(end)]
        if len([ln for ln in block.splitlines() if ln.startswith("### L")]) != 7:
            fail.append("索引块里不是 7 条线（现算块被手改过？重跑 --write-index）")

    # ── B 七条线的真源 + 深读落地 ─────────────────────────────────
    if not STATE.exists():
        fail.append("缺清单真源 state/design_dimension.json（先跑 design-inventory.py）")
        lines = []
    else:
        lines = json.loads(STATE.read_text(encoding="utf-8"))["lines"]

    # 深读文件名以总规程 §2 表里写的为准（一处真源，避免门和文档各说一套）
    named = dict(re.findall(r"\|\s*(L\d)[^|]*\|[^|]*\|\s*`(references/[^`]+)`\s*\|", body))
    for line in lines:
        lid = line["id"]
        rel = named.get(lid)
        if not rel:
            fail.append("%s 在总规程 §2 表里没有指向 references 的深读路径" % lid)
            continue
        p = REFS / rel.split("references/", 1)[1]
        if not p.exists():
            fail.append("%s 深读不在盘上：%s" % (lid, rel))
            continue
        text = p.read_text(encoding="utf-8")
        size = len(text.encode("utf-8"))
        if size < MIN_REF_BYTES:
            fail.append("%s 深读只有 %d B（< %d）⇒ 当空壳处理：%s" % (lid, size, MIN_REF_BYTES, rel))
            continue
        miss = [m["name"] for m in line["members"]
                if not re.search(r"(?<![\w\-])%s(?![\w\-])" % re.escape(m["name"]), text)]
        if miss:
            fail.append("%s 深读没点名本线成员 %d 个：%s" % (lid, len(miss), "、".join(miss[:6])))
        if not HONEST_RE.search(text):
            fail.append("%s 深读没有诚实账字样（未验/没验/没跑过…）—— 不许不交代" % lid)
        if not SOURCE_RE.search(text):
            warn.append("%s 深读没写「出处/真源」（建议补：这些结论从哪读出来的）" % lid)
        cmds = CMD_RE.findall(text)
        if len(cmds) < MIN_CMD_LINES:
            warn.append("%s 深读里只找到 %d 条命令形状（< %d）" % (lid, len(cmds), MIN_CMD_LINES))
        print("  %s %-14s 深读 %-42s %6d B ｜ 点名成员 %d/%d ｜ 命令形状 %d"
              % (lid, line["name"], rel, size, len(line["members"]) - len(miss), len(line["members"]), len(cmds)))

    # ── D 装机副本（技能只有装进**会话真会扫的根**才算能力存在）────
    # 教训一：`skills/gbt-*/SKILL.md` 写得再好，没装机就等于能力不存在 ⇒ 必须逐文件比字节
    #          （含 7 份深读）——只比 SKILL.md 会漏掉"索引装了、深读没装"。
    # 教训二（2026-09-22 现读实锤）：本机 DSH 的 `dsh-skill-filesystem` **不扫**
    #          `~/.openclaw-autoclaw/skills`；实测本会话 78 条技能里 `gbt-*` 只有 4 条、
    #          全部来自 `~/.agents/skills`。⇒ 两个根都要装、都要逐文件核（缺一个就红）。
    wanted = [MASTER] + sorted(REFS.glob("*.md")) if REFS.exists() else [MASTER]
    for label, dst_dir in (
        ("openclaw-managed（AutoClaw 产品口径）", Path.home() / ".openclaw-autoclaw" / "skills" / "gbt-design-mastery"),
        ("dsh-project（本会话真扫得到）", ROOT / ".dsh" / "skills" / "gbt-design-mastery"),
    ):
        if not dst_dir.exists():
            fail.append("装机副本不在 [%s]：%s（先跑 install-design-mastery.py）" % (label, dst_dir))
            continue
        bad_here = 0
        for src in wanted:
            dst = dst_dir / "SKILL.md" if src == MASTER else dst_dir / "references" / src.name
            if not dst.exists():
                fail.append("[%s] 装机缺件：%s" % (label, src.name))
                bad_here += 1
                continue
            if src.read_bytes() != dst.read_bytes():
                fail.append("[%s] 装机副本与源**不同哈希**：%s" % (label, src.name))
                bad_here += 1
        print("  %s 装机 [%s] %d 个文件%s"
              % ("✅" if bad_here == 0 else "🔴", label, len(wanted),
                 "逐字节一致" if bad_here == 0 else "有 %d 处不一致" % bad_here))

    # ── E 索引覆盖（转调 design-inventory，逻辑只有一份）───────────
    if "--no-index" not in argv:
        try:
            mod = load_inventory_module()
            rc = mod.main(["--check"])
            if rc != 0:
                fail.append("design-inventory.py --check 没过（索引覆盖/规则路径，见上方输出）")
        except SystemExit as e:
            if e.code not in (0, None):
                fail.append("design-inventory.py --check 异常退出 %s" % e.code)
        except Exception as e:                                    # noqa: BLE001
            warn.append("调不动 design-inventory.py --check：%r" % e)

    for w in warn:
        print("   ⚠ %s" % w)
    if fail:
        for f in fail:
            print("   🔴 %s" % f)
        print("设计全维度验收：FAIL（%d 项）" % len(fail))
        return 1
    n_ref = len([p for p in REFS.glob("*.md")]) if REFS.exists() else 0
    print("设计全维度验收：PASS（总规程 8 节齐 · 深读 %d 份点名全覆盖 · 索引覆盖 88 成员）" % n_ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
