# -*- coding: utf-8 -*-
"""点名车道（provider）三层透传的判据 —— 2026-10-14 修的那条真断线。

病案（读码逐层核实 + 真跑复现）：`cap llm_chat` 点名 `potato` 仍落到 `agnes`
（回执 `expected=agnes`）。根因是**三层各断一处**：
  ① `api.py` 的 `llm_chat` 分支调 `LLM.ask` 时压根没传 `provider`；
  ② `llm/unified.py::ask` 的 `provider` 落进 `**_ignored` 被丢；
  ③ `llm/bridge.py::chat` 签名没有 `provider` ⇒ params 不带它。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_llm_provider_lane -v`

口径（照本仓惯例）：
  · bridge / unified 两层**行为断言**，用假件替掉下层 —— **不发网、不吃票**；
  · `api` 那一层走**AST 静态断言**：`llm_chat` 是挂 `external_llm` 门的能力位，
    单测里真打既吃票又发网 ⇒ 这一层只证"接线在，且传的是 `p.get('provider')`"；
    端到端那发由 §二百八十七 的真跑读数背书。
"""
import ast
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.llm import bridge as BR      # noqa: E402
from gbt_allinone.llm import unified as U      # noqa: E402


class TestBridgeForwardsProvider(unittest.TestCase):
    def _fake(self, seen):
        class _Fake:
            def run(self, action=None, **params):
                seen.clear()
                seen.update(params)
                return {"ok": True, "reply": "x", "provider": params.get("provider") or "agnes"}
        return _Fake()

    def test_named_lane_reaches_params(self):
        seen = {}
        orig = BR._get
        BR._get = lambda: self._fake(seen)
        try:
            BR.chat("hi", provider="potato")
        finally:
            BR._get = orig
        self.assertEqual(seen.get("provider"), "potato",
                         "点名车道没进 cloud_llm 的 params（_prefer 永远收不到）")

    def test_unnamed_lane_keeps_params_unchanged(self):
        """负控：不点名时 params 里**不该出现** provider 键 —— 行为与改前一致。"""
        seen = {}
        orig = BR._get
        BR._get = lambda: self._fake(seen)
        try:
            BR.chat("hi")
        finally:
            BR._get = orig
        self.assertNotIn("provider", seen, "没点名却塞了 provider ⇒ 改了默认行为")


class TestUnifiedForwardsProvider(unittest.TestCase):
    def test_ask_passes_provider_down(self):
        got = {}
        orig = BR.chat

        def _fake(prompt, **kw):
            got.update(kw)
            return {"ok": True, "reply": "x", "provider": kw.get("provider")}

        BR.chat = _fake
        try:
            U.ask("hi", purpose="llm_chat", provider="potato")
        finally:
            BR.chat = orig
        self.assertEqual(got.get("provider"), "potato",
                         "unified.ask 把 provider 吞了（旧伤病：落进 **_ignored）")
        self.assertEqual(got.get("purpose"), "llm_chat")


class TestApiWiringIsStaticChecked(unittest.TestCase):
    def test_llm_chat_branch_passes_provider(self):
        src = (_REPO / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        hit = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            t = node.test
            is_branch = (isinstance(t, ast.Compare) and isinstance(t.left, ast.Name)
                         and t.left.id == "kind" and t.comparators
                         and isinstance(t.comparators[0], ast.Constant)
                         and t.comparators[0].value == "llm_chat")
            if not is_branch:
                continue
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                        and n.func.attr == "ask":
                    kws = {k.arg for k in n.keywords}
                    self.assertIn("provider", kws,
                                  "api.py 的 llm_chat 分支没把 provider 传给统一口（断点①）")
                    hit = True
        self.assertTrue(hit, "没在 api.py 里找到 llm_chat 分支的 ask(...) 调用")


if __name__ == "__main__":
    unittest.main(verbosity=2)
