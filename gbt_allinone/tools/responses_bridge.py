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
from pathlib import Path
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("GBT_BRIDGE_UPSTREAM", "").rstrip("/")
KEY = os.environ.get("GBT_BRIDGE_KEY", "")
MODEL = os.environ.get("GBT_BRIDGE_MODEL", "gbt-potato-v8")
PORT = int(os.environ.get("GBT_BRIDGE_PORT", "4455"))
_VENDOR = Path(__file__).resolve().parents[2] / "vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))


def _responses_usage(u: dict) -> dict:
    """Chat Completions 的 usage → Responses 的 usage。

    🔴 2026-11-05 实测（Codex 0.166.0-alpha.5.1）：把上游原样的
       {"prompt_tokens": 11, "completion_tokens": 9, "total_tokens": 20}
       塞进 response.completed，Codex 判失败并让**整轮 turn.failed**：
       failed to parse ResponseCompleted: missing field input_tokens
       —— Responses 规范里叫 input_tokens / output_tokens，不叫 prompt/completion。
       缺这一个字段，正文收到了也没用（重试 5 次后放弃）。
    """
    u = u if isinstance(u, dict) else {}

    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    inp = u.get("input_tokens")
    if inp is None:
        inp = u.get("prompt_tokens")
    inp = _int(inp)
    out = u.get("output_tokens")
    if out is None:
        out = u.get("completion_tokens")
    out = _int(out)
    total = u.get("total_tokens")
    total = _int(total) if total is not None else inp + out
    pin = u.get("prompt_tokens_details") or {}
    pout = u.get("completion_tokens_details") or {}
    din = u.get("input_tokens_details") or {}
    dout = u.get("output_tokens_details") or {}
    cached = din.get("cached_tokens")
    if cached is None:
        cached = pin.get("cached_tokens")
    reasoning = dout.get("reasoning_tokens")
    if reasoning is None:
        reasoning = pout.get("reasoning_tokens")
    return {
        "input_tokens": inp,
        "input_tokens_details": {"cached_tokens": _int(cached)},
        "output_tokens": out,
        "output_tokens_details": {"reasoning_tokens": _int(reasoning)},
        "total_tokens": total,
    }


def _up_chat(messages: list, model: str = "", on_wait=None, tools=None, tool_choice=None) -> dict:
    # 2026-10-11 实测：Serverless 端点**冷启动期会回 502**（第一次调用要 70~90s 才 ready）
    #   ⇒ 照 cloud_llm 同一条口径：**502/503/504 退避重试**（同一家重试 ≠ 换道，不违反 I1/I2）。
    payload = {"model": model or MODEL, "messages": messages,
               "max_tokens": 2000, "temperature": 0.3}
    if tools:
        payload["tools"] = tools
    if tools and tool_choice:
        payload["tool_choice"] = tool_choice
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
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


def _tool_specs(p: dict) -> dict:
    """把 Responses function tools 收成 name -> schema。"""
    out = {}
    for item in p.get("tools") or []:
        if not isinstance(item, dict) or item.get("type") != "function":
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        name = str(fn.get("name") or "").strip()
        if name:
            out[name] = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
    return out


def _chat_tools(p: dict) -> list:
    """Responses 工具定义转成 Chat Completions 的形状。"""
    if p.get("tool_choice") == "none":
        return []
    rows = []
    for item in p.get("tools") or []:
        if not isinstance(item, dict) or item.get("type") != "function":
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        if fn.get("name"):
            rows.append({"type": "function", "function": {
                "name": fn["name"], "description": fn.get("description", ""),
                "parameters": fn.get("parameters") or {"type": "object"}}})
    return rows


def _chat_tool_choice(p: dict):
    choice = p.get("tool_choice")
    if isinstance(choice, dict) and choice.get("type") == "function":
        fn = choice.get("function") if isinstance(choice.get("function"), dict) else choice
        if fn.get("name"):
            return {"type": "function", "function": {"name": fn["name"]}}
    return choice


