# -*- coding: utf-8 -*-
"""主动汇报引擎 · 全覆盖带牙用例（R-H704/R-H705）。

五轴逐一验：源 13 / 维度 8 / 门 7 / 渠道 4 / 反馈 3。
外加：覆盖矩阵必须自报缺口、自校准必须真随反馈动、正负对照必须判别。
"""
from __future__ import annotations

import ast
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import proactive_report as pr  # noqa: E402

DAY = time.mktime((2026, 9, 21, 14, 0, 0, 0, 0, -1))
NIGHT = time.mktime((2026, 9, 21, 23, 30, 0, 0, 0, -1))

GOOD = {"kind": "opportunity", "source": "opportunity",
        "text": "看到有人在收批量做落地页的活，按页结算，正好是我擅长的设计与代码。",
        "seen_before": False, "age_hours": 1, "value": 0.9,
        "new_to_owner": True, "url": "https://example.com/job"}
MEH = {"kind": "novelty", "source": "eigenflux_feed", "text": "随便一条没啥用的。"}


class AxisSourceTests(unittest.TestCase):
    def test_thirteen_sources(self):
        self.assertEqual(len(pr.SOURCES), 13)
        self.assertEqual(len(set(pr.SOURCE_KEYS)), 13, "源 key 不许重复")

    def test_every_source_declares_kind_and_wiring(self):
        for s in pr.SOURCES:
            self.assertIn(s["kind"], pr.KIND_KEYS, s["key"])
            self.assertIsInstance(s["wired"], bool, s["key"])
            if not s["wired"]:
                self.assertTrue(str(s.get("gap") or "").strip(),
                                f"{s['key']} 未接线却没写缺口理由")

    def test_wired_sources_declare_via(self):
        for s in pr.SOURCES:
            if s["wired"]:
                self.assertTrue(str(s.get("via") or "").strip(), s["key"])

    def test_sources_cover_all_four_kinds(self):
        kinds = {s["kind"] for s in pr.SOURCES}
        self.assertEqual(kinds, set(pr.KIND_KEYS), "四类汇报都要有源，不许有类别没来源")


class AxisKindTests(unittest.TestCase):
    def test_four_kinds_each_with_voice_and_why(self):
        self.assertEqual(len(pr.REPORT_KINDS), 4)
        self.assertEqual(pr.KIND_KEYS, ("novelty", "owner_need", "memory_hit", "opportunity"))
        for k in pr.REPORT_KINDS:
            self.assertIn(k["voice"], ("提醒", "意见", "建议"), k)
            self.assertTrue(k["why"].strip(), k)


