# -*- coding: utf-8 -*-
"""warm_switch「没使用的时候绝不能消耗」的判据（Owner 2026-10-21 令，逐字：「你直接操作没使用的时候绝不能消耗」）。

## 这条判据为什么必须存在（当时逮到的事故原形）

端点 `qnnqf9w8xcefj8`（gbt-v8-live）在**没人用**的情况下仍计费：
  · 心跳最后一次成功 11:27:39 之后就没了，端点 `workers.running` 仍 = 1；
  · 账户实读烧速 **$0.704/时**，余额 **$6.385** ⇒ 约 9 小时见底；
  · 服务端真账（`GET /v1/billing/endpoints`）显示它**天天在收钱**，连没干活的 10-15 / 10-18 也各收 8 分钟。
两个病根（都在本文件判）：
  ① `off()` 只 `taskkill` 本机心跳进程，**一个字节都不碰云端 worker**，却在回执里写「恢复省钱」；
  ② 端点配置 `idleTimeout=301`（碰一下就白跑 5 分钟）+ `executionTimeoutMs=null`（卡死的请求能跑到天荒地老）。
本件**全部离线**：不连网、不动门、不碰任何云端资源（P14：判据自己也得先真跑一次）。
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "gbt_allinone" / "tools" / "warm_switch.py"


def _func_src(name: str) -> str:
    """按 AST 取**某个函数本体**的源码 —— 判据只许量对象，不许量整个文件（P1 判据错尺）。"""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    lines = SRC.read_text(encoding="utf-8").splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError("源码里找不到函数 %s" % name)


def _load():
    spec = importlib.util.spec_from_file_location("warm_switch_probe", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestScale0IsNarrow(unittest.TestCase):
    """缩容必须只能缩、不能扩 —— 否则「自动省钱」这条路就成了加钱的后门。"""

    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_scale0_body_cannot_keep_workers_alive(self):
        b = self.m._SCALE0
        self.assertEqual(b["workersMin"], 0, "workersMin 必须是 0（不许留常驻底）")
        self.assertLessEqual(b["idleTimeout"], 5, "idleTimeout 必须压到最小（原来 301s 是白烧 5 分钟）")
        self.assertTrue(b.get("executionTimeoutMs"), "必须给执行上限，null=卡死请求能无限计费")

    def test_negative_control_caller_cannot_raise_min(self):
        """负对照：调用方塞 workersMin/workersMax 上线也没用（结构上吞掉，不进 PATCH 体）。"""
        seen = {}

        def fake_rest(path, method="GET", body=None):
            if method == "PATCH":
                seen["path"] = path
                seen["body"] = body
            return 200, {"workersMin": 0, "idleTimeout": 5, "workers": []}

        m = self.m
        orig_rest, orig_health = m._rest, m._health
        m._rest = fake_rest
        m._health = lambda: {"workers": {"running": 0}}
        try:
            m.scale0(workersMin=8, workersMax=8)
        finally:
            m._rest, m._health = orig_rest, orig_health
        self.assertEqual(seen.get("body"), m._SCALE0, "PATCH 体必须恒等于 _SCALE0，调用方改不动它")
        self.assertEqual(seen["body"]["workersMin"], 0)


class TestOffReallyScalesToZero(unittest.TestCase):
    """off() 不许只杀本机进程 —— 必须真打云端。"""

    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_off_calls_scale0(self):
        called = {}
        m = self.m
        orig = m.scale0
        m.scale0 = lambda **kw: (called.update(kw) or {"ok": True, "http": 200,
                                                      "after": {"workersMin": 0}, "running": 0})
        try:
            r = m.off()
        finally:
            m.scale0 = orig
        self.assertIn("why", called, "off() 必须把缩容理由传下去（审计要看得懂）")
        self.assertTrue(r["ok"], "scale0 成功时 off() 才算成功")

    def test_source_no_longer_claims_fake_scale_down(self):
        """量具必须量**对象本体**：`off()` 函数体里不许再有那句假话（文件别处的复盘注记不算）。"""
        body = _func_src("off")
        self.assertNotIn("端点按 idleTimeout 缩 0", body,
                         "off() 里不许再声称「心跳停了就自动缩 0」（旧版根本不碰 worker）")
        self.assertIn("scale0(", body, "off() 必须真的调缩容")


class TestBleedingJudge(unittest.TestCase):
    """`bleeding` = 没人用却还在跑 —— 这条判据这次必须有，且方向不能反。"""

    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def _status(self, workers):
        m = self.m
        orig_h, orig_c = m._health, m.config
        m._health = lambda: {"workers": workers}
        m.config = lambda: {"ok": True, "workersMin": 0, "idleTimeout": 5, "executionTimeoutMs": 180000}
        try:
            return m.status()
        finally:
            m._health, m.config = orig_h, orig_c

    def test_positive_control_hot_without_beat_is_bleeding(self):
        st = self._status({"idle": 0, "ready": 1, "running": 0})
        self.assertTrue(st["bleeding"], "没人用 + 还有 worker 活着 ⇒ 必须报 bleeding（正控）")

    def test_negative_control_zero_workers_is_clean(self):
        st = self._status({"idle": 0, "ready": 0, "running": 0})
        self.assertFalse(st["bleeding"], "缩 0 之后不许虚报（负控）")

    def test_status_reports_real_config(self):
        st = self._status({"idle": 0, "ready": 0, "running": 0})
        self.assertEqual(st["workersMin"], 0)
        self.assertEqual(st["idleTimeout"], 5)
        self.assertTrue(st["config_ok"], "配置读不到要如实标 config_ok=False，不许装成 0")


class TestUnknownOpFailsClosed(unittest.TestCase):
    def test_unknown_op_rejected(self):
        m = _load()
        r = m.run({"op": "把 idleTimeout 调回 301"})
        self.assertFalse(r.get("ok"), "未列出的 op 必须 fail-closed")
        for k in ("scale0", "config"):
            self.assertIn(k, r.get("ops") or [], "ops 清单要带上新 op")


if __name__ == "__main__":
    unittest.main(verbosity=2)
