# -*- coding: utf-8 -*-
"""未命中即取源判据（self_intake）。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import self_intake as SI  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


def _scopes(payload):
    d = policy.evaluate("self_intake", payload or {})
    return sorted(getattr(d, "scopes", ()) or ())


class GateTest(unittest.TestCase):

    def test_unknown_topic_is_refused(self):
        """主判据：本地未命中且无出处 ⇒ **拒绝干活**。"""
        r = SI.run("gate", topic="zzz_一个不存在的概念_不可能有出处")
        self.assertFalse(r["ok"])
        self.assertTrue(r["denied"])
        self.assertEqual(r["rule"], "no_knowledge_no_source")
        self.assertEqual(r["next_action"], "intake")
        self.assertIn("self_intake", r["how"])

    def test_source_ref_that_exists_passes(self):
        r = SI.run("gate", topic="zzz_一个不存在的概念_不可能有出处",
                   source_ref="AGENTS.md")
        self.assertTrue(r["ok"])
        self.assertEqual(r["basis"], "source_ref")

    def test_source_ref_that_does_not_exist_is_refused(self):
        r = SI.run("gate", topic="zzz_一个不存在的概念", source_ref="no/such/file.md")
        self.assertFalse(r["ok"])
        self.assertEqual(r["rule"], "source_ref_missing")

    def test_gate_needs_topic(self):
        r = SI.run("gate")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "need_topic")


class KnownTest(unittest.TestCase):

    def test_known_returns_hit_or_honest_miss(self):
        r = SI.run("known", topic="休谟 趣味")
        self.assertTrue(r["ok"])
        if not r["known"]:
            self.assertEqual(r["next_action"], "intake")
            self.assertIn("rule", r)


class IntakeTest(unittest.TestCase):

    def test_no_source_fetched_is_honest(self):
        r = SI.run("intake", topic="空源测试", urls=["http://127.0.0.1:1/nope"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "no_source_fetched")
        self.assertTrue(r["failed"])

    def test_local_file_intake_then_known_hits(self):
        """递归：取源 → 入库 → 再查就命中。"""
        topic = "判据测试_铝合金焊接工艺"
        r = SI.run("intake", topic=topic, files=["AGENTS.md"], lang="zh")
        self.assertTrue(r["ok"], r)
        self.assertGreater(r["sources"], 0)
        k = SI.run("known", topic=topic)
        self.assertTrue(k["known"], "intake 后必须命中" if r["indexed"] else "")
        # 收尾：删掉这次测试造的胶囊与护照（不留垃圾）
        for p in (r.get("capsule"), r.get("passport")):
            if p and Path(p).is_file():
                Path(p).unlink()
        for d in (ROOT / "gbt_allinone" / "store" / "devoured").glob("*铝合金*"):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)

    def test_intake_needs_topic(self):
        r = SI.run("intake")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "need_topic")


class RulesAndGateTest(unittest.TestCase):

    def test_rules_state_the_executor_is_the_plug(self):
        r = SI.run("rules")
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["loop"]), 5)
        self.assertEqual(len(r["iron_laws"]), 5)

    def test_read_ops_zero_scope_write_needs_grant(self):
        for op in SI.READ_OPS:
            with self.subTest(op=op):
                self.assertEqual(_scopes({"op": op}), [])
        self.assertEqual(_scopes({"op": "intake"}), ["filesystem_write"])

    def test_unknown_op_fails_closed(self):
        r = SI.run("nope")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")
        self.assertIn("executor", r)


class DirectionTest(unittest.TestCase):

    def test_miss_carries_direction_from_graph(self):
        from gbt_allinone import topic_web as TW
        TW.run("build", items=[
            {"id": "d1", "source": "HN", "title": "agentic pentest",
             "text": "Agentic pentest. Red team.", "tags": ["Agent安全"]},
            {"id": "d2", "source": "X", "title": "Anthropic Cyber Verification",
             "text": "Anthropic expands Cyber Verification.", "tags": ["Agent安全"]},
        ])
        r = SI.run("gate", topic="Agent安全边界实验")
        self.assertEqual(r["rule"], "no_knowledge_no_source")
        d = r.get("direction") or {}
        self.assertTrue(d.get("anchors"))
        self.assertTrue(d.get("suggest_terms"))


class VetGateTest(unittest.TestCase):
    """入库验证门（2026-10-29 主人指的「最大的隐患」）：取到 ≠ 有效。

    🔴 要咬住的关键区分（GBT 深度思考里自己点破的）：
       「来源死」（网络不通 ⇒ fetch 失败）与「内容坏」（fetch 成功但内容是垃圾）
       是**两回事**，混在一起就会把「仪器坏了」误判成「来源死了」。
    """

    def test_valid_source_passes(self):
        v, why = SI._vet_source(
            "铝合金的焊接需要先去除表面氧化膜，采用交流钨极氩弧焊，焊接电流通常取六十到一百二十安培之间，"
            "焊后还需进行固溶处理以恢复焊缝区域的耐腐蚀性能。")
        self.assertEqual(v, "ok", why)

    def test_empty_shell_is_vetoed(self):
        v, _ = SI._vet_source("ok")
        self.assertEqual(v, "empty_shell")

    def test_login_or_error_page_is_vetoed(self):
        v, _ = SI._vet_source(
            "Cloudflare 正在检查您的浏览器。verify you are human. 请完成下方的 captcha 验证码，"
            "通过验证后即可继续访问本页面。请不要关闭本窗口，验证通常只需几秒钟。")
        self.assertEqual(v, "login_or_error")

    def test_long_doc_mentioning_cloudflare_passes(self):
        """🔴 负对照：长文档正文提到 cloudflare 是正常引用，不许误伤（AGENTS.md 实测踩过）。"""
        doc = "Cloudflare Tunnel 用于把本地推理服务反向暴露成公网 HTTPS 地址，它零配置、免流量。\n" * 25
        self.assertGreater(len(doc), SI._VET_BLOCK_MAX_CHARS)
        v, _ = SI._vet_source(doc)
        self.assertEqual(v, "ok")

    def test_intake_all_vetoed_does_not_write_capsule(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.txt"
            bad.write_text("captcha 验证码 please enable javascript", encoding="utf-8")
            topic = "判据测试_垃圾源不该入库"
            r = SI.run("intake", topic=topic, files=[str(bad)])
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["reason"], "all_sources_vetoed")
            self.assertEqual(r["vetoed"][0]["url"], str(bad))
        self.assertEqual(list(SI.DEVOURED.glob("*垃圾源不该入库*")), [],
                         "全被拦下时不许写胶囊、不许吞垃圾")

    def test_source_dead_vs_content_bad_are_distinct(self):
        # 来源死：fetch 抛异常 ⇒ no_source_fetched（不是「内容坏」）
        r1 = SI.run("intake", topic="死源测试", urls=["http://127.0.0.1:1/nope"])
        self.assertEqual(r1["reason"], "no_source_fetched")
        # 内容坏：fetch 成功但内容是垃圾 ⇒ all_sources_vetoed（不是「来源死」）
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.txt"
            bad.write_text("login 请登录后访问", encoding="utf-8")
            r2 = SI.run("intake", topic="坏源测试", files=[str(bad)])
            self.assertEqual(r2["reason"], "all_sources_vetoed")


class VetVerifyTest(unittest.TestCase):
    """模型级验真（新能力）：`_parse_verdict` 是纯函数；`verify` 参数默认关、显式开才调免费车道。"""

    def test_parse_verified(self):
        v, _ = SI._parse_verdict("verified")
        self.assertEqual(v, "verified")

    def test_parse_unverified_wins_over_substring(self):
        """🔴 负对照：unverified 含 verified 子串，先判 unverified 才不会把「不可对账」判成「可对账」。"""
        v, _ = SI._parse_verdict("unverified")
        self.assertEqual(v, "unverified")

    def test_parse_empty_is_unavailable(self):
        v, _ = SI._parse_verdict("")
        self.assertEqual(v, "unavailable")

    def test_parse_garbage_is_unavailable(self):
        v, _ = SI._parse_verdict("这是一段完全读不出的乱码回复 xyzzy qwerty")
        self.assertEqual(v, "unavailable")

    def test_verify_off_keeps_behavior(self):
        """verify=False（默认）：不调模型，行为与之前完全一致，verify 返回 None。"""
        import tempfile as _tf
        with _tf.TemporaryDirectory() as td:
            good = Path(td) / "good.txt"
            good.write_text("铝合金的焊接需要先去除表面氧化膜，采用交流钨极氩弧焊，焊接电流通常取六十到一百二十安培之间，"
                            "焊后还需进行固溶处理以恢复焊缝区域的耐腐蚀性能。", encoding="utf-8")
            topic = "判据测试_verify_off"
            r = SI.run("intake", topic=topic, files=[str(good)])
            self.assertTrue(r["ok"], r)
            self.assertIsNone(r.get("verify"))
            for p in (r.get("capsule"), r.get("passport")):
                if p and Path(p).is_file():
                    Path(p).unlink()
            for d in SI.DEVOURED.glob("*verify_off*"):
                if d.is_dir():
                    shutil.rmtree(d, ignore_errors=True)

    def test_verify_on_records_verdict(self):
        """verify=True：真调免费车道（这里 mock 掉，不真出网），验真结论记入 return。"""
        import tempfile as _tf
        from unittest import mock
        with _tf.TemporaryDirectory() as td:
            good = Path(td) / "good.txt"
            good.write_text("铝合金的焊接需要先去除表面氧化膜，采用交流钨极氩弧焊，焊接电流通常取六十到一百二十安培之间，"
                            "焊后还需进行固溶处理以恢复焊缝区域的耐腐蚀性能。", encoding="utf-8")
            topic = "判据测试_verify_on"
            with mock.patch.object(SI, "_verify_knowledge", return_value=("verified", "mock")):
                r = SI.run("intake", topic=topic, files=[str(good)], verify=True)
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["verified"], 1)
            self.assertEqual(r["verify"][0]["verdict"], "verified")
            for p in (r.get("capsule"), r.get("passport")):
                if p and Path(p).is_file():
                    Path(p).unlink()
            for d in SI.DEVOURED.glob("*verify_on*"):
                if d.is_dir():
                    shutil.rmtree(d, ignore_errors=True)


class DevourOpsTest(unittest.TestCase):
    """GBT 说的 plan/batch/rejudge/ledger：零写盘预演 / 幂等 / 重判 / 看账。"""

    def _good_file(self):
        import tempfile
        td = tempfile.TemporaryDirectory()
        good = Path(td.name) / "good.txt"
        good.write_text("铝合金的焊接需要先去除表面氧化膜，采用交流钨极氩弧焊，焊接电流通常取六十到一百二十安培之间，焊后还需进行固溶处理以恢复焊缝区域的耐腐蚀性能。", encoding="utf-8")
        return td, str(good)

    def test_plan_is_zero_write(self):
        """🔴 GBT 说的「plan 假预演」正解：判定对，但不落胶囊、不入库、不记账。"""
        td, good = self._good_file()
        topic = "判据测试_plan_zero_write"
        try:
            before = len(list(SI.DEVOURED.glob("*plan_zero_write*")))
            r = SI.run("plan", topic=topic, files=[good])
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["预演"]["会吞"], 1)
            self.assertEqual(r["预演"]["会拒"], 0)
            after = len(list(SI.DEVOURED.glob("*plan_zero_write*")))
            self.assertEqual(after, before, "plan 不许落胶囊（账不多一条）")
        finally:
            td.cleanup()

    def test_plan_vetoes_garbage(self):
        td, _ = self._good_file()
        bad = Path(td.name) / "bad.txt"
        bad.write_text("captcha 验证码 请完成验证后访问本页", encoding="utf-8")
        try:
            r = SI.run("plan", topic="判据测试_plan_veto", files=[str(bad)])
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["预演"]["会拒"], 1)
            self.assertEqual(r["预演"]["会吞"], 0)
        finally:
            td.cleanup()

    def test_batch_is_idempotent(self):
        """🔴 幂等：同 topic 同源已吞过 → batch 报跳过，不再吞。"""
        td, good = self._good_file()
        topic = "判据测试_batch_idempotent"
        try:
            r1 = SI.run("intake", topic=topic, files=[good])
            self.assertTrue(r1["ok"], r1)
            r2 = SI.run("batch", items=[{"topic": topic, "files": [good]}])
            self.assertTrue(r2["ok"], r2)
            self.assertEqual(r2["跳过"], 1, r2)
            self.assertEqual(r2["该吞"], 0, r2)
            for p in (r1.get("capsule"), r1.get("passport")):
                if p and Path(p).is_file():
                    Path(p).unlink()
            for d in SI.DEVOURED.glob("*batch_idempotent*"):
                if d.is_dir():
                    shutil.rmtree(d, ignore_errors=True)
        finally:
            td.cleanup()

    def test_ledger_lists_rows(self):
        r = SI.run("ledger")
        self.assertTrue(r["ok"], r)
        self.assertGreaterEqual(r["count"], 0)

    def test_rejudge_reports(self):
        r = SI.run("rejudge")
        self.assertTrue(r["ok"], r)
        self.assertIn("会拒", r)

    def test_capsule_excerpts_not_fooled_by_h3(self):
        """🔴 负对照：胶囊含 `### https://…` 三级标题时，抽取不能在这里断（WCAG 实测踩过）。"""
        capsule_text = (
            "# 胶囊 · 某主题\n\n## 一、取到的源\n\n- `https://x/y`（500 字符）\n\n"
            "## 二、原文摘录（只摆原文，不转述）\n\n### https://x/y\n\n> " +
            "这是一段足够长的、可对账的原文内容。" * 10 +
            "\n\n## 三、人工补注\n\n---\n"
        )
        import tempfile as _tf
        with _tf.TemporaryDirectory() as td:
            p = Path(td) / "c.md"
            p.write_text(capsule_text, encoding="utf-8")
            exc = SI._capsule_excerpts(str(p))
            self.assertGreater(len(exc), 100, "抽取不该在 ### 处断掉（会误判空壳）")


class ChainAndMatchTest(unittest.TestCase):

    def test_chain_all_three_present(self):
        r = SI.run("chain")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["missing"], [])
        self.assertEqual([s["capsule_id"] for s in r["steps"]],
                         ["high-iq-g-factor", "design-thinking-dschool", "hume-aesthetics"])

    def test_chain_is_fail_closed(self):
        old = SI.CHAIN
        try:
            SI.CHAIN = old + [{"step": 9, "name": "不存在的第四件",
                              "capsule_id": "no-such-capsule-zzz", "keys": ["zzz不存在"],
                              "rule": "x"}]
            r = SI.run("chain")
            self.assertFalse(r["ok"])
            self.assertIn("no-such-capsule-zzz", r["missing"])
        finally:
            SI.CHAIN = old

    def test_title_match_beats_body_crosstalk(self):
        r = SI.run("known", topic="高智商")
        self.assertTrue(r["known"], r)
        self.assertEqual(r["matched_in"], "title")
        self.assertIn("高智商", str(r["matched"]))
        self.assertNotIn("设计思维", str(r["matched"]))

    def test_new_capsules_are_hits(self):
        for q in ("高智商 g因子", "设计思维 d.school"):
            with self.subTest(q=q):
                self.assertTrue(SI.run("known", topic=q)["known"], q)



if __name__ == "__main__":
    unittest.main(verbosity=2)
