# -*- coding: utf-8 -*-
# gbt-capability: integration
"""通信域 · coze_mail —— 对主人**自有的单一地址**做收发与整理（方案稿 §一–§六）。
边界（逐条可查）：
- **建立身份那一步是人，不是能力**：`register` 只接受主人给的 `prefix`，单值、幂等拒绝。
- **收件人白名单默认空 = 全拒**：不命中直接拒，不排队、不落草稿、**不发网络请求**。
- **confirm_token 绑定具体内容**：`sha256(to|subject|body|时间窗)`；`reply` 为
  `sha256(msg_id|body|时间窗)`。正文改一个字，旧令牌立刻作废（防「确认 A、发出 B」）。
- **正文原文永不入档**：账本只落 `content_sha256` ＋ `chars`。
- **独立通道**：`<STORE_DIR>/health/coze_mail/*.jsonl`，路径一律由 `_paths.STORE_DIR`
  在**调用时**拼（不 import 期绑常量、不硬编码 `store/`）。
- **写不进去就不许发**：出站前先做通道可写预检；预检失败 -> 出站中止，主账本落
  `health_channel_failed`（第二十五章《终端失败必须响》）。
- **凭据只存 `ref:`**：能力侧不持明文、不回传、不落档。
- **与个人账号完全隔离**：只持有本地址的 `ref:`。
**「4 个事件名承载 9 个动作」的映射（如实标，供复核）**：
    register -> coze_mail_address_set   inbox   -> coze_mail_recv（只落件数与未读数）
    send     -> coze_mail_send          search  -> coze_mail_recv（落 query_sha256）
    reply    -> coze_mail_send          read    -> coze_mail_recv（落 content_sha256 + chars）
    mark     -> coze_mail_status_change draft   -> coze_mail_status_change（落 draft_id）
    status   -> coze_mail_status_change（**仅状态变化**才落；STATUS_TTL_S 内连调 0 B）
**后端（transport）是显式接线口**：本模块实现**全部闸门与账**；真正出网/收信由
`set_transport()` 注入的实现完成。默认后端 `_UnwiredTransport` **如实报
`needs_dependency`，不伪造成功**（《反空壳律》）。
"""
from __future__ import annotations

import json
import os
import re
import time
from hashlib import sha256
from pathlib import Path

from . import _paths
from .safe_io import atomic_write_bytes

CHANNEL = "coze_mail"
ADDRESS_SUFFIX = "@coze.email"
EVENTS = ("coze_mail_recv", "coze_mail_send",
          "coze_mail_status_change", "coze_mail_address_set")
LIMIT_DEFAULT = 20
LIMIT_MAX = 200
BODY_MAX = 8000
DAILY_SEND_LIMIT = 20
STATUS_TTL_S = 30.0
TOKEN_WINDOW_S = 900
_PREFIX_RE = re.compile(r"^[a-z0-9_]{3,32}$")
_NOREPLY_RE = re.compile(r"(^|[<\s,\"'])no-?reply@", re.IGNORECASE)


class CozeMailError(ValueError):
    """调用方问题（坏参数 / 越界 / 未过闸门）—— api 归 user_error。"""


class ChannelWriteError(CozeMailError):
    """通道写不进去 —— 出站必须中止（§五 5.1）。"""


class TransportUnavailable(RuntimeError):
    """后端未接线 / 上游不可达 —— 如实报，不伪造成功。"""


_STATUS_CACHE: dict = {}
_LAST_STATUS_STATE: dict = {}
_TRANSPORT = None


class _UnwiredTransport:
    """默认后端：本仓尚无 Coze 官方邮件接口的 `ref:` 凭据与端点。"""
    reason = "backend_not_wired: Coze 官方邮件接口未接线（无 ref: 凭据 / 无端点）"

    def _refuse(self, *a, **k):
        raise TransportUnavailable(self.reason)

    status = _refuse
    inbox = _refuse
    read = _refuse
    mark = _refuse
    send = _refuse
    register_address = _refuse
    get_message = _refuse


def set_transport(transport) -> None:
    """接线口（测试 / 将来设置页）。传 None 还原默认「未接线」后端。"""
    global _TRANSPORT
    _TRANSPORT = transport


def get_transport():
    return _TRANSPORT if _TRANSPORT is not None else _UnwiredTransport()


