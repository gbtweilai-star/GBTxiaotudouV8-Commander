"""R-H611（2026-09-25）· **注入面诚实性**收成一条常设判据。

被测的四条假账（同一天撞上，都是手修的）：
  ① 三个能力总数打架（118 / 0 / 172）
  ② 两条调用法是死的（`caps/<cap_id>/run.py` 不存在 + n8n:5678 无监听）
  ③ 自我认知点名的自检命令自己崩（`awareness_gap_guard` KeyError）
  ④ 安全段是假的（从**不存在**的 `brain.cognition` 取；14 个真作用域命中 0 个）
**手修的问题是：下一个新注入块没人管。** 所以把判据收成
`tools/codex-scripts/audit-injection-honesty.py`，覆盖**所有**注入块（含将来新增的）。

判据（三条，都要有牙）：
  1. **现读必须 0 假账** —— 十段注入（插件三块 × 源稿/装机副本/负对照 + LLM system prompt）
     里，路径/模块/能力总数/历史计数/作用域五项都要对得上盘上真身；
  2. **每条规则都得咬得住**（喂进**故意做假**的样本必须报红）——
     否则"0 假账"可能只是判据瞎了；
  3. **每条规则都得放得过"引述"** —— 审计器自己不许犯「提到 ≠ 用了」（FR-1 同族）。
     这一条是本轮**首跑就被自己的假阳性打回**换来的：散文里写「python -m 包 vs 模块」、
     引号里引 `"118"`、散文里提「作用域」，原来全被误判成假账。
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDITOR = ROOT / "tools" / "codex-scripts" / "audit-injection-honesty.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_injection_honesty", AUDITOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AUD = _load()


class InjectionIsHonestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rep = AUD.audit()

    def test_auditor_actually_saw_blocks(self) -> None:
        self.assertGreaterEqual(self.rep["blocks"], 4,
                                "只查到 %d 段注入 ⇒ 判据在空转（假绿）" % self.rep["blocks"])
        self.assertIn("LLM system prompt", self.rep["block_names"])
        self.assertFalse(self.rep["diagnostics"], "有段没查成：%s" % self.rep["diagnostics"])

    def test_zero_fake_claims(self) -> None:
        self.assertEqual([], self.rep["problems"],
                         "注入面有假账：%s" % self.rep["problems"])


class RulesStillBiteTest(unittest.TestCase):
    """负对照：每条规则喂假样本必须报红（否则'0 假账'可能是瞎）。"""

    def _rules(self, text: str) -> list:
        return [b["rule"] for b in AUD.check_block("合成样本", text)]

    def test_path_rule_bites(self) -> None:
        self.assertTrue(any(r.startswith("A/") for r in self._rules("python caps/health/run.py x")))

    def test_module_rule_bites(self) -> None:
        self.assertTrue(any(r.startswith("B/") for r in self._rules("python -m no.such.module")))

    def test_count_rule_bites(self) -> None:
        self.assertTrue(any(r.startswith("C/") for r in self._rules("本框架有 118 个能力位")))

    def test_legacy_rule_bites(self) -> None:
        self.assertTrue(any(r.startswith("D/") for r in self._rules("锚点 118 就是总数")))

    def test_gate_claim_rule_bites(self) -> None:
        self.assertTrue(any(r.startswith("E/") for r in self._rules(
            "唯一授权门如下：privacy_read、filesystem_write")))


class QuotesAreNotClaimsTest(unittest.TestCase):
    """正对照：**引述**不许被判成声称（审计器自己不许犯「提到 ≠ 用了」）。"""

    def _rules(self, text: str) -> list:
        return [b["rule"] for b in AUD.check_block("合成样本", text)]

    def test_prose_mentioning_a_command_pattern_is_ok(self) -> None:
        self.assertEqual([], self._rules("修我自己一条过窄判据（python -m 包 vs 模块）"))

    def test_quoted_legacy_count_is_ok(self) -> None:
        self.assertEqual([], self._rules('已拆掉盲替换裸字面量 "118"'))

    def test_prose_mentioning_scopes_is_ok(self) -> None:
        self.assertEqual([], self._rules("F3 未清：preflight 异常 fail-open（同 N4）· 作用域相关"))

    def test_real_paths_and_packages_pass(self) -> None:
        self.assertEqual([], self._rules(
            "CLI: python tools/codex-scripts/five-dim.py cap x\n"
            "发授权: python -m gbt_allinone auth grant --scope x --ttl 600"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
