# -*- coding: utf-8 -*-
"""主题共现网判据（topic_web）。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import topic_web as TW  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402

ITEMS = [
    {"id": "a1", "source": "The Hacker News", "title": "agentic pentest",
     "text": "Agentic pentest claims autonomous discovery. Red team evaluation.",
     "tags": ["Agent安全", "红队"]},
    {"id": "a2", "source": "X / Anthropic", "title": "Anthropic expands Cyber Verification",
     "text": "Anthropic expands the Cyber Verification Program. Red team screening.",
     "tags": ["Agent安全", "红队"]},
    {"id": "a3", "source": "HF Daily", "title": "VICS-G navigation safety",
     "text": "Frozen VLA policies may block safe task completion.",
     "tags": ["Agent安全", "防御与护栏"]},
]


class BuildTest(unittest.TestCase):

    def test_build_from_inline_items(self):
        r = TW.run("build", items=ITEMS)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["items_used"], 3)
        self.assertGreaterEqual(r["nodes"], 2)
        self.assertGreaterEqual(r["edges"], 1)

    def test_every_edge_carries_evidence(self):
        """主判据：边必须能回指**共现于哪几条料**。"""
        TW.run("build", items=ITEMS)
        g = TW._load()
        for e in g["edges"]:
            self.assertTrue(e.get("items"), e)
            self.assertGreaterEqual(e["weight"], 1)

    def test_tags_win_over_fragments(self):
        """标签优先：“Agent安全”不能被拆成 Agent + 安全。"""
        r = TW.run("build", items=ITEMS)
        ids = {n["id"] for n in TW._load()["nodes"]}
        self.assertIn("Agent安全", ids)
        self.assertNotIn("安全", ids)

    def test_no_items_is_honest(self):
        r = TW.run("build", items=[{"id": "x", "text": "hi"}])
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "no_items")


class QueryTest(unittest.TestCase):

    def setUp(self):
        TW.run("build", items=ITEMS)

    def test_neighbors_lists_cooccurring_with_evidence(self):
        r = TW.run("neighbors", entity="Agent安全")
        self.assertTrue(r["ok"], r)
        self.assertGreater(r["count"], 0)
        for x in r["neighbors"]:
            self.assertTrue(x.get("evidence"))

    def test_unknown_entity_is_honest(self):
        r = TW.run("neighbors", entity="根本不存在的实体zzz")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "no_such_entity")

    def test_path_between_connected_entities(self):
        r = TW.run("path", a="Agent安全", b="红队")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["hops"], 1)

    def test_path_needs_two_entities(self):
        self.assertFalse(TW.run("path", a="x")["ok"])


class ApiContractTest(unittest.TestCase):

    def test_unknown_op_fails_closed(self):
        r = TW.run("nope")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")
        self.assertIn("executor", r)

    def test_read_ops_zero_scope_build_needs_write(self):
        for op in TW.READ_OPS:
            with self.subTest(op=op):
                d = policy.evaluate("topic_web", {"op": op})
                self.assertEqual(sorted(getattr(d, "scopes", ()) or ()), [])
        d = policy.evaluate("topic_web", {"op": "build"})
        self.assertEqual(sorted(getattr(d, "scopes", ()) or ()), ["filesystem_write"])


class AxisTest(unittest.TestCase):

    def setUp(self):
        # 判据之间必须隔离：AxisTest 按字母序最先跑，不能用别人留在盘上的图
        TW.run("build", items=[
            {"id": "b1", "source": "HN", "kind": "红队", "title": "agentic pentest",
             "text": "Agentic pentest. Red team.", "tags": ["Agent安全"]},
            {"id": "b2", "source": "X", "kind": "防御", "title": "Anthropic Cyber Verification",
             "text": "Anthropic expands Cyber Verification.", "tags": ["Agent安全"]},
        ])

    def test_three_axes_are_annotated(self):
        TW.run("build", items=[
            {"id": "b1", "source": "HN", "kind": "红队", "title": "agentic pentest",
             "text": "Agentic pentest. Red team.", "tags": ["Agent安全"]},
            {"id": "b2", "source": "X", "kind": "防御", "title": "Anthropic Cyber Verification",
             "text": "Anthropic expands Cyber Verification.", "tags": ["Agent安全"]},
        ])
        g = TW._load()
        axes = {n["axis"] for n in g["nodes"]}
        self.assertIn("标签", axes)
        self.assertIn("机构", axes)
        ids = {n["id"] for n in g["nodes"]}
        self.assertIn("Anthropic", ids)

    def test_taxonomy_op(self):
        r = TW.run("taxonomy")
        self.assertTrue(r["ok"])
        for axis in ("标签", "类型", "机构"):
            self.assertGreater(r["axes"][axis], 0)

    def test_cross_axis_path(self):
        r = TW.run("path", a="Anthropic", b="Agent安全")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["hops"], 1)


class WatermarkAndScoreTest(unittest.TestCase):

    def setUp(self):
        TW.run("build", items=[
            {"id": "c1", "source": "S-A", "ts": "2020-01-01T00:00", "title": "old",
             "text": "Agent安全 old item text", "tags": ["Agent安全"]},
            {"id": "c2", "source": "S-B", "title": "no ts",
             "text": "Agent安全 no timestamp item", "tags": ["Agent安全"]},
        ])

    def test_sources_watermark_records_last_seen(self):
        r = TW.run("sources")
        self.assertTrue(r["ok"])
        rows = {x["source"]: x for x in r["sources"]}
        self.assertIn("S-A", rows)
        self.assertEqual(rows["S-A"]["last_seen_ts"], "2020-01-01T00:00")
        self.assertEqual(rows["S-B"]["last_seen_ts"], "")

    def test_rank_is_explainable(self):
        # 显式给料：不给就读她自己的语料（胶囊多无时间戳）
        r = TW.run("rank", limit=5, items=[
            {"id": "c1", "source": "S-A", "ts": "2020-01-01T00:00",
             "text": "Agent安全 old", "tags": ["Agent安全"]},
            {"id": "c2", "source": "S-B", "text": "Agent安全 no ts",
             "tags": ["Agent安全"]},
        ])
        self.assertTrue(r["ok"])
        self.assertEqual(r["ts_missing"], 1)
        for row in r["ranked"]:
            comp = row["components"]
            self.assertAlmostEqual(row["score"],
                                   round(comp["source_weight"] * comp["recency"] * comp["tag_hits"], 4),
                                   places=3)



if __name__ == "__main__":
    unittest.main(verbosity=2)