def channel_dir() -> Path:
    """通道目录 —— **调用时**由 `_paths.STORE_DIR` 拼（不 import 期绑定）。"""
    return Path(_paths.STORE_DIR) / "health" / CHANNEL


def events_path() -> Path:
    return channel_dir() / "events.jsonl"


def state_path() -> Path:
    return channel_dir() / "state.json"


def read_state() -> dict:
    """读状态（address / allow_to / enabled）。缺文件 / 坏 JSON = 默认值，不猜。"""
    p = state_path()
    data = {"address": None, "allow_to": [], "enabled": True}
    try:
        raw = json.loads(p.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return data
    if isinstance(raw, dict):
        data["address"] = raw.get("address") or None
        allow = raw.get("allow_to")
        data["allow_to"] = [str(x).strip().lower() for x in allow] if isinstance(allow, list) else []
        data["enabled"] = bool(raw.get("enabled", True))
    return data


def write_state(state: dict) -> Path:
    """写状态（设置页 / register 共用同一口）。"""
    _paths.verify_store_binding()
    blob = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return atomic_write_bytes(state_path(), blob)


def _open_events():
    """通道追加句柄 —— 预检与写入走**同一个**开法，两者不许分叉。"""
    _paths.verify_store_binding()
    d = channel_dir()
    d.mkdir(parents=True, exist_ok=True)
    return open(events_path(), "a", encoding="utf-8", newline="\n")


def _log_event(event: str, meta: dict) -> None:
    """落一条通道账（写入 + fsync 后才返回）—— 失败抛 ChannelWriteError。

    **本函数不做「要不要发」的判断**；出站动作一律先 `_preflight_channel()` 探可写。
    """
    if event not in EVENTS:
        raise CozeMailError("未知事件名：%s（只允许 %s）" % (event, "/".join(EVENTS)))
    rec = {"ts": round(time.time(), 3),
           "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "event": event,
           "meta": meta}
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    try:
        with _open_events() as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        raise ChannelWriteError("通道写失败：%s: %s" % (type(exc).__name__, exc)) from exc


def _preflight_channel() -> None:
    """出站前的通道可写预检（「写不进去就不许发」，§五 5.1）。

    只开、不写 —— 不产生任何行。与 `_log_event` 用**同一个** `_open_events()`，
    所以「预检说能写」与「真能写」不会分叉。
    """
    try:
        with _open_events():
            pass
    except OSError as exc:
        raise ChannelWriteError("通道不可写：%s: %s" % (type(exc).__name__, exc)) from exc


def _channel_fail(action: str, reason: str, detail: str) -> None:
    """故障走**主账本**（正常事件不混、故障仍然混 —— §五 5.1）。"""
    try:
        from .store import audit
        audit("health_channel_failed", {"channel": CHANNEL, "action": action,
                                        "reason": reason, "detail": str(detail)[:200]})
    except Exception:  # noqa: BLE001 - 主账本也写不进去时，不许把出站动作放过去
        pass


def _read_rows() -> list:
    p = events_path()
    if not p.is_file():
        return []
    rows = []
    for raw in p.read_bytes().split(b"\n"):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw.decode("utf-8")))
        except ValueError:
            continue
    return rows


def _sends_today() -> int:
    day = time.strftime("%Y-%m-%d")
    n = 0
    for rec in _read_rows():
        meta = rec.get("meta") or {}
        if rec.get("event") == "coze_mail_send" and meta.get("result") == "ok":
            if str(rec.get("iso") or "").startswith(day):
                n += 1
    return n


def _token_for_bucket(bucket: int, parts) -> str:
    body = "|".join(str(x) for x in parts) + "|" + str(bucket)
    return sha256(body.encode("utf-8")).hexdigest()


