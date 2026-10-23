# -*- coding: utf-8 -*-
"""刀一 · `coze_mail` 契约测试（方案稿 §八 #1/#2/#3/#4/#5/#6/#10/#11 ＋ G6 三组 ＋ G7）。

判据的判别性（《扫描器自证律》）：每组负对照都必须真红 ——
  白名单外收件人 -> 拒绝且**网络请求不发起**；
  `body` 改一字 -> 旧 `confirm_token` 拒绝；
  通道目录不可写 -> 出站中止 ＋ 主账本**恰好 1 条** `health_channel_failed`。
隔离口径：本文件在任何 `gbt_allinone` import **之前**把 `GBT_STORE_DIR` 指到
`tempfile.mkdtemp()`（一次一换，不复用目录 —— O52），并在绑定生产 store 时立刻报错停下。
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PKG = _HERE.parent
_ROOT = _PKG.parent
_PRODUCTION_STORE = (_PKG / "store").resolve()

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_coze_mail_test_"))
# 🔴 2026-09-22 第 35 轮：owner 身份不再在 **import 期**置位（实测见 test_ai_audit.py），
#     改成"只在本模块用例期间置位、tearDownModule 还原"。
#     import 期置位 = 给整个 pytest 进程发主人身份（collect 先于跑用例）⇒
#     后续模块的用例绕开人工授权门：实测 test_framework 未置位 142 passed/0 failed，
#     置位后同命令挂死超时（真出网、真动桌面）。
_OWNER_WAS = os.environ.get("GBT_OWNER_SESSION")


def setUpModule():
    global _OWNER_WAS
    _OWNER_WAS = os.environ.get("GBT_OWNER_SESSION")
    os.environ["GBT_OWNER_SESSION"] = "1"


def tearDownModule():
    if _OWNER_WAS is None:
        os.environ.pop("GBT_OWNER_SESSION", None)
    else:
        os.environ["GBT_OWNER_SESSION"] = _OWNER_WAS


if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone import _paths, api, coze_mail_cap as CM, store  # noqa: E402
from gbt_allinone.caps_registry import BENIGN_CAPS  # noqa: E402

if Path(_paths.STORE_DIR).resolve() == _PRODUCTION_STORE:
    raise RuntimeError(
        "拒绝在绑定【生产 store】的进程里跑 coze_mail 契约测试：%s" % _paths.STORE_DIR)

ADDR = "gbt_potato_v8@coze.email"
GOOD = "friend@example.com"
STRANGER = "stranger@example.com"
BODY = "GBT-正文探针-A7F3C1\n第二行"


class FakeTransport:
    """受控后端：记下每一次调用，让「网络请求发不发起」可断言。"""

    def __init__(self, connected=True, body_kind="text", origin=None, fail=False):
        self.calls = []
        self.connected = connected
        self.body_kind = body_kind
        self.origin = origin or {"from": GOOD, "subject": "你好",
                                 "has_list_unsubscribe": False}
        self.fail = fail

    def _hit(self, name, **kw):
        self.calls.append((name, kw))
        if self.fail:
            raise CM.TransportUnavailable("fake upstream down")
        return None

    def status(self, address=None):
        self._hit("status", address=address)
        return {"connected": self.connected, "unread": 3, "last_sync_at": "2026-09-18T00:00:00"}

    def inbox(self, folder="INBOX", limit=20, since=None, unread_only=False, query=None):
        self._hit("inbox", folder=folder, limit=limit, query=query)
        return {"messages": [{"msg_id": "m1", "unread": True}],
                "next_cursor": None, "has_more": False}

    def read(self, msg_id=None, max_chars=None):
        self._hit("read", msg_id=msg_id)
        if self.body_kind == "html_only":
            return {"body_kind": "html_only"}
        return {"body": BODY, "body_kind": "text"}

    def mark(self, msg_id=None, flag=None):
        self._hit("mark", msg_id=msg_id, flag=flag)
        return {"result": "ok"}

    def send(self, sender=None, to=None, subject=None, body=None, **kw):
        self._hit("send", to=to)
        return {"result_id": "rid-1", "accepted_at": "2026-09-18T00:00:01"}

    def register_address(self, prefix=None):
        self._hit("register_address", prefix=prefix)
        return {"address": prefix + "@coze.email"}

    def get_message(self, msg_id=None):
        self._hit("get_message", msg_id=msg_id)
        return dict(self.origin)


def _channel_bytes():
    p = CM.events_path()
    return p.read_bytes() if p.is_file() else b""


def _rows():
    out = []
    for raw in _channel_bytes().split(b"\n"):
        if raw.strip():
            out.append(json.loads(raw.decode("utf-8")))
    return out


def _main_rows():
    log = Path(store._LOG)
    if not log.is_file():
        return []
    return [json.loads(x.decode("utf-8")) for x in log.read_bytes().split(b"\n") if x.strip()]


def _seed(address=ADDR, allow=(GOOD,), enabled=True):
    CM.write_state({"address": address, "allow_to": list(allow), "enabled": enabled})


def _expire_status_cache():
    CM._STATUS_CACHE.clear()


class _Base(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(CM.channel_dir(), ignore_errors=True)
        CM.set_transport(None)
        CM._STATUS_CACHE.clear()
        CM._LAST_STATUS_STATE.clear()

    def tearDown(self):
        CM.set_transport(None)
        CM._STATUS_CACHE.clear()
        CM._LAST_STATUS_STATE.clear()

    def _block_channel(self):
        """把 channels 的**落点文件名占成目录** —— 追加打开必失败。

        （Windows 上目录只读位不拦创建，故不用 chmod；也不改 `channel_dir()`，
        这样 `state.json` 仍读得到，被测的就是「账写不进去」这一件事。）
        """
        CM.channel_dir().mkdir(parents=True, exist_ok=True)
        CM.events_path().mkdir()
        return CM.events_path()

    def _send_payload(self, to=GOOD, body=BODY, subject="主题"):
        return {"to": to, "subject": subject, "body": body,
                "confirm_token": CM.build_confirm_token(to, subject, body)}

    def _api_send_payload(self, **kw):
        payload = self._send_payload(**kw)
        payload["op"] = "send"
        return payload


class StatusTtlTests(_Base):
    """§八 #1：三组必须不同；相同即报自盲。"""

    def test_status_ttl_three_groups_must_differ(self):
        _seed()
        fake = FakeTransport()
        CM.set_transport(fake)
        CM.run("status", {})                      # 预热点：这一次允许落首条状态变化
        before = _channel_bytes()

        for _ in range(3):
            CM.run("status", {})
        self.assertEqual(before, _channel_bytes(), "TTL 内连调 3 次必须 0 B 增量")
        self.assertEqual(1, len(fake.calls), "TTL 内只许打一次上游")

        CM._STATUS_CACHE.clear()
        CM.run("status", {})
        self.assertEqual(before, _channel_bytes(), "跨 TTL 且状态未变必须 0 B 增量")

        CM._STATUS_CACHE.clear()
        fake.fail = True
        n_before = len(_rows())
        out = CM.run("status", {})
        rows = _rows()
        self.assertFalse(out["ok"], "上游断开必须如实报 ok=False")
        self.assertEqual(n_before + 1, len(rows), "断开上游后必须**恰好**多 1 条")
        self.assertEqual("coze_mail_status_change", rows[-1]["event"])
        self.assertFalse(rows[-1]["meta"]["connected"])


