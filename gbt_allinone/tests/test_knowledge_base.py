# -*- coding: utf-8 -*-
"""自进化知识库 · 封印与准入的回归测试（Owner 2026-09-22：「只能是你的资料」）。

守三件事：
  1. 外来资料一律进不来（白名单默认拒）
  2. 我们自己的进得来，且带**独立观测**出来的投递方
  3. 封印审计**抓得到**污染 —— 绕过 deposit 直接写盘也能被查出来
     （抓不到就只是橡皮图章，等于没有保证）
"""
import json
import unittest

from gbt_allinone import knowledge_base as kb

# 注意（实测教训 2026-09-22）：**不许在测试里改 GBT_STORE_DIR**。
# `gbt_allinone/_paths.py` 在 import 时就把 STORE_DIR 绑定死了（O53 甲案），
# 之后再改 env 会让 verify_store_binding() 直接抛错 —— 写入口全部拒绝。
# 所以这里的隔离靠**起 Python 之前**设 env（gbt_allinone/tests/__init__.py
# 已有一道闸：绑到生产 store 就拒绝跑测试）。


class AdmissionTests(unittest.TestCase):
    """准入：只能是我们的资料。"""

    def test_foreign_sources_are_refused(self):
        for src in ("devour_github", "devour", "github", "external_llm",
                    "unknown", "web", "crawl"):
            r = kb.deposit({"source": src, "text": "别人家的知识"})
            self.assertFalse(r["ok"], f"{src} 竟然进来了")
            self.assertTrue(r.get("foreign"), f"{src} 没被标成外来")
            self.assertIn("拒收外来资料", r["reason"])

    def test_missing_source_refused(self):
        for rec in ({}, {"text": "没来源"}, {"source": "codex"}, "不是dict"):
            r = kb.deposit(rec)
            self.assertFalse(r["ok"])

    def test_our_sources_admitted(self):
        for src in ("codex", "gbt", "gbt_allinone", "owner",
                    "gbt_allinone:codex_bridge", "codex-turn"):
            r = kb.deposit({"source": src, "text": f"我们的资料 via {src}"})
            self.assertTrue(r["ok"], f"{src} 被误拒了")

    def test_admitted_by_is_observed_not_declared(self):
        # 每条用**唯一内容**：临时 store 会在多次 pytest 之间留存，
        # 内容一样就会去重，测的就不是"插入"这条路了。
        import uuid
        r = kb.deposit({"source": "codex",
                        "text": "投递方必须是看出来的 " + uuid.uuid4().hex,
                        "admitted_by": "我说我是谁就是谁"})
        self.assertTrue(r["ok"])
        rec = json.loads((kb.KB_ROOT / r["path"]).read_text(encoding="utf-8"))
        # 投递方自报的那个字段不许冒充观测值
        self.assertNotEqual(rec["admitted_by"], "我说我是谁就是谁")
        self.assertIn("test_knowledge_base.py", rec["admitted_by"])
        self.assertTrue(rec["sealed"])


class SealTests(unittest.TestCase):
    """封印审计必须抓得到污染。"""

    def test_clean_store_is_sealed(self):
        s = kb.verify_seal()
        self.assertTrue(s["sealed"], s["violations"])

    def test_rejections_are_logged(self):
        kb.deposit({"source": "github", "text": "被拒也要留痕"})
        self.assertGreaterEqual(kb.verify_seal()["foreign_rejected"], 1)

    def test_injected_foreign_record_is_caught(self):
        """绕过 deposit 直接写盘 —— 审计器必须查得出来。"""
        raw = kb.paths()["raw"] / "2026-09"
        raw.mkdir(parents=True, exist_ok=True)
        bad = raw / "INJECTED.json"
        bad.write_text(json.dumps({"sha256": "x", "source": "devour_github",
                                   "sealed": True, "text": "偷渡进来的"}),
                       encoding="utf-8")
        try:
            s = kb.verify_seal()
            self.assertFalse(s["sealed"], "塞了外来记录还说 sealed —— 橡皮图章")
            self.assertTrue(any("外来" in v["why"] for v in s["violations"]))
            # 污染必须让 pulse 显式报错，不许当没事
            self.assertIn("seal", kb.pulse()["stage_errors"])
        finally:
            bad.unlink()

    def test_injected_unsealed_record_is_caught(self):
        """来源对、但 sealed 不是 True / 缺 admitted_by，也算违规。"""
        raw = kb.paths()["raw"] / "2026-09"
        raw.mkdir(parents=True, exist_ok=True)
        bad = raw / "UNSEALED.json"
        bad.write_text(json.dumps({"sha256": "y", "source": "codex",
                                   "text": "来源对但没封印"}),
                       encoding="utf-8")
        try:
            s = kb.verify_seal()
            self.assertFalse(s["sealed"])
            whys = " ".join(v["why"] for v in s["violations"])
            self.assertIn("admitted_by", whys)
        finally:
            bad.unlink()

    def test_kb_is_physically_separate_from_devoured(self):
        """知识库与『吞进来的』那棵树必须物理分开。"""
        self.assertNotEqual(kb.KB_ROOT, kb.STORE_DIR / "devoured")
        self.assertNotIn("devoured", kb.KB_ROOT.parts)


class EnergyHonestyTests(unittest.TestCase):
    """能源与产出不许注水。"""

    def test_energy_matches_independent_recount(self):
        """能源必须等于**独立重数**出来的磁盘文件数 —— 对不上就是注水。"""
        kb.deposit({"source": "codex", "text": "数能源用的一条真实资料"})
        raw = sorted(kb.paths()["raw"].rglob("*.json"))
        tech = 0
        if kb.paths()["techniques"].is_file():
            tech = sum(1 for l in kb.paths()["techniques"].read_text(
                encoding="utf-8-sig").splitlines() if l.strip())
        e = kb.energy()
        self.assertEqual(e["raw_entries"], len(raw))
        self.assertEqual(e["techniques"], tech)
        self.assertEqual(e["energy_units"], len(raw) + tech)

    def test_voice_refuses_to_invent_style(self):
        v = kb.derive_voice(min_samples=9999)
        self.assertFalse(v["ok"])
        self.assertIn("样本", v["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
