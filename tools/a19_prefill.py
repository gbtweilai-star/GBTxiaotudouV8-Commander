#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_prefill —— 把「A19 到底能吃多大 prompt、吃多快」量成硬数字。

为什么必须量：整框切 A19 的真正门槛不是 n_ctx 数字，而是 **prefill 时间**。
iOS 只给后台约 50 秒宽限，若 8000 token 的 prompt 要 prefill 200 秒，
那 n_ctx 设多大都没用 —— 窗口内根本跑不完。

用法：
    python3 a19_prefill.py                  # 阶梯跑 500/1000/2000/4000/8000 字
    python3 a19_prefill.py --chars 500,2000,8000 --window 45

输出每个阶梯的：prompt_tokens（服务端自报）/ elapsed / prefill tok/s，
并算出「45 秒窗口能吃多少 token」。落 /tmp/a19_prefill.json。
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:1234/v1"
KEY = "gbt"
OUT = "/tmp/a19_prefill.json"
FILLER = "她自己的权重跑在手机上，中文长文本用来压满上下文窗口。"


def http(path, payload=None, timeout=600):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Authorization": "Bearer " + KEY,
                                          "Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()), time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chars", default="500,1000,2000,4000,8000")
    ap.add_argument("--window", type=float, default=45.0,
                    help="iOS 后台宽限秒数（默认 45）")
    ap.add_argument("--max-tokens", type=int, default=8)
    a = ap.parse_args()

    try:
        d, _ = http("/models", None, 10)
        model = (d.get("data") or [{}])[0].get("id", "")
    except Exception as exc:                                      # noqa: BLE001
        print("A19_OFF /v1/models %s: %s" % (type(exc).__name__, exc))
        return 2
    print("容器 UP · model=%s" % model)

    rows, best = [], None
    for n in [int(x) for x in a.chars.split(",") if x.strip()]:
        body = (FILLER * (n // len(FILLER) + 1))[:n] + "\n\n只回两个字：收到"
        try:
            r, dt = http("/chat/completions",
                         {"model": model,
                          "messages": [{"role": "user", "content": body}],
                          "max_tokens": a.max_tokens, "temperature": 0,
                          "stream": False}, 600)
            u = r.get("usage") or {}
            pt = u.get("prompt_tokens") or 0
            ct = u.get("completion_tokens") or 0
            pre = dt - (ct / 8.0 if ct else 0)   # 粗扣生成时间（按 8 tok/s 估）
            row = {"chars": n, "prompt_tokens": pt, "elapsed_s": round(dt, 2),
                   "prefill_tok_s": round(pt / pre, 1) if pre > 0 else None,
                   "ok": True}
            rows.append(row)
            best = row
            print("  %5d 字 → prompt %6d tok · %7.2fs · prefill %6.1f tok/s"
                  % (n, pt, dt, (pt / pre) if pre > 0 else 0))
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:200]
            except Exception:                                     # noqa: BLE001
                pass
            rows.append({"chars": n, "ok": False, "http": exc.code, "error": body})
            print("  %5d 字 → HTTP %s %s（很可能是超窗）" % (n, exc.code, body[:120]))
            break                                     # 超窗后没必要再往上顶
        except Exception as exc:                                  # noqa: BLE001
            rows.append({"chars": n, "ok": False, "error": "%s: %s"
                         % (type(exc).__name__, exc)})
            print("  %5d 字 → %s: %s" % (n, type(exc).__name__, exc))
            break

    budget = None
    if best and best.get("prefill_tok_s"):
        budget = int(best["prefill_tok_s"] * a.window * 0.8)   # 留 20% 余量给生成
    res = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": model,
           "window_s": a.window, "rows": rows,
           "window_prompt_budget_tokens": budget}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)

    print("-" * 56)
    if budget:
        print("结论：%.0f 秒窗口内，这个容器最多吃 ~%d token 的 prompt（含 20%% 余量）"
              % (a.window, budget))
    else:
        print("结论：一个阶梯都没跑通 —— 容器不在或全超窗")
    print("落盘 %s" % OUT)
    return 0 if budget else 3


if __name__ == "__main__":
    sys.exit(main())
