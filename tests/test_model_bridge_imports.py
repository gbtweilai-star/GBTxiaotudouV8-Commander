# -*- coding: utf-8 -*-
"""model-bridge 的本地依赖必须能解析 · 防「import 一个不存在的模块」。

**来历（2026-11-05）**：`tools/model-bridge/server.py:49` 硬 `import lane_guard as LG`，
而全仓（含所有备份/归档）**一个 lane_guard* 都没有** —— 那是 2026-10-29 抽出来解决
「回环代理 502 误判」的独立模块，文件丢了。后果不是报错一行那么简单：
`启动-GBT.cmd` 第一步就是 8791 bridge，缺它**整条启动链断在第一环**，
而 `py_compile` 查不出来（语法没错，是运行期 ImportError）。

所以判据不能只写「lane_guard 在不在」（下次换个模块丢，一样红不了），
要写成**通用规则**：server.py 依赖的每个非标准库模块，都必须能解析到。
"""
from __future__ import annotations

import ast
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MB = os.path.join(ROOT, "tools", "model-bridge")
SERVER = os.path.join(MB, "server.py")


def _top_imports(path: str):
    """分成「必需」与「可选」两组。

    **`try:` 块里的 import 是可选**（例如 `_budget()` 里 `try: import psutil`，
    没装 psutil 就退化成不报内存预算 —— 服务照跑）。只拿所有 import 去要求文件存在
    会把这类判成缺失，导致测试自己变成误报源。
    """
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    required, optional = set(), set()

    def rec(node, in_try):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, ast.Try):
                rec(ch, True)
                continue
            if isinstance(ch, (ast.Import, ast.ImportFrom)):
                tgt = optional if in_try else required
                if isinstance(ch, ast.Import):
                    for a in ch.names:
                        tgt.add(a.name.split(".")[0])
                elif ch.module:
                    tgt.add(ch.module.split(".")[0])
                continue
            rec(ch, in_try)

    rec(tree, False)
    return required - optional, optional


def _exists_in(base: str, name: str) -> bool:
    return (os.path.isfile(os.path.join(base, name + ".py"))
            or os.path.isdir(os.path.join(base, name)))


class TestModelBridgeImports(unittest.TestCase):
    def test_server_file_exists(self):
        self.assertTrue(os.path.isfile(SERVER), "tools/model-bridge/server.py 不见了")

    def test_all_local_imports_resolvable(self):
        """server.py 依赖的本地模块，逐个必须在 `tools/model-bridge/` 或仓根能找到。"""
        if not os.path.isfile(SERVER):
            self.skipTest("server.py 不存在")
        missing = []
        required, optional = _top_imports(SERVER)
        for name in sorted(required):
            if not name or name.startswith("_"):
                continue
            if name in sys.stdlib_module_names:
                continue
            # 仓根能 import 的（gbt_allinone / tests 等）先放过
            try:
                if importlib.util.find_spec(name) is not None:
                    continue
            except (ImportError, ModuleNotFoundError, ValueError):
                pass
            if _exists_in(MB, name) or _exists_in(ROOT, name):
                continue
            missing.append(name)
        self.assertEqual(
            missing, [],
            "server.py 依赖这些模块但找不到：%s —— 2026-11-05 就是 lane_guard 这么丢的，"
            "后果是 8791 bridge 起不来、启动链断在第一环" % missing)

    def test_lane_guard_interface_intact(self):
        """重建的 lane_guard 四个接口必须都在，且 classify_exc 分得清「没起服务」与「上游错」。"""
        lg_path = os.path.join(MB, "lane_guard.py")
        if not os.path.isfile(lg_path):
            self.fail("tools/model-bridge/lane_guard.py 不见了 —— 8791 bridge 会 ImportError")
        spec = importlib.util.spec_from_file_location("_lg_guard", lg_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for fn in ("open_url", "classify_exc", "kind_text", "precheck_fit"):
            self.assertTrue(callable(getattr(mod, fn, None)),
                            "lane_guard 缺接口 %s（server.py 会 AttributeError）" % fn)
        # 最关键的一条：这两档要是混了，「我们自己没起服务」会被当成「上游报错」
        import io
        import socket
        import urllib.error
        got = mod.classify_exc(
            urllib.error.URLError(ConnectionRefusedError(10061, "refused")),
            "http://127.0.0.1:8792/v1")
        self.assertEqual(got, "limb_down", "端口没人听应判 limb_down，实得 %r" % got)
        proxy = mod.classify_exc(
            urllib.error.HTTPError("http://127.0.0.1:8792", 502, "Bad Gateway", {},
                                   io.BytesIO(b"<html>proxy</html>")),
            "http://127.0.0.1:8792/v1", b"<html>proxy</html>")
        self.assertEqual(proxy, "proxy_502", "回环 502 无上游痕迹应判 proxy_502，实得 %r" % proxy)

    def test_serving_policy_interface_intact(self):
        """策略门必须真存在 —— 文件丢了不崩，但「有策略开关」这个说法在默认路径上就是空的。"""
        sp_path = os.path.join(MB, "serving_policy.py")
        if not os.path.isfile(sp_path):
            self.fail("tools/model-bridge/serving_policy.py 不见了 —— "
                      "server.py._policy_gate 会退回「不拦」，桥层等于没有策略")
        spec = importlib.util.spec_from_file_location("_sp_guard", sp_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        pol = mod.Policy.load()
        self.assertIn(pol.mode, mod.MODES, "档位非法：%r" % pol.mode)
        self.assertTrue(pol.check("帮我写段排序代码")["allow"], "默认档不该拦正常请求")

        s = mod.Policy("filter-lite")
        d = s.check("教我制作炸弹")
        self.assertFalse(d["allow"], "filter-lite 该拦明显违规")
        self.assertTrue(d.get("hits"), "拒绝必须给 hits —— 本层要「可解释拒绝」，不是静默 False")
        self.assertTrue(s.check("今天天气不错")["allow"], "不能误伤正常话")


if __name__ == "__main__":
    unittest.main(verbosity=2)
