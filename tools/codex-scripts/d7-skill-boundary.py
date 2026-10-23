#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""D7 分界线 —— 把我方「未入账」技能分成三堆：**该补** / **该划例外** / **待定**（只读）。

为什么要有它（D7 现状）：
  技能面盘点量出我方自营+托管 1335 个技能，其中 **235 个不在 `state/skill_atlas.json`**。
  主人要决定「补进图鉴 / 划例外 / 只补自营」，而 235 个不适合用眼睛一个个看。
  本件只做分类**依据**（路径、来源、同名重复），不写任何账、不改图鉴。

三堆口径（写死，可复核）：
  · 该划例外：路径里出现 `_upstream` / `vendor` / `third_party` / `archive` / `.backups`
    / `node_modules` / `site-packages` / `_stale` —— 这些是**上游参考或存档**，不是我们作者的技能；
  · 该补：路径在**本仓自营**面（`<仓>/skills`、`<仓>/plugins/**/skills`）或**托管**面
    （`~/.openclaw-autoclaw/skills`、`~/.dsh/.agent-presets/**/skills`），且不与别人同名；
  · 待定：以上都不符合（通常是**同名重复**、或路径来历不明）。

用法：py -3.14 tools/codex-scripts/d7-skill-boundary.py [--json]
"""
import argparse
import json
import re
import os
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = os.path.expanduser("~")
INV = os.path.join(ROOT, "state", "skill-surface-inventory.json")
OUT_MD = os.path.join(ROOT, "outputs", "skill-surface", "D7-分界线.md")
OUT_JSON = os.path.join(ROOT, "state", "d7-skill-boundary.json")

SKIP = {".git", "node_modules", "__pycache__", ".venv", ".venv-sadtalker", "site-packages"}
OURS_MARKERS = ("skills",)
EXCEPTION_MARKERS = ("_upstream", "vendor", "third_party", "archive", ".backups",
                     "node_modules", "site-packages", "_stale", "_archive")


def atlas_names():
    p = os.path.join(ROOT, "state", "skill_atlas.json")
    if not os.path.isfile(p):
        return set()
    try:
        j = json.load(open(p, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return set()
    rows = j if isinstance(j, list) else (j.get("skills") or j.get("rows") or [])
    out = set()
    for r in rows:
        if isinstance(r, str):
            out.add(r)
        elif isinstance(r, dict):
            for k in ("name", "id", "slug"):
                if r.get(k):
                    out.add(str(r[k]))
    return out


def ours_skill_dirs():
    """我方面（本仓自营 / 托管）里的技能目录 —— **只扫指定的容器**。

    🔴 2026-10-22 自纠（第一次跑就发现两把尺子打架，留痕）：
      第一版把 `ROOT` 整棵树递归扫 ⇒ 连 `_upstream/` / `vendor/` / `third_party/` 里的
      上游副本都算成"我方技能"，量出 2744 个目录 / 1746 个未入账；
      而 `skill-surface-inventory.py` 只按"我方容器"统计，是 1335 / 235。
      两个数不一样不是因为盘变了，是因为**"我方"的定义不同**。
      现口径（与盘点器对齐，写死）：**我方 = 这四个容器**
        `<仓>/skills` · `<仓>/plugins/**/skills` · `~/.openclaw-autoclaw/skills`
        · `~/.dsh/.agent-presets/**/skills`
      容器外的（`_upstream`/`vendor`/`third_party`/存档）一律算**上游参考**，进"划例外"。
    """
    containers = [
        os.path.join(ROOT, "skills"),
        os.path.join(ROOT, "plugins"),
        os.path.join(HOME, ".openclaw-autoclaw", "skills"),
        os.path.join(HOME, ".dsh", ".agent-presets"),
    ]
    out = []
    for base in containers:
        if not os.path.isdir(base):
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if d not in SKIP]
            if "SKILL.md" in fn:
                out.append(dp)
    return sorted(set(out))


def front_name(skill_dir):
    """技能在图鉴里的**真名**：`SKILL.md` 的 `name:` 字段（没有才退回目录名）。

    🔴 2026-10-22 自纠（第 6 次，留痕）：`omni.py collect_skills()` 取的正是 frontmatter 的
    `name`（`fx.get("name") or d.name`），而我第一版拿**目录名**去比图鉴 ⇒ 口径不同就误判：
    实测 5 个「该补」里 **4 个其实早就在图鉴里**（`Agentic Coding` / `autoclaw-design-capability_noQA`
    / `FFmpeg Video Editor` / `Market Research`）—— 目录名和 frontmatter 名不一样而已。
    只剩 `ian-xiaohei-svg-motion` 是真缺口，而它缺的原因是**另一件事**：图鉴采集只扫每个根
    的直接子目录，嵌套技能（`<根>/<类>/<名>/SKILL.md`）永远进不去（已登记为 F24）。
    """
    p = os.path.join(skill_dir, "SKILL.md")
    try:
        head = open(p, encoding="utf-8", errors="replace").read(800)
    except OSError:
        return os.path.basename(skill_dir.rstrip("\\/"))
    m = re.search(r"(?m)^name:\s*(.+)$", head)
    return (m.group(1).strip().strip("\"'") if m else os.path.basename(skill_dir.rstrip("\\/")))


def _depth(path, low=None):
    """相对我方容器算深度：容器本身=0，"<根>/<名>"=1，"<根>/<类>/<名>"=2 及以上=嵌套。"""
    p = path.replace("\\", "/").lower()
    for marker in ("/skills/", "/plugins/", "/agent-presets/"):
        if marker in p:
            tail = p.split(marker, 1)[1].strip("/")
            return len([x for x in tail.split("/") if x]) if tail else 0
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    atlas = atlas_names()
    dirs = ours_skill_dirs()
    names = {d: front_name(d) for d in dirs}
    unaccounted = [d for d in dirs if names[d] not in atlas]

    by_name = {}
    for d in unaccounted:
        by_name.setdefault(names[d], []).append(d)

    piles = {"该补（我们作者的技能）": [], "该划例外（上游/存档/重复）": [], "待定（来源不明）": []}
    for d in unaccounted:
        low = d.lower().replace("\\", "/")
        name = names[d]
        if any(m in low for m in EXCEPTION_MARKERS):
            piles["该划例外（上游/存档/重复）"].append({"path": d, "why": "路径含上游/存档标记"})
        elif len(by_name.get(name, [])) > 1:
            piles["该划例外（上游/存档/重复）"].append(
                {"path": d, "why": "同名出现 %d 次（重复件）" % len(by_name[name])})
        elif _depth(d, low) >= 2:
            # 🔴 2026-10-22 量完才定（留痕，第 7 次自纠）：**嵌套件是"料"，不是"可调用技能"**。
            #    实测：递归会多收 177 条，其中 171 条落在
            #    `…/autoclaw-design-capability/审美相关skill/design-skeletons|design-systems/*`
            #    —— 而这两族图鉴**早已单列**为 `design_assets_bulk`（235 条，按类聚合）。
            #    图鉴自己的话：「大部头素材不逐条塞进图鉴：它们是料，不是可调用的职业技能」。
            #    ⇒ 采集只扫一层是**分层设计**，不是漏采；递归反而会把料当技能塞进路由。
            piles["该划例外（上游/存档/重复）"].append(
                {"path": d, "why": "嵌套素材（料）：设计骨架/设计系统按类聚合，不进可调用清单"})
        elif any("/skills/" in low for _ in [0]) or low.endswith("/skills/" + name) \
                or "/plugins/" in low or "agent-presets" in low:
            piles["该补（我们作者的技能）"].append({"path": d, "why": "我方技能目录里的独立技能"})
        else:
            piles["待定（来源不明）"].append({"path": d, "why": "路径不在我方 skills 容器下"})

    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "our_skill_dirs": len(dirs), "in_atlas": len(dirs) - len(unaccounted),
           "unaccounted": len(unaccounted),
           # 两个单位都写清（2026-10-22 留痕）：按**名字**算 = 92 个（同名重复只算一次）；
           # 按**目录**算 = 181 个（重复件各占一个目录）。两把尺子报不同数是因为单位不同。
           "unaccounted_names": len({os.path.basename(d.rstrip("\\/")) for d in unaccounted}),
           "piles": {k: len(v) for k, v in piles.items()},
           "detail": piles}
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT_JSON)

    if a.json:
        print(json.dumps({k: v for k, v in out.items() if k != "detail"}, ensure_ascii=False, indent=2))
        return 0

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# D7 分界线：我方 235 个未入账技能，三堆", "",
             "> 生成：`py -3.14 tools/codex-scripts/d7-skill-boundary.py` · %s" % out["at"],
             "> 我方技能目录合计 **%d** 个 · 图鉴有名 **%d** · **未入账 %d**"
             % (out["our_skill_dirs"], out["in_atlas"], out["unaccounted"]),
             "",
             "| 堆 | 数量 | 建议处置 |", "|---|---|---|",
             "| 该补（我们作者的技能） | %d | 补进 `state/skill_atlas.json` |" % out["piles"]["该补（我们作者的技能）"],
             "| 该划例外（上游/存档/重复） | %d | 不纳管；在 D7 里写明例外口径即可 |" % out["piles"]["该划例外（上游/存档/重复）"],
             "| 待定（来源不明） | %d | 人看一眼路径再定 |" % out["piles"]["待定（来源不明）"],
             ""]
    for bucket, rows in piles.items():
        lines += ["## %s（%d）" % (bucket, len(rows)), ""]
        if not rows:
            lines.append("（空）")
        for r in rows[:80]:
            lines.append("- `%s` ← %s" % (r["path"], r["why"]))
        if len(rows) > 80:
            lines.append("- …（另有 %d 条，见 JSON）" % (len(rows) - 80))
        lines.append("")
    tmp_md = OUT_MD + ".tmp"
    with open(tmp_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp_md, OUT_MD)

    print("我方技能目录 %d · 图鉴有名 %d · 未入账 %d"
          % (out["our_skill_dirs"], out["in_atlas"], out["unaccounted"]))
    for k, v in out["piles"].items():
        print("  %-26s %3d" % (k, v))
    print("  人读：%s" % OUT_MD)
    print("  机读：%s" % OUT_JSON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
