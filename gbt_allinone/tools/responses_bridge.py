# -*- coding: utf-8 -*-
# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除
"""responses_bridge —— 本机 Responses↔Chat 桥（2026-10-11）。

## 为什么要有它（实测病根）
  Codex 0.155 只认 **Responses API 的流式协议**（收尾必须发 `response.completed`）；
  我们的自托管端点（vLLM）**/responses 会 200**，但**流式不按它的规矩收尾** ⇒ Codex 报
  `stream disconnected before completion: stream closed before response.completed` ✗。
  框架里已有同类先例（agnes 那条就是 wire_api="responses" 指本机代理）⇒ 本件补同一座桥，
  只不过桥的另一头是**我们自己的权重**。

## 干什么
  听 127.0.0.1:4455 · `POST /v1/responses`（流式或非流式）⇒ 转成 `POST <上游>/chat/completions`
  （非流式）⇒ 把答案**改写成 Codex 要的 SSE 事件序列**：
     response.created → response.output_item.added → response.output_text.delta…
     → response.output_item.done → response.completed（带 output 与 usage）

## 铁律
  · 上游地址与密钥只从环境变量读（不动配置、不落盘密钥）；
  · 上游 4xx/5xx 如实透传（不伪装成功）；
  · 只报"转发/改写"，不编模型能力。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("GBT_BRIDGE_UPSTREAM", "").rstrip("/")
KEY = os.environ.get("GBT_BRIDGE_KEY", "")
MODEL = os.environ.get("GBT_BRIDGE_MODEL", "gbt-potato-v8")
PORT = int(os.environ.get("GBT_BRIDGE_PORT", "4455"))


def _up_chat(messages: list, model: str = "", on_wait=None) -> dict:
    # 2026-10-11 实测：Serverless 端点**冷启动期会回 502**（第一次调用要 70~90s 才 ready）
    #   ⇒ 照 cloud_llm 同一条口径：**502/503/504 退避重试**（同一家重试 ≠ 换道，不违反 I1/I2）。
    body = json.dumps({"model": model or MODEL, "messages": messages,
                       "max_tokens": 2000, "temperature": 0.3}).encode("utf-8")
    last = None
    for attempt in range(7):
        req = urllib.request.Request(UPSTREAM + "/chat/completions", data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + KEY})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.loads(r.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as e:
            last = e
            if int(getattr(e, "code", 0)) in (502, 503, 504) and attempt < 6:
                if on_wait:
                    try:
                        on_wait()
                    except Exception:                   # noqa: BLE001
                        pass
                time.sleep(15)
                continue
            raise
        except Exception as e:                      # noqa: BLE001
            last = e
            if attempt < 6:
                time.sleep(10)
                continue
            raise
    raise last if last else RuntimeError("upstream failed")


def _to_messages(p: dict) -> list:
    msgs = []
    if p.get("instructions"):
        msgs.append({"role": "system", "content": str(p["instructions"])})
    inp = p.get("input") or p.get("messages") or ""
    if isinstance(inp, str):
        msgs.append({"role": "user", "content": inp})
    elif isinstance(inp, list):
        for it in inp:
            if isinstance(it, dict):
                role = str(it.get("role") or "user")
                c = it.get("content")
                if isinstance(c, list):
                    txt = "".join(str(x.get("text") or "") for x in c if isinstance(x, dict))
                else:
                    txt = str(c or "")
                msgs.append({"role": role, "content": txt})
            else:
                msgs.append({"role": "user", "content": str(it)})
    if not msgs:
        msgs = [{"role": "user", "content": ""}]
    return msgs


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):        # 静音
        pass

    def do_GET(self):
        if self.path.startswith("/health"):
            self._json(200, {"ok": True, "bridge": "responses_bridge", "upstream": bool(UPSTREAM),
                             "model": MODEL, "port": PORT})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else "{}"
        try:
            p = json.loads(raw or "{}")
        except Exception:
            p = {}
        if not self.path.rstrip("/").endswith("/responses"):
            self._json(404, {"error": {"message": "本桥只服务 /v1/responses"}})
            return
        if not UPSTREAM or not KEY:
            self._json(500, {"error": {"message": "缺 GBT_BRIDGE_UPSTREAM / GBT_BRIDGE_KEY（如实报，不伪装）"}})
            return
        rid = "resp_" + "%x" % int(time.time() * 1000)
        model = str(p.get("model") or MODEL)
        stream = bool(p.get("stream"))
        # 🔴 2026-10-11 实测：Codex 的读超时短 ⇒ **必须先把流开起来**再等上游，
        #    否则冷启动那 70~90s 的静默会被它判成 "stream disconnected"。
        #    ⇒ 流式路径：立刻发 SSE 头 + response.created + 周期心跳，再去等上游。
        if stream:
            # 🔴 2026-10-11 实测：HTTP/1.1 keep-alive 下**不分块**写 SSE ⇒ 客户端不知道流到哪儿结束
            #    （requests 会一直等 ⇒ 读超时）。⇒ 流式这条路**降到 HTTP/1.0 + 关连接界定**。
            self.protocol_version = "HTTP/1.0"
            self.close_connection = True
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def ev0(name: str, obj: dict):
                self.wfile.write(("event: " + name + chr(10)).encode("utf-8"))
                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + chr(10) + chr(10)).encode("utf-8"))
                self.wfile.flush()

            ev0("response.created", {"type": "response.created", "response": {"id": rid, "object": "response",
                "created_at": int(time.time()), "model": model, "status": "in_progress", "output": []}})
            # 🔴 2026-10-11 实测：上游**第一次调用要静默 70~90s**（Serverless 冷启动）⇒ 光发一次
            #    response.created 不够，Codex 自己的 SSE 空闲超时会报
            #    "idle timeout waiting for SSE" ✗ ⇒ 起**后台心跳线程**，等上游期间每 5s 一针。
            import threading as _th
            _stop = _th.Event()

            def _beat():
                # 🔴 2026-10-11 实测：**注释行 `: keep-alive` 不算活动** —— Codex 的 SSE 解析器
                #    只认**真事件** ⇒ 空闲计时照走，报 `idle timeout waiting for SSE` ✗。
                #    ⇒ 心跳改成发**合法事件** `response.in_progress`（Responses 规范里就有 ✓）。
                while not _stop.wait(10):
                    try:
                        ev0("response.in_progress", {"type": "response.in_progress", "response": {
                            "id": rid, "object": "response", "status": "in_progress", "output": []}})
                    except Exception:                       # noqa: BLE001
                        return

            _th.Thread(target=_beat, daemon=True).start()
            try:
                j = _up_chat(_to_messages(p), model, on_wait=lambda: self.wfile.write(b": keep-alive" + bytes([10, 10])) or self.wfile.flush())
            except Exception as e:
                ev0("response.failed", {"type": "response.failed", "response": {"id": rid, "status": "failed",
                     "error": {"message": "上游失败: %s: %s" % (type(e).__name__, str(e)[:160])}}})
                return
            _stop.set()
            txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            usage = j.get("usage") or {}
            item = {"type": "message", "role": "assistant", "id": "msg_" + rid[5:], "content": []}
            ev0("response.output_item.added", {"type": "response.output_item.added", "output_index": 0, "item": item})
            for i in range(0, len(txt), 60):
                ev0("response.output_text.delta", {"type": "response.output_text.delta", "output_index": 0,
                    "content_index": 0, "item_id": item["id"], "delta": txt[i:i + 60]})
            done_item = dict(item)
            done_item["content"] = [{"type": "output_text", "text": txt, "annotations": []}]
            ev0("response.output_text.done", {"type": "response.output_text.done", "output_index": 0,
                "content_index": 0, "item_id": item["id"], "text": txt})
            ev0("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": done_item})
            ev0("response.completed", {"type": "response.completed", "response": {"id": rid, "object": "response",
                "created_at": int(time.time()), "model": model, "status": "completed",
                "output": [done_item], "usage": usage}})
            return
        try:
            j = _up_chat(_to_messages(p), model)
        except Exception as e:
            self._json(502, {"error": {"message": "上游失败: %s: %s" % (type(e).__name__, str(e)[:160])}})
            return
        txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        usage = j.get("usage") or {}
        if not stream:
            self._json(200, {"id": rid, "object": "response", "created_at": int(time.time()),
                             "model": model, "status": "completed",
                             "output": [{"type": "message", "role": "assistant", "id": "msg_" + rid[5:],
                                         "content": [{"type": "output_text", "text": txt, "annotations": []}]}],
                             "usage": usage})
            return
        # 流式：发 Codex 要的事件序列
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def ev(name: str, obj: dict):
            self.wfile.write(("event: " + name + chr(10)).encode("utf-8"))
            self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + chr(10) + chr(10)).encode("utf-8"))
            self.wfile.flush()

        item = {"type": "message", "role": "assistant", "id": "msg_" + rid[5:], "content": []}
        ev("response.created", {"type": "response.created", "response": {"id": rid, "object": "response",
           "created_at": int(time.time()), "model": model, "status": "in_progress", "output": []}})
        ev("response.output_item.added", {"type": "response.output_item.added", "output_index": 0, "item": item})
        for i in range(0, len(txt), 60):
            ev("response.output_text.delta", {"type": "response.output_text.delta", "output_index": 0,
               "content_index": 0, "item_id": item["id"], "delta": txt[i:i + 60]})
        done_item = dict(item)
        done_item["content"] = [{"type": "output_text", "text": txt, "annotations": []}]
        ev("response.output_text.done", {"type": "response.output_text.done", "output_index": 0,
           "content_index": 0, "item_id": item["id"], "text": txt})
        ev("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": done_item})
        ev("response.completed", {"type": "response.completed", "response": {"id": rid, "object": "response",
           "created_at": int(time.time()), "model": model, "status": "completed",
           "output": [done_item], "usage": usage}})

    def _json(self, code: int, obj: dict):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def main():
    if not UPSTREAM or not KEY:
        print("缺 GBT_BRIDGE_UPSTREAM / GBT_BRIDGE_KEY", file=sys.stderr)
        return 2
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print("responses_bridge 听在 http://127.0.0.1:%d/v1  →  上游 %s（模型 %s）" % (PORT, UPSTREAM, MODEL), flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
