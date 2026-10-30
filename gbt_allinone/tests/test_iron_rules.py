# -*- coding: utf-8 -*-
"""十二条铁律的判据（1~3 主人令 2026-10-11 · 4~12 主人令 2026-10-30）。

硬指令正文：HEARTBEAT.md 顶部「十二条铁律」那一节；条款与实测后果见 AGENTS.md
「🔒 习惯与部署铁律」。本件只做一件事：**把那份判据挂进开机自检**，让铁律每次都现算。
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

    def test_all_twelve_rules_present(self):
        """4~12（2026-10-30 定死）必须都在，且 check() 一起判。

        锁这条的理由：铁律被"续写"进同一个入口，最容易出的问题是**新加的悄悄掉了**
        —— 脚本还能跑、还是全绿，但少判了一半。总数对不上就是掉了。
        """
        parts = self.rep.get("parts") or {}
        self.assertEqual(len(parts), 12, "铁律条数应为 12，实际 %d：%s" % (len(parts), list(parts)))
        for k in ("铁律4·双仓不许搞错", "铁律5·非法路径零容忍", "铁律6·抽屉有上限",
                  "铁律7·跳过≠通过", "铁律8·必须有负控", "铁律9·护栏只增不减",
                  "铁律10·缺字段≠假", "铁律11·全局根因单票", "铁律12·闭环真接上"):
            self.assertIn(k, parts, "缺这一条：%s" % k)

    def test_every_rule_reports_a_verdict(self):
        """每条都必须给出布尔裁决 —— 缺 ok 就等于"没法判"，不许混在全绿里。"""
        for name, v in (self.rep.get("parts") or {}).items():
            self.assertIsInstance(v.get("ok"), bool, "%s 没给布尔裁决" % name)

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