class OutboundGateTests(_Base):
    """§八 #2/#3 ＋ G6 第 1/2 组：拒绝时网络请求必须**一次都没发起**。"""

    def test_whitelist_negative_control_no_network(self):
        _seed(allow=(GOOD,))
        fake = FakeTransport()
        CM.set_transport(fake)

        with self.assertRaises(CM.CozeMailError) as ctx:
            CM.run("send", self._send_payload(to=STRANGER))
        self.assertIn("白名单", str(ctx.exception))
        self.assertEqual([], fake.calls, "白名单外收件人：网络请求必须不发起")
        self.assertEqual(0, len([r for r in _rows() if r["event"] == "coze_mail_send"]))

        out = CM.run("send", self._send_payload(to=GOOD))
        self.assertTrue(out["ok"])
        self.assertEqual(1, len(fake.calls), "正对照必须真的发一次")
        self.assertEqual(1, len([r for r in _rows() if r["event"] == "coze_mail_send"]))

    def test_confirm_token_is_content_bound(self):
        _seed(allow=(GOOD,))
        fake = FakeTransport()
        CM.set_transport(fake)
        token = CM.build_confirm_token(GOOD, "主题", BODY)
        for bad in ("GBT-正文探针-A7F3C1\n第三行", "GBT-正文探针-A7F3C1\n第二行 "):
            with self.assertRaises(CM.CozeMailError) as ctx:
                CM.run("send", {"to": GOOD, "subject": "主题", "body": bad,
                                "confirm_token": token})
            self.assertIn("confirm_token", str(ctx.exception))
        self.assertEqual([], fake.calls, "令牌不匹配：网络请求必须不发起")

        out = CM.run("send", {"to": GOOD, "subject": "主题", "body": BODY,
                              "confirm_token": token})
        self.assertTrue(out["ok"], "正对照：令牌与内容一致必须发得出去")

    def test_empty_whitelist_means_refuse_all(self):
        _seed(allow=())
        fake = FakeTransport()
        CM.set_transport(fake)
        with self.assertRaises(CM.CozeMailError):
            CM.run("send", self._send_payload(to=GOOD))
        self.assertEqual([], fake.calls)

    def test_noreply_address_is_refused_even_if_whitelisted(self):
        _seed(allow=("no-reply@example.com",))
        fake = FakeTransport()
        CM.set_transport(fake)
        with self.assertRaises(CM.CozeMailError) as ctx:
            CM.run("send", self._send_payload(to="no-reply@example.com"))
        self.assertIn("noreply", str(ctx.exception))
        self.assertEqual([], fake.calls)


