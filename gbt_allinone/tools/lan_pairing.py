# -*- coding: utf-8 -*-
# gbt-capability: lan_pairing  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""局域网配对监听 / 自签证书（P2-12 继续，主人 2026-11-03 批准）。

边界（按主人口径）：
  · 只绑 **一个局域网私有 IPv4**（或 loopback 调试）；拒绝 0.0.0.0/公网；
  · 端口 8767..8770；TLS（自签证书），证书/私钥放 `state/`，私钥权限收窄；
  · 鉴权：一次性配对码换取 Bearer device token；status 必须带 token；
  · 只开配对服务：health / pair / status；**没有远程命令/文件/执行接口**；
  · 自签不是 CA：客户端必须 pin 指纹；没有证书链/轮换/吊销分发。
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import secrets
import socket
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
CERT_PATH = _ROOT / "state" / "pairing-cert.pem"
KEY_PATH = _ROOT / "state" / "pairing-key.pem"
DEFAULT_PORT = 8767
PORTS = (8767, 8768, 8769, 8770)
MAX_BODY = 8192


class LanError(ValueError):
    pass


def _fingerprint(cert_pem: str) -> str:
    der = ssl.PEM_cert_to_DER_cert(cert_pem)
    h = hashlib.sha256(der).hexdigest().upper()
    return ":".join(h[i:i + 2] for i in range(0, len(h), 2))


def _private_ip() -> str:
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = str(info[4][0])
            try:
                a = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if a.is_private and not a.is_loopback and not a.is_link_local:
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def resolve_bind(host="loopback") -> tuple[str, str]:
    """只允许 loopback / lan / 显式私有 IPv4。返回 (bind_ip, mode)。"""
    h = str(host or "loopback").strip().lower()
    if h in ("loopback", "localhost", "127.0.0.1"):
        return "127.0.0.1", "loopback"
    if h == "lan":
        ip = _private_ip()
        return ip, "lan" if ip != "127.0.0.1" else "loopback"
    try:
        a = ipaddress.ip_address(h)
    except ValueError:
        raise LanError("host 只许 loopback/lan/私有 IPv4")
    if a.is_loopback:
        return str(a), "loopback"
    if not a.is_private or a.is_link_local or a.is_unspecified or a.is_multicast:
        raise LanError("拒绝公网/通配/链路本地地址；只许私有局域网 IP")
    return str(a), "lan"


