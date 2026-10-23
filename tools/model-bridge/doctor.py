# -*- coding: utf-8 -*-
"""一条命令体检「自有权重链路」—— 权重 / 服务 / 桥 / 车道 / 真答一轮。

为什么需要它：这条链路有好几处会「静默降级」（桥没车道 → 走云端、服务没起 → 走云端），
而回答看起来一模一样。所以判据必须是**回包里的 lane 与 weights_ours**，不是回答内容。

用法：
  python tools/model-bridge/doctor.py            # 只看状态（不发送对话）
  python tools/model-bridge/doctor.py --chat     # 真发一句，验车道与 weights_ours
退出码：0 = 全绿；2 = 有红。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GGUF = os.path.join(ROOT, "state", "weights", "gbt-v8-v82-q5_0.gguf")
LLM = "http://127.0.0.1:8792"
BRIDGE = "http://127.0.0.1:8791"

rows = []


def add(name, ok, detail):
    rows.append((name, ok, detail))
    print("  %s %-14s %s" % ("OK  " if ok else "FAIL", name, detail))


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post(url, body, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.headers), json.loads(r.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args()

    print("=== 自有权重链路体检 %s ===" % time.strftime("%Y-%m-%d %H:%M:%S"))

    # 1) 权重
    if os.path.exists(GGUF):
        mb = os.path.getsize(GGUF) / 1e6
        add("权重", True, "%s · %.0f MB" % (os.path.basename(GGUF), mb))
    else:
        add("权重", False, "缺 %s" % GGUF)

    # 2) 本机服务
    try:
        h = get(LLM + "/health")
        add("服务:8792", h.get("ok") is True,
            "eos=%s · n_ctx=%s" % (h.get("eos"), h.get("n_ctx")))
    except Exception as e:
        add("服务:8792", False, "连不上（%s）—— 在 APP 里打开会自动拉起" % type(e).__name__)

    # 3) 桥 + 车道
    lane_ok = False
    try:
        h = get(BRIDGE + "/health")
        ups = h.get("upstreams") or []
        sh = [u for u in ups if u.get("name") == "selfhost"]
        lane_ok = bool(sh and ":8792" in str(sh[0].get("base_url")))
        add("桥:8791", True, "上游 %d 条" % len(ups))
        add("selfhost车道", lane_ok,
            (sh[0].get("base_url") if sh else "不存在 → 会走云端"))
    except Exception as e:
        add("桥:8791", False, "连不上（%s）" % type(e).__name__)

    # 4) 真答一轮
    if a.chat and lane_ok:
        try:
            t0 = time.time()
            st, hd, j = post(BRIDGE + "/v1/chat/completions",
                             {"upstream": "selfhost",
                              "messages": [{"role": "user", "content": "中国的首都是哪里？"}],
                              "max_tokens": 24}, timeout=a.timeout)
            el = time.time() - t0
            g = j.get("gbt") or {}
            txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            ours = g.get("weights_ours") is True
            add("实走车道", ours, "lane=%s · weights_ours=%s" % (g.get("lane"), g.get("weights_ours")))
            add("回答", bool(txt.strip()), "%r · %.1fs" % (txt[:40], el))
        except Exception as e:
            add("真答一轮", False, "%s: %s" % (type(e).__name__, e))

    bad = [r for r in rows if not r[1]]
    print()
    print("判据 %d 项 · 红 %d 项" % (len(rows), len(bad)))
    return 2 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
