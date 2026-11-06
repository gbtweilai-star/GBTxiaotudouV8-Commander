# -*- coding: utf-8 -*-
"""APP 对话面板「AI 打印」判据（2026-11-06 主人令）。

主人原话：「APP 对话面板 AI 打印做跟 Codex 对话面板同款 AI 打印显示」
「还有对话面板的 AI 对话显示，设置这样的同款」
「精细一点必须她扫描过哪里，在执行哪里，调用什么工具每一步细节都要能看得到」。

Codex 的对话面可观测特征，这里各锁一条：
  1. 回答是**逐字吐**的，不是整段闪现 ⇒ 前端必须有打印器，且 /api/chat 回答走它；
  2. 吐字时有**末尾光标**，答完撤掉 ⇒ 打印结点带 printing 类、光标元素随收尾移除；
  3. 别把「写不到实物」当正常 ⇒ app.js 里每个 $("id") 都必须在 index.html 有对应元素；
  4. 先说过程、再说正文 ⇒ 步骤行（可折叠）+ 逐字正文；
  5. 过程要细 ⇒ 扫描 / 工具 / 回执 / 回答 四段，每段耗时来自回执实测字段。

另加一条 2026-11-06 扫描顺手修掉的口径：package.json 里不许再出现写死的
`C:/Users/<某个人>/...`（AGENTS §3），`electronDist` 一律相对路径。

判据读的是源码文本，不启服务、不碰 state。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONSOLE = ROOT / "holo_pet_w3" / "console"
APP_JS = CONSOLE / "app.js"
APP_CSS = CONSOLE / "app.css"
INDEX = CONSOLE / "index.html"
PKG = ROOT / "holo_pet_w3" / "package.json"


class TestAiPrint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = APP_JS.read_text(encoding="utf-8")
        cls.css = APP_CSS.read_text(encoding="utf-8")
        cls.html = INDEX.read_text(encoding="utf-8")

    def test_a_printer_exists_and_answer_goes_through_it(self):
        self.assertIn("function printBot(", self.js, "没有逐字打印器")
        self.assertIn("function finishPrinting(", self.js, "没有收尾器：上一轮会留半句")
        # /api/chat 的成功分支必须走打印器，不许退回整段闪现
        self.assertRegex(self.js, r"printBot\(String\(j\.text")
        self.assertNotRegex(self.js, r"addBot\(String\(j\.text")

    def test_b_printing_tail_and_caret(self):
        self.assertIn('"msg bot printing"', self.js, "打印结点没带 printing 标记")
        self.assertIn("tw-caret", self.js, "打印时没有光标元素")
        self.assertIn("__finishPrint", self.js, "结点不可被外部收尾")
        self.assertIn(".tw-caret", self.css, "光标没有样式")
        self.assertIn("@keyframes tw-blink", self.css, "光标不闪")
        self.assertIn("function _stickBottom(", self.js, "没有跟滚判定")

    def test_c_every_id_written_by_app_js_exists_in_html(self):
        ids = set(re.findall(r'\bid="([^"]+)"', self.html))
        refs = set(re.findall(r'\$\("([^"]+)"\)', self.js))
        # 由别的脚本在运行时生成的容器，不要求出现在 index.html
        dynamic = {"sm-saved"}
        missing = sorted(refs - ids - dynamic)
        self.assertEqual(missing, [], "app.js 写到不存在的元素：%s" % missing)

    def test_d_no_hardcoded_user_path_in_package(self):
        pkg = json.loads(PKG.read_text(encoding="utf-8"))
        dist = pkg.get("build", {}).get("electronDist")
        self.assertIsNotNone(dist, "electronDist 缺失：离线打包会去找下载缓存")
        self.assertNotRegex(dist, r"^[A-Za-z]:/Users/", "electronDist 写死了别人家的用户名")
        raw = PKG.read_text(encoding="utf-8")
        self.assertNotIn("C:/Users/ADMIN", raw)

    def test_e_ai_steps_block_like_codex(self):
        """Codex 的第四可观测特征：先说过程，再说正文。

        2026-11-06 主人指着 Codex 面说「还有对话面板的 AI 对话显示，设置这样的同款」。
        锁三条：① /api/chat 回执能折成步骤行；② 步骤行插在正文之前；③ 详情默认折叠可展开。
        """
        self.assertIn("function buildSteps(", self.js, "没有把 /api/chat 回执折成步骤行")
        self.assertIn("function renderSteps(", self.js, "没有步骤行渲染器")
        self.assertRegex(self.js, r"printBot\(String\(j\.text[^;]*buildSteps\(j\)",
                          "/api/chat 成功分支没把步骤行交给打印器")
        _k = self.js.index("  function printBot(text, meta, steps, turn) {")
        self.assertLess(self.js.index("      renderSteps(wrap, steps);", _k),
                        self.js.index('body = el("span", "msg-text");', _k),
                        "步骤行必须排在回答正文之前（Codex 是「先过程后正文」）")
        self.assertIn("body.hidden = true", self.js, "详情不默认折叠就会盖住正文")
        for cls in (".msg-steps", ".step-head", ".step-chev", ".step-body", ".step-row"):
            self.assertIn(cls, self.css, "步骤行缺少样式：%s" % cls)

    def test_f_every_step_visible(self):
        """2026-11-06 主人令（逐字）：「精细一点必须她扫描过哪里，在执行哪里，调用什么
        工具每一步细节都要能看得到」。

        锁五条：
          ① 回执到达前就有一条**带真实计时**的过程行（beginTurn），不是空省略号；
          ② 步骤按执行序拆成「扫描指令 / 调用工具 / 执行回执 / 组织回答」；
          ③ 每一步的耗时都来自回执实测字段（ms_route / ms / elapsed_ms），不写死；
          ④ 失败分支也走打印器 + 步骤行（报错同样要能看见她做过什么）；
          ⑤ 收起/展开是**逐条**的（step-head.is-open），不是一个箭头转全组。
        """
        self.assertIn("function beginTurn(", self.js, "没有「进行中」骨架：回执前是空省略号")
        self.assertRegex(self.js, r"var turn = beginTurn\(\);", "chatSubmit 没用进行中骨架")
        self.assertIn("__abort", self.js, "进行中骨架无法被下一轮收尾（会留下走秒的死行）")
        self.assertIn("turn.phase(", self.js, "阶段文案不可更新")
        for title in ("扫描指令", "调用工具", "执行回执", "组织回答"):
            self.assertIn(title, self.js, "步骤行缺一段：%s" % title)
        for field in ("j.ms_route", "cap.ms", "j.elapsed_ms", "rt.matched", "Object.keys(cap)"):
            self.assertIn(field, self.js, "步骤行没有用回执实测字段：%s" % field)
        self.assertRegex(self.js, r'printBot\("⚠ " \+ \(\(j && j\.error\)',
                         "失败分支没走打印器（报错看不到过程）")
        self.assertIn(".step-ms.live", self.css, "进行中的计时没有样式")
        self.assertIn(".step-head.is-open .step-chev", self.css, "展开态不是逐条的")

    def test_g_step_numbers_come_from_real_stages(self):
        """/api/chat 必须把「路由器总耗时」与「工具耗时」分开报，屏幕采集必须能自愈。

        这两条是 test_f 的地基：前端显示的两段毫秒要么来自这里的实测字段，
        要么只能靠猜 —— 猜出来的步骤行比没有更坏。
        """
        server = (ROOT / "tools" / "console-server.py").read_text(encoding="utf-8")
        self.assertIn('cap["ms_route"] = round(_cr_ms, 1)', server,
                      "回执没有分开报路由器耗时")
        self.assertIn('cap["ms_run"]', server, "回执没有报工具耗时")
        self.assertIn("time.perf_counter()", server, "分段耗时不是用 perf_counter 量的")

        core = (ROOT / "gbt_allinone" / "tentacle" / "omni_core.py").read_text(encoding="utf-8")
        self.assertIn("def _mss_drop(", core, "失效的 mss 句柄没有重建入口")
        self.assertIn("for _attempt in (0, 1):", core, "mss 抓帧失败后不重试")
        self.assertIn('result["mss_recovered"] = True', core,
                      "自愈没有在回执里留痕（看不出来是重建过还是本来就好）")


if __name__ == "__main__":
    unittest.main()