# -*- coding: utf-8 -*-
"""可达性判据 · **三件事三个判据，别混读**。

## 血账（2026-11-05 巡检）

`omni ask` 会同时给出三通道的"能不能用"，但三处说的是**三件不同的事**：

| 函数 | 真正回答的问题 | 误读成 |
|---|---|---|
| `skill_reachable` | 本会话**能不能按名字加载**这条技能（`<根>/<名>/SKILL.md` 在不在） | "技能好不好" |
| `cap_auto_runnable`（原 `cap_reachable`） | 能力位**能不能免卡无参自动跑**（门/参数/侧效应） | "能力位可不可达 / 坏没坏" |
| `local_tools()` | 工具**实物在不在 + 语法能不能解析** | "工具能不能完成任务" |

最刺眼的一条：`see_camera`（打开摄像头）在 `cap_auto_runnable` 里是 **False**，
原因「注册表未标 safe」—— 它**完全可用**，只是不能免卡自动跑。
实测 427 位里 False 的 **163 个，没有一个是"实现缺失"**，全是门类原因。
把这种 False 读成"能力位坏了"，结论会完全反过来。

## 另一处：**三份根清单各写各的**

同一件事实（"本会话读哪几个技能根"）在三处各写一遍：

1. `omni.SESSION_SKILL_ROOTS`（3 个）
2. `audit-skill-roots.py` 的 `LOADED = {user-agents, dsh-project, proj-agents}`
3. `tests/test_skill_count_agreement.py` 里的两个 hub

谁加删一个根，另外两处**不会自动跟** —— 于是又回到"同一件事两个出口两个结论"。
本判据把它们钉成一份：**改一处不改另一处就红**。
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"
AUDIT = ROOT / "tools" / "codex-scripts" / "audit-skill-roots.py"

# `cap_auto_runnable` 返回 False 时，原因**必须**落进这些门类之一。
# 换句话说：False 只许表示"要过门 / 缺参数 / 有侧效应"，**不许**表示"实现缺失"。
GATE_WORDS = ("未标 safe", "需要参数", "侧效应", "授权门", "写动作", "有后果的域", "只读")

# 一旦出现这些词，说明判据把"坏了/不存在"混进了"不能自动跑"
MISSING_WORDS = ("不存在", "缺失", "未实现", "NotImplemented", "找不到实现", "no such")


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # type: ignore[union-attr]
    return mod


class TestReachabilityAgreement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.omni = _load(OMNI, "omni_for_reach")
        cls.audit = _load(AUDIT, "audit_for_reach")
        cls.atlas = cls.omni.load_atlas()

    def test_session_roots_match_audit_loaded(self):
        """**同一份技能根清单，两个出口必须一致**（本判据是两个出口之间的锁）。"""
        mine = {str(p.resolve()) for p, _why in self.omni.SESSION_SKILL_ROOTS}
        loaded_keys = set(getattr(self.audit, "LOADED", set()))
        self.assertGreater(len(loaded_keys), 0, "审计里没有 LOADED 清单？结构变了")
        theirs = {str(p.resolve()) for k, p in self.audit.ROOTS if k in loaded_keys}

        self.assertEqual(
            mine, theirs,
            "技能根清单两个出口不一致：\n"
            "  只在 omni.SESSION_SKILL_ROOTS：%s\n"
            "  只在 audit.LOADED：%s\n"
            "⇒ 改根清单时**两处都要改**（或让一处从另一处推导）"
            % (sorted(mine - theirs), sorted(theirs - mine)))

    def test_skill_reachable_agrees_with_disk(self):
        """`skill_reachable` 不许假绿也不许假红：判定必须与盘上事实逐条一致。"""
        roots = [p for p, _ in self.omni.SESSION_SKILL_ROOTS]
        bad = []
        for sk in self.atlas["skills"]:
            if sk.get("channel") != "agent-skill":
                continue
            on_disk = any((r / sk["name"] / "SKILL.md").is_file() for r in roots)
            said, _why = self.omni.skill_reachable(sk)
            if on_disk != said:
                bad.append("%s：盘上 %s，判据说 %s（%s）"
                           % (sk["name"], "有" if on_disk else "没有", said, _why))
        self.assertEqual(bad, [],
                         "技能可达性判定与盘上不一致（%d 条）：\n  %s" % (len(bad), "\n  ".join(bad[:8])))

    def test_cap_false_never_means_missing(self):
        """**False 只许表示"要过门"，不许表示"坏了/不存在"。**"""
        wrong = []
        no_reason = []
        for c in self.atlas["caps"]:
            ok, why = self.omni.cap_auto_runnable(c)
            if ok:
                continue
            if not str(why).strip():
                no_reason.append(c["kind"])
            if any(w in str(why) for w in MISSING_WORDS):
                wrong.append("%s → %s" % (c["kind"], why))
        self.assertEqual(no_reason, [], "这些位的 False 没给理由，等于让人猜：%s" % no_reason[:8])
        self.assertEqual(
            wrong, [],
            "这些位的 False 理由在说「实现缺失」，但那是另一回事：\n  %s\n"
            "⇒ `cap_auto_runnable` 只回答「能不能免卡自动跑」，"
            "实现是否缺失要用别的判据" % "\n  ".join(wrong[:6]))

    def test_cap_false_reasons_are_known_gates(self):
        """False 的理由必须能归到已知门类 —— 出现没见过的理由说明门类漂了。"""
        unknown = []
        for c in self.atlas["caps"]:
            ok, why = self.omni.cap_auto_runnable(c)
            if ok:
                continue
            if not any(w in str(why) for w in GATE_WORDS):
                unknown.append("%s → %s" % (c["kind"], why))
        self.assertEqual(unknown, [],
                         "这些位的 False 理由不属于任何已知门类（门类名改了？）：\n  %s"
                         % "\n  ".join(unknown[:8]))

    def test_alias_does_not_diverge(self):
        """历史别名 `cap_reachable` 必须与新名 `cap_auto_runnable` 同结果（防分叉）。"""
        bad = []
        for c in self.atlas["caps"][:80]:      # 抽样即可，逻辑是同一函数
            a = self.omni.cap_auto_runnable(c)
            b = self.omni.cap_reachable(c)
            if a[0] != b[0]:
                bad.append("%s：%s ≠ %s" % (c["kind"], a, b))
        self.assertEqual(bad, [], "别名与新名结果不一致：%s" % bad[:5])

    def test_loader_hubs_are_known_roots(self):
        """「装在哪」的两个枢纽必须都在**会话根清单**里。

        否则会出现：`skills_sync` 把技能装进 `<hub>/<名>/`（加载器能看见），
        而 `omni` 的 SESSION_SKILL_ROOTS 没列这个 hub ⇒ 同一份文件两个工具两个结论。
        """
        roots = {str(p.resolve()) for p, _ in self.omni.SESSION_SKILL_ROOTS}
        hubs = {
            "home": (pathlib.Path.home() / ".agents" / "skills").resolve(),
            "repo": (ROOT / ".agents" / "skills").resolve(),
        }
        missing = {k: str(v) for k, v in hubs.items() if str(v) not in roots}
        self.assertEqual(
            missing, {},
            "这两个枢纽是技能**实际装载**的位置，但不在 SESSION_SKILL_ROOTS 里：%s\n"
            "⇒ 加载器说「装这儿」、omni 说「读不到」，又是两个出口两个结论" % missing)

    def test_existing_roots_are_real(self):
        """不存在的根要如实 —— 不许把"目录没建"当成"里面没有技能"就完事。"""
        missing = [(str(p), why) for p, why in self.omni.SESSION_SKILL_ROOTS if not p.is_dir()]
        # 允许不存在（`.dsh/skills` 本来就没建），但**必须**在清单里写着 why，
        # 且不能悄悄多出来 —— 这里只钉"清单里的每个根都有说明"。
        for path, why in missing:
            self.assertTrue(why, "根 %s 不存在却没写原因" % path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
