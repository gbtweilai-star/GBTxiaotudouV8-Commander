# -*- coding: utf-8 -*-
"""`hf_voice` 判据（主人令 2026-09-28「把插件连接好部署语音…安装 3 个这个插件轮询使用避免卡壳」）。

判据（每条都能红；**关键是第 C/D 两条——守卫和轮询必须真跑，不是看代码**）：
  A. **3 臂在册**（主人令点名的"装 3 个"）· 只回**掩码**，密钥永不回显；
  B. **无 token ⇒ 如实不可用**（fail-closed，不许拿"应该能用"顶替），且**说清缺什么、谁有权给**；
  C. **出网硬钉真跑**：非 https / 环回 / 私有 / 野主机**必须全拒**，白名单内**必须放行**
     （第一版我把白名单那条也当"漏放"，把正确行为判成红 —— 这条自己犯过的错由 C 现在钉住）；
  D. **轮询 + 冷却换道真跑**：喂失败 ⇒ 该臂进冷却、下次自动投下一臂（"避免卡壳"的机制在不在）；
  E. **多模态维度表含"文→声"**（歌声在多模态端口里有户口）；
  F. **模型表诚实**：候选全是 `verified=False`（本机没 token，谁也别当"已支持"）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "gbt_allinone" / "tools"


def _load(name: str, path: Path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


class TestHfVoice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("hv_t", T / "hf_voice.py")

    # ---- A 3 臂 + 只回掩码 ----
    def test_a_three_arms_and_masked_only(self):
        self.assertEqual(3, len(self.m.ARMS), "主人令要装 3 个轮询")
        self.assertEqual(["hf-1", "hf-2", "hf-3"], [a["id"] for a in self.m.ARMS])
        old = dict(os.environ)
        os.environ["HF_TOKEN_1"] = "hf_" + "A" * 30
        try:
            st = self.m.status()
            a1 = st["arms"][0]
            self.assertTrue(a1["present"], "配了引用却说不在位")
            self.assertTrue(a1["masked"].endswith("****"), f"掩码形状不对：{a1['masked']}")
            self.assertNotIn("A" * 10, json.dumps(st, ensure_ascii=False), "**明文被回显了**")
        finally:
            os.environ.clear()
            os.environ.update(old)

    # ---- B 无 token ⇒ fail-closed + 说清缺什么 ----
    def test_b_no_token_is_honest(self):
        old = dict(os.environ)
        for k in ("HF_TOKEN_1", "HF_TOKEN_2", "HF_TOKEN_3", "HUGGINGFACE_API_KEY", "HF_TOKEN"):
            os.environ.pop(k, None)
        try:
            r = self.m.sing(text="测试一句", model="facebook/mms-tts-zho")
            self.assertFalse(r.get("ok"), "三臂全空竟然放行")
            self.assertIn("HF_TOKEN_1", json.dumps(r, ensure_ascii=False),
                          "拒了却没说要配什么")
            self.assertIn("主人", json.dumps(r, ensure_ascii=False), "没说清谁有权给")
        finally:
            os.environ.clear()
            os.environ.update(old)

    # ---- C 出网硬钉真跑 ----
    def test_c_egress_pins_really_bite(self):
        bad = ["http://api-inference.huggingface.co/x", "https://127.0.0.1/x",
               "https://localhost/x", "https://10.1.2.3/x", "https://192.168.1.9/x",
               "https://169.254.169.254/x", "https://[::1]/x", "https://evil.example.com/x"]
        for u in bad:
            ok, why = self.m._guard(u)
            self.assertFalse(ok, f"守卫漏放：{u}（why={why}）")
        ok, why = self.m._guard("https://api-inference.huggingface.co/models/x")
        self.assertTrue(ok, f"白名单内的官方域被误拒：{why}")

    # ---- D 轮询 + 冷却换道 ----
    def test_d_rotation_skips_cooled_arm(self):
        with_temp = json.dumps({"at": "x", "event": "cool", "arm": "hf-1",
                                "until": __import__("time").time() + 600})
        old_ledger, old_names = self.m._LEDGER, None
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            self.m._LEDGER = Path(td) / "l.jsonl"
            self.m._LEDGER.write_text(with_temp + "\n", encoding="utf-8")
            old = dict(os.environ)
            os.environ.update({"HF_TOKEN_1": "hf_a", "HF_TOKEN_2": "hf_b", "HF_TOKEN_3": "hf_c"})
            try:
                st = {a["id"]: a for a in self.m.status()["arms"]}
                self.assertGreater(st["hf-1"]["cooling_for_s"], 0, "被冷却的臂没进冷却")
                picked = self.m._pick(exclude=set())
                self.assertIsNotNone(picked, "三臂都在位却挑不出一个")
                self.assertNotEqual("hf-1", picked["id"], "冷却中的臂被挑走了 ⇒ 换道没生效")
                rows = self.m.arms()["rows"]
                self.assertEqual(2, sum(1 for r in rows if r["cooling_for_s"] == 0),
                                 "冷却臂数不对（应有 2 臂可用）")
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.m._LEDGER = old_ledger

    # ---- E 多模态有"文→声"这一格 ----
    def test_e_audio_dimension_exists(self):
        mp = _load("mp_t", ROOT / "gbt_allinone" / "llm" / "multimodal_port.py")
        self.assertIn("audio", mp.DIMENSIONS, "多模态维度表里没有 audio ⇒ 歌声没户口")
        self.assertEqual("文→声", mp.DIM_META["audio"]["dir"])
        self.assertEqual("audio.write", mp.DIM_META["audio"]["gate"])

    # ---- F 模型表诚实 ----
    def test_f_model_table_is_honest(self):
        r = self.m.models()
        self.assertTrue(r["rows"], "候选模型表是空的")
        for row in r["rows"]:
            self.assertFalse(row["verified"],
                             f"{row['id']} 被标成已验证 —— 本机没 token，谁也别当已支持")
            self.assertTrue(row.get("why"), "未验必须写清为什么")


if __name__ == "__main__":
    unittest.main(verbosity=2)