class ChannelContentTests(_Base):
    """§八 #4：正文原文永不入档。"""

    def test_body_never_enters_channel(self):
        _seed()
        CM.set_transport(FakeTransport())
        out = CM.run("read", {"msg_id": "m1"})
        self.assertEqual(BODY, out["body"])
        blob = _channel_bytes()
        self.assertNotIn(BODY.encode("utf-8"), blob, "正文原文不许出现在通道里")
        self.assertNotIn("第二行".encode("utf-8"), blob)
        rows = _rows()
        self.assertEqual(1, len(rows))
        meta = rows[0]["meta"]
        self.assertEqual(hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
                         meta["content_sha256"])
        self.assertEqual(len(BODY), meta["chars"])

    def test_read_html_only_never_returns_empty_string(self):
        _seed()
        CM.set_transport(FakeTransport(body_kind="html_only"))
        out = CM.run("read", {"msg_id": "m1"})
        self.assertEqual("html_only", out["body_kind"])
        self.assertIsNone(out["body"], "HTML-only 不许回空字符串冒充正文")
        self.assertNotEqual("", out["body"])


class AddressTests(_Base):
    """§八 #6/#10 ＋ G7：地址单值、register 幂等拒绝。"""

    def test_address_is_single_value_and_register_is_idempotent(self):
        _seed(address=None, allow=(GOOD,))
        fake = FakeTransport()
        CM.set_transport(fake)
        out = CM.run("register", {"prefix": "gbt_potato_v8"})
        self.assertTrue(out["ok"])
        self.assertEqual(ADDR, out["address"])
        self.assertEqual(ADDR, CM.read_state()["address"])
        self.assertEqual(1, len([r for r in _rows() if r["event"] == "coze_mail_address_set"]))

        for other in ("other_prefix", "gbt_potato_v8"):
            n = len(_rows())
            with self.assertRaises(CM.CozeMailError) as ctx:
                CM.run("register", {"prefix": other})
            self.assertIn("幂等拒绝", str(ctx.exception))
            self.assertEqual(ADDR, CM.read_state()["address"], "地址必须不变")
            self.assertEqual(n, len(_rows()), "幂等拒绝不许落 coze_mail_address_set")

    def test_register_prefix_must_come_from_owner(self):
        _seed(address=None)
        CM.set_transport(FakeTransport())
        for bad in (None, "", "AB", "has space", "中文前缀", "a" * 33):
            with self.assertRaises(CM.CozeMailError):
                CM.run("register", {} if bad is None else {"prefix": bad})
        self.assertIsNone(CM.read_state()["address"])
        self.assertEqual([], _rows(), "拒绝路径不许在通道里留行")

    def test_unwired_backend_reports_needs_dependency_not_fake_success(self):
        _seed(address=None)
        CM.set_transport(None)                    # 默认后端 = 未接线
        out = CM.run("register", {"prefix": "gbt_potato_v8"})
        self.assertFalse(out["ok"])
        self.assertEqual("needs_dependency", out["status"])
        self.assertIsNone(CM.read_state()["address"], "未接线不许把地址当成已就位")
        self.assertEqual([], _rows())


