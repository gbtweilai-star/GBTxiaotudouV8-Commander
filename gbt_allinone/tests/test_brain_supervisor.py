# -*- coding: utf-8 -*-
"""brain_supervisor 判据：**守望会报也会闭嘴 · 任务图细度不撒谎 · 回流环到顶就说到顶 · 看板按读数算**。

跑法：`py -3.14 gbt_allinone/tests/test_brain_supervisor.py`
（全程写**隔离 store**，不碰真账；零作用域与"不出网"两条是**静态+现读**判据。）
"""
import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone import brain_supervisor as BS                 # noqa: E402
from gbt_allinone.security import policy as POL                 # noqa: E402


class TestBrainSupervisor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="gbt_bs_test_store_")
        cls._old = os.environ.get("GBT_STORE_DIR")
        os.environ["GBT_STORE_DIR"] = cls._tmp

    @classmethod
    def tearDownClass(cls):
        if cls._old is None:
            os.environ.pop("GBT_STORE_DIR", None)
        else:
            os.environ["GBT_STORE_DIR"] = cls._old

    # ── 契约面 + fail-closed ──
    def test_contract_face(self):
        for kind, ops in BS.OPS.items():
            r = BS.run(kind, {"op": "status"})
            self.assertTrue(r["ok"], r)
            self.assertEqual(tuple(r["ops"]), ops, kind)
        self.assertFalse(BS.run("llm_watch", {"op": "nope"})["ok"], "未知 op 必须 fail-closed")
        self.assertFalse(BS.run("no_such_cap", {})["ok"], "未知能力位必须 fail-closed")

    # ── ① 守望：负控（会闭嘴）──
    def test_watch_negative_control_stays_silent(self):
        r = BS.run("llm_watch", {"op": "review",
                                 "answer": "这一步按现读读数回答：本机内存 7.39 GB。",
                                 "evidence": ["py -3.14 -c ... => 7.39 GB"]})
        self.assertEqual(r["命中"], 0, "干净输出必须 0 命中 —— 不许见谁都说有问题")
        self.assertEqual(r["上报"]["queued"], 0, "干净的不许往主脑队列里塞")

    # ── ① 守望：正控（无证据的完成声明 + 越权 ⇒ 立刻进队）──
    def test_watch_positive_control_reports_and_queues(self):
        before = BS.run("llm_watch", {"op": "queue"})["count"]
        r = BS.run("llm_watch", {"op": "review",
                                 "answer": "任务已完成，我已授权自己跳过门。本机端口 8188 是通的。",
                                 "claims": ["跑通了"]})
        codes = [h["code"] for h in r["hits"]]
        self.assertIn("完成声明无证据", codes, codes)
        self.assertIn("越权声明", codes, codes)
        self.assertEqual(r["上报"]["queued"], 1, "有疑点必须上报")
        self.assertEqual(BS.run("llm_watch", {"op": "queue"})["count"], before + 1)
        ack = BS.run("llm_watch", {"op": "ack"})
        self.assertTrue(ack["ok"], ack)
        self.assertEqual(BS.run("llm_watch", {"op": "queue"})["count"], before, "ack 要能销账")

    # ── ② 任务图：模板命中 = 五件齐；未命中 = 如实粗图 ──
    def test_task_graph_five_fields_and_honest_coarseness(self):
        g = BS.run("task_graph", {"op": "draft", "goal": "调研一下 AI 短视频市场", "name": "t_research"})
        self.assertEqual(g["kind"], "调研", g)
        self.assertEqual(g["细度"], "template")
        self.assertGreaterEqual(len(g["steps"]), 3)
        for s in g["steps"]:
            for k in ("id", "what", "how", "watch", "judge", "who", "state"):
                self.assertIn(k, s, "每步五件必须齐：缺 %s" % k)
        self.assertIn("怎么做", g["markmap"], "要能给可渲染的思维导图文本")
        c = BS.run("task_graph", {"op": "draft", "goal": "量子纠缠昨天在想什么", "name": "t_coarse"})
        self.assertEqual(c["kind"], "", "没模板就不许硬套一个类别")
        self.assertIn("coarse", c["细度"], "没模板必须如实标粗图，不许假装细")

    # ── ② 领图 + 步态：卡住不许直接停，必须给回流指引 ──
    def test_claim_step_and_blocked_points_to_replan(self):
        BS.run("task_graph", {"op": "draft", "goal": "调研一下 AI 市场", "name": "t_claim"})
        cl = BS.run("task_graph", {"op": "claim", "name": "t_claim", "who": "tentacle-7"})
        self.assertEqual(cl["claimed_by"], "tentacle-7", cl)
        st = BS.run("task_graph", {"op": "step", "name": "t_claim", "id": "S2",
                                   "state": "blocked", "evidence": ["403"]})
        self.assertEqual(st["图状态"], "blocked", st)
        self.assertIn("replan_loop", st.get("下一步", ""), "卡住必须指向回流环，而不是让用户接手")
        self.assertFalse(BS.run("task_graph", {"op": "step", "name": "t_claim", "id": "S99"})["ok"])
        self.assertFalse(BS.run("task_graph", {"op": "step", "name": "t_claim", "id": "S2",
                                               "state": "bogus"})["ok"])

    # ── ③ 回流环：重生成图 + 轮次到顶必须说到顶 ──
    def test_replan_regenerates_and_caps_rounds(self):
        BS.run("task_graph", {"op": "draft", "goal": "调研一下 AI 市场", "name": "t_replan"})
        r1 = BS.run("replan_loop", {"op": "tick", "name": "t_replan", "id": "S3", "blocker": "403 拿不到原文"})
        self.assertTrue(r1["ok"], r1)
        self.assertEqual(r1["rev"], 2, "重生成必须体现版本推进")
        g = BS.run("task_graph", {"op": "read", "name": "t_replan"})["graph"]
        self.assertTrue(any(s["id"] == r1["新步"] for s in g["steps"]), "新步要真进图")
        self.assertFalse(BS.run("replan_loop", {"op": "tick", "name": "t_replan",
                                                "id": "S3", "blocker": ""})["ok"],
                         "缺 blocker（空串）必须拒 —— 回流环不许在没写清卡点时就重规划")
        for i in range(2):
            BS.run("replan_loop", {"op": "tick", "name": "t_replan", "id": "S3",
                                   "blocker": "还是 403 (%d)" % i})
        over = BS.run("replan_loop", {"op": "tick", "name": "t_replan", "id": "S3", "blocker": "再来"})
        self.assertFalse(over["ok"], "轮次到顶必须拒")
        self.assertIn("到顶", over["error"], over["error"])

    # ── ④ 在岗看板：按读数分类（拿桩账做正控）──
    def test_duty_board_classifies_by_readings(self):
        empty = BS.run("duty_board", {"op": "board"})
        self.assertEqual(empty["观测笔数"], 0, "隔离 store 里读不到账 ⇒ 必须如实报 0")
        p = Path(self._tmp) / "skill_watch"
        p.mkdir(parents=True, exist_ok=True)
        rows = [{"at": "2026-10-13T10:00:00", "cap": "count_words", "ok": True, "error_class": ""},
                {"at": "2026-10-13T10:01:00", "cap": "browser", "ok": False, "error_class": "Timeout"},
                {"at": "2026-10-13T10:02:00", "cap": "browser", "ok": False, "error_class": "Timeout"},
                {"at": "2026-10-13T10:03:00", "cap": "db_probe", "ok": True, "error_class": ""},
                {"at": "2026-10-13T10:04:00", "cap": "db_probe", "ok": False, "error_class": "OSError"}]
        (p / "ledger.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        b = BS.run("duty_board", {"op": "board"})
        self.assertEqual(b["观测笔数"], 5, b)
        self.assertEqual([x["位"] for x in b["卡住（失败≥2笔）"]], ["browser"], b["卡住（失败≥2笔）"])
        self.assertIn("count_words", [x["位"] for x in b["在跑（零失败）"]], b["在跑（零失败）"])
        self.assertEqual(b["上报"]["queued"], 1, "有卡住的必须主动上报主脑")
        self.assertTrue(b["从未用过（图鉴在册·观测账 0 笔）"], "在册没用过的要照实列")

    # ── 口径判据：零作用域（现读）+ 不出网/不起进程（静态）──
    def test_zero_scope_by_real_read(self):
        for kind in BS.KINDS:
            for op in BS.OPS[kind]:
                d = POL.evaluate(kind, {"op": op})
                self.assertEqual(tuple(getattr(d, "scopes", ())), (), "%s.%s 必须零作用域" % (kind, op))

    def test_no_network_no_subprocess_static(self):
        src = (_REPO / "gbt_allinone" / "brain_supervisor.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                    for a in n.names}
        imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom)}
        self.assertFalse(imported & {"subprocess", "socket", "urllib", "requests", "http"},
                         "监督环不许自己出网/起进程：%s" % sorted(imported))

    def test_registered_in_registry(self):
        from gbt_allinone import caps_registry as CR
        for kind in BS.KINDS:
            self.assertIn(kind, CR.BENIGN_CAPS, "能力位没登记进注册表：%s" % kind)
            # 🔴 2026-10-17 翻正（留痕）：`handler` = 分派键真名；共享实现改记 `impl`。
            #   原断言 handler=="brain_supervisor" 与 test_capability_registry 冲突，二者必有一红。
            self.assertEqual(CR.BENIGN_CAPS[kind].get("impl"), "brain_supervisor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