class AxisDimensionTests(unittest.TestCase):
    def test_eight_dimensions(self):
        self.assertEqual(len(pr.DIMENSIONS), 8)
        self.assertEqual(len(set(pr.DIM_KEYS)), 8)
        self.assertEqual(set(pr.WEIGHTS), set(pr.DIM_KEYS))

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(pr.WEIGHTS.values()), 1.0, places=6)

    def test_every_dimension_asks_a_question(self):
        for d in pr.DIMENSIONS:
            self.assertTrue(str(d["ask"]).strip(), d["key"])

    def test_score_fills_all_eight_with_evidence(self):
        s = pr.score(GOOD, now=DAY)
        self.assertEqual(set(s["dims"]), set(pr.DIM_KEYS))
        self.assertEqual(set(s["evidence"]), set(pr.DIM_KEYS))
        for k, v in s["evidence"].items():
            self.assertTrue(str(v).strip(), k)

    def test_missing_inputs_marked_assumed(self):
        s = pr.score({"kind": "novelty", "text": "一条没标注的候选"}, now=DAY)
        joined = " ".join(str(v) for v in s["evidence"].values())
        self.assertIn("assumed", joined)

    def test_confidence_rewards_wired_source_and_evidence(self):
        lo = pr.score({"kind": "novelty", "text": "x", "source": "external_world"}, now=DAY)
        hi = pr.score({"kind": "novelty", "text": "x", "source": "eigenflux_feed",
                       "url": "https://a.b"}, now=DAY)
        self.assertGreater(hi["dims"]["confidence"], lo["dims"]["confidence"])

    def test_actionability_rewards_actionable_clue(self):
        lo = pr.score({"kind": "novelty", "text": "x"}, now=DAY)
        hi = pr.score({"kind": "novelty", "text": "x", "url": "https://a.b"}, now=DAY)
        self.assertGreater(hi["dims"]["actionability"], lo["dims"]["actionability"])

    def test_risk_dimension_present_and_used(self):
        lo = pr.score({"kind": "novelty", "text": "x"}, now=DAY)
        hi = pr.score({"kind": "novelty", "text": "x", "risk": 1.0}, now=DAY)
        self.assertGreater(hi["score"], lo["score"], "风险越高越该报")

    def test_opportunity_outscores_meh(self):
        self.assertGreater(pr.score(GOOD, now=DAY)["score"], pr.score(MEH, now=DAY)["score"])

    def test_seen_before_lowers_novelty(self):
        a = pr.score({"kind": "novelty", "text": "同一句话", "seen_before": False}, now=DAY)
        b = pr.score({"kind": "novelty", "text": "同一句话", "seen_before": True}, now=DAY)
        self.assertGreater(a["score"], b["score"])

    def test_fingerprint_punctuation_insensitive(self):
        self.assertEqual(pr.fingerprint("设计稿 转 原型。"), pr.fingerprint("设计稿转原型"))


class AxisGateTests(unittest.TestCase):
    def test_seven_gates(self):
        self.assertEqual(len(pr.GATES), 7)
        self.assertEqual(pr.GATE_KEYS, ("silent_hours", "below_threshold", "hour_budget",
                                        "day_budget", "duplicate", "owner_focused",
                                        "owner_fatigued"))

    def _scored(self, cand=GOOD, **kw):
        return pr.score(cand, now=kw.pop("now", DAY))

    def test_daytime_good_speaks(self):
        g = pr.gate(self._scored(), journal=[], now=DAY)
        self.assertTrue(g["speak"])
        self.assertEqual(g["blocked"], [])

    def test_silent_hours_blocks(self):
        g = pr.gate(self._scored(), journal=[], now=NIGHT)
        self.assertIn("silent_hours", [b["rule"] for b in g["blocked"]])

    def test_day_vs_night_differ(self):
        self.assertNotEqual(pr.gate(self._scored(), journal=[], now=DAY)["speak"],
                            pr.gate(self._scored(), journal=[], now=NIGHT)["speak"])

    def test_below_threshold_blocks(self):
        g = pr.gate(self._scored(MEH), journal=[], now=DAY)
        self.assertIn("below_threshold", [b["rule"] for b in g["blocked"]])

    def test_hour_budget_blocks(self):
        j = [{"spoken": True, "at_ts": DAY - 60 * i, "fingerprint": f"a{i}"}
             for i in range(pr.BUDGET_PER_HOUR)]
        self.assertIn("hour_budget",
                      [b["rule"] for b in pr.gate(self._scored(), journal=j, now=DAY)["blocked"]])

    def test_day_budget_blocks(self):
        j = [{"spoken": True, "at_ts": DAY - 3600 * (i + 2), "fingerprint": f"b{i}"}
             for i in range(pr.BUDGET_PER_DAY)]
        rules = [b["rule"] for b in pr.gate(self._scored(), journal=j, now=DAY)["blocked"]]
        self.assertIn("day_budget", rules)

    def test_duplicate_blocks_and_expires(self):
        s = self._scored()
        fresh = [{"spoken": True, "at_ts": DAY - 3600, "fingerprint": s["fingerprint"]}]
        old = [{"spoken": True, "at_ts": DAY - (pr.DEDUPE_WINDOW_DAYS * 86400 + 60),
                "fingerprint": s["fingerprint"]}]
        self.assertFalse(pr.gate(s, journal=fresh, now=DAY)["speak"])
        self.assertTrue(pr.gate(s, journal=old, now=DAY)["speak"], "过了窗口该放行")

    def test_owner_focused_blocks_normal_but_allows_high(self):
        lo = pr.gate(self._scored(), journal=[], now=DAY, owner_state="focused")
        self.assertIn("owner_focused", [b["rule"] for b in lo["blocked"]])
        strong = {"kind": "opportunity", "source": "opportunity", "value": 1.0,
                  "text": "设计 代码 数据 研究 写作 办公 自动化 运营 营销 赚钱 变现 工具 效率",
                  "seen_before": False, "age_hours": 0, "new_to_owner": True,
                  "url": "https://x.y", "risk": 1.0}
        hi = pr.gate(pr.score(strong, now=DAY), journal=[], now=DAY, owner_state="focused")
        self.assertTrue(hi["speak"], "够高就该穿透专注门")

    def test_owner_fatigued_blocks_normal(self):
        g = pr.gate(self._scored(), journal=[], now=DAY, owner_state="fatigued")
        self.assertIn("owner_fatigued", [b["rule"] for b in g["blocked"]])

    def test_force_bypasses_and_is_marked(self):
        g = pr.gate(self._scored(), journal=[], now=NIGHT, force=True)
        self.assertTrue(g["speak"])
        self.assertIn("留痕", g["note"])


