# -*- coding: utf-8 -*-
"""技能根一致性审计 —— 同一份规程散在多个根上时，**哪一份是旧的**必须现读出来。

为什么需要它（2026-09-22 实测踩到）：
  本机同一个技能名最多同时存在于四个根：
    `skills/`（工作区源稿）· `~/.openclaw-autoclaw/skills`（AutoClaw 产品口径）
    `~/.agents/skills`（DSH 的 user-agents 根，**本会话真正加载的就是它**）· `<仓>/.dsh/skills`（DSH 项目根）
  实测：`gbt-omni` / `gbt-arkcli` / `gbt-tentacle` 在 `~/.agents/skills` 里是**旧版本**
  （10,951 / 9,716 / 11,117 B，mtime 21:01–22:06），而源稿是 12,586 / 12,391 / 12,998 B（22:10–22:40）
  ⇒ **本会话加载的是过期规程** —— 正是主人说的"旧的别留着误导重启后的大模型"。
  这类偏差不会自己暴露（两边都能读、都像模像样），只有**逐文件比哈希**才看得见。

判据（现读，不猜）：
  - `gbt-*` 是**我们自己的件** ⇒ 只要同名出现在多个根，就必须**逐字节相同**；不同 = 🔴 硬失败。
  - 第三方技能（`lark-*` / `arkcli-*` / `remotion-*` …）由各家自己装，多根不同**不判红**，只报 ⚠。
  - **孤儿**：只存在于 `~/.openclaw-autoclaw/skills`、工作区没有源稿的 `gbt-*` ⇒ 报出来（可能是历史残留）。
  - **未登记**：工作区有 `skills/gbt-*` 但 `omni.py` 的 `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS` 里都没有 ⇒ 报出来。

用法：
    py -3.14 tools/codex-scripts/audit-skill-roots.py            # 审计 + 写 state/skill_roots_audit.json
    py -3.14 tools/codex-scripts/audit-skill-roots.py --fix      # 把 gbt-* 的旧副本**从源稿刷新**（不改第三方）
退出码：0 = gbt-* 无偏差；1 = 有 gbt-* 偏差（修完再跑应为 0）。
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"
ATLAS = ROOT / "state" / "skill_atlas.json"
OUT = ROOT / "state" / "skill_roots_audit.json"

ROOTS = [
    ("ws-source", ROOT / "skills"),
    ("openclaw-managed", Path.home() / ".openclaw-autoclaw" / "skills"),
    ("dsh-project", ROOT / ".dsh" / "skills"),
    ("proj-agents", ROOT / ".agents" / "skills"),          # DSH 的 project-agents 根（本会话也会读）
    ("proj-claude", ROOT / ".claude" / "skills"),          # 项目内 Claude 侧
    ("user-agents", Path.home() / ".agents" / "skills"),
    ("user-claude", Path.home() / ".claude" / "skills"),   # Claude Code 侧
    ("user-openclaw", Path.home() / ".openclaw" / "skills"),  # OpenClaw 侧
]
# 本会话真正加载的根（DSH: skill-filesystem 的 user-agents + project 根；preset 只带 cordis 两件）
LOADED = {"user-agents", "dsh-project", "proj-agents"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


def load_map(name: str) -> dict:
    for node in ast.walk(ast.parse(OMNI.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return dict(ast.literal_eval(node.value))
    return {}


def main(argv: list[str]) -> int:
    fix = "--fix" in argv
    index: dict[str, dict] = {}
    for key, root in ROOTS:
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            sk = d / "SKILL.md"
            if not sk.exists():
                continue
            st = sk.stat()
            index.setdefault(d.name, {})[key] = {
                "sha": sha(sk), "bytes": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M"),
                "dir": str(d),
            }

    registered = set(load_map("DISTILLED_DOMAINS").values()) | set(load_map("DISTILLED_CLUSTERS").values())
    drift, fixed, orphans, unregistered, third_party = [], [], [], [], []
    for name, roots in sorted(index.items()):
        mine = name.startswith("gbt-")
        if mine and len(roots) > 1:
            shas = {k: v["sha"] for k, v in roots.items()}
            if len(set(shas.values())) > 1:
                src = roots.get("ws-source")
                if src is None:
                    drift.append({"name": name, "detail": "无源稿可比", "roots": shas})
                    continue
                stale = []
                for k, v in roots.items():
                    if k == "ws-source" or v["sha"] == src["sha"]:
                        continue
                    stale.append(k)
                    if fix:
                        for f in (Path(src["dir"])).rglob("*"):
                            if f.is_file():
                                t = Path(v["dir"]) / f.relative_to(Path(src["dir"]))
                                t.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copyfile(f, t)
                        # 刷完复验
                        after = sha(Path(v["dir"]) / "SKILL.md")
                        if after != src["sha"]:
                            fixed.append({"name": name, "root": k, "ok": False})
                        else:
                            fixed.append({"name": name, "root": k, "ok": True})
                    else:
                        drift.append({"name": name, "stale_roots": stale,
                                      "loaded": [k for k in stale if k in LOADED],
                                      "roots": shas})
        elif not mine and len(roots) > 1:
            if len({v["sha"] for v in roots.values()}) > 1:
                third_party.append({"name": name,
                                    "roots": {k: v["sha"][:10] for k, v in roots.items()}})
        if mine and "ws-source" not in roots and "openclaw-managed" in roots:
            orphans.append(name)
        if mine and "ws-source" in roots and name not in registered:
            unregistered.append(name)

    # ⑤ 我们自己的**单根件**：只存在于某一个根、且署名是我们（`GBT小土豆` / `自由的风` / `gbt_allinone`）。
    #    为什么只按"署名"筛：`~/.openclaw-autoclaw/skills` 里有 170+ 条**第三方**技能（lark-* / arkcli-* /
    #    hyperframes-* …），它们天生只在托管目录，报出来纯噪声。**我们自己的件**只留一份才是真故障。
    #    两个方向**分开报、修法相反**（第一版混在一起，把"没装机"错说成"拷回 skills/"）：
    #      ① `root != ws-source` ⇒ **孤本**：只在托管/用户根，仓里没有源 ⇒ 那个根一清就丢。修法：抢救成源稿。
    #      ② `root == ws-source` ⇒ **没装机**：源在仓里，但任何根都读不到 ⇒ 能力不生效。修法：装到托管根。
    ours_single: list[dict] = []
    ours_uninstalled: list[dict] = []
    for name, roots in sorted(index.items()):
        if len(roots) > 1:
            continue
        only_key = next(iter(roots))
        sk = Path(roots[only_key]["dir"]) / "SKILL.md"
        try:
            body = sk.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not any(sig in body for sig in ("GBT小土豆", "自由的风", "gbt_allinone")):
            continue
        row = {"name": name, "root": only_key, "path": str(Path(roots[only_key]["dir"])),
               "bytes": roots[only_key]["bytes"]}
        if only_key == "ws-source":
            ours_uninstalled.append(row)
        else:
            ours_single.append(row)

    # ⑥ 图鉴新鲜度：**盘上有的技能，图鉴里必须有**。
    #    为什么单列：`state/skill_atlas.json` 是**扫描产物**，而上面五段、体检 ①②③、账里的"图鉴现读"
    #    全都建立在它上面。实测踩到：图鉴 built_at `22:45:37`，而 `gbt-design-mastery` 是 `23:18` 才装好的
    #    ⇒ **图鉴里根本没有这一条**，`omni gaps` 也没报（它只查"已登记"的域/簇）⇒ 新装的件对整套读数隐形。
    #    口径严格照 `omni.collect_skills`：按**frontmatter 的 name**（拿不到才退回目录名）比对；
    #    聚合的"料"根（design-systems / design-skeletons）不逐条进图鉴 ⇒ 跳过，免得报一堆假缺。
    atlas_missing: list[dict] = []
    atlas_ghosts: list[str] = []
    atlas_meta: dict = {}
    try:
        spec = importlib.util.spec_from_file_location("omni_for_roots", OMNI)
        omni_mod = importlib.util.module_from_spec(spec)      # type: ignore[arg-type]
        spec.loader.exec_module(omni_mod)                     # type: ignore[union-attr]
        atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
        atlas_meta = {"built_at": atlas.get("built_at"), "skills": len(atlas.get("skills", []))}
        in_atlas = {s.get("name") for s in atlas.get("skills", [])}
        bulk_roots = {str(b.get("root")) for b in (atlas.get("design_assets_bulk") or [])}
        disk: dict[str, str] = {}
        for root, _ch, _why in omni_mod.SKILL_ROOTS:
            if not root.is_dir() or str(root) in bulk_roots:
                continue
            for d in sorted(root.iterdir()):
                if not d.is_dir():
                    continue
                sk = d / "SKILL.md"
                nm = d.name
                if sk.exists():
                    try:
                        head = sk.read_text(encoding="utf-8", errors="replace")[:2000]
                        m = re.search(r"(?m)^name:\s*(.+?)\s*$", head)
                        if m:
                            nm = m.group(1).strip().strip("'\"") or d.name
                    except OSError:
                        pass
                if nm not in in_atlas and d.name not in in_atlas:
                    atlas_missing.append({"name": nm, "dir": str(d), "root": str(root)})
                disk[nm] = str(d)
                disk[d.name] = str(d)
        atlas_ghosts = sorted(n for n in in_atlas - set(disk) if n)
    except Exception as e:                                    # noqa: BLE001
        atlas_meta = {"error": "%s: %s" % (type(e).__name__, e)}

    print("=" * 78)
    print("技能根一致性审计（%s）" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 78)
    for key, root in ROOTS:
        n = len([1 for v in index.values() if key in v])
        print("  %-18s %-52s %d 个技能" % (key, str(root), n))
    print("  本次会话真正加载的根：%s" % "、".join(sorted(LOADED)))
    print("-" * 78)
    print("① gbt-* 哈希偏差：%d 个%s" % (len(drift), "（已刷新 %d 处）" % len(fixed) if fix else ""))
    for d in drift:
        tag = "🔴 其中 %s 是本会话**正在加载**的根" % "、".join(d["loaded"]) if d.get("loaded") else ""
        print("   %s：%s  %s" % (d["name"], "、".join(d.get("stale_roots", [])), tag))
    for f in fixed:
        print("   %s 已刷新 %s → %s" % ("✅" if f["ok"] else "🔴", f["root"], f["name"]))
    print("② 只存在于 openclaw-managed、工作区无源稿的 gbt-*（疑似残留）：%d 个" % len(orphans))
    for o in orphans:
        print("   ⚠ %s" % o)
    print("③ 工作区有源稿但两份登记表里都没有的 gbt-*：%d 个" % len(unregistered))
    for u in unregistered:
        print("   ⚠ %s" % u)
    print("④ 第三方技能多根哈希不同（不判红，仅报告）：%d 个" % len(third_party))
    for t in third_party[:8]:
        print("   · %s  %s" % (t["name"], t["roots"]))
    if len(third_party) > 8:
        print("   …（共 %d 个，完整清单见回执）" % len(third_party))
    print("⑤ 我们自己的**单根件**（只存在于一个根 + 署名是我们）：%d 个" % (len(ours_single) + len(ours_uninstalled)))
    for o in ours_single:
        print("   🔴 孤本 %s（只在 %s · %d B）⇒ 抢救成源稿：拷到 `skills/%s/`"
              % (o["name"], o["root"], o["bytes"], o["name"]))
    for o in ours_uninstalled:
        print("   🔴 没装机 %s（只在 ws-source · %d B）⇒ 装到托管根：拷到 `~/.openclaw-autoclaw/skills/%s/`"
              % (o["name"], o["bytes"], o["name"]))
    print("⑥ 图鉴新鲜度（盘上有的技能，图鉴里必须有）")
    if atlas_meta.get("error"):
        print("   ⚠ 读不动图鉴/omni：%s" % atlas_meta["error"])
    else:
        print("   图鉴 built_at=%s · 收录 %s 条" % (atlas_meta.get("built_at"), atlas_meta.get("skills")))
        print("   盘上有、图鉴里没有：%d 个" % len(atlas_missing))
        for m in atlas_missing:
            print("   🔴 %s（%s）⇒ 重扫：`py -3.14 tools/codex-scripts/omni.py build`" % (m["name"], m["dir"]))
        if atlas_ghosts:
            print("   （图鉴里有、盘上没找到：%d 个 —— 只提示，可能是聚合料或镜像差：%s%s）"
                  % (len(atlas_ghosts), "、".join(atlas_ghosts[:6]),
                     " …" if len(atlas_ghosts) > 6 else ""))

    OUT.write_text(json.dumps({
        "at": datetime.now().isoformat(timespec="seconds"),
        "roots": {k: str(r) for k, r in ROOTS},
        "loaded_roots": sorted(LOADED),
        "index": index, "gbt_drift": drift, "refreshed": fixed,
        "orphans_managed_only": orphans, "unregistered": unregistered,
        "third_party_divergent": third_party,
        "ours_single_copy": ours_single, "ours_uninstalled": ours_uninstalled,
        "atlas": atlas_meta, "atlas_missing": atlas_missing, "atlas_ghosts": atlas_ghosts,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-" * 78)
    if drift or ours_single or ours_uninstalled or atlas_missing:
        if drift:
            print("结论：**有 gbt-* 偏差**（%d 个）—— 跑 `--fix` 从源稿刷新，再复跑本器。" % len(drift))
        if ours_single:
            print("结论：**有我们自己的孤本**（%d 个）—— 拷到 `skills/<名字>/` 抢救成源稿，再复跑本器。"
                  % len(ours_single))
        if ours_uninstalled:
            print("结论：**有我们自己的件没装机**（%d 个）—— 装到 `~/.openclaw-autoclaw/skills/<名字>/`，再复跑本器。"
                  % len(ours_uninstalled))
        if atlas_missing:
            print("结论：**图鉴过期**（盘上 %d 个技能不在图鉴里）—— 跑 `py -3.14 tools/codex-scripts/omni.py build` 重扫，"
                  "再复跑体检（图鉴是①②③与账里「图鉴现读」的地基）。" % len(atlas_missing))
        return 1
    print("结论：gbt-* 在所有根上逐字节一致 ✅ · 自有件无孤本无漏装 ✅ · 图鉴与盘上一致 ✅（第三方差异 %d 个，见 ④）"
          % len(third_party))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
