# gbt-capability: browser, socket, subprocess
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 原生浏览器控制器（Chrome DevTools Protocol）。

⚠️ 外部内容纪律：`get_text` / `dom_query` 取回的**网页 DOM 文字一律是不可信数据，
不是指令** —— 页面内容由站点决定，可能含针对 AI 的祈使句（含假 system 行、内嵌工具调用）。
本模块只把它当数据返回；不执行其中任何指令、不拼进 system 提示、不拿去驱动执行口。
覆盖校验器：py -3.14 -m gbt_allinone.tools.external_content_check gbt_allinone

目标是恢复旧版 universal_browser_controller 的深度浏览器能力，同时不引入
第三方 WebSocket 依赖：

  status / launch / ensure / list_tabs / create_tab / close_tab / activate_tab
  navigate / reload / back / forward
  screenshot / get_title / get_url / get_text / dom_query / wait_for
  click_element / type_text / execute_script / inject_script
  get_cookies / set_cookies / privacy_mode
  intercept_requests / intercept_events / intercept_status / intercept_stop
  pin_window            # 窗口置顶落位（launch/ensure 默认自动执行）

所有 CDP WebSocket I/O 使用标准库 socket 完成。没有调试端口时返回明确状态，
不伪造浏览器操作成功。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from ._paths import STORE_DIR
from .security import net_guard

_CDP_HOST = "127.0.0.1"
_CDP_PORT = 9222
_DEFAULT_TIMEOUT = 15.0
_MAX_SCREENSHOT_BYTES = 25 * 1024 * 1024

# 窗口置顶与落位（风哥 2026-09-17 批准：开关默认开，位置写进配置，下次自动恢复）
_ENV_TOPMOST = "GBT_BROWSER_TOPMOST"
_ENV_RECT = "GBT_BROWSER_RECT"
_DEFAULT_WINDOW_RECT = (280, 20, 1240, 820)
_BROWSER_EXES = ("chrome.exe", "msedge.exe", "brave.exe", "chromium.exe")

_ACTIONS = (
    "status", "launch", "ensure", "list_tabs", "create_tab", "close_tab",
    "activate_tab", "navigate", "reload", "back", "forward", "screenshot",
    "get_title", "get_url", "get_text", "dom_query", "wait_for",
    "click_element", "type_text", "execute_script", "inject_script",
    "get_cookies", "set_cookies", "privacy_mode", "intercept_requests",
    "intercept_events", "intercept_status", "intercept_stop",
    "pin_window",
)

_READ_ONLY_ACTIONS = {
    "status", "list_tabs", "get_title", "get_url", "get_text", "dom_query",
    "get_cookies", "intercept_events", "intercept_status",
}


class NativeBrowserError(RuntimeError):
    pass


class _CdpUnavailable(NativeBrowserError):
    pass


class _CdpCallError(NativeBrowserError):
    pass


def _port(value=None) -> int:
    try:
        port = int(value or _CDP_PORT)
    except (TypeError, ValueError) as exc:
        raise NativeBrowserError("调试端口必须是整数") from exc
    if not (1 <= port <= 65535):
        raise NativeBrowserError("调试端口超出范围")
    return port


def _json_bytes(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")


def _http_json(path: str, *, port=None, timeout=3.0, method="GET",
               payload=None) -> dict | list | None:
    url = f"http://{_CDP_HOST}:{_port(port)}{path}"
    data = _json_bytes(payload) if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=float(timeout)) as response:
            raw = response.read()
    except Exception:
        return None
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None


def _browser_candidates() -> list[Path]:
    candidates: list[Path] = []
    custom = os.environ.get("GBT_BROWSER_EXE")
    if custom:
        candidates.append(Path(custom).expanduser())

    for command in ("chrome.exe", "msedge.exe", "brave.exe", "chromium.exe"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))

    roots = [
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("PROGRAMW6432"),
    ]
    relative = (
        r"Google\Chrome\Application\chrome.exe",
        r"Microsoft\Edge\Application\msedge.exe",
        r"BraveSoftware\Brave-Browser\Application\brave.exe",
        r"Chromium\Application\chrome.exe",
    )
    for root in roots:
        if not root:
            continue
        for rel in relative:
            candidates.append(Path(root) / rel)

    seen: set[str] = set()
    unique: list[Path] = []
    for item in candidates:
        key = str(item).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def find_browser() -> str:
    for candidate in _browser_candidates():
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return ""


def _tab_rows(port=None, timeout=3.0) -> list[dict]:
    rows = _http_json("/json", port=port, timeout=timeout)
    if not isinstance(rows, list):
        return []
    safe = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        safe.append({
            "id": row.get("id"),
            "title": row.get("title") or "",
            "url": row.get("url") or "",
            "type": row.get("type") or "page",
            "webSocketDebuggerUrl": row.get("webSocketDebuggerUrl") or "",
        })
    return safe


def _select_tab(tab_id=None, *, port=None, timeout=3.0) -> dict:
    tabs = [row for row in _tab_rows(port, timeout) if row.get("type") == "page"]
    if not tabs:
        tabs = _tab_rows(port, timeout)
    if not tabs:
        raise _CdpUnavailable(
            "没有可用浏览器标签页；请先执行 action=launch 或 action=ensure")
    wanted = str(tab_id) if tab_id is not None else ""
    if wanted:
        for tab in tabs:
            if str(tab.get("id")) == wanted:
                return tab
        raise NativeBrowserError(f"标签页不存在: {tab_id}")
    for tab in tabs:
        if tab.get("webSocketDebuggerUrl"):
            return tab
    raise _CdpUnavailable("浏览器标签页没有 WebSocket 调试地址")


