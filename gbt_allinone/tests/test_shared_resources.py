# -*- coding: utf-8 -*-
"""共享资源池 · 带牙用例（R-H181）。

① 骨架期池子为空（空就是空），借号 ⇒ pool_empty；
② 每次调用留痕：缺 purpose 或 leased_to ⇒ 拒绝；
③ 恶意用途（批量注册/刷号）⇒ 拒绝；
④ 不绕验证（绕过类字眼）⇒ 拒绝；
⑤ 借出的资源不许同时租给第二个 AI；归还后**租约记录保留**（留痕不删）；
⑥ 资源值一律掩码（不许明文外露）；只读：无联网/写盘路径。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import shared_resources as sr  # noqa: E402


class SharedResourceTests(unittest.TestCase):
    def setUp(self):
        sr.POOL["phone"].clear()
        sr.POOL["email"].clear()
        sr.LEASES.clear()
        sr._SEQ["n"] = 0

    def test_skeleton_pool_is_empty(self):
        st = sr.status()
        self.assertEqual(st["pools"]["phone"]["total"], 0)
        self.assertEqual(st["pools"]["email"]["total"], 0)
        self.assertEqual(st["leases_total"], 0)
        got = sr.lease("phone", "注册 Spotify 开发者账号", leased_to="music-01")
        self.assertFalse(got["ok"])
        self.assertEqual(got["reason"], "pool_empty")

    def test_lease_requires_purpose_and_owner(self):
        sr.add_resource("phone", "13800000000")
        r1 = sr.lease("phone", "", leased_to="music-01")
        self.assertFalse(r1["ok"])
        self.assertIn("purpose_required", [p["rule"] for p in r1["problems"]])
        r2 = sr.lease("phone", "注册账号", leased_to="")
        self.assertIn("leased_to_required", [p["rule"] for p in r2["problems"]])

    def test_abuse_and_bypass_purposes_are_refused(self):
        sr.add_resource("email", "a@example.com")
        bad1 = sr.lease("email", "批量注册一百个号", leased_to="music-01")
        self.assertIn("abuse_forbidden", [p["rule"] for p in bad1["problems"]])
        bad2 = sr.lease("email", "想办法绕过验证", leased_to="music-01")
        self.assertIn("bypass_forbidden", [p["rule"] for p in bad2["problems"]])

    def test_lease_is_exclusive_and_trail_is_kept_after_release(self):
        sr.add_resource("phone", "13900000000")
        first = sr.lease("phone", "注册一个平台账号", leased_to="music-01", now=1000.0)
        self.assertTrue(first["ok"])
        second = sr.lease("phone", "同一时刻再借", leased_to="video-01", now=1001.0)
        self.assertFalse(second["ok"], "同一个资源不许同时租给两个 AI")
        done = sr.release(first["lease_id"], now=2000.0)
        self.assertTrue(done["ok"])
        self.assertTrue(done["trail_kept"], "归还后租约记录必须保留")
        self.assertEqual(len(sr.LEASES), 1)
        self.assertEqual(sr.LEASES[0]["leased_to"], "music-01")
        self.assertEqual(sr.LEASES[0]["purpose"], "注册一个平台账号")
        again = sr.lease("phone", "归还后再借", leased_to="video-01", now=2001.0)
        self.assertTrue(again["ok"], "归还后资源应回到池里可再借")

    def test_values_are_masked(self):
        got = sr.add_resource("phone", "13812345678")
        self.assertNotIn("13812345678", got["value"])
        self.assertTrue(got["value"].startswith("138"))

    def test_status_lists_who_holds_what(self):
        sr.add_resource("phone", "13700000000")
        sr.lease("phone", "注册账号", leased_to="film-01")
        st = sr.status()
        self.assertEqual(st["leases_active"], 1)
        self.assertEqual(st["active_leases"][0]["leased_to"], "film-01")
        self.assertEqual(st["pools"]["phone"]["leased"], 1)

    def test_module_has_no_network_or_write_paths(self):
        src = Path(sr.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读模块里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
