# -*- coding: utf-8 -*-
"""gbt_allinone.integration.platform_client — 平台侧调用收款钱包 HTTP API 的轻量客户端。

只依赖标准库(urllib), 不引入任何第三方包:
  - 基址: GBT_WALLET_API_BASE, 默认 http://127.0.0.1:8097
  - 令牌: GBT_WALLET_API_TOKEN(可选) -> 自动附加 `Authorization: Bearer <token>`

典型用法::

    from gbt_allinone.integration.platform_client import WalletClient
    c = WalletClient()
    c.health()
    inv = c.create_invoice("u_1001", 19.9, "USDC.E")   # 开票并登记 发票->用户 映射
    c.list_invoices()                                   # 未付/已付
    c.scan()                                            # 触发链上扫描(到账->paid)
    c.balances()                                        # 地址余额快照
    c.events(since=1710000000)                          # 事件轮询(含发票/扫描审计)

错误: 统一抛 WalletApiError(含 status/payload/retryable); 网络与 5xx 按策略重试。
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_ENV = "GBT_WALLET_API_BASE"
TOKEN_ENV = "GBT_WALLET_API_TOKEN"
IDEM_ENV = "GBT_PLATFORM_IDEM_FILE"
DEFAULT_BASE = "http://127.0.0.1:8097"

# 天然幂等的写操作: 可安全重试(服务端按游标/逐发票 credited_int 去重)
_IDEMPOTENT_POSTS = ("/api/gbtwallet/scan",)
_SLOW_PATHS = ("/api/gbtwallet/scan", "/api/gbtwallet/balances")


class WalletApiError(RuntimeError):
    """钱包 API 调用失败; retryable=True 表示可择机重试。"""

    def __init__(self, message, status=None, payload=None, retryable=False):
        super().__init__(message)
        self.status = status
        self.payload = payload if payload is not None else {}
        self.retryable = bool(retryable)

    def __str__(self):                                  # pragma: no cover - 展示用
        base = super().__str__()
        return f"{base} (status={self.status})" if self.status else base


def default_base() -> str:
    return (os.environ.get(BASE_ENV) or DEFAULT_BASE).rstrip("/")


def default_token() -> str:
    return (os.environ.get(TOKEN_ENV) or "").strip()


def _idem_path():
    p = os.environ.get(IDEM_ENV)
    if p:
        return p
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "store", "platform_idem.json")


class WalletClient:
    """钱包 API 轻量客户端(线程内复用即可; 不持有连接)。"""

    def __init__(self, base=None, token=None, timeout=10.0, retries=2, backoff=0.4,
                 opener=None, idem_file=None):
        self.base = (base or default_base()).rstrip("/")
        self.token = default_token() if token is None else (token or "")
        self.timeout = float(timeout)
        self.retries = int(retries)
        self.backoff = float(backoff)
        self._opener = opener or urllib.request.urlopen
        self._idem_file = idem_file if idem_file is not None else _idem_path()

    # ---------- 传输层 ----------

    def _url(self, path, query=None):
        url = self.base + path
        if query:
            clean = {k: v for k, v in query.items() if v is not None}
            if clean:
                url += "?" + urllib.parse.urlencode(clean)
        return url

    def _headers(self):
        h = {"Accept": "application/json", "User-Agent": "gbt-platform-client/1.0"}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        return h

    def _open(self, req, timeout):
        return self._opener(req, timeout=timeout)

    def call(self, method, path, payload=None, query=None, timeout=None, retries=None):
        """底层调用: 返回解析后的 JSON dict; 失败抛 WalletApiError。"""
        method = method.upper()
        retryable = (method == "GET") or (path in _IDEMPOTENT_POSTS)
        attempts = (self.retries if retryable else 0) if retries is None else int(retries)
        tmo = float(timeout or (max(self.timeout, 60.0) if path in _SLOW_PATHS else self.timeout))
        data = None
        headers = self._headers()
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        url = self._url(path, query)

        last = None
        for attempt in range(attempts + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with self._open(req, tmo) as resp:
                    raw = resp.read()
                    return self._decode(raw, getattr(resp, "status", 200))
            except urllib.error.HTTPError as e:                     # 4xx/5xx 有响应体
                body = b""
                try:
                    body = e.read()
                except Exception:                                   # noqa: BLE001
                    pass
                parsed = self._decode(body, e.code, strict=False)
                err = WalletApiError(parsed.get("detail") or parsed.get("error") or str(e),
                                     status=e.code, payload=parsed, retryable=e.code >= 500)
                if not err.retryable or attempt >= attempts:
                    raise err
                last = err
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
                err = WalletApiError(f"连接钱包服务失败: {e}", retryable=retryable)
                if attempt >= attempts:
                    raise err
                last = err
            if attempt < attempts:
                time.sleep(self.backoff * (2 ** attempt))
        raise last or WalletApiError("调用失败")                     # pragma: no cover

    @staticmethod
    def _decode(raw, status, strict=True):
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw or "")
        if not text.strip():
            return {} if strict else {"raw": ""}
        try:
            obj = json.loads(text)
        except Exception:                                           # noqa: BLE001
            return {} if strict else {"raw": text[:500]}
        if strict and isinstance(obj, dict) and obj.get("ok") is False:
            raise WalletApiError(obj.get("detail") or obj.get("error") or "钱包返回 ok=false",
                                 status=status, payload=obj)
        return obj

    # ---------- 业务接口 ----------

    def health(self):
        """服务与钱包状态: initialized / dir / master_evm / invoices / pending。"""
        return self.call("GET", "/api/gbtwallet/health")

    def create_invoice(self, user, amount, currency="USDC.E", label="", expires_hours=72,
                       idempotency_key=None):
        """开票(POST /invoice)并登记 发票->用户 映射; 返回含 user 的发票 dict。

        idempotency_key 非空时, 同一 key 重复调用直接返回首次结果(本地幂等表)。
        """
        if idempotency_key:
            cached = self._idem_get(idempotency_key)
            if cached:
                return cached
        resp = self.call("POST", "/api/gbtwallet/invoice",
                         {"amount": float(amount), "currency": currency,
                          "label": label, "expires_hours": int(expires_hours)})
        inv = dict(resp.get("invoice") or {})
        self._bind_user(inv, user, currency)
        inv["user"] = user
        if idempotency_key:
            self._idem_put(idempotency_key, inv)
        return inv

    def list_invoices(self, status=None, user=None):
        """发票列表; status in (pending/partial/paid); user 非空时按映射过滤。"""
        rows = list(self.call("GET", "/api/gbtwallet/invoices",
                              query={"status": status}).get("invoices") or [])
        if user is None:
            return rows
        m = self._load_map()
        return [r for r in rows if (m.get(r.get("invoice_id")) or {}).get("user") == user]

    def get_invoice(self, invoice_id):
        for r in self.list_invoices():
            if r.get("invoice_id") == invoice_id:
                return r
        return None

    def scan(self):
        """触发链上增量扫描(把到账写成 paid/partial); 幂等, 可安全重试。"""
        return self.call("POST", "/api/gbtwallet/scan")

    def balances(self):
        """各收款地址余额快照(只读, 走 RPC)。"""
        return self.call("GET", "/api/gbtwallet/balances")

    def events(self, since=None, limit=200):
        """事件轮询: since=epoch 秒, 只取 t>=since 的事件; 返回事件列表(新在前)。"""
        return list(self.call("GET", "/api/gbtwallet/events",
                              query={"since": None if since is None else int(since),
                                     "limit": int(limit)}).get("events") or [])

    def monitor(self):
        """运行总览(各台账计数); 供巡检/告警。"""
        return self.call("GET", "/api/gbtwallet/monitor")

    def wait_for_health(self, timeout=30.0, interval=1.0):
        """轮询直到 health 可用; 超时抛 WalletApiError。"""
        deadline = time.time() + float(timeout)
        last = None
        while time.time() < deadline:
            try:
                return self.health()
            except WalletApiError as e:
                last = e
                time.sleep(interval)
        raise last or WalletApiError("等待钱包服务健康超时")

    # ---------- 发票->用户 映射(与 deposit_bridge 共用同一文件) ----------

    @staticmethod
    def _load_map():
        try:
            from ..bridge import deposit_bridge as DB
            return DB.load_map()
        except Exception:                                       # noqa: BLE001
            return {}

    def _bind_user(self, invoice, user, currency):
        """登记 invoice_id -> user, 供 deposit_bridge 扫描后自动记账到账本。"""
        inv_id = invoice.get("invoice_id")
        if not inv_id or not user:
            return False
        try:
            from ..bridge import deposit_bridge as DB
            m = DB.load_map()
            m[inv_id] = {"user": user, "asset": str(currency).upper(),
                         "decimals": int(invoice.get("decimals", 6) or 6),
                         "credited_int": 0}
            DB.save_map(m)
            return True
        except Exception:                                       # noqa: BLE001
            return False

    # ---------- 本地幂等表(仅标准库 json) ----------
    # 条目结构: {"<key>": {"base": <该次开票的服务基址>, "ts": epoch, "invoice": {...}}}
    # 仅当 base 与当前客户端一致时才命中 —— 换基址/重建钱包(灾备恢复)后不会返回失效发票;
    # 数据根被重建时应删除该文件(见 deploy/DEPLOY.md 恢复步骤)。

    def _idem_load(self):
        try:
            with open(self._idem_file, encoding="utf-8") as f:
                obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
        except Exception:                                       # noqa: BLE001
            return {}

    def _idem_get(self, key):
        entry = self._idem_load().get(key)
        if not isinstance(entry, dict) or "invoice" not in entry:
            return None                                        # 旧格式/无 base 信息 => 视为未命中
        if entry.get("base") != self.base:
            return None
        return entry.get("invoice")

    def _idem_put(self, key, value) -> bool:
        """写幂等映射。**返回是否真的落盘**。

        🔴 2026-09-22 修（错报治理 · 第 31/40 条）：原来失败静默 `pass` ——
        调用方以为「这张发票已经登记过了」，而映射**其实没落盘** ⇒
        下次重试会**重复提交**（幂等门失效）。**幂等文件缺行 = 重复扣款/重复记账**，
        这是**有后果的静默**，与授权门那处同级。
        口径同全仓：**不抛 + 计数 + 同类首次出声 + 只读口 `idem_failures()`**。
        """
        m = self._idem_load()
        m[key] = {"base": self.base, "ts": int(time.time()), "invoice": value}
        try:
            d = os.path.dirname(os.path.abspath(self._idem_file))
            os.makedirs(d, exist_ok=True)
            tmp = self._idem_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._idem_file)
            return True
        except Exception as _e:                                     # noqa: BLE001
            st = getattr(type(self), "_IDEM_FAIL", None)
            if st is None:
                st = {"count": 0, "reasons": {}, "last_at": None}
                type(self)._IDEM_FAIL = st
            st["count"] += 1
            st["last_at"] = int(time.time())
            _k = type(_e).__name__
            st["reasons"][_k] = st["reasons"].get(_k, 0) + 1
            if st["reasons"][_k] == 1:                              # 同类只首次出声
                try:
                    import sys as _s
                    print("⚠️ platform_client: 幂等映射落盘失败（%s: %s）⇒ 幂等门可能失效、"
                          "重试有重复提交风险（累计 %d 次）"
                          % (_k, str(_e)[:110], st["count"]), file=_s.stderr)
                except Exception:                                   # noqa: BLE001
                    pass
            return False

    @classmethod
    def idem_failures(cls) -> dict:
        """只读：幂等映射落盘失败读数。

        `count > 0` ⇒ **幂等映射未落盘，重试可能重复提交** —— 必须被看见的读数。
        """
        st = getattr(cls, "_IDEM_FAIL", None) or {"count": 0, "reasons": {}, "last_at": None}
        return {"ok": True, "readonly": True, "count": st["count"],
                "reasons": dict(st["reasons"]), "last_at": st["last_at"],
                "note": "count>0 ⇒ 幂等映射未落盘，重试可能重复提交（有后果）"}


# ---------- 模块级便捷函数(复用默认客户端) ----------

_default_singleton = None


def _client():
    global _default_singleton
    if _default_singleton is None:
        _default_singleton = WalletClient()
    return _default_singleton


def health():
    return _client().health()


def create_invoice(user, amount, currency="USDC.E", **kw):
    return _client().create_invoice(user, amount, currency, **kw)


def list_invoices(status=None, user=None):
    return _client().list_invoices(status=status, user=user)


def scan():
    return _client().scan()


def balances():
    return _client().balances()


def events(since=None, limit=200):
    return _client().events(since=since, limit=limit)


def _main(argv=None):                                          # pragma: no cover - 运维快查
    import argparse
    ap = argparse.ArgumentParser(description="钱包 API 快查(平台侧客户端)")
    ap.add_argument("action", choices=["health", "monitor", "invoices", "balances", "events",
                                       "scan", "invoice", "status"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args(argv)
    c = WalletClient()
    if a.action == "status":
        out = {"base": c.base, "token_configured": bool(c.token), "timeout": c.timeout}
    elif a.action == "invoice":
        if len(a.args) < 2:
            ap.error("invoice 需要: <user> <amount> [currency]")
        out = c.create_invoice(a.args[0], float(a.args[1]),
                               a.args[2] if len(a.args) > 2 else "USDC.E")
    else:
        out = getattr(c, a.action)()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(_main())
