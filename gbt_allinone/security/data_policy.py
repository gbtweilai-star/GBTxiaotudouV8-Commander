# gbt-capability: network
"""外部数据交换策略：分类、最小发送与凭证脱敏。

本模块不禁止外部 LLM。可信主人会话仍可发送所需内容；所有路径在发送前统一遮蔽
高置信度凭证，并返回可审计的分类结果，避免密钥、令牌和私钥进入外部请求。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import policy

_SENSITIVE_KEYS = {
    "authorization", "proxy-authorization", "cookie", "set-cookie",
    "password", "passwd", "secret", "client_secret", "private_key",
    "api_key", "apikey", "access_token", "refresh_token", "id_token",
    "credential", "credentials",
}

_CONTENT_KEYS = {
    "prompt", "reply", "response", "content", "messages", "input",
    "history", "conversation", "system_prompt", "developer_instructions",
    "base_instructions",
}

_MAX_AUDIT_STRING = 1200
_MAX_AUDIT_ITEMS = 200
_MAX_AUDIT_DEPTH = 8

_SECRET_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.S)),
    ("bearer", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/\-=]{12,}")),
    ("api_key", re.compile(r"\b(?:sk|ak|pk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9._\-]{12,}\b")),
    ("assigned_secret", re.compile(
        r"(?im)\b(api[_-]?key|secret|password|passwd|token|access[_-]?key|private[_-]?key)"
        r"\s*[:=]\s*['\"]?([^'\"\s,;]{8,})")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("phone_cn", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
)


@dataclass
class ExternalPayload:
    text: str
    classification: str
    redactions: dict = field(default_factory=dict)
    allowed: bool = True
    reason: str = ""


def classify(meta: dict | None = None) -> str:
    meta = meta or {}
    value = str(meta.get("data_class") or meta.get("classification") or "internal").lower()
    return value if value in ("public", "internal", "private", "secret") else "internal"


def redact_text(text: str) -> tuple[str, dict]:
    value = str(text or "")
    counts = {}
    for name, pattern in _SECRET_PATTERNS:
        if name == "assigned_secret":
            def repl(match: re.Match) -> str:
                return f"{match.group(1)}=<redacted:{name}>"
        else:
            def repl(match: re.Match) -> str:
                return f"<redacted:{name}>"
        value, count = pattern.subn(repl, value)
        if count:
            counts[name] = count
    return value, counts


def _key_token(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(key or "").lower())


def _is_sensitive_key(key: str) -> bool:
    token = _key_token(key)
    if not token or token.endswith(("env", "envs", "name", "names", "count")):
        return False
    if token in _SENSITIVE_KEYS:
        return True
    return any(token.endswith(suffix) for suffix in (
        "apikey", "authorization", "cookie", "password", "passwd",
        "privatekey", "accesstoken", "refreshtoken", "idtoken",
        "clientsecret", "credential", "credentials",
    ))


def _is_content_key(key: str) -> bool:
    token = _key_token(key)
    return token in {_key_token(item) for item in _CONTENT_KEYS}


def _redacted_string(value: str) -> str:
    text, _counts = redact_text(str(value))
    if len(text) > _MAX_AUDIT_STRING:
        return text[:_MAX_AUDIT_STRING] + "<truncated>"
    return text


def _content_descriptor(value) -> dict:
    """Conversation-like values become fingerprints, never full audit copies."""
    import hashlib
    import json

    if isinstance(value, str):
        body = value.encode("utf-8", errors="replace")
        chars = len(value)
        item_count = 1
    else:
        try:
            body = json.dumps(value, ensure_ascii=False, sort_keys=True,
                              default=str).encode("utf-8", errors="replace")
            item_count = len(value) if isinstance(value, (list, tuple, dict)) else 1
        except Exception:
            body = repr(value).encode("utf-8", errors="replace")
            item_count = 1
        chars = len(body.decode("utf-8", errors="replace"))
    return {
        "redacted": "conversation_content",
        "chars": chars,
        "items": item_count,
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def sanitize_for_audit(value, *, key: str = "", _depth: int = 0,
                       _seen: set[int] | None = None):
    """Return a JSON-safe copy suitable for audit logs without mutating input.

    Credentials are masked, conversation-like values are replaced with
    fingerprints, and long free text is redacted/truncated. The function is
    intentionally conservative: it never deletes a field, only changes its
    stored representation.
    """
    if _is_sensitive_key(key):
        return "<redacted:sensitive_key>"
    if _is_content_key(key):
        return _content_descriptor(value)
    if _depth >= _MAX_AUDIT_DEPTH:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redacted_string(value)
    if isinstance(value, bytes):
        import hashlib

        return {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}

    if _seen is None:
        _seen = set()
    obj_id = id(value)
    if obj_id in _seen:
        return "<circular>"

    if isinstance(value, dict):
        _seen.add(obj_id)
        try:
            items = list(value.items())
            result = {
                str(k): sanitize_for_audit(v, key=str(k), _depth=_depth + 1,
                                           _seen=_seen)
                for k, v in items[:_MAX_AUDIT_ITEMS]
            }
            if len(items) > _MAX_AUDIT_ITEMS:
                result["_truncated_keys"] = len(items) - _MAX_AUDIT_ITEMS
            return result
        finally:
            _seen.discard(obj_id)
    if isinstance(value, (list, tuple, set, frozenset)):
        _seen.add(obj_id)
        try:
            items = list(value)
            result = [
                sanitize_for_audit(item, _depth=_depth + 1, _seen=_seen)
                for item in items[:_MAX_AUDIT_ITEMS]
            ]
            if len(items) > _MAX_AUDIT_ITEMS:
                result.append({"truncated_items": len(items) - _MAX_AUDIT_ITEMS})
            return result
        finally:
            _seen.discard(obj_id)
    return _redacted_string(str(value))


def prepare_external(text: str, meta: dict | None = None) -> ExternalPayload:
    """返回可发送文本。private/secret 数据需要显式 external 同意或主人会话。"""
    meta = meta or {}
    classification = classify(meta)
    allow_private = bool(meta.get("external_consent") or meta.get("allow_external"))
    if classification in ("private", "secret") and not (allow_private or policy.is_trusted()):
        return ExternalPayload(
            text="", classification=classification, allowed=False,
            reason="private/secret 数据发送到外部前需要 external_consent=true 或主人会话",
        )
    redacted, counts = redact_text(text)
    return ExternalPayload(text=redacted, classification=classification,
                           redactions=counts, allowed=True)


def _bad_input(value, action: str) -> dict:
    """R-H295 · ⑥ G1/G2：分析器**做不了**时的结构化上报（门组）。

    《触手覆盖矩阵.md》§三：门组 4 个只有 3 个能报"做不了"，本文件是缺的那个。
    本模块是**纯函数分析器**（没有 ok/error 形状）——对非文本输入，
    原来会一路算下去（`len(payload.text)` 之类）得出没有意义的结论。
    分析器给不出结论时必须说"给不出"，而不是给一个错的。
    """
    _why = ("需要文本输入，收到 %s —— 分析器不猜类型，给不出结论就说给不出"
            % type(value).__name__)
    return {
        "ok": False,
        "unavailable": True,
        "denied": False,
        "rule": "data_policy_bad_input",
        "action": str(action),
        "missing": ["text"],
        "why": _why,
        "error": _why,   # 向后兼容：老调用方读 error（新形状加字段，不换字段）
    }


def status(text: str, meta: dict | None = None) -> dict:
    # R-H295：非文本输入不给"看起来像结论"的东西（见 _bad_input）
    if not isinstance(text, str):
        return _bad_input(text, "data_policy.status")
    payload = prepare_external(text, meta)
    return {
        "ok": True,
        "allowed": payload.allowed,
        "classification": payload.classification,
        "redactions": payload.redactions,
        "reason": payload.reason,
        "text_chars": len(payload.text),
    }
