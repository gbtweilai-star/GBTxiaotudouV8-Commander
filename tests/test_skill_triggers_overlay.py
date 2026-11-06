# -*- coding: utf-8 -*-
"""技能触发词覆盖层判据 · **看得见 ≠ 调得到**。

## 血账（2026-11-05）

第十八批把技能口径统一成「每个 SKILL.md = 一个技能」之后，图鉴从 8 条变成 33 条，
`skills/superpowers/` 那 20 条终于进了语料。**但立刻发现它们仍然调不到**：

    omni ask "帮我把这个方案的发散思路打开一下"   → 0.4  desktop-shell（跟技能无关）
    omni ask "这个 bug 老修不好 要走系统化调试"   → 1.4  clean_residue（打偏）

原因不是语言 —— 它们的 desc **是中文**的。是**词不撞**：
`brainstorming` 的 desc 写「在任何创造性工作之前……探索用户意图、需求和设计」，
而人说的是「发散思路」；`systematic-debugging` 写「遇到任何 bug、测试失败或异常行为」，
而人说的是「老修不好」。语义同义、bigram 零交集 ⇒ 打分 0。

## 为什么用「覆盖层」而不是改 SKILL.md

那 20 条是 **vendored（第三方）**。直接改它们：

1. 与上游更新冲突（下次拉包就覆盖掉，白改）；
2. 立刻制造「源 ≠ 装」分叉 —— `tools/skills_sync.py check` 会报红，而且这个红是**我们自己造成的**。

所以覆盖层放仓内：`tools/codex-scripts/skill-triggers.json`，
`omni.collect_skills()` 在 build 时把里面的中文说法并进 `row["triggers"]`，
打分语料（`omni.py` 的 `blob = name + displayName + desc + desc_tail + triggers`）自动吃到。
**源件一个字节不动。**

## 本判据管四件事

1. 覆盖层是合法 JSON，且**写清了为什么**（`_note` / `_opt_out` / `_how_to_edit`）。
2. 每个键都是**真存在的技能** —— 打错字或技能被删，不能静静失效。
3. **尊重技能自己的禁令**：`chinese-code-review` / `chinese-documentation` 原文写着
   「仅在用户显式 /命令 时调用，不要根据上下文自动触发」⇒ 它们的键**不许出现**。
   给它们加触发词 = 我们违反技能自己写的规则。
4. **命中实证**：8 句人话必须首选命中对应技能 —— 判据不看"词加没加"，只看"调不调得到"。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "tools" / "codex-scripts" / "skill-triggers.json"
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"

# 技能自己声明「不要自动触发」的（原文见覆盖层 _opt_out）—— 不许给它们加触发词
OPT_OUT = {"chinese-code-review", "chinese-documentation"}

# 命中实证：(人话, 可接受的 top-1 集合)。
#
# 集合里有多个 = **公认歧义**，不是我放宽标准：
#   ·「gsap 官方文档」既可能是 gsap 本体也可能是 gsap-official
#   ·「小说分镜拆解」staging（拆解/调度）与 storyboard（出板）本来就重叠
#   ·「git 分支怎么规划」worktree（隔离工作区）与 git-workflow（分支策略）都沾边
# 其余一律单元素 —— 只认那一个。**判据不看"词加没加"，只看"调不调得到"。**
CASES = [
    # ── A 组：短 desc 技能（第十九批已覆盖；本批改打分公式后**不许倒退**）──
    ("帮我把这个方案的发散思路打开一下", ("brainstorming",)),
    ("这个 bug 老修不好 要走系统化调试", ("systematic-debugging",)),
    ("先写测试再实现 走测试驱动", ("test-driven-development",)),
    ("几个独立任务并行跑 用多个代理", ("dispatching-parallel-agents",)),
    ("前端不要AI味 要设计感", ("design-taste-frontend",)),
    ("怎么用技能 有哪些技能", ("using-superpowers",)),
    ("收到评审意见 要回应", ("receiving-code-review",)),
    ("合并分支收尾 开个PR", ("finishing-a-development-branch",)),
    # ── B 组：长 desc / 同族兄弟（第二十批扩的 15 条）──
    ("网页动效用 gsap 写", ("gsap",)),
    ("gsap 官方文档怎么查", ("gsap-official", "gsap")),
    ("这张参考图转成三维模型", ("ref-to-3d",)),
    ("角色参考图怎么出", ("character-refs",)),
    ("给小说配插画", ("novel-art",)),
    ("小说人物小传怎么写", ("novel-characters",)),
    ("小说分章大纲", ("novel-outline",)),
    ("小说改成剧本", ("novel-script",)),
    ("小说分镜拆解", ("novel-staging", "novel-storyboard")),
    ("小说故事板", ("novel-storyboard",)),
    ("AI 入门要学什么", ("gbt-ai-101",)),
    ("怎么让自己持续变强", ("gbt-selfgrowth",)),
    ("跑一个工作流", ("workflow-runner",)),
    ("中文提交信息怎么写", ("chinese-commit-conventions",)),
    ("git 分支怎么规划", ("chinese-git-workflow", "using-git-worktrees")),
]


def _load_omni():
    spec = importlib.util.spec_from_file_location("omni_for_triggers", OMNI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # type: ignore[union-attr]
    return mod


class TestSkillTriggersOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(OVERLAY.read_text(encoding="utf-8"))
        cls.overlay = cls.raw.get("triggers") or {}
        cls.omni = _load_omni()
        cls.known = {s["name"] for s in cls.omni.dedupe_skills(cls.omni.collect_skills()[0])
                     if s.get("channel") == "agent-skill"}

    def test_file_is_documented(self):
        """覆盖层必须自带「为什么」，否则下一个人会以为它是随手加的。"""
        for key in ("_note", "_opt_out", "_how_to_edit"):
            self.assertIn(key, self.raw, "覆盖层缺说明字段 %s —— 没写理由的配置等于谜语" % key)
        self.assertTrue(self.raw["_note"], "_note 是空的")

    def test_every_key_is_a_real_skill(self):
        """键必须对应真技能：打错字 / 技能被删，不许静静失效。"""
        unknown = sorted(set(self.overlay) - self.known)
        self.assertEqual(unknown, [],
                         "覆盖层里有 %d 个键在盘上找不到对应技能：%s\n"
                         "⇒ 改 `tools/codex-scripts/skill-triggers.json`：删掉它们，或修拼写"
                         % (len(unknown), unknown))

    def test_respects_skill_opt_out(self):
        """技能自己写着「不要自动触发」的，就一个触发词都不许加。"""
        violated = sorted(OPT_OUT & set(self.overlay))
        self.assertEqual(violated, [],
                         "给 %s 加了触发词，但这两个技能原文明确写着"
                         "「仅在用户显式 /命令 时调用，不要根据上下文自动触发」\n"
                         "⇒ 从 skill-triggers.json 里移除它们" % violated)

    def test_samples_actually_hit(self):
        """命中实证：加词的目的是**调得到**，不是词表好看。"""
        bad = []
        for q, accept in CASES:
            r = self.omni.rank(q, top=5)
            top = [s["name"] for s in r["skills"][:3]]
            if not top or top[0] not in accept:
                bad.append("  「%s」→ 期望 %s，实得 %s"
                           % (q, " / ".join(accept), top[:3] or "(无命中)"))
        self.assertEqual(bad, [],
                         "有 %d 句人话没打到对应技能：\n%s\n"
                         "⇒ 补/改 skill-triggers.json 里对应技能的中文说法，"
                         "然后跑 ./pyembed/python.exe tools/codex-scripts/omni.py build"
                         % (len(bad), "\n".join(bad)))

    def test_no_trigger_duplicates_across_skills(self):
        """同一个词不该同时挂在两个技能上 —— 那会让排名在 0.0x 之间随机摇。"""
        seen = {}
        dupes = []
        for name, words in self.overlay.items():
            for w in words:
                if w in seen and seen[w] != name:
                    dupes.append("%s 同时属于 %s 和 %s" % (w, seen[w], name))
                seen[w] = name
        self.assertEqual(dupes, [], "触发词撞车：\n  " + "\n  ".join(dupes[:10]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