class ChannelFailureTests(_Base):
    """§八 #11 ＋ G6 第 3 组：写不进去就不许发（负对照必须真红）。"""

    def test_channel_write_failure_blocks_egress(self):
        _seed(allow=(GOOD,))
        fake = FakeTransport()
        CM.set_transport(fake)
        self._block_channel()
        main_before = len(_main_rows())

        out = CM.run("send", self._send_payload())
        self.assertFalse(out["ok"])
        self.assertEqual("blocked", out["status"])
        self.assertFalse(out["network_attempted"], "通道写不进去 -> 网络请求必须不发起")
        self.assertEqual([], fake.calls, "通道写不进去 -> 一次上游调用都不许有")
        delta = [r for r in _main_rows()[main_before:] if r["event"] == "health_channel_failed"]
        self.assertEqual(1, len(delta), "故障必须恰好落 1 条主账本 health_channel_failed")
        self.assertEqual("coze_mail", delta[0]["meta"]["channel"])

    def test_channel_writable_positive_control(self):
        _seed(allow=(GOOD,))
        CM.set_transport(FakeTransport())
        main_before = len(_main_rows())
        out = CM.run("send", self._send_payload())
        self.assertTrue(out["ok"], "正对照臂自己坏了")
        self.assertEqual(1, len(_rows()), "通道可写 -> 通道落 1 条")
        self.assertEqual([], [r for r in _main_rows()[main_before:]
                              if r["event"] == "health_channel_failed"],
                         "通道可写 -> 主账本 0 条故障")


class WiringTests(_Base):
    """注册 ≠ 丢文件（R86 教训）：注册表 + 路由派发 + policy 三处必须都在。"""

    def test_registry_entry_and_dispatch_exist(self):
        self.assertIn("coze_mail", BENIGN_CAPS)
        self.assertEqual("coze_mail", BENIGN_CAPS["coze_mail"]["handler"])
        src = (_PKG / "api.py").read_text(encoding="utf-8")
        self.assertEqual(1, src.count('    if kind == "coze_mail":'))

    def test_policy_gates_outbound_for_untrusted_caller(self):
        _seed(allow=(GOOD,))
        fake = FakeTransport()
        CM.set_transport(fake)
        old = os.environ.pop("GBT_OWNER_SESSION", None)
        try:
            out = api.run_task("coze_mail", self._api_send_payload())
            body = (out.get("result") or out.get("gbt_result") or {})
            self.assertFalse(out.get("ok"), "未受信会话不许把邮件发出去：%r" % (out,))
            self.assertEqual("denied", body.get("status"),
                             "data_export 类动作在未受信会话里必须被拒：%r" % (body,))
            self.assertTrue(body.get("denied"))
            self.assertEqual([], fake.calls, "被拒时一次上游调用都不许有")
        finally:
            if old is not None:
                os.environ["GBT_OWNER_SESSION"] = old

    def test_trusted_session_can_dispatch_through_api(self):
        _seed(allow=(GOOD,))
        CM.set_transport(FakeTransport())
        out = api.run_task("coze_mail", self._api_send_payload())
        self.assertTrue(out.get("ok"), "主人会话走 api 派发必须可达：%r" % (out,))
        inner = (out.get("result") or {}).get("result") or {}
        self.assertTrue(inner.get("sent"), "派发到了能力但没真发：%r" % (inner,))

    def test_unknown_op_is_user_error(self):
        with self.assertRaises(CM.CozeMailError):
            CM.run("no_such_op", {})
        out = api.run_task("coze_mail", {"op": "no_such_op"})
        body = out.get("result") or {}
        self.assertFalse(out.get("ok"))
        self.assertEqual("user_error", body.get("error_class"), "%r" % (body,))


class ParamCapTests(_Base):
    """§四 参数硬约束：超上限**拒绝**，不许静默截断。"""

    def test_limit_over_max_is_rejected_not_truncated(self):
        _seed()
        CM.set_transport(FakeTransport())
        with self.assertRaises(CM.CozeMailError) as ctx:
            CM.run("inbox", {"limit": CM.LIMIT_MAX + 1})
        self.assertIn("超上限", str(ctx.exception))
        out = CM.run("inbox", {"limit": CM.LIMIT_MAX})
        self.assertTrue(out["ok"])
        self.assertEqual(CM.LIMIT_MAX, out["limit"])

    def test_body_over_max_is_rejected(self):
        _seed(allow=(GOOD,))
        fake = FakeTransport()
        CM.set_transport(fake)
        payload = self._send_payload(body="x" * (CM.BODY_MAX + 1))
        with self.assertRaises(CM.CozeMailError) as ctx:
            CM.run("send", payload)
        self.assertIn("超上限", str(ctx.exception))
        self.assertEqual([], fake.calls)

    def test_daily_limit_is_rejected_not_queued(self):
        _seed(allow=(GOOD,))
        fake = FakeTransport()
        CM.set_transport(fake)
        for _ in range(CM.DAILY_SEND_LIMIT):
            self.assertTrue(CM.run("send", self._send_payload())["ok"])
        with self.assertRaises(CM.CozeMailError) as ctx:
            CM.run("send", self._send_payload())
        self.assertIn("日限", str(ctx.exception))
        self.assertEqual(CM.DAILY_SEND_LIMIT, len(fake.calls), "超日限不许再打上游")