def _to_messages(p: dict) -> list:
    msgs = []
    if p.get("instructions"):
        msgs.append({"role": "system", "content": str(p["instructions"])})
    inp = p.get("input") or p.get("messages") or ""
    if isinstance(inp, str):
        msgs.append({"role": "user", "content": inp})
    elif isinstance(inp, list):
        for it in inp:
            if not isinstance(it, dict):
                msgs.append({"role": "user", "content": str(it)})
                continue
            typ = str(it.get("type") or "")
            if typ == "function_call":
                msgs.append({"role": "assistant", "content": None, "tool_calls": [{
                    "id": str(it.get("call_id") or it.get("id") or ""),
                    "type": "function", "function": {
                        "name": str(it.get("name") or ""),
                        "arguments": str(it.get("arguments") or "{}")}}]})
            elif typ == "function_call_output":
                msgs.append({"role": "tool", "tool_call_id": str(it.get("call_id") or ""),
                             "content": str(it.get("output") or "")})
            else:
                role = str(it.get("role") or "user")
                c = it.get("content")
                if isinstance(c, list):
                    txt = "".join(str(x.get("text") or "") for x in c if isinstance(x, dict))
                else:
                    txt = str(c or "")
                msgs.append({"role": role, "content": txt})
    return msgs or [{"role": "user", "content": ""}]


def _extract_json_object(text: str):
    """从显式工具指令后取一个平衡 JSON 对象，不扫描普通回答。"""
    low = text.lower()
    markers = ("use_tool", "<tool_call>")
    positions = [low.find(m) for m in markers if low.find(m) >= 0]
    if not positions:
        return None
    pos = min(positions)
    start = text.find("{", pos)
    if start < 0:
        return None
    depth, quoted, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
            continue
        if ch == '"':
            quoted = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                raw = text[start:i + 1]
                try:
                    return json.loads(raw)
                except Exception:
                    try:
                        from json_repair import repair_json
                        return repair_json(raw, return_objects=True, skip_json_loads=True)
                    except Exception:
                        return None
    return None


def _schema_accepts(value, schema: dict, depth: int = 0) -> bool:
    if depth > 12 or not isinstance(schema, dict):
        return False
    typ = schema.get("type")
    checks = {"object": lambda v: isinstance(v, dict),
              "array": lambda v: isinstance(v, list),
              "string": lambda v: isinstance(v, str),
              "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
              "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
              "boolean": lambda v: isinstance(v, bool),
              "null": lambda v: v is None}
    if typ in checks and not checks[typ](value):
        return False
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        if any(k not in value for k in (schema.get("required") or [])):
            return False
        if schema.get("additionalProperties") is False and any(k not in props for k in value):
            return False
        for key, val in value.items():
            if key in props and not _schema_accepts(val, props[key], depth + 1):
                return False
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        if any(not _schema_accepts(v, schema["items"], depth + 1) for v in value):
            return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    return True


