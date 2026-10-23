# -*- coding: utf-8 -*-
"""统一扫描位 判据（scan_cap）。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import scan_cap as SC  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


def _scopes(payload):
    d = policy.evaluate("scan_cap", payload or {})
    return sorted(getattr(d, "scopes", ()) or ())


class ScanContractTest(unittest.TestCase):

    def test_species_list_has_nine_independent_principles(self):
        r = SC.run("species")
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["species"]), 9)
        for sp in r["species"]:
            self.assertTrue(r["principle"][sp], sp)

    def test_unknown_species_fails_closed(self):
        r = SC.run("scan", species="no_such_species")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_species")
        self.assertIn("secrets", r["known"])

    def test_unknown_op_fails_closed(self):
        r = SC.run("nope")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")

    def test_scan_is_machine_readable_with_exit_code(self):
        r = SC.run("scan", species="iac", limit=200)
        self.assertEqual(r["schema"], "gbt-scan/1")
        self.assertIn("exit_code", r)
        self.assertEqual(r["disposition"], "candidate", "铁律：扫描给的是候选，不是判决")
        self.assertIn("not_final", r)
        for f in r["findings"][:5]:
            for k in ("species", "rule", "severity", "path", "line", "evidence"):
                self.assertIn(k, f)

    def test_exit_code_zero_when_no_p0(self):
        r = SC.run("scan", species="inventory", limit=100)
        self.assertEqual(r["counts"]["P0"], 0)
        self.assertEqual(r["exit_code"], 0)

    def test_blindspot_reports_no_sample_red_not_green(self):
        """§45：扫到 0 个文件不能当通过。"""
        d = (ROOT / "no_such_dir_for_scan").exists()
        self.assertFalse(d)
        r = SC.scan_inventory(ROOT / "no_such_dir_for_scan")
        self.assertEqual(r["scanned"], 0)


class RuleDecouplingTest(unittest.TestCase):

    def test_rules_loaded_from_file_when_present(self):
        cfg = SC._load_rules("secrets")
        self.assertEqual(cfg["source"], "file")
        self.assertTrue(cfg["allow"])
        self.assertIsInstance(cfg["age_s"], int, "数据新鲜度必须可读")

    def test_rules_fall_back_to_builtin_when_absent(self):
        cfg = SC._load_rules("no_such_species_rules")
        self.assertEqual(cfg["source"], "builtin")
        self.assertEqual(cfg["rules"], [])

    def test_suppression_requires_a_reason(self):
        """消音必须带理由；无理由的条目不生效（不许静默）。"""
        f = {"rule": "r", "path": "p", "line": 1, "evidence": "x", "fingerprint": "abc"}
        kept, sup = SC._apply_allow([dict(f)], [{"fingerprint": "abc"}])
        self.assertEqual(len(kept), 1, "无 reason 不得消音")
        self.assertEqual(sup, [])
        kept2, sup2 = SC._apply_allow([dict(f)], [{"fingerprint": "abc", "reason": "测试夹具"}])
        self.assertEqual(len(kept2), 0)
        self.assertEqual(len(sup2), 1)
        self.assertEqual(sup2[0]["reason"], "测试夹具")

    def test_placeholder_sequence_detected(self):
        self.assertTrue(SC._seq_like("sk-abcdefghijklmnop"))
        self.assertTrue(SC._seq_like("token=1234567890"))
        self.assertFalse(SC._seq_like("Zx9Qm2Lp7Rt4Wv1Kd"))


class ScanGateTest(unittest.TestCase):

    def test_read_ops_have_no_scopes(self):
        for op in SC.READ_OPS:
            with self.subTest(op=op):
                self.assertEqual(_scopes({"op": op}), [])

    def test_report_needs_filesystem_write(self):
        self.assertEqual(_scopes({"op": "report"}), ["filesystem_write"])

    def test_report_writes_into_store(self):
        """写到隔离 store，且**不许把进程的 store 绑定弄脏**。

        🔴 2026-10-17 修（与 `test_figure_gate` / `test_omarchy_bridge` 同一根因 · 留痕）：
          原实现：`importlib.reload(_paths)` 改绑定；`finally` 里**只有 `old is not None` 才 reload 回来**
          ⇒ `old is None`（runner 没设 env 时）分支下 `_paths` 永久停在临时根，
          之后每次写盘都抛「store 绑定与环境变量不一致」（全量跑里的残余假红）。
          而且 reload 本身会造出 `store._STORE_DIR` 与 `_paths.STORE_DIR` 两个口径
          （`test_ai_audit.py:76-83` 已记过这条血账）。
          现口径：**不 reload**，精确改三个字段 → `finally` 原样还原，env 与绑定始终自洽。
        """
        from gbt_allinone import _paths
        old_env = os.environ.get("GBT_STORE_DIR")
        old_store = _paths.STORE_DIR
        old_bind = _paths.STORE_DIR_ENV_AT_BIND
        tmp = tempfile.mkdtemp(prefix="gbt_scan_")
        os.environ["GBT_STORE_DIR"] = tmp
        _paths.STORE_DIR = Path(tmp).resolve()
        _paths.STORE_DIR_ENV_AT_BIND = tmp
        try:
            r = SC.run("report", species="iac", limit=100)
            self.assertIn("report_path", r)
            self.assertTrue(Path(r["report_path"]).exists())
            self.assertIn("scan_cap", r["report_path"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            _paths.STORE_DIR = old_store
            _paths.STORE_DIR_ENV_AT_BIND = old_bind
            if old_env is None:
                os.environ.pop("GBT_STORE_DIR", None)
            else:
                os.environ["GBT_STORE_DIR"] = old_env


if __name__ == "__main__":
    unittest.main(verbosity=2)
