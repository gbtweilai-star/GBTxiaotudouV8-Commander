# -*- coding: utf-8 -*-
"""门可见性审计 · 带牙用例（R-H248 · 坑册 §60）。

这些用例咬的是**判据本身**，不是装饰：
  · 三态不许漏（不许有沉默的文件）
  · 「已纳入」必须真命中门自己的三条规则（防清单与门漂移）
  · 「显式不纳入」必须带理由与出处（§57 同族）
  · 空清单不许当绿（§45）
  · 本模块**不许复刻**门的范围表（范围只从 framework_gate 读）
"""
from __future__ import annotations

import unittest

from gbt_allinone.tools import framework_gate as fg
from gbt_allinone.tools import gate_visibility as gv

_CACHE: dict = {}


def _rows():
    if "rows" not in _CACHE:
        _CACHE["rows"] = gv.scan()["files"]
    return _CACHE["rows"]


class StateTests(unittest.TestCase):
    """三态判据。"""

    def test_accepted_py_under_watch_dir(self):
        st, why = gv.classify("gbt_allinone/api.py")
        self.assertEqual(st, "已纳入", why)

    def test_root_watched_instruction_file(self):
        self.assertEqual(gv.classify("AGENTS.md")[0], "已纳入")

    def test_root_design_instruction_is_watched_after_rh249(self):
        # R-H249 四类拍板：根级 .md 是行为面（与 AGENTS.md 同级）⇒ 已纳入
        st, why = gv.classify("DESIGN.md")
        self.assertEqual(st, "已纳入", why)
        self.assertIn("根级行为面", why)

    def test_owner_memory_files_are_explicitly_excluded(self):
        # USER.md / MEMORY.md：门**显式不纳**（不是忘了纳）
        for name in ("USER.md", "MEMORY.md"):
            st, why = gv.classify(name)
            self.assertEqual(st, "显式不纳入", why)
            self.assertIn("记忆载体", why)

    def test_ps1_is_watched_after_rh249(self):
        st, why = gv.classify("gbt_allinone/deploy/healthcheck.ps1")
        self.assertEqual(st, "已纳入", why)

    def test_root_launcher_pair_is_watched(self):
        # 根级 .bat/.py 是启动器：deploy-app-one-click.bat → deploy_app_oneclick.py
        self.assertEqual(gv.classify("deploy-app-one-click.bat")[0], "已纳入")
        self.assertEqual(gv.classify("deploy_app_oneclick.py")[0], "已纳入")

    def test_docs_md_is_declared_not_watched_after_rh249(self):
        # 图纸面：显式不纳（带理由与出处），不是未决定、也不是已被门看见
        st, why = gv.classify("gbt_allinone/docs/门盲区清单.md")
        self.assertEqual(st, "显式不纳入", why)
        self.assertIn("出处", why)

    def test_brain_and_caps_are_declared_not_watched(self):
        for rel in ("brain/aesthetic_brain.py", "caps/design_brain/run.py"):
            st, why = gv.classify(rel)
            self.assertEqual(st, "显式不纳入", why)
            self.assertIn("出处", why)

    def test_gate_skip_dir_is_declared_not_watched(self):
        st, why = gv.classify("holo_pet/node_modules/electron/x.js")
        self.assertEqual(st, "显式不纳入", why)
        self.assertIn("跳过目录", why)

    def test_judged_dir_is_declared_not_watched_with_source(self):
        st, why = gv.classify("delivery/index_v6.html")
        self.assertEqual(st, "显式不纳入", why)
        self.assertIn("出处", why)

    def test_extra_file_is_watched(self):
        self.assertEqual(
            gv.classify(".cluster/dd_squad/toolchain_manifest.json")[0], "已纳入")

    def test_classify_never_returns_empty_state(self):
        for p in ("", "README.md", "x/y/z.qqq", "gbt_allinone/a.py"):
            st, _ = gv.classify(p)
            self.assertIn(st, gv.STATES)


class GateTests(unittest.TestCase):
    """四条机械闸。"""

    def test_gate_three_states_clean(self):
        self.assertTrue(gv.check_three_states(_rows())["ok"])

    def test_gate_declared_reasons_present(self):
        self.assertTrue(gv.check_declared_reasons()["ok"])

    def test_gate_watched_without_rule_clean(self):
        r = gv.check_watched_without_rule(_rows())
        self.assertTrue(r["ok"], r)

    def test_empty_sample_is_red_not_green(self):
        # §45：空清单不是通过，是「没测到」
        self.assertFalse(gv.check_sample([])["ok"])
        self.assertTrue(gv.check_sample(_rows())["ok"])

    def test_watched_without_rule_detects_fake_row(self):
        fake = [{"path": "delivery/fake.py", "state": "已纳入", "why": "", "ext": ".py"}]
        r = gv.check_watched_without_rule(fake)
        self.assertFalse(r["ok"])
        self.assertEqual(r["rule"], "watched_without_rule")


