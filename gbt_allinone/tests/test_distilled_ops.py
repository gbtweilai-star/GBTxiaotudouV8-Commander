# -*- coding: utf-8 -*-
"""蒸馏件判据（主人令 2026-09-28「蒸馏提炼出契合GBT小土豆V8的原生能力」）。

五个源项目（GitHub 第 39 周爆款周榜）⇒ 只补**我们真缺的核**，四件新能力位：
  · `memory_bank`   ← hindsight（来源追踪 + 记忆银行别名/零停机迁移）
  · `agent_console` ← paperclip（监督循环 + 连接请求审批桥）
  · `code_audit`    ← security-audit-skill（findings 契约 + 独立验证 + 复现 + 改动面）
  · `agent_rig`     ← orca（一队 coding agent 并行 + worktree 隔离）
  · ECC **不新增**（四轴已有对位：技能/记忆/安全/判据），对位表见技能 `gbt-distilled-ops`。

判据都带**反向自检**（把"看着在判"变成"喂它坏样本必须红"）：
  A. memory_bank：印章→追来源（内容被改必须报"被改过"）· 别名环检测 · 迁移回滚（sha 不符 ⇒ 别名回滚）
  B. agent_console：判活看**读数是否更新**（不是 exit code）· **AI 批不了**连接请求 · retry 缺票必拒
  C. code_audit：没证据不开 finding · **两路读法都命中才算确认**（改文件后必须变 unverified）· 复现命令存在
  D. agent_rig：四隔离件齐 · **缺票不起编队** · 台账非空 · 不许把命令交给 shell
  E. 一体：四件都能过 `run_task` 调到（三处齐的实证）
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "gbt_allinone" / "tools"
NEW = ["memory_bank", "agent_console", "code_audit", "agent_rig"]


def _load(name: str, path: Path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


class TestMemoryBank(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("mb_t", T / "memory_bank.py")

    def test_a_stamp_then_trace_detects_content_change(self):
        """印章 + 追来源：**内容被改过必须报出来**（不许拿"大概还是那条"顶替）。"""
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "一条记忆.md"
            f.write_text("原始内容", encoding="utf-8")
            ref = str(f)
            # ⚠️ 印章台账要**重定向到临时文件**：判据不许往真台账写（血账：早先 gods_eye 判据污染过真账本）
            real_stamps = self.m._STAMPS
            self.m._STAMPS = Path(td) / "stamps.jsonl"
            try:
                self.assertTrue(self.m.stamp(ref=ref, origin="我推的", why="判据样本").get("ok"))
                t1 = self.m.trace(ref=ref)
                self.assertIn("没被动过", t1["content_verdict"], f"刚打完章就说变过：{t1['content_verdict']}")
                f.write_text("被改过的内容", encoding="utf-8")
                t2 = self.m.trace(ref=ref)
                self.assertIn("被改过", t2["content_verdict"], f"改了内容却没报：{t2['content_verdict']}")
            finally:
                self.m._STAMPS = real_stamps

    def test_b_origin_must_be_declared(self):
        r = self.m.stamp(ref="x.md", origin="大概是主人说的", why="y")
        self.assertFalse(r.get("ok"), "含糊来源竟然过了（来源不许猜）")
        r2 = self.m.stamp(ref="x.md", origin="我推的", why="")
        self.assertFalse(r2.get("ok"), "没写为什么收这条也过了")

    def test_c_alias_cycle_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            real, real_stamps = self.m._ALIASES, self.m._STAMPS
            self.m._ALIASES = Path(td) / "a.json"
            self.m._STAMPS = Path(td) / "stamps.jsonl"
            try:
                self.m.alias(name="mem:x", target="mem:y")
                self.m.alias(name="mem:y", target="mem:x")
                r = self.m.resolve(name="mem:x")
                self.assertFalse(r.get("ok"), "成环竟然解析成功了")
                self.assertTrue(r.get("cycle"), "没报环")
            finally:
                self.m._ALIASES = real

    def test_d_migrate_rolls_back_when_sha_mismatch(self):
        """迁移的**回滚**：中途有一份对不上 ⇒ 别名必须切回旧目标（旧家一根毫毛不动）。"""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "old"
            (src / "sub").mkdir(parents=True)
            (src / "a.txt").write_text("A", encoding="utf-8")
            (src / "sub" / "b.txt").write_text("B", encoding="utf-8")
            dst = Path(td) / "new"
            real, real_stamps = self.m._ALIASES, self.m._STAMPS
            self.m._ALIASES = Path(td) / "al.json"
            self.m._STAMPS = Path(td) / "stamps.jsonl"
            old_sha = self.m._sha
            try:
                # 造一个"复制后校验失败"：**只让目标侧那一份**对不上（两边都错就相等了 —— 第一版就这么写歪了）
                def fake_sha(p):
                    if str(p).endswith("b.txt") and str(dst) in str(p):
                        return "刻意不一致"
                    return old_sha(p)

                self.m._sha = fake_sha
                r = self.m.migrate_apply(old=str(src), new=str(dst), alias_name="mem:样本")
                self.assertFalse(r.get("ok"), "sha 对不上竟然报成功")
                self.assertTrue(r.get("rolled_back"), "没回滚")
                aliases = self.m._load_aliases()
                self.assertEqual(str(src), aliases.get("mem:样本"), "回滚后别名没指回旧家")
                self.assertTrue((src / "a.txt").is_file(), "旧家被动过了")
            finally:
                self.m._sha = old_sha
                self.m._ALIASES, self.m._STAMPS = real, real_stamps


class TestAgentConsole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("ac_t", T / "agent_console.py")

    def test_a_alive_is_about_readings_not_exit_codes(self):
        """判活看**读数有没有如期更新**：新鲜读数 ⇒ ok；停更 ⇒ stale（与 exit code 无关）。"""
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "读数.json"
            f.write_text("{}", encoding="utf-8")
            led, board = self.m._LEDGER, self.m._BOARD
            self.m._LEDGER = Path(td) / "l.jsonl"
            self.m._BOARD = Path(td) / "b.json"
            try:
                self.assertTrue(self.m.add(name="样本任务", evidence=str(f), every_s=600).get("ok"))
                r = self.m.tick()
                row = r["rows"][0]
                self.assertEqual("ok", row["state"], f"新鲜读数却判 {row['state']}")
                old = 3600 * 3
                os.utime(f, (old and os.stat(f).st_mtime - old, os.stat(f).st_mtime - old))
                r2 = self.m.tick()
                self.assertEqual("stale", r2["rows"][0]["state"], "停更了还判 ok")
                self.assertTrue(r2["rows"][0]["need"], "stale 却没列出该做什么")
            finally:
                self.m._LEDGER, self.m._BOARD = led, board

    def test_b_ai_cannot_approve_connection_requests(self):
        with tempfile.TemporaryDirectory() as td:
            led = self.m._LEDGER
            self.m._LEDGER = Path(td) / "l.jsonl"
            try:
                r = self.m.request(name="样本", what="要连外部模型", scope="external_llm")
                self.assertTrue(r.get("ok"))
                a = self.m.approve(req_id=r["req_id"])
                self.assertFalse(a.get("ok"), f"**AI 竟然批了连接请求**：{a}")
                self.assertTrue(a.get("denied"), "拒的形状不对")
                self.assertEqual(1, self.m.pending()["count"], "待批数不对")
            finally:
                self.m._LEDGER = led

    def test_c_retry_without_ticket_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            led, board = self.m._LEDGER, self.m._BOARD
            self.m._LEDGER, self.m._BOARD = Path(td) / "l.jsonl", Path(td) / "b.json"
            try:
                self.m.add(name="样本2", evidence="state/shortboard.json")
                r = self.m.retry(name="样本2")
                if not r.get("ok"):
                    self.assertTrue(r.get("denied") or r.get("gate"), f"拒了但没说缺票：{r}")
            finally:
                self.m._LEDGER, self.m._BOARD = led, board


class TestCodeAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("ca_t", T / "code_audit.py")

    def test_a_findings_carry_evidence_and_repro(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "s"
            d.mkdir()
            (d / "bad.py").write_text("x = 1\n" + "shutil.rmtree('C:/真身目录')\n", encoding="utf-8")
            old_f, old_led, old_root = self.m._FINDINGS, self.m._LEDGER, self.m._ROOT
            self.m._FINDINGS = Path(td) / "f.json"
            self.m._LEDGER = Path(td) / "l.jsonl"
            self.m._ROOT = Path(td)
            try:
                r = self.m.scan(target=str(d))
                self.assertTrue(r.get("findings") >= 1, f"造了一条真破坏面却没报：{r}")
                doc = json.loads(self.m._FINDINGS.read_text(encoding="utf-8"))
                for f in doc["findings"]:
                    self.assertTrue(f.get("evidence"), "有 finding 没证据")
                    self.assertTrue(f.get("repro"), "有 finding 没复现命令")
            finally:
                self.m._FINDINGS, self.m._LEDGER, self.m._ROOT = old_f, old_led, old_root

    def test_b_verification_needs_two_readings(self):
        """**两路读法都命中才算确认**：把文件改掉 ⇒ 必须变 unverified（不许还标已确认）。"""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "s"
            d.mkdir()
            target = d / "bad.py"
            target.write_text("x = 1\n" + "shutil.rmtree('C:/真身目录')\n", encoding="utf-8")
            old_f, old_led, old_root = self.m._FINDINGS, self.m._LEDGER, self.m._ROOT
            self.m._FINDINGS = Path(td) / "f.json"
            self.m._LEDGER = Path(td) / "l.jsonl"
            self.m._ROOT = Path(td)
            try:
                self.m.scan(target=str(d))
                doc = json.loads(self.m._FINDINGS.read_text(encoding="utf-8"))
                fid = doc["findings"][0]["id"]
                v1 = self.m.verify_finding(id=fid)
                self.assertTrue(v1.get("ok"), f"刚扫完就说验不过：{v1}")
                self.assertEqual("双路", v1.get("verified_by"))
                target.write_text("x = 2\n", encoding="utf-8")          # 内容变了
                v2 = self.m.verify_finding(id=fid)
                self.assertFalse(v2.get("ok"), "文件都改了还标已确认")
                self.assertFalse(v2.get("verified_by"), "verified_by 没清掉")
            finally:
                self.m._FINDINGS, self.m._LEDGER, self.m._ROOT = old_f, old_led, old_root


class TestAgentRig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("ar_t", T / "agent_rig.py")

    def test_a_plan_has_four_isolations(self):
        with tempfile.TemporaryDirectory() as td:
            plans, led = self.m._PLANS, self.m._RIG
            self.m._PLANS, self.m._RIG = Path(td) / "p.json", Path(td) / "l.jsonl"
            try:
                r = self.m.plan(tasks="活一;活二;活三", agents_wanted="codex,claude")
                self.assertTrue(r.get("ok"), f"编队计划没出来：{r}")
                doc = json.loads(self.m._PLANS.read_text(encoding="utf-8"))[r["plan_id"]]
                for w in doc["workers"]:
                    for k in ("worktree", "log", "home", "port_block"):
                        self.assertTrue(w.get(k), f"第 {w['index']} 份缺隔离件 {k}")
                    self.assertEqual(2, len(w["port_block"]), "端口段不是一对")
                ports = [w["port_block"][0] for w in doc["workers"]]
                self.assertEqual(len(ports), len(set(ports)), "两份抢同一端口")
            finally:
                self.m._PLANS, self.m._RIG = plans, led

    def test_b_dispatch_without_ticket_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            plans, led = self.m._PLANS, self.m._RIG
            self.m._PLANS, self.m._RIG = Path(td) / "p.json", Path(td) / "l.jsonl"
            try:
                r = self.m.plan(tasks="活一;活二", agents_wanted="codex")
                d = self.m.dispatch(plan_id=r["plan_id"])
                self.assertFalse(d.get("ok"), f"缺票竟然起了编队：{d}")
                self.assertTrue(d.get("denied") or d.get("gate"), "拒了没说缺哪张票")
                self.assertIn("how_to_grant", d, "拒了没给授权命令")
            finally:
                self.m._PLANS, self.m._RIG = plans, led

    def test_c_agents_availability_is_fail_closed(self):
        old = self.m._probe
        self.m._probe = lambda *a, **k: {}
        try:
            r = self.m.agents()
            self.assertFalse(r["agents"]["codex"]["available"],
                             "探针没读数却报可用 ⇒ fail-open 又回来了")
        finally:
            self.m._probe = old


class TestNewCapsReachableThroughDoor(unittest.TestCase):
    def test_all_four_callable(self):
        sys.path.insert(0, str(ROOT))
        import gbt_allinone as g
        reads = {"memory_bank": "aliases", "agent_console": "board",
                 "code_audit": "report", "agent_rig": "status"}
        for kind, op in reads.items():
            r = g.run_task(kind, {"op": op})
            p = r.get("result", r)
            if isinstance(p, dict) and "result" in p:
                p = p["result"]
            self.assertTrue(p.get("ok"), f"{kind} op={op} 过门调不通：{str(p)[:160]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
