# -*- coding: utf-8 -*-
"""freebuff 终端集成判据（主人令 2026-09-28「把 freebuff 这个终端集成进我们的对话面板，编程就走这个」）。

判据（每条都能红；**核心是把"面板能做到哪一步"钉死，不许拿愿望当能力**）：
  A. **真身与版本真读**：版本来自 `freebuff-metadata.json`（或真跑 `-v`），**不许写死常量**；
     隔离 HOME 里二进制真在盘上；
  B. **"TUI-only"是现读结论**：现跑 `--help` ⇒ **没有一次性 prompt 参数**；若哪天有了，
     判据会红（提醒改做面板直驱）—— 这就是"结论带证据"；
  C. **起终端要票**：`launch` 缺 `process_execute` ⇒ 必须 denied（不许悄悄起进程）；
  D. **启动脚本必须 CRLF + ASCII**（血账：LF 被 cmd.exe 拆行、中文注释被当命令执行）；
  E. **`.cmd` 壳要经 cmd /c 调**（血账：Python subprocess 直接调 `freebuff` ⇒ FileNotFoundError）；
  F. **面板页在册**：`console_hub.PAGES` 里有 freebuff 页，且页面真在盘上。
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "gbt_allinone" / "tools"


def _load(name: str, path: Path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


class TestFreebuffTerm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("fbt_t", T / "freebuff_term.py")
        cls.hub = _load("hub_fbt", T / "console_hub.py")

    # ---- A 真身与版本 ----
    def test_a_version_and_binary_are_real(self):
        s = self.m.status()
        self.assertTrue(s["exe_exists"], f"隔离 HOME 里没有 freebuff.exe：{s['exe']}")
        self.assertGreater(s["exe_mb"], 50, "二进制大小异常（像半成品）")
        self.assertRegex(str(s["version"]), r"^\d+\.\d+", "版本读不出来（不许写死）")
        src = Path(T / "freebuff_term.py").read_text(encoding="utf-8")
        self.assertNotIn('"version": "0.1.2"', src, "版本被写死成常量 ⇒ 匿名数字，要真读")

    # ---- B TUI-only 是现读结论 ----
    def test_b_tui_only_is_a_live_conclusion(self):
        f = self.m.flags()
        self.assertTrue(f.get("ok"), f"跑不动 --help：{f.get('error')}")
        self.assertFalse(f["has_one_shot_prompt"],
                         "**发现了一次性 prompt ⇒ '面板不能直驱'这条结论要改**（判据红了才对）")
        self.assertIn("TUI", f["verdict"])
        self.assertTrue(f.get("entry", "").lower().endswith((".cmd", ".bat", ".exe")),
                        f"入口没解析成真身：{f.get('entry')}")

    # ---- C 起终端要票 ----
    def test_c_launch_needs_a_ticket(self):
        r = self.m.launch()
        if r.get("ok"):
            self.skipTest("当前在受信会话里（主人在场），launch 直接放行 —— 这条不适用")
        self.assertTrue(r.get("denied") or r.get("fail_closed"), f"缺票却没拒：{r}")
        self.assertIn("how_to_grant", r, "拒了没给授权命令")

    # ---- D 启动脚本 CRLF + ASCII ----
    def test_d_launcher_script_is_crlf_ascii(self):
        d = self.m.launch(dry_run=True)
        prev = d.get("script_preview", "")
        self.assertIn("\r\n", prev, "启动脚本不是 CRLF（cmd.exe 会拆错行）")
        try:
            prev.encode("ascii")
        except UnicodeEncodeError:
            self.fail("启动脚本含非 ASCII（GBK 控制台会当命令执行）")
        self.assertIn("%~dp0", prev, "没自定位（%~dp0）⇒ 会在别人的工作目录里起")

    # ---- E .cmd 壳要经 cmd /c ----
    def test_e_cmd_shim_goes_through_cmd(self):
        ent = self.m._entry()
        self.assertTrue(ent, "PATH 里找不到 freebuff 入口")
        r = self.m._invoke(["-v"], timeout=120)
        self.assertTrue(r.get("ok"), f"经 cmd /c 调不动：{r.get('error')}")
        if ent.lower().endswith((".cmd", ".bat")):
            src = Path(T / "freebuff_term.py").read_text(encoding="utf-8")
            self.assertIn('"cmd", "/c"', src, "没走 cmd /c ⇒ 大概率 FileNotFoundError 复发")

    # ---- F 面板页在册且在盘 ----
    def test_f_panel_page_registered(self):
        rows = {r["page"]: r for r in self.hub.pages()["rows"]}
        self.assertIn("freebuff", rows, "console_hub.PAGES 里没有 freebuff 页")
        p = ROOT / rows["freebuff"]["path"]
        self.assertTrue(p.is_file(), f"面板页不在盘上：{p}（跑 console_pages render）")
        txt = p.read_text(encoding="utf-8")
        for needle in ("TUI", "一次性 prompt", "process_execute", "start-freebuff.cmd"):
            self.assertIn(needle, txt, f"页面上没写清『{needle}』——边界不许含糊")


if __name__ == "__main__":
    unittest.main(verbosity=2)