def ensure_cert(cert_path=CERT_PATH, key_path=KEY_PATH, extra_hosts=None) -> dict:
    """自签证书（不存在才生成；已存在不覆盖）。私钥权限收窄。"""
    cert_path = Path(cert_path)
    key_path = Path(key_path)
    if cert_path.is_file() and key_path.is_file():
        try:
            pem = cert_path.read_text(encoding="utf-8")
            return {"ok": True, "created": False, "fingerprint": _fingerprint(pem),
                    "cert": str(cert_path), "key": str(key_path)}
        except Exception:  # noqa: BLE001
            pass
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import datetime
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "cryptography 不可用（TLS 签发依赖）: %s" % type(e).__name__}
    now = datetime.datetime.now(datetime.timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "GBT Pairing Local")])
    san = [x509.DNSName("gbt-pairing.local"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    hosts = set(extra_hosts or [])
    lan = _private_ip()
    if lan != "127.0.0.1":
        hosts.add(lan)
    for h in sorted(hosts):
        try:
            san.append(x509.IPAddress(ipaddress.ip_address(h)))
        except ValueError:
            san.append(x509.DNSName(h))
    cert = (x509.CertificateBuilder()
            .subject_name(subject).issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    try:
        os.chmod(key_path, 0o600)
        os.chmod(cert_path, 0o644)
    except OSError:
        pass
    return {"ok": True, "created": True, "fingerprint": _fingerprint(cert_path.read_text(encoding="utf-8")),
            "cert": str(cert_path), "key": str(key_path)}


def cert_info(cert_path=CERT_PATH, key_path=KEY_PATH) -> dict:
    if not (Path(cert_path).is_file() and Path(key_path).is_file()):
        return {"ok": False, "error": "证书未生成（用 start 生成）", "cert": str(cert_path)}
    try:
        fp = _fingerprint(Path(cert_path).read_text(encoding="utf-8"))
        return {"ok": True, "fingerprint": fp, "cert": str(cert_path),
                "key": str(key_path), "key_in_state": True,
                "note": "自签；客户端必须 pin 指纹；私钥不外发"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "证书读取失败: %s" % type(e).__name__}


def _default_pair(code: str, name: str) -> dict:
    from . import pairing as _pairing
    return _pairing.run("claim", code=code, name=name)


def _default_token_ok(token: str) -> dict:
    from . import pairing as _pairing
    if not token:
        return {"ok": False}
    h = hashlib.sha256(token.encode("utf-8")).hexdigest()
    try:
        rows = _pairing._BOARD._load()
    except Exception:  # noqa: BLE001
        return {"ok": False}
    for r in rows:
        if r.get("status") == "active" and r.get("token_sha256") == h:
            return {"ok": True, "device": {"id": r.get("id"), "name": r.get("name")}}
    return {"ok": False}


class _Handler(BaseHTTPRequestHandler):
    server_version = "GBTPairing/1.0"

    def log_message(self, fmt, *args):  # noqa: A003
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            n = 0
        if n > MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(max(0, n)).decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001
            return None

    def do_GET(self):  # noqa: N802
        if self.path == "/api/lan/health":
            return self._json(200, {"ok": True, "service": "gbt-lan-pairing", "version": 1,
                                    "fingerprint": self.server.fingerprint,
                                    "auth": False, "commands": False})
        if self.path == "/api/lan/status":
            auth = self.headers.get("Authorization") or ""
            token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
            got = self.server.token_ok(token)
            if not got.get("ok"):
                return self._json(401, {"ok": False, "error": "unauthorized"})
            return self._json(200, {"ok": True, "device": got.get("device"),
                                    "fingerprint": self.server.fingerprint,
                                    "commands": False})
        return self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/api/lan/pair":
            return self._json(404, {"ok": False, "error": "not found"})
        body = self._body()
        if not isinstance(body, dict):
            return self._json(400, {"ok": False, "error": "invalid json"})
        got = self.server.pair_fn(str(body.get("code") or ""), str(body.get("name") or ""))
        return self._json(200 if got.get("ok") else 400, got)


class LanServer:
    def __init__(self, host="loopback", port=DEFAULT_PORT, cert_path=CERT_PATH,
                 key_path=KEY_PATH, pair_fn=None, token_ok=None):
        self.host = host
        self.port = int(port)
        self.cert_path = Path(cert_path)
        self.key_path = Path(key_path)
        self.pair_fn = pair_fn or _default_pair
        self.token_ok = token_ok or _default_token_ok
        self.httpd = None
        self.thread = None
        self.bind_ip = ""
        self.mode = ""
        self.fingerprint = ""

    def start(self) -> dict:
        if self.httpd is not None:
            return self.status()
        if self.port not in PORTS:
            return {"ok": False, "error": "port 只许 %s" % (PORTS,)}
        try:
            bind_ip, mode = resolve_bind(self.host)
        except LanError as e:
            return {"ok": False, "error": "user_error: %s" % e}
        cert = ensure_cert(self.cert_path, self.key_path, extra_hosts=[bind_ip])
        if not cert.get("ok"):
            return cert
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        try:
            ctx.load_cert_chain(str(self.cert_path), str(self.key_path))
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "TLS 证书加载失败: %s" % type(e).__name__}
        try:
            httpd = ThreadingHTTPServer((bind_ip, self.port), _Handler)
        except OSError as e:
            return {"ok": False, "error": "绑定失败（端口占用/权限）: %s" % e}
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        httpd.pair_fn = self.pair_fn
        httpd.token_ok = self.token_ok
        httpd.fingerprint = cert["fingerprint"]
        self.httpd = httpd
        self.bind_ip = bind_ip
        self.mode = mode
        self.fingerprint = cert["fingerprint"]
        self.thread = threading.Thread(target=httpd.serve_forever,
                                       kwargs={"poll_interval": 0.2}, daemon=True)
        self.thread.start()
        return self.status()

    def stop(self) -> dict:
        if self.httpd is None:
            return {"ok": True, "running": False, "stopped": False}
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        finally:
            self.httpd = None
            self.thread = None
        return {"ok": True, "running": False, "stopped": True}

    def status(self) -> dict:
        running = self.httpd is not None
        return {"ok": True, "running": running, "bind": self.bind_ip or "",
                "mode": self.mode or "", "port": self.port,
                "url": ("https://%s:%d" % (self.bind_ip, self.port)) if running and self.bind_ip else "",
                "fingerprint": self.fingerprint, "tls": True,
                "commands": False,
                "exposure": "loopback" if self.mode == "loopback" else "private-lan"}


_SERVER = LanServer()


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    ck("loopback 解析", resolve_bind("loopback") == ("127.0.0.1", "loopback"))
    ck("lan 落在私有/回环", resolve_bind("lan")[0] != "0.0.0.0")
    ck("拒公网", _raises(lambda: resolve_bind("8.8.8.8")))
    ck("拒通配", _raises(lambda: resolve_bind("0.0.0.0")))
    ck("拒非法 host", _raises(lambda: resolve_bind("evil.example.com")))
    ck("端口白名单", LanServer(port=9999).start().get("ok") is False)
    import tempfile
    d = tempfile.mkdtemp(prefix="gbt-lan-")
    cert = ensure_cert(Path(d) / "c.pem", Path(d) / "k.pem")
    ck("证书生成", cert.get("ok") is True and cert.get("created") is True, cert)
    ck("指纹格式", ":" in cert.get("fingerprint", ""))
    ck("私钥在 state", Path(d).joinpath("k.pem").is_file())
    ck("证书信息", cert_info(Path(d) / "c.pem", Path(d) / "k.pem").get("ok") is True)
    ck("证书不覆盖", ensure_cert(Path(d) / "c.pem", Path(d) / "k.pem").get("created") is False)
    ck("schema 边界", "exposure" in run("schema") and "commands" in run("schema"))
    ck("默认未启动", run("status")["running"] is False)
    ck("stop 幂等", run("stop")["ok"] is True)
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (LanError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "ports": list(PORTS), "hosts": ["loopback", "lan", "private-ipv4"],
                "exposure": "只绑一个私有 LAN IPv4 / loopback；拒 0.0.0.0/公网",
                "tls": "自签 RSA-2048；cert/key 放 state/；私钥 0600",
                "auth": "一次性配对码换 Bearer device token；status 必须带 token",
                "commands": False, "ca": False, "rotation": False,
                "note": "只有 health/pair/status；没有远程命令/文件接口"}
    if op == "start":
        _SERVER.host = params.get("host") or "loopback"
        _SERVER.port = int(params.get("port") or DEFAULT_PORT)
        _SERVER.cert_path = Path(params.get("cert_path") or CERT_PATH)
        _SERVER.key_path = Path(params.get("key_path") or KEY_PATH)
        return _SERVER.start()
    if op == "stop":
        return _SERVER.stop()
    if op == "status":
        return _SERVER.status()
    if op == "cert":
        return cert_info()
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/start/stop/status/cert/verify）" % op)
