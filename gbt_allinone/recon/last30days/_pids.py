# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · last30days 原生层 · 子进程 PID 登记表（同化改写件）。

上游把这个登记表写在入口 `scripts/last30days.py` 里，`lib/bird_x.py` 反向
`from last30days import register_child_pid` 取用 —— 入口与库互相依赖。
同化后拆成独立模块：库与入口都只依赖本文件，依赖方向单一。

语义不变：登记子进程 PID，进程退出时按进程组 SIGTERM 收尾。
"""
from __future__ import annotations

import atexit
import os
import signal
import threading

_child_pids: set[int] = set()
_child_pids_lock = threading.Lock()


def register_child_pid(pid: int) -> None:
    with _child_pids_lock:
        _child_pids.add(pid)


def unregister_child_pid(pid: int) -> None:
    with _child_pids_lock:
        _child_pids.discard(pid)


def _cleanup_children() -> None:
    with _child_pids_lock:
        pids = list(_child_pids)
    for pid in pids:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            continue


atexit.register(_cleanup_children)
