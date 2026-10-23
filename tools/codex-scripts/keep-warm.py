# -*- coding: utf-8 -*-
"""keep-warm —— 让我们自己的引擎**一直热着**，页面才是秒级响应。

为什么必须有它（2026-10-21 实测，不是猜）：
  · RunPod serverless 端点现配 `workersMin=0` —— 仓库自己的 `llm-lane-direct.py` 就写着
    「冷启动 92s~300s」，`model-align.py` 也写着「idleTimeout=5s、workersMin=0 ⇒ 每个请求都要等」。
    这是**部署配置**的属性，页面侧再怎么等也变不出秒级。
  · 真正能改配置的是 RunPod 控制台的 Min Workers（需要账户级 REST key）；我手上只有端点 `rpa_` 钥，
    改不了 —— 所以用**保温请求**等效：每 120 秒打一次最小 chat，让 worker 不缩到 0。
  · 代价：持续占用一个 worker（持续计费）。停：删 `outputs/model-bridge/keep-warm.stop` 会退出，
    或直接 `job_kill`。

行为：最小请求（max_tokens=1）→ 记录往返毫秒 → 写 `outputs/model-bridge/keep-warm.log`；
      失败不重试轰炸（上限 1 次/轮，间隔固定 120s），并把原因如实写进日志。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
STOP = ROOT / "outputs" / "model-bridge" / "keep-warm.stop"
LOG = ROOT / "outputs" / "model-bridge" / "keep-warm.log"
INTERVAL_S = float(os.environ.get("GBT_KEEPWARM_S") or 120)
HARD_TIMEOUT_S = float(os.environ.get("GBT_KEEPWARM_TIMEOUT_S") or 150)


def env_or_reg(name: str) -> str:
    v = os.environ.get(name) or ""
    if v:
        return v
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return str(winreg.QueryValueEx(k, name)[0] or "")
    except Exception:                                          # noqa: BLE001
        return ""


def log(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), line))
    print(line, flush=True)


def ping() -> tuple[bool, int, str]:
    base = (env_or_reg("GBT_POTATO_BASE_URL") or "").rstrip("/")
    key = env_or_reg("GBT_POTATO_API_KEY")
    if not base or not key:
        return False, 0, "缺 base/key"
    body = json.dumps({"model": "/runpod-volume/gbt-v8-v83", "max_tokens": 1,
                       "messages": [{"role": "user", "content": "."}]}).encode("utf-8")
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key,
        "User-Agent": "GBTxiaotudouV8-keepwarm/1.0"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=HARD_TIMEOUT_S) as r:
            r.read()
        return True, int((time.time() - t0) * 1000), ""
    except Exception as exc:                                   # noqa: BLE001
        return False, int((time.time() - t0) * 1000), "%s: %s" % (type(exc).__name__, str(exc)[:120])


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                       # noqa: BLE001
            pass
    log("START interval=%ss timeout=%ss" % (INTERVAL_S, HARD_TIMEOUT_S))
    rounds = 0
    while True:
        if STOP.exists():
            log("STOP (发现 keep-warm.stop)")
            return 0
        ok, ms, why = ping()
        rounds += 1
        if ok:
            log("PING ok %dms (round %d)" % (ms, rounds))
        else:
            log("PING fail %dms %s" % (ms, why))
        # 分片睡：便于及时响应 stop 文件
        for _ in range(int(INTERVAL_S)):
            if STOP.exists():
                break
            time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
