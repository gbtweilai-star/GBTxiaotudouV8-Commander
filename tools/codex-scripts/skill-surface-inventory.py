#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""技能面盘点（F9 的尺子）—— 把「技能根 / 第三方技能」量成一张**纳管决策表**。

F9 原文：「本机有 28 个技能根 / 1273 个第三方技能 / 1512 个可执行件，来自十几种别的 agent 工具
（.trae/.workbuddy-ai/.zcode/.lingma/.continue/.copilot/.gemini/.omp…）—— 这是一个**没人管、
还在自己长大**的面」。

🔴 2026-10-22 第一版量错（留痕）：我把**每个技能目录**（含 SKILL.md 的目录）都当成一个"根"，
   于是量出「8131 个根 / 8969 个技能」——那个数字是"技能数×嵌套"，不是"根数"。
   口径翻正：**根 = 装技能的那个容器**（最近的名为 `skills` 的祖先；没有就用技能目录的父目录）。

判据（供 reverify F9 读）：
  · 我们自营/托管面里的每个技能都必须在 `state/skill_atlas.json` 里**有名**（纳管 = 有账）；
  · **新长出来的根**（不在上次清册里）必须点名打出来。

用法：
  py -3.14 tools/codex-scripts/skill-surface-inventory.py
  py -3.14 tools/codex-scripts/skill-surface-inventory.py --json
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
OUT_JSON = os.path.join(ROOT, "state", "skill-surface-inventory.json")
OUT_MD = os.path.join(ROOT, "outputs", "skill-surface", "纳管决策表.md")

SKIP_NAMES = {".git", "node_modules", "__pycache__", ".venv", ".venv-sadtalker",
              "site-packages", ".backups", ".trash"}
MAX_DEPTH = 8
TOOL_DIRS = {".trae", ".trae-cn", ".workbuddy-ai", ".zcode", ".lingma", ".continue", ".copilot",
             ".gemini", ".omp", ".claude", ".aider-desk", ".augment", ".freebuff", ".opencode",
             ".windsurf", ".cursor", ".openclaw", ".autoclaw", ".agents", ".qoder", ".codex"}


def all_skill_dirs(bases):
    out = []
    for base in bases:
        if not os.path.isdir(base):
            continue
        for dp, dn, fn in os.walk(base):
            rel = os.path.relpath(dp, base)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth > MAX_DEPTH:
                dn[:] = []
                continue
            dn[:] = [d for d in dn if d not in SKIP_NAMES]
            if "SKILL.md" in fn:
                out.append(dp)
    return out


def container_of(skill_dir):
    """根 = 最近一个名为 skills/skill 的祖先；没有就取父目录。"""
    p = os.path.abspath(skill_dir)
    cur = p
    for _ in range(6):
        parent = os.path.dirname(cur)
        if not parent or parent == cur:
            break
        if os.path.basename(parent).lower() in ("skills", "skill"):
            return parent
        cur = parent
    return os.path.dirname(p)


def classify(path):
    low = path.lower()
    ours_markers = [
        os.path.join(HOME, ".openclaw-autoclaw", "skills").lower(),
        os.path.join(ROOT, "skills").lower(),
        os.path.join(ROOT, "plugins").lower(),
    ]
    if any(low.startswith(m) for m in ours_markers):
        return "托管（我们自己的技能目录）"
    if low.startswith(ROOT.lower()):
        # 🔴 2026-10-22 口径统一（留痕）：`本仓自营` 只认**四个指定容器**
        #    （`<仓>/skills` · `<仓>/plugins` · `~/.openclaw-autoclaw/skills` · `~/.dsh/.agent-presets`），
        #    与 `d7-skill-boundary.py` 用同一把尺。容器之外的（`_upstream`/`vendor`/`third_party`/
        #    `projects/**` 里的副本）是**上游参考**，不是我们作者的技能 —— 否则同一件事会被两把尺子
        #    量出两个数（实测 1335 vs 704）。
        return "上游参考（仓内 vendored/副本）"
    parts = {x.lower() for x in path.split(os.sep)}
    if parts & TOOL_DIRS:
        return "外部工具（只读参考）"
    if "temp" in low or "cache" in low or "appdata\\local\\temp" in low:
        return "无主体（缓存/临时）"
    return "外部工具（只读参考）"


