#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RunPod endpoint 控制面读数 / 保温开关（走 rest.runpod.io v1，钥匙 rpa_*）。

用法：
  py -3.14 tools/model-bridge/runpod-epctl.py show
  py -3.14 tools/model-bridge/runpod-epctl.py warm 1     # workersMin=1 常驻（消灭冷启动）
  py -3.14 tools/model-bridge/runpod-epctl.py warm 0
  py -3.14 tools/model-bridge/runpod-epctl.py health
  py -3.14 tools/model-bridge/runpod-epctl.py chat "ping"

纪律：钥匙只从 HKCU\\Environment 读，永不打印；每次真跑都把上游原话带回来。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

EP = os.environ.get("GBT_POTATO_EP") or "qnnqf9w8xcefj8"
KEY = os.environ.get("GBT_POTATO_API_KEY") or os.environ.get("GBT_POTATO_LANE_KEY") or ""
BASE_REST = "https://rest.runpod.io/v1"
BASE_API = "https://api.runpod.ai/v2"


def _load_key():
    global KEY
    if KEY:
        return KEY
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        for name in ("GBT_POTATO_API_KEY", "GBT_POTATO_LANE_KEY"):
            try:
                KEY = winreg.QueryValueEx(k, name)[0]
                if KEY:
                    return KEY
            except OSError:
                pass
    return KEY


def req(url, method="GET", body=None, timeout=45, auth=True):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    r.add_header("User-Agent", "GBTxiaotudouV8-epctl/1.0")
    if auth:
        r.add_header("Authorization", "Bearer " + _load_key())
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return {"ok": True, "status": resp.status, "ms": int((time.time() - t0) * 1000), "body": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        return {"ok": False, "status": e.code, "ms": int((time.time() - t0) * 1000), "body": raw}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": 0, "ms": int((time.time() - t0) * 1000), "body": "%s: %s" % (type(e).__name__, e)}


def show():
    r = req("%s/endpoints/%s" % (BASE_REST, EP))
    out = {"rest_ms": r["ms"], "rest_status": r["status"]}
    if r["ok"]:
        try:
            j = json.loads(r["body"])
        except Exception:
            out["raw"] = r["body"][:800]
            j = {}
        keep = [
            "id", "name", "templateId", "gpuTypeIds", "gpuCount", "workersMin", "workersMax",
            "idleTimeout", "executionTimeoutMs", "scalerType", "scalerValue", "networkVolumeId",
            "allowedCudaVersions", "flashboot", "dataCenterIds", "computeType",
        ]
        out["endpoint"] = {k: j.get(k) for k in keep if k in j}
        out["keys"] = sorted(j.keys())
    else:
        out["error"] = r["body"][:500]
    h = req("%s/%s/health" % (BASE_API, EP), timeout=30)
    out["health_status"] = h["status"]
    out["health_ms"] = h["ms"]
    try:
        out["health"] = json.loads(h["body"])
    except Exception:
        out["health_raw"] = h["body"][:400]
    print(json.dumps(out, ensure_ascii=False, indent=2))


def ctl(kv):
    body = {}
    for pair in kv:
        k, _, v = pair.partition("=")
        try:
            body[k] = int(v)
        except ValueError:
            body[k] = v
    r = req("%s/endpoints/%s" % (BASE_REST, EP), method="PATCH", body=body)
    print(json.dumps({"patched": body, "status": r["status"], "ms": r["ms"], "body": r["body"][:400]}, ensure_ascii=False, indent=2))


def warm(n):
    body = {"workersMin": int(n)}
    r = req("%s/endpoints/%s" % (BASE_REST, EP), method="PATCH", body=body)
    print(json.dumps({"patch_status": r["status"], "ms": r["ms"], "body": r["body"][:900]}, ensure_ascii=False, indent=2))
    time.sleep(2)
    show()


def health():
    r = req("%s/%s/health" % (BASE_API, EP), timeout=30)
    print(json.dumps({"status": r["status"], "ms": r["ms"], "body": r["body"][:900]}, ensure_ascii=False, indent=2))


def chat(text, tools=False, max_tokens=64):
    model = os.environ.get("GBT_POTATO_EP_MODEL") or "/runpod-volume/gbt-v8-v83"
    body = {"model": model, "messages": [{"role": "user", "content": text}], "max_tokens": max_tokens, "stream": False}
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": "now", "description": "报当前时间",
                                                          "parameters": {"type": "object", "properties": {}}}}]
    r = req("%s/%s/openai/v1/chat/completions" % (BASE_API, EP), method="POST", body=body, timeout=300)
    out = {"status": r["status"], "ms": r["ms"]}
    try:
        j = json.loads(r["body"])
        ch = (j.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        out["finish"] = ch.get("finish_reason")
        out["content"] = msg.get("content")
        out["tool_calls"] = msg.get("tool_calls")
        out["usage"] = j.get("usage")
        out["model"] = j.get("model")
    except Exception:
        out["raw"] = r["body"][:600]
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "show").lower()
    if cmd == "show":
        show()
    elif cmd == "warm":
        warm(sys.argv[2] if len(sys.argv) > 2 else "1")
    elif cmd == "ctl":
        ctl(sys.argv[2:])
    elif cmd == "health":
        health()
    elif cmd == "chat":
        chat(sys.argv[2] if len(sys.argv) > 2 else "ping", tools=("--tools" in sys.argv))
    else:
        print("usage: show|warm <n>|health|chat <text> [--tools]")
