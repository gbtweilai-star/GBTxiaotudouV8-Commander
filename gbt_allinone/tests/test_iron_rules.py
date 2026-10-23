# -*- coding: utf-8 -*-
"""三条铁律的判据（主人令 2026-10-11：禁止脑补 / 必须带参 / 先纠错再回答）。

硬指令正文：HEARTBEAT.md 顶部「三条铁律」那一节。
本件只做一件事：**把那份判据挂进开机自检**，让三条铁律每次都现算。
判据只有一份 —— 本件**不重写**读数，只调 tools/codex-scripts/iron-rules-check.py。
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "iron-rules-check.py"


def _load():
    spec = importlib.util.spec_from_file_location("iron_rules_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestIronRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()
        cls.rep = cls.m.check()

    def test_three_rules_present(self):
        for k in ("铁律1·禁止脑补", "铁律2·必须带参", "铁律3·先纠错再回答"):
            self.assertIn(k, self.rep.get("parts") or {}, "缺这一条：%s" % k)

    def test_rule1_shape_is_cmd_plus_expect(self):
        r = self.rep["parts"]["铁律1·禁止脑补"]
        self.assertIsInstance(r.get("claims"), int, "铁律1 没读数")

    def test_rule2_scans_active_scripts_only(self):
        r = self.rep["parts"]["铁律2·必须带参"]
        self.assertIsInstance(r.get("calls"), int, "铁律2 没读数")

    def test_rule3_corrections_ledger_exists(self):
        f = ROOT / "state" / "corrections.jsonl"
        self.assertTrue(f.is_file(), "纠正台账没建（铁律3 要它留痕）")

    def test_negative_control_no_name_caught(self):
        probe = 'wrangler deployments list'
        m = self.m.WRANGLER_CALL.search(probe)
        self.assertTrue(m and not self.m.HAS_NAME.search(probe),
                        "无 --name 的 wrangler 调用必须被抓（负控）")

    def test_positive_control_with_name_not_caught(self):
        good = 'wrangler deployments list --name gbt-potato-cloud-10'
        m = self.m.WRANGLER_CALL.search(good)
        self.assertTrue(m and self.m.HAS_NAME.search(good),
                        "带 --name 的不该被抓（正控）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