class NoSecondTruthTests(unittest.TestCase):
    """不许复刻门的范围表 —— 范围只能从门读。"""

    def test_scope_read_from_gate(self):
        st = gv.run("status")
        self.assertEqual(st["gate_scope"]["dirs"], list(fg._WATCH_DIRS))
        self.assertEqual(st["gate_scope"]["suffix"], list(fg._WATCH_SUFFIX))
        self.assertEqual(st["gate_scope"]["root_files"], list(fg._WATCH_ROOT_FILES))
        self.assertEqual(st["gate_scope"]["root_suffix"], list(fg._WATCH_ROOT_SUFFIX))
        self.assertEqual(st["gate_scope"]["root_exclude"], list(fg._WATCH_ROOT_EXCLUDE))
        self.assertEqual(st["gate_scope"]["extra_files"], list(fg._WATCH_EXTRA_FILES))

    def test_audit_is_readonly_and_does_not_touch_gate(self):
        before = (tuple(fg._WATCH_DIRS), tuple(fg._WATCH_SUFFIX),
                  tuple(fg._WATCH_ROOT_FILES), tuple(fg._WATCH_ROOT_SUFFIX),
                  tuple(fg._WATCH_ROOT_EXCLUDE), tuple(fg._WATCH_EXTRA_FILES))
        a = gv.audit()
        after = (tuple(fg._WATCH_DIRS), tuple(fg._WATCH_SUFFIX),
                 tuple(fg._WATCH_ROOT_FILES), tuple(fg._WATCH_ROOT_SUFFIX),
                 tuple(fg._WATCH_ROOT_EXCLUDE), tuple(fg._WATCH_EXTRA_FILES))
        self.assertTrue(a["readonly"])
        self.assertEqual(before, after, "审计不许改门的监视范围")


class BlindSpotTests(unittest.TestCase):
    """盲区清单的形状。"""

    def test_blind_spots_have_shape_and_order(self):
        """盲区清单的形状。

        🔴 2026-10-17 翻正（留痕 · 原断言 / 为什么翻 / 现口径）：
          原断言：`assertTrue(rows, "盲区清单为空 ⇒ 先怀疑扫描器自己")` —— 要求盲区**非空**。
          为什么翻：它与 `test_blindspot_registry::test_zero_undecided`（主人令「绝对不能有
            任何盲区」⇒ 未决定必须为 0）**直接冲突**：未决定=0 时清单必空，两条判据不可能同时绿。
            实测 6 件门盲区已按设计登记（5 件 `.bak*` 备份散件 + 1 件 `.webmanifest`）⇒ 现在就是 0。
          现口径：**先钉死主人令**（盲区必须 0）；若真出现盲区，再逐条验形状/降序/理由 ——
            形状的牙一条不少，只是不再"为了有清单而要求有盲区"。
        """
        rows = gv.blind_spots(_rows())
        all_undecided = [r for r in _rows() if r["state"] == "未决定"]
        self.assertEqual(len(all_undecided), 0,
                         "门盲区必须为 0（主人令）：%s" % [r["path"] for r in all_undecided[:6]])
        for r in rows:
            self.assertEqual(r["files"] > 0, True)
            self.assertIn(r["kind"], ("文件", "目录"))
            self.assertTrue(r["why"])
        counts = [r["files"] for r in rows]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_blind_total_matches_scan(self):
        """`blind_total` 必须等于**独立一次扫描**里「未决定」的行数。

        🔴 2026-09-22 第 42 轮修（错报治理 · **快照 vs 现扫**）：
        原来左边是 `gv.audit()`（**每次都重新扫**），右边是 `_rows()`——
        而 `_rows()` 是**模块级快照**（`_CACHE["rows"] = gv.scan()["files"]`，只算一次）。
        两边取自**不同时刻**：全量跑时别的用例动过盘上的文件，
        快照与现扫就会不等 ⇒ 红；而单文件跑时前后没有别的写入 ⇒ 绿。
        实测归类：**隔离绿 + 全量红 = 跨文件污染**（第 39 轮那套两模式回归正好把它分出来了）。
        ⇒ 这条要守的是 `audit()` 有没有拿**过期的行集**算 blind_total。

        🔴 2026-09-23 第 52/53 轮再修（**"现扫 vs 现扫"还是半条命**）：
        第 42 轮把两边都改成"现扫"，但**它们仍然是两次独立的扫盘** ——
        中间只要有人动文件就不等。第 52 轮树指纹实测到它就是这么红的
        （`tree_changed=True`，动盘的是**并发会话**，跟本判据对错毫无关系）。
        ⇒ 现在**只扫一次**：先把行集拿到手，再让 `audit(rows=...)` 用**同一份**行集算。
          判的东西没变（audit 不许用过期的行集），但**不再依赖"这几十毫秒里没人写盘"**。
        """
        rows = gv.scan()["files"]          # ← **只扫这一次**
        a = gv.audit(rows=rows)            # ← 同一份行集递给 audit，不再自己扫第二遍
        n_undecided = len([r for r in rows if r["state"] == "未决定"])
        self.assertEqual(a["blind_total"], n_undecided)

    def test_ext_inventory_answers_md_question(self):
        inv = {r["ext"]: r for r in gv.ext_inventory(_rows())}
        self.assertIn(".md", inv)
        # R-H249 后：根级 .md 全进可见范围（除 USER/MEMORY）⇒ 已纳入不再等于"5 个名字"
        self.assertGreaterEqual(inv[".md"]["counts"]["已纳入"],
                                len(fg._WATCH_ROOT_FILES))
        # 但 docs 图纸面与 memory 日记仍**不在**门里（前者显式不纳、后者仍是未决定）
        self.assertGreater(inv[".md"]["counts"]["显式不纳入"], 0)
        # 🔴 2026-10-17 翻正（留痕）：原断言 `未决定 > 0` 与主人令「绝对不能有任何盲区」
        #   （test_blindspot_registry::test_zero_undecided）冲突 —— 它把**旧状态**当契约。
        #   现口径：.md 里**未决定必须为 0**。diagnostics：docs 图纸面走显式不纳，
        #   memory 日记由 `_WATCH_ROOT_EXCLUDE`（主人记忆载体）显式排除，不该再落未决定。
        self.assertEqual(inv[".md"]["counts"]["未决定"], 0,
                         ".md 不许再有未决定（主人令：零盲区）")


if __name__ == "__main__":
    unittest.main()
