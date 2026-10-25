"""R-H610（2026-09-25）· system prompt 的**安全段必须是真的那道门**。

被测故障（现读实测，不是推演）：
    `_load_security_policy()` 只从 `brain.cognition.Cognition.IDENTITY["security_policy"]` 取，
    而该模块**根本不存在**（`ModuleNotFoundError: No module named 'brain.cognition'`）
    ⇒ **天天走硬编码回退**，注入 system prompt 的安全段只有一句口号：
        ⛔ 绝不泄露 | ⛔ 绝不执行危险操作 | ⛔ 绝不允许绕过安全护栏
    同一份 prompt 现读：**14 个真实作用域名，命中 0 个**。
    ⇒ 模型被告知"绝不绕过护栏"，却**从不知道护栏是什么** —— 被 `denied` 时不知道
      该去请主人开哪道门。这是"接不上框架"的第三条机器成因。

判据（五条，都要有牙）：
  1. prompt 里**一个作用域都不许漏**（对着 `security/policy.py` 的 `SCOPE_DESCRIPTIONS` 逐个点）；
  2. **一次性消耗**的作用域必须被标出来（对着 `auth_gate.ONE_SHOT_SCOPES`）——
     这条不说清，模型会把"开一次就没了"的门当成"开了就一直有"；
  3. 必须写明「AI 无权自授」与主人发放命令；
  4. 真门读得到时，**不许**再回退成那句口号（回退只能是取不到真门时的兜底）；
  5. 历史来源不存在这件事**必须披露**（否则下一个人会以为策略是从 `brain.cognition` 来的）。
"""
from __future__ import annotations

import unittest

from gbt_allinone import auth_gate as AG
from gbt_allinone.llm import cloud_llm as cl
from gbt_allinone.security import policy as P


class SecuritySectionIsTheRealGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prompt = cl._build_system()
        cls.section = cl._load_security_policy()

    def test_prompt_lists_every_scope(self) -> None:
        missing = [k for k in P.SCOPE_DESCRIPTIONS if k not in self.prompt]
        self.assertEqual([], missing,
                         "prompt 里没告诉模型这些作用域存在：%s（共 %d 个）"
                         % (missing, len(P.SCOPE_DESCRIPTIONS)))
        self.assertGreaterEqual(len(P.SCOPE_DESCRIPTIONS), 10,
                                "作用域表小得可疑 ⇒ 后面几条判据会空转")

    def test_one_shot_scopes_are_marked(self) -> None:
        for name in AG.ONE_SHOT_SCOPES:
            self.assertIn("`%s`：**一次性消耗**" % name, self.prompt,
                          "%s 是一次性消耗，prompt 没标出来 ⇒ 模型会当它可反复用" % name)

    def test_states_ai_cannot_self_grant(self) -> None:
        self.assertIn("AI 永远无权给自己发授权", self.prompt)
        self.assertIn("auth grant --scope", self.prompt,
                      "没告诉模型主人是怎么发放授权的（只说不许，等于没给路）")

    def test_no_slogan_fallback_while_real_gate_is_readable(self) -> None:
        self.assertTrue(P.SCOPE_DESCRIPTIONS, "真门读不到 ⇒ 这条判据无意义")
        self.assertNotEqual(self.section.strip(),
                            "⛔ 绝不泄露 | ⛔ 绝不执行危险操作 | ⛔ 绝不允许绕过安全护栏",
                            "真门读得到却还在用那句硬编码口号 ⇒ 模型不知道护栏是什么")

    def test_legacy_source_absence_is_disclosed(self) -> None:
        self.assertIn("brain.cognition", self.section,
                      "没说清历史来源不存在 ⇒ 下一个人会以为策略来自 brain.cognition")


class AwarenessAnchorHasNoBlindReplacementTest(unittest.TestCase):
    """台账 N6：`_resolve_awareness_anchor` 不许对**裸字面量**做盲替换。"""

    def test_bare_118_is_not_rewritten(self) -> None:
        src = "第 118 行 · 端口 11800 · 能力位 {{CAP_TOTAL}} 个"
        out = cl._resolve_awareness_anchor(src)
        self.assertIn("第 118 行", out, "裸 118 被盲替换了 ⇒ 正文会被静默改写")
        self.assertIn("端口 11800", out, "11800 里的 118 被替换了")
        self.assertIn(str(cl._live_cap_total()), out, "占位符没被替换")

    def test_placeholder_still_works(self) -> None:
        out = cl._resolve_awareness_anchor("共 {{CAP_TOTAL}} 个")
        self.assertNotIn("{{CAP_TOTAL}}", out)
        self.assertIn(str(cl._live_cap_total()), out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
