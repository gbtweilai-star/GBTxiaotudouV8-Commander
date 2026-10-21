# -*- coding: utf-8 -*-
"""目录与决策校验的判据（跑法：`python -m pytest tests -q` 或 `python tests/test_catalog.py`）。

这几条判据是这一层"凭什么可信"的机器部分：
- 目录读得出来、条数与 meta 对得上；
- 检索命中要落在**该命中的域**上（正例），并且**不许乱命中**（负例）；
- 模型编一个不存在的名字，必须被判成幻觉（`ok=false`），不许放行；
- 模型回话带 ``` 包裹、带客套话时，JSON 要被正确抠出来。

其中"编名字必须被拦下"是**负对照**：判据自己也要被反向证明一次，否则它就是一句口号。
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_commander import Catalog, CommanderClient            # noqa: E402
from gbt_commander.catalog import Capability                 # noqa: E402
from gbt_commander.client import _parse_json_object          # noqa: E402


class TestCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = Catalog.load(ROOT / "data" / "capabilities.json")

    def test_loads_341(self):
        self.assertEqual(len(self.cat), 341)
        self.assertEqual(self.cat.meta.get("count"), 341)

    def test_domains_30(self):
        self.assertEqual(len(self.cat.domains()), 30)

    def test_stats_add_up(self):
        s = self.cat.stats()
        self.assertEqual(s["readonly"] + s["writes"], s["capabilities"])
        self.assertGreater(s["writes"], 0)      # 确实有会改状态的位，不是全只读
        self.assertGreater(s["needs_ticket"], 0)

    def test_scopes_parsed_not_chars(self):
        """`scopes_static` 是人话不是列表 —— 拆成单字的话这里会当场红（曾经真发生过）。"""
        zero = self.cat.get("mirror_scan")          # 零作用域那一档的代表
        self.assertEqual(zero.scopes_static, ())
        self.assertFalse(zero.needs_ticket)
        gated = self.cat.get("one_key_deploy")      # 要票那一档的代表
        self.assertIn("deploy_publish", gated.scopes_static)
        # 全目录：挂作用域的位数必须是"少数"，不是 341 位全挂
        self.assertLess(self.cat.stats()["needs_ticket"], len(self.cat))
        self.assertGreater(len(self.cat), self.cat.stats()["needs_ticket"] * 3)
        # 不许出现单字作用域（那正是把字符串当字符序列拆开的症状）
        for cap in self.cat:
            for scope in cap.scopes_static:
                self.assertRegex(scope, r"^[a-z][a-z0-9_]*$", "%s 的作用域解析坏了：%r" % (cap.name, scope))

    def test_get_roundtrip(self):
        cap = self.cat.get("mirror_scan")
        self.assertIsNotNone(cap)
        self.assertEqual(cap.name, "mirror_scan")
        self.assertEqual(cap.domain, "pipeline")

    def test_get_unknown_is_none(self):
        self.assertIsNone(self.cat.get("我编的位"))
        self.assertEqual(self.cat.get_all("我编的位"), [])

    # ---------- 正例：该命中的要命中 ----------
    def test_search_ppt_hits_genoffice(self):
        hits = self.cat.search("把 Markdown 变成 PPT", 5)
        self.assertTrue(hits, "PPT 这件事应该有落点")
        self.assertEqual(hits[0][0].name, "genoffice")
        self.assertEqual(hits[0][0].domain, "creation")

    def test_search_release_hits_pipeline(self):
        hits = self.cat.search("把这次发布推到生产", 5)
        self.assertTrue(hits)
        self.assertEqual(hits[0][0].name, "one_key_deploy")
        self.assertEqual(hits[0][0].domain, "pipeline")

    def test_search_count_words(self):
        hits = self.cat.search("统计这篇文章多少字", 3)
        self.assertEqual(hits[0][0].name, "count_words")

    def test_search_rollback(self):
        hits = self.cat.search("回滚到上一个版本", 3)
        self.assertEqual(hits[0][0].name, "pipeline_rollback")

    # ---------- 词表自身的判据（词表也是会被改的件） ----------
    def test_lexicon_names_all_exist(self):
        self.assertEqual(self.cat.lexicon_problems, [],
                         "意图词表里点到了目录里不存在的名字：%s" % self.cat.lexicon_problems)

    def test_lexicon_is_not_empty(self):
        self.assertGreaterEqual(len(self.cat.lexicon), 10)

    # ---------- 负例：不该命中的不许命中 ----------
    def test_search_gibberish_is_empty(self):
        self.assertEqual(self.cat.search("zzzqqqxxyy", 5), [])

    def test_score_zero_for_unrelated(self):
        cap = Capability(name="mirror_scan", domain="pipeline", desc="镜像体检")
        self.assertEqual(self.cat.score(cap, "zzzqqqxxyy"), 0.0)


class TestDecisionGate(unittest.TestCase):
    """不联网：直接喂模型"回话"，验校与解析这一层。"""

    def setUp(self):
        self.cat = Catalog.load(ROOT / "data" / "capabilities.json")

    def _route_with_text(self, text: str) -> dict:
        client = CommanderClient(base_url="http://127.0.0.1:9/v1", model="stub")
        client.chat = lambda *a, **k: {"ok": True, "http": 200, "elapsed_s": 0.0,
                                       "text": text, "usage": {}, "model": "stub"}
        return client.route("随便问一句", self.cat)

    def test_hallucinated_name_is_rejected(self):
        rec = self._route_with_text('{"capability":"totally_made_up","args":{},"reason":"编的"}')
        self.assertFalse(rec["ok"])
        self.assertFalse(rec["verified"])
        self.assertIn("幻觉", rec["error"])

    def test_real_name_passes_with_risk(self):
        rec = self._route_with_text('```json\n{"capability":"mirror_scan","args":{},"reason":"体检"}\n```')
        self.assertTrue(rec["ok"])
        self.assertTrue(rec["verified"])
        self.assertEqual(rec["domain"], "pipeline")
        self.assertIn(rec["risk"], {"read", "needs_gate"})

    def test_non_json_answer_rejected(self):
        rec = self._route_with_text("我觉得应该用 mirror_scan 吧")
        self.assertFalse(rec["ok"])
        self.assertIn("JSON", rec["error"])

    def test_upstream_error_passes_through(self):
        client = CommanderClient(base_url="http://127.0.0.1:9/v1", model="stub")
        client.chat = lambda *a, **k: {"ok": False, "http": 500, "error": "上游 http=500：boom"}
        rec = client.route("随便问一句", self.cat)
        self.assertFalse(rec["ok"])
        self.assertEqual(rec["error"], "上游 http=500：boom")


class TestJsonExtraction(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(_parse_json_object('{"a":1}'), {"a": 1})

    def test_with_prose_and_fence(self):
        text = '当然可以：\n```json\n{"capability":"x","args":{"k":1}}\n```\n以上。'
        self.assertEqual(_parse_json_object(text), {"capability": "x", "args": {"k": 1}})

    def test_broken_returns_none(self):
        self.assertIsNone(_parse_json_object("{不是 json}"))
        self.assertIsNone(_parse_json_object(""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
