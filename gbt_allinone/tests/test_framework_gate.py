# -*- coding: utf-8 -*-
"""框架自改门（R-H99）契约测试：隔离树 + 临时账本，跑真 CLI。

为什么用子进程 + 隔离树：
  · 本门监视的是**框架自身源码**——测试若在真树上制造改动，就是在拿真账本做实验；
  · 隔离树（--root）+ 临时账本（--store）让四条规则（基线/护照/拒关/去噪）能在不碰真账本、
    不碰真源码的前提下被真跑一遍。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(*args):
    cmd = [sys.executable, "-m", "gbt_allinone.tools.framework_gate", *args]
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")


class FrameworkGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gbt_fgate_")
        base = Path(self.tmp.name)
        self.root = base / "ws"
        self.store = base / "ledger"
        (self.root / "gbt_allinone").mkdir(parents=True)
        (self.root / "holo_pet" / "node_modules").mkdir(parents=True)
        self.src = self.root / "gbt_allinone" / "a.py"
        self.src.write_text("x = 1\n", encoding="utf-8")
        (self.root / "holo_pet" / "node_modules" / "junk.js").write_text("// no\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _args(self, *a):
        return ("--root", str(self.root), "--store", str(self.store), *a)

    def test_no_baseline_is_red_then_green(self):
        r = _run(*self._args("verify"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["reason_code"], "no_baseline")
        self.assertEqual(_run(*self._args("snapshot", "--label", "t")).returncode, 0)
        self.assertEqual(_run(*self._args("verify")).returncode, 0)

    def test_change_without_passport_is_red_then_green_with_passport(self):
        _run(*self._args("snapshot"))
        self.src.write_text("x = 2\n", encoding="utf-8")
        r = _run(*self._args("verify"))
        self.assertEqual(r.returncode, 1)
        body = json.loads(r.stdout)
        self.assertEqual(body["verdict"], "red")
        self.assertEqual(body["findings"][0]["reason_code"], "no_passport")
        self.assertEqual(body["findings"][0]["file"], "gbt_allinone/a.py")

        cid = json.loads(_run(*self._args("open", "--reason", "契约测试：先改后开护照也要能被认领")).stdout)["id"]
        closed = _run(*self._args(
            "close", "--id", cid,
            "--evidence", "py -3.10 -c pass => rc=0",
            "--rollback", "按护照 before 哈希逐字节还原",
            "--no-stamp-reason", "契约测试跑在隔离树上，不跑四元组印章",
            "--no-review-reason", "隔离树里没有第二个 checker 可跑"))
        self.assertEqual(closed.returncode, 0, closed.stdout + closed.stderr)
        self.assertEqual(json.loads(closed.stdout)["changed_files"], 1)
        self.assertEqual(_run(*self._args("verify")).returncode, 0)

    def test_passport_after_more_edits_is_stale(self):
        _run(*self._args("snapshot"))
        self.src.write_text("y = 1\n", encoding="utf-8")
        cid = json.loads(_run(*self._args("open", "--reason", "契约测试：第一次改动框架源码")).stdout)["id"]
        _run(*self._args("close", "--id", cid, "--evidence", "cmd => rc=0",
                         "--rollback", "按护照 before 哈希把 a.py 逐字节还原",
                         "--no-stamp-reason", "契约测试跑在隔离树上",
                         "--no-review-reason", "隔离树里没有第二个 checker 可跑"))
        self.src.write_text("z = 3\n", encoding="utf-8")
        r = _run(*self._args("verify"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["findings"][0]["reason_code"], "stale_passport")

    def test_close_refuses_incomplete_passport(self):
        _run(*self._args("snapshot"))
        cid = json.loads(_run(*self._args("open", "--reason", "契约测试：缺件必须拒绝关闭")).stdout)["id"]
        # 缺证据（且没盖章说明）⇒ 拒绝关闭
        r = _run(*self._args("close", "--id", cid, "--rollback", "还原"))
        self.assertEqual(r.returncode, 2)
        body = json.loads(r.stdout)
        self.assertTrue(body["blocked"])
        self.assertEqual(body["reason_code"], "passport_incomplete")
        # 证据形状不对（没有『命令 => 读数』）⇒ 也要拒
        r2 = _run(*self._args("close", "--id", cid, "--evidence", "我跑过了没问题",
                              "--rollback", "按护照 before 哈希逐字节还原",
                              "--no-stamp-reason", "契约测试跑在隔离树上"))
        self.assertEqual(r2.returncode, 2)
        self.assertIn("=>", " ".join(json.loads(r2.stdout)["problems"]))
        # 缺回滚点 ⇒ 拒
        r3 = _run(*self._args("close", "--id", cid, "--evidence", "cmd => rc=0",
                              "--no-stamp-reason", "隔离树"))
        self.assertEqual(r3.returncode, 2)
        # 全程没有一张关闭的护照 ⇒ 老账仍是红
        self.assertEqual(_run(*self._args("verify")).returncode, 0)

    def test_single_party_evidence_cannot_close_without_independent_review(self):
        """（下面紧跟 R-H107 的基线吞护照用例。）"""
        """R-H105 多脑复核：一个 AI 可能犯傻，整个脑子不会同时傻 ⇒ 单方证据不算过关。"""
        _run(*self._args("snapshot"))
        self.src.write_text("y = 42\n", encoding="utf-8")
        cid = json.loads(_run(*self._args("open", "--reason", "复核约束测试：单方证据")).stdout)["id"]
        base = ("close", "--id", cid, "--rollback", "按护照 before 哈希逐字节还原",
                "--no-stamp-reason", "契约测试跑在隔离树上")
        # ① 只有单方证据 ⇒ 拒绝关闭
        r = _run(*self._args(*base, "--evidence", "py -c pass => rc=0"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("缺独立复核", " ".join(json.loads(r.stdout)["problems"]))
        # ② 复核与证据同标签（自己给自己作证）⇒ 仍拒绝
        r2 = _run(*self._args(*base, "--evidence", "py -c pass => rc=0",
                              "--review", "py: py -c pass => rc=0"))
        self.assertEqual(r2.returncode, 2)
        self.assertIn("不独立", " ".join(json.loads(r2.stdout)["problems"]))
        # ③ 换一个 checker 出复核 ⇒ 放行，且 verify 里能看到复核已入账
        r3 = _run(*self._args(*base, "--evidence", "py -c pass => rc=0",
                              "--review", "cross_scan: 深扫十维 => 0 断连"))
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        v = json.loads(_run(*self._args("verify")).stdout)
        self.assertEqual(v["verdict"], "green")
        self.assertEqual(v["review_waived_passports"], [])
        # ④ 显式豁免也要留痕（verify 把它列出来，不装作有复核）
        cid2 = json.loads(_run(*self._args("open", "--reason", "复核豁免测试：写清原因")).stdout)["id"]
        r4 = _run(*self._args("close", "--id", cid2, "--evidence", "py -c pass => rc=0",
                              "--rollback", "按护照 before 哈希逐字节还原",
                              "--no-stamp-reason", "契约测试跑在隔离树上",
                              "--no-review-reason", "隔离树里没有第二个 checker 可跑"))
        self.assertEqual(r4.returncode, 0, r4.stdout)
        v2 = json.loads(_run(*self._args("verify")).stdout)
        self.assertIn(cid2, v2["review_waived_passports"])

    def test_dependency_noise_does_not_turn_red(self):
        _run(*self._args("snapshot"))
        junk = self.root / "holo_pet" / "node_modules" / "junk.js"
        junk.write_text("// changed\n", encoding="utf-8")
        r = _run(*self._args("verify"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(json.loads(r.stdout)["changed_files"], 0)

    def test_status_lists_passports(self):
        """（R-H107 的基线吞护照用例见下。）"""
        _run(*self._args("snapshot"))
        cid = json.loads(_run(*self._args("open", "--reason", "契约测试：状态清单要能列出护照")).stdout)["id"]
        _run(*self._args("close", "--id", cid, "--evidence", "cmd => rc=0",
                         "--rollback", "按护照 before 哈希逐字节还原",
                         "--no-stamp-reason", "契约测试跑在隔离树上",
                         "--no-review-reason", "隔离树里没有第二个 checker 可跑"))
        st = json.loads(_run(*self._args("status")).stdout)
        self.assertEqual(st["count"], 1)
        self.assertEqual(st["passports"][0]["id"], cid)
        self.assertTrue(st["passports"][0]["complete"])

    def test_snapshot_blocked_when_passport_open(self):
        """坑册第 30 条（R-H107）：**基线不能吞护照**。

        实测踩过：护照还开着，先跑一次 snapshot，改动就被新基线吃掉 ⇒ verify 直接变绿，
        "没护照=红"这条规则被绕过。任何能抹掉变更证据的动作，本身必须先被门挡一次。
        """
        _run(*self._args("snapshot"))
        self.src.write_text("q = 1\n", encoding="utf-8")
        cid = json.loads(_run(*self._args("open", "--reason", "门洞测试：开着护照重立基线")).stdout)["id"]

        # ① 护照未关 ⇒ 拒绝立基线
        r = _run(*self._args("snapshot", "--label", "try-swallow"))
        self.assertEqual(r.returncode, 2)
        body = json.loads(r.stdout)
        self.assertTrue(body["blocked"])
        self.assertEqual(body["reason_code"], "passport_open")
        self.assertIn(cid, body["open_passports"])
        # ② 证据没被吞：verify 仍然是红（no_passport）
        v = json.loads(_run(*self._args("verify")).stdout)
        self.assertEqual(v["verdict"], "red")
        self.assertEqual(v["findings"][0]["reason_code"], "no_passport")
        # ③ 显式 --force + 理由 ⇒ 放行，但把"吞了谁的护照"写进基线
        r2 = _run(*self._args("snapshot", "--force", "--reason", "契约测试：显式吞掉"))
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        base = json.loads((self.store / "baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(base["forced_over_open_passports"], [cid])
        self.assertEqual(base["force_reason"], "契约测试：显式吞掉")
        # ④ **吞并 ≠ 结案**（R-H141）：被吞的护照仍然开着 ⇒ 下一次 snapshot 仍会被它挡；
        #    而且成功输出里必须写明这一点，不许让人以为吞完就完了。
        note = json.loads(r2.stdout).get("forced_note", "")
        self.assertIn(cid, note, "吞并成功时必须提示『被吞的是哪张护照』")
        self.assertIn("仍在开", note, "吞并成功时必须提示『它仍开着、会继续挡』")
        r3 = _run(*self._args("snapshot", "--label", "again"))
        self.assertEqual(r3.returncode, 2, "被吞的护照仍开着 ⇒ 下一次 snapshot 应该仍被挡")
        self.assertEqual(json.loads(r3.stdout)["reason_code"], "passport_open")


    # 🔴 R-H466 §61：门盲区**台账** —— changed_files=0 但盲区面有改动 ⇒ 必须留账
    def _docs_dir(self):
        d = self.root / "gbt_allinone" / "docs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _open_passport(self, label):
        return json.loads(_run(*self._args(
            "open", "--label", label, "--reason", "§61 契约测试（隔离树里造盲区改动）")).stdout)["id"]

    def test_blindspot_logged_when_only_docs_changed(self):
        """只有图纸面（.md）改动 ⇒ 账上是 0（门看不见），但**必须记一条盲区日志**。"""
        _run(*self._args("snapshot", "--label", "base"))
        cid = self._open_passport("R-H466 用例：只改图纸")
        (self._docs_dir() / "x.md").write_text("# 图纸\n", encoding="utf-8")
        r = _run(*self._args(
            "close", "--id", cid,
            "--evidence", "py -3.10 x => rc=0",
            "--rollback", "删掉隔离树 gbt_allinone/docs/x.md",
            "--no-stamp-reason", "隔离树用例，不跑四元组印章",
            "--no-review-reason", "隔离树里没有第二个 checker 可跑"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body = json.loads(r.stdout)
        self.assertEqual(body["changed_files"], 0, "图纸面不在监视范围 ⇒ 账上是 0（这正是盲区）")
        self.assertTrue(body["blindspot_logged"], "changed_files=0 但有改动 ⇒ 必须写一条盲区日志")
        self.assertGreaterEqual(body["blindspot"]["changed"], 1)
        # 台账可查（只读子命令）
        r2 = _run(*self._args("blindspots"))
        self.assertEqual(r2.returncode, 0)
        self.assertGreaterEqual(json.loads(r2.stdout)["count"], 1)

    def test_blindspot_not_logged_when_source_also_changed(self):
        """真源码也改了 ⇒ 不属于盲区，**不许**把正常刀记成盲区。"""
        _run(*self._args("snapshot", "--label", "base"))
        cid = self._open_passport("R-H466 用例：源码+图纸都改")
        (self._docs_dir() / "x.md").write_text("# 图纸\n", encoding="utf-8")
        self.src.write_text("x = 2\n", encoding="utf-8")
        r = _run(*self._args(
            "close", "--id", cid,
            "--evidence", "py -3.10 x => rc=0",
            "--rollback", "删 x.md 并把 a.py 还原成 x = 1",
            "--no-stamp-reason", "隔离树用例",
            "--no-review-reason", "隔离树里没有第二个 checker"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body = json.loads(r.stdout)
        self.assertGreaterEqual(body["changed_files"], 1)
        self.assertFalse(body["blindspot_logged"], "有真源码改动 ⇒ 不算盲区")

    def test_blindspot_scan_skips_skip_dirs(self):
        """盲区扫描必须复用 _SKIP_DIRS：__pycache__ 下的 .md 不算。"""
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.tools import framework_gate as fg
        d = self._docs_dir()
        skip = d / "__pycache__"
        skip.mkdir(parents=True, exist_ok=True)
        (skip / "junk.md").write_text("x\n", encoding="utf-8")
        (d / "real.md").write_text("y\n", encoding="utf-8")
        bs = fg.blindspot_scan(self.root, 0.0) if False else fg.blindspot_scan(
            self.root, __import__("time").time() - 120)
        self.assertEqual(bs["changed"], 1, "只算 real.md（__pycache__ 被 _SKIP_DIRS 排掉）")
        self.assertIn("real.md", bs["samples"][0])


if __name__ == "__main__":
    unittest.main()
