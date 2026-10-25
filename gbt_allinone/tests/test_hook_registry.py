# -*- coding: utf-8 -*-
"""钩子矩阵 · 带牙用例（R-H184）。

① 50 条、编号连续、名字唯一、命名空间不许同名混用、六类齐、三层齐；
② 红线 ①：**L3 审计钩子不许挂在触手内部**（触手自称 L3 ⇒ 注册被拒）；
③ 红线 ②：**失败隔离** —— 链里某个钩子抛异常，后面的照跑，错误进 `errors`；
④ 红线 ③：**链可中断** —— 超 deadline ⇒ `timed_out` 且立即停止；
⑤ 状态诚实：existing 4 · candidate 1 · todo 45；
⑥ 只读：源码不许有联网/写盘路径。
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import hook_registry as hr  # noqa: E402


class RegistryShapeTests(unittest.TestCase):
    def test_fifty_hooks_numbered_and_unique(self):
        rep = hr.verify_registry()
        self.assertTrue(rep["ok"], rep["problems"])
        self.assertEqual(rep["count"], 50)
        self.assertEqual([h[0] for h in hr.HOOKS], list(range(1, 51)))
        self.assertEqual(len({h[1] for h in hr.HOOKS}), 50, "钩子名不许重")

    def test_six_categories_and_three_layers(self):
        cat = hr.catalogue()
        self.assertEqual({h["category"] for h in cat["hooks"]}, set(hr.CATEGORIES))
        self.assertEqual({h["layer"] for h in cat["hooks"]}, set(hr.LAYERS))

    def test_status_counts_are_honest(self):
        rep = hr.verify_registry()
        self.assertEqual(rep["counts"]["existing"], 4, "已有实现只有 4 条（带证据那 4 条）")
        self.assertEqual(rep["counts"]["candidate"], 1, "候选待核 1 条（不许当已有）")
        self.assertEqual(rep["counts"]["todo"], 45)

    def test_namespace_rules_per_layer(self):
        cat = hr.catalogue(layer="L3")
        for h in cat["hooks"]:
            self.assertTrue(h["namespace"].startswith("hook.audit."))
        self.assertEqual(hr.NAMESPACE["L1"], "hook.general.")
        self.assertEqual(hr.NAMESPACE["L2"], "hook.business.")


class RedLineTests(unittest.TestCase):
    def test_publish_hook_must_anchor_a_scene(self):
        """贯通④：发布钩子必须锚场景 —— 判据引用场景锚定那一份。"""
        bad = hr.publish_hook_ok("这首歌太伤感了")
        self.assertFalse(bad["ok"])
        self.assertIn(bad["rule"], ("hook_anchors_emotion", "hook_has_no_scene"))
        self.assertEqual(bad["from"], "tools.scene_anchor")
        good = hr.publish_hook_ok("分手后半夜翻到旧照片的人，别听这首歌")
        self.assertTrue(good["ok"])
        self.assertIn("before_publish", good["publish_hooks"])

    def test_l3_audit_hook_cannot_live_inside_a_tentacle(self):
        bad = hr.can_register("pre_audit_log", "L3", owner="tentacle:browser")
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "l3_must_be_external")
        good = hr.can_register("pre_audit_log", "L3", owner="framework")
        self.assertTrue(good["ok"])
        self.assertTrue(good["namespace"].startswith("hook.audit."))

    def test_failure_is_isolated(self):
        def boom():
            raise RuntimeError("钩子炸了")
        out = hr.dispatch([("good1", lambda: None), ("bad", boom), ("good2", lambda: None)])
        self.assertEqual(out["ran"], ["good1", "good2"], "坏钩子不许拖垮主流程")
        self.assertEqual(len(out["errors"]), 1)
        self.assertEqual(out["errors"][0]["hook"], "bad")
        self.assertTrue(out["chain_completed"])

    def test_chain_can_be_interrupted_by_timeout(self):
        def slow():
            time.sleep(0.05)
        out = hr.dispatch([("first", slow), ("second", slow)], deadline_s=0.01)
        self.assertIsNotNone(out["timed_out"], "超时必须有中断记录")
        self.assertFalse(out["chain_completed"])
        self.assertLessEqual(len(out["ran"]), 1, "超时后不许继续往下跑")

    def test_module_has_no_network_or_write_paths(self):
        src = Path(hr.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读模块里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
