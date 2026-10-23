"""Security regression tests for the application-level AI audit sidecar."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


_STORE = Path(tempfile.mkdtemp(prefix="gbt_ai_audit_test_"))
# 🔴 2026-09-22 第 35 轮修（错报治理 · 同进程跑全量时污染 10 条用例）：
#     这里原来是**无条件** `os.environ["GBT_STORE_DIR"] = str(_STORE)`，
#     并在 import 之后又硬改 `_paths.STORE_DIR = _STORE` / `_paths.STORE_DIR_ENV_AT_BIND`。
#     单文件跑没事（本文件最先 import 包，env 在绑定前设好）；**多文件同进程跑就出事**：
#     pytest 先 collect 所有模块 → 包早已被 runner 绑到 runner 给的隔离 store →
#     本文件再改 env/绑定，就把进程切成**两个 store 口径**
#     （`store._STORE_DIR` 是 import 期快照 = runner 的；`_paths.STORE_DIR` = 本文件的）。
#     实测后果：`selfscan` 立刻报 **P0**、`sec_defenses` ok=False，
#     连带 `test_framework` **10 条**用例红。注意 **selfscan 是对的** ——
#     进程当时确实自相矛盾，它只是如实报了。
#     （归因实测：把我第 34 轮加的那道门撤掉再跑同一个 repro ⇒ **12 failed**，
#      反而更多 ⇒ 这 10 条**不是**那道门造成的，是这里的老污染。）
#     ⇒ 现在：**已绑定就一律不动 env、不动绑定**，沿用 runner 的隔离 store；
#       未绑定（单独跑本文件）才在 import 前设 env —— 那时设才是合法的。
_ALREADY_BOUND = "gbt_allinone._paths" in sys.modules or "gbt_allinone" in sys.modules
if _ALREADY_BOUND:
    from gbt_allinone._paths import STORE_DIR as _BOUND_STORE  # noqa: E402
    _STORE = Path(_BOUND_STORE)
else:
    os.environ["GBT_STORE_DIR"] = str(_STORE)

# 🔴 2026-09-22 第 35 轮：`GBT_OWNER_SESSION` 从**模块 import 时无条件置位**改成
#     **只在本模块用例期间置位、用完还原**（见下面的 setUpModule/tearDownModule）。
#     为什么：pytest 先 collect（import）所有测试模块、再跑用例 ⇒ 在 import 期置位
#     等于**给整个进程发了主人身份**，后续每一个用例都会**绕开人工授权门**。
#     实测（同一个文件、同一套环境，**只差这一个变量**）：
#         未置位 → `test_framework` **142 passed / 5 skipped / 0 failed**
#         置位   → 同一条命令 **直接挂死超时**（>120s）：sec_llm 真去发外部 LLM 请求、
#                  mcp_full_chain 真去跑 `npx`、tentacle 真去动桌面
#     ⇒ 一个测试的"主人身份"绝不许漏给别的测试：**既造假绿（该拦的没拦），又真出网**。
_OWNER_WAS = os.environ.get("GBT_OWNER_SESSION")


def setUpModule():
    """只在本模块用例期间置位 owner session（用完 tearDownModule 还原）。"""
    global _OWNER_WAS
    _OWNER_WAS = os.environ.get("GBT_OWNER_SESSION")
    os.environ["GBT_OWNER_SESSION"] = "1"


def tearDownModule():
    """还原 owner session —— 绝不把"主人身份"留给下一个测试模块。"""
    if _OWNER_WAS is None:
        os.environ.pop("GBT_OWNER_SESSION", None)
    else:
        os.environ["GBT_OWNER_SESSION"] = _OWNER_WAS

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from gbt_allinone import _paths  # noqa: E402
from gbt_allinone import store  # noqa: E402
from gbt_allinone.llm import cloud_llm  # noqa: E402
from gbt_allinone.security import net_guard  # noqa: E402
from gbt_allinone.security import ai_audit as audit  # noqa: E402
from gbt_allinone.security import abl_gateway  # noqa: E402
from gbt_allinone import vision_cap  # noqa: E402
from gbt_allinone import voice_cap  # noqa: E402

# 🔴 2026-09-22 第 35 轮删：这里原来是
#     `_paths.STORE_DIR = _STORE` + `_paths.STORE_DIR_ENV_AT_BIND = str(_STORE)`
#     （R103 甲案的"显式重绑 + 同步快照"）。**它正是把进程切成两个 store 口径的那一刀**：
#     `store._STORE_DIR` 是 import 期 `from ._paths import STORE_DIR` 的**快照**，改 `_paths` 不会
#     带着它走 ⇒ `_paths.STORE_DIR`（新）与 `store._STORE_DIR`（旧）分叉，selfscan 报 P0。
#     上面已经按"已绑定就别动"处理：绑定前的 env 才是唯一合法的注入点 ——
#     env 与绑定天然一致，这条同步快照也就不再需要了。
#     （单独跑本文件时：env 在 import 前设好 ⇒ `_paths.STORE_DIR == _STORE`，等价。）


class TestApplicationLayerAIAudit(unittest.TestCase):
    def setUp(self):
        path = audit._audit_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)

    def _begin(self, body=None, headers=None, *, provider="openai",
               url="https://api.openai.com/v1/chat/completions"):
        return audit.begin(
            provider, url, model="gpt-test",
            request_body=body or {
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "secret prompt"}],
            },
            headers=headers or {
                "Authorization": "Bearer sk-abcdefghijklmnop",
            },
            session_id="session-test",
        )

    def test_allowlisted_endpoint_records_metadata(self):
        context = self._begin()
        self.assertTrue(context)
        self.assertTrue(audit.finish(
            context, status=200,
            response={"model": "gpt-test", "choices": [{
                "message": {"content": "secret answer"},
                "finish_reason": "stop",
            }], "usage": {"prompt_tokens": 3, "completion_tokens": 2,
                          "total_tokens": 5}},
        ))
        rows = audit.query()
        self.assertEqual([row["event"] for row in rows],
                         ["ai_request", "ai_response"])
        request = rows[0]["request_meta"]
        response = rows[-1]["response_meta"]
        self.assertEqual(request["message_count"], 1)
        self.assertNotIn("secret prompt", json.dumps(rows))
        self.assertEqual(response["content_chars"], len("secret answer"))
        self.assertEqual(response["usage"]["total_tokens"], 5)

    def test_non_allowlisted_endpoint_is_not_recorded(self):
        context = audit.begin(
            "openai", "https://example.invalid/v1/chat/completions",
            model="gpt-test", request_body={"messages": []},
        )
        self.assertIsNone(context)
        self.assertEqual(audit.query(), [])

    def test_audit_does_not_mutate_request_or_headers(self):
        body = {
            "model": "gpt-test",
            "messages": [{"role": "user", "content": "keep me unchanged"}],
        }
        headers = {"Authorization": "Bearer sk-abcdefghijklmnop"}
        body_before = copy.deepcopy(body)
        headers_before = copy.deepcopy(headers)
        context = self._begin(body, headers)
        audit.finish(context, status=200, response={"choices": [{
            "message": {"content": "ok"},
        }]})
        self.assertEqual(body, body_before)
        self.assertEqual(headers, headers_before)

    def test_secrets_and_full_content_are_not_at_rest(self):
        secret = "sk-abcdefghijklmnop"
        context = self._begin(body={
            "model": "gpt-test",
            "messages": [{"role": "user", "content": secret}],
        }, headers={"Authorization": f"Bearer {secret}"})
        audit.finish(context, status=200, response_text="full private reply")
        raw = audit._audit_file().read_bytes()
        self.assertNotIn(secret.encode(), raw)
        self.assertNotIn(b"full private reply", raw)

    def test_streaming_audit_records_fingerprint_not_reply(self):
        context = audit.begin(
            "kimi", "https://api.moonshot.cn/v1/chat/completions",
            model="kimi-test", request_body={"messages": []}, stream=True,
        )
        audit.finish(context, status=200, response_text="streamed private reply")
        response = audit.query()[-1]["response_meta"]
        self.assertEqual(response["content_chars"], len("streamed private reply"))
        self.assertNotIn("streamed private reply", json.dumps(audit.query()))

    def test_finish_is_idempotent(self):
        context = self._begin()
        audit.finish(context, status=200, response_text="one")
        audit.finish(context, status=200, response_text="two")
        self.assertEqual(len(audit.query()), 2)

    def test_audit_write_failure_is_fail_open(self):
        with mock.patch.object(
            audit, "locked_append_text", side_effect=OSError("disk unavailable"),
        ):
            context = self._begin()
        self.assertIsNone(context)
        self.assertFalse(audit.finish(None))

    def test_environment_values_are_not_dumped(self):
        marker = "env-secret-marker-123456789"
        os.environ["GBT_AUDIT_TEST_SECRET"] = marker
        try:
            context = self._begin()
            audit.finish(context, status=200, response_text="ok")
            self.assertNotIn(marker, json.dumps(audit.query()))
        finally:
            os.environ.pop("GBT_AUDIT_TEST_SECRET", None)


class TestSharedAuditRedaction(unittest.TestCase):
    def test_store_audit_redacts_nested_secrets_and_full_content(self):
        store.audit("probe", {
            "prompt": "full private prompt",
            "authorization": "Bearer sk-abcdefghijklmnop",
            "nested": {
                "api_key": "sk-abcdefghijklmnop",
                "text": "Bearer abcdefghijklmnopqrstuvwxyz",
            },
        })
        row = store.query_log(event="probe", limit=1)[-1]
        meta = row["meta"]
        self.assertEqual(meta["prompt"]["redacted"], "conversation_content")
        self.assertEqual(meta["authorization"], "<redacted:sensitive_key>")
        self.assertEqual(meta["nested"]["api_key"], "<redacted:sensitive_key>")
        self.assertNotIn("sk-abcdefghijklmnop", json.dumps(meta))
        self.assertNotIn("full private prompt", json.dumps(meta))


class TestAISinkIntegration(unittest.TestCase):
    def setUp(self):
        path = audit._audit_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)

    def test_cloud_llm_gateway_records_real_call_site(self):
        response = {
            "status": 200,
            "json": {
                "model": "gpt-test",
                "choices": [{"message": {"content": "private answer"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3,
                          "total_tokens": 5},
            },
            "text": "private answer",
        }
        body = {
            "model": "gpt-test",
            "messages": [{"role": "user", "content": "private prompt"}],
        }
        headers = {"Authorization": "Bearer sk-abcdefghijklmnop"}
        with mock.patch.object(net_guard, "safe_request_json",
                               return_value=response):
            result = cloud_llm._safe_json(
                "https://api.openai.com/v1/chat/completions",
                body, headers, 10, audit_provider="openai",
                audit_model="gpt-test", audit_session_id="s1",
            )
        self.assertEqual(result["model"], "gpt-test")
        rows = audit.query()
        self.assertEqual([row["event"] for row in rows],
                         ["ai_request", "ai_response"])
        self.assertNotIn("private prompt", json.dumps(rows))
        self.assertNotIn("private answer", json.dumps(rows))

    def test_cloud_llm_gateway_records_http_failure(self):
        response = {"status": 429, "json": None, "text": "rate limited"}
        with mock.patch.object(net_guard, "safe_request_json",
                               return_value=response):
            with self.assertRaises(RuntimeError):
                cloud_llm._safe_json(
                    "https://api.openai.com/v1/chat/completions",
                    {"model": "gpt-test", "messages": []},
                    {"Authorization": "Bearer sk-abcdefghijklmnop"},
                    10, audit_provider="openai", audit_model="gpt-test",
                )
        rows = audit.query()
        self.assertEqual(rows[-1]["event"], "ai_error")
        self.assertEqual(rows[-1]["status"], 429)

    def test_abliteration_gateway_records_metadata_only(self):
        response = {
            "status": 200,
            "json": {
                "model": "abliterated-test",
                "choices": [{"message": {"content": "private answer"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 5},
            },
            "text": "private answer",
        }
        with mock.patch.object(abl_gateway, "_key",
                               return_value="ak-abcdefghijklmnop"), \
                mock.patch.object(net_guard, "safe_request_json",
                                  return_value=response):
            result = abl_gateway.chat("private abliteration prompt")
        self.assertTrue(result["ok"])
        rows = audit.query()
        self.assertEqual([row["event"] for row in rows],
                         ["ai_request", "ai_response"])
        self.assertNotIn("private abliteration prompt", json.dumps(rows))
        self.assertNotIn("private answer", json.dumps(rows))
        self.assertNotIn("ak-abcdefghijklmnop", json.dumps(rows))

    def test_vision_cloud_records_metadata_only(self):
        class _Image:
            def save(self, handle, format=None):
                handle.write(b"fake-image")

        response = {
            "status": 200,
            "json": {
                "model": "glm-4v-test",
                "choices": [{"message": {"content": "private vision answer"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 8},
            },
            "text": "private vision answer",
        }
        with mock.patch.object(vision_cap, "resolve_vision_backend",
                               return_value={
                                   "provider": "ZHIPU_API_KEY",
                                   "base_url": "https://open.bigmodel.cn/api/paas/v4",
                                   "model": "glm-4v-test",
                                   # R-H201：backend **不许带 key**（只给 key_id/掩码）
                                   "key_id": "vision:test",
                                   "key_present": True,
                                   "key_masked": "sk-a****op",
                               }), \
                mock.patch.object(vision_cap, "_vision_key",
                                  return_value="sk-abcdefghijklmnop"), \
                mock.patch.object(vision_cap, "_img_bytes_to_pil",
                                  return_value=_Image()), \
                mock.patch.object(net_guard, "safe_request_json",
                                  return_value=response):
            result = vision_cap.cloud_recognize(
                image=b"fake", prompt="private vision prompt")
        self.assertTrue(result["ok"])
        rows = audit.query()
        self.assertEqual([row["event"] for row in rows],
                         ["ai_request", "ai_response"])
        self.assertNotIn("private vision prompt", json.dumps(rows))
        self.assertNotIn("private vision answer", json.dumps(rows))
        self.assertNotIn("sk-abcdefghijklmnop", json.dumps(rows))
        # R-H201 加固：**返回值本身也不许带明文 key**（不只是审计）
        self.assertNotIn("sk-abcdefghijklmnop", json.dumps(result, ensure_ascii=False))

    def test_asr_records_audio_fingerprint_not_audio_or_key(self):
        audio_bytes = b"RIFF-private-audio-bytes-123456789"
        with tempfile.NamedTemporaryFile(
            prefix="gbt_asr_", suffix=".wav", delete=False,
        ) as handle:
            handle.write(audio_bytes)
            audio_path = handle.name
        response = {
            "status": 200,
            "json": {"text": "private transcript"},
            "text": '{"text":"private transcript"}',
        }
        os.environ["GBT_ASR_BASE_URL"] = "https://api.openai.com/v1"
        os.environ["GBT_ASR_API_KEY"] = "asr-secret-key-123456789"
        os.environ["GBT_ASR_MODEL"] = "whisper-test"
        try:
            with mock.patch.object(
                net_guard, "safe_request_json", return_value=response,
            ):
                result = voice_cap.asr(audio_path)
            self.assertTrue(result["ok"])
            rows = audit.query()
            self.assertEqual([row["event"] for row in rows],
                             ["ai_request", "ai_response"])
            self.assertEqual(rows[-1]["response_meta"]["content_chars"],
                             len("private transcript"))
            rendered = json.dumps(rows)
            self.assertNotIn("private transcript", rendered)
            self.assertNotIn("asr-secret-key-123456789", rendered)
            self.assertNotIn(audio_bytes.decode("ascii"), rendered)
            request_meta = rows[0]["request_meta"]
            self.assertIn("audio_bytes", request_meta["body_keys"])
            self.assertIn("audio_sha256", request_meta["body_keys"])
        finally:
            os.environ.pop("GBT_ASR_BASE_URL", None)
            os.environ.pop("GBT_ASR_API_KEY", None)
            os.environ.pop("GBT_ASR_MODEL", None)
            Path(audio_path).unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main(verbosity=2)
