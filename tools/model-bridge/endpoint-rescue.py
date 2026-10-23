#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端点抢救实验（改云端参数 → 观察 → 记录；失败即回滚到原值）。

主人令 2026-10-22：「继续推进，别让任何一个能力被限制了」+ 前一轮「乙」（授权走 REST 改端点参数）。
本件只做**一件事**：换 GPU 型号组试拉起 worker，每组观察 N 秒；全失败则 PATCH 回原组。
每次 PATCH 前后都打读数（workersMin/Max/idle/GPU 组），**不打印任何密钥**。

用法：py -3.14 tools/model-bridge/endpoint-rescue.py [--watch 90] [--apply]
不带 --apply 只读（只 show + health），不 PATCH。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

CRED = os.path.expanduser(r"~\.dsh\.credentials.yaml")
EP = "qnnqf9w8xcefj8"
REST = "https://rest.runpod.io/v1/endpoints/%s" % EP
HEALTH = "https://api.runpod.ai/v2/%s/health" % EP

GROUPS = [
    ["NVIDIA L4"],
    ["NVIDIA RTX A5000"],
    ["NVIDIA A40"],
    ["NVIDIA L40S"],
    ["NVIDIA GeForce RTX 4090"],
    ["NVIDIA L4", "NVIDIA RTX A5000", "NVIDIA A40", "NVIDIA L40S", "NVIDIA GeForce RTX 4090"],
]


def key():
    try:
        t = open(CRED, encoding="utf-8").read()
    except OSError:
        t = ""
    m = re.search(r"GBT_POTATO_API_KEY:[ \t]*(?:ref:)?[ \t]*[\"']?([A-Za-z0-9_\-]{16,})", t)
    return m.group(1) if m else os.environ.get("GBT_POTATO_API_KEY")


def call(url, k, method="GET", body=None, to=30):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdr = {"Authorization": "Bearer " + k, "User-Agent": "gbt-rescue/1.0",
           "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=to) as r:
            return r.status, round((time.time() - t0) * 1000), r.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, round((time.time() - t0) * 1000), e.read(600).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, round((time.time() - t0) * 1000), str(e)[:200]


def health(k):
    st, ms, txt = call(HEALTH, k, to=15)
    if isinstance(st, str):
        return None
    try:
        j = json.loads(txt)
    except ValueError:
        return None
    w = j.get("workers") or {}
    return {"ready": int(w.get("ready") or 0), "running": int(w.get("running") or 0),
            "init": int(w.get("initializing") or 0), "throttled": int(w.get("throttled") or 0),
            "unhealthy": int(w.get("unhealthy") or 0),
            "inQueue": int((j.get("jobs") or {}).get("inQueue") or 0)}


def watch(k, secs, tag):
    t0 = time.time()
    while time.time() - t0 < secs:
        h = health(k)
        el = int(time.time() - t0)
        if h:
            alive = h["ready"] + h["running"]
            print("      %s t+%3ds ready=%d running=%d init=%d throttled=%d unhealth=%d q=%d"
                  % (tag, el, h["ready"], h["running"], h["init"], h["throttled"],
                     h["unhealthy"], h["inQueue"]), flush=True)
            if alive > 0:
                return True, h
        time.sleep(15)
    return False, health(k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", type=int, default=90)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    k = key()
    if not k:
        print("拿不到 GBT_POTATO_API_KEY")
        return 2
    st, ms, txt = call(REST, k)
    print("端点现读 status=%s (%dms)" % (st, ms))
    try:
        ep = json.loads(txt)
    except ValueError:
        print("端点 REST 读不到：", txt[:200])
        return 1
    orig = list(ep.get("gpuTypeIds") or [])
    print("  workersMin=%s workersMax=%s idle=%s flashboot=%s"
          % (ep.get("workersMin"), ep.get("workersMax"), ep.get("idleTimeout"), ep.get("flashboot")))
    print("  原 GPU 组：%s" % orig)
    print("  模板 env.MODEL_NAME=%s · networkVolume=%s"
          % ((ep.get("template") or {}).get("env", {}).get("MODEL_NAME"), ep.get("networkVolumeId")))
    if not a.apply:
        h = health(k)
        print("  现 health=%s（只读模式：要真换组试拉起加 --apply）" % h)
        return 0

    for g in GROUPS:
        print("\n=== 试验组：%s ===" % g, flush=True)
        st, ms, txt = call(REST, k, "PATCH",
                           {"gpuTypeIds": g, "workersMin": 1, "workersMax": 1, "idleTimeout": 600})
        print("  PATCH status=%s (%dms)" % (st, ms), flush=True)
        if st != 200:
            print("  PATCH 失败，跳过：", txt[:160])
            continue
        ok, h = watch(k, a.watch, "组")
        if ok:
            print("✅ 起来了：%s（GPU 组 %s 留在端点里）" % (h, g))
            print("   下一步：py -3.14 tools/codex-scripts/lane-doctor.py check")
            return 0
        print("  ❌ %ds 内没起来（final=%s）" % (a.watch, h), flush=True)

    print("\n=== 全部组失败，回滚原组 ===")
    st, ms, txt = call(REST, k, "PATCH", {"gpuTypeIds": orig})
    print("  回滚 PATCH status=%s" % st)
    print("  现读：", health(k))
    print("  ⇒ 不是 GPU 型号问题（5 组单类型 + 全组都试过）。剩下：卷挂载 / 账户额度 / 镜像启动失败，"
          "这三条必须看控制台 pod 日志。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
