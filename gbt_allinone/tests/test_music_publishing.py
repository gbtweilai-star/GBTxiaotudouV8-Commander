# -*- coding: utf-8 -*-
"""AI 音乐发布平台 · 只读三层归位用例（R-H173）。

① 三层齐（生成端/Agent 原生端/分发端），每层都带 ring 与 role；
② **没有一个平台被写成"能用"** —— 全部 verified=False / status 未核实（在 ≠ 能用）；
③ 只读：源码里不许有出网/写盘/执行痕迹（requests / urllib / subprocess / write_text）；
④ 优先集成顺序按 Agent 就绪度写死：moltdj → noumi-mcp → distro-mcp → MusicFlow。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import music_publishing as mp  # noqa: E402


class MusicPublishingTests(unittest.TestCase):
    def test_three_classes_are_present_and_shaped(self):
        d = mp.load_music_publishing()
        self.assertTrue(d["ok"])
        self.assertEqual([c["class"] for c in d["classes"]],
                         ["generation", "agent_native", "distribution"])
        for c in d["classes"]:
            self.assertTrue(c["ring"], f"{c['class']} 缺环位")
            self.assertTrue(c["role"], f"{c['class']} 缺职责")
            self.assertEqual(c["count"], len(c["items"]))

    def test_nothing_is_claimed_to_be_usable(self):
        """在 ≠ 能用：**一个平台都不许被写成能用**。"""
        d = mp.load_music_publishing()
        self.assertEqual(d["counts"]["verified"], 0, "未核实的东西不许标 verified")
        self.assertEqual(d["counts"]["unverified"], d["counts"]["total"])
        for c in d["classes"]:
            for it in c["items"]:
                self.assertIs(it["verified"], False, f"{it['name']} 被标成已核实")
                self.assertEqual(it["status"], "未核实")

    def test_module_has_no_execution_or_network_paths(self):
        src = Path(mp.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import subprocess",
                    "import socket", ".write_text(", ".write_bytes(", "unlink("):
            self.assertNotIn(bad, src, f"只读模块里不该出现：{bad}")

    def test_priority_follows_agent_readiness(self):
        self.assertEqual(list(mp.PRIORITY), ["moltdj", "noumi-mcp", "distro-mcp", "MusicFlow"])
        names = {it["name"] for c in mp.load_music_publishing()["classes"] for it in c["items"]}
        for n in mp.PRIORITY:
            self.assertIn(n, names, f"优先项 {n} 不在登记表里")


if __name__ == "__main__":
    unittest.main()
