# -*- coding: utf-8 -*-
"""A19 常驻守护（2026-10-31 · 主人令：用触手连起来做常驻）

问题：LM Pocket 的 :1234 只有 App 活着才应答；iOS 把 App 挂起后
      **端口还在（内核替它收连接）但 HTTP 不应答** —— 这是最容易被误判成"通了"的状态。

做法（这就是"用触手连接"）：
  ① 判活只认 /v1/models 真 200（TCP 通不算）
  ② 不通 ⇒ 走 omni 的 scheme 触手 apple-open lmpocket:// 拉起来，等它真应答
  ③ 通了 ⇒ 每 60 秒打一次轻量 keepalive，压住它的空闲回收
  ④ 全程落账 state/a19_resident.jsonl，能算**真实占空比**（在线时间/总时间）
  ⑤ 可选：在线期间让主动引擎用自己的脑子（GBT_A19_BRAIN=1）

重要边界（不骗人）：主人自己切回 Minis 打字时，LM Pocket 会被 iOS 挂起 ——
那是前台互斥，任何触手都改不了。常驻能做的是：**把它自动拉回来**，
让"无人值守时的后台任务"始终有脑子可用。
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG = ROOT / "state" / "a19_resident.jsonl"
KEY = os.environ.get("GBT_A19_KEY") or "gbt"


def http_ok(tmo: float = 5.0) -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models",
                                     headers={"Authorization": "Bearer " + KEY})
        with urllib.request.urlopen(req, timeout=tmo) as r:
            return r.status == 200
    except Exception:                                               # noqa: BLE001
        return False


def tcp_open(tmo: float = 1.2) -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", 1234), timeout=tmo)
        s.close()
        return True
    except Exception:                                               # noqa: BLE001
        return False


def wake(wait_s: float = 45.0) -> bool:
    """用 scheme 触手把 App 拉起来，并等它**真应答**（不是只看端口）。"""
    try:
        subprocess.run(["apple-open", "lmpocket://"], capture_output=True, timeout=25)
    except Exception:                                               # noqa: BLE001
        pass
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if http_ok(3):
            return True
        time.sleep(1.5)
    return False


def log(rec: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run(interval: float = 20.0, keepalive: float = 60.0) -> None:
    up_since = None
    down_since = time.time()
    samples_ok = 0
    samples_all = 0
    last_ka = 0.0
    print("  A19 常驻守护启动 · 探测 %.0fs / keepalive %.0fs" % (interval, keepalive), flush=True)
    while True:
        samples_all += 1
        ok = http_ok()
        if ok:
            samples_ok += 1
            if up_since is None:
                up_since = time.time()
                down_for = round(up_since - down_since, 1)
                log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "act": "up", "down_for_s": down_for})
                print("  ✅ 在线（刚才断了 %.1fs）" % down_for, flush=True)
            if keepalive and time.time() - last_ka >= keepalive:
                last_ka = time.time()
                try:                                                # 轻量 keepalive
                    req = urllib.request.Request("http://127.0.0.1:1234/v1/models",
                                                 headers={"Authorization": "Bearer " + KEY})
                    urllib.request.urlopen(req, timeout=6).read()
                except Exception:                                   # noqa: BLE001
                    pass
        else:
            if up_since is not None:
                log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "act": "down",
                     "up_for_s": round(time.time() - up_since, 1),
                     "tcp_only": tcp_open()})
                up_since = None
                down_since = time.time()
                print("  🔴 掉了（%s）⇒ 用 scheme 触手拉起" %
                      ("端口在但 HTTP 不应答" if tcp_open() else "端口关闭"), flush=True)
            if wake():
                print("  ✅ 拉起成功，已能应答", flush=True)
            else:
                log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "act": "wake_failed",
                     "tcp_only": tcp_open()})
        time.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        print(json.dumps({"http_ok": http_ok(), "tcp_open": tcp_open()}, ensure_ascii=False))
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "wake":
        print("  wake →", wake())
        sys.exit(0)
    run()