class AxisChannelTests(unittest.TestCase):
    def test_four_channels(self):
        self.assertEqual(len(pr.CHANNELS), 4)
        self.assertEqual(pr.CHANNEL_KEYS, ("timeline", "observer", "voice", "tray"))

    def test_timeline_always_kept(self):
        self.assertIn("timeline", pr.route(loud_ok=False)["channels"])

    def test_loud_channel_only_when_loud_ok(self):
        self.assertNotIn("observer", pr.route(loud_ok=False)["channels"])
        self.assertIn("observer", pr.route(loud_ok=True)["channels"])

    def test_voice_requires_opt_in(self):
        self.assertNotIn("voice", pr.route(loud_ok=True, voice_ok=False)["channels"])
        self.assertIn("voice", pr.route(loud_ok=True, voice_ok=True)["channels"])

    def test_unwired_channels_reported(self):
        self.assertIn("tray", pr.route()["unwired_channels"])


class FeedbackTests(unittest.TestCase):
    def test_ignored_raises_threshold(self):
        base = pr.threshold_of([])["threshold"]
        j = [{"spoken": True, "at_ts": DAY, "fingerprint": f"i{i}", "feedback": "ignored"}
             for i in range(5)]
        self.assertGreater(pr.threshold_of(j)["threshold"], base)

    def test_accepted_lowers_threshold(self):
        base = pr.threshold_of([])["threshold"]
        j = [{"spoken": True, "at_ts": DAY, "fingerprint": f"a{i}", "feedback": "accepted"}
             for i in range(5)]
        self.assertLess(pr.threshold_of(j)["threshold"], base)

    def test_threshold_is_bounded(self):
        j = [{"spoken": True, "at_ts": DAY, "fingerprint": f"x{i}", "feedback": "rejected"}
             for i in range(200)]
        t = pr.threshold_of(j)["threshold"]
        self.assertLessEqual(t, pr.CALIBRATE_CEIL)
        self.assertGreaterEqual(t, pr.CALIBRATE_FLOOR)

    def test_three_feedback_states(self):
        self.assertEqual(pr.FEEDBACK_STATES, ("accepted", "ignored", "rejected"))


