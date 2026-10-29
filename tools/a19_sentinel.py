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

def _lan_ip() -> str:
    """取本机网卡地址。App Store 描述原文「Expose … on your local network」——
    服务可能只绑网卡、不绑回环，所以探测必须覆盖它。"""
    try:
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.settimeout(1)
        _s.connect(("8.8.8.8", 53))
        _ip = _s.getsockname()[0]
        _s.close()
        return _ip
    except Exception:                                             # noqa: BLE001
        return ""


LAN = _lan_ip()
HOSTS = [h for h in ("127.0.0.1", LAN, "::1") if h]
BASE = "http://127.0.0.1:1234/v1"
KEY = "gbt"           # LM Pocket 里显式设的那个已知钥（小写，大写会 401）
OUT = "/tmp/a19_ready.json"          # 旧路径：a19_switch 读它拿 prefill 预算，保留
# 🔴 2026-10-29 修：docs/17 与 docs/36 都承诺「验收凭据 = state/a19_ready.json」，
#   但本器只写 /tmp ⇒ 容器真起来那一刻，文档里那份凭据不会更新（会一直是旧的 DOWN）。
#   两份都写：/tmp 给 a19_switch 读，state 给人和文档看。
STATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "state", "a19_ready.json")


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
    for p in (OUT, STATE):
        try:
            d = os.path.dirname(p)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, ensure_ascii=False, indent=1)
        except Exception:                                         # noqa: BLE001
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=600)
    ap.add_argument("--prompt", default="用一句话说清你是谁，谁开发的，谁守护的。")
    args = ap.parse_args()

    write({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "up": False, "ok": False,
           "phase": "waiting"})
    # 🔴 2026-10-29：装心跳。没有心跳就无法证明「Minis 进后台时 iSH 还在跑」——
    #   docs/22 说后台进程还活着，但那是别人的实测，不是这一刻的。每探一次落一个时间戳，
    #   事后看时间戳有没有断档，就知道窗口到底能不能被抓到。
    HB = "/tmp/a19_hb.json"
    def hb(state: str) -> None:
        try:
            with open(HB, "w", encoding="utf-8") as fh:
                json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "ts": time.time(), "state": state, "pid": os.getpid()}, fh)
        except Exception:                                         # noqa: BLE001
            pass

    deadline = time.time() + max(0, args.wait)
    hit_host = None
    while True:
        # 三地址逐个探（回环 / 网卡 / IPv6）—— 服务可能只绑网卡
        for _h in HOSTS:
            if port_up(_h):
                hit_host = _h
                break
        if hit_host:
            break
        hb("probing:" + ",".join(HOSTS))
        if time.time() > deadline:
            write({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "up": False,
                   "ok": False, "phase": "timeout",
                   "note": "LM Pocket 的 :1234 始终没开（App 要在前台点 Load & Start Server）"})
            print("TIMEOUT")
            return 1
        time.sleep(1)

    t_up = time.time()
    # 命中地址如果不是回环，后续所有请求都要打那个地址（App 可能只绑网卡）
    global BASE
    if hit_host and hit_host not in ("127.0.0.1",):
        BASE = "http://%s:1234/v1" % ("[%s]" % hit_host if ":" in hit_host else hit_host)
    write({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "up": True, "ok": False,
           "phase": "port open", "host": hit_host, "waited_s": round(t_up, 1)})

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

    # 2.5) 立刻把离线队列跑完（2026-10-29 收编）
    #  为什么在这里做：`a19_ctl.py queue drain` 早就是队列的**唯一实现**
    #  （同 QUEUE/DONE 口径、容器不在原样保留）。docs/17 与 body.py 里提到的
    #  `weights/a19_worker.py` 在仓库里从来不存在 —— 是幽灵引用。
    #  与其再写一套常驻 worker（重复实现，第二份迟早跟第一份走偏），
    #  不如让哨兵在「抓到的那一秒」直接调那个唯一实现。
    #  iOS 只给约 50 秒窗口，所以必须紧跟验收、不能等下一轮。
    try:
        import subprocess as _sp2
        here2 = os.path.dirname(os.path.abspath(__file__))
        r2 = _sp2.run([sys.executable, os.path.join(here2, "a19_ctl.py"),
                       "queue", "drain"],
                      capture_output=True, text=True, timeout=900)
        res["queue_drain"] = {"rc": r2.returncode,
                              "tail": ((r2.stdout or "") + (r2.stderr or ""))[-300:]}
        write(res)
    except Exception as exc:                                      # noqa: BLE001
        res["queue_drain_error"] = "%s: %s" % (type(exc).__name__, exc)
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
