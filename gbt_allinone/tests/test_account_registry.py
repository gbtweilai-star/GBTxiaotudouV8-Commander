# -*- coding: utf-8 -*-
"""AI 账号登记表 · 带牙用例（R-H179）。

① 空表合法（骨架期 0 账号，不许假装有人）；
② 一人一号：同平台同账号挂两个 AI ⇒ 违规；
③ 各 AI 各自持有：共用一个凭证容器 ⇒ 违规；
④ 只记路径：明文密钥 / 非 DPAPI 凭证 ⇒ 违规；
⑤ 无主账号（缺 platform 或 account）⇒ 违规；
⑥ 只读：源码里不许有联网 / 写盘路径。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import account_registry as ar  # noqa: E402


def _reg(*rows):
    return {"ok": True, "source": "test", "accounts": list(rows)}


class RegistryTests(unittest.TestCase):
    def test_skeleton_is_empty_and_legal(self):
        rep = ar.validate(ar.load())
        self.assertEqual(rep["count"], 0, "骨架期不许有账号")
        self.assertTrue(rep["ok"], "空表必须合法（否则骨架阶段就红）")
        self.assertEqual(rep["violations"], [])

    def test_same_account_on_two_ais_is_a_violation(self):
        rep = ar.validate(_reg(
            {"ai_id": "music-01", "platform": "spotify", "account": "acct-1",
             "credential_ref": "store/secrets/m1.dpapi"},
            {"ai_id": "music-02", "platform": "spotify", "account": "acct-1",
             "credential_ref": "store/secrets/m2.dpapi"},
        ))
        self.assertFalse(rep["ok"])
        self.assertIn("shared_account", [v["rule"] for v in rep["violations"]])

    def test_shared_credential_container_is_a_violation(self):
        rep = ar.validate(_reg(
            {"ai_id": "video-01", "platform": "douyin", "account": "a",
             "credential_ref": "store/secrets/shared.dpapi"},
            {"ai_id": "video-02", "platform": "douyin", "account": "b",
             "credential_ref": "store/secrets/shared.dpapi"},
        ))
        self.assertIn("shared_credential", [v["rule"] for v in rep["violations"]])

    def test_plaintext_secret_and_non_dpapi_credential_are_violations(self):
        rep = ar.validate(_reg(
            {"ai_id": "film-01", "platform": "bilibili", "account": "c",
             "credential_ref": "store/secrets/f1.dpapi",
             "note": "app_secret=abcdef123456"},
        ))
        self.assertIn("plaintext_secret", [v["rule"] for v in rep["violations"]])
        rep2 = ar.validate(_reg(
            {"ai_id": "film-02", "platform": "bilibili", "account": "d",
             "credential_ref": "notes/creds.txt"},
        ))
        self.assertIn("credential_not_dpapi", [v["rule"] for v in rep2["violations"]])

    def test_unowned_account_is_a_violation(self):
        rep = ar.validate(_reg({"ai_id": "x-01", "platform": "", "account": ""}))
        self.assertIn("unowned_account", [v["rule"] for v in rep["violations"]])

    def test_status_is_readonly_and_reports_source(self):
        st = ar.status()
        self.assertTrue(st["readonly"])
        self.assertTrue(st["source"], "必须如实报登记表来源")
        self.assertIn("accounts", st)

    def test_module_has_no_network_or_write_paths(self):
        src = Path(ar.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读模块里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
