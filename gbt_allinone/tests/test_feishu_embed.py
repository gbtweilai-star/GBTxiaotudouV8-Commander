# -*- coding: utf-8 -*-
"""飞书镶嵌窗口 · 带牙用例（R-H239）。

① 形态：**走浏览器触手**（mode=browser_tentacle）· **不需要凭据**；
② 四条红线各有闸：飞书是副本 / 凭据不许明文 / 不绕验证 / 每次操作留痕（source_kind=feishu）；
③ 骨架期 `open()` **如实说 not_implemented**（不许假装打开了）；
④ 三处 host **标「主人提供 · 盘上未见」**（未验证就说未验证）；
⑤ 只读骨架不许有出网/开浏览器/写盘路径；登记在册且**落地即接线**。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import feishu_embed as fe  # noqa: E402
from gbt_allinone.tools import orchestration_kernel as ok  # noqa: E402
from gbt_allinone import caps_registry as CR  # noqa: E402


class ShapeTests(unittest.TestCase):
    def test_mode_is_browser_tentacle_and_no_credential(self):
        st = fe.run("status")
        self.assertEqual(st["mode"], "browser_tentacle", "**走浏览器触手，不走 API**")
        self.assertFalse(st["credential_needed"], "**不需要新凭据**")
        self.assertIn("user_session", st["network_needed"])
        self.assertEqual(st["source_of_truth"], "local", "本地是源，飞书是副本")

    def test_browser_tentacle_entry_is_the_real_one(self):
        t = fe.run("tentacle")
        self.assertEqual(t["entry"], "open_url")
        self.assertIn("native_browser.py", t["native"])

    def test_hosts_are_owner_provided_not_verified(self):
        h = fe.run("hosts")
        self.assertEqual(len(h["hosts"]), 3)
        for x in h["hosts"]:
            self.assertIn("主人提供", x["from"])
        self.assertIn("盘上未见", h["note"], "未验证就说未验证")

    def test_five_actions(self):
        a = fe.run("actions")
        self.assertEqual([x["key"] for x in a["actions"]],
                         ["OPEN_WIKI", "OPEN_DOC", "OPEN_BASE", "SEARCH", "LIST_RECENT"])


class RedLineTests(unittest.TestCase):
    def test_four_redlines(self):
        r = fe.run("redlines")
        self.assertEqual(len(r["red_lines"]), 4)
        for s in ("副本", "凭据", "不绕验证", "trace_store"):
            self.assertTrue(any(s in x for x in r["red_lines"]), "少了：%s" % s)

    def test_feishu_is_copy_not_source(self):
        bad = fe.check_copy_not_source({"text": "以飞书为源，覆盖本地记录"})
        self.assertEqual(bad["rule"], "feishu_as_source")
        self.assertIn("三处未收口", bad["why"])
        self.assertTrue(fe.check_copy_not_source({"text": "打开飞书知识库"})["ok"])

    def test_no_bypass_login(self):
        for t in ("模拟登录飞书", "抓 cookie 复用", "用账号密码登录"):
            self.assertEqual(fe.check_no_bypass({"text": t})["rule"],
                             "bypass_login", "不许绕验证：%s" % t)
        self.assertTrue(fe.check_no_bypass({"text": "打开文档"})["ok"])

    def test_no_plaintext_credential(self):
        self.assertEqual(fe.check_no_plaintext_key("cli_abcdefghijklmn")["rule"],
                         "plaintext_key")
        okc = fe.check_no_plaintext_key("")
        self.assertTrue(okc["ok"])
        self.assertFalse(okc["credential_needed"])

    def test_every_action_must_trace(self):
        self.assertEqual(fe.must_trace("")["rule"], "call_not_traced")
        self.assertEqual(fe.must_trace("t-1", "libtv")["rule"], "bad_source_kind")
        self.assertEqual(fe.must_trace("t-1", "libtv")["expected"], "feishu")
        self.assertTrue(fe.must_trace("t-1", "feishu")["ok"])


class SkeletonAndWiringTests(unittest.TestCase):
    def test_open_is_honest_not_fake(self):
        r = fe.run("open", action="OPEN_WIKI", target="知识库")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "not_implemented")
        self.assertIn("open_url", r["next"], "要指向浏览器触手的真入口")
        self.assertEqual(fe.run("open", action="OPEN_WIKI")["rule"],
                         "missing_target")
        self.assertEqual(fe.run("open", action="飞来飞去")["rule"],
                         "unknown_action")

    def test_module_has_no_open_or_network_paths(self):
        src = Path(fe.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket",
                    "webbrowser", "subprocess.run(", ".write_text("):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)

    def test_registered_and_wired(self):
        cap = CR.BENIGN_CAPS.get("feishu_embed")
        self.assertIsNotNone(cap)
        self.assertEqual(cap["domain"], "integration")
        self.assertIn("feishu_embed", ok._READONLY_MODULES)
        self.assertIs(ok._READONLY_MODULES["feishu_embed"], fe)


if __name__ == "__main__":
    unittest.main()
