# -*- coding: utf-8 -*-
"""Stigmergy（协作层·间接通道）带牙用例。

牙在哪（每条都断言 **denied 的 rule 名**，不只看 ok）：
  ① 无源不许留 ② 种类白名单 ③ 强度范围 ④ 不留明文密钥（且**不写盘**）
  ⑤ 只追加（静态核 + 行为核：挥发**不删行**）⑥ 空场不许编方向
"""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone.tools import stigmergy as s  # noqa: E402


class StigmergyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gbt_stig_")

    def _rows(self):
        p = Path(self.tmp) / "pheromones.jsonl"
        if not p.exists():
            return 0
        return len([x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()])

    def test_status_shape_and_primitives(self):
        st = s.run("status")
        self.assertTrue(st["ok"])
        self.assertTrue(st["readonly"])
        self.assertEqual([p["name"] for p in st["primitives"]],
                         ["DEPOSIT", "READ", "DECAY", "FORAGE"])
        self.assertEqual(len(st["red_lines"]), 5)
        self.assertEqual(sorted(st["kinds"]), ["danger", "path", "resource", "task"])

    def test_teeth_1_no_source_denied(self):
        r = s.run("deposit", kind="task", subject="a", source="", root=self.tmp)
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "deposit_without_source")
        self.assertEqual(self._rows(), 0, "被拒的留痕**不许写盘**")

    def test_teeth_2_kind_whitelist(self):
        r = s.run("deposit", kind="nope", subject="a", source="t", root=self.tmp)
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "deposit_kind_not_allowed")
        self.assertEqual(self._rows(), 0)

    def test_teeth_3_strength_range(self):
        for bad in (0, 1.5, -0.2):
            r = s.run("deposit", kind="task", subject="a", strength=bad,
                      source="t", root=self.tmp)
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["rule"], "deposit_strength_out_of_range")
        self.assertEqual(self._rows(), 0)

    def test_teeth_4_no_plaintext_key_and_not_written(self):
        r = s.run("deposit", kind="task", subject="a", source="t",
                  note="token sk-abcdef123456", root=self.tmp)
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "plaintext_key_in_pheromone")
        self.assertIn("****", r["masked"])
        self.assertNotIn("abcdef123456", str(r), "掩码后不许回显全文")
        self.assertEqual(self._rows(), 0, "命中即拒 ⇒ **不写盘**")

    def test_append_only_static_gate(self):
        g = s.run("gate_append_only")
        self.assertTrue(g["ok"], g)
        self.assertTrue(g["append_only"])
        self.assertEqual(g["writer"], "locked_append_text")

    def test_append_only_behavior_decay_does_not_delete(self):
        s.run("deposit", kind="task", subject="a", strength=1.0, source="t",
              now=time.time() - 100 * 3600, root=self.tmp)
        s.run("deposit", kind="task", subject="b", strength=1.0, source="t",
              root=self.tmp)
        before = self._rows()
        d = s.run("decay", root=self.tmp)
        after = self._rows()
        self.assertEqual(before, after, "**挥发是读数，不是删除**")
        self.assertEqual(d["deleted"], 0)
        self.assertGreaterEqual(d["faded"], 1, "老痕应已淡出")
        self.assertEqual(after, 2, "两行都在（可回放）")

    def test_read_effective_strength_decays(self):
        now = time.time()
        s.run("deposit", kind="path", subject="same", strength=1.0,
              source="t", now=now - 2 * 3600, root=self.tmp)
        got = s.run("read", root=self.tmp)
        self.assertTrue(got["ok"])
        one = got["subjects"][0]
        self.assertEqual(one["subject"], "same")
        self.assertAlmostEqual(one["effective"], 0.5, places=2)

    def test_forage_empty_does_not_invent(self):
        f = s.run("forage", root=self.tmp)
        self.assertTrue(f["ok"])
        self.assertEqual(f["suggestions"], [])
        self.assertIn("场地是空的", f["reason"])
        self.assertIn("不编", f["reason"])

    def test_forage_orders_by_effective(self):
        s.run("deposit", kind="task", subject="weak", strength=0.3, source="t", root=self.tmp)
        s.run("deposit", kind="task", subject="strong", strength=0.9, source="t", root=self.tmp)
        f = s.run("forage", root=self.tmp)
        self.assertEqual(f["suggestions"][0]["subject"], "strong")
        self.assertIn("只排序", f["note_zh"])

    def test_collab_bridge_is_side_by_side_readonly(self):
        b = s.run("collab_bridge")
        self.assertTrue(b["ok"])
        self.assertTrue(b["readonly"])
        self.assertIn("collab_gateway", b["direct_channel"])
        self.assertIn("并排", b["relationship"])
        self.assertIn("不替代", b["relationship"])
        self.assertIn("不读写", b["no_side_effect"])

    def test_kinds_gate_half_life(self):
        g = s.run("gate_kinds")
        self.assertTrue(g["ok"], g)
        self.assertTrue(all(v > 0 for v in g["half_life_hours"].values()))


if __name__ == "__main__":
    unittest.main()
