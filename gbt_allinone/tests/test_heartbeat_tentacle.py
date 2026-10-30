# -*- coding: utf-8 -*-
"""十二根分类心跳触手 · 护栏测试（2026-10-30 立）。

主人令：「把所有原生能力以及操控部位分类好必须严格分类好，然后每一个分类部署一根
心跳触手来对分类内的一切进行定点自检和状态返回给大脑执行层分析，再返回执行指令」
追加令：「分类触手在自检的时候要懂得清理垃圾和整理自身文件整洁不被其他东西混入」

## 这些用例守的是什么（每条都对应一个能真翻车的点）

1. **分类必须严格** —— 349 条不重不漏；一旦有人往注册表加能力却忘了归类，
   `audit()` 必须红。这是"12 根触手看的是全集"的前提，破了后面全是假绿。
2. **每根六层齐全** —— 缺一层就等于自检瞎一块，而状态里看不出来（最坏的那种绿）。
3. **ok 必须是布尔** —— 实测踩过：`_check_registry` 里 `and members` 返回**列表本身**，
   `ok` 变成 29 元素的清单，判断上碰巧还对，但读数被污染。这条是回归护栏。
4. **负控必须真红** —— 只测绿等于没测。喂一份故障报告，`advise()` 必须出 red + P0。
5. **外来物只报不删** —— 卫生层的硬纪律。删了别人的东西比不清理更坏。
6. **dry-run 真的不动手** —— 默认路径必须零写入，否则"默认安全"就是一句口号。

隔离：全部在临时目录里跑，**不碰生产的 `state/heartbeat/`**。
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from gbt_allinone import cap_taxonomy as TX
from gbt_allinone import heartbeat_tentacle as HB
from gbt_allinone import brain_exec as BE


class TaxonomyStrictnessTest(unittest.TestCase):
    """一、分类必须严格：不重、不漏、总数对齐真源。"""

    def test_covers_source_exactly(self) -> None:
        a = TX.audit()
        self.assertTrue(a["ok"], "分类自校验没过：%s" % a)
        self.assertEqual(a["source_total"], a["classified_total"],
                         "真源 %d 条，已分类 %s 条 —— 有漏网"
                         % (a["source_total"], a["classified_total"]))
        self.assertEqual(a["unclassified"], [], "有未归类的能力位：%s" % a["unclassified"])
        self.assertEqual(a["duplicated"], [], "有被两个大类同时认领的：%s" % a["duplicated"])
        self.assertEqual(a["orphan_domains"], [], "有没被任何大类认领的 domain：%s"
                         % a["orphan_domains"])

    def test_every_category_non_empty(self) -> None:
        buckets = TX.all_members()
        self.assertEqual(len(buckets), 12)
        for code, items in buckets.items():
            self.assertTrue(items, "大类「%s」一条成员都没有 —— 那就是根空壳触手" % code)

    def test_action_domains_all_mapped(self) -> None:
        a = TX.audit()
        self.assertEqual(a["unmapped_action_domains"], [],
                         "触手动作域没归到大类：%s" % a["unmapped_action_domains"])
        self.assertEqual(a["action_domains"], 13, "触手动作域应为 13 个")
        self.assertEqual(a["body_senses"], 7, "七根感官")
        self.assertEqual(a["body_actuators"], 6, "六根动作")


class TentacleLayersTest(unittest.TestCase):
    """二、每根六层齐全；ok 必须是布尔（回归 `and members` 那个坑）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="gbt_hb_test_")
        self._orig = HB._STATE_DIR
        HB._STATE_DIR = Path(self._tmp)

    def tearDown(self) -> None:
        HB._STATE_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_six_layers_present_and_boolean(self) -> None:
        want = {"registry", "dispatch", "policy", "probe", "hygiene"}
        for code in TX.CATEGORIES:
            st = HB.HeartbeatTentacle(code).pulse(mode="light", persist=False)
            self.assertEqual(set(st["checks"]), want, "「%s」六层不全：%s" % (code, set(st["checks"])))
            for layer, chk in st["checks"].items():
                self.assertIsInstance(chk.get("ok"), (bool, type(None)),
                                      "「%s」的 %s.ok 不是布尔而是 %r（读数会被污染）"
                                      % (code, layer, chk.get("ok")))
            self.assertIsInstance(st["ok"], bool)
            self.assertGreater(st["members_total"], 0)

    def test_registry_layer_says_true_not_a_list(self) -> None:
        """回归：`ok = ... and members` 会让 ok 变成成员清单。"""
        st = HB.HeartbeatTentacle("身").pulse(mode="light", persist=False)
        self.assertIs(st["checks"]["registry"]["ok"], True,
                      "registry.ok 必须是 True，实际是 %r" % (st["checks"]["registry"]["ok"],))