class DraftAndReplyTests(_Base):
    """§三 draft/reply 的闸门：草稿也要过白名单；reply 收件人由原信决定。"""

    def test_draft_is_whitelisted_and_token_round_trips(self):
        _seed(allow=(GOOD,))
        fake = FakeTransport()
        CM.set_transport(fake)
        with self.assertRaises(CM.CozeMailError):
            CM.run("draft", {"to": [STRANGER], "subject": "s", "body": "b"})
        self.assertEqual([], fake.calls, "草稿不过白名单：不发网络、不落草稿")

        d = CM.run("draft", {"to": [GOOD], "subject": "主题", "body": BODY})
        self.assertTrue(d["ok"])
        out = CM.run("send", {"to": GOOD, "subject": "主题", "body": BODY,
                              "confirm_token": d["confirm_token"]})
        self.assertTrue(out["ok"], "draft 铸的令牌必须能过 send 的同一套校验")

    def test_draft_rejects_multiple_recipients(self):
        _seed(allow=(GOOD,))
        CM.set_transport(FakeTransport())
        with self.assertRaises(CM.CozeMailError):
            CM.run("draft", {"to": [GOOD, GOOD], "subject": "s", "body": "b"})

    def test_reply_takes_recipient_from_origin_and_refuses_mailing_list(self):
        _seed(allow=(GOOD,))
        fake = FakeTransport()
        CM.set_transport(fake)
        token = CM.build_confirm_token("m1", BODY)
        out = CM.run("reply", {"msg_id": "m1", "body": BODY, "confirm_token": token,
                               "to": STRANGER})
        self.assertTrue(out["ok"])
        self.assertEqual(GOOD, out["to"], "reply 的收件人必须取自原信，参数给的 to 不许生效")

        fake.origin = {"from": GOOD, "subject": "列表信", "has_list_unsubscribe": True}
        with self.assertRaises(CM.CozeMailError) as ctx:
            CM.run("reply", {"msg_id": "m1", "body": BODY, "confirm_token": token})
        self.assertIn("List-Unsubscribe", str(ctx.exception))

        fake.origin = {"from": "outsider@example.com", "subject": "x",
                       "has_list_unsubscribe": False}
        with self.assertRaises(CM.CozeMailError) as ctx:
            CM.run("reply", {"msg_id": "m1", "body": BODY, "confirm_token": token})
        self.assertIn("白名单", str(ctx.exception), "「回复 A、发给 B」必须被白名单拦下")


class IsolationScanTests(_Base):
    """§八 #5：静态扫描能力代码 —— 出现个人账号凭据即判红。"""

    FORBIDDEN = ("@gmail.", "@qq.com", "@163.com", "@outlook.", "@hotmail.",
                 "@icloud.", "password", "passwd", "personal_account",
                 "api_key=", "apikey=")

    def test_capability_source_has_no_personal_credentials(self):
        src = (_PKG / "coze_mail_cap.py").read_text(encoding="utf-8").lower()
        hits = [w for w in self.FORBIDDEN if w in src]
        self.assertEqual([], hits, "能力源码里出现疑似个人账号凭据：%r" % (hits,))
        self.assertIn("ref:", src, "凭据必须只写 ref: 形式")

    def test_scanner_negative_control(self):
        """判据自己的负对照：喂一段含凭据的文本，扫描器必须报红。"""
        planted = "MAIL_USER = 'someone@gmail.com'\npassword = 'x'"
        hits = [w for w in self.FORBIDDEN if w in planted.lower()]
        self.assertNotEqual([], hits, "SCANNER_BLIND: 扫描器对植入凭据不报红")


if __name__ == "__main__":
    unittest.main(verbosity=2)