def _responses_output(j: dict, p: dict, rid: str) -> list:
    msg = ((j.get("choices") or [{}])[0].get("message") or {})
    specs = _tool_specs(p)
    raw_calls = msg.get("tool_calls") or []
    text = str(msg.get("content") or "")
    parsed_from_text = False
    if not raw_calls and specs and p.get("tool_choice") != "none":
        obj = _extract_json_object(text)
        if isinstance(obj, dict):
            parsed_from_text = True
            fn = obj.get("function") or obj.get("name")
            args = obj.get("parameters", obj.get("arguments", {}))
            if isinstance(fn, dict):
                args = fn.get("arguments", args)
                fn = fn.get("name")
            raw_calls = [{"id": "", "type": "function",
                          "function": {"name": fn, "arguments": args}}]
    output = []
    for idx, call in enumerate(raw_calls):
        fn = call.get("function") if isinstance(call, dict) else None
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "")
        schema = specs.get(name)
        if schema is None:
            continue
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                try:
                    from json_repair import repair_json
                    args = repair_json(args, return_objects=True, skip_json_loads=True)
                except Exception:
                    continue
        if not isinstance(args, dict) or not _schema_accepts(args, schema):
            continue
        call_id = str(call.get("id") or ("call_" + rid[5:] + "_" + str(idx)))
        output.append({"type": "function_call", "id": "fc_" + call_id,
                       "call_id": call_id, "name": name,
                       "arguments": json.dumps(args, ensure_ascii=False),
                       "status": "completed"})
    if parsed_from_text and text:
        hits = [text.lower().find(m) for m in ("use_tool", "<tool_call>")
                if text.lower().find(m) >= 0]
        text = text[:min(hits)].strip() if hits else ""
    if text:
        output.insert(0, {"type": "message", "role": "assistant", "id": "msg_" + rid[5:],
                          "content": [{"type": "output_text", "text": text, "annotations": []}]})
    return output


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):        # 静音
        pass

    def do_GET(self):
        if self.path.startswith("/health"):
            self._json(200, {"ok": True, "bridge": "responses_bridge", "upstream": bool(UPSTREAM),
                             "model": MODEL, "port": PORT})
            return
        if "/models" in self.path.split("?")[0]:
            # 🔴 2026-11-05 实测：Codex 0.166 的模型目录**不是** OpenAI 的
            #    {"object":"list","data":[{"id":...}]} —— 那样回会被判
            #    `failed to decode models response: Data at line 1 column 119`。
            #    它要的是自己的 catalog 结构（证据：~/.codex/models_cache.json 顶层）：
            #      {fetched_at, etag, client_version, identity, models:[{slug, display_name, ...}]}
            #    口径：**借它自己写的缓存当模板**（不猜那 40 多个字段名），
            #          再把本桥的 MODEL 追加一条 ⇒ Codex 认得出 profile 里的名字，
            #          不再 `Model metadata ... not found. Defaulting to fallback metadata`。
            #          缓存不在/读不出来就回 404（回到它本来就能工作的行为），不编造。
            home = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
            cache = Path(home) / "models_cache.json"
            payload = None
            try:
                if cache.is_file():
                    payload = json.loads(cache.read_text(encoding="utf-8"))
            except Exception:                        # noqa: BLE001
                payload = None
            if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
                self._json(404, {"error": "not found"})
                return
            models = list(payload["models"])
            if MODEL and MODEL not in {str(m.get("slug") or "") for m in models
                                       if isinstance(m, dict)}:
                tpl = dict(models[0]) if models and isinstance(models[0], dict) else {}
                tpl["slug"] = MODEL
                tpl["display_name"] = MODEL
                tpl["description"] = "DeepSeek，经本机 Responses 桥"
                tpl["visibility"] = "list"
                tpl["supported_in_api"] = True
                models.append(tpl)
            payload["models"] = models
            self._json(200, payload)
            return

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
                j = _up_chat(_to_messages(p), model, on_wait=lambda: self.wfile.write(b": keep-alive" + bytes([10, 10])) or self.wfile.flush(), tools=_chat_tools(p), tool_choice=_chat_tool_choice(p))
            except Exception as e:
                ev0("response.failed", {"type": "response.failed", "response": {"id": rid, "status": "failed",
                     "error": {"message": "上游失败: %s: %s" % (type(e).__name__, str(e)[:160])}}})
                return
            _stop.set()
            output = _responses_output(j, p, rid)
            usage = _responses_usage(j.get("usage"))
            for output_index, item in enumerate(output):
                ev0("response.output_item.added", {"type": "response.output_item.added",
                    "output_index": output_index, "item": item})
                if item.get("type") == "message":
                    txt = (item.get("content") or [{}])[0].get("text") or ""
                    for i in range(0, len(txt), 60):
                        ev0("response.output_text.delta", {"type": "response.output_text.delta",
                            "output_index": output_index, "content_index": 0,
                            "item_id": item["id"], "delta": txt[i:i + 60]})
                    ev0("response.output_text.done", {"type": "response.output_text.done",
                        "output_index": output_index, "content_index": 0,
                        "item_id": item["id"], "text": txt})
                elif item.get("type") == "function_call":
                    args = item.get("arguments") or "{}"
                    ev0("response.function_call_arguments.delta", {
                        "type": "response.function_call_arguments.delta",
                        "output_index": output_index, "item_id": item["id"], "delta": args})
                    ev0("response.function_call_arguments.done", {
                        "type": "response.function_call_arguments.done",
                        "output_index": output_index, "item_id": item["id"], "arguments": args})
                ev0("response.output_item.done", {"type": "response.output_item.done",
                    "output_index": output_index, "item": item})
            ev0("response.completed", {"type": "response.completed", "response": {"id": rid, "object": "response",
                "created_at": int(time.time()), "model": model, "status": "completed",
                "output": output, "usage": usage}})
            return
        try:
            j = _up_chat(_to_messages(p), model, tools=_chat_tools(p), tool_choice=_chat_tool_choice(p))
        except Exception as e:
            self._json(502, {"error": {"message": "上游失败: %s: %s" % (type(e).__name__, str(e)[:160])}})
            return
        output = _responses_output(j, p, rid)
        usage = _responses_usage(j.get("usage"))
        if not stream:
            self._json(200, {"id": rid, "object": "response", "created_at": int(time.time()),
                             "model": model, "status": "completed", "output": output, "usage": usage})
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
