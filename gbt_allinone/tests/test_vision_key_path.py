# -*- coding: utf-8 -*-
"""vision 密钥路径 · 带牙用例（R-H201）。

① `plaintext_key_in_return`：返回值里出现明文 key ⇒ 拒（backend/status 都不许带）；
② `second_key_path`：不许再有第二条取 key 的路（不读 GBT_VISION_API_KEY、不回落 cloud_llm.API_KEY），
   且必须走保险箱 `load_from_vault`（**不许用 env 优先的 `load_key`**）；
③ `key_leaked_to_log`：审计只收脱敏头（Authorization 变掩码）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone import vision_cap as vc  # noqa: E402


class PlaintextTests(unittest.TestCase):
    def test_backend_has_no_plaintext_key(self):
        b = vc.resolve_vision_backend()
        self.assertNotIn("key", b, "backend 里不许有 key 字段（只许 key_id / key_masked）")
        for k in ("key_id", "key_present", "key_masked"):
            self.assertIn(k, b)
        self.assertTrue(vc.assert_no_plaintext(b, where="backend")["ok"])
        # 🔴 2026-09-25 修**假红**：这里原来是 `assertNotIn("sk-", str(b))` —— 它把**掩码**也咬了。
        #    掩码规则是「前 4 后 2」（`_mask_key`）⇒ 掩码后**本来就以 `sk-` 开头**
        #    （`sk-H****…Z8`）。保险箱里一有 `agnes` 钥匙，这句必红。
        #    实测取证：`git stash` 掉当天全部改动后在 HEAD 口径重跑，**同样 FAILED (failures=1)**
        #    ⇒ 存量假红，不是泄露。**修法是换成精确判据，不是把检查删掉。**
        #    真判据 = 同文件 `test_guard_rejects_plaintext_key` 用的那把带牙的尺子
        #    （`assert_no_plaintext` 按 `\b(?:sk|ak)[-_][A-Za-z0-9_\-]{16,}\b` 判真明文，
        #      掩码里的 `*` 不在字符集内 ⇒ 不误伤）。
        # 🔴 2026-09-25 **修假红·第二处**：掩码判据必须**按「有没有钥匙」分两态**。
        #    原样这里是**无条件**的 `assertIn("*", b["key_masked"])` ——
        #    而 `resolve_vision_backend()` 在没钥匙时是**刻意**返回空掩码的
        #    （`vision_cap.py` L204：`"key_masked": _mask_key(key) if key else ""`）。
        #    ⇒ 在隔离 store（无 DPAPI 保险库）下跑，`key_present=False`、`key_masked=""`，
        #      这条就以 **`'*' not found in ''`** 变红 ——
        #      **它分不清「掩码没掩好」和「压根没有钥匙」**，是拿一个不成立的前提去断言。
        #    实测（2026-09-25）：隔离 store 下 `key_present=False / key_masked='' / _vision_key() 为空`。
        #    **修法**：有钥匙才断言掩码性质；没钥匙就断言"必须是空串、不许编个假掩码" ——
        #            两态都带牙，而不是把检查删掉。
        if b["key_present"]:
            self.assertIn("*", b["key_masked"], "有钥匙时掩码必须真的掩过（含 *）")
            self.assertNotEqual(b["key_masked"], vc._vision_key(),
                                "掩码不许等于明文 —— 这才是「明文没出返回值」")
        else:
            self.assertEqual(b["key_masked"], "",
                             "没有钥匙时掩码必须是空串：不许凭空编一个假掩码出来")
            self.assertFalse(bool(vc._vision_key()), "key_present=False 时取值也必须是空")
        # 反向控制：把明文塞进同一个字段，这把尺子必须咬
        self.assertFalse(
            vc.assert_no_plaintext({"key_masked": "sk-" + "a" * 40}, where="poison")["ok"],
            "反向控制失败：连明文都咬不动 ⇒ 上面那两条等于没验")

    def test_guard_rejects_plaintext_key(self):
        bad = vc.assert_no_plaintext({"key": "sk-abcdefghijklmnopqrstuvwx"}, where="poisoned")
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "plaintext_key_in_return")
        self.assertIn("不许带明文", bad["why"])

    def test_status_op_is_clean_too(self):
        st = vc.run("status")
        self.assertTrue(vc.assert_no_plaintext(st, where="status")["ok"])
        self.assertNotIn("key", st)
        self.assertIn("key_masked", st)


class SinglePathTests(unittest.TestCase):
    def test_no_second_key_path_in_source(self):
        src = Path(vc.__file__).read_text(encoding="utf-8")
        self.assertNotIn('get("GBT_VISION_API_KEY"', src, "不许再从 vision 专用环境变量取 key")
        self.assertNotIn("_cl.API_KEY", src, "不许再回落到模块常量的明文 key")
        self.assertIn("load_from_vault", src, "必须走 DPAPI 保险箱")
        self.assertNotIn("_dk.load_key(", src, "不许用 load_key：它 env 优先 ⇒ 等于偷偷走环境变量")

    def test_missing_vault_key_reports_needs_dependency(self):
        key = vc._vision_key()
        if not key:
            out = vc.cloud_recognize(image=None)
            self.assertFalse(out["ok"])
            self.assertEqual(out.get("status"), "needs_dependency",
                             "保险箱没密钥 ⇒ 如实报缺，不许拿环境变量顶上")


class AuditMaskTests(unittest.TestCase):
    def test_authorization_header_is_masked_for_audit(self):
        masked = vc._safe_headers({"Content-Type": "application/json",
                                   "Authorization": "Bearer sk-abcdefghijklmnopqrstuvwx"})
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", masked["Authorization"])
        self.assertTrue(masked["Authorization"].startswith("Bearer "))
        self.assertIn("*", masked["Authorization"])
        self.assertEqual(masked["Content-Type"], "application/json")

    def test_audit_call_uses_masked_headers(self):
        src = Path(vc.__file__).read_text(encoding="utf-8")
        i = src.find("_audit.begin(")
        self.assertGreater(i, -1, "找不到 _audit.begin 调用")
        # **只看审计那一次调用**（判据不许扩大化：真实 HTTP 请求里的 headers=headers 是合法的）
        j = src.find("headers=_safe_headers(headers))", i)
        self.assertGreater(j, i, "审计没走脱敏头")
        block = src[i:j + len("headers=_safe_headers(headers))")]
        self.assertIn("_safe_headers(headers)", block,
                      "审计必须收脱敏头：不许把 Authorization 原文交给审计")
        self.assertNotIn("headers=headers", block, "审计那一段不许直接收原文头")


if __name__ == "__main__":
    unittest.main()
