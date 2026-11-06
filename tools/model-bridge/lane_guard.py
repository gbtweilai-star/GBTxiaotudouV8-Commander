# -*- coding: utf-8 -*-
"""lane_guard —— 车道守卫：回环直连 · 失败分档 · 发请求前判上下文装不装得下。

⚠️ **这是重建版，不是原始文件。** 2026-11-05 发现 `tools/model-bridge/server.py:49`
硬 import 本模块，而全仓（含所有备份/归档）**一个 `lane_guard*` 都没有** ——
`启动-GBT.cmd` 第一步就是 8791 bridge，缺它整条启动链断在第一环。

重建依据（全部来自调用点，不靠想象）：
  · `server.py:277/563/1104`  `with LG.open_url(url, req, timeout) as r:` → 上下文管理器，
    有 `.status` / `.read()`
  · `server.py:568/570/1129/1138` `LG.classify_exc(exc, url[, raw])` → 返回 kind 字符串
  · `server.py:754/1132/1140/1152` `LG.kind_text(kind)` → 返回人读文本
  · `server.py:1088` `_fit = LG.precheck_fit(l_base, l_body, lane=lane)`，
    用到 `_fit["checked"/"over"/"tokens"/"max_tokens"/"n_ctx"/"over_by"]`
  · `server.py:44-46` 的注释交代了三件职责（见下）

三个职责（照 server.py 的原注释）：
  ① **回环强制直连**：本机 HTTP_PROXY 是全局的，urlopen 对 127.0.0.1 不自动 bypass，
     车道没起时代理回 502，会被误当成「上游真回 502」。
  ② **失败分档**：`kind` 要把「我们自己没起服务」与「上游真的报错」分开 —— 两者处置完全不同。
  ③ **发之前判上下文**：GPU 车道原来靠 llama-server 推理跑起来后才回 400（满窗口实测 46.5s），
     用户白等一场才被告知装不下。这里先 `/tokenize` 数真 token 再拒。
"""
from __future__ import annotations

import json
import os
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

__all__ = ["open_url", "classify_exc", "kind_text", "precheck_fit",
           "is_loopback", "KINDS"]

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}

# 回环专用 opener：ProxyHandler({}) 清空所有代理 ⇒ 直连，不受全局 HTTP_PROXY 影响
_LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

KINDS = (
    "limb_down",        # 端口没人听 —— 我们自己的服务没起
    "proxy_502",        # 本机代理编的 502（回环 + 响应里没有上游痕迹）
    "timeout",          # 超时 —— 可能在慢启动 / 权重大
    "conn_reset",       # 连接被重置
    "dns",              # 域名解析不了
    "tls",              # TLS/证书问题
    "upstream_error",   # 上游真的回了错
    "bad_request",      # 400 类，通常是请求本身不对
    "unknown",
)

_KIND_TEXT = {
    "limb_down": "车道没起（端口没人听）——先起服务，不是上游报错",
    "proxy_502": "本机代理编的 502（端点其实没通）——查 HTTP_PROXY / NO_PROXY，别怪上游",
    "timeout": "等超时了——可能正在慢启动或权重太大，先看车道日志",
    "conn_reset": "连接被对端重置——服务可能起了一半就退了",
    "dns": "域名解析不了——检查地址拼写或网络",
    "tls": "TLS/证书问题——回环一般不该有，检查 https/wss 混用",
    "upstream_error": "上游真的回了错——这是上游的话，原样带出去",
    "bad_request": "请求本身不合法（400 类）——检查字段，不是服务没起",
    "unknown": "认不出的失败",
}


def is_loopback(host: str) -> bool:
    """是不是回环地址。"""
    if not host:
        return False
    h = str(host).strip().strip("[]").lower()
    if h in LOOPBACK_HOSTS:
        return True
    return h.startswith("127.")


def _host_of(url: str) -> str:
    try:
        return urllib.parse.urlsplit(url).hostname or ""
    except Exception:  # noqa: BLE001
        return ""


def open_url(url: str, req=None, timeout: float = 30):
    """打开 URL —— **回环地址一律直连**，不受全局 HTTP_PROXY 影响。

    与 `urllib.request.urlopen` 用法一致（可直接 `with`），只是回环走无代理 opener。
    """
    target = req if req is not None else url
    if is_loopback(_host_of(url)):
        return _LOOPBACK_OPENER.open(target, timeout=timeout)
    return urllib.request.urlopen(target, timeout=timeout)


