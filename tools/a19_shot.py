#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_shot —— 20 秒内打完的最小子弹。

为什么这么小：LM Pocket 切到后台后只有约 50 秒宽限，
而它 10 tok/s，多打几发就超时。所以只留**三发必要的**：
  ① /v1/models（真机加载的模型名）
  ② 一句身份自述（量真 tok/s、真回答）
  ③ 桥一发（验 lane=selfhost · weights_ours=true）
每条独立超时，谁挂都不拖死后面的。
"""
import json
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "a19_shot.json"


def call(url, payload, timeout):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer gbt"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        hd = dict(r.headers)
    return round(time.perf_counter() - t0, 2), raw, hd


def payload(text, mt):
    return {"model": "gbt-v8-v82-q5_0", "max_tokens": mt, "temperature": 0,
            "messages": [{"role": "system", "content":
                          "你是 GBT小土豆V8，开发者：自由的风，守护者：公主土豆。"},
                         {"role": "user", "content": text}]}


def main() -> int:
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    t_all = time.perf_counter()

    # ① models
    try:
        with urllib.request.urlopen(urllib.request.Request(
                "http://127.0.0.1:1234/v1/models",
                headers={"Authorization": "Bearer gbt"}), timeout=8) as r:
            rec["models"] = [x.get("id") for x in (json.loads(r.read()).get("data") or [])]
        print("  ① models:", rec["models"], flush=True)
    except Exception as exc:                                  # noqa: BLE001
        rec["models_err"] = "%s" % type(exc).__name__
        print("  ① models 🔴", type(exc).__name__, flush=True)

    # ② 身份自述（真 tok/s）
    try:
        el, raw, _ = call("http://127.0.0.1:1234/v1/chat/completions",
                          payload("用一句话说你是谁", 48), 14)
        d = json.loads(raw)
        txt = (((d.get("choices") or [{}])[0] or {}).get("message") or {}).get("content", "")
        n = (d.get("usage") or {}).get("completion_tokens") or 0
        rec["direct"] = {"elapsed_s": el, "model": d.get("model"), "tokens": n,
                         "tok_per_s": round(n / el, 2) if el and n else None,
                         "answer": txt.strip()[:240]}
        print("  ② 真机 %.1fs · %s tok · %.1f tok/s" % (el, n, n / el if el and n else 0), flush=True)
        print("     答:", txt.strip()[:110], flush=True)
    except Exception as exc:                                  # noqa: BLE001
        rec["direct_err"] = "%s" % type(exc).__name__
        print("  ② 真机 🔴", type(exc).__name__, flush=True)

    # ③ 桥（验 lane）
    try:
        el, raw, hd = call("http://127.0.0.1:8791/v1/chat/completions",
                           {"messages": [{"role": "user", "content": "用一句话说你是谁"}],
                            "max_tokens": 48}, 16)
        d = json.loads(raw)
        txt = (((d.get("choices") or [{}])[0] or {}).get("message") or {}).get("content", "")
        rec["bridge"] = {"elapsed_s": el, "lane": hd.get("X-GBT-Lane"),
                         "weights_ours": hd.get("X-GBT-Weights-Ours"),
                         "answer": txt.strip()[:160]}
        print("  ③ 桥 lane=%s ours=%s · %.1fs" % (rec["bridge"]["lane"],
                                                  rec["bridge"]["weights_ours"], el), flush=True)
    except Exception as exc:                                  # noqa: BLE001
        rec["bridge_err"] = "%s" % type(exc).__name__
        print("  ③ 桥 🔴", type(exc).__name__, flush=True)

    rec["total_s"] = round(time.perf_counter() - t_all, 1)
    rec["ok"] = "direct" in rec or "bridge" in rec
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  合计 %.1fs · 落盘 %s" % (rec["total_s"], OUT), flush=True)
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
