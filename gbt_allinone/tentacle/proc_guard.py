# -*- coding: utf-8 -*-
"""子进程护栏（proc_guard）：蒸馏自 v5 的 `capability_protocol._apply_resource_limits`。

v5 在 Rust/终端形态里给能力子进程加"超时 + 进程树击杀 + 资源限制"；
我们的形态是 Python 子进程（身体桥、外部工具），对应的三条硬护栏是：

  1. **进程树全杀**：Windows 上 `subprocess.kill()` 只杀直接子进程，
     子孙进程会变孤儿继续跑 → 用 `taskkill /T /F` 杀整棵树；
  2. **输出封顶**：子进程输出无上限会吃光内存/把日志撑爆 → 截断并标记 `truncated`；
  3. **环境净化**：默认不带敏感环境变量（token / key / proxy 凭据）给外部工具。

用法：
    from .proc_guard import run_capped
    r = run_capped([py, "-X", "utf8", script], timeout=60, max_chars=200_000)
"""
from __future__ import annotations

import os
import subprocess
import sys

SENSITIVE_ENV = ("GITHUB_TOKEN", "GH_TOKEN", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
                 "ABLITERATION_API_KEY", "HF_TOKEN", "AWS_SECRET_ACCESS_KEY",
                 "AWS_ACCESS_KEY_ID", "KIMI_API_KEY", "MOONSHOT_API_KEY")


def _scrub_env(env: dict | None = None) -> dict:
    base = dict(os.environ if env is None else env)
    for k in list(base):
        if k in SENSITIVE_ENV or k.upper().endswith(("_TOKEN", "_API_KEY", "_SECRET")):
            base.pop(k, None)
    return base


def _kill_tree(pid: int) -> dict:
    """杀整棵进程树（Windows: taskkill /T /F；其它: killpg）。"""
    try:
        if sys.platform.startswith("win"):
            p = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, text=True, timeout=10)
            return {"ok": p.returncode == 0, "how": "taskkill /T /F", "out": (p.stdout or "").strip()[:120]}
        os.killpg(os.getpgid(pid), 9)
        return {"ok": True, "how": "killpg"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "how": "fail", "error": "%s: %s" % (type(e).__name__, str(e)[:100])}


def run_capped(cmd, *, timeout: float = 60.0, max_chars: int = 200_000,
               cwd=None, env=None, scrub: bool = True) -> dict:
    """跑一个子进程：超时杀整棵树、输出封顶、默认净化环境。"""
    e = _scrub_env(env) if scrub else dict(os.environ if env is None else env)
    try:
        p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8",
                             errors="replace", cwd=cwd, env=e,
                             start_new_session=not sys.platform.startswith("win"))
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(ex).__name__, str(ex)[:160]),
                "timed_out": False}
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        killed = _kill_tree(p.pid)
        try:
            out, err = p.communicate(timeout=5)
        except Exception:  # noqa: BLE001
            out, err = "", ""
        return {"ok": False, "timed_out": True, "timeout": timeout,
                "killed": killed, "stdout": (out or "")[:max_chars],
                "stderr": (err or "")[:max_chars], "truncated": False,
                "note": "超时：已杀整棵进程树（不是只杀直接子进程）"}
    trunc = len(out or "") > max_chars or len(err or "") > max_chars
    return {"ok": p.returncode == 0, "returncode": p.returncode,
            "stdout": (out or "")[:max_chars], "stderr": (err or "")[:max_chars],
            "truncated": trunc, "max_chars": max_chars,
            "note": "输出已封顶" if trunc else ""}
