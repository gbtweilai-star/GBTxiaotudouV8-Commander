# -*- coding: utf-8 -*-
"""车道压测：打任何 OpenAI 兼容端点，量「首字延迟 / 吞吐 / 模型身份」。

为什么要有它：换车道（GPU→TPU→别的云）这件事，唯一能判"起来了没有"的就是这三项；
没有它们，谁都能说"接上了"。判据写死，不达标就非零退出。

用法：
  python tools/codex-scripts/lane-bench.py --base https://host/v1 --model gbt-potato-v8 --key-env GW_AUTH
  python tools/codex-scripts/lane-bench.py --selftest      # 离线自检（不联网）
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

# 判据（写死；改要留痕）
MIN_TPS = 20.0
MAX_FIRST_TOKEN_S = 2.0
PROMPTS = [
    "用一句话说明：你是谁、跑在哪。",
    "把这句话改得更口语化：本系统已完成部署。",
    "列出三件你今天能做的事，每行一件。",
]


def _post(url, payload, key, timeout):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", UA)
    if key:
        req.add_header("Authorization", "Bearer " + key)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return time.perf_counter() - t0, raw


def _parse_usage(raw):
    d = json.loads(raw.decode("utf-8", "replace"))
    usage = d.get("usage") or {}
    text = ""
    try:
        text = d["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        pass
    return usage.get("completion_tokens"), text, d


def run(args):
    key = os.environ.get(args.key_env, "") if args.key_env else ""
    if args.key_env and not key:
        print(json.dumps({"ok": False,
                          "why": "环境变量 %s 未配 ⇒ 端到端跑不了（这不是失败，是缺票）" % args.key_env},
                         ensure_ascii=False))
        return 2
    base = args.base.rstrip("/")
    url = base + "/chat/completions"

    # 先自证身份：/models 里有没有这个 model
    ident = None
    try:
        req = urllib.request.Request(base + "/models")
        req.add_header("User-Agent", UA)
        if key:
            req.add_header("Authorization", "Bearer " + key)
        with urllib.request.urlopen(req, timeout=args.timeout) as r:
            ident = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        ident = {"http_error": e.code, "body": e.read().decode("utf-8", "replace")[:200]}
    except OSError as e:
        ident = {"error": str(e)[:200]}

    lat, tps, rows = [], [], []
    for p in PROMPTS:
        payload = {"model": args.model, "messages": [{"role": "user", "content": p}],
                   "max_tokens": args.max_tokens}
        try:
            dt, raw = _post(url, payload, key, args.timeout)
            ctok, text, whole = _parse_usage(raw)
            t = (ctok / dt) if ctok else None
            lat.append(dt)
            if t:
                tps.append(t)
            rows.append({"prompt": p[:18], "secs": round(dt, 3),
                         "completion_tokens": ctok,
                         "tok_per_s": round(t, 2) if t else None,
                         "weight_flag": (whole.get("gbt") or {}).get("weights_ours"),
                         "reply_head": (text or "")[:40]})
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            rows.append({"prompt": p[:18], "http_error": e.code, "body": body})
        except OSError as e:
            rows.append({"prompt": p[:18], "error": str(e)[:200]})

    ok_rows = [r for r in rows if r.get("tok_per_s")]
    first = statistics.median(lat) if lat else None
    tps_med = statistics.median(tps) if tps else None
    weights_ours = [r.get("weight_flag") for r in ok_rows]
    verdict = {
        "ok": bool(ok_rows) and (first is not None and first <= MAX_FIRST_TOKEN_S)
              and (tps_med is not None and tps_med >= MIN_TPS),
        "first_token_s_p50": round(first, 3) if first else None,
        "tok_per_s_p50": round(tps_med, 2) if tps_med else None,
        "weights_ours": weights_ours,
        "gates": {"first_token<=%.1fs" % MAX_FIRST_TOKEN_S: (first is not None and first <= MAX_FIRST_TOKEN_S),
                  "tok_per_s>=%.0f" % MIN_TPS: (tps_med is not None and tps_med >= MIN_TPS)},
        "models_probe": ident,
        "rows": rows,
    }
    print(json.dumps(verdict, ensure_ascii=False, indent=1))
    return 0 if verdict["ok"] else 1


def selftest():
    """离线自检：判据函数在给定输入下的判决必须与预期一致（负对照也要响）。"""
    def judge(first, tps):
        return bool(first is not None and first <= MAX_FIRST_TOKEN_S
                    and tps is not None and tps >= MIN_TPS)
    cases = [((1.2, 30.0), True), ((3.0, 30.0), False), ((1.0, 5.0), False), ((None, 30.0), False)]
    bad = [c for c in cases if judge(*c[0]) != c[1]]
    print(json.dumps({"selftest_ok": not bad, "cases": len(cases),
                      "wrong": bad,
                      "gates": {"MAX_FIRST_TOKEN_S": MAX_FIRST_TOKEN_S, "MIN_TPS": MIN_TPS}},
                     ensure_ascii=False))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    ap.add_argument("--model", default="gbt-potato-v8")
    ap.add_argument("--key-env", default="GW_AUTH")
    ap.add_argument("--max-tokens", type=int, default=48)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.base:
        print(json.dumps({"ok": False, "why": "缺 --base（如 https://host/v1）"}, ensure_ascii=False))
        return 3
    return run(a)


if __name__ == "__main__":
    raise SystemExit(main())
