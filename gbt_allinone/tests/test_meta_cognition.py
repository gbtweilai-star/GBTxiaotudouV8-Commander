# -*- coding: utf-8 -*-
"""元认知循环 · 带牙用例（R-H200）。

① 红线①：自省不是自责 —— 出现自责词 ⇒ 拒（情绪归导演，自省归系统）；
② 红线②：不懂就问不许硬猜 —— 有缺口 ⇒ need_lookup_or_ask；`guess=True` ⇒ 拒；
③ 红线③：先查后问 —— 没查过就问 ⇒ must_look_up_first；
④ 红线④：问完必须沉淀 —— 同一问题二次提问 ⇒ already_asked_deposit_first；
⑤ 红线⑤：大脑也要自省 —— 只记触手 ⇒ brain_not_covered；
⑥ 外部查证要三个作用域（network_private / external_llm / data_export）；
⑦ 自省落点是**引用** root_fix.work_log（不另造存储）；只读：无网络/写盘路径。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import meta_cognition as mc  # noqa: E402


class ReflectionTests(unittest.TestCase):
    def test_self_blame_is_refused(self):
        loop = mc.MetaCognitionLoop()
        out = loop.reflect("T-1", gaps=[{"type": "uncertain", "note": "我太差了我真笨"}])
        self.assertFalse(out["ok"])
        self.assertEqual(out["rule"], "self_blame_not_allowed")
        self.assertIn("情绪归导演", out["why"])

    def test_gap_type_must_be_known(self):
        loop = mc.MetaCognitionLoop()
        out = loop.reflect("T-1", gaps=[{"type": "vibes"}])
        self.assertEqual(out["rule"], "unknown_gap_type")

    def test_reflection_log_is_a_reference_not_a_new_store(self):
        loop = mc.MetaCognitionLoop()
        out = loop.reflect("T-1", gaps=[{"type": "missing_param", "note": "缺 path"}])
        self.assertTrue(out["ok"])
        self.assertEqual(out["log_ref"], "root_fix.work_log")

    def test_brain_must_reflect_too(self):
        loop = mc.MetaCognitionLoop()
        loop.reflect("T-1", gaps=[{"type": "uncertain"}], scope="tentacle")
        only_tentacle = loop.report_short_boards()
        self.assertFalse(only_tentacle["ok"])
        self.assertEqual(only_tentacle["rule"], "brain_not_covered")
        loop.reflect("T-2", gaps=[{"type": "unknown_topic"}], scope="brain")
        both = loop.report_short_boards()
        self.assertTrue(both["ok"])
        self.assertIn("brain", both["scopes_seen"])
        self.assertEqual(both["bind_to"], "native_surface（原生面）")


class LoopTests(unittest.TestCase):
    def test_no_guessing_and_lookup_first_then_ask(self):
        loop = mc.MetaCognitionLoop()
        self.assertEqual(loop.decide(guess=True)["rule"], "no_guessing")
        gap = [{"type": "unknown_topic", "note": "Agnes 的限流阈值是多少"}]
        out = loop.decide(gaps=gap)
        self.assertFalse(out["ok"])
        self.assertEqual(out["reason"], "need_lookup_or_ask")
        early = loop.ask_owner("Agnes 限流阈值？", topic="agnes-limit")
        self.assertEqual(early["rule"], "must_look_up_first")
        miss = loop.look_up("agnes-limit", inside=True)
        self.assertFalse(miss["ok"])
        self.assertIn("brain_vault.py", " ".join(miss["checked"]))
        ext = loop.look_up("agnes-limit", inside=False)
        self.assertTrue(ext["ok"])
        self.assertEqual(ext["requires_scopes"], list(mc.EXTERNAL_SCOPES))
        asked = loop.ask_owner("Agnes 限流阈值？", topic="agnes-limit")
        self.assertEqual(asked["reason"], "need_owner_input")
        again = loop.ask_owner("Agnes 限流阈值？", topic="agnes-limit")
        self.assertEqual(again["rule"], "already_asked_deposit_first")
        done = loop.answer("agnes-limit", "免费档 60 次/分钟")
        self.assertTrue(done["deposited"])
        hit = loop.look_up("agnes-limit", inside=True)
        self.assertTrue(hit["ok"])
        self.assertEqual(hit["answer"], "免费档 60 次/分钟")

    def test_law_op_declares_five_red_lines(self):
        law = mc.run("law")
        self.assertEqual(len(law["red_lines"]), 5)
        joined = " ".join(law["red_lines"])
        for kw in ("不是自责", "不许硬猜", "先查后问", "必须沉淀", "大脑也要自省"):
            self.assertIn(kw, joined)
        self.assertEqual(law["log_ref"], "root_fix.work_log")

    def test_module_has_no_network_or_write_paths(self):
        src = Path(mc.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
