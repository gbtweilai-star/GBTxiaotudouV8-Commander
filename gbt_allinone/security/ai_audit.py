"""Application-level AI egress audit.

This module is deliberately not a proxy, packet capture service, or transport
hook. Callers invoke it at the exact application-layer point where GBT sends
an AI request. It stores metadata only, never full prompts/replies, and never
mutates the request or response objects.

Storage policy:
- endpoint must be explicitly allowlisted for the calling provider;
- records are encrypted with Windows DPAPI on Windows;
- on non-Windows, Fernet is used when ``GBT_AI_AUDIT_KEY`` is configured;
- if no safe storage backend is available, the audit write is skipped while
  the original AI call continues unchanged;
- audit failures never block, retry, modify, or delay the AI call.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import logging
import os
import secrets
import threading
import time
import urllib.parse
from pathlib import Path

from .. import _paths
from ..safe_io import locked_append_text
from .data_policy import redact_text, sanitize_for_audit

logger = logging.getLogger("gbt.ai_audit")

_DEFAULT_AI_HOSTS = {
    "openai.com": {"api.openai.com"},
    "deepseek.com": {"api.deepseek.com"},
    "moonshot.cn": {"api.moonshot.cn"},
    "bigmodel.cn": {"open.bigmodel.cn"},
    "anthropic.com": {"api.anthropic.com"},
    "googleapis.com": {"generativelanguage.googleapis.com"},
    "abliteration.ai": {"api.abliteration.ai"},
}
_KNOWN_HOSTS = frozenset(
    host for hosts in _DEFAULT_AI_HOSTS.values() for host in hosts
)
_LOCK = threading.Lock()
_MAX_QUERY = 500
_DPAPI_ENTROPY = b"GBTxiaotudouV8:ai-audit:v1"


def _env_true(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def enabled() -> bool:
    return _env_true("GBT_AI_AUDIT", True) and not _env_true(
        "GBT_AI_AUDIT_DISABLED", False
    )


def _audit_dir() -> Path:
    return Path(_paths.STORE_DIR) / "ai_audit"


def _audit_file() -> Path:
    return _audit_dir() / "events.jsonl"


def _normalize_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    aliases = {
        "moonshot": "kimi",
        "glm": "zhipu",
        "google": "gemini",
        "google-gemini": "gemini",
        "abliterated": "abliteration",
        "panel": "config",
        "digital-human": "config",
    }
    return aliases.get(value, value)


def _host_from_url(url: str) -> tuple[str, str, str]:
    parsed = urllib.parse.urlsplit(str(url or ""))
    if parsed.scheme.lower() not in ("http", "https"):
        return "", "", ""
    return (
        (parsed.hostname or "").lower().rstrip("."),
        parsed.scheme.lower(),
        parsed.path or "/",
    )


def _extra_hosts() -> set[str]:
    raw = os.environ.get("GBT_AI_AUDIT_HOSTS", "")
    hosts = set()
    for item in raw.replace(";", ",").split(","):
        value = item.strip().lower()
        if not value:
            continue
        if "://" in value:
            value = _host_from_url(value)[0]
        else:
            value = value.split(":", 1)[0]
        if value:
            hosts.add(value.rstrip("."))
    return hosts


def _is_local_host(host: str) -> bool:
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        import ipaddress

        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_allowed_endpoint(provider: str, url: str) -> bool:
    """Return whether this exact application-layer endpoint may be audited.

    The caller is already a known GBT AI call site; this check prevents an
    accidental future call from turning the audit layer into a generic network
    recorder.
    """
    provider = _normalize_provider(provider)
    host, scheme, _path = _host_from_url(url)
    if not provider or not host:
        return False
    if host in _KNOWN_HOSTS or host in _extra_hosts():
        return scheme == "https" or (
            scheme == "http" and (_is_local_host(host) or _env_true(
                "GBT_AI_AUDIT_ALLOW_HTTP", False
            ))
        )
    if _is_local_host(host):
        return _env_true("GBT_AI_AUDIT_ALLOW_LOCAL", True)
    return False


def _header_names(headers: dict | None) -> list[str]:
    return sorted({str(k).strip().lower() for k in (headers or {}) if str(k).strip()})


def _content_metadata(body) -> dict:
    """Describe a request structure without retaining prompt/reply content."""
    if not isinstance(body, dict):
        return {"kind": type(body).__name__}
    messages = body.get("messages")
    contents = body.get("contents")
    system = body.get("system")
    roles = []
    chars = 0
    message_count = 0
    if isinstance(messages, list):
        message_count = len(messages)
        for item in messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "")
            if role:
                roles.append(role)
            value = item.get("content")
            if isinstance(value, str):
                chars += len(value)
            elif value is not None:
                chars += len(json.dumps(value, ensure_ascii=False, default=str))
    elif isinstance(contents, list):
        message_count = len(contents)
        for item in contents:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "")
            if role:
                roles.append(role)
            parts = item.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        chars += len(part["text"])
    system_chars = len(system) if isinstance(system, str) else 0
    return {
        "kind": "messages" if isinstance(messages, list) else (
            "contents" if isinstance(contents, list) else "object"
        ),
        "message_count": message_count,
        "roles": roles[:24],
        "content_chars": chars,
        "system_chars": system_chars,
        "stream": bool(body.get("stream")),
        "body_keys": sorted(str(k) for k in body.keys())[:64],
    }


def _usage_metadata(response) -> dict:
    if not isinstance(response, dict):
        return {}
    usage = response.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    return {
        key: value
        for key, value in {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        }.items()
        if isinstance(value, (int, float))
    }


def _response_metadata(response=None, response_text: str | None = None) -> dict:
    if response_text is not None:
        text = str(response_text)
        metadata = _response_metadata(response) if isinstance(response, dict) else {}
        metadata.update({
            "content_chars": len(text),
            "content_sha256": hashlib.sha256(
                text.encode("utf-8", errors="replace")
            ).hexdigest(),
        })
        return metadata
    if not isinstance(response, dict):
        return {}
    choices = response.get("choices")
    content = ""
    finish_reason = ""
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        finish_reason = str(first.get("finish_reason") or "")
        message = first.get("message")
        if isinstance(message, dict):
            content = str(message.get("content") or "")
    candidates = response.get("candidates")
    if not content and isinstance(candidates, list) and candidates:
        first = candidates[0] if isinstance(candidates[0], dict) else {}
        finish_reason = str(first.get("finishReason") or finish_reason)
        parts = ((first.get("content") or {}).get("parts")
                 if isinstance(first.get("content"), dict) else None)
        if isinstance(parts, list):
            content = "".join(
                str(part.get("text") or "") for part in parts
                if isinstance(part, dict)
            )
    return {
        "content_chars": len(content),
        "content_sha256": hashlib.sha256(
            content.encode("utf-8", errors="replace")
        ).hexdigest() if content else None,
        "finish_reason": finish_reason,
        "model": str(response.get("model") or "")[:160],
        "usage": _usage_metadata(response),
    }


def _protect_dpapi(data: bytes) -> bytes | None:
    if os.name != "nt":
        return None
    try:
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte)),
            ]

        def blob(raw: bytes):
            buf = ctypes.create_string_buffer(raw, len(raw))
            return (
                DataBlob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))),
                buf,
            )

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(DataBlob), wintypes.LPCWSTR,
            ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(DataBlob),
        ]
        crypt32.CryptProtectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        input_blob, input_buf = blob(data)
        entropy_blob, entropy_buf = blob(_DPAPI_ENTROPY)
        output = DataBlob()
        ok = crypt32.CryptProtectData(
            ctypes.byref(input_blob), "GBT小土豆V8 AI audit",
            ctypes.byref(entropy_blob), None, None, 0x1,
            ctypes.byref(output),
        )
        _keepalive = (input_buf, entropy_buf)
        if not ok:
            return None
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
    except Exception:
        logger.debug("DPAPI protect unavailable", exc_info=True)
        return None


def _unprotect_dpapi(data: bytes) -> bytes | None:
    if os.name != "nt":
        return None
    try:
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte)),
            ]

        def blob(raw: bytes):
            buf = ctypes.create_string_buffer(raw, len(raw))
            return (
                DataBlob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))),
                buf,
            )

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(DataBlob), ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        input_blob, input_buf = blob(data)
        entropy_blob, entropy_buf = blob(_DPAPI_ENTROPY)
        output = DataBlob()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob), None, ctypes.byref(entropy_blob),
            None, None, 0x1, ctypes.byref(output),
        )
        _keepalive = (input_buf, entropy_buf)
        if not ok:
            return None
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
    except Exception:
        logger.debug("DPAPI unprotect unavailable", exc_info=True)
        return None


def _encrypt_record(data: bytes) -> tuple[str, bytes] | None:
    protected = _protect_dpapi(data)
    if protected is not None:
        return "dpapi", protected
    key = os.environ.get("GBT_AI_AUDIT_KEY", "").strip()
    if key:
        try:
            from cryptography.fernet import Fernet

            return "fernet", Fernet(key.encode("ascii")).encrypt(data)
        except Exception:
            logger.debug("Fernet protect unavailable", exc_info=True)
    return None


def _decrypt_record(record: dict) -> dict | None:
    alg = str(record.get("alg") or "")
    try:
        payload = base64.b64decode(str(record.get("data") or ""))
    except Exception:
        return None
    if alg == "dpapi":
        raw = _unprotect_dpapi(payload)
    elif alg == "fernet":
        try:
            key = os.environ.get("GBT_AI_AUDIT_KEY", "").strip()
            from cryptography.fernet import Fernet

            raw = Fernet(key.encode("ascii")).decrypt(payload) if key else None
        except Exception:
            raw = None
    else:
        raw = None
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _write(event: dict) -> bool:
    if not enabled() or not isinstance(event, dict):
        return False
    try:
        safe = sanitize_for_audit(event)
        raw = json.dumps(safe, ensure_ascii=False, sort_keys=True).encode("utf-8")
        encrypted = _encrypt_record(raw)
        if encrypted is None:
            logger.warning("AI audit storage unavailable; record skipped")
            return False
        alg, payload = encrypted
        envelope = {
            "v": 1,
            "alg": alg,
            "data": base64.b64encode(payload).decode("ascii"),
        }
        directory = _audit_dir()
        directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(directory, 0o700)
        except OSError:
            pass
        with _LOCK:
            path = locked_append_text(
                _audit_file(),
                json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n",
                lock_timeout=3.0,
            )
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True
    except Exception:
        logger.debug("AI audit write skipped", exc_info=True)
        return False


def begin(provider: str, url: str, *, model: str | None = None,
          request_body=None, headers: dict | None = None,
          session_id: str | None = None, stream: bool | None = None,
          attempt: int | None = None) -> dict | None:
    """Open a side-channel audit context; return None when not auditable."""
    if not enabled() or not is_allowed_endpoint(provider, url):
        return None
    host, scheme, path = _host_from_url(url)
    provider = _normalize_provider(provider)
    request_meta = _content_metadata(request_body)
    if stream is not None:
        request_meta["stream"] = bool(stream)
    context = {
        "request_id": secrets.token_hex(12),
        "started": time.monotonic(),
        "provider": provider,
        "host": host,
        "scheme": scheme,
        "path": redact_text(path[:240])[0],
        "model": str(model or request_meta.get("model") or "")[:160],
        "session_id": str(session_id or "")[:160],
        "attempt": int(attempt) if attempt is not None else None,
        "stream": bool(request_meta.get("stream")),
        "header_names": _header_names(headers),
        "request_meta": request_meta,
        "_finished": False,
    }
    event = {
        "ts": round(time.time(), 3),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": "ai_request",
        **{k: v for k, v in context.items() if not k.startswith("_")},
    }
    if not _write(event):
        return None
    return context


def finish(context: dict | None, *, status: int | None = None,
           response=None, response_text: str | None = None,
           ok: bool = True, error=None, elapsed_ms: float | None = None) -> bool:
    """Append response/error metadata and close the side-channel context."""
    if not context or context.get("_finished"):
        return False
    context["_finished"] = True
    elapsed = elapsed_ms
    if elapsed is None:
        elapsed = round((time.monotonic() - context.get("started", time.monotonic())) * 1000, 1)
    event = {
        "ts": round(time.time(), 3),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": "ai_response" if ok else "ai_error",
        "request_id": context.get("request_id"),
        "provider": context.get("provider"),
        "host": context.get("host"),
        "path": context.get("path"),
        "model": context.get("model"),
        "session_id": context.get("session_id"),
        "attempt": context.get("attempt"),
        "stream": context.get("stream"),
        "status": int(status) if status is not None else None,
        "ok": bool(ok),
        "elapsed_ms": elapsed,
        "response_meta": _response_metadata(response, response_text),
        "error_class": type(error).__name__ if error is not None else None,
    }
    return _write(event)


def _iter_file_reversed(path: Path):
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        pos = handle.tell()
        buf = b""
        while pos > 0:
            step = min(8192, pos)
            pos -= step
            handle.seek(pos)
            chunk = handle.read(step)
            buf = chunk + buf
            lines = buf.split(b"\n")
            buf = lines.pop(0)
            for line in reversed(lines):
                yield line
        if buf.strip():
            yield buf


def query(limit: int = 100) -> list[dict]:
    """Read decrypted AI audit records, oldest first."""
    path = _audit_file()
    if not path.exists():
        return []
    limit = max(1, min(int(limit), _MAX_QUERY))
    try:
        iterator = _iter_file_reversed(path)
    except OSError:
        return []
    result = []
    try:
        for raw in iterator:
            if not raw.strip():
                continue
            try:
                envelope = json.loads(raw.decode("utf-8", errors="replace"))
                record = _decrypt_record(envelope)
            except Exception:
                record = None
            if record is not None:
                result.append(record)
            if len(result) >= limit:
                break
    except OSError:
        return []
    result.reverse()
    return result


def count() -> int:
    """Return the number of encrypted AI audit records."""
    path = _audit_file()
    if not path.exists():
        return 0
    try:
        count_value = 0
        with open(path, "rb") as handle:
            for line in handle:
                if line.strip():
                    count_value += 1
        return count_value
    except OSError:
        return 0


def status() -> dict:
    return {
        "enabled": enabled(),
        "encrypted": os.name == "nt" or bool(os.environ.get("GBT_AI_AUDIT_KEY")),
        "known_hosts": sorted(_KNOWN_HOSTS),
        "extra_hosts": sorted(_extra_hosts()),
        "store": str(_audit_file()),
    }