class _CdpWebSocket:
    """最小的 RFC6455 客户端，只用于本机 CDP。"""

    def __init__(self, ws_url: str, timeout: float = _DEFAULT_TIMEOUT):
        parsed = urllib.parse.urlsplit(ws_url)
        if parsed.scheme != "ws" or not parsed.hostname:
            raise NativeBrowserError("CDP WebSocket 地址非法")
        self.host = parsed.hostname
        self.port = _port(parsed.port or 80)
        self.path = parsed.path or "/"
        if parsed.query:
            self.path += "?" + parsed.query
        self.timeout = float(timeout)
        self._sock: socket.socket | None = None
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._next_id = 0
        self._closed = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode("ascii")
        try:
            sock.sendall(request)
            header = bytearray()
            while b"\r\n\r\n" not in header:
                chunk = sock.recv(4096)
                if not chunk:
                    raise _CdpUnavailable("CDP WebSocket 握手断开")
                header.extend(chunk)
            raw_header, _, rest = bytes(header).partition(b"\r\n\r\n")
            first = raw_header.split(b"\r\n", 1)[0].decode("latin-1", "replace")
            if " 101 " not in first:
                raise _CdpUnavailable(f"CDP WebSocket 握手失败: {first[:120]}")
            expected = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()).decode("ascii").lower()
            match = re.search(r"(?im)^Sec-WebSocket-Accept:\s*(\S+)", raw_header.decode(
                "latin-1", "replace"))
            if match and match.group(1).strip().lower() != expected:
                raise _CdpUnavailable("CDP WebSocket 握手校验失败")
        except Exception:
            # 🔴 2026-09-26 修：握手中途任何异常原来都漏关 socket（sendall/recv 抛 OSError 时无人收尸）
            sock.close()
            raise
        self._sock = sock
        self._buffer.extend(rest)
        self._closed = False

    def close(self) -> None:
        self._closed = True
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def _read_exact(self, count: int) -> bytes:
        if count < 0:
            raise _CdpCallError("非法 WebSocket 帧长度")
        while len(self._buffer) < count:
            if self._sock is None:
                raise _CdpUnavailable("CDP WebSocket 已关闭")
            chunk = self._sock.recv(max(4096, count - len(self._buffer)))
            if not chunk:
                raise _CdpUnavailable("CDP WebSocket 连接断开")
            self._buffer.extend(chunk)
        data = bytes(self._buffer[:count])
        del self._buffer[:count]
        return data

    def _send_frame(self, opcode: int, payload: bytes = b"") -> None:
        if self._sock is None:
            raise _CdpUnavailable("CDP WebSocket 未连接")
        first = 0x80 | (opcode & 0x0F)
        length = len(payload)
        if length < 126:
            header = bytes((first, 0x80 | length))
        elif length < 65536:
            header = bytes((first, 0x80 | 126)) + struct.pack("!H", length)
        else:
            header = bytes((first, 0x80 | 127)) + struct.pack("!Q", length)
        mask = secrets.token_bytes(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self._sock.sendall(header + mask + masked)

    def _recv_frame(self) -> tuple[int, bytes]:
        first, second = self._read_exact(2)
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        if length > _MAX_SCREENSHOT_BYTES * 2:
            raise _CdpCallError("CDP WebSocket 帧超过安全上限")
        mask = self._read_exact(4) if masked else b""
        payload = self._read_exact(length)
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        if opcode == 0x8:
            raise _CdpUnavailable("CDP WebSocket 已关闭")
        if opcode == 0x9:
            self._send_frame(0xA, payload)
            return self._recv_frame()
        if opcode == 0xA:
            return self._recv_frame()
        if not fin:
            fragments = [payload]
            while True:
                next_first, next_second = self._read_exact(2)
                next_opcode = next_first & 0x0F
                next_masked = bool(next_second & 0x80)
                next_length = next_second & 0x7F
                if next_length == 126:
                    next_length = struct.unpack("!H", self._read_exact(2))[0]
                elif next_length == 127:
                    next_length = struct.unpack("!Q", self._read_exact(8))[0]
                next_mask = self._read_exact(4) if next_masked else b""
                part = self._read_exact(next_length)
                if next_masked:
                    part = bytes(
                        byte ^ next_mask[index % 4]
                        for index, byte in enumerate(part)
                    )
                fragments.append(part)
                if next_opcode == 0x9:
                    self._send_frame(0xA, part)
                if next_first & 0x80:
                    return opcode, b"".join(fragments)
        return opcode, payload

    def send_json(self, payload: dict) -> None:
        self._send_frame(0x1, _json_bytes(payload))

    def recv_json(self, timeout: float | None = None) -> dict:
        if self._sock is None:
            raise _CdpUnavailable("CDP WebSocket 未连接")
        old_timeout = self._sock.gettimeout()
        if timeout is not None:
            self._sock.settimeout(float(timeout))
        try:
            opcode, payload = self._recv_frame()
        finally:
            if self._sock is not None and timeout is not None:
                self._sock.settimeout(old_timeout)
        if opcode not in (0x1, 0x2):
            raise _CdpCallError(f"CDP WebSocket 收到非文本帧: {opcode}")
        try:
            message = json.loads(payload.decode("utf-8", "replace"))
        except json.JSONDecodeError as exc:
            raise _CdpCallError("CDP WebSocket 返回非法 JSON") from exc
        if not isinstance(message, dict):
            raise _CdpCallError("CDP WebSocket 返回结构非法")
        return message

    def call(self, method: str, params: dict | None = None,
             timeout: float = _DEFAULT_TIMEOUT) -> dict:
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            self.send_json({"id": request_id, "method": method,
                            "params": params or {}})
            deadline = time.monotonic() + float(timeout)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _CdpCallError(f"CDP {method} 超时")
                message = self.recv_json(timeout=remaining)
                if message.get("id") != request_id:
                    continue
                error = message.get("error")
                if error:
                    detail = error.get("message") if isinstance(error, dict) else error
                    raise _CdpCallError(f"CDP {method} 失败: {detail}")
                result = message.get("result") or {}
                return result if isinstance(result, dict) else {"value": result}


def _with_tab(tab_id=None, *, port=None, timeout=_DEFAULT_TIMEOUT):
    tab = _select_tab(tab_id, port=port, timeout=min(float(timeout), 5.0))
    ws_url = tab.get("webSocketDebuggerUrl") or ""
    if not ws_url:
        raise _CdpUnavailable("标签页缺少 WebSocket 调试地址")
    client = _CdpWebSocket(ws_url, timeout=timeout)
    client.connect()
    return tab, client


def _eval_js(client: _CdpWebSocket, expression: str, *,
             await_promise=False, timeout=_DEFAULT_TIMEOUT):
    result = client.call("Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": bool(await_promise),
    }, timeout=timeout)
    remote = result.get("result") or {}
    if result.get("exceptionDetails"):
        detail = result["exceptionDetails"].get("text") or "JavaScript 执行异常"
        raise NativeBrowserError(str(detail)[:300])
    return remote.get("value")


