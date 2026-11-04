# -*- coding: utf-8 -*-
"""原生四觉闭环 判据（主人令 2026-10-09：「视觉跟手分开……瞎子操作」「瞎还没脑」「还有耳，嘴」）。

锁五件：
  ① 四觉齐：眼/耳/嘴/手 都在（status 里逐个点名，不许少一觉）；
  ② **看不到绝不下发动作**（观测过期 ⇒ 拒动，且说清是第①眼）；
  ③ **没脑绝不下发动作**（决策 BLOCKED ⇒ 拒动，且说清是第②脑）；
  ④ **没内容不说**（空嘴必须拒）；
  ⑤ 门与内层真调用**同口径**：眼/耳=privacy_read · 嘴=audio_output · 手=desktop_control+privacy_read。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 🔴 仓约定（照 test_framework.py:11-16）：**先设隔离 store 再导入被测模块** ——
#    否则仓里的保护闸会拒（"拒绝在绑定：真 store，改的就是真（成品）测试"）。
#    我原来四个判据文件都没设 ⇒ 体检里用 pytest 跑时全部 rc=2（实测撞了）。
os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_test_store_"))

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import vision_loop as VL        # noqa: E402
from gbt_allinone.security import policy          # noqa: E402


class VisionLoopTest(unittest.TestCase):

    def test_four_senses_all_present(self):
        s = VL.run("status")
        self.assertTrue(s["ok"], s)
        for sense in ("眼", "耳", "嘴", "手"):
            self.assertIn(sense, s["四觉"], "四觉里少了「%s」" % sense)
        for k, v in s["四觉"].items():
            self.assertTrue(str(v).strip(), "%s 必须写清走哪条口" % k)

    def test_blind_never_acts(self):
        """观测过期 ⇒ 拒动（这是"瞎"那一半）。"""
        stale = {"age_ms": 99999, "nodes": [], "raw": 1}
        dec = {"决策": "SELECT", "目标": 0, "两查": {"过": True, "说明": "x"}}
        r = VL.act(dec, stale)
        self.assertFalse(r["ok"], "过期观测竟然放行了下发")
        self.assertTrue(r.get("拒动"))
        self.assertIn("看不到就不动", str(r.get("为什么")))

    def test_brainless_never_acts(self):
        """决策 BLOCKED ⇒ 拒动（这是"没脑"那一半）。"""
        fresh = {"age_ms": 0, "nodes": [], "raw": 1}
        dec = {"决策": "BLOCKED", "目标": None, "两查": {"过": True, "说明": "x"}}
        r = VL.act(dec, fresh)
        self.assertFalse(r["ok"], "没脑竟然放行了下发")
        self.assertIn("没脑就不动", str(r.get("为什么")))

    def test_empty_mouth_refuses(self):
        r = VL.speak("   ")
        self.assertFalse(r["ok"])
        self.assertIn("没内容就不说", str(r.get("为什么")))

    def test_gate_matches_inner_calls(self):
        """门与内层真调用**同口径** —— 2026-11-04 改的是口径分层，不是放宽。

        原来这里断言 `.scopes`，因为那时候「记录」与「要票」是同一张表。
        2026-11-01 主人令撤掉身体类（desktop_control / audio_output /
        browser_control / device_control / network_private）的票之后，`add()`
        把被撤票的作用域**整条丢弃** ⇒ 门不但不要票，连痕迹都没有：
        「撤票」被做成了「失明」——实测 vision_loop.act 返回 ['privacy_read']，
        少了 desktop_control，而这台机器动过键鼠这件事在审计里查不到。

        现在两份口径分开：
          · observed = 真实发生的作用域（**审计口径**，必须与内层调用逐项一致）
          · scopes   = 仍要票的作用域（**授权口径**，身体类应为空）
        """
        obs = {"status": set(), "look": {"privacy_read"}, "hear": {"privacy_read"},
               "speak": {"audio_output"}, "act": {"desktop_control", "privacy_read"},
               "loop": {"desktop_control", "privacy_read"}}
        for op, exp in obs.items():
            d = policy.evaluate("vision_loop", {"op": op})
            self.assertEqual(set(d.observed), exp,
                             "vision_loop.%s 的 observed 与内层调用不同口径" % op)
            self.assertEqual(set(d.scopes), set(),
                             "vision_loop.%s 属身体（2026-11-01 主人令）不该要票" % op)

        # 耳：voice.listen 必须被记成隐私载体（原来空 ⇒ 麦克风开了没人知道）
        self.assertIn("privacy_read",
                      set(policy.evaluate("voice", {"op": "listen"}).observed),
                      "voice.listen 没被记账 ⇒ 耳是裸的")

        # 同一件「听」在两个入口上必须同口径（vision_loop.hear vs voice.listen）
        self.assertEqual(
            set(policy.evaluate("voice", {"op": "listen"}).observed),
            set(policy.evaluate("vision_loop", {"op": "hear"}).observed),
            "同一件「听」在 voice 与 vision_loop 上口径不同")

    def test_dangerous_faces_still_need_ticket(self):
        """护栏：这次改口径**不许**放宽危险面（自证用，防我顺手放松）。"""
        cases = [("body_open", {}, "process_execute"),          # 起外部程序
                 ("osint_scan", {"target": "127.0.0.1"}, "osint_private"),  # 内网扫描
                 ("mirror_ascend", {}, "deploy_publish"),       # G3 生产面板
                 ("keylogger", {}, "privacy_read")]             # 黑客面
        for kind, payload, want in cases:
            got = set(policy.evaluate(kind, payload).scopes)
            self.assertIn(want, got, "%s 的 %s 被放宽了" % (kind, want))

    def test_observed_superset_of_scopes(self):
        """铁律：审计口径必须覆盖授权口径 —— scopes 里有的，observed 一条都不能漏。"""
        for kind, payload in (("vision_loop", {"op": "act"}), ("voice", {"op": "listen"}),
                              ("body_click", {}), ("body_open", {}),
                              ("osint_scan", {"target": "127.0.0.1"})):
            d = policy.evaluate(kind, payload)
            self.assertLessEqual(set(d.scopes), set(d.observed),
                                 "%s: scopes 里有 observed 没记到的作用域" % kind)


if __name__ == "__main__":
    unittest.main()
