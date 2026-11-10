# -*- coding: utf-8 -*-
"""原生视觉实时链路固化测试（2026-11-07 主人令）。

不测“能不能看见”（那要真屏幕），只测**口径有没有被改回去**：
策略文件、五段链、400ms、AGENTS 硬口径、能力位在册。
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "tools" / "codex-scripts" / "native-vision-policy-check.py"


def _load():
    spec = importlib.util.spec_from_file_location("native_vision_policy_check", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class NativeVisionPolicyTest(unittest.TestCase):
    def test_all_checks_green(self):
        rows = _load().check()
        bad = [r for r in rows if not r["ok"]]
        self.assertFalse(bad, "原生视觉口径回归：%s" % bad)

    def test_policy_is_single_source(self):
        mod = _load()
        rows = {r["name"]: r for r in mod.check()}
        self.assertTrue(rows["policy:default_lane"]["ok"])
        self.assertTrue(rows["policy:chain"]["ok"])
        self.assertTrue(rows["agents:policy_ref"]["ok"])


if __name__ == "__main__":
    unittest.main()