def build_confirm_token(*parts) -> str:
    """公开口：调用方（面板 / 设置页）按同一公式铸令牌，能力侧只校验。"""
    return _token_for_bucket(int(time.time() // TOKEN_WINDOW_S), parts)


def _token_ok(token: str, parts) -> bool:
    if not token:
        return False
    now = int(time.time() // TOKEN_WINDOW_S)
    return str(token) in (_token_for_bucket(now, parts), _token_for_bucket(now - 1, parts))


def _norm_addr(value) -> str:
    return str(value or "").strip().lower()


def _one_recipient(payload) -> str:
    to = payload.get("to")
    if isinstance(to, (list, tuple)):
        if len(to) != 1:
            raise CozeMailError("只允许单一收件人（白名单是一个名单，不是群发口）")
        to = to[0]
    to = _norm_addr(to)
    if not to:
        raise CozeMailError("缺少 to：收件人必须给")
    if "@" not in to:
        raise CozeMailError("to 不是合法地址：%s" % to)
    return to


def _check_recipient(addr: str, allow) -> None:
    if not allow:
        raise CozeMailError("收件人白名单为空（默认全拒）—— 先在设置页加白名单")
    if addr not in allow:
        raise CozeMailError("收件人不在白名单：%s（白名单 %d 项）" % (addr, len(allow)))
    if _NOREPLY_RE.search(addr):
        raise CozeMailError("拒发：noreply / no-reply 类地址一律不发")


def _check_body(body) -> str:
    text = "" if body is None else str(body)
    if len(text) > BODY_MAX:
        raise CozeMailError("正文超上限：%d > %d 字符（拒绝而不是截断）" % (len(text), BODY_MAX))
    return text


def _check_limit(limit) -> int:
    if limit is None:
        return LIMIT_DEFAULT
    try:
        n = int(limit)
    except (TypeError, ValueError):
        raise CozeMailError("limit 必须是整数：%r" % (limit,))
    if n < 1:
        raise CozeMailError("limit 必须 >= 1：%r" % (limit,))
    if n > LIMIT_MAX:
        raise CozeMailError("limit 超上限：%d > %d（拒绝而不是静默截断）" % (n, LIMIT_MAX))
    return n


def _require_enabled(state: dict) -> None:
    if not state.get("enabled", True):
        raise CozeMailError("mail.enabled = false：总开关关掉即全部动作拒绝")


def _down(action: str, exc: Exception) -> dict:
    return {"ok": False, "status": "needs_dependency", "action": action,
            "channel": CHANNEL, "reason": "transport_unavailable",
            "detail": str(exc)[:200],
            "note": "后端未接线 / 上游不可达 —— 如实报，不伪造成功"}


def _op_status(payload: dict) -> dict:
    state = read_state()
    _require_enabled(state)
    now = time.time()
    cached = _STATUS_CACHE.get("at")
    if cached is not None and (now - float(cached)) < STATUS_TTL_S:
        return dict(_STATUS_CACHE["payload"], cached=True)
    base = {"ok": True, "channel": CHANNEL, "address": state.get("address"),
            "quota_limit": DAILY_SEND_LIMIT, "quota_used_today": _sends_today(),
            "ttl_s": STATUS_TTL_S}
    try:
        upstream = dict(get_transport().status(address=state.get("address")) or {})
    except TransportUnavailable as exc:
        base.update({"ok": False, "connected": False, "unread": None,
                     "last_sync_at": None, "last_error": "transport_unavailable",
                     "status": "needs_dependency", "detail": str(exc)[:200]})
        _note_status_change(False, "transport_unavailable")
        _STATUS_CACHE.update({"at": now, "payload": dict(base)})
        return dict(base, cached=False)
    except Exception as exc:  # noqa: BLE001 - 上游异常也算未连通，但如实暴露
        base.update({"ok": False, "connected": False, "unread": None,
                     "last_sync_at": None, "last_error": "upstream_error",
                     "status": "error", "detail": "%s: %s" % (type(exc).__name__, exc)})
        _note_status_change(False, "upstream_error")
        _STATUS_CACHE.update({"at": now, "payload": dict(base)})
        return dict(base, cached=False)
    connected = bool(upstream.get("connected", True))
    base.update({"connected": connected, "unread": upstream.get("unread"),
                 "last_sync_at": upstream.get("last_sync_at"),
                 "last_error": upstream.get("last_error") or None})
    _note_status_change(connected, None)
    _STATUS_CACHE.update({"at": now, "payload": dict(base)})
    return dict(base, cached=False)


def _note_status_change(connected: bool, reason) -> None:
    """**仅状态变化**才落 coze_mail_status_change（TTL 内连调 0 B）。"""
    if _LAST_STATUS_STATE.get("connected") == connected:
        return
    _LAST_STATUS_STATE["connected"] = connected
    meta = {"op": "status", "connected": connected}
    if reason:
        meta["reason"] = reason
    try:
        _log_event("coze_mail_status_change", meta)
    except ChannelWriteError as exc:
        _channel_fail("status", "channel_write_failed", str(exc))


def _op_inbox(payload: dict) -> dict:
    state = read_state()
    _require_enabled(state)
    limit = _check_limit(payload.get("limit"))
    folder = str(payload.get("folder") or "INBOX")
    try:
        out = dict(get_transport().inbox(folder=folder, limit=limit,
                                         since=payload.get("since"),
                                         unread_only=bool(payload.get("unread_only"))) or {})
    except TransportUnavailable as exc:
        return _down("inbox", exc)
    msgs = list(out.get("messages") or [])
    unread = int(out.get("unread") or sum(1 for m in msgs if m.get("unread")))
    try:
        _log_event("coze_mail_recv", {"op": "inbox", "folder": folder,
                                      "count": len(msgs), "unread": unread})
    except ChannelWriteError as exc:
        _channel_fail("inbox", "channel_write_failed", str(exc))
    return {"ok": True, "channel": CHANNEL, "folder": folder, "limit": limit,
            "messages": msgs, "count": len(msgs), "unread": unread,
            "next_cursor": out.get("next_cursor"), "has_more": bool(out.get("has_more"))}


def _op_search(payload: dict) -> dict:
    state = read_state()
    _require_enabled(state)
    query = str(payload.get("query") or "").strip()
    if not query:
        raise CozeMailError("缺少 query：搜索必须给关键词")
    limit = _check_limit(payload.get("limit"))
    folder = str(payload.get("folder") or "INBOX")
    try:
        out = dict(get_transport().inbox(folder=folder, limit=limit, query=query) or {})
    except TransportUnavailable as exc:
        return _down("search", exc)
    msgs = list(out.get("messages") or [])
    q_sha = sha256(query.encode("utf-8")).hexdigest()
    try:
        _log_event("coze_mail_recv", {"op": "search", "folder": folder,
                                      "query_sha256": q_sha, "count": len(msgs)})
    except ChannelWriteError as exc:
        _channel_fail("search", "channel_write_failed", str(exc))
    return {"ok": True, "channel": CHANNEL, "folder": folder, "limit": limit,
            "query_sha256": q_sha, "messages": msgs, "count": len(msgs),
            "next_cursor": out.get("next_cursor"), "has_more": bool(out.get("has_more"))}


def _op_read(payload: dict) -> dict:
    state = read_state()
    _require_enabled(state)
    msg_id = str(payload.get("msg_id") or "").strip()
    if not msg_id:
        raise CozeMailError("缺少 msg_id")
    try:
        out = dict(get_transport().read(msg_id=msg_id,
                                        max_chars=payload.get("max_chars")) or {})
    except TransportUnavailable as exc:
        return _down("read", exc)
    body = out.get("body")
    body_kind = str(out.get("body_kind") or "text")
    if body_kind == "html_only":
        text = None
        result = {"body_kind": "html_only", "body": None}
    else:
        text = "" if body is None else str(body)
        if payload.get("max_chars"):
            text = text[:int(payload["max_chars"])]
        result = {"body_kind": "text", "body": text}
    try:
        _log_event("coze_mail_recv", {
            "op": "read", "msg_id": msg_id, "chars": len(text or ""),
            "content_sha256": sha256((text or "").encode("utf-8")).hexdigest()})
    except ChannelWriteError as exc:
        _channel_fail("read", "channel_write_failed", str(exc))
    return dict({"ok": True, "channel": CHANNEL, "msg_id": msg_id}, **result)


def _op_draft(payload: dict) -> dict:
    state = read_state()
    _require_enabled(state)
    to = _one_recipient(payload)
    _check_recipient(to, state.get("allow_to") or [])
    subject = str(payload.get("subject") or "")
    body = _check_body(payload.get("body"))
    seed = "|".join([to, subject, body, str(payload.get("in_reply_to") or "")])
    draft_id = sha256(seed.encode("utf-8")).hexdigest()[:24]
    try:
        _log_event("coze_mail_status_change",
                   {"op": "draft", "draft_id": draft_id, "chars": len(body)})
    except ChannelWriteError as exc:
        _channel_fail("draft", "channel_write_failed", str(exc))
    return {"ok": True, "channel": CHANNEL, "draft_id": draft_id, "to": to,
            "subject": subject, "chars": len(body),
            "confirm_token": build_confirm_token(to, subject, body)}


def _deliver(action: str, to: str, subject: str, body: str,
             token_parts, extra: dict) -> dict:
    """出站唯一收口：闸门已过的内容只走这里。

    顺序钉死：**① 通道可写预检 -> ② 发 -> ③ 通道落 1 条结果账**。
    预检失败 = 出站中止、不发网络请求、主账本落 1 条 health_channel_failed。
    （「没有这条账，就不许发」——预检与真写走同一个 `_open_events()`，两者不分叉。）
    """
    try:
        _preflight_channel()
    except ChannelWriteError as exc:
        _channel_fail(action, "channel_write_failed", str(exc))
        return {"ok": False, "status": "blocked", "action": action, "channel": CHANNEL,
                "reason": "channel_write_failed", "sent": False,
                "network_attempted": False,
                "detail": "通道写不进去 -> 出站中止，不发网络请求"}
    try:
        out = dict(get_transport().send(sender=read_state().get("address"), to=to,
                                        subject=subject, body=body, **extra) or {})
        ok, detail = True, ""
    except TransportUnavailable as exc:
        out, ok, detail = {}, False, str(exc)[:200]
    except Exception as exc:  # noqa: BLE001 - 上游异常如实报，不许伪成功
        out, ok, detail = {}, False, "%s: %s" % (type(exc).__name__, exc)
    meta = {"op": action, "to": to,
            "to_sha256": sha256(to.encode("utf-8")).hexdigest(),
            "subject_sha256": sha256(subject.encode("utf-8")).hexdigest(),
            "content_sha256": sha256(body.encode("utf-8")).hexdigest(),
            "chars": len(body), "result": "ok" if ok else "failed"}
    meta.update(extra.get("meta") or {})
    try:
        _log_event("coze_mail_send", meta)
    except ChannelWriteError as exc:
        # 预检过了、出站已发生 —— 如实记故障，不伪造成「今天没发过」
        _channel_fail(action, "channel_write_failed_after_send", str(exc))
    if not ok:
        return {"ok": False, "status": "needs_dependency" if not out else "error",
                "action": action, "channel": CHANNEL, "to": to, "sent": False,
                "network_attempted": True, "reason": detail}
    return {"ok": True, "channel": CHANNEL, "action": action, "to": to, "sent": True,
            "network_attempted": True, "result_id": out.get("result_id"),
            "accepted_at": out.get("accepted_at")}


def _op_send(payload: dict) -> dict:
    state = read_state()
    _require_enabled(state)
    if not state.get("address"):
        raise CozeMailError("地址未就位：先 register(prefix=主人给的前缀)")
    sent = _sends_today()
    if sent >= DAILY_SEND_LIMIT:
        raise CozeMailError("超日限：今天已发 %d 封（上限 %d）——拒绝而不是排队"
                            % (sent, DAILY_SEND_LIMIT))
    to = _one_recipient(payload)
    _check_recipient(to, state.get("allow_to") or [])
    subject = str(payload.get("subject") or "")
    body = _check_body(payload.get("body"))
    parts = (to, subject, body)
    token = str(payload.get("confirm_token") or "")
    if not _token_ok(token, parts):
        raise CozeMailError("confirm_token 不匹配（收件人/主题/正文改过一个字即失效）")
    return _deliver("send", to, subject, body, parts,
                    {"confirm_token": token, "meta": {}})


def _op_reply(payload: dict) -> dict:
    state = read_state()
    _require_enabled(state)
    if not state.get("address"):
        raise CozeMailError("地址未就位：先 register(prefix=主人给的前缀)")
    sent = _sends_today()
    if sent >= DAILY_SEND_LIMIT:
        raise CozeMailError("超日限：今天已发 %d 封（上限 %d）" % (sent, DAILY_SEND_LIMIT))
    msg_id = str(payload.get("msg_id") or "").strip()
    if not msg_id:
        raise CozeMailError("缺少 msg_id：reply 的收件人由原信决定，不由参数给")
    body = _check_body(payload.get("body"))
    parts = (msg_id, body)
    token = str(payload.get("confirm_token") or "")
    if not _token_ok(token, parts):
        raise CozeMailError("confirm_token 不匹配（msg_id|body 改一个字即失效）")
    try:
        origin = dict(get_transport().get_message(msg_id=msg_id) or {})
    except TransportUnavailable as exc:
        return _down("reply", exc)
    if origin.get("has_list_unsubscribe"):
        raise CozeMailError("拒发：原信带 List-Unsubscribe（邮件列表），不自动回复")
    to = _norm_addr(origin.get("reply_to") or origin.get("from"))
    if not to:
        raise CozeMailError("原信既无 Reply-To 也无 From —— 收件人无法确定，不发")
    _check_recipient(to, state.get("allow_to") or [])
    subject = str(origin.get("subject") or "")
    if not subject.lower().startswith("re:"):
        subject = ("Re: " + subject) if subject else "Re:"
    return _deliver("reply", to, subject, body, parts,
                    {"confirm_token": token, "in_reply_to": msg_id,
                     "meta": {"msg_id": msg_id}})


def _op_mark(payload: dict) -> dict:
    state = read_state()
    _require_enabled(state)
    msg_id = str(payload.get("msg_id") or "").strip()
    flag = str(payload.get("flag") or "").strip()
    if not msg_id or not flag:
        raise CozeMailError("mark 需要 msg_id 与 flag")
    try:
        out = dict(get_transport().mark(msg_id=msg_id, flag=flag) or {})
    except TransportUnavailable as exc:
        return _down("mark", exc)
    try:
        _log_event("coze_mail_status_change",
                   {"op": "mark", "msg_id": msg_id, "flag": flag,
                    "result": out.get("result") or "ok"})
    except ChannelWriteError as exc:
        _channel_fail("mark", "channel_write_failed", str(exc))
    return {"ok": True, "channel": CHANNEL, "msg_id": msg_id, "flag": flag}


def _op_register(payload: dict) -> dict:
    state = read_state()
    _require_enabled(state)
    prefix = payload.get("prefix")
    if not isinstance(prefix, str) or not prefix:
        raise CozeMailError("register 必须由主人给 prefix —— 能力不自拟、不兜底、不生成")
    if state.get("address"):
        raise CozeMailError(
            "地址已就位（%s）：register 幂等拒绝 —— 不覆盖、不改写（防「以为在补登记，"
            "实际在换号」）" % state.get("address"))
    if not _PREFIX_RE.match(prefix):
        raise CozeMailError("prefix 形态不合规：只允许小写字母/数字/下划线，长度 3–32")
    try:
        out = dict(get_transport().register_address(prefix=prefix) or {})
    except TransportUnavailable as exc:
        return _down("register", exc)
    address = _norm_addr(out.get("address") or (prefix + ADDRESS_SUFFIX))
    if not address.endswith(ADDRESS_SUFFIX):
        raise CozeMailError("注册返回的地址不属于 %s —— 只走 Coze 官方，不接第三方"
                            % ADDRESS_SUFFIX)
    new_state = dict(state)
    new_state["address"] = address
    write_state(new_state)
    try:
        _log_event("coze_mail_address_set",
                   {"op": "register", "address": address,
                    "prefix_sha256": sha256(prefix.encode("utf-8")).hexdigest()})
    except ChannelWriteError as exc:
        _channel_fail("register", "channel_write_failed", str(exc))
    return {"ok": True, "channel": CHANNEL, "address": address}


_OPS = {
    "status": _op_status,
    "inbox": _op_inbox,
    "search": _op_search,
    "read": _op_read,
    "draft": _op_draft,
    "send": _op_send,
    "reply": _op_reply,
    "mark": _op_mark,
    "register": _op_register,
}


def run(op, payload=None) -> dict:
    """动作分派（9 条，见模块头映射表）。坏 op / 坏参数 -> CozeMailError（user_error）。"""
    key = str(op or "").strip().lower()
    fn = _OPS.get(key)
    if fn is None:
        raise CozeMailError("未知 op：%r（可用：%s）" % (op, " / ".join(sorted(_OPS))))
    return fn(dict(payload or {}))
