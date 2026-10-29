#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_ctl —— 把 LM Pocket 当容器来管（不是当"另一个 App"来求）。

容器画像（实测口径，全部可在 status 里核对）
    image      gbt-v8-v82-q5_0.gguf  5.24 GB
    runtime     LM Pocket（Metal 后端 · 全本地 · 不碰云）
    port        127.0.0.1:1234   OpenAI 兼容
    auth        Bearer gbt（小写；大写 401）
    ctx         4096（容器内设定，不是我们决定的）
    宿主限制    iOS 前台互斥 ⇒ 容器不常驻；后台约 50s 宽限

子命令
    status            容器状态 + 规格 + 当前装载的模型（<1s，永不卡）
    up   [--wait N]   唤起容器（lmpocket://），并等 :1234 就绪
    ask  "问题"       往容器里送一个问题，取原话
    ps                容器内模型清单（/v1/models 原文）
    bench             规格实测：首字延迟 / 生成 tok/s / 身份自述
    queue add "问题"  入队（容器不在时先存着）
    queue drain       容器在时把队列一次跑完

纪律：容器不在就如实说"容器不在"，1 秒内返回，绝不干等、绝不拿云端顶替。
"""
import argparse
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

# 🔴 端点可覆盖：默认本机 LM Pocket；设 GBT_A19_BASE 就能指向**我们自己的 vLLM**
#    （RunPod 上的 gbt-v8-v83）。这样"她的嘴"不绑死在手机上，也不改一行调用代码。
BASE = os.environ.get("GBT_A19_BASE") or "http://127.0.0.1:1234/v1"
KEY = os.environ.get("GBT_A19_KEY") or "gbt"
_u = BASE.split("//")[-1].split("/")[0]
HOST = _u.split(":")[0]
PORT = int(_u.split(":")[1]) if ":" in _u else (443 if BASE.startswith("https") else 80)
QUEUE = "/tmp/a19_queue.jsonl"
DONE = "/tmp/a19_done.jsonl"

IMAGE = "gbt-v8-v82-q5_0.gguf"
IMAGE_BYTES = 5242880000          # 实测 5.24 GB


def up_port(timeout=0.8):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((HOST, PORT))
        return True
    except Exception:                                             # noqa: BLE001
        return False
    finally:
        s.close()


def http(path, payload=None, timeout=120):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Authorization": "Bearer " + KEY,
                                          "Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()), time.time() - t


def model_ids(timeout=8):
    d, dt = http("/models", None, timeout)
    return [m.get("id") for m in d.get("data", [])], dt


def chat_dict(messages, tokens=512, temp=0.7):
    """多轮版提问：直接给 messages（含 system），容器不在 ⇒ 同样如实 offline。"""
    if not up_port():
        return {"ok": False, "status": "offline", "impl": "@app",
                "why": ":1234 无监听 —— 容器不在"}
    try:
        ids, _ = model_ids()
        model = ids[0] if ids else ""
        d, dt = http("/chat/completions",
                     {"model": model, "messages": messages, "max_tokens": tokens,
                      "temperature": temp, "stream": False}, 300)
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "status": "error",
                "why": "%s: %s" % (type(exc).__name__, exc)}
    u = d.get("usage") or {}
    ct = u.get("completion_tokens") or 0
    return {"ok": True, "status": "answered", "model": d.get("model") or model,
            "answer": (d["choices"][0]["message"].get("content") or "").strip(),
            "elapsed_s": round(dt, 2), "completion_tokens": ct,
            "prompt_tokens": u.get("prompt_tokens"),
            "tok_s": round(ct / dt, 2) if dt else None}


def queue_add(prompt, tokens=512):
    """入队，返回值版。容器不在时先把问题存着。"""
    with open(QUEUE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                             "prompt": prompt, "max_tokens": tokens},
                            ensure_ascii=False) + "\n")
    n = sum(1 for _ in open(QUEUE, encoding="utf-8"))
    return {"ok": True, "status": "queued", "queued": n, "queue": QUEUE}


def status_dict():
    """给上层（omni_plug / run_task）用的返回值版 status —— 不打印，只给字典。"""
    base = {"port": PORT, "image": IMAGE, "ctx": 4096, "auth": "Bearer " + KEY,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not up_port():
        return dict(base, ok=False, container="DOWN",
                    why=":1234 无监听（iOS 已挂起容器）")
    try:
        ids, dt = model_ids()
    except Exception as exc:                                      # noqa: BLE001
        return dict(base, ok=False, container="PORT-OPEN",
                    why="%s: %s" % (type(exc).__name__, exc))
    return dict(base, ok=True, container="UP", models=ids,
                models_latency_s=round(dt, 2))


def ask_dict(prompt, tokens=512, temp=0.7, system=""):
    """返回值版提问。容器不在 ⇒ ok:false / status:offline（不顶替、不编造）。"""
    if not up_port():
        return {"ok": False, "status": "offline", "organ": "推理", "impl": "@app",
                "why": ":1234 无监听 —— 容器不在"}
    try:
        ids, _ = model_ids()
        model = ids[0] if ids else ""
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        d, dt = http("/chat/completions",
                     {"model": model, "messages": msgs, "max_tokens": tokens,
                      "temperature": temp, "stream": False}, 300)
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "status": "error",
                "why": "%s: %s" % (type(exc).__name__, exc)}
    u = d.get("usage") or {}
    ct = u.get("completion_tokens") or 0
    return {"ok": True, "status": "answered", "model": d.get("model") or model,
            "answer": (d["choices"][0]["message"].get("content") or "").strip(),
            "elapsed_s": round(dt, 2), "completion_tokens": ct,
            "tok_s": round(ct / dt, 2) if dt else None}


def cmd_status():
    if not up_port():
        print("容器  DOWN   :1234 无监听（iOS 已挂起容器）")
        print("规格  image=%s  port=127.0.0.1:%d  ctx=4096  auth=Bearer %s" % (IMAGE, PORT, KEY))
        print("操作  唤起容器: a19_ctl up --wait 60   （需在 LM Pocket 点一次 Load & Start Server）")
        return 2
    try:
        ids, dt = model_ids()
    except Exception as exc:                                      # noqa: BLE001
        print("容器  PORT-OPEN 但 /v1/models 失败: %s: %s" % (type(exc).__name__, exc))
        return 3
    print("容器  UP     :1234  /v1/models %.2fs" % dt)
    print("规格  image=%s  port=127.0.0.1:%d  ctx=4096  auth=Bearer %s" % (IMAGE, PORT, KEY))
    print("载入  models=%s" % (ids or "[]"))
    return 0


def cmd_up(wait):
    print("唤起容器 lmpocket:// …", flush=True)
    try:
        out = subprocess.run(["apple-open", "lmpocket://"], capture_output=True,
                             text=True, timeout=20).stdout
        if '"opened" : true' in out or '"opened": true' in out:
            print("已送达   App 已切到前台（现在需要在里面点 Load & Start Server）", flush=True)
        else:
            print("唤起回执: %s" % out.strip()[:160], flush=True)
    except Exception as exc:                                      # noqa: BLE001
        print("唤起失败 %s: %s" % (type(exc).__name__, exc), flush=True)

    deadline = time.time() + max(0, wait)
    t0 = time.time()
    while time.time() < deadline:
        if up_port():
            try:
                ids, dt = model_ids()
            except Exception:                                     # noqa: BLE001
                ids, dt = [], None
            print("容器  UP    等了 %.0fs · /v1/models %s · models=%s"
                  % (time.time() - t0, ("%.2fs" % dt) if dt else "err", ids or "[]"))
            return 0
        time.sleep(1)
    print("容器  仍 DOWN（等了 %ds）—— Load & Start Server 还没点，或模型还在装载" % wait)
    return 2


def cmd_ps():
    if not up_port():
        print("容器  DOWN")
        return 2
    d, dt = http("/models", None, 10)
    print(json.dumps(d, ensure_ascii=False, indent=1)[:1500])
    return 0


def cmd_ask(prompt, tokens, temp, system, raw):
    if not up_port():
        print("A19_OFF  容器不在（:1234 无监听）—— 不顶替、不编造", flush=True)
        return 2
    ids, _ = model_ids()
    model = ids[0] if ids else ""
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    t = time.time()
    try:
        d, dt = http("/chat/completions",
                     {"model": model, "messages": msgs, "max_tokens": tokens,
                      "temperature": temp, "stream": False}, 300)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:300]
        except Exception:                                         # noqa: BLE001
            pass
        print("A19_HTTP %s %s" % (exc.code, body), flush=True)
        return 3
    u = d.get("usage") or {}
    ct = u.get("completion_tokens") or 0
    txt = (d["choices"][0]["message"].get("content") or "").strip()
    if raw:
        print(txt)
        return 0
    print("[A19] %s · %.2fs · %s tok · %s tok/s"
          % (d.get("model") or model, dt, ct, ("%.1f" % (ct / dt)) if dt else "?"))
    print(txt)
    return 0


def cmd_bench():
    if not up_port():
        print("A19_OFF  容器不在")
        return 2
    ids, mdt = model_ids()
    model = ids[0] if ids else ""
    print("容器  model=%s  /v1/models %.2fs" % (model, mdt))
    r = cmd_ask("用一句话说清你是谁、谁开发的、谁守护的。", 200, 0.2, "", False)
    return r


def cmd_queue(op, prompt, tokens):
    if op == "add":
        with open(QUEUE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "prompt": prompt, "max_tokens": tokens},
                                ensure_ascii=False) + "\n")
        n = sum(1 for _ in open(QUEUE, encoding="utf-8"))
        print("入队 ok · 队列 %d 条 · 容器一开就跑：a19_ctl queue drain" % n)
        return 0
    if op == "drain":
        if not up_port():
            print("A19_OFF  容器不在，队列原样保留")
            return 2
        if not os.path.exists(QUEUE):
            print("队列空")
            return 0
        items = [json.loads(l) for l in open(QUEUE, encoding="utf-8") if l.strip()]
        out = open(DONE, "a", encoding="utf-8")
        ok = 0
        for it in items:
            if not up_port():
                print("容器中途掉了，剩 %d 条留队" % (len(items) - ok))
                break
            ids, _ = model_ids()
            try:
                d, dt = http("/chat/completions",
                             {"model": ids[0] if ids else "",
                              "messages": [{"role": "user", "content": (it.get("q") or it.get("prompt") or "").strip()}],
                              "max_tokens": it.get("max_tokens", 512),
                              "temperature": 0.7, "stream": False}, 300)
                txt = (d["choices"][0]["message"].get("content") or "").strip()
                out.write(json.dumps({"id": it.get("id"), "q": (it.get("q") or it.get("prompt") or "").strip(), "prompt": (it.get("q") or it.get("prompt") or "").strip(), "answer": txt,
                                      "elapsed_s": round(dt, 2),
                                      "model": d.get("model")}, ensure_ascii=False) + "\n")
                out.flush()
                # 2026-10-30：答完就往镜像板落一条 result ——
                # 不然「她答了什么」只躺在 /tmp 的一个文件里，协作记录是断的。
                try:
                    import os as _o, sys as _s
                    _s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.dirname(
                        _o.path.abspath(__file__))), "tools"))
                    import mirror_board as _mb
                    _mb.post("result", "A19 答：%s" % (it.get("q") or it.get("prompt") or "")[:60],
                             refs=[txt[:200]], by="a19", space="her-inbox")
                except Exception as _e:                       # noqa: BLE001
                    import os as _o2
                    with open("/tmp/board_post_err.txt","a") as _f:
                        _f.write("%s: %s\n" % (type(_e).__name__, _e))
                ok += 1
                print("答完 %d/%d  %.2fs  %s" % (ok, len(items), dt, (it.get("q") or it.get("prompt") or "")[:30]))
            except Exception as exc:                              # noqa: BLE001
                print("失败: %s: %s" % (type(exc).__name__, exc))
                break
        out.close()
        if ok == len(items):
            os.remove(QUEUE)
        else:
            body = "\n".join(json.dumps(x, ensure_ascii=False) for x in items[ok:]) + "\n"
            open(QUEUE, "w", encoding="utf-8").write(body)
        print("结果 %s" % DONE)
        return 0
    print("queue add|drain")
    return 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    p = sub.add_parser("up")
    p.add_argument("--wait", type=int, default=60)
    sub.add_parser("ps")
    sub.add_parser("bench")
    p = sub.add_parser("ask")
    p.add_argument("prompt", nargs="+")
    p.add_argument("--tokens", type=int, default=512)
    p.add_argument("--temp", type=float, default=0.7)
    p.add_argument("--system", default="")
    p.add_argument("--raw", action="store_true")
    p = sub.add_parser("queue")
    p.add_argument("op", choices=["add", "drain"])
    p.add_argument("prompt", nargs="*")
    p.add_argument("--tokens", type=int, default=512)
    a = ap.parse_args()

    if a.cmd in (None, "status"):
        return cmd_status()
    if a.cmd == "up":
        return cmd_up(a.wait)
    if a.cmd == "ps":
        return cmd_ps()
    if a.cmd == "bench":
        return cmd_bench()
    if a.cmd == "ask":
        return cmd_ask(" ".join(a.prompt), a.tokens, a.temp, a.system, a.raw)
    if a.cmd == "queue":
        return cmd_queue(a.op, " ".join(a.prompt), a.tokens)
    return 1


if __name__ == "__main__":
    sys.exit(main())
