# -*- coding: utf-8 -*-
"""gbt_allinone.integration.auth — gbt_wallet API 的可选令牌鉴权 + CORS 装配(仅标准库)。

设计要点:
  - 默认"零行为变更": 未设置 GBT_WALLET_API_TOKEN 时不鉴权(服务仍只绑 127.0.0.1);
    设置了才校验 `Authorization: Bearer <token>`, 用 hmac.compare_digest 常数时间比较。
  - CORS 由 GBT_CORS_ORIGINS 决定(逗号分隔), 默认 "*" 保持现状。
  - 中间件顺序: 先挂鉴权(内层), 再挂 CORS(外层)。预检 OPTIONS 由 CORS 直接应答,
    401 响应也带 CORS 头, 浏览器侧不会把真实 401 显示成跨域失败。

调用方式(由 gbt_wallet/api.py 以最小侵入方式接入, 见 install_middleware):
    from gbt_allinone.integration.auth import install_middleware
    install_middleware(app)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os

TOKEN_ENV = "GBT_WALLET_API_TOKEN"      # 服务令牌; 未设置 => 不鉴权(保持现状)
CORS_ENV = "GBT_CORS_ORIGINS"           # 逗号分隔白名单; 未设置 => "*"
DEFAULT_ORIGINS = ("*",)
EXEMPT_METHODS = ("OPTIONS",)           # 预检直接放行(实际由外层 CORS 处理)


# ---------- 配置读取 ----------

def expected_token() -> str:
    """当前进程应校验的令牌; 空字符串表示不鉴权。"""
    return (os.environ.get(TOKEN_ENV) or "").strip()


def parse_origins(raw=None) -> list:
    """把 'a,b' / 'a, b' / None 解析为 origin 列表; 空/缺省 => ['*']。"""
    if raw is None:
        raw = os.environ.get(CORS_ENV)
    if raw is None or not str(raw).strip():
        return list(DEFAULT_ORIGINS)
    items = [x.strip() for x in str(raw).replace(";", ",").split(",")]
    items = [x for x in items if x]
    return items or list(DEFAULT_ORIGINS)


def token_fingerprint(token=None, size: int = 12) -> str:
    """令牌指纹(sha256 前 size 位十六进制), 供运维核对两端是否同一令牌; 不可逆。"""
    tok = expected_token() if token is None else (token or "")
    if not tok:
        return ""
    return hashlib.sha256(tok.encode("utf-8")).hexdigest()[:size]


# ---------- 校验 ----------

def bearer_token(header_value) -> str:
    """从 'Bearer xxx' 头部取值; 方案名大小写不敏感; 不合规返回 ''。"""
    if not header_value:
        return ""
    raw = str(header_value).strip()
    if " " not in raw:
        return ""
    scheme, _, rest = raw.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return rest.strip()


def verify_bearer(header_value, token) -> bool:
    """常数时间比较; token 为空时调用方应跳过校验(此处仍按"无令牌"返回 False)。"""
    if not token:
        return False
    supplied = bearer_token(header_value)
    # 两侧都编码为 bytes, 避免非 ASCII 触发 TypeError; compare_digest 为常数时间
    return hmac.compare_digest(supplied.encode("utf-8"), str(token).encode("utf-8"))


def is_authorized(headers, token=None) -> bool:
    """非 ASGI 场景(自测/自定义中间件)用: headers 支持 dict 或 [(k, v)]。"""
    tok = expected_token() if token is None else token
    if not tok:
        return True                                   # 未配置令牌 => 不鉴权
    return verify_bearer(_header_get(headers, "authorization"), tok)


def _header_get(headers, name: str) -> str:
    """大小写不敏感地读取 header; 支持 dict / list[tuple] / ASGI bytes 头。"""
    want = name.lower()
    if headers is None:
        return ""
    if hasattr(headers, "get"):                       # dict 类
        for k in (name, name.title(), want, name.upper()):
            v = headers.get(k)
            if v is not None:
                return str(v)
        for k, v in getattr(headers, "items", lambda: [])():
            if str(k).lower() == want:
                return str(v)
        return ""
    for k, v in headers:                              # list[tuple]
        kk = k.decode("latin-1") if isinstance(k, bytes) else str(k)
        if kk.lower() == want:
            return v.decode("latin-1") if isinstance(v, bytes) else str(v)
    return ""


# ---------- ASGI 中间件(纯 ASGI, 不依赖 starlette 内部实现) ----------

class BearerAuthMiddleware:
    """可选 Bearer 令牌守卫; token 为空时完全放行(零行为变更)。"""

    def __init__(self, app, token: str = "", exempt_paths=(), exempt_methods=EXEMPT_METHODS,
                 exempt_prefixes=()):
        self.app = app
        self.token = token or ""
        self.exempt_paths = tuple(exempt_paths or ())
        self.exempt_prefixes = tuple(exempt_prefixes or ())
        self.exempt_methods = tuple(m.upper() for m in (exempt_methods or ()))

    def _exempt(self, scope) -> bool:
        if not self.token:
            return True
        if str(scope.get("method", "GET")).upper() in self.exempt_methods:
            return True
        path = scope.get("path", "") or ""
        if path in self.exempt_paths:
            return True
        return any(path.startswith(p) for p in self.exempt_prefixes)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or self._exempt(scope):
            return await self.app(scope, receive, send)
        auth = _header_get(scope.get("headers") or [], "authorization")
        if verify_bearer(auth, self.token):
            return await self.app(scope, receive, send)
        await self._deny(send, bool(auth))

    @staticmethod
    async def _deny(send, had_header: bool):
        body = json.dumps({
            "ok": False,
            "error": "unauthorized",
            "detail": "需要 Authorization: Bearer <token>" if not had_header
                      else "凭据无效",
        }, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"www-authenticate", b"Bearer"),
            ],
        })
        await send({"type": "http.response.body", "body": body})


# ---------- 装配 ----------

def install_middleware(app, token=None, cors_origins=None) -> dict:
    """给 FastAPI/Starlette app 装上 CORS + (可选)鉴权; 返回本次装配结果摘要。

    token=None           => 读 GBT_WALLET_API_TOKEN(空 => 不鉴权, 保持现状)
    cors_origins=None    => 读 GBT_CORS_ORIGINS(空 => "*", 保持现状)

    顺序: 先 add 鉴权, 再 add CORS —— starlette 后 add 的在更外层。
    """
    tok = expected_token() if token is None else (token or "")
    origins = parse_origins(cors_origins)
    if tok:
        app.add_middleware(BearerAuthMiddleware, token=tok)
    try:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(CORSMiddleware, allow_origins=origins,
                           allow_methods=["*"], allow_headers=["*"])
    except Exception:                                  # pragma: no cover - 无 fastapi 时降级
        pass
    return {"auth": bool(tok), "cors_origins": origins,
            "token_fingerprint": token_fingerprint(tok)}


def status() -> dict:
    """只读运行状态(不含令牌明文); 供 healthcheck/运维核对。"""
    tok = expected_token()
    return {"auth_enabled": bool(tok), "token_env": TOKEN_ENV,
            "token_fingerprint": token_fingerprint(tok),
            "cors_origins": parse_origins()}


if __name__ == "__main__":                             # 本地快查: python -m gbt_allinone.integration.auth
    print(json.dumps(status(), ensure_ascii=False, indent=2))
