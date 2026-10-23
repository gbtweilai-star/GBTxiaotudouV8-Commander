# -*- coding: utf-8 -*-
"""出图交付门 判据（figure_gate）—— 蒸馏两份开源 Skill 的铁律。"""
import os
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import figure_gate as FG  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


def _scopes(payload):
    d = policy.evaluate("figure_gate", payload or {})
    return sorted(getattr(d, "scopes", ()) or ())


class FigureGateIsolation(unittest.TestCase):
    """每组用隔离 store —— **精确改绑定 + 精确还原**（不 reload）。

    🔴 2026-10-17 修（**全量污染 153 条的源头** · 留痕）：
      原实现：`setUp` 里 `importlib.reload(_paths)` 把绑定改到本组临时根，
      `tearDown` 却**只还原 env、不还原绑定** ⇒ 进程内 `_paths.STORE_DIR_ENV_AT_BIND`
      永久停在 `gbt_fg_*`，而 env 已回到 runner 的 store ⇒ `verify_store_binding()`
      对之后**每一次写入**都抛「store 绑定与环境变量不一致」⇒ 全量跑里
      `test_file_operation`(20) / `test_framework`(106) 等共 **153** 条红（单跑却全绿）。
      现口径：**不 reload**（reload 会造出两个 store 口径 —— `test_ai_audit.py:76-83`
      已记过这条血账），改为「备份三个字段 → 精确改 → tearDown 原样还原」，
      env 与绑定在每一步都自洽。
    """

    def setUp(self):
        from gbt_allinone import _paths
        self._old_env = os.environ.get("GBT_STORE_DIR")
        self._old_store = _paths.STORE_DIR
        self._old_bind = _paths.STORE_DIR_ENV_AT_BIND
        self._tmp = tempfile.mkdtemp(prefix="gbt_fg_")
        os.environ["GBT_STORE_DIR"] = self._tmp
        _paths.STORE_DIR = Path(self._tmp).resolve()
        _paths.STORE_DIR_ENV_AT_BIND = self._tmp

    def tearDown(self):
        import shutil
        from gbt_allinone import _paths
        shutil.rmtree(self._tmp, ignore_errors=True)
        _paths.STORE_DIR = self._old_store
        _paths.STORE_DIR_ENV_AT_BIND = self._old_bind
        if self._old_env is None:
            os.environ.pop("GBT_STORE_DIR", None)
        else:
            os.environ["GBT_STORE_DIR"] = self._old_env


class ChecklistTest(FigureGateIsolation):

    def test_checklist_grades_each_item(self):
        r = FG.run("checklist")
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["items"]), 6)
        for it in r["items"]:
            self.assertIn(it["grade"], ("M", "A", "H"))
            self.assertTrue(it["why"])
        self.assertEqual(r["machine_checkable"] + r["needs_artifact"] + r["human_only"], 6)

    def test_typed_numbers_is_graded_machine_checkable(self):
        ids = {i["id"]: i for i in FG.run("checklist")["items"]}
        self.assertEqual(ids["typed_numbers"]["grade"], "M")
        self.assertEqual(ids["ugly_first_frame"]["grade"], "H")


