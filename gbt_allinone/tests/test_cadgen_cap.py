# -*- coding: utf-8 -*-
"""cadgen（本机 CAD 链的口）· 判据件。

跑法（🔴 `GBT_STORE_DIR` 必须**起 Python 之前**设 —— 仓里 `tests/__init__.py` 有哨兵）：

    $env:GBT_STORE_DIR="$env:TEMP\\gbt_test_store"; py -3.14 -m unittest gbt_allinone.tests.test_cadgen_cap -v

## 测什么 / 不测什么

- **测（真跑真件）**：① `version` 原生 rc=0 且 stdout 里有 `cadgen`；② `doctor` rc=0；
  ③ `help` 现读真参数（给的子命令不在册 ⇒ fail-closed）；④ **`snapshot` 真渲一张**（真 GLB → PNG，
  rc=0 **且产物在盘且非空**）；⑤ 未知 op / 缺 target / target 不在盘 三条 fail-closed；
  ⑥ `status` 是**纯探**（二进制/技能件/FreeCAD 三态如实现报告）。
- **不测**：`mcp`（长驻服务，本位**不接**）。
- **隔离**：snapshot 的产物写进临时目录，不往仓里丢东西。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import cadgen_cap as CG   # noqa: E402

_TMP = tempfile.TemporaryDirectory(prefix="gbt-cadgen-test-")
_MODEL = _REPO / "assets" / "treasure-chest.glb"      # 仓里真件（不是合成的）


def _binary() -> bool:
    return bool(CG._binary())


class TestCadgenContract(unittest.TestCase):
    """契约面（不起进程）。"""

    def test_status_is_pure_and_reports_three_facts(self):
        st = CG.run("status")
        self.assertTrue(st["ok"], st)
        for k in ("binary_present", "skill_present", "freecad_present"):
            self.assertIn(k, st, "status 必须如实报这三态：%s" % st)
        self.assertIn("not_wired", st["mcp"], "mcp 是长驻服务 ⇒ 必须如实标不接：%s" % st)

    def test_where_lists_ops_and_rules(self):
        wh = CG.run("where")
        self.assertTrue(wh["ok"])
        for op in ("status", "where", "version", "doctor", "help", "snapshot"):
            self.assertIn(op, wh["ops"])

    def test_unknown_op_fail_closed(self):
        r = CG.run("并没有这个 op")
        self.assertFalse(r["ok"], "未知 op 必须 fail-closed")
        self.assertTrue(r["fail_closed"])

    def test_snapshot_needs_target_and_reports_missing(self):
        a = CG.run("snapshot")
        self.assertFalse(a["ok"])
        self.assertEqual(a["status"], "needs_params")
        b = CG.run("snapshot", target=str(_TMP.name) + "/没有这个文件.stl")
        self.assertFalse(b["ok"])
        self.assertEqual(b["status"], "not_found")

    def test_help_rejects_unknown_sub(self):
        r = CG.run("help", sub="并没有这个子命令")
        self.assertFalse(r["ok"])
        self.assertTrue(r["fail_closed"])


class TestCadgenRealRuns(unittest.TestCase):
    """真跑真件（只认原生 rc）。"""

    @unittest.skipUnless(_binary(), "本机没有 cadgen 真件 ⇒ 跳过（不假装跑过）")
    def test_version_rc_zero(self):
        r = CG.run("version")
        self.assertEqual(r["rc"], 0, r)
        self.assertIn("cadgen", r["stdout"], r)

    @unittest.skipUnless(_binary(), "本机没有 cadgen 真件 ⇒ 跳过（不假装跑过）")
    def test_doctor_rc_zero(self):
        r = CG.run("doctor")
        self.assertEqual(r["rc"], 0, r)
        self.assertIn("kernel", r["stdout"].lower(), r)

    @unittest.skipUnless(_binary() and _MODEL.is_file(), "真件或靶子不在 ⇒ 跳过（不假装跑过）")
    def test_snapshot_really_renders_a_png(self):
        out = Path(_TMP.name) / "snap.png"
        r = CG.run("snapshot", target=str(_MODEL), out=str(out))
        self.assertEqual(r["rc"], 0, r)
        self.assertTrue(r["out_exists"], "rc=0 但产物不在盘 ⇒ 不算渲出来：%s" % r)
        self.assertGreater(r["out_bytes"], 1000, r)
        self.assertEqual(out.stat().st_size, r["out_bytes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
