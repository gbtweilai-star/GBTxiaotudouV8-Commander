#!/usr/bin/env python3
"""GBT 模型桥 · asyncio 版（单进程扛数千连接）

为什么要这个：
  ThreadingHTTPServer 是 thread-per-request。实测单进程 512 路就到顶，
  1024 路 TimeoutError，2048 路 `can't start new thread` —— 天花板不是内存，
  是"一个连接一个线程"。

  asyncio 版里一个连接只是一对 reader/writer，没有线程栈。
  内存从 ~1.6 MB/连接 降到 ~10 KB/连接 量级，单进程就能扛数千。

口径（跟同步桥完全一致，不另写一套）：
  · 上游表、降级链、密钥槽、自有权重判定 全部从 model_bridge 复用（单一真源）
  · 同样「连不上 / 超时 / 5xx / 429 才降级」，其余 4xx 如实上报
  · 同样注入 gbt{lane, weights_ours, fallback_from}
  · 同样响应头 X-GBT-Lane / X-GBT-Weights-Ours / X-GBT-Fallback-From

用法：
  python3 runtime/async_gate.py --port 8790
  python3 runtime/async_gate.py --self-test
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "runtime"))

from model_bridge import (  # noqa: E402
    DEFAULT, FALLBACK, OURS_LANES, UPSTREAMS, UA, key_for,
)

MAX_HEADER = 64 * 1024
CORS = (
    "Access-Control-Allow-Origin: *\r\n"
    "Access-Control-Allow-Headers: Content-Type\r\n"
    "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
    "Access-Control-Expose-Headers: X-GBT-Lane, X-GBT-Weights-Ours, X-GBT-Fallback-From\r\n"
)
STATS = {"active": 0, "peak": 0, "served": 0, "failed": 0}


def _split_base(base: str):
    u = urllib.parse.urlsplit(base)
    host = u.hostname or "127.0.0.1"
    port = u.port or (443 if u.scheme == "https" else 80)
    path = u.path.rstrip("/")
    return u.scheme, host, port, path


async def _read_request(reader) -> tuple[str, dict, bytes] | None:
    """读一个 HTTP/1.x 请求。返回 (method, headers, body) 或 None（连不上/超限）。"""
    try:
        head = await reader.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        return None
    if len(head) > MAX_HEADER:
        return None
    lines = head.decode("latin-1").split("\r\n")
    parts = lines[0].split()
    if len(parts) < 2:
        return None
    method, target = parts[0], parts[1]
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    n = int(headers.get("content-length") or 0)
    body = b""
    if n:
        try:
            body = await reader.readexactly(n)
        except asyncio.IncompleteReadError:
            return None
    return method, {"target": target, "headers": headers}, body


def _resp(status: str, body: bytes, ctype: str, extra: str = "") -> bytes:
    return ("HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n%s%s\r\n"
            % (status, ctype, len(body), CORS, extra)).encode("latin-1") + body


async def _call_upstream(name: str, body: dict, timeout: float) -> tuple[bytes, str]:
    """向一个上游发 POST /chat/completions，返回 (原始回包字节, 状态行首行)。"""
    base, model_default, profile, _to = UPSTREAMS[name]
    scheme, host, port, path = _split_base(base)
    key, _slot = key_for(profile)
    if not key:
        return b"", "NO_KEY"
    if name == DEFAULT or name in OURS_LANES:
        body.setdefault("model", model_default)
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = (
        "POST %s/chat/completions HTTP/1.1\r\nHost: %s\r\n"
        "Content-Type: application/json\r\nContent-Length: %d\r\n"
        "User-Agent: %s\r\nAuthorization: Bearer %s\r\n"
        "Accept: application/json\r\nConnection: close\r\n\r\n"
        % (path, host, len(payload), UA, key)
    ).encode("utf-8") + payload

    if scheme == "https":
        import ssl
        ctx = ssl.create_default_context()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ctx, server_hostname=host), timeout)
    else:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout)
    try:
        writer.write(req)
        await writer.drain()
        chunks = []
        t0 = time.monotonic()
        while True:
            left = timeout - (time.monotonic() - t0)
            if left <= 0:
                raise asyncio.TimeoutError
            c = await asyncio.wait_for(reader.read(65536), min(left, timeout))
            if not c:
                break
            chunks.append(c)
        raw = b"".join(chunks)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:                                     # noqa: BLE001
            pass
    head, _, _ = raw.partition(b"\r\n\r\n")
    first = head.split(b"\r\n")[0].decode("latin-1") if head else ""
    return raw, first


async def handle(reader, writer):
    STATS["active"] += 1
    if STATS["active"] > STATS["peak"]:
        STATS["peak"] = STATS["active"]
    try:
        got = await _read_request(reader)
        if got is None:
            return
        method, meta, body = got
        target = meta["target"].split("?")[0]

        if method == "OPTIONS":
            writer.write(_resp("204 No Content", b"", "text/plain"))
            await writer.drain()
            return

        if target == "/health":
            cfg = {n: {"base_url": b, "model_default": m,
                       "key_ready": bool(key_for(p)[0]), "key_slot": key_for(p)[1]}
                   for n, (b, m, p, _t) in UPSTREAMS.items()}
            out = json.dumps({"ok": True, "service": "gbt-async-gate",
                              "default": DEFAULT,
                              "upstreams": cfg,
                              "stats": STATS,
                              "at": time.strftime("%Y-%m-%dT%H:%M:%S")},
                             ensure_ascii=False).encode("utf-8")
            writer.write(_resp("200 OK", out, "application/json; charset=utf-8"))
            await writer.drain()
            STATS["served"] += 1
            return

        if target not in ("/v1/chat/completions", "/v1/models"):
            writer.write(_resp("404 Not Found",
                               b'{"error":{"message":"no route"}}',
                               "application/json"))
            await writer.drain()
            return

        if target == "/v1/models":
            out = json.dumps({"data": [{"id": m or n, "owned_by": n}
                                       for n, (b, m, p, t) in UPSTREAMS.items()]},
                             ensure_ascii=False).encode("utf-8")
            writer.write(_resp("200 OK", out, "application/json; charset=utf-8"))
            await writer.drain()
            return

        try:
            req_body = json.loads(body or b"{}")
        except Exception:                                     # noqa: BLE001
            writer.write(_resp("400 Bad Request",
                               b'{"error":{"message":"body not json"}}',
                               "application/json"))
            await writer.drain()
            return

        explicit = str(req_body.pop("upstream", "") or "").strip()
        first = explicit or DEFAULT
        if first not in UPSTREAMS:
            writer.write(_resp("400 Bad Request",
                               json.dumps({"error": {"message": "unknown upstream: %s" % first}},
                                          ensure_ascii=False).encode(),
                               "application/json; charset=utf-8"))
            await writer.drain()
            return
        allow_fb = req_body.pop("fallback", True) is not False
        chain = [first] + ([n for n in FALLBACK.get(first, []) if n != first] if allow_fb else [])

        tried, used, raw, first_line = [], None, b"", ""
        t0 = time.perf_counter()
        for cand in chain:
            base, model_default, profile, timeout_s = UPSTREAMS[cand]
            if cand != first and model_default:
                req_body["model"] = model_default
            try:
                raw, first_line = await _call_upstream(cand, dict(req_body), timeout_s)
            except asyncio.TimeoutError:
                tried.append({"upstream": cand, "timeout": True}); continue
            except Exception as exc:                          # noqa: BLE001
                tried.append({"upstream": cand, "net": type(exc).__name__}); continue
            if first_line.startswith("HTTP/1.1 5") or " 429" in first_line:
                tried.append({"upstream": cand, "http": first_line.split()[1] if len(first_line.split()) > 1 else "?"})
                continue
            if first_line.startswith("HTTP/1.1 2"):
                used = cand
                break
            # 其余 4xx：如实上报，不掩盖
            used = cand
            break

        if used is None:
            STATS["failed"] += 1
            out = json.dumps({"ok": False, "tried": tried,
                              "error": {"message": "所有上游都连不上"}},
                             ensure_ascii=False).encode("utf-8")
            writer.write(_resp("200 OK", out, "application/json; charset=utf-8"))
            await writer.drain()
            return

        head, _, payload = raw.partition(b"\r\n\r\n")
        dt = round(time.perf_counter() - t0, 2)
        if payload:
            try:
                d = json.loads(payload.decode("utf-8", "replace"))
                d["gbt"] = {"lane": used, "weights_ours": used in OURS_LANES,
                            "fallback_from": first if used != first else None,
                            "elapsed_s": dt, "bridge": "gbt-v8/async-gate"}
                payload = json.dumps(d, ensure_ascii=False).encode("utf-8")
            except Exception:                                 # noqa: BLE001
                pass
        extra = ("X-GBT-Lane: %s\r\nX-GBT-Weights-Ours: %s\r\nX-GBT-Fallback-From: %s\r\n"
                 % (used, "true" if used in OURS_LANES else "false", first))
        code = first_line.split()[1] if len(first_line.split()) > 1 else "200"
        writer.write(_resp("%s X" % code, payload,
                           "application/json; charset=utf-8", extra))
        await writer.drain()
        STATS["served"] += 1
    except Exception:                                         # noqa: BLE001
        STATS["failed"] += 1
    finally:
        STATS["active"] -= 1
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:                                     # noqa: BLE001
            pass


async def serve(port: int) -> None:
    srv = await asyncio.start_server(handle, "127.0.0.1", port, backlog=8192)
    print("asyncio 桥已起：http://127.0.0.1:%d（backlog 8192 · 单进程事件循环）" % port)
    async with srv:
        await srv.serve_forever()


def main() -> int:
    # 🔴 服务端自己的 FD 也必须是松的 —— 只抬客户端没用：
    #    accept() 会用掉服务端自己的描述符，1024 一到就是
    #    "socket.accept() out of system resource"，进程直接被打死。
    try:
        import resource
        _s, _h = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (131072, 131072))
        print("[limits] FD %s → %s" % (_s, resource.getrlimit(resource.RLIMIT_NOFILE)[0]))
    except Exception as _e:                                   # noqa: BLE001
        print("[limits] FD 提不上去：%s" % _e)

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    try:
        asyncio.run(serve(a.port))
    except KeyboardInterrupt:
        print("\n已停。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