class VerdictTest(FigureGateIsolation):

    def test_fresh_state_is_not_deliverable(self):
        v = FG.run("verdict")
        self.assertFalse(v["deliverable"])
        self.assertTrue(any("numbers_not_declared" in x for x in v["reasons"]))
        self.assertTrue(any("rounds_insufficient" in x for x in v["reasons"]))

    def test_declaring_numbers_requires_a_source(self):
        r = FG.run("declare_numbers", source="")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "needs_source")
        self.assertTrue(FG.run("declare_numbers", source="gbt_allinone/x.py")["ok"])

    def test_record_round_requires_what_was_viewed(self):
        r = FG.run("record_round", viewed=[], issues=[])
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "needs_viewed")

    def test_four_rounds_with_empty_issue_list_is_deliverable(self):
        FG.run("declare_numbers", source="gbt_allinone/model.py")
        for i in range(4):
            r = FG.run("record_round", viewed=["whole", "cut", "explode", "joint"], issues=[])
            self.assertTrue(r["ok"])
        v = FG.run("verdict")
        self.assertTrue(v["deliverable"], v["reasons"])
        self.assertEqual(v["rounds"], 4)
        self.assertIn("ugly_first_frame", v["human_still_required"])

    def test_open_issue_in_last_round_blocks_delivery(self):
        FG.run("declare_numbers", source="m.py")
        for _ in range(4):
            FG.run("record_round", viewed=["whole"], issues=[])
        FG.run("record_round", viewed=["whole"], issues=["接缝在泵体上清晰可见"])
        v = FG.run("verdict")
        self.assertFalse(v["deliverable"])
        self.assertTrue(any("open_issues" in x for x in v["reasons"]))
        self.assertEqual(len(v["open_issues"]), 1)

    def test_rounds_are_append_only_and_numbered(self):
        FG.run("record_round", viewed=["a"])
        FG.run("record_round", viewed=["b"])
        r = FG.run("rounds")
        self.assertEqual(r["count"], 2)
        self.assertEqual([x["n"] for x in r["items"]], [1, 2])

    def test_unknown_op_fails_closed(self):
        r = FG.run("nope")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")


class EvidenceTest(FigureGateIsolation):

    def test_default_requires_no_evidence(self):
        e = FG.run("evidence")
        self.assertTrue(e["ok"])
        self.assertEqual(e["required"], [])

    def test_unknown_kind_is_rejected(self):
        self.assertFalse(FG.run("record_evidence", kind="nope", passed=True)["ok"])
        self.assertFalse(FG.run("require_evidence", kinds=["nope"])["ok"])

    def test_required_but_missing_blocks_delivery(self):
        FG.run("declare_numbers", source="m.py")
        for _ in range(4):
            FG.run("record_round", viewed=["whole"], issues=[])
        self.assertTrue(FG.run("require_evidence", kinds=["audit", "lines"])["ok"])
        v = FG.run("verdict")
        self.assertFalse(v["deliverable"])
        self.assertTrue(any("evidence_missing" in x for x in v["reasons"]), v["reasons"])

    def test_failed_evidence_blocks_delivery_even_when_others_pass(self):
        FG.run("declare_numbers", source="m.py")
        for _ in range(4):
            FG.run("record_round", viewed=["whole"], issues=[])
        FG.run("require_evidence", kinds=["lines"])
        FG.run("record_evidence", kind="lines", passed=False, detail="line ends: 2")
        v = FG.run("verdict")
        self.assertFalse(v["deliverable"])
        self.assertTrue(any("evidence_failed" in x for x in v["reasons"]))

    def test_all_required_green_makes_it_deliverable(self):
        FG.run("declare_numbers", source="m.py")
        for _ in range(4):
            FG.run("record_round", viewed=["whole", "cut"], issues=[])
        FG.run("require_evidence", kinds=["audit", "lines"])
        FG.run("record_evidence", kind="audit", passed=True, command="build.mjs --audit")
        FG.run("record_evidence", kind="lines", passed=True, command="lines.mjs")
        v = FG.run("verdict")
        self.assertTrue(v["deliverable"], v["reasons"])

    def test_evidence_ops_need_filesystem_write(self):
        for op in ("record_evidence", "require_evidence"):
            with self.subTest(op=op):
                self.assertEqual(_scopes({"op": op}), ["filesystem_write"])
        self.assertEqual(_scopes({"op": "evidence"}), [])


class GateTest(unittest.TestCase):

    def test_read_ops_have_no_scopes(self):
        for op in FG.READ_OPS:
            with self.subTest(op=op):
                self.assertEqual(_scopes({"op": op}), [])

    def test_write_ops_need_filesystem_write(self):
        for op in FG.WRITE_OPS:
            with self.subTest(op=op):
                self.assertEqual(_scopes({"op": op}), ["filesystem_write"])

    def test_unknown_op_is_not_gated(self):
        self.assertEqual(_scopes({"op": "nope"}), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
