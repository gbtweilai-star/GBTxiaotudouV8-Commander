"""本地假 vLLM（OpenAI 兼容）—— 没 GPU 也能把「DSH → 适配器 → 端点」这条链**跑通并验收**。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它（主人令：以插件部署出我们自己的模型）
真部署的**唯一硬卡点**是算力（GPU）。但**接线**这一段**现在就能验完**：
`dsh-llm-qwen-local` 要的只是一个 OpenAI 兼容端点（`GET /v1/models` + `POST /v1/chat/completions`）。
⇒ 本件起一个**标准库假端点**，把整条链的形状先钉死；等 GPU 到位，只需要**把 baseURL 换成真地址**。
（插件作者自己的测试也是这么干的：README 写着「tests run against a scripted in-process vLLM (SSE) mock」。）

## 口径
- **只跑本机 127.0.0.1**；不发任何外网请求；
- 回复形状按 OpenAI 契约：`choices[0].message.content`（+ 可选 `reasoning_content`，对应 `--reasoning-parser qwen3`）；
- **它不代表模型能力**：这是**假端点**，只用来验"接线通不通、形状对不对" ⇒ 输出里必须写明。

用法：
  python tools/codex-scripts/mock-vllm-endpoint.py serve --port 8111 --model-id gbt-potato-v8
  python tools/codex-scripts/mock-vllm-endpoint.py preflight     # 起一次 + 打两个接口 + 断言形状 + 关掉
  python tools/codex-scripts/mock-vllm-endpoint.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
_CFG = {"model_id": "gbt-potato-v8", "name": "GBT小土豆V8 原生（假端点 · 仅验接线）"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def models_payload(model_id: str) -> dict:
    return {"object": "list", "data": [{"id": model_id, "object": "model", "owned_by": "gbt"}]}


def chat_payload(model_id: str, body: dict) -> dict:
    """按 OpenAI 契约回一个**形状正确**的答复（内容与能力无关，如实标它是假端点）。"""
    msgs = body.get("messages") if isinstance(body.get("messages"), list) else []
    last = msgs[-1].get("content") if msgs and isinstance(msgs[-1], dict) else ""
    if not isinstance(last, str):
        last = json.dumps(last, ensure_ascii=False)[:200]
    import re
    m = re.search(r"你是谁|who are you|你的名字", str(last), re.I)
    text = ("我是 GBT小土豆V8（由 dsh-llm-qwen-local 适配器接进来的本地端点）。"
            "⚠️ 当前是**假端点**，只用于验证接线与形状，不代表真实模型能力。") if m else \
           ("（假端点回显）收到 %d 条消息，最后一条：%s" % (len(msgs), str(last)[:120]))
    return {"id": "chatcmpl-mock", "object": "chat.completion", "created": int(time.time()),
            "model": model_id,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": text,
                                     "reasoning_content": "（假端点的推理字段占位）"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


# 1×1 的真 PNG（67 字节）。为什么塞真 PNG：让图像面的管道验收能一路验到**字节**
# （解 base64 → 头部签名 → 落盘字节数），而不是只验"回了个字符串"。
TINY_PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/"
                "q842iQAAAABJRU5ErkJggg==")


class _H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):                       # 静音；要看得见就自己 print
        pass

    def _send(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):                                # noqa: N802
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            self._send(200, models_payload(_CFG["model_id"]))
        elif self.path.rstrip("/") in ("/health", "/"):
            self._send(200, {"ok": True, "假端点": True})
        else:
            self._send(404, {"error": {"message": "not found: %s" % self.path}})

    def do_POST(self):                               # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            self._send(400, {"error": {"message": "body 不是 JSON"}})
            return
        if self.path.rstrip("/") in ("/v1/images/generations", "/images/generations"):
            # 图像面（形态与 OpenAI 的 images 接口一致：`{prompt,size,n}` → `{data:[{b64_json}]}`）。
            # 回一张**真的最小 PNG**（1×1），这样"管道验收"能一路验到**字节落盘**，
            # 而不是只验到"有个字符串"。它不是画，只是管道证据 —— 别念成"能出图了"。
            if not body.get("prompt"):
                self._send(400, {"error": {"message": "prompt 为空"}})
                return
            n = int(body.get("n") or 1)
            self._send(200, {
                "created": int(time.time()),
                "model": body.get("model") or _CFG["model_id"],
                "data": [{"b64_json": TINY_PNG_B64, "revised_prompt": str(body.get("prompt"))[:120],
                          "_size": body.get("size") or "1024x1024"} for _ in range(max(1, min(n, 4)))],
            })
            return
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, {"error": {"message": "not found: %s" % self.path}})
            return
        if not body.get("messages"):
            self._send(400, {"error": {"message": "messages 为空"}})
            return
        self._send(200, chat_payload(_CFG["model_id"], body))


def start_server(port: int, model_id: str) -> ThreadingHTTPServer:
    _CFG["model_id"] = model_id
    srv = ThreadingHTTPServer((HOST, port), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _get(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:      # noqa: S310（本机）
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _post(url: str, obj: dict, timeout: float = 5.0):
    req = urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310（本机）
        return json.loads(r.read().decode("utf-8", errors="replace"))


def preflight(port: int, model_id: str, keep: bool = False) -> int:
    srv = start_server(port, model_id)
    base = "http://%s:%d/v1" % (HOST, port)
    try:
        m = _get(base + "/models")
        ids = [d.get("id") for d in (m.get("data") or [])]
        c = _post(base + "/chat/completions",
                  {"model": model_id, "messages": [{"role": "user", "content": "你是谁？"}]})
        msg = ((c.get("choices") or [{}])[0].get("message") or {})
        ok_models = model_id in ids
        ok_chat = bool(msg.get("content"))
        print(json.dumps({
            "假端点": "%s:%d" % (HOST, port), "模型 id": model_id,
            "① /v1/models": {"过": ok_models, "读到的 id": ids},
            "② /v1/chat/completions": {"过": ok_chat,
                                       "有 content": ok_chat, "有 reasoning_content":
                                       "reasoning_content" in msg},
            "③ 身份自述": str(msg.get("content"))[:70],
            "④ 404 分支": (lambda: (lambda: (urllib.request.urlopen(
                base.rsplit("/v1", 1)[0] + "/nope", timeout=3)))() and False)() if False else "见 selftest",
            "口径": "**假端点**：只验「接线通不通/形状对不对」，**不代表模型能力**；"
            "换真地址 = 把 baseURL 指到 GPU 机器上的 vLLM",
            "判决": "✅ 接线形状验收通过（可以接真端点）" if (ok_models and ok_chat) else "🔴 形状不对",
        }, ensure_ascii=False, indent=1))
        if keep:
            print("（--keep：端点继续跑，Ctrl-C 停）")
            while True:
                time.sleep(1)
        return 0 if (ok_models and ok_chat) else 1
    finally:
        if not keep:
            srv.shutdown()


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    m = models_payload("x1")
    ck("**正控：/v1/models 形状对**",
       m.get("object") == "list" and m["data"][0]["id"] == "x1", "")
    c = chat_payload("x1", {"messages": [{"role": "user", "content": "你是谁"}]})
    msg = c["choices"][0]["message"]
    ck("**正控：chat 回复形状对（含 content / reasoning_content）**",
       bool(msg.get("content")) and "reasoning_content" in msg and c["object"] == "chat.completion", "")
    c2 = chat_payload("x1", {"messages": [{"role": "user", "content": "写个冒泡排序"}]})
    ck("**负控：非身份问句不许统一回「我是 GBT小土豆V8」**（假端点回显，不装能力）",
       "假端点回显" in c2["choices"][0]["message"]["content"], "")
    import http.client
    srv = start_server(8311, "st-model")
    try:
        conn = http.client.HTTPConnection(HOST, 8311, timeout=5)
        conn.request("GET", "/nope")
        r = conn.getresponse()
        r.read()                                        # 🔴 必须读干 body，否则下一发 ResponseNotReady
        ck("**边界：未知路径 ⇒ 404**", r.status == 404, "status=%d" % r.status)
        conn.request("POST", "/v1/chat/completions", body=b'{"model":"x","messages":[]}',
                     headers={"Content-Type": "application/json"})
        r2 = conn.getresponse()
        r2.read()
        ck("**边界：messages 为空 ⇒ 400**", r2.status == 400, "status=%d" % r2.status)
        conn.close()
    finally:
        srv.shutdown()
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["serve", "preflight", "selftest"])
    ap.add_argument("--port", type=int, default=8111)
    ap.add_argument("--model-id", default="gbt-potato-v8")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "preflight":
        return preflight(a.port, a.model_id, a.keep)
    srv = start_server(a.port, a.model_id)
    print("假端点已起：http://%s:%d/v1（模型 id=%s · Ctrl-C 停）" % (HOST, a.port, a.model_id))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
