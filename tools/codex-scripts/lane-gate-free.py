# -*- coding: utf-8 -*-
"""现役车道闸（免费道）—— 取代原先那条「云端秒级」闸。

## 为什么换（主人令 2026-10-24，逐字：「这个要花钱我们不需要直接清理了就没卡点了」）
旧闸 `lane-doctor check --gate` 判的是 **RunPod 自有权重车道**（G1–G10）。
该车道已按主人令**清理**（`ours` / `ours-alt` / `cloud` 三条已从桥里删除），
再拿它当闸 ⇒ 永远红、且红的原因已经不是"坏了"而是"不做了"。
**判据必须量在役的东西**，所以这条闸改成判**免费道**（Cloudflare Workers AI）。

## 判据（三条，全部机检）
L1 桥在役：`127.0.0.1:8791/health` 回 200，且 default 在免费道里（cfai/agnes）
L2 真出话：发一句 8 token 的请求，回包 200 且 content 非空，并带上 `lane/free` 印记
L3 明示口径：`weights_ours` 必须是 **false**（免费道不是我们自己的权重，不许糊）

退出码：全绿 0 / 有红 1；`--json` 给机读。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BRIDGE = "http://127.0.0.1:8791"
FREE_LANES = {"cfai", "agnes"}
PROMPT = "只回两个字：在线"


def _get(path, timeout=6):
    with urllib.request.urlopen(BRIDGE + path, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8", "replace"))


def _chat(timeout=90):
    body = json.dumps({"messages": [{"role": "user", "content": PROMPT}], "max_tokens": 8}).encode()
    req = urllib.request.Request(BRIDGE + "/v1/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
        return r.status, raw, dict(r.headers), round(time.perf_counter() - t0, 2)


def run() -> dict:
    checks = []
    try:
        st, h = _get("/health")
        default = str(h.get("default") or "")
        checks.append({"id": "L1", "name": "桥在役 · 默认是免费道", "ok": st == 200 and default in FREE_LANES,
                       "reading": "http=%s · default=%s" % (st, default or "(空)")})
    except Exception as exc:                                  # noqa: BLE001
        checks.append({"id": "L1", "name": "桥在役 · 默认是免费道", "ok": False,
                       "reading": "%s: %s" % (type(exc).__name__, str(exc)[:80])})
        return {"ok": False, "checks": checks, "note": "桥没起 ⇒ 后两条无从判"}

    try:
        st, raw, hdrs, dt = _chat()
        lane = hdrs.get("x-gbt-lane") or ""
        free = hdrs.get("x-gbt-free") or ""
        ours = hdrs.get("x-gbt-weights-ours") or ""
        text = ""
        try:
            d = json.loads(raw)
            text = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        except Exception:                                     # noqa: BLE001
            text = ""
        checks.append({"id": "L2", "name": "真出话（非空）", "ok": st == 200 and bool(str(text).strip()),
                       "reading": "http=%s · %.2fs · lane=%s · text=%r" % (st, dt, lane, str(text)[:30])})
        checks.append({"id": "L3", "name": "口径明示：免费道不是自有权重",
                       "ok": ours == "false" and free == "true",
                       "reading": "weights_ours=%s · free=%s" % (ours or "(缺)", free or "(缺)")})
    except Exception as exc:                                  # noqa: BLE001
        checks.append({"id": "L2", "name": "真出话（非空）", "ok": False,
                       "reading": "%s: %s" % (type(exc).__name__, str(exc)[:80])})
        checks.append({"id": "L3", "name": "口径明示：免费道不是自有权重", "ok": False, "reading": "未取到回包"})
    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "口径": "自有权重车道（RunPod）已按主人令 2026-10-24 清理；本闸只量在役的免费道"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = run()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        for c in r["checks"]:
            print("%s %-28s %s" % ("✅" if c["ok"] else "🔴", c["name"], c["reading"]))
        print("结论：%s" % ("免费道在役 · 全绿" if r["ok"] else "有红"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
