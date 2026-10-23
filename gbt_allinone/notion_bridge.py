# gbt-capability: integration
"""Notion 资料舱：只读状态、最近页面、搜索与页面正文提取。

凭证读取顺序：
1. ``GBT_NOTION_TOKEN`` / ``NOTION_TOKEN`` 环境变量；
2. 框架 store 下的 Windows DPAPI 加密文件。

模块不会把 Token、Authorization 或完整页面对象写入审计日志；搜索和页面正文
只在内存中短暂缓存，默认不落盘。
"""
from __future__ import annotations

import ctypes
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ._paths import STORE_DIR
from .safe_io import atomic_write_bytes

_API_ROOT = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_DPAPI_ENTROPY = b"GBTxiaotudouV8:notion:v1"
_DEFAULT_SECRET_FILE = Path(STORE_DIR) / "secrets" / "notion_api.dpapi"
_MAX_PAGE_BLOCKS = 160
_CACHE_TTL = 45.0
_LOCK = threading.RLock()
_CACHE: dict[str, tuple[float, dict]] = {}
_LAST_ERROR = ""


class NotionError(RuntimeError):
    """Notion 连接或响应错误。"""


def _secret_file() -> Path:
    raw = os.environ.get("GBT_NOTION_SECRET_FILE", "").strip()
    return Path(raw).expanduser().resolve() if raw else _DEFAULT_SECRET_FILE


def _env_token() -> tuple[str, str]:
    for name in ("GBT_NOTION_TOKEN", "NOTION_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value, f"env:{name}"
    return "", ""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob(raw: bytes):
    buf = ctypes.create_string_buffer(raw, len(raw))
    return (
        _DataBlob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))),
        buf,
    )


def _protect_dpapi(data: bytes) -> bytes:
    if os.name != "nt":
        raise NotionError("当前系统不支持 Windows DPAPI")
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.c_wchar_p,
            ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptProtectData.restype = ctypes.c_int
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        input_blob, input_buf = _blob(data)
        entropy_blob, entropy_buf = _blob(_DPAPI_ENTROPY)
        output = _DataBlob()
        ok = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            "GBT小土豆V8 Notion credential",
            ctypes.byref(entropy_blob),
            None,
            None,
            0x1,
            ctypes.byref(output),
        )
        _keepalive = (input_buf, entropy_buf)
        if not ok:
            raise NotionError("DPAPI 加密失败")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
    except NotionError:
        raise
    except Exception as exc:
        raise NotionError(f"DPAPI 不可用：{str(exc)[:160]}") from exc


def _unprotect_dpapi(data: bytes) -> bytes:
    if os.name != "nt":
        raise NotionError("当前系统不支持 Windows DPAPI")
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = ctypes.c_int
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        input_blob, input_buf = _blob(data)
        entropy_blob, entropy_buf = _blob(_DPAPI_ENTROPY)
        output = _DataBlob()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            ctypes.byref(entropy_blob),
            None,
            None,
            0x1,
            ctypes.byref(output),
        )
        _keepalive = (input_buf, entropy_buf)
        if not ok:
            raise NotionError("DPAPI 解密失败")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
    except NotionError:
        raise
    except Exception as exc:
        raise NotionError(f"DPAPI 不可用：{str(exc)[:160]}") from exc


