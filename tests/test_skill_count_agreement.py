# -*- coding: utf-8 -*-
"""技能口径一致性判据 · **同一份盘，几个读者必须数出同一个数**。

## 血账（2026-11-05，实测）

同一份 `skills/`，三个读技能的工具数出三个不同的数：

| 读者 | 口径 | 数出 | 后果 |
|---|---|---|---|
| `tentacle/skills_hub.py:56` | `rglob("SKILL.md")` | 26 | 漏 `gbt_allinone/skills/`（7 条） |
| `tools/codex-scripts/omni.py` | `iterdir()` 一层 | 8 | 集合包内层全丢，2 条 **desc=0 空壳** |
| `tools/codex-scripts/audit-skill-roots.py` | `iterdir()` 一层 | 6/4/2 | 与 omni 正面打架（3 missing vs 27 ghosts） |

最贵的那一半：`skills/superpowers/` 里 20 条（brainstorming / systematic-debugging /
writing-plans …）、`shuohao/` 里 7 条 —— 盘上 183 个文件都拷了、`skills_sync check`
报"四条全过"，**但图鉴里它们是空壳、路由打分永远 0 ⇒ 运行时一条都调不到**。
这就是 F18：「盘上对」被念成「生效了」。

## 口径（已统一，本判据钉死）

**每个 `SKILL.md` = 一个技能**，名取 frontmatter 的 `name:`（拿不到退回目录名）。

为什么递归不会重复计数 —— 靠下面这条**不变量**：

    不存在「父目录也带 SKILL.md」的嵌套

实测：33 个 SKILL.md 中该情况 = 0。一旦有人把某个技能改成"主件 + 子件各带 SKILL.md"，
这条会先红 —— 提醒他先想清楚"子件到底算不算独立技能"，而不是让四个读者继续各数各的。

## 红了怎么修

- **不变量红** → 先决定嵌套语义（子件是否独立技能），再改三处读者，别只改一处。
- **读数不一致红** → 跑 `./pyembed/python.exe tools/codex-scripts/omni.py build` 重建图鉴；
  仍不一致说明某处枚举口径又被改回一层了。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"
ATLAS = ROOT / "state" / "skill_atlas.json"

# 两个**源**根（`tools/skills_sync.py` 的 SOURCES 与它同源）
SOURCE_ROOTS = [ROOT / "skills", ROOT / "gbt_allinone" / "skills"]

SKIP_DIRS = {"__pycache__", ".git", "node_modules"}


def _name_of(sk: pathlib.Path) -> str:
    """技能真名：frontmatter `name:`，拿不到退回目录名。"""
    try:
        head = sk.read_text(encoding="utf-8", errors="replace")[:2000]
    except OSError:
        return sk.parent.name
    m = re.search(r"(?m)^name:\s*(.+?)\s*$", head)
    return (m.group(1).strip().strip("'\"") or sk.parent.name) if m else sk.parent.name


def _disk_skills() -> dict:
    """独立枚举（不经过任何被测工具）：{技能名: SKILL.md 路径}。"""
    out = {}
    for base in SOURCE_ROOTS:
        if not base.is_dir():
            continue
        for sk in base.rglob("SKILL.md"):
            if SKIP_DIRS & set(sk.parts):
                continue
            out[_name_of(sk)] = sk
    return out


def _load_omni():
    spec = importlib.util.spec_from_file_location("omni_for_skill_agreement", OMNI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # type: ignore[union-attr]
    return mod


class TestSkillCountAgreement(unittest.TestCase):
    def test_no_nested_skill_md(self):
        """不变量：不许出现「父目录也带 SKILL.md」的嵌套 —— 递归计数靠它才成立。"""
        bad = []
        for base in SOURCE_ROOTS:
            if not base.is_dir():
                continue
            for sk in base.rglob("SKILL.md"):
                d = sk.parent
                # 只往上看到 base 为止（base 之外是别人的地盘，不算嵌套）
                for anc in d.parents:
                    if anc == base:
                        break
                    if (anc / "SKILL.md").is_file():
                        bad.append("%s ⇐ 父目录 %s 也带 SKILL.md" % (d, anc))
                        break
        self.assertEqual(bad, [],
                         "出现嵌套 SKILL.md，递归计数会重复：\n  " + "\n  ".join(bad[:8]) +
                         "\n⇒ 先决定「子件算不算独立技能」，再同步改 omni / audit / skills_hub 三处")

    def test_disk_enumeration_not_empty(self):
        """防空集过关：源必须真枚举到技能。"""
        disk = _disk_skills()
        self.assertGreater(len(disk), 0, "源根下一个技能都没枚举到 —— 空集合过关=假绿")

    def test_omni_reader_agrees_with_disk(self):
        """omni 的读者（图鉴的源）必须与独立枚举**同名同数**。"""
        disk = _disk_skills()
        omni = _load_omni()
        raw, _bulk = omni.collect_skills()
        skills = omni.dedupe_skills(raw)

        got = {s["name"] for s in skills if s.get("channel") == "agent-skill"}
        want = set(disk)

        missing = sorted(want - got)      # 盘上有、omni 看不见
        extra = sorted(got - want)        # omni 有、盘上找不到（幽灵）
        self.assertEqual(
            (missing, extra), ([], []),
            "omni 的技能口径与盘上不一致：\n"
            "  漏（盘上有、omni 没有）：%s\n"
            "  幽灵（omni 有、盘上没）：%s\n"
            "⇒ 检查 omni.collect_skills 是否又退回了一层 iterdir（集合包内层会全丢）"
            % (missing[:10], extra[:10]))

    def test_atlas_has_no_empty_desc(self):
        """图鉴里不许有 desc 为空的技能 —— 空壳等于"装着但调不到"。"""
        if not ATLAS.is_file():
            self.skipTest("图鉴还没建：./pyembed/python.exe tools/codex-scripts/omni.py build")
        atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
        empty = [s.get("name") for s in atlas.get("skills", [])
                 if s.get("channel") == "agent-skill" and not (s.get("desc") or "").strip()]
        self.assertEqual(empty, [],
                         "图鉴里有 %d 条 desc 为空的技能（它们是集合包空壳，路由永远打不中）：%s\n"
                         "⇒ 跑 omni.py build 重建；仍空说明枚举又漏了内层"
                         % (len(empty), empty[:8]))

    def test_every_skill_is_loadable_by_layout(self):
        """**装上了 = 加载得了**：每个技能都能按 `<枢纽>/<技能名>/SKILL.md` 解析到。

        血账（2026-11-05）：`skills_sync` 早先按**包**整拷 ⇒ 枢纽里是
        `<hub>/superpowers/brainstorming/SKILL.md`，而加载器按 `<hub>/<技能名>/SKILL.md` 找，
        于是 `superpowers` 那 20 条 + `shuohao` 那 7 条**一个都加载不了** ——
        可 `skills_sync check` 当时报"四条全过、逐字节一致"。文件都在，布局错了。
        这条判据就是钉死"逐字节一致"不等于"装对了"。
        """
        if not ATLAS.is_file():
            self.skipTest("图鉴还没建")
        atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
        names = [s.get("name") for s in atlas.get("skills", [])
                 if s.get("channel") == "agent-skill"]
        hubs = [pathlib.Path.home() / ".agents" / "skills", ROOT / ".agents" / "skills"]
        bad = [n for n in names
               if not any((h / n / "SKILL.md").is_file() for h in hubs)]
        self.assertEqual(
            bad, [],
            "有 %d 个技能**按布局加载不到**（<枢纽>/<技能名>/SKILL.md 不存在）：%s\n"
            "⇒ 跑 ./pyembed/python.exe tools/skills_sync.py sync（它按技能平铺装，不按包整拷）"
            % (len(bad), bad[:8]))

    def test_atlas_count_matches_disk(self):
        """图鉴条数必须等于盘上独立枚举条数（图鉴过期会在这里红）。"""
        if not ATLAS.is_file():
            self.skipTest("图鉴还没建")
        disk = _disk_skills()
        atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
        got = {s.get("name") for s in atlas.get("skills", [])
               if s.get("channel") == "agent-skill"}
        self.assertEqual(
            len(got), len(disk),
            "图鉴 %d 条 vs 盘上 %d 条 ⇒ 图鉴过期或口径漂了；跑 omni.py build 重扫"
            % (len(got), len(disk)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
