"""GBT小土豆V8 · 目标安全校验。

只读/公开信息类扫描只应作用于公网目标。
环回、私网、链路本地、保留网段一律拒绝——除非显式传入 allow_private=True。
"""

import ipaddress
import socket
from typing import Optional, Tuple

_PRIVATE_HINT = (
    "目标属于本机/内网/保留地址段。私人框架默认不扫内网；"
    "扫描自有内网资产需人工授权（python -m gbt_allinone auth grant），"
    "AI 调用路径无权自行放行。"
)


def _ip_obj(ip: str) -> Optional[ipaddress._BaseAddress]:
    try:
        return ipaddress.ip_address(ip)
    except ValueError:
        return None


def classify_target(target: str) -> Tuple[str, str]:
    """返回 (kind, reason)。

    kind: 'public' | 'private' | 'invalid'
    """
    t = (target or "").strip()
    if not t:
        return ("invalid", "目标为空")

    # 去掉协议与路径，取主机部分
    host = t
    for prefix in ("https://", "http://"):
        if host.lower().startswith(prefix):
            host = host[len(prefix):]
    host = host.split("/")[0].split(":")[0].strip(".")

    if not host:
        return ("invalid", "无法解析出主机名")

    # 字面 IP
    ip = _ip_obj(host)
    if ip is not None:
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return ("private", _PRIVATE_HINT)
        return ("public", "")

    # 字面主机名：先拦明显本机别名
    if host.lower() in ("localhost",) or host.lower().endswith(".local"):
        return ("private", _PRIVATE_HINT)

    # 域名 → 解析成 IP 再判（任一地址落在内网即判 private）
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        return ("invalid", f"域名解析失败: {e}")
    for info in infos:
        ipstr = info[4][0]
        obj = _ip_obj(ipstr)
        if obj is None:
            continue
        if obj.is_loopback or obj.is_private or obj.is_link_local or obj.is_reserved:
            return ("private", _PRIVATE_HINT)
    return ("public", "")


def guard_target(target: str, allow_private: bool = False) -> None:
    """校验目标；不通过则抛 ValueError。

    allow_private=True 仅供扫描自有内网资产时显式使用。
    """
    kind, reason = classify_target(target)
    if kind == "invalid":
        raise ValueError(f"无效目标: {reason}")
    if kind == "private" and not allow_private:
        raise ValueError(reason)
