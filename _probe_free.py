# -*- coding: utf-8 -*-
"""免费车道探测器：逐个打免费模型，判断是否仍 429（Free usage limit reached）。

用法：
  pyembed\\python.exe -X utf8 _probe_free.py          # 探测并打印结果
  pyembed\\python.exe -X utf8 _probe_free.py --json   # 输出 JSON（供定时任务解析）
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SETTINGS = Path.home() / ".dsh" / "our-free-model" / "settings.json"
GATEWAY = "http://127.0.0.1:18899"


def load_key():
    s = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return s.get("forwardKey") or s.get("chanGateway", {}).get("relay", {}).get("key")


def models(key):
    req = urllib.request.Request(
        GATEWAY + "/v1/models",
        headers={"Authorization": "Bearer " + key},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        j = json.loads(r.read().decode("utf-8"))
    return [m["id"] for m in j.get("data", [])]


def probe(key, model):
    """返回 (state, detail)。state: available / throttled / error"""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        GATEWAY + "/v1/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read(2048)
            return "available", ""
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")[:400]
        if e.code == 429 or "Free usage limit" in raw or "quota" in raw.lower():
            return "throttled", raw
        return "error", "HTTP %d %s" % (e.code, raw)
    except Exception as exc:  # noqa: BLE001
        return "error", "%s: %s" % (type(exc).__name__, str(exc)[:200])


def main():
    key = load_key()
    if not key:
        print("未找到网关 key", file=sys.stderr)
        return 2
    try:
        ids = models(key)
    except Exception as exc:  # noqa: BLE001
        print("网关不可达：%s" % exc, file=sys.stderr)
        return 2

    # 只探真正独立的模型（带 provider 前缀的 kilo 车道 + opencode 裸 id），跳过 combo
    free = [m for m in ids
            if ("free" in m.lower() or m in ("big-pickle", "beam-free"))
            and not m.startswith("combo:")]
    results = {}
    any_ok = False
    for m in free:
        st, detail = probe(key, m)
        results[m] = {"state": st, "detail": detail[:160]}
        if st == "available":
            any_ok = True
        print("%-46s %s" % (m, st), flush=True)

    summary = {
        "probed": len(free),
        "available": [m for m, v in results.items() if v["state"] == "available"],
        "throttled": [m for m, v in results.items() if v["state"] == "throttled"],
        "error": [m for m, v in results.items() if v["state"] == "error"],
        "any_available": any_ok,
        "results": results,
    }
    if "--json" in sys.argv:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print("\n=== 汇总 ===")
        print("可用 %d / 限流 %d / 错误 %d" % (
            len(summary["available"]), len(summary["throttled"]), len(summary["error"])))
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(main())
