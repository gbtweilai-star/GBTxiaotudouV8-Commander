# -*- coding: utf-8 -*-
"""沙盘（dd_visualizer）· 万能插只读视图的契约测试（R-H99d）。

锁三件事：
  ① `/api/data` 里必须带 `plug` 快照，且**声明自己是只读**（readonly=True）。
  ② 工作流快照带得动画图需要的结构：name / node_count / levels / latest（节点状态）。
  ③ 沙盘**没有任何写入口**：Handler 没有 do_POST，页面只 fetch 只读接口 —— 这是"导演只看得见、
     不许改剧本"的机械版（不靠口号）。
"""
from __future__ import annotations

import json
import socketserver
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import dd_visualizer as DD  # noqa: E402


class DdVisualizerPlugTests(unittest.TestCase):
    def test_collect_carries_readonly_plug_snapshot(self):
        payload = DD.collect(ROOT)
        self.assertIn("plug", payload, "沙盘数据里没有万能插快照")
        plug = payload["plug"]
        self.assertIs(plug.get("readonly"), True, "万能插视图必须自报只读")
        self.assertIn("workflows", plug)
        self.assertIn("runs", plug)
        if not plug.get("ok"):
            # 取不到就如实报错，不许沉默、不许编数据
            self.assertTrue(str(plug.get("error") or "").strip(), "取不到数据却没给原因")
            return
        for wf in plug["workflows"]:
            self.assertTrue(wf.get("name"))
            self.assertEqual(wf["node_count"], len(wf.get("nodes") or []))
            self.assertIsInstance(wf.get("levels"), list)
            flat = [i for lv in wf["levels"] for i in lv]
            self.assertEqual(sorted(flat), sorted(n["id"] for n in wf["nodes"]))
            self.assertIsInstance(wf.get("latest"), dict)

    def test_levels_is_topological(self):
        nodes = [{"id": "a", "kind": "health", "depends_on": []},
                 {"id": "b", "kind": "health", "depends_on": ["a"]},
                 {"id": "c", "kind": "health", "depends_on": ["a"]},
                 {"id": "d", "kind": "health", "depends_on": ["b", "c"]}]
        levels = DD._levels(nodes)
        self.assertEqual(levels[0], ["a"])
        self.assertEqual(sorted(levels[1]), ["b", "c"])
        self.assertEqual(levels[2], ["d"])
        # 有环也不许死循环（如实收口到最后一层）
        cyc = [{"id": "x", "depends_on": ["y"]}, {"id": "y", "depends_on": ["x"]}]
        self.assertEqual(len([i for lv in DD._levels(cyc) for i in lv]), 2)

    def test_run_rows_are_recent_three_and_honest_when_empty(self):
        """R-H103：运行行 = 最近 3 次（多了不给），一条都没有就**空着**让人看清"没跑过"。

        🔴 2026-09-22 第 36 轮修（错报治理）：这条原来**不自己造前置状态**，
        直接断言 `plug["workflows"]` 非空，还要求"有运行记录的"和"没运行记录的"各至少一个。
        在**隔离空 store** 里跑（这正是跑测试的正确姿势）盘上一条工作流都没有 ⇒ 当场红，
        但红的原因**不是产品坏了**：实测把两条工作流定义好、跑掉其中一条之后，
        沙盘立刻给出 `workflows=2 / with_runs=1 / without=1`（读数全对）。
        ⇒ 判据必须**自己把那个状态造出来**（第 56 条：不许赌环境）。
        并且"两种都要有"只能在**自己造的两条**上判 —— 拿盘上恰好存在的其它工作流凑数，
        会让这条判据随环境飘（今天绿明天红，重新变成错报源）。
        """
        import gbt_allinone as gbt
        tag = __import__("uuid").uuid4().hex[:6]
        has_runs, no_runs = "dd-has-runs-" + tag, "dd-no-runs-" + tag
        nodes = [{"id": "a", "kind": "health", "params": {}}]   # 只读节点，不过门
        self.assertEqual(gbt.run_task("wf_define", {"name": has_runs, "nodes": nodes})
                         .get("status"), "ok")
        self.assertEqual(gbt.run_task("wf_define", {"name": no_runs, "nodes": nodes})
                         .get("status"), "ok")
        self.assertEqual(gbt.run_task("wf_run", {"name": has_runs}).get("status"), "ok")

        plug = DD.plug_snapshot(limit=200)
        self.assertTrue(plug["ok"], plug)
        self.assertTrue(plug["workflows"], "沙盘应能列出工作流")
        by_name = {w["name"]: w for w in plug["workflows"]}
        self.assertIn(has_runs, by_name, "刚定义的工作流没被列出来")
        self.assertIn(no_runs, by_name, "刚定义的工作流没被列出来")
        for wf in plug["workflows"]:
            recent = wf.get("recent")
            self.assertIsInstance(recent, list, f"{wf['name']} 缺 recent")
            self.assertLessEqual(len(recent), 3, f"{wf['name']} 运行行超过 3 条")
            for r in recent:
                self.assertTrue(str(r.get("status") or "").strip(), "运行行必须带状态")
        # **在自造的两条上判**"有记录 / 没记录"（不许拿盘上别的凑数）
        self.assertTrue(by_name[has_runs]["recent"], "跑过的工作流必须挂上运行行")
        self.assertFalse(by_name[no_runs]["recent"],
                         "没跑过的工作流 recent 必须为空（不许编）")

    def test_dig_panel_reads_ledger_and_never_triggers_a_scan(self):
        """R-H104：挖漏洞面板必须**只读账本**，且轮询里绝不触发真扫描。

        为什么这条必须是硬约束：`cross_scan` 一次 ~58 秒，看板 5 秒一轮 ⇒
        一旦面板"顺手扫一下"，沙盘立刻变成自杀式负载。所以这里直接查源码：
        挖漏洞这条路径里**不许出现** `_api_read(` / `run_task(`。
        """
        import inspect
        src = inspect.getsource(DD.dig_snapshot)
        self.assertNotIn("_api_read(", src, "挖漏洞路径不许走能力调用（那会触发真扫描）")
        self.assertNotIn("run_task(", src, "挖漏洞路径不许走 run_task")

        dig = DD.dig_snapshot(ROOT)
        self.assertIs(dig["readonly"], True)
        self.assertTrue(dig["ok"], dig)
        self.assertTrue(dig["scanners"], "扫描器清单不许是空的")
        for row in dig["scanners"]:
            self.assertTrue(row["kind"] and row["label"])
            self.assertIsInstance(row["ever_ran"], bool)
            if row["ever_ran"]:
                self.assertTrue(str(row["at"]).strip(), f"{row['kind']} 有读数却没时间戳")
        self.assertGreater(dig["audit_bytes_read"], 0, "应该真读了账本尾部")
        self.assertLessEqual(dig["audit_bytes_read"], dig["tail_kb"] * 1024 + 8)
        self.assertIsNotNone(dig["pits"].get("count"), f"坑册读不到：{dig['pits']}")
        self.assertEqual(len(dig["how"]), 4, "挖法四步必须齐全（这就是'你是怎么挖的'）")

    def test_dig_panel_reports_missing_ledger_not_invented(self):
        with tempfile.TemporaryDirectory(prefix="gbt_dig_") as tmp:
            dig = DD.dig_snapshot(Path(tmp))
            self.assertIs(dig["ok"], False)
            self.assertIn("审计账本", dig["error"])
            self.assertTrue(all(not r["ever_ran"] for r in dig["scanners"]),
                            "账本不在 ⇒ 所有扫描器都必须是'从未跑过'，不许编读数")

    def test_page_has_dig_panel(self):
        page = DD._PAGE
        for needle in ('id="digpanel"', 'id="dig"', "drawDig", "挖法：", "不会</strong>替你跑扫描"):
            self.assertIn(needle, page, f"页面缺少挖漏洞钩子：{needle}")
        self.assertNotIn("POST", page)

    def test_ghost_ring_shows_real_traces_and_has_no_center(self):
        """R-H106：幽灵信号环 —— 信号必须是**账本里真实发生过的**，且**没有中心节点**。"""
        import inspect
        src = inspect.getsource(DD.ring_snapshot)
        self.assertNotIn("_api_read(", src, "信号环不许走能力调用（不许触发任何动作）")
        self.assertNotIn("run_task(", src, "信号环不许走 run_task")

        ring = DD.ring_snapshot(ROOT)
        self.assertIs(ring["readonly"], True)
        self.assertIsNone(ring["center"], "环里不许有中心节点（判断住在接线里）")
        self.assertEqual(len(ring["zones"]), 6, "六区必须齐")
        self.assertEqual(len(ring["law"]), 3, "三条排布规则必须齐")
        self.assertGreater(ring["audit_bytes_read"], 0)
        self.assertLessEqual(len(ring["signals"]), 12, "痕迹只留最近一小把，不驻留、不放大")
        for s in ring["signals"]:
            self.assertIn(s["event"], DD.SIGNAL_EVENTS, "只许记真事件")
            self.assertTrue(str(s["at"]).strip(), "每条痕迹必须带时间")
            self.assertIn("→", s["trace"], "痕迹形状：origin → event")

    def test_ghost_ring_reports_missing_ledger(self):
        with tempfile.TemporaryDirectory(prefix="gbt_ring_") as tmp:
            ring = DD.ring_snapshot(Path(tmp))
            self.assertIs(ring["ok"], False)
            self.assertIn("审计账本", ring["error"])
            self.assertEqual(ring["signals"], [])

    def test_page_has_ring_panel(self):
        page = DD._PAGE
        for needle in ('id="ringpanel"', 'id="ring"', "drawRing", "无中心", "一闪而逝"):
            self.assertIn(needle, page, f"页面缺少信号环钩子：{needle}")

    def test_page_is_read_only_and_has_plug_panel(self):
        page = DD._PAGE
        self.assertIn('id="plug"', page, "页面里没有万能插面板")
        self.assertIn("drawPlug", page)
        self.assertIn("fetch('/api/data')", page)
        self.assertNotIn("POST", page, "只读看板不许出现 POST")
        self.assertFalse(hasattr(DD.Handler, "do_POST"),
                         "Handler 不许有写入口（只呈现，不执行）")

    def test_toolchain_manifest_is_honest_and_readonly(self):
        """工具链清单（R-H99e）：单一来源 + **未核实就标未核实** + 只读。"""
        tc = DD.load_toolchain(ROOT)
        self.assertTrue(tc["ok"], tc)
        self.assertIs(tc["readonly"], True)
        # 沙箱没有出站网络 ⇒ 清单**没有被核实**，视图必须如实这么说，
        # 不许把"口述清单"画成"已核实可用战力"（同"空编不点成兵力"）。
        self.assertIs(tc["verified"], False)
        self.assertTrue(tc["verified_note"].strip(), "未核实却没说清楚为什么")
        self.assertEqual(set(tc["groups"]), {"generation", "drama", "publishing"})
        for group, items in tc["groups"].items():
            self.assertTrue(items, f"{group} 是空的")
            for it in items:
                self.assertTrue(it.get("name"))
                self.assertEqual(it.get("provenance"), "owner-claim-20260919")
                self.assertIs(it.get("verified"), False)
        self.assertEqual(tc["total"], sum(tc["counts"].values()))
        self.assertTrue(tc["pending_verification"], "口述里出现过、没出处的项必须单列出来")

    def test_toolchain_missing_manifest_is_reported_not_invented(self):
        with tempfile.TemporaryDirectory(prefix="gbt_tc_") as tmp:
            tc = DD.load_toolchain(Path(tmp))
            self.assertFalse(tc["ok"])
            self.assertTrue(tc["error"].strip(), "清单不在就必须报原因，不许自己编一份")
            self.assertEqual(tc["groups"], {})

    def test_toolchain_carries_layered_dag_from_manifest(self):
        """R-H101：分层 DAG 的**层与边必须来自清单**（不许代码里另编一套），且标未实测。"""
        tc = DD.load_toolchain(ROOT)
        self.assertTrue(tc["ok"], tc)
        self.assertEqual(tc["layers"], [["generation"], ["drama"], ["publishing"]])
        self.assertEqual(sorted(tc["edges"]),
                         [["drama", "publishing"], ["generation", "drama"],
                          ["generation", "publishing"]])
        # 流向是口述、没实测 ⇒ 必须自报未实测，且要带说明
        self.assertIs(tc["flow_verified"], False)
        self.assertTrue(tc["flow_note"].strip(), "未实测的流向必须带说明")
        for a, b in tc["edges"]:
            self.assertIn(a, tc["groups"], f"边指向不存在的组：{a}")
            self.assertIn(b, tc["groups"], f"边指向不存在的组：{b}")

    def test_api_read_is_the_single_reader_and_reports_honestly(self):
        """R-H101：沙盘取数只有一条路（_api_read），形状固定，取不到只报原因。"""
        got = DD._api_read("wf_status", {"limit": 1})
        self.assertEqual(set(got), {"ok", "data", "error", "source"})
        self.assertIs(got["ok"], True)
        self.assertEqual(got["source"], "wf_status")
        bad = DD._api_read("no_such_capability_zzz", {})
        self.assertIs(bad["ok"], False)
        self.assertTrue(str(bad["error"]).strip(), "取不到数据必须给原因，不许沉默")

    def test_page_has_toolchain_hooks(self):
        page = DD._PAGE
        for needle in ('id="toolpanel"', "drawToolchain", "rebuildToolchain",
                       "chainTip", 'id="tip"', "CHAIN_RING"):
            self.assertIn(needle, page, f"页面缺少工具链钩子：{needle}")
        self.assertNotIn("POST", page)

    def test_color_means_state_and_every_scheme_has_a_legend(self):
        """R-H102：颜色=状态这条口径必须**看得见**，且两套语义各带图例，不许混。

        工作流那套色 = 最近一次**运行状态**（ok/denied/error/skipped），
        工具链那套色 = **核实状态**（未核实/已核实）。
        """
        page = DD._PAGE
        # 两套图例各自存在
        self.assertIn("节点色=最近一次运行", page)
        self.assertIn("卡片色=核实状态", page)
        # 未跑不许着色（诚实口径），并且要在图例里显式写出来
        self.assertIn("未跑（不着色）", page)
        self.assertIn("未核实（口述）", page)
        # CSS 里两套类都在（工作流状态色 + 核实状态色）
        for css in (".nd.ok{", ".nd.denied{", ".nd.error{", ".nd.skipped{", ".nd.unverified{"):
            self.assertIn(css, page, f"缺 CSS 类：{css}")
        # 工具链 chip 按核实状态上色（verifed=false ⇒ unverified 类）
        self.assertIn("nd unverified", page)

    def test_server_serves_data_and_page(self):
        with tempfile.TemporaryDirectory(prefix="gbt_ddv_") as tmp:
            root = Path(tmp)
            squad = root / ".cluster" / "dd_squad"
            squad.mkdir(parents=True)
            (squad / "board.json").write_text(json.dumps(
                [{"task_id": "DD-01", "title": "t", "status": "进行中"}], ensure_ascii=False),
                encoding="utf-8")
            (squad / "roster.json").write_text(json.dumps(
                [{"name": "甲", "backed_by": "x"}, {"name": "乙", "backed_by": None}],
                ensure_ascii=False), encoding="utf-8")

            DD.Handler.root = root
            srv = socketserver.TCPServer(("127.0.0.1", 0), DD.Handler)
            port = srv.server_address[1]
            th = threading.Thread(target=srv.serve_forever, daemon=True)
            th.start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/data", timeout=10) as r:
                    self.assertEqual(r.status, 200)
                    data = json.loads(r.read().decode("utf-8"))
                self.assertIn("plug", data)
                self.assertEqual(data["roster_summary"]["编制"], 2)
                self.assertEqual(data["roster_summary"]["实有"], 1)
                self.assertEqual(data["roster_summary"]["空编"], 1)
                # 隔离树里没有 toolchain_manifest.json ⇒ 必须**如实报缺**，不许编一份顶上
                self.assertIn("toolchain", data)
                self.assertFalse(data["toolchain"]["ok"])
                self.assertIn("清单不存在", data["toolchain"]["error"])
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r2:
                    self.assertEqual(r2.status, 200)
                    self.assertIn("万能插".encode("utf-8"), r2.read())
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
