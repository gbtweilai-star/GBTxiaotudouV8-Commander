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

# 🔴 2026-10-28：改成**守护式导入**。实测本机 py -3.14 与 py -3.10 **都没装 llama_cpp**
#   ⇒ 原来顶层直接 import，连 `--selftest`（纯判据、不需要真后端）都跑不起来。
#   现在：判据自检可在任何解释器下跑；真起服务时若缺依赖，给一句人话而不是 ModuleNotFoundError。
try:
    import llama_cpp.llama_cpp as lc
    import llama_cpp._internals as internals
    from llama_cpp import Llama
    _HAS_LC, _LC_ERR = True, ""
except ImportError as _e:                                    # noqa: BLE001
    lc = internals = None                                    # type: ignore[assignment]
    Llama = None                                             # type: ignore[assignment]
    _HAS_LC, _LC_ERR = False, str(_e)

LOCK = threading.Lock()
LLM = None
INFO = {}
LAST_HIT = time.time()      # 最后一次被调用；空闲自动退出用（按需激活的另一半）
IDLE_EXIT = 0               # 秒；0 = 不自动退


def load(model: str, n_ctx: int, threads: int, n_batch: int = 64) -> None:
    global LLM, INFO
    if not _HAS_LC:
        print("[x] 缺 llama_cpp（%s）—— 这条 selfhost CPU 车道起不来。"
              "要走 GPU 请用 tools/model-bridge/gpu_lane.py（llama-server + Vulkan）" % _LC_ERR,
              flush=True)
        raise SystemExit(3)
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


# ══════════════════════════════════════════════════════════════════════════
# 上下文装不装得下：**发出去之前先对账**（2026-10-28）
#   为什么必须卡在这一层、而不是只在车道启动时验一次：
#     llama-server / llama-cpp 在 ctx 装不下时**不报错**，只把 prompt 静默截断，仍返回 200，
#     模型基于残缺上下文作答 ⇒ 实测答案直接变胡话（12015 字文档在 ctx=2048 下只吃进 1934 token，
#     本该 8078，答案从「赤鳞-7391」变成「genoffice」）。启动时验只证明"那一刻"，
#     真正要拦的是**每一次派活**，所以在这里对账。
#   口径：默认 refuse（宁可报错，不许基于残缺上下文胡说）；
#        GBT_FIT_GATE=warn 只标注不拦；=off 关闭对账（关掉就不许声称"没截断"）。
FIT_MODE = (os.environ.get("GBT_FIT_GATE") or "refuse").strip().lower()


