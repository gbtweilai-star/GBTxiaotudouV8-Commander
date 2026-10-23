# -*- coding: utf-8 -*-
"""llm-fallback-proxy —— 先打我们自己的引擎；冷/挂时**自动反向调用免费云端**，并留痕。

主人令（2026-10-21）：「GPU 我不是设计了调用云端免费反向调用了吗」+ 选「做兜底代理」。
它解决的是什么、不是什么，写在最前面，免得以后有人读错：
  · 解决：自托管 vLLM **缩到 0 后冷启动 102 秒**，页面那句「怎么不回」。
  · 不解决：让回答变成我们自己权重的产物。兜底那一次**用的是别人的模型**
    （agnes-2.5-flash / deepseek-chat），所以回包里必须**标明**、日志里必须落账，
    绝不冒充自有权重（`_gbt_fallback.via` 与 `model` 字段都带标记）。

口径（照本仓三条纪律）：
  1. 钥只走 DPAPI 保险箱（profile=potato/agnes/deepseek）与 User 注册表，**不回显、不落盘**；
  2. 超时/失败 ≠ 成功：兜底成功要带 `reason`，全挂就原样回上游错误，不编答案；
  3. 流式照给：主引擎能流就真流；兜底那一段用非流回包合成 SSE，并在首条 delta 前置标记。

用法：
  py -3.14 -X utf8 tools/model-bridge/llm-fallback-proxy.py            # 监听 127.0.0.1:8792
  GBT_FALLBACK_TIMEOUT_MS=8000 可改"等多久算冷"
端：GET /health · GET /v1/models · POST /v1/chat/completions（stream 与非 stream 都收）
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import pathlib
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PORT = int(os.environ.get("GBT_FALLBACK_PORT") or 8792)
# 🔴 2026-10-21 主人拍板「只等自己的」：主引擎最多等 **200 秒**（无服务器冷启动实测 92–300s，
#   热态 0.8–4s）；**只有报错/真连不上才走兜底**，慢不算失败。
#   ⚠️ 90s 那版实测被页面截图当场抓包：90 秒到点落 agnes，而 agnes 拿不到工具却**模仿 XML 工具调用**
#      （`<function_calls><invoke name="read">…`），页面根本看不懂 ⇒ 兜底比不兜更坏。
TIMEOUT_MS = int(os.environ.get("GBT_FALLBACK_TIMEOUT_MS") or 200000)
FALLBACK_TIMEOUT_S = float(os.environ.get("GBT_FALLBACK_STEP_TIMEOUT_S") or 20)
KEEPALIVE_S = float(os.environ.get("GBT_FALLBACK_KEEPALIVE_S") or 5)
LOG_PATH = ROOT / "outputs" / "model-bridge" / "fallback-proxy.log"
# 🔴 UA 必须**纯 ASCII**：urllib 用 latin-1 编码请求头，写成「GBT小土豆V8-fallback」
#   会在发请求前就炸 `UnicodeEncodeError: 'latin-1' codec`，而它又被我们自己的
#   except 吞成 "http=timeout" ⇒ 兜底腿明明活着却报成超时（P21 兜底是死路）。
UA = "GBTxiaotudouV8-fallback/1.0"

# 兜底链：先用 agnes（1.3–3s 实测），再用 deepseek
FALLBACKS = (
    {"name": "agnes", "base": "https://apihub.agnes-ai.com/v1", "model": "agnes-2.5-flash",
     "profile": "agnes"},
    {"name": "deepseek", "base": "https://api.deepseek.com/v1", "model": "deepseek-chat",
     "profile": "deepseek"},
)

STATE = {"primary_calls": 0, "fallback_calls": 0, "last": None, "primary_warm_ms": None}
_LOCK = threading.Lock()


def _env_or_reg(name: str) -> str:
    v = os.environ.get(name) or ""
    if v:
        return v
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return str(winreg.QueryValueEx(k, name)[0] or "")
    except Exception:                                          # noqa: BLE001
        return ""


def primary() -> tuple[str, str, str]:
    """(base, key, source)。base 取自 GBT_POTATO_BASE_URL（与 Codex/页面同一条腿）。"""
    base = (_env_or_reg("GBT_POTATO_BASE_URL") or "").rstrip("/")
    key = _env_or_reg("GBT_POTATO_API_KEY") or _env_or_reg("GBT_CLIPROXY_KEY")
    src = "env/reg"
    if not key:
        from gbt_allinone.deepseek_key import load_key  # noqa: PLC0415
        key, src = load_key("potato")
        src = "vault:" + src
    return base, key, src


def _post(url: str, body: dict, key: str, timeout: float) -> tuple[int, bytes]:
    """POST 上游，**硬超时**。

    🔴 坑（2026-10-21 实测）：`urlopen(timeout=)` 只管**单个 socket 操作**，不管总时长 ——
      无服务器冷启动时上游慢慢挤字节，8s 的"超时"活活拖到 **84.3 秒**才回来
      （代理 /health 记的 `fallback ms: 84299` 就是它）。⇒ 线程 + `future.result(timeout)`
      卡死总时长；到点就走兜底，慢请求丢给后台 daemon 线程不管。
    """
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    def _do() -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + key, "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read() or b""
        except Exception as exc:                               # noqa: BLE001 超时/连不上
            return 0, ("%s: %s" % (type(exc).__name__, str(exc)[:160])).encode("utf-8")

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(_do)
    try:
        return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return 0, b"hard_timeout"
    finally:
        pool.shutdown(wait=False)


def _fallback_call(body: dict) -> tuple[dict | None, str]:
    """依次试兜底；成功返回 (payload, reason)。全挂返回 (None, 最后一次原因)。"""
    msgs = body.get("messages") or []
    want = body.get("max_tokens")
    last = ""
    for fb in FALLBACKS:
        try:
            from gbt_allinone.deepseek_key import load_key  # noqa: PLC0415
            key, src = load_key(fb["profile"])
        except Exception as exc:                               # noqa: BLE001
            last = "%s: 取钥失败 %s" % (fb["name"], type(exc).__name__)
            continue
        if not key:
            last = "%s: 无钥" % fb["name"]
            continue
        payload = {"model": fb["model"], "messages": msgs, "temperature": body.get("temperature", 0.3)}
        # 🔴 实测：agnes-2.5-flash 是**带思考**的模型，max_tokens=40 会全花在 reasoning 上、
        #   `content` 空（usage: reasoning_tokens=40 / text_tokens=0）⇒ 兜底必须给足预算。
        payload["max_tokens"] = min(max(int(want or 0), 512), 4096)
        st, raw = _post(fb["base"] + "/chat/completions", payload, key, FALLBACK_TIMEOUT_S)
        if st == 200:
            try:
                payload_out = json.loads(raw.decode("utf-8", "replace"))
            except Exception:                                  # noqa: BLE001
                last = "%s: 回包不是 JSON" % fb["name"]
                continue
            msg = ((payload_out.get("choices") or [{}])[0].get("message") or {})
            if not (msg.get("content") or "").strip():
                # content 空但思考里有东西 ⇒ 如实标成"只拿到思考"，不装成答案
                think = str(msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
                if think:
                    msg["content"] = "〔兜底 %s 只回了思考、正文为空〕\n%s" % (fb["name"], think[:1500])
                else:
                    last = "%s: 正文为空" % fb["name"]
                    continue
            return payload_out, "fallback:" + fb["name"]
        last = "%s: http=%s %s" % (fb["name"], st or "timeout", raw[:160].decode("utf-8", "replace"))
    return None, last


def _log_line(text: str) -> None:
    """每次请求都留一行证据（客户端报错时，这里能看出到底打没打进来、回了什么）。"""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), text))
    except Exception:                                          # noqa: BLE001
        pass


def _mark(payload: dict, reason: str, elapsed_ms: int, req_model: str = "") -> dict:
    """兜底回包必须自带标记：哪一段不是自有权重给的。

    🔴 两条口径（2026-10-21 校准）：
      ① `model` 保持**客户端请求的那个 id**（回一个陌生名字可能让适配器判不一致），
         身份标记走正文首行 + `_gbt_fallback`；
      ② 非流式也要把标记写进正文第一行 —— 只改字段的话，页面里那段文字看起来跟我们
         自己模型说的一模一样，那就是"冒充身份"，比慢 100 秒更糟。
    """
    payload = dict(payload)
    if req_model:
        payload["model"] = req_model
    payload["_gbt_fallback"] = {"via": reason, "elapsed_ms": elapsed_ms,
                                "note": "这一答**不是**自有权重：主引擎冷启动超时/不可用，走反向调用免费云端"}
    try:
        choice = (payload.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        body_text = msg.get("content") or ""
        if "〔兜底" not in body_text:
            msg["content"] = ("〔兜底 %s：主引擎冷启动超时/不可用，这一答不是自有权重〕\n%s"
                              % (reason.replace("fallback:", ""), body_text))
            choice["message"] = msg
            payload["choices"] = [choice] + list(payload.get("choices") or [])[1:]
    except Exception:                                          # noqa: BLE001
        pass
    return payload


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "authorization,content-type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):                          # 每行一个读数
        sys.stderr.write("[fallback] %s\n" % (fmt % args))

    def do_OPTIONS(self):                                       # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):                                           # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/healthz"):
            base, _key, src = primary()
            return self._json(200, {"ok": True, "service": "gbt-llm-fallback",
                                    "port": PORT, "primary": base, "key": src,
                                    "timeout_ms": TIMEOUT_MS, "state": dict(STATE),
                                    "fallbacks": [f["name"] + "/" + f["model"] for f in FALLBACKS]})
        if path.endswith("/models"):
            base, key, _src = primary()
            mid, ctx = "/runpod-volume/gbt-v8-v83", 32768
            # 现读真实窗口（服务端自报）；取不到就沿用默认，别把"取不到"念成 0
            try:
                req = urllib.request.Request(base + "/models",
                                             headers={"Authorization": "Bearer " + key, "User-Agent": UA})
                with urllib.request.urlopen(req, timeout=15) as r:
                    d = json.loads(r.read().decode("utf-8", "replace"))
                row = (d.get("data") or [{}])[0]
                mid = row.get("id") or mid
                ctx = row.get("max_model_len") or ctx
            except Exception:                                   # noqa: BLE001
                pass
            return self._json(200, {"object": "list", "data": [
                {"id": mid, "object": "model", "owned_by": "GBT小土豆V8",
                 "context_window": ctx, "max_model_len": ctx,
                 "note": "主引擎自有权重；冷启动超时会由本代理反向调用兜底并在回包里标明"}]})
        return self._json(404, {"error": {"message": "不认识：%s" % path}})

    def do_POST(self):                                          # noqa: N802
        path = self.path.split("?", 1)[0]
        if not path.endswith("/chat/completions"):
            return self._json(404, {"error": {"message": "不认识：%s" % path}})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception as exc:                                # noqa: BLE001
            return self._json(400, {"error": {"message": "请求体不是 JSON：%s" % exc}})
        stream = bool(body.get("stream"))
        t0 = time.time()
        _log_line("REQ stream=%s model=%s tools=%d msgs=%d max_tokens=%s"
                  % (stream, body.get("model"), len(body.get("tools") or []),
                     len(body.get("messages") or []), body.get("max_tokens")))
        base, key, src = primary()
        # 🔴 真因（2026-10-21 抓到的）：客户端要 `stream:true`，我**原样转发**给引擎 ⇒ 引擎回的是
        #   **SSE 文本**，我却拿它当 JSON 解析 → `JSONDecodeError` → 处理函数抛异常 → 连接被掐断
        #   → 客户端只看到 `Connection error.`（openai SDK 里就是 fetch failed）。
        #   修法：**上游一律走非流**（拿完整 JSON + usage），再按客户端要求合成 SSE。
        if stream:
            # 流式：先建连接、边等边发心跳（冷启动 90 秒也不会被客户端读超时掐死）
            return self._stream_wait(body)
        up_body = dict(body)
        up_body["stream"] = False
        up_body.pop("stream_options", None)
        st, raw = _post(base + "/chat/completions", up_body, key, TIMEOUT_MS / 1000.0)
        elapsed = int((time.time() - t0) * 1000)
        if st == 200:
            with _LOCK:
                STATE["primary_calls"] += 1
                STATE["primary_warm_ms"] = elapsed
                STATE["last"] = {"via": "self-hosted-openai", "ms": elapsed, "at": time.strftime("%H:%M:%S")}
            sys.stderr.write("[fallback] primary ok %dms stream=%s\n" % (elapsed, stream))
            _log_line("PRIMARY ok %dms stream=%s" % (elapsed, stream))
            return self._json(200, json.loads(raw.decode("utf-8", "replace")))
        # 主引擎**报错/连不上**才走兜底（慢不算失败 —— 主人定：只等自己的）
        reason = "hard_timeout" if st == 0 else "primary_http_%s" % st
        sys.stderr.write("[fallback] primary DOWN after %dms (%s) -> 反向调用\n"
                         % (elapsed, raw[:120].decode("utf-8", "replace")))
        payload, why = _fallback_call(body)
        if payload is None:
            return self._json(502, {"error": {"message": "主引擎与兜底都不可用",
                                              "primary": reason, "fallback": why}})
        with _LOCK:
            STATE["fallback_calls"] += 1
            STATE["last"] = {"via": why, "ms": int((time.time() - t0) * 1000),
                             "reason": reason, "at": time.strftime("%H:%M:%S")}
        marked = _mark(payload, why, int((time.time() - t0) * 1000), str(body.get("model") or ""))
        _log_line("FALLBACK via=%s primary=%s total_ms=%d stream=%s tools=%d msgs=%d"
                  % (why, reason, int((time.time() - t0) * 1000), stream,
                     len(body.get("tools") or []), len(body.get("messages") or [])))
        return self._json(200, marked)

    # ---------- 转发 ----------
    def _chunk(self, data: bytes) -> None:
        """HTTP/1.1 分块帧。"""
        self.wfile.write(("%x\r\n" % len(data)).encode("ascii") + data + b"\r\n")
        self.wfile.flush()

    def _stream_wait(self, body: dict) -> None:
        """流式：立刻建连接 → 边等上游边发 `: keep-alive` 心跳 → 结果到了再发正文。

        为什么必须这么干（2026-10-21）：主人定「只等自己的」，主引擎冷启动要 ~100 秒；
        客户端是流式读，**只要没有字节进来就会被判超时**（截图里 "Connection error"）。
        心跳就是告诉它"我还活着，正在唤醒自有权重"。
        """
        box: dict = {}

        def work() -> None:
            try:
                base, key, _src = primary()
                up_body = dict(body)
                up_body["stream"] = False
                up_body.pop("stream_options", None)
                t0 = time.time()
                st, raw = _post(base + "/chat/completions", up_body, key, TIMEOUT_MS / 1000.0)
                if st == 200:
                    payload = json.loads(raw.decode("utf-8", "replace"))
                    with _LOCK:
                        STATE["primary_calls"] += 1
                        STATE["primary_warm_ms"] = int((time.time() - t0) * 1000)
                        STATE["last"] = {"via": "self-hosted-openai",
                                         "ms": STATE["primary_warm_ms"], "at": time.strftime("%H:%M:%S")}
                    _log_line("PRIMARY ok %dms stream=True (keep-alive while waiting)"
                              % STATE["primary_warm_ms"])
                    box["payload"] = payload
                    return
                reason = "hard_timeout" if st == 0 else "primary_http_%s" % st
                _log_line("PRIMARY DOWN %s after %dms -> fallback" % (reason, int((time.time() - t0) * 1000)))
                payload, why = _fallback_call(body)
                if payload is None:
                    box["error"] = {"message": "主引擎与兜底都不可用", "primary": reason, "fallback": why}
                    return
                with _LOCK:
                    STATE["fallback_calls"] += 1
                    STATE["last"] = {"via": why, "reason": reason, "at": time.strftime("%H:%M:%S")}
                _log_line("FALLBACK via=%s primary=%s stream=True" % (why, reason))
                box["payload"] = _mark(payload, why, int((time.time() - t0) * 1000),
                                       str(body.get("model") or ""))
            except Exception as exc:                            # noqa: BLE001
                box["error"] = {"message": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
                _log_line("STREAM WORK CRASH %s: %s" % (type(exc).__name__, str(exc)[:200]))

        th = threading.Thread(target=work, daemon=True)
        th.start()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._cors()
        self.end_headers()
        last_beat = time.time()
        while th.is_alive():
            if time.time() - last_beat >= KEEPALIVE_S:
                try:
                    self._chunk(b": keep-alive\n\n")
                except Exception:                               # noqa: BLE001 客户端已走
                    return
                last_beat = time.time()
            time.sleep(0.2)
        if "error" in box:
            err = ("data: " + json.dumps({"error": box["error"]}, ensure_ascii=False) + "\n\n").encode("utf-8")
            self._chunk(err + b"data: [DONE]\n\n")
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
            return
        payload = box.get("payload") or {}
        msg = ((payload.get("choices") or [{}])[0].get("message") or {})
        text = msg.get("content") or ""
        note = payload.get("_gbt_fallback") or {}
        head = text
        if note and not text.startswith("〔兜底"):
            head = ("〔兜底 %s：主引擎报错/连不上（不是慢），这一答不是自有权重〕\n"
                    % str(note.get("via") or "").replace("fallback:", "")) + text
        model = payload.get("model") or "/runpod-volume/gbt-v8-v83"
        now = int(time.time())
        usage = payload.get("usage") or {}
        chunks = [
            {"id": "chatcmpl-gbt-fb", "object": "chat.completion.chunk", "model": model,
             "created": now, "system_fingerprint": "gbt-v8-fallback",
             "choices": [{"index": 0, "delta": {"role": "assistant", "content": head}, "finish_reason": None}]},
            {"id": "chatcmpl-gbt-fb", "object": "chat.completion.chunk", "model": model,
             "created": now, "system_fingerprint": "gbt-v8-fallback",
             "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": usage},
        ]
        try:
            for c in chunks:
                self._chunk(("data: " + json.dumps(c, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self._chunk(b"data: [DONE]\n\n")
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except Exception:                                       # noqa: BLE001
            pass
        self.close_connection = True

    def _relay_from_body(self, payload: dict) -> None:
        msg = ((payload.get("choices") or [{}])[0].get("message") or {})
        text = msg.get("content") or ""
        note = payload.get("_gbt_fallback") or {}
        # 兜底标记只加一次：`_mark` 已在正文首行写过，这里别再套一层（否则出现双标记）
        if note and not text.startswith("〔兜底"):
            head = ("〔兜底 %s：主引擎冷启动超时，这一答不是自有权重〕\n"
                    % str(note.get("via") or "").replace("fallback:", "")) + text
        else:
            head = text
        model = payload.get("model") or "/runpod-volume/gbt-v8-v83"
        now = int(time.time())
        usage = payload.get("usage") or {}
        chunks = [
            {"id": "chatcmpl-gbt-fb", "object": "chat.completion.chunk", "model": model,
             "created": now, "system_fingerprint": "gbt-v8-fallback",
             "choices": [{"index": 0, "delta": {"role": "assistant", "content": head},
                          "finish_reason": None}]},
            {"id": "chatcmpl-gbt-fb", "object": "chat.completion.chunk", "model": model,
             "created": now, "system_fingerprint": "gbt-v8-fallback",
             "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": usage},
        ]
        body = "".join("data: " + json.dumps(c, ensure_ascii=False) + "\n\n" for c in chunks)
        body += "data: [DONE]\n\n"
        blob = body.encode("utf-8")
        # 🔴 必须带 Content-Length：HTTP/1.1 下既不发 Content-Length 也不分块，客户端会一直
        #   等"还有没有后续字节" ⇒ 页面显示 `Connection error`（2026-10-21 实测 5 次重试全挂）。
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._cors()
        self.end_headers()
        self.wfile.write(blob)
        self.wfile.flush()
        self.close_connection = True


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                       # noqa: BLE001
            pass
    base, key, src = primary()
    print("llm-fallback-proxy · 127.0.0.1:%d" % PORT)
    print("  主引擎: %s · 钥 %s · 等 %dms" % (base or "(未配)", src, TIMEOUT_MS))
    print("  兜底链: %s" % " -> ".join("%s(%s)" % (f["name"], f["model"]) for f in FALLBACKS))
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