class AdviseNegativeControlTest(unittest.TestCase):
    """三、负控：故障报告必须出 red + P0，而且排序要先修。"""

    FAKE = {
        "at": "2026-10-30T06:00:00", "mode": "light", "score": 75.0,
        "tentacles_total": 12, "tentacles_ok": 9, "tentacles_red": 3,
        "taxonomy": {"ok": False, "unclassified": ["bogus"], "duplicated": [],
                     "orphan_domains": ["weird"], "unmapped_action_domains": ["新域"],
                     "source_total": 350, "classified_total": 349},
        "signals": [
            {"level": "P0", "code": "dispatch_gap", "category": "守",
             "tentacle": "heartbeat-守", "msg": "有 2 条 handler 不在分派表内"},
            {"level": "P0", "code": "policy_break", "category": "调",
             "tentacle": "heartbeat-调", "msg": "3 条过策略门抛异常"},
            {"level": "P1", "code": "probe_dead", "category": "感",
             "tentacle": "heartbeat-感", "msg": "eye_ready=False"},
            {"level": "INFO", "code": "probe_skipped", "category": "身",
             "tentacle": "heartbeat-身", "msg": "full 档跳过"},
        ],
    }

    def test_verdict_red_and_p0_first(self) -> None:
        adv = BE.advise(self.FAKE)
        self.assertEqual(adv["verdict"], "red", "故障报告必须判红，实际 %s" % adv["verdict"])
        self.assertFalse(adv["ok"])
        self.assertGreaterEqual(adv["counts"]["P0"], 3, "P0 至少 3 条（分类+分派+策略）")
        prios = [x["priority"] for x in adv["instructions"]]
        self.assertEqual(prios, sorted(prios, key=lambda p: {"P0": 0, "P1": 1, "P2": 2}[p]),
                         "指令必须按 P0→P1→P2 排序：%s" % prios)
        self.assertEqual(prios[0], "P0", "第一条必须是最该先修的")

    def test_taxonomy_broken_voids_everything(self) -> None:
        adv = BE.advise(self.FAKE)
        ids = [x["id"] for x in adv["instructions"]]
        self.assertIn("taxonomy_broken", ids, "分类表坏掉时必须先报这一条")


class HygieneDisciplineTest(unittest.TestCase):
    """四、卫生层：外来物只报不删；dry-run 零写入；--clean 只清自己的垃圾。"""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="gbt_hb_hyg_")
        self._orig = HB._STATE_DIR
        HB._STATE_DIR = Path(self._tmp)
        d = Path(self._tmp)
        (d / "junk.tmp").write_text("x", encoding="utf-8")
        (d / "old.pyc").write_text("x", encoding="utf-8")
        (d / "别人的东西.txt").write_text("不是我们的", encoding="utf-8")
        (d / "random_dir").mkdir()
        (d / "random_dir" / "a.bin").write_text("x", encoding="utf-8")

    def tearDown(self) -> None:
        HB._STATE_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_dry_run_reports_but_deletes_nothing(self) -> None:
        d = Path(self._tmp)
        before = sorted(p.name for p in d.iterdir())
        HB.HeartbeatTentacle("身").pulse(mode="light", persist=False, clean=False)
        after = sorted(p.name for p in d.iterdir())
        self.assertEqual(before, after, "dry-run 竟然动了文件：%s -> %s" % (before, after))

    def test_clean_removes_garbage_but_keeps_foreign(self) -> None:
        d = Path(self._tmp)
        h = HB.HeartbeatTentacle("身")._hygiene(clean=True)
        self.assertFalse((d / "junk.tmp").exists(), "垃圾没清掉：junk.tmp")
        self.assertFalse((d / "old.pyc").exists(), "垃圾没清掉：old.pyc")
        self.assertTrue((d / "别人的东西.txt").exists(),
                        "外来文件被删了 —— 这是最坏的错，别人的东西不该由触手处置")
        self.assertTrue((d / "random_dir").exists(), "外来目录被删了")
        self.assertIn("别人的东西.txt", h["foreign"], "外来物必须被识别出来")
        self.assertTrue(h["ok"] is False, "有外来混入时卫生层必须报红（值日那根）")

    def test_non_keeper_does_not_red_on_shared_foreign(self) -> None:
        """非值日的触手不因共用抽屉里有外来物而变红（否则一份东西 12 根全红）。"""
        h = HB.HeartbeatTentacle("感")._hygiene(clean=False)
        self.assertIs(h["keeper"], False)
        self.assertTrue(h["ok"], "非值日那根不该替共用抽屉背红：%s" % h)


