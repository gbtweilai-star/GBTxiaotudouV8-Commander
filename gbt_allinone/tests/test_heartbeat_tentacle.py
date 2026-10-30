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

import json
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


class PolishRound2Test(unittest.TestCase):
    """九、2026-10-30 打磨二：值日失守 / 两套健康口径 / 非原子写。

    三条都是**先查证再改**：
      ① KEEPER 指向不存在的类 ⇒ 12 根 keeper 全 False、抽屉再没人报，而报告照绿
      ② health() 五维与 heartbeat() 十二根互不相识 ⇒ 问"系统好不好"得到两个答案
      ③ write_text 是截断再写 ⇒ 并发时可能读到半截 JSON，且静默变成"首跳"
    """

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="gbt_hb_p2_")
        self._orig_dir = HB._STATE_DIR
        self._orig_keeper = HB.KEEPER
        HB._STATE_DIR = Path(self._tmp)

    def tearDown(self) -> None:
        HB._STATE_DIR = self._orig_dir
        HB.KEEPER = self._orig_keeper
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_keeper_lost_is_loud_and_still_covered(self) -> None:
        HB.KEEPER = "这个类不存在"
        code, broken = HB._resolve_keeper()
        self.assertTrue(broken, "KEEPER 不在分类表里，必须被识别为配置损坏")
        self.assertIn(code, TX.CATEGORIES, "降级代值根必须是个真实分类，否则抽屉没人看")
        rep = HB.scan_all(mode="light", persist=False)
        lost = [s for s in rep["signals"] if s["code"] == "keeper_lost"]
        self.assertEqual(len(lost), 1, "keeper_lost 应报且只报一次，实际 %d 次" % len(lost))
        adv = BE.advise(rep)
        self.assertEqual(adv["verdict"], "red", "值日配置坏了必须判红")
        self.assertIn("keeper_lost", [x["id"] for x in adv["instructions"]])

    def test_state_written_atomically(self) -> None:
        HB.HeartbeatTentacle(HB.KEEPER).pulse(mode="light", persist=True)
        d = Path(self._tmp)
        leftovers = [p.name for p in d.iterdir() if p.name.endswith(HB._SWAP_SUFFIX)]
        self.assertEqual(leftovers, [], "原子写后不该留临时件：%s" % leftovers)
        st = HB.HeartbeatTentacle(HB.KEEPER).status()
        self.assertEqual(st.get("category"), HB.KEEPER, "状态读回来不完整：%s" % st)

    def test_swapping_file_is_exempt_from_hygiene(self) -> None:
        d = Path(self._tmp)
        swap = d / ("x.json" + HB._SWAP_SUFFIX)
        swap.write_text("{}", encoding="utf-8")
        h = HB.HeartbeatTentacle(HB.KEEPER)._hygiene(clean=True)
        self.assertFalse(any(HB._SWAP_SUFFIX in g for g in h["garbage"]),
                         "正在写的临时件被当垃圾了：%s" % h["garbage"])
        self.assertFalse(any(HB._SWAP_SUFFIX in f for f in h["foreign"]),
                         "正在写的临时件被当外来物了：%s" % h["foreign"])
        self.assertTrue(swap.exists(), "临时件被扫掉了 —— 会打断别的进程写盘")

    def test_health_carries_heartbeat_summary(self) -> None:
        HB.scan_all(mode="light", persist=True)      # 先落一次，health 才有东西可读
        h = BE.health()
        self.assertIn("heartbeat", h, "health() 必须带上心跳摘要，否则是两套口径")
        self.assertIn("scope_note", h, "分工说明必须写出来，不然没人知道该看哪套")
        hb = h["heartbeat"]
        self.assertTrue(hb.get("tentacles_total") or hb.get("never_scanned"),
                        "心跳摘要要么有读数要么明确说没扫过：%s" % hb)


