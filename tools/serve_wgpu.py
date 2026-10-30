#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serve_wgpu —— 带 COOP/COEP 的静态服务（浏览器跑 wasm + WebGPU 的前提）

## 为什么要单独一个服务
浏览器里跑 llama.cpp 的 WASM（wllama / Sipp）必须开 **SharedArrayBuffer**，
而 SharedArrayBuffer 只在这两个响应头都齐了才可用：

    Cross-Origin-Opener-Policy:   same-origin
    Cross-Origin-Embedder-Policy: require-corp

`python3 -m http.server` 不发这两个头 ⇒ wasm 线程起不来，报
"SharedArrayBuffer is not defined"。这不是性能问题，是**开不了**。

## 和现有 8080 的关系（不重复造）
8080 服务普通页面（她的界面、3D 舞台），不需要 SAB。
本服务只服务 `holo_pet_w3/wgpu/` 这一棵子树，专供 WebGPU 推理页。
两个服务并存，各管各的。

## 用法
    python3 tools/serve_wgpu.py [--port 8081] [--root holo_pet_w3/wgpu]
"""
from __future__ import annotations

import argparse
import http.server
import os
import pathlib
import socketserver
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Handler(http.server.SimpleHTTPRequestHandler):
    # 🔴 2026-10-30：页面里的脚本 URL 带固定版本号（?v=20261029），
    #   改了内容但 URL 不变 ⇒ 浏览器一直吃旧缓存，改了等于没改（今天踩了两次）。
    #   在服务端禁掉缓存，比去改 401 个 page 的 script 标签干净。
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def end_headers(self):
        # 这两行是 SharedArrayBuffer 的门
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        # GGUF 很大：允许 Range，让浏览器能分段取而不是整份拉
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("[wgpu] %s - %s\n" % (self.address_string(), fmt % args))


class Threaded(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8081)
    # 🔴 2026-10-30：根原来只到 holo_pet_w3/wgpu ⇒ 页面里 `../shell/tentacle-kit.js`
    #   这类相对路径**跳出根直接 404**，于是 gbtW3 永远 undefined（页面调不到能力位）。
    #   改成以仓库根为服务根：路径语义与 :8080 一致，只是多了 COOP/COEP。
    ap.add_argument("--root", default=".")
    ap.add_argument("--bind", default="127.0.0.1")
    a = ap.parse_args()
    base = (ROOT / a.root).resolve()
    if not base.is_dir():
        print("  root 不存在：%s" % base)
        return 2
    os.chdir(base)
    srv = Threaded((a.bind, a.port), Handler)
    print("  WebGPU 静态服务: http://%s:%d/  (root=%s)" % (a.bind, a.port, a.root))
    print("  已开 COOP/COEP ⇒ SharedArrayBuffer 可用")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