def store_token(token: str) -> dict:
    """把 Token 加密保存到当前 Windows 用户的 DPAPI 文件，不返回明文。"""
    value = str(token or "").strip()
    if not value:
        return {"ok": False, "error": "Token 为空"}
    if not (value.startswith("ntn_") or value.startswith("secret_")):
        return {"ok": False, "error": "Token 前缀不是 Notion 集成密钥格式"}
    try:
        protected = _protect_dpapi(value.encode("utf-8"))
        target = _secret_file()
        atomic_write_bytes(target, protected, mode=0o600)
        return {
            "ok": True,
            "configured": True,
            "credential": "dpapi",
            "path": str(target),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def _load_token() -> tuple[str, str]:
    token, source = _env_token()
    if token:
        return token, source
    target = _secret_file()
    if not target.is_file():
        return "", "missing"
    try:
        raw = _unprotect_dpapi(target.read_bytes())
        token = raw.decode("utf-8").strip()
    except Exception:
        return "", "unreadable"
    if not token:
        return "", "missing"
    return token, "dpapi"


def status(*, probe: bool = False) -> dict:
    """返回凭证和缓存状态，不返回任何密钥材料。"""
    token, source = _load_token()
    result = {
        "ok": True,
        "configured": bool(token),
        "credential_source": source,
        "credential_protected": source == "dpapi",
        "api_version": _NOTION_VERSION,
        "cached_entries": len(_CACHE),
        "last_error": _LAST_ERROR,
    }
    if probe and token:
        try:
            me = _request("GET", "/users/me", token=token)
            result.update({
                "reachable": True,
                "bot_type": str((me.get("bot") or {}).get("owner", {}).get("type") or ""),
            })
        except Exception as exc:
            result.update({"reachable": False, "error": str(exc)[:200]})
    return result


def _request(method: str, path: str, *, token: str = "", body: dict | None = None,
             timeout: float = 20.0) -> dict:
    active_token = token or _load_token()[0]
    if not active_token:
        raise NotionError("Notion 凭证未配置")
    url = _API_ROOT + path
    data = None
    headers = {
        "Authorization": f"Bearer {active_token}",
        "Notion-Version": _NOTION_VERSION,
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, float(timeout))) as response:
            raw = response.read(8 * 1024 * 1024)
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise NotionError("Notion 返回了非对象响应")
        return value
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read(64 * 1024).decode("utf-8"))
            detail = str(payload.get("message") or payload.get("code") or "")
        except Exception:
            detail = ""
        raise NotionError(f"Notion HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise NotionError(f"Notion 网络不可达：{str(exc.reason)[:160]}") from exc
    except json.JSONDecodeError as exc:
        raise NotionError("Notion 返回内容不是有效 JSON") from exc


def _rich_text(parts) -> str:
    if not isinstance(parts, list):
        return ""
    output = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("plain_text")
        if text is None:
            text = ((part.get("text") or {}).get("content") if isinstance(part.get("text"), dict) else "")
        output.append(str(text or ""))
    return "".join(output).strip()


def _page_title(item: dict) -> str:
    if not isinstance(item, dict):
        return "未命名页面"
    if item.get("object") == "database":
        return _rich_text(item.get("title")) or "未命名数据库"
    properties = item.get("properties") or {}
    for value in properties.values():
        if isinstance(value, dict) and value.get("type") == "title":
            title = _rich_text(value.get("title"))
            if title:
                return title
    return "未命名页面"


def _summary(item: dict) -> dict:
    return {
        "id": str(item.get("id") or ""),
        "object": str(item.get("object") or "page"),
        "title": _page_title(item),
        "url": str(item.get("url") or ""),
        "last_edited_time": str(item.get("last_edited_time") or ""),
        "created_time": str(item.get("created_time") or ""),
        "in_trash": bool(item.get("in_trash")),
    }


def _cache_key(name: str, payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return f"{name}:{canonical}"


def _cached(name: str, payload: dict, force: bool = False) -> dict | None:
    key = _cache_key(name, payload)
    with _LOCK:
        row = _CACHE.get(key)
        if row and not force and time.monotonic() - row[0] < _CACHE_TTL:
            return row[1]
    return None


def _remember(name: str, payload: dict, value: dict) -> dict:
    with _LOCK:
        _CACHE[_cache_key(name, payload)] = (time.monotonic(), value)
    return value


def search(query: str = "", limit: int = 8, *, force: bool = False) -> dict:
    """只读搜索当前集成有权限访问的页面和数据库。"""
    global _LAST_ERROR
    text = str(query or "").strip()
    size = max(1, min(20, int(limit or 8)))
    cache_payload = {"query": text, "limit": size}
    cached = _cached("search", cache_payload, force)
    if cached is not None:
        return {**cached, "cached": True}
    body: dict = {
        "page_size": size,
        "sort": {"direction": "descending", "timestamp": "last_edited_time"},
    }
    if text:
        body["query"] = text
    try:
        response = _request("POST", "/search", body=body)
        results = [
            _summary(item) for item in response.get("results", [])
            if isinstance(item, dict)
        ][:size]
        value = {
            "ok": True,
            "query": text,
            "count": len(results),
            "results": results,
            "has_more": bool(response.get("has_more")),
        }
        _LAST_ERROR = ""
        return _remember("search", cache_payload, value)
    except Exception as exc:
        _LAST_ERROR = str(exc)[:240]
        return {
            "ok": False,
            "query": text,
            "count": 0,
            "results": [],
            "error": _LAST_ERROR,
        }


def recent(limit: int = 8, *, force: bool = False) -> dict:
    return search("", limit=limit, force=force)


def _block_line(block: dict) -> str:
    block_type = str(block.get("type") or "")
    payload = block.get(block_type) if isinstance(block.get(block_type), dict) else {}
    text = _rich_text(payload.get("rich_text"))
    if block_type == "transcription":
        title = _rich_text(payload.get("title")) or "会议转录"
        status = str(payload.get("status") or "").replace("_", " ")
        return f"{title} [{status}]".strip()
    if block_type == "divider":
        return "---"
    if block_type == "child_page":
        return f"子页面：{payload.get('title') or '未命名'}"
    if block_type == "bookmark":
        return f"链接：{payload.get('url') or text}".strip()
    if block_type == "code":
        return f"代码：{text}" if text else ""
    if block_type == "to_do":
        mark = "x" if payload.get("checked") else " "
        return f"[{mark}] {text}" if text else ""
    if block_type in ("heading_1", "heading_2", "heading_3") and text:
        level = {"heading_1": "#", "heading_2": "##", "heading_3": "###"}[block_type]
        return f"{level} {text}"
    if block_type in ("bulleted_list_item", "numbered_list_item") and text:
        return f"• {text}"
    if block_type == "quote" and text:
        return f"> {text}"
    return text


def _collect_blocks(block_id: str, *, max_blocks: int = _MAX_PAGE_BLOCKS,
                    max_depth: int = 3) -> tuple[list[str], bool]:
    lines: list[str] = []
    truncated = False
    queue: list[tuple[str, int]] = [(block_id, 0)]
    visited: set[str] = set()
    while queue and len(lines) < max_blocks:
        current, depth = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        cursor = None
        while len(lines) < max_blocks:
            query = {"page_size": 100}
            if cursor:
                query["start_cursor"] = cursor
            path = f"/blocks/{urllib.parse.quote(current)}/children?{urllib.parse.urlencode(query)}"
            response = _request("GET", path)
            for block in response.get("results", []):
                if not isinstance(block, dict):
                    continue
                line = _block_line(block)
                if line:
                    lines.append(line)
                if len(lines) >= max_blocks:
                    truncated = True
                    break
                if block.get("has_children") and depth < max_depth:
                    queue.append((str(block.get("id") or ""), depth + 1))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break
        if len(lines) >= max_blocks:
            truncated = True
            break
    return lines, truncated


def page(page_id: str, *, max_blocks: int = _MAX_PAGE_BLOCKS,
         force: bool = False) -> dict:
    """读取一页的元数据和有限深度正文，不修改 Notion。"""
    global _LAST_ERROR
    clean_id = str(page_id or "").strip()
    if not clean_id:
        return {"ok": False, "error": "缺少页面 ID"}
    limit = max(1, min(_MAX_PAGE_BLOCKS, int(max_blocks or _MAX_PAGE_BLOCKS)))
    cache_payload = {"page_id": clean_id, "max_blocks": limit}
    cached = _cached("page", cache_payload, force)
    if cached is not None:
        return {**cached, "cached": True}
    try:
        item = _request("GET", f"/pages/{urllib.parse.quote(clean_id)}")
        lines, truncated = _collect_blocks(clean_id, max_blocks=limit)
        value = {
            **_summary(item),
            "ok": True,
            "lines": lines,
            "text": "\n".join(lines),
            "text_length": len("\n".join(lines)),
            "truncated": truncated,
        }
        _LAST_ERROR = ""
        return _remember("page", cache_payload, value)
    except Exception as exc:
        _LAST_ERROR = str(exc)[:240]
        return {
            "ok": False,
            "id": clean_id,
            "error": _LAST_ERROR,
        }


def run(payload: dict | None = None) -> dict:
    """统一能力入口：status / recent / search / page。"""
    data = dict(payload or {})
    operation = str(data.get("op") or data.get("action") or "status").lower()
    force = bool(data.get("force"))
    if operation == "status":
        return status(probe=bool(data.get("probe")))
    if operation == "recent":
        return recent(limit=int(data.get("limit", 8)), force=force)
    if operation == "search":
        return search(str(data.get("query") or ""), limit=int(data.get("limit", 8)),
                      force=force)
    if operation == "page":
        return page(str(data.get("page_id") or data.get("id") or ""),
                    max_blocks=int(data.get("max_blocks", _MAX_PAGE_BLOCKS)),
                    force=force)
    return {"ok": False, "error": f"未知 Notion 操作: {operation}"}