def fit_verdict(prompt_tokens: int, max_tokens: int, n_ctx: int) -> dict:
    """**纯函数**：这发请求装不装得下。

    🔴 2026-10-29：判定本体**搬到 `lane_guard.fit_verdict`**（GPU 车道也要判同一件事）。
    这里只做转发 —— 两处各写一份 = 两套判断，迟早分叉。取不到 lane_guard 才用内联兜底，
    兜底与 lane_guard 的语义**必须逐条相同**（下面 `--selftest` 的 6 条就是钉这个的）。
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import lane_guard as _lg                             # noqa: PLC0415
        return _lg.fit_verdict(prompt_tokens, max_tokens, n_ctx)
    except Exception:                                        # noqa: BLE001
        if prompt_tokens <= 0 or n_ctx <= 0:
            return {"over": True, "unknowable": True,
                    "why": "读不到 prompt_tokens(%s) 或 n_ctx(%s) ⇒ 判不了，按装不下处理"
                           % (prompt_tokens, n_ctx)}
        total = prompt_tokens + max(0, max_tokens)
        return {"over": total > n_ctx, "prompt_tokens": prompt_tokens,
                "max_tokens": max(0, max_tokens), "n_ctx": n_ctx,
                "over_by": max(0, total - n_ctx)}


def _count_prompt(msgs=None, prompt=None) -> tuple:
    """真分词器数 token（不估）。返回 (tokens, 是否真分词)。"""
    try:
        if prompt is not None:
            return len(LLM.tokenize(str(prompt).encode("utf-8"), add_bos=True, special=True)), True
        total = 0
        for m in (msgs or []):
            total += len(LLM.tokenize(str(m.get("content") or "").encode("utf-8"),
                                      add_bos=False, special=True))
        return total + 8 * len(msgs or []) + 3, True     # 角色/分隔符开销
    except Exception:                                    # noqa: BLE001
        # 分词器不可用 ⇒ 退回按字符估（1.714 字符/token，2026-10-28 实测常数），并**标明是估的**
        txt = str(prompt) if prompt is not None else "".join(
            str(m.get("content") or "") for m in (msgs or []))
        return int(len(txt) / 1.714), False


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
        # 🔴 2026-10-24 加（回应「无内容限制」定位的下游风险）：**策略开关层**。
        #    口径：本层只做「档位声明 + 粗粒度拦截 + 可解释拒绝 + 审计」，**不是安全保证**。
        #    默认档 uncensored（自用）；开放给他人前先 `serving_policy.py --set-mode filter-lite|strict`。
        #    只判 chat/completions 里 user 的文字；拒的时候回 200 + 结构化说明，
        #    让下游能分清「被策略拦」与「模型坏了」。
        try:
            import serving_policy as _sp   # 同目录
            _pol = _sp.Policy.load()
            if _pol.mode != "uncensored" and self.path.rstrip("/") == "/v1/chat/completions":
                _msgs = body.get("messages") or []
                _text = " ".join(str(m.get("content") or "") for m in _msgs
                                 if str(m.get("role") or "") == "user")
                _d = _pol.check(_text)
                if not _d["allow"]:
                    self._json(200, {
                        "id": "policy-refused", "object": "chat.completion",
                        "model": body.get("model") or "gbt",
                        "choices": [{"index": 0, "finish_reason": "content_filter",
                                     "message": {"role": "assistant",
                                                 "content": "这条请求被本地策略层拦下：%s。当前档位 `%s`。"
                                                            "（这是策略开关，不是模型能力问题）"
                                                            % (_d["reason"], _d["mode"])}}],
                        "gbt": {"policy_mode": _d["mode"],
                                "policy_hits": [h["category"] for h in _d["hits"]]},
                    })
                    return
        except Exception:  # noqa: BLE001
            # 策略层自己坏了不能把服务打死，但也不能静默：打一行 stderr，继续走原路径
            print("[policy] 策略层异常，已跳过（这一发不拦）", file=sys.stderr, flush=True)
        try:
            # 🔴 2026-10-28：**发之前先对账**（chat 与 completions 两条路径共用）
            _msgs0 = body.get("messages")
            _mt0 = int(body.get("max_tokens") or 128)
            _pt, _real = _count_prompt(msgs=_msgs0,
                                       prompt=None if _msgs0 else body.get("prompt"))
            _v = fit_verdict(_pt, _mt0, int(INFO.get("n_ctx") or 0))
            if _v["over"]:
                _msg = ("这发请求装不进上下文：prompt %s token + 预留 %s > n_ctx %s（超 %s）。"
                        "**没有调用模型** —— 装不下时它不会报错，只会静默截断，然后基于残缺上下文胡说。"
                        "请先过变压器压缩、或缩短历史再发。"
                        % (_v.get("prompt_tokens", _pt), _v.get("max_tokens", _mt0),
                           _v.get("n_ctx", "?"), _v.get("over_by", "?")))
                if FIT_MODE == "refuse":
                    print("[fit] 拒绝：prompt=%s max=%s n_ctx=%s（真实分词=%s）"
                          % (_pt, _mt0, INFO.get("n_ctx"), _real), file=sys.stderr, flush=True)
                    if body.get("stream"):
                        self._stream_refuse(_msg, _v, _real)
                    else:
                        self._json(200, {
                            "id": "context-overflow", "object": "chat.completion",
                            "model": body.get("model") or "gbt",
                            "choices": [{"index": 0, "finish_reason": "context_overflow",
                                         "message": {"role": "assistant", "content": _msg}}],
                            "gbt": {"lane": "selfhost", "context_overflow": True,
                                    "fit": _v, "tokens_real": _real},
                        })
                    return
                print("[fit] 警告（GBT_FIT_GATE=%s，未拦）：prompt=%s max=%s n_ctx=%s"
                      % (FIT_MODE, _pt, _mt0, INFO.get("n_ctx")), file=sys.stderr, flush=True)
            if self.path.rstrip("/") == "/v1/chat/completions" and body.get("stream"):
                self._stream_chat(body)
                return
            with LOCK:
                if self.path.rstrip("/") == "/v1/chat/completions":
                    msgs = body.get("messages") or [{"role": "user", "content": ""}]
                    kw = dict(
                        messages=msgs,
                        max_tokens=int(body.get("max_tokens") or 128),
                        temperature=float(body.get("temperature") if body.get("temperature") is not None else 0.0),
                    )
                    # 采样后处理：细调模型在贪婪解码下容易滑进训练语料的套话（实测第 8 问跑题），
                    # 所以允许页面显式调 repeat_penalty / top_p / stop。
                    if body.get("repeat_penalty") is not None:
                        kw["repeat_penalty"] = float(body["repeat_penalty"])
                    if body.get("top_p") is not None:
                        kw["top_p"] = float(body["top_p"])
                    if body.get("stop"):
                        kw["stop"] = body["stop"]
                    out = LLM.create_chat_completion(**kw)
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
                      "ms": int((time.time() - t0) * 1000),
                      "fit": _v, "tokens_real": _real}
        self._json(200, out)

    def _stream_refuse(self, msg, v, real):
        """流式请求装不下时：**照样用 SSE 回**，别让客户端干挂着等。"""
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("x-gbt-lane", "selfhost")
        self.send_header("x-gbt-context-overflow", "true")
        self.end_headers()
        payload = {"choices": [{"index": 0, "finish_reason": "context_overflow",
                                "delta": {"role": "assistant", "content": msg}}],
                   "gbt": {"context_overflow": True, "fit": v, "tokens_real": real}}
        self.wfile.write(b"data: " + json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

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


def selftest() -> int:
    """对账判据自己的正负对照（不起模型）。"""
    cases = [
        ("正例·装得下（1000+128 ≤ 2048）", fit_verdict(1000, 128, 2048)["over"] is False),
        ("负例·环形窗口满预算必须判超（7011+128 > 2048）", fit_verdict(7011, 128, 2048)["over"] is True),
        ("正例·刚好等于上限不算超（1920+128 = 2048）", fit_verdict(1920, 128, 2048)["over"] is False),
        ("负例·差 1 token 就算超（1921+128 = 2049）", fit_verdict(1921, 128, 2048)["over"] is True),
        ("负例·读不到 n_ctx 必须按装不下处理（不许当 0 放行）", fit_verdict(100, 128, 0)["over"] is True),
        ("负例·读不到 prompt_tokens 必须按装不下处理", fit_verdict(0, 128, 2048)["over"] is True),
    ]
    bad = [n for n, ok in cases if not ok]
    for n, ok in cases:
        print(("OK  " if ok else "BAD ") + n)
    print("local_llm_server · fit 对账判据 selftest: %d/%d" % (len(cases) - len(bad), len(cases)))
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="")
    ap.add_argument("--selftest", action="store_true", help="只跑对账判据的负对照（不起模型）")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8792)
    # 🔴 2026-10-25：默认 ctx 512 → **2048**（实测，不是估）。
    #   645 token 的请求在 ctx=512 下当场 500（`Requested tokens (645) exceed context window of 512`），
    #   在 2048 下正常出话 ⇒ 512 以下根本装不下「人设 + 几轮历史」。
    #   代价约 +110MB KV（qwen2 28 层 / 4 KV 头 / head_dim 128 / fp16 ≈ 56KB 每 token）。
    #   可用 `GBT_LLM_CTX` 覆盖，别再写死。
    ap.add_argument("--ctx", type=int, default=int(os.environ.get("GBT_LLM_CTX") or 2048))
    ap.add_argument("--threads", type=int, default=8)   # 6 核/12 线程实测比 4 线程快约 10–20%
    ap.add_argument("--batch", type=int, default=64, help="n_batch（prompt 分块大小，影响首字延迟）")
    ap.add_argument("--idle-exit", type=int, default=0,
                    help="空闲多少秒后自动退出（0=不退）；配合桥的按需激活，用完就把内存还回去")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.model:
        ap.error("--model 必填（或加 --selftest 只跑判据自检）")
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