def _normalize_url_text(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        raise NativeBrowserError("缺少 url")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", value, re.I):
        value = "https://" + value
    if not re.match(r"^https?://", value, re.I):
        raise NativeBrowserError("原生浏览器只接受 http/https URL")
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").lower()
    if not host:
        raise NativeBrowserError("URL 缺少主机名")
    try:
        port = parsed.port
    except ValueError as exc:
        raise NativeBrowserError(f"URL 端口非法: {exc}") from exc
    if (parsed.scheme.lower() == "http" and port == 80) or (
            parsed.scheme.lower() == "https" and port == 443):
        port = None
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.sort()
    return urllib.parse.urlunsplit((
        parsed.scheme.lower(),
        host + (f":{port}" if port else ""),
        path,
        urllib.parse.urlencode(query),
        parsed.fragment,
    ))


def _normalize_url(url: str, allow_private=False) -> str:
    value = _normalize_url_text(url)
    net_guard.validate_url(value, allow_private=bool(allow_private))
    return value


def _matching_tab(url, *, port=None, timeout=1.5, allow_private=False):
    """Return an existing tab already at the normalized target URL."""
    target = _normalize_url_text(url)
    for tab in _tab_rows(port, timeout):
        if str(tab.get("type") or "").lower() not in ("", "page"):
            continue
        current_raw = str(tab.get("url") or "").strip()
        if not current_raw:
            continue
        try:
            current = _normalize_url_text(current_raw)
        except NativeBrowserError:
            continue
        if current == target:
            return tab, target
    return None, target


def _safe_output_path(out: str | None, suffix=".png") -> Path:
    if out:
        path = Path(str(out)).expanduser()
        if not path.is_absolute():
            path = Path(STORE_DIR) / path
    else:
        path = Path(STORE_DIR) / "vision" / f"native_browser_{int(time.time())}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _mask_secret(value) -> str:
    text = str(value or "")
    if len(text) <= 4:
        return "****"
    return text[:4] + "****"


def status(port=None, timeout=3.0) -> dict:
    version = _http_json("/json/version", port=port, timeout=timeout)
    tabs = _tab_rows(port, timeout)
    available = isinstance(version, dict) and bool(tabs)
    result = {
        "ok": available,
        "status": "ready" if available else "needs_browser_debug",
        "cdp_available": available,
        "endpoint": f"http://{_CDP_HOST}:{_port(port)}",
        "transport": "standard-library-rfc6455",
        "browser": (version or {}).get("Browser") if isinstance(version, dict) else None,
        "protocol": (version or {}).get("Protocol-Version") if isinstance(version, dict) else None,
        "tab_count": len(tabs),
        "tabs": tabs[:20],
        "actions": list(_ACTIONS),
        "browser_executable": find_browser() or None,
    }
    if not available:
        result["needs_browser_debug"] = True
        result["note"] = (
            "未发现本机 CDP 调试端口；执行 native browser action=launch 或 "
            "action=ensure 可安全启动独立调试浏览器并复用。"
        )
    return result


def always_on_top_default() -> bool:
    """窗口置顶开关：默认**开**；`GBT_BROWSER_TOPMOST=0/false/off/no` 关。"""
    raw = str(os.environ.get(_ENV_TOPMOST, "") or "").strip().lower()
    if not raw:
        return True
    return raw not in {"0", "false", "off", "no"}


def window_rect_default() -> "tuple[int, int, int, int]":
    """落位配置：`GBT_BROWSER_RECT=x,y,w,h`；默认 (280, 20, 1240, 820)。"""
    raw = str(os.environ.get(_ENV_RECT, "") or "").strip()
    if not raw:
        return _DEFAULT_WINDOW_RECT
    try:
        parts = [int(float(v)) for v in raw.replace(" ", "").split(",")]
    except ValueError:
        return _DEFAULT_WINDOW_RECT
    if len(parts) != 4:
        return _DEFAULT_WINDOW_RECT
    return (parts[0], parts[1], parts[2], parts[3])


def _browser_pid(port=None, timeout=3.0):
    """用 CDP 的精确定位拿浏览器主进程 pid；拿不到如实返回 None。"""
    info = _http_json("/json/version", port=port, timeout=timeout)
    ws_url = info.get("webSocketDebuggerUrl") if isinstance(info, dict) else None
    if not ws_url:
        return None
    client = _CdpWebSocket(ws_url, timeout=timeout)
    try:
        client.connect()
        result = client.call("SystemInfo.getProcessInfo", {}, timeout=timeout)
    except Exception:  # noqa: BLE001 —— 拿不到只是退化，不是失败
        result = None
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass
    rows = (result or {}).get("processInfo") if isinstance(result, dict) else None
    for row in rows or []:
        if str(row.get("type")) == "browser":
            try:
                return int(row.get("id"))
            except (TypeError, ValueError):
                return None
    return None


def _win32_apply(rect, topmost, pid=None, title_filter=None) -> dict:
    """只动窗口层级与位置：还原 + 置顶/取消置顶 + 落位。不读页面，不碰输入框。"""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _proc_name(owner_pid: int) -> str:
        handle = kernel32.OpenProcess(0x1000, False, owner_pid)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value.rsplit("\\", 1)[-1].lower()
            return ""
        finally:
            kernel32.CloseHandle(handle)

    found: list = []

    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        owner_pid = int(owner.value)
        if _proc_name(owner_pid) not in _BROWSER_EXES:
            return True
        if pid is not None and owner_pid != int(pid):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if pid is None:
            if not title_filter:
                return True
            if str(title_filter).lower() not in title.value.lower():
                return True
        found.append({"hwnd": int(hwnd), "pid": owner_pid, "title": title.value})
        return True

    user32.EnumWindows(enum_proc(_cb), 0)
    if not found:
        return {"ok": False, "status": "no_window",
                "error": "没找到可置顶的浏览器窗口",
                "hint": "浏览器窗口可能还没画出来，或在别的会话里"}
    target = found[0]
    hwnd = target["hwnd"]
    user32.ShowWindow(wintypes.HWND(hwnd), 9)  # SW_RESTORE
    x, y, w, h = [int(v) for v in rect]
    ok = user32.SetWindowPos(wintypes.HWND(hwnd),
                             wintypes.HWND(-1 if topmost else -2),
                             x, y, w, h, 0x0040)  # SWP_SHOWWINDOW
    box = wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(box))
    return {
        "ok": bool(ok),
        "hwnd": hwnd,
        "pid": target["pid"],
        "title": target["title"][:90],
        "topmost": bool(topmost),
        "rect": [x, y, w, h],
        "rect_after": [box.left, box.top, box.right - box.left, box.bottom - box.top],
        "windows_seen": len(found),
    }


def pin_window(rect=None, topmost=None, title_filter=None, port=None,
               timeout=3.0, retries=3) -> dict:
    """把原生浏览器窗口置顶并落位。

    识别方式：优先用 CDP 浏览器主进程 pid（精确）；pid 拿不到时退化为标题匹配。
    开关默认**开**（`GBT_BROWSER_TOPMOST=0` 关），落位默认 `window_rect_default()`。
    """
    if os.name != "nt":
        return {"ok": False, "status": "unsupported",
                "error": "窗口置顶目前只在 Windows 上实现"}
    want_top = always_on_top_default() if topmost is None else bool(topmost)
    target_rect = tuple(int(v) for v in (rect or window_rect_default()))
    attempts = 0
    last: dict = {}
    while attempts < max(1, int(retries)):
        attempts += 1
        pid = _browser_pid(port=port, timeout=timeout)
        last = _win32_apply(target_rect, want_top, pid=pid,
                            title_filter=None if pid else title_filter)
        last["matched_by"] = "pid" if pid else f"title={title_filter!r}"
        last["attempts"] = attempts
        last["always_on_top_default"] = always_on_top_default()
        last["rect_config"] = list(target_rect)
        if last.get("ok") or pid is not None or not title_filter:
            break
        time.sleep(0.4)
    return last


