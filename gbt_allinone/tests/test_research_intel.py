# -*- coding: utf-8 -*-
"""调研 AI 情报骨架 · 带牙用例（R-H175）。

① 三组 × 六维，一格不缺（缺了 forbidden_lists 就是"白忙"的源头）；
② 记账纪律机械生效：没出处 ⇒ 待核实；低置信 ⇒ 不进决策；verified 恒为 False；
③ 红线 2：**禁区优先于流量**（有禁区命中时，趋势再多也 hold）；
④ 红线 3：情报是输入不是指令（is_instruction=False + generator_still_has_veto=True）；
⑤ 只读：源码里不许有联网 / 写盘痕迹；执行只许本机只读 ffprobe/ffmpeg 且逐调用点钉死（2026-10-17 精确化）。
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import research_intel as ri  # noqa: E402


class CoverageTests(unittest.TestCase):
    def test_three_groups_six_dimensions_no_gap(self):
        cov = ri.coverage()
        self.assertEqual(len(cov["groups"]), 3)
        self.assertEqual(cov["cells_total"], 18, "三组 × 六维 = 18 格，一格都不能少")
        for g in ri.GROUPS:
            dims = {c["dimension"] for c in cov["cells"] if c["group"] == g}
            self.assertEqual(dims, set(ri.DIMENSIONS), f"{g} 维度不全")
        self.assertIn("forbidden_lists", ri.DIMENSIONS)
        self.assertTrue(ri.DIMENSIONS["forbidden_lists"].get("absolute"),
                        "禁区清单是唯一带『绝对』的那一维")

    def test_skeleton_does_not_pretend_to_have_intel(self):
        cov = ri.coverage()
        self.assertEqual(cov["filled"], 0, "骨架期不许有『已填』的情报")
        self.assertEqual(cov["unfilled"], cov["cells_total"])
        self.assertTrue(all(c["status"] == "待核实" for c in cov["cells"]))


class LedgerDisciplineTests(unittest.TestCase):
    def test_evidence_missing_means_unverified_and_not_usable(self):
        row = ri.make_intel("music_intel", "compliance_redlines",
                            "听说 Spotify 要下架 AI 音乐", evidence="", confidence=0.99)
        self.assertEqual(row["status"], "待核实")
        self.assertFalse(row["usable_for_decision"], "没有出处的情报不许进决策")

    def test_low_confidence_does_not_enter_decisions(self):
        row = ri.make_intel("video_intel", "traffic_trend", "某题材在涨",
                            evidence="https://example.com/policy", confidence=0.2)
        self.assertEqual(row["status"], "低置信")
        self.assertFalse(row["usable_for_decision"], "低置信不许进决策")
        good = ri.make_intel("video_intel", "traffic_trend", "某题材在涨",
                             evidence="https://example.com/policy", confidence=0.9)
        self.assertEqual(good["status"], "可用")
        self.assertTrue(good["usable_for_decision"])

    def test_verified_is_always_false_and_ids_are_department_prefixed(self):
        row = ri.make_intel("film_intel", "approval_rules", "分级规则",
                            evidence="https://example.com", confidence=0.8)
        self.assertIs(row["verified"], False, "自己不能给自己标『已核实』")
        self.assertTrue(row["intel_id"].startswith("FILM-"), "intel_id 要带部门前缀")

    def test_unknown_department_or_dimension_is_refused(self):
        with self.assertRaises(ValueError):
            ri.make_intel("sports_intel", "traffic_trend", "x", evidence="e")
        with self.assertRaises(ValueError):
            ri.make_intel("music_intel", "vibes", "x", evidence="e")
        with self.assertRaises(ValueError):
            ri.make_intel("music_intel", "traffic_trend", "  ", evidence="e")


class RedLineTests(unittest.TestCase):
    def _forbidden(self):
        return ri.make_intel("music_intel", "forbidden_lists",
                             "封面禁用某类画面", evidence="https://example.com/terms",
                             confidence=0.95, impact="high")

    def _hot_trend(self):
        return ri.make_intel("music_intel", "traffic_trend",
                             "该题材当下最火，播放量第一", evidence="https://example.com/trend",
                             confidence=0.95, impact="high")

    def test_audience_profile_must_carry_a_scene(self):
        """贯通②：用户画像维度必须带"听歌/看片场景"，否则拒绝。"""
        bad = ri.make_intel("video_intel", "audience_profile", "18-24 岁男性居多",
                            evidence="https://example.com/aud", confidence=0.9)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "scene_required")
        good = ri.make_intel("video_intel", "audience_profile",
                             "18-24 岁男性，多在深夜通勤场景刷短视频",
                             evidence="https://example.com/aud", confidence=0.9)
        self.assertEqual(good["status"], "可用", "带场景的用户画像应当通过（正常行没有 ok 键）")
        self.assertTrue(ri.DIMENSIONS["audience_profile"].get("must_scene"),
                        "must_scene 标记必须留在维度表里")

    def test_forbidden_beats_trend(self):
        out = ri.gate([self._hot_trend(), self._forbidden()])
        self.assertEqual(out["decision"], "hold", "禁区命中就必须 hold，哪怕趋势再火")
        self.assertEqual(out["trend_ignored"], 1, "被忽略的趋势条数要如实报出")

    def test_no_usable_intel_asks_human_instead_of_guessing(self):
        rows = [ri.make_intel("film_intel", "traffic_trend", "听说很火",
                              evidence="", confidence=0.9)]
        out = ri.gate(rows)
        self.assertEqual(out["decision"], "ask_human")

    def test_clean_input_proceeds_but_still_is_not_an_instruction(self):
        rows = [ri.make_intel("video_intel", "traffic_trend", "某风格在涨",
                              evidence="https://example.com/trend", confidence=0.8)]
        out = ri.gate(rows)
        self.assertEqual(out["decision"], "proceed")
        self.assertIs(out["is_instruction"], False, "情报是输入，不是指令")
        self.assertIs(out["generator_still_has_veto"], True, "生成端仍有过目权")


class ReadonlyTests(unittest.TestCase):
    def test_module_has_no_network_write_paths_and_exec_is_pinned(self):
        """只读骨架的**真实边界**：零出网 · 零写盘 · 零凭据；允许本机只读 ffprobe/ffmpeg。

        🔴 2026-10-17 翻正（留痕 · 原断言 / 为什么翻 / 现口径）：
          原断言：源码里出现 `"import subprocess"` 就红 —— 那是「本模块零执行」年代的口径。
          为什么翻：主人令要「看视频」的**真读数**，`understand()` 走本机 `ffprobe`/`ffmpeg`
            **只读**取元数据与场景切点（场景那一趟是 `-f null -`，不落盘、不出网、不碰凭据）
            ⇒ `import subprocess` 已经是设计的一部分；旧断言把**设计当故障**。
          现口径（更精确，不是放空）：
            ① 零网络库（requests/urllib/socket/http/ftplib/smtplib/telnetlib/poplib/imaplib/nntplib/ssl）；
            ② 零写盘/删除调用（write_text / write_bytes / unlink / rmtree / os.remove）；
            ③ **subprocess 只许跑 ffprobe / ffmpeg**（AST 逐调用点验 argv[0]），且必须带 `timeout=`
               —— 防"任意命令执行"悄悄长回来。判据比原来更宽的地方只有一条（允许两个只读工具），
               更严的地方有两条（argv 白名单 + timeout 强制）。
        """
        src = Path(ri.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import http",
                    "import ftplib", "import smtplib", "import telnetlib", "import poplib",
                    "import imaplib", "import nntplib", "import ssl",
                    ".write_text(", ".write_bytes(", "unlink(", "rmtree(", "os.remove(",
                    "from .store", "from ..store"):
            self.assertNotIn(bad, src, f"只读骨架里不该出现：{bad}")

        tree = ast.parse(src)
        allowed = {"ffprobe", "ffmpeg"}
        seen = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and getattr(fn.value, "id", "") == "_sp"):
                continue
            seen += 1
            argv = node.args[0] if node.args else None
            self.assertIsInstance(argv, (ast.List, ast.Tuple),
                                  "subprocess 调用必须给**列表** argv（不许 shell 字符串）")
            head = argv.elts[0] if getattr(argv, "elts", None) else None
            lit = head.value if isinstance(head, ast.Constant) else ""
            self.assertIn(lit, allowed, f"subprocess 只许跑 {sorted(allowed)}，实际：{lit!r}")
            self.assertTrue(any(k.arg == "timeout" for k in node.keywords),
                            "subprocess 调用必须带 timeout（防挂死）")
        self.assertGreater(seen, 0, "一个 subprocess 调用点都没扫到 ⇒ 扫描器自己瞎了")


if __name__ == "__main__":
    unittest.main()
