#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_wait —— 只认"真能应答"的 A19 抓取器（后台常驻，等你在 LM Pocket 里点那一下）。

## 为什么必须在后台跑
iOS 只允许一个 App 前台。实践上：
  · 你在 Minis 里 ⇒ LM Pocket 被挂起，:1234 起不来；
  · 你在 LM Pocket 里 ⇒ Minis 挂起，但 **iSH 的后台进程还在跑**
    （实测 duty_patrol / svc_guard watch 都能在后台活着）。
所以把探测器放后台 ⇒ 你一点「Load & Start Server」，它当场就能抓到，
不用你切回来再喊我。

## 只认"真能应答"
TCP 握手能成但进程被冻住时，请求会超时 ⇒ 那不是活。
先发一个 4 秒的 /v1/models 探活，通了才算，然后打一套：models / 真机一发 / 桥一发。
"""
import json
import pathlib
import socket
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "a19_caught.json"
STOP = ("<|im_end|>", "<|endoftext|>", "<|im_start|>")


def cut(t: str) -> str:
    t = str(t or "")
    i = min([t.find(m) for m in STOP if t.find(m) != -1] or [len(t)])
    return t[:i].strip()


def tcp() -> bool:
    s = socket.socket(); s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", 1234)); return True
    except OSError:
        return False
    finally:
        s.close()


def alive() -> bool:
    try:
        urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:1234/v1/models",
            headers={"Authorization": "Bearer gbt"}), timeout=4).read()
        return True
    except Exception:                                         # noqa: BLE001
        return False


def post(url, payload, timeout=40, extra=None):
    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json", "Authorization": "Bearer gbt"}
    h.update(extra or {})
    t0 = time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h),
                                timeout=timeout) as r:
        return round(time.perf_counter() - t0, 2), r.read(), dict(r.headers)


def battery() -> dict:
    rec = {"caught_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True}
    try:
        m = urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:1234/v1/models",
            headers={"Authorization": "Bearer gbt"}), timeout=8).read()
        rec["models"] = [x.get("id") for x in (json.loads(m).get("data") or [])]
    except Exception as e:                                    # noqa: BLE001
        rec["models_err"] = type(e).__name__
    try:
        el, raw, _ = post("http://127.0.0.1:1234/v1/chat/completions",
                          {"model": "gbt-v8-v82-q5_0", "max_tokens": 48, "temperature": 0,
                           "messages": [{"role": "system", "content":
                                         "你是 GBT小土豆V8，开发者：自由的风，守护者：公主土豆。"},
                                        {"role": "user", "content": "用一句话说你是谁"}]})
        d = json.loads(raw)
        txt = cut((((d.get("choices") or [{}])[0] or {}).get("message") or {}).get("content", ""))
        n = (d.get("usage") or {}).get("completion_tokens") or 0
        rec["direct"] = {"elapsed_s": el, "model": d.get("model"), "tokens": n,
                         "tok_per_s": round(n / el, 2) if el and n else None,
                         "answer": txt[:240]}
    except Exception as e:                                    # noqa: BLE001
        rec["direct_err"] = type(e).__name__
    try:
        el, raw, hd = post("http://127.0.0.1:8791/v1/chat/completions",
                           {"messages": [{"role": "user", "content": "用一句话说你是谁"}],
                            "max_tokens": 48}, timeout=40)
        d = json.loads(raw)
        txt = cut((((d.get("choices") or [{}])[0] or {}).get("message") or {}).get("content", ""))
        rec["bridge"] = {"elapsed_s": el, "lane": hd.get("X-GBT-Lane"),
                         "weights_ours": hd.get("X-GBT-Weights-Ours"), "answer": txt[:160]}
    except Exception as e:                                    # noqa: BLE001
        rec["bridge_err"] = type(e).__name__
    return rec


def main() -> int:
    print("  🎯 A19 等待器 · 只认真能应答 · 每 3s", flush=True)
    n = 0
    while True:
        n += 1
        if tcp() and alive():
            print("  ✅ :1234 真活 —— 开火", flush=True)
            rec = battery()
            # 🔴 2026-10-29：接上框架自己的队列通道（a19_ctl queue）。
            #   它的设计就是「容器不在就先存着，一开就跑」——这是容器不常驻下的正解，
            #   比我手搓重试专业得多（a19_ctl 是原生的手，我只是调用它）。
            try:
                import subprocess as _sp
                _q = _sp.run([sys.executable, str(ROOT / "tools" / "a19_ctl.py"),
                              "queue", "drain"], capture_output=True, text=True,
                             timeout=180, cwd=str(ROOT))
                rec["queue_drain"] = {"rc": _q.returncode,
                                      "tail": (_q.stdout or "").strip().splitlines()[-3:]}
            except Exception as exc:                          # noqa: BLE001
                rec["queue_drain"] = {"err": type(exc).__name__}
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            print("  📝 %s" % OUT, flush=True)
            print("     models=%s direct=%s bridge_lane=%s"
                  % (rec.get("models"), (rec.get("direct") or {}).get("tok_per_s"),
                     (rec.get("bridge") or {}).get("lane")), flush=True)
            return 0
        if n % 20 == 0:
            print("    …%ds（TCP=%s）" % (n * 3, "通" if tcp() else "断"), flush=True)
        time.sleep(3)


if __name__ == "__main__":
    raise SystemExit(main())