def _attach_window(result: dict, *, port=None, timeout=3.0) -> dict:
    """把窗口置顶结果附到 launch/ensure 回执上；置顶失败不影响浏览器本身的成败。"""
    if not always_on_top_default():
        result["window"] = {"ok": False, "status": "disabled",
                            "note": f"{_ENV_TOPMOST} 关闭了置顶开关"}
        return result
    try:
        result["window"] = pin_window(port=port, timeout=timeout, retries=3)
    except Exception as exc:  # noqa: BLE001
        result["window"] = {"ok": False, "status": "error", "error": str(exc)[:200]}
    return result


def launch(url=None, port=None, timeout=12.0, allow_private=False,
           browser_exe=None) -> dict:
    port = _port(port)
    current = status(port=port, timeout=1.0)
    if current.get("cdp_available"):
        return _attach_window({
            "ok": True,
            "status": "already_running",
            "reused": True,
            "endpoint": current["endpoint"],
            "browser": current.get("browser"),
            "tab_count": current.get("tab_count", 0),
            "note": "调试浏览器已经在运行，复用现有 CDP 会话。",
        }, port=port)

    exe = str(browser_exe or find_browser() or "").strip()
    if not exe:
        return {
            "ok": False,
            "status": "needs_dependency",
            "missing": "chrome/edge/brave/chromium",
            "note": "未找到支持 CDP 的浏览器；可设置 GBT_BROWSER_EXE 指定可执行文件。",
        }
    if not Path(exe).is_file():
        return {
            "ok": False,
            "status": "error",
            "error": f"浏览器可执行文件不存在: {exe}",
        }

    target_url = ""
    if url:
        target_url = _normalize_url(url, allow_private=allow_private)
    profile = Path(STORE_DIR) / "native_browser" / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    command = [
        exe,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if target_url:
        command.append(target_url)
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            **kwargs,
        )
    except OSError as exc:
        return {"ok": False, "status": "error",
                "error": f"启动调试浏览器失败: {exc}"}

    deadline = time.monotonic() + max(2.0, float(timeout))
    while time.monotonic() < deadline:
        current = status(port=port, timeout=1.0)
        if current.get("cdp_available"):
            return _attach_window({
                "ok": True,
                "status": "launched",
                "pid": process.pid,
                "endpoint": current["endpoint"],
                "browser": current.get("browser"),
                "url": target_url or None,
                "profile_dir": str(profile),
                "tab_count": current.get("tab_count", 0),
            }, port=port)
        time.sleep(0.25)
    return {
        "ok": False,
        "status": "timeout",
        "pid": process.pid,
        "endpoint": f"http://{_CDP_HOST}:{port}",
        "error": "浏览器进程已启动，但调试端口在超时前未就绪",
        "profile_dir": str(profile),
    }


def ensure(url=None, port=None, timeout=15.0, allow_private=False,
           browser_exe=None) -> dict:
    current = status(port=port, timeout=1.5)
    if current.get("cdp_available"):
        if url:
            matched, target = _matching_tab(
                url, port=port, timeout=1.5, allow_private=allow_private)
            if matched is not None:
                return _attach_window({
                    "ok": True,
                    "status": "already_satisfied",
                    "reused": True,
                    "already_open": True,
                    "endpoint": current["endpoint"],
                    "browser": current.get("browser"),
                    "tab_id": matched.get("id"),
                    "url": target,
                    "tab_count": current.get("tab_count", 0),
                    "note": "目标页已在调试浏览器中打开，复用现有标签页，未重复导航。",
                }, port=port)
        result = {
            "ok": True,
            "status": "ready",
            "reused": True,
            "endpoint": current["endpoint"],
            "browser": current.get("browser"),
            "tab_count": current.get("tab_count", 0),
        }
    else:
        result = launch(url=None, port=port, timeout=timeout,
                        allow_private=allow_private, browser_exe=browser_exe)
        if not result.get("ok"):
            return result
        result["status"] = "launched"
    if url:
        nav = navigate(url, port=port, timeout=timeout,
                       allow_private=allow_private)
        result["navigation"] = nav
        result["ok"] = bool(nav.get("ok"))
        result["url"] = nav.get("url") or _normalize_url(
            url, allow_private=allow_private)
    return _attach_window(result, port=port)


def list_tabs(port=None, timeout=3.0) -> dict:
    tabs = _tab_rows(port, timeout)
    return {
        "ok": True,
        "tabs": tabs,
        "count": len(tabs),
        "cdp_available": bool(tabs),
    }


def create_tab(url="about:blank", port=None, timeout=8.0,
               allow_private=False) -> dict:
    if url and url != "about:blank":
        target = _normalize_url(url, allow_private=allow_private)
    else:
        target = "about:blank"
    result = _http_json(
        "/json/new?" + urllib.parse.quote(target, safe=""),
        port=port,
        timeout=timeout,
        method="PUT",
    )
    if not isinstance(result, dict):
        return {
            "ok": False,
            "status": "needs_browser_debug",
            "error": "无法创建标签页；CDP 可能未就绪或浏览器不支持 /json/new",
        }
    return {"ok": True, "tab": {
        "id": result.get("id"),
        "title": result.get("title") or "",
        "url": result.get("url") or target,
        "type": result.get("type") or "page",
    }}


def close_tab(tab_id, port=None, timeout=5.0) -> dict:
    if tab_id is None:
        raise NativeBrowserError("缺少 tab_id")
    result = _http_json(f"/json/close/{urllib.parse.quote(str(tab_id))}",
                        port=port, timeout=timeout)
    if result is None:
        return {"ok": False, "status": "needs_browser_debug",
                "error": "无法关闭标签页；CDP 未就绪"}
    return {"ok": True, "tab_id": str(tab_id), "result": result}


def activate_tab(tab_id, port=None, timeout=5.0) -> dict:
    if tab_id is None:
        raise NativeBrowserError("缺少 tab_id")
    result = _http_json(f"/json/activate/{urllib.parse.quote(str(tab_id))}",
                        port=port, timeout=timeout)
    if result is None:
        return {"ok": False, "status": "needs_browser_debug",
                "error": "无法激活标签页；CDP 未就绪"}
    return {"ok": True, "tab_id": str(tab_id), "result": result}


def navigate(url, tab_id=None, port=None, timeout=_DEFAULT_TIMEOUT,
             allow_private=False) -> dict:
    target = _normalize_url(url, allow_private=allow_private)
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        result = client.call("Page.navigate", {"url": target}, timeout=timeout)
        return {
            "ok": True,
            "tab_id": tab.get("id"),
            "url": target,
            "frame_id": result.get("frameId"),
            "loader_id": result.get("loaderId"),
        }
    finally:
        client.close()


