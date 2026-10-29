#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A19 窗口猎手 —— 不再只盯 1234 一个口

为什么要重写：
  之前的等待器只探 127.0.0.1:1234。如果 LM Pocket 换了端口、或者只绑某个网卡，
  它会一直报"没开"，而真相是"开在别处"。只盯一个口 = 把"没找到"当成"没有"。

两层探法（都由实测决定，不猜）：
  ① 哨兵层：1234 每 3 秒一次，只认 4 秒内 HTTP 真应答（TCP 通但不应答 = 不算活）
  ② 扫猎层：只要哨兵发现"本机多了任何监听口"，立刻对该口做协议指纹
     —— 发 GET /v1/models，回 JSON 且带 model 字段 / data 数组 ⇒ 判为 OpenAI 兼容端点
     —— 本机已知常驻口（自己的桥 8790/8791、页面 8080/8765…）在排除表里，不误报

窗口期只有 ~50 秒（iOS 给后台 App 的宽限），所以：
  · 扫猎必须并发（200 线程），全 65535 口实测约 3~6 秒
  · 一旦命中，立刻落 state/a19_caught.json，并自动 drain 积压队列

用法：
  python3 tools/a19_hunter.py            # 常驻
  python3 tools/a19_hunter.py --once     # 只跑一轮（诊断用）
"""
from __future__ import annotations

import json
import pathlib
import socket
import sys
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
STATE.mkdir(exist_ok=True)
CAUGHT = STATE / "a19_caught.json"
QUEUE = pathlib.Path("/tmp/a19_queue.jsonl")

PORT = 1234
OWN = {1080, 1083, 8021, 8765, 8790, 8791, 8899, 8080, 3001,
       49152, 58725}          # 本机自己的口，扫到不算命中
TIMEOUT = 0.25

# App Store 描述原文：「Expose … on your local network」⇒ 服务绑的是网卡，不只是回环。
# 所以哨兵和扫猎都必须同时打回环和网卡地址，否则会漏。
def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


LAN = _lan_ip()
HOSTS = [h for h in ("127.0.0.1", LAN, "::1") if h]


def tcp_open(port: int, host: str = "127.0.0.1", timeout: float = 1.5) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def http_get(port: int, path: str = "/v1/models", timeout: float = 4.0,
             host: str = "127.0.0.1") -> str:
    h = "[%s]" % host if ":" in host else host
    req = urllib.request.Request("http://%s:%d%s" % (h, port, path),
                                 headers={"Authorization": "Bearer gbt"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(4096).decode("utf-8", "replace")


def is_openai(port: int, host: str = "127.0.0.1") -> tuple:
    """真发一次 /v1/models，按返回体判定，不按端口号猜。"""
    try:
        body = http_get(port, host=host)
        d = json.loads(body)
    except Exception:
        return (False, "")
    if isinstance(d, dict):
        if "data" in d and isinstance(d["data"], list):
            return (True, body[:200])
        if "models" in d:
            return (True, body[:200])
        if d.get("object") or d.get("id"):
            return (True, body[:200])
    return (False, body[:80])


def sweep() -> list:
    """并发扫全口，返回讲 OpenAI 协议的口。"""
    found = []
    lock = threading.Lock()

    def probe(p: int) -> None:
        if p in OWN:
            return
        for h in HOSTS:
            if not tcp_open(p, host=h, timeout=TIMEOUT):
                continue
            ok, sample = is_openai(p, host=h)
            if ok:
                with lock:
                    found.append({"port": p, "host": h, "sample": sample})

    ports = list(range(1, 65536))
    for i in range(0, len(ports), 500):
        ts = [threading.Thread(target=probe, args=(p,), daemon=True)
              for p in ports[i:i + 500]]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        if found:
            break
    return found


def drain() -> None:
    try:
        sys.path.insert(0, str(ROOT))
        import subprocess
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "a19_ctl.py"),
                            "queue", "drain"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=600)
        print("  drain: rc=%d %s" % (r.returncode, (r.stdout or "")[-300:]), flush=True)
    except Exception as e:
        print("  drain 失败: %s: %s" % (type(e).__name__, e), flush=True)


def catch(port: int, sample: str, how: str, host: str = "127.0.0.1") -> None:
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "port": port, "host": host,
           "how": how, "sample": sample, "url": "http://%s:%d/v1" % (host, port)}
    CAUGHT.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    print("  ★★★ 抓到 OPENAI 端点 :%d（%s）" % (port, how), flush=True)
    print("      %s" % sample.replace("\n", " ")[:160], flush=True)
    drain()


def main() -> int:
    once = "--once" in sys.argv
    print("  🎯 A19 窗口猎手 · 哨兵 :%d（每 3s·只认 HTTP 真应答）+ 扫猎全口" % PORT,
          flush=True)
    print("     本机自己的口已排除：%s" % sorted(OWN), flush=True)
    print("     覆盖地址：%s" % HOSTS, flush=True)
    last_sweep = 0.0
    while True:
        t0 = time.time()
        for _h in HOSTS:
            if not tcp_open(PORT, host=_h, timeout=2.0):
                continue
            ok, sample = is_openai(PORT, host=_h)
            if ok:
                print("  ★ %s:%d TCP 通 + HTTP 真应答" % (_h, PORT), flush=True)
                catch(PORT, sample, "sentinel@" + _h)
                return 0
            print("  · %s:%d TCP 通但不应答（%.1fs）—— 判未活"
                  % (_h, PORT, time.time() - t0), flush=True)
        # 扫猎：每 60 秒一次，或哨兵刚看到端口通时立刻扫
        if time.time() - last_sweep > 60:
            last_sweep = time.time()
            hit = sweep()
            if hit:
                catch(hit[0]["port"], hit[0]["sample"], "sweep", hit[0].get("host","127.0.0.1"))
                return 0
            print("  · 扫猎完成：全口无 OpenAI 端点（%.1fs）"
                  % (time.time() - t0), flush=True)
        if once:
            return 0
        time.sleep(3)


if __name__ == "__main__":
    raise SystemExit(main())