class ActClosedLoopTest(unittest.TestCase):
    """五、act()：dry_run 不动手；表外指令一律跳过并写明原因。"""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="gbt_hb_act_")
        self._orig = HB._STATE_DIR
        HB._STATE_DIR = Path(self._tmp)
        (Path(self._tmp) / "junk.tmp").write_text("x", encoding="utf-8")

    def tearDown(self) -> None:
        HB._STATE_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_dry_run_executes_nothing(self) -> None:
        r = BE.act(dry_run=True)
        self.assertEqual(r["executed"], [], "dry_run 竟然执行了动作：%s" % r["executed"])
        self.assertTrue((Path(self._tmp) / "junk.tmp").exists(), "dry_run 竟然删了文件")

    def test_out_of_table_is_skipped_with_reason(self) -> None:
        r = BE.act(dry_run=True)
        for s in r["skipped"]:
            self.assertTrue(s.get("why"), "跳过必须写明原因，不许静默：%s" % s)


class PolishRegressionTest(unittest.TestCase):
    """六、2026-10-30 打磨轮修掉的四件事，各留一条护栏。

    都是**实测踩到**的，不是假想：
      ① 落盘失败被静默吞掉 ⇒ 报告照绿（最坏的假绿）
      ② INFO 被塞成 P2 指令且不带 signal_code ⇒ 每跳一条无依据噪音
      ③ 全局根因（磁盘写不进）被 12 根各报一遍 ⇒ 一个病灶念成 12 个
      ④ 值日根靠 dict 插入顺序 ⇒ 谁重排分类表，值日根就悄悄换人
    """

    def setUp(self) -> None:
        self._orig = HB._STATE_DIR

    def tearDown(self) -> None:
        HB._STATE_DIR = self._orig

    def _unwritable(self) -> None:
        """把抽屉指向一个**文件**（不是目录），mkdir 必失败 ⇒ 稳定的写失败场景。"""
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".blocker")
        tf.close()
        self.addCleanup(lambda: os.path.exists(tf.name) and os.unlink(tf.name))
        HB._STATE_DIR = Path(tf.name)

    def test_persist_failure_goes_red_not_green(self) -> None:
        self._unwritable()
        st = HB.HeartbeatTentacle(HB.KEEPER).pulse(mode="light", persist=True)
        self.assertFalse(st.get("persisted"), "写不进盘却报 persisted=True")
        self.assertIs(st.get("ok"), False, "写不进盘还报绿 —— 这就是假绿")
        codes = [s["code"] for s in st.get("signals") or []]
        self.assertIn("persist_failed", codes)

    def test_every_instruction_is_traceable(self) -> None:
        adv = BE.advise(HB.scan_all(mode="light", persist=False))
        bad = [x for x in adv["instructions"]
               if (x.get("evidence") or {}).get("signal_code") is None]
        self.assertEqual(bad, [], "指令必须能追溯到 signal_code，否则就是噪音：%s" % bad)
        skipped = [x for x in adv["instructions"]
                   if (x.get("evidence") or {}).get("signal_code") == "probe_skipped"]
        self.assertEqual(skipped, [], "INFO(probe_skipped) 不该进 instructions")
        self.assertIsInstance(adv.get("notes"), list, "INFO 应落到 notes")

    def test_systemic_root_cause_single_ticket(self) -> None:
        self._unwritable()
        adv = BE.advise(HB.scan_all(mode="light", persist=True))
        p0 = [x for x in adv["instructions"] if x["priority"] == "P0"]
        self.assertIn("persist_failed", [x["id"] for x in p0],
                      "落盘失败必须出 P0：%s" % [x["id"] for x in p0])
        persist = [x for x in p0 if x["id"] == "persist_failed"]
        self.assertEqual(len(persist), 1, "全局根因只许开一张单，实际 %d 张" % len(persist))
        aff = persist[0].get("affected") or []
        self.assertEqual(len(aff), len(set(aff)), "affected 里有重复分类：%s" % aff)
        self.assertLessEqual(len(aff), 12, "affected 不该超过 12 个分类：%s" % aff)

    def test_keeper_is_a_constant_not_dict_order(self) -> None:
        self.assertEqual(HB.KEEPER, "身")
        self.assertIn(HB.KEEPER, TX.CATEGORIES,
                      "KEEPER=%r 不在分类表里，值日就没人值了" % HB.KEEPER)
        self.assertTrue(HB.HeartbeatTentacle(HB.KEEPER)._hygiene(clean=False)["keeper"])
        others = [c for c in TX.CATEGORIES if c != HB.KEEPER]
        self.assertFalse(HB.HeartbeatTentacle(others[0])._hygiene(clean=False)["keeper"])


