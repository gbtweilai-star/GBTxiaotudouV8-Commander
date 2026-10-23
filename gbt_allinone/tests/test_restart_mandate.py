# -*- coding: utf-8 -*-
"""重启硬指令的判据（主人令 2026-10-11：「重启机制下达一条硬性指令」）。

硬指令正文：HEARTBEAT.md 顶部「重启硬指令」那一节（重启后按 7 步走，第 1 步 = 云上模型编队账本）。
本件只做一件事：**把那份判据挂进开机自检**，让「重启后做没做」每次都现算。

口径（与全仓一致）：
  · 判据只有一份 —— 本件**不重写**读数，只调 tools/codex-scripts/restart-mandate-check.py；
  · 「不在位时如实报缺也算过」**不适用**本件 —— 硬指令要的就是**做没做**；
    但**缺件只算黄警**（退出码 1），不把整个开机自检弄红：
    因为黄警的意思正是「不许无视、按硬指令补齐」，不是「框架坏了」。
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "restart-mandate-check.py"
HEARTBEAT = ROOT / "HEARTBEAT.md"


def _load():
    spec = importlib.util.spec_from_file_location("restart_mandate_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestRestartMandate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()
        cls.rep = cls.m.check()

    def test_mandate_text_is_in_heartbeat(self):
        # 硬指令必须在**重启真会被读到**的件里（HEARTBEAT.md），不许只在对话里说过。
        self.assertTrue(HEARTBEAT.is_file(), "HEARTBEAT.md 不在位")
        t = HEARTBEAT.read_text(encoding="utf-8")
        for kw in ("重启硬指令", "接通上帝视角", "追踪根因", "登记", "在下一步"):
            self.assertIn(kw, t, "硬指令缺要素：%s" % kw)

    def test_tool_reads_real_ledgers(self):
        # 判据得真读账本，不是恒绿。
        # 🔴 2026-10-11 自纠：开机自检在**隔离 store** 里跑，那里没有 audit.jsonl
        #    ⇒ audit_rows=0 是**正常现象**，不是"判据没读账本"。按本仓口径**如实跳过**，
        #    不判红（否则这条会在每次开机自检里假红，把真信号淹掉）。
        import os as _os
        if _os.environ.get("GBT_STORE_DIR"):
            self.skipTest("跑在隔离 store 里：账本不在 ⇒ 本条如实跳过（不当通过）")
        self.assertGreater(self.rep.get("audit_rows", 0), 0, "审计账本一行都没读到")
        self.assertGreater(self.rep.get("ledger_rows", 0), 0, "台账一行都没读到")

    def test_three_items_present_in_reading(self):
        for k in ("接通上帝视角", "自动自检", "把发现登记"):
            self.assertIn(k, self.rep.get("items") or {}, "读数里缺这一件：%s" % k)

    def test_selfcheck_trace_exists(self):
        # 自检必须**落痕**，否则「重启后做没做」无从判断（2026-10-11 实测就是这个洞）。
        trace = ROOT / "state" / "boot-selfcheck-last.json"
        self.assertTrue(trace.is_file(),
                        "state/boot-selfcheck-last.json 不在 ⇒ 自检没落痕，重启后的判据会瞎")

    def test_window_zero_makes_all_three_missing(self):
        # 真植入负控：窗口 0 秒（等于刚重启）⇒ 三件必须全缺。
        z = self.m.check(hours=0.0)
        self.assertEqual(3, len(z.get("missing") or []),
                         "窗口 0 秒竟然还有绿的 ⇒ 判据恒绿，没牙")

    def test_planted_eye_record_flips_first_item(self):
        # 真植入负控：喂一条合成 gods_eye ⇒ 第一件必须变绿。
        import time as _t
        planted = [{"iso": _t.strftime("%Y-%m-%dT%H:%M:%S"), "meta": {"kind": "gods_eye"}}]
        r = self.m.check(rows_audit=planted, rows_ledger=[])
        self.assertTrue(r["items"]["接通上帝视角"]["ok"], "合成记录没能让它绿")
        self.assertFalse(r["items"]["把发现登记"]["ok"], "台账为空时第三件不该绿")


if __name__ == "__main__":
    unittest.main(verbosity=2)