class DeepCheckTest(unittest.TestCase):
    """十、2026-10-30 打磨三：分频深检 —— 不许"看着绿其实没测"。

    踩到的洞：自动链路永远 light，而「身」的器官探针是 full 档的 body_map
    ⇒ 七感官六动作在自动监控里**从来没跑过**，报告却 12/12 绿（probe.ok=None 不参与判定）。
    现在把「上次深检是什么时候」显式记账，从未/过期都要出指令，且能自动补齐。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="gbt_hb_deep_")
        self._orig = HB._STATE_DIR
        HB._STATE_DIR = Path(self._tmp)

    def tearDown(self) -> None:
        HB._STATE_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_light_only_is_reported_as_never_deep_checked(self) -> None:
        rep = HB.scan_all(mode="light", persist=True)
        self.assertFalse(rep["deep"]["ever"], "只有 light 却报 ever=True")
        ids = [x["id"] for x in BE.advise(rep)["instructions"]]
        self.assertIn("never_deep_checked", ids,
                      "从没深检过却不提示 —— 七感官等于没体检：%s" % ids)

    def test_full_marks_deep_and_clears_the_hint(self) -> None:
        HB.scan_all(mode="light", persist=True)
        rep = HB.scan_all(mode="full", persist=True)
        self.assertTrue(rep["deep"]["ever"], "跑过 full 却报 ever=False")
        self.assertIsNotNone(rep["deep"]["last_full_at"])
        self.assertFalse(rep["deep"]["stale"])
        ids = [x["id"] for x in BE.advise(rep)["instructions"]]
        self.assertNotIn("never_deep_checked", ids, "深检完还在提示从未深检")
        self.assertNotIn("deep_check_stale", ids, "刚深检完就说过期")

    def test_stale_deep_check_is_flagged(self) -> None:
        # 伪造一份"两天前深检过"的账
        old = "2026-10-28T00:00:00"
        (Path(self._tmp) / "latest.json").write_text(
            json.dumps({"at": old, "deep": {"last_full_at": old, "ever": True}},
                       ensure_ascii=False), encoding="utf-8")
        rep = HB.scan_all(mode="light", persist=True)
        self.assertTrue(rep["deep"]["stale"], "两天没深检却不判过期：%s" % rep["deep"])
        ids = [x["id"] for x in BE.advise(rep)["instructions"]]
        self.assertIn("deep_check_stale", ids)

    def test_act_auto_completes_deep_check(self) -> None:
        HB.scan_all(mode="light", persist=True)
        self.assertFalse(HB.latest()["deep"]["ever"])
        r = BE.act()
        ops = [x["op"] for x in r["executed"]]
        self.assertIn("heartbeat_full", ops, "深检缺失时 act 应自动补：%s" % ops)
        self.assertTrue(HB.latest()["deep"]["ever"], "act 补齐后 deep 仍未记账")


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

    def test_scan_without_clean_also_converges(self) -> None:
        """打磨四：环形保留必须**无条件**收敛。

        踩过：prune 只在 clean=True 时跑，而定时链路（monitor-loop）从不传 clean
        ⇒ 扫描件无限增长（实测连跑 6 次 23→28 份）。按 5 分钟一拍是 288 份/天。
        语义要分清：**环形保留是设计（缓冲区上限），不是"清理别人的东西"**。
        """
        orig = HB.KEEP_SCANS
        HB.KEEP_SCANS = 3            # 缩小预算，免得跑几十秒
        self.addCleanup(setattr, HB, "KEEP_SCANS", orig)
        for _ in range(6):
            HB.scan_all(mode="light", persist=True)      # 注意：**不传 clean**
        left = len(list(Path(self._tmp).glob("scan-*.json")))
        self.assertLessEqual(left, HB.KEEP_SCANS,
                             "不带 clean 就连着涨：%d 份 > KEEP=%d" % (left, HB.KEEP_SCANS))


class ModuleProbeDepthTest(unittest.TestCase):
    """十一、2026-10-30 打磨四：模块探针 `find_spec` 只证在位，不证能起来。

    缺 DLL / 缺可选依赖时 find_spec 仍 True，import 却会炸 —— 那是"看着绿其实没测"。
    实测本机 18 个目标目前 0 假绿，但判据没牙就不是判据：full 档追加真 import。
    """

    def test_full_mode_really_imports(self) -> None:
        st = HB.HeartbeatTentacle("知").pulse(mode="full", persist=False)
        d = st["checks"]["probe"]["detail"]
        self.assertTrue(d.get("import_probed"), "full 档却没做真 import：%s" % d)
        self.assertGreaterEqual(d.get("imported", 0), 1, "一个模块都没导进来：%s" % d)
        self.assertEqual(d.get("import_failed"), [], "有模块 import 失败：%s" % d)

    def test_light_mode_does_not_import(self) -> None:
        """浅检不能做真 import —— 那是每拍要付的代价（实测 ~290ms）。"""
        st = HB.HeartbeatTentacle("知").pulse(mode="light", persist=False)
        d = st["checks"]["probe"]["detail"]
        self.assertFalse(d.get("import_probed"), "light 档不该做真 import：%s" % d)

    def test_missing_module_still_red(self) -> None:
        """在位检查不能被深检取代：模块不存在时，两档都必须红。"""
        for mode in ("light", "full"):
            st = HB.HeartbeatTentacle("知").pulse(mode=mode, persist=False)
            self.assertIs(st["checks"]["probe"]["ok"], True, "正常模块被误判：%s" % st)
        # 反向：临时把目标改成不存在的模块 → 必须红
        orig = dict(HB.PROBES["知"])
        HB.PROBES["知"] = {"kind": "modules", "tier": "light",
                           "targets": ["gbt_allinone.根本不存在"], "note": "负控"}
        self.addCleanup(HB.PROBES.__setitem__, "知", orig)
        for mode in ("light", "full"):
            st = HB.HeartbeatTentacle("知").pulse(mode=mode, persist=False)
            self.assertIs(st["checks"]["probe"]["ok"], False,
                          "%s 档对不存在的模块没报红" % mode)


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