class CoverageMatrixTests(unittest.TestCase):
    def test_axes_counts(self):
        c = pr.coverage()
        self.assertEqual(c["axes"]["sources"]["total"], 13)
        self.assertEqual(c["axes"]["dimensions"]["total"], 8)
        self.assertEqual(c["axes"]["gates"]["total"], 7)
        self.assertEqual(c["axes"]["channels"]["total"], 4)
        self.assertEqual(c["axes"]["feedback"]["total"], 3)

    def test_cells_computed(self):
        self.assertEqual(pr.coverage()["cells"], 13 * 8 * 7 * 4)

    def test_gaps_are_registered_not_hidden(self):
        c = pr.coverage()
        self.assertEqual(c["gap_count"], len(c["gaps"]))
        self.assertGreater(c["gap_count"], 0, "确实有没接上的，必须报出来")
        for g in c["gaps"]:
            self.assertIn(g["axis"], ("source", "channel"))
            self.assertTrue(str(g["why"]).strip())

    def test_external_world_gap_is_recorded(self):
        keys = [g["key"] for g in pr.coverage()["gaps"]]
        self.assertIn("external_world", keys, "趋势源没接，必须登记")


class ComposeTests(unittest.TestCase):
    def test_short_kept_long_trimmed(self):
        self.assertFalse(pr.compose({"kind": "novelty", "text": "一句话。"})["trimmed"])
        c = pr.compose({"kind": "novelty", "text": "一。二。三。四。五。"})
        self.assertTrue(c["trimmed"])
        self.assertLessEqual(c["sentences"], 3)

    def test_empty_denied(self):
        self.assertTrue(pr.compose({"kind": "novelty", "text": ""})["denied"])

    def test_voice_follows_kind(self):
        for k in pr.REPORT_KINDS:
            self.assertEqual(pr.compose({"kind": k["key"], "text": "x。"})["voice_kind"],
                             k["voice"])


class DecideTests(unittest.TestCase):
    def test_speaks_when_gate_passes(self):
        d = pr.decide(GOOD, journal=[], now=DAY)
        self.assertTrue(d["speak"])
        self.assertIn("composed", d)
        self.assertIn("observer", d["channels"])

    def test_holds_with_reason_and_still_keeps_timeline(self):
        d = pr.decide(GOOD, journal=[], now=NIGHT)
        self.assertFalse(d["speak"])
        self.assertTrue(d["hold_reason"])
        self.assertEqual(d["channels"], ["timeline"], "压住也要留痕")

    def test_never_delivers_itself(self):
        d = pr.decide(GOOD, journal=[], now=DAY)
        self.assertFalse(d["delivered"])
        self.assertIn("只判不说", d["note"])


class IdleHuntTests(unittest.TestCase):
    def test_ranks_and_filters(self):
        h = pr.idle_hunt(candidates=[MEH, GOOD], now=DAY)
        self.assertEqual(h["ranked"][0]["candidate"], GOOD)
        self.assertEqual(len(h["found"]), 1)

    def test_empty_reported_not_invented(self):
        h = pr.idle_hunt(candidates=[], now=DAY)
        self.assertEqual(h["count"], 0)
        self.assertIn("不编", h["note"])


class ReadOnlyDisciplineTests(unittest.TestCase):
    def _source(self):
        return (ROOT / "gbt_allinone" / "tools" / "proactive_report.py").read_text(
            encoding="utf-8")

    def test_no_write_or_network(self):
        tree = ast.parse(self._source())
        banned = {"urlopen", "requests", "socket", "system", "popen",
                  "remove", "unlink", "rmtree", "write_text", "write_bytes", "mkdir"}
        offenders = [n.attr for n in ast.walk(tree)
                     if isinstance(n, ast.Attribute) and n.attr in banned]
        self.assertEqual(offenders, [], f"只读纪律被破：{offenders}")

    def test_no_network_imports(self):
        src = self._source()
        for lib in ("import requests", "import socket", "import urllib", "import subprocess"):
            self.assertNotIn(lib, src)


class EntryPointTests(unittest.TestCase):
    def test_default_op(self):
        self.assertTrue(pr.run()["ok"])

    def test_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            pr.run("nope")

    def test_all_readonly_ops_reachable(self):
        for op in ("model", "sources", "kinds", "dimensions", "gates", "channels",
                   "coverage", "threshold", "route"):
            self.assertTrue(pr.run(op)["ok"], op)

    def test_honest_boundary(self):
        self.assertIn("保证不了", pr.HONEST_BOUNDARY)


if __name__ == "__main__":
    unittest.main(verbosity=2)