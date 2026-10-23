# -*- coding: utf-8 -*-
"""人类视角执行律 · 带牙用例（R-H178）。

判据只有一条：**人打开电脑工作时，会卡自己这一步吗？** 不会 ⇒ 降级；会 ⇒ 保留。

本文件同时守两个方向（**缺一不可**）：
  ① 降级生效：可逆动作（browser open/search · notion 只读）在**非主人会话**下不挂作用域；
  ② 口径不回退：不可逆动作（automate / 写盘 / 部署 / 起进程 / 发外部）**照样挂作用域**，
     —— 没有这一半，"降级"就会变成"把门拆了"。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.security import policy  # noqa: E402


def _scopes(kind, payload):
    return set(policy.evaluate(kind, payload).scopes)


class ReversibleActionsAreFree(unittest.TestCase):
    """① 降级生效：人不会卡自己的那些动作。"""

    def test_browser_open_is_free(self):
        self.assertEqual(_scopes("browser", {"op": "open", "url": "https://example.com"}), set(),
                         "打开系统默认浏览器是人的基本可逆动作 ⇒ 免卡")

    def test_browser_search_is_free(self):
        self.assertEqual(_scopes("browser", {"op": "search", "query": "gbt"}), set(),
                         "搜索是人的基本可逆动作 ⇒ 免卡")

    def test_notion_reads_are_free(self):
        for op in ("status", "recent", "search", "page"):
            self.assertEqual(_scopes("notion", {"op": op}), set(),
                             f"notion.{op} 是**查**不是**送** ⇒ 免卡")

    def test_private_url_still_needs_network_private(self):
        """降级**没有**带走内网闸：访问本机/内网仍要 network_private。"""
        got = _scopes("browser", {"op": "open", "url": "http://127.0.0.1:8765/"})
        self.assertEqual(got, {"network_private"}, "内网判定必须保留")

    def test_authorize_does_not_consume_anything_for_reversible_actions(self):
        """非主人会话下 authorize(browser/open) ⇒ 放行，且**不消耗任何授权**。"""
        res = policy.authorize("browser", {"op": "open", "url": "https://example.com"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(res.get("authorizations"), [], "可逆动作不该消耗授权")
        self.assertEqual(list(res.get("scopes") or []), [])


class IrreversibleStaysGated(unittest.TestCase):
    """② 口径不回退：不可逆动作一条都没松。"""

    def test_browser_automate_still_needs_browser_control(self):
        self.assertIn("browser_control", _scopes("browser", {"op": "automate", "url": "https://x.com"}))

    def test_browser_unknown_op_is_fail_closed(self):
        self.assertIn("browser_control", _scopes("browser", {"op": "teleport"}),
                      "未知动作必须 fail-closed（否则降级会变成拆门）")

    def test_notion_unknown_or_write_op_needs_data_export(self):
        self.assertIn("data_export", _scopes("notion", {"op": "create_page"}),
                      "写入/未知动作仍然挂 data_export")

    def test_the_rest_of_the_table_is_untouched(self):
        cases = [
            ("create", {"op": "write"}, "filesystem_write"),
            ("pipeline_submit", {}, "deploy_publish"),
            ("mcp_connect", {}, "process_execute"),
            ("llm_chat", {}, "external_llm"),
            ("audit_query", {}, "audit_read"),          # 归属待主人拍板 ⇒ 本刀不动
            ("voice", {"op": "tts"}, "audio_output"),   # 主人 2026-09-18 拍板显式化 ⇒ 不动
        ]
        for kind, payload, scope in cases:
            self.assertIn(scope, _scopes(kind, payload), f"{kind} 的 {scope} 不该被本刀动到")


if __name__ == "__main__":
    unittest.main()
