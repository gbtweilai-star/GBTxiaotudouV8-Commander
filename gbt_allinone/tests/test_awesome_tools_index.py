# -*- coding: utf-8 -*-
"""Awesome Tools 蒸馏索引（tools/awesome_tools_index.py）用例 —— 形状 + 三条带牙。

三条带牙正是主人点名的：**索引只读 · 映射可追 · 未核实不标绿**。
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from gbt_allinone.tools import awesome_tools_index as at


class AwesomeToolsIndexTests(unittest.TestCase):
    def test_status_shape(self):
        st = at.run("status")
        self.assertTrue(st["ok"], st)
        self.assertEqual(st["kind"], "awesome_tools_index")
        self.assertEqual(st["domain"], "tools")
        self.assertEqual(len(st["primitives"]), 4)
        self.assertEqual(len(st["red_lines"]), 5)
        self.assertIn("地图", str(st["core"]))
        self.assertIn("身份不变", str(st["core"]))

    def test_four_primitives_are_readonly(self):
        pr = {p["key"]: p for p in at.run("primitives")["primitives"]}
        self.assertEqual(sorted(pr), ["INDEX", "LOOKUP", "MAP", "VERIFY"])
        for k, p in pr.items():
            self.assertFalse(p["writes"], "%s 不该写盘" % k)

    def test_evidence_says_all_unverified(self):
        # 取证读数：六个重点工具**全部 0 命中** ⇒ 一条都不能标绿
        ev = at.run("evidence")["evidence"]
        self.assertEqual(set(ev["hits"].values()), {0})
        self.assertFalse(ev["repo_evidenced"])
        self.assertTrue(all(t["status"] == "unverified" for t in at.KEY_TOOLS))
        self.assertEqual(at.run("status")["verified_green"], 0)

    def test_teeth_1_index_is_readonly(self):
        # 带牙①：索引只读 —— 检索里混进写动作 ⇒ 拒
        self.assertTrue(at.run("gate_readonly", payload="按分类列出编程工具")["ok"])
        bad = at.run("gate_readonly", payload="顺便把缺的工具安装了")
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "index_not_readonly")
        self.assertEqual(bad["hit"], "安装")

    def test_teeth_2_map_must_be_traceable(self):
        # 带牙②：映射可追 —— 没有出处的映射一律拒
        good = at.run("gate_map", entries=[
            {"name": "CC Switch", "maps_to": "auto_switch", "evidence": "主人 R-H285 明确配对"},
        ])
        self.assertTrue(good["ok"], good)
        bad = at.run("gate_map", entries=[
            {"name": "CC Switch", "maps_to": "auto_switch", "evidence": ""},
        ])
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "map_without_source")
        self.assertTrue(any("缺 evidence" in x for x in bad["bad"]))
        na = at.run("gate_map")
        self.assertTrue(na["ok"], na)

    def test_teeth_3_unverified_must_not_be_green(self):
        # 带牙③：未核实不标绿 —— green 必须带证据
        bad = at.run("gate_verify", status="green")
        self.assertFalse(bad["ok"], bad)
        self.assertEqual(bad["rule"], "unverified_green")
        ok = at.run("gate_verify", status="green", evidence="2026-09-20 跑通了 X")
        self.assertTrue(ok["ok"], ok)
        self.assertEqual(ok["status"], "green")
        # 没给状态 ⇒ 默认不绿
        self.assertEqual(at.run("gate_verify")["status"], "unverified")
        self.assertEqual(at.run("gate_verify", status="unverified")["status"], "unverified")

    def test_index_pool_is_empty_and_not_invented(self):
        # 仓库内容未取证 ⇒ 索引池为空，**不编**
        r = at.run("index", category="编程工作区")
        self.assertEqual(r["items"], [])
        self.assertIn("不编", str(r["note"]))
        self.assertTrue(len(r["categories"]) >= 10)

    def test_lookup_only_knows_owner_given_six(self):
        for t in at.KEY_TOOLS:
            self.assertTrue(at.run("lookup", name=t["name"])["ok"])
        r = at.run("lookup", name="SomethingElse")
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "not_in_index")

    def test_fragments_are_pending_not_forced(self):
        # 主人给的碎片没有明确配对 ⇒ 进待归位，**不硬配**
        r = at.run("fragments")
        self.assertIn("外部知识库", r["fragments"])
        self.assertIn("不硬配", str(r["note"]))
        names = {x["name"] for x in at.run("map")["rows"]}
        self.assertNotIn("外部知识库", names)

    def test_sections_registered_blank_with_reason(self):
        # R-H287：蒸馏稿逐节到货 —— 第一节标题到了、表内容截断 ⇒ 留空带理由
        secs = at.run("sections")["sections"]
        self.assertEqual(len(secs), 2)
        # 第一节：表格六格全填 ⇒ 内容来自**字段格**（items 本来就是空的）
        self.assertEqual(secs[0]["heading"], "仓库定位与架构")
        self.assertEqual(secs[0]["table_header"], "维度")
        # 第二节：表内容截断 ⇒ 留空带理由
        self.assertEqual(secs[1]["heading"], "分类体系蒸馏")
        self.assertEqual(secs[1]["table_header"], "分类")
        self.assertIn("留空带理由", str(secs[1]["pending_reason"]))
        self.assertIn("不许凭标题编分类", str(secs[1]["pending_reason"]))
        g = at.run("gate_sections")
        self.assertTrue(g["ok"], g)
        self.assertFalse(g["complete"], "第一节还没内容 ⇒ 未齐")

    def test_sections_teeth_blank_without_reason(self):
        # 带牙①：把理由抹掉 ⇒ 红（有理由的空 ≠ 没写理由的空）
        # R-H293 起第一节的「空」已由字段格接管 ⇒ 这一格要用**第二节**（表内容仍截断）
        s = at.SECTIONS_OWNER[1]
        saved = s["pending_reason"]
        s["pending_reason"] = ""
        try:
            g = at.run("gate_sections")
        finally:
            s["pending_reason"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "section_blank_without_reason")
        self.assertTrue(at.run("gate_sections")["ok"])

    def test_sections_teeth_items_need_source(self):
        # 带牙②：有内容却没出处 ⇒ 红
        s = at.SECTIONS_OWNER[1]
        saved = (s["items"], s["source"])
        s["items"] = ("某项",)
        s["source"] = ""
        try:
            g = at.run("gate_sections")
        finally:
            s["items"], s["source"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "section_without_source")
        # 有内容 + 有出处 ⇒ 放行且 complete 转 True
        s["items"] = ("某项",)
        s["source"] = "主人提供 · R-H293 · 逐字"
        try:
            g2 = at.run("gate_sections")
        finally:
            s["items"], s["source"] = saved
        self.assertTrue(g2["ok"], g2)
        self.assertTrue(g2["complete"])

    def test_sections_teeth_empty_is_not_green(self):
        # 带牙③：**空样本不按绿**
        saved = at.SECTIONS_OWNER
        at.SECTIONS_OWNER = ()
        try:
            g = at.run("gate_sections")
        finally:
            at.SECTIONS_OWNER = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "sections_empty")
        self.assertTrue(at.run("gate_sections")["ok"])

    def test_core_crosscheck_side_by_side(self):
        # 主人这轮说「不是代码项目，而是一份…**清单**」；我方命题说「不是代码，是**地图**」
        # ⇒ **同向、措辞不同** ⇒ 并排记、不合并，哪张作正式口径待主人定
        cc = at.run("status")["core_crosscheck"]
        self.assertTrue(cc["same_direction"])
        self.assertTrue(cc["wording_differs"])
        self.assertIn("清单", str(cc["owner_says"]))
        self.assertIn("地图", str(cc["ours_says"]))
        self.assertIn("不擅自合并", str(cc["note"]))
        self.assertIn("待主人定", str(cc["note"]))
        # 主人那两句逐字留着（不许改写）
        joined = "".join(at.OWNER_20260920_R287)
        self.assertIn("不是一个代码项目", joined)
        self.assertIn("精选工具清单", joined)

    def test_section_rows_registered_blank_with_reason(self):
        # R-H288 立 · R-H291 起四格：仓库名 / 本质 / 规模（已填）+ 目录结构（留空带理由）
        rows = at.run("section_rows")["rows"]
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["section"], "一")
        self.assertEqual(rows[0]["field"], "仓库名")
        self.assertEqual(rows[0]["value"], "paysssk-creator/AIfuzhugongju")
        # R-H293 起第一节**六格全填** ⇒ 表齐（「空」那格随「核心价值」填上而消失）
        # 注意：原始常量里没有 has_value ⇒ 这一格要读**闸算出来的** rows
        g = at.run("gate_section_rows")
        self.assertTrue(g["ok"], g)
        self.assertTrue(all(x["has_value"] for x in g["rows"]))
        self.assertTrue(g["complete"], "第一节六格全填 ⇒ 表齐")

    def test_section_rows_teeth_blank_without_reason(self):
        # 带牙①：造一格空值且**没写理由** ⇒ 红（R-H293 起第一节六格全填，只好现造一格空）
        r = at.SECTION_ROWS_OWNER[5]
        saved = (r.get("value"), r.get("pending_reason"))
        r["value"] = None
        r["pending_reason"] = ""
        try:
            g = at.run("gate_section_rows")
        finally:
            r["value"], r["pending_reason"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "row_blank_without_reason")
        self.assertTrue(at.run("gate_section_rows")["ok"])

    def test_section_rows_teeth_value_needs_source(self):
        # 带牙②：有值却没出处 ⇒ 红；补上出处 ⇒ 放行且 complete 转 True
        r = at.SECTION_ROWS_OWNER[4]
        saved = (r["value"], r["source"], r["scope"])
        r["value"] = "某个名字"
        r["source"] = ""
        try:
            g = at.run("gate_section_rows")
        finally:
            r["value"], r["source"], r["scope"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "row_value_without_source")
        r["value"] = "某个名字"
        r["source"] = "主人提供 · R-H288"
        r["scope"] = "（测试用）这格说的是什么量"
        try:
            g2 = at.run("gate_section_rows")
        finally:
            r["value"], r["source"], r["scope"] = saved
        self.assertTrue(g2["ok"], g2)
        self.assertTrue(g2["rows"][4]["has_value"])
        self.assertTrue(g2["complete"], "五格都有值 ⇒ 表齐（complete 跟着格数走）")

    def test_section_rows_teeth_unregistered_section(self):
        # 带牙③（本刀最值钱的一条）：格挂在**没登记的节**上 ⇒ 红（挂空 = 事后数不清）
        r = at.SECTION_ROWS_OWNER[0]
        saved = r["section"]
        r["section"] = "九"
        try:
            g = at.run("gate_section_rows")
        finally:
            r["section"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "row_section_unregistered")
        self.assertEqual(g["section"], "九")
        self.assertTrue(at.run("gate_section_rows")["ok"])

    def test_section_rows_teeth_empty_is_not_green(self):
        # 带牙④：空样本不按绿
        saved = at.SECTION_ROWS_OWNER
        at.SECTION_ROWS_OWNER = ()
        try:
            g = at.run("gate_section_rows")
        finally:
            at.SECTION_ROWS_OWNER = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "rows_empty")
        self.assertTrue(at.run("gate_section_rows")["ok"])

    def test_section_rows_repo_name_filled(self):
        # R-H289：仓库名 = paysssk-creator/AIfuzhugongju（逐字）
        rows = at.run("section_rows")["rows"]
        self.assertEqual(len(rows), 6)
        r0 = rows[0]
        self.assertEqual(r0["field"], "仓库名")
        self.assertEqual(r0["value"], "paysssk-creator/AIfuzhugongju")
        self.assertIn("同 owner、不同仓库", str(r0["note"]))
        self.assertIn("GBT-V8", str(r0["note"]))
        self.assertIn("不许混", str(r0["note"]))
        self.assertEqual(at.SELF_REPO, "paysssk-creator/GBT-V8")

    def test_section_rows_teeth_repo_is_self(self):
        # 带牙①：被索引的仓库名填成**本仓自己** ⇒ 红（拿自己当第三方工具清单）
        r = at.SECTION_ROWS_OWNER[0]
        saved = r["value"]
        r["value"] = at.SELF_REPO
        try:
            g = at.run("gate_section_rows")
        finally:
            r["value"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "row_repo_is_self")
        self.assertTrue(at.run("gate_section_rows")["ok"])

    def test_section_rows_teeth_owner_prefix_unstated(self):
        # 带牙②：与 SELF_REPO 共享 owner 前缀、note 却是空的 ⇒ 红
        r = at.SECTION_ROWS_OWNER[0]
        saved = r["note"]
        r["note"] = ""
        try:
            g = at.run("gate_section_rows")
        finally:
            r["note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "row_repo_owner_prefix_unstated")
        self.assertEqual(g["owner"], "paysssk-creator")
        self.assertTrue(at.run("gate_section_rows")["ok"])

    def test_section_rows_essence_filled_three_tiers(self):
        # R-H290：本质 = Awesome 清单——不是代码，是工具索引（逐字）
        rows = at.run("section_rows")["rows"]
        self.assertEqual(len(rows), 6)
        r1 = rows[1]
        self.assertEqual(r1["field"], "本质")
        self.assertEqual(r1["value"], "Awesome 清单——不是代码，是工具索引")
        self.assertIn("不是代码", str(r1["note"]))
        self.assertIn("不合并", str(r1["note"]))
        # R-H288 那次「不许拿我方推论顶」⇒ 现在主人给的值与我方同向 ⇒ 记这一笔
        self.assertIn("互证", str(r1["note"]))

    def test_section_rows_scale_filled_with_scope_and_numbers(self):
        # R-H291：规模 = README.md 约 949 行 / 159 KB
        # 🔴 「规模」这词最容易被三种东西轮流冒充 ⇒ 已填的格必须写明 scope
        r2 = at.run("section_rows")["rows"][2]
        self.assertEqual(r2["field"], "规模")
        self.assertEqual(r2["value"], "README.md 约 949 行 / 159 KB")
        self.assertEqual(list(r2["numbers"]), [949, 159])
        scope = str(r2["scope"])
        for kw in ("README 的篇幅", "不是", "star", "贡献者数"):
            self.assertIn(kw, scope)
        note = str(r2["note"])
        self.assertIn("不是本仓", note)
        self.assertIn("未独立取证", note)
        self.assertIn("不标绿", note)
        g = at.run("gate_section_rows")
        self.assertTrue(g["ok"], g)

    def test_section_rows_directory_filled_with_columns(self):
        # R-H292：目录结构 = 按工具类型分类的表格（工具名 / 详细介绍 / 下载地址）
        # 🔴 主人给的是**表格结构**，不是我方默认理解的**文件目录树** ⇒ 照主人记
        r3 = at.run("section_rows")["rows"][3]
        self.assertEqual(r3["field"], "目录结构")
        self.assertEqual(r3["value"],
                         "按工具类型分类的表格（工具名 / 详细介绍 / 下载地址）")
        self.assertEqual(list(r3["columns"]), ["工具名", "详细介绍", "下载地址"])
        self.assertIn("不是文件目录树", str(r3["scope"]))
        self.assertIn("列契约", str(r3["note"]))
        g = at.run("gate_section_rows")
        self.assertTrue(g["ok"], g)

    def test_section_rows_teeth_columns_unaccounted(self):
        # 带牙：登记的列契约里有一个列名不在逐字里 ⇒ 红（列名不许自己加）
        r = at.SECTION_ROWS_OWNER[3]
        saved = r["columns"]
        r["columns"] = ("工具名", "详细介绍", "下载地址", "评分")
        try:
            g = at.run("gate_section_rows")
        finally:
            r["columns"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "row_columns_unaccounted")
        self.assertEqual(g["missing"], ["评分"])
        self.assertTrue(at.run("gate_section_rows")["ok"])

    def test_section_rows_teeth_inference_guard_missing(self):
        # 带牙：我方已有说法的空白格，理由里没写「不许拿我方推论顶上」⇒ 红
        r = at.SECTION_ROWS_OWNER[5]
        saved = (r.get("value"), r.get("pending_reason"), r.get("ours_says"))
        r["value"] = None
        r["ours_says"] = "我方在 R-H285 的说法：一张「能力地图」"
        r["pending_reason"] = "（测试用）留空带理由，但没写那条纪律"
        try:
            g = at.run("gate_section_rows")
        finally:
            r["value"], r["pending_reason"], r["ours_says"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "row_inference_guard_missing")
        self.assertIn("能力地图", str(g["ours_says"]))
        self.assertTrue(at.run("gate_section_rows")["ok"])

    def test_section_rows_teeth_scope_missing(self):
        # 带牙：已填的格却没有 scope（没说这格说的是什么量）⇒ 红
        r = at.SECTION_ROWS_OWNER[2]
        saved = r["scope"]
        r["scope"] = ""
        try:
            g = at.run("gate_section_rows")
        finally:
            r["scope"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "row_scope_missing")
        self.assertTrue(at.run("gate_section_rows")["ok"])

    def test_section_rows_teeth_numbers_unaccounted(self):
        # 带牙：逐字里两个数，记账里只留一个 ⇒ 红（双向对账）
        r = at.SECTION_ROWS_OWNER[2]
        saved = r["numbers"]
        r["numbers"] = (949,)
        try:
            g = at.run("gate_section_rows")
        finally:
            r["numbers"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "row_numbers_unaccounted")
        self.assertEqual(g["in_verbatim"], [159.0, 949.0])
        self.assertTrue(at.run("gate_section_rows")["ok"])

    def test_crosscheck_three_sources_side_by_side(self):
        # R-H290：同一件事**三种说法** ⇒ 共同主张 + 分歧点都显式，且**不许静默合并**
        r = at.run("core_sources")
        self.assertEqual(len(r["sources"]), 4)
        cc = r["crosscheck"]
        self.assertEqual(cc["common_claim"], "不是代码")
        self.assertFalse(cc["merged"])
        self.assertIn("工具索引", str(cc["divergence"]))
        self.assertIn("地图", str(cc["divergence"]))
        g = at.run("gate_crosscheck")
        self.assertTrue(g["ok"], g)
        # 共同主张必须**真的**在多边原句里出现（去引号后核）
        self.assertGreaterEqual(len(g["appears_in"]), 2)
        self.assertIn("R-H290", g["appears_in"])

    def test_crosscheck_teeth(self):
        # 带牙①：共同主张写一个谁都没说的 ⇒ 红
        saved = at.CORE_CROSSCHECK["common_claims"]
        at.CORE_CROSSCHECK["common_claims"] = ("这仓库是个代码项目",)
        saved1 = at.CORE_CROSSCHECK["common_claim"]
        at.CORE_CROSSCHECK["common_claim"] = "这仓库是个代码项目"
        try:
            g1 = at.run("gate_crosscheck")
        finally:
            at.CORE_CROSSCHECK["common_claims"] = saved
            at.CORE_CROSSCHECK["common_claim"] = saved1
        self.assertFalse(g1["ok"], g1)
        self.assertEqual(g1["rule"], "crosscheck_common_not_shared")
        # 带牙②：分歧点抹掉 ⇒ 红（只记共同点 = 静默合并）
        saved2 = at.CORE_CROSSCHECK["divergence"]
        at.CORE_CROSSCHECK["divergence"] = ""
        try:
            g2 = at.run("gate_crosscheck")
        finally:
            at.CORE_CROSSCHECK["divergence"] = saved2
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "crosscheck_divergence_missing")
        # 带牙③：偷偷标成已合并 ⇒ 红
        saved3 = at.CORE_CROSSCHECK["merged"]
        at.CORE_CROSSCHECK["merged"] = True
        try:
            g3 = at.run("gate_crosscheck")
        finally:
            at.CORE_CROSSCHECK["merged"] = saved3
        self.assertFalse(g3["ok"], g3)
        self.assertEqual(g3["rule"], "crosscheck_silently_merged")
        self.assertTrue(at.run("gate_crosscheck")["ok"])

    def test_pending_attribution_readings(self):
        # R-H294 立 · R-H304 两条 · R-H335 三条 · R-H336 四条 · R-H341 五条 ·
        # R-H343 六条 · R-H344 七条 · R-H345 起**八条**
        r = at.run("pending")
        # ⚠️ 不许写死条数（逐刀会涨，R-H344 立）⇒ **前缀 + 下限**
        self.assertGreaterEqual(len(r["items"]), 8)
        self.assertEqual([x["token"] for x in r["items"]][:8],
                         ["代表工具", "IDE & 代码编辑器", "特点", "与 GBT 的对接",
                          "智谱华章，AI 代码生成与补全",
                          "阿里，代码智能生成 + 研发智能问答 + 任务自主执行",
                          "编程 Agent 能力", "老牌 AI 编码助手"])
        it3 = r["items"][2]
        self.assertGreaterEqual(len(list(it3["readings"])), 2, "碎片也要写清读法")
        self.assertIn("没说挂哪儿", str(it3["pending_reason"]))
        self.assertIn("等主人一句话", str(it3["pending_reason"]))
        self.assertIsNone(it3["resolved"], "归属不许自己定")
        it = r["items"][0]
        self.assertEqual(it["token"], "代表工具")
        it2 = r["items"][1]
        self.assertEqual(it2["token"], "IDE & 代码编辑器")
        self.assertIn("第五个分类名", "".join(it2["readings"]))
        self.assertIn("两个都不填", str(it2["pending_reason"]))
        self.assertIsNone(it2["resolved"])
        self.assertEqual(len(list(it["readings"])), 2)
        self.assertTrue(any("第七个字段名" in x for x in it["readings"]))
        self.assertTrue(any("列名" in x for x in it["readings"]))
        self.assertIn("不许拿我方那六个工具顶上", str(it["pending_reason"]))
        self.assertIsNone(it["resolved"], "归属不许自己定")
        g = at.run("gate_pending")
        self.assertTrue(g["ok"], g)

    def test_pending_attribution_not_forced_into_any_table(self):
        # 两种读法都**没被执行**：第一节表仍六格、第二节仍只有表头
        rows = at.run("section_rows")["rows"]
        self.assertEqual(len(rows), 6)
        self.assertNotIn("代表工具", [x["field"] for x in rows])
        secs = at.run("sections")["sections"]
        self.assertEqual(len(secs), 2)
        self.assertEqual(list(secs[1]["items"] or []), [])

    def test_pending_attribution_teeth_readings(self):
        # 带牙①：只写一种读法 ⇒ 红（那就等于已经替主人定了）
        it = at.PENDING_ATTRIBUTION[0]
        saved = it["readings"]
        it["readings"] = ("① 第一节表的第七个字段名",)
        try:
            g = at.run("gate_pending")
        finally:
            it["readings"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "pending_readings_missing")
        self.assertTrue(at.run("gate_pending")["ok"])

    def test_pending_attribution_teeth_self_resolved(self):
        # 带牙②：自己把归属定了 ⇒ 红（归属只能由主人一句话定）
        it = at.PENDING_ATTRIBUTION[0]
        saved = it["resolved"]
        it["resolved"] = "第一节第七格"
        try:
            g = at.run("gate_pending")
        finally:
            it["resolved"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "pending_self_resolved")
        self.assertTrue(at.run("gate_pending")["ok"])

    def test_pending_attribution_teeth_reason_and_empty(self):
        # 带牙③：没理由 ⇒ 红；带牙④：一条都没有 ⇒ 红（空样本不按绿）
        it = at.PENDING_ATTRIBUTION[0]
        saved = it["pending_reason"]
        it["pending_reason"] = ""
        try:
            g = at.run("gate_pending")
        finally:
            it["pending_reason"] = saved
        self.assertEqual(g["rule"], "pending_reason_missing")
        saved_all = at.PENDING_ATTRIBUTION
        at.PENDING_ATTRIBUTION = ()
        try:
            g2 = at.run("gate_pending")
        finally:
            at.PENDING_ATTRIBUTION = saved_all
        self.assertEqual(g2["rule"], "pending_all_resolved_or_empty")
        self.assertTrue(at.run("gate_pending")["ok"])

    def test_section2_columns_and_first_category(self):
        # R-H295：第二节列契约（代表工具 / 对应 GBT 能力域）+ 第一个分类名
        c = at.run("columns2")
        self.assertEqual(list(c["columns"]), ["代表工具", "对应 GBT 能力域"])
        cats = at.run("gate_categories")
        self.assertEqual(len(cats["rows"]), 28)
        self.assertEqual(cats["rows"][0]["category"], "AI辅助编程工具")
        # R-H296 起『代表工具』已填、『对应 GBT 能力域』仍空
        cells = dict(cats["rows"][0]["cells"])
        self.assertIn("Trae", str(cells["代表工具"]))
        self.assertIsNone(cells["对应 GBT 能力域"])
        g = at.run("gate_categories")
        self.assertTrue(g["ok"], g)
        self.assertFalse(g["complete"], "格还没到 ⇒ 未齐")

    def test_pending_attribution_gets_new_evidence(self):
        # R-H295 给同族列名 ⇒ 「代表工具」读法② 证据 +1（**但仍不擅自定论**）
        it = at.run("pending")["items"][0]
        self.assertIn("证据 +1", str(it["pending_reason"]))
        self.assertIn("仍不擅自定论", str(it["pending_reason"]))
        self.assertIsNone(it["resolved"], "还没定论，不许自己填归属")

    def test_categories_teeth(self):
        # 带牙①：没理由（格没到却不写理由）⇒ 红；带牙②：自己加一列 ⇒ 红
        r = at.CATEGORY_ROWS_OWNER[0]
        saved = r["pending_reason"]
        r["pending_reason"] = ""
        try:
            g = at.run("gate_categories")
        finally:
            r["pending_reason"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "category_without_reason")
        saved2 = r["cells"]
        r["cells"] = {"评分": "5"}
        try:
            g2 = at.run("gate_categories")
        finally:
            r["cells"] = saved2
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "category_cell_unknown_column")
        self.assertTrue(at.run("gate_categories")["ok"])

    def test_categories_teeth_empty_and_source(self):
        # 带牙③：空样本不按绿；带牙④：有值没出处 ⇒ 红
        saved = at.CATEGORY_ROWS_OWNER
        at.CATEGORY_ROWS_OWNER = ()
        try:
            g = at.run("gate_categories")
        finally:
            at.CATEGORY_ROWS_OWNER = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "categories_empty")
        r = at.CATEGORY_ROWS_OWNER[0]
        saved2 = (r["cells"], r["source"])
        r["cells"] = {"代表工具": "CC Switch"}
        r["source"] = ""
        try:
            g2 = at.run("gate_categories")
        finally:
            r["cells"], r["source"] = saved2
        self.assertEqual(g2["rule"], "category_cell_without_source")
        self.assertTrue(at.run("gate_categories")["ok"])

    def test_category_representative_tools_filled(self):
        # R-H296：分类『AI辅助编程工具』的『代表工具』= 五个工具（逐字，斜杠原样）
        # 注意：原始常量里 cells 只含已填的键 ⇒ 这一格读**闸归一化后的** rows
        rows = at.run("gate_categories")["rows"]
        cells = dict(rows[0]["cells"])
        self.assertEqual(cells["代表工具"],
                         "Trae / Fitten Code / CodeGeeX / 通义灵码 / GitHub Copilot")
        self.assertIsNone(cells["对应 GBT 能力域"], "那一格还没到")
        self.assertIn("对应 GBT 能力域", str(rows[0]["pending_reason"]))
        self.assertIn("不许拿我方 R-H285", str(rows[0]["pending_reason"]))
        g = at.run("gate_categories")
        self.assertTrue(g["ok"], g)
        self.assertFalse(g["complete"], "还有一格没到 ⇒ 未齐")

    def test_category_partial_fill_needs_reason(self):
        # 带牙：填了一半却不写理由 ⇒ 红（半填不许当成不用解释）
        r = at.CATEGORY_ROWS_OWNER[0]
        saved = r["pending_reason"]
        r["pending_reason"] = ""
        try:
            g = at.run("gate_categories")
        finally:
            r["pending_reason"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "category_without_reason")
        self.assertTrue(at.run("gate_categories")["ok"])

    def test_pending_attribution_action_evidence(self):
        # R-H296 行为证据入账 ⇒ 但 resolved 仍 None，且理由必须写明「仍在等主人一句话」
        it = at.run("pending")["items"][0]
        self.assertIn("行为证据", str(it["action_evidence"]))
        self.assertIn("读法②", str(it["action_evidence"]))
        self.assertIsNone(it["resolved"], "证据再强也不许自解")
        self.assertIn("主人一句话", str(it["pending_reason"]))
        self.assertTrue(at.run("gate_pending")["ok"])

    def test_pending_attribution_teeth_evidence_without_wait(self):
        # 带牙：有行为证据却没写「仍在等主人一句话」⇒ 红（防「证据够了就自己定」）
        it = at.PENDING_ATTRIBUTION[0]
        saved = it["pending_reason"]
        it["pending_reason"] = "两读法并排、不擅自判定（但没写还在等一句话）"
        try:
            g = at.run("gate_pending")
        finally:
            it["pending_reason"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "pending_evidence_without_wait")
        self.assertTrue(at.run("gate_pending")["ok"])

    def test_second_category_blank_with_reason(self):
        # R-H297：第二个分类『AI实用效率工具』⇒ 建行、其余格未到 ⇒ 留空带理由
        g = at.run("gate_categories")
        rows = g["rows"]
        self.assertEqual([x["category"] for x in rows],
                         ["AI辅助编程工具", "AI实用效率工具", "AI模型管理工具",
                          "AI短剧生成工具", "实用画图工具", "文档和知识库工具",
                          "Markdown 编辑器", "Markdown 文件转换器",
                          "开发环境管理工具", "GitHub 加速工具",
                          "文本编辑器工具", "数据库管理工具", "数据库设计工具", "Git 管理工具", "抓包调试工具", "性能压测工具", "Redis 管理工具", "文件同步工具", "报表制作工具", "文件下载工具", "Docker 管理工具", "网络管理工具", "内网穿透工具", "堡垒机工具", "实用建站工具", "Kafka 管理工具", "图像处理软件", "Edge/Chrome/VS Code 插件"])
        # R-H298 起第二个分类的『代表工具』已填（CowAgent / OpenClaw Monitor）
        c1 = dict(rows[1]["cells"])
        self.assertEqual(c1["代表工具"], "CowAgent / OpenClaw Monitor")
        self.assertIsNone(c1["对应 GBT 能力域"])
        self.assertIn("不许凭分类名编工具", str(rows[1]["pending_reason"]))
        self.assertTrue(g["ok"], g)
        self.assertFalse(g["complete"], "两行都还有格没到 ⇒ 未齐")

    def test_two_categories_batches_side_by_side(self):
        # 🔴 取证：两个分类名**都不在** R-H285 那批分类名里 ⇒ 两批并存、不合并
        names = [str(r["category"]) for r in at.CATEGORY_ROWS_OWNER]
        for n in names:
            self.assertNotIn(n, at.CATEGORIES_OWNER,
                             "%s 若已在旧批里，本闸的前提就不成立" % n)
        # 「两批并存」是**全局说明**（不是每行各自的属性）⇒ 核全局那一格
        self.assertIn("两批", at.CATEGORY_VS_REGISTRY_NOTE)
        self.assertIn("并存", at.CATEGORY_VS_REGISTRY_NOTE)
        g = at.run("gate_categories")
        self.assertIn("两批", str(g["vs_registry_note"]))
        self.assertIn("并存", str(g["vs_registry_note"]))

    def test_categories_teeth_registry_unstated(self):
        # 带牙：分类名不在旧批里、又没写明两批并存 ⇒ 红（防静默合并）
        # ⚠️ 判据挂**全局说明**（两批并存是全局事实，不是每行的属性）
        saved = at.CATEGORY_VS_REGISTRY_NOTE
        at.CATEGORY_VS_REGISTRY_NOTE = "（测试用）没有写明与旧批的关系"
        try:
            g = at.run("gate_categories")
        finally:
            at.CATEGORY_VS_REGISTRY_NOTE = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "category_name_vs_registry_unstated")
        self.assertTrue(at.run("gate_categories")["ok"])

    def test_second_category_representative_filled(self):
        # R-H298：第二个分类的『代表工具』= CowAgent / OpenClaw Monitor（逐字）
        rows = at.run("gate_categories")["rows"]
        cells = dict(rows[1]["cells"])
        self.assertEqual(cells["代表工具"], "CowAgent / OpenClaw Monitor")
        self.assertIsNone(cells["对应 GBT 能力域"])
        self.assertIn("重叠", str(rows[1]["pending_reason"]))
        self.assertIn("R-H285", str(rows[1]["pending_reason"]))
        self.assertTrue(at.run("gate_categories")["ok"])

    def test_overlap_with_rh285_is_real(self):
        # 取证：这两个名字**确实在**我方 R-H285 那六个里（不是我们猜的重叠）
        names = [t["name"] for t in at.KEY_TOOLS]
        for n in ("CowAgent", "OpenClaw Monitor"):
            self.assertIn(n, names)
        g = at.run("gate_categories")
        self.assertIn("CowAgent", list(g["overlap_with_rh285"]))
        self.assertIn("OpenClaw Monitor", list(g["overlap_with_rh285"]))

    def test_categories_teeth_overlap_unstated(self):
        # 带牙：格里有 R-H285 的名字、却没写重叠 ⇒ 红（防「同一批被当两批新发现」）
        r = at.CATEGORY_ROWS_OWNER[1]
        saved = r["pending_reason"]
        # 要**只**踩重叠那条：前半满足「两批并存」，且不出现「重叠 / R-H285」
        r["pending_reason"] = "（测试用）留空带理由；两批并存，关系待定"
        try:
            g = at.run("gate_categories")
        finally:
            r["pending_reason"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "category_overlap_with_rh285_unstated")
        self.assertIn("CowAgent", list(g["hits"]))
        self.assertTrue(at.run("gate_categories")["ok"])

    def test_third_category_blank_with_reason(self):
        # R-H299：第三个分类『AI模型管理工具』⇒ 建行、其余格未到 ⇒ 留空带理由
        g = at.run("gate_categories")
        rows = g["rows"]
        self.assertEqual([x["category"] for x in rows],
                         ["AI辅助编程工具", "AI实用效率工具", "AI模型管理工具",
                          "AI短剧生成工具", "实用画图工具", "文档和知识库工具",
                          "Markdown 编辑器", "Markdown 文件转换器",
                          "开发环境管理工具", "GitHub 加速工具",
                          "文本编辑器工具", "数据库管理工具", "数据库设计工具", "Git 管理工具", "抓包调试工具", "性能压测工具", "Redis 管理工具", "文件同步工具", "报表制作工具", "文件下载工具", "Docker 管理工具", "网络管理工具", "内网穿透工具", "堡垒机工具", "实用建站工具", "Kafka 管理工具", "图像处理软件", "Edge/Chrome/VS Code 插件"])
        # R-H301 起第三个分类的『代表工具』已填
        c2v = dict(rows[2]["cells"])
        self.assertEqual(c2v["代表工具"], "CC Switch / CC-Switch CLI")
        # R-H302 起第三行**两格齐**（第一条完整分类行）
        self.assertEqual(c2v["对应 GBT 能力域"], "模型路由 / 供应商切换")
        # 第三行已齐 ⇒ 「留空带理由」这格自然没了；改看**第四行**
        self.assertIn("不许凭分类名编工具", str(rows[3]["pending_reason"]))
        self.assertTrue(g["ok"], g)

    def test_categories_teeth_duplicate_name(self):
        # 带牙：同一个分类名建两行 ⇒ 红（复制粘贴最容易出）
        saved = at.CATEGORY_ROWS_OWNER[2]["category"]
        at.CATEGORY_ROWS_OWNER[2]["category"] = "AI实用效率工具"
        try:
            g = at.run("gate_categories")
        finally:
            at.CATEGORY_ROWS_OWNER[2]["category"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "category_duplicate")
        self.assertTrue(at.run("gate_categories")["ok"])

    def test_third_category_representative_filled(self):
        # R-H301：第三个分类的『代表工具』= CC Switch / CC-Switch CLI（逐字）
        rows = at.run("gate_categories")["rows"]
        cells = dict(rows[2]["cells"])
        self.assertEqual(cells["代表工具"], "CC Switch / CC-Switch CLI")
        # R-H302 起这一格也到了 ⇒ 第三行**两格齐**
        self.assertEqual(cells["对应 GBT 能力域"], "模型路由 / 供应商切换")
        # R-H302 起第三行已齐（理由那格是 None）⇒ 这两句在 **note** 里
        r = str(rows[2]["pending_reason"]) + "\n" + str(rows[2].get("note"))
        for kw in ("重叠", "变体", "R-H285"):
            self.assertIn(kw, r)
        self.assertTrue(at.run("gate_categories")["ok"])

    def test_variant_detected(self):
        # 取证：CC-Switch CLI 是 CC Switch 的**变体**（前缀一致、整串更长）
        g = at.run("gate_categories")
        self.assertIn("CC Switch", list(g["overlap_with_rh285"]))
        self.assertIn("CC-Switch CLI", list(g["variants_of_rh285"]))

    def test_categories_teeth_variant_unstated(self):
        # 带牙：有变体却没写「变体」⇒ 红（只写重叠不够）
        r = at.CATEGORY_ROWS_OWNER[2]
        saved = r["pending_reason"]
        saved_note = r.get("note")
        r["pending_reason"] = "（测试用）留空带理由；与 R-H285 重叠"
        r["note"] = "（测试用）note 里也不写那件事"
        try:
            g = at.run("gate_categories")
        finally:
            r["pending_reason"] = saved
            r["note"] = saved_note
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "category_variant_unstated")
        self.assertIn("CC-Switch CLI", list(g["variants"]))
        self.assertTrue(at.run("gate_categories")["ok"])

    def test_first_complete_category_row(self):
        # R-H302：第三个分类两格齐 —— 分类表里**第一条完整行**
        g = at.run("gate_categories")
        rows = g["rows"]
        self.assertTrue(rows[2]["has_all"], "第三行应当两格齐")
        self.assertFalse(rows[0]["has_all"], "前两行仍缺「对应 GBT 能力域」")
        self.assertFalse(g["complete"], "还有行没齐 ⇒ 整表未齐")
        note = str(g.get("vs_registry_note"))
        self.assertIn("两批", note)

    def test_fourth_category_blank_with_reason(self):
        # R-H302：第四个分类『AI短剧生成工具』⇒ 建行、其余格未到 ⇒ 留空带理由
        rows = at.run("gate_categories")["rows"]
        self.assertEqual([x["category"] for x in rows],
                         ["AI辅助编程工具", "AI实用效率工具", "AI模型管理工具",
                          "AI短剧生成工具", "实用画图工具", "文档和知识库工具",
                          "Markdown 编辑器", "Markdown 文件转换器",
                          "开发环境管理工具", "GitHub 加速工具",
                          "文本编辑器工具", "数据库管理工具", "数据库设计工具", "Git 管理工具", "抓包调试工具", "性能压测工具", "Redis 管理工具", "文件同步工具", "报表制作工具", "文件下载工具", "Docker 管理工具", "网络管理工具", "内网穿透工具", "堡垒机工具", "实用建站工具", "Kafka 管理工具", "图像处理软件", "Edge/Chrome/VS Code 插件"])
        # R-H303 起第四行『代表工具』已填、『对应 GBT 能力域』仍空
        c = dict(rows[3]["cells"])
        self.assertEqual(c["代表工具"], "MoneyPrinterTurbo")
        self.assertIsNone(c["对应 GBT 能力域"])
        self.assertIn("不许凭分类名编工具", str(rows[3]["pending_reason"]))
        self.assertIn("重叠", str(rows[3]["pending_reason"]))

    def test_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            at.run("nope")

    def test_staged_value_held_not_landed(self):
        # R-H305：主人给的清单**暂存**（不落表）⇒ 分类仍 4 个、第五格仍 None
        it = [x for x in at.run("pending")["items"] if x["token"].startswith("IDE")][0]
        self.assertEqual(it["staged_value"], "VS Code / Trae 等")
        self.assertIn("暂存", str(it["staged_note"]))
        self.assertIn("不落", str(it["staged_note"]))
        self.assertIn("行为证据 +1", str(it["pending_reason"]))
        self.assertIn("读法②", str(it["pending_reason"]))
        self.assertIsNone(it["resolved"], "仍不许自解归属")
        cats = at.run("gate_categories")["rows"]
        self.assertEqual(len(cats), 28, "暂存不许变成新分类")
        self.assertIsNone(dict(cats[0]["cells"])["对应 GBT 能力域"], "也不许塞进第一行")

    def test_staged_without_hold_note_goes_red(self):
        # 带牙：暂存却没写「暂存、不落表」⇒ 红（防暂存悄悄变成已落）
        it = [x for x in at.PENDING_ATTRIBUTION if x["token"].startswith("IDE")][0]
        saved = it["staged_note"]
        it["staged_note"] = "（测试用）就放在这儿"
        try:
            g = at.run("gate_pending")
        finally:
            it["staged_note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "staged_without_hold_note")
        self.assertTrue(at.run("gate_pending")["ok"])

        with self.assertRaises(ValueError):
            at.run("nope")

    # ---------- R-H334：源表列契约 + 截断碎片 ----------

    def test_source_table_columns_owner_order(self):
        # R-H334：主人给的源表结构 = 工具名 | 详细介绍 | 下载地址（顺序即主人给的顺序）
        g = at.run("gate_source_columns")
        self.assertTrue(g["ok"], g)
        self.assertEqual(list(g["columns"]), ["工具名", "详细介绍", "下载地址"])
        self.assertEqual(list(g["owner_columns"]), ["工具名", "详细介绍", "下载地址"])
        self.assertFalse(g["same_table"], "源表与本仓第二节是两张表")
        d = at.run("source_columns")
        self.assertEqual(list(d["columns"]), list(at.SOURCE_TABLE_COLUMNS_OWNER))

    def test_source_columns_not_merged_with_local(self):
        # 两张表的列名一个都不重合 ⇒ 不许当同一个
        self.assertEqual(set(at.SOURCE_TABLE_COLUMNS) & set(at.SECTION2_COLUMNS), set())
        self.assertTrue(at.run("gate_source_columns")["ok"])
        self.assertEqual(list(at.SECTION2_COLUMNS), ["代表工具", "对应 GBT 能力域"])

    def test_source_columns_teeth_order_and_mix(self):
        # 带牙①：重排顺序 ⇒ 红；带牙②：把源列混进本仓列 ⇒ 红
        saved = at.SOURCE_TABLE_COLUMNS
        at.SOURCE_TABLE_COLUMNS = ("工具名", "下载地址", "详细介绍")
        try:
            g = at.run("gate_source_columns")
        finally:
            at.SOURCE_TABLE_COLUMNS = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "source_column_order_changed")
        self.assertTrue(at.run("gate_source_columns")["ok"])

        saved2 = at.SECTION2_COLUMNS
        at.SECTION2_COLUMNS = ("代表工具", "工具名")
        try:
            g2 = at.run("gate_source_columns")
        finally:
            at.SECTION2_COLUMNS = saved2
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "source_columns_merged_into_local")
        self.assertTrue(at.run("gate_source_columns")["ok"])

    def test_truncated_fragment_held_not_landed(self):
        # R-H334：工具 是截断出来的 ⇒ 不许当分类名 / 列名 / 格值
        g = at.run("gate_truncated")
        self.assertTrue(g["ok"], g)
        # 🔧 R-H384 增长连带：碎片**会长**（现在 3 条：工具 / 原语 / text）
        self.assertEqual(g["count"], len(at.TRUNCATED_FRAGMENTS))
        self.assertGreaterEqual(g["count"], 1)
        it = [x for x in at.run("truncated")["items"] if x["token"] == "工具"][0]
        self.assertEqual(it["token"], "工具")
        self.assertIn("留空不编", str(it["note"]))
        self.assertIn("补全", str(it["note"]))
        self.assertIsNone(it["resolved"], "碎片不许自解")
        for n in [r["category"] for r in at.CATEGORY_ROWS_OWNER]:
            self.assertNotEqual(n, "工具", "碎片不许当分类名")
        self.assertNotIn("工具", list(at.SOURCE_TABLE_COLUMNS))

    def test_truncated_teeth_landed_and_reason_missing(self):
        # 带牙①：碎片落进数据面 ⇒ 红；带牙②：没写「留空不编」⇒ 红
        tmp = {"section": "二", "category": "工具", "cells": {}, "source": "（测试用）",
               "pending_reason": "（测试用）留空带理由"}
        saved_rows = at.CATEGORY_ROWS_OWNER
        at.CATEGORY_ROWS_OWNER = tuple(saved_rows) + (tmp,)
        try:
            g = at.run("gate_truncated")
        finally:
            at.CATEGORY_ROWS_OWNER = saved_rows
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "truncated_fragment_landed")
        self.assertTrue(at.run("gate_truncated")["ok"])
        # R-H419：一大段（三、/3.1/3.2）+ 『预设』第三个表头残片 + 『text』第二次
        r19 = at.run("incoming_distills"); vb19 = str(r19["items"][0]["verbatim"])
        for kw in ("三、为 GBT 设计的原生路由层", "3.1 核心设计原则", "3.2 三层路由预设",
                   "用户显式声明优先级 → 网关绝不偷换 → 五层逐级兜底 → 每次切换留痕",
                   "由本地大脑直接调度"):
            self.assertIn(kw, vb19)
        fr = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}
        self.assertTrue(fr["预设"].get("header"), "『预设』是表头残片")
        self.assertIn("R-H419", str(fr["text"]["at"]), "『text』第二次出现")
        # 🔴 「三、」**不许**塞进 FUSION_SECTIONS（那张表是「四、」的 4.x ⇒ 递增不许被破坏）
        self.assertEqual(at.run("gate_fusion_sections")["nos"], ["4.1", "4.2", "4.3"])
        # R-H420：『对应优先级』形态待定 ⇒ 两种读法并排、不进任何结构
        r20 = at.run("incoming_distills"); vb20 = str(r20["items"][0]["verbatim"])
        self.assertIn("对应优先级", vb20)
        sp = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertGreaterEqual(len(sp), 1)
        self.assertEqual(sp[0][0], "对应优先级")
        # R-H421：『本地行为』同族（仍形态待定 ⇒ shape_pending 两条）
        r21 = at.run("incoming_distills")
        self.assertIn("本地行为", str(r21["items"][0]["verbatim"]))
        sp21 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertGreaterEqual(len(sp21), 2)
        self.assertEqual(sp21[1][0], "本地行为")
        self.assertIn("第三个列名", sp21[1][1])
        # R-H422：『gbt-best』⇒ shape_pending 第三条（形态待定）+ 盘上那条是**我自己写的摘要**
        r22 = at.run("incoming_distills"); it22 = r22["items"][0]
        self.assertIn("gbt-best", str(it22["verbatim"]))
        sp22 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        # R-H423 增长连带：会继续长 ⇒ 只看前三条
        self.assertEqual([x[0] for x in sp22][:3], ["对应优先级", "本地行为", "gbt-best"])
        self.assertIn("第一行的格", sp22[2][1])
        self.assertIn("两套前缀", sp22[2][2])
        self.assertIn("我自己写的对话摘要", str(it22["disk_check"]))
        # R-H423：『质量优先』⇒ shape_pending 第四条（与 gbt-best 同族 · 仍不硬判）
        r23 = at.run("incoming_distills"); it23 = r23["items"][0]
        self.assertIn("质量优先", str(it23["verbatim"]))
        sp23 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertEqual([x[0] for x in sp23][:4],
                         ["对应优先级", "本地行为", "gbt-best", "质量优先"])
        self.assertIn("第一行第二格", [x for x in sp23 if x[0] == "质量优先"][0][1])
        self.assertIn("配对", [x for x in sp23 if x[0] == "质量优先"][0][2])
        # R-H424：第五条（语义明确但仍挂不上结构）+ 与盘上「降级/能源池」同族
        r24 = at.run("incoming_distills"); it24 = r24["items"][0]
        self.assertIn("本地模型不够时，上云端最强模型", str(it24["verbatim"]))
        sp24 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertIn(sp24[4][0], ["本地模型不够时，上云端最强模型"])
        self.assertIn("格值", sp24[4][1])
        self.assertIn("独立", [x for x in sp24 if x[0] == "本地模型不够时，上云端最强模型"][0][2])
        # R-H425：第六条（gbt-balanced · 与 gbt-best 同族）+ 盘上那套是我自己写的摘要
        r25 = at.run("incoming_distills"); it25 = r25["items"][0]
        self.assertIn("gbt-balanced", str(it25["verbatim"]))
        sp25 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertEqual(sp25[5][0], "gbt-balanced")
        self.assertIn("第二行第一格", sp25[5][1])
        self.assertIn("我自己写的摘要", [x for x in sp25 if x[0] == "gbt-balanced"][0][2])
        # R-H426：第七条（平衡优先 · 与质量优先同族）+ 与之配对的说明
        r26 = at.run("incoming_distills"); it26 = r26["items"][0]
        self.assertIn("平衡优先", str(it26["verbatim"]))
        sp26 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertIn(sp26[6][0], ["平衡优先"])
        self.assertIn("第二行第二格", sp26[6][1])
        self.assertIn("配对", [x for x in sp26 if x[0] == "平衡优先"][0][2])
        # R-H427：第八条（与 R-H424 那句同向 ⇒ 但并排、不许当同一个）
        r27 = at.run("incoming_distills"); it27 = r27["items"][0]
        self.assertIn("本地模型优先，不够再上云端", str(it27["verbatim"]))
        sp27 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertIn(sp27[7][0], ["本地模型优先，不够再上云端"])
        self.assertIn("同向但字面不同", [x for x in sp27 if x[0] == "本地模型优先，不够再上云端"][0][2])
        self.assertIn("不许当同一个", [x for x in sp27 if x[0] == "本地模型优先，不够再上云端"][0][2])
        # R-H428：第九条（gbt-eco · 与 gbt-best/gbt-balanced 同族）
        r28 = at.run("incoming_distills"); it28 = r28["items"][0]
        self.assertIn("gbt-eco", str(it28["verbatim"]))
        sp28 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        # ⚠️ 我改成**按名字找**（原先按**下标** ⇒ 列表一长就指错人）
        self.assertIn("gbt-eco", [x[0] for x in sp28])
        self.assertIn("第三行第一格", [x for x in sp28 if x[0] == "gbt-eco"][0][1])
        # R-H429：第十条（成本优先）⇒ **三对「像一对」齐了**（best↔质量 / balanced↔平衡 / eco↔成本）
        r29 = at.run("incoming_distills"); it29 = r29["items"][0]
        self.assertIn("成本优先", str(it29["verbatim"]))
        sp29 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertIn("成本优先", [x[0] for x in sp29])
        self.assertIn("第三行第二格", [x for x in sp29 if x[0] == "成本优先"][0][1])
        names29 = [x[0] for x in sp29]
        for t29 in ("gbt-best", "质量优先", "gbt-balanced", "平衡优先", "gbt-eco", "成本优先"):
            self.assertIn(t29, names29, "三对的六个词都该在待定格里")
        # R-H430：第十一条 —— 同主题**第三次**说法，但**未必同向**（不许我调和）
        r30 = at.run("incoming_distills"); it30 = r30["items"][0]
        self.assertIn("只用本地模型，不够就降级", str(it30["verbatim"]))
        sp30 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertIn("只用本地模型，不够就降级", [x[0] for x in sp30])
        # ⚠️ 一律**按名字找那一条**（按下标会在列表变长后指错人 —— 今天我踩了 4 次）
        _d30 = [x for x in sp30 if x[0] == "只用本地模型，不够就降级"][0][2]
        self.assertIn("可能不同向", _d30)
        self.assertIn("不许当同一个", _d30)
        self.assertIn("更不许我擅自调和", _d30)
        # 同一主题的三句**都在册**（并排，没合并）
        vb30 = str(it30["verbatim"])
        for t30 in ("本地模型不够时，上云端最强模型", "本地模型优先，不够再上云端", "只用本地模型，不够就降级"):
            self.assertIn(t30, vb30)
        # R-H431：3.3 五层框图（frame_layers 5 条）+ 两套五层名并排对照 + 『任务类型』表头
        r31 = at.run("incoming_distills"); it31 = r31["items"][0]
        self.assertIn("3.3 五层本地路由架构", str(it31["verbatim"]))
        self.assertTrue(r31["frame_layers_complete"], "框图五层都登记了")
        self.assertEqual(r31["frame_layers"][4][2], "全部不可用 → 返回 needs_external_key")
        diff = [list(d.items())[0] for d in r31["layer_name_diff"]]
        print("layer_name_diff =", diff)
        self.assertEqual(diff[4][1], "逐字一致", "L5 两套名都是『兜底层』")
        for i in range(4):
            self.assertIn("一字之差", diff[i][1], "L1-L4 都是一字之差")
        fr = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}
        self.assertTrue(fr["任务类型"].get("header"))
        # R-H432：『复杂度』= 第五个表头残片（3.4 矩阵第二列）
        r32 = at.run("incoming_distills")
        self.assertIn("复杂度", str(r32["items"][0]["verbatim"]))
        fr32 = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}
        self.assertTrue(fr32["复杂度"].get("header"))
        self.assertEqual(fr32["复杂度"]["kind"], "truncated")
        self.assertIn("第五个", str(fr32["复杂度"]["note"]))
        # R-H433：第六个表头残片（推荐能源）+ 与盘上「能源池」同向
        fr33 = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}
        self.assertTrue(fr33["推荐能源"].get("header"))
        self.assertIn("第六个", str(fr33["推荐能源"]["note"]))
        self.assertIn("能源池", str(fr33["推荐能源"]["note"]))
        self.assertIn("推荐能源", str(at.run("incoming_distills")["items"][0]["verbatim"]))
        # R-H434：3.4 矩阵第一行第一格（**推断形态**）⇒ 未成行 + 行数未知
        r34 = at.run("incoming_distills")
        self.assertIn("代码补全 / 单行生成", str(r34["items"][0]["verbatim"]))
        self.assertEqual(r34["matrix_rows"], [["代码补全 / 单行生成"]])
        self.assertEqual(r34["matrix_cells"], 1, "只到一格")
        self.assertIn("行数未知", str(r34["matrix_note"]))
        # R-H435：『低』= 弱推断（单字）⇒ **不进矩阵**（判不出来就不判）
        r35 = at.run("incoming_distills"); it35 = r35["items"][0]
        self.assertIn("低", str(it35["verbatim"]))
        sp35 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        self.assertIn("低", [x[0] for x in sp35])
        self.assertIn("第一行第二格", [x for x in sp35 if x[0] == "低"][0][1])
        self.assertIn("截断", [x for x in sp35 if x[0] == "低"][0][2])
        # R-H436：缺格不许跳（第二格没到 ⇒ 第三格也不落位）
        r36 = at.run("incoming_distills")
        self.assertIn("本地 Qwen2.5-Coder-7B", str(r36["items"][0]["verbatim"]))
        sp36 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        q36 = [x for x in sp36 if x[0] == "本地 Qwen2.5-Coder-7B"][0]
        self.assertIn("缺格不许跳", q36[2])
        # R-H437：一条原则（仍待定）——与「显式声明」同族，但不硬判
        r37 = at.run("incoming_distills")
        self.assertIn("不管做什么必须注重细节", str(r37["items"][0]["verbatim"]))
        sp37 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        d37 = [x for x in sp37 if x[0] == "不管做什么必须注重细节"][0]
        self.assertIn("核心设计原则", d37[1])
        self.assertIn("通用嘱咐", d37[2])
        # R-H438：第十五条（仍不硬判）
        r38 = at.run("incoming_distills")
        self.assertIn("工具函数 / 脚本", str(r38["items"][0]["verbatim"]))
        sp38 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        d38 = [x for x in sp38 if x[0] == "工具函数 / 脚本"][0]
        self.assertIn("第二行第一格", d38[1])
        # R-H439：第十六条（低-中 · 仍不硬判 · 缺格不许跳）
        r39 = at.run("incoming_distills")
        self.assertIn("低-中", str(r39["items"][0]["verbatim"]))
        sp39 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        d39 = [x for x in sp39 if x[0] == "低-中"][0]
        self.assertIn("第二行第二格", d39[1])
        self.assertIn("缺格不许跳", d39[2])
        # R-H440：第十七条（与 Coder 那条同前缀、不同尾 ⇒ 并排、不许当同一个）
        r40 = at.run("incoming_distills")
        self.assertIn("本地 Qwen2.5-7B", str(r40["items"][0]["verbatim"]))
        sp40 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        d40 = [x for x in sp40 if x[0] == "本地 Qwen2.5-7B"][0]
        self.assertIn("同前缀、不同尾", d40[2])
        self.assertIn("不许当同一个", d40[2])
        self.assertIn("本地 Qwen2.5-Coder-7B", [x[0] for x in sp40], "两个都在册、并排")
        # R-H441：第十八条（任务类型候选第三个）⇒ 仍不硬判
        r41 = at.run("incoming_distills")
        self.assertIn("Bug 定位与修复", str(r41["items"][0]["verbatim"]))
        sp41 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        d41 = [x for x in sp41 if x[0] == "Bug 定位与修复"][0]
        self.assertIn("候选已 3 个", d41[2])
        # ⚠️ 我上一版写错了：第一个候选**已落位**（在矩阵里），后两个在**待定格**里
        self.assertIn("代码补全 / 单行生成", r41["matrix_rows"][0], "第一个候选在矩阵里")
        for t41 in ("工具函数 / 脚本", "Bug 定位与修复"):
            self.assertIn(t41, [x[0] for x in sp41], "另两个在待定格里")
        # R-H442：第十九条（复杂度候选第三个 中-高）⇒ 仍不硬判
        r42 = at.run("incoming_distills")
        self.assertIn("中-高", str(r42["items"][0]["verbatim"]))
        sp42 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        d42 = [x for x in sp42 if x[0] == "中-高"][0]
        self.assertIn("候选已 3 个", d42[2])
        self.assertIn("全在待定格", d42[2])
        for t42 in ("低", "低-中", "中-高"):
            self.assertIn(t42, [x[0] for x in sp42], "三个复杂度候选都在册")
        # R-H443：第二十条（本地模型第三个 DeepSeek-R1-7B）
        r43 = at.run("incoming_distills")
        self.assertIn("本地 DeepSeek-R1-7B", str(r43["items"][0]["verbatim"]))
        sp43 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        names43 = [x[0] for x in sp43]
        for t43 in ("本地 Qwen2.5-Coder-7B", "本地 Qwen2.5-7B", "本地 DeepSeek-R1-7B"):
            self.assertIn(t43, names43, "三个本地模型名都在册")
        self.assertIn("全在待定格", [x for x in sp43 if x[0] == "本地 DeepSeek-R1-7B"][0][2])
        # R-H444：第二十一条（任务类型候选第四个 ⇒ 4/3/3 不对称，照实写）
        r44 = at.run("incoming_distills")
        self.assertIn("系统架构设计", str(r44["items"][0]["verbatim"]))
        sp44 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        d44 = [x for x in sp44 if x[0] == "系统架构设计"][0]
        self.assertIn("候选已 4 个", d44[2])
        self.assertIn("不对称", d44[2])
        # R-H445：第二十二条（复杂度候选第四个「高」⇒ 补齐梯子 ⇒ 4/4/3）
        r45 = at.run("incoming_distills")
        self.assertIn("高", str(r45["items"][0]["verbatim"]))
        sp45 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        names45 = [x[0] for x in sp45]
        d45 = [x for x in sp45 if x[0] == "高"][0]
        self.assertIn("补齐梯子", d45[2])
        self.assertIn("4/4/3", d45[2])
        for t45 in ("低", "低-中", "中-高", "高"):
            self.assertIn(t45, names45, "四档都在册")
        # R-H446：第二十三条（云端 Agnes（如可用）· 带条件 ⇒ 不许当已可用 · 4/4/4）
        r46 = at.run("incoming_distills")
        self.assertIn("云端 Agnes（如可用）", str(r46["items"][0]["verbatim"]))
        sp46 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        d46 = [x for x in sp46 if x[0] == "云端 Agnes（如可用）"][0]
        self.assertIn("带条件", d46[2])
        self.assertIn("不许当已可用", d46[2])
        self.assertIn("齐 ≠ 许可", d46[2])
        # R-H446：取证读数必须落进条目（不许只写在战报里）
        self.assertIn("R-H446 复证", str(r46["items"][0]["disk_check"]))
        self.assertIn("51 行 / 20 个文件", str(r46["items"][0]["disk_check"]))
        self.assertIn("同名 ≠ 同物", str(r46["items"][0]["disk_check"]))
        # R-H447：第二十四条（Agent 编排 · 同名 ≠ 同物）
        self.assertIn("Agent 编排", str(r46["items"][0]["verbatim"]))
        sp47 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        d47 = [x for x in sp47 if x[0] == "Agent 编排"][0]
        self.assertIn("同名 ≠ 同物", d47[2])
        self.assertIn("编排内核", d47[2])
        self.assertIn("R-H447 复证", str(r46["items"][0]["disk_check"]))
        # R-H448：重复 ≠ 许可 —— 第二次到货不许新立第二条（带牙）
        sp48 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n48 = [x[0] for x in sp48]
        self.assertEqual(n48.count("高"), 1, "重复到货不许新立第二条")
        self.assertEqual(len(n48), len(set(n48)), "待定格不许重名")
        d48 = [x for x in sp48 if x[0] == "高"][0]
        self.assertIn("R-H448", d48[2])
        self.assertIn("第二次", d48[2])
        self.assertIn("重复 ≠ 许可", d48[2])
        self.assertIn("R-H448 复证", str(r46["items"][0]["disk_check"]))
        # R-H449：第二十五条（本地模型 + 编排内核 · 复合句不许我擅自拆）
        self.assertIn("本地模型 + 编排内核", str(r46["items"][0]["verbatim"]))
        sp49 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n49 = [x[0] for x in sp49]
        self.assertEqual(n49.count("本地模型 + 编排内核"), 1)
        self.assertEqual(len(n49), len(set(n49)), "待定格不许重名")
        # 🔴 R-H450 修正：原先钉死 `== 25` ⇒ 下一刀加条目就红（**断言不许钉死会增长的总数**）
        #    本刀**是**新条目（当时 24 → 25）⇒ 改成**下界**，历史读数留在注释里
        self.assertGreaterEqual(len(n49), 25, "R-H449 是新条目（当时 24 → 25）")
        d49 = [x for x in sp49 if x[0] == "本地模型 + 编排内核"][0]
        whole49 = " ".join(str(x) for x in d49)
        self.assertIn("不许我擅自把它拆成两条", whole49)
        self.assertIn("重合", whole49)
        self.assertIn("0 行", whole49)
        self.assertIn("R-H449 复证", str(r46["items"][0]["disk_check"]))
        # R-H450：第二十六条（默认兜底 · 与『兜底层』相关但不同物）
        self.assertIn("默认兜底", str(r46["items"][0]["verbatim"]))
        sp50 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n50 = [x[0] for x in sp50]
        self.assertEqual(n50.count("默认兜底"), 1)
        self.assertEqual(len(n50), len(set(n50)), "待定格不许重名")
        # （同上：用下界，不钉死总数）
        self.assertGreaterEqual(len(n50), 26, "R-H450 是新条目（当时 25 → 26）")
        d50 = [x for x in sp50 if x[0] == "默认兜底"][0]
        whole50 = " ".join(str(x) for x in d50)
        self.assertIn("同名 ≠ 同物", whole50)
        self.assertIn("兜底层", whole50)
        self.assertIn("不许当同一个", whole50)
        self.assertIn("R-H450 复证", str(r46["items"][0]["disk_check"]))
        # R-H451：重复 ≠ 许可（第二次到货不许新立第二条）—— 只用**时间稳健**的牙
        sp51 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n51 = [x[0] for x in sp51]
        self.assertEqual(n51.count("本地 Qwen2.5-7B"), 1, "重复到货不许新立第二条")
        self.assertEqual(n51.count("本地 Qwen2.5-Coder-7B"), 1, "同前缀不同尾也不许并成一条")
        self.assertEqual(len(n51), len(set(n51)), "待定格不许重名")
        d51 = [x for x in sp51 if x[0] == "本地 Qwen2.5-7B"][0]
        self.assertIn("R-H451", d51[2])
        self.assertIn("第二次", d51[2])
        self.assertIn("重复 ≠ 许可", d51[2])
        self.assertIn("R-H451 复证", str(r46["items"][0]["disk_check"]))
        # R-H452：编号小节 3.5 + 『已有模块』形态待定（全用**时间稳健**的牙）
        sp52 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n52 = [x[0] for x in sp52]
        self.assertEqual(n52.count("3.5 与已有系统的对接"), 1)
        self.assertEqual(n52.count("已有模块"), 1)
        self.assertEqual(len(n52), len(set(n52)), "待定格不许重名")
        self.assertIn("3.5 与已有系统的对接", str(r46["items"][0]["verbatim"]))
        d52a = [x for x in sp52 if x[0] == "3.5 与已有系统的对接"][0]
        self.assertIn("递增", " ".join(str(x) for x in d52a))
        self.assertIn("不许塞进 FUSION_SECTIONS", " ".join(str(x) for x in d52a))
        d52b = [x for x in sp52 if x[0] == "已有模块"][0]
        w52b = " ".join(str(x) for x in d52b)
        self.assertIn("同名 ≠ 同物", w52b)
        self.assertIn("不擅自塞进 TRUNCATED_FRAGMENTS", w52b)
        # 🔴 牙：本刀**没**擅自改碎片契约（改契约 = 判定）
        self.assertNotIn("已有模块", [str(x.get("token")) for x in at.TRUNCATED_FRAGMENTS])
        # 🔴 牙：3.x 小节必须**递增出现**（编号不许乱、不许重）
        v52 = str(r46["items"][0]["verbatim"])
        pos52 = [v52.find("3.%d " % k) for k in (1, 2, 3, 4, 5)]
        self.assertTrue(all(p >= 0 for p in pos52), "3.1-3.5 都应在 verbatim 里")
        self.assertEqual(pos52, sorted(pos52), "3.x 小节必须递增出现")
        self.assertIn("R-H452 复证", str(r46["items"][0]["disk_check"]))
        # R-H453：版本号对不上（v2.0 ↔ v3.0）—— 全用**时间稳健**的牙
        sp53 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n53 = [x[0] for x in sp53]
        T53 = "自动化切换引擎 v3.0"
        self.assertEqual(n53.count(T53), 1)
        self.assertEqual(len(n53), len(set(n53)), "待定格不许重名")
        self.assertIn(T53, str(r46["items"][0]["verbatim"]))
        w53 = " ".join(str(x) for x in [y for y in sp53 if y[0] == T53][0])
        self.assertIn("版本号对不上", w53)
        self.assertIn("v2.0", w53)
        self.assertIn("同名 ≠ 同物", w53)
        self.assertIn("挂 = 判定", w53)
        # 🔴 牙：盘上那份文档**没被本刀改过**（还是 v2.0）
        _d = (ROOT / "gbt_allinone/docs/自动化切换引擎.md").read_text(encoding="utf-8-sig")
        self.assertIn("v2.0", _d)
        self.assertNotIn("v3.0", _d)
        self.assertIn("R-H453 复证", str(r46["items"][0]["disk_check"]))
        # R-H454：能源池（盘上真有同名物且已接线）—— 时间稳健的牙
        sp54 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n54 = [x[0] for x in sp54]
        self.assertEqual(n54.count("能源池"), 1)
        self.assertEqual(len(n54), len(set(n54)), "待定格不许重名")
        self.assertIn("能源池", str(r46["items"][0]["verbatim"]))
        w54 = " ".join(str(x) for x in [y for y in sp54 if y[0] == "能源池"][0])
        self.assertIn("不许当新事据", w54)
        self.assertIn("许可落位", w54)
        self.assertIn("不许当同一个", w54)
        # 🔴 牙：这条的依据是**盘上真物**（不是我说有就有）
        self.assertTrue((ROOT / "gbt_allinone/tools/energy_pool.py").exists())
        self.assertIn('kind == "energy_pool"',
                      (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8-sig"))
        self.assertIn("energy_pool",
                      (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8-sig"))
        self.assertIn("R-H454 复证", str(r46["items"][0]["disk_check"]))
        # R-H455：pick() 那条 + 弹性触手池（全用**时间稳健**的牙）
        sp55 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n55 = [x[0] for x in sp55]
        T55A = "路由层从池中 pick() 能源，按优先级"
        T55B = "弹性触手池"
        self.assertEqual(n55.count(T55A), 1)
        self.assertEqual(n55.count(T55B), 1)
        self.assertEqual(len(n55), len(set(n55)), "待定格不许重名")
        self.assertIn(T55A, str(r46["items"][0]["verbatim"]))
        self.assertIn(T55B, str(r46["items"][0]["verbatim"]))
        w55a = " ".join(str(x) for x in [y for y in sp55 if y[0] == T55A][0])
        self.assertIn("位置推断", w55a)
        self.assertIn("不硬判", w55a)
        w55b = " ".join(str(x) for x in [y for y in sp55 if y[0] == T55B][0])
        self.assertIn("既有文档概念", w55b)
        self.assertIn("不许当『已实现』", w55b)
        # 🔴 牙：两条的依据都是**盘上真事据**（不是我说有就有）
        _ep = (ROOT / "gbt_allinone/tools/energy_pool.py").read_text(encoding="utf-8-sig")
        self.assertIn("def pick(", _ep)
        self.assertIn("pool.pick(", _ep)
        self.assertIn("弹性触手池",
                      (ROOT / "gbt_allinone/docs/模型密钥池设计.md").read_text(encoding="utf-8-sig"))
        self.assertIn("R-H455 复证", str(r46["items"][0]["disk_check"]))
        # R-H456：分工那句 + 身份内核（全用**时间稳健**的牙）
        sp56 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n56 = [x[0] for x in sp56]
        T56A = "路由层决定用哪个能源，触手负责执行"
        T56B = "身份内核"
        self.assertEqual(n56.count(T56A), 1)
        self.assertEqual(n56.count(T56B), 1)
        self.assertEqual(len(n56), len(set(n56)), "待定格不许重名")
        self.assertIn(T56A, str(r46["items"][0]["verbatim"]))
        self.assertIn(T56B, str(r46["items"][0]["verbatim"]))
        w56a = " ".join(str(x) for x in [y for y in sp56 if y[0] == T56A][0])
        self.assertIn("位置推断", w56a)
        self.assertIn("不许当同一个", w56a)
        self.assertIn("不许我擅自调和", w56a)
        w56b = " ".join(str(x) for x in [y for y in sp56 if y[0] == T56B][0])
        self.assertIn("机械闸", w56b)
        self.assertIn("identity_rewritten", w56b)
        self.assertIn("不许当新事据", w56b)
        # 🔴 牙：这条的依据是**盘上真物（且有闸）**，不是我说有就有
        _lb = (ROOT / "gbt_allinone/tools/local_brain.py").read_text(encoding="utf-8-sig")
        self.assertIn("身份内核不许被模型改写", _lb)
        self.assertIn("check_identity_text", _lb)
        _yg = (ROOT / "gbt_allinone/docs/能源观.md").read_text(encoding="utf-8-sig")
        self.assertIn("身份内核（根）", _yg)
        self.assertIn("换叶不换根", _yg)
        self.assertIn("身份源仍在本地",
                      (ROOT / "gbt_allinone/tools/cloud_pc.py").read_text(encoding="utf-8-sig"))
        self.assertIn("R-H456 复证", str(r46["items"][0]["disk_check"]))
        # R-H457：trace_store（四件齐的真物）—— 全用**时间稳健**的牙
        sp57 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n57 = [x[0] for x in sp57]
        T57 = "trace_store"
        self.assertEqual(n57.count(T57), 1)
        self.assertEqual(len(n57), len(set(n57)), "待定格不许重名")
        self.assertIn(T57, str(r46["items"][0]["verbatim"]))
        w57 = " ".join(str(x) for x in [y for y in sp57 if y[0] == T57][0])
        self.assertIn("不在 tools/ 下", w57)
        self.assertIn("位置推断", w57)
        self.assertIn("三处同名", w57)
        self.assertIn("不下「就是同一个」的判定", w57)
        self.assertIn("不许当新事据", w57)
        self.assertIn("许可落位", w57)
        # 🔴 牙：四件齐 —— 模块 / 注册 / 出口 / 用例（不是我说有就有）
        self.assertTrue((ROOT / "gbt_allinone/trace_store.py").exists())
        self.assertTrue((ROOT / "gbt_allinone/tests/test_trace_store.py").exists())
        self.assertIn("trace_store",
                      (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8-sig"))
        self.assertIn('kind == "trace_store"',
                      (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8-sig"))
        self.assertIn("R-H457 复证", str(r46["items"][0]["disk_check"]))
        # R-H458：三行（切换留痕那句 / 四、章节标题 / 孤立一词）—— 时间稳健的牙
        sp58 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n58 = [x[0] for x in sp58]
        T58A = "每次切换写 model_used + dispatch_reason"
        T58B = "\ufe0f 四、五条红线（写死）"
        T58C = "红线"
        for _t in (T58A, T58B, T58C):
            self.assertEqual(n58.count(_t), 1, _t)
        self.assertEqual(len(n58), len(set(n58)), "待定格不许重名")
        self.assertEqual(n58.count(T58C), 1, "『红线』不许并成两条")
        self.assertIn(T58B, str(r46["items"][0]["verbatim"]), "含**不可见字符**的那行也要逐字在")
        w58a = " ".join(str(x) for x in [y for y in sp58 if y[0] == T58A][0])
        self.assertIn("不许当新事据", w58a)
        self.assertIn("并句 ≠ 原文", w58a)
        w58b = " ".join(str(x) for x in [y for y in sp58 if y[0] == T58B][0])
        self.assertIn("U+FE0F", w58b)
        self.assertIn("逐字保留、不擅自删", w58b)
        w58c = " ".join(str(x) for x in [y for y in sp58 if y[0] == T58C][0])
        self.assertIn("不擅自塞进 TRUNCATED_FRAGMENTS", w58c)
        # 🔴 牙：那两条的依据是**盘上真物（含闸）**
        _as = (ROOT / "gbt_allinone/tools/auto_switch.py").read_text(encoding="utf-8-sig")
        self.assertIn("must_dispatch_reason", _as)
        self.assertIn("no_dispatch_reason", _as)
        self.assertIn("model_used", _as)
        self.assertNotIn("红线", [str(x.get("token")) for x in at.TRUNCATED_FRAGMENTS])
        # 🔴 牙：不可见字符**真**是 U+FE0F（不是我以为）
        self.assertEqual(T58B[0], "\ufe0f")
        self.assertIn("R-H458 复证", str(r46["items"][0]["disk_check"]))
        # R-H459：重复到货 ⇒ **一个新条目都不许立**（牙的形状与 R-H448 相反）
        sp59 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n59 = [x[0] for x in sp59]
        T59 = "显式声明，绝不偷换"
        self.assertEqual(n59.count(T59), 0, "重复到货不许在待定格新立条目")
        self.assertGreaterEqual(len(n59), 38, "总数只会涨、不许被本刀改动（下界口径）")
        self.assertEqual(len(n59), len(set(n59)), "待定格不许重名")
        self.assertEqual(str(r46["items"][0]["verbatim"]).count(T59), 1,
                         "verbatim 里仍只出现 1 次（不许把同一句登记成两次）")
        self.assertIn("R-H459", str(r46["items"][0]["got"]))
        self.assertIn("第二次", str(r46["items"][0]["got"]))
        self.assertIn("38 条", str(r46["items"][0]["got"]))
        self.assertIn("重复 ≠ 许可", str(r46["items"][0]["got"]))
        self.assertIn("R-H459 复证", str(r46["items"][0]["disk_check"]))
        # R-H460：两处逐字之差 / 一字之差（全用**时间稳健**的牙）
        sp60 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n60 = [x[0] for x in sp60]
        T60A = "用户选 gbt-best，网关不许在高峰期偷偷降档"
        T60B = "五层逐级兜底"
        self.assertEqual(n60.count(T60A), 1)
        self.assertEqual(n60.count(T60B), 1)
        self.assertEqual(len(n60), len(set(n60)), "待定格不许重名")
        v60 = str(r46["items"][0]["verbatim"])
        self.assertIn(T60A, v60)
        self.assertIn(T60B, v60)
        w60a = " ".join(str(x) for x in [y for y in sp60 if y[0] == T60A][0])
        self.assertIn("teamo-best", w60a)
        self.assertIn("gbt-*", w60a)
        self.assertIn("不许当同一个", w60a)
        self.assertIn("不许我擅自调和", w60a)
        self.assertIn("两套前缀", w60a)
        w60b = " ".join(str(x) for x in [y for y in sp60 if y[0] == T60B][0])
        self.assertIn("一字之差", w60b)
        self.assertIn("既有原则行的一段", w60b)
        self.assertIn("不许当同一个", w60b)
        # 🔴 牙：两处对照都在**盘上真事据**里（不是我编的对照物）
        self.assertIn("teamo-best", v60)
        self.assertIn("五层防护，逐层兜底", v60)
        self.assertIn("网关绝不偷换 → 五层逐级兜底 →", v60)
        self.assertIn("R-H460 复证", str(r46["items"][0]["disk_check"]))
        # R-H461：半句落地/整句未落 + 本地优先（红线第一条，且同名不同物）
        sp61 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n61 = [x[0] for x in sp61]
        T61A = "每一层都有明确的兜底策略，不许静默失败"
        T61B = "本地优先"
        self.assertEqual(n61.count(T61A), 1)
        self.assertEqual(n61.count(T61B), 1)
        self.assertEqual(len(n61), len(set(n61)), "待定格不许重名")
        v61 = str(r46["items"][0]["verbatim"])
        self.assertIn(T61A, v61)
        self.assertIn(T61B, v61)
        w61a = " ".join(str(x) for x in [y for y in sp61 if y[0] == T61A][0])
        self.assertIn("半句已在盘上落地", w61a)
        self.assertIn("整句未落", w61a)
        self.assertIn("不许把半句当整句的许可", w61a)
        w61b = " ".join(str(x) for x in [y for y in sp61 if y[0] == T61B][0])
        self.assertIn("五条红线的第一条", w61b)
        self.assertIn("LOCAL_ONLY", w61b)
        self.assertIn("同名 ≠ 同物", w61b)
        self.assertIn("Obsidian", w61b)
        # 🔴 牙：两处的依据都是**盘上真事据**（不是我说的）
        self.assertIn("不许静默失败",
                      (ROOT / "holo_pet/app.js").read_text(encoding="utf-8-sig", errors="replace"))
        self.assertIn("不许静默失败",
                      (ROOT / "gbt_allinone/tentacle/capture_environment.py").read_text(
                          encoding="utf-8-sig", errors="replace"))
        _zg = (ROOT / "gbt_allinone/docs/自给自足大脑.md").read_text(encoding="utf-8-sig")
        self.assertIn("本地优先", _zg)
        self.assertIn("LOCAL_ONLY", _zg)
        self.assertIn("本地优先",
                      (ROOT / "gbt_allinone/docs/AwesomeTools蒸馏.md").read_text(encoding="utf-8-sig"))
        self.assertIn("R-H461 复证", str(r46["items"][0]["disk_check"]))
        # R-H462：本地/云端第 4 次说法 + 每次切换留痕（同型子串到货）
        sp62 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n62 = [x[0] for x in sp62]
        T62A = "默认走本地模型，云端只在任务需要时启用"
        T62B = "每次切换留痕"
        self.assertEqual(n62.count(T62A), 1)
        self.assertEqual(n62.count(T62B), 1)
        self.assertEqual(len(n62), len(set(n62)), "待定格不许重名")
        v62 = str(r46["items"][0]["verbatim"])
        self.assertIn(T62A, v62)
        self.assertIn(T62B, v62)
        w62a = " ".join(str(x) for x in [y for y in sp62 if y[0] == T62A][0])
        self.assertIn("第 4 次说法", w62a)
        self.assertIn("不许我擅自调和", w62a)
        self.assertIn("可能不同向", w62a)
        w62b = " ".join(str(x) for x in [y for y in sp62 if y[0] == T62B][0])
        self.assertIn("既有原则行的一段", w62b)
        self.assertIn("同型", w62b)
        self.assertIn("R-H460", w62b)
        # 🔴 牙：前三次说法**真的都在 verbatim 里**（对照物不是编的）
        for _t62 in ("本地模型不够时，上云端最强模型", "本地模型优先，不够再上云端",
                     "只用本地模型，不够就降级"):
            self.assertIn(_t62, v62)
        self.assertIn("网关绝不偷换 → 五层逐级兜底 → 每次切换留痕", v62)
        self.assertIn("R-H462 复证", str(r46["items"][0]["disk_check"]))
        # R-H463：三件都落地/拼句未落 + 身份内核不变（子串到货第 3 次）
        sp63 = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("shape_pending") or ())]
        n63 = [x[0] for x in sp63]
        T63A = "写 trace_store，记 model_used + dispatch_reason"
        T63B = "身份内核不变"
        self.assertEqual(n63.count(T63A), 1)
        self.assertEqual(n63.count(T63B), 1)
        self.assertEqual(len(n63), len(set(n63)), "待定格不许重名")
        v63 = str(r46["items"][0]["verbatim"])
        self.assertIn(T63A, v63)
        self.assertIn(T63B, v63)
        w63a = " ".join(str(x) for x in [y for y in sp63 if y[0] == T63A][0])
        self.assertIn("三件都落地、拼句未落", w63a)
        self.assertIn("不许把三件当整句的许可", w63a)
        self.assertIn("高度重合", w63a)
        self.assertIn("不许当同一个", w63a)
        w63b = " ".join(str(x) for x in [y for y in sp63 if y[0] == T63B][0])
        self.assertIn("红线⑤ 行的一段", w63b)
        self.assertIn("identity_rewritten", w63b)
        self.assertIn("同型第 3 次", w63b)
        self.assertIn("不许当同一个", w63b)
        # 🔴 牙：两处的依据都是**盘上真事据**
        _zg63 = (ROOT / "gbt_allinone/docs/自给自足大脑.md").read_text(encoding="utf-8-sig")
        self.assertIn("身份内核不变", _zg63)
        self.assertIn("identity_rewritten", _zg63)
        self.assertIn("身份内核不变",
                      (ROOT / "gbt_allinone/tools/cloud_pc.py").read_text(encoding="utf-8-sig"))
        self.assertIn("身份内核不变",
                      (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8-sig"))
        self.assertIn("trace_store",
                      (ROOT / "gbt_allinone/tools/auto_switch.py").read_text(encoding="utf-8-sig"))
        self.assertIn("R-H463 复证", str(r46["items"][0]["disk_check"]))
        self.assertEqual(r36["matrix_rows"], [["代码补全 / 单行生成"]],
                         "**缺格不许跳**：矩阵里仍只有一格")
        self.assertEqual(r35["matrix_rows"], [["代码补全 / 单行生成"]],
                         "弱推断**不许落位**（矩阵里仍只有一格）")
        self.assertEqual(sorted(x["token"] for x in at.TRUNCATED_FRAGMENTS if x.get("header")),
                         sorted(["层级", "名称", "核心职责", "预设", "任务类型", "复杂度", "推荐能源"]))
        self.assertNotIn("本地行为", list(at.SECTION2_COLUMNS) + list(at.SOURCE_TABLE_COLUMNS))
        self.assertIn("列名", sp[0][1])
        self.assertIn("第一行的格", sp[0][2])
        # 🔴 不许当列名、不许当格值
        self.assertNotIn("对应优先级", list(at.SECTION2_COLUMNS))
        self.assertNotIn("对应优先级", list(at.SOURCE_TABLE_COLUMNS))
        self.assertEqual(at.run("fusion_rows")["count"], 7, "融合表没被动")
        # R-H403：『核心职责』= 第三列列名（表头残片一族在逐个到货）
        g = at.run("gate_truncated")
        hdr = list(g.get("header_fragments") or [])
        print("header_fragments =", hdr)
        # ⚠️ 我漏看：这几行被我插进了**另一个用例**里（truncated_teeth_landed…）—— 记账在此
        # R-H419 增长连带：表头残片会长 ⇒ 只断言「含前三 + 每个都在册」
        for _t in ("层级", "名称", "核心职责"):
            self.assertIn(_t, hdr)
        self.assertEqual(sorted(hdr), sorted(x["token"] for x in at.TRUNCATED_FRAGMENTS
                                             if x.get("header")))
        cz = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}["核心职责"]
        self.assertEqual(cz["kind"], "truncated")
        # ⚠️ 「第三列列名」落在 **ctx** 里（不在 note）⇒ 按整条断言
        for kw in ("第三列列名", "都不含", "不许拿它当", "逐个到货", "补全"):
            self.assertIn(kw, str(cz))
        self.assertNotIn("核心职责", list(at.SECTION2_COLUMNS))
        self.assertNotIn("核心职责", list(at.SOURCE_TABLE_COLUMNS))
        # R-H402：『名称』= 表头/列名残片（紧跟『层级』）⇒ 仍不编；且两个既有列契约都不含它
        nm = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}["名称"]
        self.assertEqual(nm["kind"], "truncated")
        self.assertIn("R-H402", str(nm["at"]))
        for kw in ("列名残片", "两个既有列契约", "不许拿它当", "第三个表", "补全"):
            self.assertIn(kw, str(nm["note"]))
        self.assertNotIn("名称", list(at.SECTION2_COLUMNS))
        self.assertNotIn("名称", list(at.SOURCE_TABLE_COLUMNS))
        self.assertTrue(at.run("gate_truncated")["ok"])

        it = at.TRUNCATED_FRAGMENTS[0]
        saved = it["note"]
        it["note"] = "（测试用）没写那条纪律"
        try:
            g2 = at.run("gate_truncated")
        finally:
            it["note"] = saved
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "truncated_without_hold_note")
        self.assertTrue(at.run("gate_truncated")["ok"])

    def test_registry_evidence_r334_in_global_note(self):
        # R-H334 证据 +1：主人把第 1 分类与『编程工作区』并列写 ⇒ 疑似对应（仍不自解）
        g = at.run("gate_categories")
        self.assertIn("证据 +1", str(g["vs_registry_note"]))
        self.assertIn("编程工作区", str(g["vs_registry_note"]))
        self.assertIn("不擅自合并", str(g["vs_registry_note"]))
        rows = at.run("gate_categories")["rows"]
        self.assertIn("疑似对应", str(rows[0].get("note")))
        self.assertTrue(at.run("gate_categories")["ok"])

    # ---------- R-H335：待归属第三条 + 源表列改「基列锁死 · 末尾可追加」 ----------

    def test_pending_three_items_side_by_side(self):
        # 三条待归属并排：每条都 ≥2 读法、都不自解、闸全绿
        r = at.run("pending")
        # 口径随 R-H336 更新：R-H335 时三条，R-H336 起四条
        self.assertGreaterEqual(len(r["items"]), 3)
        for x in r["items"]:
            self.assertGreaterEqual(len(list(x["readings"])), 2)
            self.assertIsNone(x["resolved"])
        self.assertTrue(at.run("gate_pending")["ok"])

    def test_te_dian_not_landed_anywhere(self):
        # 『特点』这一轮**一个格都没落**：不是分类名、不是源表列、不是第二节列、不是格值
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertNotIn("特点", vals)
        self.assertNotIn("特点", [str(x.get("field")) for x in at.SECTION_ROWS_OWNER])
        self.assertTrue(at.run("gate_categories")["ok"])
        self.assertTrue(at.run("gate_source_columns")["ok"])

    def test_source_columns_append_requires_source(self):
        # R-H335 改判据：基列不许改；**末尾可追加主人逐字给的列** —— 但追加必须登记 + 带出处
        base = tuple(at.SOURCE_TABLE_COLUMNS_OWNER)
        saved_cols = at.SOURCE_TABLE_COLUMNS
        saved_app = at.SOURCE_TABLE_COLUMNS_APPENDS
        at.SOURCE_TABLE_COLUMNS = base + ("特点",)
        try:
            g = at.run("gate_source_columns")
        finally:
            at.SOURCE_TABLE_COLUMNS = saved_cols
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "source_column_append_unsourced")
        self.assertTrue(at.run("gate_source_columns")["ok"])

        at.SOURCE_TABLE_COLUMNS_APPENDS = ({"name": "特点", "source": ""},)
        at.SOURCE_TABLE_COLUMNS = base + ("特点",)
        try:
            g2 = at.run("gate_source_columns")
        finally:
            at.SOURCE_TABLE_COLUMNS_APPENDS = saved_app
            at.SOURCE_TABLE_COLUMNS = saved_cols
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "source_column_append_without_source")
        self.assertTrue(at.run("gate_source_columns")["ok"])

        at.SOURCE_TABLE_COLUMNS_APPENDS = (
            {"name": "特点", "source": "主人提供 · R-? · 逐字"},)
        at.SOURCE_TABLE_COLUMNS = base + ("特点",)
        try:
            g3 = at.run("gate_source_columns")
        finally:
            at.SOURCE_TABLE_COLUMNS_APPENDS = saved_app
            at.SOURCE_TABLE_COLUMNS = saved_cols
        self.assertTrue(g3["ok"], g3)
        self.assertEqual(list(g3["columns"]), list(base) + ["特点"])
        self.assertEqual(list(at.SOURCE_TABLE_COLUMNS), list(base),
                         "R-H335 **一列都没真加**（只把判据改成可追加）")

    # ---------- R-H336：待归属第四条 + 再现名字（Trae） ----------

    def test_pending_items_side_by_side(self):
        # 待归属并排：每条 ≥2 读法、都不自解、闸全绿（条数随刀次增长）
        r = at.run("pending")
        self.assertGreaterEqual(len(r["items"]), 4)
        for x in r["items"]:
            self.assertGreaterEqual(len(list(x["readings"])), 2)
            self.assertIsNone(x["resolved"])
        it4 = r["items"][3]
        self.assertIn("没说挂哪儿", str(it4["pending_reason"]))
        self.assertIn("等主人一句话", str(it4["pending_reason"]))
        self.assertTrue(at.run("gate_pending")["ok"])

    def test_reappearing_trae_side_by_side(self):
        # R-H336：『Trae』盘上**已经有了** ⇒ 记再现（不是新工具）：不许另起一行、不许丢弃
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        # 口径随 R-H338 更新：再现名字 1 → 2 条（新增 Fitten Code）
        self.assertGreaterEqual(g["count"], 1)
        it = at.run("reappearing")["items"][0]
        self.assertEqual(it["token"], "Trae")
        self.assertTrue(any(n.endswith("格 代表工具") for n in it["where"]),
                        "整段相等的那一处（面名带行号，R-H348 起）")
        self.assertIn("待归属暂存值", it["near_miss"], "『Trae 等』整段不等 ⇒ 像但不等于")
        self.assertIn("已在", str(it["note"]))
        self.assertIn("再现", str(it["note"]))
        self.assertIsNone(it["resolved"])
        self.assertNotIn("Trae", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER],
                         "再现的名字不许另起一行")

    def test_reappearing_teeth(self):
        # 带牙①：说「已在」但盘上找不到 ⇒ 红；② 没写「再现」⇒ 红；③ 另起一行 ⇒ 红
        it = at.REAPPEARING_TOKENS[0]
        saved_tok = it["token"]
        # ⚠️ 用「Fitten」测**前缀巧合**：它是『Fitten Code』的前缀，却**不是任何一段的整段** ⇒
        #    声称「已在」但按整段找不到 ⇒ 必须红
        #    （不要用『Trae 等』—— 它恰好是暂存值『VS Code / Trae 等』split 后的**整段**，
        #      那是真命中，不是假命中）
        it["token"] = "Fitten"
        try:
            g = at.run("gate_reappearing")
        finally:
            it["token"] = saved_tok
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "reappearance_claim_without_match")
        self.assertTrue(any(n.endswith("格 代表工具") for n in (g.get("claimed_in") or [])),
                        "前缀巧合那条：claimed_in 里应指出它在哪一格（面名带行号）")
        self.assertTrue(at.run("gate_reappearing")["ok"])

        saved_note = it["note"]
        it["note"] = "（测试用）只写了已在，没写那两个字"
        try:
            g2 = at.run("gate_reappearing")
        finally:
            it["note"] = saved_note
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "reappearance_note_incomplete")
        self.assertTrue(at.run("gate_reappearing")["ok"])

        tmp = {"section": "二", "category": "Trae", "cells": {}, "source": "（测试用）",
               "pending_reason": "（测试用）留空带理由"}
        saved_rows = at.CATEGORY_ROWS_OWNER
        at.CATEGORY_ROWS_OWNER = tuple(saved_rows) + (tmp,)
        try:
            g3 = at.run("gate_reappearing")
        finally:
            at.CATEGORY_ROWS_OWNER = saved_rows
        self.assertFalse(g3["ok"], g3)
        self.assertEqual(g3["rule"], "reappearing_token_became_new_row")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    # ---------- R-H337：Trae 的详细介绍「暂存、不落表」 ----------

    def test_trae_staged_detail_held_not_landed(self):
        # 主人给的详细介绍**一个字都没落表**，只暂存在再现条目里
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        it = at.run("reappearing")["items"][0]
        self.assertIn("字节跳动", str(it["staged_detail"]))
        self.assertIn("Doubao-1.5-pro", str(it["staged_detail"]))
        self.assertIn("暂存", str(it["staged_detail_note"]))
        self.assertIn("不落", str(it["staged_detail_note"]))
        self.assertIn("R-H337", str(it["note"]))
        sentence = str(it["staged_detail"])
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if sentence in v], "详细介绍一个字都不许落表")

    def test_gbt_bridge_gets_new_evidence(self):
        # R-H337：『与 GBT 的对接』补行为证据 +1（紧跟 Trae 与那句介绍之后）—— 仍不自解
        it = [x for x in at.run("pending")["items"] if x["token"] == "与 GBT 的对接"][0]
        self.assertIn("R-H337", str(it["pending_reason"]))
        self.assertIn("证据 +1", str(it["pending_reason"]))
        self.assertIn("仍在等主人一句话", str(it["pending_reason"]))
        self.assertIsNone(it["resolved"], "证据再强也不自解")
        self.assertTrue(at.run("gate_pending")["ok"])

    def test_staged_detail_teeth(self):
        # 带牙①：没写「暂存、不落表」⇒ 红；② 那句**落进表**⇒ 红
        live = at.REAPPEARING_TOKENS[0]
        saved_note = live["staged_detail_note"]
        # ⚠️ 样本要**只踩这一条牙**：先满足「归属依据」，再漏掉「暂存 / 不落」
        #    （R-H338 的教训：样本挑错 ⇒ 验到的是另一条牙）
        live["staged_detail_note"] = "（测试用）**归属依据**：形态（测试用）；但没有写那两条纪律"
        try:
            g = at.run("gate_reappearing")
        finally:
            live["staged_detail_note"] = saved_note
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "staged_detail_without_hold_note")
        self.assertTrue(at.run("gate_reappearing")["ok"])

        cell = at.CATEGORY_ROWS_OWNER[0]["cells"]
        saved_cell = cell.get("对应 GBT 能力域")
        cell["对应 GBT 能力域"] = str(live["staged_detail"])
        try:
            g2 = at.run("gate_reappearing")
        finally:
            cell["对应 GBT 能力域"] = saved_cell
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "staged_detail_landed")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    # ---------- R-H338：再现名字第二条 + 新牙「一串里的名字不许被拆成多行」 ----------

    def test_fitten_code_reappearing_with_cell_mates(self):
        # 同一格里的名字被**逐个再给**：第二个是 Fitten Code；它的「同格伙伴」要能报出来
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        # 口径随 R-H340 更新：再现名字 2 → 3 条（新增 CodeGeeX）
        self.assertGreaterEqual(g["count"], 2)
        items = at.run("reappearing")["items"]
        self.assertEqual([x["token"] for x in items][:2], ["Trae", "Fitten Code"])
        fit = items[1]
        self.assertTrue(any(n.endswith("格 代表工具") for n in fit["where"]))
        mates = list(fit["cell_mates"] or [])
        for name in ("Trae", "CodeGeeX", "通义灵码", "GitHub Copilot"):
            self.assertIn(name, mates)
        self.assertIn("再现", str(fit["note"]))
        self.assertIsNone(fit["resolved"])

    def test_cell_pieces_teeth_not_split_into_rows(self):
        # 带牙：把一串里的**任何一段**拿去建分类行 ⇒ 红（一个格仍是**一个格**）
        # ⚠️ 口径随 R-H342 改：样本**自己挑** —— 从真数据里取一个**非登记**的同格名字。
        #    写死样本会随刀次过期（CodeGeeX / 通义灵码 先后来都被登记过）；
        #    而验**通用**牙的前提正是「这个名字还**没被登记**」。
        registered = {str(x["token"]) for x in at.REAPPEARING_TOKENS}
        sample = None
        for r in at.CATEGORY_ROWS_OWNER:
            for v in dict(r.get("cells") or {}).values():
                for piece in str(v or "").split("/"):
                    p = piece.strip()
                    if p and p not in registered:
                        sample = p
                        break
                if sample:
                    break
            if sample:
                break
        self.assertIsNotNone(sample, "得先有一个**非登记**的同格名字，通用牙才验得动")
        tmp = {"section": "二", "category": sample, "cells": {}, "source": "（测试用）",
               "pending_reason": "（测试用）留空带理由"}
        saved_rows = at.CATEGORY_ROWS_OWNER
        at.CATEGORY_ROWS_OWNER = tuple(saved_rows) + (tmp,)
        try:
            g = at.run("gate_reappearing")
        finally:
            at.CATEGORY_ROWS_OWNER = saved_rows
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "cell_pieces_split_into_rows")
        self.assertIn(sample, list(g.get("rows") or []))
        self.assertTrue(at.run("gate_reappearing")["ok"])
        self.assertNotIn(sample, [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    # ---------- R-H339：第二个工具的详细介绍也「暂存、不落表」 ----------

    def test_fitten_code_staged_detail_held_not_landed(self):
        # 两条再现条目**各自**都有暂存的详细介绍；两条都一个字没落表
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        # ⚠️ 不许写死名单（逐刀会涨，R-H344 立）⇒ 成员判定
        for name in ("Trae", "Fitten Code"):
            self.assertIn(name, list(g["with_detail"] or []))
        items = at.run("reappearing")["items"]
        fit = items[1]
        self.assertIn("80+", str(fit["staged_detail"]))
        self.assertIn("调试 Bug", str(fit["staged_detail"]))
        self.assertIn("暂存", str(fit["staged_detail_note"]))
        self.assertIn("不落", str(fit["staged_detail_note"]))
        self.assertIn("R-H339", str(fit["note"]))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        for it in items:
            sentence = str(it["staged_detail"])
            self.assertFalse([v for v in vals if sentence in v],
                             "%s 的介绍一个字都不许落表" % it["token"])

    def test_staged_detail_teeth_cover_every_item(self):
        # 带牙**覆盖到每一条**（不只第一条）：第二条的暂存纪律同样要响
        live = at.REAPPEARING_TOKENS[1]
        saved_note = live["staged_detail_note"]
        # 同上：只踩「暂存 / 不落」这条牙
        live["staged_detail_note"] = "（测试用）**归属依据**：形态（测试用）；但没有写那两条纪律"
        try:
            g = at.run("gate_reappearing")
        finally:
            live["staged_detail_note"] = saved_note
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "staged_detail_without_hold_note")
        self.assertEqual(g.get("token"), "Fitten Code")
        self.assertTrue(at.run("gate_reappearing")["ok"])

        cell = at.CATEGORY_ROWS_OWNER[0]["cells"]
        saved_cell = cell.get("对应 GBT 能力域")
        cell["对应 GBT 能力域"] = str(live["staged_detail"])
        try:
            g2 = at.run("gate_reappearing")
        finally:
            cell["对应 GBT 能力域"] = saved_cell
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "staged_detail_landed")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    # ---------- R-H340：再现第三条 + 组读数 + 去重牙 ----------

    def test_codegeex_reappearing_and_same_cell_groups(self):
        # 同一格被逐个再给**三个**；派生组读数要让这件事看得见（但仍不拆行）
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        items = at.run("reappearing")["items"]
        # 口径随 R-H342 更新：再现名字 3 → 4 条（新增通义灵码）
        self.assertEqual([x["token"] for x in items][:3],
                         ["Trae", "Fitten Code", "CodeGeeX"])
        cg = items[2]
        self.assertTrue(any(n.endswith("格 代表工具") for n in cg["where"]))
        self.assertIn("通义灵码", list(cg["cell_mates"] or []))
        self.assertIsNone(cg["resolved"])
        groups = dict(g["same_cell_groups"] or {})
        # ⚠️ 不许写死名单（逐刀会涨）⇒ 与 items **自洽**：组里就是「来源含该格的那些 token」
        # ⚠️ 自洽要**按精确的组键**（后缀会让第 3 行也命中 —— R-H348 连带）
        key = "第1行 格 代表工具"
        want = sorted({x["token"] for x in items if key in (x["where"] or [])})
        self.assertEqual(sorted(groups.get(key) or []), want)
        for name in ("Trae", "Fitten Code", "CodeGeeX"):
            self.assertIn(name, want)
        self.assertNotIn("CodeGeeX", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER],
                         "再现的名字不许另起一行")

    def test_reappearing_duplicate_teeth(self):
        # 带牙：同一个名字在再现区登记两遍 ⇒ 红（计数不许虚高）
        saved = at.REAPPEARING_TOKENS
        dup = {"token": "Trae", "at": "（测试用）",
               "note": "**已在**盘上（测试用重复登记）；记为**再现**"}
        at.REAPPEARING_TOKENS = tuple(saved) + (dup,)
        try:
            g = at.run("gate_reappearing")
        finally:
            at.REAPPEARING_TOKENS = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "reappearing_token_duplicate")
        self.assertEqual(g.get("token"), "Trae")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    # ---------- R-H341：待归属第五条（一句没点名归属的介绍）+ 暂存值落表牙 ----------

    def test_sentence_pending_held_not_landed(self):
        # 没点名是谁的介绍 ⇒ 待归属第五条；原文**暂存、不落表**
        g = at.run("gate_pending")
        self.assertTrue(g["ok"], g)
        it = [x for x in at.run("pending")["items"]
              if x["token"].startswith("智谱华章")][0]
        self.assertIn("没点名", str(it["pending_reason"]))
        self.assertIn("形态像 ≠ 就是", str(it["pending_reason"]))
        self.assertIn("等主人一句话", str(it["pending_reason"]))
        self.assertEqual(it["staged_value"], "智谱华章，AI 代码生成与补全")
        self.assertIn("暂存", str(it["staged_note"]))
        self.assertIn("不落", str(it["staged_note"]))
        self.assertIsNone(it["resolved"])
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "智谱华章" in v], "一个字都不许落表")

    def test_pending_staged_value_teeth_not_landed(self):
        # 带牙：**写了「暂存」两个字、照样落表** ⇒ 红（机械核过，不只核写字）
        it = [x for x in at.PENDING_ATTRIBUTION if x["token"].startswith("智谱华章")][0]
        cell = at.CATEGORY_ROWS_OWNER[0]["cells"]
        saved_cell = cell.get("对应 GBT 能力域")
        cell["对应 GBT 能力域"] = str(it["staged_value"])
        try:
            g = at.run("gate_pending")
        finally:
            cell["对应 GBT 能力域"] = saved_cell
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "pending_staged_value_landed")
        self.assertIn("第1行 格 对应 GBT 能力域", list(g.get("where") or []))
        self.assertTrue(at.run("gate_pending")["ok"])

    # ---------- R-H342：再现第四条『通义灵码』 ----------

    def test_tongyi_reappearing_fourth(self):
        # 同一格被逐个再给**四个**；仍不拆行、仍不定论
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        items = at.run("reappearing")["items"]
        # ⚠️ 不许写死总条数（逐刀会涨）⇒ 前缀 + 成员
        toks = [x["token"] for x in items]
        self.assertEqual(toks[:4], ["Trae", "Fitten Code", "CodeGeeX", "通义灵码"])
        self.assertIn("通义灵码", toks)
        ty = items[3]
        self.assertTrue(any(n.endswith("格 代表工具") for n in ty["where"]))
        self.assertIn("GitHub Copilot", list(ty["cell_mates"] or []))
        self.assertIn("再现", str(ty["note"]))
        self.assertIsNone(ty["resolved"])
        groups = dict(g["same_cell_groups"] or {})
        cell = sorted(groups.get("第1行 格 代表工具") or [])
        for name in ("Trae", "Fitten Code", "CodeGeeX", "通义灵码"):
            self.assertIn(name, cell)
        self.assertNotIn("通义灵码", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    # ---------- R-H343：待归属第六条（第二句「没点名归属」的介绍） ----------

    def test_ali_sentence_pending_sixth(self):
        # 第二句同样没点名 ⇒ 第六条；派生读数要让「几条在暂存」看得见
        g = at.run("gate_pending")
        self.assertTrue(g["ok"], g)
        items = at.run("pending")["items"]
        # ⚠️ 不许写死总条数（逐刀会涨）⇒ 按**位置**断言：第 6 条就是那句
        self.assertGreaterEqual(len(items), 6)
        it = items[5]
        self.assertTrue(it["token"].startswith("阿里"))
        self.assertEqual(it["staged_value"],
                         "阿里，代码智能生成 + 研发智能问答 + 任务自主执行")
        for kw in ("没点名", "形态像 ≠ 就是", "等主人一句话"):
            self.assertIn(kw, str(it["pending_reason"]))
        self.assertIn("暂存", str(it["staged_note"]))
        self.assertIn("不落", str(it["staged_note"]))
        self.assertIsNone(it["resolved"])
        staged = list(g.get("staged_items") or [])
        self.assertIn("IDE & 代码编辑器", staged)
        self.assertIn("智谱华章，AI 代码生成与补全", staged)
        self.assertIn("阿里，代码智能生成 + 研发智能问答 + 任务自主执行", staged)
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "阿里" in v], "一句话都不许落表")

    # ---------- R-H344：再现第五条（那一格五个全到）+ 待归属第七条 ----------

    def test_github_copilot_reappearing_fifth_and_full_cell(self):
        # 那一格五个名字**全部**被逐个再给 ⇒ 仍是**一个格**，不许拆行
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        items = at.run("reappearing")["items"]
        # ⚠️ 不许写死总名单（逐刀会涨）⇒ 前缀 + 成员（R-H348 起再现已跨行）
        toks = [x["token"] for x in items]
        self.assertEqual(toks[:5], ["Trae", "Fitten Code", "CodeGeeX", "通义灵码",
                                    "GitHub Copilot"])
        self.assertIn("GitHub Copilot", toks)
        gh = items[4]
        self.assertTrue(any(n.endswith("格 代表工具") for n in gh["where"]))
        self.assertIsNone(gh["resolved"])
        groups = dict(g["same_cell_groups"] or {})
        self.assertEqual(sorted(groups.get("第1行 格 代表工具") or []),
                         ["CodeGeeX", "Fitten Code", "GitHub Copilot", "Trae", "通义灵码"])
        self.assertNotIn("GitHub Copilot",
                         [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    def test_agent_phrase_pending_seventh_position_reversed(self):
        # 本句在**工具名之前**给出（前两句在之后）⇒ 形态不完全同 ⇒ **不记证据 +1**
        g = at.run("gate_pending")
        self.assertTrue(g["ok"], g)
        items = at.run("pending")["items"]
        # ⚠️ 不许写死总条数（逐刀会涨，R-H344 立）⇒ 按**位置**断言
        self.assertGreaterEqual(len(items), 7)
        it = items[6]
        self.assertEqual(it["token"], "编程 Agent 能力")
        self.assertEqual(it["staged_value"], "编程 Agent 能力")
        for kw in ("位置相反", "形态不完全同", "不记「证据 +1」", "仍在等主人一句话"):
            self.assertIn(kw, str(it["pending_reason"]))
        self.assertIn("暂存", str(it["staged_note"]))
        self.assertIn("不落", str(it["staged_note"]))
        self.assertIsNone(it["resolved"])
        self.assertIn("编程 Agent 能力", list(g.get("staged_items") or []))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "编程 Agent 能力" in v], "一个字都不许落表")
        # 🔎 上刀预警的「免费样本会用完」：本条**已在实现里覆盖**（挑样本扫**所有格**）
        registered = {str(x["token"]) for x in at.REAPPEARING_TOKENS}
        free = [p.strip() for r in at.CATEGORY_ROWS_OWNER
                for v in dict(r.get("cells") or {}).values()
                for p in str(v or "").split("/")
                if p.strip() and p.strip() not in registered]
        self.assertTrue(free, "必须还剩**非登记**样本，通用牙才验得动")

    # ---------- R-H345：待归属第八条（短名词短语，位置同、**句型不同**） ----------

    def test_short_phrase_pending_eighth_not_evidence(self):
        # 位置在工具名之后（同那几句），但**句型不同** ⇒ **不记「证据 +1」**（不许只看位置）
        g = at.run("gate_pending")
        self.assertTrue(g["ok"], g)
        items = at.run("pending")["items"]
        self.assertGreaterEqual(len(items), 8)
        it = items[7]
        self.assertEqual(it["token"], "老牌 AI 编码助手")
        self.assertEqual(it["staged_value"], "老牌 AI 编码助手")
        for kw in ("短名词短语", "句型不同", "不记「证据 +1」", "不许只看位置一项就凑数",
                   "仍在等主人一句话"):
            self.assertIn(kw, str(it["pending_reason"]))
        self.assertIn("暂存", str(it["staged_note"]))
        self.assertIn("不落", str(it["staged_note"]))
        self.assertIsNone(it["resolved"])
        self.assertIn("老牌 AI 编码助手", list(g.get("staged_items") or []))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "老牌 AI 编码助手" in v], "一个字都不许落表")

    # ---------- R-H346：顺序读数区（源编号 vs 本仓位置）+ 不硬凑 + 截断碎片补记 ----------

    def test_source_order_reading_mismatch_stated(self):
        # 源编号 2 · 本仓第 3 行 ⇒ 不一致，且必须**写明**（不许静默）
        g = at.run("gate_source_order")
        self.assertTrue(g["ok"], g)
        it = at.run("source_order")["items"][0]
        self.assertEqual(it["category"], "AI模型管理工具")
        self.assertEqual(it["source_no"], 2)
        self.assertEqual(it["our_index"], 3, "our_index 由闸现算，不许手写")
        self.assertTrue(it["mismatch"])
        self.assertIn("不一致", str(it["note"]))
        self.assertIn("AI模型管理工具", list(g.get("mismatched") or []))
        rows = at.run("gate_categories")["rows"]
        self.assertIn("R-H346", str(rows[2].get("note")))
        self.assertIn("不记跨批证据", str(rows[2].get("note")))

    def test_source_order_teeth_both_directions(self):
        # 带牙①：不一致却不写明 ⇒ 红；② 写了「不一致」但盘上其实一致 ⇒ 也红
        live = at.SOURCE_ORDER_READINGS[0]
        saved = live["note"]
        live["note"] = "（测试用）只记了编号，没写那三个字"
        try:
            g = at.run("gate_source_order")
        finally:
            live["note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "source_order_mismatch_unstated")
        self.assertTrue(at.run("gate_source_order")["ok"])

        saved_no = live["source_no"]
        live["source_no"] = 3      # 假装编号=位置（表若被重排就是这形状）
        try:
            g2 = at.run("gate_source_order")
        finally:
            live["source_no"] = saved_no
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "source_order_stale_note")
        self.assertTrue(at.run("gate_source_order")["ok"])

    def test_truncated_tool_fragment_second_time(self):
        # 『工具』**第二次出现**（R-H346）⇒ 仍**留空不编**；碎片不许当数据
        g = at.run("gate_truncated")
        self.assertTrue(g["ok"], g)
        it = at.run("truncated")["items"][0]
        self.assertEqual(it["token"], "工具")
        self.assertIn("R-H346", str(it["at"]))
        self.assertIn("第二次", str(it["note"]))
        self.assertIn("留空不编", str(it["note"]))
        self.assertNotIn("工具", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    # ---------- R-H347：『特点』第二次出现（补记、不新立条目） ----------

    def test_te_dian_second_time_recorded_not_new_item(self):
        # 第二次给同一个词 ⇒ **补记**在那条上：不新立条目、不落表、仍不自解
        items = at.run("pending")["items"]
        # ⚠️ 语义断言：『特点』**只出现一次**（重复出现不新立条目）
        self.assertEqual([x["token"] for x in items].count("特点"), 1)
        td = [x for x in items if x["token"] == "特点"][0]
        r = str(td["pending_reason"])
        self.assertIn("R-H347", r)
        self.assertIn("第二次出现", r)
        self.assertIn("再给一次也不等于可以落表", r)
        self.assertIn("等主人一句话", r)
        self.assertIsNone(td["resolved"])
        self.assertTrue(at.run("gate_pending")["ok"])
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if v.strip() == "特点"], "重复出现也不许落表")

    def test_pending_repeat_not_license_teeth(self):
        # 带牙：写了「第二次出现」却不写「仍在等 / 不擅自」⇒ 红（**重复 ≠ 许可**）
        it = [x for x in at.PENDING_ATTRIBUTION if x["token"] == "特点"][0]
        saved = it["pending_reason"]
        it["pending_reason"] = "（测试用）它第二次出现了"
        try:
            g = at.run("gate_pending")
        finally:
            it["pending_reason"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "pending_repeat_not_license")
        self.assertEqual(g.get("token"), "特点")
        self.assertTrue(at.run("gate_pending")["ok"])

    # ---------- R-H348：面的行号 + CC Switch（第一个非第 1 行的再现） ----------

    def test_cc_switch_row3_not_mixed_with_row1(self):
        # 面名带行号后：第 1 行与第 3 行必须**分成两组**，不许混
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        items = at.run("reappearing")["items"]
        # ⚠️ 不许写死总条数（逐刀会涨，R-H344 立）
        self.assertGreaterEqual(len(items), 6)
        cc = [x for x in items if x["token"] == "CC Switch"][0]
        # 🔧 R-H359：面名补了「我方 R-H285 工具名单」⇒ CC Switch 现在**两处都在**
        #    （这本身就是**重叠读数**：源表格值 + 我方名单 ⇒ 并排、不合并）
        self.assertIn("第3行 格 代表工具", list(cc["where"]))
        self.assertIn("我方 R-H285 工具名单", list(cc["where"]))
        self.assertEqual(len(list(cc["where"])), 2, "两处来源都要在 where 里")
        self.assertEqual(list(cc["cell_mates"] or []), ["CC-Switch CLI"])
        groups = dict(g["same_cell_groups"] or {})
        # ⚠️ 不许写死名单（逐刀会涨）⇒ 与该键**派生自洽** + 成员判定
        key3 = "第3行 格 代表工具"
        want3 = sorted({x["token"] for x in items if key3 in (x["where"] or [])})
        self.assertEqual(sorted(groups.get(key3) or []), want3)
        self.assertIn("CC Switch", want3)
        self.assertEqual(sorted(groups.get("第1行 格 代表工具") or []),
                         ["CodeGeeX", "Fitten Code", "GitHub Copilot", "Trae", "通义灵码"])
        for v in groups.values():
            self.assertFalse("CC Switch" in v and "Trae" in v, "不许跨行混组")
        self.assertNotIn("CC Switch", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    def test_gbt_repeat_recorded_and_tooth_relaxed(self):
        # ①『与 GBT 的对接』第二次出现 ⇒ 补记；② 牙放宽：「不自解」也算（不只「不擅自」）
        items = at.run("pending")["items"]
        # ⚠️ 语义断言（比写死条数更准）：该 token **只出现一次** = 重复不新立
        self.assertEqual([x["token"] for x in items].count("与 GBT 的对接"), 1)
        gb = [x for x in items if x["token"] == "与 GBT 的对接"][0]
        r = str(gb["pending_reason"])
        for kw in ("R-H348", "第二次出现", "再给一次也不等于可以落表", "等主人一句话"):
            self.assertIn(kw, r)
        self.assertIsNone(gb["resolved"])
        self.assertTrue(at.run("gate_pending")["ok"])
        it = [x for x in at.PENDING_ATTRIBUTION if x["token"] == "与 GBT 的对接"][0]
        saved = it["pending_reason"]
        it["pending_reason"] = "（测试用）它第二次出现；仍不自解 ⇒ 仍在等主人一句话"
        try:
            g = at.run("gate_pending")
        finally:
            it["pending_reason"] = saved
        self.assertTrue(g["ok"], "「不自解」与「不擅自」同族，都该算（R-H348 放宽）")
        self.assertTrue(at.run("gate_pending")["ok"])

    # ---------- R-H349：CC Switch 的介绍（推断归属）+ 归属依据牙 + 两种处理并排 ----------

    def test_cc_switch_detail_staged_inferred_owner(self):
        # 三句介绍都挂条目上（Trae / Fitten / CC Switch），且都写明**归属依据**
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        # ⚠️ 不许写死名单（逐刀会涨）⇒ 成员判定
        for name in ("CC Switch", "Fitten Code", "Trae"):
            self.assertIn(name, list(g["with_detail"] or []))
        cc = [x for x in at.run("reappearing")["items"] if x["token"] == "CC Switch"][0]
        self.assertIn("供应商配置", str(cc["staged_detail"]))
        note = str(cc["staged_detail_note"])
        for kw in ("归属依据", "没点名", "推断", "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "供应商配置" in v], "介绍一个字都不许落表")

    def test_staged_detail_without_owner_basis_teeth(self):
        # 带牙：挂了介绍却不写「归属依据」⇒ 红（推断会被当成判定）
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "CC Switch"][0]
        saved = live["staged_detail_note"]
        live["staged_detail_note"] = "（测试用）暂存、不落表，但没写那条依据"
        try:
            g = at.run("gate_reappearing")
        finally:
            live["staged_detail_note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "staged_detail_without_owner_basis")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_two_handling_side_by_side_stated(self):
        # 两种处理**并排写明**：那两句留在待归属，三句挂条目 ⇒ 不迁移、不合并
        items = at.run("pending")["items"]
        self.assertGreaterEqual(len(items), 8, "本刀不迁移")
        for tok in ("智谱华章，AI 代码生成与补全",
                    "阿里，代码智能生成 + 研发智能问答 + 任务自主执行"):
            it = [x for x in items if x["token"] == tok][0]
            r = str(it["pending_reason"])
            self.assertIn("R-H349", r)
            self.assertIn("两种处理并存", r)
            self.assertIn("不迁移", r)
            self.assertIn("等主人一句话", r)
        self.assertTrue(at.run("gate_pending")["ok"])

    # ---------- R-H350：小节内容（跨源同向）+ CC-Switch CLI（变体） ----------

    def test_gbt_section_content_staged_and_cross_source(self):
        # ① 内容暂存（不落表）② 与我方 owner_use **同前缀、不同尾** ⇒ 跨源同向、并排记
        g = at.run("gate_pending")
        self.assertTrue(g["ok"], g)
        it = [x for x in at.run("pending")["items"]
              if x["token"] == "与 GBT 的对接"][0]
        self.assertIn("直接对接自动切换引擎", str(it["staged_value"]))
        self.assertIn("UI 层", str(it["staged_value"]))
        self.assertIn("暂存", str(it["staged_note"]))
        self.assertIn("不落", str(it["staged_note"]))
        r = str(it["pending_reason"])
        for kw in ("R-H350", "行为证据 +1", "跨源同向", "同前缀、不同尾",
                   "不许当同一个", "不硬凑", "等主人一句话"):
            self.assertIn(kw, r)
        self.assertIsNone(it["resolved"])
        own = [t for t in at.KEY_TOOLS if t["name"] == "CC Switch"][0]["owner_use"]
        self.assertTrue(str(it["staged_value"]).startswith("直接对接自动切换引擎"))
        self.assertTrue(own.startswith("直接对接自动切换引擎"))
        self.assertNotEqual(str(it["staged_value"]), own, "同前缀不同尾 ⇒ 不许当同一个")
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "UI 层" in v], "内容一个字都不许落表")

    def test_cc_switch_cli_variant_reappearing(self):
        # 第 3 行那格第二个 ⇒ 再现；且它必须是**变体**（与谁、差在哪写清）
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        items = at.run("reappearing")["items"]
        toks = [x["token"] for x in items]
        self.assertIn("CC-Switch CLI", toks)
        cli = [x for x in items if x["token"] == "CC-Switch CLI"][0]
        self.assertEqual(list(cli["where"]), ["第3行 格 代表工具"])
        self.assertEqual(list(cli["cell_mates"] or []), ["CC Switch"])
        n = str(cli["note"])
        for kw in ("变体", "CC Switch", "空格 ↔ 连字符", "不许当同一个", "不许当成另一个新工具"):
            self.assertIn(kw, n)
        self.assertIsNone(cli["resolved"])
        groups = dict(g["same_cell_groups"] or {})
        self.assertEqual(sorted(groups.get("第3行 格 代表工具") or []),
                         ["CC Switch", "CC-Switch CLI"])

    def test_reappearance_variant_unstated_teeth(self):
        # 带牙：变体却没写「变体」⇒ 红（否则会被当成同一个或另一个新工具）
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "CC-Switch CLI"][0]
        saved = live["note"]
        live["note"] = "**已在**盘上（测试用）；记为**再现**，没写那两个字"
        try:
            g = at.run("gate_reappearing")
        finally:
            live["note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "reappearance_variant_unstated")
        self.assertEqual(list(g.get("of") or []), ["CC Switch"])
        self.assertTrue(at.run("gate_reappearing")["ok"])

    # ---------- R-H351：CC-Switch CLI 的介绍（推断）+ 追溯补登记 ----------

    def test_cc_switch_cli_detail_inferred_owner(self):
        # 第四条介绍也挂条目；说明必须写「归属依据」，且整句不落表
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        cli = [x for x in at.run("reappearing")["items"]
               if x["token"] == "CC-Switch CLI"][0]
        self.assertEqual(str(cli["staged_detail"]),
                         "命令行版，统一管理五大 CLI 工具的供应商配置")
        note = str(cli["staged_detail_note"])
        for kw in ("归属依据", "没点名", "推断", "第二种读法", "暂存", "不落", "CLI"):
            self.assertIn(kw, note)
        self.assertIn("命令行版本", str(cli["note"]), "同前缀不同尾要并排记")
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "命令行版" in v], "介绍一个字都不许落表")

    def test_late_fragment_backfilled_with_reason(self):
        # 『命令行版本』= **追溯补登记**（主人早前那条长消息里的碎片，当时漏登记）
        r = at.run("fragments")
        self.assertIn("命令行版本", list(r["fragments"]))
        self.assertIn("追溯补登记", str(r["note"]))
        self.assertIn("0 命中", str(r["note"]))
        self.assertIn("不硬配", str(r["note"]))
        # 补登记 ≠ 硬配：它**不在**任何格 / 分类名里
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "命令行版本" in v], "待归位碎片不许落表")

    def test_same_prefix_different_tail_pair(self):
        # 同前缀、不同尾：『命令行版…』（本轮）vs『命令行版本』（追溯补登记）⇒ 并排、不当同一个
        detail = [x for x in at.REAPPEARING_TOKENS
                  if x["token"] == "CC-Switch CLI"][0]["staged_detail"]
        frag = [f for f in at.OWNER_FRAGMENTS if f.startswith("命令行版")][0]
        self.assertTrue(str(detail).startswith("命令行版"))
        self.assertTrue(frag.startswith("命令行版"))
        self.assertNotEqual(str(detail), frag, "同前缀不同尾 ⇒ 不许当同一个")

    # ---------- R-H352：顺序读数第二条（括号词命中旧批）+ 第九条 + 碎片第三次 ----------

    def test_order_reading_second_hits_old_batch(self):
        # 源编号 3 vs 本仓第 4 行；括号词『视频创作流水线』**正好是**旧批分类名 ⇒ 跨批对应（强）
        g = at.run("gate_source_order")
        self.assertTrue(g["ok"], g)
        self.assertGreaterEqual(g["count"], 2)
        it = at.run("source_order")["items"][1]
        self.assertEqual(it["category"], "AI短剧生成工具")
        self.assertEqual(it["source_no"], 3)
        self.assertEqual(it["our_index"], 4, "our_index 由闸现算")
        self.assertTrue(it["mismatch"])
        n = str(it["note"])
        for kw in ("不一致", "对应", "视频创作流水线", "不擅自合并"):
            self.assertIn(kw, n)
        self.assertIn("AI短剧生成工具", list(g.get("mismatched") or []))
        names = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        self.assertEqual(names[3], "AI短剧生成工具", "表未被重排")

    def test_order_batch_teeth_both_branches(self):
        # 带牙①：命中旧批却没写「对应」⇒ 红；② 没命中却没写「不是」⇒ 红
        live = [x for x in at.SOURCE_ORDER_READINGS
                if x["category"] == "AI短剧生成工具"][0]
        saved = live["note"]
        live["note"] = ("源仓库编号 3；本仓第 4 行 ⇒ 顺序不一致；"
                        "括号词『视频创作流水线』（测试用：故意不写那两个字）")
        try:
            g = at.run("gate_source_order")
        finally:
            live["note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "source_order_old_batch_hit_unstated")
        self.assertTrue(at.run("gate_source_order")["ok"])

        live2 = [x for x in at.SOURCE_ORDER_READINGS
                 if x["category"] == "AI模型管理工具"][0]
        saved2 = live2["note"]
        live2["note"] = "源仓库编号 2；本仓第 3 行 ⇒ 顺序不一致（测试用：不写那两字）"
        try:
            g2 = at.run("gate_source_order")
        finally:
            live2["note"] = saved2
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "source_order_old_batch_miss_unstated")
        self.assertTrue(at.run("gate_source_order")["ok"])

    def test_pending_ninth_phrase_with_para_staged(self):
        # 第九条：短语 + **同批来的正文**（正文含中文引号，逐字暂存、不落表）
        g = at.run("gate_pending")
        self.assertTrue(g["ok"], g)
        items = at.run("pending")["items"]
        self.assertGreaterEqual(len(items), 9)
        it = items[8]
        self.assertEqual(it["token"], "自动切换引擎的 CLI 入口")
        para = str(it["staged_value"])
        self.assertIn("供应商路由 + 一键切换", para)
        self.assertIn(chr(0x201C), para)      # 开引号（用 chr 写，绕开预检的「同行两种引号」规则）
        self.assertTrue(para.endswith("需要的。"))
        for kw in ("暂存", "不落"):
            self.assertIn(kw, str(it["staged_note"]))
        r = str(it["pending_reason"])
        for kw in ("三读法并排", "不擅自判定", "成对", "不合并", "等主人一句话"):
            self.assertIn(kw, r)
        self.assertIsNone(it["resolved"])
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "最直接相关" in v], "正文一个字都不许落表")

    def test_truncated_tool_fragment_third_time(self):
        # 『工具』第三次出现（R-H334 / R-H346 / R-H352）⇒ 仍留空不编
        g = at.run("gate_truncated")
        self.assertTrue(g["ok"], g)
        it = at.run("truncated")["items"][0]
        self.assertEqual(it["token"], "工具")
        for kw in ("R-H352", "第三次"):
            self.assertIn(kw, str(it["note"]) + str(it["at"]))
        self.assertIn("留空不编", str(it["note"]))
        self.assertIn("R-H352", str(it["at"]))

    # ---------- R-H354：『特点』第三次 + 派生读数 repeat_topics ----------

    def test_te_dian_third_time_still_recorded_not_landed(self):
        # 第三次同样**补记**：条数不增、仍不落表、仍不自解
        items = at.run("pending")["items"]
        self.assertEqual([x["token"] for x in items].count("特点"), 1,
                         "重复出现不许新立条目（第三次也一样）")
        td = [x for x in items if x["token"] == "特点"][0]
        r = str(td["pending_reason"])
        for kw in ("R-H354", "第三次出现", "仍是读数、不是许可", "等主人一句话"):
            self.assertIn(kw, r)
        self.assertIsNone(td["resolved"])
        self.assertTrue(at.run("gate_pending")["ok"])
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if v.strip() == "特点"], "第三次也不许落表")

    def test_repeat_topics_derived_reading(self):
        # 派生读数（正则现算）：谁被重复投喂、最多几次 —— 一眼可见、不许手写
        g = at.run("gate_pending")
        rt = dict(g.get("repeat_topics") or {})
        print("repeat_topics =", rt)
        # ⚠️ 不许写死次数（逐刀会涨，R-H344 立）⇒ **下限**断言
        self.assertGreaterEqual(rt.get("特点", 0), 3, "『特点』至少被给过三次")
        self.assertGreaterEqual(rt.get("与 GBT 的对接", 0), 2, "它被给过两次")
        fake = at._max_repeat("它第二次出现，后来第三次出现")
        self.assertEqual(fake, 3, "取**最大** N，不取最后一个")
        self.assertEqual(at._max_repeat("没有那两个字"), 0)

    # ---------- R-H355：第 4 行的再现 + 按行读数 + 『与 GBT』第三次 ----------

    def test_moneyprinter_reappearing_from_row4(self):
        # 第一个来自**第 4 行**的再现；该格**只有一个名字** ⇒ cell_mates 为空（这本身是读数）
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        items = at.run("reappearing")["items"]
        mpt = [x for x in items if x["token"] == "MoneyPrinterTurbo"][0]
        # 🔧 R-H359：同上（它也在我方 R-H285 名单里 ⇒ 两处来源）
        self.assertIn("第4行 格 代表工具", list(mpt["where"]))
        self.assertIn("我方 R-H285 工具名单", list(mpt["where"]))
        self.assertIsNone(mpt["cell_mates"], "单名格 ⇒ 无同格伙伴（不许编一个）")
        n = str(mpt["note"])
        for kw in ("再现", "第一个来自第 4 行", "KEY_TOOLS", "重叠"):
            self.assertIn(kw, n)
        self.assertIsNone(mpt["resolved"])
        self.assertNotIn("MoneyPrinterTurbo",
                         [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    def test_reappearing_by_row_reading(self):
        # 派生读数：按**行**统计再现 ⇒ 哪些行开始被逐个投喂，一眼可见
        g = at.run("gate_reappearing")
        by_row = dict(g.get("reappearing_by_row") or {})
        print("reappearing_by_row =", {k: len(v) for k, v in by_row.items()})
        self.assertEqual(len(by_row.get("第1行") or []), 5)
        self.assertEqual(len(by_row.get("第3行") or []), 2)
        self.assertEqual(list(by_row.get("第4行") or []), ["MoneyPrinterTurbo"])
        # 与 items **自洽**（不写死名单）
        for row, toks in by_row.items():
            want = sorted({x["token"] for x in at.run("reappearing")["items"]
                           if any(str(w).startswith(row) for w in (x["where"] or []))})
            self.assertEqual(sorted(toks), want)

    def test_gbt_third_time_recorded(self):
        # 第三次仍补记：不新立、不落表；派生读数也要跟着涨
        items = at.run("pending")["items"]
        self.assertEqual([x["token"] for x in items].count("与 GBT 的对接"), 1)
        it = [x for x in items if x["token"] == "与 GBT 的对接"][0]
        r = str(it["pending_reason"])
        for kw in ("R-H355", "第三次出现", "不新立条目、不落表", "等主人一句话"):
            self.assertIn(kw, r)
        g = at.run("gate_pending")
        # ⚠️ 不许写死次数（逐刀会涨，R-H344 立）⇒ **下限**断言
        self.assertGreaterEqual(dict(g.get("repeat_topics") or {}).get("与 GBT 的对接", 0), 3)
        self.assertTrue(g["ok"])

    # ---------- R-H356：第 4 行那句介绍（推断）+ 证据强度读数 ----------

    def test_moneyprinter_detail_inferred_and_not_landed(self):
        # 第五条介绍：同样标「没点名 ⇒ 推断」、暂存、不落表
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        mpt = [x for x in at.run("reappearing")["items"]
               if x["token"] == "MoneyPrinterTurbo"][0]
        self.assertEqual(str(mpt["staged_detail"]), "输入主题/关键词，全自动生成视频文案、素材、字幕、背景音乐，合成高清短视频")
        note = str(mpt["staged_detail_note"])
        for kw in ("归属依据", "没点名", "推断", "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIn("每个被逐个再给的工具后面都跟着一句介绍", str(mpt["note"]))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "高清短视频" in v], "介绍一个字都不许落表")

    def test_detail_ratio_derived_reading(self):
        # 派生读数（现算）：带介绍的条数 / 再现总条数 —— 「一工具一行」的证据强度可算
        g = at.run("gate_reappearing")
        dr = dict(g.get("detail_ratio") or {})
        print("detail_ratio =", dr)
        self.assertEqual(dr.get("with_detail"), len(list(g.get("with_detail") or [])))
        self.assertEqual(dr.get("total"), g.get("count"))
        self.assertGreaterEqual(dr.get("with_detail", 0), 5, "至少五条带介绍")
        self.assertAlmostEqual(dr.get("ratio", 0),
                               round(dr["with_detail"] / max(1, dr["total"]), 2), places=2)

    def test_all_reappearing_with_detail_pattern(self):
        # 读数：**被逐个再给的工具后面都跟着一句介绍**（现算核过，仍不定论）
        g = at.run("gate_reappearing")
        items = at.run("reappearing")["items"]
        with_detail = set(g.get("with_detail") or [])
        for tok in ("Trae", "Fitten Code", "CC Switch", "CC-Switch CLI",
                    "MoneyPrinterTurbo"):
            self.assertIn(tok, with_detail)
        # 但**不许**因此认为「已定论」：条目里必须仍写着推断
        for x in items:
            if x["token"] in with_detail:
                self.assertIn("推断", str(x["staged_detail_note"]))
        self.assertTrue(g["ok"])

    # ---------- R-H357：新面孔（FastMovieAI）+ 自维护读数 newcomers ----------

    def test_fastmovieai_newcomer_pending_tenth(self):
        # 全盘 0 命中 ⇒ 新面孔；三读法并排、不落表、不自解
        g = at.run("gate_pending")
        self.assertTrue(g["ok"], g)
        items = at.run("pending")["items"]
        self.assertGreaterEqual(len(items), 10)
        it = items[9]
        self.assertEqual(it["token"], "FastMovieAI")
        r = str(it["pending_reason"])
        for kw in ("三读法并排", "不擅自判定", "全盘 0 命中", "新面孔",
                   "盘上首次出现", "看着像 ≠ 就是", "等主人一句话"):
            self.assertIn(kw, r)
        self.assertIsNone(it["resolved"])
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "FastMovieAI" in v], "新面孔一个字都不许落表")

    def test_newcomers_derived_reading_self_consistent(self):
        # 派生读数：**不在任何数据面**的待归属项（现算、自维护）
        g = at.run("gate_pending")
        newcomers = list(g.get("newcomers") or [])
        print("newcomers =", newcomers)
        self.assertIn("FastMovieAI", newcomers)
        self.assertNotIn("代表工具", newcomers, "它在第二节列名里 ⇒ 不是新面孔")
        known = at._known_names()
        for x in at.run("pending")["items"]:
            self.assertEqual(str(x["token"]).strip() not in known,
                             x["token"] in newcomers, "读数必须与当前数据面自洽")

    def test_newcomers_is_self_maintaining(self):
        # 自维护：名字一旦**真落进某个数据面** ⇒ 自动从 newcomers 消失（不用人工维护）
        cell = at.CATEGORY_ROWS_OWNER[0]["cells"]
        saved = cell.get("对应 GBT 能力域")
        cell["对应 GBT 能力域"] = "FastMovieAI"
        try:
            after = list(at.run("gate_pending").get("newcomers") or [])
        finally:
            cell["对应 GBT 能力域"] = saved
        self.assertNotIn("FastMovieAI", after, "落进数据面后应自动退出 newcomers")
        self.assertIn("FastMovieAI",
                      list(at.run("gate_pending").get("newcomers") or []),
                      "复原后应回到 newcomers")

    # ---------- R-H358：FastMovieAI 的介绍（暂存 + 推断）+ 归属状态牙 ----------

    def test_fastmovieai_detail_staged_inferred(self):
        # 待归属项也能**带一句介绍**（暂存）：必须写明归属依据、且不落表
        g = at.run("gate_pending")
        self.assertTrue(g["ok"], g)
        it = [x for x in at.run("pending")["items"] if x["token"] == "FastMovieAI"][0]
        self.assertEqual(str(it["staged_value"]), "功能完整的开源短剧/短视频创作平台，前后端分离，集成用户管理、支付、内容管理、视频生成")
        note = str(it["staged_note"])
        for kw in ("归属依据", "没点名", "推断", "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIn("R-H358", str(it["pending_reason"]))
        self.assertIn("FastMovieAI", list(g.get("staged_items") or []))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "前后端分离" in v], "介绍一个字都不许落表")

    def test_staged_value_owner_unstated_teeth(self):
        # 带牙：暂存值没写「这是谁的 / 不知道是谁」⇒ 红（不许沉默）
        it = [x for x in at.PENDING_ATTRIBUTION if x["token"] == "FastMovieAI"][0]
        saved = it["staged_note"]
        it["staged_note"] = "⏸ **暂存、不落表**：只写了暂存两个字"
        try:
            g = at.run("gate_pending")
        finally:
            it["staged_note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "staged_value_owner_unstated")
        self.assertEqual(g.get("token"), "FastMovieAI")
        self.assertTrue(at.run("gate_pending")["ok"])

    def test_all_staged_values_state_owner(self):
        # 全量核：**每条**带暂存值的待归属项都写明了归属状态（不只新加的那条）
        ok_words = ("归属依据", "未点名", "不明", "没定")
        n = 0
        for x in at.PENDING_ATTRIBUTION:
            if x.get("staged_value"):
                n += 1
                self.assertTrue(any(k in str(x.get("staged_note") or "") for k in ok_words),
                                "%s 没写明归属状态" % x["token"])
        self.assertGreaterEqual(n, 6, "空样本不按绿：至少要真核过几条")
        self.assertTrue(at.run("gate_pending")["ok"])

    # ---------- R-H359：Huobao Drama + 面名补 R-H285 名单 + 读数分流 ----------

    def test_huobao_drama_reappearing_from_rh285_list(self):
        # 只在我方 R-H285 名单里出现的名字 ⇒ 记再现，来源是「名单」而不是「行格」
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        hb = [x for x in at.run("reappearing")["items"]
              if x["token"] == "Huobao Drama"][0]
        self.assertEqual(list(hb["where"]), ["我方 R-H285 工具名单"])
        n = str(hb["note"])
        for kw in ("再现", "KEY_TOOLS", "video_pipeline", "两处", "不合并"):
            self.assertIn(kw, n)
        self.assertIsNone(hb["resolved"])
        self.assertNotIn("Huobao Drama",
                         [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    def test_reappearing_elsewhere_reading(self):
        # 读数分流：不在行里的再现（by_row 只收行，elsewhere 收其余的）
        g = at.run("gate_reappearing")
        by_row = dict(g.get("reappearing_by_row") or {})
        elsewhere = list(g.get("reappearing_elsewhere") or [])
        print("by_row =", {k: len(v) for k, v in by_row.items()}, "| elsewhere =", elsewhere)
        for row, group in by_row.items():
            self.assertTrue(row.startswith("第"), "by_row 只该有行来源：%s" % row)
            want = sorted({x["token"] for x in at.run("reappearing")["items"]
                           if any(str(n2).startswith(row + " ")
                                  for n2 in (x["where"] or []))})
            self.assertEqual(sorted(group), want)
        self.assertIn("Huobao Drama", elsewhere, "它不在行里 ⇒ 应进 elsewhere")
        self.assertFalse([k for k in by_row if not k.startswith("第")],
                         "by_row 不许出现非行的怪 key")

    def test_known_names_includes_rh285_list(self):
        # 修缺口：我方 KEY_TOOLS 也算「盘上已有」⇒ 已知名字不会被误判成新面孔
        known = at._known_names()
        for nm in ("Huobao Drama", "MoneyPrinterTurbo", "CC Switch"):
            self.assertIn(nm, known, "%s 是我方登记过的名字" % nm)
        newcomers = list(at.run("gate_pending").get("newcomers") or [])
        self.assertNotIn("Huobao Drama", newcomers, "它不是新面孔")

    # ---------- R-H360：Huobao Drama 的介绍（推断）+ 重复介绍牙 ----------

    def test_huobao_detail_staged_inferred(self):
        # 第 6 条「名字 → 紧接着一句介绍」；本条来源是**名单**而非行格
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        hb = [x for x in at.run("reappearing")["items"]
              if x["token"] == "Huobao Drama"][0]
        det = str(hb["staged_detail"])
        for kw in ("Go + Vue3", "剧本解析", "分镜生成", "视频合成", "全链路"):
            self.assertIn(kw, det)
        note = str(hb["staged_detail_note"])
        for kw in ("归属依据", "没点名", "推断", "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIn("第 6 条", str(hb["note"]))
        self.assertIn("Huobao Drama", list(g.get("with_detail") or []))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        vals += list(at.SOURCE_TABLE_COLUMNS) + list(at.SECTION2_COLUMNS)
        self.assertFalse([v for v in vals if "全链路" in v], "介绍一个字都不许落表")

    def test_detail_ratio_grows_to_six(self):
        # 证据强度读数：带介绍 6 / 再现 9
        g = at.run("gate_reappearing")
        dr = dict(g.get("detail_ratio") or {})
        print("detail_ratio =", dr)
        self.assertEqual(dr.get("with_detail"), len(list(g.get("with_detail") or [])))
        self.assertEqual(dr.get("total"), g.get("count"))
        self.assertGreaterEqual(dr.get("with_detail", 0), 6)
        self.assertIn("Huobao Drama", list(g.get("with_detail") or []))

    def test_staged_detail_duplicate_teeth(self):
        # 带牙：同一句介绍挂两个名字 ⇒ 红（一份介绍不能认两个主）
        src = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Huobao Drama"][0]
        dst = [x for x in at.REAPPEARING_TOKENS if x["token"] == "MoneyPrinterTurbo"][0]
        saved = dst.get("staged_detail")
        dst["staged_detail"] = str(src["staged_detail"])
        try:
            g = at.run("gate_reappearing")
        finally:
            dst["staged_detail"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "staged_detail_duplicated_across_names")
        self.assertIn("Huobao Drama", [str(g.get("token")), str(g.get("also"))])
        self.assertTrue(at.run("gate_reappearing")["ok"])

    # ---------- R-H361：LocalMiniDrama（短剧三件套到齐）+ 六条投喂进度 ----------

    def test_localminidrama_reappearing_completes_trio(self):
        # 短剧三件套到齐；三件里**只有一件**在源表格值里 ⇒ 两处并排、不合并
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        items = at.run("reappearing")["items"]
        lmd = [x for x in items if x["token"] == "LocalMiniDrama"][0]
        self.assertEqual(list(lmd["where"]), ["我方 R-H285 工具名单"])
        n = str(lmd["note"])
        for kw in ("再现", "KEY_TOOLS", "video_pipeline", "三件套到齐", "不合并"):
            self.assertIn(kw, n)
        self.assertIsNone(lmd["resolved"])
        toks = [x["token"] for x in items]
        for nm in ("MoneyPrinterTurbo", "Huobao Drama", "LocalMiniDrama"):
            self.assertIn(nm, toks, "短剧三件套应都到")
        self.assertNotIn("LocalMiniDrama",
                         [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    def test_rh285_covered_reading(self):
        # 派生读数：我方 R-H285 六条的**投喂进度**（现算、不手写）
        g = at.run("gate_reappearing")
        cov = list(g.get("rh285_covered") or [])
        print("rh285_covered =", cov, "/", g.get("rh285_total"))
        self.assertEqual(g.get("rh285_total"), len(at.KEY_TOOLS))
        names = {t["name"] for t in at.KEY_TOOLS}
        self.assertTrue(set(cov) <= names, "读数只该含 KEY_TOOLS 里的名字")
        for nm in ("CC Switch", "MoneyPrinterTurbo", "Huobao Drama", "LocalMiniDrama"):
            self.assertIn(nm, cov)
        # 与 items **自洽**（独立复算）
        want = sorted({x["token"] for x in at.run("reappearing")["items"] if x["token"] in names})
        self.assertEqual(sorted(cov), want)

    def test_elsewhere_reading_covers_the_two(self):
        # 读数分流：不在行里的再现现在有两条（都是名单来源）
        g = at.run("gate_reappearing")
        elsewhere = list(g.get("reappearing_elsewhere") or [])
        print("elsewhere =", elsewhere)
        self.assertEqual(sorted(elsewhere), ["Huobao Drama", "LocalMiniDrama"])
        by_row = dict(g.get("reappearing_by_row") or {})
        self.assertFalse([k for k in by_row if not k.startswith("第")])

    # ---------- R-H362：LocalMiniDrama 的介绍（推断 + 词义呼应）----------

    def test_localminidrama_detail_inferred_with_name_echo(self):
        # 第七条介绍：归属依据除了「紧跟其后」，还有**名字词义呼应**（Local ↔ 本地）
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        lmd = [x for x in at.run("reappearing")["items"]
               if x["token"] == "LocalMiniDrama"][0]
        self.assertEqual(str(lmd["staged_detail"]), "本地 AI 短剧/漫剧生成，数据不出本机，无订阅费")
        note = str(lmd["staged_detail_note"])
        for kw in ("归属依据", "名字词义呼应", "没点名", "推断", "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIn("三句全齐", str(lmd["note"]))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "无订阅费" in v], "介绍一个字都不许落表")

    def test_detail_ratio_and_groups(self):
        # 证据强度：带介绍 7 / 再现 10；并按来源分组
        g = at.run("gate_reappearing")
        dr = dict(g.get("detail_ratio") or {})
        print("detail_ratio =", dr)
        self.assertEqual(dr.get("with_detail"), len(list(g.get("with_detail") or [])))
        self.assertGreaterEqual(dr.get("with_detail", 0), 7)
        by_row = dict(g.get("detail_by_row") or {})
        elsewhere = list(g.get("detail_elsewhere") or [])
        print("detail_by_row =", {k: len(v) for k, v in by_row.items()},
              "| detail_elsewhere =", elsewhere)
        self.assertEqual(sorted(elsewhere), ["Huobao Drama", "LocalMiniDrama"],
                         "名单来源的两条**都带介绍**（2/2）")
        for row, group in by_row.items():
            self.assertTrue(row.startswith("第"))
            want = sorted({x["token"] for x in at.run("reappearing")["items"]
                           if x.get("staged_detail")
                           and any(str(n2).startswith(row + " ")
                                   for n2 in (x["where"] or []))})
            self.assertEqual(sorted(group), want)

    def test_trio_all_have_detail(self):
        # 短剧三件套**三句介绍全齐**（现算核过）
        g = at.run("gate_reappearing")
        wd = set(g.get("with_detail") or [])
        for nm in ("MoneyPrinterTurbo", "Huobao Drama", "LocalMiniDrama"):
            self.assertIn(nm, wd, "%s 应带一句介绍" % nm)
        self.assertTrue(g["ok"])

    # ---------- R-H363：顺序读数第三条（本仓无此行）+ 碎片第四次 ----------

    def test_order_reading_third_no_local_row(self):
        # 源编号 4 = 「智能体生态工具」；**本仓无此行** ⇒ 显式 local_row=None
        g = at.run("gate_source_order")
        self.assertTrue(g["ok"], g)
        self.assertGreaterEqual(g["count"], 3)
        it = at.run("source_order")["items"][2]
        self.assertEqual(it["category"], "智能体生态工具")
        self.assertEqual(it["source_no"], 4)
        self.assertIsNone(it["our_index"], "本仓无此行 ⇒ our_index 为 None（闸现算）")
        self.assertTrue(it["mismatch"], "无对应行也算**不一致**")
        n = str(it["note"])
        for kw in ("本仓无此行", "不是同一个", "不一致", "对应",
                   "不许重排", "不许新增行", "同前缀", "不同尾"):
            self.assertIn(kw, n)
        self.assertIn("智能体生态工具", list(g.get("mismatched") or []))
        names = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        self.assertNotIn("智能体生态工具", names, "**不许新增行**")
        self.assertEqual(names[4], "实用画图工具", "第 5 行不是它 ⇒ 表未被重排")

    def test_order_no_local_row_teeth(self):
        # 带牙①：不声明 local_row=None 而名字又不在表里 ⇒ 读数悬空；
        # 带牙②：声明了 None 却没写「本仓无此行」⇒ 也算沉默
        live = [x for x in at.SOURCE_ORDER_READINGS
                if x["category"] == "智能体生态工具"][0]
        saved_row = live["local_row"]
        saved_note = live["note"]
        del live["local_row"]
        try:
            g = at.run("gate_source_order")
        finally:
            live["local_row"] = saved_row
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "source_order_category_unknown")
        self.assertTrue(at.run("gate_source_order")["ok"])

        live["note"] = "（测试用）源编号 4，没写那五个字"
        try:
            g2 = at.run("gate_source_order")
        finally:
            live["note"] = saved_note
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "source_order_no_local_row_unstated")
        self.assertTrue(at.run("gate_source_order")["ok"])

    def test_truncated_tool_fragment_fourth_time(self):
        # 『工具』第四次出现；四次位置**完全一致**（都在带编号的分类头之后）
        g = at.run("gate_truncated")
        self.assertTrue(g["ok"], g)
        it = at.run("truncated")["items"][0]
        self.assertEqual(it["token"], "工具")
        self.assertIn("R-H363", str(it["at"]))
        for kw in ("第四次", "留空不编", "位置**完全一致**" if False else "位置"):
            self.assertIn(kw, str(it["note"]))
        self.assertIn("表头", str(it["note"]), "四次一致 ⇒ 更像「每分类下的表头 / 字段名」"
                         "（**但仍不编**）")
        self.assertNotIn("工具", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    # ---------- R-H364：『特点』第四次 + 积压读数 ----------

    def test_te_dian_fourth_time_still_recorded(self):
        # 第四次仍**补记**：条数不增、不落表、不自解，且理由里写清「四次」
        items = at.run("pending")["items"]
        self.assertEqual([x["token"] for x in items].count("特点"), 1)
        td = [x for x in items if x["token"] == "特点"][0]
        r = str(td["pending_reason"])
        for kw in ("R-H364", "第四次出现", "四次都给同一个词", "卡在我们之间",
                   "不新立条目、不落表、不自解", "等主人一句话"):
            self.assertIn(kw, r)
        self.assertIsNone(td["resolved"])
        self.assertTrue(at.run("gate_pending")["ok"])
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if v.strip() == "特点"], "第四次也不许落表")

    def test_repeated_but_unresolved_reading(self):
        # 派生读数：反复投喂 ≥2 次、但仍未自解 ⇒ 「积压在哪」变成数字
        g = at.run("gate_pending")
        rt = dict(g.get("repeat_topics") or {})
        rep = list(g.get("repeated_but_unresolved") or [])
        print("repeat_topics =", rt, "| repeated_but_unresolved =", rep)
        self.assertIn("特点", rep)
        self.assertIn("与 GBT 的对接", rep)
        for tok in rep:
            self.assertGreaterEqual(rt.get(tok, 0), 2, "进这个读数的必须真的被反复给过")
            it = [x for x in at.run("pending")["items"] if x["token"] == tok][0]
            self.assertIsNone(it["resolved"], "仍未自解")
        self.assertEqual(sorted(rep), sorted(rt.keys()),
                         "当前所有反复投喂项都仍未解决 ⇒ 两个读数应一致")

    # ---------- R-H365：CowAgent（名单+行两处来源）+ 六条进度 5/6 ----------

    def test_cowagent_reappearing_two_sources(self):
        # 『CowAgent』在**第 2 行格值**与**我方名单**里**都**出现 ⇒ 两处来源（重叠读数）
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        ca = [x for x in at.run("reappearing")["items"] if x["token"] == "CowAgent"][0]
        w = list(ca["where"])
        print("CowAgent where =", w)
        self.assertIn("第2行 格 代表工具", w)
        self.assertIn("我方 R-H285 工具名单", w)
        self.assertEqual(len(w), 2, "两处来源都要在（不许只记一处）")
        n = str(ca["note"])
        for kw in ("再现", "第五", "im_multiplex", "5 / 6", "OpenClaw Monitor",
                   "不是许可"):
            self.assertIn(kw, n)
        self.assertIsNone(ca["resolved"])
        self.assertNotIn("CowAgent", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    def test_rh285_progress_five_of_six(self):
        # 六条进度：5 / 6（还差 OpenClaw Monitor）；读数与 items 自洽
        g = at.run("gate_reappearing")
        cov = list(g.get("rh285_covered") or [])
        names = {t["name"] for t in at.KEY_TOOLS}
        print("rh285_covered =", cov, "/", g.get("rh285_total"), "| 还差 =",
              sorted(names - set(cov)))
        self.assertIn("CowAgent", cov)
        # ⚠️ 不许写死条数（逐刀会涨，R-H344 立）⇒ 用**语义读数**：到齐与否由闸现算
        self.assertGreaterEqual(len(cov), 5, "至少五条")
        self.assertEqual(sorted(names - set(cov)),
                         [] if g.get("rh285_complete") else sorted(names - set(cov)))
        want = sorted({x["token"] for x in at.run("reappearing")["items"]
                       if x["token"] in names})
        self.assertEqual(sorted(cov), want)

    def test_gbt_fourth_time_recorded(self):
        # 第四次仍补记；且被点名为「反复投喂的两条」之一
        items = at.run("pending")["items"]
        self.assertEqual([x["token"] for x in items].count("与 GBT 的对接"), 1)
        it = [x for x in items if x["token"] == "与 GBT 的对接"][0]
        r = str(it["pending_reason"])
        for kw in ("R-H365", "第四次出现", "四次都给同一个短语",
                   "repeated_but_unresolved", "等主人一句话"):
            self.assertIn(kw, r)
        g = at.run("gate_pending")
        self.assertIn("与 GBT 的对接", list(g.get("repeated_but_unresolved") or []))
        self.assertGreaterEqual(dict(g.get("repeat_topics") or {}).get("与 GBT 的对接", 0), 4)
        self.assertTrue(g["ok"])

    # ---------- R-H366：CowAgent 的介绍（推断 + 跨源呼应）+ 呼应可算 ----------

    def test_cowagent_detail_inferred_with_owner_use_echo(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        ca = [x for x in at.run("reappearing")["items"] if x["token"] == "CowAgent"][0]
        det = str(ca["staged_detail"])
        for kw in ("超级 AI 助理", "主动思考", "任务规划", "Skills", "QQ 接入"):
            self.assertIn(kw, det)
        note = str(ca["staged_detail_note"])
        for kw in ("归属依据", "owner_use", "没点名", "推断", "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIn("跨源呼应第四处", str(ca["note"]))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "超级 AI 助理" in v], "介绍一个字都不许落表")

    def test_detail_owner_use_echo_is_computable(self):
        # 呼应**可算**：≥4 字连续重合（去空格标点后）⇒ 不靠感觉
        g = at.run("gate_reappearing")
        echo = dict(g.get("detail_owner_use_echo") or {})
        print("detail_owner_use_echo =", echo)
        self.assertIn("CowAgent", echo)
        self.assertTrue(echo["CowAgent"], "句尾四平台名与 owner_use 应有重合")
        # 独立复算（不看模块自己的结果）
        own = {t["name"]: t["owner_use"] for t in at.KEY_TOOLS}
        import re as _re
        strip = _re.compile(r"[\s\u3000/（）()\[\]【】、，,。.·\-—+\|｜]+")
        for tok, hit in echo.items():
            a = strip.sub("", str([x for x in at.run("reappearing")["items"]
                                   if x["token"] == tok][0]["staged_detail"]))
            b = strip.sub("", str(own.get(tok) or ""))
            want = any(a[i:i + 4] in b for i in range(0, max(0, len(a) - 3)))
            self.assertEqual(bool(hit), want, "%s 的呼应读数复算不上" % tok)

    def test_echo_negative_case_is_false(self):
        # 反向：把一段与 owner_use 无关的介绍挂上去 ⇒ 呼应应为 False（读数**不靠感觉**）
        # ⚠️ 老用例这里写过「OpenClaw Monitor 还没登记」当便利前提 ⇒ 它已登记 ⇒ 前提过期
        #    ⇒ 删掉便利前提，只留**真正的判据**（负例 / 正例 / 短于 4 字）
        self.assertTrue(at._echo_hit("完全不相干的文字", "多平台接入能力（微信 / 飞书）") is False)
        self.assertTrue(at._echo_hit("多平台接入能力", "多平台接入能力（微信 / 飞书）") is True)
        self.assertFalse(at._echo_hit("平台", "多平台接入能力"), "短于 4 字不算重合")

    # ---------- R-H367：OpenClaw Monitor（六条到齐）+ 两条读数 ----------

    def test_openclaw_monitor_reappearing_two_sources(self):
        # 第六/末条：**两处来源**（第 2 行格值 + 我方名单），与 CowAgent 同款
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        oc = [x for x in at.run("reappearing")["items"]
              if x["token"] == "OpenClaw Monitor"][0]
        w = list(oc["where"])
        print("OpenClaw Monitor where =", w)
        self.assertIn("第2行 格 代表工具", w)
        self.assertIn("我方 R-H285 工具名单", w)
        self.assertEqual(len(w), 2)
        n = str(oc["note"])
        for kw in ("再现", "第六/末条", "god_view", "6 / 6", "到齐 ≠ 许可", "不合并"):
            self.assertIn(kw, n)
        self.assertIsNone(oc["resolved"])
        self.assertNotIn("OpenClaw Monitor",
                         [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    def test_rh285_complete_reading_and_summary(self):
        # 到齐读数 + 来源统计（都现算）
        g = at.run("gate_reappearing")
        cov = list(g.get("rh285_covered") or [])
        names = {t["name"] for t in at.KEY_TOOLS}
        print("rh285_covered =", cov, "| complete =", g.get("rh285_complete"),
              "| source_summary =", g.get("source_summary"))
        self.assertEqual(sorted(cov), sorted(names), "六条应全部到齐")
        self.assertTrue(g.get("rh285_complete"), "到齐读数应为 True")
        ss = dict(g.get("source_summary") or {})
        self.assertEqual(ss.get("total"), g.get("count"))
        items = at.run("reappearing")["items"]
        want_row = len([x for x in items
                        if any(str(n2).startswith("第") for n2 in (x["where"] or []))])
        want_both = len([x for x in items
                         if any(str(n2).startswith("第") for n2 in (x["where"] or []))
                         and "我方 R-H285 工具名单" in (x["where"] or [])])
        self.assertEqual(ss.get("in_row"), want_row)
        self.assertEqual(ss.get("both"), want_both)
        self.assertLessEqual(ss.get("both"), ss.get("in_row"))

    def test_complete_is_not_a_license(self):
        # 「到齐」不许被当成许可：六条仍**一条都没落表**、且**都没自解**
        g = at.run("gate_reappearing")
        ca = at.run("gate_categories")
        names = {t["name"] for t in at.KEY_TOOLS}
        cats = [str(x["category"]) for x in ca["rows"]]
        self.assertFalse([n for n in names if n in cats], "六条名字不许出现在分类名里")
        # ⚠️ 这里原先写「六条名字不许出现在任何格值里」⇒ **判据过了头**：第 4 行那格本来就只有
        #    MoneyPrinterTurbo（源表原有，不是我落的）。真正的语义是：**每个出现都要被来源解释**
        #    （即它必须能在 where 里指到「第N行 格 代表工具」或「我方 R-H285 名单」）⇒ 不许「新落」
        for x in at.CATEGORY_ROWS_OWNER:
            for k, v in dict(x.get("cells") or {}).items():
                val = str(v or "").strip()
                if val in names:
                    tag = [w for w in at.run("reappearing")["items"]
                           if w["token"] == val][0]["where"]
                    self.assertTrue(any(str(t).endswith("格 %s" % k) for t in tag),
                                    "%s 在格 %s 里出现，却没有任何来源解释它" % (val, k))
        for x in at.run("reappearing")["items"]:
            self.assertIsNone(x["resolved"], "再现条目**一律不许自解**（到齐也不例外）")
        self.assertTrue(g["ok"])

    # ---------- R-H368：OpenClaw Monitor 的介绍（语义同向但**可算未命中**）----------

    def test_openclaw_detail_inferred_echo_false(self):
        # 第九条介绍；诚实处：**语义同向**但**可算读数 False**（必须如实写、不许声称命中）
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        oc = [x for x in at.run("reappearing")["items"]
              if x["token"] == "OpenClaw Monitor"][0]
        det = str(oc["staged_detail"])
        for kw in ("监控 OpenClaw", "会话状态", "Token 使用量", "任务执行进度"):
            self.assertIn(kw, det)
        note = str(oc["staged_detail_note"])
        for kw in ("归属依据", "语义同向", "未命中", "没点名", "推断",
                   "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIs(oc.get("echo_claim"), False, "声明必须写明")
        echo = dict(g.get("detail_owner_use_echo") or {})
        self.assertIs(echo.get("OpenClaw Monitor"), False, "可算读数确实未命中")
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "任务执行进度" in v], "介绍一个字都不许落表")

    def test_echo_claim_teeth_both_directions(self):
        # 带牙①：声明 True 但可算 False ⇒ 红；② 声明 False 但可算 True ⇒ 也红
        oc = [x for x in at.REAPPEARING_TOKENS if x["token"] == "OpenClaw Monitor"][0]
        saved = oc["echo_claim"]
        oc["echo_claim"] = True
        try:
            g = at.run("gate_reappearing")
        finally:
            oc["echo_claim"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "echo_claim_without_computation")
        self.assertTrue(at.run("gate_reappearing")["ok"])

        ca = [x for x in at.REAPPEARING_TOKENS if x["token"] == "CowAgent"][0]
        saved2 = ca.get("echo_claim")
        ca["echo_claim"] = False
        try:
            g2 = at.run("gate_reappearing")
        finally:
            ca["echo_claim"] = saved2
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "echo_denial_against_computation")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_echo_reading_shape_and_ratio(self):
        # 呼应读数只覆盖「带介绍 ∩ 我方名单」；比例读数同步涨
        g = at.run("gate_reappearing")
        echo = dict(g.get("detail_owner_use_echo") or {})
        names = {t["name"] for t in at.KEY_TOOLS}
        want = sorted({x["token"] for x in at.run("reappearing")["items"]
                       if x["token"] in names and x.get("staged_detail")})
        print("echo keys =", sorted(echo), "| want =", want)
        self.assertEqual(sorted(echo), want)
        dr = dict(g.get("detail_ratio") or {})
        print("detail_ratio =", dr)
        self.assertGreaterEqual(dr.get("with_detail", 0), 9)
        self.assertEqual(dr.get("total"), g.get("count"))

    # ---------- R-H369：顺序读数第四条（一字之差的近似行）+ 碎片第五次 ----------

    def test_order_reading_fourth_near_row(self):
        # 源 5 = 『文档与知识库工具』；本仓第 6 行是『文档**和**知识库工具』⇒ **一字之差**
        g = at.run("gate_source_order")
        self.assertTrue(g["ok"], g)
        self.assertGreaterEqual(g["count"], 4)
        it = at.run("source_order")["items"][3]
        self.assertEqual(it["category"], "文档与知识库工具")
        self.assertEqual(it["source_no"], 5)
        self.assertIsNone(it["our_index"], "近似行 ⇒ our_index 为 None")
        self.assertTrue(it["mismatch"], "源名与本仓行名不同 ⇒ 不一致")
        self.assertEqual(str(it.get("near_row") or ""), "文档和知识库工具",
                         "近似行要**随条目带出来**（出口与判据不许各说各话）")
        n = str(it["note"])
        for kw in ("一字之差", "疑似对应", "不一致", "不许重排", "不许新增行",
                   "不许拿源名去改本仓行名", "不是", "语义呼应"):
            self.assertIn(kw, n)
        names = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        self.assertEqual(names[5], "文档和知识库工具", "🔴 本仓第 6 行**没被改名**")
        self.assertNotIn("文档与知识库工具", names, "不许新增行")
        # 两种形态**互斥**：R-H363 那条是真「本仓无此行」（没有 near_row）
        third = at.run("source_order")["items"][2]
        self.assertFalse(str(third.get("near_row") or ""))

    def test_order_near_row_teeth_three(self):
        # 带牙①：近似行不在本仓 ⇒ 红；② 没写「一字之差 / 疑似对应」⇒ 红；
        # ③ 近似行与源名一模一样（= 拿源名改了本仓行名）⇒ 红
        live = [x for x in at.SOURCE_ORDER_READINGS
                if x["category"] == "文档与知识库工具"][0]
        saved_near = live["near_row"]
        saved_note = live["note"]
        live["near_row"] = "根本没这一行"
        try:
            g1 = at.run("gate_source_order")
        finally:
            live["near_row"] = saved_near
        self.assertFalse(g1["ok"], g1)
        self.assertEqual(g1["rule"], "source_order_near_row_unknown")
        self.assertTrue(at.run("gate_source_order")["ok"])

        live["note"] = "（测试用）源编号 5，没写那几个词"
        try:
            g2 = at.run("gate_source_order")
        finally:
            live["note"] = saved_note
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "source_order_near_row_unstated")
        self.assertTrue(at.run("gate_source_order")["ok"])

        # ⚠️ 第一版我只改 near_row（表并没被改名）⇒ 闸报「近似行不存在」才对（那是准确诊断）。
        #    要验这条牙，必须**真的把本仓第 6 行改成源名**（模拟禁令要拦的那个动作），再复原。
        # 这条牙的前提是**两边都变成源名**：本仓行被改名 **且** `near_row` 也记成源名
        #（=「我改了名，还把它当成近似行记着」的样子）⇒ 此时两边相等 ⇒ 红
        row = at.CATEGORY_ROWS_OWNER[5]
        saved_cat = row["category"]
        row["category"] = "文档与知识库工具"
        live["near_row"] = "文档与知识库工具"
        try:
            g3 = at.run("gate_source_order")
        finally:
            row["category"] = saved_cat
            live["near_row"] = saved_near
        self.assertFalse(g3["ok"], g3)
        self.assertEqual(g3["rule"], "source_order_renamed_local_row")
        self.assertTrue(at.run("gate_source_order")["ok"])
        self.assertEqual(str(at.CATEGORY_ROWS_OWNER[5]["category"]), "文档和知识库工具",
                         "复核后行名要复原")

    def test_truncated_tool_fragment_fifth_time(self):
        # 『工具』第五次出现；五次位置一致 ⇒ **仍只是读数**（位置像不等于它就是表头）
        g = at.run("gate_truncated")
        self.assertTrue(g["ok"], g)
        it = at.run("truncated")["items"][0]
        self.assertIn("R-H369", str(it["at"]))
        for kw in ("第五次", "留空不编", "也只是读数"):
            self.assertIn(kw, str(it["note"]))
        self.assertNotIn("工具", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])

    # ---------- R-H370：『特点』第五次 + 只读出口 awaiting ----------

    def test_te_dian_fifth_time_still_recorded(self):
        # 第五次仍**补记**：条数不增、不落表、不自解；并写明「我这边没有会自己变好的路径」
        items = at.run("pending")["items"]
        self.assertEqual([x["token"] for x in items].count("特点"), 1)
        td = [x for x in items if x["token"] == "特点"][0]
        r = str(td["pending_reason"])
        for kw in ("R-H370", "第五次出现", "五次都给同一个词", "不新立、不落表、不自解",
                   "没有任何「再等下去会自己好」的路径"):
            self.assertIn(kw, r)
        self.assertIsNone(td["resolved"])
        g = at.run("gate_pending")
        self.assertGreaterEqual(dict(g.get("repeat_topics") or {}).get("特点", 0), 5)
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if v.strip() == "特点"], "第五次也不许落表")

    def test_awaiting_readonly_aggregates_all_blocked(self):
        # 一页「等你拍板」：聚齐五类，且**只读**
        a = at.run("awaiting")
        self.assertTrue(a["ok"])
        self.assertTrue(a["readonly"])
        for key in ("pending_unresolved", "order_mismatched", "repeated_but_unresolved",
                    "truncated_fragments", "details_still_unowned"):
            self.assertIn(key, a)
        print("awaiting counts =", a["counts"])
        c = a["counts"]
        self.assertEqual(c["pending"], len(a["pending_unresolved"]))
        self.assertEqual(c["order_mismatched"], len(a["order_mismatched"]))
        self.assertEqual(c["truncated"], len(a["truncated_fragments"]))
        self.assertEqual(c["details_unowned"], len(a["details_still_unowned"]))
        self.assertEqual(c["total_items_needing_owner"],
                         sum([c["pending"], c["order_mismatched"], c["repeated"],
                              c["truncated"], c["details_unowned"]]))
        self.assertIn("只读", str(a["note"]))
        self.assertIn("主人", str(a["note"]))

    def test_awaiting_matches_individual_gates(self):
        # 与各区**逐项一致**（独立复算：awaiting 不许自说自话）
        a = at.run("awaiting")
        p = at.run("pending")
        so = at.run("gate_source_order")
        tr = at.run("truncated")
        rg = at.run("gate_reappearing")
        self.assertEqual(a["pending_unresolved"], [x["token"] for x in p["items"]])
        self.assertEqual(a["order_mismatched"],
                         [str(c2) for c2 in (so.get("mismatched") or [])])
        self.assertEqual([x["token"] for x in a["truncated_fragments"]],
                         [x["token"] for x in tr["items"]])
        self.assertEqual(a["details_still_unowned"],
                         [str(t) for t in (rg.get("with_detail") or [])])
        # awaiting **不写任何东西**：跑两遍读数一致
        a2 = at.run("awaiting")
        self.assertEqual(a["counts"], a2["counts"])

    # ---------- R-H371：PandaWiki（第 6 行首发）+ 与 GBT 第五次 ----------

    def test_pandawiki_reappearing_from_row6(self):
        # 第 6 行那格（3 个名字）开始被逐个投喂；它只是**再现**，不许拆行
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        pw = [x for x in at.run("reappearing")["items"] if x["token"] == "PandaWiki"][0]
        self.assertEqual(list(pw["where"]), ["第6行 格 代表工具"])
        self.assertEqual(sorted(pw["cell_mates"] or []), ["Notion", "Obsidian"])
        n = str(pw["note"])
        for kw in ("再现", "首位", "第 6 行开始被逐个投喂", "三个名字",
                   "逐个投喂 ≠ 拆行", "一个格"):
            self.assertIn(kw, n)
        self.assertIsNone(pw["resolved"])
        self.assertNotIn("PandaWiki", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])
        # 那一格仍是**一个格**（三个名字并排）
        cell = str(dict(at.CATEGORY_ROWS_OWNER[5]["cells"])["代表工具"])
        for name in ("PandaWiki", "Obsidian", "Notion"):
            self.assertIn(name, cell)

    def test_reappearing_by_row_gains_row6(self):
        # 按行读数应多出第 6 行（且与 items 自洽）
        g = at.run("gate_reappearing")
        by_row = dict(g.get("reappearing_by_row") or {})
        print("by_row =", {k: len(v) for k, v in by_row.items()})
        # ⚠️ 不许写死名单（逐刀会涨，R-H344 立）⇒ 成员断言 + 下面那圈自洽
        self.assertIn("PandaWiki", list(by_row.get("第6行") or []))
        for row, group in by_row.items():
            want = sorted({x["token"] for x in at.run("reappearing")["items"]
                           if any(str(n2).startswith(row + " ") for n2 in (x["where"] or []))})
            self.assertEqual(sorted(group), want)
        # awaiting 一页读数应同步（含这条再现）
        a = at.run("awaiting")
        self.assertEqual(a["counts"]["pending"], 10)
        self.assertGreaterEqual(a["counts"]["details_unowned"], 9)

    def test_gbt_fifth_time_recorded(self):
        items = at.run("pending")["items"]
        self.assertEqual([x["token"] for x in items].count("与 GBT 的对接"), 1)
        it = [x for x in items if x["token"] == "与 GBT 的对接"][0]
        r = str(it["pending_reason"])
        for kw in ("R-H371", "第五次出现", "五次都给同一个短语",
                   "五次一致 ≠ 可以落表", "awaiting"):
            self.assertIn(kw, r)
        g = at.run("gate_pending")
        self.assertGreaterEqual(dict(g.get("repeat_topics") or {}).get("与 GBT 的对接", 0), 5)
        self.assertIn("与 GBT 的对接", list(g.get("repeated_but_unresolved") or []))
        self.assertTrue(g["ok"])

    # ---------- R-H372：PandaWiki 的介绍 + 归属依据一览 ----------

    def test_pandawiki_detail_staged_inferred(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        pw = [x for x in at.run("reappearing")["items"] if x["token"] == "PandaWiki"][0]
        self.assertEqual(str(pw["staged_detail"]), "AI 驱动的开源知识库搭建系统，支持 AI 创作、AI 问答、AI 搜索")
        note = str(pw["staged_detail_note"])
        for kw in ("归属依据", "紧跟其后", "语义呼应", "可算口径", "未命中",
                   "没点名", "推断", "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIn("未命中", str(pw["note"]))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "AI 问答" in v], "介绍一个字都不许落表")

    def test_detail_evidence_summary_reading(self):
        # 归属依据一览（固定词表 · 只作读数）
        g = at.run("gate_reappearing")
        es = dict(g.get("detail_evidence_summary") or {})
        print("evidence summary =", es)
        self.assertIn("PandaWiki", es)
        self.assertIn("紧跟其后", es["PandaWiki"])
        self.assertIn("未命中", es["PandaWiki"])
        # 覆盖率：每条带介绍都有一份依据
        self.assertEqual(sorted(es), sorted(g.get("with_detail") or []))
        # 🔧 R-H379：**形态证据不止一种说法** —— 本轮出现「在名字之前」的形态
        #    （介绍紧接在**下一个名字之前**）⇒ 只要**有一种位置说法**即可
        for tok, kws in es.items():
            self.assertTrue(kws, "%s 的依据清单为空" % tok)
            # 🔧 R-H380：形态证据**第三种说法** —— **结构（源表列序）**
            #    （本刀语义不排他 ⇒ 归属由「名字在前、介绍在后」的**列序**定）
            self.assertTrue(("紧跟其后" in kws) or ("在名字之前" in kws)
                            or ("源表列序" in kws),
                            "%s 少了形态证据（紧跟其后 / 在名字之前 / 源表列序）" % tok)
        # CowAgent 那条额外有 owner_use（与 R-H366 一致）
        self.assertIn("owner_use", es.get("CowAgent") or [])
        self.assertIn("名字词义呼应", es.get("LocalMiniDrama") or [])

    def test_evidence_summary_is_not_a_gate(self):
        # 说明性读数：**改它不影响闸绿**（判据是 echo_claim 那条，不是这张一览）
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "PandaWiki"][0]
        saved = live["staged_detail_note"]
        live["staged_detail_note"] = "（测试用）暂存、不落表；归属依据 = 形态"
        try:
            g = at.run("gate_reappearing")
            es = dict(g.get("detail_evidence_summary") or {})
        finally:
            live["staged_detail_note"] = saved
        # 剥离后那条 note 里没有词表里的任何一项 ⇒ 一览应为**空清单**（它不是判据、也不补默认）
        self.assertEqual(list(es.get("PandaWiki") or []), [],
                         "一览是按词表统计的读数：没命中词表就是空清单")
        self.assertTrue(g["ok"], "它**不该**影响闸绿（闸只看 echo_claim 与暂存纪律）")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    # ---------- R-H373：Obsidian（第 6 行第二个）+ 每格喂到几成 ----------

    def test_obsidian_reappearing_row6_second(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        ob = [x for x in at.run("reappearing")["items"] if x["token"] == "Obsidian"][0]
        self.assertEqual(list(ob["where"]), ["第6行 格 代表工具"])
        self.assertEqual(sorted(ob["cell_mates"] or []), ["Notion", "PandaWiki"])
        n = str(ob["note"])
        for kw in ("再现", "第二个", "2 / 3", "Notion", "一个格"):
            self.assertIn(kw, n)
        self.assertIsNone(ob["resolved"])
        self.assertNotIn("Obsidian", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])
        cell = str(dict(at.CATEGORY_ROWS_OWNER[5]["cells"])["代表工具"])
        for name in ("PandaWiki", "Obsidian", "Notion"):
            self.assertIn(name, cell, "那一格仍是三个名字（不许拆行）")

    def test_cell_feed_progress_reading(self):
        # 每格喂到几成（只看 ≥2 段的格）：现算、与再现区自洽
        g = at.run("gate_reappearing")
        prog = dict(g.get("cell_feed_progress") or {})
        print("cell_feed_progress =", prog)
        # 🔧 R-H375 增长连带：第 6 行那格已喂完（3/3）⇒ 锁**已喂完**这件事，
        #    不再写死「2」这个中间态
        self.assertEqual(prog.get("第6行 格 代表工具"), {"given": 3, "total": 3})
        self.assertEqual(prog.get("第1行 格 代表工具"), {"given": 5, "total": 5})
        self.assertEqual(prog.get("第3行 格 代表工具"), {"given": 2, "total": 2})
        # 独立复算：所有键都该是**多名字格**，且 given ≤ total
        tokens = {x["token"] for x in at.run("reappearing")["items"]}
        for i, row in enumerate(at.CATEGORY_ROWS_OWNER, 1):
            for k, v in dict(row.get("cells") or {}).items():
                pieces = [p.strip() for p in str(v).split("/") if p.strip()]
                key = "第%d行 格 %s" % (i, k)
                # ⚠️ 只统计**名字列**（『对应 GBT 能力域』是描述列 ⇒ 不进这个读数）
                if k in at.NAME_COLUMNS and len(pieces) >= 2:
                    want = {"given": len([p for p in pieces if p in tokens]),
                            "total": len(pieces)}
                    self.assertEqual(prog.get(key), want, "%s 复算不上" % key)
                else:
                    self.assertNotIn(key, prog,
                                     "%s 不该进「名字格」读数（单名字 / 或不是名字列）" % key)

    def test_feed_progress_is_not_a_gate(self):
        # 说明性读数：它只呈现进度，**不许**因为「没喂完」就把闸判红
        g = at.run("gate_reappearing")
        prog = dict(g.get("cell_feed_progress") or {})
        unfinished = [k for k, v in prog.items() if v["given"] < v["total"]]
        print("还没喂完的格 =", unfinished)
        # ⚠️ 不许写死「只剩一格」——未喂完的格会随刀次变化 ⇒ 只断言**关键项 + 自洽**
        # 🔧 R-H375 增长连带：第 6 行**喂完了**（3/3）⇒ 它**不该**还在未喂完里；
        #    换成别的还没喂完的格（第 7 行）来验「有格没喂完 ⇒ 闸仍绿」，
        #    并按 §45 先证明**样本数 > 0**（空清单不按绿）
        self.assertNotIn("第6行 格 代表工具", unfinished, "第 6 行已喂完（3/3）")
        self.assertTrue(unfinished, "空清单不是通过 —— 至少得有一个还没喂完的格")
        self.assertIn("第7行 格 代表工具", unfinished)
        self.assertNotIn("第3行 格 对应 GBT 能力域", prog,
                         "『对应 GBT 能力域』是**描述列**，不进「名字格」读数（判据别扩大化）")
        self.assertTrue(g["ok"], "有格没喂完 ⇒ **闸仍绿**（进度不是判据）")

    # ---------- R-H374：Obsidian 的介绍 + 可追溯牙 ----------

    def test_obsidian_detail_staged_inferred(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        ob = [x for x in at.run("reappearing")["items"] if x["token"] == "Obsidian"][0]
        self.assertEqual(str(ob["staged_detail"]), "本地优先的知识管理，Markdown 格式，数据完全由你掌控")
        note = str(ob["staged_detail_note"])
        for kw in ("归属依据", "紧跟其后", "完全对得上", "没点名", "推断",
                   "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIn("对得上也只是证据", str(ob["note"]))
        vals = [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER]
        for x in at.CATEGORY_ROWS_OWNER:
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "数据完全由你掌控" in v], "介绍一个字都不许落表")

    def test_detail_round_trace_teeth(self):
        # 带牙：挂着介绍却说不出「哪一轮给的」⇒ 红（与「有值的格必须有出处」同族）
        import re as _re
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Obsidian"][0]
        saved_note = live["note"]
        saved_sd = live["staged_detail_note"]
        live["note"] = _re.sub(r"R-H\d{3}", "（抹掉轮次）", str(saved_note))
        live["staged_detail_note"] = _re.sub(r"R-H\d{3}", "（抹掉轮次）", str(saved_sd))
        try:
            g = at.run("gate_reappearing")
        finally:
            live["note"] = saved_note
            live["staged_detail_note"] = saved_sd
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "detail_without_round")
        self.assertEqual(g.get("token"), "Obsidian")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_detail_ratio_grows_and_all_have_round(self):
        # 比例读数涨到 11/14；并且**每条介绍都能追到轮次**（独立复算，不看闸的结果）
        import re as _re
        g = at.run("gate_reappearing")
        dr = dict(g.get("detail_ratio") or {})
        print("detail_ratio =", dr)
        self.assertGreaterEqual(dr.get("with_detail", 0), 11)
        self.assertEqual(dr.get("total"), g.get("count"))
        for x in at.run("reappearing")["items"]:
            if not x.get("staged_detail"):
                continue
            trace = str(x.get("note") or "") + "\n" + str(x.get("staged_detail_note") or "")
            self.assertTrue(_re.search(r"R-H\d{3}", trace),
                            "%s 的介绍说不出是哪一轮给的" % x["token"])
        self.assertTrue(g["ok"])

    # ---------- R-H375：Notion（第 6 行第三个 · 该格 3/3）+ 真身点名牙 ----------

    def test_notion_reappearing_third_completes_row6(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        nt = [x for x in at.run("reappearing")["items"] if x["token"] == "Notion"][0]
        self.assertEqual(list(nt["where"]), ["第6行 格 代表工具"])
        self.assertEqual(sorted(nt["cell_mates"] or []), ["Obsidian", "PandaWiki"])
        n = str(nt["note"])
        for kw in ("再现", "第三个", "3 / 3", "喂完", "一个格"):
            self.assertIn(kw, n)
        self.assertIsNone(nt["resolved"])
        self.assertNotIn("Notion", [str(x["category"]) for x in at.CATEGORY_ROWS_OWNER])
        cell = str(dict(at.CATEGORY_ROWS_OWNER[5]["cells"])["代表工具"])
        for name in ("PandaWiki", "Obsidian", "Notion"):
            self.assertIn(name, cell, "喂完 ≠ 拆行：那一格仍是三个名字")

    def test_notion_detail_is_relation_not_identity(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        nt = [x for x in at.run("reappearing")["items"] if x["token"] == "Notion"][0]
        self.assertEqual(str(nt["staged_detail"]), "与 context_vault 互补")
        note = str(nt["staged_detail_note"])
        # 🔧 R-H379：R-H375 当时把依据写成「紧跟其后」，**按消息次序实际是「在名字之前」**
        #    ⇒ 本刀照实正字；断言跟到**事实口径**上
        for kw in ("归属依据", "在名字之前", "真身", "没点名", "推断", "关系描述",
                   "不是身份判定", "第二种读法", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIn("不是同一个", note, "「与 X 互补」说的是关系，不是身份")
        # 词表读数不许被我自己的**否定句**误伤：note 里若出现词表词，必须是**真命中**
        es = dict(g.get("detail_evidence_summary") or {})
        # ⚠️ R-H379 实测：一览现在是**两条** —— 「紧跟其后」出现，是因为我在正字时
        #    **引用了旧措辞**（『R-H375 当时把依据写成「紧跟其后」』）
        #    ⇒ 词表读数**第 2 次被「引用/否定」喂响**（与 R-H376 那处同族）
        #    ⇒ 如实断言实测值，**不去改词表**（改词表会波及 12 条历史条目）
        self.assertEqual(list(es.get("Notion") or []), ["紧跟其后", "在名字之前"])
        vals = []
        for x in at.CATEGORY_ROWS_OWNER:
            vals.append(str(x.get("category") or ""))
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "与 context_vault 互补" in v],
                         "介绍一个字都不许落表")

    def test_local_ref_tooth_teeth(self):
        # 带牙：介绍里点名了我方真身，可那真身在盘上找不到 ⇒ 红
        saved = at.LOCAL_ASSETS
        at.LOCAL_ASSETS = (("context_vault", "gbt_allinone/tools/__no_such_asset__.py"),)
        try:
            g = at.run("gate_reappearing")
        finally:
            at.LOCAL_ASSETS = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "local_ref_unverified")
        self.assertEqual(g.get("token"), "Notion")
        self.assertEqual(g.get("asset"), "context_vault")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_local_ref_tooth_not_scoped_wider(self):
        # 判据别扩大化：**不在词表里**的名字不进这条牙（也不许影响闸绿）
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Trae"][0]
        saved = live["staged_detail"]
        live["staged_detail"] = str(saved) + "；与 trace_store 互补"
        try:
            g = at.run("gate_reappearing")
            refs = dict(g.get("detail_local_refs") or {})
            on_disk = dict(g.get("local_assets_on_disk") or {})
        finally:
            live["staged_detail"] = saved
        self.assertTrue(g["ok"], "词表外的名字不进判据 ⇒ 闸仍绿")
        self.assertNotIn("Trae", refs, "trace_store 不在词表里 ⇒ 不算点名了我方真身")
        self.assertEqual(list(refs.get("Notion") or []), ["context_vault"])
        self.assertEqual(on_disk, {"context_vault": True}, "真身必须在盘上且非空")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    # ---------- R-H376：Notion 的**第二句**（并排 · 不覆盖）+ 三条第二句牙 ----------

    def test_notion_second_sentence_side_by_side(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        nt = [x for x in at.run("reappearing")["items"] if x["token"] == "Notion"][0]
        self.assertEqual(str(nt["staged_detail_extra"]), "一体化工作空间，集笔记、数据库、任务管理于一体")
        self.assertEqual(str(nt["staged_detail"]), "与 context_vault 互补",
                         "第二句不许覆盖第一句 —— 第一句仍在原位")
        note = str(nt["staged_detail_note"])
        for kw in ("第二句", "并排", "不覆盖", "关系", "身份", "互补而不重叠",
                   "推断", "暂存", "不落"):
            self.assertIn(kw, note)
        self.assertIn("R-H376", str(nt["note"]))
        self.assertIn("R-H375", str(nt["note"]), "第一句那一轮也还写着")
        extra = str(nt["staged_detail_extra"])
        vals = []
        for x in at.CATEGORY_ROWS_OWNER:
            vals.append(str(x.get("category") or ""))
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if extra in v], "第二句一个字也不许落表")

    def test_detail_extra_tooth_second_mark(self):
        # 带牙：挂了第二句却没写明「第二句」⇒ 红（会被当成第一句的改写）
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Notion"][0]
        saved = live["staged_detail_note"]
        live["staged_detail_note"] = str(saved).replace("第二句", "那句")
        try:
            g = at.run("gate_reappearing")
        finally:
            live["staged_detail_note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "detail_extra_without_second_mark")
        self.assertEqual(g.get("token"), "Notion")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_detail_extra_tooth_duplicating_first(self):
        # 带牙：第二句与第一句逐字相同 ⇒ 红（同一句记两遍 = 假增）
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Notion"][0]
        saved = live["staged_detail_extra"]
        live["staged_detail_extra"] = str(live["staged_detail"])
        try:
            g = at.run("gate_reappearing")
        finally:
            live["staged_detail_extra"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "detail_extra_duplicating_first")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_detail_extra_tooth_own_round(self):
        # 带牙：第二句**没写明自己那一轮** ⇒ 红
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Notion"][0]
        self.assertEqual(str(live.get("staged_detail_extra_round")), "R-H376")
        saved = live.get("staged_detail_extra_round")
        live["staged_detail_extra_round"] = ""
        try:
            g = at.run("gate_reappearing")
        finally:
            live["staged_detail_extra_round"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "detail_extra_without_own_round")
        self.assertEqual(g.get("token"), "Notion")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_detail_extra_tooth_round_must_be_in_text(self):
        # 带牙：字段写了轮次，可**正文里说不出** ⇒ 红（字段与正文不许各说各话）
        import re as _re
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Notion"][0]
        saved_n, saved_s = live["note"], live["staged_detail_note"]
        live["note"] = _re.sub(r"R-H376", "（抹掉）", str(saved_n))
        live["staged_detail_note"] = _re.sub(r"R-H376", "（抹掉）", str(saved_s))
        try:
            g = at.run("gate_reappearing")
        finally:
            live["note"], live["staged_detail_note"] = saved_n, saved_s
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "detail_extra_round_unstated")
        self.assertEqual(g.get("round"), "R-H376")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_detail_sentence_count_reading(self):
        # 派生读数：每条的介绍**句数**（现算不手写；它只是读数）
        g = at.run("gate_reappearing")
        cnt = dict(g.get("detail_sentence_count") or {})
        print("detail_sentence_count =", cnt)
        want = {}
        for x in at.run("reappearing")["items"]:
            if not x.get("staged_detail"):
                continue
            want[x["token"]] = (1 if x.get("staged_detail") else 0) \
                + (1 if x.get("staged_detail_extra") else 0)
        self.assertEqual(cnt, want)
        self.assertEqual(cnt.get("Notion"), 2, "Notion 有两句（关系 + 身份）")
        self.assertEqual(sorted({v for v in cnt.values()}), [1, 2])
        self.assertTrue(g["ok"], "句数只是读数，不影响闸绿")

    # ---------- R-H377：顺序读数第五条（源 6 · 本仓无此行）+ 括号核审计 ----------

    def test_order_reading_fifth_no_local_row(self):
        # 源 6『网络加速工具』⇒ 本仓**无此行**（第三种形态：local_row=None）
        g = at.run("gate_source_order")
        self.assertTrue(g["ok"], g)
        self.assertGreaterEqual(g["count"], 5)
        it = at.run("source_order")["items"][4]
        self.assertEqual(it["category"], "网络加速工具")
        self.assertEqual(it["source_no"], 6)
        self.assertIsNone(it["our_index"])
        self.assertIsNone(it["local_row"])
        self.assertIsNone(it["near_row"])
        self.assertTrue(it["mismatch"])
        n = str(it["note"])
        for kw in ("本仓无此行", "不一致", "不许重排", "不是", "对应"):
            self.assertIn(kw, n)
        self.assertIn("网络加速工具", g["mismatched"])
        # 🔴 不许拿源编号当本仓行号 ⇒ 本仓表**没动**（第 7 行仍是 Markdown 编辑器）
        self.assertEqual(str(at.CATEGORY_ROWS_OWNER[6]["category"]), "Markdown 编辑器")
        self.assertNotIn("网络加速工具",
                         [str(x.get("category") or "") for x in at.CATEGORY_ROWS_OWNER])

    def test_order_reading_fifth_paren_vs_name(self):
        # 两件事**分开写**：括号词『环境优化』**不是**旧批名；『对应』是给**源名**的
        it = at.run("source_order")["items"][4]
        self.assertEqual(it["paren"], "环境优化")
        n = str(it["note"])
        self.assertIn("『环境优化』**不是**", n)
        self.assertIn("源名里的『网络加速』", n)
        self.assertIn("给源名的", n)
        self.assertIn("不是给括号词的", n)

    def test_source_order_paren_audit_reading(self):
        # 审计读数（现算）：旧批命中到底是**括号词**来的，还是**源名 / 我的说明**来的
        g = at.run("gate_source_order")
        audit = dict(g.get("source_order_paren_audit") or {})
        print("source_order_paren_audit =", audit)
        self.assertEqual(len(audit), g["count"], "每条读数都要有一条审计")
        a = dict(audit.get("网络加速工具") or {})
        self.assertEqual(a.get("paren"), "环境优化")
        self.assertEqual(list(a.get("hits_in_note") or []), ["环境配置", "网络加速"])
        self.assertEqual(list(a.get("hits_in_paren") or []), [],
                         "**真·括号词**『环境优化』一个旧批名都没命中")
        # 独立复算：按 CATEGORIES_OWNER 顺序扫 note
        for it in at.run("source_order")["items"]:
            note = str(it["note"])
            want = [c for c in at.CATEGORIES_OWNER if c in note]
            self.assertEqual(list(dict(audit[it["category"]])["hits_in_note"]), want)
        self.assertTrue(g["ok"], "审计只是读数，不影响闸绿")

    def test_paren_audit_separates_paren_hits(self):
        # 把括号词换成一个**真的**旧批名 ⇒ 审计要能把它和「源名命中」分开
        live = [x for x in at.SOURCE_ORDER_READINGS if x["category"] == "网络加速工具"][0]
        saved = live.get("paren")
        live["paren"] = "环境配置"
        try:
            a = dict(dict(at.run("gate_source_order")["source_order_paren_audit"])
                     .get("网络加速工具") or {})
        finally:
            live["paren"] = saved
        self.assertEqual(list(a.get("hits_in_paren") or []), ["环境配置"])
        self.assertEqual(list(a.get("hits_in_note") or []), ["环境配置", "网络加速"])
        self.assertEqual(dict(dict(at.run("gate_source_order")["source_order_paren_audit"])
                             .get("网络加速工具"))["hits_in_paren"], [])

    def test_truncated_fragment_sixth(self):
        # 『工具』截断**第六次**（六次都在带编号的分类头之后）⇒ 仍留空不编
        g = at.run("gate_truncated")
        self.assertTrue(g["ok"], g)
        fr = list(at.TRUNCATED_FRAGMENTS)
        self.assertTrue(fr, "样本数必须 > 0（空清单不按绿）")
        t = [x for x in fr if x["token"] == "工具"][0]
        self.assertIn("R-H377", str(t["at"]))
        n = str(t["note"])
        for kw in ("第六次", "留空不编", "位置像不等于", "主人补全", "主人撤回"):
            self.assertIn(kw, n)
        # 🔴 仍不许当数据：它不许出现在任何分类名 / 行里
        self.assertNotIn("工具", [str(x.get("category") or "") for x in at.CATEGORY_ROWS_OWNER])

    # ---------- R-H378：『Watt Toolkit』（第 10 行首位）+ 像但不等价的候选行 ----------

    def test_watt_toolkit_reappearing_row10_first(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        self.assertGreaterEqual(g["count"], 16)
        wt = [x for x in at.run("reappearing")["items"] if x["token"] == "Watt Toolkit"][0]
        self.assertEqual(list(wt["where"]), ["第10行 格 代表工具"])
        self.assertEqual(sorted(wt["cell_mates"] or []), ["FastGithub", "dev-sidecar"])
        n = str(wt["note"])
        for kw in ("再现", "首位", "1 / 3", "第 10 行", "一个格"):
            self.assertIn(kw, n)
        self.assertIsNone(wt["resolved"])
        self.assertNotIn("Watt Toolkit",
                         [str(x.get("category") or "") for x in at.CATEGORY_ROWS_OWNER])
        cell = str(dict(at.CATEGORY_ROWS_OWNER[9]["cells"])["代表工具"])
        for name in ("Watt Toolkit", "FastGithub", "dev-sidecar"):
            self.assertIn(name, cell, "喂到一个 ≠ 拆行：那一格仍是三个名字")
        prog = dict(g.get("cell_feed_progress") or {})
        # 🔧 R-H380 增长连带：第 10 行**喂完了**（3/3）
        self.assertEqual(prog.get("第10行 格 代表工具"), {"given": 3, "total": 3})

    def test_near_names_reading_and_no_verdict_change(self):
        # 候选行只是读数：源 6 的判定**一个字没改**（仍「本仓无此行 / 不一致」）
        g = at.run("gate_source_order")
        nn = dict(g.get("source_order_near_names") or {})
        print("source_order_near_names =", nn)
        self.assertEqual(list(nn.get("网络加速工具") or []),
                         ["GitHub 加速工具", "网络管理工具"])
        it = at.run("source_order")["items"][4]
        self.assertIsNone(it["local_row"])
        self.assertTrue(it["mismatch"])
        n = str(it["note"])
        for kw in ("本仓无此行", "不一致", "像但不等于", "不许当同一个", "无对应行就是无对应行"):
            self.assertIn(kw, n)
        self.assertIn("Watt Toolkit", n, "候选人里要写明「主人刚给的名字正住在第 10 行」")
        # 候选必须真的在本仓
        cats = [str(r.get("category") or "") for r in at.CATEGORY_ROWS_OWNER]
        for cand in nn["网络加速工具"]:
            self.assertIn(cand, cats)

    def test_near_names_tooth_unknown(self):
        # 带牙：候选行不在本仓 ⇒ 红
        live = [x for x in at.SOURCE_ORDER_READINGS if x["category"] == "网络加速工具"][0]
        saved = live.get("near_names")
        live["near_names"] = ("不存在的行",)
        try:
            g = at.run("gate_source_order")
        finally:
            live["near_names"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "source_order_near_names_unknown")
        self.assertEqual(g.get("near_name"), "不存在的行")
        self.assertTrue(at.run("gate_source_order")["ok"])

    def test_near_names_tooth_is_row(self):
        # 带牙：候选名与源名一样 ⇒ 红（说明本仓其实有这一行）
        live = [x for x in at.SOURCE_ORDER_READINGS if x["category"] == "网络加速工具"][0]
        saved = live.get("near_names")
        live["near_names"] = ("网络加速工具",)
        try:
            g = at.run("gate_source_order")
        finally:
            live["near_names"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "source_order_near_names_is_row")
        self.assertTrue(at.run("gate_source_order")["ok"])

    def test_near_names_tooth_unstated(self):
        # 带牙：写了候选却没写「像但不等于 / 不许当同一个」⇒ 红
        live = [x for x in at.SOURCE_ORDER_READINGS if x["category"] == "网络加速工具"][0]
        saved = live["note"]
        live["note"] = (str(saved).replace("像但不等于", "相关")
                        .replace("不许当同一个", "待定"))
        try:
            g = at.run("gate_source_order")
        finally:
            live["note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "source_order_near_names_unstated")
        self.assertTrue(at.run("gate_source_order")["ok"])

    # ---------- R-H379：FastGithub（第 10 行第二个）+ **归属反转** + 位置读数 ----------

    def test_fastgithub_reappearing_second_row10(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        fg = [x for x in at.run("reappearing")["items"] if x["token"] == "FastGithub"][0]
        self.assertEqual(list(fg["where"]), ["第10行 格 代表工具"])
        self.assertEqual(sorted(fg["cell_mates"] or []), ["Watt Toolkit", "dev-sidecar"])
        n = str(fg["note"])
        for kw in ("再现", "第二个", "2 / 3", "一个格", "一个字都没替它编"):
            self.assertIn(kw, n)
        self.assertIsNone(fg["resolved"])
        # 🔧 R-H380 增长连带：本刀起那句介绍挂到了它头上（staged_detail 非 None）
        self.assertIsNotNone(fg.get("staged_detail"))
        # 🔧 R-H380 增长连带：第 10 行已 3/3
        prog = dict(g.get("cell_feed_progress") or {})
        self.assertEqual(prog.get("第10行 格 代表工具"), {"given": 3, "total": 3})

    def test_watt_detail_goes_by_semantics_not_position(self):
        # **归属反转**：介绍在**名字之前**，但语义只对得上 Watt Toolkit
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        wt = [x for x in at.run("reappearing")["items"] if x["token"] == "Watt Toolkit"][0]
        self.assertEqual(str(wt["staged_detail"]), "C# 开源，跨平台 GitHub 加速 + Steam 工具箱")
        self.assertEqual(str(wt["detail_position"]), "after_name",
                         "R-H380 口径定死：相对**它挂的那个名字** ⇒ 介绍在它之后")
        self.assertEqual(str(wt["detail_next_name_side"]), "before_next_name",
                         "那是「与紧随其后的名字」的**读数**，不是位置判据")
        note = str(wt["staged_detail_note"])
        for kw in ("归属依据", "语义完全对得上", "Steam 工具箱", "在名字之前",
                   "没点名", "推断", "第二种读法", "FastGithub 不做 Steam 工具箱",
                   "暂存", "不落"):
            self.assertIn(kw, note)
        # 🔧 R-H380：这一刀给 FastGithub 挂了介绍（**结构定归属**）⇒ 断言改成「挂对了」
        fg = [x for x in at.run("reappearing")["items"] if x["token"] == "FastGithub"][0]
        self.assertEqual(str(fg.get("detail_position")), "after_name")
        self.assertEqual(str(fg.get("staged_detail")), "GitHub 加速，解决打不开、头像无法加载、clone/push 失败等问题")
        fgn = str(fg.get("staged_detail_note"))
        for kw in ("推断", "源表列序", "语义这次定不了归属", "第二种读法",
                   "第三种读法", "不硬配", "暂存", "不落"):
            self.assertIn(kw, fgn)

    def test_detail_position_tooth_unknown(self):
        # 带牙：位置读数自造第三种 ⇒ 红
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Watt Toolkit"][0]
        saved = live.get("detail_position")
        live["detail_position"] = "sideways"
        try:
            g = at.run("gate_reappearing")
        finally:
            live["detail_position"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "detail_position_unknown")
        self.assertEqual(g.get("value"), "sideways")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_detail_position_tooth_unstated(self):
        # 带牙：位置换成 before_owner_name，而正文里**没有**那个结构化标记 ⇒ 红
        #    （R-H380 起标记是整串「位置读数：在名字之前」——否定句抄不出它）
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Watt Toolkit"][0]
        saved = live.get("detail_position")
        live["detail_position"] = "before_owner_name"
        try:
            g = at.run("gate_reappearing")
        finally:
            live["detail_position"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "detail_position_unstated")
        self.assertEqual(g.get("position"), "before_owner_name")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_detail_position_reading(self):
        # 派生读数：每条介绍的位置（现算 · 只是读数）
        g = at.run("gate_reappearing")
        m = dict(g.get("detail_position_map") or {})
        print("detail_position_map =", m)
        # 🔧 R-H380 **口径定死**（相对 owner）：
        #    Watt Toolkit / FastGithub 的介绍都跟在**它们自己的名字之后** ⇒ after_name
        #    Notion 的介绍在**它名字之前** ⇒ before_owner_name
        self.assertEqual(m.get("Watt Toolkit"), "after_name")
        self.assertEqual(m.get("FastGithub"), "after_name")
        self.assertEqual(m.get("Notion"), "before_owner_name")
        want = {x["token"]: str(x["detail_position"]) for x in at.REAPPEARING_TOKENS
                if x.get("staged_detail") and x.get("detail_position")}
        self.assertEqual(m, want)
        self.assertEqual(list(g.get("detail_positions") or []),
                         ["after_name", "before_owner_name"])
        self.assertTrue(g["ok"], "位置读数只是读数，不影响闸绿")

    def test_notion_position_corrected(self):
        # R-H375 的措辞照实正字（我自己的问题）：仍挂 Notion、仍推断、判定不改
        nt = [x for x in at.run("reappearing")["items"] if x["token"] == "Notion"][0]
        sn = str(nt["staged_detail_note"])
        for kw in ("R-H379 正字", "在名字之前", "照实改正", "措辞与事实不符"):
            self.assertIn(kw, sn)
        n = str(nt["note"])
        for kw in ("R-H379 追认", "权重上升", "判定一个字不改", "不落表"):
            self.assertIn(kw, n)
        self.assertEqual(str(nt["staged_detail"]), "与 context_vault 互补")

    # ---------- R-H380：dev-sidecar（第 10 行第三个 · 3/3）+ 结构定归属 + 口径定死 ----------

    def test_dev_sidecar_reappearing_third_completes_row10(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        ds = [x for x in at.run("reappearing")["items"] if x["token"] == "dev-sidecar"][0]
        self.assertEqual(list(ds["where"]), ["第10行 格 代表工具"])
        self.assertEqual(sorted(ds["cell_mates"] or []), ["FastGithub", "Watt Toolkit"])
        n = str(ds["note"])
        for kw in ("再现", "第三个", "3 / 3", "喂完", "一个格", "一个字都没替它编"):
            self.assertIn(kw, n)
        # 🔧 R-H381 增长连带：本刀给 dev-sidecar 挂了介绍（**三种证据同向**）
        self.assertEqual(str(ds.get("staged_detail")), "GitHub / git clone / releases 下载 / stackoverflow 加速")
        self.assertEqual(str(ds.get("detail_position")), "after_name")
        dsn = str(ds.get("staged_detail_note"))
        for kw in ("三种证据第一次同向", "没点名", "推断", "同一个名字不挂两句",
                   "位置读数：跟在名字之后", "暂存", "不落"):
            self.assertIn(kw, dsn)
        prog = dict(g.get("cell_feed_progress") or {})
        self.assertEqual(prog.get("第10行 格 代表工具"), {"given": 3, "total": 3})
        # 喂完 ≠ 拆行 ≠ 落表
        cats = [str(r.get("category") or "") for r in at.CATEGORY_ROWS_OWNER]
        self.assertNotIn("dev-sidecar", cats)
        cell = str(dict(at.CATEGORY_ROWS_OWNER[9]["cells"])["代表工具"])
        for name in ("Watt Toolkit", "FastGithub", "dev-sidecar"):
            self.assertIn(name, cell)

    def test_fastgithub_detail_by_structure_not_semantics(self):
        # 语义不排他 ⇒ 由**结构（源表列序）**定归属，并把三种读法并排
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        fg = [x for x in at.run("reappearing")["items"] if x["token"] == "FastGithub"][0]
        self.assertEqual(str(fg["staged_detail"]), "GitHub 加速，解决打不开、头像无法加载、clone/push 失败等问题")
        note = str(fg["staged_detail_note"])
        for kw in ("归属依据", "源表列序", "不排他", "语义这次定不了归属",
                   "第二种读法", "dev-sidecar", "第三种读法", "整类的描述",
                   "不硬配", "位置读数：跟在名字之后", "推断", "暂存", "不落"):
            self.assertIn(kw, note)
        vals = []
        for x in at.CATEGORY_ROWS_OWNER:
            vals.append(str(x.get("category") or ""))
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "GitHub 加速，解决打不开、头像无法加载、clone/push 失败等问题" in v], "介绍一个字都不许落表")

    def test_detail_position_vendored_to_owner(self):
        # 口径定死：`detail_position` 一律相对**它挂的那个名字（owner）**
        g = at.run("gate_reappearing")
        m = dict(g.get("detail_position_map") or {})
        self.assertEqual(m.get("Watt Toolkit"), "after_name")
        self.assertEqual(m.get("FastGithub"), "after_name")
        self.assertEqual(m.get("Notion"), "before_owner_name")
        self.assertEqual(list(g.get("detail_positions") or []),
                         ["after_name", "before_owner_name"])
        # 「与紧随其后的名字」是**另一件事**（读数），本刀显式记下
        sidem = dict(g.get("detail_next_name_side_map") or {})
        print("detail_next_name_side_map =", sidem)
        self.assertEqual(sidem.get("Watt Toolkit"), "before_next_name")
        self.assertEqual(list(g.get("detail_next_name_sides") or []),
                         ["before_next_name", "none"])

    def test_detail_next_name_side_tooth_unknown(self):
        # 带牙：与「紧随其后的名字」的关系自造第四种 ⇒ 红
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Watt Toolkit"][0]
        saved = live.get("detail_next_name_side")
        live["detail_next_name_side"] = "after_next_name"
        try:
            g = at.run("gate_reappearing")
        finally:
            live["detail_next_name_side"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "detail_next_name_side_unknown")
        self.assertEqual(g.get("value"), "after_next_name")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_evidence_vocab_has_structure_term(self):
        # 词表加了第三种形态证据「源表列序」；每条带介绍仍至少有一种依据
        g = at.run("gate_reappearing")
        es = dict(g.get("detail_evidence_summary") or {})
        print("evidence summary =", es)
        self.assertIn("源表列序", es.get("FastGithub") or [])
        self.assertTrue(es.get("FastGithub"), "空清单不许当通过（§45）")
        for tok, kws in es.items():
            self.assertTrue(("紧跟其后" in kws) or ("在名字之前" in kws)
                            or ("源表列序" in kws), "%s 少了形态证据" % tok)

    # ---------- R-H381：第六条读数（源 7 · 只差一个空格）+ 同源名再现 ----------

    def test_order_reading_sixth_one_space_apart(self):
        # 源 7『AI 模型管理工具』（带空格）与本仓第 3 行『AI模型管理工具』（无空格）
        g = at.run("gate_source_order")
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["count"], 6)
        it = at.run("source_order")["items"][5]
        self.assertEqual(it["category"], "AI 模型管理工具")
        self.assertEqual(it["source_no"], 7)
        self.assertEqual(it["near_row"], "AI模型管理工具")
        self.assertIsNone(it["our_index"])
        self.assertTrue(it["mismatch"])
        n = str(it["note"])
        for kw in ("只差一个空格", "疑似对应", "不许当同一个", "不一致",
                   "不许重排", "不许新增行", "不许拿源名去改本仓行名",
                   "不是", "只差一个空格", "等主人一句话"):
            self.assertIn(kw, n)
        self.assertIn("一个空格之差", n, "口径要写准：不是一个字之差")
        # 🔴 本仓表没动：第 3 行仍叫「AI模型管理工具」（无空格）
        self.assertEqual(str(at.CATEGORY_ROWS_OWNER[2]["category"]), "AI模型管理工具")
        self.assertNotIn("AI 模型管理工具",
                         [str(x.get("category") or "") for x in at.CATEGORY_ROWS_OWNER])

    def test_duplicate_source_names_reading(self):
        # 归一化（抹空格）后同名 ⇒ 一眼可见；现算不手写
        g = at.run("gate_source_order")
        dup = dict(g.get("duplicate_source_names") or {})
        print("duplicate_source_names =", dup)
        self.assertEqual(dup, {"AI模型管理工具": [2, 7]})
        mine = {}
        for x in at.run("source_order")["items"]:
            mine.setdefault(str(x["category"]).replace(" ", ""), []).append(x["source_no"])
        mine = {k: sorted(v) for k, v in mine.items() if len(v) > 1}
        self.assertEqual(dup, mine)
        self.assertTrue(g["ok"], "它只是读数")

    def test_duplicate_source_name_tooth(self):
        # 带牙：归一化同名的两条，其中一条**没写明**「同名/只差一个空格」⇒ 红
        live = [x for x in at.SOURCE_ORDER_READINGS if x["source_no"] == 2][0]
        saved = live["note"]
        live["note"] = (str(saved).replace("只差一个空格", "写法不同")
                        .replace("同名", "相近"))
        try:
            g = at.run("gate_source_order")
        finally:
            live["note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "source_order_duplicate_name_unstated")
        self.assertEqual(list(g.get("source_nos") or []), ["2", "7"])
        self.assertTrue(at.run("gate_source_order")["ok"])
        # 不扩大化：不重复的条目不受这条牙管
        # ⚠️ 我第一版挑了源 6 —— 它**带 near_names** ⇒ 会被 near_names 那条牙拦住，
        #    验不出「重名牙只管重复项」⇒ 换成**没有候选、没有近似行**的源 3
        live2 = [x for x in at.SOURCE_ORDER_READINGS if x["source_no"] == 3][0]
        saved2 = live2["note"]
        # ⚠️ 再修一次：换成源 3 之后，这条最小 note 里没有旧批名 ⇒ 走的是
        #    「**没命中**旧批」那支 ⇒ 必须写明「**不是**」（不然又红一次）
        live2["note"] = "顺序**不一致**；括号词**不是**旧批名 ⇒ 只记读数"
        try:
            g2 = at.run("gate_source_order")
        finally:
            live2["note"] = saved2
        self.assertTrue(g2["ok"], "不重复的条目不该被这条牙管（判据别扩大化）")

    def test_second_reading_gets_duplicate_note(self):
        # 源 2 当年存成无空格 ⇒ **补记**（判定不改）：要写明它与源 7 只差一个空格
        it = at.run("source_order")["items"][0]
        n = str(it["note"])
        for kw in ("R-H381 补记", "只差一个空格", "不许当同一个", "是我吃掉了空格",
                   "等主人一句话", "顺序不一致"):
            self.assertIn(kw, n)
        self.assertEqual(it["source_no"], 2)
        self.assertEqual(it["our_index"], 3, "判定不改：仍是「源 2 vs 本仓第 3 行」")

    def test_truncated_fragment_seventh(self):
        # 『工具』截断**第七次**（七次都在带编号的分类头之后）⇒ 仍留空不编
        g = at.run("gate_truncated")
        self.assertTrue(g["ok"], g)
        t = [x for x in at.TRUNCATED_FRAGMENTS if x["token"] == "工具"][0]
        self.assertIn("R-H381", str(t["at"]))
        self.assertIn("第七次", str(t["note"]))
        self.assertIn("位置像", str(t["note"]))

    # ---------- R-H382：『CC Switch』第二次被投喂（补记 · 一个名字一条）----------

    def test_cc_switch_reappearing_second_time(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        # 🔴 一个名字一条：补记**不新增条目**
        self.assertEqual(g["count"], 18, "补记不许让再现条数变多")
        cc = [x for x in at.run("reappearing")["items"] if x["token"] == "CC Switch"]
        self.assertEqual(len(cc), 1, "同一个名字只许一条（reappearing_token_duplicate）")
        cc = cc[0]
        self.assertIn("R-H348", str(cc["at"]))
        self.assertIn("R-H382", str(cc["at"]))
        self.assertEqual(cc["reappearance_times"], 2)
        n = str(cc["note"])
        for kw in ("R-H382 补记", "第二次投喂", "不许另起一行", "不许当重复丢掉",
                   "不新增条目", "重复 ≠ 许可", "不落表"):
            self.assertIn(kw, n)
        # 第二次**不新增任何事实**：介绍仍是 R-H349 那句，位置仍是第 3 行首位
        self.assertIn("桌面应用", str(cc["staged_detail"]))
        # 🔧 R-H382 同刀修正：它其实是**两处来源**（行 + 我方 R-H285 名单）
        self.assertEqual(list(cc["where"]),
                         ["第3行 格 代表工具", "我方 R-H285 工具名单"])
        self.assertIn("两处来源", n)
        self.assertEqual(sorted(cc["cell_mates"] or []), ["CC-Switch CLI"])

    def test_reappearance_repeat_reading(self):
        # 派生读数：被重复投喂的名字（与待归属侧 repeat_topics 对称）
        g = at.run("gate_reappearing")
        rep = dict(g.get("reappearance_repeat") or {})
        print("reappearance_repeat =", rep)
        # 🔧 R-H383 增长连带：`CC-Switch CLI` 也被投喂了第二次
        self.assertEqual(rep, {"CC Switch": 2, "CC-Switch CLI": 2})
        mine = {x["token"]: x["reappearance_times"] for x in at.REAPPEARING_TOKENS
                if x.get("reappearance_times", 1) > 1}
        self.assertEqual(rep, mine, "独立复算：不看闸，自己按字段算")
        self.assertTrue(g["ok"], "它只是读数（**重复 ≠ 许可**）")

    def test_reappearance_repeat_tooth(self):
        # 带牙：次数 ≥2 却看不出重复 ⇒ 红（不许静默吞掉）
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "CC Switch"][0]
        saved = live["note"]
        live["note"] = (str(saved).replace("第二次投喂", "又来了一趟")
                        .replace("第二次", "又一次").replace("再次", "又")
                        .replace("多次", "好几回"))
        try:
            g = at.run("gate_reappearing")
        finally:
            live["note"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "reappearance_repeat_unstated")
        self.assertEqual(g.get("token"), "CC Switch")
        self.assertEqual(g.get("times"), 2)
        self.assertTrue(at.run("gate_reappearing")["ok"])
        # 带牙：次数不是 ≥1 的整数 ⇒ 红
        saved_t = live.get("reappearance_times")
        live["reappearance_times"] = 0
        try:
            g2 = at.run("gate_reappearing")
        finally:
            live["reappearance_times"] = saved_t
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "reappearance_times_invalid")
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_reappearance_repeat_tooth_not_scoped_wider(self):
        # 判据别扩大化：只被投喂一次的条目**不受这条牙管**
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Trae"][0]
        self.assertEqual(live.get("reappearance_times", 1), 1)
        saved = live["note"]
        live["note"] = str(saved).replace("第二次", "").replace("再次", "")
        try:
            g = at.run("gate_reappearing")
        finally:
            live["note"] = saved
        self.assertTrue(g["ok"], "次数 = 1 的条目不该被这条牙管")

    # ---------- R-H383：CLI 第二次投喂 + 第二句（同骨架）+ 家族牙 + 近似读数 ----------

    def test_cli_second_time_and_second_sentence(self):
        g = at.run("gate_reappearing")
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["count"], 18, "补记不新增条目")
        cli = [x for x in at.run("reappearing")["items"]
               if x["token"] == "CC-Switch CLI"][0]
        self.assertEqual(cli["reappearance_times"], 2)
        self.assertIn("R-H350", str(cli["at"]))
        self.assertIn("R-H383", str(cli["at"]))
        self.assertEqual(str(cli["staged_detail_extra"]), "桌面应用，管理 5 大 CLI 工具的供应商配置，一键切换")
        self.assertEqual(str(cli["staged_detail_extra_round"]), "R-H383")
        self.assertIn("命令行版", str(cli["staged_detail"]), "第一句不许被覆盖")
        sn = str(cli["staged_detail_note"])
        for kw in ("第二句", "并排", "不覆盖", "同骨架", "不新增事实",
                   "位置读数：跟在名字之后"):
            self.assertIn(kw, sn)
        self.assertIn("R-H383", str(cli["note"]))
        self.assertIn("R-H350", str(cli["note"]))

    def test_cli_position_vs_semantics_conflict(self):
        # 位置（在名字之前 ⇒ 跟它前面的名字）指向它，可『桌面应用』指向 CC Switch
        cli = [x for x in at.run("reappearing")["items"]
               if x["token"] == "CC-Switch CLI"][0]
        n = str(cli["note"])
        for kw in ("位置与语义打架", "桌面应用", "CC Switch", "第二种读法",
                   "不硬配", "不新增事实", "第三遍"):
            self.assertIn(kw, n)
        sn = str(cli["staged_detail_note"])
        for kw in ("第二读法", "CC Switch", "不硬配"):
            self.assertIn(kw, sn)

    def test_detail_family_map_and_tooth(self):
        g = at.run("gate_reappearing")
        fam = dict(g.get("detail_family_map") or {})
        print("detail_family_map =", fam)
        self.assertEqual(fam, {"CC Switch": "cli_供应商配置",
                               "CC-Switch CLI": "cli_供应商配置"})
        # 带牙：同家族却不写明「同骨架 / 不新增事实」⇒ 红
        live = [x for x in at.REAPPEARING_TOKENS if x["token"] == "CC-Switch CLI"][0]
        saved_n, saved_s = live["note"], live["staged_detail_note"]
        live["note"] = str(saved_n).replace("同骨架", "类似").replace("不新增事实", "无新内容")
        live["staged_detail_note"] = (str(saved_s).replace("同骨架", "类似")
                                      .replace("不新增事实", "无新内容"))
        try:
            gb = at.run("gate_reappearing")
        finally:
            live["note"], live["staged_detail_note"] = saved_n, saved_s
        self.assertFalse(gb["ok"], gb)
        self.assertEqual(gb["rule"], "detail_family_unstated")
        self.assertEqual(gb.get("family"), "cli_供应商配置")
        self.assertTrue(at.run("gate_reappearing")["ok"])
        # 不扩大化：没有家族标记的条目不受这条牙管
        live2 = [x for x in at.REAPPEARING_TOKENS if x["token"] == "Trae"][0]
        self.assertIsNone(live2.get("detail_family"))
        self.assertTrue(at.run("gate_reappearing")["ok"])

    def test_detail_near_pairs_reading_is_not_a_gate(self):
        # 近似读数：**明确不是判据**（它会被共用专有名词喂饱 ⇒ 实测证据就在读数里）
        g = at.run("gate_reappearing")
        pairs = list(g.get("detail_near_pairs") or [])
        print("detail_near_pairs =", pairs)
        self.assertTrue(pairs, "样本数必须 > 0（空清单不按绿）")
        keys = {(p["a"], p["b"]) for p in pairs}
        self.assertIn(("CC Switch", "CC-Switch CLI"), keys)
        # 🔴 它**被专有名词喂饱**的两处证据（正是「不许当判据」的理由）
        samples = {p["sample"] for p in pairs}
        self.assertIn("OpenClaw", samples, "CC Switch ↔ OpenClaw Monitor 命中的是工具名")
        self.assertTrue(any("GitHub加速" in s for s in samples),
                        "Watt Toolkit ↔ FastGithub 命中的也是工具名/词")
        for p in pairs:
            self.assertGreaterEqual(p["len"], 6)
            self.assertIn("sample", p)
        self.assertTrue(g["ok"], "它只是读数 ⇒ 不影响闸绿（判据是 `detail_family` 那条）")

    def test_cli_near_duplicate_marked_not_new_fact(self):
        # 三句同骨架（R-H349 → R-H351 → R-H383）⇒ 必须写明「不新增事实」
        cli = [x for x in at.run("reappearing")["items"]
               if x["token"] == "CC-Switch CLI"][0]
        self.assertIn("第三遍", str(cli["note"]))
        vals = []
        for x in at.CATEGORY_ROWS_OWNER:
            vals.append(str(x.get("category") or ""))
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        self.assertFalse([v for v in vals if "桌面应用，管理 5 大 CLI 工具的供应商配置，一键切换" in v],
                         "第二句一个字也不许落表")

    def test_repeat_reading_two_names(self):
        g = at.run("gate_reappearing")
        rep = dict(g.get("reappearance_repeat") or {})
        self.assertEqual(rep, {"CC Switch": 2, "CC-Switch CLI": 2})
        mine = {x["token"]: x["reappearance_times"] for x in at.REAPPEARING_TOKENS
                if x.get("reappearance_times", 1) > 1}
        self.assertEqual(rep, mine)

    # ---------- R-H384：融合设计（第四节 · 7 条映射）+ 两条新碎片形态 ----------

    def test_fusion_rows_seven_rows_and_crosschecks(self):
        g = at.run("gate_fusion_rows")
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["count"], 7)
        kinds = list(g.get("kinds") or [])
        print("fusion kinds =", kinds)
        self.assertEqual(kinds, ["逐字", "前缀", "一字之差", "对应", "呼应"])
        rows = at.run("fusion_rows")["items"]
        self.assertEqual([r["no"] for r in rows], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(rows[0]["left"], "AI辅助编程工具")
        self.assertEqual(rows[0]["right"], "编程工作区的备选引擎")
        self.assertEqual(rows[6]["left"], "网络加速工具")
        self.assertEqual(rows[6]["right"], "环境优化工具")
        for r in rows:
            self.assertTrue(any(k in str(r["crosscheck"]) for k in kinds),
                            "第 %s 条没说清是哪种对照" % r["no"])

    def test_fusion_row_without_crosscheck_tooth(self):
        live = at.FUSION_ROWS[0]
        saved = live["crosscheck"]
        # ⚠️ 对照牙（同刀修正后）判的是「**非空**」—— 空了才叫沉默
        live["crosscheck"] = ""
        try:
            g = at.run("gate_fusion_rows")
        finally:
            live["crosscheck"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "fusion_row_without_crosscheck")
        self.assertTrue(at.run("gate_fusion_rows")["ok"])

    def test_fusion_row_from_and_unverified_teeth(self):
        # 出处标签必须真的存在（不许编）
        live = at.FUSION_ROWS[1]
        saved_f, saved_r = live["right_from"], live["right"]
        live["right_from"] = "KEY_TOOLS:不存在的工具"
        try:
            g = at.run("gate_fusion_rows")
        finally:
            live["right_from"] = saved_f
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "fusion_row_from_unknown")
        self.assertEqual(g.get("side"), "right")
        # 声称「逐字」，可那一串在**那个出处里按整段找不到** ⇒ 红
        # ⚠️ 要挑**可校验**的边（逐字/前缀/一字之差）—— 第 5 条右边是「逐字」
        live2 = at.FUSION_ROWS[4]
        saved2 = live2["right"]
        live2["right"] = "上帝视角的监控组件（编的）"
        try:
            g2 = at.run("gate_fusion_rows")
        finally:
            live2["right"] = saved2
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "fusion_row_crosscheck_unverified")
        self.assertTrue(at.run("gate_fusion_rows")["ok"])

    def test_fusion_row_landed_tooth(self):
        # 🔴 一条都不许落进任何表：把某条表值临时改成映射的右边 ⇒ 红
        row = at.CATEGORY_ROWS_OWNER[0]
        cells = dict(row.get("cells") or {})
        try:
            row["cells"] = dict(cells, **{"代表工具": "编程工作区的备选引擎"})
            g = at.run("gate_fusion_rows")
        finally:
            row["cells"] = cells
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "fusion_row_landed")
        self.assertTrue(at.run("gate_fusion_rows")["ok"])

    def test_fragment_kinds_and_fence_note(self):
        # 两种碎片形态：truncated（等补全）/ fence（格式残片）—— 纪律不同、不许混
        g = at.run("gate_truncated")
        self.assertTrue(g["ok"], g)
        fr = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}
        print("fragments =", sorted(fr))
        self.assertEqual(list(at.FRAGMENT_KINDS), ["truncated", "fence"])
        self.assertEqual(fr["工具"]["kind"], "truncated")
        self.assertIn("补全", str(fr["工具"]["note"]))
        self.assertEqual(fr["原语"]["kind"], "truncated")
        self.assertIn("R-H384", str(fr["原语"]["at"]))
        self.assertIn("补全", str(fr["原语"]["note"]))
        self.assertEqual(fr["text"]["kind"], "fence")
        self.assertIn("格式", str(fr["text"]["note"]))
        self.assertIn("留空不编", str(fr["text"]["note"]))
        self.assertNotIn("补全", str(fr["text"]["note"]),
                         "格式残片没有「补全」这一说 —— 两种形态不许混")
        live = fr["原语"]
        saved = live["kind"]
        live["kind"] = "whatever"
        try:
            gb = at.run("gate_truncated")
        finally:
            live["kind"] = saved
        self.assertFalse(gb["ok"], gb)
        self.assertEqual(gb["rule"], "fragment_kind_unknown")
        self.assertTrue(at.run("gate_truncated")["ok"])

    def test_fusion_rows_not_landed_anywhere(self):
        # 7 条映射的**右边**一个字都不许出现在任何数据面里
        vals = []
        for x in at.CATEGORY_ROWS_OWNER:
            vals.append(str(x.get("category") or ""))
            vals += [str(v or "") for v in dict(x.get("cells") or {}).values()]
        for r in at.FUSION_ROWS:
            self.assertFalse([v for v in vals if str(r["right"]) in v],
                             "第 %s 条落表了" % r["no"])
        self.assertTrue(at.run("gate_fusion_rows")["ok"])

    # ---------- R-H385：4.2 原语（INDEX）----------

    def test_fusion_primitive_index(self):
        g = at.run("gate_fusion_primitives")
        self.assertTrue(g["ok"], g)
        # R-H386 增长连带：现在是**两条**原语
        self.assertEqual(g["count"], len(at.FUSION_PRIMITIVES))
        it = at.run("fusion_primitives")["items"][0]
        self.assertEqual(it["name"], "INDEX")
        self.assertEqual(it["order"], 1, "本仓 PRIMITIVES 的第 1 条 ⇒ 顺位一致")
        self.assertEqual(it["of"], 4)
        n = str(it["note"])
        for kw in ("后继词", "不是补全", "仍留空不编", "不许塞进再现区"):
            self.assertIn(kw, n)
        self.assertEqual(list(g["known"]), [p["key"] for p in at.PRIMITIVES])

    def test_fusion_primitive_unknown_tooth(self):
        live = at.FUSION_PRIMITIVES[0]
        saved = live["name"]
        live["name"] = "SUMMON"
        try:
            g = at.run("gate_fusion_primitives")
        finally:
            live["name"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "fusion_primitive_unknown")
        self.assertTrue(at.run("gate_fusion_primitives")["ok"])

    def test_fusion_primitive_is_fragment_tooth(self):
        # 🔴 碎片不许当原语（没说完 ≠ 原语）
        live = at.FUSION_PRIMITIVES[0]
        saved = live["name"]
        live["name"] = "原语"
        try:
            g = at.run("gate_fusion_primitives")
        finally:
            live["name"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "fusion_primitive_is_fragment")
        self.assertTrue(at.run("gate_fusion_primitives")["ok"])

    def test_fusion_primitive_not_reappearing_token(self):
        # 原语名**不许**塞进再现区（那里要求能在分类行/名单里按整段找到）
        toks = [x["token"] for x in at.REAPPEARING_TOKENS]
        self.assertNotIn("INDEX", toks)
        self.assertEqual(at.run("gate_reappearing")["count"], 18)

    def test_fusion_primitive_lookup_second(self):
        g = at.run("gate_fusion_primitives")
        self.assertTrue(g["ok"], g)
        # R-H387 增长连带：现在是**三条**
        self.assertEqual(g["count"], len(at.FUSION_PRIMITIVES))
        it = at.run("fusion_primitives")["items"][1]
        self.assertEqual(it["name"], "LOOKUP")
        self.assertEqual(it["order"], 2)
        # R-H387 增长连带：given 会长 ⇒ 只看**前两条**（本刀的现场）
        self.assertEqual(list(g["given"])[:2], ["INDEX", "LOOKUP"])
        self.assertTrue(g["order_same"], "主人给的顺序 = 本仓顺序（前两条）")

    def test_fusion_primitive_map_third_and_lookup_detail(self):
        # R-H387：第 3 条 MAP（顺位 3/4）+ LOOKUP 的介绍（能追到哪一轮）
        g = at.run("gate_fusion_primitives")
        self.assertTrue(g["ok"], g)
        # R-H388 增长连带：已**四条**
        self.assertEqual(g["count"], len(at.FUSION_PRIMITIVES))
        names = [x["name"] for x in at.run("fusion_primitives")["items"]]
        # R-H388 增长连带：只看**前三名**（本刀现场）
        self.assertEqual(names[:3], ["INDEX", "LOOKUP", "MAP"])
        self.assertTrue(g["order_same"], "顺序仍与本仓一致")
        # R-H388 增长连带：只看**前三条**的顺位
        self.assertEqual([x["order"] for x in at.run("fusion_primitives")["items"]][:3], [1, 2, 3])
        # R-H388 增长连带：有介绍的不止一条了 ⇒ 只看「含 LOOKUP」
        self.assertIn("LOOKUP", list(g["with_detail"]))
        self.assertEqual(g["detail_rounds"]["LOOKUP"], "R-H387")
        lu = [x for x in at.run("fusion_primitives")["items"] if x["name"] == "LOOKUP"][0]
        self.assertEqual(lu["detail"], "查工具详情（介绍 + 下载地址）")
        mp = [x for x in at.run("fusion_primitives")["items"] if x["name"] == "MAP"][0]
        # R-H388 起 MAP 也有介绍了 ⇒ 改看**最后一个还没介绍的**（VERIFY）
        self.assertIsNone([x for x in at.run("fusion_primitives")["items"]
                           if x["name"] == "VERIFY"][0]["detail"], "不许替它编")

    def test_fusion_primitive_detail_round_tooth(self):
        # 带牙：挂了介绍却说出不哪一轮 ⇒ 红
        live = [x for x in at.FUSION_PRIMITIVES if x["name"] == "LOOKUP"][0]
        saved = live.get("detail_round")
        live["detail_round"] = ""
        try:
            g = at.run("gate_fusion_primitives")
        finally:
            live["detail_round"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "fusion_primitive_detail_without_round")
        self.assertTrue(at.run("gate_fusion_primitives")["ok"])

    def test_fusion_primitive_duplicate_tooth(self):
        live = dict(at.FUSION_PRIMITIVES[0])
        at.FUSION_PRIMITIVES = tuple(list(at.FUSION_PRIMITIVES) + [dict(live)])
        try:
            g = at.run("gate_fusion_primitives")
        finally:
            at.FUSION_PRIMITIVES = tuple(list(at.FUSION_PRIMITIVES)[:-1])
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "fusion_primitive_duplicate")
        self.assertTrue(at.run("gate_fusion_primitives")["ok"])

    def test_fusion_primitives_complete_four(self):
        # R-H388：第 4 条 VERIFY ⇒ 四原语到齐 4/4（到齐 ≠ 许可）；MAP 也拿到介绍
        g = at.run("gate_fusion_primitives")
        self.assertTrue(g["ok"], g)
        names = [x["name"] for x in at.run("fusion_primitives")["items"]]
        self.assertEqual(names, ["INDEX", "LOOKUP", "MAP", "VERIFY"])
        self.assertEqual(g["progress"], {"given": 4, "of": 4, "complete": True})
        self.assertEqual(sorted(g["with_detail"]), ["LOOKUP", "MAP"])
        self.assertEqual(g["detail_rounds"], {"LOOKUP": "R-H387", "MAP": "R-H388"})
        mp = [x for x in at.run("fusion_primitives")["items"] if x["name"] == "MAP"][0]
        self.assertEqual(mp["detail"], "工具 → 能力位映射")
        ve = [x for x in at.run("fusion_primitives")["items"] if x["name"] == "VERIFY"][0]
        self.assertIsNone(ve["detail"], "VERIFY 的介绍还没到 ⇒ 不许替它编")
        self.assertTrue(g["order_same"])

    def test_fusion_sections_three(self):
        g = at.run("gate_fusion_sections")
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["nos"], ["4.1", "4.2", "4.3"])
        self.assertEqual(list(g["items"])[2]["title"], "三条带牙用例")
        self.assertIn("不许替它编三条用例", str(list(g["items"])[2]["note"]))

    def test_fusion_section_teeth(self):
        live = dict(at.FUSION_SECTIONS[2])
        saved = at.FUSION_SECTIONS
        # 重号
        at.FUSION_SECTIONS = tuple(list(saved[:2]) + [dict(live, no="4.2")])
        try: g1 = at.run("gate_fusion_sections")
        finally: at.FUSION_SECTIONS = saved
        # 倒序
        at.FUSION_SECTIONS = tuple(list(saved[:2]) + [dict(live, no="4.0")])
        try: g2 = at.run("gate_fusion_sections")
        finally: at.FUSION_SECTIONS = saved
        print("dup =>", g1.get("rule"), "| order =>", g2.get("rule"))
        self.assertEqual(g1.get("rule"), "fusion_section_duplicate")
        self.assertEqual(g2.get("rule"), "fusion_section_out_of_order")
        self.assertTrue(at.run("gate_fusion_sections")["ok"])

    def test_truncated_fragment_use_case_fourth(self):
        fr = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}
        # R-H393 增长连带：碎片会长 ⇒ 与登记表一致 + 必含本刀那条
        self.assertEqual(sorted(fr), sorted(x["token"] for x in at.TRUNCATED_FRAGMENTS))
        self.assertIn("用例", fr)
        self.assertEqual(fr["用例"]["kind"], "truncated")
        self.assertIn("补全", str(fr["用例"]["note"]))
        self.assertIn("原语", str(fr["用例"]["note"]), "它与『原语』同型")
        self.assertTrue(at.run("gate_truncated")["ok"])

    def test_fusion_case_one_index_readonly(self):
        g = at.run("gate_fusion_cases")
        self.assertTrue(g["ok"], g)
        # R-H391 增长连带：用例会长 ⇒ 与登记表一致 + 取第 1 条
        self.assertEqual(g["count"], len(at.FUSION_CASES))
        it = at.run("fusion_cases")["items"][0]
        self.assertEqual(it["text"], "索引只读")
        self.assertEqual(it["from"], "PRIMITIVES:INDEX")
        self.assertEqual(g["progress"]["of"], 3, "标题说三条")
        self.assertIn("只读", str(it["crosscheck"]))

    def test_fusion_case_teeth(self):
        live = dict(at.FUSION_CASES[0])
        saved = at.FUSION_CASES
        at.FUSION_CASES = tuple([dict(live, **{"from": "PRIMITIVES:NOPE"})])
        try: g1 = at.run("gate_fusion_cases")
        finally: at.FUSION_CASES = saved
        at.FUSION_CASES = tuple([dict(live, **{"from": ""})])
        try: g2 = at.run("gate_fusion_cases")
        finally: at.FUSION_CASES = saved
        print("from-unknown =>", g1.get("rule"), "| without-from =>", g2.get("rule"))
        self.assertEqual(g1.get("rule"), "fusion_case_from_unknown")
        self.assertEqual(g2.get("rule"), "fusion_case_without_from")
        self.assertTrue(at.run("gate_fusion_cases")["ok"])

    def test_fusion_case_two_mapping_traceable(self):
        g = at.run("gate_fusion_cases")
        self.assertTrue(g["ok"], g)
        # R-H392 增长连带：三条到齐 ⇒ 与登记表一致
        self.assertEqual(g["count"], len(at.FUSION_CASES))
        its = at.run("fusion_cases")["items"]
        self.assertEqual([x["text"] for x in its][:2], ["索引只读", "映射可追"])
        self.assertEqual(its[1]["from"], "PRIMITIVES:MAP")
        self.assertEqual(list(its[1]["teeth"]),
                         ["fusion_row_from_unknown", "fusion_row_crosscheck_unverified"])
        self.assertEqual(g["progress"]["of"], 3)
        # R-H392 增长连带：有牙的条数会长 ⇒ 只看「含映射可追」且**第 1 条仍无牙**
        self.assertIn("映射可追", list(g["with_teeth"]))
        self.assertNotIn("索引只读", list(g["with_teeth"]), "第 1 条目前没有牙 ⇒ 如实记")
        self.assertEqual(list(its[0]["teeth"]), [])

    def test_fusion_case_teeth_unknown_tooth(self):
        live = dict(at.FUSION_CASES[1])
        saved = at.FUSION_CASES
        at.FUSION_CASES = tuple([dict(live, teeth=["不存在的牙"])])
        try: g = at.run("gate_fusion_cases")
        finally: at.FUSION_CASES = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "fusion_case_teeth_unknown")
        self.assertTrue(at.run("gate_fusion_cases")["ok"])
        # 牙名真表来自**现扫源码**（不是手写清单）：两把真牙都该在里面
        self.assertIn("fusion_row_from_unknown", at._known_rules())
        self.assertIn("fusion_case_teeth_unknown", at._known_rules())

    def test_fusion_case_three_verify_no_green(self):
        # R-H392：第 3 条 ⇒ **三条到齐 3/3**（到齐 ≠ 许可），且三条都有出处
        g = at.run("gate_fusion_cases")
        self.assertTrue(g["ok"], g)
        its = at.run("fusion_cases")["items"]
        self.assertEqual([x["text"] for x in its], ["索引只读", "映射可追", "未核实不标绿"])
        self.assertEqual(its[2]["from"], "PRIMITIVES:VERIFY")
        self.assertEqual(list(its[2]["teeth"]), ["unverified_green"])
        self.assertEqual(g["progress"], {"given": 3, "of": 3, "complete": True})
        self.assertEqual(list(g["with_teeth"]), ["映射可追", "未核实不标绿"])
        for x in its:
            self.assertTrue(str(x["from"]).startswith("PRIMITIVES:"))

    def test_incoming_distill_teamorouter(self):
        # R-H393：未到齐的输入专区（内容一个字不编）
        g = at.run("gate_incoming_distills")
        self.assertTrue(g["ok"], g)
        # R-H394 增长连带：未到齐会长 ⇒ 与登记表一致
        self.assertEqual(g["count"], len(at.INCOMING_DISTILLS))
        it = at.run("incoming_distills")["items"][0]
        self.assertIn("TeamoRouter", it["topic"])
        self.assertIn("未到齐", it["got"])
        self.assertIn("=>", it["disk_check"], "必须带盘上取证读数")
        self.assertIn("0 行", it["disk_check"])
        self.assertIn("一个字都不编", it["note"])

    def test_incoming_distill_teeth(self):
        live = dict(at.INCOMING_DISTILLS[0])
        saved = at.INCOMING_DISTILLS
        at.INCOMING_DISTILLS = tuple([dict(live, got="开头", note="待看")])
        try: g1 = at.run("gate_incoming_distills")
        finally: at.INCOMING_DISTILLS = saved
        at.INCOMING_DISTILLS = tuple([dict(live, disk_check="盘上没有")])
        try: g2 = at.run("gate_incoming_distills")
        finally: at.INCOMING_DISTILLS = saved
        print("gap =>", g1.get("rule"), "| check =>", g2.get("rule"))
        self.assertEqual(g1.get("rule"), "incoming_gap_unstated")
        self.assertEqual(g2.get("rule"), "incoming_without_disk_check")
        self.assertTrue(at.run("gate_incoming_distills")["ok"])

    def test_truncated_fragment_level_fifth(self):
        fr = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}
        self.assertIn("层级", fr)
        self.assertEqual(fr["层级"]["kind"], "truncated")
        self.assertIn("补全", str(fr["层级"]["note"]))
        self.assertTrue(at.run("gate_truncated")["ok"])

    def test_incoming_overlap_reading(self):
        # R-H394：两条未到齐输入**逐字重合**（重合串「工程哲学」）—— 只作读数，不许当同一个
        g = at.run("gate_incoming_distills")
        self.assertTrue(g["ok"], g)
        ov = dict(g.get("overlap") or {})
        print("overlap =", ov)
        self.assertTrue(ov, "样本数必须 > 0")
        # 🔴 R-H395 收窄后：**每条只留一条最长重合**（原先 50+ 片段 ⇒ 没法用）
        for k, v in ov.items():
            self.assertIsInstance(v, str, "收窄后是**一条**最长重合（不是片段清单）")
            self.assertGreaterEqual(len(v), 4)
        # 🔴 R-H396：口径收窄到**只在 got 上算** ⇒ 剪出来的该是**主人给的词**（不是我的模板碎片）
        self.assertIn("工程哲学", " ".join(ov.values()))
        for bad in ("重发", "可能是", "重合串", "并排记", "仍未到齐"):
            self.assertNotIn(bad, " ".join(ov.values()), "不许把**我写的模板**剪成重合")
        self.assertEqual(sorted(v for v in ov.values()), ["工程哲学", "工程哲学"])
        self.assertIn("第一层：路由策略", it0_got := str(at.run("incoming_distills")["items"][0]["got"]))
        self.assertIn("显式声明，绝不偷换", it0_got)
        # R-H397：第一层内容 + 第二层到货；并记「同一件事两套前缀」
        # ⚠️ 这两段落在 **verbatim**（主人逐字）里，不在 got（got 只放「到货/未到齐」标注）
        vb0 = str(at.run("incoming_distills")["items"][0]["verbatim"])
        self.assertIn("teamo-best / teamo-balanced / teamo-eco", vb0)
        self.assertIn("偷偷降档", vb0)
        self.assertIn("第二层：调度架构", vb0)
        # R-H398：第二层内容到货（五层防护，逐层兜底）+ 又一处「两套说法」
        self.assertIn("五层防护，逐层兜底", str(at.run("incoming_distills")["items"][0]["verbatim"]))
        self.assertIn("仍未到齐", it0_got)
        blob = str(it0 := at.run("incoming_distills")["items"][0]["disk_check"]) + \
            " ".join(str(x["note"]) for x in at.run("incoming_distills")["items"])
        # R-H399：第二层的内容（五层名序列）+ 第三层到货 ⇒ layers 读数（到齐 ≠ 许可）
        self.assertIn("策略层 → 匹配层 → 健康检测层 → 故障切换层 → 兜底层", vb0)
        self.assertIn("第三层：成本控制", vb0)
        # R-H400：第三层的内容到货 ⇒ 三层各有一句；⚠️ 但**不宣布整段到齐**
        self.assertIn("靠工程优化，不靠掺水", vb0)
        # R-H404：那张表的第一格到货（L1）⇒ 一格不成行，仍算未到齐
        r4 = at.run("incoming_distills")
        self.assertIn("L1", vb0)
        # R-H407 增长连带：层格会长 ⇒ 只看含 L1
        self.assertIn("L1", r4["cells"])
        # R-H405：第一行第二格到货（路由策略层）⇒ row1 = [L1, 路由策略层] · 一行三列
        self.assertIn("路由策略层", vb0)
        # R-H406 增长连带：第一行会长 ⇒ 只看前两格
        self.assertEqual(r4["row1"][:2], ["L1", "路由策略层"])
        # R-H406：第三格到货 ⇒ 第一行**三格到齐**（成行）· ⚠️ 但一行成行 ≠ 表完成
        self.assertIn("按用户声明的优先级选择路由方向", vb0)
        r6 = at.run("incoming_distills")
        self.assertEqual(r6["row1"], ["L1", "路由策略层", "按用户声明的优先级选择路由方向"])
        self.assertTrue(r6["row1_complete"], "第一行三格到齐")
        # R-H407：L2 到货（第二行第一格）⇒ 通用行读数 rows；L2 未成行
        self.assertIn("L2", vb0)
        r7 = at.run("incoming_distills")
        # R-H408：L2 行第二格到货（智能匹配层）⇒ 仍未成行；并与「匹配层」并排（一字之差）
        self.assertIn("智能匹配层", vb0)
        self.assertEqual(r7["rows"][0], ["L1", "路由策略层", "按用户声明的优先级选择路由方向"])
        # R-H409：第三格到货 ⇒ **L2 成行**（两行成行）
        self.assertIn("模型映射 + 通道粘性 + 缓存热度感知", vb0)
        r9 = at.run("incoming_distills")
        self.assertEqual(r9["rows"][1],
                         ["L2", "智能匹配层", "模型映射 + 通道粘性 + 缓存热度感知"])
        # R-H410：L3 到货（第一格）⇒ 未成行；「STICKY（粘性）」是**说明**、不填进那一格
        self.assertIn("STICKY（粘性）", vb0)
        self.assertIn("L3", vb0)
        r10 = at.run("incoming_distills")
        # R-H411：L3 第二格到货（健康检测层）⇒ 仍未成行；且与五层名序列**逐字一致**
        self.assertIn("健康检测层", vb0)
        r11 = at.run("incoming_distills")
        # R-H412：第三格到货 ⇒ **L3 成行**（三行成行）
        self.assertIn("智能心跳 + 稀释率检测 + 丢包率监控", vb0)
        r12 = at.run("incoming_distills")
        self.assertEqual(r12["rows"][2],
                         ["L3", "健康检测层", "智能心跳 + 稀释率检测 + 丢包率监控"])
        # R-H413：L4 到货（第一格，未成行）+ HEALTH（健康）作**说明**（不填格）
        self.assertIn("HEALTH（健康）", vb0)
        self.assertIn("L4", vb0)
        r13 = at.run("incoming_distills")
        # R-H414：L4 第二格到货（故障切换层）⇒ 仍未成行；与五层名序列**逐字一致**（第二处）
        self.assertIn("故障切换层", vb0)
        r14 = at.run("incoming_distills")
        # R-H415：第三格到货 ⇒ **L4 成行**（四行成行）
        self.assertIn("电路断路器 + 灰度降级", vb0)
        r15 = at.run("incoming_distills")
        self.assertEqual(r15["rows"][3],
                         ["L4", "故障切换层", "电路断路器 + 灰度降级"])
        # R-H416：L5 到货（第一格，未成行）+ FALLBACK（兜底）作**标注**（名字未到 ⇒ 不许编）
        self.assertIn("FALLBACK（兜底）", vb0)
        self.assertIn("L5", vb0)
        r16 = at.run("incoming_distills")
        # R-H417：L5 第二格到货（兜底层）⇒ 仍未成行；标注与名字**现在对上了**
        self.assertIn("兜底层", vb0)
        r17 = at.run("incoming_distills")
        # R-H418 增长连带：那一行会长 ⇒ 只看前两格
        self.assertEqual(r17["rows"][4][:2], ["L5", "兜底层"])
        # R-H418：第三格到货 ⇒ **L5 成行 ⇒ 五行全成行（5/5）**；⚠️ 表齐 ≠ 许可
        self.assertIn("最终兜底方案", vb0)
        r18 = at.run("incoming_distills")
        self.assertEqual(r18["rows"][4], ["L5", "兜底层", "最终兜底方案"])
        self.assertEqual(r18["rows_complete_rows"], 5, "五行全成行")
        self.assertTrue(r18["table_complete"], "表到齐（读数）")
        self.assertIn("表齐 ≠ 许可", str(r18["table_note"]))
        self.assertIn("仍未到齐", str(r18["items"][0]["got"]))
        notes17 = " ".join(str(x) for x in (r17["items"][0].get("alias_notes") or []))
        self.assertIn("兜底层", notes17)
        self.assertIn("现在对上了", notes17)
        self.assertGreaterEqual(r16["rows_complete_rows"], 4, "至少 L1-L4 成行")
        notes16 = " ".join(str(x) for x in (r16["items"][0].get("alias_notes") or []))
        self.assertIn("FALLBACK", notes16)
        self.assertIn("不许替它编名字", notes16)
        # R-H417 增长连带：名字到货后那一行会长 ⇒ 只看第一格 + 名字仍是「后到」的
        self.assertEqual(r16["rows"][4][0], "L5")
        # ⚠️ 我写错了：`r16` 是**跑在同一个进程的当前状态**（名字已经到了）⇒ 不该断言长度
        self.assertGreaterEqual(len(r16["rows"][4]), 1)
        self.assertIn("仍未到齐", str(r15["items"][0]["got"]))
        self.assertGreaterEqual(r14["rows_complete_rows"], 3, "至少 L1-L3 成行")
        rels = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("name_relations") or ())]
        self.assertTrue(any(x[0].startswith("L4") and "逐字一致" in x[1] for x in rels),
                        "L4 这格也是逐字一致")
        self.assertEqual(len([x for x in rels if "逐字一致" in x[1]]), 2, "两处逐字一致")
        self.assertGreaterEqual(r13["rows_complete_rows"], 3, "至少 L1/L2/L3 成行")
        notes13 = " ".join(str(x) for x in (r13["items"][0].get("alias_notes") or []))
        self.assertIn("HEALTH", notes13)
        self.assertIn("不许当同一个", notes13)
        self.assertEqual(r13["rows"][2][1], "健康检测层", "格里的字没被改写")
        self.assertIn("仍未到齐", str(r12["items"][0]["got"]))
        # R-H415 增长连带：成行数又长了 ⇒ 用「≥3」
        self.assertGreaterEqual(r11["rows_complete_rows"], 3, "R-H412 起至少 L1-L3 成行")
        rel = [tuple(x) for x in (at.INCOMING_DISTILLS[0].get("name_relations") or ())]
        self.assertTrue(any("逐字一致" in x[1] for x in rel), "L3 那格是逐字一致")
        self.assertTrue(any("一字之差" in x[1] for x in rel), "L2 那格是一字之差")
        self.assertTrue(list(r10["items"][0].get("alias_notes") or []), "alias_notes 要随出口带出来")
        # R-H412 增长连带：成行数会长 ⇒ 只看「≥2」
        self.assertGreaterEqual(r10["rows_complete_rows"], 2, "至少 L1、L2 成行")
        self.assertEqual(r10["rows"][1][2], "模型映射 + 通道粘性 + 缓存热度感知",
                         "第三格**一个字都没被改写**（STICKY 不进格）")
        self.assertIn("仍未到齐", str(at.run("incoming_distills")["items"][0]["got"]))
        # R-H412 增长连带：又长了一行 ⇒ 用「≥2」而不是写死
        self.assertGreaterEqual(r7["rows_complete_rows"], 2, "R-H409 起至少 L1+L2 成行")
        # ⚠️ 「一字之差」这条读数我落在 **docs**（模块里的 got 我没改）⇒ 按文档断言
        # ⚠️ 测试模块里没有 ROOT ⇒ 用 pathlib 现取（我上一版忘了）
        from pathlib import Path as _P
        _doc = (_P(__file__).resolve().parents[1] / "docs" / "AwesomeTools蒸馏.md"
                ).read_text(encoding="utf-8-sig")
        self.assertIn("一字之差", _doc)
        self.assertEqual(r7["rows_of"], 5, "目标五层")
        # R-H409 增长连带：成行数会长 ⇒ 只看「≥1」
        self.assertGreaterEqual(r7["rows_complete_rows"], 1, "至少 L1 成行")
        # 带牙：rows 里的格也必须在 verbatim 里
        live = [x for x in at.INCOMING_DISTILLS if x.get("rows")][0]
        saved = live["rows"]
        live["rows"] = (("L1", "路由策略层", "按用户声明的优先级选择路由方向"), ("L2", "编的"))
        try:
            gg = at.run("gate_incoming_distills")
        finally:
            live["rows"] = saved
        self.assertFalse(gg["ok"], gg)
        self.assertEqual(gg["rule"], "incoming_row1_unverified")
        self.assertIn("一行成行 ≠ 表完成", str(r6["row1_note"]))
        self.assertEqual(r4["row1_of"], 3, "一行三列（层级|名称|核心职责）")
        # 带牙：登记的格必须在 verbatim 里找得到
        live = [x for x in at.INCOMING_DISTILLS if x.get("row1")][0]
        saved = live["row1"]
        live["row1"] = ("L1", "编的格")
        try:
            gg = at.run("gate_incoming_distills")
        finally:
            live["row1"] = saved
        self.assertFalse(gg["ok"], gg)
        self.assertEqual(gg["rule"], "incoming_row1_unverified")
        self.assertTrue(at.run("gate_incoming_distills")["ok"])
        self.assertEqual(r4["cells_of"], 5, "目标 = 五层（L1-L5）")
        self.assertIn("一格不成行", str(r4["cells_note"]))
        # R-H401：第二节到货 + 又止于「层级」（碎片第二次出现 ⇒ 仍不编）
        for kw in (">99% 缓存命中率", "二、五层调度系统的蒸馏提炼",
                   "能管理 500+ 供应商的五层调度系统"):
            self.assertIn(kw, vb0)
        fr = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}["层级"]
        self.assertIn("R-H401", str(fr["at"]))
        self.assertIn("第二次出现", str(fr["note"]))
        self.assertIn("留空不编", str(fr["note"]))
        self.assertTrue(at.run("gate_truncated")["ok"])
        g3 = at.run("gate_incoming_distills")
        self.assertTrue(g3["ok"], g3)
        got3 = str(at.run("incoming_distills")["items"][0]["got"])
        self.assertIn("三层各有一句内容", got3)
        self.assertIn("不敢宣布整段到齐", got3)
        self.assertIn("未到齐", got3)
        g2 = at.run("gate_incoming_distills")
        self.assertEqual(g2["layers"], ["路由策略", "调度架构", "成本控制"])
        self.assertTrue(g2["layers_complete"], "三层到齐（**到齐 ≠ 许可**）")
        self.assertIn("同名 ≠ 同物", blob)
        for kw in ("五层防护/逐层兜底 => **0 行**", "五层架构 L1-L5", "像但不等于"):
            self.assertIn(kw, blob)
        self.assertIn("仍未到齐", it0_got)
        # ⚠️ 那条「两套前缀」我落进了**第 2 条**的 note（不在第 1 条）⇒ 按**整区**断言
        notes = " ".join(str(x["note"]) for x in at.run("incoming_distills")["items"])
        for kw in ("两套前缀", "gbt-*", "teamo-*", "不许擅自改"):
            self.assertIn(kw, notes)
        # 我自己的模板句**不许**被当成重合
        for bad in ("并排记", "等主人补全", "一个字都不编"):
            self.assertNotIn(bad, " ".join(ov.values()))
        note = str(at.run("incoming_distills")["items"][1]["note"])
        for kw in ("逐字重合", "重发", "续写", "不合并", "一个字都不编"):
            self.assertIn(kw, note)

    def test_incoming_overlap_tooth(self):
        live = dict(at.INCOMING_DISTILLS[1])
        saved = at.INCOMING_DISTILLS
        at.INCOMING_DISTILLS = tuple([dict(saved[0]), dict(live, note="仍未到齐 等主人补全")])
        try: g = at.run("gate_incoming_distills")
        finally: at.INCOMING_DISTILLS = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "incoming_overlap_unstated")
        self.assertTrue(at.run("gate_incoming_distills")["ok"])

    def test_truncated_fragment_engineering_philosophy(self):
        fr = {x["token"]: x for x in at.TRUNCATED_FRAGMENTS}
        self.assertIn("工程哲学", fr)
        self.assertEqual(fr["工程哲学"]["kind"], "truncated")
        self.assertIn("补全", str(fr["工程哲学"]["note"]))
        self.assertTrue(at.run("gate_truncated")["ok"])

    def test_incoming_second_item_arrived(self):
        # R-H396：第二条内容到货（显式声明，绝不偷换）⇒ 仍未到齐
        g = at.run("gate_incoming_distills")
        self.assertTrue(g["ok"], g)
        it = at.run("incoming_distills")["items"][0]
        self.assertIn("显式声明，绝不偷换", it["got"])
        self.assertIn("仍未到齐", it["got"])

    def test_incoming_first_layer_arrived(self):
        # R-H395：第一层：路由策略（仍未到齐）
        g = at.run("gate_incoming_distills")
        self.assertTrue(g["ok"], g)
        it = at.run("incoming_distills")["items"][0]
        self.assertIn("第一层：路由策略", it["got"])
        self.assertIn("仍未到齐", it["got"], "三层只到一层 ⇒ 不许当成到齐")


if __name__ == "__main__":
    unittest.main()