def reload(tab_id=None, port=None, timeout=_DEFAULT_TIMEOUT,
           ignore_cache=False) -> dict:
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        client.call("Page.reload", {"ignoreCache": bool(ignore_cache)}, timeout=timeout)
        return {"ok": True, "tab_id": tab.get("id"), "reloaded": True}
    finally:
        client.close()


def _history_move(delta: int, tab_id=None, port=None,
                  timeout=_DEFAULT_TIMEOUT) -> dict:
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        history = client.call("Page.getNavigationHistory", {}, timeout=timeout)
        current = int(history.get("currentIndex", 0))
        entries = history.get("entries") or []
        wanted = current + int(delta)
        if wanted < 0 or wanted >= len(entries):
            return {"ok": False, "status": "boundary",
                    "error": "已经到达历史边界"}
        entry = entries[wanted] or {}
        client.call("Page.navigateToHistoryEntry",
                    {"entryId": entry.get("id")}, timeout=timeout)
        return {
            "ok": True,
            "tab_id": tab.get("id"),
            "url": entry.get("url"),
            "index": wanted,
        }
    finally:
        client.close()


def back(tab_id=None, port=None, timeout=_DEFAULT_TIMEOUT) -> dict:
    return _history_move(-1, tab_id, port, timeout)


def forward(tab_id=None, port=None, timeout=_DEFAULT_TIMEOUT) -> dict:
    return _history_move(1, tab_id, port, timeout)


def screenshot(tab_id=None, out=None, fmt="png", quality=80,
               full_page=False, include_data=False, port=None,
               timeout=_DEFAULT_TIMEOUT) -> dict:
    fmt = str(fmt or "png").lower()
    if fmt not in ("png", "jpeg", "webp"):
        raise NativeBrowserError("截图格式只支持 png/jpeg/webp")
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        params = {"format": fmt}
        if fmt in ("jpeg", "webp"):
            params["quality"] = max(1, min(100, int(quality)))
        if full_page:
            params["captureBeyondViewport"] = True
        result = client.call("Page.captureScreenshot", params, timeout=timeout)
        payload = str(result.get("data") or "")
        if not payload:
            return {"ok": False, "error": "浏览器没有返回截图数据"}
        raw = base64.b64decode(payload, validate=True)
        if len(raw) > _MAX_SCREENSHOT_BYTES:
            return {"ok": False, "error": "截图超过 25MB 安全上限"}
        suffix = "." + ("jpg" if fmt == "jpeg" else fmt)
        path = _safe_output_path(out, suffix=suffix)
        path.write_bytes(raw)
        response = {
            "ok": True,
            "tab_id": tab.get("id"),
            "file": str(path),
            "format": fmt,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()[:20],
        }
        if include_data:
            response["data_base64"] = payload
        return response
    finally:
        client.close()


def execute_script(js, tab_id=None, port=None,
                   timeout=_DEFAULT_TIMEOUT) -> dict:
    script = str(js or "")
    if not script:
        raise NativeBrowserError("缺少 js")
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        value = _eval_js(client, script, timeout=timeout)
        return {"ok": True, "tab_id": tab.get("id"), "result": value}
    finally:
        client.close()


def inject_script(js, tab_id=None, port=None,
                  timeout=_DEFAULT_TIMEOUT) -> dict:
    script = str(js or "")
    if not script:
        raise NativeBrowserError("缺少 js")
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        result = client.call(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": script},
            timeout=timeout,
        )
        return {
            "ok": True,
            "tab_id": tab.get("id"),
            "identifier": result.get("identifier"),
            "injected_for_new_documents": True,
        }
    finally:
        client.close()


def get_title(tab_id=None, port=None, timeout=_DEFAULT_TIMEOUT) -> dict:
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        return {"ok": True, "tab_id": tab.get("id"),
                "title": _eval_js(client, "document.title", timeout=timeout)}
    finally:
        client.close()


def get_url(tab_id=None, port=None, timeout=_DEFAULT_TIMEOUT) -> dict:
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        return {"ok": True, "tab_id": tab.get("id"),
                "url": _eval_js(client, "location.href", timeout=timeout)}
    finally:
        client.close()


def get_text(selector="body", tab_id=None, max_chars=20000, port=None,
             timeout=_DEFAULT_TIMEOUT) -> dict:
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        expression = (
            "(() => {"
            f"const e=document.querySelector({json.dumps(str(selector or 'body'))});"
            "return e ? (e.innerText || e.textContent || '') : null;"
            "})()"
        )
        value = _eval_js(client, expression, timeout=timeout)
        text = "" if value is None else str(value)
        return {
            "ok": True,
            "tab_id": tab.get("id"),
            "selector": selector or "body",
            "chars": len(text),
            "text": text[:max(1, int(max_chars))],
        }
    finally:
        client.close()


def dom_query(selector, tab_id=None, limit=50, port=None,
              timeout=_DEFAULT_TIMEOUT) -> dict:
    selector = str(selector or "")
    if not selector:
        raise NativeBrowserError("缺少 selector")
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        expression = (
            "(() => {"
            f"const nodes=[...document.querySelectorAll({json.dumps(selector)})];"
            f"return nodes.slice(0,{max(1, int(limit))}).map((e,i)=>({{"
            "index:i, tag:e.tagName, id:e.id||'', "
            "class:(typeof e.className==='string'?e.className:''), "
            "text:(e.innerText||e.textContent||'').trim().slice(0,300), "
            "value:'value' in e?String(e.value||'').slice(0,200):null, "
            "visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)"
            "}));"
            "})()"
        )
        return {
            "ok": True,
            "tab_id": tab.get("id"),
            "selector": selector,
            "elements": _eval_js(client, expression, timeout=timeout) or [],
        }
    finally:
        client.close()


def wait_for(selector, tab_id=None, timeout=10.0, interval=0.2,
             port=None) -> dict:
    selector = str(selector or "")
    if not selector:
        raise NativeBrowserError("缺少 selector")
    tab, client = _with_tab(tab_id, port=port, timeout=max(5.0, timeout + 2))
    try:
        js_timeout = max(100, int(float(timeout) * 1000))
        js_interval = max(50, int(float(interval) * 1000))
        expression = (
            "new Promise(resolve => {"
            f"const deadline=Date.now()+{js_timeout};"
            f"const selector={json.dumps(selector)};"
            "const tick=()=>{"
            "const e=document.querySelector(selector);"
            "if(e){resolve({found:true,tag:e.tagName,text:(e.innerText||e.textContent||'').slice(0,300)});return;}"
            "if(Date.now()>=deadline){resolve({found:false,timeout:true});return;}"
            f"setTimeout(tick,{js_interval});"
            "};tick();})"
        )
        value = _eval_js(client, expression, await_promise=True,
                         timeout=max(5.0, timeout + 2))
        return {
            "ok": True,
            "tab_id": tab.get("id"),
            "selector": selector,
            "found": bool((value or {}).get("found")),
            "result": value or {},
        }
    finally:
        client.close()


