#!/usr/bin/env python3
"""自适应监听队列 —— 按压力自动跟随，不写死数字

为什么要有这个：
  `socketserver.TCPServer.request_queue_size` **默认只有 5**。这是 `listen(2)` 的
  backlog —— 内核挂起的**未完成三次握手**连接队列长度。并发一上来，超出的连接
  在队列里就被丢掉，客户端看到 `URLError` / `connection reset`。

  实测（本机，model_bridge）：
    默认 5    →  96 路就掉 7 个，192 路掉 72 个
    写死 1024 →  128/192 路零失败
  但写死一个大数只是把阈值往后推，既不省资源也不自适应。

所以这里做成**闭环**：
  · 每秒采样一次当前在处理的连接数（active）与这一秒的峰值（peak）
  · 目标队列 = clamp(peak × 2, 下限 64, 上限 8192)  —— 跟着压力走
  · 压力回落就自动收窄（peak 会随 active 一起降下来）
  · 变化时重调 `socket.listen(n)`（Linux 允许重复调用改 backlog，无需重开端口）
  · 每次调整都写一行日志，可追溯

口径：
  · 只调 backlog，**不限制任何并发**。这个模块不拒绝请求、不排队、不丢包。
  · 提不上去（O_SError）就保持原值，绝不因此让服务起不来。
"""
from __future__ import annotations

import sys
import threading
import time
from http.server import ThreadingHTTPServer

MIN_BACKLOG = 64
MAX_BACKLOG = 8192
TICK = 1.0          # 采样周期（秒）
HEADROOM = 2        # 目标 = 峰值 × 这个系数


class AdaptiveThreadingHTTPServer(ThreadingHTTPServer):
    """监听队列跟着压力自动走的 ThreadingHTTPServer。"""

    # 绑定时先用的初始值（服务一起来就有基本容量，不等第一次 tick）
    request_queue_size = MIN_BACKLOG
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, *args, **kwargs):
        self._lock = threading.Lock()
        self._active = 0
        self._peak = 0
        self._cur_backlog = int(self.request_queue_size)
        self._last_reported = self._cur_backlog
        super().__init__(*args, **kwargs)
        t = threading.Thread(target=self._tune_loop, name="backlog-tuner", daemon=True)
        t.start()

    # ── 计数：连接进来 +1，收工 -1 ───────────────────────────────
    def process_request(self, request, client_address):  # noqa: D401
        with self._lock:
            self._active += 1
            if self._active > self._peak:
                self._peak = self._active
        super().process_request(request, client_address)

    def shutdown_request(self, request):                  # noqa: D401
        try:
            super().shutdown_request(request)
        finally:
            with self._lock:
                self._active -= 1

    # ── 调压循环 ────────────────────────────────────────────────
    def _tune_loop(self) -> None:
        while True:
            time.sleep(TICK)
            with self._lock:
                active = self._active
                peak = self._peak
                self._peak = active          # 每秒重置峰值，跟随瞬时压力
                cur = self._cur_backlog
            # 目标：峰值连同当前在跑的都要容纳，再留一倍余量
            want = max(peak, active) * HEADROOM
            target = max(MIN_BACKLOG, min(MAX_BACKLOG, want))
            # 已经够用就别动（避免抖动）：低于当前的一半才收窄
            if target <= cur and cur <= target * 2:
                continue
            try:
                self.socket.listen(target)
            except OSError as exc:               # noqa: BLE001
                sys.stderr.write("[backlog] 调不了 %d（%s），保持 %d\n"
                                 % (target, exc, cur))
                continue
            with self._lock:
                self._cur_backlog = target
            sys.stderr.write("[backlog] %d → %d（在跑 %d · 峰值 %d）\n"
                             % (cur, target, active, peak))

    # ── 只读：给 /health 之类看的 ───────────────────────────────
    def backlog_stats(self) -> dict:
        with self._lock:
            return {"active": self._active, "peak": self._peak,
                    "backlog": self._cur_backlog,
                    "min": MIN_BACKLOG, "max": MAX_BACKLOG}
