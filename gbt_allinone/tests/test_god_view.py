# -*- coding: utf-8 -*-
"""上帝视角 判据（主人令 2026-10-09：「超级导航 + 意见和建议 = 定心丸」）。

锁四件事：
  ① overview 全是**现读**（能力位 200+ · 域 10+ · 报警/交付闸字段齐）；
  ② navigate **不给假候选**：出片/安全/部署/触手这几句人话必须命中对应能力位（档 A）；
     没命中的句子必须**如实说没命中**，不许硬凑；
  ③ advise **每条建议都带依据**（没依据不许写成建议）；
  ④ 按不开口闸：输出里**不许出现把活推回用户的句式**。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 🔴 仓约定（照 test_framework.py:11-16）：**先设隔离 store 再导入被测模块** ——
#    否则仓里的保护闸会拒（"拒绝在绑定：真 store，改的就是真（成品）测试"）。
#    我原来四个判据文件都没设 ⇒ 体检里用 pytest 跑时全部 rc=2（实测撞了）。
os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_test_store_"))

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import god_view as GV  # noqa: E402
from gbt_allinone import ux_doctrine as UX  # noqa: E402


class GodViewTest(unittest.TestCase):

    def test_overview_is_live(self):
        o = GV.run("overview")
        self.assertTrue(o["ok"], o)
        self.assertGreaterEqual(o["能力位"], 200)
        self.assertGreaterEqual(o["域数"], 8)
        self.assertIn("断连缺失", o["报警"])
        self.assertIn("交付闸", o)

    def test_navigate_hits_right_family(self):
        cases = {"出一支30秒短视频": ("media_pipeline", "video", "media"),
                 "扫一下有没有漏洞": ("sec_scan", "sec_chain", "hook_enforcer"),
                 "把项目部署上线": ("deploy_queue", "one_key_deploy"),
                 "给她配上职业装备": ("tentacle_equip", "agency_tentacles")}
        for goal, wants in cases.items():
            got = [c["能力位"] for c in GV.run("navigate", goal=goal)["候选"]]
            self.assertTrue(any(w in got for w in wants),
                            "「%s」应该命中 %s，实得 %s" % (goal, wants, got))

    def test_navigate_honest_when_missed(self):
        r = GV.run("navigate", goal="zzzznonsenseqqq")
        self.assertTrue(r["ok"])
        self.assertEqual(r["候选"], [], "命中不了的句子不许硬凑候选")
        self.assertTrue(r.get("没命中就如实"), "没命中必须如实说明")

    def test_advise_always_cites_evidence(self):
        a = GV.run("advise")
        self.assertTrue(a["ok"], a)
        self.assertTrue(a["建议"], "建议不许为空")
        for s in a["建议"]:
            self.assertTrue(str(s.get("依据") or "").strip(),
                            "每条建议都要有依据：%s" % s)

    def test_decision_brain_is_the_system_one_contract(self):
        """决策脑 = System One 契约；云侧 Laya c02 **未绑定必须如实报**（不许假称已接）。"""
        b = GV.run("brain")
        self.assertTrue(b["ok"], b)
        # 契约形状（来自 litellm 的 jev_classifier，只读）：choice + probabilities + confidence
        self.assertIn("System-One 契约", b["脑"])
        self.assertIn("probabilities", b["脑"])
        self.assertEqual(b["端点路径"], "/v1/systemone", "契约的端点路径")
        self.assertFalse(b["端点是否已配"], "端点没配就必须如实报 False（不许假装云上已通）")
        self.assertIn("external_llm", b["出网门"], "出网必须过门（配了也不许偷发）")
        self.assertEqual(b["云插件"]["插件 id"], "g1-02", "Laya 在云插件里的 id")
        self.assertFalse(b["云侧是否已绑定"], "云侧只有 spec，不许报成已绑定")
        self.assertIn("control_loop", b["云插件"]["本机驱动"])

    def test_systemone_request_matches_the_contract(self):
        """请求形状逐字对齐 litellm 的 build_jev_request：state / model / questions{名:{instructions,criteria}}。"""
        req = GV.build_systemone_request("出一支短视频", {"media_pipeline": "视频编排", "audio_mix": "混音"})
        self.assertEqual(sorted(req), ["model", "questions", "state"])
        q = req["questions"]["落点"]
        self.assertIn("instructions", q)
        self.assertEqual(sorted(q["criteria"]), ["audio_mix", "media_pipeline"])

    def test_local_brain_conforms_and_is_labelled_local(self):
        """本机实现必须**自报家门**是 local-conforming，不许冒充云上 Laya。"""
        resp = GV._local_systemone(GV.build_systemone_request(
            "扫漏洞", {"sec_scan": "安全扫描", "hook_enforcer": "钩子闸"}))
        self.assertEqual(resp["impl"], "local-conforming")
        ans = resp["answers"]["落点"]
        self.assertIn("choice", ans)
        self.assertIn("probabilities", ans)
        self.assertIn("confidence", ans)
        self.assertLessEqual(ans["confidence"], 1.0)

    def test_decide_gives_typed_decision(self):
        d = GV.run("decide", goal="出一支30秒短视频")
        self.assertTrue(d["ok"], d)
        self.assertIn(d["决策"], ("SELECT", "CLICK", "TYPE_TEXT", "DONE", "WAIT", "BLOCKED",
                                  "SCROLL_UP", "SCROLL_DOWN"),
                      "决策必须落在**枚举**内（枚举之外的动作不存在）")
        if d["决策"] == "SELECT":
            self.assertIsNotNone(d.get("落在"), "SELECT 必须给出落在哪个能力位")
            self.assertIn("两查", d)
        self.assertIn("快脑", d)

    def test_decide_blocked_when_nothing_matches(self):
        d = GV.run("decide", goal="zzzznonsenseqqq")
        self.assertEqual(d["决策"], "BLOCKED", "没命中必须如实 BLOCKED，不许硬猜")

    def test_cloud_plane_reads_the_executable_mesh(self):
        """云插件面必须读**可执行真身** mesh.json（不是 50 槽蓝图）。

        🔴 这条判据立自一次真栽的跟头（2026-10-09）：我原来读 plugins50.json（蓝图），
        据此报「待主人侧 20 槽」——**看错了台账**。真身是 mesh.json：10 个云插件、
        **每个绑一根触手**（一触手一云插件）、ops + op_gates 齐全。
        """
        c = GV.run("cloud")
        self.assertTrue(c["ok"], c)
        self.assertIn("mesh.json", c["真身"])
        self.assertEqual(c["拼接网"]["插件数"], 10, "拼接网是 10 个云插件")
        self.assertEqual(c["分档"], {"接线就绪": 10}, "10/10 都该是接线就绪")
        for p in c["插件"]:
            self.assertTrue(p["驱动在册"], "%s 的触手驱动不在活注册表里：%s" % (p["插件"], p["触手驱动"]))
            self.assertTrue(p["ops"], "%s 没有 op" % p["插件"])
            self.assertIn(p["档"], ("接线就绪",))
        self.assertIn("已登录", str(c["云账号"]["登录态"]))
        self.assertGreaterEqual(c["云账号"]["在用作用域"], 10)
        self.assertEqual(c["拼接网"]["绑定"]["directed_expected"], 90, "10×9=90 条有向边")
        laya = c["50槽蓝图_规划未部署"]["Laya 槽"]
        self.assertIsNotNone(laya, "50 槽蓝图里必须有 Laya 槽 g1-02")
        self.assertEqual(laya["触手驱动"], "control_loop")
        self.assertTrue(laya["驱动在册"], "Laya 的触手驱动必须是活能力位")

    def test_no_ask_doctrine_holds(self):
        a = GV.run("advise")
        blob = str(a)
        r = UX.check_ask(blob, acted=True)
        self.assertTrue(r["通过"], "上帝视角自己的输出里不许出现要用户做事的句式：%s" % r)


if __name__ == "__main__":
    unittest.main()
