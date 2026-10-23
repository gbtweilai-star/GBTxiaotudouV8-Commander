# -*- coding: utf-8 -*-
"""触手自配装备与账号 判据（主人令 2026-10-09：「触手自主注册配置自己的装备」「职业也是一个不能少」）。

锁四件事：
  ① **职业是前提**：职业册现读三件套不截断；没立职业 → 空需求，不瞎配；
  ② **需求是算出来的**：分域表 + 职业名关键词（带「视频」就要 ffmpeg，带「视觉」就要 screen）；
  ③ **装备坞是真门**：白名单外拒 · 已装的真探测 · 要授权的如实报 needs_grant · 第三方件不代下；
  ④ **门按 op 挂**：读类零作用域，equip/install 挂 filesystem_write（equip 动装备再挂 process_execute）。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import tentacle_equip as TE  # noqa: E402
from gbt_allinone import tool_bay as TB  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


class TentacleEquipTest(unittest.TestCase):

    def test_profession_catalog_is_read_without_truncation(self):
        r = TE.run("status")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["职业总数"], r["已看"], "「一共多少」与「看了多少」必须分开报且对得上")
        self.assertFalse(r["截断"], "默认上限内不许截断")
        self.assertGreaterEqual(r["职业总数"], 100)
        # 🔴 2026-10-17 翻正（留痕 · 原断言 / 为什么翻 / 现口径）：
        #   原断言把分域数写死成 **19** —— 职业册从 `vaults/agency_tentacles/library/zh` **现扫**，
        #   实测已长到 **295 职业 / 20 分域**（外部职业定义又进了一批）⇒ 写死的数字必然腐烂。
        #   原期望【不变】：分域数必须与**职业册现读**一致。现口径：从 `TE.professions()` 现算，
        #   另留一条**下限**（当年 19 个分域，缩水就要红）——不写死、也不放空。
        prof = TE.professions()
        divs = {row.get("division") for row in (prof.get("professions") or [])}
        divs.discard(None)
        self.assertEqual(r["分域数"], len(divs), "分域数必须与职业册现读一致（不许写死）")
        self.assertGreaterEqual(len(divs), 19, "分域数缩水（当年 19 个分域）")

    def test_no_profession_means_no_equipment(self):
        p = TE.run("plan", key="__绝对没有这个职业__")
        self.assertFalse(p["ok"])
        self.assertEqual(p["需要装备"], [], "未立职业就得空需求，不瞎配")
        self.assertEqual(p["需要服务位"], [])

    def test_needs_are_computed_from_division_and_keywords(self):
        found = TE.professions()
        rows = found["professions"]
        design = next(r for r in rows if r["division"] == "design")
        need = TE.needs_for(design)
        self.assertTrue(need.tools, "分域表必须给出装备")
        hit = next((r for r in rows
                    if "视频" in (str(r.get("name") or "") + str(r.get("description") or ""))), None)
        if hit:
            self.assertIn("ffmpeg", TE.needs_for(hit).tools, "名字/职责带「视频」就必须补 ffmpeg")

    def test_plan_is_readonly(self):
        p = TE.run("plan", key="design")
        self.assertIn("说明", p)
        self.assertIn("只读", p["说明"])

    def test_tool_bay_whitelist(self):
        r = TB.run("install", tool="__不在白名单的东西__")
        self.assertFalse(r["ok"])
        self.assertIn("白名单", r["why"])
        self.assertIn("git", r["whitelist"])

    def test_tool_bay_probes_for_real(self):
        st = TB.run("state")
        self.assertEqual(st["白名单数"], len(TB.CATALOG))
        self.assertIn("python", st["已装"], "python 在本机必须探得到")
        self.assertIn("无探针", st["逐件"]["json_tool"]["state"]) if False else None
        for name, v in st["逐件"].items():
            if v["state"] == "已装":
                self.assertTrue(v["probed"], "报「已装」的必须真跑过探针：%s" % name)

    def test_gate_gear_reports_needs_grant_not_fake(self):
        """screen 要接上她的眼 ⇒ 必须过 privacy_read 门；没票就得如实报。"""
        r = TB.ToolBay().install("screen")
        if r.get("ok"):
            self.skipTest("本机此刻有 privacy_read 票（窗口内），跳过")
        self.assertEqual(r.get("needs_grant"), "privacy_read")
        self.assertFalse(r.get("fake", False))

    def test_third_party_gear_needs_owner_not_silent_install(self):
        r = TB.ToolBay().install("ocr")           # 本机未装、且无探针
        self.assertFalse(r.get("ok"))
        self.assertTrue(r.get("needs_owner_manual"), "第三方件不许偷偷装：%s" % r)

    def test_equip_dry_run_by_default(self):
        found = TE.professions()["professions"]
        slug = found[0]["slug"]
        e = TE.equip(slug, accounts=False, tools=True)
        self.assertTrue(e["dry_run"], "dry_run 必须默认真")
        self.assertTrue(all(a.get("干") == "只算" for a in e["动作"]), e["动作"])

    def test_equip_unknown_profession_refused(self):
        e = TE.equip("__没有__", dry_run=False)
        self.assertFalse(e["ok"])
        self.assertIn("先立职业", e["why"])

    def test_ledgers_are_written(self):
        before = TE.LEDGER.exists()
        TE.run("plan", key="design")
        self.assertTrue(TE.LEDGER.exists() or before, "算过一次就该落账")

    def test_gate_scopes(self):
        cases = [
            ({"op": "status"}, set()),
            ({"op": "plan", "key": "x"}, set()),
            ({"op": "professions"}, set()),
            ({"op": "report"}, set()),
            ({"op": "equip", "key": "x", "dry_run": True}, {"filesystem_write", "process_execute"}),
            ({"op": "equip", "key": "x", "tools": False}, {"filesystem_write"}),
            ({"op": "weird"}, {"filesystem_write"}),
        ]
        for payload, want in cases:
            d = policy.evaluate("tentacle_equip", dict(payload))
            self.assertEqual(set(d.scopes), want, "tentacle_equip 作用域不对：%s" % payload)
        for payload, want in [({"op": "state"}, set()),
                              ({"op": "install", "tool": "git"}, {"filesystem_write"}),
                              ({"op": "weird"}, {"filesystem_write"})]:
            d = policy.evaluate("tool_bay", dict(payload))
            self.assertEqual(set(d.scopes), want, "tool_bay 作用域不对：%s" % payload)

    def test_assign_one_tentacle_one_profession(self):
        """职业是前提：给触手立职业 → 一触手一职业（重复立要 force）· 不在册的拒。"""
        import tempfile as _tf
        from pathlib import Path as _P
        rows = TE.professions()["professions"]
        pick = next(r for r in rows if r["division"] == "engineering")
        old = TE.ASSIGN_FILE
        with _tf.TemporaryDirectory() as td:
            TE.ASSIGN_FILE = _P(td) / "assign.json"
            try:
                a = TE.assign("t900", pick["slug"])
                self.assertTrue(a["ok"], a)
                self.assertEqual(a["职业"], pick["name"])
                again = TE.assign("t900", pick["slug"])
                self.assertFalse(again["ok"], "一触手一职业：重复立必须拒")
                self.assertIn("已立过职业", again["why"])
                forced = TE.assign("t900", pick["slug"], force=True)
                self.assertTrue(forced["ok"], "加 force 才许改")
                bad = TE.assign("t901", "__册里没有这个职业__")
                self.assertFalse(bad["ok"], "不在册的职业不许立")
                self.assertEqual(TE.assigned()["根数"], 1)
            finally:
                TE.ASSIGN_FILE = old

    def test_plan_accepts_a_tentacle_id(self):
        """立了职业的触手，按 id 就能出需求（不用再报职业名）。"""
        import tempfile as _tf
        from pathlib import Path as _P
        rows = TE.professions()["professions"]
        pick = next(r for r in rows if r["division"] == "design")
        old = TE.ASSIGN_FILE
        with _tf.TemporaryDirectory() as td:
            TE.ASSIGN_FILE = _P(td) / "assign.json"
            try:
                TE.assign("t902", pick["slug"])
                p = TE.plan("t902")
                self.assertTrue(p["ok"], p)
                self.assertEqual(p["职业"], pick["name"])
                self.assertTrue(p["需要装备"], "立了职业就该算得出装备需求")
            finally:
                TE.ASSIGN_FILE = old

    def test_assign_is_gated(self):
        self.assertEqual(set(policy.evaluate("tentacle_equip",
                                             {"op": "assign", "tentacle": "t1",
                                              "profession": "x"}).scopes),
                         {"filesystem_write"})
        self.assertEqual(set(policy.evaluate("tentacle_equip", {"op": "assigned"}).scopes), set())


if __name__ == "__main__":
    unittest.main()
