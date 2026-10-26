#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_ask —— 在本对话框里直接调 A19 的原生权重（绕过 Minis 的模型注入）。

为什么要绕：本框的系统注入已上万 token，而 A19 那份权重只有 4096 窗。
把注入塞进去必然爆窗；只送问题本身，4096 绰绰有余。

用法：
    python3 a19_ask.py "你是谁？"
    python3 a19_ask.py --raw "..."        # 只要正文，不要任何提示行
    python3 a19_ask.py --probe            # 只探活（<1 秒）

退出码：0 成功 · 2 A19 未开（App 在前台点 Load & Start Server）· 3 请求失败
"""
import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:1234/v1"
KEY = "gbt"                 # LM Pocket 里显式设的已知钥（小写；大写 401）
HOST, PORT = "127.0.0.1", 1234


def port_up(timeout=0.8):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((HOST, PORT))
        return True
    except Exception:                                             # noqa: BLE001
        return False
    finally:
        s.close()


def post(path, payload, timeout):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + KEY,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def models(timeout=10):
    req = urllib.request.Request(BASE + "/models",
                                 headers={"Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="*")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--tokens", type=int, default=512)
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--system", default="")
    ap.add_argument("--timeout", type=float, default=120)
    a = ap.parse_args()

    if not port_up():
        print("A19_OFF  :1234 没开 —— LM Pocket 要在前台点 Load & Start Server", flush=True)
        return 2

    t0 = time.time()
    try:
        m = models(10)
    except Exception as exc:                                      # noqa: BLE001
        print("A19_ERR /v1/models %s: %s" % (type(exc).__name__, exc), flush=True)
        return 3

    ids = [x.get("id") for x in m.get("data", [])]
    model = ids[0] if ids else ""

    if a.probe:
        print("A19_OK  model=%s  probe=%.2fs" % (model, time.time() - t0), flush=True)
        return 0

    prompt = " ".join(a.prompt).strip()
    if not prompt:
        print("用法: a19_ask.py \"问题\"", flush=True)
        return 1

    msgs = []
    if a.system:
        msgs.append({"role": "system", "content": a.system})
    msgs.append({"role": "user", "content": prompt})

    t1 = time.time()
    try:
        d = post("/chat/completions",
                 {"model": model, "messages": msgs, "max_tokens": a.tokens,
                  "temperature": a.temp, "stream": False}, a.timeout)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:300]
        except Exception:                                         # noqa: BLE001
            pass
        print("A19_HTTP %s %s" % (exc.code, body), flush=True)
        return 3
    except Exception as exc:                                      # noqa: BLE001
        print("A19_ERR %s: %s" % (type(exc).__name__, exc), flush=True)
        return 3

    dt = time.time() - t1
    u = d.get("usage") or {}
    ct = u.get("completion_tokens") or 0
    txt = (d["choices"][0]["message"].get("content") or "").strip()

    if a.raw:
        print(txt)
        return 0

    print("[A19] model=%s  %.2fs  %s tok  %s tok/s" % (
        d.get("model") or model, dt, ct, ("%.1f" % (ct / dt)) if dt else "?"))
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