class ScanRetentionTest(unittest.TestCase):
    """七、扫描件环形保留必须是**真不变量**（≤ KEEP_SCANS），不是"大概"。

    踩过：卫生层在"写这一份之前"跑，清完再写稳定多 1 份（实测 21 > 20）。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="gbt_hb_ret_")
        self._orig = HB._STATE_DIR
        HB._STATE_DIR = Path(self._tmp)

    def tearDown(self) -> None:
        HB._STATE_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_prune_keeps_at_most_keep_scans(self) -> None:
        d = Path(self._tmp)
        total = HB.KEEP_SCANS + 7
        for i in range(total):
            (d / ("scan-x%03d.json" % i)).write_text("{}", encoding="utf-8")
        removed = HB._prune_scans(HB.KEEP_SCANS)
        left = len(list(d.glob("scan-*.json")))
        self.assertEqual(removed, 7, "应删 7 份，实删 %d" % removed)
        self.assertLessEqual(left, HB.KEEP_SCANS, "保留 %d 份 > KEEP=%d" % (left, HB.KEEP_SCANS))

    def test_clean_scan_ends_within_budget(self) -> None:
        for _ in range(2):
            HB.scan_all(mode="light", persist=True, clean=True)
        left = len(list(Path(self._tmp).glob("scan-*.json")))
        self.assertLessEqual(left, HB.KEEP_SCANS,
                             "clean 跑完仍有 %d 份 > KEEP=%d" % (left, HB.KEEP_SCANS))


class CliJsonPurityTest(unittest.TestCase):
    """八、CLI 的 stdout 必须是**纯 JSON**。

    踩过：默认模式把 JSON 和"== 执行指令 =="都打到 stdout ⇒ 下游 json.load 报
    Extra data。机器读不了，这套东西就白做。
    """

    def test_stdout_is_pure_json(self) -> None:
        import json as _json
        import subprocess
        import sys as _sys

        root = Path(__file__).resolve().parents[2]
        r = subprocess.run([_sys.executable, "-X", "utf8", "-m", "gbt_allinone", "heartbeat",
                            "--act", "--dry"],
                           cwd=str(root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        self.assertEqual(r.returncode, 0, "exit=%s stderr=%s" % (r.returncode, r.stderr[-400:]))
        try:
            d = _json.loads(r.stdout)
        except Exception as exc:  # noqa: BLE001
            self.fail("stdout 不是纯 JSON（%s）：%r" % (type(exc).__name__, r.stdout[:300]))
        self.assertIn("dry_run", d)
        self.assertIn("skipped", d)


if __name__ == "__main__":
    unittest.main()