def classify_exc(exc, url: str, raw=None) -> str:
    """把异常归成一档 —— 关键是分清「我们没起服务」与「上游报错」。

    `raw` 传上游/代理回包体时能进一步分辨：本机代理编的 502 只在 body 里留痕迹，
    响应头是干净的（这也是为什么调用点都坚持「先读 body 再归因」）。
    """
    host = _host_of(url)
    loop = is_loopback(host)

    if isinstance(exc, urllib.error.HTTPError):
        code = int(getattr(exc, "code", 0) or 0)
        if code in (400, 404, 405, 413, 422):
            return "bad_request"
        if code in (502, 503, 504):
            text = b""
            if isinstance(raw, (bytes, bytearray)):
                text = bytes(raw)
            elif isinstance(raw, str):
                text = raw.encode("utf-8", "replace")
            low = text[:2000].lower()
            # 回环 + 5xx + 响应里没有任何上游痕迹 ⇒ 大概率是代理编的
            if loop and not any(k in low for k in (b"upstream", b"llama", b"model", b"vllm")):
                return "proxy_502"
            return "upstream_error"
        if code >= 500:
            return "upstream_error"
        return "unknown"

    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (ConnectionRefusedError, ConnectionAbortedError)):
            return "limb_down" if isinstance(reason, ConnectionRefusedError) else "conn_reset"
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return "timeout"
        if isinstance(reason, socket.gaierror):
            return "dns"
        if isinstance(reason, ssl.SSLError):
            return "tls"
        txt = str(reason or exc).lower()
        if "refused" in txt:
            return "limb_down"
        if "timed out" in txt or "timeout" in txt:
            return "timeout"
        if "getaddrinfo" in txt or "name or service" in txt:
            return "dns"
        if "certificate" in txt or "ssl" in txt:
            return "tls"
        return "unknown"

    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, ConnectionRefusedError):
        return "limb_down"
    if isinstance(exc, ConnectionResetError):
        return "conn_reset"
    if isinstance(exc, socket.gaierror):
        return "dns"
    if isinstance(exc, ssl.SSLError):
        return "tls"
    if isinstance(exc, json.JSONDecodeError):
        return "upstream_error"

    txt = "%s: %s" % (type(exc).__name__, exc)
    low = txt.lower()
    if "refused" in low:
        return "limb_down"
    if "timed out" in low or "timeout" in low:
        return "timeout"
    return "unknown"


def kind_text(kind: str) -> str:
    """kind → 人读文本（对外回执里用它，别让人去猜代码）。"""
    return _KIND_TEXT.get(str(kind or "").strip(), _KIND_TEXT["unknown"])


def _prompt_text(body) -> str:
    """从请求体里取待数 token 的文本。"""
    if not isinstance(body, dict):
        return ""
    if isinstance(body.get("prompt"), str):
        return body["prompt"]
    parts = []
    for m in (body.get("messages") or []):
        if not isinstance(m, dict):
            continue
        c = m.get("content")
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, list):
            for seg in c:
                if isinstance(seg, dict) and isinstance(seg.get("text"), str):
                    parts.append(seg["text"])
    return "\n".join(parts)


def _n_ctx(base: str, lane: str | None) -> int:
    """车道的上下文窗口：环境变量优先（`GBT_GPU_CTX`），其次问 `/props`。"""
    if lane and "gpu" in str(lane):
        try:
            v = int(str(os.environ.get("GBT_GPU_CTX") or "0").strip())
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    try:
        with open_url(base.rstrip("/") + "/props", None, 2.0) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        for path in (("default_generation_settings", "n_ctx"), ("n_ctx",)):
            cur = d
            ok = True
            for k in path:
                if isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    ok = False
                    break
            if ok:
                try:
                    v = int(cur)
                    if v > 0:
                        return v
                except (TypeError, ValueError):
                    pass
    except Exception:  # noqa: BLE001
        pass
    return 0


def precheck_fit(base: str, body, lane: str | None = None) -> dict:
    """发请求**之前**判这发装不装得下 —— 用车道自己的 `/tokenize` 数真 token。

    返回：`{checked, over, tokens, max_tokens, n_ctx, over_by}`；
    判不了就 `{checked: False, why: ...}` —— **判不了不等于通过**，调用方看 `checked`。
    """
    out: dict = {"checked": False}
    try:
        n_ctx = _n_ctx(base, lane)
        if n_ctx <= 0:
            out["why"] = "读不到 n_ctx（/props 没给，环境变量也没设）"
            return out
        prompt = _prompt_text(body)
        req = urllib.request.Request(
            base.rstrip("/") + "/tokenize",
            data=json.dumps({"content": prompt}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with open_url(base.rstrip("/") + "/tokenize", req, 3.0) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        tokens = len(d.get("tokens") or [])
        if not tokens:
            out["why"] = "/tokenize 没返回 tokens"
            return out
        try:
            max_tokens = int((body or {}).get("max_tokens") or 512)
        except (TypeError, ValueError):
            max_tokens = 512
        total = tokens + max_tokens
        return {
            "checked": True,
            "over": total > n_ctx,
            "tokens": tokens,
            "max_tokens": max_tokens,
            "n_ctx": n_ctx,
            "over_by": max(0, total - n_ctx),
            "lane": lane,
        }
    except Exception as exc:  # noqa: BLE001
        out["why"] = "%s: %s" % (type(exc).__name__, str(exc)[:160])
        out["kind"] = classify_exc(exc, base)
        return out
