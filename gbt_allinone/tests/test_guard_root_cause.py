# -*- coding: utf-8 -*-
"""红黄警报的根因判据（2026-11-07）。

锁四件事（都是这次真踩过的）：
  ① legacy_guard：备份区内的 .bak 不算红；文档编号撞车不进 verdict；
  ② inventory：git 已忽略的运行时/空目录归 runtime，不算异物；
  ③ preflight：signature restore 的探针口径必须跟随调用方的 scope；
  ④ page_scan：单个能力位阻塞时按 yellow 超时放行，不拖死整批。
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class TestLegacyGuard(unittest.TestCase):
    def test_backup_zone_excluded_and_doc_collision_not_red(self):
        from gbt_allinone.tentacle import legacy_guard as LG
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "state" / "backup").mkdir(parents=True)
            (root / "state" / "backup" / "a.bak").write_text("x", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "1-a.md").write_text("x", encoding="utf-8")
            (root / "docs" / "1-b.md").write_text("y", encoding="utf-8")
            old = LG.ROOT
            LG.ROOT = root
            try:
                s = LG.scan()
            finally:
                LG.ROOT = old

            self.assertEqual(s["categories"]["backup-files"]["files"], 0)
            self.assertEqual(s["categories"]["backup-files"]["inside_backup_zones"], 1)
            self.assertEqual(s["categories"]["dup-doc-numbers"]["groups"], 1)
            # 只有「编号撞车」，没有真旧物 ⇒ clean；撞车单独进 notes
            self.assertEqual(s["verdict"], "clean")
            self.assertEqual(
                s["notes"]["doc-number-collisions"]["groups"], 1)

            # 散落在项目里的 .bak 才是真旧物，必须仍然判红
            (root / "docs" / "a.md.bak").write_text("x", encoding="utf-8")
            LG.ROOT = root
            try:
                s2 = LG.scan()
            finally:
                LG.ROOT = old
            self.assertEqual(s2["verdict"], "legacy_found")
            self.assertEqual(s2["categories"]["backup-files"]["files"], 1)


class TestInventoryRuntime(unittest.TestCase):
    def test_git_ignored_and_empty_dir_are_runtime(self):
        from gbt_allinone import inventory as I
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "pyproject.toml").write_text("", encoding="utf-8")
            (home / "gbt_allinone").mkdir()
            (home / "pyembed").mkdir()
            (home / "pyembed" / "python.exe").write_text("x", encoding="utf-8")
            (home / "render").mkdir()                      # 空目录：产物占位
            (home / "notes.bak").write_text("x", encoding="utf-8")
            (home / "loose.bin").write_text("x", encoding="utf-8")

            old = (I._HOME, I._CHECKOUT, I._GIT_TOPS, I._REPO_TOP)
            I._HOME = home
            I._CHECKOUT = True
            I._GIT_TOPS = (set(), {"pyembed"})
            I._REPO_TOP = {"pyproject.toml", "gbt_allinone"}
            try:
                r = I.scan()
            finally:
                (I._HOME, I._CHECKOUT, I._GIT_TOPS, I._REPO_TOP) = old

            self.assertIn("pyembed", r["items"]["runtime"])
            self.assertIn("render", r["items"]["runtime"])
            self.assertIn("notes.bak", r["items"]["runtime"])
            self.assertEqual(r["items"]["foreign"], ["loose.bin"])
            self.assertEqual(r["verdict"], "foreign_found")


class TestPreflightSignatureScope(unittest.TestCase):
    def test_probe_carries_callers_scope(self):
        from gbt_allinone import preflight as P
        seen = {}

        def fake_audit(restore=False, scope="framework"):
            seen["restore"] = restore
            seen["scope"] = scope
            return {"verdict": "missing", "missing": ["docs/x.md"]}

        with mock.patch("gbt_allinone.signature.audit", side_effect=fake_audit):
            out = P._observe_signature_restore({"restore": True, "scope": "all"})

        self.assertEqual(seen, {"restore": False, "scope": "all"})
        self.assertFalse(out["matched"])
        self.assertEqual(out["reason"], "signature_missing")


class TestPageScanTimeout(unittest.TestCase):
    def test_blocked_cap_is_yellow_not_hang(self):
        from gbt_allinone.tools import page_scan as PS
        old = os.environ.get("GBT_PAGE_SCAN_TIMEOUT")
        os.environ["GBT_PAGE_SCAN_TIMEOUT"] = "0.2"
        try:
            with mock.patch("gbt_allinone.api.run_task",
                            side_effect=lambda *a, **k: time.sleep(5)):
                t0 = time.time()
                r = PS._classify("blocked_cap")
                elapsed = time.time() - t0
        finally:
            if old is None:
                os.environ.pop("GBT_PAGE_SCAN_TIMEOUT", None)
            else:
                os.environ["GBT_PAGE_SCAN_TIMEOUT"] = old

        self.assertEqual(r["color"], "yellow", r)
        self.assertTrue(r.get("timeout"), r)
        self.assertLess(elapsed, 3.0, "超时没生效，整批会被拖住")


if __name__ == "__main__":
    unittest.main()
