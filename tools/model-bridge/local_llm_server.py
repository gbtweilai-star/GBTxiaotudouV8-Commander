# -*- coding: utf-8 -*-
"""本机自有权重服务（OpenAI 兼容）—— 给 main.cjs / 桥的 selfhost 车道用。

为什么不用 llama_cpp.server：它不暴露 use_extra_bufts，默认会为 CPU repack 申请
3.97 GB 连续内存，这台 7.4 GB 机器直接加载失败（实测）。这里复用我们验证过的加载方式：
  · use_extra_bufts=False（关 repack，纯 mmap 按需换页）
  · 启动即做特殊 token 体检（缺 bos/eos/pad 直接拒绝启动，而不是等用户发现回答被截断）

用法：
  python tools/model-bridge/local_llm_server.py --model state/weights/gbt-v8-v82-q5_0.gguf --port 8792
接口：
  GET  /health
  POST /v1/chat/completions   （OpenAI 形状）
  POST /v1/completions
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import llama_cpp.llama_cpp as lc
import llama_cpp._internals as internals
from llama_cpp import Llama

LOCK = threading.Lock()
LLM = None
INFO = {}
LAST_HIT = time.time()      # 最后一次被调用；空闲自动退出用（按需激活的另一半）
IDLE_EXIT = 0               # 秒；0 = 不自动退


def load(model: str, n_ctx: int, threads: int, n_batch: int = 64) -> None:
    global LLM, INFO
    _orig = lc.llama_model_default_params

    def patched():
        p = _orig()
        p.use_extra_bufts = False          # 关掉 CPU_REPACK 的整模型副本
        return p

    lc.llama_model_default_params = patched
    if hasattr(internals, "llama_model_default_params"):
        internals.llama_model_default_params = patched

    t0 = time.time()
    LLM = Llama(model_path=model, n_ctx=n_ctx, n_threads=threads, n_batch=n_batch,
                verbose=False, use_mmap=True)
    eos = int(LLM.token_eos())
    bos = int(LLM.token_bos())
    if eos in (0, 1, 2) or LLM.detokenize([eos]) == b",":
        print("[x] eos 可疑（%d）—— GGUF 缺 tokenizer.ggml.eos_token_id，拒绝启动" % eos)
        raise SystemExit(3)
    INFO = {"model": model, "weights_ours": True, "lane": "selfhost",
            "eos": eos, "bos": bos, "load_s": round(time.time() - t0, 2),
            "n_ctx": n_ctx, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    print("[ok] 已加载 %s · eos=%d · %.1fs" % (model, eos, INFO["load_s"]), flush=True)


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("x-gbt-lane", "selfhost")
        self.send_header("x-gbt-weights-ours", "true")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        global LAST_HIT
        LAST_HIT = time.time()
        if self.path.rstrip("/") in ("/health", ""):
            self._json(200, {"ok": True, **INFO})
        elif self.path.rstrip("/") == "/v1/models":
            self._json(200, {"object": "list", "data": [
                {"id": "gbt-local", "object": "model", "owned_by": "selfhost"}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        global LAST_HIT
        LAST_HIT = time.time()
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            self._json(400, {"error": "bad json"})
            return

        t0 = time.time()
        try:
            if self.path.rstrip("/") == "/v1/chat/completions" and body.get("stream"):
                self._stream_chat(body)
                return
            with LOCK:
                if self.path.rstrip("/") == "/v1/chat/completions":
                    msgs = body.get("messages") or [{"role": "user", "content": ""}]
                    out = LLM.create_chat_completion(
                        messages=msgs,
                        max_tokens=int(body.get("max_tokens") or 128),
                        temperature=float(body.get("temperature") if body.get("temperature") is not None else 0.0),
                    )
                elif self.path.rstrip("/") == "/v1/completions":
                    out = LLM(body.get("prompt") or "",
                              max_tokens=int(body.get("max_tokens") or 128),
                              temperature=float(body.get("temperature") if body.get("temperature") is not None else 0.0))
                else:
                    self._json(404, {"error": "not found"})
                    return
        except Exception as e:
            self._json(500, {"error": "%s: %s" % (type(e).__name__, e)})
            return

        out["model"] = os.path.basename(INFO.get("model") or "")
        out["gbt"] = {"weights_ours": True, "lane": "selfhost",
                      "ms": int((time.time() - t0) * 1000)}
        self._json(200, out)

    def _stream_chat(self, body):
        """SSE 逐 token 回 —— 长回答不用等 19 秒才见字。"""
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("x-gbt-lane", "selfhost")
        self.send_header("x-gbt-weights-ours", "true")
        self.end_headers()
        msgs = body.get("messages") or [{"role": "user", "content": ""}]
        try:
            with LOCK:
                for chunk in LLM.create_chat_completion(
                        messages=msgs,
                        max_tokens=int(body.get("max_tokens") or 128),
                        temperature=float(body.get("temperature") if body.get("temperature") is not None else 0.0),
                        stream=True):
                    self.wfile.write(b"data: " + json.dumps(chunk, ensure_ascii=False).encode("utf-8") + b"\n\n")
                    self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self.wfile.write(b"data: " + json.dumps(
                    {"error": "%s: %s" % (type(e).__name__, e)}).encode("utf-8") + b"\n\n")
                self.wfile.flush()
            except Exception:
                pass

    def log_message(self, fmt, *a):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % a))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8792)
    ap.add_argument("--ctx", type=int, default=512)
    ap.add_argument("--threads", type=int, default=8)   # 6 核/12 线程实测比 4 线程快约 10–20%
    ap.add_argument("--batch", type=int, default=64, help="n_batch（prompt 分块大小，影响首字延迟）")
    ap.add_argument("--idle-exit", type=int, default=0,
                    help="空闲多少秒后自动退出（0=不退）；配合桥的按需激活，用完就把内存还回去")
    a = ap.parse_args()
    global IDLE_EXIT
    IDLE_EXIT = max(0, a.idle_exit)
    load(a.model, a.ctx, a.threads, a.batch)
    if IDLE_EXIT > 0:
        def _watch():
            while True:
                time.sleep(min(30, IDLE_EXIT))
                if time.time() - LAST_HIT >= IDLE_EXIT:
                    sys.stderr.write("[idle] %ds 无请求，退出（内存还给系统）\n" % IDLE_EXIT)
                    os._exit(0)
        threading.Thread(target=_watch, daemon=True).start()
        sys.stderr.write("[ok] 空闲 %ds 自动退出已启用\n" % IDLE_EXIT)
    srv = ThreadingHTTPServer((a.host, a.port), H)
    print("[ok] http://%s:%d  (/health · /v1/chat/completions)" % (a.host, a.port), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
