# -*- coding: utf-8 -*-
"""LibTV 节点式工作流 · 带牙用例（R-H246）。

① 五动作与已落两套**全不相同**（真新增量）；
② 五大基础节点齐（含**脚本节点**这个「生产」节点）；
③ 参数契约：`-s` 走 schema（**schema 外的键会被拒**）/ `-u` 顶层属性 / 历史默认；
④ 两条避坑各有闸：资源组必须绑定 / 终点节点必须抑制 stdout；
⑤ 四条红线**与已落的一字不差**（引用，不新造）；
⑥ 来源如实：**主人提供 · 盘上无命中 · 未独立取证**；
⑦ 只读骨架不许有建节点/连线/网络/写盘路径；登记在册且**落地即接线**。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import libtv_workflow as lw  # noqa: E402
from gbt_allinone.tools import orchestration_kernel as ok  # noqa: E402
from gbt_allinone import caps_registry as CR  # noqa: E402


class ShapeTests(unittest.TestCase):
    def test_five_actions_are_new(self):
        got = [a["key"] for a in lw.run("actions")["actions"]]
        self.assertEqual(got, ["create_node", "connect", "set_params",
                               "run", "batch_run"])
        old = ("session_progress", "switch_project", "download_assets")
        for a in got:
            self.assertNotIn(a, old, "五动作必须是新增量，不与旧 3 actions 重叠")

    def test_five_node_types_with_script_node(self):
        nodes = lw.run("node_types")["nodes"]
        self.assertEqual([n["key"] for n in nodes],
                         ["text", "image", "video", "audio", "script"])
        script = [n for n in nodes if n["key"] == "script"][0]
        self.assertIn("生产", script["what"])
        self.assertIn("分镜脚本", script["note"])
        self.assertIn("上传", lw.run("node_types")["quick_add"])

    def test_param_contract_two_switches(self):
        p = lw.run("params")
        self.assertEqual(p["generator"]["flag"], "-s")
        self.assertIn("schema", p["generator"]["rule"])
        self.assertEqual(p["node_top_level"]["flag"], "-u")
        self.assertEqual(p["history_defaults"]["model"], "StarVideo 2.0")
        self.assertEqual(p["history_defaults"]["aspect"], "16:9")
        self.assertEqual(len(p["history_defaults"]["resolutions"]), 2)


class PitfallAndRedLineTests(unittest.TestCase):
    def test_two_pitfalls_have_gates(self):
        ks = [x["key"] for x in lw.run("pitfalls")["pitfalls"]]
        self.assertEqual(ks, ["group_bind", "stdout_suppress"])
        self.assertEqual(lw.check_group_bound([])["rule"], "group_not_bound")
        self.assertIn("标准输入", lw.check_group_bound([])["why"])
        self.assertTrue(lw.check_group_bound(["k1", "k2"])["ok"])
        self.assertEqual(
            lw.check_stdout_suppressed(True, False)["rule"],
            "stdout_not_suppressed")
        self.assertTrue(lw.check_stdout_suppressed(True, True)["ok"])
        self.assertTrue(lw.check_stdout_suppressed(False, False)["ok"],
                        "非终点节点不要求抑制")

    def test_schema_gate_rejects_unknown_keys(self):
        out = lw.check_schema_keys(["a", "b"], ["a"])
        self.assertEqual(out["rule"], "schema_key_rejected")
        self.assertEqual(out["bad"], ["b"])
        self.assertEqual(lw.check_schema_keys([], ["a"])["rule"],
                         "no_generator_params")
        self.assertEqual(lw.check_schema_keys(["a"], [])["rule"],
                         "schema_unknown", "拿不到 schema 不许凭记忆写键")
        self.assertTrue(lw.check_schema_keys(["a"], ["a", "b"])["ok"])

    def test_four_redlines_identical_to_existing(self):
        r = lw.run("redlines")
        self.assertEqual(len(r["red_lines"]), 4)
        self.assertIn("DPAPI", r["red_lines"][0])
        self.assertIn("落盘", r["red_lines"][1])
        self.assertIn("libtv", r["red_lines"][2])
        self.assertIn("官方入口", r["red_lines"][3])
        self.assertIn("不重造", r["source"], "本刀只引用已有红线")
        self.assertEqual(lw.check_no_plaintext_key("lt-abcdefghijklmnop1234")["rule"],
                         "plaintext_key")

    def test_howto_has_startup_strategy(self):
        steps = lw.run("howto")["steps"]
        self.assertEqual(len(steps), 4)
        self.assertIn("最小单元", steps[1]["what"])
        self.assertIn("返工", steps[1]["what"])
        self.assertIn("分镜图组", steps[2]["what"])


class SkeletonAndWiringTests(unittest.TestCase):
    def test_source_is_owner_provided_not_verified(self):
        st = lw.run("status")
        self.assertIn("主人提供", st["source"])
        self.assertIn("未独立取证", st["source"])

    def test_module_has_no_write_or_network_paths(self):
        src = Path(lw.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket",
                    "subprocess.run(", ".write_text(", ".write_bytes("):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)

    def test_registered_and_wired(self):
        cap = CR.BENIGN_CAPS.get("libtv_workflow")
        self.assertIsNotNone(cap)
        self.assertEqual(cap["domain"], "video")
        self.assertIn("libtv_workflow", ok._READONLY_MODULES)
        self.assertIs(ok._READONLY_MODULES["libtv_workflow"], lw)


if __name__ == "__main__":
    unittest.main()