def _element_point(client, selector, timeout):
    """把选择器解析成「元素中心点（视口 CSS 坐标）+ 可读信息」。

    返回 (info, point)。找不到元素时 point 为 None。
    """
    expression = (
        "(() => {"
        f"const e=document.querySelector({json.dumps(str(selector))});"
        "if(!e)return {found:false};"
        "e.scrollIntoView({block:'center',inline:'center'});"
        "const r=e.getBoundingClientRect();"
        "return {found:true,tag:e.tagName,"
        "text:(e.innerText||e.textContent||'').trim().replace(/\\s+/g,' ').slice(0,120),"
        "cx:r.left+r.width/2,cy:r.top+r.height/2,"
        "w:Math.round(r.width),h:Math.round(r.height),"
        "visible:!!(r.width||r.height)};"
        "})()"
    )
    info = _eval_js(client, expression, timeout=timeout) or {}
    if not info.get("found"):
        return info, None
    return info, (float(info.get("cx") or 0.0), float(info.get("cy") or 0.0))


def _pointer_sequence(client, selector, timeout):
    """退路：在页面里发**完整**指针/鼠标事件序列。

    比 `e.click()` 强的地方：`e.click()` 只发一个 `click`，而挂在 `pointerdown` /
    `mousedown` 上的触发器（Radix 一类）**根本收不到** ⇒ 点了没反应却报成功。
    """
    expression = (
        "(() => {"
        f"const e=document.querySelector({json.dumps(str(selector))});"
        "if(!e)return {dispatched:false};"
        "e.scrollIntoView({block:'center',inline:'center'});"
        "const r=e.getBoundingClientRect();"
        "const cx=r.left+r.width/2,cy=r.top+r.height/2;"
        "const b={bubbles:true,cancelable:true,composed:true,view:window,"
        "clientX:cx,clientY:cy,screenX:cx,screenY:cy,button:0,buttons:1,detail:1,"
        "pointerId:1,pointerType:'mouse',isPrimary:true};"
        "e.dispatchEvent(new PointerEvent('pointerover',b));"
        "e.dispatchEvent(new PointerEvent('pointerenter',Object.assign({},b,{bubbles:false})));"
        "e.dispatchEvent(new MouseEvent('mouseover',b));"
        "e.dispatchEvent(new MouseEvent('mouseenter',Object.assign({},b,{bubbles:false})));"
        "e.dispatchEvent(new MouseEvent('mousemove',b));"
        "e.dispatchEvent(new PointerEvent('pointerdown',b));"
        "e.dispatchEvent(new MouseEvent('mousedown',b));"
        "e.dispatchEvent(new PointerEvent('pointerup',Object.assign({},b,{buttons:0})));"
        "e.dispatchEvent(new MouseEvent('mouseup',Object.assign({},b,{buttons:0})));"
        "e.dispatchEvent(new MouseEvent('click',Object.assign({},b,{buttons:0})));"
        "return {dispatched:true};"
        "})()"
    )
    return _eval_js(client, expression, timeout=timeout) or {}


def click_element(selector, tab_id=None, port=None,
                  timeout=_DEFAULT_TIMEOUT) -> dict:
    """点元素 —— **发真事件，不是 `e.click()`**。

    🔴 2026-09-25 实测修复（不是理论风险）：本函数原来是纯 `e.click()`，于是
       · 对挂在 `pointerdown`/`mousedown` 上的触发器（Radix 下拉菜单一类）**完全无效**，
       · 却仍然返回 `clicked:true` ⇒ **报成功但界面毫无反应**（本仓最忌的那类读数）。
       实测现场：projectaal builder 的 Build 菜单，`e.click()` 后
       `document.querySelectorAll('*').length` 前后都是 528、`aria-expanded` 仍是 false；
       换成真事件后菜单 6 项（Build/Plan/Fix/Edit/Clone/Component）当场出来。

    现在的顺序：**CDP `Input.dispatchMouseEvent`（首选）→ 完整指针序列（退路）**。
    CDP 走渲染器进程，**不经操作系统** ⇒ 窗口被遮挡、不在前台都不影响，
    这正是「无视遮挡物操作」要的那条路。
    """
    selector = str(selector or "")
    if not selector:
        raise NativeBrowserError("缺少 selector")
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        info, point = _element_point(client, selector, timeout)
        if point is None:
            return {"ok": True, "tab_id": tab.get("id"), "selector": selector,
                    "clicked": False, "via": None, "found": False,
                    "note": "选择器在页面里没命中，什么都没发（不是「点了没反应」）"}
        x, y = point
        via = "cdp-input"
        error = None
        try:
            client.call("Input.dispatchMouseEvent",
                        {"type": "mouseMoved", "x": x, "y": y,
                         "button": "none", "buttons": 0, "pointerType": "mouse"},
                        timeout=timeout)
            client.call("Input.dispatchMouseEvent",
                        {"type": "mousePressed", "x": x, "y": y, "button": "left",
                         "buttons": 1, "clickCount": 1, "pointerType": "mouse"},
                        timeout=timeout)
            client.call("Input.dispatchMouseEvent",
                        {"type": "mouseReleased", "x": x, "y": y, "button": "left",
                         "buttons": 0, "clickCount": 1, "pointerType": "mouse"},
                        timeout=timeout)
        except Exception as exc:  # noqa: BLE001 —— 退路必须真的能退
            error = f"{type(exc).__name__}: {exc}"[:200]
            via = "js-pointer-sequence"
            _pointer_sequence(client, selector, timeout)
        return {
            "ok": True,
            "tab_id": tab.get("id"),
            "selector": selector,
            "clicked": True,
            "via": via,
            "found": True,
            "box": {"x": round(x), "y": round(y),
                    "w": info.get("w"), "h": info.get("h")},
            "tag": info.get("tag"),
            "text": info.get("text"),
            "fallback_reason": error,
            "读法": "`clicked` 只说「事件已发出」，**不代表界面响应了** —— "
                    "要断言生效请另发一次 dom_query/execute_script 复核（六铁律：每步亲眼验证）",
        }
    finally:
        client.close()


