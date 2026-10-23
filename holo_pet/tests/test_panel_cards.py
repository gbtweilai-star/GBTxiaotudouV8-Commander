# -*- coding: utf-8 -*-
"""接面板带牙用例（R-H159 立 · R-H169 补"不许静默失败"）：卡片渲染不报错 / 空数据不崩 / 只读不写。

说明：app.js 是前端脚本，本仓无 JS 运行环境 ⇒ 用例做**静态契约 + 语法**两层：
  ① `node --check` 过语法（语法过了才算过第一关）；
  ② 源码级断言：只读、空数据有守卫、不直连 store、无写路径。
  ③ R-H169 起：**失败不许静默**（页面上必须有红字）、**成功必须有可见信标**。
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "holo_pet" / "app.js"
PAGE = ROOT / "holo_pet" / "index.html"


class PanelCardsTests(unittest.TestCase):
    def setUp(self):
        self.src = APP.read_text(encoding="utf-8")
        m = re.search(r"function renderReadonlyCards\(.*?\n\}\n", self.src, re.S)
        self.block = m.group(0) if m else ""

    def test_card_hooks_exist_and_page_serves_them(self):
        self.assertIn("function renderReadonlyCards(", self.src, "卡片渲染函数不在")
        self.assertIn("renderReadonlyCards(catalog, strip);", self.src, "卡片没有被调用")
        self.assertIn('"空间投射 · 只读卡片（5/5 未核实）"', self.block)
        self.assertIn("ARM ≠ LIVE", self.block, "红线必须写进卡片")
        self.assertIn("未核实", self.block)
        self.assertIn('id="quick-strip"'.replace('id=', 'class='), PAGE.read_text(encoding="utf-8"))

    def test_catalog_is_passed_into_observer_rendering(self):
        """能力目录必须显式传入后续渲染链，不能依赖不存在的全局 catalog。"""
        self.assertIn("async function setupObserverAndTree(catalog)", self.src)
        self.assertIn("return catalog;", self.src)
        self.assertIn("const catalog = await setupCapabilityCatalog();", self.src)
        self.assertIn("await setupObserverAndTree(catalog);", self.src)
        self.assertNotIn("setupObserverAndTree();", self.src)

    def test_free_local_avatar_is_default_and_xingyun_is_optional(self):
        page = PAGE.read_text(encoding="utf-8")
        styles = (ROOT / "holo_pet" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('id="local-avatar"', page)
        self.assertIn('id="btn-avatar-local"', page)
        self.assertIn('id="btn-avatar-xingyun"', page)
        self.assertIn('data-state="idle"', page)
        self.assertIn("function setLocalAvatarState(", self.src)
        self.assertIn("function startLocalAvatar()", self.src)
        self.assertIn("startLocalAvatar();", self.src)
        self.assertIn('localAvatar.source = "xingyun"', self.src)
        self.assertIn('[data-state="speaking"]', styles)
        self.assertIn("local-blink", styles)
        self.assertIn("local-head-sway", styles)

    def test_empty_data_does_not_crash(self):
        """空数据不崩：进函数先守卫，再对 items 做 Array.isArray 兜底。"""
        self.assertIn("if (!host || !catalog) return;", self.block)
        self.assertIn("Array.isArray(catalog.items)", self.block)
        self.assertIn(".filter(Boolean)", self.block)

    def test_readonly_no_store_no_write_path(self):
        """只读：不直连 store、无写路径（POST / postJson）。"""
        for bad in ("store/", "workflows.json", "wf_runs", "postJson(", "method: \"POST\""):
            self.assertNotIn(bad, self.block, f"只读卡片里不该出现：{bad}")
        self.assertIn("/api/capabilities", self.block)

    def test_app_js_passes_syntax_check(self):
        r = subprocess.run(["node", "--check", str(APP)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"app.js 语法不过：{r.stderr[:300]}")

    def test_card_failure_is_isolated(self):
        """失败隔离（钩子矩阵红线 2）：卡片渲染必须包在 try/catch 里，不许连累能力总目录。"""
        self.assertIn("try {\n    renderReadonlyCards(catalog, strip);", self.src)
        self.assertIn("catch (err)", self.src)
        self.assertIn("能力总目录不受影响", self.src)

    def test_failure_is_visible_not_silent(self):
        """R-H169：失败不许静默 —— catch 里必须**往页面上写红字**，不能只 console.warn。

        由来（一手）：R-H159 那版只 `console.warn` ⇒ "卡片没渲染"和"渲染了"在主人眼里
        长得一模一样，谁也说不清是哪一种（今天被主人当场问到，才把它当成病来治）。
        """
        self.assertIn('cardErrorBox(strip, err, "renderReadonlyCards");', self.src,
                      "catch 里没有调用可见失败提示 —— 又变回静默失败")
        m = re.search(r"function cardErrorBox\(.*?\n\}\n", self.src, re.S)
        self.assertTrue(m, "可见失败提示函数 cardErrorBox 不在")
        blk = m.group(0)
        self.assertIn("insertBefore", blk, "失败提示必须真的插进页面 DOM（不然还是看不见）")
        self.assertIn("画不出来", blk, "必须说清：不是没有卡片，是画不出来")

    def test_success_has_visible_beacon(self):
        """R-H169：成功也要留可见痕迹 —— **看得到信标 = 新代码在跑**。"""
        self.assertIn("readonly-cards-badge", self.block, "成功信标不在卡片段里")
        self.assertIn("R-H187", self.block, "信标上必须写清版本（否则新旧无法分辨）")
        self.assertIn("/api/purge", self.block, "信标要列全数据源（R-H171 起有多处）")
        self.assertIn("/api/music", self.block, "信标要列全数据源（R-H173 起含 /api/music）")

    def test_music_card_is_readonly_and_says_unverified(self):
        """卡④（R-H173）：音乐平台 —— 只从 /api/music 取数，且**必须把"未核实"印在卡上**。"""
        m = re.search(r"async function renderMusicCard\(.*?\n\}\n", self.src, re.S)
        self.assertTrue(m, "卡④ renderMusicCard 不在")
        blk = m.group(0)
        self.assertIn('fetchJsonOrExplain("/api/music"', blk)
        for bad in ("postJson(", 'method: "POST"', "store/"):
            self.assertNotIn(bad, blk, f"音乐卡片里不该出现：{bad}")
        self.assertIn("未核实", blk, "不许把『在』写成『能用』")
        self.assertIn("不加任何执行能力", blk)
        self.assertIn("if (!res.ok", blk, "取不到数据要先守卫")

    def test_workspace_exists_and_can_execute(self):
        """卡⑤（R-H186）：工作区 —— **全 App 唯一能干活的那一块**。

        出口复用现成的 POST /api/capability（→ run_task，过 auth_gate）；
        侧效应能力沿用 needs_confirmation 的"再点一次确认"。
        """
        self.assertIn("renderWorkspace(catalog, strip);", self.src, "工作区没被调用")
        m = re.search(r"function renderWorkspace\(.*?\n\}\n", self.src, re.S)
        self.assertTrue(m, "卡⑤ renderWorkspace 不在")
        blk = m.group(0)
        for piece in ("ws-kind", "ws-payload", "ws-run", "ws-out"):
            self.assertIn(piece, blk, "工作区缺件：%s" % piece)
        self.assertIn('postJson("/api/capability"', blk, "执行必须走既有出口")
        self.assertIn("payload", blk, "必须能把参数传进去（这是它和芯片的区别）")
        self.assertIn("needs_confirmation", blk, "侧效应能力要二次确认")
        self.assertIn("再点一次确认执行", blk)
        self.assertIn("不可逆动作照卡", blk, "红线要印在卡上")
        self.assertIn("只有这块能干活", blk, "与只读卡的分界要写明")
        self.assertIn("JSON.parse", blk, "参数要能解析并给出失败提示")

    def test_only_the_workspace_may_execute(self):
        """分界：只读卡**不许**有执行路径；工作区**必须**有。"""
        rd = re.search(r"function renderReadonlyCards\(.*?\n\}\n", self.src, re.S).group(0)
        for bad in ("postJson(", 'method: "POST"'):
            self.assertNotIn(bad, rd, "只读卡里不许出现执行路径：%s" % bad)
        ws = re.search(r"function renderWorkspace\(.*?\n\}\n", self.src, re.S).group(0)
        self.assertIn("postJson(", ws, "工作区必须真的能执行")

    def test_overview_is_readonly_and_only_uses_get(self):
        """上帝视角（R-H187）：**只呈现，不执行** —— 整块不许有 POST。"""
        self.assertIn("renderOverview(catalog)", self.src, "上帝视角没被调用")
        m = re.search(r"async function renderOverview\(.*?\n\}\n", self.src, re.S)
        self.assertTrue(m, "renderOverview 不在")
        blk = m.group(0)
        for bad in ("postJson(", 'method: "POST"'):
            self.assertNotIn(bad, blk, "总览块不许有执行路径：%s" % bad)
        for src_api in ("/api/state", "/api/purge", "/api/capabilities"):
            self.assertIn(src_api, blk if src_api != "/api/capabilities" else blk + self.src,
                          "总览读数要来自 %s" % src_api)
        self.assertIn("只呈现，不执行", blk)
        self.assertIn("未接入", blk, "取不到的读数要如实标『未接入』，不许假装有")

    def test_layout_hosts_exist_and_cards_leave_the_composer(self):
        """布局（R-H187）：卡片挂进设计好的 host；输入框里不许再长卡。"""
        page = PAGE.read_text(encoding="utf-8")
        for host_id in ("overview-host", "readonly-host", "workbench-host"):
            self.assertIn('id="%s"' % host_id, page, "index.html 缺 host：%s" % host_id)
        self.assertIn('getElementById("readonly-host")', self.src)
        self.assertIn('getElementById("workbench-host")', self.src)
        # host 必须在 form.composer 之外（不是它的子节点）
        composer_at = page.find('id="composer"')
        for host_id in ("overview-host", "readonly-host", "workbench-host"):
            at = page.find('id="%s"' % host_id)
            self.assertGreater(at, 0)
            self.assertLess(at, composer_at, "%s 应排在输入框之前（不在输入框里）" % host_id)

    def test_two_blocks_do_not_interfere(self):
        """两条带牙边界：总览只读 · 工作区可执行 —— 互不干扰（各自的 host 各归各）。"""
        ov = re.search(r"async function renderOverview\(.*?\n\}\n", self.src, re.S).group(0)
        ws = re.search(r"function renderWorkspace\(.*?\n\}\n", self.src, re.S).group(0)
        self.assertIn('getElementById("overview-host")', ov, "总览要挂自己的 host")
        self.assertIn('getElementById("workbench-host")', ws, "工作区要挂自己的 host")
        self.assertNotIn('getElementById("workbench-host")', ov, "总览不许碰工作区的 host")
        self.assertNotIn('getElementById("overview-host")', ws, "工作区不许碰总览的 host")

    def test_purge_card_is_readonly_and_prints_the_scope(self):
        """卡③（R-H171）：净化读数 —— 只从 /api/purge 取数，**口径必须印在卡上**。

        由来：`anomalies 20 / runtime_faults 0` 两个数长得很像，谁拿错尺子都会得出
        "净化没做成"的结论 ⇒ 口径必须和读数一起出现在**卡片上**，不能只躺在文档里。
        """
        m = re.search(r"async function renderPurgeCard\(.*?\n\}\n", self.src, re.S)
        self.assertTrue(m, "卡③ renderPurgeCard 不在")
        blk = m.group(0)
        self.assertIn('fetchJsonOrExplain("/api/purge"', blk,
                      "数据源必须是只读出口 /api/purge（不许直连 store）")
        for bad in ("postJson(", 'method: "POST"', "store/"):
            self.assertNotIn(bad, blk, f"净化读数卡片里不该出现：{bad}")
        self.assertIn("不是净化成绩", blk, "口径必须印在卡上（别让人拿错尺子）")
        self.assertIn("runtime_faults", blk)
        self.assertIn("if (!host", blk, "空容器要先守卫")
        self.assertIn("if (!res.ok", blk, "取不到数据要先守卫，不许崩")
        self.assertIn("重启面板", blk, "旧面板进程取不到时要说清怎么办")


if __name__ == "__main__":
    unittest.main()
