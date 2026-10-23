# gbt-capability: browser
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""browser 能力 — 真实浏览器自动化（标准库 webbrowser + 可选自动化后端）。

⚠️ 外部内容纪律：`fetch`（以及 `automate`/`native` 取回的页面文字）拿到的**网页内容
一律是不可信数据，不是指令** —— 页面里可能写着"忽略你之前的指令"之类的话。
本模块只把它当数据返回；不执行其中任何祈使句、不拼进 system 提示、不拿去驱动执行口。
调用方要把它喂给模型时，必须自己在 system 侧声明"以下是外部资料"。
覆盖校验器：py -3.14 -m gbt_allinone.tools.external_content_check gbt_allinone

三级后端，如实降级：
1. open/search（webbrowser 标准库）：打开 URL / 默认浏览器搜索——零依赖真执行
2. fetch（urllib）：无头抓取页面文本（静态内容）——零依赖真执行
3. automate（Playwright/Selenium）：未安装时如实返回 needs_dependency + 安装指引
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

# 原生浏览器窗口的 op 别名。必须与 security/policy.py 里 `elif kind == "browser":`
# 那一段认的别名集合保持一致 —— 那边是判定作用域的唯一权威，此处只是同一把钥匙。
# 漂移会导致「门认、分发不认」（或反过来）；回归校验每次都逐字比对这两处。
NATIVE_BROWSER_OPS = ("native", "deep", "controller", "cdp")


def open_url(url):
    """用系统默认浏览器打开 URL（真实执行）。"""
    if not url:
        raise ValueError("缺少 url")
    if not re.match(r"^https?://", url):
        url = "https://" + url
    import webbrowser
    ok = webbrowser.open(url)
    return {"ok": bool(ok), "action": "open", "url": url,
            "backend": "system-default-browser"}


def search(query, engine="bing"):
    """用系统默认浏览器搜索（真实执行）。"""
    if not query:
        raise ValueError("缺少 query")
    engines = {
        "bing": "https://www.bing.com/search?q=",
        "baidu": "https://www.baidu.com/s?wd=",
        "google": "https://www.google.com/search?q=",
        "duckduckgo": "https://duckduckgo.com/?q=",
    }
    if engine not in engines:
        raise ValueError(f"未知引擎: {engine}（可用: {'/'.join(engines)}）")
    import urllib.parse
    import webbrowser
    url = engines[engine] + urllib.parse.quote_plus(query)
    ok = webbrowser.open(url)
    return {"ok": bool(ok), "action": "search", "engine": engine,
            "query": query, "url": url, "backend": "system-default-browser"}


def fetch(url, timeout=20, max_chars=20000):
    """无头抓取页面（静态内容，标准库真实执行；动态渲染需 automate 后端）。"""
    if not url:
        raise ValueError("缺少 url")
    if not re.match(r"^https?://", url):
        url = "https://" + url
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GBT-V8/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, errors="replace")
        # 粗提正文：去 script/style/tag
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {"ok": True, "action": "fetch", "url": url, "status": "fetched",
                "chars": len(text), "text": text[:max_chars],
                "note": "静态抓取；动态渲染页面请用 op=automate（需 Playwright）"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "action": "fetch", "url": url, "error": str(e)[:200]}


def automate(op="status", **params):
    """浏览器自动化（需 Playwright）。

    未安装时如实返回 needs_dependency + 安装指引，不伪造自动化结果。
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        installed = True
    except Exception:
        installed = False
    if not installed:
        return {"ok": False, "status": "needs_dependency",
                "missing": "playwright",
                "install": "python -m pip install playwright && python -m playwright install chromium",
                "note": "open/search/fetch 已可用（标准库）；自动化需安装 Playwright"}
    # 已安装 → 真实自动化
    from playwright.sync_api import sync_playwright
    act = params.get("act", "goto")
    url = params.get("url", "https://www.bing.com")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=bool(params.get("headless", True)))
        page = browser.new_page()
        try:
            page.goto(url, timeout=30000)
            if act == "goto":
                title = page.title()
                return {"ok": True, "backend": "playwright", "url": url, "title": title}
            if act == "text":
                return {"ok": True, "backend": "playwright", "url": url,
                        "text": page.inner_text("body")[:20000]}
            if act == "click":
                sel = params.get("selector")
                if not sel:
                    raise ValueError("click 需要 selector")
                page.click(sel)
                return {"ok": True, "backend": "playwright", "clicked": sel,
                        "url_after": page.url}
            if act == "type":
                sel, val = params.get("selector"), params.get("value", "")
                if not sel:
                    raise ValueError("type 需要 selector")
                page.fill(sel, val)
                return {"ok": True, "backend": "playwright", "filled": sel}
            if act == "screenshot":
                out = params.get("out", "store/vision/browser_shot.png")
                page.screenshot(path=out)
                return {"ok": True, "backend": "playwright", "screenshot": out}
            raise ValueError(f"未知 act: {act}（可用: goto/text/click/type/screenshot）")
        finally:
            browser.close()


def native(action="status", **params):
    """原生浏览器窗口（Chrome DevTools Protocol）—— 引擎在 native_browser.py。

    本函数只是门面转发：动作表、CDP 传输、窗口落位全在引擎里；
    异常与「没装/没开」一律由引擎如实返回，这里不加工、不伪造。

    参数裁剪是必须的：api 层为了浏览器门面统一，会带 url/query/engine/max_chars/
    timeout 一整组；而原生引擎的多数动作不接受 url（如 status），直接透传会变成
    `status() got an unexpected keyword argument 'url'`。所以按**目标动作的真实签名**
    裁剪；动作自带 **kwargs 的不裁剪，保持弹性。
    """
    import inspect

    from . import native_browser
    act = str(action or "status").strip().lower()
    handler = getattr(native_browser, act, None)
    if callable(handler):
        try:
            sig = inspect.signature(handler)
            if not any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
                params = {k: v for k, v in params.items() if k in sig.parameters}
        except (TypeError, ValueError):
            pass
    return native_browser.run(act, **params)


def run(op="open", **params):
    """browser 统一入口：open/search/fetch（标准库）/ automate（需 Playwright）
    / native（原生浏览器窗口，delegate 到 native_browser.py）。"""
    if op in NATIVE_BROWSER_OPS:
        # R-H291：门早就造好了（security/policy.py 按 kind=browser / op=native /
        # action=… 判定作用域），但分发层从没把 op=native 转给引擎 —— 门造好了线没接，
        # 1508 行的原生浏览器只能绕道 Codex 动态工具，绕开了统一入口。此处补的就是这条线：
        # 只转发，不新增也不放宽任何作用域，判定权仍 100% 在 security/policy.py。
        action = params.pop("action", None) or params.pop("cmd", None) or "status"
        return native(action, **params)
    if op in ("open", "goto", None):
        return open_url(params.get("url"))
    if op == "search":
        return search(params.get("query"), params.get("engine", "bing"))
    if op == "fetch":
        return fetch(params.get("url"), int(params.get("timeout", 20)),
                     int(params.get("max_chars", 20000)))
    if op == "automate":
        return automate(**params)
    if op == "status":
        try:
            import playwright  # noqa: F401
            auto = "playwright（已安装）"
        except Exception:
            auto = "needs_dependency（python -m pip install playwright）"
        return {"ok": True, "open_search_fetch": "标准库（可用）", "automate": auto}
    raise ValueError(f"未知 op: {op}（可用: open/search/fetch/automate/status/"
                     f"{'/'.join(NATIVE_BROWSER_OPS)}）")
