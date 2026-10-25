# -*- coding: utf-8 -*-
"""模型密钥池 · 带牙用例（R-H197）。

① 红线⑥：新增密钥**默认拒绝**（auth_gate_required），显式 authorized 才落池；
② 红线①：一 AI 一号 —— 缺 owner_ai_id ⇒ 拒；触手借密钥必须带 owner_ai_id；
③ 红线②：密钥只存 DPAPI（须落在 store/secrets/*.dpapi）；明文密钥 ⇒ 拒；
④ 红线③：同一 AI 不许换绑容器（防两处真相）；
⑤ 红线④：**不批量注册 / 不绕验证**（用途里出现即拒）；
⑥ 红线⑤：超限**只上报**（`action: report_only`），不自动换号；
⑦ 引用唯一真相源：Agnes profile 取自 `deepseek_key._PROFILES`（不另抄一份）；
⑧ 没有对应身份的密钥 ⇒ 拒执行 + 上报（不瞎猜）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import model_key_pool as mkp  # noqa: E402

REF = "gbt_allinone/store/secrets/agnes_api.dpapi"


def _pool():
    p = mkp.ModelKeyPool()
    p.register_key(mkp.ProviderProfile(api_key_ref=REF, owner_ai_id="music-01"),
                   authorized=True, purpose="为音乐 AI 配置唯一密钥")
    return p


class RedLineTests(unittest.TestCase):
    def test_register_requires_auth_gate(self):
        p = mkp.ModelKeyPool()
        out = p.register_key(mkp.ProviderProfile(api_key_ref=REF, owner_ai_id="music-01"))
        self.assertFalse(out["ok"])
        self.assertEqual(out["rule"], "auth_gate_required")
        self.assertIn("filesystem_write", out["scopes"])

    def test_owner_ai_id_is_mandatory(self):
        p = mkp.ModelKeyPool()
        out = p.register_key(mkp.ProviderProfile(api_key_ref=REF, owner_ai_id=""),
                             authorized=True)
        self.assertEqual(out["rule"], "missing_owner_ai_id")
        self.assertIn("一 AI 一号", out["why"])

    def test_key_must_be_dpapi_path(self):
        p = mkp.ModelKeyPool()
        for bad in ("plain.txt", "store/secrets/key.json", "sk-abcdef0123456789abcdef"):
            out = p.register_key(mkp.ProviderProfile(api_key_ref=bad, owner_ai_id="a-01"),
                                 authorized=True)
            self.assertEqual(out["rule"], "key_must_be_dpapi", "不该接受：%s" % bad)

    def test_same_owner_cannot_rebind_to_another_container(self):
        p = _pool()
        out = p.register_key(mkp.ProviderProfile(
            api_key_ref="gbt_allinone/store/secrets/other_api.dpapi", owner_ai_id="music-01"),
            authorized=True)
        self.assertEqual(out["rule"], "shared_key")

    def test_bulk_register_and_bypass_are_refused(self):
        p = mkp.ModelKeyPool()
        bad = p.register_key(mkp.ProviderProfile(api_key_ref=REF, owner_ai_id="x-01"),
                             authorized=True, purpose="批量注册一百个号")
        self.assertIn("no_bulk_register", [r["rule"] for r in bad["problems"]])
        bad2 = p.register_key(mkp.ProviderProfile(api_key_ref=REF, owner_ai_id="x-02"),
                              authorized=True, purpose="绕过验证直接开")
        self.assertIn("no_bypass", [r["rule"] for r in bad2["problems"]])

    def test_plaintext_secret_in_purpose_is_refused(self):
        p = mkp.ModelKeyPool()
        bad = p.register_key(mkp.ProviderProfile(api_key_ref=REF, owner_ai_id="x-03"),
                             authorized=True, purpose="key sk-abcdef0123456789abcdef")
        self.assertIn("no_plaintext_secret", [r["rule"] for r in bad["problems"]])


class LeaseTests(unittest.TestCase):
    def test_lease_needs_owner_and_known_key(self):
        p = mkp.ModelKeyPool()
        self.assertEqual(p.lease("t-1", "")["rule"], "missing_owner_ai_id")
        self.assertEqual(p.lease("t-1", "nobody")["rule"], "no_key_for_owner")
        p2 = _pool()
        ok = p2.lease("t-1", "music-01")
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["key_ref"], REF)
        self.assertIn("借用", ok["note"])

    def test_tentacles_never_create_their_own_key(self):
        """一触手一号 = 批量注册 = 违规：同一 AI 的多个触手共用**同一把**密钥。"""
        p = _pool()
        a = p.lease("t-A", "music-01")
        b = p.lease("t-B", "music-01")
        self.assertEqual(a["key_ref"], b["key_ref"], "同 AI 的触手共用身份密钥")
        self.assertEqual(p.stats()["keys_total"], 1, "两个触手不该多出密钥")

    def test_usage_over_limit_reports_only(self):
        p = _pool()
        p.set_limit("music-01", 100)
        row = p.lease("t-1", "music-01")
        p.report_usage(row["lease_id"], 60)
        over = p.report_usage(row["lease_id"], 60)
        self.assertTrue(over["limit_exceeded"])
        self.assertEqual(over["action"], "report_only")
        self.assertIn("不自动换号", over["note"])
        self.assertTrue(p.release(row["lease_id"])["ok"])

    def test_concurrency_is_per_ai_identity_and_blocks_at_cap(self):
        """R-H198 · 「必须一人一个」：**并发按 AI 身份计，到顶即拒**（并说清不许抢别人的钥匙）。"""
        p = _pool()
        p.set_concurrency("music-01", 1)
        first = p.lease("t-1", "music-01")
        self.assertTrue(first["ok"])
        second = p.lease("t-2", "music-01")
        self.assertFalse(second["ok"])
        self.assertEqual(second["rule"], "owner_concurrency_full")
        self.assertIn("不许去抢别人的钥匙", second["why"])
        p.release(first["lease_id"])
        self.assertTrue(p.lease("t-3", "music-01")["ok"], "release 之后名额应当腾出来")

    def test_cross_ai_borrow_is_refused(self):
        p = _pool()
        out = p.borrow("video-01", "music-01", tentacle_id="t-9")
        self.assertFalse(out["ok"])
        self.assertEqual(out["rule"], "cross_ai_borrow")
        self.assertIn("限流", out["why"])
        self.assertIn("必须一人一个", " ".join(mkp.RED_LINES))


class ReferenceTests(unittest.TestCase):
    def test_agnes_profile_comes_from_the_single_source(self):
        agnes = mkp.run("agnes")
        self.assertEqual(agnes["base_url"], "https://apihub.agnes-ai.com/v1")
        self.assertEqual(agnes["model"], "agnes-2.5-flash")
        self.assertTrue(agnes["profile_known"],
                        "agnes profile 必须取自 deepseek_key._PROFILES（唯一真相源）")
        self.assertIn("agnes", mkp._DEFAULT._profile_names())

    def test_module_has_no_network_or_write_paths(self):
        src = Path(mkp.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink("):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