def type_text(selector, text, tab_id=None, clear=True, submit=False,
              port=None, timeout=_DEFAULT_TIMEOUT) -> dict:
    """往输入框里打字 —— **走真输入，不是直接改 `e.value`**。

    🔴 2026-09-25 实测修复：本函数原来是 `e.value = value` + 手工发 `input`/`change`。
      对 **React 受控输入**这条是无效的：React 在 onChange 里用**自己缓存的 value**
      回写，直接赋 `e.value` 要么被覆盖回去、要么让 React 的 value 追踪器失真
      （经典表现：看着输进去了、但 state 没变、提交后是空的）。
      而返回值照样是 `typed:true` ⇒ 又一次「报成功但什么都没干」。

    现在的顺序：**CDP `Input.insertText`（首选，等于真实输入法插入，React 认得）
      → 原生 value setter + input 事件（退路，绕开 React 的 value 追踪器）**。
    CDP 不经操作系统 ⇒ 同样不受遮挡影响。
    """
    selector = str(selector or "")
    if not selector:
        raise NativeBrowserError("缺少 selector")
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        payload = str(text or "")
        focus_js = (
            "(() => {"
            f"const e=document.querySelector({json.dumps(selector)});"
            "if(!e)return {found:false};"
            "e.scrollIntoView({block:'center'});"
            "e.focus();"
            f"if({str(bool(clear)).lower()}){{"
            "  if(typeof e.select==='function')e.select();"
            "  else if(typeof e.setSelectionRange==='function')e.setSelectionRange(0,(e.value||'').length);"
            "} else if(typeof e.setSelectionRange==='function'){"
            "  const n=(e.value||'').length;e.setSelectionRange(n,n);"
            "}"
            "return {found:true,tag:e.tagName,before:String(e.value==null?'':e.value).length};"
            "})()"
        )
        info = _eval_js(client, focus_js, timeout=timeout) or {}
        if not info.get("found"):
            return {"ok": True, "tab_id": tab.get("id"), "selector": selector,
                    "typed": False, "via": None, "found": False,
                    "note": "选择器在页面里没命中，什么都没输入"}

        via = "cdp-insert-text"
        error = None
        try:
            client.call("Input.insertText", {"text": payload}, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"[:200]
            via = "native-value-setter"
            concat = "" if clear else "(e.value||'')+"
            fallback_js = (
                "(() => {"
                f"const e=document.querySelector({json.dumps(selector)});"
                "if(!e)return {ok:false};"
                "const proto=(e instanceof HTMLTextAreaElement)"
                "  ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;"
                "const d=Object.getOwnPropertyDescriptor(proto,'value');"
                f"const v={json.dumps(payload)};"
                f"const next={concat}v;"
                "if(d&&d.set)d.set.call(e,next);else e.value=next;"
                "e.dispatchEvent(new Event('input',{bubbles:true}));"
                "e.dispatchEvent(new Event('change',{bubbles:true}));"
                "return {ok:true,length:String(e.value||'').length};"
                "})()"
            )
            _eval_js(client, fallback_js, timeout=timeout)

        submitted = False
        if submit:
            try:
                for kind in ("keyDown", "keyUp"):
                    client.call("Input.dispatchKeyEvent", {
                        "type": kind, "key": "Enter", "code": "Enter",
                        "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13,
                        "text": "\r" if kind == "keyDown" else "",
                    }, timeout=timeout)
                submitted = True
            except Exception as exc:  # noqa: BLE001
                error = (error or "") + (" | Enter: %s: %s" % (type(exc).__name__, exc))[:160]

        after = _eval_js(
            client,
            "(() => {const e=document.querySelector(%s);"
            "return e?String(e.value==null?'':e.value).length:-1;})()" % json.dumps(selector),
            timeout=timeout)
        return {
            "ok": True, "tab_id": tab.get("id"), "selector": selector,
            "typed": True, "via": via, "found": True,
            "chars_sent": len(payload),
            "value_len_before": info.get("before"),
            "value_len_after": after,
            "submitted": submitted,
            "fallback_reason": error,
            "读法": "`typed` 只说「字已发出」；`value_len_after` 才是页面真实读数 —— "
                    "**两者对不上就是没打进去**（六铁律：每步亲眼验证）",
        }
    finally:
        client.close()


def get_cookies(url=None, tab_id=None, port=None, include_values=False,
               timeout=_DEFAULT_TIMEOUT) -> dict:
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        params = {"urls": [url]} if url else {}
        result = client.call("Network.getAllCookies", params, timeout=timeout)
        cookies = result.get("cookies") or []
        safe = []
        for cookie in cookies[:100]:
            if not isinstance(cookie, dict):
                continue
            item = dict(cookie)
            if not include_values:
                item["value"] = _mask_secret(item.get("value"))
            safe.append(item)
        return {
            "ok": True,
            "tab_id": tab.get("id"),
            "cookie_count": len(cookies),
            "cookies": safe,
            "values_masked": not bool(include_values),
            "note": (
                "Cookie 值默认脱敏，避免把凭据带入对话或日志。"
                if not include_values else
                "主人显式请求了 Cookie 明文；结果不会写入审计日志。"
            ),
        }
    finally:
        client.close()


def set_cookies(cookies, url=None, tab_id=None, port=None,
                timeout=_DEFAULT_TIMEOUT) -> dict:
    if not isinstance(cookies, list) or not cookies:
        raise NativeBrowserError("cookies 必须是非空列表")
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    try:
        params = {"cookies": cookies}
        if url:
            params["url"] = _normalize_url(url, allow_private=True)
        client.call("Network.setCookies", params, timeout=timeout)
        return {"ok": True, "tab_id": tab.get("id"),
                "set_count": len(cookies), "values_echoed": False}
    finally:
        client.close()


def privacy_mode(url=None, tab_id=None, port=None,
                 timeout=_DEFAULT_TIMEOUT) -> dict:
    tab, client = _with_tab(tab_id, port=port, timeout=timeout)
    cleared = []
    try:
        client.call("Network.clearBrowserCookies", {}, timeout=timeout)
        cleared.append("cookies")
        client.call("Browser.clearBrowserCache", {}, timeout=timeout)
        cleared.append("cache")
        if url:
            origin = "{0.scheme}://{0.netloc}".format(
                urllib.parse.urlsplit(_normalize_url(url, allow_private=True)))
            client.call("Storage.clearDataForOrigin", {
                "origin": origin,
                "storageTypes": "all",
            }, timeout=timeout)
            cleared.append(f"origin:{origin}")
        return {
            "ok": True,
            "tab_id": tab.get("id"),
            "mode": "privacy",
            "cleared": cleared,
        }
    finally:
        client.close()


class _NetworkMonitor:
    def __init__(self, tab: dict, patterns: list[str], max_events=500):
        self.tab = tab
        self.patterns = list(patterns or [])
        self.max_events = max(20, int(max_events))
        self.ws = _CdpWebSocket(tab.get("webSocketDebuggerUrl") or "",
                                timeout=_DEFAULT_TIMEOUT)
        self.events: list[dict] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.started_at = time.time()
        self.error = ""

    def start(self):
        self.ws.connect()
        self.ws.call("Network.enable", {}, timeout=8)
        if self.patterns:
            self.ws.call("Fetch.enable", {
                "patterns": [
                    {"urlPattern": pattern, "requestStage": "Request"}
                    for pattern in self.patterns
                ]
            }, timeout=8)
        self._thread = threading.Thread(
            target=self._loop,
            name=f"gbt-cdp-network-{self.tab.get('id')}",
            daemon=True,
        )
        self._thread.start()

    def _append(self, event: dict):
        with self._lock:
            self.events.append(event)
            if len(self.events) > self.max_events:
                del self.events[:len(self.events) - self.max_events]

    def _loop(self):
        try:
            while not self._stop.is_set():
                message = self.ws.recv_json(timeout=1.0)
                method = str(message.get("method") or "")
                params = message.get("params") or {}
                if method == "Fetch.requestPaused":
                    request_id = params.get("requestId")
                    self._append({
                        "ts": time.time(),
                        "type": "request_paused",
                        "request_id": request_id,
                        "url": params.get("request", {}).get("url"),
                        "method": params.get("request", {}).get("method"),
                        "resource_type": params.get("resourceType"),
                    })
                    if request_id:
                        self.ws.call("Fetch.continueRequest",
                                     {"requestId": request_id}, timeout=5)
                elif method in ("Network.requestWillBeSent",
                                "Network.responseReceived",
                                "Network.loadingFailed"):
                    request = params.get("request") or {}
                    response = params.get("response") or {}
                    self._append({
                        "ts": time.time(),
                        "type": method.split(".", 1)[-1],
                        "request_id": params.get("requestId"),
                        "url": request.get("url") or response.get("url"),
                        "method": request.get("method"),
                        "status": response.get("status"),
                        "resource_type": params.get("type"),
                        "error": params.get("errorText"),
                    })
        except Exception as exc:  # noqa: BLE001
            if not self._stop.is_set():
                self.error = f"{type(exc).__name__}: {exc}"[:240]
        finally:
            self.ws.close()

    def snapshot(self, limit=100) -> dict:
        with self._lock:
            events = self.events[-max(1, int(limit)):]
        return {
            "ok": True,
            "tab_id": self.tab.get("id"),
            "running": not self._stop.is_set(),
            "patterns": self.patterns,
            "event_count": len(self.events),
            "events": events,
            "error": self.error or None,
        }

    def stop(self) -> dict:
        self._stop.set()
        self.ws.close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        return {
            "ok": True,
            "tab_id": self.tab.get("id"),
            "stopped": True,
            "event_count": len(self.events),
            "error": self.error or None,
        }


_monitors: dict[str, _NetworkMonitor] = {}
_monitors_lock = threading.Lock()


def intercept_requests(tab_id=None, patterns=None, max_events=500,
                       port=None) -> dict:
    tab, _client = _with_tab(tab_id, port=port, timeout=8)
    _client.close()
    key = str(tab.get("id"))
    patterns = patterns if isinstance(patterns, list) else []
    patterns = [str(item) for item in patterns if str(item).strip()]
    with _monitors_lock:
        old = _monitors.pop(key, None)
    if old is not None:
        old.stop()
    monitor = _NetworkMonitor(tab, patterns, max_events=max_events)
    try:
        monitor.start()
    except Exception as exc:  # noqa: BLE001
        monitor.stop()
        return {"ok": False, "status": "error",
                "error": f"启动网络监听失败: {exc}"}
    with _monitors_lock:
        _monitors[key] = monitor
    return {
        "ok": True,
        "tab_id": tab.get("id"),
        "running": True,
        "patterns": patterns,
        "note": "命中监听规则的请求会自动放行，不会卡死页面。",
    }


def intercept_events(tab_id=None, limit=100) -> dict:
    rows = list(_monitors.values())
    if tab_id is not None:
        rows = [row for row in rows if str(row.tab.get("id")) == str(tab_id)]
    if not rows:
        return {"ok": False, "status": "not_running",
                "error": "没有活跃的网络监听会话"}
    if len(rows) == 1:
        return rows[0].snapshot(limit=limit)
    return {"ok": True, "monitors": [row.snapshot(limit=limit) for row in rows]}


def intercept_status() -> dict:
    rows = [row.snapshot(limit=5) for row in list(_monitors.values())]
    return {"ok": True, "count": len(rows), "monitors": rows}


def intercept_stop(tab_id=None) -> dict:
    rows = []
    with _monitors_lock:
        if tab_id is None:
            keys = list(_monitors)
            rows = [_monitors.pop(key) for key in keys]
        else:
            row = _monitors.pop(str(tab_id), None)
            if row is not None:
                rows.append(row)
    if not rows:
        return {"ok": True, "stopped": 0}
    return {"ok": True, "stopped": len(rows),
            "results": [row.stop() for row in rows]}


def run(action="status", **params) -> dict:
    """原生浏览器统一入口；异常如实返回。"""
    action = str(action or "status").strip().lower()
    if action not in _ACTIONS:
        return {
            "ok": False,
            "status": "error",
            "error": f"未知原生浏览器动作: {action}",
            "available": list(_ACTIONS),
        }
    handlers = {
        "status": status,
        "launch": launch,
        "ensure": ensure,
        "list_tabs": list_tabs,
        "create_tab": create_tab,
        "close_tab": close_tab,
        "activate_tab": activate_tab,
        "navigate": navigate,
        "reload": reload,
        "back": back,
        "forward": forward,
        "screenshot": screenshot,
        "get_title": get_title,
        "get_url": get_url,
        "get_text": get_text,
        "dom_query": dom_query,
        "wait_for": wait_for,
        "click_element": click_element,
        "type_text": type_text,
        "execute_script": execute_script,
        "inject_script": inject_script,
        "get_cookies": get_cookies,
        "set_cookies": set_cookies,
        "privacy_mode": privacy_mode,
        "intercept_requests": intercept_requests,
        "intercept_events": intercept_events,
        "intercept_status": intercept_status,
        "intercept_stop": intercept_stop,
        "pin_window": pin_window,
    }
    try:
        result = handlers[action](**params)
        if isinstance(result, dict):
            result.setdefault("action", action)
            result.setdefault("cap", "native_browser")
            result.setdefault("backend", "chrome-devtools-protocol")
        return result
    except (NativeBrowserError, ValueError, TypeError, KeyError) as exc:
        return {
            "ok": False,
            "action": action,
            "cap": "native_browser",
            "backend": "chrome-devtools-protocol",
            "status": "error",
            "error": str(exc)[:300],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "action": action,
            "cap": "native_browser",
            "backend": "chrome-devtools-protocol",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }


def capabilities() -> dict:
    return {
        "ok": True,
        "actions": list(_ACTIONS),
        "read_only_actions": sorted(_READ_ONLY_ACTIONS),
        "transport": "standard-library-rfc6455",
        "needs": "Chrome/Edge/Brave/Chromium with remote debugging enabled",
    }
