#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把一台已在跑的 TPU(vLLM TorchTPU) 服务**验活后**登记进车道表（只读探测 + 写本地登记）。

做四件事：
  ① GET `<base>/models` —— 必须 200 且含 model id；
  ② POST `<base>/chat/completions` 发一次 8 token —— 必须回非空文本；
  ③ 两步都过才写 `state/lane-backends.json` 的 `tpu-torchtpu`（enabled=true, priority=5, base_url_direct=你给的）；
  ④ 不碰任何云端、不碰 Worker（真切换走部署门 D5）。

用法：
  py -3.14 tools/model-bridge/tpu-register.py --base-url http://10.0.0.5:8000/v1 --model gbt-potato-v8
  py -3.14 tools/model-bridge/tpu-register.py --base-url ... --dry-run   # 只验活不写
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REG = os.path.join(ROOT, "state", "lane-backends.json")


def call(url, body=None, to=25):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdr = {"User-Agent": "gbt-tpu-register/1.0", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=hdr,
                                 method="POST" if body is not None else "GET")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=to) as r:
            return True, round((time.time() - t0) * 1000), r.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, round((time.time() - t0) * 1000), "HTTP %s: %s" % (
            e.code, e.read(400).decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return False, round((time.time() - t0) * 1000), "%s: %s" % (type(e).__name__, str(e)[:120])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", default="gbt-potato-v8")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    base = a.base_url.rstrip("/")
    if not base.startswith("http"):
        print("❌ --base-url 必须是 http(s) 开头")
        return 2

    print("① /models")
    ok, ms, txt = call(base + "/models")
    print("   %s (%dms) %s" % ("200" if ok else "失败", ms, txt[:200]))
    if not ok:
        print("   ⇒ 没起服务 / 地址不对 / 端口没开。先看 serve.sh 的日志。")
        return 1
    try:
        ids = [m.get("id") for m in (json.loads(txt).get("data") or [])]
    except ValueError:
        ids = []
    print("   模型: %s" % ids)
    if a.model not in ids:
        print("   ⚠️ 你给的 --model=%s 不在列表里（列表：%s）—— 登记时会用列表第一个" % (a.model, ids[:3]))
        a.model = ids[0] if ids else a.model

    print("② /chat/completions（8 token 探活）")
    ok2, ms2, txt2 = call(base + "/chat/completions",
                          {"model": a.model, "max_tokens": 8, "stream": False,
                           "messages": [{"role": "user", "content": "只回一个字母：A"}]}, to=120)
    text = ""
    if ok2:
        try:
            j = json.loads(txt2)
            text = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            usage = j.get("usage") or {}
        except ValueError:
            text = ""
            usage = {}
        print("   ✅ %dms · 回字=%r · usage=%s" % (ms2, text[:40], usage))
    else:
        print("   ❌ %dms · %s" % (ms2, txt2[:200]))
    if not ok2 or not text.strip():
        print("   ⇒ 服务在但不产字（可能是权重没加载完/编译中/显存或 HBM 不足）。**不登记**。")
        return 1

    if a.dry_run:
        print("\n（--dry-run：验活通过，但没写登记表）")
        return 0

    reg = json.load(open(REG, encoding="utf-8"))
    hit = False
    for b in reg.get("backends") or []:
        if b.get("id") == "tpu-torchtpu":
            b["base_url_direct"] = base
            b["model"] = a.model
            b["health"] = base + "/models"
            b["enabled"] = True
            b["priority"] = 5
            b["status_at_20261023"] = "alive: /models 200 · chat 8 token 回字 %r（%dms）" % (text[:20], ms2)
            hit = True
    if not hit:
        print("❌ lane-backends.json 里没有 tpu-torchtpu 这一条，先补登记再跑")
        return 2
    tmp = REG + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(reg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, REG)
    print("\n✅ 已登记并 enable：tpu-torchtpu → %s（priority=5）" % base)
    print("   下一步：py -3.14 tools/model-bridge/lane-failover.py --promote tpu-torchtpu")
    print("   注意：这只改本地登记/意图；Worker 上游要动仍走部署门 D5。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
