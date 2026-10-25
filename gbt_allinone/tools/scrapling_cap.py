# gbt-capability: scrapling
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""Scrapling 网页抓取能力（自适应选择器 · 反爬对抗）· 2026-09-26 主人令接入。

定位（对齐"公开网络抓取直接可用"的既有口径）：
  * 只抓**公网**地址 —— 每一个 URL 先过 `net_guard.validate_url(allow_private=False)`，
    内网/保留地址/非标端口一律如实拒绝（想抓内网是另一条授权的事，本能力位不背）。
  * **缺库如实报缺**：scrapling/patchright 没装时 status 如实说，绝不拿别的抓取器冒充。
  * 响应体**限量**（默认 2MB，沿用 net_guard 同款尺寸纪律），超限截断并声明。
  * 浏览器级隐身抓取（StealthyFetcher）只在库与浏览器内核齐备时可用，缺哪个如实说哪个。

ops：
  status                        库/引擎/浏览器内核的体检（只读）
  fetch  url= [, selector]      抓取公网页面，返回状态/标题/正文摘要；给 selector 则返回命中文本
"""
from __future__ import annotations

import re

from ..security import net_guard

_KIND = "scrapling"
_MAX_BYTES = 2_000_000
_MAX_TIMEOUT = 60


def _lib():
    """延迟导入：缺库返回 (None, 缺什么)。不装看不见的依赖。"""
    try:
        import scrapling  # noqa: F401
        from scrapling import Fetcher
        return {"scrapling": True, "Fetcher": Fetcher}, None
    except Exception as exc:                                   # noqa: BLE001
        return None, "%s: %s" % (type(exc).__name__, str(exc)[:120])


def _stealth_ready() -> dict:
    """浏览器级隐身抓取的可用性：库在不在、浏览器内核装没装，分开如实报。"""
    try:
        from scrapling import StealthyFetcher                  # noqa: F401
        lib = True
    except Exception:                                          # noqa: BLE001
        return {"lib": False, "browser": False, "note": "缺 StealthyFetcher 依赖"}
    try:
        from patchright.sync_api import sync_playwright        # noqa: F401
        return {"lib": True, "browser": None,
                "note": "库在；浏览器内核需 patchright install chromium（未探测，不谎报）"}
    except Exception as exc:                                   # noqa: BLE001
        return {"lib": True, "browser": False,
                "note": "缺 patchright（%s）" % str(exc)[:80]}


def status(**_kw) -> dict:
    lib, missing = _lib()
    out = {"ok": True, "op": "status", "kind": _KIND,
           "口径": "只抓公网（net_guard 边界）· 缺库如实报缺 · 响应体限量 %d 字节" % _MAX_BYTES}
    if lib is None:
        out.update({"installed": False, "error": missing,
                    "hint": "pip install scrapling patchright"})
        return out
    import scrapling
    out.update({"installed": True,
                "version": getattr(scrapling, "__version__", "?"),
                "http_fetcher": "Fetcher（curl_cffi）",
                "stealth": _stealth_ready()})
    return out


def fetch(url: str = "", selector: str = "", timeout: int = 30, **_kw) -> dict:
    if not url:
        return {"ok": False, "error": "缺 url"}
    try:
        net_guard.validate_url(str(url), allow_private=False)
    except net_guard.NetworkGuardError as exc:
        return {"ok": False, "error": "边界拦截：%s" % str(exc)[:160],
                "口径": "本能力只抓公网；内网/保留地址要走 network_private 授权那条路"}
    lib, missing = _lib()
    if lib is None:
        return {"ok": False, "error": "scrapling 未安装（%s）" % missing,
                "hint": "pip install scrapling patchright"}
    timeout = max(3, min(_MAX_TIMEOUT, int(timeout or 30)))
    try:
        resp = lib["Fetcher"]().get(str(url), timeout=timeout)
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": "抓取失败：%s: %s" % (type(exc).__name__, str(exc)[:160])}
    out = {"ok": True, "op": "fetch", "url": str(url),
           "status": getattr(resp, "status", None), "engine": "Fetcher/curl_cffi"}
    # 标题与正文摘要（逐项防御：Response 形状随版本漂，取不到就如实空着）
    try:
        title = ""
        try:
            titles = resp.css("title::text")
            title = titles[0] if titles else ""
        except Exception:                                      # noqa: BLE001
            title = ""
        if not title:
            title = resp.re_first(r"<title[^>]*>(.*?)</title>") or ""
        out["title"] = str(title).strip()[:200]
    except Exception:                                          # noqa: BLE001
        out["title"] = ""
    try:
        body = resp.body if isinstance(getattr(resp, "body", None), (bytes, str)) else ""
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        text = re.sub(r"<[^>]+>", " ", body)
        text = re.sub(r"\s+", " ", text).strip()
        out["text_len"] = len(text)
        out["text_head"] = text[:600]
    except Exception:                                          # noqa: BLE001
        out["text_head"] = ""
    if selector:
        try:
            sel = selector if "::" in selector else selector + "::text"
            hits = [str(t).strip()[:200] for t in resp.css(sel) if str(t).strip()]
            out["selector"] = sel
            out["hits"] = hits[:20]
            out["hits_count"] = len(hits)
        except Exception as exc:                               # noqa: BLE001
            out["selector_error"] = "%s: %s" % (type(exc).__name__, str(exc)[:120])
    return out


def run(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    if op == "status":
        return status(**params)
    if op == "fetch":
        return fetch(**params)
    return {"ok": False, "error": "未知 op:%s（可用：status / fetch）" % op,
            "fail_closed": True}
