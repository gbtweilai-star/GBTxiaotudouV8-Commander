# gbt-capability: socket, network
"""统一网络边界：URL 校验、DNS 结果检查、连接目标固定与响应体限额。

未授权模式只允许公网 HTTP(S) 目标，阻断 loopback、私网、链路本地、保留地址和
云元数据地址。授权模式不删除能力，而是允许主人显式放行自有内网目标。
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import urllib.parse
from dataclasses import dataclass
from typing import Iterable


class NetworkGuardError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedURL:
    url: str
    scheme: str
    host: str
    port: int
    pinned_ip: str
    addresses: tuple[str, ...]

    @property
    def path(self) -> str:
        parsed = urllib.parse.urlsplit(self.url)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        return path


def _ip_obj(value: str) -> ipaddress._BaseAddress | None:
    try:
        return ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return None


def blocked_ip_reason(ip: str) -> str:
    obj = _ip_obj(ip)
    if obj is None:
        return "无法识别 IP"
    if obj.is_loopback:
        return "loopback"
    if obj.is_private:
        return "private"
    if obj.is_link_local:
        return "link-local"
    if obj.is_reserved:
        return "reserved"
    if obj.is_multicast:
        return "multicast"
    if obj.is_unspecified:
        return "unspecified"
    if not obj.is_global:
        return "non-global"
    return ""


def resolve_host(host: str) -> tuple[str, ...]:
    host = (host or "").strip().rstrip(".")
    if not host:
        raise NetworkGuardError("缺少主机名")
    literal = _ip_obj(host)
    if literal is not None:
        return (str(literal),)
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise NetworkGuardError(f"域名解析失败: {exc}") from exc
    values = []
    for info in infos:
        ip = info[4][0].split("%", 1)[0]
        if ip not in values:
            values.append(ip)
    if not values:
        raise NetworkGuardError("域名没有可用地址")
    return tuple(values)


def validate_host(host: str, *, allow_private: bool = False) -> tuple[str, ...]:
    addresses = resolve_host(host)
    if allow_private:
        return addresses
    blocked = [(ip, blocked_ip_reason(ip)) for ip in addresses if blocked_ip_reason(ip)]
    if blocked:
        detail = ", ".join(f"{ip}({why})" for ip, why in blocked[:4])
        raise NetworkGuardError(f"目标指向非公网地址: {detail}")
    return addresses


def validate_url(url: str, *, allow_private: bool = False) -> ValidatedURL:
    raw = str(url or "").strip()
    if not raw:
        raise NetworkGuardError("缺少 url")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme.lower() not in ("http", "https"):
        raise NetworkGuardError("只允许 http:// 或 https:// URL")
    if parsed.username or parsed.password:
        raise NetworkGuardError("URL 不允许包含内嵌用户名或密码")
    try:
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise NetworkGuardError(f"URL 端口无效: {exc}") from exc
    if port not in (80, 443) and not allow_private:
        raise NetworkGuardError("未授权模式只允许标准 HTTP/HTTPS 端口")
    addresses = validate_host(host, allow_private=allow_private)
    return ValidatedURL(raw, parsed.scheme.lower(), host, port, addresses[0], addresses)


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, pinned_ip: str, timeout: float):
        super().__init__(host, port=port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self):
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, pinned_ip: str, timeout: float,
                 context: ssl.SSLContext):
        super().__init__(host, port=port, timeout=timeout, context=context)
        self._pinned_ip = pinned_ip

    def connect(self):
        raw = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def _decode_headers(response: http.client.HTTPResponse) -> dict[str, str]:
    return {str(k): str(v) for k, v in response.getheaders()}


def safe_request(url: str, *, method: str = "GET", headers: dict | None = None,
                 body: bytes | None = None, timeout: float = 20.0,
                 max_bytes: int = 2_000_000, allow_private: bool = False,
                 max_redirects: int = 5) -> dict:
    """固定 DNS 解析结果后发起 HTTP 请求，并在每一跳重新校验边界。"""
    current = str(url or "")
    request_headers = dict(headers or {})
    request_headers.setdefault("User-Agent", "Mozilla/5.0 GBT-V8/1.0")
    current_method = method.upper()
    current_body = body
    redirects = []
    for _ in range(max(0, int(max_redirects)) + 1):
        v = validate_url(current, allow_private=allow_private)
        if v.scheme == "https":
            conn = PinnedHTTPSConnection(
                v.host, v.port, v.pinned_ip, float(timeout), ssl.create_default_context())
        else:
            conn = PinnedHTTPConnection(v.host, v.port, v.pinned_ip, float(timeout))
        try:
            conn.request(current_method, v.path, body=current_body, headers=request_headers)
            response = conn.getresponse()
            limit = max(1, int(max_bytes))
            chunks = []
            total = 0
            truncated = False
            while True:
                chunk = response.read(min(65536, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    truncated = True
                    break
            raw = b"".join(chunks)[:limit]
            status = int(response.status)
            response_headers = _decode_headers(response)
            if status in (301, 302, 303, 307, 308) and response_headers.get("Location"):
                next_url = urllib.parse.urljoin(current, response_headers["Location"])
                redirects.append({"from": current, "to": next_url, "status": status})
                current = next_url
                if status == 303:
                    current_method, current_body = "GET", None
                continue
            return {
                "url": current,
                "status": status,
                "headers": response_headers,
                "body": raw,
                "bytes": len(raw),
                "truncated": truncated,
                "resolved_ip": v.pinned_ip,
                "redirects": redirects,
            }
        finally:
            conn.close()
    raise NetworkGuardError(f"重定向次数超过上限: {max_redirects}")


def safe_get(url: str, *, timeout: float = 20.0, max_bytes: int = 2_000_000,
             headers: dict | None = None, allow_private: bool = False) -> dict:
    return safe_request(url, method="GET", headers=headers, timeout=timeout,
                        max_bytes=max_bytes, allow_private=allow_private)


def safe_request_json(url: str, *, method: str = "GET", headers: dict | None = None,
                      body: bytes | None = None, timeout: float = 20.0,
                      max_bytes: int = 2_000_000, allow_private: bool = False,
                      max_redirects: int = 5) -> dict:
    """统一安全请求 + JSON 解码；保留 HTTP 状态和原始文本用于如实报错。"""
    import json

    response = safe_request(
        url, method=method, headers=headers, body=body, timeout=timeout,
        max_bytes=max_bytes, allow_private=allow_private,
        max_redirects=max_redirects,
    )
    raw = response.pop("body", b"")
    text = raw.decode("utf-8", errors="replace")
    response["text"] = text
    try:
        response["json"] = json.loads(text)
    except Exception:
        response["json"] = None
    return response
