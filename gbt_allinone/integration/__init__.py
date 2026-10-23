# -*- coding: utf-8 -*-
"""gbt_allinone.integration — 平台与收款钱包(gbt_wallet)的接轨层。

- auth: gbt_wallet.api 的可选令牌鉴权 + CORS 装配(默认行为不变)。
- platform_client: 平台侧调用钱包 HTTP API 的轻量客户端(仅标准库 urllib)。

只依赖标准库; 不改 gbt_wallet 的业务逻辑与数据格式。
"""
from .auth import (install_middleware, verify_bearer, expected_token,
                   parse_origins, token_fingerprint)
from .platform_client import WalletClient, WalletApiError

__all__ = ["install_middleware", "verify_bearer", "expected_token", "parse_origins",
           "token_fingerprint", "WalletClient", "WalletApiError"]
