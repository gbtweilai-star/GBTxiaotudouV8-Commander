# -*- coding: utf-8 -*-
"""设计维度**清单**（现算，供"融会贯通"总规程与验收门使用）。

为什么要单独做一份清单、而不是凭关键词筛：
  "设计全维度"如果靠关键词猜，一定会**多收**（把 arkcli/alchemy 这类只是"涉及图"的也算进来）
  或**漏收**（比如 `media-use`、裸名 `pptx`/`cloudflare` 这种不带前缀的）。
  所以这里把**七条设计线**写死成显式规则，逐线现算成员，产出 `state/design_dimension.json`：
  总规程按它点名，验收门按它查覆盖 —— **两边同一份真源**，不各写一套。

七条线（每条 = 技能前缀 + 工作区规则/素材 + 一个"出口"）：
  L1 定档与审美 · L2 界面实现 · L3 设计稿与设计系统 · L4 动效与合成
  L5 演示与文档 · L6 出图与素材 · L7 视频与成片

用法：
    py -3.14 tools/codex-scripts/design-inventory.py            # 打印 + 写 state/design_dimension.json
    py -3.14 tools/codex-scripts/design-inventory.py --check    # 只检查总规程有没有点名全部成员
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
ATLAS = ROOT / "state" / "skill_atlas.json"
OUT = ROOT / "state" / "design_dimension.json"
MASTER = ROOT / "skills" / "gbt-design-mastery" / "SKILL.md"

# 七条线：prefixes = 技能名前缀（含裸名用 "<name>" 写法）；rules = 工作区规则/素材；outlet = 这条线最终产出什么
LINES: list[dict] = [
    {"id": "L1", "name": "定档与审美", "prefixes": [],
     "names": ["gbt-aesthetic"],
     "rules": ["DESIGN.md", "OUTPUT_RULES.md", "tools/codex-scripts/audit_aesthetic.py",
               "tools/codex-scripts/fixtures/aesthetic-sins.html"],
     "outlet": "三档转盘 + 三轴选型 + AI 味禁令与验收清单"},
    {"id": "L2", "name": "界面实现", "prefixes": ["frontend-", "web-"],
     "rules": ["REDESIGN.md", "UI-check.md", "CODE_INGESTION.md", "design-assets-index/"],
     "outlet": "可跑界面：HTML/App 页面、组件、原型"},
    {"id": "L3", "name": "设计稿与设计系统", "prefixes": ["figma-", "design-"],
     "rules": ["DESIGN.md", "PRD_INGESTION.md", "审美相关skill/design-systems/"],
     "outlet": "设计令牌/设计系统/设计稿 ↔ 代码双向"},
    {"id": "L4", "name": "动效与合成", "prefixes": ["gsap-", "hyperframes-", "remotion-"],
     "rules": [],
     "note": "工作区内**没有**本线可指的规则/素材（原挂的 `visual-asset-director.md` 现读是"
             "「素材视觉审查」面，只在评审里提到 motion 一词，**产权属 L6/L2**，已摘）。"
             "GSAP 真知识落在**装机目录**：`hyperframes-animation/adapters/gsap*.md`"
             "（`~/.agents/skills` 与 `~/.claude/skills` 各一份，约 33 KB，**工作区里没有这份**）"
             "⇒ 读 GSAP 要出工作区。",
     "outlet": "动效与视频合成（HTML 合成 / React / GSAP 三层）"},
    {"id": "L5", "name": "演示与文档", "prefixes": ["pptx-", "glmv-"],
     "names": ["<pptx>"],
     "rules": ["OUTPUT_RULES.md"],
     "outlet": "幻灯片 / 报告 / PDF→网页或幻灯片"},
    {"id": "L6", "name": "出图与素材", "prefixes": ["fal-", "venice-", "autoglm-"],
     "rules": ["visual-asset-director.md", "design-assets-index/"],
     "outlet": "图像/素材产出（含 3D、抠图、超分、修图）"},
    {"id": "L7", "name": "视频与成片", "prefixes": ["video-", "chengfeng-"],
     "rules": [],
     "note": "工作区内**没有**本线专属规则文件（原挂的两件现读都不是规则：`IMAGE_GENERATION.md`"
             "是**生图面 L6** 的规程、全文只在第 38 行提到 video 一次；`render/` 是数字人项目的"
             "**PNG 产物**目录 260 文件 / 57 MB，成片落点是 `video-out/`）—— **产物与落点都不是规则**。"
             "L7 的口径在成员规程里（`gbt-video` / `gbt-video-tools` / `gbt-chengfeng` / `hyperframes-*`）"
             "与总规程 §4 两道闸。",
     "outlet": "成片：剪辑/字幕/配音/导出（含能力域 video 4 位）"},
]


def negctl() -> int:
    """负控：在**自己的一份临时副本**上把一条声明路径改成不存在的，`--check` 必须判红。

    为什么用"改副本、跑副本、删副本"而不是"改真身再靠 finally 还原"：
    后者只要中途被 kill / 断电，**真脚本就留在坏状态里**；而本门的判据正是"声明与盘上是否一致"，
    自己坏了会把整条设计线的验收带偏。所以真身全程零改动，判完还核一遍 sha。
    """
    import hashlib
    import subprocess

    src = Path(__file__).resolve()
    orig = src.read_bytes()
    sha0 = hashlib.sha256(orig).hexdigest()
    copy = src.with_name("_negctl_" + src.name)      # 必须留在同目录，ROOT 才解析得到
 # 锚点**不能原样写在这里**：写全了文件里就有两处（L5 一处 + 本行一处），
    #    `count != 1` 立刻把自己判红（本脚本第一版就是这么自伤的）。拆开拼，运行期等值、文件里不等值。
    anchor = '"rules": ["OUTPUT_RULES' + '.md"],'
    if orig.decode("utf-8").count(anchor) != 1:
        print("🔴 负控锚点不再是唯一一处 —— L5 的 rules 被改过，请更新 negctl 的锚点")
        return 1

    def run(p):
        r = subprocess.run([sys.executable, str(p), "--check"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    wrong = []
    try:
        copy.write_bytes(orig)
        rc, out = run(copy)
        print("   正对照（未改的副本）exit=%d（期望 0）" % rc)
        if rc != 0:
            wrong.append("正对照 exit=%d" % rc)
        copy.write_text(orig.decode("utf-8").replace(
            anchor, '"rules": ["OUTPUT_RULES.md", "fixtures/__definitely_absent__.md"],'),
            encoding="utf-8")
        rc, out = run(copy)
        print("   负对照（声明指向不存在的路径）exit=%d（期望 1）" % rc)
        for ln in out.splitlines():
            if "不在盘" in ln:
                print("      " + ln.strip()[:150])
        if rc != 1:
            wrong.append("负对照没判红（exit=%d）" % rc)
    finally:
        if copy.exists():
            copy.unlink()

    if hashlib.sha256(src.read_bytes()).hexdigest() != sha0:
        wrong.append("真脚本被改动了")
    if wrong:
        print("🔴 负控失败：" + "；".join(wrong))
        return 1
    print("✅ 负控通过：副本未改判绿 · 声明指空判红 · 真脚本 sha 未变、临时副本已清")
    return 0


def main(argv: list[str]) -> int:
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    skills = atlas["skills"]
    out: dict = {"built_from": str(ATLAS.relative_to(ROOT)), "lines": []}
    total = 0
    for line in LINES:
        members = []
        for s in skills:
            n = s["name"]
            for pre in line["prefixes"]:
                if n.startswith(pre):
                    members.append({"name": n, "channel": s.get("channel"),
                                    "desc": (s.get("desc") or "")[:100]})
                    break
        for nm in line.get("names", []):
            bare = nm.strip("<>")
            hit = [s for s in skills if s["name"] == bare]
            if not hit:
                hit = [s for s in skills if s["name"] == bare or s["name"].startswith(bare)]
            for s in hit:
                if not any(m["name"] == s["name"] for m in members):
                    members.append({"name": s["name"], "channel": s.get("channel"),
                                    "desc": (s.get("desc") or "")[:100]})
        rules = []
        for r in line["rules"]:
            p = ROOT / r
            rules.append({"path": r, "exists": p.exists()})
        members.sort(key=lambda m: m["name"])
        total += len(members)
        out["lines"].append({**{k: line[k] for k in ("id", "name", "outlet")},
                             **({"note": line["note"]} if line.get("note") else {}),
                             "members": members, "rules": rules})
    out["total_members"] = total

    if "--check" in argv:
        if not MASTER.exists():
            print("总规程还没写：%s" % MASTER.relative_to(ROOT))
            return 1
        body = MASTER.read_text(encoding="utf-8")
        missing = []
        absent = []
        for line in out["lines"]:
            for m in line["members"]:
                if not re.search(r"(?<![\w\-])%s(?![\w\-])" % re.escape(m["name"]), body):
                    missing.append("%s/%s" % (line["id"], m["name"]))
            for r in line["rules"]:
                # 声明了却不在盘上 = **声明的路径错了**或**那件东西根本没有**。
                # 旧版这里 `continue` 跳过 ⇒ 路径写错也照样 exit 0（实测踩过：
                # L1 的负对照写成 `fixtures/…`，真身在 `tools/codex-scripts/fixtures/…`）。
                # 那种"门说 PASS、声明的素材其实指空"就是假绿，所以现在必须计入失败。
                if not r["exists"]:
                    absent.append("%s/规则:%s" % (line["id"], r["path"]))
                    continue
                if r["path"].split("/")[-1] not in body:
                    missing.append("%s/规则:%s" % (line["id"], r["path"]))
        print("总规程：%s（%d B）" % (MASTER.relative_to(ROOT), MASTER.stat().st_size))
        print("设计线 %d 条 · 成员 %d 个 · 未点名 %d 个 · 声明却不在盘上 %d 件"
              % (len(out["lines"]), total, len(missing), len(absent)))
        for m in missing:
            print("   ✗ 未点名 %s" % m)
        for a in absent:
            print("   🔴 声明却不在盘上 %s（改对路径，或从 LINES 里删掉这个声明）" % a)
        return 1 if (missing or absent) else 0

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("设计维度清单 → %s（%d 条线 · %d 个成员）"
          % (OUT.relative_to(ROOT), len(out["lines"]), total))

    # --write-index：把"全维度地图"写进总规程的**标记块**里（块内由工具现算，块外是人写的散文）。
    # 为什么要这样：88 个成员手抄必走样；而总规程又必须**点名每一个**（验收门就是这么判的）。
    # ⇒ 索引交给工具生成，判断与裁决留给人写 —— 各干各的，谁也不冒充谁。
    if "--write-index" in argv:
        if not MASTER.exists():
            print("总规程不在，先写骨架：%s" % MASTER.relative_to(ROOT))
            return 1
        body = MASTER.read_text(encoding="utf-8")
        begin, end = "<!-- DESIGN-INDEX:BEGIN -->", "<!-- DESIGN-INDEX:END -->"
        if begin not in body or end not in body:
            print("总规程里缺标记块 %s / %s" % (begin, end))
            return 1
        block = [begin, "",
                 "> 本段由 `tools/codex-scripts/design-inventory.py --write-index` **现算生成** —— **别手改**；",
                 "> 改线/加成员请改脚本里的 `LINES` 或图鉴，然后重跑本命令。", ""]
        for line in out["lines"]:
            block.append("### %s %s（%d 个成员）" % (line["id"], line["name"], len(line["members"])))
            block.append("")
            block.append("出口：%s" % line["outlet"])
            block.append("")
            block.append("| 成员 | 通道 | 什么时候用它 |")
            block.append("|---|---|---|")
            for m in line["members"]:
                block.append("| `%s` | %s | %s |" % (m["name"], m["channel"], m["desc"]))
            block.append("")
            block.append("规则/素材：")
            block.append("")
            if line["rules"]:
                for r in line["rules"]:
                    block.append("- `%s` %s" % (r["path"], "✅ 在" if r["exists"] else "🔴 **不在**（现读）"))
            else:
                block.append("- （本线**没有**工作区规则/素材 —— 原因见下）")
            if line.get("note"):
                block.append("")
                block.append("> 说明：%s" % line["note"])
            block.append("")
        block.append(end)
        new = body[:body.index(begin)] + "\n".join(block) + body[body.index(end) + len(end):]
        MASTER.write_text(new, encoding="utf-8")
        print("已把全维度地图写进 %s（%d 字节）" % (MASTER.relative_to(ROOT), len(new.encode("utf-8"))))
    # 逐线摘要是**要给人看的**（旧版写在 `return 0` 后面 ⇒ 死代码，永远不打印）。
    for line in out["lines"]:
        print("  %s %-12s 成员 %2d ｜ 规则/素材 %d 件（缺 %d）｜ 出口：%s"
              % (line["id"], line["name"], len(line["members"]), len(line["rules"]),
                 sum(1 for r in line["rules"] if not r["exists"]), line["outlet"]))
    return 0


if __name__ == "__main__":
    if "--negctl" in sys.argv[1:]:
        raise SystemExit(negctl())
    raise SystemExit(main(sys.argv[1:]))