def atlas_names():
    p = os.path.join(ROOT, "state", "skill_atlas.json")
    if not os.path.isfile(p):
        return set()
    try:
        j = json.load(open(p, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return set()
    rows = j if isinstance(j, list) else (j.get("skills") or j.get("rows") or [])
    names = set()
    for r in rows:
        if isinstance(r, str):
            names.add(r)
        elif isinstance(r, dict):
            for k in ("name", "id", "slug"):
                if r.get(k):
                    names.add(str(r[k]))
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    skill_dirs = sorted(set(all_skill_dirs([ROOT, HOME])))
    groups = {}
    for sd in skill_dirs:
        c = container_of(sd)
        groups.setdefault(c, []).append(os.path.basename(sd.rstrip("\\/")))
    rows = []
    for container, names in groups.items():
        rows.append({"root": container, "skills": len(names), "bucket": classify(container),
                     "names_sample": names[:4]})
    rows.sort(key=lambda r: (-r["skills"], r["root"]))

    prev = {}
    if os.path.isfile(OUT_JSON):
        try:
            prev = json.load(open(OUT_JSON, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prev = {}
    prev_roots = {r.get("root") for r in (prev.get("roots") or [])}
    new_roots = [r["root"] for r in rows if r["root"] not in prev_roots] if prev_roots else []

    by_bucket = {}
    for r in rows:
        b = by_bucket.setdefault(r["bucket"], {"roots": 0, "skills": 0})
        b["roots"] += 1
        b["skills"] += r["skills"]
    total_skills = sum(r["skills"] for r in rows)

    # 🔴 2026-10-22 口径统一（第二处，留痕）：我方计数改成**递归 + 按路径去重**，
    #    与 `d7-skill-boundary.py` 用同一套算法 ⇒ 两个工具报同一个数。
    #    旧写法只数容器下的**直接子目录**（`skill-surface` 报 698，而 `d7` 报 704），
    #    同一个盘被两把尺子量出两个数 —— 那比不量还坏。
    atlas = atlas_names()
    ours_dirs = []
    containers = [os.path.join(ROOT, "skills"), os.path.join(ROOT, "plugins"),
                  os.path.join(HOME, ".openclaw-autoclaw", "skills"),
                  os.path.join(HOME, ".dsh", ".agent-presets")]
    for base in containers:
        if not os.path.isdir(base):
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if d not in SKIP_NAMES]
            if "SKILL.md" in fn:
                ours_dirs.append(dp)
    ours_dirs = sorted(set(ours_dirs))
    # 🔴 2026-10-22 落成规则（F9 的收口）：未入册**不等于缺口**。只有同时满足
    #    「名字不在图鉴」+「不属于三类例外」的，才算**真缺口**：
    #      ① 上游/存档/vendored（路径含 _upstream / vendor / third_party / archive / _stale）
    #      ② 同名重复（同一个名字在我方面里出现多次 ⇒ 只算一次账，其余是副本）
    #      ③ 嵌套素材（料）：深度 ≥2 的 SKILL.md —— 图鉴自己把 design-skeletons / design-systems
    #         按类聚合为 `design_assets_bulk`（现读 235 条），它们是料不是可调用技能。
    #    判据（供 reverify F9 读）：`ours_gap`（真缺口条目）与新根才让它红。
    def _depth(p):
        q = p.replace("\\", "/").lower()
        for mk in ("/skills/", "/plugins/", "/agent-presets/"):
            if mk in q:
                tail = q.split(mk, 1)[1].strip("/")
                return len([x for x in tail.split("/") if x]) if tail else 0
        return 1

    def _front(p):
        try:
            head = open(os.path.join(p, "SKILL.md"), encoding="utf-8", errors="replace").read(800)
        except OSError:
            return os.path.basename(p.rstrip("\\/"))
        m = re.search(r"(?m)^name:\s*(.+)$", head)
        return (m.group(1).strip().strip("\"'") if m else os.path.basename(p.rstrip("\\/")))

    names = {d: _front(d) for d in ours_dirs}
    unaccounted = [d for d in ours_dirs if names[d] not in atlas]
    EXC = ("_upstream", "vendor", "third_party", "archive", "_stale", ".backups", "node_modules")
    seen = {}
    for d in unaccounted:
        seen.setdefault(names[d], []).append(d)
    gap, exc = [], []
    for d in unaccounted:
        low = d.lower().replace("\\", "/")
        if any(m in low for m in EXC):
            exc.append({"path": d, "why": "上游/存档/vendored"})
        elif len(seen.get(names[d], [])) > 1:
            exc.append({"path": d, "why": "同名重复（%d 份）" % len(seen[names[d]])})
        elif _depth(d) >= 2:
            exc.append({"path": d, "why": "嵌套素材（料，按类聚合）"})
        else:
            gap.append({"path": d, "name": names[d]})
    unaccounted_names = sorted({names[d] for d in unaccounted})

    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "roots": rows,
        "total_roots": len(rows),
        "total_skills": total_skills,
        "by_bucket": by_bucket,
        "new_roots_since_last": new_roots,
        "ours_dirs": len(ours_dirs),
        "ours_in_atlas": len(ours_dirs) - len(unaccounted),
        "ours_unaccounted_dirs": len(unaccounted),
        "ours_unaccounted_names": len(unaccounted_names),
        "ours_exceptions": len(exc),
        "ours_exceptions_by_why": {w: sum(1 for x in exc if x["why"].startswith(w))
                                   for w in ("上游/存档/vendored", "同名重复", "嵌套素材")},
        # ↓ 这两个才是 F9 的判据：**真缺口**（未入册、也不属于任何例外）
        "ours_gap": gap[:60],
        "ours_gap_count": len(gap),
        "elapsed_s": round(time.time() - t0, 1),
    }
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT_JSON)

    if a.json:
        print(json.dumps({k: v for k, v in out.items() if k != "roots"}, ensure_ascii=False, indent=2))
        return 0

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# 技能面纳管决策表（F9）", "",
             "> 生成：`py -3.14 tools/codex-scripts/skill-surface-inventory.py` · %s" % out["at"],
             "> 口径：**根 = 装技能的那个容器**（最近的 `skills` 祖先）；**纳管 = 有账**（在 `state/skill_atlas.json` 有名）。",
             "",
             "## 汇总", "", "| 桶 | 根数 | 技能数 | 处置 |", "|---|---|---|---|"]
    verdicts = {
        "托管（我们自己的技能目录）": "纳管（必须有账）",
        "本仓自营": "纳管（必须有账）",
        "外部工具（只读参考）": "**不纳管**：只读参考，不进门、不路由",
        "无主体（缓存/临时）": "**忽略**：临时/缓存，不算技能面",
    }
    for b, v in sorted(by_bucket.items(), key=lambda kv: -kv[1]["skills"]):
        lines.append("| %s | %d | %d | %s |" % (b, v["roots"], v["skills"], verdicts.get(b, "看情况")))
    lines += ["", "合计：**%d 个技能根 · %d 个技能**（扫 %.1f 秒）" % (len(rows), total_skills, out["elapsed_s"]), "",
              "## 我方（四个容器）的账", "",
              "- 目录 **%d** ｜ 图鉴有名 **%d** ｜ 未入册 **%d**"
              % (out["ours_dirs"], out["ours_in_atlas"], out["ours_unaccounted_dirs"]),
              "- 未入册里：**例外 %d**（上游/存档/vendored %d · 同名重复 %d · 嵌套素材(料) %d）｜ **真缺口 %d**"
              % (out["ours_exceptions"],
                 out["ours_exceptions_by_why"].get("上游/存档/vendored", 0),
                 out["ours_exceptions_by_why"].get("同名重复", 0),
                 out["ours_exceptions_by_why"].get("嵌套素材", 0),
                 out["ours_gap_count"])]
    if gap:
        lines.append("- 🔴 **真缺口（该补）**：" + "、".join(x["name"] for x in gap[:40]))
    if new_roots:
        lines += ["", "## 🔴 自上次清册以来新长出来的根（%d 个）" % len(new_roots), ""]
        for r in new_roots[:40]:
            lines.append("- `%s`" % r)
    lines += ["", "## 逐根明细", "", "| 桶 | 技能数 | 根 |", "|---|---|---|"]
    for r in rows:
        lines.append("| %s | %d | `%s` |" % (r["bucket"], r["skills"], r["root"]))
    tmp_md = OUT_MD + ".tmp"
    with open(tmp_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp_md, OUT_MD)

    print("技能面：%d 个根 · %d 个技能 · 扫 %.1f 秒" % (len(rows), total_skills, out["elapsed_s"]))
    for b, v in sorted(by_bucket.items(), key=lambda kv: -kv[1]["skills"]):
        print("  %-28s %3d 根 · %4d 技能" % (b, v["roots"], v["skills"]))
    print("  我方 %d 目录 · 图鉴有名 %d · 未入册 %d（例外 %d · **真缺口 %d**）"
          % (out["ours_dirs"], out["ours_in_atlas"], out["ours_unaccounted_dirs"],
             out["ours_exceptions"], out["ours_gap_count"]))
    if new_roots:
        print("  🔴 新长出来的根 %d 个（前 5）：%s" % (len(new_roots), "、".join(new_roots[:5])))
    print("  机读：%s" % OUT_JSON)
    print("  人读：%s" % OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
