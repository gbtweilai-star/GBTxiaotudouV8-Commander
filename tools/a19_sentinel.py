#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A19 哨兵：等 LM Pocket 的 :1234 起来，一起来就把整条链跑通并落读数。

用法：
    python3 a19_sentinel.py --wait 600            # 最多等 600 秒
    python3 a19_sentinel.py --wait 0              # 起来了就直接测，不等

落点 /tmp/a19_ready.json：
    {"at":..., "up":true, "models":[...], "load_s":..., "first_token_s":...,
     "gen_tok_s":..., "identity":"...", "ok":true}
"""
import argparse
import json
import socket
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:1234/v1"
KEY = "gbt"           # LM Pocket 里显式设的那个已知钥（小写，大写会 401）
OUT = "/tmp/a19_ready.json"


def port_up(host="127.0.0.1", port=1234, timeout=1.0):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def call(path, payload=None, timeout=180):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Authorization": "Bearer " + KEY,
                                          "Content-Type": "application/json"})
    t = time.time()
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    return json.loads(raw), time.time() - t


def write(obj):
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=600)
    ap.add_argument("--prompt", default="用一句话说清你是谁，谁开发的，谁守护的。")
    args = ap.parse_args()

    write({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "up": False, "ok": False,
           "phase": "waiting"})
    deadline = time.time() + max(0, args.wait)
    while not port_up():
        if time.time() > deadline:
            write({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "up": False,
                   "ok": False, "phase": "timeout",
                   "note": "LM Pocket 的 :1234 始终没开（App 要在前台点 Load & Start Server）"})
            print("TIMEOUT")
            return 1
        time.sleep(1)

    t_up = time.time()
    write({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "up": True, "ok": False,
           "phase": "port open", "waited_s": round(t_up, 1)})

    # 1) 端口通了不代表服务器就绪 —— 反复问 /models 直到 200
    models, load_s, last_err = [], None, None
    for _ in range(120):
        try:
            d, dt = call("/models", timeout=10)
            models = [m.get("id") for m in d.get("data", [])]
            load_s = round(dt, 2)
            break
        except Exception as exc:                                  # noqa: BLE001
            last_err = "%s: %s" % (type(exc).__name__, exc)
            time.sleep(1)

    if load_s is None:
        write({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "up": True, "ok": False,
               "phase": "models failed", "error": last_err})
        print("MODELS FAILED", last_err)
        return 1

    res = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "up": True, "phase": "models ok",
           "models": models, "models_latency_s": load_s}

    # 2) 真跑一次：量首字延迟 + 生成速度 + 身份
    payload = {"model": models[0] if models else "",
               "messages": [{"role": "user", "content": args.prompt}],
               "max_tokens": 200, "temperature": 0.2, "stream": False}
    try:
        t0 = time.time()
        d, dt = call("/chat/completions", payload, timeout=300)
        txt = (d["choices"][0]["message"].get("content") or "")
        usage = d.get("usage") or {}
        ct = usage.get("completion_tokens") or 0
        res.update({"ok": True, "model_reported": d.get("model"),
                    "wall_s": round(dt, 2),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": ct,
                    "gen_tok_s": round(ct / dt, 2) if dt else None,
                    "identity": txt.strip()[:300]})
    except Exception as exc:                                      # noqa: BLE001
        res.update({"ok": False, "phase": "chat failed",
                    "error": "%s: %s" % (type(exc).__name__, exc)})
    write(res)

    # 3) 顺带把「能吃多大的 prompt」也量了 —— 这是能否整框切 A19 的唯一硬依据。
    try:
        import subprocess as _sp
        here = os.path.dirname(os.path.abspath(__file__))
        _sp.run([sys.executable, os.path.join(here, "a19_prefill.py"), "--window", "45"],
                capture_output=True, text=True, timeout=1800)
        if os.path.exists("/tmp/a19_prefill.json"):
            res["prefill"] = json.load(open("/tmp/a19_prefill.json", encoding="utf-8"))
            write(res)
    except Exception as exc:                                      # noqa: BLE001
        res["prefill_error"] = "%s: %s" % (type(exc).__name__, exc)
        write(res)

    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
