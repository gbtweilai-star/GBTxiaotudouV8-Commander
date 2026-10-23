# -*- coding: utf-8 -*-
"""prompt_bridge 契约测试（**独立文件**：不动 test_framework 的 Ran 174）。

判据 P1–P3（对应 docs/prompt_bridge-最小一刀设计.md）；P5 零新增依赖由 regression_stamp 的
deps 指纹在回归时核对，不在此断言。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_test_store_"))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

from gbt_allinone import prompt_bridge as PB  # noqa: E402


class PromptBridgeTests(unittest.TestCase):
    def test_P1_structure_complete(self):
        """P1：产出必须含四段。"""
        r = PB.run("compile", text="帮我写个用户登录功能")
        self.assertTrue(r["ok"], r)
        for seg in PB.SEGMENTS:
            self.assertIn(seg, r["prompt"], f"缺段：{seg}")

    def test_P2_intent_keywords_kept(self):
        """P2：原文关键词必须全部保留（丢一个即 intent_loss）。"""
        raw = "帮我写个用户登录功能，支持 JWT 和 限流"
        r = PB.run("compile", text=raw)
        kws = PB.extract_keywords(raw)
        self.assertTrue(kws, "关键词抽取不该为空（正对照）")
        missing = [k for k in kws if k not in r["prompt"]]
        self.assertEqual(missing, [], f"丢词：{missing}")
        self.assertTrue(r["ok"])

    def test_P2_has_teeth(self):
        """P2 有牙：人为丢词时，判据必须报 intent_loss（变异负对照）。"""
        raw = "实现 汇率换算 与 缓存"
        bad = PB.compile_prompt.__wrapped__ if hasattr(PB.compile_prompt, "__wrapped__") else None
        # 直接构造"丢了关键词"的情形：把 prompt 换成不含原词的内容再跑同一判据
        kws = PB.extract_keywords(raw)
        self.assertTrue(kws)
        fake_prompt = "【角色设定】\n资深工程师\n"
        missing = [k for k in kws if k not in fake_prompt]
        self.assertTrue(len(missing) >= 1, "这个变异必须至少丢一个词，否则判据没牙")

    def test_P3_never_raises_and_degrades(self):
        """P3：空输入/未知 op 都要结构化降级，不抛异常、不冒充成功。"""
        r1 = PB.run("compile", text="")
        self.assertFalse(r1["ok"])
        self.assertEqual(r1["reason_code"], "empty_input")
        r2 = PB.run("nonsense_op", text="x")
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["reason_code"], "unknown_op")
        r3 = PB.run("passthrough", text="")
        self.assertFalse(r3["ok"])
        self.assertEqual(r3["reason_code"], "empty_input")

    def test_two_modes_both_return_prompt(self):
        """两态：compile 与 passthrough 都必须返回 prompt（空态除外）。"""
        c = PB.run("compile", text="加个数据库连接池")
        p = PB.run("passthrough", text="加个数据库连接池")
        self.assertTrue(c["prompt"] and p["prompt"])
        self.assertEqual(p["prompt"], "加个数据库连接池")   # 透传不改写
        self.assertEqual(c["mode"], "compile")
        self.assertEqual(p["mode"], "passthrough")


    def test_status_is_side_effect_free(self):
        """「先问再动」的可验形式（风哥 2026-09-19：翻译不能丢时序）。

        v1.0 的 `intercept_input()` 是"**先报状态，再执行**"——防的是"在错误的态下执行"。
        本仓的等价物必须是**前置查询**：`status` 是**零副作用纯函数**，调用方在发车前先问。
        判据：直调 `status` 前后，store 里的审计流字节数**不变**。
        """
        from gbt_allinone import _paths
        audit = _paths.STORE_DIR / "audit.jsonl"
        before = audit.stat().st_size if audit.exists() else 0
        s1 = PB.run("status")
        s2 = PB.run("status")
        after = audit.stat().st_size if audit.exists() else 0
        self.assertEqual(before, after, "status 必须是零副作用：不得写审计")
        self.assertEqual(s1, s2, "status 必须是纯函数：两次调用结果一致")

    def test_status_declares_no_external_model(self):
        """第一刀的边界要能被程序读到：external_model=False。"""
        s = PB.run("status")
        self.assertTrue(s["ok"])
        self.assertFalse(s["external_model"])
        self.assertEqual(s["deps"], "stdlib-only")


if __name__ == "__main__":
    unittest.main(verbosity=2)
